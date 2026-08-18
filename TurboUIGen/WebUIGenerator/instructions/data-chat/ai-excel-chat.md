# AI Excel Chat — Chat with Your Data

## Overview

**AI Excel Chat** is a client-side Excel upload app with an AI-powered chat interface. Users upload any `.xlsx` or `.xls` file, the app parses it, and then they can ask natural language questions about their data. The AI responds with text answers, auto-generated charts, or filtered data tables.

**Brand:**
- App name: AI Excel Chat
- Primary color: `#4F46E5` (indigo-600)
- Background: `#F8FAFC`
- Card background: white, rounded-xl, subtle shadow

---

## Dependencies

Add these to `package.json`:
- `d3` — for rendering inline charts in AI responses
- No xlsx needed on frontend — the backend handles parsing

---

## Architecture

This is a SINGLE-PAGE application with no routing. Uses the `data-chat` skill.

The app has two states:
1. **Upload State** — drag-and-drop zone for Excel files
2. **Chat State** — after upload, an AI chat interface where you ask questions about your data

---

## Skill Usage — MANDATORY

**You MUST use the `data-chat` skill for this app.** The skill provides:
- File upload with drag-and-drop (Excel/PDF)
- AI chat interface with real LLM calls via backend API
- Inline D3 chart rendering for chart responses
- Sortable table rendering for tabular responses
- Markdown-formatted text responses
- Typing indicators, error handling, retry

**CRITICAL — Page naming:** Name your main page `DataChat` or `AiChat` or `ChatWithData` so the skill auto-matching triggers correctly.

---

## Configuration

The DataChat config should use:
- `contextType: 'upload-excel'` — user uploads an Excel file
- `suggestedPrompts` — provide 4 useful example questions like:
  - "What are the key trends in this data?"
  - "Show me a bar chart of the top 10 values"
  - "Summarize the data by category"
  - "What correlations can you find?"
- `accentColor: '#4F46E5'`

---

## Backend

This app requires the DataChat API server (`api_server.py`) running alongside the frontend. The skill automatically bundles:
- `api_server.py` — FastAPI server with `/api/chat` and `/api/ingest/excel` endpoints
- `.env` — pre-filled with LiteLLM proxy credentials
- `requirements.txt` — Python dependencies

To run the backend:
```bash
pip install -r requirements.txt
python api_server.py
```

The Vite dev server proxies `/api/*` requests to the backend on port 8080.

---

## File Structure

```
src/
  App.tsx     — imports and renders the DataChat page
  pages/
    DataChat.tsx  — the DataChat skill component (auto-matched)
  config/
    DataChat.config.ts — filled config
api_server.py     — FastAPI backend (bundled by skill)
.env              — LLM credentials (bundled by skill)
requirements.txt  — Python deps (bundled by skill)
```

Rules:
- Maximum 3 frontend files in `src/`
- The skill handles ALL chat UI, chart rendering, and upload logic
- Do NOT create custom chart components or chat bubbles — use the skill as-is

---

## Important Implementation Notes

1. **The backend must be running** for chat to work. The frontend shows an error message if the API is unreachable.
2. **Context is sent with every message** — the LLM always has access to the data schema and sample rows.
3. **Response format selector** — users can force "Chart" or "Table" output, or leave on "Auto" for the AI to decide.
4. **Large files** — the backend only sends first 10 sample rows to the LLM, but processes up to 100 rows for the response context.
5. **No client-side parsing** — unlike ExcelInsight, this app parses on the server to keep the client lean.
