# PRD.md

# Product Requirements Document
## OEM–Dealer Data & Insights Platform (Working Title)

**Document Owner:** Product Management
**Status:** Draft for Stakeholder Review
**Version:** 1.1 (Revised — addresses BA and PM self-critique of v1.0)

---

## 1. Executive Summary

This document defines the requirements for a web-based application that gives Original Equipment Manufacturers (OEMs) and their affiliated Dealers a shared platform to view, manage, and analyze operational data. The platform is built around three core capabilities explicitly requested in the product brief:

1. **Data Grids** — structured, interactive tabular views of operational data.
2. **Visualization/Analysis** — charts and analytical views built on the same underlying data.
3. **Conversational Chatbot** — a chat interface that allows users to query their data using natural language, in addition to navigating grids and dashboards manually.

The platform must serve two distinct but related audiences — OEM staff (who need cross-dealer, aggregated visibility) and Dealer staff (who need focused visibility into their own dealership's data) — under a single, secured application with role- and tenant-aware access enforced identically across grid, chart, and chatbot surfaces.

**[ASSUMPTION]** The original product idea did not specify the underlying business domain (e.g., vehicle inventory, sales, service/warranty claims, parts orders). This PRD treats the platform as a general **OEM–Dealer operational data management platform**. Feature requirements below are written to be domain-agnostic wherever possible; domain-specific examples are illustrative only. The specific data domain(s) must be confirmed before detailed schema/data-dictionary work begins (see Open Questions, Item 1). This is now treated as a **launch-blocking dependency**, not a deferred detail — see Section 5 (Conceptual Data Model) and Section 6, P0-5.

---

## 2. Problem Statement

OEMs and their dealer networks operate on a common set of data (illustratively: inventory, orders, sales, claims, performance), but today:

- **OEMs** lack a consolidated, real-time view across all dealers, forcing manual data collection, spreadsheet consolidation, and delayed decision-making.
- **Dealers** lack self-service tools to inspect and analyze their own operational data without going through OEM-provided reports or manual requests, which are often slow and inflexible.
- **Both audiences** need to interpret data quickly, but grids and dashboards alone require users to already know what question to ask and where to look — there is no fast, conversational way to ask "what changed" or "why" without a trained analyst.
- Data currently used by both parties is fragmented across mismatched formats, tools, and access levels, creating trust issues, duplicated effort, and slow time-to-insight.
- Because data currently originates from multiple disconnected sources (dealer-entered records, OEM systems, spreadsheets), **any platform that displays data must also define how data gets into the platform in the first place** — this was previously unaddressed and is now in scope (P0-5).

**Core problem to solve:** OEMs and dealers need one shared, secured platform where each party can get their relevant data into the system, view the data relevant to their role, explore it visually, and get fast answers — without waiting on manual reporting cycles or misusing data outside their permission scope.

---

## 3. User Personas

**[ASSUMPTION]** Names, titles, and narrative detail below are illustrative personas constructed from the roles identified during discovery (OEM Admin/Analyst, Dealer Principal, Dealer Staff). Exact org titles and the final role list must be validated with real customers — see Open Questions.

### Persona 1: Priya Sharma — OEM Operations Analyst ("OEM Admin/Analyst" role)
- **Role:** Works at OEM headquarters, responsible for monitoring performance and data quality across all dealers in her region.
- **Goals:** Get a consolidated, accurate, real-time view of all dealer data; spot outliers/underperforming dealers quickly; answer ad-hoc leadership questions without building a new report each time.
- **Pain Points:** Currently relies on dealers to submit spreadsheets on a lag; no single source of truth; cross-dealer comparisons take days to compile.
- **Success looks like:** She opens the platform, sees all dealers' data in one grid/dashboard, and asks the chatbot a direct question ("Which dealers had the largest change in X last month?") and gets an immediate, trustworthy, correctly-scoped answer.

### Persona 2: Marcus Webb — Dealer Principal
- **Role:** Owns/runs a single dealership; accountable for his dealership's overall performance to the OEM.
- **Goals:** Monitor his dealership's data in real time; understand trends without needing a dedicated analyst; ensure his team's data is accurate before the OEM reviews it.
- **Pain Points:** Only sees data the OEM chooses to send him, on the OEM's schedule; no ability to self-serve analysis; no fast way to ask questions about his own numbers.
- **Success looks like:** He logs in, sees only his dealership's data (never another dealer's), can slice/filter it himself, and can ask the chatbot plain-language questions about his own performance.

### Persona 3: Sam Ortiz — Dealer Staff (Sales/Service Coordinator)
- **Role:** Front-line staff member responsible for entering/maintaining day-to-day records at the dealership (illustrative: sales records, service entries).
- **Goals:** Quickly find and update specific records; avoid data-entry errors; get quick answers to routine questions without escalating to a manager.
- **Pain Points:** Limited system access today means constant back-and-forth with the Dealer Principal or OEM for basic lookups; no visibility into whether entered data is correct/complete.
- **Success looks like:** He accesses a restricted, role-appropriate view of dealership data, edits only the fields he's permitted to, and asks the chatbot simple lookup questions instead of interrupting his manager.

---

## 4. Goals & Success Metrics

### 4.1 Business Goals
1. Give OEMs a single consolidated view of dealer data, replacing manual/periodic data consolidation.
2. Give dealers self-service access to their own data without waiting on OEM-provided reports.
3. Reduce time-to-insight for both OEM and dealer users by supplementing grids/dashboards with a conversational query interface.
4. Ensure strict, verifiable data access boundaries between OEM and dealer roles, and between dealers themselves.
5. Establish a trustworthy, auditable system of record so that data entering the platform (manually or via import) is validated and traceable.

### 4.2 Success Metrics (Targets)

| Metric | Baseline (Today) | Target (Post-Launch) | Measurement Method |
|---|---|---|---|
| Time for OEM analyst to produce a cross-dealer comparison view | Manual, days **[ASSUMPTION — baseline to be confirmed with pilot customer]** | ≤ 5 minutes via grid/dashboard | Time-to-task usability testing with target users |
| Time for dealer user to answer a basic data question (e.g., "how many records changed this week") | Manual/ask someone **[ASSUMPTION]** | ≤ 2 minutes using chatbot or grid | Time-to-task usability testing |
| % of chatbot answers that are correct AND within the user's permitted data scope | N/A (new capability) | ≥ 90%, validated via QA regression test set covering cross-tenant queries | QA test suite (must include adversarial cross-tenant prompts) + user feedback flagging |
| % of chatbot answers with zero cross-tenant data leakage | N/A | 100% (zero tolerance) | Automated QA test suite run pre-release and on every model/prompt change |
| % of active users who use the chatbot at least once per week | N/A (new capability) | ≥ 60% of logged-in users within 60 days of launch | Product usage analytics |
| Data access violations (a user viewing/editing/querying data outside permitted scope) | N/A | 0 (zero tolerance) | Access control audit logs, reviewed weekly for first quarter post-launch |
| % of manually/imported records that pass validation on first submission | Unmeasured today | ≥ 95% within 60 days of launch | Ingestion/import success logs |
| User-reported data trust issues (e.g., "this number looks wrong") | Unmeasured today | Reduce reported discrepancies by 50% within 2 quarters of launch | Support ticket tagging |
| Weekly active users among invited dealer/OEM staff | N/A | ≥ 70% weekly active rate within 90 days of launch | Product usage analytics |

---

## 5. Conceptual Data Model (Pre-Requirement Foundation)

**[ASSUMPTION — must be ratified by stakeholders before engineering begins detailed schema work; flagged by BA as a hard prerequisite for building the Grid and Visualization features.]**

Regardless of final business domain, the platform requires the following domain-agnostic entities to exist so that access control, grids, charts, and chatbot scoping can all be built against a shared model:

| Entity | Description | Key Attributes (illustrative) |
|---|---|---|
| **OEM (Tenant Root)** | The manufacturer organization; owns one or more Dealers. | OEM ID, name, region(s) |
| **Dealer (Tenant)** | A dealership belonging to exactly one OEM; the primary data-isolation boundary for dealer-side users. | Dealer ID, OEM ID (owning tenant), name, region |
| **User** | A person with login access, belonging to either the OEM or exactly one Dealer. | User ID, tenant scope (OEM-wide or single Dealer), Role |
| **Role** | Defines permission scope and CRUD/field-level rights. Final role list is **[DECISION NEEDED]** (illustrative candidates: OEM Admin, OEM Analyst, Dealer Principal, Dealer Staff). | Role ID, scope type, permitted actions |
| **Record** | A generic unit of business data shown in the grid (the actual domain entity — e.g., "vehicle," "claim," "order" — is **[DECISION NEEDED]**, see Open Questions). Every Record has exactly one owning Dealer (its tenant). | Record ID, owning Dealer ID, field values, created/modified metadata |
| **Field Definition** | Describes a column on a Record: type, validation rule, required/optional, editable-by-role. | Field name, data type, validation rule, editable roles |
| **Audit Event** | An immutable log entry for any data access or change (view, edit, export, chatbot query). | Event ID, User ID, Role, action, scope accessed, timestamp |
| **Conversation/Query Log** | A record of a chatbot interaction, linked to the User and the data scope that was accessed to answer it. | Query text, resolved scope, response, timestamp |

This model does not commit to a specific business domain; it defines the minimum shared structure so that P0-2 (Grid), P0-3 (Visualization), and P0-4 (Chatbot) can be specified without engineering inventing an undocumented schema. **A full Data Dictionary (concrete Record types, field lists, and validation rules) is a required artifact before implementation of P0-2 begins — see P0-5 and Open Questions.**

---

## 6. Feature Requirements

Features are prioritized using MoSCoW-style tiers (P0 = Must Have / launch blocker, P1 = Should Have, P2 = Nice to Have). **P0 is capped at 5 features by design.**

### 6.1 P0 — Must Have (Launch Blockers)

#### P0-1: Role-Based, Tenant-Isolated Access Control
**Description:** Every user is assigned a Role (final list **[DECISION NEEDED]**; illustrative candidates: OEM Admin, OEM Analyst, Dealer Principal, Dealer Staff) that determines which Dealer(s) and which Record fields they can view or edit. OEM roles may see data across Dealers; Dealer roles see only their own Dealer's data.
**Why P0:** Without this, the platform cannot be safely used by two different organizations sharing one system — this is a data governance and trust prerequisite for every other feature.
**Acceptance Criteria:**
- A Dealer-role user can never view, export, or query (via grid, chart, or chatbot) another Dealer's records, under any circumstance.
- An OEM-role user's visible data scope (single Dealer vs. all Dealers) matches their assigned permission level exactly.
- Every grid, chart, and chatbot response independently enforces the same access rules — no feature bypasses the access control layer (there is exactly one authorization source of truth, not per-feature logic).
- Attempting to access out-of-scope data returns a clear "not authorized" response rather than an error that leaks the existence of the data.
- Every data access event (view, edit, export, chatbot query) is written to an Audit Event log with User, Role, action, and scope accessed.
- Field-level permissions (which Roles can edit which fields) are enforced server-side; client-side restrictions alone are not sufficient and must be treated as a security bug if relied upon exclusively.

#### P0-2: Interactive Data Grid
**Description:** A tabular view of Records that users can view, sort, filter, and search according to their permission scope. Authorized users can edit records inline, subject to field-level permissions defined in the Data Dictionary (P0-5).
**Why P0:** Explicitly requested as a core capability; it is the primary way users inspect and manage raw data.
**Acceptance Criteria:**
- Users can sort and filter the grid by any column visible to their Role.
- Users can search across the records visible to their Role.
- Editable fields are editable only for Roles with the appropriate permission per the Data Dictionary; read-only fields are visually distinguished and cannot be modified regardless of client-side manipulation (enforced server-side, per P0-1).
- Every edit is validated against the documented field rules (required/optional, type, format, uniqueness, referential integrity where applicable) before being saved; invalid edits are rejected with a specific, field-level error message (not a generic failure).
- Users can export the currently filtered/visible view of the grid, restricted to their permitted data scope; exports are logged as Audit Events.
- The grid supports pagination or virtualized scrolling such that a Dealer with **[DECISION NEEDED: expected max record volume per tenant]** records loads its default view in ≤ 3 seconds.
- A new Dealer with zero Records sees a clear empty state with guidance on how to add/import data (linking to P0-5), not a blank or broken grid.
- Concurrent edits to the same Record by two users are detected and surfaced (e.g., "this record was updated by another user — reload to see the latest version") rather than silently overwritten.

#### P0-3: Visualization & Analysis Dashboard
**Description:** A set of chart-based views built on the same Records and permission scope as the Grid, allowing users to see trends and comparisons without manually building a report.
**Why P0:** Explicitly requested as one of the three core capabilities in the original product brief; without it, "analysis" — named in the product idea — does not exist as a feature.
**Acceptance Criteria:**
- Charts respect the exact same tenant/role-based data scope as the Grid (an OEM Analyst sees cross-dealer aggregation; a Dealer user sees only their own Dealer's data) — enforced via the same authorization layer as P0-1, not a separate implementation.
- The dashboard supports at minimum: a time-series/trend view and a comparison view (e.g., dealer-vs-dealer for OEM roles, period-vs-period for Dealer roles). Exact chart type list is **[DECISION NEEDED]** pending domain confirmation.
- Users can filter the dashboard by the same dimensions available in the Grid (e.g., date range, and other Record fields defined in the Data Dictionary).
- Selecting a data point or segment in a chart allows the user to drill down to the underlying filtered Grid rows (cross-filtering between chart and grid).
- A Dealer or OEM scope with no data (new tenant, or filter returning zero results) shows an explicit empty state ("No data for this selection") rather than a blank or broken chart.
- Dashboard load time for a default view is ≤ 5 seconds for a tenant with **[DECISION NEEDED: expected data volume]** records.

#### P0-4: Conversational Chatbot (Read-Only Query Assistant)
**Description:** A chat interface allowing users to ask natural-language questions about the data within their permitted scope and receive answers grounded in that data. In v1, the chatbot is **read-only** — it cannot create, edit, or delete Records (write actions are explicitly Out of Scope for v1, see Section 7).
**Why P0:** Explicitly requested as one of the three core capabilities; addresses the Problem Statement's call for fast, conversational answers without manual report-building.
**Acceptance Criteria:**
- Every chatbot query is resolved using the same tenant/role-based data scope enforced in P0-1; the chatbot cannot answer with data outside the requesting user's permitted scope under any phrasing of the question, including adversarial or indirect prompts attempting to reference other dealers.
- If a user asks a question that would require out-of-scope data, the chatbot responds with a clear "I can't access that" message — it does not guess, does not partially leak scope, and does not silently fail.
- If a user asks a question the chatbot cannot answer from available data (ambiguous, unsupported, or no matching data), it responds with an explicit fallback message rather than a fabricated answer.
- Every chatbot query and its resolved data scope is logged as a Conversation/Query Log entry and is auditable (per P0-1).
- Chatbot responses render within **[DECISION NEEDED: target response latency, e.g., ≤ 5 seconds for 95th percentile]**.
- The chatbot cannot execute any Create/Update/Delete action against Records in v1; if a user asks it to perform a write action, it responds that this isn't supported and directs them to the Grid.
- A QA regression test set (referenced in Section 4.2 success metrics) covering at least: in-scope factual questions, cross-tenant leakage attempts, ambiguous questions, and write-action requests, must pass before each release.

#### P0-5: Structured Data Entry & Import
**Description:** The mechanism by which Records enter the platform for v1: (a) manual entry/edit through the Grid (covered by P0-2's edit capability), and (b) a structured bulk import (e.g., file-based upload) validated against the Data Dictionary before Records are created.
**Why P0:** Flagged as a hard gap in critique — without a defined way for data to enter the system, the Grid (P0-2) and Dashboard (P0-3) have nothing to display. This is a launch blocker, not a "nice to have."
**Acceptance Criteria:**
- A **Data Dictionary** artifact — defining every Record type in scope for v1, its fields, data types, required/optional status, uniqueness rules, and which Roles may edit each field — is authored and approved before this feature is implemented. Ownership of authoring/maintaining the Data Dictionary is **[DECISION NEEDED]**.
- Users with import permission (Role-restricted, per P0-1) can upload a structured file of Records for their permitted scope only (a Dealer user can only import records owned by their own Dealer).
- Every imported row is validated against the Data Dictionary rules before being committed; rows that fail validation are rejected individually with a specific, row-level error message, while valid rows in the same batch are still committed (partial success, not all-or-nothing failure, unless stakeholders decide otherwise — **[DECISION NEEDED]**).
- Import activity (who, when, how many records, how many succeeded/failed) is logged as an Audit Event and visible to the importing user as an import summary/report.
- System-to-system automated sync/integration with existing OEM source systems is **explicitly Out of Scope for v1** (see Section 7) — v1 supports manual entry and file-based import only.

---

### 6.2 P1 — Should Have

#### P1-1: Onboarding & Invitation Flow
**Acceptance Criteria:** New OEM and Dealer users are invited via an email-based invitation tied to a pre-assigned Role and tenant scope; first login requires credential setup and displays a guided first-run view of Grid/Dashboard/Chatbot; a Dealer with no data yet is shown a clear path to their first import or manual entry (linking to P0-5).

#### P1-2: Notifications & Anomaly Alerts
**Acceptance Criteria:** Users can opt into alerts (e.g., in-app, email) for defined conditions (e.g., a metric crossing a threshold, an outlier dealer). Alert rule configuration is scoped to what the user's Role is permitted to see (an OEM Analyst can configure cross-dealer alerts; a Dealer user only their own). Exact alert conditions/thresholds are **[DECISION NEEDED]**.

#### P1-3: Audit Log Viewer (Compliance UI)
**Acceptance Criteria:** Authorized OEM Admin roles can view a searchable UI over the Audit Event log (who accessed/edited/exported/queried what, and when), scoped to their permission level, without needing direct database access.

#### P1-4: Saved Views & Filters
**Acceptance Criteria:** Users can save a named Grid filter/sort configuration or Dashboard filter configuration for reuse, scoped privately to that user (shared/team-level saved views are P2).

#### P1-5: Localization — Currency, Units, and Regional Formatting
**Acceptance Criteria:** For OEMs operating across multiple countries/regions, numeric fields, currency, date, and unit-of-measure formatting display according to the Dealer's/OEM's configured region. Full multi-language UI translation is explicitly P2 (see below); this P1 item covers formatting/units only. Applicability is **[DECISION NEEDED]** pending confirmation of whether the initial customer base is multi-region.

#### P1-6: Scheduled/Recurring Export
**Acceptance Criteria:** Users with export permission can configure a recurring export (e.g., weekly) of a saved Grid view, delivered within their permitted data scope, logged as an Audit Event each time it runs.

---

### 6.3 P2 — Nice to Have

- **P2-1: Write-Capable Chatbot Actions** — allowing the chatbot to create/edit Records via conversation, with the same validation and permission enforcement as the Grid. Deferred due to the higher risk of unintended/incorrect writes via natural language; revisit after v1 read-only chatbot is proven reliable.
- **P2-2: System-to-System Integration/Sync** — automated data sync from OEM source-of-record systems, replacing manual import. Deferred pending confirmation of which source systems exist (see Open Questions).
- **P2-3: Full Multi-Language UI Translation** — translating the application UI itself (not just data formatting) into additional languages.
- **P2-4: Mobile-Responsive/Native Layouts** — optimized layouts for phone/tablet form factors.
- **P2-5: Custom Report Builder** — allowing users to construct and save custom multi-chart reports beyond the fixed P0-3 dashboard views.
- **P2-6: Shared/Team-Level Saved Views** — extending P1-4 so saved views can be shared across a Dealer's or OEM team's users.
- **P2-7: Predictive/Forecasting Analytics** — trend forecasting or ML-driven anomaly prediction beyond descriptive historical visualization.

---

## 7. Out of Scope (v1)

To prevent scope creep, the following are explicitly **not** part of this release:

- A **native mobile application** (iOS/Android). Only a responsive-enough web experience for desktop use is required for v1; dedicated mobile optimization is P2.
- **Write-capable chatbot actions** (creating, editing, or deleting Records via chat). v1 chatbot is strictly read-only (P0-4).
- **Automated system-to-system integration/sync** with OEM source-of-record systems. v1 supports manual entry and file-based import only (P0-5); live API/sync integration is P2 and requires separate scoping once source systems are identified.
- **Predictive analytics, forecasting, or machine-learning-driven recommendations.** v1 visualization is descriptive/historical only (P0-3).
- **Billing, invoicing, or payment processing** of any kind between OEMs and Dealers.
- **A public/partner-facing API** for third-party systems to consume platform data. Any future API is a separate initiative.
- **Full multi-language UI translation.** v1 may address regional formatting (P1-5) but not full UI localization (P2-3).
- **Offline mode / offline data entry.** The application requires an active connection for v1.
- **Definition of the specific business domain schema** (e.g., exact vehicle/claim/order field lists) is not finalized in this PRD — it is a required pre-implementation dependency tracked as the Data Dictionary (P0-5) and Open Questions, not a feature to be designed here.

---

## 8. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| **Cross-tenant data leakage** via grid, chart, or chatbot (a Dealer sees another Dealer's data) | Critical — breaks core trust model, potential legal/contractual exposure | Medium (chatbot free-text queries are the highest-risk surface) | Single, shared authorization layer enforced server-side for all three surfaces (P0-1); mandatory adversarial QA test suite specifically targeting chatbot cross-tenant leakage before every release; zero-tolerance success metric with audit log review |
| **Chatbot hallucination** — bot fabricates an answer not grounded in actual permitted data | High — destroys user trust in the platform's numbers | Medium-High (inherent risk with natural-language query interfaces) | Chatbot must only answer from data it can retrieve within scope; explicit fallback response required when it cannot answer (P0-4 acceptance criteria); QA regression test set with target ≥90% correct-and-in-scope answers, monitored post-launch |
| **Undefined business domain delays engineering** — grid/chart/chatbot cannot be built against an undefined schema | High — blocks all P0 features | High (currently unresolved) | Conceptual Data Model (Section 5) and Data Dictionary requirement (P0-5) established as explicit pre-implementation gates; domain confirmation tracked as Open Question #1, owner and deadline **[DECISION NEEDED]** |
| **Poor data quality from manual entry/import** (garbage-in) undermines dashboard/chatbot trust | Medium-High | Medium-High | Mandatory field-level validation on both Grid edits and Import (P0-2, P0-5); import success-rate tracked as a success metric; row-level (not batch-level) validation errors surfaced to users |
| **Dealer adoption resistance** — dealers may distrust giving OEM more visibility into their data, or may not trust the chatbot's answers | Medium | Medium | Clear, auditable access-scope guarantees communicated to dealers; onboarding flow (P1-1) demonstrates what OEM can/cannot see; phased pilot rollout recommended before full rollout |
| **Grid/Dashboard performance degradation** at scale (large dealer networks, large record volumes) | Medium | Medium (depends on undetermined data volume) | Explicit performance acceptance criteria in P0-2/P0-3 tied to confirmed volume assumptions; load testing required before GA; volume assumptions flagged as Open Question |
| **Scope creep from stakeholders wanting write-capable chatbot or live system integration in v1** | Medium | Medium-High (common pattern once chatbot/import are seen working) | Explicit Out of Scope section (Section 7) circulated and signed off by stakeholders; P2 backlog items documented so requests have a clear, deferred home rather than being added mid-build |
| **Concurrent edit conflicts** on shared Records between multiple dealer staff | Low-Medium | Medium | Conflict detection requirement in P0-2 acceptance criteria (surfacing "updated by another user" rather than silent overwrite) |

---

## 9. Open Questions

1. **[DECISION NEEDED]** What is the actual business domain / Record type(s) in scope for v1 (inventory, sales, service/warranty claims, parts orders, or a combination)? This blocks Data Dictionary authoring and detailed schema work for P0-2/P0-3/P0-5.
2. **[DECISION NEEDED]** What is the final Role list and permission matrix (this PRD uses OEM Admin / OEM Analyst / Dealer Principal / Dealer Staff as illustrative placeholders only)?
3. **[DECISION NEEDED]** Who owns authoring and maintaining the Data Dictionary (field list, types, validation rules) — the OEM, the platform team, or a joint process?
4. **[DECISION NEEDED]** What are the expected data volumes per tenant (Records per Dealer, number of Dealers per OEM) needed to set concrete performance targets for P0-2 and P0-3?
5. **[DECISION NEEDED]** What is the target chatbot response latency (P0-4)?
6. **[DECISION NEEDED]** Is the initial customer base multi-region/multi-currency (affects priority of P1-5 Localization)?
7. **[DECISION NEEDED]** Are there existing OEM source-of-record systems that will eventually need integration (affects future scoping of P2-2), and if so, which ones?
8. **[DECISION NEEDED]** For bulk import (P0-5), should a batch with partial validation failures commit the valid rows (partial success) or reject the entire batch (all-or-nothing)?
9. **[DECISION NEEDED]** What are the data retention and audit log retention requirements (e.g., regulatory/contractual retention periods for Audit Events)?
10. **[DECISION NEEDED]** What alert conditions/thresholds are needed for P1-2 Notifications, and who defines them (OEM-configured globally, or per-Dealer configurable)?
11. **[DECISION NEEDED]** Is there a target pilot customer/dealer group for initial rollout, to validate the baseline metrics currently marked as assumptions in Section 4.2?