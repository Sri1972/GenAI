# Fleet Management — Phase 2: Live Map & Fleet Inventory

**UI Mode:**
- 🟡 **Rebuild Wireframe** — if a stub screen with this name already exists on the canvas
- 🟢 **Add Screens** — if adding to an existing canvas without stubs (places new frames to the right)
**Canvas:** 1440×900 desktop

> **Prerequisite:** Run Phase 1 (`05_fleet_phase1_command.md`) first. Fleet Command Center must already exist on the canvas.

> ⚠️ **STRICT PHASE SCOPE — build ONLY these 11 frames, nothing else:**
> - Screen: `Live Map`
> - Screen: `Fleet Inventory`
> - Overlay: `vehicle-type-modal`
> - Overlay: `vehicle-popup-modal`
> - Overlay: `vehicle-search-modal`
> - Overlay: `region-filter-modal`
> - Overlay: `type-filter-modal`
> - Overlay: `status-filter-modal`
> - Overlay: `add-vehicle-modal`
> - Overlay: `vehicle-detail-modal`
> - Overlay: `vehicle-alert-modal`
>
> Do NOT create Driver Roster or any other screen. Leave sidebar nav items for Driver Roster **unwired** — they will be connected in Phase 3. The QA pass must NOT flag that as an error.

Add the Live Map and Fleet Inventory screens.

---

## Screen: Live Map

### Layout
- Same sidebar (260px), active: **Live Map**
- Header: "Live Map — Vehicle Tracking"; controls row: `dropdown-Region-on-LiveMap` (same 5 options as Phase 1), `dropdown-VehicleType-on-LiveMap` (options: All, Car, Van, Truck, Bus); "Refresh" ghost button + timestamp "Last updated: 10:42:31"

### Content sections (top → bottom)

**Map area** (full content width, 500px):
- Rectangle (full width, 500px), fill `#dce8f5`, border `#9ab8d4`
- Centred label: "Live Map — Vehicle Tracking (3,412 vehicles)"
- Sub-label: "Map placeholder: integration with mapping provider required"
- 6 small colored circle markers scattered across the rectangle: 3 green (active), 1 yellow (idle), 1 orange (maintenance), 1 red (alert)

**Vehicle status bar** (below map, horizontal): 4 inline stat pills — Active 3,412 | Idle 287 | Maintenance 143 | Alerts 18

---

## Screen: Fleet Inventory

### Layout
- Same sidebar (260px), active: **Fleet Inventory**
- Header: "Fleet Inventory", "Add Vehicle" (primary) + "Bulk Import" (ghost) buttons

### Content sections (top → bottom)

**Filter bar**:
- Search: `search-btn-FleetInventory` (placeholder "Search by ID, make, driver…")
- `dropdown-Region-on-FleetInventory` — options: All Regions, North America, EMEA, APAC, LATAM
- `dropdown-Type-on-FleetInventory` — options: All Types, Car, Van, Truck, Bus
- `dropdown-Status-on-FleetInventory` — options: All Status, Active, Idle, Maintenance, Offline

**Data table** — 8 rows:
| Vehicle ID | Type | Make/Model | Region | Driver | Mileage | Status | Last Seen |
|-----------|------|------------|--------|--------|---------|--------|-----------|
| VH-0001 | Car | Toyota Camry | North America | J. Mitchell | 48,210 km | Active | 2 min ago |
| VH-0047 | Truck | Ford F-250 | APAC | L. Kim | 112,880 km | Alert | 5 min ago |
| VH-0892 | Van | Mercedes Sprinter | EMEA | A. Becker | 88,430 km | Active | 12 min ago |
| VH-1100 | Car | BMW 3 Series | North America | P. Nguyen | 34,770 km | Maintenance | 2h ago |
| VH-2210 | Truck | Volvo FH | LATAM | C. Santos | 201,550 km | Alert | 8 min ago |
| VH-3821 | Car | Renault Megane | EMEA | T. Müller | 61,220 km | Alert | 2 min ago |
| VH-4100 | Bus | Mercedes Citaro | APAC | H. Park | 310,000 km | Idle | 45 min ago |
| VH-5500 | Van | Ford Transit | North America | M. Lopez | 75,340 km | Active | 7 min ago |

---

## Overlays to create

| Frame name | Size | Content |
|------------|------|---------|
| `vehicle-type-modal` | 180×220 | 5 option rows: All, Car, Van, Truck, Bus |
| `vehicle-popup-modal` | 340×280 | Title "VH-1042", driver name, type, speed, location text, status badge, "View Full Details" button, Close button |
| `vehicle-search-modal` | 620×420 | Title "Vehicle Search", 4 matching vehicle rows (ID, type, make, status, driver), Close button |
| `region-filter-modal` | 200×220 | 5 option rows: All Regions, North America, EMEA, APAC, LATAM |
| `type-filter-modal` | 180×220 | 5 option rows: All Types, Car, Van, Truck, Bus |
| `status-filter-modal` | 180×200 | 5 option rows: All Status, Active, Idle, Maintenance, Offline |
| `add-vehicle-modal` | 580×500 | Title "Add Vehicle", fields: Vehicle ID (auto), Type dropdown, Make, Model, Region, Assign Driver, Initial Mileage; Save + Cancel buttons |
| `vehicle-detail-modal` | 600×560 | Title "VH-0001 — Toyota Camry", full details, service history (3 rows), assigned driver card, location history (3 rows), Close button |
| `vehicle-alert-modal` | 520×400 | Title "Alert — VH-0047", alert details, recommended action, "Dispatch Technician" + Close buttons |

---

## Wiring

**Live Map:**
| Source element | Interaction | Destination |
|----------------|-------------|-------------|
| `dropdown-Region-on-LiveMap` | Overlay | `region-picker-modal` (reuse from Phase 1) |
| `dropdown-VehicleType-on-LiveMap` | Overlay | `vehicle-type-modal` |
| Map marker 1 (green — active) | Overlay | `vehicle-popup-modal` |
| Map marker 6 (red — alert) | Overlay | `vehicle-popup-modal` |

**Fleet Inventory:**
| Source element | Interaction | Destination |
|----------------|-------------|-------------|
| `search-btn-FleetInventory` | Overlay | `vehicle-search-modal` |
| `dropdown-Region-on-FleetInventory` | Overlay | `region-filter-modal` |
| `dropdown-Type-on-FleetInventory` | Overlay | `type-filter-modal` |
| `dropdown-Status-on-FleetInventory` | Overlay | `status-filter-modal` |
| "Add Vehicle" button | Overlay | `add-vehicle-modal` |
| Table row 1 (VH-0001) | Overlay | `vehicle-detail-modal` |
| Table row 2 (VH-0047 — Alert) | Overlay | `vehicle-alert-modal` |
