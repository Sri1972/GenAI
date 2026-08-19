# TalentScope — People Analytics & Workforce Intelligence

## App Overview

**App name:** people-analytics
**Theme:** Modern HR tech — clean, human-centered, generous spacing
**Accent color:** #6366F1 (indigo — trust, stability)
**Secondary accent:** #EC4899 (pink — diversity, people warmth)
**Style:** Light mode, large typography, soft card shadows, rounded 16px corners. Feels approachable, not corporate.

---

## Data Model

### Table: employees
| Column | Type | Description |
|--------|------|-------------|
| id | integer | Auto PK |
| employee_id | text | Unique ID (EMP-XXXXX format) |
| name | text | Full name |
| department | categorical | Engineering, Product, Sales, Marketing, Finance, HR, Operations, Legal |
| title | text | Job title |
| level | categorical | IC1, IC2, IC3, IC4, Senior, Lead, Manager, Director, VP |
| location | categorical | New York, San Francisco, London, Berlin, Singapore, Remote |
| hire_date | text | YYYY-MM-DD (range: 2018–2025) |
| salary | numeric | Annual salary USD (55000–350000) |
| performance_rating | numeric | Last review score 1.0–5.0 |
| engagement_score | numeric | Pulse survey 1–100 |
| manager_name | text | Direct manager |
| gender | categorical | Male, Female, Non-binary |
| flight_risk | categorical | Low, Medium, High |
| status | categorical | Active, On Leave, Exiting |

**Seed rows:** 75
**Seed notes:** Realistic distribution — 30% Engineering, 15% Sales, 12% Product. Level pyramid: many IC1–IC3, few Director/VP. Salaries correlate with level. Flight risk inversely correlates with engagement. 5 manager_names.

### Table: one_on_ones
| Column | Type | Description |
|--------|------|-------------|
| id | integer | Auto PK |
| employee_id | text | References employees.employee_id |
| employee_name | text | Employee name |
| manager_name | text | Manager name |
| date | text | YYYY-MM-DD (range: 2024-09 to 2025-06) |
| mood | categorical | Great, Good, Okay, Concerned, Struggling |
| topics | text | Comma-separated topics discussed (e.g., "career growth, workload, team dynamics") |
| action_items | text | What was agreed (e.g., "Schedule skip-level, Adjust sprint load") |
| follow_up_needed | categorical | Yes, No |
| sentiment_score | numeric | AI-derived sentiment from notes 1.0–5.0 |

**Seed rows:** 60
**Seed notes:** Spread across employees — high-risk employees should have more 1:1s. Mood should trend with engagement_score. Topics should feel realistic. Some follow_up_needed = Yes with specific action items.

### Table: goals
| Column | Type | Description |
|--------|------|-------------|
| id | integer | Auto PK |
| employee_id | text | References employees.employee_id |
| employee_name | text | Employee name |
| goal_title | text | Goal description (e.g., "Ship v2.0 API", "Close $500K pipeline") |
| category | categorical | Delivery, Growth, Leadership, Collaboration, Innovation |
| status | categorical | On Track, At Risk, Behind, Completed, Not Started |
| progress_pct | integer | 0–100 completion |
| due_date | text | YYYY-MM-DD |
| weight | numeric | Goal weight/importance (0.1–0.5, should sum to ~1.0 per employee) |

**Seed rows:** 80
**Seed notes:** 2–4 goals per employee. Mix of statuses. Senior/Lead employees have Leadership goals. Progress should roughly match status (Completed=100, Behind<30, etc.). Due dates spread across next 2 quarters.

---

## Pages

Add 6 pages to the sidebar:
1. Org Pulse
2. Nine-Box
3. 1:1 Tracker
4. Goal Progress
5. HR Copilot
6. Workforce Insights

---

### Page 1: Org Pulse
**Sidebar label:** "Org Pulse"
**Component:** `src/pages/OrgPulse.tsx`

Organization health at a glance — NOT a traditional dashboard. Uses a radial/circular layout as the hero visual.

- **Engagement sunburst (main visual, centered, 450px diameter):**
  - Center: Overall engagement score (large number + label)
  - Inner ring: departments (8 segments, sized by headcount)
  - Outer ring: subdivided by level within each department
  - Segment color: engagement score (green ≥70, amber 50–69, red <50)
  - Click a segment to filter the summary below

- **Mood pulse strip (below sunburst, full width):**
  - Horizontal timeline (last 6 months) showing average sentiment_score from 1:1s
  - Line chart with mood emoji markers at each data point (😊 >4.0, 😐 3.0–4.0, 😟 <3.0)
  - One line per department (multi-line, toggleable legend)

- **Flight risk cards (bottom, horizontal scroll):**
  - Only employees where flight_risk = "High" (sorted by engagement ascending)
  - Each card: Name, Title, Department badge, Engagement gauge (mini circular), Tenure, Last 1:1 mood
  - Red left border on each card
  - Max 8 cards visible, scroll for more

- **Quick stats (right sidebar, 200px, or below on mobile):**
  - Active headcount
  - On Leave count
  - Exiting count
  - Avg performance rating
  - 1:1s completed this month
  - Goals at risk (count)

---

### Page 2: Nine-Box
**Sidebar label:** "9-Box"
**Component:** `src/pages/NineBox.tsx`

Classic 9-box talent grid — performance vs potential. Interactive matrix visualization.

- **Nine-box grid (main visual, full width, 600px tall):**
  - 3×3 grid. X axis: Performance (Low / Medium / High — derived from performance_rating: <3.0 / 3.0–4.0 / >4.0). Y axis: Potential (Low / Medium / High — derived from engagement_score: <40 / 40–70 / >70, as a proxy for potential).
  - Each cell contains employee avatars/chips (initials circle + name truncated)
  - Cell background colors:
    - Top-right (High/High): "Star" — green
    - Top-left (High Potential / Low Performance): "Enigma" — amber
    - Bottom-right (Low Potential / High Performance): "Workhorse" — blue
    - Bottom-left (Low/Low): "Action Needed" — red
    - Middle cells: light gray
  - Cell header: category name + count
  - Click a cell to see full list below

- **Selected cell detail panel (below grid):**
  - Table of employees in the selected 9-box cell
  - Columns: Name, Department, Title, Level, Performance, Engagement, Tenure, Flight Risk badge
  - Recommended action for the cell (text banner): e.g., "Stars: Accelerate career path, increase visibility, stretch assignments"

- **Department filter (top):** Dropdown to filter by department. Grid recomputes when changed.

- **Distribution summary (compact, below detail):**
  - 3×3 mini table showing just the COUNT in each cell
  - Percentage breakdown of "Stars" vs "Action Needed" employees

---

### Page 3: 1:1 Tracker
**Sidebar label:** "1:1s"
**Component:** `src/pages/OneOnOneTracker.tsx`

Manager 1:1 meeting tracking with sentiment trends. Calendar/timeline-inspired layout.

- **Manager view selector (top):** Horizontal tab for each manager_name. Shows their direct report count.

- **Meeting timeline (main visual, vertical):**
  - Vertical timeline (most recent at top)
  - Each entry: Date, Employee name + avatar, Mood indicator (colored circle: Great=green, Good=lime, Okay=amber, Concerned=orange, Struggling=red)
  - Topics as small tag pills
  - Expand on click to show: action_items, follow_up_needed badge, sentiment_score

- **Cadence heatmap (right panel, 300px):**
  - Calendar-style grid (last 3 months)
  - Days colored by 1:1 count: white=0, light indigo=1, dark indigo=3+
  - Shows which days the manager holds 1:1s (reveals gaps)

- **Follow-up queue (below timeline):**
  - List of 1:1s where follow_up_needed = "Yes" AND no subsequent 1:1 with that employee
  - Cards: Employee, date of 1:1, action items, days since (amber if >14 days, red if >30)
  - Sorted by days-since descending

- **Mood distribution (bottom, compact):**
  - Stacked horizontal bar per manager: % Great/Good/Okay/Concerned/Struggling
  - Reveals which managers have healthier team sentiment

---

### Page 4: Goal Progress
**Sidebar label:** "Goals"
**Component:** `src/pages/GoalProgress.tsx`

OKR/goal tracking with visual progress indicators. Kanban-meets-progress-bar hybrid.

- **Progress overview (top, 5 swim lanes, horizontal):**
  - Not Started | On Track | At Risk | Behind | Completed
  - Each lane shows a COUNT bubble + colored line below (matches status color)
  - Not Started=gray, On Track=green, At Risk=amber, Behind=red, Completed=indigo

- **Goal cards (main content, filterable grid):**
  - Filter by: Department, Category, Status, Employee search
  - Card layout (2 columns):
    - Goal title (bold)
    - Employee name + department badge
    - Category pill (colored: Delivery=blue, Growth=green, Leadership=purple, Collaboration=teal, Innovation=pink)
    - Progress bar (0–100%, colored by status)
    - Due date (with countdown: "12 days left" or "⚠️ 5 days overdue" in red)
    - Weight badge (shows priority)
  - Sorted by: due_date ascending (most urgent first)

- **Department progress radar (bottom-left):**
  - Radar/spider chart with 5 axes = goal categories
  - One polygon per department (select up to 3 to compare)
  - Axis values = avg progress_pct in that category

- **Completion velocity (bottom-right):**
  - Line chart: cumulative goals completed over time (last 6 months)
  - Shows acceleration/deceleration in goal completion

---

### Page 5: HR Copilot
**Sidebar label:** "HR Copilot"
**Component:** `src/pages/HrCopilot.tsx`

AI-powered HR partner. Empathetic, discrete, and constructive.

**Layout:** Chat (65% width) + context panel (35% width, collapsible).

**Chat panel (left):**
- Soft indigo accent, white background
- AI uses warm but professional language
- Can render: employee comparison tables, progress indicators, bullet lists with action items
- Input placeholder: "Ask about people, engagement, goals, or retention…"

**Suggestion chips (above input):**
- "Who's at risk of leaving in Engineering?"
- "Show me overdue 1:1 follow-ups"
- "Draft talking points for a retention conversation"
- "Which teams have the lowest engagement?"
- "Compare goal completion rates by department"
- "Summarize this quarter's 9-box shifts"

**Context panel (right, 35%):**
- **Flight risk summary:** High (red count) / Medium (amber) / Low (green)
- **Overdue follow-ups:** Count with "oldest: X days" note
- **Goals at risk:** Count
- **Recent mood trend:** Mini sparkline of avg sentiment_score last 30 days
- Panel updates when conversation references specific data

**AI persona:**
System context: "You are an experienced HR business partner with deep analytics expertise. You have access to employee data, 1:1 meeting records, goals, and engagement scores. Be empathetic but data-driven. When discussing individuals, be constructive — focus on support actions, not blame. Suggest specific interventions: skip-level meetings, workload adjustments, career path conversations, compensation reviews. Never frame flight risk as the employee's fault. For aggregate questions, use specific numbers and department comparisons. Format responses with bullet points and bold key findings."

---

### Page 6: Workforce Insights
**Sidebar label:** "Insights"
**Component:** `src/pages/WorkforceInsights.tsx`

Advanced people analytics — visual deep-dive into workforce composition and health.

- **Radar/spider chart (top-left, 380px):**
  - Compare departments across 6 dimensions: Engagement, Performance, Retention, Diversity, Goal Completion, Manager Effectiveness
  - One polygon per department (top 4 by headcount)
  - Normalize values to 0–100 scale
  - Hoverable vertices showing exact scores

- **Sunburst chart (top-right, 380px):**
  - Org hierarchy: Department (inner) → Level (middle) → Location (outer)
  - Sized by headcount
  - Color by department
  - Click to zoom into a ring segment

- **Box plot (middle-left, 320px):**
  - Salary distribution by department
  - One box per department showing median, Q1, Q3, whiskers, outliers
  - Overlay: industry benchmark median line
  - Highlight departments with high dispersion

- **Funnel chart (middle-right, 320px):**
  - Hiring pipeline: Applications (100%) → Phone Screen → Technical → Onsite → Offer → Accepted → Started
  - Show conversion rate between each step
  - Color gradient from blue to green as candidates progress

- **Histogram (bottom-left, 300px):**
  - Engagement score distribution (bins: 0–20, 20–40, 40–60, 60–80, 80–100)
  - Overlay: flight_risk color segments within each bin
  - Shows if low engagement correlates with high flight risk

- **Polar/rose chart (bottom-right, 300px):**
  - 1:1 meeting topics frequency (8 petals: career growth, workload, team dynamics, compensation, recognition, projects, wellbeing, feedback)
  - Sized by frequency count
  - Color by average sentiment_score for that topic

---

## Behavior notes

1. **Human-centered** — generous whitespace, large rounded cards, soft shadows. Not clinical.
2. **No traditional data grids** — prefer cards, timelines, the 9-box matrix, and Kanban lanes over spreadsheet-style tables.
3. **Privacy-conscious** — flight risk and compensation framed supportively, not punitively.
4. **Indigo + pink palette** — indigo for structure/trust, pink for diversity/people highlights.
5. **Interactive 9-box** — the matrix IS the navigation for that page. Click to explore.
6. **No maps** — workforce data doesn't need geographic visualization here.
