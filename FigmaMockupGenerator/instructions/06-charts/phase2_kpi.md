# Charts & Maps Test — Phase 2: KPI Summary

**UI Mode:**
- 🟡 **Rebuild Wireframe** — if a stub screen with this name already exists on the canvas
- 🟢 **Add Screens** — if adding to an existing canvas without stubs (places new frames to the right)
**Canvas:** 1440×900 desktop

> **Prerequisite:** Run Phase 1 (`06_charts_phase1_charts_map.md`) first. Charts Overview and Map View screens must already exist on the canvas.

Add the KPI Summary screen to complete the dashboard. Then run `figma_wire_all` to connect all sidebar navigation across all three screens.

---

## Screen: KPI Summary

### Layout
- Same sidebar (240px), active: **KPI Summary**
- Page heading: "KPI Summary"

### Content (top → bottom)

**KPI metric row** — 4 cards across the top:
| Metric | Value | Change |
|--------|-------|--------|
| Revenue | $4.8M | +12% |
| Active Users | 12,340 | +8% |
| Conversion Rate | 3.4% | -0.2% |
| Avg Order Value | $142 | +5% |

**Pie and donut charts side by side:**
- Left: pie chart titled "Revenue by Region" — Americas 42%, EMEA 31%, APAC 19%, Other 8% — show legend
- Right: donut chart titled "Traffic Sources" — Organic 38%, Paid 27%, Direct 20%, Referral 15% — show legend

**Two gauge charts side by side:**
- Left: gauge titled "System Health" — value 87 out of 100 — green
- Right: gauge titled "Budget Utilisation" — value 64 out of 100 — amber

**Data table** — 4 rows, columns: Region, Q4 Revenue, YoY Growth:
| Region | Q4 Revenue | YoY Growth |
|--------|-----------|------------|
| Americas | $2.0M | +14% |
| EMEA | $1.5M | +9% |
| APAC | $0.9M | +18% |
| Other | $0.4M | +3% |

---

## Wiring

After building the KPI Summary screen, call `figma_wire_all` to connect all sidebar navigation links between Charts Overview, Map View, and KPI Summary in all directions.
