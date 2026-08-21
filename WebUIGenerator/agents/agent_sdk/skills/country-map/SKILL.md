---
name: country-map
description: Sub-national choropleth map for ANY single country (India states, UK regions, Germany Bundesländer, Brazil estados, France régions, etc.). Uses public GeoJSON URLs for admin-1 boundaries. Use when a page needs: countrymap, indiamap, india, ukmap, germanymap, germany, brazilmap, brazil, francemap, france.
---

# country-map

## When to use

Trigger keywords: countrymap, indiamap, india, ukmap, germanymap, germany, brazilmap, brazil, francemap, france, canadamap, canada, australiamap, australia, japanmap, japan, chinamap, china, mexicomap, mexico, italymap, italy, spainmap, spain, southafricamap, nigeriamap, indonesiamap, provinces, bundesland, prefecture, estado, subnational, regional, statewise, districtwise.

## How to build

This capability ships a full, tested reference implementation. **Read `references/CountryMap.skill.tsx`** — it already implements the component. You have two options:
1. COPY VERBATIM — write it to the target page path unchanged.

2. FILL SCAFFOLD — read `references/CountryMap.config.ts` and replace every `{{PLACEHOLDER}}` with real fields, writing the config alongside the component.


## Config contract

- `tableName` — string — SQLite table name from schema.sql
- `countryName` — string — display name (e.g. 'India', 'United Kingdom')
- `geoJsonUrl` — string — public URL to GeoJSON with admin-1 boundaries (see config template for common URLs)
- `regionNameProp` — string — GeoJSON property containing region name (e.g. 'NAME_1', 'name', 'state')
- `regionField` — string — column in YOUR data matching region names in the GeoJSON
- `valueField` — string — numeric field that drives colour intensity
- `labelField` — string — label for tooltips (often same as regionField)
- `title` — string
- `colorScheme` — 'blue'|'green'|'orange'|'purple'|'red'
- `valueFormat` — string — d3 format (e.g. ',.0f', '$,.1f')
- `filterField` — string | null


## House rules
- D3 only for charts/maps (never Highcharts/Recharts/Chart.js).
- Data comes from `useApi(tableName)` → `GET /api/data/{tableName}` (snake_case fields). Never import from `../data`.
