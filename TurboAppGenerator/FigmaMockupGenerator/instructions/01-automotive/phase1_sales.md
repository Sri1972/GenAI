# Automotive Analytics — Phase 1: Sales Overview

**UI Mode:** 🟢 **Build Wireframe**

Build the first screen of a dark automotive analytics application at 1440×900. Also create two empty placeholder screens so that sidebar navigation works from day one.

> Do NOT apply Mobility Global branding. Use the custom dark color scheme specified below.

**Colors:** Background `#0f172a` · Sidebar `#1e293b` · Cards `#1e293b` · Accent `#6366f1` · Text `#f1f5f9`

---

## Screen 1: Sales Overview (fully built)

Left sidebar (240px) with navigation: **Sales Overview** (active), Vehicle Inventory, Forecast.
Header bar: title "Sales Overview", "Export Report" action button (top right).

**4 KPI cards across the top:**

| Metric | Value | Trend |
|--------|-------|-------|
| Total Revenue | $4.2M | +8% vs last month |
| Units Sold | 1,847 | +12% YTD |
| Avg Deal Size | $2,274 | -2% vs last month |
| YTD Growth | +12% | On target |

**Bar chart** "Monthly Revenue by Region" — 6 bars: North 180px, South 140px, East 160px, West 120px, Central 100px, International 90px (max 200px).

**Data table** "Top 5 Models":

| Model | Units Sold | Revenue | Margin % | Status |
|-------|-----------|---------|----------|--------|
| Model X Pro | 412 | $936K | 22% | In Stock |
| Sedan Elite | 389 | $701K | 18% | Low Stock |
| SUV Titan | 301 | $842K | 24% | In Stock |
| City Compact | 288 | $374K | 15% | In Stock |
| Pickup Max | 275 | $660K | 21% | Critical |

**What opens what:**
- "Export Report" button → opens the export modal as an overlay
- Clicking table row 1 (Model X Pro) → opens the model detail modal as an overlay

---

## Screen 2: Vehicle Inventory (placeholder only)

Same sidebar navigation with Vehicle Inventory marked active. Content area shows a centred message: "Vehicle Inventory — Content coming in Phase 2". No other content needed.

---

## Screen 3: Forecast (placeholder only)

Same sidebar navigation with Forecast marked active. Content area shows a centred message: "Forecast — Content coming in Phase 3". No other content needed.

---

## Modals

### Export modal — 480×240
Title "Export Report". "Export as CSV" button (primary). "Export as PDF" button (secondary). Cancel link.

### Model detail modal — 480×400
Title "Model X Pro". Stats: Units Sold 412, Revenue $936K, Margin 22%, Status "In Stock" badge. Stock History section with 3 data rows. Close button.

---

## Prototype start
Set **Sales Overview** as the prototype start screen.


