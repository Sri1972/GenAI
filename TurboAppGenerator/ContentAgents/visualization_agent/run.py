"""
Visualization Agent — turns tabular data (pasted or uploaded CSV/JSON/XLSX)
into a self-contained, interactive HTML file: charts via D3.js, spatial data
via Leaflet (OpenStreetMap tiles, no API key).

Deliberately does NOT ask Claude to write the D3/Leaflet JavaScript itself —
every other chart-generation path in this codebase that let an LLM hand-write
chart/graphics code has hit real, hard-to-predict bugs (malformed D3
selections, ResizeObserver infinite loops, broken tooltips). Instead, Claude
only decides *what* to chart — a small structured JSON spec (chart types,
which columns map to which axes, titles) — and this file's own fixed,
hand-written D3/Leaflet templates render it deterministically. That collapses
an entire class of "LLM wrote broken JS" bugs by construction, at the cost of
only supporting the chart types this file actually implements (see
CHART_BUILDERS below) rather than anything an LLM could freely invent.

Usage:
    python run.py --brief "Revenue by region over time" --data-file sales.csv [--out out.html]
    python run.py --brief "Plot these store locations" --context "name,lat,lng\\n..."
"""

import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.aggregate import aggregate_rows
from common.claude_cli import run_claude, extract_json

SYSTEM_PROMPT = """You are the Visualization Agent's planning step. You have
no tool access in this call -- the brief and data below are already
complete. Do not ask to open files or run scripts yourself.

Given a brief and a table of data (columns + sample rows), decide how to
best visualize it and respond with ONLY a single JSON object, no prose:

{
  "title": "<short title for the whole visualization>",
  "summary": "<2-3 sentence description of what the chart(s)/map show>",
  "charts": [
    {
      "type": "bar" | "line" | "area" | "pie" | "scatter" | "choropleth",
      "title": "<chart title>",
      "x_field": "<exact column name from the data for the x-axis/category/label -- for \"choropleth\", the column holding country names or ISO-2/ISO-3 codes>",
      "y_field": "<exact column name from the data for the y-axis/value -- for \"choropleth\", the numeric value to shade each country by>",
      "series_field": "<exact column name to split into multiple series/colors, or null -- always null for \"choropleth\">",
      "agg": "sum" | "avg" | "count" | "min" | "max" | "none"
    }
  ],
  "map": {
    "lat_field": "<exact column name with latitude>",
    "lng_field": "<exact column name with longitude>",
    "label_field": "<exact column name to show as each marker's popup label>"
  } | null,
  "reshape": {
    "id_fields": ["<exact column name(s) to keep as-is on every melted row, e.g. 'region'>"],
    "value_fields": ["<exact column names that are actually VALUES of one dimension, e.g. 'Jan', 'Feb', 'Mar'>"],
    "category_field_name": "<new field name for what value_fields represent, e.g. 'month'>",
    "value_field_name": "<new field name for the actual numbers, e.g. 'revenue'>"
  } | null
}

Rules:
- x_field/y_field/series_field/lat_field/lng_field/label_field MUST be exact
  column names from the data given -- never invent a column that doesn't
  exist.
- Only include "map" if the data actually has latitude/longitude columns (or
  the brief explicitly asks for a map AND there's a clear lat/lng pair).
  Otherwise map MUST be null.
- Pick 1-4 charts that best answer the brief. Don't chart every column just
  because it exists -- pick what the brief is actually asking about.
- Decide the chart type FIRST from the brief, then supply/find data to match
  it -- never the reverse. Whenever you populate the top-level "data" field
  below (cases 2/3), "charts" must NOT be left empty -- include at least one
  chart (or a "map") whose x_field/y_field actually reference that data.
  Writing real data into "data" and then returning "charts": [] defeats the
  entire point of having found/supplied it; if you truly have nothing
  chartable, leave "data" out too and explain why in "summary" instead.
- "pie" is only appropriate for a single categorical breakdown (a handful of
  categories) -- never for a field with many distinct values or for
  continuous/time data.
- "choropleth" is for a world/country map shaded by a numeric value per
  country -- use it when the brief explicitly wants a country/world map
  (e.g. "population by country", "a world map of X"), x_field is a column of
  country names or ISO-2/ISO-3 codes, y_field is the numeric value to shade
  by. It always renders every country's outline regardless of how many you
  have real values for -- countries with no matching value just render
  uncolored, so it's fine to use even when you only have data for some
  countries (e.g. the top 20), not just all ~195. Never use "choropleth" for
  non-geographic categories, and never invent country values just to fill
  out the map beyond what rules 2/3 below already allow you to supply.
- y_field must be a numeric column. x_field is usually categorical or a date.
- "agg" decides how MULTIPLE rows sharing the same x_field (and series_field,
  if set) get combined into one point -- you choose WHICH operation makes
  sense; the actual arithmetic is always done exactly in code, never by you.
  Use "none" ONLY when x_field (+series_field) is already unique per row
  (e.g. one row per date in a time series) -- if the same x_field value
  appears on more than one row and you pick "none", those rows will
  overlap/stack on top of each other instead of combining, which looks
  broken. Use "sum" for totals (revenue, counts of things), "avg" for rates/
  scores/percentages, "count" for "how many rows/occurrences", "min"/"max"
  for extremes. When in doubt and the field is a total-like quantity, "sum"
  is usually right; for "none", double-check x_field+series_field really is
  unique per row in what you were given.
- "pie" almost always needs a real "agg" (rarely "none") since it's a
  categorical breakdown by definition.
- If the data is in WIDE format -- one column per category/date instead of
  one row per data point (e.g. columns "region, Jan, Feb, Mar" instead of
  "region, month, revenue") -- set "reshape" to melt it into long format
  FIRST, then write your chart(s)' x_field/y_field as category_field_name/
  value_field_name (the NEW field names reshape creates), not the original
  wide columns. Only name which existing columns are id vs value columns in
  "reshape" -- never retype the actual numbers; the real values are copied
  from the given data by code, exactly. Leave "reshape" null when the data
  is already one row per data point.

There are three possible situations for the data below:

1. It's ALREADY a clean table (a header row + data rows) -- use its column
   names as given and do NOT repeat the rows back in your response.

2. It's prose/metadata from a connected source (e.g. an upstream parser's
   own summary) -- look for ACTUAL numeric/categorical values genuinely
   written in that text (e.g. "revenue rose from $1.2M to $1.5M", a sentence
   mentioning specific figures per category) and, ONLY if you find real
   ones, include them as an additional top-level field:
     "data": [ {"<column>": <value>, ...}, ... ]
   using column names you choose that make sense for charting.
   CRITICAL -- never fabricate data to fill a gap in this case. If the
   prose/metadata is a summary with no actual numbers/values written in it
   (e.g. it says "the East region led in profitability" without ever
   stating a real profit figure), you have NOTHING real to chart from it.
   Do NOT invent plausible-sounding numbers -- that is worse than no chart
   at all. Return "charts": [], "map": null, and use "summary" to say
   plainly that the connected source doesn't contain concrete enough data
   to visualize, naming what IS mentioned qualitatively if anything.

3. It says "(none given)" -- no file, paste, or connected source was
   provided at all, only the brief. This is different from case 2: nobody
   handed you a thin source to fill gaps in, so if the brief asks about
   something you genuinely know well from your own general knowledge (e.g.
   well-known country/world statistics, historical figures, geography),
   supply that data yourself as the "data" field, using your best real
   recollection -- and say plainly in "summary" that these figures come
   from your own general knowledge rather than a live or verified source,
   and may be approximate or out of date. If the brief asks about something
   you don't actually know with real confidence (private, highly specific,
   or very recent data), do not guess -- return "charts": [], "map": null,
   and say in "summary" that you don't have reliable data for this without
   a real source being provided.

Only include "data" in cases 2 and 3 -- omit it entirely when real rows
were already given to you directly (case 1).
"""


def read_csv_text(text: str) -> tuple[list[dict], list[str]]:
    reader = csv.DictReader(io.StringIO(text))
    columns = reader.fieldnames or []
    rows = list(reader)
    return rows, columns


def read_data_file(raw: bytes, filename: str) -> tuple[list[dict], list[str]]:
    """Parse an uploaded/referenced data file into (rows, column names).
    Every value stays a string here -- common/aggregate.py's own numeric
    coercion handles turning numeric-looking strings into real numbers at
    render time, so this stays a single, simple code path regardless of
    source."""
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        return read_csv_text(raw.decode("utf-8", errors="replace"))
    if suffix == ".json":
        data = json.loads(raw.decode("utf-8", errors="replace"))
        if isinstance(data, dict):
            data = data.get("data") or data.get("rows") or [data]
        rows = [dict(r) for r in data if isinstance(r, dict)]
        columns = list(rows[0].keys()) if rows else []
        return rows, columns
    if suffix in (".xlsx", ".xlsm"):
        wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True)
        ws = wb.worksheets[0]
        all_rows = list(ws.iter_rows(values_only=True))
        if not all_rows:
            return [], []
        columns = [str(c) if c is not None else "" for c in all_rows[0]]
        rows = [dict(zip(columns, r)) for r in all_rows[1:] if any(v is not None for v in r)]
        return rows, columns
    raise ValueError(f"Unsupported data file type: {suffix or '(none)'} -- use .csv, .json, or .xlsx")


def _rows_preview_text(rows: list[dict], columns: list[str], max_rows: int = 60) -> str:
    preview = rows[:max_rows]
    lines = [",".join(columns)]
    for r in preview:
        lines.append(",".join(str(r.get(c, "")) for c in columns))
    suffix = f"\n... ({len(rows) - max_rows} more row(s) not shown)" if len(rows) > max_rows else ""
    return "\n".join(lines) + suffix


# ── Deterministic HTML/D3/Leaflet builder — no LLM-authored JS ─────────────

_HTML_SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
{leaflet_head}
<style>
  :root {{
    color-scheme: light dark;
    --surface-1: #fcfcfb;
    --surface-page: #f9f9f7;
    --text-primary: #0b0b0b;
    --text-secondary: #52514e;
    --text-muted: #898781;
    --border-hairline: rgba(11,11,11,0.10);
    --grid-line: #e1e0d9;
    --series-1: #2a78d6; --series-2: #eb6834; --series-3: #1baf7a; --series-4: #eda100;
    --series-5: #e87ba4; --series-6: #008300; --series-7: #4a3aa7; --series-8: #e34948;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --surface-1: #1a1a19;
      --surface-page: #0d0d0d;
      --text-primary: #ffffff;
      --text-secondary: #c3c2b7;
      --text-muted: #898781;
      --border-hairline: rgba(255,255,255,0.14);
      --grid-line: #2c2c2a;
      --series-1: #3987e5; --series-2: #d95926; --series-3: #199e70; --series-4: #c98500;
      --series-5: #d55181; --series-6: #008300; --series-7: #9085e9; --series-8: #e66767;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 28px;
          background: var(--surface-page); color: var(--text-primary); }}
  h1 {{ font-size: 20px; font-weight: 600; margin: 0 0 4px; }}
  p.summary {{ color: var(--text-secondary); font-size: 13px; margin: 0 0 24px; max-width: 720px; line-height: 1.5; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 20px; }}
  .block {{ background: var(--surface-1); border: 1px solid var(--border-hairline); border-radius: 14px;
            padding: 18px 18px 14px; position: relative; box-shadow: 0 1px 3px rgba(0,0,0,0.07); }}
  .block-head {{ display: flex; align-items: baseline; justify-content: space-between; gap: 10px; margin-bottom: 10px; }}
  .block h2 {{ font-size: 14px; font-weight: 600; margin: 0; color: var(--text-primary);
               overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .block-actions {{ display: flex; gap: 6px; flex-shrink: 0; }}
  .block-actions button {{ font: inherit; font-size: 11px; color: var(--text-secondary); background: transparent;
               border: 1px solid var(--border-hairline); border-radius: 6px; padding: 3px 8px; cursor: pointer; }}
  .block-actions button:hover {{ color: var(--text-primary); border-color: var(--text-muted); }}
  .chart {{ width: 100%; height: 320px; }}
  .chart[data-type="choropleth"] {{ height: 420px; }}
  .map {{ width: 100%; height: 420px; border-radius: 10px; }}
  .tooltip {{ position: absolute; pointer-events: none; background: var(--text-primary); color: var(--surface-1);
              font-size: 12px; padding: 6px 10px; border-radius: 6px; opacity: 0; transition: opacity .1s; z-index: 10;
              max-width: 240px; box-shadow: 0 2px 8px rgba(0,0,0,0.18); }}
  .legend {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 10px; font-size: 11px; color: var(--text-secondary); }}
  .legend span.dot {{ display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 5px; vertical-align: middle; }}
  .axis text {{ fill: var(--text-muted); }}
  .axis path, .axis line {{ stroke: var(--grid-line); }}
</style>
</head>
<body>
  <h1>{title}</h1>
  <p class="summary">{summary}</p>
  <div class="grid" id="grid"></div>
  <div class="tooltip" id="tooltip"></div>
{leaflet_body}
<script id="main-script">
const CHARTS = {charts_json}; /*__CHARTS_END__*/
const COLORS = [1, 2, 3, 4, 5, 6, 7, 8].map(
  i => getComputedStyle(document.body).getPropertyValue(`--series-${{i}}`).trim()
);
const tooltip = d3.select('#tooltip');

function showTip(html, x, y) {{
  tooltip.style('opacity', 1).style('left', (x + 14) + 'px').style('top', (y + 10) + 'px').html(html);
}}
function hideTip() {{ tooltip.style('opacity', 0); }}

function makeBlock(spec) {{
  const title = spec.title || '';
  const block = d3.select('#grid').append('div').attr('class', 'block');
  const head = block.append('div').attr('class', 'block-head');
  head.append('h2').attr('title', title).text(title);
  const actions = head.append('div').attr('class', 'block-actions');
  const chartEl = block.append('div').attr('class', 'chart').attr('data-type', spec.type).node();
  actions.append('button').text('PNG').on('click', () => exportChart(chartEl, title, 'png'));
  actions.append('button').text('SVG').on('click', () => exportChart(chartEl, title, 'svg'));
  actions.append('button').text('HTML').on('click', () => exportChartHtml(spec, title));
  return chartEl;
}}

function renderChart(spec) {{
  const el = makeBlock(spec);
  const draw = () => {{
    const width = el.clientWidth;
    if (width <= 0) return;
    el.innerHTML = '';
    const height = el.clientHeight || 320;
    // Choropleth is a full-bleed map, not an axis-based chart -- the usual
    // axis-label margins would just waste space around it.
    const margin = spec.type === 'choropleth'
      ? {{ top: 4, right: 4, bottom: 4, left: 4 }}
      : {{ top: 10, right: 20, bottom: 46, left: 56 }};
    const iw = Math.max(10, width - margin.left - margin.right);
    const ih = Math.max(10, height - margin.top - margin.bottom);
    const svg = d3.select(el).append('svg').attr('width', width).attr('height', height)
      .style('background', 'var(--surface-1)');
    const g = svg.append('g').attr('transform', `translate(${{margin.left}},${{margin.top}})`);
    (RENDERERS[spec.type] || RENDERERS.bar)(g, iw, ih, spec);
  }};
  // Lets an async renderer (choropleth, waiting on the world-map GeoJSON
  // fetch) trigger its own re-draw once data arrives, without needing a
  // real resize to happen first.
  el.__redraw = draw;
  draw();
  new ResizeObserver(draw).observe(el);
}}

// A bar's rounded corners always sit at the "data end" (far from the zero
// baseline) and stay square at the baseline -- for a negative value that's
// the bottom, not the top, so this checks which pixel is actually on top
// rather than assuming positive-only data.
function roundedBarPath(x, w, yBaseline, yDataEnd, r) {{
  const top = Math.min(yBaseline, yDataEnd), bottom = Math.max(yBaseline, yDataEnd);
  r = Math.max(0, Math.min(r, w / 2, bottom - top));
  if (yDataEnd < yBaseline) {{
    return `M${{x}},${{bottom}} L${{x}},${{top + r}} Q${{x}},${{top}} ${{x + r}},${{top}} `
         + `L${{x + w - r}},${{top}} Q${{x + w}},${{top}} ${{x + w}},${{top + r}} L${{x + w}},${{bottom}} Z`;
  }}
  return `M${{x}},${{top}} L${{x}},${{bottom - r}} Q${{x}},${{bottom}} ${{x + r}},${{bottom}} `
       + `L${{x + w - r}},${{bottom}} Q${{x + w}},${{bottom}} ${{x + w}},${{bottom - r}} L${{x + w}},${{top}} Z`;
}}
const BAR_MAX_WIDTH = 24;
// Past this many bars, direct value labels stack up into unreadable noise
// (especially with grouped series) -- the legend, tooltip, and the
// exported HTML/table view still carry every exact value regardless, so
// nothing is actually lost by skipping the inline text past this point.
const BAR_LABEL_MAX = 24;

const RENDERERS = {{
  bar(g, w, h, spec) {{
    const data = spec.rows;
    const categories = [...new Set(data.map(d => d.x))];
    const seriesNames = [...new Set(data.map(d => d.series).filter(s => s != null))];
    const hasSeries = seriesNames.length > 0;
    const x0 = d3.scaleBand().domain(categories).range([0, w]).padding(0.28);
    // Sub-band per series inside each category's slot -- without this,
    // every series at the same x would sit at the identical x-position and
    // draw directly on top of each other instead of side by side.
    const x1 = hasSeries ? d3.scaleBand().domain(seriesNames).range([0, x0.bandwidth()]).padding(0.1) : null;
    const y = d3.scaleLinear().domain(d3.extent([0, ...data.map(d => d.y)])).nice().range([h, 0]);
    g.append('g').attr('class', 'axis').attr('transform', `translate(0,${{h}})`).call(d3.axisBottom(x0).tickSizeOuter(0))
      .selectAll('text').attr('transform', 'rotate(-30)').style('text-anchor', 'end').style('font-size', '10px');
    g.append('g').attr('class', 'axis').call(d3.axisLeft(y).ticks(5)).selectAll('text').style('font-size', '10px');
    function barGeom(d) {{
      const groupW = hasSeries ? x1.bandwidth() : x0.bandwidth();
      const bw = Math.min(groupW, BAR_MAX_WIDTH);
      const slot = x0(d.x) + (hasSeries ? x1(d.series) : 0);
      return {{ bx: slot + (groupW - bw) / 2, bw }};
    }}
    g.selectAll('.bar').data(data).join('path').attr('class', 'bar')
      .attr('d', d => {{ const {{ bx, bw }} = barGeom(d); return roundedBarPath(bx, bw, y(0), y(d.y), 4); }})
      .attr('fill', d => hasSeries ? COLORS[SERIES_INDEX(spec, d.series) % 8] : COLORS[0])
      .on('mousemove', (ev, d) => showTip(`<b>${{d.x}}</b><br>${{d.series ? d.series + ': ' : ''}}${{fmt(d.y)}}`, ev.pageX, ev.pageY))
      .on('mouseleave', hideTip);
    // Value at the tip of every bar (the documented bar/column convention --
    // unlike a line, a bar chart's whole point is usually the exact values,
    // so labeling each one isn't the same "chaos" a labeled-every-point
    // line would be). Sits above the tip for a positive bar, below for a
    // negative one -- text is a text-secondary token, never the bar's own
    // series color (a light hue like yellow reads poorly as text).
    if (data.length <= BAR_LABEL_MAX) {{
      g.selectAll('.bar-label').data(data).join('text').attr('class', 'bar-label')
        .attr('x', d => {{ const {{ bx, bw }} = barGeom(d); return bx + bw / 2; }})
        .attr('y', d => y(d.y) + (d.y >= 0 ? -5 : 13))
        .attr('text-anchor', 'middle').style('font-size', '9px').attr('fill', 'var(--text-secondary)')
        .text(d => fmt(d.y));
    }}
    drawLegend(g, spec);
  }},
  line(g, w, h, spec) {{ drawLineOrArea(g, w, h, spec, false); }},
  area(g, w, h, spec) {{ drawLineOrArea(g, w, h, spec, true); }},
  scatter(g, w, h, spec) {{
    const data = spec.rows;
    const x = d3.scaleLinear().domain(d3.extent(data, d => d.x)).nice().range([0, w]);
    const y = d3.scaleLinear().domain(d3.extent(data, d => d.y)).nice().range([h, 0]);
    g.append('g').attr('class', 'axis').attr('transform', `translate(0,${{h}})`).call(d3.axisBottom(x).ticks(6)).selectAll('text').style('font-size', '10px');
    g.append('g').attr('class', 'axis').call(d3.axisLeft(y).ticks(6)).selectAll('text').style('font-size', '10px');
    g.selectAll('circle').data(data).join('circle')
      .attr('cx', d => x(d.x)).attr('cy', d => y(d.y)).attr('r', 4.5)
      .attr('fill', d => d.series != null ? COLORS[SERIES_INDEX(spec, d.series) % 8] : COLORS[0])
      .attr('stroke', 'var(--surface-1)').attr('stroke-width', 1.5)
      .on('mousemove', (ev, d) => showTip(`x: ${{fmt(d.x)}}<br>y: ${{fmt(d.y)}}${{d.series ? '<br>' + d.series : ''}}`, ev.pageX, ev.pageY))
      .on('mouseleave', hideTip);
    drawLegend(g, spec);
  }},
  pie(g, w, h, spec) {{
    const data = spec.rows;
    const total = d3.sum(data, d => d.y);
    const radius = Math.min(w, h) / 2;
    const cg = g.append('g').attr('transform', `translate(${{w / 2}},${{h / 2}})`);
    const arc = d3.arc().innerRadius(radius * 0.55).outerRadius(radius);
    const pie = d3.pie().value(d => d.y).sort(null);
    const arcs = pie(data);
    cg.selectAll('path').data(arcs).join('path')
      .attr('d', arc).attr('fill', (d, i) => COLORS[i % 8]).attr('stroke', 'var(--surface-1)').attr('stroke-width', 2)
      .on('mousemove', (ev, d) => showTip(`<b>${{d.data.x}}</b><br>${{fmt(d.data.y)}}`, ev.pageX, ev.pageY))
      .on('mouseleave', hideTip);
    // % label centered in each slice, but only slices wide enough to hold
    // it legibly (a sliver's value still lives in the legend + tooltip --
    // never clip text into an arc that's too thin for it). Text color
    // flips to ink or white by the slice's own fill luminance, since a
    // fixed white would be illegible on a light hue like yellow.
    const labelArc = d3.arc().innerRadius(radius * 0.78).outerRadius(radius * 0.78);
    cg.selectAll('.pie-label').data(arcs.filter(d => (d.endAngle - d.startAngle) >= 0.35)).join('text')
      .attr('class', 'pie-label').attr('transform', d => `translate(${{labelArc.centroid(d)}})`)
      .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle').style('font-size', '10px')
      .attr('fill', (d, i) => textColorOn(COLORS[arcs.indexOf(d) % 8]))
      .text(d => total ? `${{Math.round(d.data.y / total * 100)}}%` : '');
    drawLegend(g, spec);
  }},
  choropleth(g, w, h, spec) {{
    if (!worldGeoData) {{
      g.append('text').attr('x', w / 2).attr('y', h / 2).attr('text-anchor', 'middle')
        .style('font-size', '12px').attr('fill', 'var(--text-muted)').text('Loading world map…');
      loadWorldGeo().then(() => {{
        const el = g.node().parentNode.parentNode;
        if (el && el.__redraw) el.__redraw();
      }});
      return;
    }}
    const valueByFeature = new Map();
    spec.rows.forEach(r => {{
      const feature = findCountryFeature(r.x);
      if (feature) valueByFeature.set(feature, r.y);
    }});
    const values = [...valueByFeature.values()];
    const color = values.length ? d3.scaleSequential(d3.interpolateViridis).domain(d3.extent(values)) : null;
    const projection = d3.geoNaturalEarth1().fitSize([w, h], worldGeoData);
    const path = d3.geoPath(projection);
    g.selectAll('path').data(worldGeoData.features).join('path')
      .attr('d', path)
      .attr('fill', f => valueByFeature.has(f) ? color(valueByFeature.get(f)) : 'var(--grid-line)')
      .attr('stroke', 'var(--surface-1)').attr('stroke-width', 0.5)
      .on('mousemove', (ev, f) => {{
        const v = valueByFeature.get(f);
        showTip(`<b>${{f.properties.ADMIN}}</b><br>${{v != null ? fmt(v) : 'No data'}}`, ev.pageX, ev.pageY);
      }})
      .on('mouseleave', hideTip);
    if (color) drawColorLegend(g, h, color);
  }},
}};

// ── World map (choropleth) support -- country boundaries are fetched once
// from a CDN GeoJSON (Natural Earth 1:110m, via jsdelivr's GitHub proxy) and
// cached; matching an LLM-given country name/code to the right feature is
// done here in fixed code (normalize + a common-alias table + ISO-2/3
// fallback), never by the LLM itself -- same "LLM picks fields, code renders
// exactly" split as every other chart type in this file. ──
const WORLD_GEO_URL = 'https://cdn.jsdelivr.net/gh/nvkelso/natural-earth-vector@master/geojson/ne_110m_admin_0_countries.geojson';
let worldGeoData = null, worldGeoPromise = null, countryIndex = null;

function loadWorldGeo() {{
  if (worldGeoData) return Promise.resolve(worldGeoData);
  if (worldGeoPromise) return worldGeoPromise;
  worldGeoPromise = fetch(WORLD_GEO_URL).then(r => r.json()).then(geo => {{
    worldGeoData = geo;
    countryIndex = buildCountryIndex(geo);
    return geo;
  }}).catch(() => {{
    worldGeoData = {{ type: 'FeatureCollection', features: [] }};
    countryIndex = {{ byName: new Map(), byIso3: new Map(), byIso2: new Map() }};
    return worldGeoData;
  }});
  return worldGeoPromise;
}}

// Strips accents (via Unicode decomposition, keeping only the ASCII base
// letters) and punctuation so e.g. "Côte d'Ivoire" and "cote divoire" match
// the same normalized key -- both this dataset's own ADMIN names and
// whatever an LLM writes get run through this before comparing.
function normCountryName(s) {{
  const decomposed = String(s || '').normalize('NFD');
  let ascii = '';
  for (const ch of decomposed) {{ if (ch.codePointAt(0) < 128) ascii += ch; }}
  // Hyphens/underscores become spaces (so "Congo-Kinshasa" ~ "congo kinshasa",
  // not "congokinshasa") before any other punctuation is dropped outright.
  return ascii.toLowerCase().trim().replace(/[-_]/g, ' ').replace(/[^a-z0-9 ]/g, '')
    .split(' ').filter(Boolean).join(' ');
}}

// Common short/alternate names -> this dataset's own canonical ADMIN name.
// Both sides are compared after normCountryName, so case/punctuation/accents
// on either side don't need to match exactly -- only the underlying words.
const COUNTRY_ALIASES = {{
  'usa': 'united states of america', 'us': 'united states of america',
  'united states': 'united states of america', 'america': 'united states of america',
  'uk': 'united kingdom', 'great britain': 'united kingdom', 'britain': 'united kingdom',
  'russian federation': 'russia',
  'republic of korea': 'south korea', 'korea south': 'south korea',
  'dprk': 'north korea', 'korea north': 'north korea',
  'democratic republic of congo': 'democratic republic of the congo',
  'dr congo': 'democratic republic of the congo', 'drc': 'democratic republic of the congo',
  'congo kinshasa': 'democratic republic of the congo',
  'congo': 'republic of the congo', 'republic of congo': 'republic of the congo',
  'congo brazzaville': 'republic of the congo',
  'cote divoire': 'ivory coast',
  'czech republic': 'czechia',
  'burma': 'myanmar',
  'swaziland': 'eswatini',
  'macedonia': 'north macedonia', 'fyrom': 'north macedonia',
  'timor leste': 'east timor',
  'serbia': 'republic of serbia',
  'tanzania': 'united republic of tanzania',
  'bahamas': 'the bahamas',
  'brunei darussalam': 'brunei',
  'lao pdr': 'laos',
  'uae': 'united arab emirates',
  'holy see': 'vatican city',
  'cape verde': 'cabo verde',
}};

function buildCountryIndex(geo) {{
  const byName = new Map(), byIso3 = new Map(), byIso2 = new Map();
  geo.features.forEach(f => {{
    const p = f.properties || {{}};
    byName.set(normCountryName(p.ADMIN), f);
    if (p.ISO_A3 && p.ISO_A3 !== '-99') byIso3.set(p.ISO_A3.toUpperCase(), f);
    if (p.ISO_A2 && p.ISO_A2 !== '-99') byIso2.set(p.ISO_A2.toUpperCase(), f);
  }});
  return {{ byName, byIso3, byIso2 }};
}}

function findCountryFeature(rawName) {{
  if (!countryIndex) return null;
  const code = String(rawName || '').trim().toUpperCase();
  if (code.length === 3 && countryIndex.byIso3.has(code)) return countryIndex.byIso3.get(code);
  if (code.length === 2 && countryIndex.byIso2.has(code)) return countryIndex.byIso2.get(code);
  const n = normCountryName(rawName);
  if (countryIndex.byName.has(n)) return countryIndex.byName.get(n);
  const aliased = COUNTRY_ALIASES[n];
  if (aliased && countryIndex.byName.has(aliased)) return countryIndex.byName.get(aliased);
  return null;
}}

function drawColorLegend(g, h, color) {{
  const [lo, hi] = color.domain();
  const legendW = 160, legendH = 10, steps = 12;
  const lg = g.append('g').attr('transform', `translate(4, ${{h - 26}})`);
  for (let i = 0; i < steps; i++) {{
    lg.append('rect').attr('x', (legendW / steps) * i).attr('y', 0)
      .attr('width', legendW / steps + 0.5).attr('height', legendH)
      .attr('fill', color(lo + (hi - lo) * (i / (steps - 1))));
  }}
  lg.append('text').attr('class', 'legend-label').attr('x', 0).attr('y', legendH + 12)
    .style('font-size', '9px').attr('fill', 'var(--text-secondary)').text(fmt(lo));
  lg.append('text').attr('class', 'legend-label').attr('x', legendW).attr('y', legendH + 12)
    .attr('text-anchor', 'end').style('font-size', '9px').attr('fill', 'var(--text-secondary)').text(fmt(hi));
}}

function drawLineOrArea(g, w, h, spec, filled) {{
  const data = spec.rows;
  const series = groupBySeries(data);
  const x = d3.scalePoint().domain([...new Set(data.map(d => d.x))]).range([0, w]);
  const y = d3.scaleLinear().domain(d3.extent([0, ...data.map(d => d.y)])).nice().range([h, 0]);
  g.append('g').attr('class', 'axis').attr('transform', `translate(0,${{h}})`).call(d3.axisBottom(x).tickSizeOuter(0))
    .selectAll('text').attr('transform', 'rotate(-30)').style('text-anchor', 'end').style('font-size', '10px');
  g.append('g').attr('class', 'axis').call(d3.axisLeft(y).ticks(5)).selectAll('text').style('font-size', '10px');
  const line = d3.line().x(d => x(d.x)).y(d => y(d.y)).curve(d3.curveMonotoneX);
  const area = d3.area().x(d => x(d.x)).y0(y(0)).y1(d => y(d.y)).curve(d3.curveMonotoneX);
  series.forEach((pts, i) => {{
    const color = COLORS[i % 8];
    if (filled) {{
      g.append('path').datum(pts).attr('d', area).attr('fill', color).attr('opacity', 0.12);
    }}
    g.append('path').datum(pts).attr('d', line).attr('fill', 'none').attr('stroke', color).attr('stroke-width', 2);
    g.selectAll(`.dot-${{i}}`).data(pts).join('circle').attr('class', `dot-${{i}}`)
      .attr('cx', d => x(d.x)).attr('cy', d => y(d.y)).attr('r', 4).attr('fill', color)
      .attr('stroke', 'var(--surface-1)').attr('stroke-width', 2)
      .on('mousemove', (ev, d) => showTip(`<b>${{d.x}}</b>${{d.series ? ' — ' + d.series : ''}}<br>${{fmt(d.y)}}`, ev.pageX, ev.pageY))
      .on('mouseleave', hideTip);
    // Label just the series' endpoint -- labeling every point on a line is
    // exactly the "chaos" case direct labels are meant to avoid; the
    // tooltip on every dot above still covers the rest.
    const last = pts[pts.length - 1];
    g.append('text').attr('class', 'value-label').attr('x', x(last.x) + 7).attr('y', y(last.y))
      .attr('dominant-baseline', 'middle').style('font-size', '10px').attr('fill', 'var(--text-secondary)')
      .text(fmt(last.y));
  }});
  drawLegend(g, spec);
}}

function groupBySeries(rows) {{
  const map = new Map();
  rows.forEach(r => {{
    const key = r.series ?? '__single__';
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(r);
  }});
  return [...map.values()];
}}
function SERIES_INDEX(spec, name) {{
  if (!spec._seriesOrder) spec._seriesOrder = [...new Set(spec.rows.map(d => d.series))];
  return spec._seriesOrder.indexOf(name);
}}
function drawLegend(g, spec) {{
  if (!spec.rows.some(d => d.series != null)) return;
  const names = [...new Set(spec.rows.map(d => d.series))];
  const parent = d3.select(g.node().parentNode.parentNode);
  const legend = parent.append('div').attr('class', 'legend');
  names.forEach((n, i) => {{
    legend.append('span').html(`<span class="dot" style="background:${{COLORS[i % 8]}}"></span>${{n}}`);
  }});
}}
function fmt(v) {{ return typeof v === 'number' ? d3.format(',.2~f')(v) : v; }}
// Simple relative-luminance check so a label placed *inside* a colored
// fill (only ever done for the pie's in-slice labels) always clears
// contrast, per the rule that identity comes from the mark, never from
// coloring the text -- a fixed white would be illegible on a light hue.
function textColorOn(hex) {{
  const c = hex.replace('#', '');
  const r = parseInt(c.substring(0, 2), 16), g = parseInt(c.substring(2, 4), 16), b = parseInt(c.substring(4, 6), 16);
  return (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.6 ? '#0b0b0b' : '#ffffff';
}}

// Exports a chart as a standalone PNG/SVG file, for pasting into a doc/deck.
// A static export inherently loses the live hover tooltips (that's a
// property of static images, not something worth trying to fake) -- the
// interactive HTML file itself is unaffected and still has full tooltips.
function exportChart(chartEl, title, format) {{
  const svgEl = chartEl.querySelector('svg');
  if (!svgEl) return;
  const cs = getComputedStyle(document.body);
  const bg = cs.getPropertyValue('--surface-1').trim();
  const textMuted = cs.getPropertyValue('--text-muted').trim();
  const textSecondary = cs.getPropertyValue('--text-secondary').trim();
  const gridLine = cs.getPropertyValue('--grid-line').trim();

  const clone = svgEl.cloneNode(true);
  clone.setAttribute('style', `background:${{bg}}`);
  const style = document.createElementNS('http://www.w3.org/2000/svg', 'style');
  // Scoped per class rather than a blanket `text{{fill:...}}` -- that would
  // override the pie's own per-slice luminance-picked label color (a
  // literal hex already baked into its own fill attribute, which must be
  // left alone) as well as the CSS var() this SVG has no scope to resolve
  // once cloned out on its own.
  style.textContent = `text {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }} `
    + `.axis text {{ fill: ${{textMuted}}; }} .axis path, .axis line {{ stroke: ${{gridLine}}; }} `
    + `.bar-label, .value-label, .legend-label {{ fill: ${{textSecondary}}; }}`;
  clone.insertBefore(style, clone.firstChild);

  const xml = new XMLSerializer().serializeToString(clone);
  const svgBlob = new Blob([xml], {{ type: 'image/svg+xml;charset=utf-8' }});
  if (format === 'svg') {{ downloadBlob(svgBlob, `${{slugify(title)}}.svg`); return; }}

  const url = URL.createObjectURL(svgBlob);
  const img = new Image();
  img.onload = () => {{
    const scale = 2;
    const canvas = document.createElement('canvas');
    canvas.width = svgEl.width.baseVal.value * scale;
    canvas.height = svgEl.height.baseVal.value * scale;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.scale(scale, scale);
    ctx.drawImage(img, 0, 0);
    URL.revokeObjectURL(url);
    canvas.toBlob(blob => downloadBlob(blob, `${{slugify(title)}}.png`), 'image/png');
  }};
  img.onerror = () => URL.revokeObjectURL(url);
  img.src = url;
}}

// Exports ONE chart as its own standalone HTML file that still has full
// working tooltips -- unlike PNG/SVG (necessarily static), this clones the
// whole current page (same CSS, palette, and render code already loaded)
// and narrows its own CHARTS array down to just this one chart, so opening
// the file re-renders exactly this chart, fully interactive, with nothing
// duplicated from the dashboard it came from.
function exportChartHtml(spec, title) {{
  const docClone = document.documentElement.cloneNode(true);
  const grid = docClone.querySelector('#grid');
  if (grid) grid.innerHTML = '';  // runtime-appended chart divs aren't part of the static template
  const tooltipEl = docClone.querySelector('#tooltip');
  if (tooltipEl) tooltipEl.removeAttribute('style');

  const scriptEl = docClone.querySelector('#main-script');
  const marker = '/*__CHARTS_END__*/';
  const startTag = 'const CHARTS = ';
  const text = scriptEl.textContent;
  const startIdx = text.indexOf(startTag);
  const endIdx = text.indexOf(marker, startIdx) + marker.length;
  scriptEl.textContent = text.slice(0, startIdx) + startTag + JSON.stringify([spec]) + '; ' + marker + text.slice(endIdx);

  // The page's <h1>/summary describe the WHOLE original dashboard (possibly
  // several charts) -- misleading once this file only contains one of them,
  // so this exported copy gets its own chart's title instead and drops the
  // dashboard-wide summary rather than showing a description that no longer
  // matches what's actually on the page.
  const titleEl = docClone.querySelector('title');
  if (titleEl) titleEl.textContent = title || 'Chart';
  const h1El = docClone.querySelector('h1');
  if (h1El) h1El.textContent = title || 'Chart';
  const summaryEl = docClone.querySelector('p.summary');
  if (summaryEl) summaryEl.remove();

  const html = '<!DOCTYPE html>' + docClone.outerHTML;
  downloadBlob(new Blob([html], {{ type: 'text/html;charset=utf-8' }}), `${{slugify(title)}}.html`);
}}

function downloadBlob(blob, filename) {{
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}}
function slugify(s) {{ return (s || 'chart').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '') || 'chart'; }}

CHARTS.forEach(renderChart);
// Defensive empty state -- if the planning call left "charts" empty (and
// there's no Leaflet marker map either), show something that explains that
// rather than leaving the page silently blank below the summary.
if (CHARTS.length === 0 && !document.getElementById('map')) {{
  d3.select('#grid').append('div').attr('class', 'block').style('grid-column', '1 / -1')
    .append('p').style('color', 'var(--text-muted)').style('font-size', '13px').style('margin', '0')
    .text('No chart was generated for this request -- see the summary above for details.');
}}
{map_script}
</script>
</body>
</html>
"""

_LEAFLET_HEAD = ('<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />\n'
                  '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>')

_LEAFLET_BODY = ('  <div class="block" style="margin-top:20px">'
                  '<div class="block-head"><h2>{title}</h2></div><div class="map" id="map"></div></div>')

_LEAFLET_SCRIPT = """
const MAP_POINTS = {points_json};
if (MAP_POINTS.length) {{
  const map = L.map('map');
  L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    attribution: '&copy; OpenStreetMap contributors', maxZoom: 18,
  }}).addTo(map);
  const markers = MAP_POINTS.map(p => L.marker([p.lat, p.lng]).bindPopup(p.label));
  const group = L.featureGroup(markers).addTo(map);
  map.fitBounds(group.getBounds(), {{ padding: [24, 24] }});
}}
"""


def _melt_rows(rows: list[dict], id_fields: list[str], value_fields: list[str],
                category_field_name: str, value_field_name: str) -> list[dict]:
    """Deterministically reshapes wide-format rows (one column per
    category, e.g. Jan/Feb/Mar) into long format (one row per data point).
    Every output value is copied directly from a real input cell -- this
    only rearranges existing values, never computes or invents a new one,
    so it's safe to trust even though the LLM chose which columns to melt
    (see SYSTEM_PROMPT's "reshape" field: it names columns, never retypes
    numbers). Reproduced directly: a wide upload (region, Jan, Feb, Mar...)
    against a "revenue trend by month" brief correctly got reshaped by the
    LLM into real long-format "data" rows -- but generate() ignored that
    and charted the original wide rows anyway, since a chart's x_field/
    y_field ("month"/"revenue") don't exist as columns until melted,
    producing a silently empty chart despite the LLM doing the right thing."""
    out = []
    for r in rows:
        base = {f: r.get(f) for f in id_fields if f in r}
        for vf in value_fields:
            if vf not in r:
                continue
            entry = dict(base)
            entry[category_field_name] = vf
            entry[value_field_name] = r.get(vf)
            out.append(entry)
    return out


def _chart_rows(rows: list[dict], x_field: str, y_field: str, series_field: str | None,
                 agg: str = "none") -> list[dict]:
    """Builds one {x, y, series?} point per (x_field, series_field) pair,
    via the shared common/aggregate.py -- see that module's docstring for
    why the actual grouping/arithmetic lives there instead of here (any
    other agent that needs the same "group and reduce exactly" step can
    import it directly, without duplicating this logic)."""
    grouped = aggregate_rows(rows, group_by=x_field, value_field=y_field, agg=agg, series_by=series_field)
    out = []
    for g in grouped:
        entry = {"x": g["group"], "y": g["value"]}
        if series_field:
            entry["series"] = g.get("series")
        out.append(entry)
    return out


_MONTH_ORDER = {name.lower(): i for i, name in enumerate(
    ["January", "February", "March", "April", "May", "June",
     "July", "August", "September", "October", "November", "December"], 1)}
_MONTH_ORDER.update({name[:3]: i for name, i in list(_MONTH_ORDER.items())})
_WEEKDAY_ORDER = {name.lower(): i for i, name in enumerate(
    ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], 1)}
_WEEKDAY_ORDER.update({name[:3]: i for name, i in list(_WEEKDAY_ORDER.items())})
_ISO_DATE_RE = re.compile(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})")


def _temporal_sort_key(x) -> tuple | None:
    """Returns a sort key if x looks unambiguously like a month name,
    weekday name, ISO-ish date, or plain number -- None if it doesn't
    match any of those, so the caller can tell "no reliable order" apart
    from "sorts first". Only ever called when EVERY x value in a chart
    matches the SAME one of these categories (see _maybe_sort_chronologically)
    -- never applied to plain categorical labels, which have no inherently
    "more correct" order to impose."""
    if isinstance(x, (int, float)):
        return (0, x)
    s = str(x).strip()
    if s.lower() in _MONTH_ORDER:
        return (1, _MONTH_ORDER[s.lower()])
    if s.lower() in _WEEKDAY_ORDER:
        return (2, _WEEKDAY_ORDER[s.lower()])
    m = _ISO_DATE_RE.match(s)
    if m:
        return (3, int(m.group(1)), int(m.group(2)), int(m.group(3)))
    try:
        return (0, float(s.replace(",", "")))
    except ValueError:
        return None


def _maybe_sort_chronologically(chart_rows: list[dict]) -> list[dict]:
    """Line/area charts visually imply a left-to-right sequence -- a
    dataset that isn't already sorted by date/month/weekday/number (a real
    possibility: nothing guarantees an upload or an upstream source lists
    rows in order) renders as a misleading zigzag instead of a clean trend.
    Reproduced directly: months given as Mar, Jan, Jun, Feb, Apr, May
    plotted in exactly that file order. Only reorders when EVERY x value
    resolves to the same recognized category -- if even one doesn't, this
    leaves the original order untouched rather than guessing."""
    keys = [_temporal_sort_key(r["x"]) for r in chart_rows]
    if any(k is None for k in keys):
        return chart_rows
    return [r for _, r in sorted(zip(keys, chart_rows), key=lambda pair: pair[0])]


def build_html(spec: dict, rows: list[dict], out_path: Path):
    charts = []
    for c in spec.get("charts", []) or []:
        chart_rows = _chart_rows(rows, c.get("x_field", ""), c.get("y_field", ""), c.get("series_field"),
                                  agg=c.get("agg", "none"))
        if not chart_rows:
            continue
        if c.get("type") in ("line", "area"):
            chart_rows = _maybe_sort_chronologically(chart_rows)
        charts.append({"type": c.get("type", "bar"), "title": c.get("title", ""), "rows": chart_rows})

    map_spec = spec.get("map")
    leaflet_head = leaflet_body = map_script = ""
    if map_spec and map_spec.get("lat_field") and map_spec.get("lng_field"):
        points = []
        for r in rows:
            try:
                lat = float(r.get(map_spec["lat_field"]))
                lng = float(r.get(map_spec["lng_field"]))
            except (TypeError, ValueError):
                continue
            label = str(r.get(map_spec.get("label_field", ""), ""))
            points.append({"lat": lat, "lng": lng, "label": label})
        if points:
            leaflet_head = _LEAFLET_HEAD
            leaflet_body = _LEAFLET_BODY.format(title="Map")
            map_script = _LEAFLET_SCRIPT.format(points_json=json.dumps(points))

    html = _HTML_SHELL.format(
        title=spec.get("title", "Visualization"),
        summary=spec.get("summary", ""),
        charts_json=json.dumps(charts),
        leaflet_head=leaflet_head,
        leaflet_body=leaflet_body,
        map_script=map_script,
    )
    out_path.write_text(html, encoding="utf-8")


def generate(brief: str, out_path: Path, rows: list[dict] | None = None,
             columns: list[str] | None = None, raw_context: str | None = None) -> dict:
    """Shared by the CLI below and both server handlers (library-mode +
    workflow-node-mode): run the planning LLM call, then build the HTML
    deterministically. Returns the spec (used as this item's library
    metadata).

    Two calling shapes:
    - rows/columns given (Utility Agents tab: an uploaded/pasted data file
      already parsed cleanly) -- charted directly, no LLM round-trip needed
      for the actual data.
    - raw_context given instead (a workflow node chained after an upstream
      reader, whose own drafted metadata -- prose + embedded sample values,
      not a clean table -- is all that's available) -- the planning call
      also extracts real data rows itself (see SYSTEM_PROMPT's "data"
      field), since there's no deterministic way to parse arbitrary prose
      metadata into a table.
    """
    if rows is not None:
        data_section = (f"DATA ({len(rows)} row(s), columns: {', '.join(columns or [])}):\n"
                         f"{_rows_preview_text(rows, columns or [])}")
    else:
        data_section = f"DATA / REFERENCE CONTENT:\n{raw_context or '(none given)'}"

    prompt = (f"BRIEF: {brief}\n\n{data_section}\n\n"
              "Produce the visualization spec JSON described in your instructions.")
    result = run_claude(prompt, system_prompt=SYSTEM_PROMPT, allowed_tools=[])
    spec = extract_json(result["result"])

    reshape = spec.get("reshape")
    source_rows = rows if rows is not None else (spec.get("data") or [])
    if reshape and reshape.get("value_fields"):
        # Claude names columns only (id_fields/value_fields); the actual
        # reshaping is deterministic, whether the wide rows came from an
        # uploaded file or from Claude's own "data" extraction out of prose
        # (e.g. a pdf_parser question answer chained in as raw_context) --
        # both are equally real wide-format rows that need melting.
        chart_rows = _melt_rows(
            source_rows, reshape.get("id_fields") or [], reshape["value_fields"],
            reshape.get("category_field_name") or "category",
            reshape.get("value_field_name") or "value",
        )
    else:
        chart_rows = source_rows

    build_html(spec, chart_rows, out_path)
    return spec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", required=True, help="What to visualize")
    ap.add_argument("--data-file", help="Path to a .csv/.json/.xlsx file with the data")
    ap.add_argument("--context", help="Pasted data (CSV or JSON text) if no --data-file is given")
    ap.add_argument("--out")
    args = ap.parse_args()

    if args.data_file:
        rows, columns = read_data_file(Path(args.data_file).read_bytes(), args.data_file)
    elif args.context:
        stripped = args.context.strip()
        if stripped.startswith("[") or stripped.startswith("{"):
            rows, columns = read_data_file(args.context.encode("utf-8"), "context.json")
        else:
            rows, columns = read_csv_text(args.context)
    else:
        print("Provide --data-file or --context with the data to visualize.", file=sys.stderr)
        sys.exit(1)

    if not rows:
        print("No data rows could be parsed from the given input.", file=sys.stderr)
        sys.exit(1)

    out_path = Path(args.out) if args.out else Path.cwd() / "visualization.html"
    spec = generate(args.brief, out_path, rows=rows, columns=columns)
    print(f"Wrote {len(spec.get('charts', []))} chart(s)"
          f"{' + a map' if spec.get('map') else ''} to {out_path}")


if __name__ == "__main__":
    main()
