# Sports Analytics — Full Build

**UI Mode:** 🟢 **New Wireframe**

Build a complete 3-screen sports analytics application for a football (soccer) club. Desktop layout, 1440×900.

> Do NOT apply Mobility Global branding. Use the custom dark color scheme below.

**Colors:** Background `#0a0e1a` · Sidebar `#111827` · Cards `#1a2235` · Accent `#f59e0b` · Text `#f9fafb` · Muted `#9ca3af`

---

## Screen 1: Team Overview

Left sidebar (220px, dark bg `#111827`): club badge (amber circle 40px), "FC Analytics" wordmark, navigation: **Team Overview** (active), Player Stats, Match Analysis.
Header: season picker dropdown "2024/25" (options: 2024/25, 2023/24, 2022/23), "Export Report" ghost button (top right).

**5 KPI cards:**

| Metric | Value | Note |
|--------|-------|------|
| Points | 72 | 3rd place |
| Wins | 22 | Out of 34 played |
| Goals Scored | 68 | 2.0 per game |
| Goals Conceded | 31 | 0.91 per game |
| Clean Sheets | 14 | League best |

**Bar chart** "Points Per Month" — 6 bars (Aug–Jan): 80, 110, 100, 90, 130, 120px. Amber bars.

**Two-column row:**
- Left: horizontal bar chart "Top Scorers" — 5 players: Marcos Silva 18, Luis García 14, Yuki Tanaka 9, Ben Owusu 8, Dani Perez 6. Bars: 180, 140, 90, 80, 60px.
- Right: Formation card (360×340, dark bg, amber border). "4-3-3 Formation" title. Dot grid with 11 labeled player position circles.

**What opens what:**
- Season picker dropdown → opens season selector modal
- "Export Report" button → opens export modal
- Clicking bar 1 in Top Scorers (Marcos Silva) → opens player detail modal

---

## Screen 2: Player Stats

Left sidebar: Team Overview, **Player Stats** (active), Match Analysis.
Header: "Player Statistics", search field (placeholder "Search player…"), position filter dropdown (All/Forward/Midfielder/Defender/Goalkeeper).

**Player table — 10 rows:**

| # | Name | Position | Matches | Goals | Assists | Pass % | Rating |
|---|------|----------|---------|-------|---------|--------|--------|
| 9 | Marcos Silva | Forward | 28 | 18 | 6 | 78% | 8.4 |
| 10 | Luis García | Forward | 30 | 14 | 9 | 82% | 8.2 |
| 7 | Yuki Tanaka | Midfielder | 32 | 9 | 12 | 88% | 8.1 |
| 11 | Ben Owusu | Forward | 27 | 8 | 4 | 75% | 7.9 |
| 8 | Dani Perez | Midfielder | 31 | 6 | 14 | 91% | 8.3 |
| 6 | Kwame Asante | Midfielder | 29 | 2 | 8 | 90% | 7.7 |
| 5 | Tomás Novak | Defender | 33 | 1 | 3 | 89% | 7.8 |
| 4 | Ahmed Rashid | Defender | 30 | 0 | 2 | 93% | 7.6 |
| 3 | Luca Romano | Defender | 26 | 0 | 1 | 87% | 7.4 |
| 1 | Felix Brandt | Goalkeeper | 34 | 0 | 0 | 95% | 8.0 |

Pagination row below table: Prev / 1 2 3 / Next.

**What opens what:**
- Search field → opens player search modal
- Position dropdown → opens position filter modal
- Clicking row 1 (Marcos Silva) → opens player detail modal
- Clicking row 2 (Luis García) → opens player detail modal (same frame)

---

## Screen 3: Match Analysis

Left sidebar: Team Overview, Player Stats, **Match Analysis** (active).
Header: "Match Analysis", match picker dropdown "vs. Riverside FC (Jun 18)" (options: vs. Riverside FC (Jun 18), vs. City United (Jun 11), vs. North Athletic (Jun 4), vs. East FC (May 28)).

**Match result banner** — large card (full width):
- Score: "FC Analytics  3 — 1  Riverside FC"
- Scorers: "Marcos Silva 22', Luis García 58', Dani Perez 87' | Riverside: Kowalski 71'"

**Two-column row:**
- Left: Possession comparison bars — "Possession" Home 62% / Away 38%, "Shots on Target" 8/3, "Corners" 6/2, "Fouls" 9/14. Each stat shown as two proportional rectangles side by side.
- Right: Bar chart "Shots by Player" — 5 bars: L.García 5, M.Silva 4, Y.Tanaka 3, B.Owusu 2, D.Perez 2. Heights: 160, 128, 96, 64, 64px.

**Match Events timeline** — 8 rows:

| Time | Event | Player |
|------|-------|--------|
| 22' | Goal | Marcos Silva |
| 36' | Yellow Card | Kwame Asante |
| 45+2' | Half Time | — |
| 58' | Goal | Luis García |
| 65' | Substitution | Ben Owusu → Dani Perez |
| 71' | Opponent Goal | Kowalski (Riverside) |
| 87' | Goal | Dani Perez |
| 90' | Full Time | — |

**What opens what:**
- Match picker dropdown → opens match selector modal
- Clicking event row 1 (Goal — Marcos Silva 22') → opens event detail modal

---

## Modals

### Season selector modal — 160×180
3 options: 2024/25, 2023/24, 2022/23.

### Export modal — 400×200
Title "Export Report". "Download as PDF" button (primary). "Download as CSV" button (secondary). Cancel link.

### Player detail modal — 520×580
Title "Marcos Silva". Position badge "Forward". Stats grid: Goals 18, Assists 6, Matches 28, Rating 8.4. Form bar chart (5 bars for last 5 matches, amber). Close button.

### Player search modal — 560×380
Title "Player Search Results". 4 player rows showing name, position, goals, rating. Close button.

### Position filter modal — 160×200
5 options: All, Forward, Midfielder, Defender, Goalkeeper.

### Match selector modal — 260×220
4 match rows showing date, opponent, and score. E.g. "Jun 18 — vs. Riverside FC — 3–1".

### Event detail modal — 400×300
Title "Goal — 22'". Player name, event type. Video replay placeholder rectangle (320×180). Close button.

---

## Prototype start
Set **Team Overview** as the prototype start screen.
