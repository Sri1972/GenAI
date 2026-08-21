---
name: usa-map
description: Interactive D3 USA state-level choropleth map. Works for state sales, election maps, demographic data, etc. Use when a page needs: usamap, usmap, northamerica, states, statemap, usachoropleth, unitedstates.
---

# usa-map

## When to use

Trigger keywords: usamap, usmap, northamerica, states, statemap, usachoropleth, unitedstates.

## How to build

This capability ships a full, tested reference implementation. **Read `references/UsaMap.skill.tsx`** — it already implements the component. You have two options:
1. COPY VERBATIM — write it to the target page path unchanged.

2. FILL SCAFFOLD — read `references/UsaMap.config.ts` and replace every `{{PLACEHOLDER}}` with real fields, writing the config alongside the component.


## Config contract

- `dataExport` — imported array from ../data
- `stateField` — string — state name or abbreviation field
- `valueField` — string — numeric field that drives colour intensity
- `title` — string
- `colorScheme` — 'blue'|'green'|'orange'|'purple'
- `filterField` — string | null


## House rules
- D3 only for charts/maps (never Highcharts/Recharts/Chart.js).
- Data comes from `useApi(tableName)` → `GET /api/data/{tableName}` (snake_case fields). Never import from `../data`.
