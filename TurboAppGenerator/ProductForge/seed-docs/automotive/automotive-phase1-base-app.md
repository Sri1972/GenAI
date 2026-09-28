# AutoPulse Global — Product Requirements

## Overview

**AutoPulse Global** is an automotive sales intelligence platform. It shows vehicle sales performance across global markets and US states.

**Brand:**
- App name: AutoPulse Global
- Accent blue: `#0064D2` · Accent purple: `#420E71`
- Sidebar: dark navy `#0D1B2A` with white text
- Page background: `#F8FAFC`
- Success: `#059669` · Warning: `#D97706` · Danger: `#DC2626`

---

## Navigation

Dark sidebar with 4 pages:

1. Dashboard
2. Global Map
3. North America
4. Analytics

---

## Data

### Global Sales
Fields: country, countryCode, region (Americas / Europe / Asia Pacific / Middle East & Africa), make, model, units, revenue, ytdGrowth, marketShare, quarter (Q1–Q4 2024).
Generate 60 records across 15 countries and 8 makes: Tesla, Toyota, BMW, Ford, Mercedes, Volkswagen, Hyundai, Honda.

### US State Sales
Fields: state, abbr, make, model, units, revenue, dealerCount, ytdGrowth.
Generate 40 records across major US states.

### KPIs
6 metrics: Total Revenue, Units Sold, Active Dealers, Market Share, YTD Growth, EV Mix. Each has a value and change direction (up/down/neutral).

### Forecast
Monthly Jan 2024 – Dec 2025. Fields: month (YYYY-MM), actual (null for future), forecast, lower, upper, ev, ice.

---

## Pages

### Dashboard
Executive overview — the landing page.

- Row of 6 KPI cards (label, value, up/down indicator).
- Two charts side by side: revenue by region (horizontal bar) and units by make (donut).
- Full-width line chart: monthly revenue with Actual, Forecast, and Prior Year lines.

### Global Map
World heatmap of vehicle sales.

- Dropdowns to filter by make and quarter.
- Full-width world map shaded by sales volume per country. Hover tooltip shows country and units.
- Summary table below: region, total volume, total revenue, top make.

### North America
US state-level sales heatmap.

- Dropdown to filter by make.
- Full-width USA choropleth map shaded by volume per state. Hover shows state and units. Click a state to highlight it.
- Sortable table below: State, Make, Volume, Revenue, Dealer Count, YTD Growth.

### Analytics
Trend analysis in two tabs.

- **Tab 1 — Volume:** Multi-line chart of quarterly volume for top 5 makes. Below it, a grouped bar chart of volume by region per quarter.
- **Tab 2 — Revenue:** Stacked area chart of revenue by region over time. Below it, a horizontal bar chart of top 10 models by revenue.

---

## General Requirements

- All data is local — no external API calls
- All charts resize responsively
- App looks polished at 1440px desktop width