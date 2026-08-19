# FreightCommand — Supply Chain Visibility & Logistics Intelligence

## App Overview

**App name:** supply-chain
**Theme:** Industrial logistics — bold, utilitarian, data-dense
**Accent color:** #EA580C (burnt orange — urgency, industrial)
**Secondary accent:** #2563EB (blue — tracking, reliability)
**Style:** Semi-dark sidebar/header (#1C1917), white content area. Monospace for tracking IDs. Industrial/utilitarian feel — designed for a logistics NOC.

---

## Data Model

### Table: shipments
| Column | Type | Description |
|--------|------|-------------|
| id | integer | Auto PK |
| tracking_id | text | Unique tracking (FRT-XXXXXXXX format) |
| origin_city | text | Origin city |
| origin_country | text | Country code (US, CN, DE, JP, KR, VN, IN, MX, BR, NL) |
| dest_city | text | Destination city |
| dest_country | text | Destination country code |
| mode | categorical | Ocean, Air, Rail, Truck, Multimodal |
| carrier | text | Carrier name (Maersk, FedEx, BNSF, DHL, UPS, CMA CGM, Yang Ming, Evergreen) |
| status | categorical | Booked, In Transit, At Port, Customs Hold, Out for Delivery, Delivered, Exception |
| priority | categorical | Express, Standard, Economy |
| weight_kg | numeric | 1–25000 |
| container_type | categorical | 20ft, 40ft, 40ft HC, LTL, Parcel, Bulk |
| ship_date | text | YYYY-MM-DD |
| eta | text | YYYY-MM-DD |
| actual_arrival | text | YYYY-MM-DD or null |
| delay_days | integer | Days late (0=on time, negative=early, positive=late) |
| value_usd | numeric | 500–2000000 |
| customer | text | Customer account name (8 different customers) |

**Seed rows:** 75
**Seed notes:** 40% Ocean, 25% Air, 15% Truck, 12% Rail, 8% Multimodal. Status: 30% Delivered, 30% In Transit, 15% At Port, 10% Booked, 8% Out for Delivery, 5% Customs Hold, 2% Exception. 60% on-time, 25% late (1–15 days), 15% early.

### Table: milestones
| Column | Type | Description |
|--------|------|-------------|
| id | integer | Auto PK |
| tracking_id | text | References shipments.tracking_id |
| event | categorical | Booking Confirmed, Picked Up, Departed Origin, In Transit, Arrived Port, Customs Cleared, Departed Port, Out for Delivery, Delivered, Exception Raised |
| location | text | City where event occurred |
| timestamp | text | YYYY-MM-DD HH:MM |
| notes | text | Brief event note (e.g., "Vessel EVER GIVEN departed Shanghai") |

**Seed rows:** 200
**Seed notes:** Each shipment has 3–8 milestones in chronological order. Delivered shipments have full milestone chains. In-Transit shipments have partial chains. Timestamps should be realistic (ocean takes 20–35 days, air takes 2–5 days).

### Table: carriers
| Column | Type | Description |
|--------|------|-------------|
| id | integer | Auto PK |
| name | text | Carrier name (must match shipments.carrier) |
| mode | categorical | Primary mode (Ocean, Air, Rail, Truck) |
| on_time_pct | numeric | Historical on-time delivery rate (65–98%) |
| avg_delay_days | numeric | Average delay when late (0.5–8.0) |
| shipment_count | integer | Total shipments with this carrier (5–25) |
| cost_index | numeric | Relative cost (0.7–2.5, where 1.0 = average) |
| reliability_score | numeric | Composite score 1.0–5.0 |
| coverage | text | Route coverage description (e.g., "Asia-Pacific → North America", "Intra-Europe") |
| contract_status | categorical | Active, Expiring Soon, Under Review |

**Seed rows:** 8
**Seed notes:** Match the 8 carrier names in shipments. Ocean carriers: lower cost but higher delay. Air: highest cost, lowest delay. Truck: mid cost, most reliable for domestic. At least 2 should be "Expiring Soon" to create alerts.

---

## Pages

Add 6 pages to the sidebar:
1. Shipment Timeline
2. Carrier Scorecard
3. Exception Board
4. Network Graph
5. Logistics AI
6. Analytics Deep Dive

---

### Page 1: Shipment Timeline
**Sidebar label:** "Timeline"
**Component:** `src/pages/ShipmentTimeline.tsx`

Shipment tracking with milestone visualization — Gantt meets package tracking. NOT a table.

- **Search bar (top, prominent):** Large search input — "Enter tracking ID or customer name" — filters everything below.

- **Shipment lanes (main visual, full width, vertical scroll):**
  Each shipment renders as a horizontal LANE (like a Gantt bar):
  - Left label: Tracking ID (monospace) + route ("Shanghai → Newark")
  - Horizontal bar spanning ship_date → eta (or actual_arrival if delivered)
    - Bar color by mode (Ocean=blue, Air=orange, Rail=green, Truck=gray, Multimodal=purple)
    - Milestone dots ON the bar at their relative position in time
    - Dot color: completed=solid, future=outline/dashed
    - If delayed: bar extends past ETA with red dashed extension
    - If delivered early: green checkmark at actual_arrival, bar shortened
  - Right label: Status badge + delay indicator
  - Click a lane to expand milestone detail below it

- **Expanded milestone view (appears below clicked lane):**
  - Vertical timeline of all milestones for that shipment
  - Each milestone: timestamp, event name, location, notes
  - Connected by a vertical line with dots (completed=filled, pending=hollow)
  - Timeline direction: left-to-right chronological

- **Filters (above lanes):** Mode selector (pills), Status dropdown, Priority dropdown, Sort by (Ship Date / ETA / Delay)

- **Lane density control (top-right):** Show 10 / 25 / All toggle

---

### Page 2: Carrier Scorecard
**Sidebar label:** "Carriers"
**Component:** `src/pages/CarrierScorecard.tsx`

Carrier performance comparison — report card layout with competitive ranking.

- **Carrier ranking (main visual, full width):**
  A ranked list (NOT a table — think leaderboard):
  - Each carrier as a wide horizontal card (full width, stacked vertically)
  - Ranked by reliability_score descending
  - Card content:
    - Rank badge (#1, #2, etc. — gold/silver/bronze for top 3)
    - Carrier name (large, bold)
    - Mode badge (icon + text)
    - Coverage route (gray subtitle)
    - **Metric strip (5 inline metrics):**
      - On-Time % (green if >85%, amber 70–85%, red <70%)
      - Avg Delay (days, green if <2, red if >5)
      - Shipment Count
      - Cost Index (formatted as "1.2×", colored: green if <1.0, amber 1.0–1.5, red >1.5)
      - Reliability Score (star display out of 5)
    - Contract status badge (Active=green, Expiring Soon=amber pulse, Under Review=red)

- **Comparison radar (below ranking, 400px):**
  - Radar/spider chart with 4 axes: On-Time %, Cost Efficiency (inverted cost_index), Volume, Reliability Score
  - Select 2–3 carriers to compare (checkboxes on each card)
  - Overlapping polygons with carrier-colored fills

- **Mode comparison (bottom):**
  - Grouped bar: Average metrics by mode (Ocean vs Air vs Rail vs Truck)
  - Bars: on_time_pct, avg_delay, cost_index
  - Reveals mode-level trade-offs (speed vs cost vs reliability)

---

### Page 3: Exception Board
**Sidebar label:** "Exceptions"
**Component:** `src/pages/ExceptionBoard.tsx`

Exception management — Kanban board with severity-driven layout. Action-oriented.

- **Severity counters (top strip):**
  - Count of shipments by status = "Exception" or "Customs Hold"
  - Grouped: Critical delay >7 days (red), Moderate delay 3–7 days (amber), Minor delay 1–2 days (gray)
  - + "Customs Holds" count (separate orange badge)

- **Exception kanban (main content, full width, 3 columns):**
  - **Column 1: "Active — Customs"** (orange header)
    - Cards for all shipments where status = "Customs Hold"
  - **Column 2: "Active — Delayed"** (red header)
    - Cards for shipments where delay_days > 3 AND status ∈ (In Transit, At Port)
  - **Column 3: "Resolved This Week"** (green header)
    - Cards for shipments delivered in last 7 days that HAD delay_days > 3

  Each exception card:
  - Tracking ID (monospace, bold orange)
  - Route: origin → destination (compact)
  - Carrier + Mode badges
  - Delay: "+X days" (red bold)
  - Value at risk: $X,XXX (if high value, gold border)
  - Customer name
  - Latest milestone event + timestamp
  - Priority badge (Express items get red priority strip)

- **Resolution actions (card footer):** "Escalate" / "Contact Carrier" / "Reroute" buttons (visual — show toast)

- **Root cause breakdown (below Kanban):**
  - Donut chart: Why are things delayed? (Port Congestion / Weather / Customs / Carrier Issue / Documentation / Other)
  - Derived from the latest milestone notes for delayed shipments

---

### Page 4: Network Graph
**Sidebar label:** "Network"
**Component:** `src/pages/NetworkGraph.tsx`

Trade lane network visualization — node-link diagram showing the flow between origins and destinations. NOT a geographic map — a FORCE-DIRECTED or HIERARCHICAL graph.

- **Network graph (main visual, full width, 550px tall):**
  - Nodes = unique cities (both origins and destinations from shipments)
  - Node size = number of shipments touching that city (as origin OR destination)
  - Node color = role (pure origin=orange, pure destination=blue, both=purple)
  - Edges = trade lanes between cities
  - Edge thickness = shipment count on that lane
  - Edge color by mode (most common mode on that lane): Ocean=blue, Air=orange, Truck=gray
  - Edge dash pattern if any shipment on that lane is delayed (solid=all on time, dashed=some delayed)
  - Force-directed layout with drag-to-rearrange
  - Hover node: city name, total shipments, top carriers, avg delay
  - Hover edge: origin → dest, count, modes, on-time rate

- **Lane table (below graph, collapsible):**
  - Rows: unique origin→destination pairs
  - Columns: Origin, Destination, Shipments, Primary Mode, Avg Delay Days, On-Time %, Total Value
  - Sorted by shipment count descending
  - Click a row to highlight that edge in the graph above

- **Network health metrics (right sidebar, 250px):**
  - Total active lanes (unique O/D pairs)
  - Most congested lane (highest avg delay)
  - Highest value lane (most $ in transit)
  - Most reliable lane (best on-time %)
  - "Concentration risk" — if >40% of shipments flow through one city, flag it

---

### Page 5: Logistics AI
**Sidebar label:** "Logistics AI"
**Component:** `src/pages/LogisticsAi.tsx`

AI operations assistant — industrial, precise, tracking-focused.

**Layout:** Full-width chat (max-width 880px) with persistent status bar at top.

**Status bar (always visible, top, dark background):**
- In Transit: X | At Port: X | Customs: X | Exceptions: X | On-Time Rate: X%
- Monospace numbers, compact layout, updates contextually

**Chat interface:**
- Dark header strip with orange accent, white message area
- Monospace for all tracking IDs and numbers in AI responses
- AI can render: shipment milestone timelines, carrier comparison tables, route recommendations
- Input placeholder: "Track a shipment, investigate delays, or ask about logistics…"

**Suggestion chips (single row):**
- "Track FRT-00012345"
- "What's causing delays from Shanghai this week?"
- "Compare carrier performance for ocean freight"
- "Show all customs holds"
- "Which lanes have the worst on-time rate?"
- "Recommend fastest carrier for US to Germany"

**AI persona:**
System context: "You are a logistics operations AI supporting supply chain managers at a freight forwarding company. You have access to all shipment tracking data, milestone events, and carrier scorecards. Be precise — always include tracking IDs, dates, and dollar amounts. When discussing delays, identify the specific milestone where the delay occurred and suggest mitigation (reroute, expedite customs, escalate to carrier). For carrier recommendations, compare on-time rates, cost indexes, and coverage. Use logistics terminology naturally: TEU, LTL, drayage, demurrage, throughput, ETA, BOL. Present multi-shipment data in tables. Flag high-value shipments at risk proactively."

---

### Page 6: Analytics Deep Dive
**Sidebar label:** "Analytics"
**Component:** `src/pages/AnalyticsDeepDive.tsx`

Advanced logistics analytics — visual deep-dive into supply chain performance.

- **Radar/spider chart (top-left, 380px):**
  - Compare top 4 carriers across 5 dimensions: On-Time %, Cost Index, Avg Delay, Reliability Score, Coverage
  - Normalize all values to 0–100 scale
  - One polygon per carrier, semi-transparent fills
  - Legend with carrier names

- **Sankey diagram (top-right, 380px):**
  - Cargo flow: Origin Country → Transport Mode → Destination Country
  - Top 5 origin countries, all 5 modes, top 5 destination countries
  - Link thickness proportional to shipment value
  - Color by transport mode

- **Waterfall chart (middle, full width, 320px):**
  - Delay attribution analysis for late shipments
  - Steps: Scheduled Transit → Port Waiting → Customs Hold → Weather Delays → Carrier Delays → Actual Transit
  - Red bars for delay additions, green for early portions, blue for totals

- **Treemap (middle-bottom, full width, 350px):**
  - Shipment value breakdown: Mode → Carrier → Customer
  - Sized by value_usd
  - Color by delay_days (green = on-time/early, red = late)

- **Bubble chart (bottom-left, 380px):**
  - X: Weight (kg), Y: Value (USD), Bubble Size: Delay days
  - Color by mode (Ocean=blue, Air=cyan, Rail=gray, Truck=orange)
  - Helps identify high-value/high-delay shipments

- **Gauge chart row (bottom-right, 3 gauges stacked):**
  - Fleet Utilization (% of containers active)
  - On-Time Delivery Rate (target: 85%)
  - Exception Resolution Rate (% resolved within 48h)

---

## Behavior notes

1. **Industrial aesthetic** — utilitarian, monospace for IDs, dense information. Not playful.
2. **Gantt-style tracking** — the shipment timeline uses horizontal lanes, NOT a table with status columns.
3. **Force-directed graph** — the network page tests a complex D3 layout algorithm. NOT a geographic map.
4. **Kanban for exceptions** — action-oriented columns, not a static report.
5. **Orange + blue** — orange for urgency/exceptions, blue for tracking/ocean/stable operations.
6. **No geographic maps** — the network graph replaces them. Trade lanes as edges, cities as nodes.
7. **Leaderboard ranking** — carrier page uses ranked cards, not a boring sortable table.
