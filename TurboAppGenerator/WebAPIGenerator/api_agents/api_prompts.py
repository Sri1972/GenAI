"""
System prompts for API generation mode.
These are used by the shared agents when mode="api" to produce production-grade APIs.
"""

# Moved to AgentPlatform/catalog/api_architect/config.yaml's `role` field
# (verbatim, minus the REST-naming bullets now covered by the shared
# backend_engineering_principles.md include) -- see api_orchestrator.py's
# __init__ (self._architect_agent).

API_ARCHITECT_USER = """\
Design the API architecture for the following requirements:

{requirements}

{endpoint_hints}

Language/Framework: {language}
Database: {database}

Return ONLY the JSON architecture document. No explanation text.
"""

# Moved to AgentPlatform/catalog/api_architect/config.yaml's `stage_roles.refine`
# field (verbatim) -- see api_orchestrator.py's refine() call site
# (self._architect_agent.generate(merge_prompt, stage="refine", ...)).

API_ARCHITECT_REFINE_USER = """\
The EXISTING architecture (preserve every entity/field/endpoint in here exactly,
except for whatever the requested change below explicitly asks to add):
{existing_architecture_json}

The requested change:
{refine_prompt}

Language/Framework: {language}
Database: {database}

Return ONLY the full, merged JSON architecture document. No explanation text.
"""

# Moved to AgentPlatform/catalog/api_services_engineer/config.yaml's `role`
# field (verbatim) -- see api_orchestrator.py's __init__ (self._services_agent).

# Implementation is split into a bootstrap call (entry point, DB setup, shared
# schemas, dependency manifest) followed by one call per entity — instead of a
# single monolithic call asked to generate an entire multi-entity API at once.
# This exists for two reasons: (1) progress visibility — a 10+ entity API used to
# be one multi-minute LLM call with zero feedback in between; splitting it reports
# a real milestone as each entity actually finishes generating, not just a final
# summary; (2) headroom — no single call is asked to produce the whole app's worth
# of files in one completion, which is the same class of truncation risk that
# motivated moving test generation to be deterministic (see _generate_tests).
SERVICES_ENGINEER_API_BOOTSTRAP_USER = """\
Generate ONLY the project's shared bootstrap/foundation files. Entity-specific
models, schemas, services, and routes are generated in separate calls afterward —
do NOT generate any of those yet, and do NOT reference any entity-specific module
that doesn't exist yet.

Full architecture (for context only — so the shared conventions you design here
work for every entity that's coming, not just generate anything entity-specific
from it yet):
{architecture_json}

Language: {language}
Auth type: {auth_type}
Include rate limiting: {rate_limiting}
Database: {database}

Generate exactly these kinds of files, and nothing entity-specific:
- Entry point: `src/main.py` for Python — a bare `FastAPI()` app (module-level
  `app`) with CORS middleware configured, no entity routes included yet (those are
  wired in automatically after each entity's own call) / `Application.java` for Java
- Database/session setup: `src/database.py` for Python (an engine + a `get_db()`
  dependency) / the equivalent Spring Data JPA datasource config for Java
- If the database is SQLite: SQLite disables foreign-key enforcement per connection
  by default, so a bad row (wrong/missing parent id) would otherwise insert
  successfully instead of failing loudly. In `src/database.py`, right after your
  engine is created, register a `connect` event listener that turns it on for every
  connection the pool opens:
  ```python
  from sqlalchemy import event

  @event.listens_for(engine, "connect")  # for an async engine, use engine.sync_engine here instead
  def _set_sqlite_pragma(dbapi_connection, connection_record):
      cursor = dbapi_connection.cursor()
      cursor.execute("PRAGMA foreign_keys=ON")
      cursor.close()
  ```
  This is mandatory, not optional — do not skip it or substitute a differently-named
  pragma.
- Do NOT create any pagination/list-result wrapper class — entities return Spring
  Data's own `Page<T>` directly (Java) or a plain inline dict (Python), per the
  system prompt's rule; there is deliberately nothing shared to generate here for
  pagination specifically.
- Shared error handling that EVERY entity's own files will rely on — this is
  mandatory, not optional, because entity files are generated in separate calls
  later and will assume these already exist without re-declaring them:
  - Python: a `ResourceNotFoundException` and a `ConflictException` in
    `src/exceptions.py`, plus `@app.exception_handler(...)` handlers registered on
    `app` for both of them AND for FastAPI's own `HTTPException`/
    `RequestValidationError`, all reshaping the response body to `{{"error": "..."}}`
    (NOT FastAPI's default `{{"detail": "..."}}`) so every entity's error responses
    look identical without each one having to format its own. ALSO register a
    catch-all `@app.exception_handler(Exception)` for anything not covered above —
    it MUST log the exception (`logging.getLogger(__name__).exception(...)`, which
    includes the full traceback) BEFORE returning the generic 500 `{{"error": "An
    unexpected error occurred"}}` body, otherwise a real bug in generated code has
    no way to ever surface in the logs — the response body alone can't say what
    broke.
  - Java: `com.api.exception.ResourceNotFoundException`,
    `com.api.exception.ConflictException`, and a
    `com.api.exception.GlobalExceptionHandler` annotated `@RestControllerAdvice`
    that maps ResourceNotFoundException to 404, ConflictException to 400 (a
    business-rule violation, e.g. a duplicate unique field or an invalid state
    transition — match whatever status the architecture's own data rules specify
    for that case), and validation errors to 400, all as a `{{"error": "..."}}`
    JSON body. Its catch-all `@ExceptionHandler(Exception.class)` MUST log the
    exception first — a private `static final Logger` field
    (`LoggerFactory.getLogger(GlobalExceptionHandler.class)`) and
    `log.error("Unhandled exception", ex);` — BEFORE returning the generic 500
    body, otherwise a real bug in generated code has no way to ever surface in the
    logs — the response body alone can't say what broke.
- The full dependency manifest (`requirements.txt` for Python, `pom.xml` for Java)
  covering everything the FULL architecture above will need once every entity is
  implemented, not just this call

Generate files as a JSON object: {{"files": {{"path/to/file": "content", ...}}}}
"""

SERVICES_ENGINEER_API_BATCH_USER = """\
Generate the model, schema/DTO, service, and controller/router for EACH of the
entities listed below — implement all of them in this one response, each with the
same per-entity file layout as if it were generated alone (one model, one schema,
one service, one controller per entity). Do not generate files for any entity NOT
listed below, and do not regenerate the shared bootstrap files listed further down,
or ANY entity's repository/DAO interface (including the entities in THIS batch) —
every repository, for every entity in the whole API, was already generated in a
separate step before this call; import and reuse them as-is, never redeclare one.

The FULL, exact content of every shared bootstrap file (exception classes, error
handler, etc.) AND every entity's repository/DAO interface — for the whole API, not
just entities implemented so far — is given below. This matters because some of
this API's own endpoints require querying another entity directly (e.g. checking a
referenced record's state before allowing an action, or a multi-entity "full
details" endpoint). When you call a constructor or method defined in ANY of these
files — a shared exception class, or any entity's repository — you MUST match its
real signature EXACTLY as written there: parameter count, order, and types. Do NOT
guess a plausible-looking signature from memory/convention — a guessed signature
that merely looks reasonable will not actually match what was really defined
elsewhere, and the mismatch is a compile error, not something caught until the
whole project fails to build. Reminder: pagination itself needs none of this in the
first place — return `Page<T>` (Java) or a plain dict (Python) directly, per the
system prompt, never a shared or per-service wrapper class of your own:
{shared_contract_files}

For any not-found / conflict error in any of this batch's services or controllers,
THROW the shared exceptions already generated in bootstrap — for Python,
`from src.exceptions import ResourceNotFoundException, ConflictException`; for
Java, `com.api.exception.ResourceNotFoundException` /
`com.api.exception.ConflictException`. Do NOT define your own exception class and
do NOT catch-and-format errors yourself — the shared handler registered in
bootstrap already converts these into the standard `{{"error": "..."}}` response for
every entity.

Full architecture (for context — field types and relationships of entities NOT in
this batch, needed to correctly type this batch's own foreign key fields):
{architecture_json}

The entities to implement in this call:
{entities_json}

Endpoints these entities' controllers/routers must implement — implement EXACTLY
these and no others. Do NOT also implement any other endpoint you notice in the
full architecture above just because it seems related to one of these entities
(e.g. a nested route under another resource that happens to return or accept this
batch's data) — every endpoint in the full architecture is assigned to exactly one
entity's implementation, and implementing it again here creates a duplicate route
mapping that crashes the app at startup with an ambiguous-mapping error, not a
compile error, so it won't be caught until the server actually tries to start:
{batch_endpoints_json}

Already-generated files so far (reuse these — the entry point, DB setup, shared
schemas, and any previously-implemented entity's files):
{existing_files_summary}

Language: {language}
Auth type: {auth_type}
Include rate limiting: {rate_limiting}
Database: {database}

Generate files as a JSON object: {{"files": {{"path/to/file": "content", ...}}}}
"""

# A custom/join/aggregate endpoint (e.g. GET /api/carrier-performance,
# joining two tables) doesn't belong to any single entity's resource path,
# so _endpoints_for_entity's per-entity matching (used to build each
# SERVICES_ENGINEER_API_BATCH_USER call above) never selects it for ANY
# entity's batch — it gets planned in the architecture and then silently
# never implemented at all. Reproduced directly: a real generation's
# architect planned 3 such endpoints, none of which existed anywhere in the
# generated tree. api_orchestrator.py computes which endpoints no entity
# batch claimed and, if any, sends them here as one dedicated call instead.
SERVICES_ENGINEER_API_CUSTOM_ENDPOINTS_USER = """\
Generate a SEPARATE, dedicated controller/router implementing ONLY the custom
endpoints listed below — each one is a cross-entity or aggregate query (a join,
group-by, or computed metric spanning more than one table) that does NOT belong
to any single entity's own CRUD controller. Do NOT create a new model/entity
class for these — read directly through the ALREADY-GENERATED repositories/DAOs
given below (or issue a raw query through the existing database session/
connection if no single repository method covers the join) and shape the
response to match each endpoint's description exactly.

Full architecture (for context — entity fields/relationships needed to build
the joins/aggregations below):
{architecture_json}

The FULL, exact content of every entity's repository/DAO interface — reuse
these for the underlying table access; match method signatures EXACTLY as
written, do NOT guess one that merely looks plausible:
{shared_contract_files}

Already-generated files so far (reuse these — the entry point, DB setup,
shared schemas, and every entity's own files):
{existing_files_summary}

Implement EXACTLY these endpoints and no others:
{custom_endpoints_json}

For any not-found / conflict error, THROW the shared exceptions already
generated in bootstrap — for Python, `from src.exceptions import
ResourceNotFoundException, ConflictException`; for Java,
`com.api.exception.ResourceNotFoundException` /
`com.api.exception.ConflictException`. Do NOT define your own exception class.

Language: {language}
Auth type: {auth_type}
Include rate limiting: {rate_limiting}
Database: {database}

For Python: place the router in `src/routes/custom.py`, exporting a
module-level `router = APIRouter()` — it will be auto-registered.
For Java: place the controller in the same package as the other controllers
(e.g. `com.api.controller.CustomEndpointsController`), annotated
`@RestController` — Spring's component scan picks it up automatically, no
manual wiring needed.

Generate files as a JSON object: {{"files": {{"path/to/file": "content", ...}}}}
"""

# Used only for entities that already exist and are being extended (new field,
# new endpoint) — never for a brand-new entity, which uses
# SERVICES_ENGINEER_API_BATCH_USER above unchanged, since "generate this fresh"
# is exactly what that prompt already does.
SERVICES_ENGINEER_API_REFINE_BATCH_USER = """\
This is a REFINEMENT to an API that is ALREADY BUILT and (likely) already running
against a database that may hold real seeded data — NOT a fresh build. For EACH of
the entities listed below, you are given the CURRENT, exact content of its model,
schema/DTO, service, and controller files. Update them to satisfy the refinement
request below:

- PRESERVE every existing field, method, endpoint, and behavior EXACTLY as-is —
  same names, same signatures, same logic — even if you would structure it
  differently starting from scratch.
- ONLY add what the refinement request below actually asks for: new fields on the
  model/DTO, new methods on the service, new endpoints on the controller.
- Do NOT rename, remove, or restructure anything that already works.
- Do NOT regenerate any entity NOT listed below, and do NOT regenerate any
  bootstrap file or repository interface — reuse them exactly as given.

The refinement request:
{refine_prompt}

The CURRENT content of every file for the entities in this batch (return the FULL
updated content for each file that needs a change — every file you don't need to
touch should simply not appear in your response at all, since it's already correct
as-is on disk):
{existing_batch_files}

The FULL, exact content of every shared bootstrap file AND every entity's
repository/DAO interface, for the whole API — same rule as always: match any
signature here EXACTLY, never guess one:
{shared_contract_files}

Full architecture (the FULL, already-merged result, including this refinement's own
new fields/endpoints):
{architecture_json}

This batch's entities, with their final (post-refinement) field lists:
{entities_json}

Endpoints these entities' controllers/routers must implement — this is the FULL
list for these entities post-refinement (existing endpoints are included here too,
not just the new one(s) — implement all of them, but only the NEW ones actually
need new code; the existing ones should already be satisfied by the existing
controller content above, so leave that method as-is):
{batch_endpoints_json}

Language: {language}
Auth type: {auth_type}
Include rate limiting: {rate_limiting}
Database: {database}

Generate files as a JSON object: {{"files": {{"path/to/file": "content", ...}}}} —
include ONLY the files that actually changed.
"""

# Used only for entities whose repository/DAO already exists and is being
# extended because of this refinement (a new field, or a new endpoint that
# was attributed to this entity) — never for a brand-new entity, which uses
# the plain repository batch prompt unchanged. Without this, regenerating a
# repository from scratch can silently change or drop an existing method's
# signature that OTHER, unrelated entities' already-generated service code
# still calls — breaking a cross-entity contract that this refine pass never
# even looks at, since only the entities in this batch are in scope.
REPOSITORY_REFINE_BATCH_USER = """\
This is a REFINEMENT to an API that is ALREADY BUILT and (likely) already running —
NOT a fresh build. Other entities' already-generated service code may call methods
on the repositories below by their EXACT current name and parameter list — you
cannot see that calling code in this call, so you must not change any signature
it might depend on.

- PRESERVE every existing method on each repository below EXACTLY as-is — same
  name, same parameter list (including Pageable, if present), same return type —
  even if you would design it differently starting from scratch.
- ONLY ADD new methods actually needed for the new fields/endpoints in this
  refinement. Never rename, remove, or change the parameters of an existing
  method — if an existing method almost fits but needs (for example) pagination
  it doesn't have, ADD a new, differently-named method instead of changing the
  existing one.
- Do NOT regenerate any repository NOT listed below.

The refinement request:
{refine_prompt}

The CURRENT, exact content of each repository/DAO module in this batch (return
the FULL updated content only for ones that actually need a new method; omit
any that need no change, since they're already correct as-is on disk):
{existing_repo_files}

This batch's entities, with their final (post-refinement) field lists:
{entities_json}

All entities in the API (for reference — field types/relationships of entities
NOT in this batch):
{entities_full_json}

All endpoints in the API (read every one, not just this batch's own — another
entity's endpoint may need a new method on one of these repositories):
{endpoints_json}

The real, already-finalized schema:
{schema_sql}

Language: {language}
Database: {database}

Generate files as a JSON object: {{"files": {{"path/to/file": "content", ...}}}} —
include ONLY the files that actually changed.
"""

# Moved to AgentPlatform/catalog/api_security_engineer/config.yaml's `role`
# field (verbatim) -- see api_orchestrator.py's __init__ (self._security_agent).

SECURITY_ENGINEER_USER = """\
Generate security middleware for this API:

Architecture: {architecture_json}
Language: {language}
Auth type: {auth_type}
Rate limit: {rate_limit_rpm} requests per minute per client

Existing files context:
{existing_files_summary}

Generate the security files as JSON: {{"files": {{"path": "content", ...}}}}
"""

# Tests themselves are generated deterministically now (see
# ApiCrewOrchestrator._generate_tests) — the architecture document already
# fully describes entities and endpoints, so there's no LLM judgment call
# left to make for standard CRUD/auth/404/rate-limit coverage, and no need to
# invent example data. Docs are still one small, separate LLM call — asking
# for tests + a full OpenAPI spec + a README all in one response used to
# routinely produce 100k+ char completions that got cut off mid-JSON with no
# way to repair them. README-only here is small and low-risk; the OpenAPI
# spec was dropped entirely — the running app already serves its own
# auto-generated, always-accurate spec at /docs or /v3/api-docs, so a second
# hand-written one would just drift out of sync with the real code.
DOCS_WRITER_SYSTEM = """\
You are a technical writer producing a README for a freshly generated API.

Cover:
- What the API does (one paragraph)
- Setup + run instructions for the target language/framework
- Environment variables it reads (and where the real generated values live)
- 2-3 example requests using curl, matching the real endpoints given

Output as JSON: {"files": {"README.md": "content"}}
"""

DOCS_WRITER_USER = """\
Write a README for this API:

Architecture: {architecture_json}
Language: {language}
Auth type: {auth_type}

Generate as JSON: {{"files": {{"README.md": "content"}}}}
"""
