Create a 3-screen analytics dashboard to test all chart types and map rendering.

**Theme:** Dark — dark navy background, card panels slightly lighter, indigo accent, light text.
**Canvas size:** 1440×900 per screen.
**Sidebar navigation:** 240px wide, same on all screens.

---

## Screen 1 — Charts Overview

Sidebar nav items: Charts Overview (active), Map View, KPI Summary.
Page heading: "Charts Overview".

### Content (two columns side by side throughout)

**Row 1 — two bar charts**
- Left: vertical bar chart titled "Monthly Revenue" — 6 months Jan–Jun, values roughly 120, 95, 145, 110, 160, 130. Indigo bars.
- Right: horizontal bar chart titled "Top Products by Sales" — 5 products (Product A–E), values 340, 280, 210, 175, 140. Teal bars, category labels on the left.

**Row 2 — line and area charts**
- Left: line chart titled "Weekly Active Users" — 7 days Mon–Sun, values 820, 940, 880, 1020, 1150, 760, 620. Green line with dots.
- Right: area chart titled "Cumulative Revenue" — 4 quarters Q1–Q4, values 1200, 2100, 3400, 4800. Amber fill.

**Row 3 — scatter chart and three KPI sparkline cards**
- Left: scatter chart titled "Risk vs Return" — 6 funds (Fund A–F), values 72, 58, 85, 43, 91, 66. Red dots.
- Right: three small KPI cards side by side, each with a metric and a small sparkline graph underneath:
  - "Revenue" — $4.8M — sparkline trending upward
  - "Users" — 12,340 — sparkline trending upward
  - "Churn" — 2.1% — sparkline trending downward (amber)

---

## Screen 2 — Map View

Sidebar nav items: Charts Overview, Map View (active), KPI Summary.
Page heading: "Map View".

### Content

**Full-width world map** at the top — shows the entire world, wide zoom. Label above: "Global Overview".

**Two regional maps side by side** below:
- Left: map centred on New York City. Label above: "New York Region".
- Right: map centred on London. Label above: "London Region".

All three maps should show real street-level map tiles, not placeholder rectangles.

---

## Screen 3 — KPI Summary

Sidebar nav items: Charts Overview, Map View, KPI Summary (active).
Page heading: "KPI Summary".

### Content

**KPI metric row** — 4 cards across the top:
- Revenue: $4.8M (+12%)
- Active Users: 12,340 (+8%)
- Conversion Rate: 3.4% (−0.2%)
- Avg Order Value: $142 (+5%)

**Pie and donut charts side by side:**
- Left: pie chart titled "Revenue by Region" — Americas 42%, EMEA 31%, APAC 19%, Other 8%. Show legend.
- Right: donut chart titled "Traffic Sources" — Organic 38%, Paid 27%, Direct 20%, Referral 15%. Show legend.

**Two gauge charts side by side:**
- Left: gauge titled "System Health" — value 87 out of 100. Green.
- Right: gauge titled "Budget Utilisation" — value 64 out of 100. Amber.

**Data table** at the bottom — 4 rows, columns: Region, Q4 Revenue, YoY Growth.
Americas $2.0M +14% | EMEA $1.5M +9% | APAC $0.9M +18% | Other $0.4M +3%

---

## Navigation wiring

- Sidebar nav items on every screen navigate to their respective screens.
- Set **Charts Overview** as the prototype start screen.
