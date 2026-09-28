# API Agent Architecture — TurboAppGenerator

## Overview

The API Agent generates production-ready, externally-consumable APIs from requirements. It follows the same proven pattern as the UI Agent (multi-agent orchestrator → post-processing → self-healing) but with specialized agents focused on API security, resilience, and standards compliance.

## Core Design Principle: Unified Agent Pool

**One set of highly-skilled agents powers BOTH web app and API generation.** The agents are built to the higher API standard and their capability is dialed up or down based on the generation mode:

| Agent | Web App Mode (lighter) | API Mode (full power) |
|-------|----------------------|---------------------|
| `data_architect` | Schema + seed for SQLite | Schema + migrations + indexes for PostgreSQL/SQLite |
| `services_engineer` | Simple CRUD backend | Full REST with services layer, validation, pagination |
| `security_engineer` | Skip (internal app) | JWT/OAuth2 + rate limiting + CORS + sanitization |
| `test_engineer` | Basic QA checks | Full test suite + harness + OpenAPI spec |
| `devops_engineer` | Simple start script | Dockerfile + compose + health checks |

The mode is passed as context to each agent's prompt, controlling depth:
```
mode: "webapp"  → "Generate a simple internal API server for the React frontend."
mode: "api"     → "Generate a production-grade, externally-facing API with auth, rate limiting, and comprehensive error handling."
```

This means **improvements to any agent benefit both pipelines** — a smarter `services_engineer` makes better web app backends AND better standalone APIs.

## Output Structure

Generated API projects produce a `files` dict with this structure:

```
{project-name}/
├── src/
│   ├── main.py / Application.java / app.ts     # Entry point
│   ├── config/
│   │   ├── settings.py / AppConfig.java         # Environment-driven config
│   │   ├── database.py / DatabaseConfig.java    # DB connection + pooling
│   │   └── security.py / SecurityConfig.java    # Auth + CORS + headers
│   ├── models/
│   │   └── {entity}.py / {Entity}.java          # DB models / entities
│   ├── schemas/
│   │   └── {entity}.py / {Entity}Dto.java       # Request/response schemas (validation)
│   ├── routes/ (or controllers/)
│   │   └── {entity}_routes.py / {Entity}Controller.java
│   ├── middleware/
│   │   ├── auth.py / AuthFilter.java            # JWT / API key validation
│   │   ├── rate_limit.py / RateLimitFilter.java # Token bucket rate limiting
│   │   ├── logging.py / RequestLogger.java      # Structured request/response logging
│   │   └── error_handler.py / GlobalExceptionHandler.java  # RFC 7807 errors
│   └── services/
│       └── {entity}_service.py / {Entity}Service.java  # Business logic
├── tests/
│   ├── conftest.py / TestConfig.java            # Test fixtures + test DB
│   ├── test_{entity}.py / {Entity}Test.java     # Unit + integration tests
│   └── test_harness.py / ApiTestHarness.java    # Interactive test runner
├── openapi.yaml                                  # OpenAPI 3.1 specification
├── Dockerfile                                    # Multi-stage production build
├── docker-compose.yml                            # API + DB + Redis (rate limiting)
├── .env.example                                  # Environment variable template
├── README.md                                     # Setup, endpoints, auth guide
└── Makefile / run.sh                             # Common commands (start, test, lint)
```

## Multi-Agent Pipeline (ApiCrewOrchestrator)

Six stages, mirroring the UI pipeline but with API-specialized agents:

### Stage 1: API Architecture (`api_architect`)
**Input:** Requirements text, optional endpoint definitions
**Output:** API design document

- Identifies entities/resources from requirements
- Defines endpoint structure (RESTful resource naming)
- Determines relationships and cardinality
- Chooses pagination strategy (cursor vs offset)
- Defines versioning approach (URL path: /v1/)
- Maps out authentication requirements per endpoint

### Stage 2: Data Modeling (`data_architect`)
**Input:** Architecture document
**Output:** `schema.sql`, `seed.sql`, model files

- Same agent as UI pipeline (reused)
- Generates database schema with indexes, constraints, foreign keys
- Creates seed data for testing
- Generates ORM models (SQLAlchemy / JPA / Prisma)

### Stage 3: Security & Middleware (`security_engineer`) ← NEW
**Input:** Architecture document, entity list
**Output:** Auth middleware, rate limiter, CORS config, error handler

- Generates JWT/OAuth2/API key authentication middleware
- Implements rate limiting (configurable: requests/minute per key)
- Sets up CORS with configurable origins
- Implements RFC 7807 Problem Details error responses
- Adds security headers (Helmet/Spring Security defaults)
- Generates request validation schemas with sanitization

### Stage 4: Routes & Business Logic (`api_engineer`)
**Input:** Architecture doc, models, schemas, middleware
**Output:** Route/controller files, service layer

- Generates RESTful controllers with full CRUD
- Implements business logic in service layer (separation of concerns)
- Adds input validation using schemas
- Implements pagination, filtering, sorting
- Adds proper HTTP status codes (201 Created, 204 No Content, etc.)
- Generates OpenAPI decorators/annotations inline

### Stage 5: Testing & Documentation (`test_engineer`) ← NEW
**Input:** All generated code, OpenAPI spec
**Output:** Test files, test harness, OpenAPI yaml, README

- Generates unit tests for each service
- Generates integration tests that hit actual endpoints
- Creates an interactive test harness (CLI or web-based)
- Generates the OpenAPI 3.1 spec from code annotations
- Writes README with setup instructions, auth guide, example requests

### Stage 6: Infrastructure & Packaging (`devops_engineer`) ← NEW
**Input:** All generated code, language choice
**Output:** Dockerfile, docker-compose, Makefile, .env.example

- Multi-stage Dockerfile (build → slim runtime)
- docker-compose with DB + Redis (for rate limiting state)
- Health check and readiness endpoints
- Graceful shutdown handling
- Environment variable documentation

## Unified Agent Pool

These agents are shared across BOTH web app and API generation. Each agent has a "depth dial" controlled by the mode parameter:

| Agent | Role | Shared With UI? | Key Skills |
|-------|------|----------------|-----------|
| `ux_architect` | Design pages, navigation, layout | UI only | UX, wireframing, React patterns |
| `api_architect` | Design REST resources, relationships, auth model | API only | RESTful design, API-first thinking |
| `data_architect` | Schema, models, migrations, seed data | **Both** | SQL, ORM, normalization |
| `services_engineer` | Routes, services, business logic, validation | **Both** (enhanced for API mode) | HTTP semantics, clean architecture |
| `security_engineer` | Auth, rate limiting, CORS, input sanitization | **Both** (skip for webapp, full for API) | OWASP API Top 10, OAuth2, JWT |
| `test_engineer` | Tests, harness, OpenAPI spec, docs | **Both** (QA for webapp, full for API) | Testing patterns, OpenAPI 3.1 |
| `devops_engineer` | Docker, compose, health checks, packaging | API only | Containerization, 12-factor app |
| `visual_design` | UI components, charts, styling | UI only | React, Tailwind, D3 |
| `react_ui` | Pages, routing, state management | UI only | React, TypeScript |

**The `services_engineer` is the key shared agent** — today it generates the simple `app_server_template.py` / Spring Boot for web apps. By upgrading it to API-grade skills, web app backends also improve (better error handling, proper validation, etc.).

## Post-Processing Pipeline

After generation, run fixers specific to API concerns:

```python
files = _fix_import_consistency(files)        # Fix cross-file import issues
files = _fix_openapi_spec(files)              # Validate + fix OpenAPI yaml
files = _fix_error_responses(files)           # Ensure RFC 7807 consistency
files = _fix_auth_middleware_wiring(files)     # Ensure auth applied to all routes
files = _fix_rate_limit_config(files)          # Ensure rate limit values are sane
files = _fix_test_imports(files)               # Fix test file imports
files = _inject_health_endpoint(files)         # Ensure /health and /ready exist
```

## Self-Healing Loops

### Loop 1: Syntax & Type Check
- **Python:** `mypy --strict` + `ruff check`
- **Java:** `mvn compile` (catches type errors)
- **Node:** `tsc --noEmit`
- Feed errors back to LLM for up to 3 rounds (same as UI `_tsc_heal`)

### Loop 2: Test Execution
- Run the generated test suite
- If tests fail, feed failures to LLM to fix the implementation
- Up to 2 rounds (same as UI `_qa_heal`)

### Loop 3: OpenAPI Validation ← NEW
- Validate `openapi.yaml` against OpenAPI 3.1 spec
- Check that all defined routes match the spec
- Fix discrepancies

## Progress Reporting

Same pattern as UI — callback with stage tags:

```
"api:architecture"    → Designing API structure...
"api:data_model"      → Creating database models...
"api:security"        → Building auth & rate limiting...
"api:routes"          → Generating endpoints & business logic...
"api:tests"           → Writing tests & documentation...
"api:packaging"       → Creating Docker & deploy config...
"api:validate"        → Running type checks...
"api:test_run"        → Executing test suite...
"api:ready"           → API ready!
```

## Language Support (Both first-class from Day 1)

### Python (FastAPI)
- FastAPI + Pydantic v2 for validation
- SQLAlchemy 2.0 for ORM
- Alembic for migrations
- pytest + httpx for testing
- slowapi for rate limiting
- uvicorn for production serving

### Java (Spring Boot) ← Same priority as Python
- Spring Boot 3.3 + Spring Security
- JPA/Hibernate for ORM
- Flyway for migrations
- JUnit 5 + MockMvc + RestAssured for testing
- Bucket4j for rate limiting
- Embedded Tomcat for production serving
- Already proven in TurboUIGen web app backends

### Node.js (Express + TypeScript) — Phase 3
- Express + express-validator + Zod
- Prisma ORM
- Jest + supertest for testing
- express-rate-limit for rate limiting

## How Mode Controls the Same Agents

| Aspect | Web App Mode | API Mode |
|--------|-------------|----------|
| Primary output | React .tsx + simple backend | Production API (routes, services, middleware) |
| `services_engineer` depth | Simple CRUD, no auth | Full REST, services layer, validation, pagination |
| `security_engineer` | Skipped | JWT/OAuth2 + rate limiting + CORS |
| `test_engineer` | QA visual checks | Full test suite + OpenAPI spec + harness |
| `data_architect` | SQLite, simple schema | PostgreSQL option, indexes, migrations |
| Validation | TSC compiles + visual QA | Type check + tests pass + OpenAPI valid |
| Run environment | Vite + simple API server | uvicorn / Spring Boot / node |
| Post-processing | Fix imports, D3, maps | Fix OpenAPI, auth wiring, test imports |
| Languages | Python or Java (backend) | Python or Java (full stack) |
| Docker | Not included | Dockerfile + docker-compose |

**The upgrade path is automatic:** as we make `services_engineer` smarter for API mode, web app backends get better error handling, validation, and structure for free.

## Implementation Priority

### Phase 1 (MVP — Get it working, Python + Java)
1. Upgrade `services_engineer` agent prompts to handle API mode (shared agent)
2. Create `ApiCrewOrchestrator` (adapt from UI orchestrator, reuse `data_architect`)
3. Add `api_architect` stage (architecture + endpoint design)
4. Generate routes/controllers + models + services for **both Python and Java**
5. Basic `_fix_*` post-processors for API code
6. Wire into `/api/generate` with `mode: "api"` parameter
7. Templates for both FastAPI and Spring Boot (parallel to existing web app templates)

### Phase 2 (Security + Testing)
8. Add `security_engineer` prompts (JWT + rate limiting + CORS)
9. Add `test_engineer` prompts (tests + OpenAPI spec + harness)
10. Self-healing: type check + test execution loops
11. Security templates for both Python (slowapi, python-jose) and Java (Spring Security, Bucket4j)

### Phase 3 (Polish + Node.js)
12. Add `devops_engineer` stage (Docker + compose + health)
13. Node.js (Express + TypeScript) support
14. Interactive test harness in the UI (run tests from browser)
15. Import from Product Forge (same as UI tab)
16. Web app backends automatically upgraded (shared agent improvements flow back)

## API Endpoint (server.py)

```python
POST /api/generate
{
  "project_name": "inventory-service",
  "prompt": "Requirements text...",
  "mode": "api",                          # ← NEW: "webapp" (default) or "api"
  "api_options": {                         # ← NEW: API-specific config
    "language": "python",                  # python | java | node
    "auth_type": "jwt",                    # jwt | api_key | oauth2 | none
    "rate_limit": 100,                     # requests per minute per client
    "database": "postgresql",              # sqlite | postgresql | mysql
    "include_docker": true,
    "include_tests": true,
    "endpoints": [                         # optional — AI infers if omitted
      {"method": "GET", "path": "/api/v1/inventory", "description": "List items"}
    ]
  }
}
```

## Templates Needed

Similar to the UI agent's `services_engineer/templates/`:

```
agents/api_engineer/templates/
├── python/
│   ├── main_template.py                  # FastAPI app skeleton
│   ├── auth_jwt_template.py              # JWT middleware
│   ├── auth_apikey_template.py           # API key middleware
│   ├── rate_limit_template.py            # Rate limiting middleware
│   ├── error_handler_template.py         # RFC 7807 error handler
│   ├── health_template.py               # Health/readiness endpoints
│   ├── test_conftest_template.py         # pytest fixtures
│   └── Dockerfile.template              # Multi-stage Python build
├── java/
│   ├── Application.java                  # Spring Boot entry
│   ├── SecurityConfig.java               # Spring Security config
│   ├── RateLimitFilter.java              # Bucket4j rate limiter
│   ├── GlobalExceptionHandler.java       # RFC 7807 errors
│   ├── HealthController.java             # Actuator + custom health
│   └── Dockerfile.template              # Multi-stage Maven build
└── node/
    ├── app_template.ts                   # Express app skeleton
    ├── auth_middleware_template.ts        # JWT/API key middleware
    ├── rate_limit_template.ts            # express-rate-limit config
    ├── error_handler_template.ts         # Error middleware
    └── Dockerfile.template              # Multi-stage Node build
```

## Prompt Architecture

Each agent gets a system prompt defining its expertise:

- **api_architect:** "You are a senior API architect. Design RESTful APIs following best practices: resource-oriented URLs, proper HTTP verbs, consistent naming, HATEOAS where appropriate..."
- **security_engineer:** "You are a security engineer specializing in API security. Implement auth following OWASP API Security Top 10. Never store secrets in code. Always validate and sanitize input..."
- **api_engineer:** "You are a backend engineer. Write clean, testable code with proper separation of concerns. Use dependency injection. Handle all error cases. Return appropriate HTTP status codes..."
- **test_engineer:** "You are a QA engineer. Write comprehensive tests: happy path, edge cases, auth failures, rate limit behavior, invalid input. Generate realistic test data..."
