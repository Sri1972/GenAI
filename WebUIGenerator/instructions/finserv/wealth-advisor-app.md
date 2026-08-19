# WealthPulse — Portfolio Intelligence Platform

## App Overview

**App name:** wealth-advisor
**Theme:** Institutional wealth management with a premium, dark-toned aesthetic
**Accent color:** #10B981 (emerald green — signals growth/positive returns)
**Dark mode preferred:** Yes — dark sidebar (#0F172A), dark cards (#1E293B), light text

---

## Data Model

### Table: positions
| Column | Type | Description |
|--------|------|-------------|
| id | integer | Auto PK |
| client_name | text | Client full name |
| account_type | categorical | Individual, Joint, Trust, IRA, 401k |
| ticker | text | Stock/ETF ticker (AAPL, MSFT, VTI, BND, GLD, QQQ, NVDA, etc.) |
| asset_class | categorical | US Large Cap, US Small Cap, International Equity, Fixed Income, Commodities, Real Estate, Crypto, Cash |
| shares | numeric | Shares held (1–5000) |
| cost_basis | numeric | Average cost per share in USD |
| current_price | numeric | Current market price per share |
| market_value | numeric | shares × current_price |
| gain_loss_pct | numeric | Unrealized gain/loss % (-40 to +200) |
| weight_pct | numeric | % of client's total portfolio (1–35) |
| sector | categorical | Technology, Healthcare, Financials, Energy, Consumer, Industrials, Utilities, Materials, Broad Market |
| last_traded | text | YYYY-MM-DD of last transaction in this position |

**Seed rows:** 90
**Seed notes:** 8 client_names, each with 8–15 positions. Tickers should be real and match their sector/asset_class (e.g., AAPL=Technology/US Large Cap, BND=Broad Market/Fixed Income). Gain_loss_pct should vary: 60% positive, 40% negative. Weight_pct should roughly sum to 100 per client.

### Table: trades
| Column | Type | Description |
|--------|------|-------------|
| id | integer | Auto PK |
| client_name | text | Must match a positions.client_name |
| action | categorical | Buy, Sell, Dividend Reinvest, Rebalance |
| ticker | text | Stock/ETF ticker |
| shares | numeric | Shares traded |
| price | numeric | Execution price per share |
| total | numeric | shares × price |
| date | text | YYYY-MM-DD (range: 2024-09 to 2025-06) |
| rationale | text | Brief reason for trade (e.g., "Tax-loss harvest", "Sector rotation", "Dividend reinvestment") |

**Seed rows:** 70
**Seed notes:** Mix of Buy (45%), Sell (30%), Dividend Reinvest (15%), Rebalance (10%). Spread across all clients and tickers. Rationale should be realistic 3–6 word phrases.

### Table: risk_metrics
| Column | Type | Description |
|--------|------|-------------|
| id | integer | Auto PK |
| client_name | text | References positions.client_name |
| sharpe_ratio | numeric | Risk-adjusted return (0.2–2.8) |
| max_drawdown_pct | numeric | Worst peak-to-trough loss (-5 to -35) |
| beta | numeric | Portfolio beta vs S&P 500 (0.4–1.6) |
| volatility_annual | numeric | Annualized volatility % (5–28) |
| var_95 | numeric | 95% Value at Risk in USD (5000–500000) |
| concentration_top3 | numeric | % of portfolio in top 3 positions (20–75) |
| risk_score | categorical | Conservative, Moderate, Aggressive, Speculative |

**Seed rows:** 8 (one per client)
**Seed notes:** Risk metrics should correlate: high beta → high volatility → aggressive risk_score. Conservative clients: beta <0.8, volatility <12%. Speculative: beta >1.3, volatility >22%.

---

## Pages

Add 6 pages to the sidebar:
1. Watchlist
2. Trade Blotter
3. Risk Matrix
4. Allocation Drift
5. AI Strategist
6. Analytics Lab

---

### Page 1: Watchlist
**Sidebar label:** "Watchlist"
**Component:** `src/pages/Watchlist.tsx`

Live portfolio feed — NOT a dashboard. Think Bloomberg terminal meets modern UI. A streaming-style view of positions with real-time-feel updates.

- **Client selector (top bar):** Horizontal tab strip with all 8 client names. Selecting one filters everything below. "All Clients" tab shows aggregate.

- **Position cards (main content, 3-column masonry grid):**
  Each card represents one position:
  - Ticker (large, bold, monospace) + Company/ETF name
  - Current price + daily change indicator (fake — just use gain_loss_pct direction)
  - Shares × Price = Market Value
  - Gain/Loss badge (green with ↑ if positive, red with ↓ if negative, show $ and %)
  - Mini sparkline showing fake 30-day trend (generate from gain_loss_pct direction — up trend if positive, down if negative)
  - Asset class tag (small pill)
  - Weight in portfolio (small progress arc)

  Cards should be sorted by absolute gain/loss descending (biggest movers first).

- **Sector ring (floating panel, top-right):** Small donut chart showing sector allocation for selected client. Hoverable segments.

- **Bottom ticker tape:** Horizontal scrolling strip showing latest trades (action + ticker + shares + date). Marquee-style.

---

### Page 2: Trade Blotter
**Sidebar label:** "Blotter"
**Component:** `src/pages/TradeBlotter.tsx`

Trade activity ledger — dense, spreadsheet-like, designed for rapid scanning. Think trading desk UI.

- **Trade summary bar (horizontal, 4 metrics):**
  - Trades This Week (count)
  - Net Buy/Sell Ratio (buys vs sells this month)
  - Total Volume (sum of total, formatted $X.XM)
  - Most Active Ticker (ticker with most trades)

- **Activity timeline (full width, 180px tall):**
  - Vertical bars for each day (last 30 days), bar height = number of trades that day
  - Color: green for net-buy days (more buys than sells), red for net-sell days
  - Hover shows date + count + net direction

- **Trade table (main content, dense):**
  - No filter dropdowns — instead, use column header filter icons (click to toggle)
  - Columns: Date (compact: "Jun 14"), Client, Action (colored: Buy=green text, Sell=red text, Div=purple, Rebal=blue), Ticker (monospace bold), Shares, Price ($XX.XX), Total ($X,XXX), Rationale (italic, gray)
  - Alternating row shading for readability
  - Sortable by any column
  - Pagination at 25 rows (dense view)
  - **Keyboard shortcut hint:** "Press / to search" (search filters across all text columns)

- **Export:** CSV download button (top-right, subtle)

---

### Page 3: Risk Matrix
**Sidebar label:** "Risk"
**Component:** `src/pages/RiskMatrix.tsx`

Risk visualization — bubble chart + comparison table. NO KPI cards at top.

- **Risk scatter (main visual, 500px tall, full width):**
  - X axis: Volatility (annual %)
  - Y axis: Sharpe Ratio
  - Bubble size: Total portfolio value (sum of market_value per client)
  - Bubble color: risk_score (Conservative=blue, Moderate=green, Aggressive=amber, Speculative=red)
  - Each bubble labeled with client name
  - Quadrant lines: vertical at volatility=15%, horizontal at sharpe=1.5
  - Quadrant labels: "Efficient" (top-left), "Star Performer" (top-right), "Stable" (bottom-left), "Risky" (bottom-right)
  - Hover tooltip: all risk metrics for that client

- **Risk comparison table (below scatter):**
  - One row per client
  - Columns: Client, Risk Score (colored badge), Sharpe, Max Drawdown (red bar width), Beta (vs 1.0 baseline indicator), VaR 95% ($), Concentration Top 3 (% with warning if >60%), Volatility
  - Conditional formatting: cells red/amber/green based on risk thresholds
  - Sort by any column

- **Concentration warning panel (right sidebar, 250px):**
  - Lists clients where concentration_top3 > 55%
  - Shows their top 3 tickers and weights
  - Orange border to signal "review needed"

---

### Page 4: Allocation Drift
**Sidebar label:** "Drift"
**Component:** `src/pages/AllocationDrift.tsx`

Asset allocation analysis — target vs actual visualization. Unique butterfly/tornado chart.

- **Client selector:** Same horizontal tabs as Watchlist page.

- **Tornado chart (main visual, full width, 400px):**
  - One row per asset_class
  - Left side (blue): Target allocation % (derived: Conservative=60% bonds/30% equity/10% cash, Moderate=50/40/10, Aggressive=70 equity/20 bonds/10 alt, Speculative=80 equity/10 crypto/10 alt)
  - Right side (green/red): Actual allocation % (sum of weight_pct grouped by asset_class for selected client)
  - Drift indicator: red highlight if actual deviates >5% from target
  - Center axis shows asset class names

- **Sector sunburst (below, left half):**
  - Two-level sunburst: inner ring = asset_class, outer ring = sector
  - Sized by market_value
  - Hovering outer ring shows: sector name, $ value, % of total

- **Drift alerts (below, right half):**
  - Card list of positions causing the biggest drift
  - Each card: Ticker, Asset Class, Current Weight vs Target Weight, Suggested Action ("Trim by X%" or "Add X%")
  - Sorted by absolute drift magnitude descending

- **Rebalance simulator (bottom bar):** Toggle button "Show Rebalance Preview" — when enabled, adds dashed lines to tornado chart showing what happens if top 3 drift positions are corrected.

---

### Page 5: AI Strategist
**Sidebar label:** "AI Strategist"
**Component:** `src/pages/AiStrategist.tsx`

AI-powered investment strategy advisor. Terminal-inspired chat with a dark theme.

**Layout:** Full-width dark chat interface (max-width 860px centered). No sidebar panels — everything lives in the conversation.

**Chat interface:**
- Dark background (#0F172A), emerald accent for AI message borders
- AI responses use monospace for numbers/tickers, can include inline formatted tables
- User messages right-aligned, dark gray bubble
- Input at bottom with emerald border glow on focus
- Placeholder: "Ask about portfolios, risk, trades, or allocation strategy…"

**Suggestion chips (single row, scrollable):**
- "Which clients need rebalancing?"
- "Show me the highest-risk positions"
- "Compare Sharpe ratios across all accounts"
- "What's causing drift in the Trust accounts?"
- "Recommend tax-loss harvesting candidates"
- "Generate a quarterly performance summary"

**AI persona:**
System context: "You are a senior investment strategist at a wealth management firm. You have access to all position data, trade history, and risk metrics for 8 client portfolios. Provide data-driven recommendations using specific tickers, dollar amounts, and percentages. When discussing risk, reference Sharpe ratio, drawdown, and concentration. For rebalancing, specify exact trades needed. Use a professional, concise tone — think Bloomberg terminal meets advisory letter. Format numbers precisely: $X,XXX.XX for values, X.XX% for percentages, always include ticker symbols in monospace."

---

### Page 6: Analytics Lab
**Sidebar label:** "Analytics"
**Component:** `src/pages/AnalyticsLab.tsx`

Advanced chart showcase page — visual deep-dive into portfolio performance and risk.

- **Radar chart (top-left, 380px):**
  - 5 axes: Sharpe Ratio, Beta, Volatility, Concentration, Max Drawdown
  - One polygon per client (show top 4 clients by portfolio value)
  - Normalize all values to 0–100 scale for fair comparison
  - Legend showing client names with colored dots

- **Candlestick chart (top-right, 380px):**
  - Show simulated 30-day price history for the most-traded ticker
  - Generate OHLC from current_price ± random walk (seed from gain_loss_pct)
  - Green candles for up days, red for down days
  - Volume bars below (secondary y-axis)

- **Waterfall chart (middle, full width, 320px):**
  - P&L attribution for the top client by portfolio value
  - Steps: Starting Value → Equity Gains → Fixed Income → Dividends → Fees → Current Value
  - Green bars for positive, red for negative, blue for total
  - Show dollar amounts on each bar

- **Gauge chart row (below waterfall, 3 gauges side by side):**
  - Portfolio Health Score (0–100, derived from Sharpe + inverse Volatility)
  - Diversification Score (0–100, inverse of concentration_top3)
  - Risk-Adjusted Return (0–100, Sharpe/2.5 scaled)
  - Color bands: green 70–100, yellow 40–70, red 0–40

- **Treemap (bottom, full width, 350px):**
  - Hierarchy: Asset Class → Sector → Top 3 Tickers
  - Sized by market_value
  - Colored by gain_loss_pct (green gradient for gains, red for losses)
  - Hover shows: ticker, shares, market value, gain/loss %

---

## Behavior notes

1. **Dark premium theme** — dark backgrounds, emerald accents, no playful elements. Think Bloomberg/Refinitiv.
2. **Monospace for financials** — all tickers, prices, and portfolio values in monospace font.
3. **No generic KPI row at top** — each page has its own unique entry point (cards, scatter, tornado chart).
4. **Sparklines** — use inline SVG mini-charts in position cards (no full D3 setup needed for these).
5. **Dense data** — this is a professional tool, not a consumer app. Pack information tightly.
