---
name: data-chat
description: LLM-powered chat interface that connects to ANY data source. Uses a local FastAPI backend with Bedrock/LiteLLM. Use when a page needs: datachat, chatwithdata, dataillm, aichat, chatbot, askdata, nlq, naturalanguage, chatexcel, chatpdf.
---

# data-chat

## When to use

Trigger keywords: datachat, chatwithdata, dataillm, aichat, chatbot, askdata, nlq, naturalanguage, chatexcel, chatpdf, chatwithai, copilot, dataassistant, querydata, smartchat.

## How to build

This capability ships a full, tested reference implementation. **Read `references/DataChat.skill.tsx`** — it already implements the component. You have two options:
1. COPY VERBATIM — write it to the target page path unchanged.

2. FILL SCAFFOLD — read `references/DataChat.config.ts` and replace every `{{PLACEHOLDER}}` with real fields, writing the config alongside the component.


## Config contract

- `pageTitle` — string — heading displayed above the chat
- `pageSubtitle` — string — description below the heading
- `apiBaseUrl` — string — base URL for the API server (default '/api')
- `accentColor` — hex string — accent for user bubbles (e.g. '#4F46E5')
- `contextType` — 'structured'|'document'|'custom'|'upload-excel'|'upload-pdf'
- `initialContext` — null (for upload modes) or {schema?, sampleRows?, text?, metadata?}
- `suggestedPrompts` — string[4] — clickable prompt chips shown when chat is empty
- `systemPromptOverride` — string|null — custom system prompt or null for default


## House rules
- D3 only for charts/maps (never Highcharts/Recharts/Chart.js).
- Data comes from `useApi(tableName)` → `GET /api/data/{tableName}` (snake_case fields). Never import from `../data`.


## Backend
This skill needs a backend: server `datachat_api_server.py`, env `datachat_env_template.txt`, python deps: fastapi, uvicorn, python-dotenv, openai, httpx, openpyxl, PyMuPDF. See the `fastapi-backend` skill.
