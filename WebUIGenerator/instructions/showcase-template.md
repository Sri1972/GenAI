# [App Name] — Full Feature Showcase

> **Instructions for PMs:** Copy this file, replace the bracketed sections with your domain data, and run it through TurboUIGen. Everything below "---" markers is what you customize.

---

## App Overview

**App name:** [Your App Name]
**Theme:** [One-line description, e.g. "Global SaaS Metrics Dashboard"]
**Accent color:** [Primary brand hex, e.g. #0064D2]

---

## Data Model

Define your database table(s) below. Each table becomes a REST API endpoint automatically (`/api/data/{table_name}`).

### Table: [table_name]
| Column | Type | Description |
|--------|------|-------------|
| [col1] | text | [what it is] |
| [col2] | numeric | [what it is] |
| [col3] | categorical | [what it is — list values if enum-like] |
| ... | ... | ... |

**Seed rows:** [number, e.g. 60–100 rows]
**Seed notes:** [any distribution hints, e.g. "spread across 4 regions and 8 product lines"]

> Add more tables by repeating this block. Each table gets its own page or can be shared across pages.

---

## Pages

### Page 1: Dashboard
**Sidebar label:** "Dashboard"

Overview page with KPIs and charts.

- **KPI row** (top): [List 4–6 metrics, e.g. Total Revenue, Active Users, Avg Order Value, MoM Growth]
- **Charts row** (2 side-by-side):
  - Left: [chart type] showing [what]. E.g. "Bar chart showing revenue by region"
  - Right: [chart type] showing [what]. E.g. "Donut chart showing product mix by category"
- **Map** (below charts): World choropleth colored by [metric], e.g. "revenue by country". Tooltip shows country name + value.

**Chart types available:** bar, line, donut, scatter, area, grouped bar, stacked bar

---

### Page 2: Data Explorer
**Sidebar label:** "Explorer"

Full data grid with filtering, sorting, and export.

- **Filter bar:**
  - Text search: searches across [which columns, e.g. name, description]
  - Dropdown filters: [list columns that should be dropdowns, e.g. Region, Category, Status]
  - Reset button + row count badge
- **Data table:**
  - Columns: [list all visible columns with any special formatting]
  - Special formatting examples:
    - `status` → color badge (green=Active, amber=Pending, red=Churned)
    - `growth` → green/red text based on positive/negative
    - `score` → progress bar (0–100)
  - Sortable by clicking column headers
  - Pagination: 20 rows per page
- **Export CSV** button that downloads the current filtered view

---

### Page 3: AI Advisor
**Sidebar label:** "AI Advisor"

AI chat page powered by the `/api/chat` endpoint. Three-column layout.

- **Left column:** Persona selector
  - Define 2–3 personas for your domain:
    - **[Persona 1 name]** (role: [role], accent: [hex])
      System context: "[How the AI should frame answers for this persona]"
      Prompt buttons: [list 4–5 quick questions]
    - **[Persona 2 name]** (role: [role], accent: [hex])
      System context: "[...]"
      Prompt buttons: [list 4–5 quick questions]

- **Center column:** Chat panel
  - Renders text, charts, tables, and maps inline based on AI response
  - Free-text input at the bottom — user can ask anything about the data
  - Typing indicator while waiting

- **Right column:** Export panel with 3–4 slide templates for PPTX export

---

## Architecture (DO NOT EDIT — handled automatically)

- **Database:** SQLite with schema.sql + seed.sql in `api/` folder
- **Backend:** Python FastAPI (`api/app_server.py`) auto-generated with:
  - `GET /api/data/{table}` — list/filter/sort/paginate
  - `GET /api/data/{table}/aggregate` — groupBy/sum/avg/count
  - `POST /api/chat` — LLM-powered data chat with chart/table/map responses
- **Frontend:** React 18 + Vite + TypeScript + Tailwind CSS
- **Charts:** D3.js (no recharts/highcharts)
- **Maps:** D3 + topojson + world-atlas/us-atlas
- **Components:** mobility-global-ds (Header, Sidebar, Card, Button, Badge)
- **Data fetching:** `useApi` hook — no static JSON files

---

## Quick-Start Example

Below is a complete filled-in example you can run as-is to see every feature working:

---
---

# SaaS Metrics Hub — Full Feature Showcase

## App Overview

**App name:** SaaS Metrics Hub
**Theme:** B2B SaaS company performance tracker
**Accent color:** #2563EB

---

## Data Model

### Table: subscriptions
| Column | Type | Description |
|--------|------|-------------|
| company | text | Customer company name |
| country | text | Country name |
| country_code | text | ISO 3166-1 alpha-2 (US, GB, DE, etc.) |
| region | categorical | Americas, Europe, Asia Pacific, Middle East & Africa |
| plan | categorical | Starter, Professional, Enterprise |
| mrr | numeric | Monthly recurring revenue in USD |
| arr | numeric | Annual recurring revenue (mrr × 12) |
| users | numeric | Active seats |
| health_score | numeric | 0–100 customer health score |
| status | categorical | Active, At Risk, Churned |
| signed_date | text | YYYY-MM-DD contract start |
| nps | numeric | -100 to 100 net promoter score |
| industry | categorical | Technology, Finance, Healthcare, Retail, Manufacturing |

**Seed rows:** 80
**Seed notes:** Spread across all 4 regions, 3 plans, 5 industries. ~60% Active, ~25% At Risk, ~15% Churned. MRR ranges: Starter $500–2000, Professional $2000–8000, Enterprise $8000–50000.

---

## Pages

### Page 1: Dashboard
**Sidebar label:** "Dashboard"

- **KPI row:** Total ARR, Active Customers, Avg Health Score, Churn Rate (% of Churned), Avg NPS
- **Charts (2 side-by-side):**
  - Left: Bar chart — ARR by region
  - Right: Donut chart — customer count by plan (Starter/Professional/Enterprise)
- **Charts (2 side-by-side below):**
  - Left: Stacked bar — status breakdown (Active/At Risk/Churned) by region
  - Right: Scatter plot — health_score vs mrr, colored by status
- **Map:** World choropleth colored by total ARR per country (color scheme: blue)

---

### Page 2: Customer Explorer
**Sidebar label:** "Customers"

- **Filter bar:**
  - Text search: company name
  - Dropdowns: Region, Plan, Status, Industry
  - Reset + row count badge
- **Data table:**
  - Columns: Company, Region (badge), Plan (badge), MRR (formatted $), Users, Health Score (progress bar 0–100, green >70, amber 40–70, red <40), Status (color badge: Active=green, At Risk=amber, Churned=red), NPS, Industry
  - Sortable, paginated at 20 rows
- **Export CSV** button

---

### Page 3: AI Advisor
**Sidebar label:** "AI Advisor"

- **Personas:**
  - **CRO** (Chief Revenue Officer) — accent `#0064D2`
    System context: "You are advising a Chief Revenue Officer. Focus on revenue growth, churn impact, expansion opportunities, and board-level metrics. Be concise with executive summaries."
    Prompts: ARR Growth Summary, Churn Risk Report, Expansion Revenue Opportunity, Regional Performance Ranking, Board Deck Bullets

  - **CS Lead** (Customer Success) — accent `#059669`
    System context: "You are advising a Customer Success leader. Focus on health scores, at-risk accounts, NPS trends, and retention strategies. Be actionable and specific."
    Prompts: At-Risk Accounts, Health Score Distribution, NPS Trend Analysis, Retention Playbook, Top Accounts to Save

  - **Product Manager** — accent `#7C3AED`
    System context: "You are advising a Product Manager. Focus on usage patterns, plan adoption, feature-value correlation, and segment behaviors. Use data to support product decisions."
    Prompts: Plan Adoption Breakdown, Usage vs Health Correlation, Enterprise vs SMB Patterns, Feature Tier Analysis, Segment Opportunities

- **Export templates:** Executive Summary (navy #132445), Revenue Deep Dive (blue #2563EB), Customer Health (green #059669), Market Analysis (purple #7C3AED)

---

## Important implementation notes

1. All data comes from the SQLite database via `/api/data/subscriptions`. Use the `useApi` hook.
2. Do NOT create `src/data/*.json` files.
3. The AI chat supports text, chart, table, AND map response types — all rendered inline.
4. Wrap `/api/chat` fetch with an `AbortController` (180s timeout).
5. Cache chat responses per persona+question to avoid redundant LLM calls.
6. Charts use D3.js. Maps use D3 + topojson + world-atlas.
7. The DataAdvisor page is a custom three-column layout — generate from scratch, not from a skill template.
