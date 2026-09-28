# TRD.md

# Technical Requirements Document
## OEM–Dealer Data & Insights Platform — Prototype Build

**Document Owner:** Solutions Architecture
**Status:** Final — Ready for Implementation
**Version:** 1.1 (Final — incorporates Round 1–4 critique from Solutions Architect and Business Analyst)
**Traces to:** PRD.md v1.1, Round 1–4 discussion (Solutions Architect, Business Analyst, Backend API Engineer)

---

## Table of Contents

1. Document Purpose & Scope
2. Scope Resolution: PRD Ambition vs. Prototype Reality
3. Technology Stack & Rationale
4. High-Level Architecture
5. Service Boundaries & Component Responsibilities
6. Data Model & Entity Relationships
7. Business Rules & Data Validation
8. "Viewing As" Scoping Model (Mock Role-Based Access)
9. Service Contract Design (Function-Level API Surface)
10. Chatbot Design & Query Resolution Strategy
11. Non-Functional Requirements
12. Security & Data Protection Posture
13. Observability & Logging Strategy
14. Error Handling Strategy
15. Data Flows
16. Deployment Topology
17. Testing Strategy
18. Out of Scope / Deferred to Production Roadmap
19. Assumptions Log
20. Traceability Matrix

---

## 1. Document Purpose & Scope

This TRD translates PRD.md into concrete technical decisions for a **working prototype**. It defines *what* technology is used, *why*, how components interact, what business rules must be enforced, and what quality bar (performance, reliability, security posture) the build must meet.

This document does **not** contain schemas, API payload contracts, or code — those belong in SPECS.md. Where a decision requires eventual implementation detail, this document states the *requirement and rationale*; SPECS.md states the *exact shape*.

**Audience:** Frontend developer(s) implementing the prototype, and any future engineer picking this up for a production rebuild.

---

## 2. Scope Resolution: PRD Ambition vs. Prototype Reality

PRD.md describes a production-grade, multi-tenant, security-critical system: server-enforced authentication, tenant isolation, RBAC, audit logging, and a chatbot with a **zero-tolerance cross-tenant leakage** requirement (P0, 100% target). The active build profile for this exercise is **Prototype/Lightweight**, which explicitly disallows authentication, backend persistence beyond a browser-local store, and cloud infrastructure unless the *product idea itself* explicitly demands it.

**Resolution (ratified across Round 1–4 discussion):**

- The **product idea** ("web app for OEMs and dealers with data grids, visualization, and a chatbot") governs scope — not the PRD's aspirational production posture. The product idea does not state "users must log in" or "requires an account."
- Therefore this prototype has **no authentication, no server-enforced authorization, no persistent backend, no audit trail, and no guaranteed data isolation.**
- Every PRD requirement that depends on server-side enforcement (auth, tenant isolation, audit logging, 100% chatbot leakage guarantee) is **reframed, not silently dropped**: it is implemented as a **client-side, cosmetic mock** and explicitly labeled as such in-app and in this document, so no one downstream mistakes a UI convenience for a security boundary.
- All such reframed items are logged in Section 18 (Out of Scope) as **launch-blocking gaps for any future production build.**
- The PRD's open domain question (Section 5 of PRD, "[DECISION NEEDED]") is **resolved for this build**: the concrete domain is **Vehicle Inventory** (see Section 6). This is a prototype-scope decision, not a business commitment — it must be re-validated with real stakeholders before any production rebuild.

This is a deliberate, documented trade-off — not an oversight.

---

## 3. Technology Stack & Rationale

| Layer | Choice | Rationale |
|---|---|---|
| **Structure/Styling** | HTML5 + CSS3 + Tailwind CSS (via CDN) | Matches prototype default. No build step required. Tailwind gives consistent, fast styling for grids/dashboards/chat panels without a component framework. |
| **Application Logic** | Vanilla JavaScript (ES2020+), organized into `dataStore.*`, `services.*`, `ui.*` namespaces/modules | No multi-page routing and no need for a component library's state-management overhead — a single-page app with tabbed views (Grid / Analytics / Chat) satisfies all requirements. React + Vite is an *allowed alternative* but is **not chosen**: it would add a build step and dependency surface with no functional benefit at this scale. |
| **Data Visualization** | Chart.js (via CDN, no build step) | Lightweight, no-license charting library sufficient for the analytical views described in PRD §1 (bar/line/comparison charts for inventory trends, dealer comparisons). Chosen over heavier charting suites to keep the app a single self-contained artifact. |
| **Data Grid Rendering** | Hand-rolled HTML table + vanilla JS (sort/filter/pagination logic in `services.*`) | A full third-party grid library (e.g., AG Grid) was considered and rejected for this prototype — see "Why not X?" below. |
| **Persistence** | **None (browser session memory only).** The mock dataset is loaded once at app start from a bundled static JSON file into an in-memory JS structure (`dataStore`). No SQLite, no server DB. Data does **not** survive a page refresh; edits made during a session are lost on reload. | The product idea does not explicitly require data to survive beyond a browser session. Per guardrails, no backend/database is assumed unless explicitly needed. If persistence across sessions becomes a real requirement, SQLite is the pre-approved next step (see Section 18). |
| **Backend/API** | **None.** All "service calls" are synchronous/async in-browser JavaScript function calls, not HTTP calls. | No server-side logic is required for filtering, aggregating, or answering pattern-matched chat queries against an in-memory dataset. |
| **Chatbot NLU** | Client-side, rule-based intent matching (keyword/pattern matching mapped to a fixed, enumerated set of supported query intents — see Section 10) — **[ASSUMPTION]** | The product idea says "chat bot that users can talk to" but specifies no NLP technology, and guardrails forbid introducing external integrations (e.g., a hosted LLM API) unless explicitly requested. Flagged as an assumption because a real conversational chatbot would typically call an LLM API; that is explicitly **out of scope** for this prototype. |
| **Authentication** | **None.** | Per guardrails and Section 2 scope resolution. |
| **Hosting** | Static file hosting / local dev server (open `index.html` directly, or serve via any static file server) | No cloud infrastructure needed for a client-only application. |
| **Observability** | Browser console logging only | Per guardrails; no monitoring service introduced. |
| **Testing** | Manual smoke-test checklist (Section 17) | Per guardrails; no automated test framework mandated for this scope, though Vitest is an allowed future addition if the team requests automated coverage. |

### Why not X?

- **Why not a real backend (Node/Express, FastAPI, Spring)?** The product idea does not require data to persist beyond the browser, does not require multi-user concurrent write access, and does not require server-enforced security. Introducing a backend would add deployment/operational burden (a process to run, a port to manage, a database file to maintain) with no functional payoff at this scope. If real persistence or real access control becomes a stated requirement, a minimal FastAPI or Express service backed by SQLite is the pre-approved next step — not a larger framework.
- **Why not React + Vite?** React earns its cost when a project needs componentized reuse across multiple routed pages, complex shared state, or a component ecosystem (form libraries, routers). This app is a single page with three tabbed views sharing one in-memory dataset — plain JS modules with clear boundaries (`dataStore` / `services` / `ui`) achieve the same separation of concerns without a build pipeline.
- **Why not a full-featured data grid library (AG Grid, Handsontable)?** Those libraries are justified when requirements include drag-and-drop column reordering, virtualized rendering of 100k+ rows, or complex cell editors. This prototype's assumed data volume (≤5,000 records — see Section 11) does not need virtualization; sort/filter/paginate on an in-memory array is sufficient and keeps the artifact dependency-light.
- **Why not a real LLM-backed chatbot?** This would require an external API integration (e.g., a hosted LLM provider), which the guardrails disallow by default and the product idea does not explicitly request. A rule-based intent matcher against a known, enumerated set of query patterns (Section 10) still delivers the core UX described in the PRD personas ("ask a plain-language question, get an answer") within a fixed, documented scope. This is the single largest capability gap versus the PRD's ambition and is called out explicitly in Section 18.
- **Why not SQLite now?** SQLite is the pre-approved database for this profile *if* server-side persistence is explicitly needed. Nothing in the product idea requires data to survive a page refresh or be shared across users/sessions, so introducing a database (and by extension a backend to talk to it) would be scope creep relative to the stated requirement.

---

## 4. High-Level Architecture

The prototype is a **single-page, client-only application** with three tabbed surfaces (Grid, Analytics, Chat) plus a role-switching control, all sharing one in-memory data source.

```
┌──────────────────────────────────────────────────────────────────────┐
│                     Browser (client-only application)                │
│                                                                        │
│  ┌─────────────────┐   Global: "Viewing As" selector (Role + Dealer) │
│  │  ui.viewingAs    │   — mocked scoping control, always visible      │
│  └────────┬─────────┘                                                 │
│           │ sets viewerContext, shared by all tabs                    │
│           ▼                                                           │
│  ┌───────────────┐   ┌───────────────┐   ┌────────────────┐          │
│  │   ui.grid     │   │  ui.analytics │   │   ui.chat      │          │
│  │ (table render,│   │ (chart render │   │ (message list, │          │
│  │  sort/filter  │   │  via Chart.js)│   │  input box)    │          │
│  │  controls,    │   │               │   │                │          │
│  │  edit forms)  │   │               │   │                │          │
│  └──────┬────────┘   └──────┬────────┘   └───────┬────────┘          │
│         │                   │                     │                   │
│         ▼                   ▼                     ▼                   │
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │                    services.*  (business logic)                   ││
│  │  getVehicles / getVehicleById / updateVehicle /                  ││
│  │  getAnalyticsSummary / resolveChatQuery /                        ││
│  │  getRejectedRows / loadDataset                                    ││
│  │  — every function scope-filters via services._applyScope() —      ││
│  └───────────────────────────────┬────────────────────────────────────┘│
│                                  ▼                                     │
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │                        dataStore (in-memory)                      ││
│  │  vehicles[], rejectedRows[], dealers[] (derived), sessionEditLog[] ││
│  │  Loaded once at startup from /data/vehicles.seed.json              ││
│  └──────────────────────────────────────────────────────────────────┘│
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │              Browser console (observability sink only)            ││
│  └──────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────┘
```

**Key architectural properties:**
- **No network calls** at runtime except loading the static seed JSON file and CDN-hosted Tailwind/Chart.js assets.
- **Single source of truth**: `dataStore` is the only place raw records live. Grid, Analytics, and Chat all read through `services.*`, never directly from `dataStore`.
- **Scope enforcement is centralized**, not duplicated per UI surface — this is what makes the "Viewing As" mock behave consistently across grid/chart/chat (see Section 8).
- **Everything is synchronous or resolves in-process** — there is no distributed failure mode to design for, because there is no second process. The only "external dependency" is the static seed file fetch at startup (see Section 12 for its failure handling).

---

## 5. Service Boundaries & Component Responsibilities

Even without a network boundary, we maintain **logical service boundaries** so the code is provably scoped and portable to a real backend later.

| Component | Responsibility | Must NOT Do |
|---|---|---|
| `dataStore.*` | Owns the mock dataset in memory: `vehicles[]`, `rejectedRows[]`, `dealers[]` (derived list), `sessionEditLog[]` (in-session edit history for chat "what changed" queries). Exposes raw read/write primitives only. | Must not apply business rules, scoping, or validation — it is a dumb store. Must not be called directly by `ui.*`. |
| `services.*` | All business logic: filtering, pagination, sorting, aggregation, validation, scope enforcement (`_applyScope`), chat intent resolution. Every public function accepts `viewerContext` and returns a response envelope (Section 9). | Must not touch the DOM. Must not assume a specific UI surface calling it — grid, chart, and chat all call the same functions. |
| `ui.grid` | Renders the vehicle table, sort/filter/pagination controls, inline edit form, Rejected Rows panel. Calls `services.getVehicles`, `services.updateVehicle`, `services.getRejectedRows`. | Must not filter or scope data itself — it renders whatever `services.*` returns. |
| `ui.analytics` | Renders Chart.js visualizations from `services.getAnalyticsSummary`. | Must not recompute aggregates client-side outside `services.*`. |
| `ui.chat` | Renders message thread, input box, calls `services.resolveChatQuery`. Maintains a `conversationId` for the session. | Must not attempt its own text parsing — all intent matching lives in `services.*`. |
| `ui.viewingAs` | Renders the Role + Dealer selector, constructs `viewerContext`, broadcasts it to all three tabs on change. | Must not persist `viewerContext` beyond the browser session (no localStorage), per Section 2's "cosmetic mock" framing. |

---

## 6. Data Model & Entity Relationships

**[ASSUMPTION — domain resolved for prototype scope per Section 2; must be re-validated with real stakeholders before production.]**

### 6.1 Entities

| Entity | Description | Cardinality |
|---|---|---|
| **OEM** | The single manufacturer tenant root for this prototype. | Exactly 1 in seed data ("Prototype Motors OEM"). |
| **Dealer** | A dealership belonging to the OEM. | 1 OEM → many Dealers. Seed data contains **12 dealers**. |
| **Vehicle** | The core Record entity — one vehicle inventory unit. | Exactly 1 owning Dealer per Vehicle. Seed data contains **~3,000 vehicles** distributed across the 12 dealers (uneven distribution, intentionally, to exercise empty/sparse states). |
| **RejectedRow** | A row from the seed load that failed validation (Section 7). Retained for display, excluded from the working dataset. | 0..N per load. |
| **SessionEditRecord** | An in-memory record of an edit made during the current session (field, old value, new value, timestamp, editing role). Used only to answer chatbot "what changed" queries (Section 10). Not persisted beyond the session. | 0..N per session. |
| **ViewerContext** | Not a persisted entity — a transient object representing the current "Viewing As" selection. Exists only in `ui.viewingAs` state and is passed by reference into every `services.*` call. | 1 active per session. |

### 6.2 Relationships

```
OEM (1) ──owns──> Dealer (many)
Dealer (1) ──owns──> Vehicle (many)
Vehicle (1) ──may produce──> RejectedRow (0..1, at load time only, mutually exclusive with being a valid Vehicle)
Vehicle (1) ──may produce──> SessionEditRecord (0..N, at edit time, session-scoped)
```

### 6.3 Dataset Provenance & Size — **[ASSUMPTION, ratifies SA critique]**

- The seed dataset is a **static JSON file bundled with the app** at `/data/vehicles.seed.json`.
- **Assumed scale for all NFR targets and design decisions in this document:** ≤ 5,000 raw rows on load, ≤ 12 dealers, 1 OEM. Actual seed ships with ~3,000 valid rows + a deliberate handful (~20–30) of invalid rows to exercise the Rejected Rows panel.
- This file is **not editable by end users** and is **not regenerated** — it is a fixed fixture for the prototype's lifetime. Any future "real ingestion" capability is out of scope (Section 18).
- The **Dealer list is not hardcoded** — it is **derived** from the set of distinct, valid `Dealer ID` values present in `dataStore.vehicles` after validation, sorted alphabetically by Dealer name for display in the "Viewing As" selector (see Section 8.3 — resolves BA critique 1.2).

---

## 7. Business Rules & Data Validation

### 7.1 Vehicle Field Validation (applied once, at `loadDataset` time)

| Field | Type | Validation Rule | On Violation |
|---|---|---|---|
| VIN | string(17) | Required; exactly 17 alphanumeric chars; must be unique in dataset | Reject row; flag `INVALID_VIN` |
| Dealer ID | string | Required; must match a known Dealer in mock dataset | Reject row; flag `UNKNOWN_DEALER` |
| Model | string | Required, non-empty | Reject row; flag `MISSING_MODEL` |
| Status | enum | One of: `In Stock`, `In Transit`, `Sold`, `Reserved` | Reject row; flag `INVALID_STATUS` |
| Price | number | ≥ 0; ≤ 500,000 (sanity ceiling) | Reject row; flag `PRICE_OUT_OF_RANGE` |
| Days In Inventory | integer | ≥ 0; **derived server-side (client-side, in this prototype) from `Last Updated`, never trusted from raw input** | Recompute always; never reject a row solely for this field |
| Last Updated | date | Must parse as valid ISO date; not in the future | Reject row; flag `INVALID_DATE` |

**Rule:** Rows failing validation are **excluded from the working dataset** (`dataStore.vehicles`) but **retained** in `dataStore.rejectedRows` with reason codes. Users must see what didn't load, not just a silent drop.

### 7.2 Rejected Rows Panel — UI & Interaction Requirements (resolves BA critique 1.3)

- Accessible as a labeled sub-panel/tab within the **Grid** surface (not a separate top-level tab), titled "Rejected Rows (data quality)."
- **Visibility rule:** Visible **only** when `viewerContext.role === "OEM_ADMIN"`. Ingestion/data-quality review is modeled as an OEM-level concern in this prototype; Dealer Principal and Dealer Staff do not see this panel, and it does not appear in their UI at all (not merely disabled — absent).
- Displays a badge with the count of rejected rows next to the panel's entry point.
- Table columns: `Original Row #`, `Reason Code`, `Reason Description` (human-readable), `Raw Data` (rendered as a collapsed/expandable JSON snippet).
- Read-only. No re-submit/edit/retry capability in this prototype (true ingestion correction is out of scope — Section 18).
- If zero rows were rejected, the panel shows an explicit empty state ("No rejected rows — all seed data passed validation"), not a hidden/absent panel, so the OEM Admin can confirm the load was clean.

### 7.3 Editable Field Rules (applies to `updateVehicle`)

| Field | Editable? | Notes |
|---|---|---|
| VIN | Never editable by any role | Immutable identifier |
| Dealer ID | Never editable by any role | Reassigning a vehicle to another dealer is out of scope |
| Model | Editable by Dealer Principal only | See Section 8 |
| Status | Editable by Dealer Principal and Dealer Staff | Most common day-to-day operational edit |
| Price | Editable by Dealer Principal only | |
| Days In Inventory | Never directly editable by any role | Always recomputed from `Last Updated`; any manual input is ignored/overwritten |
| Last Updated | Not directly editable; **system-set** to the current timestamp automatically whenever any other field on the record is successfully edited | Prevents users from backdating/future-dating records |

---

## 8. "Viewing As" Scoping Model (Mock Role-Based Access)

This is a **cosmetic, client-side mock**, not a security boundary. It is labeled as such in-app (a persistent banner: *"Viewing As is a prototype convenience, not access control — any user can change this."*) and in this document, per Section 2.

### 8.1 Complete Decision Table (resolves BA critique 1.1 — Dealer Staff row completed)

| Viewing As | Sees Records Where | Grid Edit Rights | Rejected Rows Panel | Chatbot Query Scope |
|---|---|---|---|---|
| **OEM Admin/Analyst** | All dealers, all vehicles | Read-only (no edit in prototype) | **Visible** | All dealers |
| **Dealer Principal** | `Dealer ID = selected dealer` only | Can edit: `Model`, `Status`, `Price`. Cannot edit `VIN`, `Dealer ID`, `Days In Inventory` | Not visible | Selected dealer only |
| **Dealer Staff** | `Dealer ID = selected dealer` only | Can edit: `Status` **only**. Cannot edit `VIN`, `Dealer ID`, `Model`, `Price`, `Days In Inventory` | Not visible | Selected dealer only |

### 8.2 Default State & Edge Cases (resolves BA critique 1.1 sub-items)

- **App startup default:** `role = OEM_ADMIN`, `dealerId = null`. Grid/Analytics/Chat immediately show all-dealer data — no picker is forced on load, since OEM Admin has no dealer dimension to select.
- **Switching to Dealer Principal or Dealer Staff:** the Dealer dropdown becomes **required and visible**. On first switch to either dealer role, it auto-selects the **first dealer alphabetically** from the derived dealer list (Section 6.3) so the UI is never in an ambiguous "role selected, no data scope" state. The user may then change the dealer selection freely (this is a prototype convenience — in reality a dealer user would only ever see their own dealer, but since there is no auth, the picker allows switching to demo all roles).
- **Selected dealer has zero vehicles** (possible given uneven seed distribution): Grid shows an explicit empty state — *"No vehicles found for this dealer"* — not a blank table indistinguishable from a loading state or bug.
- **Selected Dealer ID no longer present in the dataset:** Not reachable during normal operation since the dataset is static after `loadDataset` runs once at startup and is never re-loaded or mutated in a way that removes a dealer. Defined defensively anyway: if `services._applyScope` receives a `dealerId` with zero matching records anywhere in `dataStore.vehicles` (including rejected rows), it returns the same empty-state result as "zero vehicles," not an error — a missing dealer and an empty dealer are visually indistinguishable to the user by design, since distinguishing them offers no actionable value in a static-dataset prototype.

### 8.3 Dealer List Population Rule (resolves BA critique 1.2)

The "Viewing As" Dealer dropdown **must** be populated from `dataStore.dealers` — the distinct, valid `Dealer ID`/`Dealer Name` pairs derived from `dataStore.vehicles` after validation — sorted alphabetically by name. It must **never** be a hardcoded static list, because a hardcoded list could reference a dealer with zero valid records post-validation, producing an empty state indistinguishable from a bug (per BA rationale). This derivation runs once, immediately after `loadDataset` completes.

---

## 9. Service Contract Design (Function-Level API Surface)

This is a contract-first design even without HTTP — every function is pure with respect to its inputs (`(input, viewerContext) => envelope`), enabling a future migration to a real API as a rename, not a rewrite.

### 9.1 Response Envelope (used identically by grid, chart, and chat)

```
// success
{ success: true, data: <payload>, meta: { page?, pageSize?, total?, requestId } }

// failure
{ success: false, error: { code: "STRING_CODE", message: "human-readable, no internals" }, meta: { requestId } }
```

### 9.2 Function Surface

```
services.loadDataset(rawRows) -> envelope<LoadReport>
services.getVehicles(filters, pagination, viewerContext) -> envelope<Vehicle[]>
services.getVehicleById(id, viewerContext) -> envelope<Vehicle>
services.updateVehicle(id, patch, viewerContext) -> envelope<Vehicle>
services.getAnalyticsSummary(filters, viewerContext) -> envelope<AnalyticsSummary>
services.resolveChatQuery(text, viewerContext, conversationId) -> envelope<ChatResponse>
services.getRejectedRows(viewerContext) -> envelope<RejectedRow[]>
```

**`viewerContext` shape (mandatory on every call, no exceptions):**
```
{ role: "OEM_ADMIN" | "DEALER_PRINCIPAL" | "DEALER_STAFF", dealerId: string | null }
```

### 9.3 Scope Enforcement Rule

Every function's **first line of business logic** must call `services._applyScope(records, viewerContext)` before any filtering, sorting, or aggregation requested by the caller. This is not optional and not the caller's responsibility. Centralizing this here is what allows grid, chart, and chatbot to be **provably consistent** with each other, even though none of it constitutes real security (Section 12).

### 9.4 Pagination Rules (non-negotiable)

- `getVehicles` must **never** return the full dataset in one call.
- Default `pageSize: 25`; `maxPageSize: 100`.
- A request with `pageSize > 100` is **rejected** with `error.code = "INVALID_PAGINATION"` — never silently clamped — so bugs in calling code surface immediately rather than degrading silently.
- `getRejectedRows` is exempt from pagination (bounded by design to a small number of rows at prototype scale — see Section 11 for the explicit ceiling assumption) but still returns the standard envelope shape.

### 9.5 Access Rejection Behavior

If `updateVehicle` is called with a `viewerContext` whose role/dealer combination does not have edit rights for the requested field (per Section 7.3/8.1), the function returns `error.code = "FIELD_NOT_EDITABLE"` rather than silently ignoring the patch. The UI layer is responsible for disabling those inputs so this path is a defensive backstop, not the primary UX — consistent with the "centralize the rule, don't rely on the caller" principle in 9.3.

---

## 10. Chatbot Design & Query Resolution Strategy

### 10.1 Approach

Client-side, rule-based intent matching against a **fixed, enumerated set of supported query patterns**. No external LLM call (Section 3, "Why not X?"). `resolveChatQuery(text, viewerContext, conversationId)` normalizes input text (lowercase, trim, strip punctuation), matches against known intent patterns, executes the matching aggregation/lookup against `services._applyScope`-filtered data, and returns a natural-language templated response plus the underlying data payload (so the UI can optionally render a mini-table/chart alongside the text).

### 10.2 Supported Intents (resolves SA critique — "single largest capability gap" must be enumerated, not implied)

| # | Intent | Example Phrases (case-insensitive, keyword-matched) | Required Entities | Behavior |
|---|---|---|---|---|
| 1 | Count by status | "how many vehicles are in stock", "count in transit vehicles", "how many sold vehicles" | `status` (one of the 4 enum values, keyword-matched) | Returns count of scoped vehicles matching status. |
| 2 | Average/total price | "what's the average price of vehicles in stock", "total value of inventory" | optional `status` filter | Returns avg or sum of `Price` over scoped, optionally status-filtered vehicles. |
| 3 | Oldest inventory / aging | "which vehicles have been in inventory longest", "show oldest inventory", "aging report" | none | Returns top 5 scoped vehicles by `Days In Inventory` descending. |
| 4 | Dealer comparison (**OEM Admin only**) | "which dealer has the most vehicles in stock", "compare dealers by inventory count" | none | If `viewerContext.role !== "OEM_ADMIN"`, returns a scoping-refusal message (10.4). Otherwise aggregates vehicle counts grouped by Dealer. |
| 5 | VIN lookup | "show me vehicle VIN 1FA6P8TH5XXXXXXXX", "look up VIN <17 chars>" | 17-char alphanumeric token in message | Returns the single matching vehicle if it exists **and** is within scope; if it exists but is out of scope, returns the same "not found" message as if it didn't exist at all (see 10.5 — this is the leakage-prevention behavior). |
| 6 | Session edit summary ("what changed") | "what changed today", "what did I edit this session", "how many records changed" | none | Returns a summary built from `dataStore.sessionEditLog`, filtered to edits made **within the current browser session only** — **not** a historical trend, since there is no persistence across sessions. This is explicitly narrower than the PRD's "what changed this week" framing (Section 19, Assumption). |
| 7 | Unsupported/fallback | Any input not matching intents 1–6 | — | Returns a fixed fallback message listing example supported questions, plus a console log entry (`intent: "UNMATCHED"`) for later review of missed query patterns. |

### 10.3 Scoping Enforcement in Chat

Every intent's data access runs through the **same** `services._applyScope` used by grid and analytics — the chatbot does not have its own data-access path. This means whatever the currently selected "Viewing As" context is, the chatbot answers are constrained identically to what the grid/chart would show for that same context.

### 10.4 Scope-Restricted Intent Refusal

For intents restricted to a role (currently only #4), if invoked by an out-of-scope role, the response is a clear, non-technical refusal: *"Dealer comparison across all dealers is only available when Viewing As OEM Admin/Analyst."* This is logged to console as `intent: "DEALER_COMPARISON", outcome: "REFUSED_SCOPE"`.

### 10.5 Leakage-Prevention Behavior (mocked, not guaranteed — see Section 12)

For lookup-style intents (#5), if the requested record exists in the full dataset but falls outside the current `viewerContext` scope, the chatbot returns an identical "not found" response as if the record did not exist at all — it must **never** distinguish "doesn't exist" from "exists but you can't see it," since that distinction itself would leak information. This is a best-effort UX consistency behavior; because there is no server-side enforcement, it is **not a real security guarantee** (Section 12) and must not be represented as satisfying the PRD's zero-tolerance leakage metric.

### 10.6 Conversation State

`conversationId` is generated client-side per chat session (not persisted). Prior turns in the same conversation are **not** used to resolve ambiguous references in this prototype (e.g., "what about last week" following a prior question) — each message is resolved independently. This is a stated limitation, not a bug (Section 19).

---

## 11. Non-Functional Requirements

### 11.1 Dataset Scale Assumption (resolves SA critique — explicit numbers, not "prototype scale")

**[ASSUMPTION]** All targets below assume:
- ≤ 5,000 total raw rows processed at load (≤ 3,000 expected valid, remainder rejected/padding for test purposes)
- ≤ 12 dealers, 1 OEM
- ≤ 30 rejected rows in the seed fixture
- Single browser tab, single user, no concurrent multi-tab writes considered

If these assumptions are exceeded (e.g., a future seed file with 50,000 rows), the performance targets below are **not guaranteed** and virtualized rendering / indexing would need re-evaluation — flagged for the production roadmap (Section 18).

### 11.2 Performance Targets (per operation, in-memory, single-threaded)

| Operation | Target Latency | Basis |
|---|---|---|
| `loadDataset` (full seed parse + validate, one-time at app start) | ≤ 2 seconds | ≤5,000 rows, synchronous validation per row |
| `getVehicles` (25-row page, filtered/sorted) | ≤ 150 ms | Array filter/sort/slice over ≤5,000 in-memory records |
| `getVehicleById` | ≤ 50 ms | Indexed lookup (Map keyed by VIN or ID) |
| `updateVehicle` | ≤ 50 ms | In-memory mutation + edit log append |
| `getAnalyticsSummary` | ≤ 300 ms | Full-dataset aggregation (grouping/summing across ≤5,000 records) |
| `resolveChatQuery` | ≤ 300 ms | Pattern match + one aggregation pass, comparable to `getAnalyticsSummary` |
| `getRejectedRows` | ≤ 50 ms | ≤30 rows, no pagination needed |
| Initial page interactive (first paint to usable Grid tab) | ≤ 3 seconds | Includes CDN asset fetch (Tailwind, Chart.js) + seed JSON fetch + `loadDataset` on typical broadband |

### 11.3 Availability & Reliability

- **No uptime SLA applies** — this is a static, client-only artifact with no server component to be "up" or "down." Availability is bounded entirely by the user's browser and (for CDN assets) the CDN's availability.
- **Single external dependency at runtime:** the CDN-hosted Tailwind CSS and Chart.js scripts. **Failure mode:** if the CDN is unreachable, styling and/or charts will fail to render; the app must still load the Grid tab's raw HTML table with unstyled/degraded CSS rather than a blank white screen (graceful degradation requirement, not optional).
- **Seed data fetch failure mode:** if `/data/vehicles.seed.json` fails to load (404, malformed JSON, network error), the app must show a clear, user-facing error state ("Unable to load vehicle data — please refresh") rather than a silent blank grid, and must log the failure to console with the underlying error.

### 11.4 Throughput & Concurrency

- **Not applicable in the traditional sense** — single user, single browser tab, no server to receive concurrent requests.
- Explicitly **not designed for**: multiple users editing shared data concurrently, multi-tab synchronization, or any notion of "requests per second." Any of these would require the backend/persistence layer explicitly deferred in Section 18.

### 11.5 Browser Compatibility

- Target: current stable versions of Chrome, Edge, Firefox, Safari (evergreen browsers). No IE11 or legacy browser support.
- No mobile-specific responsive design requirement stated in the product idea; **[ASSUMPTION]** basic responsive layout (Tailwind's default breakpoints) is applied opportunistically but not a tested requirement for this prototype.

---

## 12. Security & Data Protection Posture

**This section exists to prevent misinterpretation of Sections 8 and 10 as real security controls.**

- **No authentication.** Any person with the URL/file can open the app and act as any role.
- **No authorization enforcement at a trust boundary.** All "scoping" (Section 8) is implemented in client-side JavaScript that any user could bypass via browser dev tools (editing `viewerContext` directly, or calling `services.*` functions from the console with an arbitrary `viewerContext`).
- **No data protection in transit or at rest** beyond whatever the browser/OS/filesystem already provides — there is no transmitted data beyond the initial static asset fetch (no user data ever leaves the browser).
- **No audit trail.** `dataStore.sessionEditLog` exists only to support the chatbot's "what changed" intent (Section 10.2, #6) within a session — it is not a security audit log, is never persisted, and is lost on refresh.
- **Explicit non-goals for this artifact**, all deferred to Section 18: server-enforced tenant isolation, RBAC, audit logging with retention, zero cross-tenant leakage guarantee, encryption at rest, secrets management (moot — there are no secrets, no API keys, no credentials in this build).
- **In-app labeling requirement:** the "Viewing As" control (Section 8) must display a persistent, visible disclaimer that it is a prototype convenience and not an access control mechanism. This is a product requirement, not a suggestion — it exists specifically so this prototype cannot be mistaken for, or demoed as, a secure multi-tenant system.

---

## 13. Observability & Logging Strategy

Per guardrails: browser console logging only, no monitoring service.

- **Log once per service-boundary call**, not inside loops, per the Backend Engineer's contract discipline. Every `services.*` function call logs a single structured line on entry and exit:
  ```
  console.log({ requestId, fn: "getVehicles", viewerContext, durationMs, outcome: "success"|"error", errorCode? })
  ```
- **`requestId`** is a client-generated UUID-like string (e.g., timestamp + random suffix), created fresh per call, included in both the log line and the response envelope's `meta.requestId`, so a user-reported issue ("the chart looked wrong") can be correlated to a specific console log entry during a support/demo session.
- **Chatbot-specific logging:** every `resolveChatQuery` call logs the matched intent (or `"UNMATCHED"`), the `viewerContext`, and whether any scope-restriction refusal occurred (Section 10.4) — this is the closest the prototype gets to the PRD's audit intent, and is explicitly documented as **console-only, non-persistent, and not a substitute for real audit logging** (Section 18).
- **Load-time logging:** `loadDataset` logs a summary line: total rows processed, valid count, rejected count, breakdown by reason code.
- No PII beyond what's already in the mock dataset (which contains no real customer/personal data — vehicle inventory records only).

---

## 14. Error Handling Strategy

### 14.1 Error Codes (enumerated, extend only with team agreement)

| Code | Meaning | Raised By |
|---|---|---|
| `INVALID_VIN` | Row failed VIN validation at load | `loadDataset` |
| `UNKNOWN_DEALER` | Row references a Dealer ID not present in the known dealer list at load | `loadDataset` |
| `MISSING_MODEL` | Row missing required Model field | `loadDataset` |
| `INVALID_STATUS` | Row status not one of the 4 enum values | `loadDataset` |
| `PRICE_OUT_OF_RANGE` | Row price outside 0–500,000 | `loadDataset` |
| `INVALID_DATE` | Row Last Updated not a valid, non-future ISO date | `loadDataset` |
| `INVALID_PAGINATION` | Caller requested `pageSize > 100` or negative/zero page | `getVehicles` |
| `NOT_FOUND` | Requested vehicle ID/VIN does not exist **or** exists but is out of scope (indistinguishable, Section 10.5) | `getVehicleById`, `updateVehicle`, chat VIN lookup |
| `FIELD_NOT_EDITABLE` | Patch attempted a field the current role cannot edit (Section 7.3) | `updateVehicle` |
| `DATASET_LOAD_FAILED` | Seed JSON fetch or parse failed | app bootstrap |
| `UNMATCHED_INTENT` | Chat input didn't match any known pattern (not a true "error," logged as informational, returned as a normal success envelope with a fallback message — not an `error` envelope, since it's expected user behavior, not a system fault) | `resolveChatQuery` |

### 14.2 UI Presentation Rules

- Load-time validation errors (`INVALID_VIN`, etc.) are **never** shown as pop-up alerts — they populate the Rejected Rows panel (Section 7.2) only.
- Runtime errors (`NOT_FOUND`, `FIELD_NOT_EDITABLE`, `INVALID_PAGINATION`) surface as inline, non-blocking UI messages near the relevant control (e.g., a disabled-field tooltip for `FIELD_NOT_EDITABLE`), never as raw JSON or stack traces.
- `DATASET_LOAD_FAILED` is the one condition that blocks the entire app with a full-screen error state, since no tab can function without data.
- All error messages shown to users are human-readable and contain **no internal implementation details** (no stack traces, no raw error codes) — the code is for logs/QA only.

---

## 15. Data Flows

### 15.1 App Bootstrap / Dataset Load

```
App start
  → fetch /data/vehicles.seed.json
  → services.loadDataset(rawRows)
      → per-row validation (Section 7.1)
      → valid rows → dataStore.vehicles[]
      → invalid rows → dataStore.rejectedRows[] (with reason code)
      → derive dataStore.dealers[] from valid vehicles (Section 6.3/8.3)
  → console.log load summary
  → ui.viewingAs initializes to { role: OEM_ADMIN, dealerId: null }
  → ui.grid renders first page (services.getVehicles)
```

### 15.2 Grid View / Filter / Edit

```
User changes "Viewing As" → new viewerContext broadcast
  → ui.grid re-calls services.getVehicles(currentFilters, currentPagination, viewerContext)
User edits a cell
  → ui.grid calls services.updateVehicle(id, patch, viewerContext)
      → services._applyScope check: is this vehicle in scope for viewerContext?
      → field-editability check (Section 7.3)
      → on success: mutate dataStore.vehicles, set Last Updated = now,
        recompute Days In Inventory, append dataStore.sessionEditLog
      → return envelope
  → ui.grid re-renders affected row
```

### 15.3 Analytics View

```
User opens Analytics tab (or changes Viewing As / filters)
  → ui.analytics calls services.getAnalyticsSummary(filters, viewerContext)
      → services._applyScope filters records first
      → aggregation (counts by status, avg price, dealer comparisons if in scope)
  → ui.analytics renders Chart.js charts from returned data
```

### 15.4 Chatbot Query

```
User types a message → ui.chat calls services.resolveChatQuery(text, viewerContext, conversationId)
  → normalize text
  → match against enumerated intents (Section 10.2)
  → on match: services._applyScope-filtered data lookup/aggregation → templated response
  → on no match: fallback response, log UNMATCHED_INTENT
  → ui.chat appends both user message and bot response to the visible thread
```

---

## 16. Deployment Topology

- **Artifact:** a small set of static files — `index.html`, JS modules (`dataStore.js`, `services.js`, `ui.*.js`), and the seed data file `/data/vehicles.seed.json`. No server-side code, no build step.
- **Hosting:** any static file host (e.g., open `index.html` directly from disk, or serve the folder via any static file server — Python's `http.server`, `npx serve`, GitHub Pages, etc.). No specific hosting provider is mandated or assumed.
- **No environments** (dev/staging/prod distinction is not meaningful for a single static artifact with no backend config to vary) — there is one build, run anywhere a static file can be served.
- **No CI/CD pipeline** — per guardrails, manual build/run. There is nothing to "build" beyond having the files present; "deployment" is a file copy.

---

## 17. Testing Strategy

Manual smoke-test checklist (per guardrails; no automated framework mandated). To be run after any code change before considering the prototype demo-ready.

1. **Load:** App loads without console errors; load summary shows expected valid/rejected counts.
2. **Rejected Rows visibility:** Confirm panel is visible under OEM Admin, absent under Dealer Principal and Dealer Staff; confirm reason codes match seeded invalid rows.
3. **Viewing As — OEM Admin:** Grid shows all 12 dealers' vehicles; Analytics shows dealer-comparison chart; Chat answers a dealer-comparison question (intent #4) successfully.
4. **Viewing As — Dealer Principal:** Switch to a specific dealer; Grid shows only that dealer's vehicles; attempt to edit Model/Status/Price (should succeed) and VIN (should be non-editable); Chat's dealer-comparison question (intent #4) returns the scope-refusal message.
5. **Viewing As — Dealer Staff:** Same dealer as above; confirm only Status is editable, Model/Price edit attempts are blocked (`FIELD_NOT_EDITABLE`).
6. **Empty dealer state:** Select a dealer known to have zero (or very few) vehicles in the seed data; confirm explicit empty-state messaging, not a blank/ambiguous grid.
7. **Pagination boundaries:** Request page size > 100 via console (`services.getVehicles`) and confirm `INVALID_PAGINATION` is returned, not silently clamped.
8. **Chatbot — each of the 7 intents:** Manually exercise one example phrase per intent (Section 10.2) under at least one role each, confirm expected response shape and scope behavior.
9. **Chatbot leakage-style check (mocked, not guaranteed):** As a Dealer Principal for Dealer A, attempt a VIN lookup for a known Dealer B vehicle; confirm response is the same "not found" message as a nonexistent VIN.
10. **Session edit summary:** Make 2–3 edits, then ask the chatbot "what changed today"; confirm the summary reflects only session edits, not historical/persisted data.
11. **CDN degradation:** Simulate blocked CDN (e.g., via browser dev tools request blocking) and confirm Grid tab still renders a usable (if unstyled) table rather than a blank page.
12. **Seed load failure:** Rename/remove the seed JSON temporarily and confirm the full-screen `DATASET_LOAD_FAILED` error state appears instead of a silent blank app.

---

## 18. Out of Scope / Deferred to Production Roadmap

Explicitly deferred — **not silently dropped** — from PRD.md's production-grade requirements:

| PRD Requirement | Status in This Prototype | Production Roadmap Note |
|---|---|---|
| Server-enforced authentication | **Absent** | Add real auth (session or token-based) before any real deployment beyond a local demo. |
| Server-enforced tenant isolation / RBAC | **Mocked client-side only** (Section 8) | Move `_applyScope` logic server-side; treat every client-provided `viewerContext` as untrusted. |
| Audit trail with weekly review (access violations) | **Absent** — console log only, non-persistent | Requires backend + persistent store (SQLite as the pre-approved next step) + retention policy. |
| Zero cross-tenant chatbot leakage (100% target) | **Best-effort UX consistency only** (Section 10.5); **not guaranteed** | Requires server-side scope enforcement on every chatbot data access, plus the QA adversarial test suite the PRD specifies. |
| Real data ingestion pipeline (P0-5) | **Partially mocked**: static seed file + one-time validation + Rejected Rows panel | Requires a real import/ingestion service, likely file upload + backend validation, plus a correction/resubmit workflow. |
| Real conversational chatbot (LLM-backed) | **Rule-based, fixed intents only** (Section 10.2) | Requires an external LLM API integration — explicitly out of scope for this build profile; would need its own data-leakage-prevention design (e.g., retrieval scoped server-side before any prompt construction). |
| Data persistence across sessions | **Absent** — in-memory only | SQLite is the pre-approved next step if this becomes a real requirement. |
| Multi-user concurrent access / conflict resolution | **Absent** — single user, single tab assumption | Requires a real backend with concurrency control (optimistic locking, etc.). |
| Role list finalization / org title validation (PRD Open Questions) | **Assumed as 3 roles** (OEM Admin/Analyst, Dealer Principal, Dealer Staff) per BA decision | **[DECISION NEEDED]** — must be validated with real customers before production. |
| Business domain finalization | **Assumed as Vehicle Inventory** per BA decision (Section 2, 6) | **[DECISION NEEDED]** — PRD explicitly flagged this as needing stakeholder ratification; not done here. |

---

## 19. Assumptions Log

All `[ASSUMPTION]` items from this document, consolidated:

1. **Domain:** Vehicle Inventory chosen as the concrete business domain (Section 2, 6) — resolves PRD's open item for prototype scope only; not a business decision.
2. **Dataset scale:** ≤5,000 raw rows, ≤3,000 valid vehicles, ≤12 dealers, 1 OEM, ≤30 rejected rows (Section 6.3, 11.1) — governs all performance targets and pagination defaults.
3. **Chatbot NLU:** Rule-based/keyword intent matching, not an LLM integration (Section 3, 10) — driven by guardrails disallowing external API integrations by default.
4. **Chatbot "what changed" scope:** Limited to in-session edits only, not a historical/weekly trend as the PRD's success metric example implies (Section 10.2, #6) — no persistence exists to support the broader framing.
5. **Rejected Rows visibility:** Restricted to OEM Admin role only (Section 7.2) — a scoping decision not explicitly stated in the PRD, made to keep ingestion/data-quality concerns at the OEM tenant level.
6. **Role list:** Three roles only (OEM Admin/Analyst, Dealer Principal, Dealer Staff), per BA's Final Round decision — PRD flagged the final role list as `[DECISION NEEDED]`; treated as resolved for prototype scope only.
7. **Responsive design:** Opportunistic via Tailwind defaults, not a tested requirement (Section 11.5).
8. **No conversation memory:** Each chatbot message resolved independently; no multi-turn context resolution (Section 10.6).

Remaining genuine open items (not resolved by this prototype, correctly flagged for stakeholders, not for the frontend implementer):

- **[DECISION NEEDED]** Final confirmed business domain for any production rebuild (PRD Section 5).
- **[DECISION NEEDED]** Final confirmed role list and permitted actions per role for any production rebuild (PRD Section 5).

---

## 20. Traceability Matrix

| PRD Item | TRD Treatment | Section |
|---|---|---|
| Data Grids (core capability) | Hand-rolled table, sort/filter/paginate, in-scope, fully specified | 3, 5, 9, 15.2 |
| Visualization/Analysis (core capability) | Chart.js against `getAnalyticsSummary`, in-scope, fully specified | 3, 5, 9, 15.3 |
| Conversational Chatbot (core capability) | Rule-based, 7 enumerated intents, in-scope with documented limitations | 3, 10, 15.4 |
| OEM consolidated cross-dealer view (Persona 1 / Goal 1) | Mocked via "Viewing As = OEM Admin," fully in scope for UI behavior, not backed by real tenant isolation | 8 |
| Dealer self-service view (Persona 2/3 / Goal 2) | Mocked via "Viewing As = Dealer Principal/Staff," fully in scope for UI behavior | 8 |
| Reduced time-to-insight via chatbot (Goal 3) | In scope for the 7 supported intents; not a general-purpose NLU | 10 |
| Strict, verifiable OEM/Dealer access boundaries (Goal 4) | **Not achievable in this build** — explicitly mocked, not verifiable, per Section 2 | 8, 12, 18 |
| Trustworthy, auditable ingestion (Goal 5 / P0-5) | Partially addressed: validation + Rejected Rows panel; no real audit trail | 7, 13, 18 |
| Success Metric: ≥90% correct + in-scope chatbot answers | Not measurable without a real QA regression harness against live data; enumerated intents are internally consistent but this metric is **not validated** in this build | 10, 18 |
| Success Metric: 100% zero cross-tenant leakage | **Not achievable** — no server-side enforcement exists (Section 12) | 12, 18 |
| Success Metric: 0 data access violations | **Not measurable** — no audit logging exists beyond console | 13, 18 |
| Success Metric: ≥95% import validation pass rate | Addressed structurally (validation rules exist and are enforced at load); actual seed data's pass rate is a function of the fixture, not a system guarantee | 7 |