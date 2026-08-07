# Sports Analytics — Phase 1: Team Overview & Player Stats

**UI Mode:** 🟢 **Build Wireframe**
**Canvas:** 1440×900 desktop

> ⚠️ **STRICT PHASE SCOPE — build ONLY these 7 frames, nothing else:**
> - Screen: `Team Overview`
> - Screen: `Player Stats`
> - Overlay: `season-picker-modal`
> - Overlay: `export-modal`
> - Overlay: `player-detail-modal`
> - Overlay: `player-search-modal`
> - Overlay: `position-filter-modal`
>
> Do NOT create Match Analysis or any other screen. Leave `tab-MatchAnalysis-on-TeamOverview` and `tab-MatchAnalysis-on-PlayerStats` **unwired** — they will be connected in Phase 2. The QA pass must NOT flag that missing navigation target as an error.

Build the first two screens of a dark sports analytics dashboard for a football (soccer) club.

**Theme:** Dark stadium — bg `#0a0e1a`, sidebar `#111827`, cards `#1a2235`, accent `#f59e0b`, text `#f9fafb`, muted `#9ca3af`, success `#10b981`, danger `#ef4444`.

---

## Screen 1: Team Overview

### Layout
- Left sidebar (220px), dark bg `#111827`: club badge (amber circle 40px), "FC Analytics" wordmark, nav items: **Team Overview** (active), Player Stats, Match Analysis
- Top bar: season picker dropdown "2024/25" — name `dropdown-Season-on-TeamOverview` — options: 2024/25, 2023/24, 2022/23; "Export Report" ghost button (top right)

### Content sections (top → bottom)

**Season summary KPI row** — 5 cards:
| Card | Value | Note |
|------|-------|-------|
| Points | 72 | 3rd place |
| Wins | 22 | Out of 34 played |
| Goals Scored | 68 | 2.0 per game |
| Goals Conceded | 31 | 0.91 per game |
| Clean Sheets | 14 | League best |

**Bar chart** (drawn with rectangles, 6 bars) — title "Points Per Month":
- Months: Aug, Sep, Oct, Nov, Dec, Jan
- Bar heights: 80, 110, 100, 90, 130, 120 px (max 140px) — accent color `#f59e0b`

**Two-column row** (below bar chart):
- Left column: Bar chart (5 horizontal bars) — "Top Scorers": Marcos Silva 18, Luis García 14, Yuki Tanaka 9, Ben Owusu 8, Dani Perez 6; bar heights 180, 140, 90, 80, 60 px
- Right column: Formation card — rectangle 360×340, fill `#1a2235`, amber border; "4-3-3 Formation" title; dot grid with 11 labeled player position circles

---

## Screen 2: Player Stats

### Layout
- Same sidebar, active: **Player Stats**
- Header: "Player Statistics", search bar `search-btn-PlayerStats` (placeholder "Search player…"), filter dropdown `dropdown-Position-on-PlayerStats` — options: All, Forward, Midfielder, Defender, Goalkeeper

### Content sections (top → bottom)

**Player table** — 10 rows:
| # | Name | Position | Matches | Goals | Assists | Passes % | Rating |
|---|------|----------|---------|-------|---------|----------|--------|
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

---

## Overlays to create

| Frame name | Size | Content |
|------------|------|---------|
| `season-picker-modal` | 160×180 | 3 option rows: 2024/25, 2023/24, 2022/23 |
| `export-modal` | 400×200 | Title "Export Report", "Download as PDF" + "Download as CSV" buttons, Cancel |
| `player-detail-modal` | 520×580 | Title "Marcos Silva", position badge "Forward", stats grid: Goals 18, Assists 6, Matches 28, Rating 8.4; form bar chart (5 bars for last 5 matches), Close button |
| `player-search-modal` | 560×380 | Title "Player Search Results", 4 player rows (name, position, goals, rating), Close button |
| `position-filter-modal` | 160×200 | 5 option rows: All, Forward, Midfielder, Defender, Goalkeeper |

---

## Wiring

After ALL seven frames are built, call `figma_list_frame_nodes` on both screens to confirm node names, then wire in a single call:

```
figma_wire_all(
  links=[
    {"source_frame": "Team Overview",  "source_node": "dropdown-Season-on-TeamOverview", "target_frame": "season-picker-modal",   "type": "OVERLAY"},
    {"source_frame": "Team Overview",  "source_node": "export-btn-TeamOverview",         "target_frame": "export-modal",          "type": "OVERLAY"},
    {"source_frame": "Team Overview",  "source_node": "bar1-btn-TeamOverview",           "target_frame": "player-detail-modal",   "type": "OVERLAY"},
    {"source_frame": "Team Overview",  "source_node": "tab-PlayerStats-on-TeamOverview", "target_frame": "Player Stats",          "type": "NAVIGATE"},
    {"source_frame": "Player Stats",   "source_node": "search-btn-PlayerStats",         "target_frame": "player-search-modal",   "type": "OVERLAY"},
    {"source_frame": "Player Stats",   "source_node": "dropdown-Position-on-PlayerStats","target_frame": "position-filter-modal", "type": "OVERLAY"},
    {"source_frame": "Player Stats",   "source_node": "row1-btn-PlayerStats",            "target_frame": "player-detail-modal",   "type": "OVERLAY"},
    {"source_frame": "Player Stats",   "source_node": "row2-btn-PlayerStats",            "target_frame": "player-detail-modal",   "type": "OVERLAY"},
    {"source_frame": "Player Stats",   "source_node": "tab-TeamOverview-on-PlayerStats", "target_frame": "Team Overview",         "type": "NAVIGATE"},
  ],
  start_frame="Team Overview"
)
```

**Do NOT** wire `tab-MatchAnalysis-on-TeamOverview` or `tab-MatchAnalysis-on-PlayerStats` — that screen doesn't exist yet.

---

## Prototype start
Handled by `start_frame="Team Overview"` in the `figma_wire_all` call above.

## Prototype start
Set **Team Overview** as the prototype start frame.
