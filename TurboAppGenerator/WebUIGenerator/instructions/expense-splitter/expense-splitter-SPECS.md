# FairSplit — Technical Specification (Buildable Scope)

## Why this file was rewritten

The previous version of this file specified a Node/Express + PostgreSQL +
Redis microservices architecture with Docker/Kubernetes deployment — an
architecture this pipeline has no way to generate (it builds a single
React/TS + Tailwind frontend backed by SQLite + a REST API, matching the
pattern used by every other successfully-generated app in this instructions/
directory). It also contained several literal document-corruption artifacts
(injected "Guardrail Warning" lines that cut off JSON/TS code blocks
mid-token) that would have fed malformed text into the generation pipeline.

This rewrite keeps FairSplit's real product intent from
`expense-splitter-PRD.md` — balances, itemized splits with tax/tip
proportioning, settlement optimization, recurring splits, analytics — but
rescopes the *implementation* to what this pipeline actually builds: a
seeded SQLite dataset + auto-generated REST API + React pages, in the same
style as `hr/people-analytics-app.md`, `retail/store-ops-app.md`, etc.

**Explicitly out of scope for this generated app** (all handled with seeded/
static data instead): live receipt OCR/image upload, real email sending,
user authentication, real payment processing (Venmo/PayPal/Stripe). The
seed data represents *already-processed* splits — the UI demonstrates the
full assignment/calculation/settlement/analytics experience without needing
any of those external integrations.

---

## App Overview

**App name:** fairsplit
**Theme:** Friendly personal finance / social expense tracking — warm, trustworthy, card-heavy
**Accent color:** #16A34A (green — positive balance, "they owe you")
**Secondary accent:** #DC2626 (red — negative balance, "you owe them"; use sparingly, only for balance sign)
**Style:** Light mode, rounded corners (12px), card-first layouts over data grids

---

## Data Model

### Table: people
| Column | Type | Description |
|--------|------|-------------|
| id | integer | Auto PK |
| name | text | Full name |
| email | text | Unique email |
| phone | text | Optional phone (or empty string) |
| avatar_color | categorical | Chip color for initials avatar (blue, green, purple, amber, pink, teal) |
| joined_date | text | YYYY-MM-DD |

**Seed rows:** 10
**Seed notes:** One person represents "You" / the logged-in user (name it clearly, e.g. "You (Sarah)") — every balance/settlement is relative to this person.

### Table: splits
| Column | Type | Description |
|--------|------|-------------|
| id | integer | Auto PK |
| name | text | e.g. "Dinner at Mario's", "March Rent" |
| category | categorical | Dinner, Trip, Rent, Utilities, Groceries, Other |
| type | categorical | One-Time, Recurring |
| frequency | text | Weekly, Bi-Weekly, Monthly, or empty string for One-Time |
| organizer | text | Person name who paid/organized (references people.name) |
| subtotal | numeric | Sum of item amounts before tax/tip |
| tax_amount | numeric | Tax, distributed proportionally by item subtotal |
| tip_amount | numeric | Tip, distributed proportionally by item subtotal |
| total_amount | numeric | subtotal + tax_amount + tip_amount |
| status | categorical | Open, Partially Settled, Settled, Active, Paused (One-Time uses Open/Partially Settled/Settled; Recurring uses Active/Paused) |
| created_date | text | YYYY-MM-DD |
| due_date | text | YYYY-MM-DD, or next cycle's due date for Recurring |
| receipt_note | text | Short static note simulating a receipt reference, e.g. "5 items · receipt on file" |

**Seed rows:** 26
**Seed notes:** ~20 One-Time (mix of Dinner/Trip/Groceries, spread across last 60 days, ~60% Settled, 25% Open, 15% Partially Settled), ~6 Recurring (Rent + Utilities templates, Active, next_due_date within next 14 days).

### Table: split_items
| Column | Type | Description |
|--------|------|-------------|
| id | integer | Auto PK |
| split_id | integer | References splits.id |
| description | text | e.g. "Pasta", "House Wine (glass)" |
| amount | numeric | Line item price |
| quantity | integer | 1–4 |
| assigned_to | text | Person name this item is claimed by (references people.name) |

**Seed rows:** 90
**Seed notes:** 3–6 items per One-Time split, summing to that split's subtotal exactly. Recurring splits can have 1–2 items (e.g. "Rent share", "Internet").

### Table: settlements
| Column | Type | Description |
|--------|------|-------------|
| id | integer | Auto PK |
| from_person | text | Who paid |
| to_person | text | Who received |
| amount | numeric | Settlement amount |
| method | categorical | Venmo, PayPal, Cash, Bank Transfer, Zelle |
| settled_date | text | YYYY-MM-DD |
| note | text | Optional note, or empty string |
| related_split | text | Split name this settles, or "Settle Up (net)" for a multi-split settlement |

**Seed rows:** 16
**Seed notes:** Spread across the last 45 days, matching amounts that make sense against the settled/partially-settled splits above.

---

## Pages

Add 5 pages to the sidebar:
1. Balances
2. Splits
3. Recurring
4. Analytics
5. Split Assistant

---

### Page 1: Balances
**Sidebar label:** "Balances"
**Component:** `src/pages/Balances.tsx`

The home/landing page — net position with everyone, at a glance.

- **Summary header (top):** "You are owed $X total" / "You owe $Y total" / "Net position: ±$Z" — large, bold, colored (green if net positive, red if negative).
- **Per-person balance cards (main content, grid):**
  - One card per person (excluding "You"): avatar chip, name, net balance across ALL their splits with "You" (positive = they owe you, green; negative = you owe them, red).
  - Small text: number of open/partially-settled splits contributing to this balance.
  - "Settle Up" button (visual only — shows a toast/confirmation, no real payment).
  - "View Splits" link — filters the Splits page to that person.
- **Sort/filter (above grid):** Sort by amount (highest first) / name / most recent activity. Filter: All / Owes You / You Owe / Settled.
- **Zero-balance toggle:** Show/hide people with $0 net balance.

---

### Page 2: Splits
**Sidebar label:** "Splits"
**Component:** `src/pages/SplitsHistory.tsx`

History and itemized detail for One-Time splits — NOT a live receipt upload flow (see scope note above); items are pre-seeded to demonstrate the assignment/settlement experience.

- **Filter bar (top):** Search by split name, category dropdown, status dropdown (Open/Partially Settled/Settled/All), date range.
- **Split list (main content, card list, most recent first):**
  Each card: name, category badge, organizer, total_amount (large), status badge (color-coded), receipt_note, created_date. Click to expand detail below.
- **Split detail (expands below clicked card):**
  - `receipt_note` shown as a small static "receipt reference" chip (no image upload/OCR — this is a seeded placeholder).
  - Itemized list: each split_item with description, amount, quantity, and assigned person (avatar chip).
  - **Tax/tip breakdown:** subtotal, tax_amount, tip_amount, total_amount shown as a clear itemized strip, with tax/tip shown as proportionally distributed per person below it (e.g. "Alice: $20.50 items + $1.64 tax + $4.10 tip = $26.24").
  - **Settlement instructions:** optimized "who pays whom" lines derived from each person's subtotal vs. what they've already settled (e.g. "Alice pays You $26.24").
  - Status badge + "Mark as Settled" toggle (visual only).

---

### Page 3: Recurring
**Sidebar label:** "Recurring"
**Component:** `src/pages/RecurringSplits.tsx`

Dashboard for recurring splits (rent, utilities) — forward-looking.

- **Recurring split cards (main content, grid):**
  Each card: name, category badge, frequency badge, amount_per_cycle (total_amount), next_due_date (prominent, "Due in N days"), status (Active=green dot, Paused=gray dot).
  - Members strip: avatar chips of everyone on this recurring split with their per-cycle share.
  - "Pause" / "Resume" toggle button (visual only).
- **Upcoming cycles (below cards, simple timeline):** Next 30 days, one marker per recurring split's next 1-2 due dates.
- **Payment status this cycle:** progress indicator per recurring split ("2 of 3 paid this cycle") — derive from settlements where `related_split` matches.

---

### Page 4: Analytics
**Sidebar label:** "Analytics"
**Component:** `src/pages/Analytics.tsx`

Spending trends and splitting patterns across all data.

- **KPI row (top, 4 cards):** Total split all-time, Total owed to you, Total you owe, Active splits count.
- **Spending over time (line or bar chart, full width):** Monthly total split amount, filterable by date range (30/90 days, 6 months, all).
- **Category breakdown (donut chart):** split total_amount by category (Dinner/Trip/Rent/Utilities/Groceries/Other).
- **Top splitting partners (horizontal bar chart):** people ranked by total amount split together, descending.
- **Settlement status (stacked bar chart):** Settled vs. Partially Settled vs. Open, by month.
- **Balance history (line chart):** net balance with all people combined, over the last 6 months (positive = owed to you, negative = you owe).

---

### Page 5: Split Assistant
**Sidebar label:** "Split Assistant"
**Component:** `src/pages/SplitAssistant.tsx`

A conversational AI assistant over the splits/balances/settlements data — generate this page from scratch (custom layout), do NOT use a generic pre-built skill template.

**Layout:** Centered chat (max-width 720px) with a floating quick-insights card, similar in spirit to a personal-finance copilot.

**Chat interface:**
- Light background, green accent on AI avatar and message timestamps.
- AI messages can render: tables (comparing people's balances), bullet lists, and small inline bar/line charts.
- Friendly, concise tone — this assistant should feel like a helpful friend doing the math, not a corporate bot.
- Input placeholder: "Ask about balances, splits, or settlements…"

**Quick insights card (floating, top-right, 220px wide, collapsible):**
- "Right Now" header — net position, most overdue split, active recurring splits count.

**Suggestion chips:**
- "Who owes me the most right now?"
- "Summarize this month's spending by category"
- "Show my settlement history with [a person from seed data]"
- "Which recurring split is due soonest?"
- "How much have I spent on Dinner this year?"

**AI persona:**
System context: "You are FairSplit's assistant, helping a user understand their shared expenses. You have access to all splits, balances, and settlement records. Be friendly and concise — use specific names and dollar amounts. When asked about balances, always clarify direction (who owes whom). Use tables to compare people, bullet points for summaries. Flag overdue recurring splits proactively."

This page should use the same real-LLM-backed chat pattern already proven in this pipeline (backend `/api/chat` endpoint reading from the SQLite-backed REST API) — not a hand-rolled canned-response list.

---

## Behavior notes

1. **Card-first, not table-first** — balances and splits use rich cards; tables appear only inside expanded split detail and analytics.
2. **Green = owed to you, red = you owe** — apply this consistently everywhere a balance/net amount is shown (Balances page, Analytics balance history, settlement instructions).
3. **No live integrations** — no receipt upload/OCR, no real email, no real auth, no real payment processing. All of that is represented as realistic seeded data instead (see scope note at the top of this file).
4. **Settlement math must be exact** — tax/tip proportional distribution and "who pays whom" instructions should be internally consistent with the seeded subtotal/tax/tip/total columns (no rounding drift that leaves totals mismatched).
5. **No maps, no geographic visualization** — this app has no location dimension.
