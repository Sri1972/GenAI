# Backend Architecture Diagrams

> End-to-end flow for TurboUIGen web apps with Python (FastAPI) vs Java (Spring Boot) backends.

---

## Table of Contents

- [Generation Pipeline (Shared)](#generation-pipeline)
- [Runtime: Python Backend](#runtime-python)
- [Runtime: Java Spring Boot Backend](#runtime-java)
- [Shared Frontend Contract](#shared-frontend)
- [Request Flow Through Proxy Chain](#proxy-chain)
- [Directory Structure Comparison](#directory-comparison)
- [Startup Process Comparison](#startup-comparison)
- [Component Layering](#component-layering)

---

<div id="generation-pipeline"></div>

## Generation Pipeline (Shared for Both Backends)

Both Python and Java apps go through the same multi-agent generation pipeline. The `backend_type` parameter ("python" or "java") determines which backend template is bundled.

```
  User (Browser at localhost:3000)
       |
       |  POST /api/generate
       |  { prompt: "...", backend_type: "python" | "java" }
       |
       v
  +------------------------------------------------------------------+
  |  API Gateway  (API/server.py - FastAPI @ port 3000)              |
  |                                                                   |
  |  GenerateRequest { prompt, backend_type, project_name }          |
  +------------------------------------------------------------------+
       |
       v
  +------------------------------------------------------------------+
  |  generate_project(prompt, backend_type)                           |
  |  WebUIGenerator/agents/uigen_agent.py                            |
  +------------------------------------------------------------------+
       |
       |  1. Multi-Agent Crew generates files dict
       |
       v
  +------------------------------------------------------------------+
  |  6-Agent Pipeline                                                 |
  |                                                                   |
  |  +-------------+   +---------------+   +------------------+      |
  |  | 1. UX       |-->| 2. Data       |-->| 3. Visual Design |      |
  |  | Architect   |   | Architect     |   | Agent            |      |
  |  |             |   |               |   |                  |      |
  |  | pages,      |   | schema.sql,   |   | Tailwind theme,  |      |
  |  | navigation, |   | seed.sql,     |   | color palette    |      |
  |  | layout      |   | relationships |   |                  |      |
  |  +-------------+   +---------------+   +------------------+      |
  |        |                  |                     |                  |
  |        v                  v                     v                  |
  |  +------------------------------------------------------------+  |
  |  | 4. Orchestrator (parallel page generation via ThreadPool)   |  |
  |  |    Generates: src/pages/*.tsx, src/components/*.tsx          |  |
  |  +------------------------------------------------------------+  |
  |        |                                                          |
  |        v                                                          |
  |  +-------------------+   +------------------+                    |
  |  | 5. Services Eng.  |   | 6. AI/GenAI      |                    |
  |  |                   |   | (if DataChat)    |                    |
  |  | useApi.ts,        |   | DataChat.tsx,    |                    |
  |  | App.tsx,          |   | chat_api.py      |                    |
  |  | vite.config.ts    |   |                  |                    |
  |  +-------------------+   +------------------+                    |
  +------------------------------------------------------------------+
       |
       |  2. Bundle backend based on backend_type
       |
       v
  +------------------------------------------------------------------+
  |  _bundle_api_server(files, backend_type)                          |
  |                                                                   |
  |       backend_type == "python"        backend_type == "java"      |
  |              |                               |                    |
  |              v                               v                    |
  |  +---------------------+      +---------------------------+      |
  |  | _bundle_python_api  |      | _bundle_java_api_server   |      |
  |  |                     |      |                           |      |
  |  | Copies:             |      | Copies from templates/:   |      |
  |  |  app_server_        |      |  pom.xml                  |      |
  |  |   template.py       |      |  Application.java         |      |
  |  |  --> api/app_server  |      |  DatabaseConfig.java      |      |
  |  |                     |      |  CorsConfig.java          |      |
  |  | Moves:              |      |  DatabaseInitializer.java  |      |
  |  |  schema.sql --> api/ |      |  TableService.java        |      |
  |  |  seed.sql --> api/   |      |  DynamicApiController.java|      |
  |  |                     |      |  mvnw.cmd                  |      |
  |  | Creates:            |      |                           |      |
  |  |  api/.env           |      | Moves:                    |      |
  |  |  api/requirements   |      |  schema.sql --> backend/   |      |
  |  |   .txt              |      |  seed.sql --> backend/     |      |
  |  +---------------------+      |                           |      |
  |                               | Creates:                   |      |
  |                               |  backend/.env              |      |
  |                               |  backend/.backend_type     |      |
  |                               +---------------------------+      |
  +------------------------------------------------------------------+
       |
       |  3. Run postprocessors
       |
       v
  +------------------------------------------------------------------+
  |  run_all_postprocessors(files, project_name, port, api_port)      |
  |                                                                   |
  |  Key steps:                                                       |
  |  - _patch_vite_for_ds()     --> Clean vite.config.ts template     |
  |  - _inject_api_proxy()      --> Adds proxy + base path config     |
  |  - 15+ other fixers         --> D3, imports, props, maps, etc.    |
  +------------------------------------------------------------------+
       |
       |  4. Write to disk, start servers
       |
       v
  +------------------------------------------------------------------+
  |  _write_files(project_dir, files)                                 |
  |  _ensure_node_modules()  --> junction to shared-nm                |
  |  _start_vite(project_dir, port)     --> Vite dev server           |
  |  _start_api_server(project_dir, api_port)                         |
  |       |                                                           |
  |       |-- reads backend/.backend_type                             |
  |       |                                                           |
  |       |-- "java-springboot" --> _start_java_api_server()          |
  |       |       mvn spring-boot:run --server.port={api_port}        |
  |       |       (reads JAVA_HOME, MAVEN_HOME from backend/.env)     |
  |       |                                                           |
  |       |-- (default/python) --> python api/app_server.py           |
  |       |       (reads API_PORT from api/.env)                      |
  +------------------------------------------------------------------+
       |
       |  5. Self-heal
       |
       v
  +------------------------------------------------------------------+
  |  _tsc_heal (up to 3 rounds) --> Fix TypeScript errors             |
  |  QA Agent (Playwright)      --> Visit routes, capture errors      |
  |  _qa_heal (up to 2 rounds)  --> Fix runtime errors                |
  +------------------------------------------------------------------+
       |
       v
  App live at http://localhost:3000/app/{project-name}/
```

---

<div id="runtime-python"></div>

## Runtime Architecture: Python Backend

```
  Browser (User)
       |
       |  http://localhost:3000/app/{name}/
       |
       v
  +------------------------------------------------------------------+
  |  TurboUIGen Main Server (FastAPI @ port 3000)                     |
  |  API/server.py                                                    |
  |                                                                   |
  |  proxy_vite() handler:                                            |
  |  +------------------------------------------------------------+  |
  |  |                                                             |  |
  |  |  IF path starts with "api/"                                 |  |
  |  |       |                                                     |  |
  |  |       +--> Direct route to API backend (port 81xx)          |  |
  |  |            (bypasses Vite, low latency)                     |  |
  |  |                                                             |  |
  |  |  ELSE (static assets, .tsx, .css, etc.)                     |  |
  |  |       |                                                     |  |
  |  |       +--> Forward to Vite dev server (port 51xx)           |  |
  |  |                                                             |  |
  |  +------------------------------------------------------------+  |
  +------------------------------------------------------------------+
       |                          |
       | API requests             | Asset requests
       v                          v
  +------------------------+   +----------------------------------+
  |  Python API Server     |   |  Vite Dev Server (port 51xx)     |
  |  (port 81xx)           |   |                                  |
  |                        |   |  Serves:                         |
  |  api/app_server.py     |   |   - src/*.tsx (transpiled)       |
  |  Framework: FastAPI    |   |   - Tailwind CSS                 |
  |  DB: aiosqlite         |   |   - node_modules (via junction)  |
  |                        |   |                                  |
  |  Single-file server:   |   |  Config:                         |
  |  - Auto-discovers      |   |   - base: /app/{name}/           |
  |    tables from         |   |   - proxy fallback: /api/* -->   |
  |    schema.sql          |   |     localhost:81xx               |
  |  - Creates SQLite DB   |   |   - HMR: disabled                |
  |    on startup          |   |                                  |
  |  - Runs seed.sql       |   +----------------------------------+
  |                        |
  |  Routes:               |
  |  GET  /api/data/{t}    |  --> { data: [...], total, limit, offset, hasMore }
  |  GET  /api/data/{t}/   |
  |       count            |  --> { count: N }
  |  GET  /api/data/{t}/   |
  |       aggregate        |  --> [{ group, value }, ...]
  |  POST /api/data/{t}    |  --> { created row }
  |  PUT  /api/data/{t}/{id}   --> { updated row }
  |  DELETE /api/data/{t}/{id} --> { deleted: true }
  |  GET  /api/metadata    |  --> { tables, columns }
  |                        |
  |       +--------+       |
  |       | SQLite |       |
  |       | data.db|       |
  |       +--------+       |
  +------------------------+
```

---

<div id="runtime-java"></div>

## Runtime Architecture: Java Spring Boot Backend

```
  Browser (User)
       |
       |  http://localhost:3000/app/{name}/
       |
       v
  +------------------------------------------------------------------+
  |  TurboUIGen Main Server (FastAPI @ port 3000)                     |
  |  API/server.py                                                    |
  |                                                                   |
  |  proxy_vite() handler:                                            |
  |  +------------------------------------------------------------+  |
  |  |                                                             |  |
  |  |  IF path starts with "api/"                                 |  |
  |  |       |                                                     |  |
  |  |       +--> Direct route to API backend (port 81xx)          |  |
  |  |            (bypasses Vite, low latency)                     |  |
  |  |                                                             |  |
  |  |  ELSE (static assets, .tsx, .css, etc.)                     |  |
  |  |       |                                                     |  |
  |  |       +--> Forward to Vite dev server (port 51xx)           |  |
  |  |                                                             |  |
  |  +------------------------------------------------------------+  |
  +------------------------------------------------------------------+
       |                          |
       | API requests             | Asset requests
       v                          v
  +-----------------------------+   +-------------------------------+
  |  Java Spring Boot Server    |   |  Vite Dev Server (port 51xx)  |
  |  (port 81xx)                |   |                               |
  |                             |   |  (Same as Python path)        |
  |  Embedded Tomcat            |   |                               |
  |  Spring Boot 3.3.5          |   +-------------------------------+
  |  JdbcTemplate + SQLite      |
  |                             |
  |  OOP Layered Architecture:  |
  |                             |
  |  +-------------------------+|
  |  |     Controller Layer    ||
  |  |  DynamicApiController   ||
  |  |  @RestController        ||
  |  |  @RequestMapping("/api")||
  |  |                         ||
  |  |  Endpoints:             ||
  |  |  GET  /api/data/{t}     ||  --> { data, total, limit, offset, hasMore }
  |  |  GET  /api/data/{t}/    ||
  |  |       count             ||  --> { count: N }
  |  |  GET  /api/data/{t}/    ||
  |  |       aggregate         ||  --> [{ group, value }, ...]
  |  |  GET  /api/data/{t}/{id}||  --> { single row }
  |  |  POST /api/data/{t}     ||  --> { created row } (201)
  |  |  PUT  /api/data/{t}/{id}||  --> { updated row }
  |  |  DELETE /api/data/{t}/{id} --> { deleted: true }
  |  |  GET  /api/tables       ||  --> { tables: [...] }
  |  +------------+------------+|
  |               |             |
  |               v             |
  |  +-------------------------+|
  |  |      Service Layer      ||
  |  |    TableService.java    ||
  |  |                         ||
  |  |  - getAll(table, limit, ||
  |  |    offset, order)       ||
  |  |  - query(table, filters,||
  |  |    limit, offset, order)||
  |  |  - count(table)         ||
  |  |  - getById(table, id)   ||
  |  |  - insert(table, data)  ||
  |  |  - update(table, id,    ||
  |  |    data)                ||
  |  |  - delete(table, id)    ||
  |  |  - aggregate(table,     ||
  |  |    groupBy, agg)        ||
  |  |  - listTables()         ||
  |  |  - validateTableName()  ||
  |  |  - getPrimaryKeyColumn()||
  |  +------------+------------+|
  |               |             |
  |               v             |
  |  +-------------------------+|
  |  |      DAO Layer          ||
  |  |   Spring JdbcTemplate   ||
  |  |                         ||
  |  |  - queryForList()       ||
  |  |  - queryForObject()     ||
  |  |  - update()             ||
  |  |  (parameterized SQL)    ||
  |  +------------+------------+|
  |               |             |
  |               v             |
  |  +-------------------------+|
  |  |    Configuration        ||
  |  |                         ||
  |  |  DatabaseConfig.java    ||
  |  |   - SQLite DataSource   ||
  |  |   - DB_PATH from env    ||
  |  |                         ||
  |  |  CorsConfig.java        ||
  |  |   - Allow localhost:*   ||
  |  |                         ||
  |  |  DatabaseInitializer    ||
  |  |   - @PostConstruct      ||
  |  |   - Reads schema.sql    ||
  |  |   - Reads seed.sql      ||
  |  |   - IF NOT EXISTS safe  ||
  |  |   - Seeds empty tables  ||
  |  +------------+------------+|
  |               |             |
  |               v             |
  |  +-------------------------+|
  |  |       SQLite DB         ||
  |  |       data.db           ||
  |  |                         ||
  |  |  org.xerial:sqlite-jdbc ||
  |  |  (portable, same as     ||
  |  |   production Postgres)  ||
  |  +-------------------------+|
  +-----------------------------+
```

---

<div id="shared-frontend"></div>

## Shared Frontend Contract

The frontend is **identical** regardless of backend type. Both backends implement the same REST API contract.

```
  +------------------------------------------------------------------+
  |  useApi.ts Hook (same for Python and Java backends)               |
  +------------------------------------------------------------------+
  |                                                                   |
  |  const _API_BASE = import.meta.env.BASE_URL  // "/app/{name}"    |
  |                                                                   |
  |  Request:                                                         |
  |  fetch(`${_API_BASE}/api/data/${table}?limit=100&offset=0&order=asc`)
  |                                                                   |
  |  Expected Response (BOTH backends return this):                   |
  |  +-------------------------------------------------------------+ |
  |  |  {                                                           | |
  |  |    "data": [ { row1 }, { row2 }, ... ],                      | |
  |  |    "total": 150,                                             | |
  |  |    "limit": 100,                                             | |
  |  |    "offset": 0,                                              | |
  |  |    "hasMore": true                                           | |
  |  |  }                                                           | |
  |  +-------------------------------------------------------------+ |
  |                                                                   |
  |  Features:                                                        |
  |  - Retry with exponential backoff (2x on 500+)                   |
  |  - AbortController on component unmount                          |
  |  - Pagination (offset-based)                                     |
  |  - Sort and filter params                                        |
  |  - BASE_URL-aware (works through proxy chain)                    |
  |                                                                   |
  +------------------------------------------------------------------+
  |                                                                   |
  |  Additional API functions (same contract, both backends):         |
  |                                                                   |
  |  fetchAggregate(table, groupBy, agg)                             |
  |    --> GET /api/data/{table}/aggregate?group_by=X&agg=count      |
  |                                                                   |
  |  createRecord(table, data)                                       |
  |    --> POST /api/data/{table}  body: { ...fields }               |
  |                                                                   |
  |  updateRecord(table, id, data)                                   |
  |    --> PUT /api/data/{table}/{id}  body: { ...fields }           |
  |                                                                   |
  |  deleteRecord(table, id)                                         |
  |    --> DELETE /api/data/{table}/{id}                              |
  |                                                                   |
  +------------------------------------------------------------------+

  The same schema.sql and seed.sql drive both backends.
  Same useApi hook. Same React components.
  The backend is completely transparent to the frontend.
```

---

<div id="proxy-chain"></div>

## Request Flow Through Proxy Chain

```
  Browser at localhost:3000
       |
       |  GET /app/my-app/api/data/employees?limit=100&offset=0
       |
       v
  +------------------------------------------------------------------+
  |  TurboUIGen Main Server (port 3000)                               |
  |  API/server.py :: proxy_vite()                                    |
  |                                                                   |
  |  path = "api/data/employees"                                      |
  |  path.startswith("api/") == True                                  |
  |       |                                                           |
  |       +--> Direct route to backend                                |
  |            api_port = _api_ports["my-app"]  // e.g. 8107          |
  |            target = http://127.0.0.1:8107/api/data/employees      |
  |            ?limit=100&offset=0                                    |
  +------------------------------------------------------------------+
       |
       v (direct HTTP forward)
  +------------------------------------------------------------------+
  |  Backend Server (port 8107)                                       |
  |                                                                   |
  |  Python: FastAPI                  Java: Spring Boot               |
  |  @app.get("/api/data/{table}")    @GetMapping("/data/{table}")    |
  |                                                                   |
  |  Both return:                                                     |
  |  { "data": [...], "total": 42, "limit": 100,                    |
  |    "offset": 0, "hasMore": false }                               |
  +------------------------------------------------------------------+
       |
       v (JSON response back up the chain)
  +------------------------------------------------------------------+
  |  TurboUIGen Main Server (port 3000)                               |
  |  Returns response to browser with original Content-Type          |
  +------------------------------------------------------------------+
       |
       v
  Browser receives JSON, useApi hook populates component state


  --- For static assets (CSS, JS, images): ---

  Browser: GET /app/my-app/src/pages/Dashboard.tsx
       |
       v
  TurboUIGen (port 3000) :: proxy_vite()
       | path = "src/pages/Dashboard.tsx"
       | path.startswith("api/") == False
       v
  Forward to Vite (port 51xx)
       | Vite transpiles .tsx --> JavaScript
       v
  Return transpiled JS to browser
```

---

<div id="directory-comparison"></div>

## Directory Structure Comparison

### Python Backend App

```
generated/web-apps/{app-name}/
|
+-- src/                              <-- React frontend
|   +-- App.tsx                       Main app component + router
|   +-- main.tsx                      Entry point
|   +-- pages/
|   |   +-- Dashboard.tsx             Page components
|   |   +-- Analytics.tsx
|   |   +-- ...
|   +-- components/
|   |   +-- ExportToolbar.tsx         CSV/Excel/PDF export
|   |   +-- ...
|   +-- hooks/
|       +-- useApi.ts                 Data fetching hook
|
+-- api/                              <-- Python backend
|   +-- app_server.py                 FastAPI server (single file)
|   +-- schema.sql                    Table definitions
|   +-- seed.sql                      Sample data
|   +-- data.db                       SQLite database (auto-created)
|   +-- .env                          API_PORT=81xx
|   +-- requirements.txt              aiosqlite, fastapi, uvicorn
|
+-- vite.config.ts                    Vite config (proxy + base path)
+-- package.json                      npm deps (mirrors shared-nm)
+-- tsconfig.json                     TypeScript config + path aliases
+-- tailwind.config.js                Tailwind theme
+-- index.html                        HTML entry point
+-- node_modules/                     --> junction to shared-nm
+-- api_server.log                    Backend stdout/stderr
+-- vite.log                          Vite stdout/stderr
+-- .meta.json                        Project metadata
+-- .history.json                     Build history
```

### Java Spring Boot Backend App

```
generated/web-apps/{app-name}/
|
+-- src/                              <-- React frontend (IDENTICAL)
|   +-- App.tsx
|   +-- main.tsx
|   +-- pages/
|   |   +-- Dashboard.tsx
|   |   +-- Analytics.tsx
|   |   +-- ...
|   +-- components/
|   |   +-- ExportToolbar.tsx
|   |   +-- ...
|   +-- hooks/
|       +-- useApi.ts                 Same hook, same API contract
|
+-- backend/                          <-- Java backend
|   +-- pom.xml                       Maven build (Spring Boot 3.3.5)
|   +-- .backend_type                 "java-springboot" (marker file)
|   +-- .env                          JAVA_HOME, MAVEN_HOME, PORT, DB_PATH
|   +-- schema.sql                    Table definitions (same format)
|   +-- seed.sql                      Sample data (same format)
|   +-- data.db                       SQLite database (auto-created)
|   +-- mvnw.cmd                      Maven wrapper (no global install needed)
|   +-- src/
|   |   +-- main/
|   |       +-- java/com/turboui/app/
|   |       |   +-- Application.java           @SpringBootApplication
|   |       |   +-- config/
|   |       |   |   +-- DatabaseConfig.java    SQLite DataSource bean
|   |       |   |   +-- CorsConfig.java        CORS for React frontend
|   |       |   +-- service/
|   |       |   |   +-- TableService.java      Business logic + JDBC
|   |       |   |   +-- DatabaseInitializer.java  Schema + seed on startup
|   |       |   +-- controller/
|   |       |       +-- DynamicApiController.java  REST endpoints
|   |       +-- resources/
|   |           +-- application.properties     server.port, JDBC URL
|   +-- target/                       (Maven build output - auto-generated)
|
+-- vite.config.ts                    Vite config (proxy + base path)
+-- package.json                      npm deps (mirrors shared-nm)
+-- tsconfig.json                     TypeScript config + path aliases
+-- tailwind.config.js                Tailwind theme
+-- index.html                        HTML entry point
+-- node_modules/                     --> junction to shared-nm
+-- api_server.log                    Backend stdout/stderr (mvn output)
+-- vite.log                          Vite stdout/stderr
+-- .meta.json                        Project metadata
+-- .history.json                     Build history
```

---

<div id="startup-comparison"></div>

## Startup Process Comparison

| Step | Python Backend | Java Spring Boot Backend |
|------|---------------|--------------------------|
| **Detection** | `api/app_server.py` exists | `backend/.backend_type` = "java-springboot" |
| **Config file** | `api/.env` (API_PORT) | `backend/.env` (JAVA_HOME, MAVEN_HOME, PORT, DB_PATH) |
| **Start command** | `python api/app_server.py` | `mvn spring-boot:run --server.port=81xx` |
| **DB initialization** | Python reads schema.sql + seed.sql at startup | `@PostConstruct` in DatabaseInitializer.java |
| **DB driver** | `aiosqlite` (async) | `org.xerial:sqlite-jdbc` (JDBC) |
| **Web framework** | FastAPI + uvicorn | Spring Boot + embedded Tomcat |
| **Startup time** | ~2 seconds | ~8-20 seconds (Maven compile + Spring init) |
| **TurboUIGen timeout** | 15 seconds | 90 seconds |
| **Process flags** | `DETACHED_PROCESS` (survives parent restart) | `DETACHED_PROCESS` (survives parent restart) |
| **Hot reload** | No (restart required) | No (restart required, recompiles) |
| **Port env var** | `API_PORT` | `PORT` (also `server.port` in properties) |

---

<div id="component-layering"></div>

## Component Layering Comparison

### Python: Single-File Architecture

```
+-------------------------------------------+
|           app_server.py                    |
|                                           |
|  +-------------------------------------+ |
|  |  Routes (FastAPI decorators)        | |
|  |  @app.get("/api/data/{table}")      | |
|  |  @app.get("/api/data/{table}/count")| |
|  |  @app.post("/api/data/{table}")     | |
|  +-------------------------------------+ |
|  |  Business Logic (inline functions)  | |
|  |  - discover_tables()               | |
|  |  - validate_table_name()           | |
|  |  - get_primary_key()               | |
|  +-------------------------------------+ |
|  |  Data Access (aiosqlite)            | |
|  |  - async with aiosqlite.connect()  | |
|  |  - cursor.execute(sql, params)     | |
|  +-------------------------------------+ |
|  |  Startup                            | |
|  |  - Read schema.sql                 | |
|  |  - Run seed.sql                    | |
|  |  - uvicorn.run(app, port=PORT)     | |
|  +-------------------------------------+ |
+-------------------------------------------+

  Single file, ~400 lines
  Good for: rapid prototyping, simple APIs
  Trade-off: no separation of concerns
```

### Java: OOP Layered Architecture

```
+-------------------------------------------+
|  Controller Layer                         |
|  DynamicApiController.java                |
|                                           |
|  - @RestController                        |
|  - @RequestMapping("/api")                |
|  - Input validation (path vars, params)   |
|  - Response formatting (wrapped JSON)     |
|  - HTTP status codes (200, 201, 400, 404) |
|  - Exception handling                     |
+-------------------+-----------------------+
                    |
                    v  (dependency injection)
+-------------------------------------------+
|  Service Layer                            |
|  TableService.java                        |
|                                           |
|  - Business logic                         |
|  - Table name validation (regex + exists) |
|  - Primary key discovery (PRAGMA)         |
|  - Query building with parameterization   |
|  - No HTTP concerns                       |
+-------------------+-----------------------+
                    |
                    v  (JdbcTemplate injected)
+-------------------------------------------+
|  DAO Layer (Spring JDBC)                  |
|  JdbcTemplate (auto-configured)           |
|                                           |
|  - queryForList(sql, params)              |
|  - queryForObject(sql, type)              |
|  - update(sql, params)                    |
|  - Parameterized queries (SQL injection   |
|    safe)                                  |
+-------------------+-----------------------+
                    |
                    v
+-------------------------------------------+
|  Configuration Layer                      |
|  DatabaseConfig.java                      |
|  CorsConfig.java                          |
|  DatabaseInitializer.java                 |
|                                           |
|  - @Configuration beans                   |
|  - DataSource setup (SQLite JDBC URL)     |
|  - CORS rules for React frontend          |
|  - Schema + seed execution on startup     |
+-------------------------------------------+

  6 Java files, proper separation of concerns
  Good for: enterprise apps, team development, testability
  Trade-off: more boilerplate, longer startup
```

---

## Technology Stack Summary

| Layer | Python Backend | Java Backend |
|-------|---------------|-------------|
| **Language** | Python 3.11+ | Java 17+ (targeting 21) |
| **Web Framework** | FastAPI (async) | Spring Boot 3.3.5 |
| **HTTP Server** | uvicorn | Embedded Tomcat |
| **Database** | SQLite via aiosqlite | SQLite via org.xerial:sqlite-jdbc |
| **DB Access** | Raw SQL (aiosqlite cursor) | Spring JdbcTemplate |
| **Build Tool** | None (interpreted) | Maven (pom.xml) |
| **Package Manager** | pip (requirements.txt) | Maven (pom.xml dependencies) |
| **Config** | .env file (python-dotenv) | .env + application.properties |
| **CORS** | FastAPI CORSMiddleware | Spring WebMvcConfigurer |
| **JSON** | FastAPI auto-serialization | Spring Jackson (auto) |
| **Process Wrapper** | Maven wrapper (mvnw.cmd) | N/A |
| **Production DB** | PostgreSQL (via asyncpg) | PostgreSQL (via JDBC) |

---

## Why JDBC Instead of JPA?

The Java backend uses **Spring JDBC (JdbcTemplate)** rather than JPA/Hibernate because:

1. **Dynamic table discovery** - Tables are auto-discovered from schema.sql at runtime. JPA requires compile-time entity classes.
2. **Production portability** - The enterprise uses PostgreSQL. JDBC SQL is nearly identical between SQLite and Postgres. JPA's abstraction would hide this portability.
3. **Simplicity** - No entity mapping, no lazy loading, no N+1 queries. Just SQL.
4. **Same schema.sql** - Both Python and Java read the same schema.sql/seed.sql files with the same SQL dialect.
