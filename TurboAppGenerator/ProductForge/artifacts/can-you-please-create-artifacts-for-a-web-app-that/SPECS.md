# SPECS.md
## OEM–Dealer Data & Insights Platform — Prototype Build Specification

**Document Owner:** Solutions Architecture
**Status:** Draft — Part 1 of 4
**Traces to:** PRD.md v1.1, TRD.md v1.1

> This document is the only artifact in this pipeline containing code, schemas, and exact contracts. PRD/TRD remain conceptual; this document must be precise enough that an AI coding agent can implement without follow-up questions. Where a decision is genuinely unresolved upstream, it is marked **[DECISION NEEDED]** rather than assumed.

---

## Table of Contents

1. Project Structure
2. Technology Stack & Versions
3. Environment Configuration
4. Data Models & Schema
5. Service Contracts (`dataStore.*`, `services.*`) — *Part 2*
6. Viewing-As Scoping Model — Implementation Spec — *Part 2*
7. Chatbot Design — Intent Catalog & Resolution Logic — *Part 2*
8. UI Component Specs (Grid, Charts, Chat, Viewing-As Selector) — *Part 3*
9. Data Grid Behavior Spec (sort/filter/pagination) — *Part 3*
10. Visualization/Analytics Spec (chart types, data bindings) — *Part 3*
11. Error Handling & Validation Rules — *Part 3*
12. Mock Data Generation Script Spec — *Part 4*
13. Observability / Logging Spec — *Part 4*
14. Security & Data Protection Notes (mock boundaries) — *Part 4*
15. Testing Plan & Smoke Checklist — *Part 4*
16. Deployment & Build Instructions — *Part 4*
17. Traceability Matrix (PRD/TRD → SPECS) — *Part 4*

---

## 1. Project Structure

Single self-contained, client-only static artifact. No build step, no package manager required to *run* the app. A Node.js script exists only as dev-time tooling to generate the bundled mock dataset — it is not shipped or executed by the app at runtime.

```
oem-dealer-platform/
├── index.html                     # Single entry point; tab shell (Grid / Analytics / Chat) + Viewing-As selector
├── README.md                      # How to run (open index.html or serve statically), how to regenerate mock data
│
├── css/
│   └── styles.css                 # Small set of custom rules Tailwind utility classes can't express
│                                   # (e.g., custom scrollbar for grid, chat bubble tails). No Tailwind build — Tailwind loaded via CDN in index.html.
│
├── js/
│   ├── config.js                  # App-wide constants (page size, max records, data file path, schemaVersion). See Section 3.
│   ├── main.js                    # Bootstraps app: loads data, initializes dataStore, wires ui.* modules, sets default viewingAs
│   ├── dataStore.js               # In-memory store: raw entities, integrity checks, indexes, getScopedRecords()
│   ├── services.js                # services.* contract layer (getVehicles, getDealers, getAnalyticsSummary, etc.) — spec'd in Part 2
│   ├── chatbotEngine.js           # Rule-based intent matcher + resolvers; consumes services.* only — spec'd in Part 2
│   │
│   ├── ui/
│   │   ├── viewingAs.js           # Renders + manages the global "Viewing As" role/dealer selector control
│   │   ├── grid.js                # Renders data grid tab: table, sort/filter controls, pagination controls
│   │   ├── charts.js              # Renders analytics tab: Chart.js chart instances bound to services.getAnalyticsSummary()
│   │   └── chat.js                # Renders chat tab: message list, input box, calls chatbotEngine.handleMessage()
│   │
│   └── utils/
│       ├── validators.js          # viewingAs validation, record validation helpers (fail-closed checks)
│       └── format.js              # Currency/date/number formatting helpers used across grid/charts/chat
│
├── data/
│   └── mockData.json              # Bundled static dataset: schemaVersion + oem + dealers[] + vehicles[]. Loaded once via fetch() at startup.
│
├── scripts/
│   └── generate-mock-data.js      # Node.js (dev-only, NOT shipped/served). Regenerates data/mockData.json with referential integrity + stable IDs.
│                                   # Run manually: `node scripts/generate-mock-data.js`. Requires Node 18+.
│
└── tests/
    └── smoke-checklist.md         # Manual smoke-test checklist (Section 15, Part 4)
```

**Rules governing this structure:**
- No `node_modules/`, no `package.json` is required to **run** the app — `index.html` opened directly (or served statically) must work standalone, loading Tailwind and Chart.js from CDN and `mockData.json` via a relative `fetch()`.
- `scripts/generate-mock-data.js` is the only file in the repo requiring Node.js, and only for regenerating `data/mockData.json`. It must never be referenced by `index.html` or any browser-loaded script.
- Script load order in `index.html` is fixed and must be: `config.js` → `dataStore.js` → `services.js` → `chatbotEngine.js` → `utils/*.js` → `ui/*.js` → `main.js` (all as plain `<script>` tags, no ES module bundler required; `defer` attribute on all).
- **[DECISION NEEDED]** Whether to convert `js/*.js` files to native ES modules (`<script type="module">`) instead of global namespace objects (`dataStore`, `services`, `ui`, `chatbotEngine` as `window`-level objects). This spec assumes **global namespace objects**, matching TRD Section 3's `dataStore.* / services.* / ui.*` naming — not ES modules — to avoid CORS-on-`file://` issues when a user opens `index.html` directly without a server.
- All entity IDs (`vehicleId`, `dealerId`, `oemId`) referenced anywhere in `js/*` are treated as **opaque, pre-generated strings** — no browser-side code may generate a new entity ID at runtime. ID generation is the exclusive responsibility of `scripts/generate-mock-data.js` (see Section 4.6).

---

## 2. Technology Stack & Versions

| Layer | Technology | Version / Source | Notes |
|---|---|---|---|
| Markup | HTML5 | — | Single page, semantic sectioning for the three tabs |
| Styling | Tailwind CSS | Play CDN, `<script src="https://cdn.tailwindcss.com"></script>` | **[ASSUMPTION]** Play CDN serves the latest Tailwind v3.x build and cannot be pinned to an exact patch version by URL. Acceptable for a prototype; flagged in Section 14 (Part 4) as a production gap (pin via build step later). |
| Custom CSS | Plain CSS3 | — | `css/styles.css`, minimal, only for what Tailwind utilities can't do |
| Charting | Chart.js | `4.4.4`, pinned via `https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js` | Exact version pinned (unlike Tailwind) since jsdelivr supports version-locked URLs |
| App logic | Vanilla JavaScript | ES2020+, no transpilation | Target: latest 2 versions of Chrome, Edge, Firefox, Safari. No IE11/legacy support. |
| Data format | JSON | — | `data/mockData.json`, static, fetched once at app start |
| Mock data generator | Node.js | `18.x LTS` or later (dev-only) | Used only to run `scripts/generate-mock-data.js`; not part of the shipped app |
| Persistence | None | — | In-memory only; browser session; lost on refresh (per TRD Section 3) |
| Backend | None | — | No HTTP server; all "services" are in-process JS function calls |
| Auth | None | — | Per guardrails and TRD Section 2 |
| Hosting | Static file hosting or `file://` | — | No cloud infra; `index.html` must work opened directly or via any static server (e.g., `python -m http.server`) |
| Testing | Manual | `tests/smoke-checklist.md` | No automated test framework in this build |
| Observability | Browser console | — | `console.log` / `console.warn` / `console.error` only, per conventions in Section 13 (Part 4) |

### Why these exact pins?
- Chart.js is pinned to an exact version (`4.4.4`) because chart config APIs can change between minor versions and this app hard-codes chart config objects against that API surface — an unpinned CDN URL risks silent breakage on a future Chart.js release.
- Tailwind is **not** pinned because the Play CDN product does not support version-locked utility generation the way a build-time Tailwind install would; this is an accepted prototype-only trade-off (see Section 14, Part 4, for the production remediation: install Tailwind via npm + PostCSS build when this app graduates past prototype).

### Why not X?
- **Why not a real backend?** No persistence, concurrency, or server-enforced security is required at this scope (see TRD §3). A backend would add operational burden with no functional payoff.
- **Why not a full grid library (AG Grid, Handsontable)?** Justified only at row counts/virtualization needs this prototype doesn't have (see Section 4.5 — dataset capped at ~2,000–3,000 rows).
- **Why not a real LLM API?** Disallowed by guardrails absent an explicit request; a rule-based intent matcher (Section 7, Part 2) satisfies the stated UX within a documented, fixed scope.

---

## 3. Environment Configuration

**There are no runtime environment variables.** This is a static client-only application with no server process, no build step, and no `.env` file. `process.env` must never appear in any file under `js/`.

### 3.1 Application Configuration Constants (`js/config.js`)

All tunables are hard-coded JS constants (not env vars), loaded first in script order so every other module can reference `window.APP_CONFIG`.

```js
// js/config.js
window.APP_CONFIG = Object.freeze({
  SCHEMA_VERSION: "1.0.0",           // Must match data/mockData.json's top-level schemaVersion exactly
  DATA_FILE_PATH: "./data/mockData.json",

  // Pagination defaults (see Section 9, Part 3 — Grid Behavior Spec)
  DEFAULT_PAGE_SIZE: 50,
  MAX_PAGE_SIZE: 200,

  // Dataset size guardrails (see Section 4.5) — used by integrity checks to warn, not to hard-fail
  EXPECTED_OEM_COUNT: 1,
  EXPECTED_MIN_DEALERS: 8,
  EXPECTED_MAX_DEALERS: 10,
  EXPECTED_MIN_VEHICLES: 2000,
  EXPECTED_MAX_VEHICLES: 3000,

  // Chatbot (see Section 7, Part 2)
  CHAT_MAX_HISTORY_MESSAGES: 50,     // In-memory chat transcript cap per session; oldest messages dropped beyond this

  // Viewing-As mock roles (see Section 6, Part 2)
  VALID_ROLES: ["OEM_ADMIN", "OEM_ANALYST", "DEALER_PRINCIPAL", "DEALER_STAFF"],
});
```

### 3.2 Mock Data Generation Script Parameters (dev-only, Node.js CLI — not app env vars)

`scripts/generate-mock-data.js` accepts optional CLI flags (with defaults) — these are **not** consumed by the browser app and must not be read via `process.env` anywhere in `js/`:

| Flag | Default | Description |
|---|---|---|
| `--dealerCount` | `9` | Number of dealers to generate (must fall within 8–10 per Section 4.5) |
| `--vehicleCount` | `2500` | Total vehicles to generate across all dealers (must fall within 2000–3000) |
| `--seed` | `42` | Deterministic RNG seed — reruns with the same seed must produce identical output, so chatbot test fixtures (Part 2/4) don't drift between regenerations |
| `--outFile` | `./data/mockData.json` | Output path |

**Rule:** Running the script with the same `--seed` value must be idempotent (byte-identical output) to keep any hard-coded chatbot QA fixtures valid across regenerations. The script must use a seeded PRNG (e.g., a small mulberry32/xorshift implementation embedded in the script — no external RNG package) rather than `Math.random()`, which cannot be seeded.

### 3.3 What is explicitly NOT configured

- No API base URL (no API exists — all calls are in-process function calls per TRD §3/§4).
- No auth config, token, or session storage key (no auth exists per Section 2 scope resolution).
- No feature flags — the mock role list in `VALID_ROLES` is the only "environment-like" toggle, and it is fixed at build time in `config.js`, not overridable at runtime by end users.

---

## 4. Data Models & Schema

This section defines the **exact, binding shape** of every entity in `data/mockData.json` and the in-memory `dataStore`. Nothing here is illustrative — an AI coding agent must implement these shapes verbatim. The concrete business domain for this prototype build is **Vehicle Inventory** (per TRD §2, resolving PRD §5's open `[DECISION NEEDED]` for prototype purposes only).

### 4.1 Entity-Relationship Overview

```
OEM (1)
  └── Dealer (8–10)
         └── Vehicle (2,000–3,000 total, distributed across dealers)
```

- Exactly **one** OEM per dataset (single-tenant-root prototype; PRD's multi-OEM future is out of scope — see Section 18, Part 4).
- Every `Dealer.oemId` must resolve to the single `oem.oemId`.
- Every `Vehicle.dealerId` must resolve to exactly one entry in `dealers[]`.
- There is no entity below Vehicle (no line items, no history/audit table) in this prototype.

### 4.2 Top-Level JSON File Shape (`data/mockData.json`)

```ts
interface MockDataFile {
  schemaVersion: string;   // e.g. "1.0.0" — MUST exactly match window.APP_CONFIG.SCHEMA_VERSION
  generatedAt: string;     // ISO-8601 timestamp, set by the generator script at write time
  generatorSeed: number;   // the --seed value used to produce this file (traceability/debug aid)
  oem: OEM;
  dealers: Dealer[];
  vehicles: Vehicle[];
}
```

**Rule:** `dataStore.init()` (Section 8, Part 2) must reject the file (→ `status = 'FAILED'`) if `schemaVersion` is missing or does not match `window.APP_CONFIG.SCHEMA_VERSION`. This is a hard-fail, not a warning — a schema mismatch means the parsing code below cannot be trusted against the data.

### 4.3 `OEM` Entity

```ts
interface OEM {
  oemId: string;      // Format: "OEM-001" — fixed, single record in this dataset
  name: string;        // e.g. "Acme Motors" (generator may hard-code or randomize from a small name list)
  regions: string[];   // e.g. ["Northeast", "Midwest", "West"] — union of all dealer regions, written by generator
}
```

### 4.4 `Dealer` Entity

```ts
interface Dealer {
  dealerId: string;    // Format: "DLR-001" through "DLR-010" — sequential, zero-padded to 3 digits
  oemId: string;        // Must equal the single OEM's oemId — FK, validated at load (Section 4.7)
  name: string;          // e.g. "Northgate Motors"
  region: string;        // One of a fixed enum set written by the generator, e.g. "Northeast" | "Southeast" | "Midwest" | "West" | "Southwest"
}
```

- **Count constraint:** 8–10 records total (`EXPECTED_MIN_DEALERS` / `EXPECTED_MAX_DEALERS`).

### 4.5 `Vehicle` Entity

```ts
interface Vehicle {
  vehicleId: string;              // Format: "VEH-00001" through "VEH-99999" — sequential, zero-padded to 5 digits. PRIMARY KEY.
  vin: string;                     // 17-char synthetic VIN, generator-produced, unique per vehicle (not a real VIN checksum — cosmetic only)
  oemId: string;                    // Denormalized copy of the owning dealer's oemId — write-once by generator (see Section 4.8)
  dealerId: string;                  // FK → Dealer.dealerId — validated at load (Section 4.7)
  dealerName: string;                 // Denormalized copy of Dealer.name at generation time (see Section 4.8)
  region: string;                      // Denormalized copy of Dealer.region at generation time (see Section 4.8)
  make: string;                         // e.g. "Toyota" — drawn from a fixed small enum list in the generator
  model: string;                         // e.g. "Camry" — drawn from a make-appropriate fixed list
  year: number;                            // Integer, e.g. 2021–2025 range
  trim: string;                             // e.g. "SE", "Limited" — free-form short string from a fixed list
  status: "in-stock" | "sold" | "in-transit" | "reserved";  // Fixed enum — exactly these 4 string literals, case-sensitive
  price: number;                             // USD, integer cents-free (e.g. 28500 = $28,500), > 0
  cost: number;                               // USD, integer, > 0, always ≤ price (generator-enforced invariant)
  dateReceived: string;                         // ISO-8601 date, e.g. "2024-11-03"
  dateSold: string | null;                        // ISO-8601 date if status === "sold", else null — generator-enforced invariant
}
```

**Derived field — computed at load time, never stored in JSON:**

```ts
interface VehicleWithDerived extends Vehicle {
  daysInInventory: number;   // Computed once by dataStore.init() as:
                              //   (status === "sold" ? dateSold : "today") - dateReceived, in whole days
                              // Recomputed only on a fresh dataStore.init() call (i.e., on page load) — NOT
                              // recomputed reactively as time passes during a session. A session left open
                              // across midnight will show a stale daysInInventory value until refresh; this
                              // is an accepted prototype limitation (see Section 18, Part 4).
}
```

- **Count constraint:** 2,000–3,000 total records (`EXPECTED_MIN_VEHICLES` / `EXPECTED_MAX_VEHICLES`), distributed across dealers by the generator (even-ish distribution is sufficient; exact balancing is not a requirement).
- **Business invariants enforced by the generator (not re-validated at runtime beyond referential integrity — see Section 4.7):** `cost ≤ price`; `dateSold` present if and only if `status === "sold"`; `dateReceived ≤ dateSold` when both present.

### 4.6 Primary Key Strategy

- All IDs (`oemId`, `dealerId`, `vehicleId`) are **generated exactly once, at build time, by `scripts/generate-mock-data.js`**, using deterministic sequential formats (not UUIDs — sequential IDs make manual QA and chatbot test fixtures easier to read and debug).
- **Browser-side code must never generate a new entity ID.** `dataStore.js` and `services.js` treat all IDs as opaque, pre-assigned strings.
- Because IDs are written once into `data/mockData.json` and the app has no persistence layer, IDs are stable **within a single generated dataset** but will **not** be stable across a re-run of the generator with different `--vehicleCount`/`--dealerCount` values (they will be stable across re-runs with the *same* flags and seed, per the idempotency rule in Section 3.2). Any hard-coded chatbot QA fixture (Part 2/4) that references a specific `vehicleId` or `dealerId` must be regenerated if the generator is re-run with different flags.

### 4.7 Referential Integrity — Validated at Load Time

Referential integrity is enforced twice — once cosmetically by the generator (it should never intentionally produce a dangling reference), and **authoritatively by `dataStore.init()` at every app load**, since the JSON file is an untrusted external artifact as far as the running app is concerned.

**Rules enforced in `dataStore.init()` (see Section 8, Part 2 for full function spec):**
1. Every `dealer.oemId` must equal `oem.oemId`. If not, exclude that dealer, record an `IntegrityError`, `console.error`.
2. Every `vehicle.dealerId` must resolve to a surviving entry in `dealers[]` (post step 1). If not, exclude that vehicle, record an `IntegrityError`, `console.error`.
3. Excluded records are **never** included in any `dataStore` getter output (including `getScopedRecords()`) — exclusion happens once, at load, and is permanent for the session.
4. Integrity failures do **not** halt app startup (unlike a `schemaVersion` mismatch, which does — Section 4.2). A partially-clean dataset still renders; the app is simply missing the bad records. This distinction (hard-fail vs. exclude-and-continue) must be preserved exactly — see Section 11 (Part 3) for the full error-handling matrix.

```ts
interface IntegrityError {
  recordType: 'vehicle' | 'dealer';
  recordId: string;
  reason: string;              // e.g. "dealerId 'DLR-099' not found in dealers[]"
  excludedFromDataset: true;
}
```

- `integrityErrors[]` accumulated during load is retained for the life of the session (never cleared) and is surfaced via `services.getSystemHealth()` (Section 5, Part 2) so the UI can optionally show a "N records excluded" notice — this is a data-quality signal, not a security boundary.

### 4.8 Denormalization Rule (`dealerName`, `region`, `oemId` on `Vehicle`)

- `dealerName`, `region`, and `oemId` on each `Vehicle` record are **derived/duplicated data**, written once by the generator script at dataset creation time by copying the values from the corresponding `Dealer`/`OEM` record at that moment.
- These denormalized fields are **never re-derived or re-synced at runtime**. If a future change to a `Dealer.name` or `Dealer.region` were made (there is no in-app edit capability for dealers in this prototype — see Section 18, Part 4), existing `Vehicle` records would **not** reflect that change until the mock dataset is regenerated from scratch.
- Any in-session vehicle field edit (via the grid — see Section 9, Part 3) applies only to editable vehicle fields (e.g., `status`, `price`) and must **never** allow editing `dealerName`, `region`, or any FK field (`dealerId`, `oemId`) directly, since that would desynchronize the denormalized copy from its source without any reconciliation mechanism in this build.

### 4.9 Dataset Size Rationale (Why 8–10 dealers / 2,000–3,000 vehicles?)

- Large enough that cross-dealer analytics (PRD Persona 1 — Priya) produce meaningful, non-trivial comparisons.
- Small enough that no virtualization, indexing beyond simple in-memory array filters, or pagination-at-the-data-layer (as opposed to pagination-at-the-UI-layer, which is still mandatory — see Section 9, Part 3) is required to stay responsive per the NFR targets (Section 11, TRD).
- These bounds are enforced only as **soft warnings** at load time (`console.warn` if outside range), not hard failures — a generator run with `--vehicleCount 1500` should still work, just log a warning that it's outside the documented/tested range.

---

## 5. Service Contract Design — Complete API Specifications

There is no HTTP transport in this build (per TRD §2/§3). The `dataStore.*` and `services.*` module boundary **is** the API surface and is specified below with the same rigor as an HTTP contract: every function has a signature, a request/response schema, logical status codes, error conditions, and business rules. An AI coding agent must implement exactly this contract — no additional endpoints, no additional parameters, no silent behavior changes.

---

### 5.1 API Design Principles (apply to every endpoint below)

**Call convention:** All `services.*` functions are **async** (return `Promise`) for interface stability, even though execution is synchronous against in-memory data — this keeps calling code (UI layer) agnostic if a real backend is substituted later. All `dataStore.*` functions are **synchronous** (internal layer only; never called directly by `ui.*` — see §8.1).

**Response envelope (all `services.*` functions that return collections):**
```ts
interface ServiceResult<T> {
  data: T;
  meta: Record<string, any>; // shape defined per-endpoint below
}
```

**Logical status codes** (no HTTP transport exists; these are the equivalent semantic outcomes every endpoint must map to):

| Logical Code | Meaning | Return Behavior |
|---|---|---|
| `OK` | Success, ≥1 result | `{ data: [...], meta: {...} }` |
| `OK_EMPTY` | Success, valid query, 0 matching results (legitimate) | `{ data: [], meta: {...totalCount:0} }` — **no console log** |
| `FAIL_CLOSED_EMPTY` | `viewingAs` failed validation | `{ data: [], meta: {...scopeWarning:true} }` + `console.error(...)` |
| `BAD_REQUEST` | Malformed/missing param, wrong type, unknown filter/sort field | `throw new ServiceError(code, message, details)` |
| `FATAL` | `dataStore` not initialized, or dataset failed to load | `throw new ServiceError(code, message)` — caller must render app-level error state |

**Error type (shared across all endpoints):**
```ts
class ServiceError extends Error {
  code: string;              // e.g. "INVALID_PARAM_TYPE", "DATASTORE_NOT_INITIALIZED", "UNKNOWN_SORT_FIELD"
  details?: Record<string, any>;
  constructor(code: string, message: string, details?: Record<string, any>);
}
```

**Hard rule (per Backend API Engineer directive):** Exceptions are thrown **only** for programmer/integration errors (bad param types, missing required params, unknown enum/filter/sort values, calling before `dataStore.init()` resolves). A legitimate empty result (`OK_EMPTY`) and an invalid-scope result (`FAIL_CLOSED_EMPTY`) are **never** thrown — always returned as normal `ServiceResult` objects. `undefined`/`null` is never returned in place of `data`; `data` is always `[]`, `{}`, or a concrete typed object. Every `ui.*` caller can therefore rely on a single `try { } catch { }` for programmer errors and plain conditional checks on `meta` for empty/scope states — Grid, Chart, and Chat must not each invent their own "no data" handling.

**Shared type (referenced throughout; full entity schemas in Section 4):**
```ts
type Role = "OEM_ADMIN" | "OEM_ANALYST" | "DEALER_PRINCIPAL" | "DEALER_STAFF";

interface ViewingAs {
  role: Role;
  dealerId: string | null;
  // null is VALID only for role = OEM_ADMIN | OEM_ANALYST
  // non-null is REQUIRED for role = DEALER_PRINCIPAL | DEALER_STAFF
}
```

**Single Source of Truth Rule (mandatory, per Full Stack Developer directive):** Every `services.*` endpoint below that returns vehicle-derived data (grid, analytics, chatbot) MUST obtain its working record set by calling `dataStore.getScopedRecords(viewingAs)` (5.2.2) — directly or transitively — and MUST NOT read `dataStore`'s raw internal arrays through any other path. Grid, Chart, and Chatbot are guaranteed to agree because they share this one function. `chatbotEngine.js` calls `services.*` only (never `dataStore.*` directly), and every `services.*` function it calls receives the same `viewingAs` object the UI shell currently holds — the chatbot never queries with a wider scope than the active "Viewing As" selection, even though there is no real security boundary in this build.

**Validation-at-the-boundary rule (per Backend API Engineer directive):** Because there is no server, every `services.*` entry point is the trust boundary for this application. Every function listed in §5.3 validates its own inputs on every call — it never trusts that `viewingAs`, `filters`, `sort`, or `pagination` were pre-validated by the caller. Validation order is always: (1) type/shape checks on required params → `BAD_REQUEST` if malformed; (2) `viewingAs` semantic validation → `FAIL_CLOSED_EMPTY` if invalid; (3) domain-specific checks (unknown filter/sort field, out-of-range pagination) → `BAD_REQUEST`. This order is fixed so error precedence is deterministic and testable.

---

### 5.2 `dataStore.*` — Internal Data Layer API

`dataStore.*` is never called by `ui.*` directly (see §8.1). It is the only layer that touches the raw in-memory arrays.

#### 5.2.1 `dataStore.init(rawJson)`

**Method:** CALL (async) — must be invoked exactly once at app bootstrap, before any other `dataStore.*` or `services.*` call.

**Request Schema:** `rawJson: unknown` — the parsed contents of `data/mockData.json`.

**Preconditions:** none — this is the bootstrap call.

**Success Response (`OK`):**
```ts
{
  initialized: true,
  recordCounts: { vehicles: number, dealers: number },
  integrityIssues: IntegrityIssue[]   // may be empty array; see 5.2.5
}
```

**Fatal Error Responses (`FATAL`):**

| Code | Trigger |
|---|---|
| `DATASET_LOAD_FAILURE` | Bundled JSON file fails to fetch or fails to `JSON.parse`, or top-level shape (`schemaVersion`, `oem`, `dealers`, `vehicles`) is missing/malformed |
| `SCHEMA_VERSION_MISMATCH` | `rawJson.schemaVersion !== APP_CONFIG.SCHEMA_VERSION` — treated as fatal, not a warning, since field shapes may have silently changed |
| `INTEGRITY_CHECK_FAILURE` | 100% of vehicle records fail referential integrity (zero valid records remain after check — catastrophic, not partial) |

**Business Rules:**
- Sets `status = 'LOADING'` immediately, then `status = 'READY'` on success or `status = 'FAILED'` on any `FATAL` path.
- Populates internal state: `_state.vehicles`, `_state.dealers`, `_state.oem`, `_state.schemaVersion`, `_state.loadedAt` (ISO timestamp), `_state.integrityErrors`.
- Runs the referential integrity pass defined in 5.2.5 as part of init. **Partial** integrity failures (some invalid records) do **not** throw; invalid records are excluded from `_state.vehicles`, pushed to `_state.integrityErrors`, and each logged via `console.error`. `init()` still resolves with `OK` in this case.
- `Object.freeze()` is applied to `_state.oem` and every element of `_state.dealers` immediately after the integrity pass — reference data is immutable for the rest of the session. `_state.vehicles` elements are **not** frozen (they must remain mutable for `updateVehicleField`, §5.3.5).
- Any `dataStore.*` or `services.*` function called before `init()` resolves, or after a `FATAL` rejection, must throw `ServiceError("DATASTORE_NOT_INITIALIZED", ...)`.
- Caller (`ui.appShell`) is responsible for rendering a full-app error state on `FATAL` — no partial UI, no fallback dataset.

---

#### 5.2.2 `dataStore.getScopedRecords(viewingAs)`

**Method:** CALL (sync, pure — no I/O, no mutation)

**Request Schema:**
```ts
function getScopedRecords(viewingAs: ViewingAs): Vehicle[]
```

**Preconditions:** `dataStore.init()` has resolved (`status === 'READY'`); otherwise throws `ServiceError("DATASTORE_NOT_INITIALIZED", ...)`.

**Success Response (`OK` / `OK_EMPTY`):** `Vehicle[]` — filtered per rules below. Never `null`/`undefined`; an empty array is a valid result.

**Fail-Closed Response (`FAIL_CLOSED_EMPTY`):** `[]` (empty array) + `console.error("[dataStore.getScopedRecords] invalid viewingAs", viewingAs)`

**Business Rules (filtering logic, evaluated in order — first matching rule wins, no fallthrough to "return everything"):**
1. `viewingAs` is not an object, or `viewingAs.role` is not one of `APP_CONFIG.VALID_ROLES` → **fail closed**, return `[]`.
2. `role ∈ {OEM_ADMIN, OEM_ANALYST}` and `dealerId === null` → return **all** vehicles currently in `_state.vehicles` (full OEM-wide scope). This is the only path that returns unfiltered data.
3. `role ∈ {OEM_ADMIN, OEM_ANALYST}` and `dealerId` is a non-null string that resolves to a known dealer in `_state.dealers` → return vehicles filtered to `vehicle.dealerId === viewingAs.dealerId` (OEM user drilling into one dealer).
4. `role ∈ {DEALER_PRINCIPAL, DEALER_STAFF}` and `dealerId` is a non-null string that resolves to a known dealer → return vehicles filtered to `vehicle.dealerId === viewingAs.dealerId`. This is the mandatory path for both dealer-side roles — `dealerId === null` is **not valid** for these roles.
5. `role ∈ {DEALER_PRINCIPAL, DEALER_STAFF}` and `dealerId === null`, OR any role paired with a `dealerId` string that does **not** resolve to a known dealer in `_state.dealers` → **fail closed**, return `[]`.
6. No rule above matched (defensive default) → **fail closed**, return `[]`.

This function is the single scoping chokepoint mandated in §5.1 — every other `dataStore.*`/`services.*` function that returns vehicle data calls this function internally rather than re-implementing filtering logic.

---

#### 5.2.3 `dataStore.getReferenceData()`

**Method:** CALL (sync, pure)

**Request Schema:** none (no params)

**Preconditions:** `dataStore.init()` has resolved.

**Success Response (`OK`):**
```ts
{ oem: OEM, dealers: Dealer[] }   // frozen references; never filtered by viewingAs — dealer directory metadata (id/name/region) is not treated as sensitive in this prototype
```

**Business Rules:**
- Returns the frozen `_state.oem` and `_state.dealers` directly (no copy needed — frozen, immutable).
- Unlike `getScopedRecords`, this function is **not** scoped by `viewingAs`. Rationale: the Viewing-As selector itself (`ui.viewingAsSelector`) needs the full dealer list to populate its dropdown regardless of current role — restricting the dealer directory would make the mock role-switcher unusable. This is explicitly a mock-scope decision, not a security posture (see Section 14, Part 4).

---

#### 5.2.4 `dataStore.updateVehicle(vehicleId, patch)`

**Method:** CALL (sync, mutating — the only `dataStore.*` function permitted to mutate `_state.vehicles`)

**Request Schema:**
```ts
function updateVehicle(vehicleId: string, patch: Partial<Pick<Vehicle, "status" | "price" | "cost" | "dateSold">>): Vehicle
```

**Preconditions:**
- `dataStore.init()` has resolved.
- Called **only** by `services.updateVehicleField` (5.3.5) — never directly by `ui.*`, and never with a `patch` key outside the allowlist above (enforced by the caller, §5.3.5; this function trusts its caller since it is internal).

**Success Response:** the updated `Vehicle` object (same object reference, mutated in place, so any code holding a stale reference from a prior `getScopedRecords()` call sees the update — this is intentional for this prototype's simplicity, not a production pattern).

**Error Responses:**

| Code | Trigger |
|---|---|
| `VEHICLE_NOT_FOUND` (`BAD_REQUEST`) | `vehicleId` does not exist in `_state.vehicles` |

**Business Rules:**
- If `patch` includes `dateSold` or `status: "sold"`, recompute the derived field `daysInInventory` immediately (see Section 4 for the derivation formula) — this is the only place `daysInInventory` is recalculated after initial load.
- Denormalized fields (`dealerName`, `region`, `vin`, `oemId`, `dealerId`, `make`, `model`, `year`, `trim`, `dateReceived`, `vehicleId`) are **never** part of `patch` — they are written once by the generation script and never re-derived or edited at runtime (per Database Engineer directive). `services.updateVehicleField` enforces this allowlist before calling this function; this function does not re-validate it.
- Does not emit `grid:rowUpdated` itself — event emission is the UI layer's responsibility (§6.0), triggered after `services.updateVehicleField` resolves successfully.

---

#### 5.2.5 Referential Integrity Types & Checks

```ts
interface IntegrityIssue {
  recordType: 'vehicle' | 'dealer';
  recordId: string;
  reason: string;          // e.g. "dealerId 'DLR-099' not found in dealers[]"
  excludedFromDataset: true;
}
```

**Checks run once, during `dataStore.init()`, before any data is exposed to `services.*`:**
1. Every `vehicle.dealerId` must resolve to an entry in `dealers[]` → else exclude the vehicle, log an `IntegrityIssue`.
2. Every `dealer.oemId` must resolve to the single `oem.oemId` → else exclude the dealer (and transitively, all its vehicles get excluded by rule 1 on re-check), log an `IntegrityIssue`.
3. Every `vehicle.vehicleId` and `dealer.dealerId` must be unique within their collection → first occurrence wins, duplicates excluded and logged.

These checks are re-validated only at `init()` time — never re-run on every `getScopedRecords()` call — since the dataset is static for the session except for in-place edits via `updateVehicle`, which cannot introduce new referential integrity violations (it never changes `dealerId`, `oemId`, or IDs).

---

### 5.3 `services.*` — Public API (the only layer `ui.*` may call)

Every function below is `async` per §5.1 and internally calls `dataStore.getScopedRecords(viewingAs)` (directly or transitively) rather than any raw array.

#### 5.3.1 `services.getVehicles(viewingAs, filters?, sort?, pagination?)`

**Signature:**
```ts
async function getVehicles(
  viewingAs: ViewingAs,
  filters?: VehicleFilters,
  sort?: SortSpec,
  pagination?: PaginationSpec
): Promise<ServiceResult<Vehicle[]>>
```
```ts
interface VehicleFilters {
  status?: "in-stock" | "sold" | "in-transit" | "reserved";
  make?: string;
  model?: string;
  dealerId?: string;          // only meaningful for OEM roles further narrowing an already-scoped view; ignored (not an error) if it equals the dealer already implied by viewingAs
  yearMin?: number;
  yearMax?: number;
  priceMin?: number;
  priceMax?: number;
  vinSearch?: string;         // case-insensitive substring match against vin
}
interface SortSpec {
  field: "vin" | "make" | "model" | "year" | "price" | "cost" | "dateReceived" | "dateSold" | "daysInInventory" | "status" | "dealerName";
  direction: "asc" | "desc";
}
interface PaginationSpec {
  page: number;      // 1-indexed; defaults to 1
  pageSize: number;  // defaults to APP_CONFIG.DEFAULT_PAGE_SIZE (50); hard-capped at APP_CONFIG.MAX_PAGE_SIZE (200)
}
```

**Preconditions:** `dataStore.init()` has resolved.

**Success Response (`OK` / `OK_EMPTY`):**
```ts
{
  data: Vehicle[],                    // the current page, already sorted/filtered
  meta: {
    totalCount: number,               // total matching records across ALL pages, post-filter, pre-pagination
    page: number,
    pageSize: number,
    totalPages: number
  }
}
```

**Error Responses (`BAD_REQUEST`):**

| Code | Trigger |
|---|---|
| `UNKNOWN_SORT_FIELD` | `sort.field` not in the allowlist above |
| `INVALID_PAGE_SIZE` | `pagination.pageSize` ≤ 0 or > `APP_CONFIG.MAX_PAGE_SIZE` |
| `INVALID_PAGE_NUMBER` | `pagination.page` < 1, or `pagination.page` is not an integer |
| `INVALID_FILTER_TYPE` | Any filter value is the wrong type (e.g. `yearMin` is a string) |

**Fail-Closed Response (`FAIL_CLOSED_EMPTY`):** returned if `viewingAs` fails `dataStore.getScopedRecords` validation — `meta.scopeWarning = true`, `meta.totalCount = 0`.

**Business Rules:**
1. Validate `viewingAs`, `filters`, `sort`, `pagination` in that fixed order (per §5.1 boundary rule) before touching data.
2. Apply defaults: `pagination.page ?? 1`, `pagination.pageSize ?? APP_CONFIG.DEFAULT_PAGE_SIZE`.
3. Call `dataStore.getScopedRecords(viewingAs)` to get the base working set — **never** any wider set.
4. Apply `filters` (AND semantics across all provided fields) to the scoped set.
5. Apply `sort` (defaults to `{ field: "dateReceived", direction: "desc" }` if omitted).
6. Compute `totalCount` from the filtered-but-not-yet-paginated set, then slice for the requested page.
7. Pagination metadata is **always** returned, even when the dataset is small enough to fit on one page — the contract does not change shape based on dataset size (per Backend API Engineer directive), so the Grid's rendering logic stays stable if the mock dataset grows.

---

#### 5.3.2 `services.getVehicleById(viewingAs, vehicleId)`

**Signature:**
```ts
async function getVehicleById(viewingAs: ViewingAs, vehicleId: string): Promise<ServiceResult<Vehicle | null>>
```

**Preconditions:** `dataStore.init()` has resolved.

**Success Response (`OK`):** `{ data: Vehicle, meta: {} }`

**Success-but-not-found Response (`OK_EMPTY`):** `{ data: null, meta: { found: false } }` — **not an error.** A vehicle that exists in the full dataset but outside the caller's scope, or a `vehicleId` that doesn't exist at all, are both treated identically as "not found within your scope" — the response must not leak whether the record exists outside the caller's scope (the one cross-tenant-leakage-shaped behavior worth mocking correctly even without real security).

**Error Responses (`BAD_REQUEST`):**

| Code | Trigger |
|---|---|
| `MISSING_VEHICLE_ID` | `vehicleId` is empty/not a string |

**Business Rules:**
- Implemented as `dataStore.getScopedRecords(viewingAs).find(v => v.vehicleId === vehicleId) ?? null` — by construction, this can never return a vehicle outside the caller's current scope.

---

#### 5.3.3 `services.getDealers(viewingAs)`

**Signature:**
```ts
async function getDealers(viewingAs: ViewingAs): Promise<ServiceResult<Dealer[]>>
```

**Preconditions:** `dataStore.init()` has resolved.

**Success Response (`OK`):**
```ts
{ data: Dealer[], meta: { totalCount: number } }
```

**Business Rules:**
- Used by `ui.viewingAsSelector` to populate the dealer dropdown, and by Grid/Chart to resolve `dealerId → dealerName/region` display labels.
- Delegates to `dataStore.getReferenceData()` (5.2.3) and returns the full dealer list **regardless of `viewingAs`** — dealer directory metadata is explicitly not scope-restricted in this prototype (see 5.2.3 rationale). `viewingAs` is still a required, validated parameter (fails `BAD_REQUEST` if malformed) purely for contract consistency across `services.*`, even though it doesn't filter the result here.

---

#### 5.3.4 `services.getAnalyticsSummary(viewingAs, groupBy)`

**Signature:**
```ts
async function getAnalyticsSummary(
  viewingAs: ViewingAs,
  groupBy: "byDealer" | "byStatus" | "byMake" | "byMonth"
): Promise<ServiceResult<AnalyticsGroup[]>>
```
```ts
interface AnalyticsGroup {
  key: string;              // e.g. dealer name, status value, make, "2024-03"
  vehicleCount: number;
  averagePrice: number;     // rounded to 2 decimals
  averageDaysInInventory: number;  // rounded to 1 decimal
}
```

**Preconditions:** `dataStore.init()` has resolved.

**Success Response (`OK` / `OK_EMPTY`):** `{ data: AnalyticsGroup[], meta: { groupBy: string, totalVehiclesConsidered: number } }`

**Error Responses (`BAD_REQUEST`):**

| Code | Trigger |
|---|---|
| `UNKNOWN_GROUP_BY` | `groupBy` not one of the four enumerated values |

**Business Rules:**
1. Calls `dataStore.getScopedRecords(viewingAs)` — the same chokepoint Grid uses — then aggregates. This guarantees a chart total and a grid row count for the same `viewingAs` are always mathematically consistent (the Full Stack Developer's stated failure mode this contract is designed to prevent).
2. `byDealer` grouping is only meaningful for OEM roles with `dealerId === null`; if called by a dealer-scoped `viewingAs`, it legitimately returns a single-entry array (their one dealer) — this is `OK`, not an error.
3. `byMonth` groups by `dateReceived`'s `YYYY-MM`.

---

#### 5.3.5 `services.updateVehicleField(viewingAs, vehicleId, field, newValue)`

**Signature:**
```ts
async function updateVehicleField(
  viewingAs: ViewingAs,
  vehicleId: string,
  field: "status" | "price" | "cost" | "dateSold",
  newValue: string | number | null
): Promise<ServiceResult<Vehicle>>
```

**Preconditions:** `dataStore.init()` has resolved.

**Success Response (`OK`):** `{ data: Vehicle /* full updated record */, meta: { updatedField: string, previousValue: any } }`

**Error Responses (`BAD_REQUEST`):**

| Code | Trigger |
|---|---|
| `FIELD_NOT_EDITABLE` | `field` not in the editable allowlist `["status", "price", "cost", "dateSold"]` — all other fields (including denormalized `dealerName`/`region` and generated IDs) are immutable at runtime per Database Engineer directive |
| `INVALID_FIELD_VALUE` | `status` not in the enum; `price`/`cost` not a positive number; `dateSold` not `null` or a valid ISO date |
| `INVALID_STATE_TRANSITION` | `dateSold` set while `status !== "sold"`, or `status` set to `"sold"` with no `dateSold` provided in the same call |

**Fail-Closed Response (`FAIL_CLOSED_EMPTY`):** N/A for this endpoint — a write attempt with an invalid/out-of-scope `viewingAs` is instead treated as `VEHICLE_NOT_FOUND` (`BAD_REQUEST`), per the rule below, to avoid a distinct code path that could be probed to distinguish "invalid scope" from "record doesn't exist."

**Business Rules:**
1. Resolve the target record via `dataStore.getScopedRecords(viewingAs).find(v => v.vehicleId === vehicleId)`. If not found (either wrong scope or truly nonexistent), throw `ServiceError("VEHICLE_NOT_FOUND", ...)` — identical error for both cases, consistent with 5.3.2's no-leak rule.
2. Field-level permission (which roles may edit which fields) is enforced by the shared validator defined in the Viewing-As Scoping Model (Section 6, Part 2) — this function calls that validator before calling `dataStore.updateVehicle`, but does not duplicate its rule table here.
3. On success, calls `dataStore.updateVehicle(vehicleId, { [field]: newValue })` (5.2.4) and returns the mutated record. `ui.dataGridView` is responsible for emitting `grid:rowUpdated` after this promise resolves (§6.0) — this service function does not emit UI events itself.

---

### 5.4 Cross-Cutting Validation Rules (Module Boundary Enforcement)

These rules apply uniformly to every function in §5.3 and are not restated per-endpoint:

1. **Fixed validation order:** (1) param shape/type → `BAD_REQUEST`; (2) `viewingAs` semantic validity → `FAIL_CLOSED_EMPTY` (or `VEHICLE_NOT_FOUND` for the write endpoint, per 5.3.5 rule 1); (3) domain-specific rules (unknown enum values, out-of-range pagination, invalid state transitions) → `BAD_REQUEST`.
2. **No silent widening of scope, ever.** No `services.*` function may fall back to unscoped data if `viewingAs` is missing, malformed, or fails validation — the only correct behavior is `FAIL_CLOSED_EMPTY` (reads) or a thrown `BAD_REQUEST`/`VEHICLE_NOT_FOUND` (writes).
3. **No function returns `null`/`undefined` in place of `data`.** Absence is always `[]` (collections), `null` inside a typed envelope (single-record lookups, per 5.3.2), or a thrown `ServiceError` (programmer error) — never a bare `null`/`undefined` return value.
4. **All logging is `console.error` only, and only for `FAIL_CLOSED_EMPTY` and integrity issues** (5.2.1, 5.2.5) — `OK_EMPTY` results are legitimate and must never log anything, per §5.1's logical status code table, to keep the console signal-to-noise ratio usable during manual smoke testing (Section 15, Part 4).

> **Guardrail Warning**: Design missing critical sections: ['scalab', 'monitor', 'deploy']

---

## 6. Frontend Component Specifications

All components are vanilla-JS modules under the `ui.*` namespace (per TRD §3/§4). "Props" below means the parameters passed into a component's `init()`/`render()` function, not React props. "State" means module-scoped (closure) variables — there is no global mutable state outside `dataStore`. Components communicate exclusively through a shared, minimal pub/sub event bus (defined in 6.0) — direct cross-component function calls between UI modules are disallowed to prevent hidden coupling. **No `ui.*` module may call `dataStore.*` directly — every data access goes through `services.*` (see §8.1).**

### 6.0 `ui.eventBus` (Shared Infrastructure — used by all components below)

```ts
// Thin wrapper over EventTarget. Single instance, created once at app bootstrap.
interface UiEventBus {
  on(eventName: string, handler: (detail: any) => void): () => void; // returns unsubscribe fn
  emit(eventName: string, detail: any): void;
}
```

**Canonical event catalog** (no component may emit or listen to an event not listed here — undocumented events are a spec violation):

| Event Name | Emitted By | Consumed By | Detail Payload |
|---|---|---|---|
| `app:dataLoaded` | `ui.appShell` (on bootstrap success) | Grid, Analytics, Chat, ViewingAsSelector | `{ recordCount: number, datasetGeneratedAt: string }` |
| `app:dataLoadFailed` | `ui.appShell` | `ui.errorBanner` | `{ code: 'FATAL', message: string }` |
| `viewingAs:changed` | `ui.viewingAsSelector` | Grid, Analytics, Chat | `{ role: string, dealerId: string \| null }` |
| `grid:rowUpdated` | `ui.dataGridView` | `ui.analyticsView`, `ui.chatView` (cache-invalidation only) | `{ vehicleId: string, field: string, oldValue: any, newValue: any }` |
| `chat:messageSent` | `ui.chatView` | (internal to chatView only — listed for completeness, no external consumers) | `{ text: string }` |
| `service:error` | any component wrapping a `services.*` call | `ui.errorBanner` | `{ code: string, message: string, context: string }` |

#### 6.0.1 Shared Result-Handling Convention (mandatory — used identically by Grid, Analytics, Chat)

Per the Backend API Engineer's contract rules (§5.1), every `services.*` call resolves to exactly one of five logical outcomes. **Every `ui.*` component that calls `services.*` must branch on these five outcomes in this exact order, with no component-specific variations.** This is the single canonical pattern referenced by §6.3, §6.4, and §6.5 below rather than being re-derived per component:

```ts
async function withServiceResult(promise, { onOk, onEmpty, onScopeWarning, context }) {
  try {
    const result = await promise;                 // { data, meta }
    if (result.meta?.scopeWarning) { onScopeWarning(result); return; }  // FAIL_CLOSED_EMPTY
    if (Array.isArray(result.data) ? result.data.length === 0 : result.data == null) {
      onEmpty(result);                             // OK_EMPTY — no console log, this is legitimate
      return;
    }
    onOk(result);                                  // OK
  } catch (err) {
    // BAD_REQUEST or FATAL — both are thrown ServiceError instances
    window.eventBus.emit('service:error', { code: err.code ?? 'UNKNOWN', message: err.message, context });
    if (err.code === 'FATAL') throw err;            // caller (appShell) must render app-level error state
    // BAD_REQUEST: caller renders its own local inline error state (component-specific, see below)
  }
}
```

Rules for all three tab components:
- `onEmpty` must render a **visually distinct** "no results" state, never a blank/empty grid area, empty chart canvas, or silent chat response.
- `onScopeWarning` must render a **visually distinct** "invalid viewing scope" state (different copy from `onEmpty`) and must never fall back to showing unscoped/all data.
- A thrown `BAD_REQUEST` is a programmer/UI error (e.g., malformed filter object) and must never be presented to the end user as "no data" — it renders a small inline diagnostic message ("Something went wrong loading this view — check console") distinct from both of the above.
- `FATAL` always propagates to `ui.appShell`, which is the only component permitted to render a full-screen blocking error (via `ui.errorBanner` in `fullscreen` mode).

---

### 6.1 `ui.appShell` (Root Component)

**Purpose:** Bootstraps the app, owns the tab container, orchestrates initial data load, renders the persistent "Viewing As" selector and global error banner.

**Props:** none (top-level; instantiated once from `index.html` inline script on `DOMContentLoaded`).

**Internal State:**
```ts
{
  activeTab: 'grid' | 'analytics' | 'chat';   // default: 'grid'
  bootstrapStatus: 'loading' | 'ready' | 'error';
}
```

**Behavior:**
1. On load: render skeleton shell (tab bar + empty content area + `ui.viewingAsSelector` in header) immediately, `bootstrapStatus = 'loading'`.
2. Call `dataStore.init()` (synchronous per §5 call convention: `dataStore.*` is sync). Wrap in try/catch.
   - Success → `bootstrapStatus = 'ready'`, emit `app:dataLoaded`, mount `ui.dataGridView` into content area for `activeTab`.
   - Failure (thrown `ServiceError` with code `FATAL`) → `bootstrapStatus = 'error'`, emit `app:dataLoadFailed`, render `ui.errorBanner` full-screen, **do not mount any tab**.
3. Tab click → set `activeTab`, unmount current tab component, mount the selected one (`ui.dataGridView` / `ui.analyticsView` / `ui.chatView`). Mounting/unmounting is cheap re-render, not component destruction of the underlying data — each tab component re-reads current `viewingAs` from `ui.viewingAsSelector.getCurrentViewingAs()` on mount.
4. Only one tab is ever mounted/rendered in the DOM at a time (`display:none` is **not** used — full unmount/remount to avoid stale DOM referencing stale data after a `viewingAs` change while a tab was hidden).
5. If `dataStore.getIntegrityErrors().length > 0` after a successful init, `appShell` renders a one-time, dismissible, app-level (not per-tab) notice: *"N records were excluded at load due to data integrity issues — see browser console for details."* This is sourced once at bootstrap, not re-checked per tab mount (integrity errors never change after `dataStore.init()` completes, per §8.2).

**Events:**
- Emits: `app:dataLoaded`, `app:dataLoadFailed`
- Listens: none

---

### 6.2 `ui.viewingAsSelector`

**Purpose:** Single, always-visible control (per TRD's mock RBAC design) that lets the user simulate any role/tenant combination. This is the **only** place `viewingAs` state is mutated.

**Props:**
```ts
{
  availableRoles: Array<{ role: string, dealerId: string | null, label: string }>;
  // Populated at init from dataStore reference data (dealers list), not hardcoded.
}
```

**Internal State:**
```ts
{
  current: { role: string, dealerId: string | null };
  // default on app load: { role: 'OEM_ADMIN', dealerId: null } — [DECISION NEEDED: confirm default role
  // with stakeholders; OEM_ADMIN chosen as default because it is the least-restrictive view and makes
  // the prototype demoable immediately without requiring a selection first]
}
```

**Behavior:**
- Renders two linked `<select>` elements: Role dropdown, and a Dealer dropdown (disabled/cleared when an OEM-scoped role is selected; enabled and required when a Dealer-scoped role is selected).
- Role list is the fixed enumerated set from `APP_CONFIG.VALID_ROLES`: `OEM_ADMIN`, `OEM_ANALYST`, `DEALER_PRINCIPAL`, `DEALER_STAFF`. `OEM_ADMIN` / `OEM_ANALYST` → `dealerId: null`. `DEALER_PRINCIPAL` / `DEALER_STAFF` → `dealerId` required, populated from the dealers reference list loaded by `dataStore`.
- On any change to either dropdown that results in a **valid** combination (`{role, dealerId}` satisfies the validation rule in §7.1), update `current` and emit `viewingAs:changed`.
- If a Dealer role is selected but no dealer has been chosen yet, do **not** emit — show inline hint text "Select a dealer" and leave the last-valid `viewingAs` in effect.
- A small always-visible label reads: **"Mock view — not a security boundary. Simulates access scope for demo purposes only."** (verbatim text required — this is the in-app disclosure mandated by TRD §2).

**Events:**
- Emits: `viewingAs:changed`
- Listens: none

**Public method (called by `appShell` and tab components on mount, not an event):**
```ts
ui.viewingAsSelector.getCurrentViewingAs(): { role: string, dealerId: string | null }
```

---

### 6.3 `ui.dataGridView` (Grid Tab)

**Purpose:** Interactive tabular view of scoped vehicle records with sort, filter, pagination, and inline cell editing.

**Props:** none (reads current `viewingAs` via `ui.viewingAsSelector.getCurrentViewingAs()` on mount).

**Internal State:**
```ts
{
  filters: {
    search: string;                    // debounced 300ms, matches against denormalized dealerName/region + vin/model fields
    statusFilter: string | null;       // one of the vehicle status enum values, or null (no filter)
  };
  sort: { field: string | null; direction: 'asc' | 'desc' };
  pagination: {
    page: number;                      // 1-indexed, default 1
    pageSize: number;                  // default APP_CONFIG.DEFAULT_PAGE_SIZE (50), max APP_CONFIG.MAX_PAGE_SIZE (200)
  };
  lastResult: ServiceResult<Vehicle[]> | null;
  loadState: 'idle' | 'loading' | 'ok' | 'empty' | 'scopeWarning' | 'error';
  editableFields: string[];            // computed once per mount/viewingAs change — see permission table below
  pendingEdits: Map<string, Set<string>>; // vehicleId -> in-flight field names, used to disable a cell mid-save
}
```

**Data fetch/render behavior:**
1. On mount and on every `viewingAs:changed`: reset `pagination.page = 1`, recompute `editableFields` from the new role (table below), then call `services.getVehicles(viewingAs, filters, pagination)` through the shared handler in §6.0.1:
   - `onOk` → `loadState = 'ok'`, render table rows from `result.data`, render pagination controls from `result.meta.totalCount / meta.page / meta.pageSize` (per §5, `getVehicles` always returns pagination metadata, even for small result sets).
   - `onEmpty` → `loadState = 'empty'`, render "No vehicles match your current filters." with a "Clear filters" action — visually distinct from the scope-warning state below.
   - `onScopeWarning` → `loadState = 'scopeWarning'`, render "Your current viewing scope is invalid — no data can be shown until a valid role/dealer is selected." and disable filter/sort controls until `viewingAs:changed` fires again with a valid scope.
   - Thrown `BAD_REQUEST`/`FATAL` → per §6.0.1 (`FATAL` propagates to `appShell`; `BAD_REQUEST` renders local inline diagnostic banner within the grid panel only).
2. Sorting: clicking a column header toggles `sort.direction` (or sets `sort.field` if a different column) and re-fetches. Only columns present in the `Vehicle` schema (§4) are valid sort fields — attempting to sort a denormalized-only or non-existent field is a `BAD_REQUEST` per §5, so the UI restricts sortable columns to a fixed, documented allow-list (defined in §9, Grid Behavior Spec) rather than allowing arbitrary field clicks.
3. Filtering: `filters.search` is debounced (300ms) before triggering a re-fetch; `filters.statusFilter` re-fetches immediately on change.
4. Pagination controls: prev/next + page-size selector with options `[25, 50, 100, 200]` (never exceeding `APP_CONFIG.MAX_PAGE_SIZE`). Changing `pageSize` resets `page` to 1.
5. **Denormalized columns** (`dealerName`, `region`) are rendered directly from fields already present on each `Vehicle` record — the grid must **never** look these up from `dealers[]` at render time. Per the Database Engineer's rule (§4/§8), these fields are written once by the mock data generation script and are considered stale-but-authoritative for the session; the grid does not re-derive them even if a `dealer` record were hypothetically edited elsewhere (it currently cannot be — `dealers[]` is frozen, §8.2).

**Inline editing — permission & validation rules (mock enforcement, explicitly disclosed as non-authoritative):**

| Field | Editable? | Editable By (role) | Validation Rule |
|---|---|---|---|
| `status` | Yes | `DEALER_PRINCIPAL`, `DEALER_STAFF` — own dealer's rows only | Must be one of the enum values defined in §4 (`In Stock`, `In Transit`, `Sold`, `On Hold`) |
| `notes` | Yes | `DEALER_PRINCIPAL`, `DEALER_STAFF` — own dealer's rows only | Max 500 chars; HTML-escaped on render (basic XSS hygiene, not a security control) |
| All other fields | No | — | Read-only in the grid regardless of role, including for editable-role users |

- `OEM_ADMIN` and `OEM_ANALYST` render the entire grid **read-only** — no editable cell affordance (no cursor change, no click-to-edit) is rendered for these roles, consistent with the PRD personas (OEM views/analyzes; does not edit dealer-entered data).
- For `DEALER_PRINCIPAL`/`DEALER_STAFF`, a cell is only rendered editable if `field ∈ editableFields` **and** `row.dealerId === viewingAs.dealerId`. Since `services.getVehicles` already scopes returned rows to the caller's `dealerId` (§7/§8), every row visible to a dealer-scoped user already satisfies this — the check is defense-in-depth against a future bug in the scoping layer, not a real security boundary.
- On edit commit (blur or Enter key): call `services.updateVehicleField(viewingAs, vehicleId, field, newValue)` (full request/response contract specified in §5.x; this section defines only the triggering UI behavior). While the call is in-flight, mark `{vehicleId, field}` in `pendingEdits` and disable that cell (spinner or dimmed state) to prevent double-submit.
  - On success: re-render the cell from the **returned** `result.data` (the service's returned record is the source of truth — do not optimistically trust the typed value), emit `grid:rowUpdated` with `{ vehicleId, field, oldValue, newValue }`.
  - On failure (thrown `ServiceError`, e.g. field not in whitelist, row out of scope, or failed validation): revert the cell to `oldValue`, render a red outline + tooltip with `err.message`, and emit `service:error` with `context: 'grid:edit'`. This does **not** propagate to a full-screen error — it is always an inline, per-cell failure.
- A persistent disclosure line above the grid reads: **"Edits are stored in memory for this browser session only and are lost on refresh. Editing permissions shown here are a UI mock, not enforced server-side."**

**Events:**
- Emits: `grid:rowUpdated`, `service:error`
- Listens: `viewingAs:changed`

---

### 6.4 `ui.analyticsView` (Analytics Tab)

**Purpose:** Chart.js-based visual analysis of the same scoped dataset shown in the grid (bar/line/pie views per §10).

**Props:** none (reads current `viewingAs` via `ui.viewingAsSelector.getCurrentViewingAs()` on mount).

**Internal State:**
```ts
{
  loadState: 'idle' | 'loading' | 'ok' | 'empty' | 'scopeWarning' | 'error';
  lastSummary: ServiceResult<AnalyticsSummary> | null;   // AnalyticsSummary shape defined in §10
  chartInstances: Map<string, Chart>;                     // keyed by canvas element id, one entry per chart
}
```

**Behavior:**
1. On mount and on every `viewingAs:changed`: call `services.getAnalyticsSummary(viewingAs)` through the **same** shared handler pattern defined in §6.0.1 — `onOk` renders/re-renders the fixed set of charts defined in §10 (e.g., inventory-by-status bar chart, days-in-inventory trend line, inventory-mix pie chart); `onEmpty` renders a single "No data available for this scope." placeholder in place of all chart canvases (not three empty charts); `onScopeWarning` renders the same distinct "invalid viewing scope" message used by the grid, for UX consistency across tabs.
2. Chart instances are **destroyed and recreated** (`chart.destroy()` then `new Chart(...)`) on every data refresh rather than mutated in place, to avoid Chart.js stale-scale/animation bugs — this is a deliberate implementation rule, not an oversight.
3. Also listens for `grid:rowUpdated` — since an inline grid edit can change a field (e.g., `status`) that feeds the analytics summary, this event triggers the same re-fetch-and-rerender path as `viewingAs:changed` (cache-invalidation only; the payload itself is not consumed, it is only a signal to refetch).
4. On tab unmount (user switches to Grid or Chat tab), all entries in `chartInstances` must be explicitly `.destroy()`'d before the DOM nodes are removed, to avoid Chart.js memory leaks across repeated tab switches within a session.

**Events:**
- Emits: `service:error`
- Listens: `viewingAs:changed`, `grid:rowUpdated`

---

### 6.5 `ui.chatView` (Chat Tab)

**Purpose:** Conversational interface over the same scoped dataset, resolved via `chatbotEngine` (rule-based intent matching, §7) against `services.*` only — never against `dataStore.*` directly.

**Props:** none.

**Internal State:**
```ts
{
  transcript: Array<{ role: 'user' | 'bot' | 'system'; text: string; ts: string; matchedIntent?: string }>;
  // Capped at APP_CONFIG.CHAT_MAX_HISTORY_MESSAGES (50) — oldest dropped (FIFO) beyond that.
  // Module-scoped: persists across tab switches within the session; cleared on full page reload (no persistence).
  inputValue: string;
  isProcessing: boolean;
}
```

**Behavior:**
1. On submit (Enter or Send click, ignored if `inputValue` is blank or `isProcessing` is true): push a `user` message to `transcript`, emit `chat:messageSent`, set `isProcessing = true`, then call `chatbotEngine.handleMessage(text, viewingAs)` where `viewingAs` is read **fresh** from `ui.viewingAsSelector.getCurrentViewingAs()` at send time — never cached from mount — so a mid-session role change is always reflected in the next answer.
2. `chatbotEngine.handleMessage()` internally calls `services.*` functions (never `dataStore.*` directly, per §8.1) and therefore inherits the same five-outcome contract. The bot's reply text is derived only from `OK`/`OK_EMPTY` results; if the underlying service call returns `scopeWarning: true`, the bot must reply with a fixed, non-data-leaking message: *"I can't answer that with your current viewing scope."* — it must never fall back to answering with unscoped data.
3. If no intent in the fixed catalog (§7) matches the input, `chatbotEngine` returns a "no match" result (not an exception) and `chatView` pushes a fallback `bot` message: *"I couldn't match that to a supported question. Try asking about inventory counts, days in inventory, or dealer comparisons."* This is expected UX for an out-of-scope question — it must **not** emit `service:error` (that event is reserved for actual service-layer failures, not for "no intent matched").
4. If `chatbotEngine` (or a `services.*` call it makes) throws a genuine `ServiceError` (`BAD_REQUEST`/`FATAL`), `chatView` pushes a distinct `bot` message: *"Something went wrong answering that — please try again."* and emits `service:error` with `context: 'chat:handleMessage'`. This is visually/textually distinct from the "no match" fallback in step 3, so a user (and QA) can tell the difference between "the bot doesn't support this question" and "the system errored."
5. On `viewingAs:changed` while the Chat tab exists (mounted or not — the transcript is module state, not DOM state): append a `system` message to the transcript, e.g. *"Viewing scope changed to Dealer Principal — Westside Motors. New questions will reflect this scope."* Existing transcript history is preserved (not cleared) for conversational continuity, but is **not** re-answered against the new scope.
6. When `transcript.length` exceeds `APP_CONFIG.CHAT_MAX_HISTORY_MESSAGES`, drop the oldest message(s) (FIFO) before rendering.

**Events:**
- Emits: `chat:messageSent`, `service:error`
- Listens: `viewingAs:changed`

---

### 6.6 `ui.errorBanner`

**Purpose:** The single rendering surface for both app-level fatal failures and transient per-action service errors. No other component renders its own full-screen error state.

**Props:**
```ts
{ mode: 'fullscreen' | 'inline' }
```

**Behavior:**
- Subscribes to `app:dataLoadFailed` → always renders in `fullscreen` mode: a blocking overlay with the error message and a "Reload" button; the rest of the app is not interactive behind it.
- Subscribes to `service:error` → renders in `inline` mode as a dismissible toast anchored to the top of the current tab's content area, auto-dismissing after 6 seconds; every `service:error` event is also always `console.error`-logged regardless of whether the toast is dismissed early, per §13.
- `fullscreen` and `inline` are mutually exclusive rendering paths within the same component module — an `inline` toast never appears while a `fullscreen` overlay is active (the overlay takes rendering priority and suppresses toasts until dismissed via reload).

**Events:**
- Emits: none
- Listens: `app:dataLoadFailed`, `service:error`

> **Guardrail Warning**: Design missing critical sections: ['scalab', 'monitor', 'deploy']

---

## 8. Service Boundaries, Internal APIs & Cross-Cutting Concerns

### 8.1 Layering Contract (restated for enforcement)

```
ui.*        → calls → services.*   (async, Promise-based, only layer UI may call)
services.*  → calls → dataStore.*  (sync, internal only — ui.* MUST NOT call dataStore.* directly)
dataStore.* → owns  → in-memory dataset (vehicles[], dealers[], oem, schemaVersion, loadedAt)
```

**Enforcement rule:** Any `ui.*` module found calling `dataStore.*` directly is a spec violation. Code review checklist item (see §14.3). There is no HTTP transport and no backend process anywhere in this build — "service boundary" here means a **JS module boundary**, not a network boundary. No `fetch()` call exists anywhere except the single, one-time `fetch('./data/mockData.json')` at bootstrap (see §16).

### 8.2 `dataStore.*` — Internal Module Contract (synchronous, not directly callable by `ui.*`)

```ts
// dataStore.js — internal state, exposed only to services.js

interface DataStoreState {
  schemaVersion: string;             // must match generation script output, e.g. "1.0.0"
  oem: OEM;
  dealers: Dealer[];
  vehicles: Vehicle[];
  loadedAt: string;                   // ISO timestamp, set at successful load
  integrityErrors: IntegrityError[];  // populated during load, never cleared
  status: 'UNINITIALIZED' | 'LOADING' | 'READY' | 'FAILED';
}

interface IntegrityError {
  recordType: 'vehicle' | 'dealer';
  recordId: string;
  reason: string;         // e.g. "dealerId 'DLR-099' not found in dealers[]"
  excludedFromDataset: true;
}
```

#### 8.2.0 Primary Key Strategy (per Database Engineer mandate)

- `oemId`, `dealerId`, `vehicleId` are **generated once, at build time, by `scripts/generate-mock-data.js`** (see §12) — they are baked into `data/mockData.json` as plain strings (e.g. `VEH-00001`, `DLR-003`, `OEM-01`).
- `dataStore.js` **never generates, reassigns, or mutates an ID at runtime.** IDs are treated as opaque, immutable identifiers for the lifetime of the browser session.
- Any code path that would need to fabricate an ID at runtime (e.g., a "new record" feature) is **out of scope** for this prototype — see TRD Section 18. This build only edits fields on existing, pre-identified records (see §8.2.2); it never creates or deletes records.
- Rationale: runtime-generated IDs would produce different values on every reload/regeneration, silently breaking any hard-coded chatbot QA fixtures (Section 7) and any manual test steps in `tests/smoke-checklist.md` that reference specific IDs.

```ts
dataStore.init(rawJson: unknown): void
```
- **Preconditions:** none (this is the entry point). May only be called once per page load; calling it a second time is a no-op that logs `console.warn('[dataStore] init() called after status=READY/FAILED — ignored')` and returns immediately, to prevent accidental double-load producing duplicate in-memory arrays.
- **Behavior:**
  1. Set `status = 'LOADING'`.
  2. Validate top-level shape (`schemaVersion`, `oem`, `dealers`, `vehicles` all present and correctly typed). If missing/malformed → `status = 'FAILED'`, `console.error`, return (caller — `ui.appShell` — checks `dataStore.getStatus()` and emits `app:dataLoadFailed`).
  3. Run referential integrity pass (see §11.3). Exclude failing records, push to `integrityErrors`, `console.error` each. This is the closest thing this prototype has to a foreign-key constraint and must run on **every** load, not just be assumed from a clean generation script — the script and the runtime loader are independent guarantees.
  4. Compute derived field `daysInInventory` for every surviving vehicle (see §8.2.1).
  5. Freeze `oem` and `dealers` arrays (`Object.freeze` each element) — reference data is immutable after load. `vehicles` array elements are **not** frozen (grid editing mutates `status`/price fields in place — see §8.2.2).
  6. Set `loadedAt = new Date().toISOString()`, `status = 'READY'`.
- **Postconditions:** `dataStore.getStatus() === 'READY'` or `'FAILED'`. No other state is valid after `init()` returns.

```ts
dataStore.getStatus(): 'UNINITIALIZED' | 'LOADING' | 'READY' | 'FAILED'
dataStore.getRawCounts(): { oemCount: 1, dealerCount: number, vehicleCount: number, excludedCount: number }
dataStore.getIntegrityErrors(): IntegrityError[]   // read-only accessor for ui.errorBanner diagnostics panel (§14.4)
```

#### 8.2.1 Derived Field Computation Rule

```ts
function computeDaysInInventory(vehicle: RawVehicle, asOfDate: Date): number | null {
  if (vehicle.status === 'sold' && vehicle.dateSold) {
    return dateDiffInDays(vehicle.dateReceived, vehicle.dateSold);
  }
  if (vehicle.status !== 'sold') {
    return dateDiffInDays(vehicle.dateReceived, asOfDate); // asOfDate = dataStore.loadedAt, fixed for the session
  }
  return null; // sold but dateSold missing — should have failed integrity check (§11.3); defensive fallback
}
```
`asOfDate` is captured **once** at load time and reused for the entire session (not recomputed live) so grid/chart/chatbot never disagree on "today" mid-session.

#### 8.2.2 Denormalized Field Refresh Rule (per Database Engineer mandate)

`Vehicle.dealerName` and `Vehicle.region` are **denormalized copies** of `Dealer.name` / `Dealer.region`, written **once, at generation time, by `scripts/generate-mock-data.js`** — purely for grid/chart query convenience (avoids a join on every render).

- **`dataStore.js` never re-derives these fields at runtime.** There is no "refresh denormalized fields" step in `init()` and no listener that re-syncs them if a dealer record were ever edited.
- **Consequence (explicit limitation, not a bug):** Dealer entities are frozen after load (§8.2, step 5) and this prototype has **no UI path to edit a Dealer's `name` or `region`** — only `Vehicle` fields are editable via the grid (§13.3 in Part 3). Because the only mutation surface (`grid:rowUpdated`) never touches `dealers[]`, denormalized `dealerName`/`region` on vehicles can never drift out of sync within a session. If a future version adds dealer-editing, this rule **must** be revisited (either re-derive on every read, or cascade-update all vehicles for that dealer on edit) — logged as a forward-looking note in TRD Section 18.

### 8.3 `dataStore.getScopedRecords(viewingAs)` — Single Source of Truth for Scoping

This is the **only** function permitted to filter vehicles by role/dealer. No other module (not `services.*`, not any `ui.*` component) may implement its own filtering logic — duplicating scoping logic anywhere else is a spec violation, since it would create two places that could disagree about what a user is allowed to see.

```ts
interface ViewingAs {
  role: 'OEM_ADMIN' | 'OEM_ANALYST' | 'DEALER_PRINCIPAL' | 'DEALER_STAFF';
  dealerId: string | null; // null REQUIRED for OEM_ADMIN/OEM_ANALYST, REQUIRED non-null for DEALER_* roles
}

dataStore.getScopedRecords(viewingAs: ViewingAs): { vehicles: Vehicle[], scopeValid: boolean }
```

**Validation rules (fail-closed):**
1. `role` must be one of the 4 enumerated values (`window.APP_CONFIG.VALID_ROLES`) — else `scopeValid: false`, `vehicles: []`.
2. If `role` is `OEM_ADMIN` or `OEM_ANALYST` → `dealerId` must be `null`. If non-null provided, `scopeValid: false`, `vehicles: []` (malformed combination — fail closed, do not silently ignore the bad `dealerId`).
3. If `role` is `DEALER_PRINCIPAL` or `DEALER_STAFF` → `dealerId` must be a non-null string that exists in `dataStore.dealers`. If missing or unknown → `scopeValid: false`, `vehicles: []`.
4. On `scopeValid: false`, caller (`services.*`) MUST log via `console.error('[SCOPE_FAIL_CLOSED]', viewingAs)` and return `FAIL_CLOSED_EMPTY` (see §8.5) — **never** fall back to unscoped/all-records. Fail-closed is a hard invariant of this layer, not a default that can be overridden by a "show all on error" convenience path.

**Filtering logic when valid:**
```ts
if (role === 'OEM_ADMIN' || role === 'OEM_ANALYST') {
  return { vehicles: dataStore.vehicles, scopeValid: true }; // full dataset, all dealers
}
// DEALER_PRINCIPAL / DEALER_STAFF
return {
  vehicles: dataStore.vehicles.filter(v => v.dealerId === viewingAs.dealerId),
  scopeValid: true
};
```

**Role-based field masking:** `DEALER_STAFF` receives the same row set as `DEALER_PRINCIPAL` (dealer-level isolation is the only isolation boundary in this prototype). Field-level permission differences between `DEALER_PRINCIPAL` and `DEALER_STAFF` (e.g., cost visibility) are **[DECISION NEEDED]** — PRD Section 5 defers final role/permission granularity. This prototype does **not** mask any fields by role beyond dealer-level row scoping. This is logged as a gap in §8.6 below and TRD Section 18.

**Critical distinction — this is not access control:** `getScopedRecords` filters an in-memory array based on a client-side dropdown selection (`viewingAs`). It is a **cosmetic convenience** that lets the UI demonstrate role-aware views. It provides **zero actual security** — see §8.6.

### 8.4 `services.*` — Public Contract (Error Handling, Validation & Query Pipeline)

```ts
services.getVehicles(
  viewingAs: ViewingAs,
  filters?: VehicleFilters,
  sort?: SortSpec,
  pagination?: { page: number; pageSize: number }
): Promise<ServiceResult<Vehicle[]>>
```
- **Preconditions:** `dataStore.getStatus() === 'READY'` (else throws `ServiceError('FATAL', 'dataStore not ready', { status: dataStore.getStatus() })`).
- **Step order (mandatory, never reordered):** (1) scope via `dataStore.getScopedRecords`, (2) filter, (3) sort, (4) paginate. Filters/sort/pagination must never be applied before scoping — this ordering is what guarantees a malformed filter can never accidentally widen scope back to unscoped data.
- **Validation:** every `filters` key and `sort.field` must be a recognized `Vehicle` field (see §4). An unrecognized field throws `ServiceError('BAD_REQUEST', "unknown filter field 'foo'", { field: 'foo' })` — it does **not** silently ignore the bad field and return partially-filtered results, since that could mask a caller bug that thinks it's filtering when it isn't.
- **Defaults:** `pagination.page` defaults to `1`; `pagination.pageSize` defaults to `APP_CONFIG.DEFAULT_PAGE_SIZE` (50), clamped to `APP_CONFIG.MAX_PAGE_SIZE` (200) — a requested `pageSize > 200` is **not** an error, it is silently clamped and the clamp is reflected in `meta.pageSize` so the UI can show the true page size used.
- **Return:** `ServiceResult<Vehicle[]>` with `meta: { totalCount, page, pageSize, scopeValid }`. If `scopeValid === false`, `data: []` and `meta.scopeWarning: true` (logical code `FAIL_CLOSED_EMPTY`, §8.5) — the promise **resolves**, it does not reject; a scope failure is a valid (if unfortunate) outcome the UI must handle gracefully, not an exceptional program state.

Other `services.*` functions (`getDealers`, `getAnalyticsSummary`, `updateVehicleField`, etc., fully specified in Part 2/3) follow the identical pattern: scope-first, validate params, return `ServiceResult` or throw `ServiceError`, never return unscoped data on any failure path.

### 8.5 Error Handling Strategy — Shared `ServiceError` Type & Logical Status Codes

**Logical status codes** (no HTTP transport exists; these are the semantic outcomes every `services.*` function must map to — restated here as the canonical definition referenced by §8.3/§8.4 above):

| Logical Code | Meaning | Return Behavior | Console Behavior |
|---|---|---|---|
| `OK` | Success, ≥1 result | `{ data: [...], meta: {...} }` | none |
| `OK_EMPTY` | Success, valid query, 0 matching results (legitimate) | `{ data: [], meta: {...totalCount:0} }` | **none** — this is a normal outcome, not an error |
| `FAIL_CLOSED_EMPTY` | `viewingAs` failed validation (§8.3) | `{ data: [], meta: {...scopeWarning:true} }` | `console.error('[SCOPE_FAIL_CLOSED]', viewingAs)` |
| `BAD_REQUEST` | Malformed/missing param, wrong type, unknown filter/sort field | `throw new ServiceError('BAD_REQUEST', message, details)` | `console.error` at throw site |
| `FATAL` | `dataStore` not initialized, or dataset failed to load | `throw new ServiceError('FATAL', message)` | `console.error`; caller (`ui.*`) must render app-level error state, not a per-widget error |

**Shared error type (used by every `services.*` function, no ad-hoc `Error` throws permitted anywhere in `services.js` or `chatbotEngine.js`):**

```ts
class ServiceError extends Error {
  code: 'BAD_REQUEST' | 'FATAL';   // FAIL_CLOSED_EMPTY and OK_EMPTY are NOT thrown — they are normal resolved returns
  details?: Record<string, any>;
  constructor(code: 'BAD_REQUEST' | 'FATAL', message: string, details?: Record<string, any>) {
    super(message);
    this.name = 'ServiceError';
    this.code = code;
    this.details = details;
  }
}
```

**Propagation rule:** Any `ui.*` component that calls a `services.*` function MUST wrap the call in `try/catch`. On catch, emit `service:error` (event catalog, §6.0) with `{ code, message, context: '<calling component name>' }` and render a local inline error state — it must **never** let an uncaught `ServiceError` bubble to a global `window.onerror` handler as the primary error-surfacing mechanism. Global `window.onerror`/`window.onunhandledrejection` handlers may exist as a last-resort safety net (logging only) but are not a substitute for local handling.

### 8.6 Authentication & Authorization Boundary — Explicit Statement (No Auth Exists)

Per TRD Section 2 and the mandatory guardrails for this build profile: **this application has no authentication and no server-enforced authorization of any kind.** This subsection exists specifically so no downstream reader mistakes the `viewingAs` mechanism (§8.3) for a security boundary.

- There is no login screen, no session, no token, no cookie, no user account of any kind.
- `ui.viewingAsSelector` (§6) is a plain `<select>`/dropdown that any user can change to any role/dealer combination at any time, with zero restriction. It is a **UI convenience for demonstrating role-scoped views**, not an access control mechanism.
- `dataStore.getScopedRecords` (§8.3) enforces fail-closed *filtering logic*, but it filters an array that is **already fully present in browser memory** — a user with browser developer tools can inspect `window` state (if it were exposed) or network payloads and see the entire dataset regardless of the selected `viewingAs`. There is no server that withholds unscoped data from the client in the first place.
- **Zero cross-tenant leakage (PRD Section 4.2, P0 metric) cannot be met by this build and is not claimed to be met.** The PRD's 100%-leakage-prevention target requires server-side enforcement (the server never sends data outside the caller's authenticated scope). This prototype sends the **entire dataset** to every browser session unconditionally at bootstrap; "scoping" only affects what is *rendered*, not what is *transmitted or accessible*.
- This gap is logged as a **launch-blocking item for any production rebuild** in TRD Section 18 and must be surfaced in-app (see §14 — a persistent, non-dismissible banner reading "Prototype — no real security boundary; role selector is a UI demo only").
- If real auth is explicitly requested in a future iteration, the pre-approved next step per stack guardrails is a minimal session-based auth flow on a real backend (Node/Express or FastAPI) with server-side scoping enforced before data ever leaves the server — not a client-side gate in front of the same fully-loaded dataset.

### 8.7 Validation Rules Summary (Consolidated Fail-Closed Patterns)

All validation in this layer follows one consistent philosophy — **fail closed, log loudly, never guess**:

| Input | Invalid Condition | Behavior |
|---|---|---|
| `viewingAs.role` | Not in `VALID_ROLES` | `scopeValid: false`, empty result, `console.error` |
| `viewingAs.dealerId` | Wrong nullability for role, or unknown dealer ID | `scopeValid: false`, empty result, `console.error` |
| `filters.*` / `sort.field` | Unrecognized field name | `throw ServiceError('BAD_REQUEST', ...)` — never ignored |
| `pagination.page` | `< 1` or non-integer | `throw ServiceError('BAD_REQUEST', ...)` |
| `pagination.pageSize` | `> MAX_PAGE_SIZE` | **Not an error** — clamped, reflected in response `meta` |
| Incoming JSON record (vehicle/dealer) | Fails referential integrity (§11.3) | Excluded at load, logged to `integrityErrors`, never surfaced as a runtime error to the UI mid-session |
| Chatbot free-text input | Does not match any known intent pattern (§7) | Resolved as a distinct `NO_MATCH` intent with a canned "I didn't understand" response — **never** silently falls back to returning unscoped or best-guess data |

### 8.8 External Integrations

**There are none.** No LLM API, no analytics/telemetry service, no third-party data source, no payment or notification integration exists anywhere in this build. The only two network fetches in the entire application are: (1) the CDN `<script>` tags for Tailwind and Chart.js, and (2) the one-time local `fetch('./data/mockData.json')` at bootstrap. Any future integration (e.g., a real LLM for the chatbot, per TRD Section 18) requires a new TRD/SPECS revision — it must not be silently introduced by an implementer as a "helpful upgrade."

### 8.9 State Machine — `dataStore` Lifecycle (Formal Definition)

```
UNINITIALIZED ──init() called──> LOADING ──validation + integrity pass OK──> READY
                                     │
                                     └──validation fails / fetch throws──> FAILED
```

- **Valid transitions:** `UNINITIALIZED → LOADING`, `LOADING → READY`, `LOADING → FAILED`.
- **Terminal states for the session:** `READY` and `FAILED` are both terminal — there is no `READY → LOADING` retry transition in this build (no "reload data" button in scope). A user who hits `FAILED` must reload the page.
- **Invalid transitions are defensive no-ops, not silent successes:** calling `init()` again while `status` is `READY` or `FAILED` logs `console.warn` and returns without re-running any load logic (§8.2).
- Every `ui.*` component that reads data must check `dataStore.getStatus()` indirectly via the `app:dataLoaded` / `app:dataLoadFailed` events (§6.0) — no component may poll `dataStore.getStatus()` directly (that would violate the layering contract, §8.1); `ui.appShell` is the sole owner of translating dataStore state transitions into UI events.

### 8.10 Testing Hooks for the Service Layer

Per the manual-testing default for this profile, there is no automated test framework requirement, but the service layer must remain **deterministically testable by hand**:

- `scripts/generate-mock-data.js --seed 42` must produce byte-identical output on every run (§3.2), so any manual smoke-test step that asserts a specific chatbot answer or grid row count remains valid across regenerations.
- `services.*` functions must have no hidden dependency on wall-clock time at call time — the only time-dependent value (`daysInInventory`) is pinned to `dataStore.loadedAt`, computed once (§8.2.1), so repeated calls within a session are idempotent and reproducible.
- `tests/smoke-checklist.md` (Section 15, Part 4) must include at least one explicit test case per row of the §8.7 validation table above (e.g., "select an invalid role via dev tools console → confirm empty grid + console error, not a crash or unscoped data").

### 8.11 Deployment / Load-Order Enforcement Notes (Service Layer Specific)

- The fixed script load order defined in §1 (`config.js → dataStore.js → services.js → chatbotEngine.js → utils/*.js → ui/*.js → main.js`) is a **hard requirement** for this layer specifically: `services.js` references `window.APP_CONFIG` (from `config.js`) and the `dataStore` global at module-evaluation time for constant lookups — loading out of order causes a `ReferenceError` at script parse/execution time, not a graceful runtime error.
- Because there is no bundler and no build step, this ordering is enforced only by the literal `<script>` tag order in `index.html` — there is no tooling safety net (e.g., a module resolver) catching an accidental reorder. Code review must check this explicitly (§14.3 checklist item).
- No server-side deployment step applies to this layer — `services.js` and `dataStore.js` ship as-is, unminified, as static files alongside everything else (§16).