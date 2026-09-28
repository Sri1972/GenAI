# SaaS Project Management — Phase 3: Team & Reports

**UI Mode:**
- 🟡 **Rebuild Wireframe** — if a stub screen with this name already exists on the canvas
- 🟢 **Add Screens** — if adding to an existing canvas without stubs (places new frames to the right)
**Canvas:** 1440×900 desktop

> **Prerequisite:** Run Phase 1 and Phase 2 first. My Dashboard and Projects screens must already exist on the canvas.

Add the Team and Reports screens to complete the app. Then run `figma_wire_all` to connect all sidebar navigation across all four screens.

---

## Screen: Team

### Layout
- Same sidebar (220px), active: **Team**
- Header: "Team", "Invite Member" button (primary, top right)

### Content sections (top → bottom)

**Stats row** — 3 cards:
| Card | Value | Note |
|------|-------|------|
| Total Members | 24 | 3 pending invites |
| Active Projects | 12 | Across 4 teams |
| Avg Utilisation | 78% | Healthy |

**Team member table** — 8 rows:
| Name | Role | Team | Active Projects | Utilisation | Status |
|------|------|------|-----------------|-------------|--------|
| Sarah Chen | Lead Designer | Design | 3 | 92% | Online |
| Marcus Webb | Sr Engineer | Engineering | 4 | 88% | In Meeting |
| Priya Nair | PM | Management | 6 | 95% | Online |
| Jordan Lee | Engineer | Engineering | 2 | 65% | Offline |
| Aisha Patel | Marketing Lead | Marketing | 2 | 71% | Online |
| Tom Burke | DevOps | Engineering | 3 | 80% | Online |
| Nina Petrov | Designer | Design | 2 | 60% | Away |
| Carlos Diaz | Sales | Sales | 4 | 85% | Online |

---

## Screen: Reports

### Layout
- Same sidebar (220px), active: **Reports**
- Header: "Reports & Analytics", date range button "Last 30 Days" — name `dropdown-DateRange-on-Reports` — options: Last 7 Days, Last 30 Days, Last Quarter, Custom

### Content sections (top → bottom)

**Bar chart** (drawn with rectangles, 4 bars) — title "Tasks Completed by Team (Last 30 Days)":
- Teams: Engineering, Design, Marketing, Sales
- Bar heights: 160, 120, 90, 70 px — bars in accent color `#0ea5e9`

**Two-column row**:
- Left: Bar chart (3 bars) — "Top Projects by Completion": CRM Integration 89%, Website Redesign 68%, Mobile App 42%; heights 160, 120, 76 px
- Right: Summary text card — "Velocity: +18% vs last month" / "On-time rate: 82%" / "Avg cycle time: 3.2 days"

**Data table** — "Detailed Report: Tasks" (5 rows):
| Task | Project | Assignee | Created | Completed | Days |
|------|---------|----------|---------|-----------|------|
| Login bug fix | Auth Service | Jordan Lee | Jun 1 | Jun 3 | 2 |
| API docs update | Mobile App v2 | Tom Burke | Jun 2 | Jun 6 | 4 |
| Brand kit v2 | Brand Refresh | Nina Petrov | May 20 | Jun 1 | 12 |
| DB migration | Data Pipeline | Marcus Webb | Jun 4 | — | — |
| Campaign assets | Brand Refresh | Aisha Patel | May 28 | Jun 1 | 4 |

---

## Overlays to create

| Frame name | Size | Content |
|------------|------|---------|
| `invite-modal` | 480×320 | Title "Invite Team Member", fields: Email, Role dropdown, Team dropdown; Send Invite + Cancel buttons |
| `member-profile-modal` | 520×480 | Title "Sarah Chen", avatar placeholder, role/team info, Active Projects list (3 rows), Utilisation bar (92%), Close button |
| `daterange-modal` | 180×200 | 4 option rows: Last 7 Days, Last 30 Days, Last Quarter, Custom |

---

## Wiring

| Source element | Interaction | Destination |
|----------------|-------------|-------------|
| "Invite Member" button | Overlay | `invite-modal` |
| Table row 1 (Sarah Chen) | Overlay | `member-profile-modal` |
| `dropdown-DateRange-on-Reports` | Overlay | `daterange-modal` |

After building both screens and all overlays, call `figma_wire_all` to connect all sidebar navigation links across My Dashboard, Projects, Team, and Reports.
