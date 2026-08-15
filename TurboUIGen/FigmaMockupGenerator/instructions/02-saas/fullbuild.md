# SaaS Project Management — Full Build

**UI Mode:** 🟢 **New Wireframe**

Build a complete 4-screen SaaS project management application. Desktop layout, 1440×900.

> Do NOT apply Mobility Global branding. Use the custom light color scheme below.

**Colors:** Background `#f8fafc` · Sidebar `#1e293b` · Cards `#ffffff` · Accent `#0ea5e9` · Text `#0f172a` · Muted `#64748b`

---

## Screen 1: My Dashboard

Left sidebar (220px, dark bg `#1e293b`): app logo "Taskflow" at top, navigation: **Dashboard** (active), Projects, Team, Reports. User avatar and name "Alex Morgan" at bottom.
Header: title "Dashboard", notification bell button (top right), "New Task" primary button (top right).

**Welcome banner** — light blue background: "Good morning, Alex. You have 8 tasks due today."

**4 KPI cards:**

| Metric | Value | Note |
|--------|-------|------|
| Active Projects | 12 | 3 due this week |
| Open Tasks | 47 | 8 due today |
| Completed Today | 6 | +20% vs yesterday |
| Overdue | 4 | Needs attention |

**Bar chart** "Tasks Completed This Week" — 5 bars (Mon–Fri): 90, 120, 70, 150, 110px. Accent color bars.

**Task list** "Today's Tasks" — 6 rows:

| Task | Project | Priority | Due | Status |
|------|---------|----------|-----|--------|
| Review design mockups | Website Redesign | High | Today 2pm | In Progress |
| Send proposal to client | CRM Integration | High | Today 4pm | Not Started |
| Update API docs | Mobile App v2 | Medium | Today EOD | In Progress |
| Team standup notes | All | Low | Today 9am | Done |
| Fix login bug | Auth Service | High | Today 3pm | In Progress |
| Deploy staging release | DevOps | Medium | Today 5pm | Not Started |

**What opens what:**
- "New Task" button → opens new task modal
- Notification bell → opens notifications panel
- Clicking task row 1 → opens task detail modal

---

## Screen 2: Projects

Left sidebar: Dashboard, **Projects** (active), Team, Reports.
Header: "Projects", toggle "Grid View / List View", "New Project" primary button.
Filter bar: search field, Status dropdown (All/Active/On Hold/Completed/Cancelled), Team dropdown (All/Engineering/Design/Marketing/Sales).

**6 project cards in a 2-column grid:**

| Project | Team | Progress | Status | Due |
|---------|------|----------|--------|-----|
| Website Redesign | Design | 68% | Active | Jul 30 |
| Mobile App v2 | Engineering | 42% | Active | Aug 15 |
| CRM Integration | Sales | 89% | Active | Jun 25 |
| Data Pipeline | Engineering | 15% | On Hold | Sep 1 |
| Brand Refresh | Marketing | 100% | Completed | Jun 1 |
| Partner Portal | Engineering | 55% | Active | Aug 30 |

Each card shows: project name (bold), team tag, progress bar, status badge, due date.

**What opens what:**
- Search field → opens project search results modal
- Status dropdown → opens status filter modal
- Team dropdown → opens team filter modal
- Clicking "Website Redesign" card → opens project detail modal
- "New Project" button → opens new project modal

---

## Screen 3: Team

Left sidebar: Dashboard, Projects, **Team** (active), Reports.
Header: "Team", "Invite Member" primary button.

**3 stat cards:** Total Members 24, Active Projects 12, Avg Utilisation 78%.

**Team member table — 8 rows:**

| Name | Role | Team | Projects | Utilisation | Status |
|------|------|------|----------|-------------|--------|
| Sarah Chen | Lead Designer | Design | 3 | 92% | Online |
| Marcus Webb | Sr Engineer | Engineering | 4 | 88% | In Meeting |
| Priya Nair | PM | Management | 6 | 95% | Online |
| Jordan Lee | Engineer | Engineering | 2 | 65% | Offline |
| Aisha Patel | Marketing Lead | Marketing | 2 | 71% | Online |
| Tom Burke | DevOps | Engineering | 3 | 80% | Online |
| Nina Petrov | Designer | Design | 2 | 60% | Away |
| Carlos Diaz | Sales | Sales | 4 | 85% | Online |

**What opens what:**
- "Invite Member" button → opens invite member modal
- Clicking row 1 (Sarah Chen) → opens member profile modal

---

## Screen 4: Reports

Left sidebar: Dashboard, Projects, Team, **Reports** (active).
Header: "Reports & Analytics", date range button "Last 30 Days" (dropdown).

**Bar chart** "Tasks Completed by Team (Last 30 Days)" — 4 bars: Engineering 160px, Design 120px, Marketing 90px, Sales 70px.

**Two-column row:**
- Left: bar chart "Top Projects by Completion" — 3 bars: CRM Integration 89%, Website Redesign 68%, Mobile App 42%
- Right: summary card — Velocity +18%, On-time rate 82%, Avg cycle time 3.2 days

**Data table** "Detailed Report: Tasks" — 5 rows with columns: Task, Project, Assignee, Created, Completed, Days.

**What opens what:**
- Date range button → opens date range modal

---

## Modals

### New task modal — 560×440
Title "New Task". Fields: Task name, Project (dropdown), Priority (dropdown), Due date, Assignee, Description. "Save" primary button. Cancel button.

### Notifications panel — 320×400
Title "Notifications". 5 notification rows with icon, message, and timestamp. "Mark all read" link. Close button.

### Task detail modal — 580×500
Title "Review design mockups". Fields showing: project, assignee, due date, status badge, description text. Comments section with 2 existing comments and reply input. Close button.

### Project search modal — 600×420
Title "Search Projects". 4 matching project rows showing name, team, status, progress %. Close button.

### Status filter modal — 160×200
5 options: All, Active, On Hold, Completed, Cancelled.

### Team filter modal — 160×200
5 options: All, Engineering, Design, Marketing, Sales.

### Project detail modal — 640×560
Title "Website Redesign". Description text. Progress bar at 68%. Task list (4 rows). Team members row (3 avatars). Close button.

### New project modal — 560×480
Title "New Project". Fields: Name, Description, Team (dropdown), Due date, Status. Save + Cancel buttons.

### Invite member modal — 480×320
Title "Invite Team Member". Fields: Email, Role (dropdown), Team (dropdown). "Send Invite" primary button. Cancel.

### Member profile modal — 520×480
Title "Sarah Chen". Avatar placeholder. Role and team info. Active projects list (3 rows). Utilisation bar at 92%. Close button.

### Date range modal — 180×200
4 options: Last 7 Days, Last 30 Days, Last Quarter, Custom.

---

## Prototype start
Set **My Dashboard** as the prototype start screen.
