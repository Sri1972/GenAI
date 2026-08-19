Create a 4-screen SaaS project management web app at 1440×900.

**Theme:** Light professional — bg `#f8fafc`, sidebar `#1e293b`, cards `#ffffff`, accent `#0ea5e9`, danger `#ef4444`, success `#22c55e`, text `#0f172a`, muted `#64748b`.

---

## Screen 1 — My Dashboard

### Layout
- Left sidebar (220px): app logo "Taskflow", nav items: Dashboard, Projects, Team, Reports
- User avatar + name at sidebar bottom
- Top bar: title "Dashboard", notification bell icon (top right), "New Task" button (primary, top right)

### Content sections (top → bottom)

**Welcome banner** — "Good morning, Alex. You have 8 tasks due today."

**Summary KPI row** — 4 cards:
| Card | Value | Note |
|------|-------|------|
| Active Projects | 12 | 3 due this week |
| Open Tasks | 47 | 8 due today |
| Completed Today | 6 | +20% vs yesterday |
| Overdue | 4 | Needs attention |

**Bar chart** (drawn with rectangles, 5 bars) — title "Tasks Completed This Week":
- Days: Mon, Tue, Wed, Thu, Fri
- Bar heights: 90, 120, 70, 150, 110 px (max 160px)
- Bars in accent color `#0ea5e9`

**Task list** — "Today's Tasks" (6 rows):
| # | Task | Project | Priority | Due | Status |
|---|------|---------|----------|-----|--------|
| 1 | Review design mockups | Website Redesign | High | Today 2pm | In Progress |
| 2 | Send proposal to client | CRM Integration | High | Today 4pm | Not Started |
| 3 | Update API docs | Mobile App v2 | Medium | Today EOD | In Progress |
| 4 | Team standup notes | All | Low | Today 9am | Done |
| 5 | Fix login bug | Auth Service | High | Today 3pm | In Progress |
| 6 | Deploy staging release | DevOps | Medium | Today 5pm | Not Started |

### Wiring
| Source element | Interaction | Destination |
|----------------|-------------|-------------|
| Sidebar: "Projects" | Navigate | Projects screen |
| Sidebar: "Team" | Navigate | Team screen |
| Sidebar: "Reports" | Navigate | Reports screen |
| "New Task" button | Overlay | New Task modal (560×440) — Task name, Project dropdown, Priority dropdown, Due date, Assignee, Description, Save + Cancel buttons |
| Notification bell icon (`notification-bell-btn-Dashboard`) | Overlay | Notifications modal (320×400) — 5 notification rows, "Mark all read" link, Close button |
| Task row 1 (Review design mockups) | Overlay | Task Detail modal (580×500) — title, description, project, assignee, due date, status badge, comments section, Close button |

---

## Screen 2 — Projects

### Layout
- Same sidebar, active: Projects
- Header: "Projects", toggle buttons: "Grid View" / "List View" (toggle group named `view-toggle-on-Projects`)
- "New Project" button (primary, top right)

### Content sections

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

Each card: project name (bold), team tag, progress bar (drawn as two rectangles: grey background + colored fill), status badge, due date, 3 avatar icons.

### Wiring
| Source element | Interaction | Destination |
|----------------|-------------|-------------|
| Sidebar: "Dashboard" | Navigate | My Dashboard screen |
| Sidebar: "Team" | Navigate | Team screen |
| Sidebar: "Reports" | Navigate | Reports screen |
| `search-btn-Projects` | Overlay | Project search modal (600×420) — results list with 4 matching project rows, Close button |
| `dropdown-Status-on-Projects` | Overlay | Status filter modal (160×200) — options: All, Active, On Hold, Completed, Cancelled |
| `dropdown-Team-on-Projects` | Overlay | Team filter modal (160×200) — options: All, Engineering, Design, Marketing, Sales |
| Project card "Website Redesign" | Overlay | Project Detail modal (640×560) — name, description, progress bar, task list (4 tasks), team members row, Close button |
| "New Project" button | Overlay | New Project modal (560×480) — Name, Description, Team dropdown, Due date, Status, Save + Cancel |

---

## Screen 3 — Team

### Layout
- Same sidebar, active: Team
- Header: "Team", "Invite Member" button (top right)

### Content sections

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

### Wiring
| Source element | Interaction | Destination |
|----------------|-------------|-------------|
| Sidebar: "Dashboard" | Navigate | My Dashboard screen |
| Sidebar: "Projects" | Navigate | Projects screen |
| Sidebar: "Reports" | Navigate | Reports screen |
| "Invite Member" button | Overlay | Invite modal (480×320) — Email input, Role dropdown, Team dropdown, Send Invite + Cancel buttons |
| Table row 1 (Sarah Chen) | Overlay | Member Profile modal (520×480) — avatar, name, role, team, active projects list, utilisation bar, Close button |

---

## Screen 4 — Reports

### Layout
- Same sidebar, active: Reports
- Header: "Reports & Analytics", date range picker (styled button): "Last 30 Days" — name `dropdown-DateRange-on-Reports` — options: Last 7 Days, Last 30 Days, Last Quarter, Custom

### Content sections

**Bar chart** (drawn with rectangles, 4 bars) — title "Tasks Completed by Team (Last 30 Days)":
- Teams: Engineering, Design, Marketing, Sales
- Bar heights: 160, 120, 90, 70 px
- Bars in accent color

**Two-column row**:
- Left: **Bar chart** (3 bars) — "Top Projects by Completion":
  - Projects: CRM Integration 89%, Website Redesign 68%, Mobile App 42%
  - Heights: 160, 120, 76 px
- Right: **Summary text card** — "Velocity: +18% vs last month", "On-time rate: 82%", "Avg cycle time: 3.2 days"

**Data table** — "Detailed Report: Tasks":
| Task | Project | Assignee | Created | Completed | Days |
|------|---------|----------|---------|-----------|------|
| Login bug fix | Auth Service | Jordan Lee | Jun 1 | Jun 3 | 2 |
| API docs update | Mobile App v2 | Tom Burke | Jun 2 | Jun 6 | 4 |
| Brand kit v2 | Brand Refresh | Nina Petrov | May 20 | Jun 1 | 12 |
| DB migration | Data Pipeline | Marcus Webb | Jun 4 | — | — |
| Campaign assets | Brand Refresh | Aisha Patel | May 28 | Jun 1 | 4 |

### Wiring
| Source element | Interaction | Destination |
|----------------|-------------|-------------|
| Sidebar: "Dashboard" | Navigate | My Dashboard screen |
| Sidebar: "Projects" | Navigate | Projects screen |
| Sidebar: "Team" | Navigate | Team screen |
| `dropdown-DateRange-on-Reports` | Overlay | Date range modal (180×200) — 4 option rows: Last 7 Days, Last 30 Days, Last Quarter, Custom |

---

## Overlay frames to create

| Frame name | Size | Purpose |
|------------|------|---------|
| `new-task-modal` | 560×440 | New task form |
| `notifications-modal` | 320×400 | Notification list |
| `task-detail-modal` | 580×500 | Task detail view |
| `project-search-modal` | 600×420 | Project search results |
| `status-filter-modal` | 160×200 | Status filter dropdown |
| `team-filter-modal` | 160×200 | Team filter dropdown |
| `project-detail-modal` | 640×560 | Project detail card |
| `new-project-modal` | 560×480 | New project form |
| `invite-modal` | 480×320 | Invite member form |
| `member-profile-modal` | 520×480 | Team member profile |
| `daterange-modal` | 180×200 | Date range options |

---

## Prototype start screen
Set **My Dashboard** as the prototype start frame.
