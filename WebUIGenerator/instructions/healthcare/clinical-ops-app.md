# MedFlow — Clinical Operations & Patient Flow Intelligence

## App Overview

**App name:** clinical-ops
**Theme:** Healthcare operations — clean, clinical, high-contrast, information-dense
**Accent color:** #0891B2 (cyan/teal — clinical, calm)
**Secondary accent:** #DC2626 (red — reserved ONLY for critical/life-safety alerts)
**Style:** Light mode, high contrast, large readable fonts, dense layouts. Functional over pretty. Designed for charge nurses on 12-hour shifts staring at screens.

---

## Data Model

### Table: patients
| Column | Type | Description |
|--------|------|-------------|
| id | integer | Auto PK |
| patient_id | text | Unique ID (PAT-XXXXX format) |
| name | text | Full name (synthetic) |
| age | integer | 18–95 |
| gender | categorical | Male, Female, Other |
| unit | categorical | Emergency, ICU, Cardiac, Ortho, Neuro, General, Peds, Oncology |
| admission_date | text | YYYY-MM-DD (last 45 days) |
| status | categorical | Admitted, In Treatment, Observation, Ready for Discharge, Discharged, Transferred |
| acuity | categorical | Critical, Urgent, Standard, Low |
| attending | text | Doctor name |
| bed_id | text | Bed identifier (e.g., "ICU-04", "GEN-12A") |
| los_days | integer | Length of stay (0–40) |
| readmission | categorical | Yes, No |
| insurance | categorical | Private, Medicare, Medicaid, Self-Pay, VA |
| next_action | text | What happens next (e.g., "CT scan at 14:00", "Discharge pending pharmacy", "Consult cardiology") |

**Seed rows:** 65
**Seed notes:** 30% Discharged, 25% In Treatment, 20% Admitted, 12% Observation, 8% Ready for Discharge, 5% Transferred. ICU = higher acuity. LOS: Critical avg 12d, Standard avg 3d. Readmission ~15%.

### Table: bed_board
| Column | Type | Description |
|--------|------|-------------|
| id | integer | Auto PK |
| unit | categorical | Same as patients.unit |
| bed_id | text | Unique bed identifier |
| status | categorical | Occupied, Clean Available, Dirty, Blocked, Maintenance |
| patient_id | text | References patients.patient_id or null if empty |
| patient_name | text | Patient name or null |
| acuity | categorical | Critical, Urgent, Standard, Low, or null if empty |
| admit_date | text | YYYY-MM-DD or null |
| expected_discharge | text | YYYY-MM-DD or null |
| isolation | categorical | None, Contact, Droplet, Airborne, Protective |
| equipment | text | Special equipment needed (e.g., "Ventilator", "Cardiac Monitor", "None") |

**Seed rows:** 80
**Seed notes:** Distribute beds per unit: ICU 16, Emergency 24, General 20, Cardiac 8, Ortho 6, Neuro 4, Peds 2. About 75% Occupied, 10% Clean Available, 8% Dirty, 5% Blocked, 2% Maintenance. Isolation: 15% Contact, 5% Droplet, 3% Airborne, rest None.

### Table: handoff_notes
| Column | Type | Description |
|--------|------|-------------|
| id | integer | Auto PK |
| patient_id | text | References patients.patient_id |
| patient_name | text | Patient name |
| unit | categorical | Same units |
| shift_from | categorical | Day (7A-7P), Night (7P-7A) |
| shift_to | categorical | Day (7A-7P), Night (7P-7A) |
| date | text | YYYY-MM-DD (last 7 days) |
| nurse_from | text | Outgoing nurse name |
| nurse_to | text | Incoming nurse name |
| summary | text | Clinical summary (2-3 sentences about patient status) |
| concerns | text | Active concerns (e.g., "Blood pressure trending up", "Pain management inadequate") |
| tasks_pending | text | Outstanding tasks (e.g., "Labs at 06:00, PT eval pending, Family meeting 10:00") |
| priority | categorical | Routine, Watch Closely, Urgent Attention |

**Seed rows:** 50
**Seed notes:** Cover the last 7 days of shift changes. Critical/Urgent patients should have "Watch Closely" or "Urgent Attention" priority. Summaries should sound clinical but be synthetic. 8 nurse names rotating.

---

## Pages

Add 6 pages to the sidebar:
1. Bed Board
2. Patient Journey
3. Shift Handoff
4. Unit Capacity
5. Clinical AI
6. Unit Analytics

---

### Page 1: Bed Board
**Sidebar label:** "Bed Board"
**Component:** `src/pages/BedBoard.tsx`

Visual bed management board — the SPATIAL LAYOUT of the hospital floor. Think whiteboard that charge nurses use, digitized.

- **Unit selector (top tabs):** Tab for each unit (Emergency, ICU, Cardiac, etc.) + "All Units" tab.

- **Bed grid (main visual, full width):**
  For the selected unit, render a GRID of bed cells (arranged to mimic floor layout):
  - Each cell represents one bed
  - Cell dimensions ~120px × 80px
  - **Occupied beds:**
    - Patient initials (large, center)
    - Acuity stripe (left border color: Critical=red, Urgent=orange, Standard=teal, Low=green)
    - Bed ID (small, top-left)
    - LOS days (small badge, top-right)
    - Isolation icon if applicable (⚠️ Contact, 💨 Droplet, ☢️ Airborne, 🛡️ Protective)
    - Bottom strip: expected_discharge date or "No date"
  - **Empty beds:**
    - Clean Available: green dashed border, "Available" text
    - Dirty: yellow background, "Turnover" text
    - Blocked/Maintenance: gray striped background

  - Click an occupied bed → detail panel slides in from right

- **Bed detail panel (slides from right, 350px):**
  - Patient: name, age, gender, admission date, LOS
  - Attending physician
  - Next action (bold, teal)
  - Equipment list
  - Isolation protocol
  - Latest handoff note summary
  - "Ready for Discharge" toggle (visual only — shows toast)

- **Bottom stats bar:**
  - Unit occupancy: X / Y beds (with %)
  - Available now: count
  - Discharges today: count (where expected_discharge = today)
  - Dirty awaiting turnover: count

---

### Page 2: Patient Journey
**Sidebar label:** "Journeys"
**Component:** `src/pages/PatientJourney.tsx`

Patient flow visualization — Sankey/alluvial diagram showing how patients move through the system.

- **Sankey diagram (main visual, full width, 500px tall):**
  - Left nodes: Admission source (Emergency=40%, Direct Admit=35%, Transfer=15%, Observation=10%) — derive from unit + admission patterns
  - Middle nodes: Current unit (one per unit, sized by patient count)
  - Right nodes: Discharge destination (Home=50%, Ready for Discharge pending=20%, Transferred=10%, Still in Treatment=20%)
  - Flow width = patient count
  - Colors by acuity (Critical flows = red tint, Standard = teal tint)
  - Hover a flow to see: count, avg LOS for that path, readmission rate for that path

- **LOS distribution (below Sankey, left half):**
  - Violin plot or box plot — one per unit
  - Shows the spread of length-of-stay for each unit
  - Outliers marked as individual dots
  - Median line emphasized

- **Readmission panel (below, right half):**
  - Readmission rate by unit (horizontal bars)
  - Total readmissions count
  - List of readmitted patients: name, unit, original LOS, days between discharge and readmit
  - Flag if readmit within 7 days (red) vs 8–30 days (amber)

- **Filter (top):** Time range selector (Last 7 days / 14 days / 30 days / All) — affects which patients are included in the Sankey.

---

### Page 3: Shift Handoff
**Sidebar label:** "Handoff"
**Component:** `src/pages/ShiftHandoff.tsx`

Shift change communication board — structured handoff notes for incoming nurses. Card-based, prioritized.

- **Shift context bar (top):**
  - Current shift indicator: "Night → Day Handoff" or "Day → Night Handoff" (auto-detect based on time, or toggle)
  - Date selector (defaults to today/most recent)
  - Unit filter dropdown

- **Priority lanes (main content, 3 columns):**
  - **Column 1: Urgent Attention** (red header, red left border on cards)
  - **Column 2: Watch Closely** (amber header)
  - **Column 3: Routine** (teal header)

  Each column contains handoff cards sorted by priority:
  - **Card content:**
    - Patient name + bed_id (bold header)
    - Acuity badge
    - Clinical summary (2–3 lines)
    - **Concerns section** (orange highlight if present): active concerns text
    - **Pending tasks** (checklist style): tasks_pending as bullet points
    - Nurse from → Nurse to (small footer)
    - Isolation badge if applicable

- **Handoff completeness (right sidebar, 200px):**
  - Progress ring: X of Y patients have handoff notes for this shift
  - "Missing handoffs" list (patients in unit without a note for this shift change)
  - Nurse workload: cards per nurse (bar chart showing who has more patients)

- **Search + Filter (above columns):** Search by patient name, filter by nurse_to name.

---

### Page 4: Unit Capacity
**Sidebar label:** "Capacity"
**Component:** `src/pages/UnitCapacity.tsx`

Capacity planning view — forward-looking with discharge predictions.

- **Capacity timeline (main visual, full width, 400px, Gantt-style):**
  - X axis: next 7 days
  - Y axis: one row per unit
  - Each row shows a horizontal stacked bar:
    - Solid fill = currently occupied beds that will STILL be occupied (no expected discharge in that window)
    - Hatched fill = beds expected to free up (expected_discharge in that day range)
    - Open space = projected available beds
  - Today marker (vertical line)
  - Hover shows: unit, day, projected occupied, projected available

- **Today's snapshot (above timeline, 4 compact cards):**
  - Total Census (non-discharged patients)
  - Beds Available Now (Clean Available count)
  - Expected Discharges Today
  - Pending Admissions (count where status = "Admitted" and los_days = 0 — just arrived)

- **Bottleneck indicators (below timeline):**
  - Units projected to exceed 90% capacity in next 3 days (amber/red warning cards)
  - "ICU projected full by Wednesday — 2 expected discharges, 4 pending admits"
  - Suggested action: "Consider step-down transfers for stable ICU patients"

- **Turnover efficiency (bottom, 2 charts side-by-side):**
  - Left: Bar chart — avg hours from "Ready for Discharge" to actual bed available, per unit
  - Right: Stacked bar — bed status breakdown per unit (Occupied / Clean / Dirty / Blocked)

---

### Page 5: Clinical AI
**Sidebar label:** "Clinical AI"
**Component:** `src/pages/ClinicalAi.tsx`

AI operations assistant — precise, clinical, operational focus (NOT medical advice).

**Layout:** Chat (55% width) + live status strip (45% width, vertical).

**Chat panel (left, 55%):**
- White background, teal accent borders on AI messages
- Professional clinical tone — no emoji, no casual language
- AI responses include formatted patient lists, capacity tables, and task summaries
- Input placeholder: "Ask about bed capacity, patient flow, staffing, or handoff notes…"

**Suggestion chips:**
- "What's the bed situation right now?"
- "Show me patients with LOS over 10 days"
- "Who's ready for discharge but still here?"
- "Summarize tonight's handoff priorities"
- "Which units will hit capacity this week?"
- "List patients needing isolation beds"

**Live status strip (right, 45%):**
- **Census gauge:** Large circular — total occupied / total beds
- **By-unit mini bars:** One row per unit showing occupancy bar (colored by threshold)
- **Alerts section:** 
  - Beds at capacity (red)
  - Dirty beds > 30 min (amber)
  - Missing handoff notes (amber)
- **Discharges today:** Count + patient names
- Strip scrolls independently of chat

**AI persona:**
System context: "You are a clinical operations AI supporting charge nurses and hospital administrators. You have access to bed board data, patient census, handoff notes, and capacity projections. Be precise and concise — nursing teams need facts fast. When reporting capacity, always state: current census, available beds, expected discharges, and pending admits. For handoff questions, summarize by priority level. Suggest operational actions (expedite discharges, activate housekeeping, redistribute load) when bottlenecks exist. NEVER provide medical advice, diagnoses, or treatment recommendations — operational decisions only. Use clinical terminology: census, LOS, acuity, throughput, turnover time."

---

### Page 6: Unit Analytics
**Sidebar label:** "Analytics"
**Component:** `src/pages/UnitAnalytics.tsx`

Advanced clinical analytics — visual deep-dive into hospital operations and patient flow.

- **Sankey diagram (top, full width, 400px):**
  - Patient flow: Admission Source (ER, Scheduled, Transfer) → Unit (ICU, Cardiac, General, etc.) → Outcome (Discharged, Transferred, Readmitted)
  - Link thickness proportional to patient count
  - Color by acuity level

- **Gauge chart row (3 gauges, below Sankey):**
  - Overall Bed Occupancy Rate (target: 85%, danger >95%)
  - ICU Utilization (target: 80%, danger >90%)
  - Average LOS vs Target (gauge shows ratio)
  - Color: green <80%, amber 80–90%, red >90%

- **Box plot (middle-left, 350px):**
  - Length of Stay distribution by unit
  - One box per unit (ICU, Cardiac, General, Ortho, etc.)
  - Shows median, quartiles, outliers
  - Highlight units where median LOS exceeds benchmark

- **Polar/rose chart (middle-right, 350px):**
  - Admissions by hour of day (24 petals)
  - Sized by admission count at that hour
  - Color intensity by average acuity at that hour
  - Helps identify peak admission windows

- **Funnel chart (bottom-left, 300px):**
  - Patient journey funnel: Admitted (100%) → Stabilized → Treatment Plan → Recovery → Discharge Ready → Discharged
  - Show conversion rates between stages
  - Highlight where patients "get stuck" (longest stage)

- **Histogram (bottom-right, 300px):**
  - LOS distribution across all patients (bins: 0–2d, 2–5d, 5–10d, 10–20d, 20+d)
  - Overlay: benchmark distribution line
  - Color by readmission risk

---

## Behavior notes

1. **Spatial bed board** — the grid IS the hospital floor. This is the core differentiator. Not a table.
2. **Priority-driven handoff** — the 3-column priority layout mimics how charge nurses actually think about shift change.
3. **Clinical density** — pack information tight. Nurses scan, they don't browse. No decorative whitespace.
4. **Red = life safety only** — never use red for "bad metric." Red means someone might die. Use amber for most warnings.
5. **Sankey for flow** — tests the pipeline's ability to generate complex D3 Sankey diagrams.
6. **No maps** — hospital operations are spatial (bed board) but not geographic.
7. **Forward-looking** — the capacity timeline is PREDICTIVE, not just current state. That's what makes it useful.
