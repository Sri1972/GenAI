# CampusIQ — Student Success & Academic Intelligence

## App Overview

**App name:** campus-insights
**Theme:** Modern edtech — approachable, colorful, student-friendly
**Accent color:** #0EA5E9 (sky blue — openness, clarity)
**Secondary accent:** #F97316 (orange — energy, alerts, achievement)
**Style:** Light mode, playful rounded elements, gradient section headers, friendly icons. Feels like a modern LMS, not a spreadsheet.

---

## Data Model

### Table: students
| Column | Type | Description |
|--------|------|-------------|
| id | integer | Auto PK |
| student_id | text | Unique ID (STU-XXXXX format) |
| name | text | Full name |
| program | categorical | Computer Science, Business, Engineering, Liberal Arts, Nursing, Data Science |
| year | categorical | Freshman, Sophomore, Junior, Senior, Graduate |
| gpa | numeric | Current GPA 0.0–4.0 |
| credits_completed | integer | Total credits earned (0–140) |
| credits_enrolled | integer | Current semester credits (12–21) |
| advisor | text | Academic advisor name |
| enrollment_status | categorical | Full-time, Part-time, Probation, Dean's List |
| risk_level | categorical | On Track, Watch, At Risk, Critical |
| last_login_days | integer | Days since last LMS login (0–45) |
| campus | categorical | Main Campus, North Extension, Online |
| extracurricular | text | Club/activity name or "None" |

**Seed rows:** 80
**Seed notes:** GPA distribution mean 3.1, std 0.6. Credits correlate with year. Risk: At Risk if GPA < 2.0 OR last_login_days > 21. Dean's List if GPA > 3.7. CS 25%, Business 20%, Engineering 18%, Liberal Arts 15%, Nursing 12%, Data Science 10%.

### Table: assignments
| Column | Type | Description |
|--------|------|-------------|
| id | integer | Auto PK |
| student_id | text | References students.student_id |
| course_code | text | e.g., "CS-301", "BUS-210" |
| assignment_name | text | e.g., "Midterm Exam", "Final Project", "Weekly Quiz 4" |
| type | categorical | Exam, Project, Quiz, Essay, Lab, Presentation |
| score | numeric | Points earned (0–100) |
| max_score | numeric | Total possible points (always 100) |
| submitted_date | text | YYYY-MM-DD or null if not submitted |
| due_date | text | YYYY-MM-DD |
| late | categorical | On Time, Late, Missing |
| weight_pct | numeric | % of course grade this assignment is worth (5–40) |

**Seed rows:** 200
**Seed notes:** 2–4 assignments per student. Mix of types. Scores should correlate with student GPA (high-GPA students score 80–100, low-GPA 40–70). ~10% Missing (submitted_date=null, late=Missing), ~15% Late. Exam weight=30–40%, Quiz=5–10%, Project=20–30%.

### Table: office_hours
| Column | Type | Description |
|--------|------|-------------|
| id | integer | Auto PK |
| advisor | text | Advisor or instructor name |
| student_id | text | References students.student_id |
| student_name | text | Student name |
| date | text | YYYY-MM-DD |
| time_slot | text | e.g., "10:00 AM", "2:30 PM" |
| duration_min | integer | Meeting length (15, 30, 45, 60) |
| topic | categorical | Academic Plan, Grade Concern, Career Guidance, Personal Issue, Registration Help, Research Opportunity |
| outcome | categorical | Action Plan Set, Referral Made, Follow-up Needed, Resolved, No Show |
| notes | text | Brief meeting note |

**Seed rows:** 45
**Seed notes:** At-risk students should have more office hours visits. Some No Shows from disengaged students (high last_login_days). Topics weighted: Academic Plan 30%, Grade Concern 25%, Career 20%, others split.

---

## Pages

Add 6 pages to the sidebar:
1. Student Mosaic
2. Assignment Tracker
3. Risk Radar
4. Office Hours
5. Advisor AI
6. Academic Analytics

---

### Page 1: Student Mosaic
**Sidebar label:** "Mosaic"
**Component:** `src/pages/StudentMosaic.tsx`

Visual student overview using a MOSAIC/WAFFLE CHART as the hero — each student is one cell in a grid. NOT a table, NOT a dashboard.

- **Waffle grid (main visual, full width, ~500px tall):**
  - 80 small squares arranged in a grid (10 columns × 8 rows)
  - Each square = one student
  - Square color by risk_level: On Track=#10B981 (green), Watch=#F59E0B (amber), At Risk=#F97316 (orange), Critical=#EF4444 (red)
  - Hover a square: tooltip with name, program, GPA, year, risk_level
  - Click a square: expands to show student detail card below

- **Color-by selector (top-right):** Dropdown to change what the grid colors represent:
  - Risk Level (default)
  - Program (6 distinct colors)
  - Year (gradient: Freshman=light → Senior/Graduate=dark)
  - GPA Range (<2.0=red, 2.0–3.0=amber, 3.0–3.5=blue, >3.5=green)
  - Last Login (recent=green, old=red)

- **Legend strip (below grid):** Color legend matching current selection, with counts per category.

- **Distribution rings (below, 3 side-by-side donut charts):**
  - By Program (6 slices)
  - By Year (5 slices)
  - By Campus (3 slices)
  - Each with total in center

- **Student detail (bottom, appears on click):**
  - Expanded card: Name, all attributes, mini grade sparkline (from assignments), recent office hours visits
  - Close button to collapse

---

### Page 2: Assignment Tracker
**Sidebar label:** "Assignments"
**Component:** `src/pages/AssignmentTracker.tsx`

Assignment submission and grade analysis — calendar + swarm visualization.

- **Submission calendar (top, full width, 200px tall):**
  - Month-view calendar (current month)
  - Each day cell shows colored dots for submissions due/received that day:
    - Green dot = On Time submission
    - Orange dot = Late submission
    - Red dot = Missing (past due, no submission)
  - Day cells with many dots are visually denser
  - Click a day to filter the table below to that day's assignments

- **Grade distribution swarm/beeswarm (middle, full width, 300px tall):**
  - X axis: Score (0–100)
  - Y axis: jittered (beeswarm) to avoid overlap
  - One dot per assignment
  - Dot color by type (Exam=indigo, Project=teal, Quiz=amber, Essay=pink, Lab=green, Presentation=purple)
  - Vertical reference lines at 60 (passing), 80 (good), 90 (excellent)
  - Filter by assignment type using legend toggle below

- **Submission table (bottom, collapsible):**
  - Filter: Student search, Course code, Type dropdown, Late filter (All/On Time/Late/Missing)
  - Columns: Student, Course, Assignment, Type (badge), Score/Max (with fill bar), Submitted, Due Date, Status (On Time=green, Late=orange, Missing=red badge), Weight %
  - Sorted by due_date descending by default
  - Export: Excel button

---

### Page 3: Risk Radar
**Sidebar label:** "Risk Radar"
**Component:** `src/pages/RiskRadar.tsx`

Early warning system for at-risk students. Radar/polar visualization + actionable card list.

- **Risk radar chart (main visual, centered, 450px diameter):**
  - Polar/radar with 5 axes representing risk indicators:
    - GPA (inverted: lower GPA = farther from center = higher risk)
    - LMS Engagement (last_login_days inverted)
    - Assignment Completion (% not Missing)
    - Office Hours Visits (count, more = lower risk)
    - Credit Load (credits_enrolled vs expected for year)
  - One polygon per risk_level group (average for On Track, Watch, At Risk, Critical)
  - 4 overlapping polygons in different colors (green/amber/orange/red)
  - Shows the "risk shape" — which factors contribute most to risk

- **Risk factor breakdown (below radar, 5 horizontal bars):**
  - One bar per risk axis
  - Shows distribution: what % of At Risk/Critical students are failing on each axis
  - Helps identify: "Is it mostly GPA? Or disengagement?"

- **At-risk student cards (below, scrollable grid):**
  - Only students where risk_level = "At Risk" or "Critical"
  - Card layout (3 per row):
    - Student name + program badge
    - GPA (large, colored red/orange)
    - Risk factors: icons for each failing axis (e.g., 📵 if last_login >14, 📉 if GPA <2.0, ❌ if Missing assignments >2)
    - Last LMS login (relative date, red if >14 days)
    - Suggested intervention (auto-generated text: "Schedule advisor meeting" / "Tutoring referral" / "Check-in call")
    - "Take Action" button (shows toast notification)

- **Trend sparklines (bottom):** Mini line charts showing At Risk count per week over last 8 weeks — is it growing or shrinking?

---

### Page 4: Office Hours
**Sidebar label:** "Office Hours"
**Component:** `src/pages/OfficeHours.tsx`

Office hours management — schedule-style layout with outcomes tracking.

- **Advisor selector (top):** Pill buttons for each advisor name. Shows their meeting count.

- **Schedule view (main, full width, time-slot based):**
  - Vertical day columns (Mon–Fri, current week)
  - Time slots stacked (9:00 AM – 5:00 PM in 30-min blocks)
  - Meeting blocks color-coded by topic (Academic Plan=blue, Grade Concern=orange, Career=purple, Personal=pink, Registration=gray, Research=green)
  - Block content: student name (truncated), duration
  - Gaps shown as available slots (light dashed border)
  - Click a block to see detail

- **Outcome tracker (right panel, 280px):**
  - Stacked horizontal bar: % of meetings by outcome (Resolved=green, Action Plan=blue, Referral=purple, Follow-up=amber, No Show=red)
  - "No Shows this week" count with warning if >3
  - "Follow-ups pending" count

- **Meeting detail (expandable on click):**
  - Student name + risk badge
  - Topic, Duration, Notes
  - Outcome badge
  - Link to student card

- **Topic trends (bottom, small chart):**
  - Horizontal bar chart: topic frequency over last month
  - Reveals what students are most commonly asking about

---

### Page 5: Advisor AI
**Sidebar label:** "Advisor AI"
**Component:** `src/pages/AdvisorAi.tsx`

AI academic advisor — warm, encouraging, mentor-like tone.

**Layout:** Full-width centered chat (max-width 760px) with a student spotlight panel that appears contextually.

**Chat interface:**
- Sky blue AI bubbles, light gray user bubbles
- Welcome message: "👋 Hi! I'm your Academic Advisor AI. I can help identify students who need support, analyze assignment patterns, or suggest interventions. What would you like to explore?"
- AI can render: student cards, grade tables, risk indicators, and progress bars inline
- Input placeholder: "Ask about students, assignments, office hours, or academic trends…"

**Suggestion chips (2 rows, scrollable):**
Row 1:
- "Who needs immediate attention?"
- "Show me students who stopped logging in"
- "Which courses have the most missing assignments?"

Row 2:
- "Draft an outreach email for disengaged students"
- "Compare program GPAs this semester"
- "What interventions have worked best?"

**Student spotlight (slides in from right when AI discusses a specific student):**
- Name, program, year
- GPA gauge (0–4.0 scale)
- Risk level badge
- Recent assignments (last 3 with scores)
- Office hours history (count + last visit date)
- Disappears when conversation moves to aggregate topics

**AI persona:**
System context: "You are an empathetic academic advisor AI supporting student success. You have access to student records, assignment submissions, and office hours data. Your goal is to help advisors proactively support struggling students. When identifying at-risk students, be constructive — focus on what can be done, not what went wrong. Suggest specific interventions (tutoring, schedule adjustment, advisor meeting, peer mentoring). Use encouraging language. For aggregate questions, provide specific numbers and trends. When a student is discussed, highlight their strengths alongside concerns. Never be punitive — every student can improve with the right support."

---

### Page 6: Academic Analytics
**Sidebar label:** "Analytics"
**Component:** `src/pages/AcademicAnalytics.tsx`

Advanced academic analytics — visual deep-dive into student outcomes and institutional health.

- **Radar/spider chart (top-left, 380px):**
  - Student wellness assessment across 6 dimensions: Academic (GPA), Attendance, Engagement, Social (office hours), Financial Aid Status, Course Load Balance
  - Show average profile for each risk_level (Low/Medium/High)
  - Three overlapping polygons with legend

- **Sunburst chart (top-right, 380px):**
  - Course enrollment hierarchy: School (inner) → Department (middle) → Course (outer)
  - Sized by enrollment count
  - Color by average GPA of enrolled students (green=high, red=low)

- **Box plot (middle-left, 320px):**
  - GPA distribution by department
  - One box per department showing median, Q1, Q3, whiskers
  - Highlight departments with median below 2.5
  - Overlay: overall university median line

- **Funnel chart (middle-right, 320px):**
  - Student retention funnel: Enrolled Year 1 (100%) → Returned Year 2 → Year 3 → Year 4 → Graduated
  - Show attrition % at each stage
  - Compare: At-Risk cohort vs General cohort (two funnels side by side)

- **Histogram (bottom-left, 300px):**
  - Grade distribution across all assignments
  - Bins: A (90–100), B (80–89), C (70–79), D (60–69), F (<60)
  - Color per grade band (green→yellow→orange→red)
  - Overlay: "expected" normal distribution curve

- **Polar chart (bottom-right, 300px):**
  - Office hours visits by day of week (7 petals: Mon–Sun)
  - Sized by visit count
  - Color by average outcome (Resolved=green, Follow-up needed=amber)
  - Shows which days advisors are most impactful

---

## Behavior notes

1. **Visual-first** — the waffle grid, beeswarm, radar, and schedule ARE the pages. Tables are secondary/collapsible.
2. **Approachable** — rounded corners, emoji accents in alerts, friendly color palette. Not a corporate tool.
3. **Risk without alarm** — use amber/orange gradients rather than harsh red for most indicators. Red only for Critical.
4. **No maps** — geographic data isn't relevant here. Spatial layouts are the schedule view and mosaic grid.
5. **Beeswarm is unique** — tests the pipeline's ability to generate non-standard D3 visualizations.
6. **Calendar as navigation** — the assignment calendar and office hours schedule drive interaction, not filter dropdowns.
