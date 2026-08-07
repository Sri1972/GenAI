# Figma Mockup Generator — Instruction Files

Paste the full contents of any file below into the **"From Prompt"** input on the Figma Mockup Generator page to generate a fully interactive Figma prototype.

---

## How to use — two approaches

### Option A: Full build (one file, all screens at once) — recommended
Use the `_fullbuild` files (or `01_automotive_dashboard.md`). Paste the entire file into the prompt, select 🟢 **New Wireframe**, and get everything built in a single run. Best for most use cases.

### Option B: Incremental phases (build one screen at a time)
Use the `_phase` files. Each phase builds 1–2 screens and is run separately. Useful when the full build is too large, or when you want to review each screen before adding the next.

| UI Button | When to use |
|-----------|-------------|
| 🟢 **New Wireframe** | Start fresh — warns if existing frames found, clears canvas, builds all screens. Tracks expected screens and resumes if build stops early. |
| 🟢 **Edit Wireframe** | Edit existing screens (surgical changes) OR add new screens alongside them. Nothing is deleted. |
| 🟡 **Replace Wireframe** | Pre-delete screens with matching names and rebuild them from scratch. Other screens are untouched. |

---

## Full-build instruction files (recommended starting point)

Each file builds the complete app — all screens + all modals — in a single run. Use 🟢 **New Wireframe** on a blank Figma canvas.

| File | App | Screens | Modals | Theme |
|------|-----|---------|--------|-------|
| [01_automotive_dashboard.md](01_automotive_dashboard.md) | Automotive Analytics | 3 | 8 | Dark navy/indigo |
| [02_saas_fullbuild.md](02_saas_fullbuild.md) | SaaS Project Management | 4 | 11 | Light white/sky blue |
| [03_sports_fullbuild.md](03_sports_fullbuild.md) | Sports Analytics | 3 | 7 | Dark stadium/amber |
| [04_wiring_test_fullbuild.md](04_wiring_test_fullbuild.md) | Wiring Smoke Test | 2 | 5 | Light minimal |

> **Tip:** Start with `04_wiring_test_fullbuild.md` to verify that navigation, overlays, and close buttons all work before running a larger build.

---

### 01 — Automotive Dashboard (dark, 3 screens)
| Phase | File | Builds |
|-------|------|--------|
| 1 | [01_automotive_phase1_sales.md](01_automotive_phase1_sales.md) | Sales Overview screen + 2 overlays |
| 2 | [01_automotive_phase2_inventory.md](01_automotive_phase2_inventory.md) | Vehicle Inventory screen + 5 overlays |
| 3 | [01_automotive_phase3_forecast.md](01_automotive_phase3_forecast.md) | Forecast screen + 1 overlay + full wiring |

### 02 — SaaS Project Management (light, 4 screens)
| Phase | File | Builds |
|-------|------|--------|
| 1 | [02_saas_phase1_dashboard.md](02_saas_phase1_dashboard.md) | My Dashboard screen + 3 overlays |
| 2 | [02_saas_phase2_projects.md](02_saas_phase2_projects.md) | Projects screen + 5 overlays |
| 3 | [02_saas_phase3_team_reports.md](02_saas_phase3_team_reports.md) | Team + Reports screens + 3 overlays + full wiring |

### 03 — Sports Analytics (dark, 3 screens)
| Phase | File | Builds |
|-------|------|--------|
| 1 | [03_sports_phase1_overview_stats.md](03_sports_phase1_overview_stats.md) | Team Overview + Player Stats screens + 5 overlays |
| 2 | [03_sports_phase2_match.md](03_sports_phase2_match.md) | Match Analysis screen + 2 overlays + full wiring |

### 04 — Wiring Smoke Test (light, 2 screens)
| Phase | File | Builds |
|-------|------|--------|
| 1 | [04_wiretest_phase1_home.md](04_wiretest_phase1_home.md) | Home screen + 3 overlays |
| 2 | [04_wiretest_phase2_catalog.md](04_wiretest_phase2_catalog.md) | Catalog screen + 3 overlays + full wiring |

### 05 — Fleet Management / MobilityHub (corporate light, 4 screens)
| Phase | File | Builds |
|-------|------|--------|
| 1 | [05_fleet_phase1_command.md](05_fleet_phase1_command.md) | Fleet Command Center screen + 4 overlays |
| 2 | [05_fleet_phase2_map_inventory.md](05_fleet_phase2_map_inventory.md) | Live Map + Fleet Inventory screens + 9 overlays |
| 3 | [05_fleet_phase3_drivers.md](05_fleet_phase3_drivers.md) | Driver Roster screen + 5 overlays + full wiring |

### 06 — Charts & Maps Test (dark, 3 screens)
| Phase | File | Builds |
|-------|------|--------|
| 1 | [06_charts_phase1_charts_map.md](06_charts_phase1_charts_map.md) | Charts Overview + Map View screens |
| 2 | [06_charts_phase2_kpi.md](06_charts_phase2_kpi.md) | KPI Summary screen + full wiring |

---

## Single-shot (full-build) files

These monolithic files build entire prototypes in one run. Use them when you want everything at once.

| File | Description | Screens | Complexity |
|------|-------------|---------|------------|
| [01_automotive_dashboard.md](01_automotive_dashboard.md) | Dark automotive analytics — charts, tables, dropdowns, modals | 3 | Medium |
| [02_saas_project_management.md](02_saas_project_management.md) | Light SaaS — tasks, projects, team, reports | 4 | High |
| [03_sports_analytics.md](03_sports_analytics.md) | Dark sports analytics — team, players, match analysis | 3 | Medium |
| [04_simple_2screen_wiring_test.md](04_simple_2screen_wiring_test.md) | Minimal wiring smoke test | 2 | Low |
| [05_mobility_global_brand.md](05_mobility_global_brand.md) | Corporate fleet management — map, inventory, drivers | 4 | High |
| [06_charts_and_maps_test.md](06_charts_and_maps_test.md) | All chart types + real map tiles | 3 | Medium |

---

## What each phase file contains

Every phase file is structured as:

1. **Mode** — `new` (Phase 1) or `edit` (Phase 2+)
2. **Prerequisite** — which earlier phases must be complete (Phase 2+ only)
3. **Screens to build** — layout, content sections, sample data
4. **Overlays to create** — modal/overlay frame names and sizes for this phase only
5. **Wiring** — source → interaction → destination for this phase's screens
6. **Prototype start** — set in Phase 1, or confirmed in the final phase

---

## Node naming conventions

| Pattern | Example | Used for |
|---------|---------|---------|
| `tab-{Target}-on-{Screen}` | `tab-Overview-on-Home` | Tab bar navigation |
| `search-btn-{Screen}` | `search-btn-FleetInventory` | Search bar trigger |
| `dropdown-{Label}-on-{Screen}` | `dropdown-Status-on-Projects` | Filter dropdown trigger |
| `notification-bell-btn-{Screen}` | `notification-bell-btn-Dashboard` | Notification panel |

---

## Tips

- **Start with `04_wiretest_phase1_home.md`** → `04_wiretest_phase2_catalog.md` to verify all wiring types work before running a complex multi-phase build.
- The final phase of every set calls `figma_wire_all` — this automatically connects all sidebar nav links across every screen added across all phases.
- Bar charts are drawn with rectangles and work reliably. Line/area/pie charts use `figma_create_chart`.
- Maps use `figma_create_map` which fetches real OpenStreetMap tiles.

