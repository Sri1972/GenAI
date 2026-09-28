# GlobalCommerce — E-Commerce Analytics Hub

## App Overview

**App name:** GlobalCommerce
**Theme:** Cross-border e-commerce performance tracker
**Accent color:** #2563EB

---

## Data Model

### Table: orders
| Column | Type | Description |
|--------|------|-------------|
| order_id | text | Unique order identifier (ORD-XXXXX) |
| customer | text | Customer name |
| country | text | Country name |
| country_code | text | ISO 3166-1 alpha-2 (US, GB, DE, JP, etc.) |
| region | categorical | North America, Europe, Asia Pacific, Latin America |
| product | text | Product name |
| category | categorical | Electronics, Apparel, Home & Garden, Sports, Beauty |
| channel | categorical | Web, Mobile App, Marketplace, Social |
| amount | numeric | Order total in USD |
| quantity | numeric | Items in order |
| profit_margin | numeric | Profit margin percentage (5–45%) |
| status | categorical | Delivered, Shipped, Processing, Returned |
| order_date | text | YYYY-MM-DD (range: 2024-01 to 2025-06) |
| rating | numeric | Customer rating 1–5 (nullable for non-delivered) |

**Seed rows:** 80
**Seed notes:** Spread evenly across 4 regions (20 per region), all 5 categories, all 4 channels. Countries should include US, CA, MX, BR, GB, DE, FR, ES, JP, AU, IN, KR, SG. Amounts range $15–$2500. Mix of statuses: ~55% Delivered, ~20% Shipped, ~15% Processing, ~10% Returned.

---

## Pages

Add 3 pages to the sidebar:
1. Dashboard
2. Orders
3. AI Advisor

---

### Page 1: Dashboard
**Sidebar label:** "Dashboard"
**Component:** `src/pages/Dashboard.tsx`

Overview page with KPIs, charts, and a world map.

- **KPI row (4 cards):**
  - Total Revenue (sum of amount, formatted as $X.XM)
  - Total Orders (count)
  - Avg Order Value (mean of amount, formatted $XX)
  - Return Rate (% of Returned orders)

- **Charts row (2 side-by-side):**
  - Left: Bar chart — total revenue by region (4 bars)
  - Right: Donut chart — order count by category (5 slices)

- **Second row (2 side-by-side):**
  - Left: Grouped bar chart — order count by channel per region
  - Right: Scatter plot — amount (x) vs profit_margin (y), colored by category

- **Map (full width below):** World choropleth colored by total revenue per country (aggregate by country_code). Color scheme: blue. Tooltip shows country name + formatted revenue.

---

### Page 2: Orders
**Sidebar label:** "Orders"
**Component:** `src/pages/Orders.tsx`

Full data grid with filtering, sorting, pagination, and export.

- **Filter bar:**
  - Text search: searches order_id, customer, product
  - Dropdown: Region (all regions)
  - Dropdown: Category (all categories)
  - Dropdown: Channel (all channels)
  - Dropdown: Status (all statuses)
  - Reset button + row count badge

- **Data table columns:**
  - Order ID (monospace font)
  - Customer
  - Country (text)
  - Region (colored badge: North America=blue, Europe=purple, Asia Pacific=teal, Latin America=amber)
  - Product
  - Category (badge)
  - Channel
  - Amount (formatted $X,XXX.XX)
  - Qty
  - Margin (green if >25%, amber 15–25%, red <15%)
  - Status (color badge: Delivered=green, Shipped=blue, Processing=amber, Returned=red)
  - Rating (star display, gray if null)

- Sortable by clicking column headers
- Pagination: 15 rows per page
- **Export CSV** button downloads current filtered data

---

### Page 3: AI Advisor
**Sidebar label:** "AI Advisor"
**Component:** `src/pages/DataAdvisor.tsx`

AI chat page powered by `/api/chat`. Three-column layout.

> NOTE: This page has a custom three-column layout with personas. Generate the full page component from scratch — do NOT use a pre-built skill template.

**Left column (240px fixed):** Persona selector.
- Three persona cards — name, role, colored left border. Clicking selects the persona.
- Below: 5 prompt buttons for the active persona.

**Personas:**

- **Head of E-Commerce** (accent `#2563EB`)
  System context: "You are advising a Head of E-Commerce. Focus on revenue drivers, channel performance, conversion trends, and growth strategy. Keep answers executive-level with key metrics and recommendations."
  Prompts:
  - Revenue by Region
  - Top Performing Channels
  - Category Growth Trends
  - Return Rate Analysis
  - Board Summary

- **Operations Manager** (accent `#DC2626`)
  System context: "You are advising an Operations Manager. Focus on fulfillment metrics, processing times, return rates, and logistics optimization. Be precise with numbers and flag operational bottlenecks."
  Prompts:
  - Fulfillment Status Breakdown
  - Return Hotspots
  - Processing Backlog
  - Regional Logistics
  - Shipping Performance

- **Product Analyst** (accent `#059669`)
  System context: "You are advising a Product Analyst. Focus on product performance, category trends, margin analysis, customer ratings, and cross-sell opportunities. Use data patterns to support product decisions."
  Prompts:
  - Category Performance Matrix
  - Margin Leaders & Laggards
  - Rating vs Revenue Correlation
  - Cross-Region Product Gaps
  - Channel Mix by Category

**Center column (flex):** Chat panel.
- User messages in dark navy bubbles, AI responses in light bubbles.
- Typing indicator while waiting.
- Free-text input at bottom — user can ask anything about the data.
- AI can respond with text, charts, tables, or maps rendered inline.

**Right column (280px fixed):** Export panel.
- Four slide template cards:
  - Executive Summary (navy `#132445`)
  - Channel Deep Dive (blue `#2563EB`)
  - Product Analysis (green `#059669`)
  - Regional Report (red `#DC2626`)
- Each has "Export PPTX" button to export the chat as a slide deck.

---

## Behavior notes

1. **Persona context** — same question by different personas yields different answer styles.
2. **Chat history** — follow-up questions should work.
3. **Error handling** — show a friendly error message if AI fails, allow retry.
4. **Loading state** — disable buttons while waiting.
5. **Response caching** — repeated clicks on the same prompt button return cached answer instantly.
6. **Personas config** — store as TypeScript config, not JSON data file.
