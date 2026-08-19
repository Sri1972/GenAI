# SaaS Project Management — Phase 1: Dashboard

**UI Mode:** 🟢 **Build Wireframe**
**Canvas:** 1440×900 desktop

> ⚠️ **STRICT PHASE SCOPE — build ONLY these 4 frames, nothing else:**
> - Screen: `My Dashboard`
> - Overlay: `new-task-modal`
> - Overlay: `notifications-modal`
> - Overlay: `task-detail-modal`
>
> Do NOT create Projects, Team, or Reports screens. Sidebar nav items for those screens are **visual placeholders only** — leave them unwired. The QA pass must NOT flag missing navigation targets as errors or attempt to build missing screens.

Build the first screen of a light SaaS project management app.

**Theme:** Light professional — bg `#f8fafc`, sidebar `#1e293b`, cards `#ffffff`, accent `#0ea5e9`, danger `#ef4444`, success `#22c55e`, text `#0f172a`, muted `#64748b`.

---

## Screen: My Dashboard

### Layout
- Left sidebar (220px), dark bg `#1e293b`: app logo "Taskflow" at top, nav items: **Dashboard** (active), Projects, Team, Reports; user avatar + "Alex Morgan" at bottom
- Top bar (white): title "Dashboard", notification bell icon `notification-bell-btn-Dashboard` (top right), "New Task" button (primary, top right)

### Content sections (top → bottom)

**Welcome banner** — bg `#e0f2fe`, text "Good morning, Alex. You have 8 tasks due today."

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

---

## Overlays to create

| Frame name | Size | Content |
|------------|------|---------|
| `new-task-modal` | 560×440 | Title "New Task", fields: Task name, Project dropdown, Priority dropdown, Due date, Assignee, Description; Save + Cancel buttons |
| `notifications-modal` | 320×400 | Title "Notifications", 5 notification rows with icon + text + time, "Mark all read" link at top, Close button |
| `task-detail-modal` | 580×500 | Title "Review design mockups", fields: project, assignee, due date, status badge, description, Comments section with 2 existing comments + reply input, Close button |

---

## Wiring

After ALL four frames are built, call `figma_list_frame_nodes(frame_name="My Dashboard")` to confirm node names, then wire in a single call:

```
figma_wire_all(
  links=[
    {"source_frame": "My Dashboard", "source_node": "notification-bell-btn-Dashboard", "target_frame": "notifications-modal", "type": "OVERLAY"},
    {"source_frame": "My Dashboard", "source_node": "new-task-btn-Dashboard",            "target_frame": "new-task-modal",      "type": "OVERLAY"},
    {"source_frame": "My Dashboard", "source_node": "row1-btn-Dashboard",               "target_frame": "task-detail-modal",   "type": "OVERLAY"},
  ],
  start_frame="My Dashboard"
)
```

**Do NOT** wire sidebar items for Projects, Team, or Reports — those screens don't exist yet.

---

## Prototype start
Handled by `start_frame="My Dashboard"` in the `figma_wire_all` call above.
