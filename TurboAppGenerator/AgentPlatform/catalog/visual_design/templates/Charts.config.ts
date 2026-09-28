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
 *   'multi'        — grid or tabs of mixed panels (charts[] array — each entry is its own cfg)
 *
 * IMPORTANT RULES:
 * 1. Line charts MUST have multiple series (one per dimension being compared).
 *    E.g. "volume by top 5 brands" = 5 series entries, NOT 1 series with combined data.
 * 2. Area charts with multiple dimensions MUST list all dimensions as separate series entries.
 * 3. Tabs layout: use layout='tabs'. Each tab is ONE entry in charts[] and can itself contain
 *    a nested charts[] array for showing multiple visualizations within that tab.
 * 4. Data is LIVE, not invented: set `tableName` to a real table from schema.sql and the
 *    template fetches it at runtime — do NOT hand-write a `data: [...]` array of numbers.
 *    aggregateSimple groups rows by labelField and computes valueField via `aggMethod`
 *    ('sum' default, or 'avg'|'count'|'min'|'max') — e.g. tableName:'orders', labelField:'quarter',
 *    valueField:'revenue' sums revenue per quarter across every row automatically.
 *    If the label/group you need lives on a DIFFERENT table than the metric, add
 *    `joinTableName` + `joinKey` (shared column) + `joinFields` (columns to pull in) — the
 *    template fetches both tables and joins them before aggregating. `data: [...]` should only
 *    hold genuinely static content that was never meant to be database-backed.
 */
export const config = {

  // ── Which chart type to render ─────────────────────────────────────────────
  chartType: '{{CHART_TYPE}}' as 'bar'|'stacked-bar'|'line'|'donut'|'pie'|'area'|'grouped-bar'|'scatter'|'bubble'|'histogram'|'heatmap'|'treemap'|'radar'|'waterfall'|'multi',

  pageTitle:    '{{PAGE_TITLE}}',
  pageSubtitle: '{{PAGE_SUBTITLE}}',

  // ── Data source ────────────────────────────────────────────────────────────
  // tableName is the REQUIRED way to get real data — fetched live from /api/{tableName}.
  // Leave data: null. Only set an inline data array for genuinely static, non-database content.
  tableName: '{{TABLE_NAME}}',  // API table name from schema.sql — data auto-fetched
  data: null as any[] | null,   // null = use tableName API; do NOT fill with invented numbers
  aggMethod: 'sum' as 'sum' | 'avg' | 'count' | 'min' | 'max',  // how same-labelField rows combine
  joinTableName: null as string | null,  // set when the group/label field lives on a different table
  joinKey: '{{JOIN_KEY}}',               // shared column between tableName and joinTableName
  joinFields: [] as string[],            // columns to pull from joinTableName onto each row

  // ── Bar / Donut / Treemap / Histogram shared ───────────────────────────────
  labelField:   '{{LABEL_FIELD}}',   // category label for bar, donut, treemap, waterfall
  valueField:   '{{VALUE_FIELD}}',   // numeric field for bar height, slice size, etc.
  colorField:   {{COLOR_FIELD}},     // optional per-row colour field (null for auto)
  defaultColor: '{{DEFAULT_COLOR}}', // fallback colour (bar, histogram, bubble)
  horizontal:   {{HORIZONTAL}},      // bar chart: true = horizontal bars
  valueFormat:  '{{VALUE_FORMAT}}',  // d3 format: ',.0f' | '$,.2f' | '.1%' etc.
  centerLabel:  '{{CENTER_LABEL}}',  // donut: text in the hole

  // ── Line / Area shared ─────────────────────────────────────────────────────
  // CRITICAL: Always include ALL dimensions as separate series entries.
  // For a "top 5 makes" line chart, include 5 series — NOT 1.
  xField: '{{X_FIELD}}',             // x-axis data field (line, area, scatter, bubble)
  series: [
    { field: '{{SERIES_1_FIELD}}', label: '{{SERIES_1_LABEL}}', color: '{{SERIES_1_COLOR}}' },
    { field: '{{SERIES_2_FIELD}}', label: '{{SERIES_2_LABEL}}', color: '{{SERIES_2_COLOR}}' },
    { field: '{{SERIES_3_FIELD}}', label: '{{SERIES_3_LABEL}}', color: '{{SERIES_3_COLOR}}' },
    // Add more series as needed — one per line/area/bar group
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
  // layout: 'tabs'  — horizontal tab bar; one tab visible at a time
  //
  // TABS WITH MULTIPLE CHARTS PER TAB:
  // When the spec says "Tab 1 has chart A and chart B", each tab entry should include
  // a nested charts[] array. The renderer stacks them vertically within the tab panel.
  //
  // Each entry in charts[] (top-level OR nested inside a tab) is a FULL, independent chart
  // config — it gets its OWN tableName (fetched live) exactly like a top-level chart. NEVER
  // substitute a hand-written data array for a live fetch. Use joinTableName when the
  // group/label lives on a different table than the metric.
  //
  // Example — 2 tabs, each with 2 live-data charts:
  // layout: 'tabs',
  // charts: [
  //   {
  //     title: 'Volume',
  //     charts: [
  //       { type: 'bar', title: 'Volume by Quarter', tableName: 'orders',
  //         labelField: 'quarter', valueField: 'units', aggMethod: 'sum' },
  //       { type: 'grouped-bar', title: 'Volume by Region', tableName: 'orders', groupKey: 'quarter',
  //         series: [{field:'east_units',label:'East',color:'#0064D2'},{field:'west_units',label:'West',color:'#D97706'}] },
  //     ],
  //   },
  //   {
  //     title: 'Revenue',
  //     charts: [
  //       { type: 'treemap', title: 'Revenue by Brand', tableName: 'orders', joinTableName: 'products',
  //         joinKey: 'product_id', joinFields: ['brand'], labelField: 'brand', valueField: 'revenue' },
  //       { type: 'bar', title: 'Top 10 Items', tableName: 'orders', labelField: 'item_name',
  //         valueField: 'revenue', horizontal: true, valueFormat: '$,.0f' },
  //     ],
  //   },
  // ],
  layout: 'grid' as 'grid' | 'tabs',
  charts: [
    // Each chart entry gets its own type, tableName (+ optional joinTableName/aggMethod), and
    // field config. For tabs: title becomes the tab label; nested charts[] shows multiple
    // charts in that tab.
  ],

} as const
