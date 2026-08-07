# AutoPulse Global — Automotive Sales Intelligence Platform

## What We're Building

A full-featured automotive sales intelligence platform called "AutoPulse Global" that gives OEMs and dealer groups real-time visibility into global vehicle sales, inventory health, forecasting, and AI-powered analytics. The platform is built in 4 phases, delivered iteratively.

## Target Users

- VP of Sales at global automotive companies (executive dashboards, board-ready insights)
- Dealer Analysts tracking operational metrics (inventory turns, days-on-lot, regional gaps)
- Market Strategists evaluating expansion targets and forecast scenarios

## Brand & Design

- App name: AutoPulse Global
- Accent blue: #0064D2, Accent purple: #420E71
- Sidebar: dark navy #0D1B2A with white text
- Page background: #F8FAFC
- Success: #059669, Warning: #D97706, Danger: #DC2626
- Desktop-optimized at 1440px with responsive charts

## Phase 1: Core Dashboard & Maps

**Pages:** Dashboard, Global Map, North America, Analytics

### Dashboard (Landing Page)
- Row of 6 KPI cards: Total Revenue, Units Sold, Active Dealers, Market Share, YTD Growth, EV Mix (each with value + up/down indicator)
- Two charts side by side: revenue by region (horizontal bar) + units by make (donut)
- Full-width line chart: monthly revenue with Actual, Forecast, and Prior Year lines

### Global Map
- Filter dropdowns: make, quarter
- World choropleth heatmap shaded by sales volume per country (hover tooltip: country + units)
- Summary table below: region, total volume, total revenue, top make

### North America
- Filter dropdown: make
- USA choropleth map shaded by volume per state (hover: state + units, click to highlight)
- Sortable table: State, Make, Volume, Revenue, Dealer Count, YTD Growth

### Analytics (Two tabs)
- Volume tab: multi-line chart quarterly volume for top 5 makes + grouped bar of volume by region per quarter
- Revenue tab: stacked area chart revenue by region over time + horizontal bar top 10 models by revenue

## Phase 2: Sales Grid & Inventory Management

**New pages:** Sales Grid, Inventory

### Sales Grid
- Full data explorer with filter bar: search, region dropdown, make dropdown, quarter dropdown, reset button, row count
- Sortable table: Country, Region (badge), Make (badge), Model, Quarter, Volume, Revenue, YTD Growth (green/red), Market Share (progress bar)
- Pagination at 20 rows/page + CSV export

### Inventory
- Four KPI cards: Total Stock, % Available, In Transit, Avg Days on Lot
- Filter bar: search by VIN/model/city, status dropdown, make dropdown
- Sortable table: VIN (monospace), Make, Model, Year, Trim, Color, MSRP, Status (color-coded: Available=green, Reserved=amber, In Transit=blue, Sold=gray), Dealer City, Days on Lot (0-30 green, 31-60 amber, 61+ red)
- Horizontal bar chart: vehicle count by age bucket (0-30 / 31-60 / 61-90 / 90+ days)

## Phase 3: Forecasting & Scenario Planning

**New page:** Forecast

### Forecast
- Controls: scenario dropdown (Base Case / Optimistic +15% / Pessimistic -15%), make dropdown, confidence band toggle
- Line chart Jan 2024-Dec 2025: Actual (solid blue), Forecast (dashed purple), Prior Year (gray), optional confidence band (shaded upper/lower)
- Two charts below: grouped bar EV vs ICE monthly volumes + variance bar chart (actual minus forecast, green/red bars)
- Summary table: last 6 + next 6 months with Month, Actual, Forecast, Variance, Variance %, Confidence (progress bar)

## Phase 4: AI Concierge (Live LLM)

**New page:** AI Concierge (component: DataAdvisor)

### Three-Column Layout

**Left (240px) — Persona Selector:**
Three persona cards with colored left borders. Each has 5 pre-built prompt buttons:
- VP of Sales (#0064D2): Q4 Revenue Summary, Top Markets by Growth, EV Mix Trend, Competitive Landscape, Board Deck Bullets
- Dealer Analyst (#420E71): Dealer Scorecard, Inventory Health, Days-to-Sale Analysis, Regional Gaps, Restock Recommendations
- Market Strategist (#059669): Global Expansion Targets, Segment Mix Analysis, Asia Pacific Outlook, Price Point Sensitivity, Forecast Scenarios

**Center (flex) — Chat Panel:**
- User messages in dark navy bubbles, AI responses in white bubbles with border
- Typing indicator (bouncing dots) while waiting
- Text input + Send button (Enter to submit)
- AI reads the real database and generates answers tailored to the selected persona's role
- Inline charts below AI responses (bar, line, area, donut, scatter — at least 5 distinct chart types across 15 prompts)

**Right (280px) — Export Panel:**
Four slide template cards (Executive Summary, Regional Deep Dive, Market Analysis, Dealer Spotlight) with "Export PPTX" button that generates a PowerPoint deck with one slide per AI response including native charts.

## Data Architecture

- SQLite database with tables: global_sales, state_sales, kpis, forecast, inventory
- REST API serving all data (no JSON file imports in frontend)
- global_sales: 60 records across 15 countries, 8 makes (Tesla, Toyota, BMW, Ford, Mercedes, Volkswagen, Hyundai, Honda)
- state_sales: 40 records across major US states
- inventory: 50 VIN records with status tracking
- forecast: monthly Jan 2024-Dec 2025 with actual/forecast/upper/lower/ev/ice/priorYear
- Personas and slide templates stored as TypeScript config (not data files)

## Technical Stack

- React + TypeScript frontend
- Python FastAPI backend with SQLite
- Chart library for all visualizations (responsive)
- pptxgenjs for PowerPoint export
- LiteLLM proxy for AI concierge responses
- API-first architecture: all data flows through REST endpoints

## Key Behaviors

- Same question asked by different personas yields different answer styles
- Chat supports follow-up questions (conversation memory)
- Response caching for repeated prompt clicks
- All charts resize responsively
- Error handling with user-friendly messages and retry
- No external API calls for data — all local/seeded
