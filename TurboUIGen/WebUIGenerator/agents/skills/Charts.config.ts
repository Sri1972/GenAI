// @ts-nocheck
/**
 * Charts.config.ts — Fill in for each project.
 * Replace every {{PLACEHOLDER}} with real values from the project data.
 *
 * Set chartType to select the chart renderer:
 *   'bar'          — bar chart (horizontal or vertical)
 *   'stacked-bar'  — stacked bar (series[], groupKey)
 *   'line'         — multi-line time-series (series[], xField)
 *   'donut'/'pie'  — donut / pie with legend (labelField, valueField)
 *   'area'         — area chart, optional stacked (series[], xField)
 *   'grouped-bar'  — grouped bars per category (series[], groupKey)
 *   'scatter'      — scatter plot (xField, yField, optional series[])
 *   'bubble'       — bubble chart (xField, yField, sizeField)
 *   'histogram'    — frequency distribution (valueField, optional bins)
 *   'heatmap'      — matrix grid (xField, yField, valueField)
 *   'treemap'      — rectangular hierarchy (labelField, valueField, optional groupField)
 *   'radar'        — spider chart (axes[], series[{label,values[]}])
 *   'waterfall'    — bridge/waterfall (labelField, valueField, optional isTotal flag per row)
 *   'multi'        — grid of mixed panels (charts[] array — each entry is its own cfg)
 */
export const config = {

  // ── Which chart type to render ─────────────────────────────────────────────
  chartType: '{{CHART_TYPE}}' as 'bar'|'stacked-bar'|'line'|'donut'|'pie'|'area'|'grouped-bar'|'scatter'|'bubble'|'histogram'|'heatmap'|'treemap'|'radar'|'waterfall'|'multi',

  pageTitle:    '{{PAGE_TITLE}}',
  pageSubtitle: '{{PAGE_SUBTITLE}}',

  // ── Data source ────────────────────────────────────────────────────────────
  // Use tableName to fetch from API (preferred), or data for inline array
  tableName: '{{TABLE_NAME}}',  // API table name from schema.sql — data auto-fetched
  data: null as any[] | null,   // null = use tableName API; set inline array for static data

  // ── Bar / Donut / Treemap / Histogram shared ───────────────────────────────
  labelField:   '{{LABEL_FIELD}}',   // category label for bar, donut, treemap, waterfall
  valueField:   '{{VALUE_FIELD}}',   // numeric field for bar height, slice size, etc.
  colorField:   {{COLOR_FIELD}},     // optional per-row colour field (null for auto)
  defaultColor: '{{DEFAULT_COLOR}}', // fallback colour (bar, histogram, bubble)
  horizontal:   {{HORIZONTAL}},      // bar chart: true = horizontal bars
  valueFormat:  '{{VALUE_FORMAT}}',  // d3 format: ',.0f' | '$,.2f' | '.1%' etc.
  centerLabel:  '{{CENTER_LABEL}}',  // donut: text in the hole

  // ── Line / Area shared ─────────────────────────────────────────────────────
  xField: '{{X_FIELD}}',             // x-axis data field (line, area, scatter, bubble)
  series: [
    { field: '{{SERIES_1_FIELD}}', label: '{{SERIES_1_LABEL}}', color: '{{SERIES_1_COLOR}}' },
    // { field: '{{SERIES_2_FIELD}}', label: '{{SERIES_2_LABEL}}', color: '{{SERIES_2_COLOR}}' },
  ] as Array<{ field: string; label: string; color: string }>,
  yFormat: '{{Y_FORMAT}}',
  stacked: {{STACKED}},              // area / stacked-bar: true = stacked layers

  // ── Grouped-bar / Stacked-bar ──────────────────────────────────────────────
  groupKey: '{{GROUP_KEY}}',         // field used as x-axis group label

  // ── Scatter ────────────────────────────────────────────────────────────────
  // xField, yField, series[] (each series has a field for y), optional labelField
  yField:   '{{Y_FIELD}}',           // y-axis numeric field (scatter, bubble)
  xLabel:   '{{X_AXIS_LABEL}}',      // axis label text
  yLabel:   '{{Y_AXIS_LABEL}}',
  xFormat:  '{{X_FORMAT}}',          // d3 format for x-axis ticks

  // ── Bubble ─────────────────────────────────────────────────────────────────
  // xField, yField, sizeField, optional labelField, colorField/groupField
  sizeField:  '{{SIZE_FIELD}}',      // numeric field mapped to circle radius
  sizeLabel:  '{{SIZE_LABEL}}',      // tooltip label for the size dimension
  sizeFormat: '{{SIZE_FORMAT}}',     // d3 format for size value in tooltip
  groupField: '{{GROUP_FIELD}}',     // optional field for colour grouping

  // ── Histogram ──────────────────────────────────────────────────────────────
  // valueField, optional bins (default 20), xLabel, defaultColor
  bins: {{BINS}},                    // number of histogram bins (default 20)

  // ── Heatmap ────────────────────────────────────────────────────────────────
  // xField (columns), yField (rows), valueField, optional colorScheme
  // colorScheme: 'blue' | 'red' | 'green' | 'purple'  (default 'blue')
  colorScheme: '{{COLOR_SCHEME}}',

  // ── Treemap ────────────────────────────────────────────────────────────────
  // labelField, valueField, optional groupField (creates parent groups)

  // ── Radar ──────────────────────────────────────────────────────────────────
  // axes: string[] — spoke labels
  // series: [{ label, color, values: number[] }] — one value per axis per series
  axes: [{{RADAR_AXES}}] as string[],
  // series already defined above — for radar, each entry needs a values[] array

  // ── Waterfall ──────────────────────────────────────────────────────────────
  // labelField, valueField (positive = up, negative = down)
  // Add isTotal: true to a row to draw it from zero (subtotal / grand total bar)
  positiveColor: '{{POSITIVE_COLOR}}', // default '#22C55E'
  negativeColor: '{{NEGATIVE_COLOR}}', // default '#EF4444'
  totalColor:    '{{TOTAL_COLOR}}',    // default '#0064D2'

  // ── Filter ─────────────────────────────────────────────────────────────────
  filterField:   {{FILTER_FIELD}},
  filterOptions: [{{FILTER_OPTIONS}}],

  // ── Multi-chart mode ───────────────────────────────────────────────────────
  // Only used when chartType = 'multi'. Each entry is a self-contained chart cfg.
  // layout: 'grid'  — 2-col auto-fit grid (default)
  // layout: 'tabs'  — horizontal tab bar; one chart visible at a time (use when the spec says "tabs" or "two tabs")
  // Each chart entry uses tableName to fetch its data from the API.
  layout: 'grid' as 'grid' | 'tabs',
  charts: [
    // Examples — each chart gets its own tableName and field references from schema.sql:
    // { type: 'bar',          title: 'Revenue by Region',  tableName: 'sales', labelField: 'region',  valueField: 'revenue',  horizontal: true, valueFormat: '$,.0f' },
    // { type: 'donut',        title: 'Market Share',       tableName: 'market_share', labelField: 'brand', valueField: 'share', valueFormat: '.1%', centerLabel: 'Share' },
    // { type: 'line',         title: 'Monthly Trend',      tableName: 'monthly_sales', xField: 'month', series: [{field:'sales', label:'Sales', color:'#0064D2'}], yFormat: '$,.0f' },
    // { type: 'scatter',      title: 'Price vs Volume',    tableName: 'trades', xField: 'price', yField: 'volume', labelField: 'ticker' },
    // { type: 'stacked-bar',  title: 'Budget vs Actual',   tableName: 'budgets', groupKey: 'quarter', series: [{field:'budget',label:'Budget',color:'#94A3B8'},{field:'actual',label:'Actual',color:'#0064D2'}] },
    // { type: 'radar',        title: 'Skill Matrix',       axes: ['Speed','Quality','Cost','Scale','Support'], series: [{label:'Team A', color:'#0064D2', values:[80,70,90,60,75]}] },
  ],

} as const
