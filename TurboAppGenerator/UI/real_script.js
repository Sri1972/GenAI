
const CHARTS = []; /*__CHARTS_END__*/
const COLORS = [1, 2, 3, 4, 5, 6, 7, 8].map(
  i => getComputedStyle(document.body).getPropertyValue(`--series-${i}`).trim()
);
const tooltip = d3.select('#tooltip');

function showTip(html, x, y) {
  tooltip.style('opacity', 1).style('left', (x + 14) + 'px').style('top', (y + 10) + 'px').html(html);
}
function hideTip() { tooltip.style('opacity', 0); }

function makeBlock(spec) {
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
}

function renderChart(spec) {
  const el = makeBlock(spec);
  const draw = () => {
    const width = el.clientWidth;
    if (width <= 0) return;
    el.innerHTML = '';
    const height = el.clientHeight || 320;
    // Choropleth is a full-bleed map, not an axis-based chart -- the usual
    // axis-label margins would just waste space around it.
    const margin = spec.type === 'choropleth'
      ? { top: 4, right: 4, bottom: 4, left: 4 }
      : { top: 10, right: 20, bottom: 46, left: 56 };
    const iw = Math.max(10, width - margin.left - margin.right);
    const ih = Math.max(10, height - margin.top - margin.bottom);
    const svg = d3.select(el).append('svg').attr('width', width).attr('height', height)
      .style('background', 'var(--surface-1)');
    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);
    (RENDERERS[spec.type] || RENDERERS.bar)(g, iw, ih, spec);
  };
  // Lets an async renderer (choropleth, waiting on the world-map GeoJSON
  // fetch) trigger its own re-draw once data arrives, without needing a
  // real resize to happen first.
  el.__redraw = draw;
  draw();
  new ResizeObserver(draw).observe(el);
}

// A bar's rounded corners always sit at the "data end" (far from the zero
// baseline) and stay square at the baseline -- for a negative value that's
// the bottom, not the top, so this checks which pixel is actually on top
// rather than assuming positive-only data.
function roundedBarPath(x, w, yBaseline, yDataEnd, r) {
  const top = Math.min(yBaseline, yDataEnd), bottom = Math.max(yBaseline, yDataEnd);
  r = Math.max(0, Math.min(r, w / 2, bottom - top));
  if (yDataEnd < yBaseline) {
    return `M${x},${bottom} L${x},${top + r} Q${x},${top} ${x + r},${top} `
         + `L${x + w - r},${top} Q${x + w},${top} ${x + w},${top + r} L${x + w},${bottom} Z`;
  }
  return `M${x},${top} L${x},${bottom - r} Q${x},${bottom} ${x + r},${bottom} `
       + `L${x + w - r},${bottom} Q${x + w},${bottom} ${x + w},${bottom - r} L${x + w},${top} Z`;
}
const BAR_MAX_WIDTH = 24;
// Past this many bars, direct value labels stack up into unreadable noise
// (especially with grouped series) -- the legend, tooltip, and the
// exported HTML/table view still carry every exact value regardless, so
// nothing is actually lost by skipping the inline text past this point.
const BAR_LABEL_MAX = 24;

const RENDERERS = {
  bar(g, w, h, spec) {
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
    g.append('g').attr('class', 'axis').attr('transform', `translate(0,${h})`).call(d3.axisBottom(x0).tickSizeOuter(0))
      .selectAll('text').attr('transform', 'rotate(-30)').style('text-anchor', 'end').style('font-size', '10px');
    g.append('g').attr('class', 'axis').call(d3.axisLeft(y).ticks(5)).selectAll('text').style('font-size', '10px');
    function barGeom(d) {
      const groupW = hasSeries ? x1.bandwidth() : x0.bandwidth();
      const bw = Math.min(groupW, BAR_MAX_WIDTH);
      const slot = x0(d.x) + (hasSeries ? x1(d.series) : 0);
      return { bx: slot + (groupW - bw) / 2, bw };
    }
    g.selectAll('.bar').data(data).join('path').attr('class', 'bar')
      .attr('d', d => { const { bx, bw } = barGeom(d); return roundedBarPath(bx, bw, y(0), y(d.y), 4); })
      .attr('fill', d => hasSeries ? COLORS[SERIES_INDEX(spec, d.series) % 8] : COLORS[0])
      .on('mousemove', (ev, d) => showTip(`<b>${d.x}</b><br>${d.series ? d.series + ': ' : ''}${fmt(d.y)}`, ev.pageX, ev.pageY))
      .on('mouseleave', hideTip);
    // Value at the tip of every bar (the documented bar/column convention --
    // unlike a line, a bar chart's whole point is usually the exact values,
    // so labeling each one isn't the same "chaos" a labeled-every-point
    // line would be). Sits above the tip for a positive bar, below for a
    // negative one -- text is a text-secondary token, never the bar's own
    // series color (a light hue like yellow reads poorly as text).
    if (data.length <= BAR_LABEL_MAX) {
      g.selectAll('.bar-label').data(data).join('text').attr('class', 'bar-label')
        .attr('x', d => { const { bx, bw } = barGeom(d); return bx + bw / 2; })
        .attr('y', d => y(d.y) + (d.y >= 0 ? -5 : 13))
        .attr('text-anchor', 'middle').style('font-size', '9px').attr('fill', 'var(--text-secondary)')
        .text(d => fmt(d.y));
    }
    drawLegend(g, spec);
  },
  line(g, w, h, spec) { drawLineOrArea(g, w, h, spec, false); },
  area(g, w, h, spec) { drawLineOrArea(g, w, h, spec, true); },
  scatter(g, w, h, spec) {
    const data = spec.rows;
    const x = d3.scaleLinear().domain(d3.extent(data, d => d.x)).nice().range([0, w]);
    const y = d3.scaleLinear().domain(d3.extent(data, d => d.y)).nice().range([h, 0]);
    g.append('g').attr('class', 'axis').attr('transform', `translate(0,${h})`).call(d3.axisBottom(x).ticks(6)).selectAll('text').style('font-size', '10px');
    g.append('g').attr('class', 'axis').call(d3.axisLeft(y).ticks(6)).selectAll('text').style('font-size', '10px');
    g.selectAll('circle').data(data).join('circle')
      .attr('cx', d => x(d.x)).attr('cy', d => y(d.y)).attr('r', 4.5)
      .attr('fill', d => d.series != null ? COLORS[SERIES_INDEX(spec, d.series) % 8] : COLORS[0])
      .attr('stroke', 'var(--surface-1)').attr('stroke-width', 1.5)
      .on('mousemove', (ev, d) => showTip(`x: ${fmt(d.x)}<br>y: ${fmt(d.y)}${d.series ? '<br>' + d.series : ''}`, ev.pageX, ev.pageY))
      .on('mouseleave', hideTip);
    drawLegend(g, spec);
  },
  pie(g, w, h, spec) {
    const data = spec.rows;
    const total = d3.sum(data, d => d.y);
    const radius = Math.min(w, h) / 2;
    const cg = g.append('g').attr('transform', `translate(${w / 2},${h / 2})`);
    const arc = d3.arc().innerRadius(radius * 0.55).outerRadius(radius);
    const pie = d3.pie().value(d => d.y).sort(null);
    const arcs = pie(data);
    cg.selectAll('path').data(arcs).join('path')
      .attr('d', arc).attr('fill', (d, i) => COLORS[i % 8]).attr('stroke', 'var(--surface-1)').attr('stroke-width', 2)
      .on('mousemove', (ev, d) => showTip(`<b>${d.data.x}</b><br>${fmt(d.data.y)}`, ev.pageX, ev.pageY))
      .on('mouseleave', hideTip);
    // % label centered in each slice, but only slices wide enough to hold
    // it legibly (a sliver's value still lives in the legend + tooltip --
    // never clip text into an arc that's too thin for it). Text color
    // flips to ink or white by the slice's own fill luminance, since a
    // fixed white would be illegible on a light hue like yellow.
    const labelArc = d3.arc().innerRadius(radius * 0.78).outerRadius(radius * 0.78);
    cg.selectAll('.pie-label').data(arcs.filter(d => (d.endAngle - d.startAngle) >= 0.35)).join('text')
      .attr('class', 'pie-label').attr('transform', d => `translate(${labelArc.centroid(d)})`)
      .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle').style('font-size', '10px')
      .attr('fill', (d, i) => textColorOn(COLORS[arcs.indexOf(d) % 8]))
      .text(d => total ? `${Math.round(d.data.y / total * 100)}%` : '');
    drawLegend(g, spec);
  },
  choropleth(g, w, h, spec) {
    if (!worldGeoData) {
      g.append('text').attr('x', w / 2).attr('y', h / 2).attr('text-anchor', 'middle')
        .style('font-size', '12px').attr('fill', 'var(--text-muted)').text('Loading world map…');
      loadWorldGeo().then(() => {
        const el = g.node().parentNode.parentNode;
        if (el && el.__redraw) el.__redraw();
      });
      return;
    }
    const valueByFeature = new Map();
    spec.rows.forEach(r => {
      const feature = findCountryFeature(r.x);
      if (feature) valueByFeature.set(feature, r.y);
    });
    const values = [...valueByFeature.values()];
    const color = values.length ? d3.scaleSequential(d3.interpolateViridis).domain(d3.extent(values)) : null;
    const projection = d3.geoNaturalEarth1().fitSize([w, h], worldGeoData);
    const path = d3.geoPath(projection);
    g.selectAll('path').data(worldGeoData.features).join('path')
      .attr('d', path)
      .attr('fill', f => valueByFeature.has(f) ? color(valueByFeature.get(f)) : 'var(--grid-line)')
      .attr('stroke', 'var(--surface-1)').attr('stroke-width', 0.5)
      .on('mousemove', (ev, f) => {
        const v = valueByFeature.get(f);
        showTip(`<b>${f.properties.ADMIN}</b><br>${v != null ? fmt(v) : 'No data'}`, ev.pageX, ev.pageY);
      })
      .on('mouseleave', hideTip);
    if (color) drawColorLegend(g, h, color);
  },
};

// ── World map (choropleth) support -- country boundaries are fetched once
// from a CDN GeoJSON (Natural Earth 1:110m, via jsdelivr's GitHub proxy) and
// cached; matching an LLM-given country name/code to the right feature is
// done here in fixed code (normalize + a common-alias table + ISO-2/3
// fallback), never by the LLM itself -- same "LLM picks fields, code renders
// exactly" split as every other chart type in this file. ──
const WORLD_GEO_URL = 'https://cdn.jsdelivr.net/gh/nvkelso/natural-earth-vector@master/geojson/ne_110m_admin_0_countries.geojson';
let worldGeoData = null, worldGeoPromise = null, countryIndex = null;

function loadWorldGeo() {
  if (worldGeoData) return Promise.resolve(worldGeoData);
  if (worldGeoPromise) return worldGeoPromise;
  worldGeoPromise = fetch(WORLD_GEO_URL).then(r => r.json()).then(geo => {
    worldGeoData = geo;
    countryIndex = buildCountryIndex(geo);
    return geo;
  }).catch(() => {
    worldGeoData = { type: 'FeatureCollection', features: [] };
    countryIndex = { byName: new Map(), byIso3: new Map(), byIso2: new Map() };
    return worldGeoData;
  });
  return worldGeoPromise;
}

// Strips accents (via Unicode decomposition, keeping only the ASCII base
// letters) and punctuation so e.g. "Côte d'Ivoire" and "cote divoire" match
// the same normalized key -- both this dataset's own ADMIN names and
// whatever an LLM writes get run through this before comparing.
function normCountryName(s) {
  const decomposed = String(s || '').normalize('NFD');
  let ascii = '';
  for (const ch of decomposed) { if (ch.codePointAt(0) < 128) ascii += ch; }
  // Hyphens/underscores become spaces (so "Congo-Kinshasa" ~ "congo kinshasa",
  // not "congokinshasa") before any other punctuation is dropped outright.
  return ascii.toLowerCase().trim().replace(/[-_]/g, ' ').replace(/[^a-z0-9 ]/g, '')
    .split(' ').filter(Boolean).join(' ');
}

// Common short/alternate names -> this dataset's own canonical ADMIN name.
// Both sides are compared after normCountryName, so case/punctuation/accents
// on either side don't need to match exactly -- only the underlying words.
const COUNTRY_ALIASES = {
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
};

function buildCountryIndex(geo) {
  const byName = new Map(), byIso3 = new Map(), byIso2 = new Map();
  geo.features.forEach(f => {
    const p = f.properties || {};
    byName.set(normCountryName(p.ADMIN), f);
    if (p.ISO_A3 && p.ISO_A3 !== '-99') byIso3.set(p.ISO_A3.toUpperCase(), f);
    if (p.ISO_A2 && p.ISO_A2 !== '-99') byIso2.set(p.ISO_A2.toUpperCase(), f);
  });
  return { byName, byIso3, byIso2 };
}

function findCountryFeature(rawName) {
  if (!countryIndex) return null;
  const code = String(rawName || '').trim().toUpperCase();
  if (code.length === 3 && countryIndex.byIso3.has(code)) return countryIndex.byIso3.get(code);
  if (code.length === 2 && countryIndex.byIso2.has(code)) return countryIndex.byIso2.get(code);
  const n = normCountryName(rawName);
  if (countryIndex.byName.has(n)) return countryIndex.byName.get(n);
  const aliased = COUNTRY_ALIASES[n];
  if (aliased && countryIndex.byName.has(aliased)) return countryIndex.byName.get(aliased);
  return null;
}

function drawColorLegend(g, h, color) {
  const [lo, hi] = color.domain();
  const legendW = 160, legendH = 10, steps = 12;
  const lg = g.append('g').attr('transform', `translate(4, ${h - 26})`);
  for (let i = 0; i < steps; i++) {
    lg.append('rect').attr('x', (legendW / steps) * i).attr('y', 0)
      .attr('width', legendW / steps + 0.5).attr('height', legendH)
      .attr('fill', color(lo + (hi - lo) * (i / (steps - 1))));
  }
  lg.append('text').attr('class', 'legend-label').attr('x', 0).attr('y', legendH + 12)
    .style('font-size', '9px').attr('fill', 'var(--text-secondary)').text(fmt(lo));
  lg.append('text').attr('class', 'legend-label').attr('x', legendW).attr('y', legendH + 12)
    .attr('text-anchor', 'end').style('font-size', '9px').attr('fill', 'var(--text-secondary)').text(fmt(hi));
}

function drawLineOrArea(g, w, h, spec, filled) {
  const data = spec.rows;
  const series = groupBySeries(data);
  const x = d3.scalePoint().domain([...new Set(data.map(d => d.x))]).range([0, w]);
  const y = d3.scaleLinear().domain(d3.extent([0, ...data.map(d => d.y)])).nice().range([h, 0]);
  g.append('g').attr('class', 'axis').attr('transform', `translate(0,${h})`).call(d3.axisBottom(x).tickSizeOuter(0))
    .selectAll('text').attr('transform', 'rotate(-30)').style('text-anchor', 'end').style('font-size', '10px');
  g.append('g').attr('class', 'axis').call(d3.axisLeft(y).ticks(5)).selectAll('text').style('font-size', '10px');
  const line = d3.line().x(d => x(d.x)).y(d => y(d.y)).curve(d3.curveMonotoneX);
  const area = d3.area().x(d => x(d.x)).y0(y(0)).y1(d => y(d.y)).curve(d3.curveMonotoneX);
  series.forEach((pts, i) => {
    const color = COLORS[i % 8];
    if (filled) {
      g.append('path').datum(pts).attr('d', area).attr('fill', color).attr('opacity', 0.12);
    }
    g.append('path').datum(pts).attr('d', line).attr('fill', 'none').attr('stroke', color).attr('stroke-width', 2);
    g.selectAll(`.dot-${i}`).data(pts).join('circle').attr('class', `dot-${i}`)
      .attr('cx', d => x(d.x)).attr('cy', d => y(d.y)).attr('r', 4).attr('fill', color)
      .attr('stroke', 'var(--surface-1)').attr('stroke-width', 2)
      .on('mousemove', (ev, d) => showTip(`<b>${d.x}</b>${d.series ? ' — ' + d.series : ''}<br>${fmt(d.y)}`, ev.pageX, ev.pageY))
      .on('mouseleave', hideTip);
    // Label just the series' endpoint -- labeling every point on a line is
    // exactly the "chaos" case direct labels are meant to avoid; the
    // tooltip on every dot above still covers the rest.
    const last = pts[pts.length - 1];
    g.append('text').attr('class', 'value-label').attr('x', x(last.x) + 7).attr('y', y(last.y))
      .attr('dominant-baseline', 'middle').style('font-size', '10px').attr('fill', 'var(--text-secondary)')
      .text(fmt(last.y));
  });
  drawLegend(g, spec);
}

function groupBySeries(rows) {
  const map = new Map();
  rows.forEach(r => {
    const key = r.series ?? '__single__';
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(r);
  });
  return [...map.values()];
}
function SERIES_INDEX(spec, name) {
  if (!spec._seriesOrder) spec._seriesOrder = [...new Set(spec.rows.map(d => d.series))];
  return spec._seriesOrder.indexOf(name);
}
function drawLegend(g, spec) {
  if (!spec.rows.some(d => d.series != null)) return;
  const names = [...new Set(spec.rows.map(d => d.series))];
  const parent = d3.select(g.node().parentNode.parentNode);
  const legend = parent.append('div').attr('class', 'legend');
  names.forEach((n, i) => {
    legend.append('span').html(`<span class="dot" style="background:${COLORS[i % 8]}"></span>${n}`);
  });
}
function fmt(v) { return typeof v === 'number' ? d3.format(',.2~f')(v) : v; }
// Simple relative-luminance check so a label placed *inside* a colored
// fill (only ever done for the pie's in-slice labels) always clears
// contrast, per the rule that identity comes from the mark, never from
// coloring the text -- a fixed white would be illegible on a light hue.
function textColorOn(hex) {
  const c = hex.replace('#', '');
  const r = parseInt(c.substring(0, 2), 16), g = parseInt(c.substring(2, 4), 16), b = parseInt(c.substring(4, 6), 16);
  return (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.6 ? '#0b0b0b' : '#ffffff';
}

// Exports a chart as a standalone PNG/SVG file, for pasting into a doc/deck.
// A static export inherently loses the live hover tooltips (that's a
// property of static images, not something worth trying to fake) -- the
// interactive HTML file itself is unaffected and still has full tooltips.
function exportChart(chartEl, title, format) {
  const svgEl = chartEl.querySelector('svg');
  if (!svgEl) return;
  const cs = getComputedStyle(document.body);
  const bg = cs.getPropertyValue('--surface-1').trim();
  const textMuted = cs.getPropertyValue('--text-muted').trim();
  const textSecondary = cs.getPropertyValue('--text-secondary').trim();
  const gridLine = cs.getPropertyValue('--grid-line').trim();

  const clone = svgEl.cloneNode(true);
  clone.setAttribute('style', `background:${bg}`);
  const style = document.createElementNS('http://www.w3.org/2000/svg', 'style');
  // Scoped per class rather than a blanket `text{fill:...}` -- that would
  // override the pie's own per-slice luminance-picked label color (a
  // literal hex already baked into its own fill attribute, which must be
  // left alone) as well as the CSS var() this SVG has no scope to resolve
  // once cloned out on its own.
  style.textContent = `text { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; } `
    + `.axis text { fill: ${textMuted}; } .axis path, .axis line { stroke: ${gridLine}; } `
    + `.bar-label, .value-label, .legend-label { fill: ${textSecondary}; }`;
  clone.insertBefore(style, clone.firstChild);

  const xml = new XMLSerializer().serializeToString(clone);
  const svgBlob = new Blob([xml], { type: 'image/svg+xml;charset=utf-8' });
  if (format === 'svg') { downloadBlob(svgBlob, `${slugify(title)}.svg`); return; }

  const url = URL.createObjectURL(svgBlob);
  const img = new Image();
  img.onload = () => {
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
    canvas.toBlob(blob => downloadBlob(blob, `${slugify(title)}.png`), 'image/png');
  };
  img.onerror = () => URL.revokeObjectURL(url);
  img.src = url;
}

// Exports ONE chart as its own standalone HTML file that still has full
// working tooltips -- unlike PNG/SVG (necessarily static), this clones the
// whole current page (same CSS, palette, and render code already loaded)
// and narrows its own CHARTS array down to just this one chart, so opening
// the file re-renders exactly this chart, fully interactive, with nothing
// duplicated from the dashboard it came from.
function exportChartHtml(spec, title) {
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
  downloadBlob(new Blob([html], { type: 'text/html;charset=utf-8' }), `${slugify(title)}.html`);
}

function downloadBlob(blob, filename) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
function slugify(s) { return (s || 'chart').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '') || 'chart'; }

CHARTS.forEach(renderChart);

