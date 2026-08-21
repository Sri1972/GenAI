---
name: ai-chat
description: Three-panel AI chat interface: persona selector + chat window + export panel. Use when a page needs: faqassistant, faqbot, helpdesk.
---

# ai-chat

## When to use

Trigger keywords: faqassistant, faqbot, helpdesk.

## How to build

This capability ships a full, tested reference implementation. **Read `references/AiChat.skill.tsx`** — it already implements the component. You have two options:
1. COPY VERBATIM — write it to the target page path unchanged.

2. FILL SCAFFOLD — read `references/AiChat.config.ts` and replace every `{{PLACEHOLDER}}` with real fields, writing the config alongside the component.


## Config contract

- `personasExport` — imported personas array — each: {id, name, role, accentColor, prompts:[{id,label,question}]}
- `responsesExport` — imported responses map — Record<questionString, responseString>
- `slideTemplates` — imported slide templates (or null if no PPTX export)
- `pageTitle` — string
- `pageSubtitle` — string


## House rules
- D3 only for charts/maps (never Highcharts/Recharts/Chart.js).
- Data comes from `useApi(tableName)` → `GET /api/data/{tableName}` (snake_case fields). Never import from `../data`.
