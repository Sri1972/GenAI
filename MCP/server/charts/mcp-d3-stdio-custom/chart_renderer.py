"""
================================================================================
Chart.js Fallback Renderer (Data Format Normalizer)
================================================================================

PURPOSE:
    This is the FALLBACK RENDERING ENGINE that provides Chart.js-based chart
    generation when D3 templates are unavailable or data format is incompatible.
    It also handles intelligent data format detection and normalization.

ARCHITECTURE ROLE:
    - **Layer 3 (Bottom)**: Data Processing & Fallback Rendering
    - Imported and used by d3_chart_api_server.py
    - Never directly called by d3_chart_mcp.py (top layer)
    - Provides Chart.js UMD as reliable fallback option

DEPENDENCIES:
    - **d3_chart_api_server.py** (Layer 2 - Caller)
      - IMPORTED BY: d3_chart_api_server.py
      - Functions used: render_chart_html_from_dataset(), extract_json_from_text()
    
    - External Libraries:
      - Chart.js (via CDN in generated HTML)
      - Standard Python libraries: json, re, pathlib, datetime, hashlib, os

KEY FUNCTIONS:
    1. render_chart_html_from_dataset(data_obj, title_text, chart_type)
       - Main entry point for Chart.js rendering
       - Normalizes various data formats into Chart.js format
       - Detects chart type from data structure if not specified
       - Returns complete HTML string with Chart.js embedded
    
    2. extract_json_from_text(text)
       - Extracts JSON from text/markdown with code blocks
       - Handles various JSON formatting issues
       - Used for parsing LLM-generated chart data
    
    3. _build_chartjs_html(chart_payload, title_text, chart_type)
       - Internal function to generate Chart.js HTML template
       - Embeds data as JSON in <script id="chart-data">
       - Uses Chart.js UMD build for reliability

DATA FORMAT DETECTION HEURISTICS:
    - Detects label fields: month, date, week, period, time
    - Detects name fields: project, name, title, project_name
    - Detects numeric fields automatically
    - Special handling for planned/actual budget fields
    - Converts to Chart.js format: {labels: [], datasets: [{data: []}]}

SUPPORTED INPUT FORMATS:
    1. Chart.js format: {labels: [], datasets: [{label, data, backgroundColor}]}
    2. Record arrays: [{month: "Jan", value: 100}, ...]
    3. Nested objects: {result: [{...}]}
    4. Project allocation: [{month, resource_id, project_allocation_details}]
    5. Simple arrays: [10, 20, 30, 40]

CHART TYPE DETECTION:
    - Auto-detects bar vs line based on data structure
    - Switches to bar when planned/actual fields present
    - Respects explicit chart_type hint parameter
    - Defaults to line chart when uncertain

OUTPUT:
    - Returns HTML string (not saved to file)
    - d3_chart_api_server.py handles file saving
    - HTML contains standalone Chart.js visualization
    - Can be opened directly in browser

USAGE PATTERN:
    Called by d3_chart_api_server.py when:
    1. D3 template fails or unavailable
    2. Data format needs normalization
    3. Simple charts don't require D3 complexity
    4. Fallback needed for reliability

WHY CHART.JS FALLBACK?
    - More forgiving with data formats
    - Easier to debug and maintain
    - Good default for simple charts
    - Reliable when D3 templates incomplete

================================================================================
"""

import json
import re
from pathlib import Path
from datetime import datetime
import hashlib
import os

# ================================================================================
# LIBRARY PATHS - Local files with CDN fallback
# ================================================================================
CHARTJS_LOCAL_PATH = '../scripts/chart_js/chart.umd.min.js'
CHARTJS_CDN_URL = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js'
CHARTJS_DATALABELS_LOCAL_PATH = '../scripts/chart_js/chartjs-plugin-datalabels.min.js'
CHARTJS_DATALABELS_CDN_URL = 'https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js'

CHARTJS_SCRIPT_TAG = f"<script src='{CHARTJS_LOCAL_PATH}' onerror=\"this.onerror=null; this.src='{CHARTJS_CDN_URL}';\"></script>"
CHARTJS_DATALABELS_SCRIPT_TAG = f"<script src='{CHARTJS_DATALABELS_LOCAL_PATH}' onerror=\"this.onerror=null; this.src='{CHARTJS_DATALABELS_CDN_URL}';\"></script>"

# ================================================================================


def render_chart_html_from_dataset(data_obj, title_text: str = "Chart", chart_type: str | None = None) -> str:
    """Render a Chart.js HTML page from a normalized dataset object.
    data_obj can be: {'labels':[], 'datasets':[...]} or a dict with 'result' list or list of records.
    Returns full HTML string embedding JSON in <script id="chart-data"> and initializing Chart.js UMD.
    """
    # Normalize records
    records = []
    if isinstance(data_obj, dict) and 'result' in data_obj:
        records = data_obj.get('result') or []
    elif isinstance(data_obj, list):
        records = data_obj
    elif isinstance(data_obj, dict):
        # try to find inner list
        for v in data_obj.values():
            if isinstance(v, list):
                records = v
                break
    records = [r for r in records if isinstance(r, dict)]

    # If data_obj already looks like labels/datasets, use it directly
    if isinstance(data_obj, dict) and 'labels' in data_obj and 'datasets' in data_obj:
        chart_payload = {'labels': data_obj['labels'], 'datasets': data_obj['datasets']}
        # allow chart_type hint
        ct = chart_type or 'line'
        return _build_chartjs_html(chart_payload, title_text, ct)

    # Heuristics to construct labels/datasets from records
    label_field = None
    numeric_fields = []
    name_field = None
    if records:
        sample = records[0]
        for k in sample.keys():
            lk = k.lower()
            if any(x in lk for x in ("month", "date", "week", "period", "time")):
                label_field = k
                break
        for k in sample.keys():
            lk = k.lower()
            if any(x in lk for x in ("project", "name", "title", "project_name")) and isinstance(sample.get(k), str):
                name_field = k
                break
        for k, v in sample.items():
            if k == label_field:
                continue
            lk = k.lower()
            if any(sub in lk for sub in ("cumul", "cumulative", "running_total", "total")):
                continue
            if isinstance(v, (int, float)):
                numeric_fields.append(k)

    labels = []
    datasets = []
    # Normalize explicit hint and treat it as authoritative if provided.
    chart_t = None
    hint_flag = False
    if chart_type:
        try:
            ct = str(chart_type).strip().lower()
        except Exception:
            ct = None
        if ct in ('donut', 'doughnut'):
            chart_t = 'doughnut'
        elif ct in ('pie', 'bar', 'line', 'doughnut'):
            chart_t = ct
        else:
            chart_t = ct or 'line'
        hint_flag = True
    else:
        chart_t = 'line'

    # Project-mode grouped bars if we have a project/name label and planned/actual-like numeric fields
    planned_keys = []
    actual_keys = []
    if records and name_field:
        for k in records[0].keys():
            lk = k.lower()
            if re.search(r'planned|plan|budget', lk):
                planned_keys.append(k)
            if re.search(r'actual|spent|spent_amount|cost|expense', lk):
                actual_keys.append(k)
        # Only switch to bar when there are planned/actual keys AND there was no explicit hint
        if (planned_keys or actual_keys) and not hint_flag:
            chart_t = 'bar'
            labels = [str(r.get(name_field, '')) for r in records]
            def extract_vals(keys):
                vals = []
                for r in records:
                    v = None
                    for k in keys:
                        if k in r and r.get(k) not in (None, ''):
                            v = r.get(k)
                            break
                    try:
                        vals.append(float(v) if v is not None else 0.0)
                    except Exception:
                        vals.append(0.0)
                return vals
            palette = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd"]
            if planned_keys:
                datasets.append({"label": "Planned", "data": extract_vals(planned_keys), "backgroundColor": palette[0], "borderColor": palette[0]})
            if actual_keys:
                datasets.append({"label": "Actual", "data": extract_vals(actual_keys), "backgroundColor": palette[1], "borderColor": palette[1]})
            if not datasets and numeric_fields:
                for idx, f in enumerate(numeric_fields):
                    vals = []
                    for r in records:
                        try:
                            vals.append(float(r.get(f, 0) if r.get(f) is not None else 0)
                            )
                        except Exception:
                            vals.append(0)
                    color = palette[idx % len(palette)]
                    datasets.append({"label": f, "data": vals, "backgroundColor": color, "borderColor": color})

    # Pie/doughnut detection: single numeric field per categorical label -> render a pie
    if chart_t == 'line' and records:
        def _is_time_like(key):
            return key and any(x in key.lower() for x in ("month", "date", "week", "period", "time"))

        category_field = name_field or label_field
        if not category_field:
            for k, v in records[0].items():
                if isinstance(v, str) and not _is_time_like(k):
                    category_field = k
                    break

        candidate_numeric_fields = []
        if category_field:
            for k, v in records[0].items():
                if k == category_field:
                    continue
                try:
                    if isinstance(v, (int, float)):
                        candidate_numeric_fields.append(k)
                    elif isinstance(v, str) and re.match(r'^[\d,\.\-\s]+$', v.strip()):
                        candidate_numeric_fields.append(k)
                except Exception:
                    pass

            if len(candidate_numeric_fields) == 1 and not hint_flag:
                num_key = candidate_numeric_fields[0]
                chart_t = 'pie'
                labels = [str(r.get(category_field, '')) for r in records]
                vals = []
                for r in records:
                    try:
                        raw = r.get(num_key, 0)
                        if raw is None:
                            raw = 0
                        vals.append(float(re.sub(r'[^0-9.\-]', '', str(raw)) or 0))
                    except Exception:
                        vals.append(0)
                palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]
                bg_colors = [palette[i % len(palette)] for i in range(len(labels))]
                datasets.append({"label": num_key, "data": vals, "backgroundColor": bg_colors, "borderColor": bg_colors})

    # Time-series / multi-line fallback
    if chart_t == 'line':
        if records:
            for r in records:
                labels.append(str(r.get(label_field)) if label_field and label_field in r else '')
            if not numeric_fields and records:
                sample = records[0]
                for k, v in sample.items():
                    if k == label_field:
                        continue
                    try:
                        vals = [float(rr.get(k, 0) or 0) for rr in records]
                        if any(vv != 0 for vv in vals):
                            numeric_fields.append(k)
                    except Exception:
                        pass
            palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]
            for idx, f in enumerate(numeric_fields):
                vals = []
                for r in records:
                    try:
                        v = r.get(f, None)
                        vals.append(float(v) if v is not None else None)
                    except Exception:
                        vals.append(None)
                color = palette[idx % len(palette)]
                datasets.append({"label": f, "data": vals, "borderColor": color, "backgroundColor": color, "fill": False})

    if not datasets:
        labels = labels or ["x"]
        datasets = [{"label": "value", "data": [0 for _ in labels], "borderColor": "#777", "backgroundColor": "#bbb"}]

    chart_payload = {"labels": labels, "datasets": datasets}
    return _build_chartjs_html(chart_payload, title_text, chart_t)


def _build_chartjs_html(chart_payload, title_text, chart_type):
    template = """<!doctype html>
<html>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>__TITLE__</title>
""" + CHARTJS_SCRIPT_TAG + """
""" + CHARTJS_DATALABELS_SCRIPT_TAG + """
<style>
body{font-family:Segoe UI,Arial,sans-serif;margin:0;padding:0;background:#f5f5f5;box-sizing:border-box}
.container{width:100vw;margin:0;background:#fff;padding:20px;box-sizing:border-box}
.summary-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:24px}
.summary-card{background:#f8f9fa;border:1px solid #dee2e6;border-radius:8px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,0.05)}
.summary-label{font-size:13px;color:#6c757d;font-weight:500;margin-bottom:4px}
.summary-value{font-size:24px;font-weight:700;color:#212529}
.chart-wrap{position:relative;height:520px;padding:10px}
canvas{width:100% !important;height:100% !important}
.legend{margin-top:20px;padding-top:15px;border-top:1px solid #e0e0e0;display:flex;flex-wrap:wrap;gap:8px;justify-content:center;max-width:100%;overflow:visible}
.legend-item{display:flex;gap:8px;align-items:center;padding:6px 10px;border-radius:6px;color:#222;white-space:nowrap}
.sw{width:14px;height:14px;border-radius:3px;display:inline-block;flex-shrink:0}
.info{font-size:13px;color:#666;text-align:center;margin-top:10px}
.export-btn{position:fixed;top:20px;right:20px;padding:10px 16px;background:#0066cc;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:14px;font-weight:500;box-shadow:0 2px 8px rgba(0,0,0,0.15);transition:all 0.2s;z-index:1000}
.export-btn:hover{background:#0052a3;box-shadow:0 4px 12px rgba(0,0,0,0.2)}
.export-btn:active{transform:scale(0.98)}
.export-btn:disabled{background:#ccc;cursor:not-allowed}
.toast{position:fixed;top:80px;right:20px;padding:12px 20px;background:#28a745;color:#fff;border-radius:6px;box-shadow:0 4px 12px rgba(0,0,0,0.2);font-size:14px;opacity:0;transition:opacity 0.3s;pointer-events:none;z-index:1001}
.toast.show{opacity:1}
@media print{.export-btn,.toast{display:none !important}}
.screenshot-mode .export-btn,.screenshot-mode .toast{display:none !important}
h2{margin-top:60px}
</style>
</head>
<body>
<div class='container'>
<button class='export-btn' id='copyChartBtn' title='Copy chart as image to clipboard'>📋 Copy Chart</button>
<div class='toast' id='toast'>Copied to clipboard!</div>
<h2>__TITLE__</h2>
<div id='summary' class='summary-grid'></div>
<div class='chart-wrap'>
<canvas id='hoursChart'></canvas>
</div>
<div id='legend' class='legend' aria-hidden='false'></div>
<div class='info'>Generated from PMO data</div>
</div>
<script id='chart-data' type='application/json'>
__CHART_PAYLOAD__
</script>
        <script>
// Common utility functions for building summary panels and legends (works with D3 or Chart.js)
function buildSummaryPanel(datasets, summaryElementId) {
  var summaryEl = document.getElementById(summaryElementId || 'summary');
  if (!summaryEl) return;
  summaryEl.innerHTML = '';
  
  var grandTotal = 0;
  datasets.forEach(function(ds) {
    var data = ds.data || [];
    data.forEach(function(v) {
      var num = typeof v === 'number' ? v : (typeof v === 'object' && v.y != null ? v.y : 0);
      grandTotal += num;
    });
  });
  
  if (grandTotal > 0) {
    var totalCard = document.createElement('div');
    totalCard.style.background = '#e7f3ff';
    totalCard.style.border = '2px solid #0d6efd';
    totalCard.style.borderRadius = '8px';
    totalCard.style.padding = '16px';
    totalCard.style.textAlign = 'center';
    totalCard.style.gridColumn = '1 / -1';
    
    var totalLabel = document.createElement('div');
    totalLabel.style.fontSize = '13px';
    totalLabel.style.fontWeight = '600';
    totalLabel.style.color = '#495057';
    totalLabel.textContent = 'Total';
    
    var totalValue = document.createElement('div');
    totalValue.style.fontSize = '28px';
    totalValue.style.fontWeight = '700';
    totalValue.style.color = '#0d6efd';
    totalValue.textContent = Math.round(grandTotal).toLocaleString();
    
    totalCard.appendChild(totalLabel);
    totalCard.appendChild(totalValue);
    summaryEl.appendChild(totalCard);
    
    datasets.forEach(function(ds, idx) {
      var dsTotal = 0;
      var data = ds.data || [];
      data.forEach(function(v) {
        var num = typeof v === 'number' ? v : (typeof v === 'object' && v.y != null ? v.y : 0);
        dsTotal += num;
      });
      
      if (dsTotal > 0) {
        var card = document.createElement('div');
        card.style.background = '#f8f9fa';
        card.style.border = '1px solid #dee2e6';
        card.style.borderRadius = '6px';
        card.style.padding = '12px';
        
        var cardLabel = document.createElement('div');
        cardLabel.style.fontSize = '12px';
        cardLabel.style.color = '#6c757d';
        cardLabel.style.fontWeight = '500';
        cardLabel.style.marginBottom = '4px';
        cardLabel.textContent = ds.label || 'Dataset ' + (idx + 1);
        
        var cardValue = document.createElement('div');
        cardValue.style.fontSize = '20px';
        cardValue.style.fontWeight = '700';
        cardValue.style.color = '#212529';
        cardValue.textContent = Math.round(dsTotal).toLocaleString();
        
        card.appendChild(cardLabel);
        card.appendChild(cardValue);
        summaryEl.appendChild(card);
      }
    });
  }
}

function buildLegend(datasets, labels, legendElementId) {
  var legendEl = document.getElementById(legendElementId || 'legend');
  if (!legendEl) return;
  legendEl.innerHTML = '';
  
  datasets.forEach(function(ds) {
    var total = 0;
    var data = ds.data || [];
    data.forEach(function(v) {
      var num = typeof v === 'number' ? v : (typeof v === 'object' && v.y != null ? v.y : 0);
      if (!isNaN(num)) total += num;
    });
    
    var item = document.createElement('div');
    item.className = 'legend-item';
    
    var sw = document.createElement('div');
    sw.className = 'sw';
    sw.style.background = (ds.backgroundColor || ds.borderColor || '#777');
    
    var textDiv = document.createElement('div');
    textDiv.textContent = (ds.label || 'Series') + ' - ' + Math.round(total).toLocaleString();
    
    item.appendChild(sw);
    item.appendChild(textDiv);
    legendEl.appendChild(item);
  });
}

function buildHierarchicalLegend(payload, legendElementId) {
  var legendEl = document.getElementById(legendElementId || 'legend');
  if (!legendEl) return;
  legendEl.innerHTML = '';
  
  // Change legend layout to grid
  legendEl.style.display = 'grid';
  legendEl.style.gridTemplateColumns = 'repeat(auto-fit, minmax(350px, 1fr))';
  legendEl.style.gap = '16px';
  
  var labels = payload.labels || [];
  var datasets = payload.datasets || [];
  
  // Parse labels for hierarchy
  var parsedLabels = labels.map(function(label, idx) {
    var parts = label.split(' - ');
    if (parts.length > 1) {
      return {level1: parts[0].trim(), level2: parts.slice(1).join(' - ').trim(), original: label, index: idx};
    }
    return {level1: label, level2: null, original: label, index: idx};
  });
  
  // Group by level1
  var level1Groups = {};
  parsedLabels.forEach(function(parsed) {
    if (!level1Groups[parsed.level1]) {
      level1Groups[parsed.level1] = [];
    }
    level1Groups[parsed.level1].push(parsed);
  });
  
  // Build legend hierarchy
  Object.keys(level1Groups).forEach(function(level1Item) {
    var level1Items = level1Groups[level1Item];
    
    // Calculate level1 total and organize by level2
    var level1Total = 0;
    var level2Items = {};
    
    level1Items.forEach(function(item) {
      var level2Item = item.level2 || 'Main';
      if (!level2Items[level2Item]) {
        level2Items[level2Item] = [];
      }
      
      datasets.forEach(function(ds) {
        var value = ds.data[item.index] || 0;
        if (value > 0) {
          level1Total += value;
          level2Items[level2Item].push({
            name: ds.label,
            value: value,
            color: ds.backgroundColor || ds.borderColor || '#777'
          });
        }
      });
    });
    
    if (level1Total === 0) return;
    
    // Create level1 container
    var level1Container = document.createElement('div');
    level1Container.style.background = '#f8f9fa';
    level1Container.style.border = '1px solid #dee2e6';
    level1Container.style.borderRadius = '6px';
    level1Container.style.padding = '12px';
    
    // Level 1 header
    var level1Header = document.createElement('div');
    level1Header.style.fontWeight = '700';
    level1Header.style.fontSize = '14px';
    level1Header.style.marginBottom = '8px';
    level1Header.style.color = '#212529';
    level1Header.textContent = level1Item + ' - $' + Math.round(level1Total).toLocaleString();
    level1Container.appendChild(level1Header);
    
    // Level 2 items and Level 3 data under level1
    Object.keys(level2Items).forEach(function(level2Item) {
      var dataItems = level2Items[level2Item];
      if (dataItems.length === 0) return;
      
      var level2Total = dataItems.reduce(function(sum, p) { return sum + p.value; }, 0);
      
      // Level 2 header
      var level2Header = document.createElement('div');
      level2Header.style.paddingLeft = '12px';
      level2Header.style.fontWeight = '600';
      level2Header.style.fontSize = '13px';
      level2Header.style.color = '#495057';
      level2Header.style.marginTop = '6px';
      level2Header.style.marginBottom = '4px';
      level2Header.textContent = level2Item + ' - $' + Math.round(level2Total).toLocaleString();
      level1Container.appendChild(level2Header);
      
      // Level 3 data under Level 2 (show top 5)
      var topItems = dataItems.sort(function(a, b) { return b.value - a.value; }).slice(0, 5);
      topItems.forEach(function(dataItem) {
        var level3Item = document.createElement('div');
        level3Item.style.paddingLeft = '24px';
        level3Item.style.display = 'flex';
        level3Item.style.alignItems = 'center';
        level3Item.style.gap = '8px';
        level3Item.style.margin = '2px 0';
        level3Item.style.fontSize = '12px';
        level3Item.style.color = '#6c757d';
        
        var colorSwatch = document.createElement('div');
        colorSwatch.className = 'sw';
        colorSwatch.style.background = dataItem.color;
        
        var textDiv = document.createElement('div');
        textDiv.textContent = dataItem.name + ' - $' + Math.round(dataItem.value).toLocaleString();
        
        level3Item.appendChild(colorSwatch);
        level3Item.appendChild(textDiv);
        level1Container.appendChild(level3Item);
      });
    });
    
    legendEl.appendChild(level1Container);
  });
}

function buildHierarchicalSummary(payload, summaryElementId) {
  var summaryEl = document.getElementById(summaryElementId || 'summary');
  if (!summaryEl) return;
  summaryEl.innerHTML = '';
  
  var labels = payload.labels || [];
  var datasets = payload.datasets || [];
  
  // Extract level names from title (e.g., "Costs by Portfolio and Product Line")
  var level1Name = 'Items';
  var level2Name = 'Sub-items';
  
  var title = payload.title || '';
  var byMatch = title.match(/\\s+by\\s+(.+?)$/i);
  if (byMatch) {
    var entitiesStr = byMatch[1];
    var entityWords = entitiesStr.split(/\\s+and\\s+|\\s*,\\s*|\\s*&\\s*/i).map(function(w){ return w.trim(); }).filter(function(w){ return w; });
    
    if (entityWords.length >= 1) {
      var firstEntity = entityWords[0].trim();
      firstEntity = firstEntity.split(/\\s+/).map(function(w){ return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase(); }).join(' ');
      level1Name = firstEntity.endsWith('s') ? firstEntity : firstEntity + 's';
    }
    
    if (entityWords.length >= 2) {
      var secondEntity = entityWords[1].trim();
      secondEntity = secondEntity.split(/\\s+/).map(function(w){ return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase(); }).join(' ');
      level2Name = secondEntity.endsWith('s') ? secondEntity : secondEntity + 's';
    }
  }
  
  // Group data by level1 (parse labels to extract level1 items like "Market & Sell")
  var level1Groups = {};
  
  labels.forEach(function(label, labelIdx) {
    // Parse label to extract level1 (split by " - " delimiter)
    // Example: "Market & Sell - PAS" -> level1="Market & Sell", level2FromLabel="PAS"
    var parts = label.split(' - ');
    var level1Item = parts.length > 1 ? parts[0].trim() : label;
    var level2FromLabel = parts.length > 1 ? parts.slice(1).join(' - ').trim() : null;
    
    if (!level1Groups[level1Item]) {
      level1Groups[level1Item] = {total: 0, level2Items: {}};
    }
    
    // Each dataset represents a level3 item (project), level2 comes from label
    datasets.forEach(function(ds) {
      var value = ds.data[labelIdx] || 0;
      if (value > 0) {
        level1Groups[level1Item].total += value;
        
        // Use level2 from label if available, otherwise use dataset label as level2
        var level2Item = level2FromLabel || ds.label;
        if (!level1Groups[level1Item].level2Items[level2Item]) {
          level1Groups[level1Item].level2Items[level2Item] = {total: 0, projects: {}};
        }
        level1Groups[level1Item].level2Items[level2Item].total += value;
        
        // Add project (dataset) under level2
        var projectName = ds.label;
        if (!level1Groups[level1Item].level2Items[level2Item].projects[projectName]) {
          level1Groups[level1Item].level2Items[level2Item].projects[projectName] = 0;
        }
        level1Groups[level1Item].level2Items[level2Item].projects[projectName] += value;
      }
    });
  });
  
  // Calculate grand total
  var grandTotal = 0;
  Object.keys(level1Groups).forEach(function(key) {
    grandTotal += level1Groups[key].total;
  });
  
  // Build Level 1 cards (Portfolios)
  Object.keys(level1Groups).forEach(function(level1Item) {
    var level1Data = level1Groups[level1Item];
    if (level1Data.total === 0) return;
    
    var card1 = document.createElement('div');
    card1.style.background = '#f8f9fa';
    card1.style.border = '2px solid #dee2e6';
    card1.style.borderRadius = '8px';
    card1.style.padding = '16px';
    card1.style.marginBottom = '16px';
    
    var level1Label = document.createElement('div');
    level1Label.style.fontSize = '16px';
    level1Label.style.fontWeight = '700';
    level1Label.style.color = '#212529';
    level1Label.style.marginBottom = '8px';
    level1Label.textContent = level1Item;
    
    var level1Value = document.createElement('div');
    level1Value.style.fontSize = '20px';
    level1Value.style.fontWeight = '700';
    level1Value.style.color = '#0d6efd';
    level1Value.style.marginBottom = '12px';
    level1Value.textContent = '$' + Math.round(level1Data.total).toLocaleString();
    
    card1.appendChild(level1Label);
    card1.appendChild(level1Value);
    
    // Build Level 2 cards (Product Lines) under Level 1
    Object.keys(level1Data.level2Items).forEach(function(level2Item) {
      var level2Data = level1Data.level2Items[level2Item];
      var level2Total = level2Data.total;
      if (level2Total === 0) return;
      
      var card2 = document.createElement('div');
      card2.style.background = '#fff';
      card2.style.borderLeft = '3px solid #0d6efd';
      card2.style.padding = '12px';
      card2.style.margin = '8px 0';
      card2.style.borderRadius = '4px';
      
      var level2Label = document.createElement('div');
      level2Label.style.fontSize = '14px';
      level2Label.style.fontWeight = '600';
      level2Label.style.color = '#495057';
      level2Label.style.marginBottom = '8px';
      level2Label.textContent = level2Item + ' - $' + Math.round(level2Total).toLocaleString();
      card2.appendChild(level2Label);
      
      // Build Level 3 cards (Projects) under Level 2
      Object.keys(level2Data.projects).forEach(function(projectName) {
        var projectValue = level2Data.projects[projectName];
        if (projectValue === 0) return;
        
        var card3 = document.createElement('div');
        card3.style.background = '#f8f9fa';
        card3.style.borderLeft = '2px solid #6c757d';
        card3.style.padding = '8px';
        card3.style.marginLeft = '12px';
        card3.style.marginTop = '4px';
        card3.style.borderRadius = '3px';
        
        var projectLabel = document.createElement('div');
        projectLabel.style.fontSize = '12px';
        projectLabel.style.color = '#6c757d';
        projectLabel.textContent = projectName + ': $' + Math.round(projectValue).toLocaleString();
        
        card3.appendChild(projectLabel);
        card2.appendChild(card3);
      });
      
      card1.appendChild(card2);
    });
    
    summaryEl.appendChild(card1);
  });
  
  // Add grand total card at the end
  if (grandTotal > 0) {
    var totalCard = document.createElement('div');
    totalCard.style.background = '#e7f3ff';
    totalCard.style.border = '2px solid #0d6efd';
    totalCard.style.borderRadius = '8px';
    totalCard.style.padding = '12px';
    totalCard.style.textAlign = 'center';
    
    var totalLabel = document.createElement('div');
    totalLabel.style.fontSize = '12px';
    totalLabel.style.fontWeight = '600';
    totalLabel.style.color = '#495057';
    totalLabel.textContent = 'Total';
    
    var totalValue = document.createElement('div');
    totalValue.style.fontSize = '20px';
    totalValue.style.fontWeight = '700';
    totalValue.style.color = '#0d6efd';
    totalValue.textContent = '$' + Math.round(grandTotal).toLocaleString();
    
    totalCard.appendChild(totalLabel);
    totalCard.appendChild(totalValue);
    summaryEl.appendChild(totalCard);
  }
}

(function(){
    try{
        var chartType = '__CHART_TYPE__';
        // Accept common synonyms and normalize to Chart.js expected types
        if (chartType === 'donut') chartType = 'doughnut';
        if (!chartType) chartType = 'line';
    var payload = JSON.parse(document.getElementById('chart-data').textContent || '{}');
    payload.datasets = payload.datasets || [];
    payload.datasets.forEach(function(ds){
            ds.data = (ds.data || []).map(function(v){ if (v === null || v === undefined) return 0; if (typeof v === 'number') return v; var n = Number(String(v).replace(/[^0-9.\-]/g, '')); return Number.isFinite(n) ? n : 0; });
            ds.backgroundColor = ds.backgroundColor || ds.borderColor || '#777';
            ds.borderColor = ds.borderColor || ds.backgroundColor;
            ds.borderWidth = ds.borderWidth != null ? ds.borderWidth : 2;
            // make lines and points more visible by default
            if (ds.pointRadius == null) ds.pointRadius = 3;
            if (ds.tension == null) ds.tension = 0.35;
    });

    // Build summary and legend - use hierarchical versions for grouped/multi bar charts
    if (chartType === 'bar' && payload.datasets && payload.datasets.length > 1) {
        buildHierarchicalSummary(payload, 'summary');
        buildHierarchicalLegend(payload, 'legend');
    } else {
        buildSummaryPanel(payload.datasets, 'summary');
        buildLegend(payload.datasets, payload.labels, 'legend');
    }

    var ctx = document.getElementById('hoursChart').getContext('2d');
        
        // Helper function for wrapping long labels
        function wrapLabel(label, maxLength) {
            if (typeof label === 'string' && label.length > maxLength) {
                var words = label.split(' ');
                var lines = [];
                var currentLine = '';
                words.forEach(function(word) {
                    if ((currentLine + ' ' + word).length > maxLength) {
                        if (currentLine) lines.push(currentLine);
                        currentLine = word;
                    } else {
                        currentLine = currentLine ? currentLine + ' ' + word : word;
                    }
                });
                if (currentLine) lines.push(currentLine);
                return lines;
            }
            return label;
        }
        
        var opts = {
            responsive: true,
            maintainAspectRatio: false,
            scales: { 
                y: { 
                    beginAtZero: true,
                    ticks: {
                        callback: function(value, index, ticks) {
                            return wrapLabel(this.getLabelForValue(value), 15);
                        }
                    }
                },
                x: {
                    ticks: {
                        callback: function(value, index, ticks) {
                            return wrapLabel(this.getLabelForValue(value), 15);
                        },
                        maxRotation: 0,
                        minRotation: 0
                    }
                }
            },
            plugins: { 
                legend: { display: false },
                datalabels: {
                    display: true,
                    color: '#444',
                    font: { weight: 'bold', size: 11 },
                    formatter: function(value, context) {
                        if (chartType === 'pie' || chartType === 'doughnut') {
                            return value > 0 ? value.toLocaleString() : '';
                        }
                        // For line/bar charts, show label on every point/bar
                        return value > 0 ? value.toLocaleString() : '';
                    },
                    anchor: 'end',
                    align: 'top',
                    offset: 4
                },
                tooltip: {
                    enabled: true,
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#fff',
                    bodyColor: '#fff',
                    borderColor: '#666',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: true,
                    callbacks: {
                        label: function(context) {
                            var label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            label += context.parsed.y != null ? context.parsed.y.toLocaleString() + ' hrs' : '';
                            return label;
                        },
                        title: function(context) {
                            return context[0].label || '';
                        }
                    }
                }
            },
            elements: {
                point: { radius: 4, hoverRadius: 6 },
                line: { tension: 0.35, borderWidth: 2 }
            }
        };
    if (chartType === 'bar') opts.scales.x = { stacked: false };

        try{ 
            Chart.register(ChartDataLabels);
            new Chart(ctx, { type: chartType, data: payload, options: opts }); 
        }catch(e){
            console.error('Chart init error', e);
            // visible in-page error banner for easier debugging when running headless or in screenshots
            try{
                var err = document.createElement('div');
                err.style.background = '#fee'; err.style.color = '#900'; err.style.padding = '12px'; err.style.border = '1px solid #f99'; err.style.margin = '8px'; err.style.borderRadius = '6px'; err.style.fontFamily='monospace';
                err.textContent = 'Chart init error: ' + (e && e.message ? e.message : String(e));
                document.body.insertBefore(err, document.body.firstChild);
            }catch(_){}
        }

  }catch(e){ console.error('render error', e); }
})();

// Copy chart to clipboard functionality for Chart.js
async function copyChartToClipboard() {
  const btn = document.getElementById('copyChartBtn');
  const toast = document.getElementById('toast');
  
  try {
    btn.disabled = true;
    btn.textContent = '⏳ Copying...';
    
    // Hide button and toast during capture
    const container = document.querySelector('.container');
    container.classList.add('screenshot-mode');
    
    // Wait a moment for CSS to apply
    await new Promise(resolve => setTimeout(resolve, 100));
    
    // Use html2canvas to capture entire container (summary + chart + legend)
    // Try loading from local file first, fallback to CDN if needed
    let html2canvas;
    try {
      const module = await import('../scripts/html2canvas/html2canvas.min.js');
      html2canvas = module.default || window.html2canvas;
    } catch (e) {
      // Fallback to CDN if local file fails
      const module = await import('https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/+esm');
      html2canvas = module.default;
    }
    const canvas = await html2canvas(container, {
      backgroundColor: '#ffffff',
      scale: 2,
      logging: false,
      windowWidth: container.scrollWidth,
      windowHeight: container.scrollHeight
    });
    
    // Show button again
    container.classList.remove('screenshot-mode');
    
    // Convert canvas to blob and copy to clipboard
    await new Promise((resolve, reject) => {
      canvas.toBlob(async (blob) => {
        try {
          await navigator.clipboard.write([
            new ClipboardItem({ 'image/png': blob })
          ]);
          toast.textContent = '✓ Copied to clipboard!';
          toast.classList.add('show');
          setTimeout(() => toast.classList.remove('show'), 2000);
          resolve();
        } catch (err) {
          reject(err);
        }
      }, 'image/png');
    });
    
  } catch (err) {
    console.error('Copy failed:', err);
    document.querySelector('.container').classList.remove('screenshot-mode');
    toast.textContent = '✗ Copy failed: ' + err.message;
    toast.style.background = '#dc3545';
    toast.classList.add('show');
    setTimeout(() => {
      toast.classList.remove('show');
      toast.style.background = '#28a745';
    }, 3000);
  } finally {
    btn.disabled = false;
    btn.textContent = '📋 Copy Chart';
  }
}

document.getElementById('copyChartBtn').addEventListener('click', copyChartToClipboard);
</script>
<details style="margin:12px 20px;padding:10px;border-radius:6px;background:#fff;border:1px solid #eee;max-width:1100px">
    <summary style="font-weight:600">Debug: embedded chart payload (click to expand)</summary>
    <pre style="white-space:pre-wrap;word-break:break-word;padding:8px;margin:8px;background:#fafafa;border-radius:4px;border:1px solid #efefef">__CHART_PAYLOAD__</pre>
</details>
</body>
</html>"""

    # Add title to payload for hierarchical summary to parse entity names
    chart_payload_with_title = chart_payload.copy() if isinstance(chart_payload, dict) else chart_payload
    if isinstance(chart_payload_with_title, dict):
        chart_payload_with_title['title'] = title_text
    
    html = template.replace('__TITLE__', str(title_text)).replace('__CHART_PAYLOAD__', json.dumps(chart_payload_with_title)).replace('__CHART_TYPE__', chart_type)
    # If user requested a D3-style donut/pie, provide an alternative D3-based template
    if chart_type in ('donut', 'doughnut', 'pie'):
        d3_template = """<!doctype html>
<html>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>__TITLE__</title>
<script src='https://d3js.org/d3.v7.min.js'></script>
<style>
body{font-family:Segoe UI,Arial,sans-serif;margin:20px;background:#f5f5f5}
.container{max-width:900px;margin:0 auto;background:#fff;padding:20px;border-radius:8px}
.chart-wrap{display:flex;justify-content:center;align-items:center}
.legend{display:flex;flex-wrap:wrap;gap:10px;justify-content:center;margin-top:16px}
.legend-item{display:flex;gap:8px;align-items:center;padding:6px 10px;border-radius:6px;color:#222}
.sw{width:14px;height:14px;border-radius:3px;display:inline-block}
</style>
</head>
<body>
<div class='container'><h2>__TITLE__</h2><div class='chart-wrap' id='chart'></div><div id='legend' class='legend'></div></div>
<script id='chart-data' type='application/json'>
__CHART_PAYLOAD__
</script>
<script>
(function(){
  try{
    var payload = JSON.parse(document.getElementById('chart-data').textContent || '{}');
    var labels = payload.labels || [];
    var ds = payload.datasets && payload.datasets[0] || {data:[], backgroundColor:[]};
    var data = ds.data || [];
    var colors = ds.backgroundColor && ds.backgroundColor.length ? ds.backgroundColor : d3.schemeTableau10;
    var total = d3.sum(data);
    var width = Math.min(700, window.innerWidth - 120), height = Math.min(700, window.innerHeight - 240), radius = Math.min(width, height) / 2;
    var svg = d3.select('#chart').append('svg').attr('width', width).attr('height', height).append('g').attr('transform', 'translate(' + width/2 + ',' + height/2 + ')');
    var arc = d3.arc().innerRadius(radius*0.5).outerRadius(radius*0.9);
    var labelArc = d3.arc().innerRadius(radius*0.7).outerRadius(radius*0.7);
    var pie = d3.pie().value(function(d){ return d; }).sort(null);
    var arcs = svg.selectAll('arc').data(pie(data)).enter().append('g').attr('class','arc');
    arcs.append('path').attr('d', arc).attr('fill', function(d,i){ return colors[i % colors.length]; }).attr('stroke', '#fff').attr('stroke-width', 2).style('cursor','pointer').style('filter','drop-shadow(0 2px 4px rgba(0,0,0,0.1))')
      .on('mouseover', function(event,d){ 
        d3.select(this).transition().duration(200).attr('d', d3.arc().innerRadius(radius*0.5).outerRadius(radius*0.95)).style('filter','drop-shadow(0 4px 8px rgba(0,0,0,0.2))');
        var percent = ((d.data / total) * 100).toFixed(1);
        tip.style('opacity',1).html(labels[d.index] + ': <strong>' + d.data.toLocaleString() + '</strong><br>(' + percent + '%)');
      })
      .on('mouseout', function(){
        d3.select(this).transition().duration(200).attr('d', arc).style('filter','drop-shadow(0 2px 4px rgba(0,0,0,0.1))');
        tip.style('opacity',0);
      });
    // tooltip
    var tip = d3.select('body').append('div').style('position','absolute').style('padding','10px 14px').style('background','rgba(0,0,0,0.9)').style('color','#fff').style('border-radius','6px').style('pointer-events','none').style('opacity',0).style('font-size','13px').style('z-index','10000').style('box-shadow','0 4px 12px rgba(0,0,0,0.3)');
    arcs.on('mousemove', function(event){ tip.style('left',(event.pageX+15)+'px').style('top',(event.pageY-15)+'px'); });
    // Add data labels on slices
    arcs.append('text').attr('transform', function(d){ return 'translate(' + labelArc.centroid(d) + ')'; }).attr('text-anchor','middle').style('font-size','12px').style('font-weight','700').style('fill','#333').style('text-shadow','0 1px 3px rgba(255,255,255,0.9), 0 -1px 3px rgba(255,255,255,0.9), 1px 0 3px rgba(255,255,255,0.9), -1px 0 3px rgba(255,255,255,0.9)').style('pointer-events','none').each(function(d){
      var percent = ((d.data / total) * 100).toFixed(1);
      var text = d3.select(this);
      if(d.endAngle - d.startAngle > 0.3) {
        text.append('tspan').attr('x',0).attr('dy','0em').text(d.data.toLocaleString()).style('font-size','13px');
        text.append('tspan').attr('x',0).attr('dy','1.2em').text('(' + percent + '%)').style('font-size','11px').style('fill','#555');
      }
    });
    // legend
    var legend = d3.select('#legend'); legend.html('');
    labels.forEach(function(l,i){ 
      var percent = ((data[i] / total) * 100).toFixed(1);
      var item = legend.append('div').attr('class','legend-item'); 
      item.append('div').attr('class','sw').style('background', colors[i % colors.length]); 
      item.append('div').text(l + ' - ' + (data[i]||0).toLocaleString() + ' (' + percent + '%)'); 
    });
  }catch(e){ console.error('D3 render error', e); }
})();
</script>
</body>
</html>"""
        return d3_template.replace('__TITLE__', str(title_text)).replace('__CHART_PAYLOAD__', json.dumps(chart_payload))
    return html


def extract_json_from_text(text: str):
    # Try to parse JSON directly or extract first {...} block
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        candidate = None
        if m:
            candidate = m.group(1)
        else:
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1 and end > start:
                candidate = text[start:end+1]
        if candidate:
            try:
                return json.loads(candidate)
            except Exception:
                try:
                    cand = re.sub(r',\s*(?=[\]}])', '', candidate)
                    return json.loads(cand)
                except Exception:
                    return None
        return None
