# Sports Analytics — Phase 2: Match Analysis

**UI Mode:**
- 🟡 **Rebuild Wireframe** — if a stub screen with this name already exists on the canvas
- 🟢 **Add Screens** — if adding to an existing canvas without stubs (places new frames to the right)
**Canvas:** 1440×900 desktop

> **Prerequisite:** Run Phase 1 (`03_sports_phase1_overview_stats.md`) first. Team Overview and Player Stats screens must already exist on the canvas.

Add the Match Analysis screen to complete the dashboard. Then run `figma_wire_all` to connect all sidebar navigation across all three screens.

---

## Screen: Match Analysis

### Layout
- Same sidebar (220px), active: **Match Analysis**
- Header: "Match Analysis", match picker dropdown "vs. Riverside FC (Jun 18)" — name `dropdown-Match-on-MatchAnalysis` — options: vs. Riverside FC (Jun 18), vs. City United (Jun 11), vs. North Athletic (Jun 4), vs. East FC (May 28)

### Content sections (top → bottom)

**Match result banner** — large card (full width, 120px):
- Left: "FC Analytics" text + score "3 — 1" (large, bold) + "Riverside FC" text
- Scorers row: "Marcos Silva 22', Luis García 58', Dani Perez 87' | Riverside: Kowalski 71'"

**Two-column row**:

Left column — **Stats comparison bars**:
- Label "Possession" — two side-by-side rectangles: Home 62% (width 372px, accent `#f59e0b`) + Away 38% (width 228px, muted `#4b5563`)
- Same pattern for: Shots on Target (8 vs 3), Corners (6 vs 2), Fouls (9 vs 14)

Right column — **Bar chart** (5 bars) — "Shots by Player":
- Players: L.García 5, M.Silva 4, Y.Tanaka 3, B.Owusu 2, D.Perez 2
- Bar heights: 160, 128, 96, 64, 64 px — accent color

**Timeline** — "Match Events" (8 rows, vertical list):
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

---

## Overlays to create

| Frame name | Size | Content |
|------------|------|---------|
| `match-picker-modal` | 260×220 | 4 match rows: date + opponent + score (e.g. "Jun 18 — vs. Riverside FC — 3–1") |
| `event-detail-modal` | 400×300 | Title "Goal — 22'", Player: Marcos Silva, description, video placeholder rectangle (320×180, fill `#1a2235`, label "Video Replay"), Close button |

---

## Wiring

| Source element | Interaction | Destination |
|----------------|-------------|-------------|
| Sidebar: "Team Overview" | Navigate | Team Overview screen |
| Sidebar: "Player Stats" | Navigate | Player Stats screen |
| `dropdown-Match-on-MatchAnalysis` | Overlay | `match-picker-modal` |
| Timeline row 1 (Goal — Marcos Silva 22') | Overlay | `event-detail-modal` |

After building the screen and overlays, call `figma_wire_all` to connect all sidebar navigation across Team Overview, Player Stats, and Match Analysis.
