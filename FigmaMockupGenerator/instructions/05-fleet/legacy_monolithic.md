Create a 4-screen global mobility & fleet management platform at 1440×900. This app tracks vehicle fleets across multiple regions for a global enterprise.

**Theme:** Corporate light — bg `#f0f4f8`, sidebar `#0f2744`, cards `#ffffff`, accent `#1d6fa4`, accent-2 `#e8732a`, text `#1a2b42`, muted `#6b7a8d`, success `#10b981`, warning `#f59e0b`, danger `#ef4444`.

---

## Screen 1 — Fleet Command Center

### Layout
- Left sidebar (260px), dark bg `#0f2744`: logo area (white wordmark "MobilityHub"), nav groups:
  - **Overview**: Fleet Command Center, Live Map
  - **Management**: Fleet Inventory, Driver Roster
  - Divider, then "Settings" + "Help" at bottom
- Top bar (white, 56px): breadcrumb "Fleet Command Center", region picker dropdown "Region: Global" — name `dropdown-Region-on-FleetCommand` — options: Global, North America, EMEA, APAC, LATAM
- Right of header: alert bell `notification-bell-btn-FleetCommand`, avatar "JD"

### Content sections (top → bottom)

**Global KPI row** — 5 cards:
| Card | Value | Delta | Status |
|------|-------|-------|--------|
| Active Vehicles | 3,412 | +24 today | Green |
| Idle Vehicles | 287 | -12 today | Yellow |
| In Maintenance | 143 | 4.2% of fleet | Orange |
| Drivers On Duty | 2,891 | 84.7% utilisation | Green |
| Alerts | 18 | 3 critical | Red |

**Bar chart** (drawn with rectangles, 5 bars) — title "Fleet Utilisation by Region (%)":
- Regions: North America, EMEA, APAC, LATAM, Global Avg
- Values: 88, 82, 76, 71, 84 (draw bars proportional; max bar height 160px)
- Color-code bars: accent `#1d6fa4` for regions, accent-2 `#e8732a` for Global Avg
- Y-axis: 0–100%, x-axis labels below bars

**Two-column row**:

Left — **Alert list** "Active Alerts (18)" — 5 rows:
| Severity | Alert | Vehicle | Region | Time |
|----------|-------|---------|--------|------|
| CRITICAL | Engine warning light | VH-3821 | EMEA | 2 min ago |
| CRITICAL | Fuel critically low | VH-0047 | APAC | 5 min ago |
| CRITICAL | Geofence breach | VH-2210 | LATAM | 8 min ago |
| HIGH | Scheduled maintenance overdue | VH-1100 | NA | 1h ago |
| HIGH | Driver fatigue alert | VH-0892 | EMEA | 1.5h ago |

Right — **Status ring summary** (use colored rectangles as a legend instead):
- 4 rectangles in a 2×2 grid with labels:
  - Active (green, 3412), Idle (yellow, 287), Maintenance (orange, 143), Offline (grey, 89)

### Wiring
| Source element | Interaction | Destination |
|----------------|-------------|-------------|
| Sidebar: "Live Map" | Navigate | Live Map screen |
| Sidebar: "Fleet Inventory" | Navigate | Fleet Inventory screen |
| Sidebar: "Driver Roster" | Navigate | Driver Roster screen |
| `dropdown-Region-on-FleetCommand` | Overlay | Region picker modal (200×240) — 5 option rows: Global, North America, EMEA, APAC, LATAM |
| `notification-bell-btn-FleetCommand` | Overlay | Alerts modal (360×480) — 8 alert rows with severity badge + description + vehicle ID + time, "Acknowledge All" button, Close button |
| Alert row 1 (Engine warning — VH-3821) | Overlay | Alert Detail modal (520×400) — alert type, vehicle ID, region, timestamp, recommended action text, "Dispatch Technician" button, Close button |
| Bar chart bar 1 (North America) | Overlay | Region Drill-down modal (580×440) — region name, total vehicles, utilisation bar chart (3 smaller bars for sub-regions), top 3 alerts list, Close button |

---

## Screen 2 — Live Map

### Layout
- Same sidebar, active: Live Map
- Header: "Live Map — Vehicle Tracking", controls row: `dropdown-Region-on-LiveMap` (same 5 options), `dropdown-VehicleType-on-LiveMap` (options: All, Car, Van, Truck, Bus)
- "Refresh" button (ghost) + timestamp "Last updated: 10:42:31"

### Content sections

**Map area** (full content width, 500px tall):
- Rectangle (full width, 500px), fill `#dce8f5`, border `#9ab8d4`
- Centered label: "Live Map — Vehicle Tracking (3,412 vehicles)"
- Sub-label: "Map placeholder: integration with mapping provider required"
- 6 small colored circle markers scattered in the rectangle (simulate vehicles):
  - 3 green (active), 1 yellow (idle), 1 orange (maintenance), 1 red (alert)
  - Place them at varied positions across the rectangle

**Vehicle status summary bar** (below map, horizontal):
- 4 inline stat pills: Active 3,412 | Idle 287 | Maintenance 143 | Alerts 18

### Wiring
| Source element | Interaction | Destination |
|----------------|-------------|-------------|
| Sidebar: "Fleet Command Center" | Navigate | Fleet Command Center screen |
| Sidebar: "Fleet Inventory" | Navigate | Fleet Inventory screen |
| Sidebar: "Driver Roster" | Navigate | Driver Roster screen |
| `dropdown-Region-on-LiveMap` | Overlay | Region picker modal (200×240) — same 5 options |
| `dropdown-VehicleType-on-LiveMap` | Overlay | Vehicle type modal (180×220) — All, Car, Van, Truck, Bus |
| Map vehicle marker 1 (green, active) | Overlay | Vehicle popup modal (340×280) — Vehicle ID: VH-1042, driver name, type, speed, location text, status badge, "View Full Details" button, Close button |
| Map vehicle marker 6 (red, alert) | Overlay | Vehicle popup modal (340×280) — Vehicle ID: VH-3821, alert badge, engine warning message, location text, "Dispatch" button, Close button |

---

## Screen 3 — Fleet Inventory

### Layout
- Same sidebar, active: Fleet Inventory
- Header: "Fleet Inventory", buttons: "Add Vehicle" (primary) + "Bulk Import" (ghost)

### Content sections

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

### Wiring
| Source element | Interaction | Destination |
|----------------|-------------|-------------|
| Sidebar: "Fleet Command Center" | Navigate | Fleet Command Center screen |
| Sidebar: "Live Map" | Navigate | Live Map screen |
| Sidebar: "Driver Roster" | Navigate | Driver Roster screen |
| `search-btn-FleetInventory` | Overlay | Vehicle search modal (620×420) — 4 matching vehicle rows (ID, type, make, status, driver), Close button |
| `dropdown-Region-on-FleetInventory` | Overlay | Region filter modal (200×220) — 5 options |
| `dropdown-Type-on-FleetInventory` | Overlay | Type filter modal (180×220) — 5 options |
| `dropdown-Status-on-FleetInventory` | Overlay | Status filter modal (180×200) — 5 options |
| "Add Vehicle" button | Overlay | Add Vehicle modal (580×500) — Vehicle ID (auto), Type dropdown, Make, Model, Region, Assign Driver, Initial mileage; Save + Cancel buttons |
| Table row 1 (VH-0001) | Overlay | Vehicle Detail modal (600×560) — full details, service history (3 rows), assigned driver card, location history (3 rows), Close button |
| Table row 2 (VH-0047 — Alert) | Overlay | Vehicle Alert Detail modal (520×400) — alert details, recommended action, "Dispatch Technician" + Close buttons |

---

## Screen 4 — Driver Roster

### Layout
- Same sidebar, active: Driver Roster
- Header: "Driver Roster", "Add Driver" button (primary)

### Content sections

**Summary cards** — 3 cards:
| Card | Value | Note |
|------|-------|------|
| Total Drivers | 2,891 | Across 5 regions |
| On Duty Now | 2,604 | 90.1% active |
| Fatigue Alerts | 3 | Immediate action |

**Filter bar**:
- Search: `search-btn-DriverRoster` (placeholder "Search driver name or ID…")
- `dropdown-DriverRegion-on-DriverRoster` — options: All Regions, North America, EMEA, APAC, LATAM

**Driver table** — 8 rows:
| Driver ID | Name | Region | Vehicle | Hours This Week | Status | Score |
|-----------|------|--------|---------|-----------------|--------|-------|
| DR-001 | James Mitchell | North America | VH-0001 | 38h | On Duty | 94 |
| DR-002 | Lisa Kim | APAC | VH-0047 | 44h | On Duty | 87 |
| DR-003 | Axel Becker | EMEA | VH-0892 | 41h | On Duty | 91 |
| DR-004 | Phuong Nguyen | North America | VH-1100 | 22h | Off Duty | 89 |
| DR-005 | Carlos Santos | LATAM | VH-2210 | 50h | Fatigue Alert | 72 |
| DR-006 | Thomas Müller | EMEA | VH-3821 | 47h | On Duty | 78 |
| DR-007 | Hyun Park | APAC | VH-4100 | 18h | Off Duty | 95 |
| DR-008 | Maria Lopez | North America | VH-5500 | 39h | On Duty | 90 |

### Wiring
| Source element | Interaction | Destination |
|----------------|-------------|-------------|
| Sidebar: "Fleet Command Center" | Navigate | Fleet Command Center screen |
| Sidebar: "Live Map" | Navigate | Live Map screen |
| Sidebar: "Fleet Inventory" | Navigate | Fleet Inventory screen |
| `search-btn-DriverRoster` | Overlay | Driver search modal (580×380) — 4 driver result rows (ID, name, region, status), Close button |
| `dropdown-DriverRegion-on-DriverRoster` | Overlay | Driver region filter modal (200×220) — 5 options |
| "Add Driver" button | Overlay | Add Driver modal (560×460) — Driver ID (auto), Name, Region, Assign Vehicle dropdown, License number, Contact; Save + Cancel |
| Table row 1 (DR-001 James Mitchell) | Overlay | Driver Profile modal (560×540) — photo placeholder, name, ID, region, current vehicle, hours this week (bar chart 5 bars: Mon-Fri), driving score with color, recent trips list (3 rows), Close button |
| Table row 5 (DR-005 Carlos Santos — Fatigue Alert) | Overlay | Fatigue Alert modal (480×360) — driver name, hours on duty (50h), alert reason, recommended rest period, "Pull Off Route" + "Notify Manager" + Close buttons |

---

## Overlay frames to create

| Frame name | Size | Purpose |
|------------|------|---------|
| `region-picker-modal` | 200×240 | Region selector (shared) |
| `alerts-modal` | 360×480 | Alert list panel |
| `alert-detail-modal` | 520×400 | Single alert detail |
| `region-drilldown-modal` | 580×440 | Region fleet detail |
| `vehicle-type-modal` | 180×220 | Vehicle type filter |
| `vehicle-popup-modal` | 340×280 | Map vehicle info popup |
| `vehicle-search-modal` | 620×420 | Inventory search results |
| `region-filter-modal` | 200×220 | Inventory region filter |
| `type-filter-modal` | 180×220 | Inventory type filter |
| `status-filter-modal` | 180×200 | Inventory status filter |
| `add-vehicle-modal` | 580×500 | Add vehicle form |
| `vehicle-detail-modal` | 600×560 | Full vehicle details |
| `vehicle-alert-modal` | 520×400 | Vehicle alert detail |
| `driver-search-modal` | 580×380 | Driver search results |
| `driver-region-modal` | 200×220 | Driver region filter |
| `add-driver-modal` | 560×460 | Add driver form |
| `driver-profile-modal` | 560×540 | Driver full profile |
| `fatigue-alert-modal` | 480×360 | Fatigue alert action |

---

## Prototype start screen
Set **Fleet Command Center** as the prototype start frame.
