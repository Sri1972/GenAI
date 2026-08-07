#!/usr/bin/env python3
"""
================================================================================
D3 Chart API Server (STDIO JSON-RPC Backend)
================================================================================

PURPOSE:
    This is the CORE CHART GENERATION ENGINE that accepts JSON tool calls via
    STDIN and returns JSON responses via STDOUT. It's a JSON-RPC style server
    (not a true MCP server) that acts as the backend for d3_chart_mcp.py.

ARCHITECTURE ROLE:
    - **Layer 2 (Middle)**: Chart Generation Backend
    - Receives tool requests from d3_chart_mcp.py parent process
    - Contains D3.js HTML templates for 20+ chart types
    - Generates standalone HTML files with embedded D3.js visualizations
    - Falls back to Chart.js rendering for unsupported formats

DEPENDENCIES:
    1. **chart_renderer.py** (Layer 3 - Fallback Renderer)
       - IMPORTS: render_chart_html_from_dataset, extract_json_from_text
       - Used when D3 template not available or data format needs normalization
       - Provides Chart.js-based rendering as fallback
       - Handles data format detection and conversion
    
    2. **d3_chart_mcp.py** (Layer 1 - Caller)
       - This file is SPAWNED as subprocess by d3_chart_mcp.py
       - NOT imported - runs as separate process
       - Receives requests via STDIN, returns via STDOUT

DATA FLOW:
    1. Read JSON request from STDIN: {"tool": "bar", "arguments": {...}}
    2. Extract tool name and arguments
    3. Route to appropriate handler (handle_bar, handle_line, etc.)
    4. Generate HTML using D3 templates (script_bar, script_line, etc.)
    5. Save HTML to ./html-charts/ directory
    6. Return JSON response via STDOUT: {"status": "ok", "path": "...", "html": "..."}

SUPPORTED CHART TYPES (20+ templates):
    Basic: bar, horizontal_bar, grouped_bar, stacked_bar, line, area
    Distribution: scatter, bubble, histogram, boxplot
    Circular: pie, donut, radial_bar
    Hierarchical: tree, treemap, circle_packing, sunburst
    Network: force_directed, chord, sankey
    Specialized: heatmap, calendar, radar, bullet, parallel

D3 TEMPLATE STRUCTURE:
    - Each script_*() function returns D3.js code as string
    - Templates expect __DATA_VAR__ placeholder for JSON injection
    - Templates wrapped in BASE_HTML with D3.js v7 CDN
    - Saved as standalone HTML files (can open directly in browser)

FALLBACK LOGIC:
    1. Try D3 template for requested chart type
    2. If data format incompatible or template missing:
       -> Use chart_renderer.py for Chart.js rendering
    3. If all fails, default to line chart

COMMUNICATION PROTOCOL:
    - NOT a true MCP server (no MCP protocol handshake)
    - Simple JSON-RPC: one request in, one response out, then exit
    - Parent process (d3_chart_mcp.py) manages lifecycle

OUTPUT LOCATION:
    All charts saved to: ./html-charts/chart_TIMESTAMP_HASH.html

================================================================================
"""
from __future__ import annotations
import sys
import json
import os
from pathlib import Path
from datetime import datetime
import hashlib
import html
import traceback
import re
import logging
from chart_renderer import render_chart_html_from_dataset, extract_json_from_text
from utils.screenshot import capture_html_as_png

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
DEFAULT_OUTDIR = ROOT / 'html-charts'
DEFAULT_OUTDIR.mkdir(parents=True, exist_ok=True)

# Load external resources and prompts if available
RESOURCES_FILE = ROOT / 'resources' / 'chart_resources.txt'
PROMPTS_FILE = ROOT / 'prompts' / 'chart_prompts.txt'

resources_text = RESOURCES_FILE.read_text(encoding='utf-8') if RESOURCES_FILE.exists() else ''
prompts_text = PROMPTS_FILE.read_text(encoding='utf-8') if PROMPTS_FILE.exists() else ''

# ================================================================================
# LIBRARY PATHS - Local files with CDN fallback
# ================================================================================
D3_LOCAL_PATH = '../scripts/d3_js/d3.v7.min.js'
D3_CDN_URL = 'https://d3js.org/d3.v7.min.js'
D3_SCRIPT_TAG = f"<script src='{D3_LOCAL_PATH}' onerror=\"this.onerror=null; this.src='{D3_CDN_URL}';\"></script>"

HTML2CANVAS_LOCAL_PATH = '../scripts/html2canvas/html2canvas.min.js'
HTML2CANVAS_CDN_URL = 'https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js'

# Basic helper to save html safely
def save_html(html_text: str, prefix: str = 'chart', output_dir: str = None, title: str = None, 
              chart_type: str = None, framework: str = 'd3', auto_screenshot: bool = True) -> str:
    """
    Saves HTML content to a file in the specified or default html-charts directory.
    Optionally generates a PNG screenshot automatically.
    
    Args:
        html_text (str): The HTML content to save
        prefix (str): Filename prefix (default: 'chart') - legacy parameter, overridden by title/chart_type
        output_dir (str): Optional custom output directory path
        title (str): Chart title for filename
        chart_type (str): Chart type (e.g., 'line', 'bar', 'heatmap')
        framework (str): Framework used ('d3' or 'chartjs')
        auto_screenshot (bool): If True, automatically generates PNG screenshot (default: True)
    
    Returns:
        str: Absolute path to the saved HTML file
        
    Creates a descriptive filename using title, chart type, framework, and timestamp.
    If auto_screenshot is True, also creates a PNG file with the same name.
    """
    # Use provided output_dir or default
    outdir = Path(output_dir) if output_dir else DEFAULT_OUTDIR
    outdir.mkdir(parents=True, exist_ok=True)
    
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    
    # Build descriptive filename: title_charttype_framework_timestamp.html
    filename_parts = []
    
    if title:
        # Clean title: remove special chars, limit length, convert to snake_case
        clean_title = re.sub(r'[^\w\s-]', '', title.lower())
        clean_title = re.sub(r'[-\s]+', '_', clean_title)
        clean_title = clean_title[:50]  # Limit to 50 chars
        if clean_title:
            filename_parts.append(clean_title)
    
    if chart_type:
        filename_parts.append(chart_type.lower().replace(' ', '_'))
    
    if framework:
        filename_parts.append(framework.lower())
    
    filename_parts.append(ts)
    
    # Fallback to prefix if no parts generated
    if not filename_parts or len(filename_parts) == 1:  # Only timestamp
        filename = f"{prefix}_{ts}.html"
    else:
        filename = '_'.join(filename_parts) + '.html'
    
    path = outdir / filename

    # When saving to a custom output_dir the relative ../scripts/... paths are wrong.
    # Replace them with absolute file:/// URIs pointing at the server's scripts folder.
    # Spaces in the path must be percent-encoded or browsers won't load the scripts.
    if output_dir:
        from urllib.parse import quote
        abs_scripts = quote((ROOT / 'scripts').as_posix(), safe='/:')
        html_text = html_text.replace("'../scripts/", f"'file:///{abs_scripts}/")
        html_text = html_text.replace('"../scripts/', f'"file:///{abs_scripts}/')

    with open(path, 'wb') as f:
        data = html_text.encode('utf-8')
        f.write(data)
        f.flush()
        try:
            os.fsync(f.fileno())
        except Exception:
            pass
    
    # Auto-generate PNG screenshot if requested
    if auto_screenshot:
        try:
            png_path = capture_html_as_png(str(path), width=1400, height=900, wait_time=2500)
            logger.info(f"Screenshot created: {png_path}")
        except Exception as e:
            logger.warning(f"Failed to create screenshot for {path}: {e}")
    
    return str(path)

# D3 templates
# Common JavaScript utilities for summary panels and legends (framework-agnostic)
COMMON_CHART_UTILS = """
// Common utility functions for building summary panels and legends (works with D3 or Chart.js)
function buildSummaryPanel(datasets, summaryElementId) {
  var summaryEl = document.getElementById(summaryElementId || 'summary');
  if (!summaryEl) return;
  summaryEl.innerHTML = '';
  
  // Calculate grand total
  var grandTotal = 0;
  datasets.forEach(function(ds) {
    var data = ds.data || [];
    data.forEach(function(v) {
      var num = typeof v === 'number' ? v : (typeof v === 'object' && v.y != null ? v.y : 0);
      grandTotal += num;
    });
  });
  
  if (grandTotal > 0) {
    // Add grand total card
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
    
    // Add per-dataset cards
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
"""

BASE_HTML = """<!doctype html>
<html>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width,initial-scale=1'>
  <title>{title}</title>
  <style>
    body{font-family:Segoe UI,Arial,sans-serif;margin:0;padding:0;background:#f5f5f5;box-sizing:border-box}
    .container{width:100vw;margin:0;background:#fff;padding:20px;box-sizing:border-box}
    .summary-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:24px}
    .summary-card{background:#f8f9fa;border:1px solid #dee2e6;border-radius:8px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,0.05)}
    .summary-label{font-size:13px;color:#6c757d;font-weight:500;margin-bottom:4px}
    .summary-value{font-size:24px;font-weight:700;color:#212529}
    .viz{min-height:400px;margin-bottom:20px;width:calc(100vw - 40px)}
    .legend{margin-top:20px;padding-top:15px;border-top:1px solid #e0e0e0;display:flex;flex-wrap:wrap;gap:8px;justify-content:center;max-width:100%;overflow:visible}
    .legend-item{display:flex;gap:8px;align-items:center;padding:6px 10px;border-radius:6px;color:#222;white-space:nowrap}
    .sw{width:14px;height:14px;border-radius:3px;display:inline-block;flex-shrink:0}
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
<h2>{title}</h2>
<div id='summary' class='summary-grid'></div>
<div id='viz' class='viz'></div>
<div id='legend' class='legend' aria-hidden='false'></div>
<div style='margin-top:8px;color:#666;font-size:13px'>Generated by local D3 MCP server</div>
</div>
""" + D3_SCRIPT_TAG + """
<script>
""" + COMMON_CHART_UTILS + """

// Copy chart to clipboard functionality
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

{script}
</script>
</body>
</html>
"""

# Utility: safe JSON -> JS variable
def to_js_var(obj, varname='data'):
    """
    Converts a Python object to a JavaScript variable declaration.
    
    Args:
        obj: Python object to serialize (dict, list, etc.)
        varname (str): JavaScript variable name (default: 'data')
    
    Returns:
        str: JavaScript const declaration string
        
    Safely serializes Python objects to JSON and escapes problematic HTML sequences
    like '</' that could break when embedded in HTML script tags.
    """
    j = json.dumps(obj, ensure_ascii=False)
    # escape special </ to avoid HTML issues
    j = j.replace('</', '<\/')
    return f"const {varname} = {j};\n"

# Chart scripts implementations
def script_line(data_var='data', opts=None):
    """
    Generates D3.js script for multi-line chart visualization with data labels.
    
    Args:
        data_var (str): JavaScript variable name containing the chart data
        opts: Optional configuration (currently unused)
    
    Returns:
        str: JavaScript code for D3 line chart
        
    Expected data format: {labels: [], datasets: [{label: str, data: []}]}
    Creates a responsive line chart with:
    - Summary statistics cards at the top
    - Multiple colored lines for each dataset
    - Monotone X curve interpolation for smooth lines
    - Automatic scaling and axes
    - Points with data labels visible on chart (not just tooltips)
    - Labels positioned above data points for screenshot visibility
    - Deduplication of labels to fix overlapping x-axis values
    """
    # data: {labels:[], datasets:[{label,data:[]}]}
    tpl = """
(function(){
const rawData = __DATA_VAR__;
// Deduplicate labels to fix overlapping x-axis values
const uniqueLabelsMap = new Map();
const labels = rawData.labels || [];
const datasets = rawData.datasets || [];

// Create unique labels by keeping only first occurrence
const uniqueLabels = [];
const labelIndexMap = [];
labels.forEach((label, idx) => {
  if (!uniqueLabelsMap.has(label)) {
    uniqueLabelsMap.set(label, uniqueLabels.length);
    uniqueLabels.push(label);
    labelIndexMap.push(uniqueLabels.length - 1);
  } else {
    labelIndexMap.push(uniqueLabelsMap.get(label));
  }
});

// Aggregate data for duplicate labels (sum values)
const aggregatedDatasets = datasets.map(ds => {
  const newData = new Array(uniqueLabels.length).fill(0);
  ds.data.forEach((val, idx) => {
    const targetIdx = labelIndexMap[idx];
    newData[targetIdx] += (val || 0);
  });
  return {...ds, data: newData};
});

// Calculate summary statistics
const summaryStats = [];
aggregatedDatasets.forEach(ds => {
  const values = ds.data.filter(v => v != null && !isNaN(v));
  const total = values.reduce((a,b) => a+b, 0);
  const avg = values.length > 0 ? total / values.length : 0;
  const max = values.length > 0 ? Math.max(...values) : 0;
  summaryStats.push({label: ds.label, total, avg, max});
});

// Display summary cards
const summaryContainer = d3.select('#summary');
summaryStats.forEach(stat => {
  const card = summaryContainer.append('div').attr('class', 'summary-card');
  card.append('div').attr('class', 'summary-label').text(stat.label);
  card.append('div').attr('class', 'summary-value').text(Math.round(stat.total).toLocaleString());
  card.append('div').style('font-size','11px').style('color','#6c757d').style('margin-top','4px')
    .html(`Avg: ${Math.round(stat.avg)} | Max: ${Math.round(stat.max)}`);
});

// Chart rendering
const margin = {top:30,right:30,bottom:80,left:60};
const container = d3.select('#viz');
const width = Math.max(800, window.innerWidth - 40 - margin.left - margin.right);
const height = 500;
const svg = container.append('svg')
  .attr('width', width + margin.left + margin.right)
  .attr('height', height + margin.top + margin.bottom)
  .append('g').attr('transform', `translate(${margin.left},${margin.top})`);

const x = d3.scalePoint().domain(uniqueLabels).range([0,width]).padding(0.5);
const y = d3.scaleLinear().range([height,0]);
let allValues = [];
aggregatedDatasets.forEach(d=>allValues = allValues.concat(d.data));
const minVal = d3.min(allValues) || 0;
const maxVal = d3.max(allValues) || 0;
// Handle negative values by extending domain below zero if needed
const yMin = minVal < 0 ? minVal * 1.15 : 0;
const yMax = maxVal * 1.15;
y.domain([yMin, yMax]);
const line = d3.line().x((d,i)=>x(uniqueLabels[i])).y(d=>y(d)).curve(d3.curveCardinal.tension(0.3));
// Helper function for text wrapping
function wrapText(text, width) {
  text.each(function() {
    const text = d3.select(this);
    const words = text.text().split(/\s+/).reverse();
    let word, line = [], lineNumber = 0;
    const lineHeight = 1.1, y = text.attr('y'), dy = parseFloat(text.attr('dy')) || 0;
    let tspan = text.text(null).append('tspan').attr('x', 0).attr('y', y).attr('dy', dy + 'em');
    while (word = words.pop()) {
      line.push(word);
      tspan.text(line.join(' '));
      if (tspan.node().getComputedTextLength() > width) {
        line.pop();
        tspan.text(line.join(' '));
        line = [word];
        tspan = text.append('tspan').attr('x', 0).attr('y', y).attr('dy', ++lineNumber * lineHeight + dy + 'em').text(word);
      }
    }
  });
}
// Add grid lines (y-axis only, no x-axis grid to avoid clutter)
svg.append('g').attr('class','grid').call(d3.axisLeft(y).tickSize(-width).tickFormat('')).selectAll('line').style('stroke','#e0e0e0').style('stroke-dasharray','2,2');
// Add axes with word-wrapped x-axis labels
const xAxisGroupLine = svg.append('g').attr('transform',`translate(0,${height})`).call(d3.axisBottom(x));
xAxisGroupLine.selectAll('text').style('text-anchor','middle').style('font-size','11px').style('fill','#666').call(wrapText, x.bandwidth ? x.bandwidth() : 80);
svg.append('g').call(d3.axisLeft(y)).selectAll('text').style('font-size','12px').style('fill','#666');
// Create enhanced tooltip
const tooltip = d3.select('body').append('div').style('position','absolute').style('background','rgba(255,255,255,0.98)').style('color','#333').style('padding','12px 16px').style('border-radius','6px').style('border','1px solid #ddd').style('box-shadow','0 4px 12px rgba(0,0,0,0.15)').style('font-size','13px').style('pointer-events','none').style('opacity',0).style('z-index','10000').style('min-width','150px');
aggregatedDatasets.forEach(function(ds, idx){
   const color = ds.backgroundColor || ds.borderColor || d3.schemeTableau10[idx%10];
   // Draw line with subtle fill
   svg.append('path').datum(ds.data).attr('fill','none').attr('stroke',color).attr('stroke-width',3).attr('d',line).style('filter','drop-shadow(0 2px 3px rgba(0,0,0,0.1))');
   // Add area fill with transparency
   const area = d3.area().x((d,i)=>x(uniqueLabels[i])).y0(height).y1(d=>y(d)).curve(d3.curveCardinal.tension(0.3));
   svg.append('path').datum(ds.data).attr('fill',color).attr('opacity',0.1).attr('d',area);
   // Add points with enhanced hover - store index in data binding to fix tooltip issue with duplicate values
   svg.selectAll('.dot'+idx).data(ds.data).enter().append('circle').attr('class','dot'+idx).attr('cx',(d,i)=>x(uniqueLabels[i])).attr('cy',d=>y(d)).attr('r',5).attr('fill',color).attr('stroke','#fff').attr('stroke-width',2.5).style('cursor','pointer')
   .each(function(d, i) { d3.select(this).datum({value: d, index: i}); })
   .on('mouseover', function(event,d){
     d3.select(this).attr('r',8).style('filter','drop-shadow(0 2px 4px rgba(0,0,0,0.3))');
     const i = d.index;
     const allData = aggregatedDatasets.map((dataset,dIdx)=>{
       const val = dataset.data[i] || 0;
       const dColor = dataset.backgroundColor || dataset.borderColor || d3.schemeTableau10[dIdx%10];
       return `<div style='display:flex;align-items:center;gap:8px;margin:4px 0'><div style='width:12px;height:12px;background:${dColor};border-radius:2px'></div><span style='flex:1'>${dataset.label}:</span><strong>${Math.round(val*100)/100}</strong></div>`;
     }).join('');
     tooltip.style('opacity',1).html(`<div style='font-weight:600;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid #eee'>${uniqueLabels[i]}</div>${allData}`).style('left',(event.pageX+15)+'px').style('top',(event.pageY-15)+'px');
   })
   .on('mouseout', function(){
     d3.select(this).attr('r',5).style('filter','none');
     tooltip.style('opacity',0);
   });
   // Add data labels with smart positioning
   svg.selectAll('.label'+idx).data(ds.data).enter().append('text').attr('class','label'+idx).attr('x',(d,i)=>x(uniqueLabels[i])).attr('y',d=>Math.min(y(d)-10, height-20)).attr('text-anchor','middle').style('font-size','11px').style('font-weight','700').style('fill',color).style('text-shadow','0 1px 2px rgba(255,255,255,0.8)').style('pointer-events','none').text(d=>Math.round(d*10)/10);
});
// Add legend after all datasets (outside loop to avoid duplication)
aggregatedDatasets.forEach(function(ds, idx){
   const color = ds.backgroundColor || ds.borderColor || d3.schemeTableau10[idx%10];
   d3.select('#legend').append('div').attr('class','legend-item').html(`<div class='sw' style='background:${color}'></div><div>${ds.label}</div>`);
});
})();
"""
    return tpl.replace('__DATA_VAR__', data_var)

def script_bar(data_var='data', stacked=False):
    """
    Generates D3.js script for vertical bar chart (single or multi-series) with data labels.
    
    Args:
        data_var (str): JavaScript variable name containing the chart data
        stacked (bool): Whether to create stacked bars (default: False)
    
    Returns:
        str: JavaScript code for D3 bar chart
        
    Expected data format: {labels: [], datasets: [{label: str, data: [], backgroundColor: str}]}
    Creates responsive bar chart with:
    - Automatic scaling and axes with rotated x-axis labels
    - Multiple datasets shown as grouped or side-by-side bars
    - Color coding for different series
    - Data labels on top of bars (visible in screenshots)
    - Hover interactions and tooltips
    """
    tpl = """
(function(){
const container = d3.select('#viz');
const labels = __DATA_VAR__.labels || [];
const datasets = __DATA_VAR__.datasets || [];

// Build summary statistics panel
const summaryContainer = d3.select('#summary');
summaryContainer.html('');

// Calculate dataset totals
const grandTotal = datasets.reduce((sum, ds) => sum + ds.data.reduce((s, v) => s + (v || 0), 0), 0);

if (grandTotal > 0) {
  // Add grand total card
  const totalCard = summaryContainer.append('div')
    .style('background', '#e7f3ff')
    .style('border', '2px solid #0d6efd')
    .style('border-radius', '8px')
    .style('padding', '16px')
    .style('text-align', 'center')
    .style('grid-column', '1 / -1');
  
  totalCard.append('div')
    .style('font-size', '13px')
    .style('font-weight', '600')
    .style('color', '#495057')
    .text('Total');
  
  totalCard.append('div')
    .style('font-size', '28px')
    .style('font-weight', '700')
    .style('color', '#0d6efd')
    .text(Math.round(grandTotal).toLocaleString());
  
  // Add per-dataset cards
  datasets.forEach((ds, idx) => {
    const dsTotal = ds.data.reduce((sum, v) => sum + (v || 0), 0);
    if (dsTotal > 0) {
      const card = summaryContainer.append('div')
        .style('background', '#f8f9fa')
        .style('border', '1px solid #dee2e6')
        .style('border-radius', '6px')
        .style('padding', '12px');
      
      card.append('div')
        .style('font-size', '12px')
        .style('color', '#6c757d')
        .style('font-weight', '500')
        .style('margin-bottom', '4px')
        .text(ds.label || 'Dataset ' + (idx + 1));
      
      card.append('div')
        .style('font-size', '20px')
        .style('font-weight', '700')
        .style('color', '#212529')
        .text(Math.round(dsTotal).toLocaleString());
    }
  });
}

const margin = {top:30,right:30,bottom:80,left:60};
const width = Math.max(800, window.innerWidth - 40 - margin.left - margin.right);
const height = 500;
const svg = container.append('svg')
  .attr('width', width + margin.left + margin.right)
  .attr('height', height + margin.top + margin.bottom)
  .append('g').attr('transform', `translate(${margin.left},${margin.top})`);
const x0 = d3.scaleBand().domain(labels).range([0,width]).padding(0.2);
const x1 = d3.scaleBand().padding(0.05);
const y = d3.scaleLinear().range([height,0]);
if(__STACKED__){
  // stacked: compute stacks
  const series = d3.stack().keys(d3.range(datasets.length))(labels.map((l,i)=>datasets.map(ds=>ds.data[i]||0)));
  const maxVal = d3.max(series, s=>d3.max(s, d=>d[1]))||0;
  y.domain([0,maxVal*1.1]);
  x1.domain(d3.range(datasets.length)).range([0,x0.bandwidth()]);
  // Helper function for text wrapping
  function wrapText(text, width) {
    text.each(function() {
      const text = d3.select(this);
      const words = text.text().split(/\s+/).reverse();
      let word, line = [], lineNumber = 0;
      const lineHeight = 1.1, y = text.attr('y'), dy = parseFloat(text.attr('dy')) || 0;
      let tspan = text.text(null).append('tspan').attr('x', 0).attr('y', y).attr('dy', dy + 'em');
      while (word = words.pop()) {
        line.push(word);
        tspan.text(line.join(' '));
        if (tspan.node().getComputedTextLength() > width) {
          line.pop();
          tspan.text(line.join(' '));
          line = [word];
          tspan = text.append('tspan').attr('x', 0).attr('y', y).attr('dy', ++lineNumber * lineHeight + dy + 'em').text(word);
        }
      }
    });
  }
  // Add grid lines
  svg.append('g').attr('class','grid').call(d3.axisLeft(y).tickSize(-width).tickFormat('')).selectAll('line').style('stroke','#e0e0e0').style('stroke-dasharray','2,2');
  const xAxisGroup = svg.append('g').attr('transform',`translate(0,${height})`).call(d3.axisBottom(x0));
  xAxisGroup.selectAll('text').style('text-anchor','middle').style('font-size','11px').style('fill','#666').call(wrapText, x0.bandwidth());
  svg.append('g').call(d3.axisLeft(y)).selectAll('text').style('font-size','12px').style('fill','#666');
  // Create enhanced tooltip
  const tooltip = d3.select('body').append('div').style('position','absolute').style('background','rgba(255,255,255,0.98)').style('color','#333').style('padding','12px 16px').style('border-radius','6px').style('border','1px solid #ddd').style('box-shadow','0 4px 12px rgba(0,0,0,0.15)').style('font-size','13px').style('pointer-events','none').style('opacity',0).style('z-index','10000');
  const colors = datasets.map((d,i)=>d.backgroundColor||d.borderColor||d3.schemeTableau10[i%10]);
  const groups = svg.selectAll('g.layer').data(series).enter().append('g').attr('class','layer').attr('fill',(d,i)=>colors[i]);
  groups.selectAll('rect').data(d=>d).enter().append('rect').attr('x',(d,i)=>x0(labels[i])).attr('y',d=>y(d[1])).attr('height',d=>y(d[0])-y(d[1])).attr('width',x0.bandwidth()).attr('rx',2).style('cursor','pointer').style('filter','drop-shadow(0 1px 2px rgba(0,0,0,0.1))')
    .on('mouseover', function(event,d){
      d3.select(this).style('opacity',0.85).style('filter','drop-shadow(0 2px 4px rgba(0,0,0,0.2))');
      const seriesIdx = series.indexOf(d3.select(this.parentNode).datum());
      const ptIdx = d.index || 0;
      const value = d[1] - d[0];
      tooltip.style('opacity',1).html(`<div style='font-weight:600;margin-bottom:6px;color:${colors[seriesIdx]}'>${datasets[seriesIdx].label}</div><div>${labels[ptIdx]}: <strong>${Math.round(value*100)/100}</strong></div>`).style('left',(event.pageX+15)+'px').style('top',(event.pageY-15)+'px');
    })
    .on('mouseout', function(){
      d3.select(this).style('opacity',1).style('filter','drop-shadow(0 1px 2px rgba(0,0,0,0.1))');
      tooltip.style('opacity',0);
    });
  // Add data labels for stacked bars
  groups.selectAll('text').data(d=>d).enter().append('text').attr('x',(d,i)=>x0(labels[i])+x0.bandwidth()/2).attr('y',d=>(y(d[1])+y(d[0]))/2).attr('text-anchor','middle').style('font-size','11px').style('font-weight','700').style('fill','#fff').style('text-shadow','0 1px 2px rgba(0,0,0,0.3)').style('pointer-events','none').text(d=>Math.round((d[1]-d[0])*10)/10);
  datasets.forEach((ds,i)=>{ d3.select('#legend').append('div').attr('class','legend-item').html(`<div class='sw' style='background:${colors[i]}'></div><div>${ds.label}</div>`); });
} else {
  x1.domain(d3.range(datasets.length)).range([0,x0.bandwidth()]);
  const maxv = d3.max(datasets, ds=>d3.max(ds.data||[]))||0; y.domain([0,maxv*1.15]);
  // Helper function for text wrapping
  function wrapText(text, width) {
    text.each(function() {
      const text = d3.select(this);
      const words = text.text().split(/\s+/).reverse();
      let word, line = [], lineNumber = 0;
      const lineHeight = 1.1, y = text.attr('y'), dy = parseFloat(text.attr('dy')) || 0;
      let tspan = text.text(null).append('tspan').attr('x', 0).attr('y', y).attr('dy', dy + 'em');
      while (word = words.pop()) {
        line.push(word);
        tspan.text(line.join(' '));
        if (tspan.node().getComputedTextLength() > width) {
          line.pop();
          tspan.text(line.join(' '));
          line = [word];
          tspan = text.append('tspan').attr('x', 0).attr('y', y).attr('dy', ++lineNumber * lineHeight + dy + 'em').text(word);
        }
      }
    });
  }
  // Add grid lines
  svg.append('g').attr('class','grid').call(d3.axisLeft(y).tickSize(-width).tickFormat('')).selectAll('line').style('stroke','#e0e0e0').style('stroke-dasharray','2,2');
  const xAxisGroup2 = svg.append('g').attr('transform',`translate(0,${height})`).call(d3.axisBottom(x0));
  xAxisGroup2.selectAll('text').style('text-anchor','middle').style('font-size','11px').style('fill','#666').call(wrapText, x0.bandwidth());
  svg.append('g').call(d3.axisLeft(y)).selectAll('text').style('font-size','12px').style('fill','#666');
  // Create enhanced tooltip
  const tooltip = d3.select('body').append('div').style('position','absolute').style('background','rgba(255,255,255,0.98)').style('color','#333').style('padding','12px 16px').style('border-radius','6px').style('border','1px solid #ddd').style('box-shadow','0 4px 12px rgba(0,0,0,0.15)').style('font-size','13px').style('pointer-events','none').style('opacity',0).style('z-index','10000');
  const barGroups = svg.selectAll('g.bar-group').data(labels).enter().append('g').attr('transform',d=>`translate(${x0(d)},0)`);
  barGroups.selectAll('rect').data((d,i)=>datasets.map(ds=>({key:ds.label,value:ds.data[i]||0, color:ds.backgroundColor||ds.borderColor, idx:i, label:labels[i]}))).enter().append('rect')
    .attr('x',(d,i)=>x1(i)).attr('y',d=>y(d.value)).attr('width',x1.bandwidth()).attr('height',d=>height-y(d.value)).attr('fill',d=>d.color||'#777').attr('rx',2).style('cursor','pointer').style('filter','drop-shadow(0 1px 2px rgba(0,0,0,0.1))')
    .on('mouseover', function(event,d){
      d3.select(this).style('opacity',0.85).style('filter','drop-shadow(0 2px 4px rgba(0,0,0,0.2))');
      tooltip.style('opacity',1).html(`<div style='font-weight:600;margin-bottom:6px;color:${d.color}'>${d.key}</div><div>${d.label}: <strong>${Math.round(d.value*100)/100}</strong></div>`).style('left',(event.pageX+15)+'px').style('top',(event.pageY-15)+'px');
    })
    .on('mouseout', function(){
      d3.select(this).style('opacity',1).style('filter','drop-shadow(0 1px 2px rgba(0,0,0,0.1))');
      tooltip.style('opacity',0);
    });
  // Add data labels on top of bars with smart positioning
  barGroups.selectAll('text').data((d,i)=>datasets.map(ds=>({key:ds.label,value:ds.data[i]||0, color:ds.backgroundColor||ds.borderColor, idx:i}))).enter().append('text')
    .attr('x',(d,i)=>x1(i)+x1.bandwidth()/2).attr('y',d=>Math.max(y(d.value)-8, 15)).attr('text-anchor','middle').style('font-size','11px').style('font-weight','700').style('fill','#333').style('text-shadow','0 1px 2px rgba(255,255,255,0.8)').style('pointer-events','none').text(d=>Math.round(d.value*10)/10);
  datasets.forEach((ds,i)=>{ d3.select('#legend').append('div').attr('class','legend-item').html(`<div class='sw' style='background:${ds.backgroundColor||ds.borderColor||d3.schemeTableau10[i%10]}'></div><div>${ds.label}</div>`); });
}
})();
"""
    return tpl.replace('__DATA_VAR__', data_var).replace('__STACKED__', 'true' if stacked else 'false')

def script_pie(data_var='data', donut=False):
    """
    Generates D3.js script for pie or donut chart with data labels and interactive tooltips.
    
    Args:
        data_var (str): JavaScript variable name containing the chart data
        donut (bool): Whether to create donut chart with inner radius (default: False)
    
    Returns:
        str: JavaScript code for D3 pie/donut chart
        
    Expected data format: {labels: [], datasets: [{data: [], backgroundColor: []}]} 
    or simplified: [{label: str, value: number, color: str}]
    Creates responsive pie/donut chart with:
    - Proportional slices based on data values
    - Color coding for each slice
    - Data labels on each slice showing value and percentage
    - Enhanced hover animations and tooltips
    - Optional inner radius for donut style
    """
    tpl = """
(function(){
const container = d3.select('#viz');
const labels = __DATA_VAR__.labels || [];
const ds = __DATA_VAR__.datasets && __DATA_VAR__.datasets[0] || {data:[], backgroundColor: []};
const data = (ds.data || []).map((v,i)=>({label: labels[i]||('Seg'+i), value: v||0, color: (ds.backgroundColor && ds.backgroundColor[i]) || ds.borderColor || d3.schemeTableau10[i%10]}));
const total = d3.sum(data, d=>d.value);

// Build summary statistics panel
const summaryContainer = d3.select('#summary');
summaryContainer.html('');

if (total > 0) {
  // Add grand total card
  const totalCard = summaryContainer.append('div')
    .style('background', '#e7f3ff')
    .style('border', '2px solid #0d6efd')
    .style('border-radius', '8px')
    .style('padding', '16px')
    .style('text-align', 'center')
    .style('grid-column', '1 / -1');
  
  totalCard.append('div')
    .style('font-size', '13px')
    .style('font-weight', '600')
    .style('color', '#495057')
    .text('Total');
  
  totalCard.append('div')
    .style('font-size', '28px')
    .style('font-weight', '700')
    .style('color', '#0d6efd')
    .text(Math.round(total).toLocaleString());
  
  // Add per-slice cards
  data.forEach((d, idx) => {
    if (d.value > 0) {
      const percent = ((d.value / total) * 100).toFixed(1);
      const card = summaryContainer.append('div')
        .style('background', '#f8f9fa')
        .style('border', '1px solid #dee2e6')
        .style('border-radius', '6px')
        .style('padding', '12px');
      
      card.append('div')
        .style('font-size', '12px')
        .style('color', '#6c757d')
        .style('font-weight', '500')
        .style('margin-bottom', '4px')
        .text(d.label);
      
      card.append('div')
        .style('font-size', '20px')
        .style('font-weight', '700')
        .style('color', '#212529')
        .text(Math.round(d.value).toLocaleString());
      
      card.append('div')
        .style('font-size', '12px')
        .style('color', '#6c757d')
        .text(percent + '%');
    }
  });
}

const rect = container.node().getBoundingClientRect();
const rectWidth = rect.width || container.node().clientWidth || document.documentElement.clientWidth || window.innerWidth || 800;
const rectHeight = rect.height || container.node().clientHeight || document.documentElement.clientHeight || window.innerHeight || 520;
const width = Math.min(600, rectWidth);
const height = Math.min(520, rectHeight);
const radius = Math.min(width, height)/2 - 10;
const svg = container.append('svg').attr('width', width).attr('height', height).append('g').attr('transform',`translate(${width/2},${height/2})`);
const pie = d3.pie().value(d=>d.value).sort(null);
const arc = d3.arc().innerRadius({INNER}).outerRadius(radius);
const labelArc = d3.arc().innerRadius(radius * 0.7).outerRadius(radius * 0.7);
const arcs = svg.selectAll('arc').data(pie(data)).enter().append('g').attr('class','arc');
// Create enhanced tooltip
const tooltip = d3.select('body').append('div').style('position','absolute').style('background','rgba(0,0,0,0.9)').style('color','#fff').style('padding','10px 14px').style('border-radius','6px').style('font-size','13px').style('pointer-events','none').style('opacity',0).style('z-index','10000').style('box-shadow','0 4px 12px rgba(0,0,0,0.3)');
// Draw slices
arcs.append('path').attr('d',arc).attr('fill',d=>d.data.color).attr('stroke','#fff').attr('stroke-width',2).style('cursor','pointer').style('filter','drop-shadow(0 2px 4px rgba(0,0,0,0.1))')
  .on('mouseover', function(event,d){
    d3.select(this).transition().duration(200).attr('d',d3.arc().innerRadius({INNER}).outerRadius(radius * 1.05)).style('filter','drop-shadow(0 4px 8px rgba(0,0,0,0.3))');
    const percent = ((d.data.value / total) * 100).toFixed(1);
    tooltip.style('opacity',1).html(`<div style='font-weight:600;margin-bottom:4px'>${d.data.label}</div><div>Value: <strong>${d.data.value.toLocaleString()}</strong></div><div>Percentage: <strong>${percent}%</strong></div>`).style('left',(event.pageX+15)+'px').style('top',(event.pageY-15)+'px');
  })
  .on('mousemove', function(event){
    tooltip.style('left',(event.pageX+15)+'px').style('top',(event.pageY-15)+'px');
  })
  .on('mouseout', function(event,d){
    d3.select(this).transition().duration(200).attr('d',arc).style('filter','drop-shadow(0 2px 4px rgba(0,0,0,0.1))');
    tooltip.style('opacity',0);
  });
// Add data labels on slices
arcs.append('text').attr('transform', d=>`translate(${labelArc.centroid(d)})`).attr('text-anchor','middle').style('font-size','12px').style('font-weight','700').style('fill','#333').style('text-shadow','0 1px 3px rgba(255,255,255,0.9), 0 -1px 3px rgba(255,255,255,0.9), 1px 0 3px rgba(255,255,255,0.9), -1px 0 3px rgba(255,255,255,0.9)').style('pointer-events','none').each(function(d){
  const percent = ((d.data.value / total) * 100).toFixed(1);
  const text = d3.select(this);
  // Only show label if slice is large enough
  if(d.endAngle - d.startAngle > 0.3) {
    text.append('tspan').attr('x',0).attr('dy','0em').text(d.data.value.toLocaleString()).style('font-size','13px');
    text.append('tspan').attr('x',0).attr('dy','1.2em').text(`(${percent}%)`).style('font-size','11px').style('fill','#555');
  }
});
// Legend
const legend = d3.select('#legend');
data.forEach(d=>{ 
  const percent = ((d.value / total) * 100).toFixed(1);
  legend.append('div').attr('class','legend-item').html(`<div class='sw' style='background:${d.color}'></div><div>${d.label} - ${d.value.toLocaleString()} (${percent}%)</div>`); 
});
})();
"""
    inner = 'radius*0.5' if donut else '0'
    return tpl.replace('__DATA_VAR__', data_var).replace('{INNER}', inner)


def script_bubble(data_var='data'):
    """
    Generates D3.js script for bubble chart visualization.
    
    Args:
        data_var (str): JavaScript variable name containing the chart data
    
    Returns:
        str: JavaScript code for D3 bubble chart
        
    Expected data format: {datasets: [{label: str, data: [{x: num, y: num, r: num}], backgroundColor: []}]}
    Creates responsive bubble chart with:
    - Three-dimensional data representation (x, y, radius)
    - Multiple series support with different colors
    - Automatic scaling for all three dimensions
    - Interactive hover effects and tooltips
    - Suitable for correlation analysis with size encoding
    """
    # Expects payload: { datasets: [ { label: 'series', data: [ {x:.., y:.., r:..}, ... ], backgroundColor: [] } ] }
    tpl = """
(function(){
const container = d3.select('#viz');
const rect = container.node().getBoundingClientRect();
const width = Math.max(300, rect.width || container.node().clientWidth || window.innerWidth || 800);
const height = Math.max(300, rect.height || container.node().clientHeight || window.innerHeight || 520);
const svg = container.append('svg').attr('width', width).attr('height', height).append('g').attr('transform','translate(40,20)');
const payload = __DATA_VAR__ || {};
const datasets = payload.datasets || [];
if(!datasets.length){ container.append('div').text('No bubble data'); return; }
const points = datasets[0].data || [];
// compute scales
const xs = points.map(d=>+d.x||0), ys = points.map(d=>+d.y||0), rs = points.map(d=>+d.r||0);
const xScale = d3.scaleLinear().domain([d3.min(xs)||0, d3.max(xs)||1]).range([0, width-120]);
const yScale = d3.scaleLinear().domain([d3.min(ys)||0, d3.max(ys)||1]).range([height-80, 0]);
const rScale = d3.scaleSqrt().domain([d3.min(rs)||0, d3.max(rs)||1]).range([4, 40]);
// axes
const xAxis = d3.axisBottom(xScale).ticks(6);
const yAxis = d3.axisLeft(yScale).ticks(6);
svg.append('g').attr('transform',`translate(0,${height-80})`).call(xAxis);
svg.append('g').call(yAxis);
// points
const color = (datasets[0].backgroundColor && datasets[0].backgroundColor[0]) || '#1f77b4';
svg.selectAll('circle').data(points).enter().append('circle')
    .attr('cx',d=>xScale(+d.x||0))
    .attr('cy',d=>yScale(+d.y||0))
    .attr('r',d=>rScale(+d.r||0))
    .attr('fill', (d,i)=> (datasets[0].backgroundColor && datasets[0].backgroundColor[i]) || color)
    .attr('stroke','#fff').attr('stroke-width',1).attr('opacity',0.9)
    .on('mouseover', function(event,d){ const tip = d3.select('body').append('div').attr('id','tmpTip').style('position','absolute').style('padding','6px 8px').style('background','#222').style('color','#fff').style('border-radius','6px').style('pointer-events','none'); tip.html((d.label?d.label+'<br/>':'')+'x:'+d.x+' y:'+d.y+' size:'+d.r); })
    .on('mousemove', function(event){ d3.select('#tmpTip').style('left',(event.pageX+12)+'px').style('top',(event.pageY+12)+'px'); })
    .on('mouseout', function(){ d3.select('#tmpTip').remove(); });
// legend
d3.select('#legend').append('div').attr('class','legend-item').html(`<div class='sw' style='background:${color}'></div><div>${datasets[0].label||'series'}</div>`);
})();
"""
    return tpl.replace('__DATA_VAR__', data_var)


def script_heatmap(data_var='data'):
    """
    Generates D3.js script for heatmap visualization.
    
    Args:
        data_var (str): JavaScript variable name containing the chart data
    
    Returns:
        str: JavaScript code for D3 heatmap chart
        
    Expected data format: {xLabels: [], yLabels: [], values: [[...]]} where values[y][x]
    Creates responsive heatmap with:
    - 2D grid representation of numerical data
    - Color intensity mapping based on data values
    - X and Y axis labels for categories
    - Automatic color scaling from light to dark
    - Hover interactions showing exact values
    """
    # Expects payload: { xLabels:[], yLabels:[], values: [[...]] } where values[y][x]
    tpl = """
(function(){
const container = d3.select('#viz');
const payload = __DATA_VAR__ || {};
let xLabels = payload.xLabels || payload.x_labels || payload.labels || [];
let yLabels = payload.yLabels || payload.y_labels || payload.labelsY || [];
let values = payload.values || payload.matrix || payload.data || [];

// Auto-transform hierarchical data to matrix if needed
if((!xLabels.length || !yLabels.length || !values.length) && payload) {
  // Look for array properties that could be hierarchical data
  const arrayProps = Object.keys(payload).filter(k => Array.isArray(payload[k]) && payload[k].length > 0);
  
  // Find the main data array (usually the largest one with objects)
  const dataArray = arrayProps.map(k => ({key: k, arr: payload[k]}))
    .filter(item => typeof item.arr[0] === 'object' && item.arr[0] !== null)
    .sort((a, b) => b.arr.length - a.arr.length)[0];
  
  if(dataArray) {
    const records = dataArray.arr;
    const sample = records[0];
    const keys = Object.keys(sample);
    
    // Find potential dimension keys (first 2-3 string/categorical fields)
    const dimKeys = keys.filter(k => typeof sample[k] === 'string').slice(0, 2);
    // Find value key (numeric field, often 'cost', 'value', 'amount', etc.)
    const valueKey = keys.find(k => typeof sample[k] === 'number') || keys[keys.length - 1];
    
    if(dimKeys.length >= 2 && valueKey) {
      // Extract unique values for each dimension
      const dim1Values = [...new Set(records.map(r => r[dimKeys[0]]))].sort();
      const dim2Values = [...new Set(records.map(r => r[dimKeys[1]]))].sort();
      
      // Build matrix
      const matrix = Array(dim1Values.length).fill(0).map(() => Array(dim2Values.length).fill(0));
      
      records.forEach(record => {
        const row = dim1Values.indexOf(record[dimKeys[0]]);
        const col = dim2Values.indexOf(record[dimKeys[1]]);
        const val = parseFloat(record[valueKey]) || 0;
        if(row >= 0 && col >= 0) {
          matrix[row][col] += val;
        }
      });
      
      yLabels = dim1Values;
      xLabels = dim2Values;
      values = matrix;
    }
  }
}

if(!xLabels.length || !yLabels.length || !values.length){ container.append('div').text('No heatmap data (expect xLabels,yLabels,values matrix)'); return; }

// Build summary statistics panel
const summaryContainer = d3.select('#summary');
summaryContainer.html('');

// Calculate row and column totals
const rowTotals = values.map(row => row.reduce((sum, v) => sum + (v || 0), 0));
const colTotals = xLabels.map((_, colIdx) => {
  return values.reduce((sum, row) => sum + (row[colIdx] || 0), 0);
});
const grandTotal = rowTotals.reduce((sum, v) => sum + v, 0);

// Add grand total card
const totalCard = summaryContainer.append('div')
  .style('background', '#e7f3ff')
  .style('border', '2px solid #0d6efd')
  .style('border-radius', '8px')
  .style('padding', '16px')
  .style('text-align', 'center')
  .style('grid-column', '1 / -1');

totalCard.append('div')
  .style('font-size', '13px')
  .style('font-weight', '600')
  .style('color', '#495057')
  .text('Total Investment');

totalCard.append('div')
  .style('font-size', '28px')
  .style('font-weight', '700')
  .style('color', '#0d6efd')
  .text('$' + Math.round(grandTotal).toLocaleString());

// Add row totals (y-axis categories)
yLabels.forEach((yLabel, idx) => {
  if (rowTotals[idx] > 0) {
    const card = summaryContainer.append('div')
      .style('background', '#f8f9fa')
      .style('border', '1px solid #dee2e6')
      .style('border-radius', '6px')
      .style('padding', '12px');
    
    card.append('div')
      .style('font-size', '12px')
      .style('color', '#6c757d')
      .style('font-weight', '500')
      .style('margin-bottom', '4px')
      .text(yLabel);
    
    card.append('div')
      .style('font-size', '20px')
      .style('font-weight', '700')
      .style('color', '#212529')
      .text('$' + Math.round(rowTotals[idx]).toLocaleString());
  }
});

// Calculate max y-label width dynamically
const maxYLabelLength = Math.max(...yLabels.map(label => label.length));
const leftMargin = Math.max(120, maxYLabelLength * 7); // 7px per character, minimum 120px

const margin = {top:20,right:20,bottom:80,left:leftMargin};
const rect = container.node().getBoundingClientRect();
const width = Math.max(320, rect.width || container.node().clientWidth || window.innerWidth) - margin.left - margin.right;
const height = Math.max(240, rect.height || container.node().clientHeight || window.innerHeight) - margin.top - margin.bottom;
const gridWidth = width / xLabels.length;
const gridHeight = height / yLabels.length;
const svg = container.append('svg').attr('width', width + margin.left + margin.right).attr('height', height + margin.top + margin.bottom)
    .append('g').attr('transform',`translate(${margin.left},${margin.top})`);
// color scale
const flat = [].concat.apply([], values.map(r=>r.map(v=>+v||0)));
const minV = d3.min(flat), maxV = d3.max(flat);
const color = d3.scaleSequential(d3.interpolateYlOrRd).domain([minV||0, maxV||1]);
// cells
for(var yi=0;yi<yLabels.length;yi++){
    for(var xi=0;xi<xLabels.length;xi++){
        var v = values[yi] && values[yi][xi] != null ? values[yi][xi] : 0;
        svg.append('rect').attr('x', xi*gridWidth).attr('y', yi*gridHeight).attr('width', Math.max(1, gridWidth-1)).attr('height', Math.max(1, gridHeight-1)).style('fill', color(+v)).style('stroke','#fff').style('stroke-width',0.3)
            .on('mouseover', (function(xi,yi,v){ return function(event){ var tip = d3.select('body').append('div').attr('id','tmpTip').style('position','absolute').style('padding','6px 8px').style('background','#222').style('color','#fff').style('border-radius','6px').style('pointer-events','none'); tip.html(xLabels[xi] + ' / ' + yLabels[yi] + ': ' + v); }; })(xi,yi,v))
            .on('mousemove', function(event){ d3.select('#tmpTip').style('left',(event.pageX+12)+'px').style('top',(event.pageY+12)+'px'); })
            .on('mouseout', function(){ d3.select('#tmpTip').remove(); });
    }
}
// axes labels
const xg = svg.append('g').attr('transform',`translate(0,${height})`);

// X-axis labels with text wrapping
xg.selectAll('text').data(xLabels).enter().append('text')
    .attr('x', (d,i)=>i*gridWidth + gridWidth/2)
    .attr('y', 12)
    .attr('text-anchor', 'middle')
    .style('font-size', '11px')
    .each(function(d) {
        const text = d3.select(this);
        const maxWidth = gridWidth - 4; // Leave 4px padding
        const words = d.split(/\s+/);
        let line = [];
        let lineNumber = 0;
        const lineHeight = 1.1; // ems
        const y = text.attr('y');
        
        // If label is short enough, don't wrap
        if (d.length * 6 < maxWidth) {
            text.text(d);
            return;
        }
        
        text.text(null); // Clear text to build tspans
        
        let tspan = text.append('tspan')
            .attr('x', text.attr('x'))
            .attr('y', y)
            .attr('dy', 0);
        
        for (let i = 0; i < words.length; i++) {
            line.push(words[i]);
            tspan.text(line.join(' '));
            
            if (tspan.node().getComputedTextLength() > maxWidth && line.length > 1) {
                line.pop();
                tspan.text(line.join(' '));
                line = [words[i]];
                lineNumber++;
                tspan = text.append('tspan')
                    .attr('x', text.attr('x'))
                    .attr('y', y)
                    .attr('dy', lineNumber * lineHeight + 'em')
                    .text(words[i]);
            }
        }
    });

const yg = svg.append('g');
yg.selectAll('text').data(yLabels).enter().append('text').attr('x', -12).attr('y', (d,i)=>i*gridHeight + gridHeight/2).attr('text-anchor','end').attr('dominant-baseline','middle').text(d=>d).style('font-size','11px');
// legend swatches: simple gradient
var legend = d3.select('#legend'); legend.append('div').text('Heatmap scale');
})();
"""
    return tpl.replace('__DATA_VAR__', data_var)


def script_packed(data_var='data'):
    """
    Generates D3.js script for circle packing (packed bubble) visualization.
    
    Args:
        data_var (str): JavaScript variable name containing the chart data
    
    Returns:
        str: JavaScript code for D3 packed circle chart
        
    Expected data formats:
    1. Flat items: {items: [{id: str, label: str, value: number, color: str}]}
    2. Hierarchical: [{name: str, children: [{name: str, children: [{name: str, value: number}]}]}]
    3. Single hierarchy: {name: str, children: [...]}
    
    Creates responsive packed circle chart with:
    - Proportional circle sizes based on data values
    - Hierarchical bubble packing algorithm (d3.pack)
    - Color coding for different categories
    - Efficient space utilization with no overlaps
    - Interactive hover with tooltips
    - Nested structure visualization with labels
    - Ideal for hierarchical part-to-whole relationships
    """
    # Supports multiple payload formats: { items: [...] }, [...], or {name: 'root', children: [...]}
    tpl = """
(function(){
const container = d3.select('#viz');
const payload = __DATA_VAR__ || {};

// Detect and normalize the data format
let hierarchyData = null;

// Format 1: Direct hierarchy with name and children
if (payload.name && payload.children) {
    hierarchyData = payload;
}
// Format 2: Array of hierarchical nodes (use first or wrap in root)
else if (Array.isArray(payload) && payload.length > 0) {
    if (payload[0].children) {
        // Hierarchical array - wrap in root
        hierarchyData = { name: 'root', children: payload };
    } else {
        // Flat array of items - convert to hierarchy
        hierarchyData = { name: 'root', children: payload.map(i => ({
            name: i.name || i.label || i.id || String(i),
            value: +i.value || 0,
            color: i.color
        }))};
    }
}
// Format 3: Object with items array
else if (payload.items && Array.isArray(payload.items)) {
    hierarchyData = { name: 'root', children: payload.items.map(i => ({
        name: i.name || i.label || i.id || String(i),
        value: +i.value || 0,
        color: i.color
    }))};
}
// Format 4: Object with data array
else if (payload.data && Array.isArray(payload.data)) {
    hierarchyData = { name: 'root', children: payload.data.map(i => ({
        name: i.name || i.label || i.id || String(i),
        value: +i.value || 0,
        color: i.color
    }))};
}

if (!hierarchyData) {
    container.append('div').text('No packed data found. Expected formats: {items: [...]}, {name, children: [...]}, or array of hierarchical nodes.');
    return;
}

const rect = container.node().getBoundingClientRect();
const width = Math.max(800, rect.width || container.node().clientWidth || window.innerWidth);
const height = Math.max(700, rect.height || container.node().clientHeight || window.innerHeight);
const svg = container.append('svg').attr('width', width).attr('height', height).append('g').attr('transform','translate(0,0)');

// Create color scale for hierarchy levels
const colorScale = d3.scaleOrdinal(d3.schemeTableau10);

// Build hierarchy and compute circle packing layout
const pack = d3.pack().size([width, height]).padding(3);
const hierarchy = d3.hierarchy(hierarchyData)
    .sum(d => {
        // Only sum values from leaf nodes (nodes without children)
        // This prevents double-counting when intermediate nodes have values
        if (d.children && d.children.length > 0) {
            return 0; // Intermediate nodes: value will be calculated from children
        }
        return d.value || 0; // Leaf nodes: use their value
    })
    .sort((a, b) => b.value - a.value);
pack(hierarchy);

// Calculate and display summary statistics
const summaryContainer = d3.select('#summary');
summaryContainer.html(''); // Clear any existing content

// Helper function to parse cost strings like "$75,158.4" to numbers
function parseCost(cost) {
    if (typeof cost === 'number') return cost;
    if (typeof cost === 'string') {
        return parseFloat(cost.replace(/[$,]/g, '')) || 0;
    }
    return 0;
}

// Build hierarchical summary dynamically from tree structure using computed hierarchy values
const level1Nodes = hierarchy.children || [];

level1Nodes.forEach(node1 => {
    if (!node1.value || node1.value === 0) return;
    
    // Level 1 card
    const card1 = summaryContainer.append('div')
        .style('background', '#f8f9fa')
        .style('border', '2px solid #dee2e6')
        .style('border-radius', '8px')
        .style('padding', '16px')
        .style('margin-bottom', '16px');
    
    card1.append('div')
        .style('font-size', '16px')
        .style('font-weight', '700')
        .style('color', '#212529')
        .style('margin-bottom', '8px')
        .text(node1.data.name);
    
    card1.append('div')
        .style('font-size', '20px')
        .style('font-weight', '700')
        .style('color', '#0d6efd')
        .style('margin-bottom', '12px')
        .text('$' + Math.round(node1.value).toLocaleString());
    
    // Level 2 nodes
    const level2Nodes = node1.children || [];
    level2Nodes.forEach(node2 => {
        if (!node2.value || node2.value === 0) return;
        
        const card2 = card1.append('div')
            .style('background', '#fff')
            .style('border-left', '3px solid #0d6efd')
            .style('padding', '12px')
            .style('margin', '8px 0')
            .style('border-radius', '4px');
        
        card2.append('div')
            .style('font-size', '14px')
            .style('font-weight', '600')
            .style('color', '#495057')
            .style('margin-bottom', '8px')
            .text(node2.data.name + ' - $' + Math.round(node2.value).toLocaleString());
        
        // Level 3 nodes - show each individually with cost
        const level3Nodes = node2.children || [];
        const activeLevel3 = level3Nodes.filter(n => n.value > 0);
        if (activeLevel3.length > 0) {
            activeLevel3.forEach(node3 => {
                card2.append('div')
                    .style('font-size', '12px')
                    .style('color', '#6c757d')
                    .style('padding-left', '12px')
                    .style('margin-top', '4px')
                    .html(`• ${node3.data.name}: <span style="color:#212529;font-weight:600">$${Math.round(node3.value).toLocaleString()}</span>`);
            });
        }
    });
});

// Add overall summary card (dynamically calculated)
const leafNodes = hierarchy.leaves();
const totalValue = d3.sum(leafNodes, d => d.value || 0);
const level1Count = (hierarchy.children || []).filter(n => n.value > 0).length;
const level2Count = (hierarchy.children || []).reduce((sum, n1) => sum + ((n1.children || []).filter(n => n.value > 0).length), 0);
const level3Count = leafNodes.length;

if (totalValue > 0) {
    const totalCard = summaryContainer.append('div')
        .style('background', '#e7f3ff')
        .style('border', '2px solid #0d6efd')
        .style('border-radius', '8px')
        .style('padding', '16px')
        .style('text-align', 'center');
    
    // Use label from payload metadata if available
    let totalLabel = 'Total';
    
    if (payload.summary && payload.summary.totalLabel) {
        totalLabel = payload.summary.totalLabel;
    } else if (payload.metadata && payload.metadata.totalLabel) {
        totalLabel = payload.metadata.totalLabel;
    } else if (payload.totalLabel) {
        totalLabel = payload.totalLabel;
    } else if (payload.summary) {
        // Extract label from the actual field name that starts with "total"
        const summaryKeys = Object.keys(payload.summary);
        const totalKey = summaryKeys.find(k => k.toLowerCase().startsWith('total'));
        
        if (totalKey) {
            // Convert camelCase or snake_case to Title Case
            // e.g., "totalPlannedCost" -> "Total Planned Cost"
            // e.g., "total_planned_cost" -> "Total Planned Cost"
            totalLabel = totalKey
                .replace(/([A-Z])/g, ' $1')  // camelCase: insert space before capitals
                .replace(/_/g, ' ')           // snake_case: replace underscores with spaces
                .split(' ')
                .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
                .join(' ')
                .trim();
        }
    }
    
    totalCard.append('div')
        .style('font-size', '14px')
        .style('font-weight', '600')
        .style('color', '#495057')
        .text(totalLabel);
    
    totalCard.append('div')
        .style('font-size', '24px')
        .style('font-weight', '700')
        .style('color', '#0d6efd')
        .style('margin', '8px 0')
        .text('$' + Math.round(totalValue).toLocaleString());
    
    // Smart detection of level names from the actual data structure
    // Infer from actual hierarchy node names first, then fallback to metadata
    let level1Name = 'Items';
    let level2Name = 'Sub-items';
    let level3Name = 'Leaf items';
    
    // Priority 1: Try to extract from chart title or payload metadata
    if (payload.title || payload.chartTitle) {
        const title = (payload.title || payload.chartTitle);
        // Extract entity names that appear after "by" - preserving full compound names
        const byMatch = title.match(/\s+by\s+(.+?)$/i);
        if (byMatch) {
            const entitiesStr = byMatch[1];
            // Split by "and", "," or "&" to get individual entity names
            const entityWords = entitiesStr.split(/\s+and\s+|\s*,\s*|\s*&\s*/i).map(w => w.trim()).filter(w => w);
            
            if (entityWords.length >= 1) {
                let firstEntity = entityWords[0].trim();
                firstEntity = firstEntity.split(/\s+/).map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ');
                level1Name = firstEntity.endsWith('s') ? firstEntity : firstEntity + 's';
            }
            
            if (entityWords.length >= 2) {
                let secondEntity = entityWords[1].trim();
                secondEntity = secondEntity.split(/\s+/).map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ');
                level2Name = secondEntity.endsWith('s') ? secondEntity : secondEntity + 's';
            }
            
            if (entityWords.length >= 3) {
                let thirdEntity = entityWords[2].trim();
                thirdEntity = thirdEntity.split(/\s+/).map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ');
                level3Name = thirdEntity.endsWith('s') ? thirdEntity : thirdEntity + 's';
            }
        }
    }
    
    // Priority 2: Skip automatic inference - only use title or metadata
    // If we couldn't extract entity names from title or metadata, don't use generic fallbacks
    
    // Priority 3: Override with explicit metadata if provided (explicit always wins)
    if (payload.summary && payload.summary.level1Name) {
        level1Name = payload.summary.level1Name;
        level2Name = payload.summary.level2Name || level2Name;
        level3Name = payload.summary.level3Name || level3Name;
    } else if (payload.metadata) {
        level1Name = payload.metadata.level1Name || level1Name;
        level2Name = payload.metadata.level2Name || level2Name;
        level3Name = payload.metadata.level3Name || level3Name;
    } else if (payload.levelNames) {
        level1Name = payload.levelNames.level1 || payload.levelNames[0] || level1Name;
        level2Name = payload.levelNames.level2 || payload.levelNames[1] || level2Name;
        level3Name = payload.levelNames.level3 || payload.levelNames[2] || level3Name;
    } else if (payload.summary) {
        // Priority 4: Try to infer from summary field names (look for breakdown patterns)
        const summaryKeys = Object.keys(payload.summary);
        const breakdownKey = summaryKeys.find(k => k.toLowerCase().includes('breakdown'));
        
        if (breakdownKey) {
            const key = breakdownKey.toLowerCase();
            // Extract entity name from breakdown key
            const match = key.match(/^(.+?)breakdown$/i);
            if (match) {
                const entityName = match[1];
                const capitalized = entityName.charAt(0).toUpperCase() + entityName.slice(1);
                level1Name = level1Count === 1 ? capitalized : capitalized + 's';
            }
        }
    }
    
    // Only show detail counts if we have proper entity names (from title or metadata)
    // Don't show generic fallback names like "Items", "Sub-items", etc.
    let details = [];
    if (level1Count > 0 && level1Name !== 'Items') details.push(`${level1Count} ${level1Name}`);
    if (level2Count > 0 && level2Name !== 'Sub-items') details.push(`${level2Count} ${level2Name}`);
    if (level3Count > 0 && level3Name !== 'Leaf items') details.push(`${level3Count} ${level3Name}`);
    
    if (details.length > 0) {
        totalCard.append('div')
            .style('font-size', '12px')
            .style('color', '#495057')
            .text(details.join(' • '));
    }
}

// Create tooltip
const tooltip = d3.select('body').append('div')
    .style('position', 'absolute')
    .style('background', 'rgba(0,0,0,0.85)')
    .style('color', '#fff')
    .style('padding', '8px 12px')
    .style('border-radius', '6px')
    .style('font-size', '12px')
    .style('pointer-events', 'none')
    .style('opacity', 0)
    .style('z-index', '10000');

// Render all nodes (not just leaves) to show hierarchy
const node = svg.selectAll('g.node')
    .data(hierarchy.descendants())
    .enter().append('g')
    .attr('class', 'node')
    .attr('transform', d => `translate(${d.x},${d.y})`);

// Draw circles with hierarchy-aware colors
node.append('circle')
    .attr('r', d => d.r)
    .attr('fill', (d,i) => {
        // Use explicit color if available, otherwise color by depth
        if (d.data.color) return d.data.color;
        return d.depth === 0 ? 'transparent' : colorScale(d.depth);
    })
    .attr('stroke', d => d.depth === 0 ? 'transparent' : '#fff')
    .attr('stroke-width', d => d.depth === 0 ? 0 : 2)
    .attr('opacity', d => d.depth === 0 ? 0 : 0.75)
    .style('cursor', d => d.depth > 0 ? 'pointer' : 'default')
    .on('mouseover', function(event, d) {
        if (d.depth === 0) return; // Skip root
        d3.select(this).transition().duration(200)
            .attr('opacity', 0.95)
            .attr('stroke-width', 3);
        
        // Build hierarchy path
        const path = d.ancestors().reverse().map(n => n.data.name).join(' → ');
        const valueText = d.value ? d.value.toLocaleString() : 'N/A';
        
        tooltip.transition().duration(200).style('opacity', 1);
        tooltip.html(`<strong>${path}</strong><br/>Value: ${valueText}`)
            .style('left', (event.pageX + 15) + 'px')
            .style('top', (event.pageY - 15) + 'px');
    })
    .on('mouseout', function(event, d) {
        if (d.depth === 0) return;
        d3.select(this).transition().duration(200)
            .attr('opacity', 0.75)
            .attr('stroke-width', 2);
        tooltip.transition().duration(200).style('opacity', 0);
    });

// Add labels (only for nodes with sufficient radius)
node.append('text')
    .attr('dy', '.3em')
    .style('text-anchor', 'middle')
    .style('font-size', d => Math.max(9, Math.min(14, d.r / 4)) + 'px')
    .style('font-weight', '600')
    .style('fill', d => d.depth === 1 ? '#fff' : '#333')
    .style('text-shadow', d => d.depth === 1 ? '0 1px 3px rgba(0,0,0,0.5)' : '0 1px 2px rgba(255,255,255,0.8)')
    .style('pointer-events', 'none')
    .text(d => {
        if (d.r < 20) return ''; // Don't show label if circle too small
        const name = d.data.name || '';
        return name.length > 15 ? name.slice(0, 12) + '...' : name;
    });

// Build hierarchical legend dynamically using computed hierarchy values
const legend = d3.select('#legend');
legend.html('');

// Change legend layout to vertical columns
legend.style('display', 'grid')
    .style('grid-template-columns', 'repeat(auto-fit, minmax(350px, 1fr))')
    .style('gap', '16px')
    .style('align-items', 'start')
    .style('justify-content', 'start');

// Get level 1 nodes from computed hierarchy
const level1 = hierarchy.children || [];

level1.forEach((node1, idx) => {
    if (!node1.value || node1.value === 0) return;
    
    // Create a container for each level1 item
    const level1Container = legend.append('div')
        .style('background', '#f8f9fa')
        .style('border', '1px solid #dee2e6')
        .style('border-radius', '6px')
        .style('padding', '12px');
    
    const color1 = colorScale(1);
    
    // Level 1 item
    level1Container.append('div')
        .style('display', 'flex')
        .style('align-items', 'center')
        .style('gap', '8px')
        .style('font-weight', '700')
        .style('font-size', '14px')
        .style('margin-bottom', '8px')
        .style('color', '#212529')
        .html(`<div class='sw' style='background:${color1}'></div><div>${node1.data.name} - $${Math.round(node1.value).toLocaleString()}</div>`);
    
    // Level 2 nodes
    const level2 = node1.children || [];
    level2.forEach(node2 => {
        if (!node2.value || node2.value === 0) return;
        
        const color2 = colorScale(2);
        level1Container.append('div')
            .style('display', 'flex')
            .style('align-items', 'center')
            .style('gap', '8px')
            .style('padding-left', '20px')
            .style('font-size', '12px')
            .style('font-weight', '600')
            .style('margin-top', '6px')
            .style('color', '#495057')
            .html(`<div class='sw' style='background:${color2}'></div><div>${node2.data.name} - $${Math.round(node2.value).toLocaleString()}</div>`);
        
        // Top 5 level 3 items
        const level3 = (node2.children || []).filter(n => n.value > 0).sort((a, b) => b.value - a.value).slice(0, 5);
        level3.forEach(node3 => {
            const color3 = colorScale(3);
            level1Container.append('div')
                .style('display', 'flex')
                .style('align-items', 'center')
                .style('gap', '8px')
                .style('padding-left', '40px')
                .style('font-size', '11px')
                .style('margin-top', '3px')
                .style('color', '#6c757d')
                .html(`<div class='sw' style='background:${color3}'></div><div>${node3.data.name} - $${Math.round(node3.value).toLocaleString()}</div>`);
        });
    });
});
})();
"""
    return tpl.replace('__DATA_VAR__', data_var)


def script_histogram(data_var='data'):
    # Expects payload: {values: [10,20,30,...], bins: 10}
    tpl = """
(function(){
const container = d3.select('#viz'); const payload = __DATA_VAR__||{};
const values = payload.values || payload.data || [];
if(!values.length){ container.append('div').text('No histogram data (expect values: [])'); return; }
const bins = payload.bins || 10;
const rect = container.node().getBoundingClientRect(); const width = Math.max(320, rect.width)-40; const height = Math.max(240, rect.height)-40;
const svg = container.append('svg').attr('width', width).attr('height', height).append('g').attr('transform','translate(20,10)');
const x = d3.scaleLinear().domain(d3.extent(values)).range([0, width-60]);
const histogram = d3.bin().domain(x.domain()).thresholds(bins);
const binsData = histogram(values);
const y = d3.scaleLinear().domain([0, d3.max(binsData, d=>d.length)||1]).range([height-60,0]);
svg.selectAll('rect').data(binsData).enter().append('rect').attr('x', d=>x(d.x0)).attr('y', d=>y(d.length)).attr('width', d=>Math.max(1, x(d.x1)-x(d.x0)-1)).attr('height', d=>height-60 - y(d.length)).attr('fill','#69b3a2');
function wrapText(text, width) {
  text.each(function() {
    const text = d3.select(this), words = text.text().split(/\s+/).reverse();
    let word, line = [], lineNumber = 0;
    const lineHeight = 1.1, y = text.attr('y'), dy = parseFloat(text.attr('dy')) || 0;
    let tspan = text.text(null).append('tspan').attr('x', 0).attr('y', y).attr('dy', dy + 'em');
    while (word = words.pop()) {
      line.push(word); tspan.text(line.join(' '));
      if (tspan.node().getComputedTextLength() > width) {
        line.pop(); tspan.text(line.join(' ')); line = [word];
        tspan = text.append('tspan').attr('x', 0).attr('y', y).attr('dy', ++lineNumber * lineHeight + dy + 'em').text(word);
      }
    }
  });
}
const xAxis = svg.append('g').attr('transform',`translate(0,${height-60})`).call(d3.axisBottom(x));
xAxis.selectAll('text').style('text-anchor','middle').call(wrapText, 60);
})();
"""
    return tpl.replace('__DATA_VAR__', data_var)


def script_horizontal_bar(data_var='data'):
    """
    Generates D3.js script for horizontal bar chart.
    
    Args:
        data_var (str): JavaScript variable name containing the chart data
    
    Returns:
        str: JavaScript code for D3 horizontal bar chart
        
    Expected data format: {labels: [], values: []} or {labels: [], data: []}
    Creates responsive horizontal bar chart with:
    - Bars extending horizontally (x-axis shows values)
    - Labels displayed on y-axis
    - Automatic scaling and color coding
    - Compact layout suitable for long category names
    """
    # Expects payload: {labels:[], values:[]}
    tpl = """
(function(){
const container = d3.select('#viz'); const payload = __DATA_VAR__||{}; const labels = payload.labels||[]; const vals = payload.values||payload.data||[];
if(!labels.length){ container.append('div').text('No horizontal bar data'); return; }

// Build summary statistics panel
const summaryContainer = d3.select('#summary');
summaryContainer.html('');

const total = vals.reduce((sum, v) => sum + (v || 0), 0);

if (total > 0) {
  // Add grand total card
  const totalCard = summaryContainer.append('div')
    .style('background', '#e7f3ff')
    .style('border', '2px solid #0d6efd')
    .style('border-radius', '8px')
    .style('padding', '16px')
    .style('text-align', 'center')
    .style('grid-column', '1 / -1');
  
  totalCard.append('div')
    .style('font-size', '13px')
    .style('font-weight', '600')
    .style('color', '#495057')
    .text('Total');
  
  totalCard.append('div')
    .style('font-size', '28px')
    .style('font-weight', '700')
    .style('color', '#0d6efd')
    .text(Math.round(total).toLocaleString());
  
  // Add per-item cards
  labels.forEach((label, idx) => {
    const value = vals[idx] || 0;
    if (value > 0) {
      const card = summaryContainer.append('div')
        .style('background', '#f8f9fa')
        .style('border', '1px solid #dee2e6')
        .style('border-radius', '6px')
        .style('padding', '12px');
      
      card.append('div')
        .style('font-size', '12px')
        .style('color', '#6c757d')
        .style('font-weight', '500')
        .style('margin-bottom', '4px')
        .text(label);
      
      card.append('div')
        .style('font-size', '20px')
        .style('font-weight', '700')
        .style('color', '#212529')
        .text(Math.round(value).toLocaleString());
    }
  });
}

// Calculate max label length for left margin
const maxLabelLength = Math.max(...labels.map(l => l.length));
const leftMargin = Math.max(120, maxLabelLength * 7);

const rect = container.node().getBoundingClientRect(); const width = Math.max(320, rect.width)-40; const height = Math.max(240, rect.height)-40;
const svg = container.append('svg').attr('width', width).attr('height', height).append('g').attr('transform',`translate(${leftMargin},10)`);
const y = d3.scaleBand().domain(labels).range([0, height-60]).padding(0.1);
const x = d3.scaleLinear().domain([0, d3.max(vals)||0]).range([0, width-leftMargin-60]);

svg.selectAll('rect').data(labels).enter().append('rect').attr('y', d=>y(d)).attr('x',0).attr('height', y.bandwidth()).attr('width', (d,i)=>x(vals[i]||0)).attr('fill','#4C78A8');

// Y-axis with text wrapping for long labels
function wrapText(text, width) {
  text.each(function() {
    const text = d3.select(this);
    const words = text.text().split(/\s+/).reverse();
    let word, line = [], lineNumber = 0;
    const lineHeight = 1.1;
    const y = text.attr('y');
    const dy = parseFloat(text.attr('dy')) || 0;
    let tspan = text.text(null).append('tspan').attr('x', -10).attr('y', y).attr('dy', dy + 'em');
    
    while (word = words.pop()) {
      line.push(word);
      tspan.text(line.join(' '));
      if (tspan.node().getComputedTextLength() > width) {
        line.pop();
        tspan.text(line.join(' '));
        line = [word];
        tspan = text.append('tspan').attr('x', -10).attr('y', y).attr('dy', ++lineNumber * lineHeight + dy + 'em').text(word);
      }
    }
  });
}

const yAxis = svg.append('g').call(d3.axisLeft(y));
yAxis.selectAll('text').style('text-anchor','end').style('font-size','11px').call(wrapText, leftMargin - 20);
})();
"""
    return tpl.replace('__DATA_VAR__', data_var)


def script_grouped_bar(data_var='data'):
    """
    Generates D3.js script for grouped bar chart with interactive features and summary panels.
    
    Args:
        data_var (str): JavaScript variable name containing the chart data
    
    Returns:
        str: JavaScript code for D3 grouped bar chart
        
    Expected data format: {labels: [], datasets: [{label: str, data: [], backgroundColor: str}]}
    Creates responsive grouped bar chart with:
    - Summary statistics cards showing Total/Avg/Max per dataset
    - Multiple datasets displayed as grouped bars per category
    - Interactive tooltips showing project name, month, and value
    - Dynamic legend with color-coded project names
    - Dual axes (x: categories, y: values)
    - Smooth hover animations and transitions
    
    This is the enhanced version with summary panels, legend and tooltip functionality.
    """
    # Expects payload: {labels:[], datasets:[{label:'A', data:[]}, ...]}
    tpl = """
(function(){
const payload = __DATA_VAR__||{}; const labels = payload.labels||[]; const datasets = payload.datasets||[]; if(!labels.length||!datasets.length){ d3.select('#viz').append('div').text('No grouped bar data'); return; }

// Calculate and display summary statistics
const summaryContainer = d3.select('#summary');
summaryContainer.html('');

// Extract level names from metadata (needed for both paths)
let level1Name = 'Items';
let level2Name = 'Sub-items';
let level3Name = 'Projects';

if (payload.summary && payload.summary.level1Name) {
  level1Name = payload.summary.level1Name;
  level2Name = payload.summary.level2Name || 'Sub-items';
  level3Name = payload.summary.level3Name || 'Projects';
} else if (payload.metadata) {
  level1Name = payload.metadata.level1Name || level1Name;
  level2Name = payload.metadata.level2Name || level2Name;
  level3Name = payload.metadata.level3Name || level3Name;
} else if (payload.levelNames) {
  level1Name = payload.levelNames[0] || payload.levelNames.level1 || level1Name;
  level2Name = payload.levelNames[1] || payload.levelNames.level2 || level2Name;
} else if (payload.summary) {
  // Infer level names from field names containing "breakdown"
  const summaryKeys = Object.keys(payload.summary);
  const breakdownKey = summaryKeys.find(k => k.toLowerCase().includes('breakdown'));
  
  if (breakdownKey) {
    // Extract the entity name from the key (e.g., "entityBreakdown" -> "Entity")
    const match = breakdownKey.match(/^(.+?)Breakdown$/i);
    if (match) {
      const entityName = match[1];
      // Convert to title case and pluralize for level1
      level1Name = entityName.charAt(0).toUpperCase() + entityName.slice(1) + 's';
      
      // For level2, keep generic since we can't know the structure without hardcoded checks
      level2Name = 'Subcategories';
    }
  }
}

// Smart detection: Check if data contains hierarchical structure or flat structure
// Hierarchical: {name, children: [{name, children: [...]}]}
// Flat: {labels: [], datasets: [{label, data: []}]}

let hierarchyData = null;
let isHierarchical = false;

// Check if payload contains hierarchical data structure
if (payload.name && payload.children) {
  hierarchyData = payload;
  isHierarchical = true;
} else if (payload.hierarchy) {
  hierarchyData = payload.hierarchy;
  isHierarchical = true;
}

if (isHierarchical && hierarchyData) {
  // HIERARCHICAL PATH: Build D3 hierarchy and display recursively
  const hierarchy = d3.hierarchy(hierarchyData)
    .sum(d => {
      if (d.children && d.children.length > 0) return 0;
      return d.value || 0;
    })
    .sort((a, b) => b.value - a.value);
  
  // Recursive function to build nested summary cards
  function buildHierarchyCards(node, container, level = 1) {
    if (!node.value || node.value === 0) return;
    
    const card = container.append('div')
      .style('background', level === 1 ? '#f8f9fa' : '#fff')
      .style('border', level === 1 ? '2px solid #dee2e6' : 'none')
      .style('border-left', level > 1 ? '3px solid #0d6efd' : 'none')
      .style('border-radius', level === 1 ? '8px' : '4px')
      .style('padding', level === 1 ? '16px' : '12px')
      .style('margin', level === 1 ? '0 0 16px 0' : '8px 0')
      .style('margin-left', level > 2 ? '12px' : '0');
    
    card.append('div')
      .style('font-size', level === 1 ? '16px' : '14px')
      .style('font-weight', level === 1 ? '700' : '600')
      .style('color', level === 1 ? '#212529' : '#495057')
      .style('margin-bottom', level === 1 ? '8px' : '4px')
      .text(node.data.name);
    
    card.append('div')
      .style('font-size', level === 1 ? '20px' : '14px')
      .style('font-weight', '700')
      .style('color', '#0d6efd')
      .style('margin-bottom', level === 1 ? '12px' : '8px')
      .text('$' + Math.round(node.value).toLocaleString());
    
    // Recursively process children
    if (node.children && node.children.length > 0) {
      const activeChildren = node.children.filter(n => n.value > 0);
      activeChildren.forEach(child => {
        buildHierarchyCards(child, card, level + 1);
      });
    }
  }
  
  // Build cards from root's children
  const rootChildren = hierarchy.children || [];
  rootChildren.forEach(node => {
    buildHierarchyCards(node, summaryContainer, 1);
  });
  
  // Add total summary
  const grandTotal = hierarchy.value || 0;
  if (grandTotal > 0) {
    const totalCard = summaryContainer.append('div')
      .style('background', '#e7f3ff')
      .style('border', '2px solid #0d6efd')
      .style('border-radius', '8px')
      .style('padding', '12px')
      .style('text-align', 'center');
    
    let totalLabel = 'Total';
    if (payload.summary && payload.summary.totalLabel) {
      totalLabel = payload.summary.totalLabel;
    }
    
    totalCard.append('div')
      .style('font-size', '12px')
      .style('font-weight', '600')
      .style('color', '#495057')
      .text(totalLabel);
    
    totalCard.append('div')
      .style('font-size', '20px')
      .style('font-weight', '700')
      .style('color', '#0d6efd')
      .text('$' + Math.round(grandTotal).toLocaleString());
  }
  
} else {
  // FLAT PATH: Handle {labels, datasets} structure (2 levels max)

  // Parse labels to detect if they contain multi-level info
  const parsedLabels = labels.map(label => {
    // Try splitting by newline first
    let parts = label.split(/[\\n\\r]+/);
    if (parts.length === 1) {
      // Try common delimiters: " - ", " | ", " / ", " > "
      const delimiters = [' - ', ' | ', ' / ', ' > ', ': '];
      for (const delim of delimiters) {
        if (label.includes(delim)) {
          parts = label.split(delim);
          break;
        }
      }
    }
    if (parts.length > 1) {
      return {level1: parts[0].trim(), level2: parts[1].trim(), original: label};
    }
    return {level1: label, level2: null, original: label};
  });
  
  // Parse labels to detect hierarchy and infer entity names from actual data
  const hasHierarchy = parsedLabels.some(p => p.level2 !== null);
  
  // Priority 1: Try to infer names from the chart title or payload metadata fields
  if (payload.title || payload.chartTitle) {
    const title = (payload.title || payload.chartTitle);
    // Extract entity names that appear after "by" - preserving full compound names
    // Example: "Costs by Portfolio and Product Line" -> ["Portfolio", "Product Line"]
    const byMatch = title.match(/\s+by\s+(.+?)$/i);
    if (byMatch) {
      const entitiesStr = byMatch[1];
      // Split by "and", "," or "&" to get individual entity names
      const entityWords = entitiesStr.split(/\s+and\s+|\s*,\s*|\s*&\s*/i).map(w => w.trim()).filter(w => w);
      
      if (entityWords.length >= 1) {
        // First entity type becomes level1Name (keep full phrase, just capitalize and pluralize)
        let firstEntity = entityWords[0].trim();
        // Capitalize first letter of each word
        firstEntity = firstEntity.split(/\s+/).map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ');
        // Pluralize if not already plural
        if (!firstEntity.endsWith('s')) {
          level1Name = firstEntity + 's';
        } else {
          level1Name = firstEntity;
        }
      }
      
      if (entityWords.length >= 2) {
        // Second entity type becomes level2Name (keep full phrase)
        let secondEntity = entityWords[1].trim();
        // Capitalize first letter of each word
        secondEntity = secondEntity.split(/\s+/).map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ');
        // Pluralize if not already plural
        if (!secondEntity.endsWith('s')) {
          level2Name = secondEntity + 's';
        } else {
          level2Name = secondEntity;
        }
      }
      
      if (entityWords.length >= 3) {
        // Third entity type becomes level3Name (keep full phrase)
        let thirdEntity = entityWords[2].trim();
        // Capitalize first letter of each word
        thirdEntity = thirdEntity.split(/\s+/).map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ');
        // Pluralize if not already plural
        if (!thirdEntity.endsWith('s')) {
          level3Name = thirdEntity + 's';
        } else {
          level3Name = thirdEntity;
        }
      }
    }
  }
  
  // Priority 2: Skip automatic inference - only use title or metadata
  // If we couldn't extract entity names from title or metadata, don't use generic fallbacks
  
  // Priority 3: Override with explicit metadata if provided (explicit always wins)
  if (payload.summary && payload.summary.level1Name) {
    level1Name = payload.summary.level1Name;
  }
  if (payload.summary && payload.summary.level2Name) {
    level2Name = payload.summary.level2Name;
  }
  if (payload.summary && payload.summary.level3Name) {
    level3Name = payload.summary.level3Name;
  }
  
  // Group by level1
  const level1Groups = {};
  parsedLabels.forEach((parsed, idx) => {
    if (!level1Groups[parsed.level1]) {
      level1Groups[parsed.level1] = [];
    }
    level1Groups[parsed.level1].push({...parsed, index: idx});
  });
  
  // Build nested hierarchy: Level1 -> Level2 -> Items
  Object.keys(level1Groups).forEach(level1Item => {
    const level1Items = level1Groups[level1Item];
    
    // Calculate level1 total
    let level1Total = 0;
    const level2Data = {};
    
    level1Items.forEach(item => {
      const level2Item = item.level2;
      if (level2Item && !level2Data[level2Item]) {
        level2Data[level2Item] = [];
      }
      
      // Find all datasets with data for this label
      datasets.forEach(ds => {
        const value = ds.data[item.index] || 0;
        if (value > 0) {
          level1Total += value;
          if (level2Item) {
            // Has level2 in label - use it
            level2Data[level2Item].push({
              name: ds.label,
              value: value,
              color: ds.backgroundColor
            });
          } else {
            // No level2 in label - dataset itself is level2
            // Parse dataset label to extract level2 if it contains delimiter
            let datasetLevel2 = ds.label;
            const delimiterMatch = ds.label.match(/^(.+?)\s*[-|\/>\:]\s*(.+)$/);
            if (delimiterMatch) {
              datasetLevel2 = delimiterMatch[1].trim();
            }
            
            if (!level2Data[datasetLevel2]) {
              level2Data[datasetLevel2] = [];
            }
            level2Data[datasetLevel2].push({
              name: ds.label,
              value: value,
              color: ds.backgroundColor
            });
          }
        }
      });
    });
    
    if (level1Total === 0) return; // Skip empty items
    
    // Create Level 1 card
    const card1 = summaryContainer.append('div')
      .style('background', '#f8f9fa')
      .style('border', '2px solid #dee2e6')
      .style('border-radius', '8px')
      .style('padding', '16px')
      .style('margin-bottom', '16px');
    
    card1.append('div')
      .style('font-size', '16px')
      .style('font-weight', '700')
      .style('color', '#212529')
      .style('margin-bottom', '8px')
      .text(level1Item);
    
    card1.append('div')
      .style('font-size', '20px')
      .style('font-weight', '700')
      .style('color', '#0d6efd')
      .style('margin-bottom', '12px')
      .text('$' + Math.round(level1Total).toLocaleString());
    
    // Add Level 2 items under Level 1
    Object.keys(level2Data).forEach(level2Item => {
      const dataItems = level2Data[level2Item];
      if (dataItems.length === 0) return;
      
      const level2Total = dataItems.reduce((sum, p) => sum + p.value, 0);
      
      const card2 = card1.append('div')
        .style('background', '#fff')
        .style('border-left', '3px solid #0d6efd')
        .style('padding', '12px')
        .style('margin', '8px 0')
        .style('border-radius', '4px');
      
      card2.append('div')
        .style('font-size', '14px')
        .style('font-weight', '600')
        .style('color', '#495057')
        .style('margin-bottom', '8px')
        .text(level2Item + ' - $' + Math.round(level2Total).toLocaleString());
      
      // Add Level 3 items under Level 2
      dataItems.forEach(dataItem => {
        card2.append('div')
          .style('font-size', '12px')
          .style('color', '#6c757d')
          .style('padding-left', '12px')
          .style('margin', '4px 0')
          .html(`<span style="display:inline-block;width:12px;height:12px;background:${dataItem.color};border-radius:2px;margin-right:8px"></span>\u2022 ${dataItem.name}: <span style="font-weight:600">$${Math.round(dataItem.value).toLocaleString()}</span>`);
      });
    });
  });

  // Add total summary card
  const grandTotal = datasets.reduce((sum, ds) => {
    return sum + ds.data.reduce((s, v) => s + (v || 0), 0);
  }, 0);

  if (grandTotal > 0) {
    // Count unique level1 items
    const activeLevel1 = Object.keys(level1Groups).length;
    
    // Count unique level2 items across all level1 groups
    let activeLevel2 = 0;
    const allLevel2Items = new Set();
    
    Object.keys(level1Groups).forEach(level1Key => {
      const level1Items = level1Groups[level1Key];
      
      // Check if we have hierarchy in labels
      const hasLevel2InLabels = level1Items.some(item => item.level2 !== null);
      
      if (hasLevel2InLabels) {
        // Count unique level2 from labels
        level1Items.forEach(item => {
          if (item.level2) {
            allLevel2Items.add(item.level2);
          }
        });
      } else {
        // Count unique level2 from dataset labels (when no hierarchy in main labels)
        level1Items.forEach(item => {
          datasets.forEach(ds => {
            const value = ds.data[item.index] || 0;
            if (value > 0) {
              // Extract level2 from dataset label
              let datasetLevel2 = ds.label;
              const delimiterMatch = ds.label.match(/^(.+?)\s*[-|\/>\:]\s*(.+)$/);
              if (delimiterMatch) {
                datasetLevel2 = delimiterMatch[1].trim();
              }
              allLevel2Items.add(datasetLevel2);
            }
          });
        });
      }
    });
    
    activeLevel2 = allLevel2Items.size;
    
    // Count unique level3 items (datasets with non-zero values)
    const activeLevel3Items = new Set();
    datasets.forEach(ds => {
      const hasData = ds.data.some(v => v > 0);
      if (hasData) {
        activeLevel3Items.add(ds.label);
      }
    });
    const activeLevel3 = activeLevel3Items.size;
    
    const totalCard = summaryContainer.append('div')
      .style('background', '#e7f3ff')
      .style('border', '2px solid #0d6efd')
      .style('border-radius', '8px')
      .style('padding', '12px')
      .style('text-align', 'center');
    
    let totalLabel = 'Total';
    if (payload.summary && payload.summary.totalLabel) {
      totalLabel = payload.summary.totalLabel;
    } else if (payload.metadata && payload.metadata.totalLabel) {
      totalLabel = payload.metadata.totalLabel;
    } else if (payload.summary) {
      const summaryKeys = Object.keys(payload.summary);
      const totalKey = summaryKeys.find(k => k.toLowerCase().startsWith('total'));
      if (totalKey) {
        totalLabel = totalKey
          .replace(/([A-Z])/g, ' $1')
          .replace(/_/g, ' ')
          .split(' ')
          .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
          .join(' ')
          .trim();
      }
    }
    
    totalCard.append('div')
      .style('font-size', '12px')
      .style('font-weight', '600')
      .style('color', '#495057')
      .text(totalLabel);
    
    totalCard.append('div')
      .style('font-size', '20px')
      .style('font-weight', '700')
      .style('color', '#0d6efd')
      .style('margin', '4px 0')
      .text('$' + Math.round(grandTotal).toLocaleString());
    
    // Only show detail counts if we have proper entity names (from title or metadata)
    // Don't show generic fallback names like "Items", "Sub-items", "Projects"
    if (level1Name !== 'Items' && level2Name !== 'Sub-items' && level3Name !== 'Projects') {
      totalCard.append('div')
        .style('font-size', '11px')
        .style('color', '#495057')
        .text(`${activeLevel1} ${level1Name} • ${activeLevel2} ${level2Name} • ${activeLevel3} ${level3Name}`);
    }
  }
}

const rect = d3.select('#viz').node().getBoundingClientRect(); const width = Math.max(320, rect.width)-60; const height = Math.max(240, rect.height)-60;
const svg = d3.select('#viz').append('svg').attr('width', width).attr('height', height).append('g').attr('transform','translate(40,20)');
const x0 = d3.scaleBand().domain(labels).range([0, width-80]).padding(0.2);
const x1 = d3.scaleBand().domain(d3.range(datasets.length)).range([0, x0.bandwidth()]).padding(0.05);
const y = d3.scaleLinear().domain([0, d3.max(datasets, ds=>d3.max(ds.data||[]))||0]).range([height-80,0]);
const colors = datasets.map((d,i)=>d.backgroundColor||d.borderColor||d3.schemeTableau10[i%10]);

// Create tooltip div
const tooltip = d3.select('body').append('div')
  .attr('class', 'tooltip')
  .style('opacity', 0)
  .style('position', 'absolute')
  .style('background', 'rgba(0,0,0,0.8)')
  .style('color', 'white')
  .style('padding', '8px 12px')
  .style('border-radius', '4px')
  .style('font-size', '12px')
  .style('font-family', 'Segoe UI, Arial, sans-serif')
  .style('pointer-events', 'none')
  .style('z-index', '1000');

const groups = svg.selectAll('g').data(labels).enter().append('g').attr('transform', d=>`translate(${x0(d)},0)`);
groups.selectAll('rect').data((d,i)=>datasets.map((ds,j)=>({v:ds.data[i]||0, color: ds.backgroundColor||ds.borderColor, label: ds.label, month: d, datasetIndex: j}))).enter().append('rect')
  .attr('x',(d,i)=>x1(i))
  .attr('y',d=>y(d.v))
  .attr('width',x1.bandwidth())
  .attr('height',d=>height-80 - y(d.v))
  .attr('fill',d=>d.color||'#777')
  .on('mouseover', function(event, d) {
    tooltip.transition().duration(200).style('opacity', .9);
    tooltip.html(`<strong>${d.label}</strong><br/>${d.month}: ${d.v}%`)
      .style('left', (event.pageX + 10) + 'px')
      .style('top', (event.pageY - 28) + 'px');
  })
  .on('mouseout', function(d) {
    tooltip.transition().duration(500).style('opacity', 0);
  });

// X-axis with word wrapping for long labels
function wrapText(text, width) {
  text.each(function() {
    const text = d3.select(this), words = text.text().split(/\s+/).reverse();
    let word, line = [], lineNumber = 0;
    const lineHeight = 1.1, y = text.attr('y'), dy = parseFloat(text.attr('dy')) || 0;
    let tspan = text.text(null).append('tspan').attr('x', 0).attr('y', y).attr('dy', dy + 'em');
    while (word = words.pop()) {
      line.push(word); tspan.text(line.join(' '));
      if (tspan.node().getComputedTextLength() > width) {
        line.pop(); tspan.text(line.join(' ')); line = [word];
        tspan = text.append('tspan').attr('x', 0).attr('y', y).attr('dy', ++lineNumber * lineHeight + dy + 'em').text(word);
      }
    }
  });
}
const xAxisGroup = svg.append('g').attr('transform',`translate(0,${height-80})`).call(d3.axisBottom(x0));
xAxisGroup.selectAll('text').style('text-anchor','middle').style('font-size','11px').call(wrapText, x0.bandwidth());

// Remove default text labels and add wrapped text
xAxisGroup.selectAll('text').remove();
xAxisGroup.selectAll('.label-wrap')
  .data(labels)
  .enter()
  .append('foreignObject')
  .attr('x', d => x0(d) + x0.bandwidth()/2 - 50)
  .attr('y', 5)
  .attr('width', 100)
  .attr('height', 60)
  .append('xhtml:div')
  .style('font-size', '11px')
  .style('text-align', 'center')
  .style('word-wrap', 'break-word')
  .style('line-height', '1.2')
  .style('color', '#666')
  .text(d => d);

svg.append('g').call(d3.axisLeft(y));

// Generate hierarchical legend with 3 levels matching summary structure
const legend = d3.select('#legend');
legend.html('');

// Change legend layout to grid
legend.style('display', 'grid')
  .style('grid-template-columns', 'repeat(auto-fit, minmax(350px, 1fr))')
  .style('gap', '16px');

// Parse labels for hierarchy
const parsedLabelsForLegend = labels.map(label => {
  // Try splitting by newline first
  let parts = label.split(/[\\n\\r]+/);
  if (parts.length === 1) {
    // Try common delimiters: " - ", " | ", " / ", " > "
    const delimiters = [' - ', ' | ', ' / ', ' > ', ': '];
    for (const delim of delimiters) {
      if (label.includes(delim)) {
        parts = label.split(delim);
        break;
      }
    }
  }
  if (parts.length > 1) {
    return {level1: parts[0].trim(), level2: parts[1].trim(), original: label};
  }
  return {level1: label, level2: null, original: label};
});

// Group by level1
const level1GroupsLegend = {};
parsedLabelsForLegend.forEach((parsed, idx) => {
  if (!level1GroupsLegend[parsed.level1]) {
    level1GroupsLegend[parsed.level1] = [];
  }
  level1GroupsLegend[parsed.level1].push({...parsed, index: idx});
});

// Build legend hierarchy
Object.keys(level1GroupsLegend).forEach(level1Item => {
  const level1Items = level1GroupsLegend[level1Item];
  
  // Calculate level1 total and organize by level2
  let level1Total = 0;
  const level2Items = {};
  
  level1Items.forEach(item => {
    const level2Item = item.level2 || 'Main';
    if (!level2Items[level2Item]) {
      level2Items[level2Item] = [];
    }
    
    datasets.forEach(ds => {
      const value = ds.data[item.index] || 0;
      if (value > 0) {
        level1Total += value;
        level2Items[level2Item].push({
          name: ds.label,
          value: value,
          color: ds.backgroundColor
        });
      }
    });
  });
  
  if (level1Total === 0) return;
  
  // Create level1 container
  const level1Container = legend.append('div')
    .style('background', '#f8f9fa')
    .style('border', '1px solid #dee2e6')
    .style('border-radius', '6px')
    .style('padding', '12px');
  
  // Level 1 header
  level1Container.append('div')
    .style('font-weight', '700')
    .style('font-size', '14px')
    .style('margin-bottom', '8px')
    .style('color', '#212529')
    .text(level1Item + ' - $' + Math.round(level1Total).toLocaleString());
  
  // Level 2 items and Level 3 data under level1
  Object.keys(level2Items).forEach(level2Item => {
    const dataItems = level2Items[level2Item];
    if (dataItems.length === 0) return;
    
    const level2Total = dataItems.reduce((sum, p) => sum + p.value, 0);
    
    // Level 2 header
    level1Container.append('div')
      .style('padding-left', '12px')
      .style('font-weight', '600')
      .style('font-size', '13px')
      .style('color', '#495057')
      .style('margin-top', '6px')
      .style('margin-bottom', '4px')
      .text(level2Item + ' - $' + Math.round(level2Total).toLocaleString());
    
    // Level 3 data under Level 2 (show top 5)
    const topItems = dataItems.sort((a, b) => b.value - a.value).slice(0, 5);
    topItems.forEach(dataItem => {
      level1Container.append('div')
        .style('padding-left', '24px')
        .style('display', 'flex')
        .style('align-items', 'center')
        .style('gap', '8px')
        .style('margin', '2px 0')
        .style('font-size', '12px')
        .style('color', '#6c757d')
        .html(`<div class='sw' style='background:${dataItem.color}'></div><div>${dataItem.name} - $${Math.round(dataItem.value).toLocaleString()}</div>`);
    });
  });
});
})();
"""
    return tpl.replace('__DATA_VAR__', data_var)


def script_scatter(data_var='data'):
    """
    Generates D3.js script for scatter plot visualization.
    
    Args:
        data_var (str): JavaScript variable name containing the chart data
    
    Returns:
        str: JavaScript code for D3 scatter plot
        
    Expected data format: [{x: number, y: number, label: str}] or {points: [...]}
    Creates responsive scatter plot with:
    - Two-dimensional data points plotted on X-Y axes
    - Automatic domain calculation from data extents
    - Optional point sizing via 'r' property
    - Color coding support per point
    - Linear scaling for both axes
    - Suitable for correlation and distribution analysis
    """
    # Expects payload: [{x:.., y:.., label:?}, ...] or {points:[...]}
    tpl = """
(function(){
const container = d3.select('#viz'); const payload = __DATA_VAR__||{}; const pts = payload.points || payload.data || [];
if(!pts.length){ container.append('div').text('No scatter data'); return; }
const rect = container.node().getBoundingClientRect(); const width = Math.max(320, rect.width)-40; const height = Math.max(240, rect.height)-40;
const svg = container.append('svg').attr('width', width).attr('height', height).append('g').attr('transform','translate(40,20)');
const x = d3.scaleLinear().domain(d3.extent(pts, d=>+d.x||0)).range([0, width-80]); const y = d3.scaleLinear().domain(d3.extent(pts, d=>+d.y||0)).range([height-80,0]);
function wrapText(text, width) {
  text.each(function() {
    const text = d3.select(this), words = text.text().split(/\s+/).reverse();
    let word, line = [], lineNumber = 0;
    const lineHeight = 1.1, yPos = text.attr('y'), dy = parseFloat(text.attr('dy')) || 0;
    let tspan = text.text(null).append('tspan').attr('x', 0).attr('y', yPos).attr('dy', dy + 'em');
    while (word = words.pop()) {
      line.push(word); tspan.text(line.join(' '));
      if (tspan.node().getComputedTextLength() > width) {
        line.pop(); tspan.text(line.join(' ')); line = [word];
        tspan = text.append('tspan').attr('x', 0).attr('y', yPos).attr('dy', ++lineNumber * lineHeight + dy + 'em').text(word);
      }
    }
  });
}
const xAxis = svg.append('g').attr('transform',`translate(0,${height-80})`).call(d3.axisBottom(x));
xAxis.selectAll('text').style('text-anchor','middle').call(wrapText, 60);
svg.append('g').call(d3.axisLeft(y));
svg.selectAll('circle').data(pts).enter().append('circle').attr('cx',d=>x(+d.x||0)).attr('cy',d=>y(+d.y||0)).attr('r', d=>+d.r||4).attr('fill', d=>d.color||'#1f77b4').attr('opacity',0.9);
})();
"""
    return tpl.replace('__DATA_VAR__', data_var)


def script_treemap_placeholder(data_var='data'):
    """
    Generates D3.js script for treemap visualization (placeholder implementation).
    
    Args:
        data_var (str): JavaScript variable name containing the chart data
    
    Returns:
        str: JavaScript code for D3 treemap chart
        
    Expected data format: {name: 'root', children: [{name: str, value: number}]}
    Creates basic treemap with:
    - Hierarchical rectangular space-filling layout
    - Proportional rectangle sizes based on values
    - Nested structure representation
    - Color coding for different categories
    - Space-efficient visualization for hierarchical data
    
    Note: This is a placeholder implementation for basic treemap functionality.
    """
    # Expects hierarchical payload like {name:'root', children:[{name:'A', value:10}, ...]}
    tpl = """
(function(){
const container = d3.select('#viz'); const payload = __DATA_VAR__||{}; const root = payload;
if(!root || !root.children){ container.append('div').text('Treemap expects hierarchical data with children'); return; }
const rect = container.node().getBoundingClientRect(); const width = Math.max(320, rect.width)-40; const height = Math.max(320, rect.height)-40;
const svg = container.append('svg').attr('width', width).attr('height', height);
var hierarchy = d3.hierarchy(root).sum(d=>d.value||0);
d3.treemap().size([width,height]).padding(2)(hierarchy);
var nodes = svg.selectAll('g').data(hierarchy.leaves()).enter().append('g').attr('transform', d=>'translate('+d.x0+','+d.y0+')');
nodes.append('rect').attr('width', d=>d.x1-d.x0).attr('height', d=>d.y1-d.y0).attr('fill', (d,i)=>d.data.color||d3.schemeTableau10[i%10]);
nodes.append('text').attr('x',4).attr('y',14).text(d=>d.data.name||'');
})();
"""
    return tpl.replace('__DATA_VAR__', data_var)


def script_tree(data_var='data'):
    # Expects hierarchical payload: {name:'root', children:[...]} -> renders a simple dendrogram
    tpl = """
(function(){
const data = __DATA_VAR__ || {};
if(!data || !data.children){ d3.select('#viz').append('div').text('Tree expects hierarchical data'); return; }
const width = Math.max(320, document.getElementById('viz').clientWidth||400), height = Math.max(320, document.getElementById('viz').clientHeight||400);
const root = d3.hierarchy(data);
const tree = d3.tree().size([height-40, width-160]); tree(root);
const svg = d3.select('#viz').append('svg').attr('width', width).attr('height', height).append('g').attr('transform','translate(80,20)');
svg.selectAll('line').data(root.links()).enter().append('line').attr('x1',d=>d.source.y).attr('y1',d=>d.source.x).attr('x2',d=>d.target.y).attr('y2',d=>d.target.x).attr('stroke','#999');
svg.selectAll('text').data(root.descendants()).enter().append('text').attr('x',d=>d.y).attr('y',d=>d.x).text(d=>d.data.name||'').attr('font-size',10);
})();
"""
    return tpl.replace('__DATA_VAR__', data_var)


def script_force(data_var='data'):
    # Expects payload: {nodes:[{id:...}], links:[{source:..., target:...}]}
    tpl = """
(function(){
const payload = __DATA_VAR__||{}; const nodes = payload.nodes||[]; const links = payload.links||[]; if(!nodes.length){ d3.select('#viz').append('div').text('No force graph nodes'); return; }
const width = Math.max(320, document.getElementById('viz').clientWidth||600), height = Math.max(320, document.getElementById('viz').clientHeight||400);
const svg = d3.select('#viz').append('svg').attr('width', width).attr('height', height);
const sim = d3.forceSimulation(nodes).force('charge', d3.forceManyBody().strength(-200)).force('link', d3.forceLink(links).id(d=>d.id).distance(60)).force('center', d3.forceCenter(width/2,height/2));
const link = svg.append('g').selectAll('line').data(links).enter().append('line').attr('stroke','#999');
const node = svg.append('g').selectAll('circle').data(nodes).enter().append('circle').attr('r',6).attr('fill','#1f77b4');
sim.on('tick', ()=>{ link.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y).attr('x2',d=>d.target.x).attr('y2',d=>d.target.y); node.attr('cx',d=>d.x).attr('cy',d=>d.y); });
})();
"""
    return tpl.replace('__DATA_VAR__', data_var)


def script_chord_placeholder(data_var='data'):
    # Placeholder: expects adjacency matrix; implementing full chord diagram is left as an exercise
    tpl = """
(function(){ d3.select('#viz').append('div').text('Chord diagram placeholder - requires adjacency matrix payload'); })();
"""
    return tpl.replace('__DATA_VAR__', data_var)


def script_sankey_placeholder(data_var='data'):
    tpl = """
(function(){ d3.select('#viz').append('div').text('Sankey placeholder - requires d3-sankey plugin and proper payload'); })();
"""
    return tpl.replace('__DATA_VAR__', data_var)


def script_choropleth_placeholder(data_var='data'):
    tpl = """
(function(){ d3.select('#viz').append('div').text('Choropleth placeholder - requires GeoJSON + value mapping'); })();
"""
    return tpl.replace('__DATA_VAR__', data_var)


def script_radar_placeholder(data_var='data'):
    tpl = """
(function(){ d3.select('#viz').append('div').text('Radar chart placeholder - consider using d3.lineRadial'); })();
"""
    return tpl.replace('__DATA_VAR__', data_var)


def script_calendar_heatmap_placeholder(data_var='data'):
    tpl = """
(function(){ d3.select('#viz').append('div').text('Calendar heatmap placeholder - expects date,value array'); })();
"""
    return tpl.replace('__DATA_VAR__', data_var)


def script_parallel_coords_placeholder(data_var='data'):
    tpl = """
(function(){ d3.select('#viz').append('div').text('Parallel coordinates placeholder - expects array of records with same keys'); })();
"""
    return tpl.replace('__DATA_VAR__', data_var)


# Main request handler
def render_using_script(script_fn, args, title=None, prefix='chart', output_dir=None):
    """
    Renders a chart using a specific D3 script function.
    
    Args:
        script_fn: D3 script function that returns JavaScript code
        args (dict): Chart arguments containing title and data
        title (str): Optional title override
        prefix (str): Filename prefix for saved HTML file
        output_dir (str): Optional custom output directory path
    
    Returns:
        dict: Response with status, path to saved HTML file, and HTML content
        
    This function:
    - Extracts data and title from arguments
    - Calls the specified D3 script function to generate JavaScript
    - Embeds the script in the BASE_HTML template
    - Saves the complete HTML file and returns the path
    - Used for specialized chart types like grouped_bar, scatter, etc.
    """
    title_text = None
    payload = None
    if isinstance(args, dict):
        title_text = args.get('title') or args.get('chart_title') or args.get('title_text')
        payload = args.get('data') or args.get('payload') or args.get('dataset') or args
    else:
        payload = args
    if payload is None:
        payload = {}
    title_text = title_text or title or 'D3 Chart'
    script = to_js_var(payload, 'data') + script_fn('data')
    html_text = BASE_HTML.replace('{title}', html.escape(title_text)).replace('{script}', script)
    
    # Extract chart type from prefix for better filename
    chart_type_name = prefix if prefix != 'chart' else 'chart'
    path = save_html(html_text, prefix=prefix, output_dir=output_dir, title=title_text, chart_type=chart_type_name, framework='d3')
    return {'status': 'ok', 'path': path, 'html': html_text}


# MCP Tool Registry: Maps tool names to chart generation functions
# Each tool corresponds to a specific chart type and rendering approach
TOOLS = {
    # Standard Chart.js-compatible charts (via handle_template)
    'line': lambda args: handle_template(args, chart_type='line', output_dir=args.get('output_dir') if isinstance(args, dict) else None),
    'multi_line': lambda args: handle_template(args, chart_type='line', output_dir=args.get('output_dir') if isinstance(args, dict) else None),
    'bar': lambda args: handle_template(args, chart_type='bar', output_dir=args.get('output_dir') if isinstance(args, dict) else None),
    'multi_bar': lambda args: handle_template(args, chart_type='bar', output_dir=args.get('output_dir') if isinstance(args, dict) else None),
    'stacked_bar': lambda args: handle_template(args, chart_type='bar', stacked=True, output_dir=args.get('output_dir') if isinstance(args, dict) else None),
    'pie': lambda args: handle_template(args, chart_type='pie', output_dir=args.get('output_dir') if isinstance(args, dict) else None),
    'donut': lambda args: handle_template(args, chart_type='donut', output_dir=args.get('output_dir') if isinstance(args, dict) else None),
    'bubble': lambda args: handle_template(args, chart_type='bubble', output_dir=args.get('output_dir') if isinstance(args, dict) else None),
    'heatmap': lambda args: handle_template(args, chart_type='heatmap', output_dir=args.get('output_dir') if isinstance(args, dict) else None),
    'packed': lambda args: render_using_script(script_packed, args, prefix='packed', output_dir=args.get('output_dir') if isinstance(args, dict) else None),
    
    # Specialized D3 charts (via render_using_script)
    'histogram': lambda args: render_using_script(script_histogram, args, prefix='histogram', output_dir=args.get('output_dir') if isinstance(args, dict) else None),
    'horizontal_bar': lambda args: render_using_script(script_horizontal_bar, args, prefix='hbar', output_dir=args.get('output_dir') if isinstance(args, dict) else None),
    'grouped_bar': lambda args: handle_template(args, chart_type='grouped_bar', output_dir=args.get('output_dir') if isinstance(args, dict) else None) if (isinstance(args, dict) and args.get('framework', 'd3').lower() == 'chartjs') else render_using_script(script_grouped_bar, args, prefix='grouped_bar', output_dir=args.get('output_dir') if isinstance(args, dict) else None),
    'scatter': lambda args: render_using_script(script_scatter, args, prefix='scatter', output_dir=args.get('output_dir') if isinstance(args, dict) else None),
    
    # Hierarchical and network visualizations (placeholder implementations)
    'treemap': lambda args: render_using_script(script_treemap_placeholder, args, prefix='treemap', output_dir=args.get('output_dir') if isinstance(args, dict) else None),
    'tree': lambda args: render_using_script(script_tree, args, prefix='tree', output_dir=args.get('output_dir') if isinstance(args, dict) else None),
    'force': lambda args: render_using_script(script_force, args, prefix='force', output_dir=args.get('output_dir') if isinstance(args, dict) else None),
    'chord': lambda args: render_using_script(script_chord_placeholder, args, prefix='chord', output_dir=args.get('output_dir') if isinstance(args, dict) else None),
    'sankey': lambda args: render_using_script(script_sankey_placeholder, args, prefix='sankey', output_dir=args.get('output_dir') if isinstance(args, dict) else None),
    
    # Specialized visualizations (placeholder implementations)  
    'choropleth': lambda args: render_using_script(script_choropleth_placeholder, args, prefix='choropleth', output_dir=args.get('output_dir') if isinstance(args, dict) else None),
    'radar': lambda args: render_using_script(script_radar_placeholder, args, prefix='radar', output_dir=args.get('output_dir') if isinstance(args, dict) else None),
    'calendar_heatmap': lambda args: render_using_script(script_calendar_heatmap_placeholder, args, prefix='calendar_heatmap', output_dir=args.get('output_dir') if isinstance(args, dict) else None),
    'parallel_coords': lambda args: render_using_script(script_parallel_coords_placeholder, args, prefix='parallel_coords', output_dir=args.get('output_dir') if isinstance(args, dict) else None),
    
    # Primary MCP entry points
    'render_from_dataset': lambda args: render_from_dataset_tool(args),      # Main chart generation tool with intelligent routing
    'merge_timeseries': lambda args: merge_timeseries_tool(args),            # Time series data merging utility
}


def merge_timeseries_tool(args: dict):
    """
    Utility tool for merging multiple time series datasets into a unified format.
    
    Args:
        args (dict): Arguments containing multiple time series data sources
    
    Returns:
        dict: Merged time series data in normalized format
        
    This tool helps consolidate multiple time-based datasets into a single
    chart-ready format with aligned time labels and multiple data series.
    Useful for comparing trends across different data sources or time periods.
    """
    """Merge multiple timeseries (list of series or dict of plan results) into normalized {labels, datasets}.
    Expected input shapes:
      - {'series': [{'label':'s1','labels':[...],'data':[...], 'color':'#...' }, ...]}
      - {'items': [{'id':'s1','result':[{'month':'2025-01','value':1}, ...]}, ...]} where inner records have a time-like key
      - Or a dict mapping keys to lists of records: {'s1': [...], 's2': [...]} where each list has objects with a time label
    Returns: {'status':'ok','merged': {'labels': [...], 'datasets': [...]}}
    """
    try:
        # normalize various incoming shapes
        series_input = []
        if not args:
            return {'status':'error','message':'no_args'}
        # direct 'series' list
        if isinstance(args, dict) and 'series' in args and isinstance(args['series'], list):
            series_input = args['series']
        # plan-like items with 'result' lists
        elif isinstance(args, dict) and 'items' in args and isinstance(args['items'], list):
            for it in args['items']:
                sid = it.get('id') or it.get('name') or 'series'
                recs = it.get('result') or it.get('records') or it.get('data') or []
                series_input.append({'label': sid, 'records': recs})
        # mapping of keys to list-of-records
        elif isinstance(args, dict) and all(isinstance(v, list) for v in args.values()):
            for k, v in args.items():
                series_input.append({'label': k, 'records': v})
        else:
            # try to see if args itself is a list of series-like dicts
            if isinstance(args, list):
                for s in args:
                    if isinstance(s, dict):
                        series_input.append(s)

        # helper to detect label key and numeric key inside records
        def detect_keys(records):
            if not records or not isinstance(records, list):
                return (None, None)
            sample = records[0]
            if not isinstance(sample, dict):
                return (None, None)
            label_key = None
            numeric_key = None
            for k in sample.keys():
                lk = k.lower()
                if any(x in lk for x in ('month', 'date', 'period', 'time', 'week')):
                    label_key = k
                    break
            if not label_key:
                # fallback to common names
                for k in sample.keys():
                    if k.lower() in ('label', 'name', 'period'):
                        label_key = k; break
            for k, v in sample.items():
                if k == label_key:
                    continue
                if isinstance(v, (int, float)) or (isinstance(v, str) and re.match(r'^[\d,\.\-\s]+$', v.strip())):
                    numeric_key = k
                    break
            return (label_key, numeric_key)

        # Build a mapping of label -> index by union of all labels
        all_labels_set = set()
        prepared = []
        for s in series_input:
            lbl = s.get('label') or s.get('id') or s.get('name') or 'series'
            records = s.get('records') or s.get('data') or s.get('values') or s.get('points') or []
            if isinstance(records, list) and records and isinstance(records[0], dict):
                lk, nk = detect_keys(records)
                if lk and nk:
                    labels = [str(r.get(lk, '') ) for r in records]
                    vals = []
                    for r in records:
                        v = r.get(nk, 0)
                        try:
                            if isinstance(v, str):
                                v = float(re.sub(r'[^0-9.\-\.]', '', v) or 0)
                        except Exception:
                            try: v = float(v)
                            except Exception: v = 0
                        vals.append(float(v or 0))
                    for L in labels:
                        all_labels_set.add(L)
                    prepared.append({'label': lbl, 'labels': labels, 'data': vals, 'color': s.get('color') or s.get('backgroundColor') or s.get('borderColor')})
                else:
                    # skip unknown shape
                    continue
            elif isinstance(records, list) and records and not isinstance(records[0], dict):
                # positional series with implicit labels
                idx_labels = [str(i) for i in range(len(records))]
                for L in idx_labels:
                    all_labels_set.add(L)
                prepared.append({'label': lbl, 'labels': idx_labels, 'data': [float(v or 0) for v in records], 'color': s.get('color') or s.get('backgroundColor') or s.get('borderColor')})

        if not prepared:
            return {'status':'error','message':'no_series_parsable'}

        # Build unified ordered labels (sort months like YYYY-MM or lexicographically)
        def sort_labels(labels_list):
            # attempt to sort by YYYY-MM pattern
            try:
                if all(re.match(r'^\d{4}-\d{2}$', l) for l in labels_list):
                    return sorted(labels_list)
            except Exception:
                pass
            # fallback lexicographic
            return sorted(labels_list)

        all_labels = sort_labels(list(all_labels_set))

        # Build aligned datasets filling missing values with 0
        datasets = []
        palette = ['#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd','#8c564b']
        for i, s in enumerate(prepared):
            lbl = s['label']
            mapping = {l: v for l, v in zip(s['labels'], s['data'])}
            aligned = [float(mapping.get(L, 0) or 0) for L in all_labels]
            color = s.get('color') or palette[i % len(palette)]
            datasets.append({'label': lbl, 'data': aligned, 'borderColor': color, 'backgroundColor': color, 'fill': False})

        merged = {'labels': all_labels, 'datasets': datasets}
        return {'status':'ok','merged': merged}
    except Exception as e:
        tb = traceback.format_exc()
        return {'status':'error','message':'merge_failed','error': str(e), 'trace': tb}

def handle_template(args, chart_type='line', stacked=False, output_dir=None):
    """
    Main chart generation handler that processes data and creates visualizations.
    
    Args:
        args (dict): Chart arguments containing title, data, and framework
        chart_type (str): Type of chart to generate ('line', 'bar', 'pie', etc.)
        stacked (bool): Whether to create stacked version of bar charts
        output_dir (str): Optional custom output directory path
    
    Returns:
        dict: Response with status, path to saved HTML file, and HTML content
        
    This is the core function that:
    - Normalizes various input data formats
    - Respects explicit framework selection ('d3', 'chartjs', 'auto')
    - Selects appropriate D3 chart script or Chart.js renderer based on framework
    - Handles data transformation from raw records to Chart.js format
    - Generates and saves complete HTML pages with visualizations
    - Supports multiple chart types with automatic fallback
    """
    # Extract framework preference (default: 'd3')
    framework = args.get('framework', 'd3').lower() if isinstance(args, dict) else 'd3'
    if framework not in ('d3', 'chartjs', 'auto'):
        framework = 'd3'  # fallback to D3 if invalid value
    
    # args may contain title and data. Data expected normalized: {labels:[], datasets:[{label,data:[], backgroundColor:[]}]}
    title = args.get('title') or args.get('chart_title') or 'Chart'
    payload = args.get('data') or args.get('dataset') or args.get('payload') or {}
    # if payload is dict with 'result' key, try to normalize
    if isinstance(payload, dict) and 'result' in payload and isinstance(payload['result'], list):
        # attempt to normalize list of dicts into labels + datasets if possible
        recs = payload['result']
        # primitive normalization: if recs are objects with 'project' and 'planned_cost' keys, make labels and one dataset
        if recs and isinstance(recs[0], dict):
            sample = recs[0]
            # choose category key heuristically
            cat = None
            numeric = None
            for k in sample.keys():
                lk = k.lower()
                if any(x in lk for x in ('project','name','title')) and isinstance(sample[k], str):
                    cat = k; break
            for k in sample.keys():
                if k==cat: continue
                if isinstance(sample[k], (int,float)) or (isinstance(sample[k], str) and sample[k].strip().replace('.','',1).replace(',','').lstrip('-').isdigit()):
                    numeric = k; break
            if cat and numeric:
                labels = [str(r.get(cat,'')) for r in recs]
                values = []
                for r in recs:
                    try: v = r.get(numeric,0)
                    except: v = 0
                    try: values.append(float(str(v).replace(',','')))
                    except: values.append(0)
                payload = {'labels': labels, 'datasets':[{'label': numeric, 'data': values}]}
    # If the caller explicitly requested a D3-only chart, handle directly before
    # enforcing the normalized labels/datasets shape. This lets callers provide
    # payloads like {'items': [...]} for packed charts or raw datasets for bubble/heatmap.
    ct = chart_type.lower() if isinstance(chart_type, str) else None
    
    # If Chart.js framework explicitly requested, use Chart.js renderer
    if framework == 'chartjs':
        html_text = render_chart_html_from_dataset(payload, title_text=title, chart_type=ct)
        path = save_html(html_text, prefix=f'chartjs_{chart_type}', output_dir=output_dir, title=title, chart_type=ct, framework='chartjs')
        return {'status':'ok', 'path': path, 'html': html_text}
    
    # For 'd3' or 'auto' framework, proceed with D3 templates
    # explicit packed/proportional/circle_packing OR hierarchical data structure detected
    # Handle chart type with spaces by normalizing
    ct_normalized = ct.replace(' ', '_') if ct else None
    if ct_normalized in ('packed', 'pack', 'proportional', 'circle_packing', 'circle_pack', 'circlepacking', 'packed_circle') or \
       (isinstance(payload, dict) and 'items' in payload) or \
       (isinstance(payload, dict) and 'name' in payload and 'children' in payload):
        script = to_js_var(payload, 'data') + script_packed('data')
        html_text = BASE_HTML.replace('{title}', html.escape(title)).replace('{script}', script)
        path = save_html(html_text, prefix='packed', output_dir=output_dir, title=title, chart_type='packed', framework='d3')
        return {'status':'ok', 'path': path, 'html': html_text}
    # explicit bubble
    if ct == 'bubble':
        script = to_js_var(payload, 'data') + script_bubble('data')
        html_text = BASE_HTML.replace('{title}', html.escape(title)).replace('{script}', script)
        path = save_html(html_text, prefix='bubble', output_dir=output_dir, title=title, chart_type='bubble', framework='d3')
        return {'status':'ok', 'path': path, 'html': html_text}
    # explicit heatmap
    if ct == 'heatmap':
        script = to_js_var(payload, 'data') + script_heatmap('data')
        html_text = BASE_HTML.replace('{title}', html.escape(title)).replace('{script}', script)
        path = save_html(html_text, prefix='heatmap', output_dir=output_dir, title=title, chart_type='heatmap', framework='d3')
        return {'status':'ok', 'path': path, 'html': html_text}

    # fallback ensure payload has labels/datasets
    labels = payload.get('labels') if isinstance(payload, dict) else None
    datasets = payload.get('datasets') if isinstance(payload, dict) else None
    if not labels or not datasets:
        # attempt to accept shorthand data like {'labels':[], 'values':[]}
        if isinstance(payload, dict) and 'labels' in payload and 'values' in payload:
            labels = payload['labels']
            datasets = [{'label':'Value','data':payload['values']}]
        else:
            return {'status': 'error', 'message': 'no_data: labels and datasets are required'}
    # select script
    if chart_type=='line':
        script = to_js_var(payload,'data') + script_line('data')
    elif chart_type=='bar' and not stacked:
        script = to_js_var(payload,'data') + script_bar('data', stacked=False)
    elif chart_type=='bar' and stacked:
        script = to_js_var(payload,'data') + script_bar('data', stacked=True)
    elif chart_type=='grouped_bar':
        script = to_js_var(payload,'data') + script_grouped_bar('data')
    elif chart_type=='pie' or chart_type=='donut':
        script = to_js_var(payload,'data') + script_pie('data', donut=(chart_type=='donut'))
    elif chart_type=='bubble':
        script = to_js_var(payload,'data') + script_bubble('data')
    elif chart_type=='heatmap':
        script = to_js_var(payload,'data') + script_heatmap('data')
    elif isinstance(chart_type, str) and chart_type.lower() in ('packed','pack','proportional','packed_circle'):
        script = to_js_var(payload,'data') + script_packed('data')
    else:
        script = to_js_var(payload,'data') + script_line('data')
    # Use simple replace to inject title and script. Avoid str.format because the
    # JavaScript template contains many braces which interfere with Python formatting.
    html_text = BASE_HTML.replace('{title}', html.escape(title)).replace('{script}', script)
    path = save_html(html_text, prefix=chart_type, output_dir=output_dir, title=title, chart_type=chart_type, framework='d3')
    return {'status':'ok','path':path,'html':html_text}


def render_from_dataset_tool(args: dict):
    """
    Main MCP tool for rendering charts from dataset arguments.
    
    Args:
        args (dict): Tool arguments containing data, title, chart_type, framework, and output_dir
    
    Returns:
        dict: Response with status, path to saved HTML file, and HTML content
        
    This is the primary entry point for chart generation that:
    - Accepts multiple data formats (data, payload, dataset, labels/datasets)
    - Honors explicit framework selection ('d3', 'chartjs', 'auto')
    - Honors explicit chart_type hints for routing to specific D3 scripts
    - Provides intelligent fallback routing (grouped_bar -> D3, pie/donut -> handle_template)  
    - Handles packed chart conversion heuristics with explicit hint override
    - Supports both D3-specific charts and Chart.js-compatible formats
    - Used by PMO client and other MCP consumers for chart generation
    
    Framework selection logic:
    - framework='d3' -> Prefer D3 templates, fallback to Chart.js if needed
    - framework='chartjs' -> Always use Chart.js renderer
    - framework='auto' -> Intelligently choose based on chart type and data
    
    Special routing:
    - chart_type='grouped_bar' -> script_grouped_bar (D3)
    - chart_type='horizontal_bar' -> script_horizontal_bar (D3)  
    - chart_type='scatter' -> script_scatter (D3)
    - chart_type='packed' -> handle_template (D3 packed)
    - Other types -> render_chart_html_from_dataset (Chart.js)
    """
    try:
        # Extract output directory preference
        output_dir = args.get('output_dir') if isinstance(args, dict) else None
        
        # Extract framework preference (default: 'd3')
        framework = args.get('framework', 'd3').lower() if isinstance(args, dict) else 'd3'
        if framework not in ('d3', 'chartjs', 'auto'):
            framework = 'd3'  # fallback to D3 if invalid value
        
        payload = None
        # common: caller provides a wrapper: {"data": {...}} or {"payload": {...}} or {"dataset": {...}}
        if isinstance(args, dict) and 'data' in args and isinstance(args['data'], (dict, list)):
            payload = args['data']
        elif isinstance(args, dict) and 'payload' in args and isinstance(args['payload'], (dict, list)):
            payload = args['payload']
        elif isinstance(args, dict) and 'dataset' in args:
            payload = args['dataset']
        # accept when the caller passes the normalized payload at the top-level, e.g. arguments = {labels:[], datasets:[]}
        elif isinstance(args, dict) and 'labels' in args and 'datasets' in args:
            payload = args
        # accept when args is itself a list/dict payload
        elif isinstance(args, (dict, list)) and ('labels' in args if isinstance(args, dict) else False):
            payload = args
        elif isinstance(args, dict) and 'html' in args and isinstance(args['html'], str):
            html_text = args['html']
            path = save_html(html_text, prefix='render', output_dir=output_dir)
            return {'status':'ok','path':path,'html':html_text}
        else:
            if isinstance(args, dict):
                for v in args.values():
                    if isinstance(v, str):
                        j = extract_json_from_text(v)
                        if j:
                            payload = j
                            break
        if not payload:
            return {'status':'error','message':'no_payload','details':'No data/payload/html found in arguments'}

        # Honor explicit chart type hint if provided (e.g., 'pie' or 'donut')
        chart_type_hint = None
        if isinstance(args, dict):
            chart_type_hint = args.get('chart_type') or args.get('type') or args.get('chartType')
        
        # If Chart.js framework explicitly requested, check if chart type is supported
        if framework == 'chartjs':
            # Check if requesting a D3-only chart type (not supported by Chart.js)
            if isinstance(chart_type_hint, str) and str(chart_type_hint).strip().lower() in ('packed', 'pack', 'proportional', 'circle_packing', 'circle_pack', 'circlepacking', 'packed_circle', 'treemap', 'sankey', 'chord', 'force', 'heatmap', 'horizontal_bar'):
                return {
                    'status': 'error',
                    'message': 'chart_type_not_supported',
                    'details': f"Chart type '{chart_type_hint}' is not supported by Chart.js. This is a D3-only visualization. Please use framework='d3' or choose a Chart.js-compatible chart type.\n\nChart.js supports: line, bar, grouped_bar, pie, donut, scatter, bubble.\nD3.js supports: line, bar, grouped_bar, pie, donut, bubble, heatmap, packed, treemap, sankey, chord, force, horizontal_bar."
                }
            
            # Chart.js supports grouped bar charts natively - map grouped_bar to 'bar' type
            chart_type_for_chartjs = chart_type_hint
            if isinstance(chart_type_hint, str) and chart_type_hint.lower() in ('grouped_bar', 'multi_bar'):
                chart_type_for_chartjs = 'bar'  # Chart.js uses 'bar' type for grouped bars
            
            html_text = render_chart_html_from_dataset(payload, title_text=args.get('title') or args.get('chart_title') or 'Chart', chart_type=chart_type_for_chartjs)
            path = save_html(html_text, prefix='chartjs_render', output_dir=output_dir)
            return {'status':'ok','path':path,'html':html_text}
        
        # If the caller explicitly asked for a packed/proportional/circle_packing chart, route to D3 implementation
        if isinstance(chart_type_hint, str) and str(chart_type_hint).strip().lower() in ('packed', 'pack', 'proportional', 'circle_packing', 'circle_pack', 'circlepacking', 'packed_circle'):
            # Use render_using_script directly with script_packed for hierarchical data support
            html_result = render_using_script(script_packed, {'data': payload, 'title': args.get('title') or args.get('chart_title') or 'Chart'}, prefix='packed', output_dir=output_dir)
            return html_result
        
        # For framework='d3', route standard chart types to D3 templates via handle_template
        if framework == 'd3' and isinstance(chart_type_hint, str):
            chart_hint_lower = str(chart_type_hint).strip().lower()
            # Circle packing types need special handling with render_using_script for hierarchical data
            if chart_hint_lower in ('packed', 'pack', 'proportional', 'circle_packing', 'circle_pack', 'circlepacking', 'packed_circle'):
                payload_with_title = payload.copy() if isinstance(payload, dict) else payload
                if isinstance(payload_with_title, dict):
                    payload_with_title['title'] = args.get('title') or args.get('chart_title') or 'Chart'
                html_result = render_using_script(script_packed, {'data': payload_with_title, 'title': args.get('title') or args.get('chart_title') or 'Chart'}, prefix='packed', output_dir=output_dir)
                return html_result
            # Standard chart types that have D3 implementations
            elif chart_hint_lower in ('line', 'bar', 'pie', 'donut', 'bubble', 'heatmap'):
                # Use handle_template which has D3 script implementations for these types
                is_stacked = 'stacked' in chart_hint_lower
                base_type = chart_hint_lower.replace('stacked_', '').replace('_bar', '').replace('bar', 'bar')
                html_result = handle_template(
                    {'data': payload, 'title': args.get('title') or args.get('chart_title') or 'Chart', 'framework': framework},
                    chart_type=base_type if base_type in ('line', 'bar', 'pie', 'donut', 'bubble', 'heatmap') else chart_hint_lower,
                    stacked=is_stacked,
                    output_dir=output_dir
                )
                return html_result
        
        # If the caller asked for D3-specific specialized chart types, route to the appropriate D3 scripts
        if isinstance(chart_type_hint, str):
            chart_hint_lower = str(chart_type_hint).strip().lower()
            if chart_hint_lower == 'grouped_bar':
                payload_with_title = payload.copy() if isinstance(payload, dict) else payload
                if isinstance(payload_with_title, dict):
                    payload_with_title['title'] = args.get('title') or args.get('chart_title') or 'Chart'
                html_text = render_using_script(script_grouped_bar, {'data': payload_with_title, 'title': args.get('title') or args.get('chart_title') or 'Chart'}, prefix='grouped_bar', output_dir=output_dir)
                if isinstance(html_text, dict) and html_text.get('status') == 'ok':
                    return html_text
            elif chart_hint_lower == 'horizontal_bar':
                html_text = render_using_script(script_horizontal_bar, {'data': payload, 'title': args.get('title') or args.get('chart_title') or 'Chart'}, prefix='hbar', output_dir=output_dir)
                if isinstance(html_text, dict) and html_text.get('status') == 'ok':
                    return html_text
            elif chart_hint_lower == 'scatter':
                html_text = render_using_script(script_scatter, {'data': payload, 'title': args.get('title') or args.get('chart_title') or 'Chart'}, prefix='scatter', output_dir=output_dir)
                if isinstance(html_text, dict) and html_text.get('status') == 'ok':
                    return html_text
            # if render_using_script failed, fall through to Chart.js renderer

        # Heuristic: if caller passed a normalized Chart.js-style payload (labels + single numeric dataset)
        # treat it as a proportional-area (packed) candidate and render with D3 pack for proportional circles.
        # However, do NOT perform this conversion when the caller explicitly requested a pie/donut chart via
        # the chart_type_hint. Respect explicit hints.
        try:
            skip_packed = False
            if isinstance(chart_type_hint, str):
                try:
                    if str(chart_type_hint).strip().lower() in ('pie', 'donut', 'doughnut'):
                        skip_packed = True
                except Exception:
                    pass

            if (not skip_packed) and isinstance(payload, dict) and 'labels' in payload and 'datasets' in payload and isinstance(payload['datasets'], list) and len(payload['datasets']) == 1:
                labels = payload.get('labels') or []
                ds = payload['datasets'][0]
                values = ds.get('data') if isinstance(ds.get('data'), list) else None
                if isinstance(labels, list) and isinstance(values, list) and len(labels) == len(values) and len(labels) > 0:
                    # Check that values are numeric (or numeric strings)
                    numeric_ok = True
                    numeric_vals = []
                    for v in values:
                        try:
                            nv = float(v)
                            numeric_vals.append(nv)
                        except Exception:
                            numeric_ok = False
                            break
                    if numeric_ok:
                        # Build items list for packed renderer
                        colors = ds.get('backgroundColor') if isinstance(ds.get('backgroundColor'), list) else None
                        items = []
                        for i, lab in enumerate(labels):
                            item = {'id': lab, 'label': lab, 'value': numeric_vals[i]}
                            if colors and i < len(colors):
                                item['color'] = colors[i]
                            items.append(item)
                        html_result = handle_template({'data': {'items': items}, 'title': args.get('title') or args.get('chart_title') or 'Chart'}, chart_type='packed', output_dir=output_dir)
                        return html_result
        except Exception:
            # fall through to default renderer
            pass

        # Final fallback: if framework is 'chartjs' or 'auto', use Chart.js renderer
        # For 'd3', we still try Chart.js as ultimate fallback
        html_text = render_chart_html_from_dataset(payload, title_text=args.get('title') or args.get('chart_title') or 'Chart', chart_type=chart_type_hint)
        path = save_html(html_text, prefix=f'{framework}_render' if framework in ('d3', 'chartjs') else 'render', output_dir=output_dir)
        return {'status':'ok','path':path,'html':html_text}
    except Exception as e:
        tb = traceback.format_exc()
        return {'status':'error','message':'render_failed','error':str(e),'trace':tb}

# Main loop: read lines from stdin
if __name__ == '__main__':
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception as e:
            resp = {'status':'error','message':'invalid_json','error':str(e)}
            print(json.dumps(resp), flush=True)
            continue
        tool = req.get('tool') or req.get('name')
        args = req.get('arguments') or req.get('args') or req.get('payload') or {}
        handler = TOOLS.get(tool)
        if not handler:
            resp = {'status':'error','message':'unknown_tool','tool':tool}
            print(json.dumps(resp), flush=True)
            continue
        try:
            result = handler(args)
            print(json.dumps(result), flush=True)
        except Exception as e:
            tb = traceback.format_exc()
            resp = {'status':'error','message':'handler_exception','error':str(e), 'trace': tb}
            print(json.dumps(resp), flush=True)