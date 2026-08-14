# RetailNerve — Store Operations Command Center

## App Overview

**App name:** store-ops
**Theme:** Vibrant retail operations — warm, energetic, card-heavy
**Accent color:** #F59E0B (amber — retail energy, urgency)
**Secondary accent:** #7C3AED (purple — premium/loyalty)
**Style:** Light mode with bold section headers, rounded corners (12px), playful but professional

---

## Data Model

### Table: stores
| Column | Type | Description |
|--------|------|-------------|
| id | integer | Auto PK |
| store_code | text | Unique store ID (STR-001 format) |
| name | text | Store name (e.g., "Downtown Flagship", "Airport Express") |
| city | text | City name |
| state | text | US state abbreviation |
| format | categorical | Flagship, Standard, Express, Outlet, Pop-up |
| sqft | integer | Store square footage (600–45000) |
| employees | integer | Headcount (3–120) |
| open_date | text | YYYY-MM-DD (stores opened 2016–2024) |
| status | categorical | Open, Renovating, Seasonal Close |
| rating | numeric | Customer satisfaction 1.0–5.0 |

**Seed rows:** 30
**Seed notes:** Mix of formats — 3 Flagships, 12 Standard, 8 Express, 4 Outlet, 3 Pop-up. Express stores small (600–2500 sqft), Flagships large (20000–45000 sqft). Pop-ups newest (2023–2024).

### Table: hourly_metrics
| Column | Type | Description |
|--------|------|-------------|
| id | integer | Auto PK |
| store_code | text | References stores.store_code |
| hour | text | HH:00 format (08:00 to 21:00) |
| date | text | YYYY-MM-DD (today and yesterday only) |
| foot_traffic | integer | Visitors that hour (0–300) |
| transactions | integer | Completed sales (0–80) |
| revenue | numeric | Revenue that hour in USD (0–15000) |
| avg_basket | numeric | Average basket size USD (15–180) |
| staff_on_floor | integer | Employees working (1–15) |
| queue_wait_min | numeric | Average checkout wait in minutes (0–12) |

**Seed rows:** 150
**Seed notes:** Cover all 30 stores for today (14 hours each = too many — just cover 10 stores × 14 hours + a few others). Traffic peaks at 12:00–14:00 and 17:00–19:00. Morning slow. Revenue correlates with traffic. Flagships have 5–15 staff, Express 1–3.

### Table: promotions
| Column | Type | Description |
|--------|------|-------------|
| id | integer | Auto PK |
| promo_code | text | Promotion code (e.g., "SUMMER25", "FLASH50") |
| name | text | Promotion name (e.g., "Summer Clearance", "Flash Friday") |
| type | categorical | Percentage Off, BOGO, Bundle, Free Shipping, Loyalty Bonus |
| discount_pct | integer | Discount percentage (10–60) |
| start_date | text | YYYY-MM-DD |
| end_date | text | YYYY-MM-DD |
| status | categorical | Scheduled, Active, Ended, Paused |
| channel | categorical | In-Store Only, Online Only, Omnichannel |
| redemptions | integer | Number of times used (0–2500) |
| revenue_attributed | numeric | Revenue from this promo ($0–$180000) |
| target_segment | categorical | All Customers, Loyalty Members, New Customers, Lapsed, VIP |

**Seed rows:** 18
**Seed notes:** Mix of Active (5), Ended (8), Scheduled (3), Paused (2). Active promos should have higher redemptions. Ended promos have full revenue_attributed data. Scheduled promos have 0 redemptions.

---

## Pages

Add 5 pages to the sidebar:
1. Live Floor
2. Hourly Pulse
3. Promo War Room
4. Store Cards
5. Ask RetailBot

---

### Page 1: Live Floor
**Sidebar label:** "Live Floor"
**Component:** `src/pages/LiveFloor.tsx`

Real-time store floor visualization — a GRID LAYOUT representing the store network as a spatial arrangement. NOT a map, NOT a table.

- **Store grid (main content, full width):**
  A CSS grid of store "tiles" arranged in a 5×6 grid (or responsive). Each tile represents one store:
  - Store name (truncated)
  - Format icon (🏬 Flagship, 🏪 Standard, ⚡ Express, 🏷️ Outlet, 🎪 Pop-up)
  - LIVE metrics: current hour's foot_traffic and transactions (from hourly_metrics for the latest hour)
  - Background color pulse: Green if conversion rate (transactions/traffic) > 40%, amber 25–40%, red <25%
  - Small status dot: Open=green, Renovating=amber, Seasonal Close=gray
  - Tile size proportional to store format (Flagship=2×2, Standard=1×1, Express=1×0.5)

  Tiles should feel "alive" — like a NOC monitoring wall.

- **Live stats ticker (top strip):**
  - Network-wide right now: Total visitors this hour | Transactions this hour | Revenue this hour | Avg wait time

- **Alert panel (bottom, collapsible):**
  - Stores where queue_wait_min > 8 (⚠️ "High wait time at [store]")
  - Stores where staff_on_floor < 2 and foot_traffic > 50 (⚠️ "Understaffed at [store]")
  - Stores with 0 transactions in last hour (⚠️ "No sales at [store]")

---

### Page 2: Hourly Pulse
**Sidebar label:** "Hourly Pulse"
**Component:** `src/pages/HourlyPulse.tsx`

Time-of-day performance heatmap — reveals when each store peaks and troughs.

- **Store selector:** Multi-select chips to pick which stores to compare (default: top 5 by revenue).

- **Heatmap (main visual, full width, 500px tall):**
  - Rows = selected stores (store name)
  - Columns = hours (08:00 through 21:00, 14 columns)
  - Cell color = revenue (white→amber→deep orange gradient)
  - Cell text = transaction count
  - Hover tooltip: store, hour, revenue, traffic, conversion rate, staff count, wait time
  - Row totals on right edge (daily revenue)
  - Column totals on bottom edge (network total per hour)

- **Conversion funnel (below heatmap, 3 stages):**
  - Traffic → Transactions → Revenue per Transaction
  - Horizontal funnel showing drop-off at each stage
  - Numbers for today vs yesterday comparison

- **Staff efficiency scatter (bottom):**
  - X: staff_on_floor
  - Y: revenue per staff member (revenue / staff_on_floor)
  - One dot per store-hour combination (today)
  - Color by format
  - Reveals optimal staffing levels

---

### Page 3: Promo War Room
**Sidebar label:** "Promos"
**Component:** `src/pages/PromoWarRoom.tsx`

Promotion management with a calendar/timeline focus — NOT a table-first view.

- **Promo timeline (main visual, full width, Gantt-style):**
  - Horizontal timeline spanning last 60 days → next 30 days
  - Each promotion as a horizontal bar from start_date to end_date
  - Bar color by type: Percentage Off=amber, BOGO=purple, Bundle=teal, Free Shipping=blue, Loyalty Bonus=pink
  - Bar height/thickness by revenue_attributed (thicker = more successful)
  - Today marker (vertical dashed line)
  - Hover: full promo details

- **Active promos panel (right sidebar, 280px):**
  - Cards for each promo where status = "Active"
  - Card content: name, discount_pct (large bold number + "% OFF"), channel badge, target_segment, redemptions counter (animated number), revenue_attributed
  - Status toggle (Pause/Resume button — visual only, shows toast)

- **Performance comparison (below timeline):**
  - Grouped bar chart: one group per promo type
  - Bars: avg redemptions, avg revenue per promo
  - Helps identify which promo types work best

- **ROI leaderboard (bottom, simple ranked list):**
  - All ended promos ranked by revenue_attributed / discount_pct (efficiency score)
  - Medal icons: 🥇🥈🥉 for top 3
  - Show promo name, type, revenue, discount level

---

### Page 4: Store Cards
**Sidebar label:** "Stores"
**Component:** `src/pages/StoreCards.tsx`

Store directory as rich profile cards — NOT a data grid. Instagram-for-stores aesthetic.

- **Filter strip (top):** Format pill selector (All / Flagship / Standard / Express / Outlet / Pop-up) + Sort by dropdown (Rating / Revenue / Size / Newest)

- **Store cards (3-column responsive grid):**
  Each card has:
  - Header with gradient background (color varies by format: Flagship=purple gradient, Standard=amber, Express=teal, Outlet=gray, Pop-up=pink)
  - Store name (white text over gradient)
  - City, State
  - Format badge
  - **Stats section:**
    - ⭐ Rating (stars display)
    - 📐 Square footage (formatted with comma)
    - 👥 Employees
    - 📅 Open since (relative: "3 years ago")
  - **Today's performance strip (if hourly_metrics available):**
    - Revenue today (sum of hours), Visitors today, Conversion %
  - Status indicator at bottom (green strip = Open, amber = Renovating, gray = Closed)

- **Comparison mode:** Checkbox "Compare" on each card. When 2–3 are checked, a comparison panel slides up from bottom showing side-by-side stats.

---

### Page 5: Ask RetailBot
**Sidebar label:** "RetailBot"
**Component:** `src/pages/AskRetailBot.tsx`

Conversational AI with a friendly, action-oriented retail personality.

**Layout:** Centered chat (max-width 680px) with a floating quick-insights card.

**Chat interface:**
- White background, amber accent on AI avatar and message timestamps
- AI avatar: 🤖 with amber circle background
- AI messages can render: tables (for comparing stores), bullet lists, and small inline bar charts
- Conversational, uses contractions, occasionally uses retail slang ("Let's check the numbers", "Here's the play")
- Input placeholder: "Ask about store performance, promos, or staffing…"

**Quick insights card (floating, top-right, 220px wide, collapsible):**
- "Right Now" header
- Network revenue today (live-ish)
- Top performing store
- Biggest alert (if any)
- Active promos count

**Suggestion chips (above input, 2 rows):**
Row 1:
- "Which stores need more staff right now?"
- "How's the Summer Clearance promo doing?"
- "Compare Flagship vs Express conversion rates"

Row 2:
- "What drove revenue yesterday?"
- "Give me a morning briefing"
- "Which promo type should we run next?"

**AI persona:**
System context: "You are RetailBot, a sharp and friendly retail operations assistant. You know everything about our 30 stores — their hourly performance, staffing levels, promotions, and customer metrics. Be direct and action-oriented: if a store is understaffed, say so and suggest a fix. If a promo is underperforming, flag it. Use specific store names, numbers, and comparisons. Keep it concise — retail managers are busy. You can use tables to compare stores and bullet points for action items. Add urgency when warranted ('the Downtown Flagship needs attention — zero sales in the last hour')."

---

## Behavior notes

1. **Card-heavy, not table-heavy** — prefer rich cards and visual grids over traditional data tables.
2. **Warm palette** — amber primary, purple for premium/loyalty. White backgrounds with colored accents.
3. **Real-time feel** — "Live Floor" should feel like a monitoring tool, not a static report.
4. **Gantt for promos** — timeline visualization is the hero, not a boring table of promos.
5. **No maps** — this app deliberately avoids maps. The store grid IS the spatial view.
6. **Playful but professional** — emoji icons in tiles are OK, but the data/numbers must be crisp.
