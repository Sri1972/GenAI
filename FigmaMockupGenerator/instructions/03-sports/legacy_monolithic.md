Create a 3-screen sports analytics dashboard for a football (soccer) club at 1440×900.

**Theme:** Dark stadium — bg `#0a0e1a`, sidebar `#111827`, cards `#1a2235`, accent `#f59e0b`, text `#f9fafb`, muted `#9ca3af`, success `#10b981`, danger `#ef4444`.

---

## Screen 1 — Team Overview

### Layout
- Left sidebar (220px): club badge (circle, 40px, amber), "FC Analytics" wordmark, nav items: Team Overview, Player Stats, Match Analysis
- Top bar: season picker dropdown "2024/25" — name `dropdown-Season-on-TeamOverview` — options: 2024/25, 2023/24, 2022/23
- Right of header: "Export Report" ghost button

### Content sections (top → bottom)

**Season summary KPI row** — 5 cards:
| Card | Value | Note |
|------|-------|------|
| Points | 72 | 3rd place |
| Wins | 22 | Out of 34 played |
| Goals Scored | 68 | 2.0 per game |
| Goals Conceded | 31 | 0.91 per game |
| Clean Sheets | 14 | League best |

**Bar chart** (drawn with rectangles, 6 bars) — title "Points Per Month":
- Months: Aug, Sep, Oct, Nov, Dec, Jan
- Bar heights: 80, 110, 100, 90, 130, 120 px (max 140px)
- Bars in accent color `#f59e0b`
- Axis labels below bars

**Two-column row**:

Left column — **Bar chart** (5 bars) — "Top Scorers":
- Players: Marcos Silva 18, Luis García 14, Yuki Tanaka 9, Ben Owusu 8, Dani Perez 6
- Bar heights: 180, 140, 90, 80, 60 px (horizontal labels on y-axis)

Right column — **Formation card**:
- Rectangle 360×340, fill `#1a2235`, border `#f59e0b`
- Text "4-3-3 Formation" centered at top
- Dot grid representing player positions (use small filled circles via rectangles + text labels for names)

### Wiring
| Source element | Interaction | Destination |
|----------------|-------------|-------------|
| Sidebar: "Player Stats" | Navigate | Player Stats screen |
| Sidebar: "Match Analysis" | Navigate | Match Analysis screen |
| `dropdown-Season-on-TeamOverview` | Overlay | Season picker modal (160×180) — options: 2024/25, 2023/24, 2022/23 |
| "Export Report" button | Overlay | Export modal (400×200) — "Download as PDF / CSV" + Cancel button |
| Bar chart bar 1 (Marcos Silva) | Overlay | Player Detail modal (480×500) — player name, photo placeholder, stats: goals, assists, matches, avg rating, mini bar chart |

---

## Screen 2 — Player Stats

### Layout
- Same sidebar, active: Player Stats
- Header: "Player Statistics", search: `search-btn-PlayerStats` (placeholder "Search player…")
- Filter: `dropdown-Position-on-PlayerStats` — options: All, Forward, Midfielder, Defender, Goalkeeper

### Content sections

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

Below table: pagination row (Prev / 1 2 3 / Next).

### Wiring
| Source element | Interaction | Destination |
|----------------|-------------|-------------|
| Sidebar: "Team Overview" | Navigate | Team Overview screen |
| Sidebar: "Match Analysis" | Navigate | Match Analysis screen |
| `search-btn-PlayerStats` | Overlay | Player search modal (560×380) — search results list with 4 player rows: name, position, goals, rating; Close button |
| `dropdown-Position-on-PlayerStats` | Overlay | Position filter modal (160×200) — All, Forward, Midfielder, Defender, Goalkeeper |
| Table row 1 (Marcos Silva) | Overlay | Player Detail modal (520×580) — large name, position badge, stats grid (goals/assists/matches/rating), bar chart of form (5 bars for last 5 matches), Close button |
| Table row 2 (Luis García) | Overlay | Player Detail modal (same frame — 520×580) |

---

## Screen 3 — Match Analysis

### Layout
- Same sidebar, active: Match Analysis
- Header: "Match Analysis", match picker dropdown "vs. Riverside FC (Jun 18)" — name `dropdown-Match-on-MatchAnalysis` — options: vs. Riverside FC (Jun 18), vs. City United (Jun 11), vs. North Athletic (Jun 4), vs. East FC (May 28)

### Content sections

**Match result banner** — large card:
- Left: "FC Analytics" crest + score "3 — 1" + "Riverside FC" crest (placeholder circles)
- Scorers: Marcos Silva 22', Luis García 58', Dani Perez 87' | Riverside: Kowalski 71'

**Two-column row**:

Left column — **Possession bar** (drawn as two side-by-side rectangles, proportional):
- Label: "Possession" — Home 62%, Away 38%
- Home rectangle: width 372px, fill accent; Away rectangle: width 228px, fill muted
- Below: similar bars for Shots on Target (8 vs 3), Corners (6 vs 2), Fouls (9 vs 14)

Right column — **Bar chart** (drawn, 5 bars) — "Shots by Player":
- Players: L.García 5, M.Silva 4, Y.Tanaka 3, B.Owusu 2, D.Perez 2
- Bar heights: 160, 128, 96, 64, 64 px

**Timeline** — "Match Events" list (vertical, 8 rows):
| Time | Event | Player |
|------|-------|--------|
| 22' | ⚽ Goal | Marcos Silva |
| 36' | 🟡 Yellow Card | Kwame Asante |
| 45+2' | Half Time | — |
| 58' | ⚽ Goal | Luis García |
| 65' | 🔄 Substitution | Ben Owusu → Dani Perez |
| 71' | ⚽ Opponent Goal | Kowalski (Riverside) |
| 87' | ⚽ Goal | Dani Perez |
| 90' | Full Time | — |

### Wiring
| Source element | Interaction | Destination |
|----------------|-------------|-------------|
| Sidebar: "Team Overview" | Navigate | Team Overview screen |
| Sidebar: "Player Stats" | Navigate | Player Stats screen |
| `dropdown-Match-on-MatchAnalysis` | Overlay | Match picker modal (260×220) — 4 match rows (date + opponent + score) |
| Timeline row "Marcos Silva (Goal 22')" | Overlay | Event Detail modal (400×300) — time, player, event type, video placeholder rectangle (320×180), Close button |

---

## Overlay frames to create

| Frame name | Size | Purpose |
|------------|------|---------|
| `season-picker-modal` | 160×180 | Season selector |
| `export-modal` | 400×200 | Export confirmation |
| `player-detail-modal` | 520×580 | Individual player stats |
| `player-search-modal` | 560×380 | Player search results |
| `position-filter-modal` | 160×200 | Position filter options |
| `match-picker-modal` | 260×220 | Match selection list |
| `event-detail-modal` | 400×300 | Match event detail |

---

## Prototype start screen
Set **Team Overview** as the prototype start frame.
