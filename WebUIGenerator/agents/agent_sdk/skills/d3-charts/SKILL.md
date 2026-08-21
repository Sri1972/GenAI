---
name: d3-charts
description: All-in-one chart page supporting 14 chart types: bar, stacked-bar, line, donut/pie, area, grouped-bar, scatter, bubble, histogram, heatmap, treemap, radar, waterfall, or multi-panel grid. Set chartType in config. Use when a page needs: barchart, bar, histogram, ranking, waterfall, bridge, linechart, trend, timeseries, timeline.
---

# d3-charts

## When to use

Trigger keywords: barchart, bar, histogram, ranking, waterfall, bridge, linechart, trend, timeseries, timeline, sparkline, forecast, donut, pie, share, breakdown, composition, area, stacked, stackedarea, cumulative, groupedbar, grouped, clustered, multibar, scatter, bubble, correlation, quadrant, heatmap, matrix, treemap, hierarchy, radar, spider, chart, charts, analytics, stats, reports, performance, visualization.

## How to build

This capability ships a full, tested reference implementation. **Read `references/Charts.skill.tsx`** — it already implements the component. You have two options:
1. COPY VERBATIM — write it to the target page path unchanged.

2. FILL SCAFFOLD — read `references/Charts.config.ts` and replace every `{{PLACEHOLDER}}` with real fields, writing the config alongside the component.


## Config contract

- `chartType` — 'bar'|'stacked-bar'|'line'|'donut'|'pie'|'area'|'grouped-bar'|'scatter'|'bubble'|'histogram'|'heatmap'|'treemap'|'radar'|'waterfall'|'multi' — MUST be set
- `tableName` — string — SQLite table name from schema.sql (data fetched from /api/data/{tableName})
- `pageTitle` — string
- `pageSubtitle` — string | null
- `labelField` — string — bar label, slice label, treemap label, or waterfall step label
- `valueField` — string — numeric field for bar height, slice size, etc.
- `colorField` — string | null — per-item colour field (or null for auto-colour)
- `defaultColor` — string — hex fallback colour (bar, histogram, bubble)
- `horizontal` — boolean — true for horizontal bars
- `valueFormat` — string — d3 format e.g. ',.0f' or '$,.1f'
- `centerLabel` — string — text in donut hole
- `xField` — string — x-axis data field
- `series` — Array<{field, label, color}> — for line/area/grouped-bar/stacked-bar
- `yFormat` — string — d3 format for y axis
- `stacked` — boolean — true for stacked area
- `groupKey` — string — x-axis group field for grouped-bar/stacked-bar
- `yField` — string — y-axis numeric field for scatter/bubble
- `sizeField` — string — circle size field for bubble chart
- `xLabel` — string — x-axis label text
- `yLabel` — string — y-axis label text
- `groupField` — string | null — colour grouping for bubble chart
- `bins` — number — number of histogram bins (default 20)
- `colorScheme` — 'blue'|'red'|'green'|'purple' — heatmap/map colour ramp
- `axes` — string[] — spoke label names for radar chart
- `positiveColor` — string — up-step bar colour (default '#22C55E')
- `negativeColor` — string — down-step bar colour (default '#EF4444')
- `totalColor` — string — total/subtotal bar colour (default '#0064D2')
- `filterField` — string | null
- `filterOptions` — string[]
- `charts` — Array of self-contained chart configs — each has: type (any chartType above), title, data, plus the fields for that type.
- `layout` — 'grid' (default) | 'tabs'


## House rules
- D3 only for charts/maps (never Highcharts/Recharts/Chart.js).
- Data comes from `useApi(tableName)` → `GET /api/data/{tableName}` (snake_case fields). Never import from `../data`.
