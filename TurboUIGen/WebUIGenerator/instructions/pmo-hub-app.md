# PMO Command Center — Project & Resource Intelligence

## App Overview

**App name:** PMO Command Center
**Theme:** Enterprise project management office — portfolio health, resource allocation, and delivery intelligence
**Accent color:** #0F172A

---

## Data Model

### Table: projects
| Column | Type | Description |
|--------|------|-------------|
| project_id | text | Unique ID (PRJ-001 through PRJ-025) |
| name | text | Project name |
| sponsor | text | Executive sponsor name |
| pm | text | Project manager name |
| department | categorical | Engineering, Data & Analytics, Infrastructure, Product, Security |
| priority | categorical | Critical, High, Medium, Low |
| status | categorical | On Track, At Risk, Delayed, Completed, On Hold |
| phase | categorical | Initiation, Planning, Execution, Closing |
| start_date | text | YYYY-MM-DD |
| target_date | text | YYYY-MM-DD |
| budget | numeric | Total budget in USD (50000–2000000) |
| spent | numeric | Amount spent to date |
| completion | numeric | Percentage complete 0–100 |
| rag | categorical | Green, Amber, Red |
| region | categorical | Americas, EMEA, APAC, Global |

**Seed rows:** 25
**Seed notes:** Mix of statuses (40% On Track, 25% At Risk, 15% Delayed, 15% Completed, 5% On Hold). Budgets vary by department — Security/Infrastructure tend higher. Completion correlates loosely with phase (Initiation=5–15%, Planning=15–35%, Execution=35–85%, Closing=85–100%). Spread across all regions and departments.

### Table: resources
| Column | Type | Description |
|--------|------|-------------|
| resource_id | text | Unique ID (RES-001 through RES-040) |
| name | text | Employee name |
| role | categorical | Developer, Architect, Analyst, Designer, QA, DevOps, Scrum Master, Product Owner |
| department | categorical | Engineering, Data & Analytics, Infrastructure, Product, Security |
| level | categorical | Junior, Mid, Senior, Lead, Principal |
| location | categorical | New York, London, Singapore, Toronto, Sydney |
| capacity_hrs | numeric | Weekly available hours (typically 40) |
| allocated_hrs | numeric | Weekly hours allocated to projects (0–50, can exceed capacity) |
| utilization | numeric | Percentage (allocated_hrs / capacity_hrs × 100) |
| hourly_rate | numeric | Internal cost rate USD (75–250 depending on level) |
| skills | text | Comma-separated skill tags |
| availability | categorical | Available, Fully Allocated, Over-allocated, On Leave |

**Seed rows:** 40
**Seed notes:** Distribution: ~15% Available, ~45% Fully Allocated (95–105%), ~30% Over-allocated (>105%), ~10% On Leave. Levels pyramid: 30% Junior/Mid, 40% Senior, 20% Lead, 10% Principal. Spread across all 5 locations.

### Table: timesheets
| Column | Type | Description |
|--------|------|-------------|
| entry_id | text | Unique ID (TS-0001 through TS-0200) |
| resource_id | text | FK to resources |
| resource_name | text | Employee name (denormalized for easy query) |
| project_id | text | FK to projects |
| project_name | text | Project name (denormalized) |
| week | text | ISO week start date YYYY-MM-DD (Mondays from 2025-01 to 2025-06) |
| hours | numeric | Hours logged that week (1–45) |
| billable | categorical | Yes, No |
| activity | categorical | Development, Design, Testing, Meetings, Planning, Admin, Support |

**Seed rows:** 200
**Seed notes:** Each resource has 4–6 timesheet entries across different weeks. Hours per person per week should sum to roughly their allocated_hrs. ~75% billable. Activities weighted toward Development (30%) and Meetings (20%).

---

## Pages

Add 5 pages to the sidebar:
1. Portfolio
2. Resources
3. Timesheets
4. Capacity
5. AI Advisor

---

### Page 1: Portfolio
**Sidebar label:** "Portfolio"

Executive portfolio overview — the PMO's "war room" view.

- **Project cards grid:** Show all projects as cards in a responsive grid (3 columns).
  Each card shows:
  - Project name (bold) + project_id (muted)
  - PM name
  - Department badge + Priority badge
  - Progress bar (colored by RAG: Green=#10B981, Amber=#F59E0B, Red=#EF4444)
  - Completion % label
  - Budget: "$X spent of $Y" with small progress bar
  - Status badge (On Track=green, At Risk=amber, Delayed=red, Completed=blue, On Hold=gray)
  - Target date

- **Filter bar above cards:** Department dropdown, Priority dropdown, Status dropdown, RAG dropdown, text search (project name or PM name), Reset button

- **Summary bar above cards (inline stats, not KPI cards):** Active Projects count, On Track %, Total Budget, Budget Consumed %, At Risk + Delayed count — displayed as a compact horizontal stat strip (single row of labeled values, no card borders).

---

### Page 2: Resources
**Sidebar label:** "Resources"

Resource pool management — who's available, who's overloaded.

- **Charts row (2 side-by-side):**
  - Left: Bar chart — average utilization by department
  - Right: Scatter plot — allocated_hrs (x) vs capacity_hrs (y), colored by availability. Points above the diagonal line = over-allocated.

- **Filter bar:** Text search (name, skills), Role dropdown, Department dropdown, Level dropdown, Location dropdown, Availability dropdown, Reset + count badge

- **Data table:**
  - Name
  - Role (badge)
  - Department
  - Level (badge: Junior=gray, Mid=blue, Senior=purple, Lead=indigo, Principal=amber)
  - Location
  - Capacity (hrs/wk)
  - Allocated (hrs/wk)
  - Utilization (progress bar: green ≤85%, amber 86–105%, red >105%)
  - Rate ($/hr formatted)
  - Availability (badge: Available=green, Fully Allocated=blue, Over-allocated=red, On Leave=gray)
  - Skills (truncated with tooltip)

- Sortable, paginated at 15 rows
- **Export CSV** button

---

### Page 3: Timesheets
**Sidebar label:** "Timesheets"

Weekly time tracking view with aggregations.

- **Charts row (2 side-by-side):**
  - Left: Stacked bar — total hours by week (last 8 weeks), stacked by activity type
  - Right: Donut chart — hours by activity (Development/Design/Testing/Meetings/Planning/Admin/Support)

- **Filter bar:** Text search (resource name, project name), Project dropdown (distinct project names), Activity dropdown, Billable dropdown (Yes/No/All), Week range (last 4 weeks / last 8 weeks / all), Reset + count badge

- **Data table:**
  - Resource Name
  - Project Name
  - Week (formatted as "Jan 6" style)
  - Hours
  - Activity (badge, colored: Development=blue, Design=purple, Testing=green, Meetings=amber, Planning=teal, Admin=gray, Support=orange)
  - Billable (Yes=green check, No=red x)

- Sortable, paginated at 20 rows
- **Export CSV** button

---

### Page 4: Capacity
**Sidebar label:** "Capacity"

Capacity planning heatmap and allocation view.

- **Heatmap (full width):** Resources (y-axis, grouped by department) vs Utilization.
  - Simple horizontal bar per resource showing allocated vs capacity, colored by utilization band.
  - Color: green (≤70%), teal (71–85%), amber (86–100%), orange (101–115%), red (>115%).

- **Department summary table:**
  - Department
  - Headcount
  - Total Capacity (hrs)
  - Total Allocated (hrs)
  - Avg Utilization %
  - Over-allocated Count
  - Available Count

- **Charts (2 side-by-side below):**
  - Left: Grouped bar — capacity vs allocated by department
  - Right: Bar chart — headcount by role across all departments

---

### Page 5: AI Advisor
**Sidebar label:** "AI Advisor"

AI-powered PMO intelligence chatbot. Three-column layout with role-based personas.

**Left column:** Persona selector.
- Three persona cards — name, role, colored left border. Clicking selects.
- Below: 5 prompt buttons for active persona.

**Personas:**

- **PMO Director** (accent `#0F172A`)
  Role context: "Focus on portfolio health, RAG trends, budget burn rates, delivery risks, and executive reporting. Give concise summaries with clear action items."
  Prompts:
  - Portfolio Health Summary
  - Budget Burn Report
  - At-Risk Projects Deep Dive
  - Delivery Forecast
  - Steering Committee Brief

- **Resource Manager** (accent `#7C3AED`)
  Role context: "Focus on utilization rates, over-allocation hotspots, skill gaps, bench availability, and optimal rebalancing. Be specific about names and numbers."
  Prompts:
  - Utilization Heatmap Summary
  - Over-allocated Staff
  - Available Bench
  - Skill Gap Analysis
  - Rebalancing Recommendations

- **Delivery Lead** (accent `#0891B2`)
  Role context: "Focus on timesheet patterns, sprint velocity indicators, meeting overhead, billability targets, and team productivity. Flag anomalies."
  Prompts:
  - Timesheet Anomalies
  - Billability vs Target (75%)
  - Meeting Overhead Analysis
  - Top Contributors
  - Project Effort Distribution

**Center column:** Chat panel.
- User messages in dark bubbles, AI responses in light bubbles.
- Typing indicator while waiting.
- Free-text input at bottom — user can ask anything about the data.
- AI can respond with text, charts, tables, or maps rendered inline.

**Right column:** Export panel.
- Four slide template cards:
  - Portfolio Status (slate)
  - Resource Report (purple)
  - Delivery Metrics (teal)
  - Steering Deck (amber)
- Each has "Export PPTX" button to export the chat as a slide deck.

---

## Visual Style

Use a dark slate/indigo accent palette to differentiate from other apps. Cards should have subtle slate borders and shadows. The overall feel should be professional and data-dense — a tool for senior managers, not a consumer product.
