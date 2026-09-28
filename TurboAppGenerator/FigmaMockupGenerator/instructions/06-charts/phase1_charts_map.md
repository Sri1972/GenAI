# Charts & Maps Test — Phase 1: Charts Overview & Map View

**UI Mode:** 🟢 **Build Wireframe**
**Canvas:** 1440×900 desktop

> ⚠️ **STRICT PHASE SCOPE — build ONLY these 2 frames, nothing else:**
> - Screen: `Charts Overview`
> - Screen: `Map View`
>
> Do NOT create the KPI Summary screen. The sidebar nav item for KPI Summary is a **visual placeholder only** — leave it unwired. The QA pass must NOT flag that as an error or attempt to build the KPI Summary screen.

Build the first two screens of a 3-screen dashboard testing all chart and map types.

**Theme:** Dark navy — bg `#0f172a`, sidebar `#1e293b`, cards `#1e293b`, accent `#6366f1`, text `#f1f5f9`, muted `#94a3b8`.

---

## Screen 1: Charts Overview

### Layout
- Left sidebar (240px), nav items: **Charts Overview** (active), Map View, KPI Summary
- Page heading: "Charts Overview"

### Content — two columns side by side throughout

**Row 1 — two bar charts:**
- Left: vertical bar chart titled "Monthly Revenue" — 6 months Jan–Jun, values 120, 95, 145, 110, 160, 130 — indigo bars `#6366f1`
- Right: horizontal bar chart titled "Top Products by Sales" — 5 products (Product A–E), values 340, 280, 210, 175, 140 — teal bars `#14b8a6`, category labels on left

**Row 2 — line and area charts:**
- Left: line chart titled "Weekly Active Users" — 7 days Mon–Sun, values 820, 940, 880, 1020, 1150, 760, 620 — green line `#22c55e` with dots
- Right: area chart titled "Cumulative Revenue" — 4 quarters Q1–Q4, values 1200, 2100, 3400, 4800 — amber fill `#f59e0b`

**Row 3 — scatter chart and KPI sparkline cards:**
- Left: scatter chart titled "Risk vs Return" — 6 funds (Fund A–F), values 72, 58, 85, 43, 91, 66 — red dots `#ef4444`
- Right: 3 KPI cards side by side, each with a metric + sparkline: "Revenue $4.8M" (upward), "Users 12,340" (upward), "Churn 2.1%" (downward, amber)

---

## Screen 2: Map View

### Layout
- Same sidebar, active: **Map View**
- Page heading: "Map View"

### Content

**Full-width world map** — label above "Global Overview". Shows the entire world at wide zoom using real OpenStreetMap tiles.

**Two regional maps side by side** — both using real map tiles:
- Left: centred on New York City (lat 40.7128, lon -74.0060, zoom 11) — label "New York Region"
- Right: centred on London (lat 51.5074, lon -0.1278, zoom 11) — label "London Region"

---

## Wiring

| Source element | Interaction | Destination |
|----------------|-------------|-------------|
| Sidebar "Map View" on Charts Overview | Navigate | Map View screen |
| Sidebar "Charts Overview" on Map View | Navigate | Charts Overview screen |

---

## Prototype start
Set **Charts Overview** as the prototype start frame.
