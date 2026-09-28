# SaaS Project Management — Phase 2: Projects

**UI Mode:**
- 🟡 **Rebuild Wireframe** — if a stub screen with this name already exists on the canvas
- 🟢 **Add Screens** — if adding to an existing canvas without stubs (places new frames to the right)
**Canvas:** 1440×900 desktop

> **Prerequisite:** Run Phase 1 (`02_saas_phase1_dashboard.md`) first. My Dashboard must already exist on the canvas.

> ⚠️ **STRICT PHASE SCOPE — build ONLY these 6 frames, nothing else:**
> - Screen: `Projects`
> - Overlay: `project-search-modal`
> - Overlay: `status-filter-modal`
> - Overlay: `team-filter-modal`
> - Overlay: `project-detail-modal`
> - Overlay: `new-project-modal`
>
> Do NOT create Team or Reports screens. Leave sidebar nav items for those screens unwired. The QA pass must NOT flag missing navigation targets as errors or attempt to build those screens.

Add the Projects screen to the right of My Dashboard.

---

## Screen: Projects

### Layout
- Same sidebar (220px), active: **Projects**
- Header: "Projects", toggle buttons "Grid View" / "List View" (`view-toggle-on-Projects`), "New Project" button (primary, top right)

### Content sections (top → bottom)

**Filter bar**:
- Search: placeholder "Search projects…" — name `search-btn-Projects`
- Dropdown: "Status: All" — name `dropdown-Status-on-Projects` — options: All, Active, On Hold, Completed, Cancelled
- Dropdown: "Team: All" — name `dropdown-Team-on-Projects` — options: All, Engineering, Design, Marketing, Sales

**Project cards grid** — 2 columns × 3 rows (6 cards):

| Project | Team | Progress | Status | Due |
|---------|------|----------|--------|-----|
| Website Redesign | Design | 68% | Active | Jul 30 |
| Mobile App v2 | Engineering | 42% | Active | Aug 15 |
| CRM Integration | Sales | 89% | Active | Jun 25 |
| Data Pipeline | Engineering | 15% | On Hold | Sep 1 |
| Brand Refresh | Marketing | 100% | Completed | Jun 1 |
| Partner Portal | Engineering | 55% | Active | Aug 30 |

Each card: project name (bold), team tag, progress bar (two rectangles: grey bg + colored fill), status badge, due date, 3 avatar circles.

---

## Overlays to create

| Frame name | Size | Content |
|------------|------|---------|
| `project-search-modal` | 600×420 | Title "Search Projects", 4 matching project rows (name, team, status, progress %), Close button |
| `status-filter-modal` | 160×200 | 5 option rows: All, Active, On Hold, Completed, Cancelled |
| `team-filter-modal` | 160×200 | 5 option rows: All, Engineering, Design, Marketing, Sales |
| `project-detail-modal` | 640×560 | Title "Website Redesign", description, 68% progress bar, Tasks section (4 rows), Team Members row (3 avatars + names), Close button |
| `new-project-modal` | 560×480 | Title "New Project", fields: Name, Description, Team dropdown, Due date, Status; Save + Cancel buttons |

---

## Wiring

| Source element | Interaction | Destination |
|----------------|-------------|-------------|
| Sidebar: "Dashboard" | Navigate | My Dashboard screen |
| `search-btn-Projects` | Overlay | `project-search-modal` |
| `dropdown-Status-on-Projects` | Overlay | `status-filter-modal` |
| `dropdown-Team-on-Projects` | Overlay | `team-filter-modal` |
| Project card "Website Redesign" | Overlay | `project-detail-modal` |
| "New Project" button | Overlay | `new-project-modal` |
