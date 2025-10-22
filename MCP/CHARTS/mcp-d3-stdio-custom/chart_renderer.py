import json
import re
from pathlib import Path
from datetime import datetime
import hashlib
import os


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
<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js'></script>
<style>
body{font-family:Segoe UI,Arial,sans-serif;margin:20px;background:#f5f5f5}
.container{max-width:1100px;margin:0 auto;background:#fff;padding:20px;border-radius:8px;box-shadow:0 4px 18px rgba(0,0,0,0.08)}
.chart-wrap{position:relative;height:520px;padding:10px}
canvas{width:100% !important;height:100% !important}
.legend-box{background:#ffffff;border:1px solid rgba(0,0,0,0.06);padding:12px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.04);margin-top:12px;display:flex;justify-content:center}
.legend-custom{display:flex;gap:12px;flex-wrap:wrap;align-items:center}
.legend-item{display:flex;align-items:center;gap:10px;font-size:13px;color:#fff;padding:8px 12px;border-radius:8px;font-weight:600}
.legend-color{width:12px;height:12px;border-radius:2px;display:inline-block;margin-right:8px}
.info{font-size:13px;color:#666;text-align:center;margin-top:10px}
</style>
</head>
<body>
<div class='container'>
<h2>__TITLE__</h2>
<div class='chart-wrap'>
<canvas id='hoursChart'></canvas>
</div>
<div class='legend-box' aria-hidden='false'>
  <div id='chart-legend' class='legend-custom'></div>
</div>
<div class='info'>Generated from PMO data</div>
</div>
<script id='chart-data' type='application/json'>
__CHART_PAYLOAD__
</script>
        <script>
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

    var ctx = document.getElementById('hoursChart').getContext('2d');
        var opts = {
            responsive: true,
            maintainAspectRatio: false,
            scales: { y: { beginAtZero: true } },
            plugins: { legend: { display: false } },
            elements: {
                point: { radius: 3 },
                line: { tension: 0.35, borderWidth: 2 }
            }
        };
    if (chartType === 'bar') opts.scales.x = { stacked: false };

        try{ new Chart(ctx, { type: chartType, data: payload, options: opts }); }catch(e){
            console.error('Chart init error', e);
            // visible in-page error banner for easier debugging when running headless or in screenshots
            try{
                var err = document.createElement('div');
                err.style.background = '#fee'; err.style.color = '#900'; err.style.padding = '12px'; err.style.border = '1px solid #f99'; err.style.margin = '8px'; err.style.borderRadius = '6px'; err.style.fontFamily='monospace';
                err.textContent = 'Chart init error: ' + (e && e.message ? e.message : String(e));
                document.body.insertBefore(err, document.body.firstChild);
            }catch(_){}
        }

    var legendEl = document.getElementById('chart-legend'); legendEl.innerHTML = '';
    if (chartType === 'pie' || chartType === 'doughnut'){
      var labels = payload.labels || [];
      var ds = payload.datasets && payload.datasets[0] || { data: [], backgroundColor: [] };
      var bg = ds.backgroundColor || [];
      for(var i=0;i<labels.length;i++){
        var val = (ds.data && ds.data[i]) || 0;
        var color = Array.isArray(bg) ? (bg[i] || '#777') : (bg || '#777');
        var item = document.createElement('div'); item.className='legend-item'; item.style.background = color;
        var sw = document.createElement('span'); sw.className='legend-color'; sw.style.background = color; sw.style.display='inline-block'; sw.style.width='12px'; sw.style.height='12px'; sw.style.marginRight='8px'; sw.style.borderRadius='2px';
        var lbl = document.createElement('span'); lbl.textContent = labels[i] + ' — ' + (Number(val)||0).toLocaleString();
        item.appendChild(sw); item.appendChild(lbl); legendEl.appendChild(item);
      }
    } else {
      payload.datasets.forEach(function(ds){
        var total = 0; for(var i=0;i<ds.data.length;i++){ var v = ds.data[i]; if(typeof v === 'number' && !isNaN(v)) total += v; }
        var item = document.createElement('div'); item.className='legend-item'; item.style.background = ds.backgroundColor || '#777';
        var sw = document.createElement('span'); sw.className='legend-color'; sw.style.background = (ds.backgroundColor||'#777'); sw.style.display='inline-block'; sw.style.width='12px'; sw.style.height='12px'; sw.style.marginRight='8px'; sw.style.borderRadius='2px';
        var lbl = document.createElement('span'); lbl.textContent = ds.label + ' — ' + total.toLocaleString();
        item.appendChild(sw); item.appendChild(lbl); legendEl.appendChild(item);
      });
    }

  }catch(e){ console.error('render error', e); }
})();
</script>
<details style="margin:12px 20px;padding:10px;border-radius:6px;background:#fff;border:1px solid #eee;max-width:1100px">
    <summary style="font-weight:600">Debug: embedded chart payload (click to expand)</summary>
    <pre style="white-space:pre-wrap;word-break:break-word;padding:8px;margin:8px;background:#fafafa;border-radius:4px;border:1px solid #efefef">__CHART_PAYLOAD__</pre>
</details>
</body>
</html>"""

    html = template.replace('__TITLE__', str(title_text)).replace('__CHART_PAYLOAD__', json.dumps(chart_payload)).replace('__CHART_TYPE__', chart_type)
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
    var width = Math.min(700, window.innerWidth - 120), height = Math.min(700, window.innerHeight - 240), radius = Math.min(width, height) / 2;
    var svg = d3.select('#chart').append('svg').attr('width', width).attr('height', height).append('g').attr('transform', 'translate(' + width/2 + ',' + height/2 + ')');
    var arc = d3.arc().innerRadius(radius*0.5).outerRadius(radius*0.9);
    var pie = d3.pie().value(function(d){ return d; }).sort(null);
    var arcs = svg.selectAll('arc').data(pie(data)).enter().append('g').attr('class','arc');
    arcs.append('path').attr('d', arc).attr('fill', function(d,i){ return colors[i % colors.length]; }).attr('stroke', '#fff').attr('stroke-width', 1);
    // tooltip
    var tip = d3.select('body').append('div').style('position','absolute').style('padding','6px 10px').style('background','#222').style('color','#fff').style('border-radius','6px').style('pointer-events','none').style('opacity',0);
    arcs.on('mouseover', function(event,d){ tip.style('opacity',1).html(labels[d.index] + ': ' + d.data.toLocaleString()); })
        .on('mousemove', function(event){ tip.style('left',(event.pageX+12)+'px').style('top',(event.pageY+12)+'px'); })
        .on('mouseout', function(){ tip.style('opacity',0); });
    // legend
    var legend = d3.select('#legend'); legend.html('');
    labels.forEach(function(l,i){ var item = legend.append('div').attr('class','legend-item'); item.append('div').attr('class','sw').style('background', colors[i % colors.length]); item.append('div').text(l + ' — ' + (data[i]||0).toLocaleString()); });
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
