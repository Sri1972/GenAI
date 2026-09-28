# Fleet Management — Phase 1: Fleet Command Center

**UI Mode:** 🟢 **Build Wireframe**
**Canvas:** 1440×900 desktop

> ⚠️ **STRICT PHASE SCOPE — build ONLY these 5 frames, nothing else:**
> - Screen: `Fleet Command Center`
> - Overlay: `region-picker-modal`
> - Overlay: `alerts-modal`
> - Overlay: `alert-detail-modal`
> - Overlay: `region-drilldown-modal`
>
> Do NOT create Live Map, Fleet Inventory, Driver Roster, or any other screen. Sidebar nav items for those screens are **visual placeholders only** — leave them unwired. The QA pass must NOT flag missing navigation targets as errors or attempt to build those screens.

Build the first screen of a corporate fleet management platform.

**Theme:** Corporate light — bg `#f0f4f8`, sidebar `#0f2744` (dark navy), cards `#ffffff`, accent `#1d6fa4`, accent-2 `#e8732a`, text `#1a2b42`, muted `#6b7a8d`, success `#10b981`, warning `#f59e0b`, danger `#ef4444`.

---

## Screen: Fleet Command Center

### Layout
- Left sidebar (260px), dark navy `#0f2744`: white wordmark "MobilityHub" at top; nav groups:
  - **Overview**: **Fleet Command Center** (active), Live Map
  - **Management**: Fleet Inventory, Driver Roster
  - Divider, then Settings + Help at bottom
- Top bar (white, 56px): breadcrumb "Fleet Command Center"; dropdown "Region: Global" — name `dropdown-Region-on-FleetCommand` — options: Global, North America, EMEA, APAC, LATAM; alert bell `notification-bell-btn-FleetCommand` (right); avatar "JD" (right)

### Content sections (top → bottom)

**Global KPI row** — 5 cards:
| Card | Value | Delta | Status |
|------|-------|-------|--------|
| Active Vehicles | 3,412 | +24 today | green badge |
| Idle Vehicles | 287 | -12 today | yellow badge |
| In Maintenance | 143 | 4.2% of fleet | orange badge |
| Drivers On Duty | 2,891 | 84.7% utilisation | green badge |
| Alerts | 18 | 3 critical | red badge |

**Bar chart** (drawn with rectangles, 5 bars) — title "Fleet Utilisation by Region (%)":
- Regions: North America, EMEA, APAC, LATAM, Global Avg
- Bar heights proportional to: 88, 82, 76, 71, 84 (max height 160px)
- North America–LATAM bars in accent `#1d6fa4`; Global Avg bar in accent-2 `#e8732a`
- Y-axis: 0–100%, labels below bars

**Two-column row**:
- Left — Alert list "Active Alerts (18)" — 5 rows:
  | Severity | Alert | Vehicle | Region | Time |
  |----------|-------|---------|--------|------|
  | CRITICAL | Engine warning light | VH-3821 | EMEA | 2 min ago |
  | CRITICAL | Fuel critically low | VH-0047 | APAC | 5 min ago |
  | CRITICAL | Geofence breach | VH-2210 | LATAM | 8 min ago |
  | HIGH | Maintenance overdue | VH-1100 | NA | 1h ago |
  | HIGH | Driver fatigue alert | VH-0892 | EMEA | 1.5h ago |
- Right — Status summary grid (2×2, using colored rectangles + labels): Active (green, 3412) · Idle (yellow, 287) · Maintenance (orange, 143) · Offline (grey, 89)

---

## Overlays to create

| Frame name | Size | Content |
|------------|------|---------|
| `region-picker-modal` | 200×240 | 5 option rows: Global, North America, EMEA, APAC, LATAM |
| `alerts-modal` | 360×480 | Title "Active Alerts (18)", 8 alert rows (severity badge, description, vehicle ID, time), "Acknowledge All" button, Close button |
| `alert-detail-modal` | 520×400 | Title "Engine Warning — VH-3821", alert type, vehicle ID, region, timestamp, recommended action text, "Dispatch Technician" + Close buttons |
| `region-drilldown-modal` | 580×440 | Title "North America Fleet", total vehicles, utilisation sub-bar chart (3 bars for sub-regions), top 3 alerts list, Close button |

---

## Wiring

After ALL five frames are built, call `figma_list_frame_nodes(frame_name="Fleet Command Center")` to confirm node names, then wire in a single call:

```
figma_wire_all(
  links=[
    {"source_frame": "Fleet Command Center", "source_node": "dropdown-Region-on-FleetCommand",      "target_frame": "region-picker-modal",   "type": "OVERLAY"},
    {"source_frame": "Fleet Command Center", "source_node": "notification-bell-btn-FleetCommand",  "target_frame": "alerts-modal",          "type": "OVERLAY"},
    {"source_frame": "Fleet Command Center", "source_node": "row1-btn-FleetCommand",               "target_frame": "alert-detail-modal",    "type": "OVERLAY"},
    {"source_frame": "Fleet Command Center", "source_node": "bar1-btn-FleetCommand",               "target_frame": "region-drilldown-modal", "type": "OVERLAY"},
  ],
  start_frame="Fleet Command Center"
)
```

**Do NOT** wire sidebar items for Live Map, Fleet Inventory, or Driver Roster — those screens don't exist yet.

---

## Prototype start
Handled by `start_frame="Fleet Command Center"` in the `figma_wire_all` call above.
