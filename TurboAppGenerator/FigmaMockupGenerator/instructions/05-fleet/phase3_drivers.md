# Fleet Management — Phase 3: Driver Roster

**UI Mode:**
- 🟡 **Rebuild Wireframe** — if a stub screen with this name already exists on the canvas
- 🟢 **Add Screens** — if adding to an existing canvas without stubs (places new frames to the right)
**Canvas:** 1440×900 desktop

> **Prerequisite:** Run Phase 1 and Phase 2 first. Fleet Command Center, Live Map, and Fleet Inventory must already exist on the canvas.

Add the Driver Roster screen to complete the platform. Then run `figma_wire_all` to connect all sidebar navigation across all four screens.

---

## Screen: Driver Roster

### Layout
- Same sidebar (260px), active: **Driver Roster**
- Header: "Driver Roster", "Add Driver" button (primary, top right)

### Content sections (top → bottom)

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

---

## Overlays to create

| Frame name | Size | Content |
|------------|------|---------|
| `driver-search-modal` | 580×380 | Title "Driver Search", 4 driver result rows (ID, name, region, status), Close button |
| `driver-region-modal` | 200×220 | 5 option rows: All Regions, North America, EMEA, APAC, LATAM |
| `add-driver-modal` | 560×460 | Title "Add Driver", fields: Driver ID (auto), Name, Region, Assign Vehicle dropdown, License number, Contact; Save + Cancel buttons |
| `driver-profile-modal` | 560×540 | Title "James Mitchell", photo placeholder (circle, 64px), ID + region + current vehicle, Hours This Week bar chart (5 bars Mon–Fri), driving score 94 (green), Recent Trips (3 rows), Close button |
| `fatigue-alert-modal` | 480×360 | Title "Fatigue Alert — Carlos Santos", hours on duty 50h, alert reason, recommended rest period, "Pull Off Route" + "Notify Manager" + Close buttons |

---

## Wiring

| Source element | Interaction | Destination |
|----------------|-------------|-------------|
| `search-btn-DriverRoster` | Overlay | `driver-search-modal` |
| `dropdown-DriverRegion-on-DriverRoster` | Overlay | `driver-region-modal` |
| "Add Driver" button | Overlay | `add-driver-modal` |
| Table row 1 (DR-001 James Mitchell) | Overlay | `driver-profile-modal` |
| Table row 5 (DR-005 Carlos Santos — Fatigue Alert) | Overlay | `fatigue-alert-modal` |

After building the screen and all overlays, call `figma_wire_all` to connect all sidebar navigation links across Fleet Command Center, Live Map, Fleet Inventory, and Driver Roster.
