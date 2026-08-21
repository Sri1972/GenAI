---
name: pptx-export
description: PowerPoint export panel using pptxgenjs. Generates a real .pptx with cover slide + content slides from any data. Use when a page needs: pptx, powerpoint, slides, presentation, slideexport, pptxexport, slidereport.
---

# pptx-export

## When to use

Trigger keywords: pptx, powerpoint, slides, presentation, slideexport, pptxexport, slidereport.

## How to build

This capability ships a full, tested reference implementation. **Read `references/PptxExport.skill.tsx`** — it already implements the component. You have two options:
1. COPY VERBATIM — write it to the target page path unchanged.

2. FILL SCAFFOLD — read `references/PptxExport.config.ts` and replace every `{{PLACEHOLDER}}` with real fields, writing the config alongside the component.


## Config contract

- `slideTemplates` — Array<{id, name, description, primaryColor}> — visual themes
- `buildSlides` — function signature hint — describe what data to put on each slide
- `filenamePrefix` — string — e.g. 'report' → 'report-2024-01.pptx'


## House rules
- D3 only for charts/maps (never Highcharts/Recharts/Chart.js).
- Data comes from `useApi(tableName)` → `GET /api/data/{tableName}` (snake_case fields). Never import from `../data`.
