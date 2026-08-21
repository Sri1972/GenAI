---
name: pdf-export
description: Multi-section PDF report with a styled cover page, table of contents, and one auto-table page per data section. Use when a page needs: pdf, pdfexport, exportpdf, pdfreport, printable, printreport.
---

# pdf-export

## When to use

Trigger keywords: pdf, pdfexport, exportpdf, pdfreport, printable, printreport.

## How to build

This capability ships a full, tested reference implementation. **Read `references/PdfExport.skill.tsx`** — it already implements the component. You have two options:
1. COPY VERBATIM — write it to the target page path unchanged.

2. FILL SCAFFOLD — read `references/PdfExport.config.ts` and replace every `{{PLACEHOLDER}}` with real fields, writing the config alongside the component.


## Config contract

- `reportTitle` — string — main heading on the cover page
- `subtitle` — string — optional subtitle on cover
- `author` — string — optional author name
- `filenamePrefix` — string — e.g. 'sales-report'
- `theme` — 'striped' | 'grid' | 'plain'
- `accentColor` — hex string — e.g. '#0064D2'
- `sections` — Array<{title, description, dataExport, columns: [{key, header, format?, pdfWidth?}]}>


## House rules
- D3 only for charts/maps (never Highcharts/Recharts/Chart.js).
- Data comes from `useApi(tableName)` → `GET /api/data/{tableName}` (snake_case fields). Never import from `../data`.
