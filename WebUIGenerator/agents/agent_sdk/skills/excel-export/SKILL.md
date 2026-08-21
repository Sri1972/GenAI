---
name: excel-export
description: Excel/CSV export button with optional sheet configuration. Use when a page needs: excelexport, xlsx, csvexport, download, spreadsheet.
---

# excel-export

## When to use

Trigger keywords: excelexport, xlsx, csvexport, download, spreadsheet.

## How to build

This capability ships a full, tested reference implementation. **Read `references/ExcelExport.skill.tsx`** — it already implements the component. You have two options:
1. COPY VERBATIM — write it to the target page path unchanged.

2. FILL SCAFFOLD — read `references/ExcelExport.config.ts` and replace every `{{PLACEHOLDER}}` with real fields, writing the config alongside the component.


## Config contract

- `sheets` — Array<{name, dataExport, columns: [{key, header}]}>
- `filename` — string — e.g. 'report.xlsx'


## House rules
- D3 only for charts/maps (never Highcharts/Recharts/Chart.js).
- Data comes from `useApi(tableName)` → `GET /api/data/{tableName}` (snake_case fields). Never import from `../data`.
