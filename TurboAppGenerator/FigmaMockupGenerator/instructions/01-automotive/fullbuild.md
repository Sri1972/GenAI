# Automotive Analytics — Full Build

**UI Mode:** 🟢 **Build Wireframe**

Build a complete 3-screen dark analytics application for an automotive sales team. Desktop layout, 1440×900.

> Do NOT apply Mobility Global branding. Use the custom dark color scheme below.

**Colors:** Background `#0f172a` · Sidebar `#1e293b` · Cards `#1e293b` · Accent `#6366f1` · Text `#f1f5f9`

---

## Screen 1: Sales Overview

Left sidebar (240px) with navigation: **Sales Overview** (active), Vehicle Inventory, Forecast.
Header bar: title "Sales Overview", "Export Report" action button (top right).

**4 KPI cards across the top:**

| Metric | Value | Trend |
|--------|-------|-------|
| Total Revenue | $4.2M | +8% vs last month |
| Units Sold | 1,847 | +12% YTD |
| Avg Deal Size | $2,274 | -2% vs last month |
| YTD Growth | +12% | On target |

**Bar chart** "Monthly Revenue by Region" — 6 bars: North 180px, South 140px, East 160px, West 120px, Central 100px, International 90px (max 200px). X-axis labels below bars.

**Data table** "Top 5 Models":

| Model | Units Sold | Revenue | Margin % | Status |
|-------|-----------|---------|----------|--------|
| Model X Pro | 412 | $936K | 22% | In Stock |
| Sedan Elite | 389 | $701K | 18% | Low Stock |
| SUV Titan | 301 | $842K | 24% | In Stock |
| City Compact | 288 | $374K | 15% | In Stock |
| Pickup Max | 275 | $660K | 21% | Critical |

**What opens what:**
- "Export Report" button → opens `export-modal` as an overlay
- Clicking table row 1 (Model X Pro) → opens `model-detail-modal` as an overlay

---

## Screen 2: Vehicle Inventory

Left sidebar: Sales Overview, **Vehicle Inventory** (active), Forecast.
Header: "Vehicle Inventory", "Add Vehicle" primary button, "Export" ghost button.
Filter bar below header: search field, Make dropdown (All/Toyota/Ford/BMW/Mercedes/Honda), Status dropdown (All/In Stock/Reserved/Sold).

**Data table — 8 rows:**

| VIN | Make | Model | Year | Color | Status | Days on Lot |
|-----|------|-------|------|-------|--------|-------------|
| 1HGBH41JXMN109186 | Honda | Civic | 2024 | Pearl White | In Stock | 12 |
| 2T1BURHE0JC043821 | Toyota | Camry | 2023 | Midnight Blue | Reserved | 28 |
| 3VWFE21C04M000001 | BMW | 3 Series | 2024 | Jet Black | In Stock | 5 |
| 1FTFW1ET5DFC10312 | Ford | F-150 | 2023 | Rapid Red | Sold | 45 |
| WDDNG7BB4EA395614 | Mercedes | C-Class | 2024 | Silver | In Stock | 8 |
| 5FNRL5H6XEB040128 | Honda | Odyssey | 2022 | Lunar Silver | Reserved | 31 |
| 2HKRM3H71FH500123 | Toyota | RAV4 | 2024 | Super White | In Stock | 3 |
| 1G1ZD5ST8JF123456 | Chevrolet | Malibu | 2023 | Mosaic Black | Sold | 67 |

**What opens what:**
- Search bar → opens `search-results-modal` as an overlay
- Make dropdown → opens `make-dropdown-modal` as an overlay
- Status dropdown → opens `status-dropdown-modal` as an overlay
- "Add Vehicle" button → opens `add-vehicle-modal` as an overlay
- Clicking table row 1 (Honda Civic) → opens `vehicle-detail-modal` as an overlay

---

## Screen 3: Forecast

Left sidebar: Sales Overview, Vehicle Inventory, **Forecast** (active).
Header: "Sales Forecast", "Download Report" action button.

**Layout (content area starts at x=264, y=96 — advance Y after each section):**

**y=96 → 3 summary cards (height 100px):**

| Card | Value | Note |
|------|-------|------|
| Q1 Target | $1.1M | On track |
| Q2 Target | $1.3M | At risk |
| Annual Target | $4.8M | 87% achieved |

Three cards across: x=264, 564, 864 — each width=276, height=100.

**y=220 → Line chart "12-Month Revenue Forecast" (height 220px):**
Use figma_create_chart with chart_type="line". Full width (x=264, width=1000).
Data: Jan=180, Feb=210, Mar=195, Apr=240, May=255, Jun=230, Jul=260, Aug=275, Sep=250, Oct=280, Nov=295, Dec=310.

**y=472 → Bar chart "Forecast vs Actual by Quarter" (height 220px):**
Use figma_create_chart with chart_type="bar" and series param for grouped bars.
x=264, width=1000. Two series:
  - Forecast (accent color): Q1=410, Q2=455, Q3=490, Q4=520
  - Actual (muted color):    Q1=398, Q2=430, Q3=0,   Q4=0

IMPORTANT: These two charts must NOT overlap. The bar chart y=472 is BELOW the line chart (y=220 + height=220 + 32px gap = 472).

**What opens what:**
- "Download Report" button → opens `download-modal` as an overlay

---

## Modals

### export-modal — 480×240
Title "Export Report". Button "Export as CSV" (primary). Button "Export as PDF" (secondary). Cancel link.

### model-detail-modal — 480×400
Title "Model X Pro". Stats: Units Sold 412, Revenue $936K, Margin 22%, Status "In Stock" badge. Stock History section with 3 data rows. Close button.

### search-results-modal — 600×450
Title "Search Results". 4 vehicle result rows each showing VIN, Make, Model, Status. Close button.

### make-dropdown-modal — 160×220
Six selectable options: All, Toyota, Ford, BMW, Mercedes, Honda.

### status-dropdown-modal — 160×180
Four selectable options: All, In Stock, Reserved, Sold.

### add-vehicle-modal — 540×400
Title "Add Vehicle". Input fields: VIN, Make, Model, Year, Color, Status. Save button (primary). Cancel button.

### vehicle-detail-modal — 480×520
Title "Honda Civic". VIN, all vehicle fields, Days on Lot: 12. History notes section. Close button.

### download-modal — 480×200
Title "Downloading Report". Body text "forecast_report.pdf is being prepared…". OK button.

---

## Prototype start
Set **Sales Overview** as the prototype start screen.
