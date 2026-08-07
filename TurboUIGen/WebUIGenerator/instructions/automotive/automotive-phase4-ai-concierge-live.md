# AutoPulse — Phase 4: AI Concierge (Live LLM)

## What to add

Add 1 new page to the existing AutoPulse app. Keep all existing pages and data unchanged.

Add to the sidebar last:
8. DataAdvisor

**Page component name:** `DataAdvisor` (file: `src/pages/DataAdvisor.tsx`)
**Sidebar label:** "AI Concierge"

> NOTE: This page has a custom three-column layout with personas. Generate the full page component from scratch — do NOT use a pre-built skill template.

---

## Prerequisites

This is Phase 4 — it requires the existing AutoPulse app (Phases 1–3) already built with the API-first architecture (schema.sql, seed.sql, api/ folder with app_server.py).

The app's database has a `global_sales` table with columns: country, country_code, region, make, model, units, revenue, ytd_growth, market_share, quarter.

---

## How it works

This page uses the **DataChat API** (`/api/chat`) as its backend. Instead of canned responses from a JSON file, the AI reads the real `global_sales` database table and generates answers on the fly — tailored to the selected persona's role.

The `/api/chat` endpoint is already part of `app_server.py` (bundled in the `api/` folder). The page just needs to POST to it with the right payload.

---

## New Data

### src/config/Personas.config.ts
Export a `personas` array and a `slideTemplates` array. These are UI configuration, NOT database data — store them as a TypeScript config file.

Three personas, each with id, name, role, description, accentColor, systemContext (a short role instruction), and a prompts array of 5 objects (each with id, label, question).

- **VP of Sales** (accent `#0064D2`, systemContext: "You are advising a VP of Sales at a global automotive company. Keep answers executive-level: key figures, trends, and actionable takeaways. Use bullet points for board-ready summaries.")
  - Q4 Revenue Summary
  - Top Markets by Growth
  - EV Mix Trend
  - Competitive Landscape
  - Board Deck Bullets

- **Dealer Analyst** (accent `#420E71`, systemContext: "You are advising a Dealer Analyst. Focus on granular operational metrics: dealer performance, inventory turns, days-to-sale, and regional distribution gaps. Be precise with numbers.")
  - Dealer Scorecard
  - Inventory Health
  - Days-to-Sale Analysis
  - Regional Gaps
  - Restock Recommendations

- **Market Strategist** (accent `#059669`, systemContext: "You are advising a Market Strategist. Focus on macro trends, segment shifts, geographic expansion opportunities, and forecast scenarios. Compare regions and identify white-space.")
  - Global Expansion Targets
  - Segment Mix Analysis
  - Asia Pacific Outlook
  - Price Point Sensitivity
  - Forecast Scenarios

Also include in the same config file a `slideTemplates` array with 4 templates: Executive Summary (navy `#132445`), Regional Deep Dive (teal `#0891B2`), Market Analysis (purple `#420E71`), Dealer Spotlight (amber `#D97706`). Each has id, name, description, primary (color hex).

**DO NOT create any src/data/*.json files. The personas and templates are config, not data.**

---

## New Page

### AI Concierge
Three-column layout, full height.

**Left column (240px fixed):** Persona selector.
- Three persona cards — name, role, colored left border matching accentColor. Clicking selects the persona.
- Below the cards: 5 prompt buttons for the active persona. Each button shows the prompt label. Clicking a button sends that question to the chat.

**Center column (flex):** Chat panel.
- User messages right-aligned in dark navy bubbles (`#0D1B2A`).
- AI responses left-aligned in white bubbles with a light border.
- While waiting for a response: a typing indicator (three bouncing dots).
- Text input at the bottom with a Send button. Enter key submits.
- AI can respond with plain text, charts, tables, or geographic maps — all rendered inline in the chat.

**Right column (280px fixed):** Export panel.
- Four slide template cards showing name, description, and a colored top stripe.
- Each has an "Export PPTX" button that exports the current chat conversation as a PowerPoint deck (one slide per AI response, charts included).

---

## Behavior notes

1. **Persona context** — the same question asked by different personas should yield different styles of answer.
2. **Chat history** — follow-up questions should work (the AI remembers the conversation).
3. **Error handling** — if the AI fails, show a friendly error message and let the user retry.
4. **Loading state** — disable buttons while waiting for a response.
5. **Response caching** — if the user clicks the same prompt button twice, show the cached answer instantly without re-calling the AI.
6. **Personas config** — store as a TypeScript config file, not a JSON data file.
