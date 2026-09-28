# Automotive Analytics — Phase 3: Forecast

**UI Mode:** 🟡 **Rebuild Wireframe**

Replace the Forecast screen placeholder with full content. The Forecast frame exists on the canvas as a stub — delete it and rebuild it completely.

---

## Screen: Forecast

Delete the existing `Forecast` frame using `figma_delete_frame`, then create a new `Forecast` frame (1440×900) with:

Left sidebar (240px): Sales Overview, Vehicle Inventory, **Forecast** (active).
Header: "Sales Forecast", "Download Report" action button.

**3 summary cards:**

| Card | Value | Note |
|------|-------|------|
| Q1 Target | $1.1M | On track |
| Q2 Target | $1.3M | At risk |
| Annual Target | $4.8M | 87% achieved |

**Line chart placeholder** — full-width rectangle, height 200px, centred label "12-Month Revenue Forecast".

**Bar chart** "Forecast vs Actual by Quarter" — 4 pairs of side-by-side bars (Forecast in accent color, Actual in muted):
Q1: 180/172px · Q2: 200/160px · Q3: 190/0px · Q4: 210/0px

---

## Modal to build

Download confirmation modal (480×200): Title "Downloading Report", body "forecast_report.pdf is being prepared…", OK button.

---

## What opens what

"Download Report" button opens the download confirmation modal as an overlay.

---

## Prototype start
Set **Sales Overview** as the prototype start screen.



```

Then set the prototype start frame:
```
figma_wire_all(links=[], start_frame="Sales Overview")
```

---

## Prototype start
Handled by `start_frame="Sales Overview"` in the `figma_wire_all` call above.
