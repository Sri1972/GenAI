---
name: world-map
description: Interactive D3 world choropleth map shaded by any numeric metric. Works for global sales, population, election results, climate data, etc. Use when a page needs: worldmap, globalmap, world, global, international, choropleth, heatmap, countries.
---

# world-map

## When to use

Trigger keywords: worldmap, globalmap, world, global, international, choropleth, heatmap, countries.

## How to build

This capability ships a full, tested reference implementation. **Read `references/WorldMap.skill.tsx`** — it already implements the component. You have two options:
1. COPY VERBATIM — write it to the target page path unchanged.

2. FILL SCAFFOLD — read `references/WorldMap.config.ts` and replace every `{{PLACEHOLDER}}` with real fields, writing the config alongside the component.


## Config contract

- `dataExport` — imported array from ../data
- `countryCodeField` — string — ISO-2 country code field (e.g. 'countryCode')
- `valueField` — string — numeric field that drives colour intensity
- `labelField` — string — country name field for tooltip
- `title` — string
- `colorScheme` — 'blue'|'green'|'orange'|'purple' — heatmap colour ramp
- `filterField` — string | null — optional dropdown filter field


## House rules
- D3 only for charts/maps (never Highcharts/Recharts/Chart.js).
- Data comes from `useApi(tableName)` → `GET /api/data/{tableName}` (snake_case fields). Never import from `../data`.
