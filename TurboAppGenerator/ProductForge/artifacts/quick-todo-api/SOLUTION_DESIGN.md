# SOLUTION DESIGN DOCUMENT
## To-Do List API

**Document Version:** 1.0  
**Last Updated:** [Current Date]  
**Status:** Ready for Implementation  
**Owner:** Engineering Leadership

---

## TABLE OF CONTENTS

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Component Design](#component-design)
4. [Data Model](#data-model)
5. [API Contract Overview](#api-contract-overview)
6. [Security Design](#security-design)
7. [Scalability Approach](#scalability-approach)
8. [Deployment Architecture](#deployment-architecture)
9. [Monitoring & Observability Strategy](#monitoring--observability-strategy)
10. [Concurrency & Consistency Model](#concurrency--consistency-model)
11. [Error Handling Strategy](#error-handling-strategy)
12. [Data Retention & Lifecycle](#data-retention--lifecycle)
13. [Design Decisions & Trade-offs](#design-decisions--trade-offs)
14. [Open Questions for Stakeholder Validation](#open-questions-for-stakeholder-validation)

---

## EXECUTIVE SUMMARY

This Solution Design Document translates the Product Requirements Document (PRD) and Technical Requirements Document (TRD) into a comprehensive architectural blueprint for the To-Do List API.

### What We're Building

A **single-service, stateless REST API** that manages task lifecycle operations (create, list, retrieve, update status, delete) with strong consistency guarantees, explicit state machine validation, and support for 1,000 concurrent users at <200ms p95 latency.

### Key Architectural Decisions

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| **Single monolithic service** | Simplicity, operational ease, no distributed coordination overhead | Cannot independently scale read vs. write paths; refactor to microservices if scale demands it |
| **SQLite for persistence** | Zero-configuration, file-based, ACID transactions, suitable for prototype/small scale | Not suitable for multi-instance deployments; migrate to PostgreSQL if HA required |
| **No authentication/authorization** | Per guardrails and PRD scope; tasks are not user-scoped | Suitable for internal/prototype use only; add auth layer if multi-tenant or public-facing |
| **Optimistic locking for concurrency** | Prevents lost writes; clients handle conflicts explicitly | Requires clients to implement retry logic; not suitable for high-contention workloads |
| **Hard-delete only (no soft-delete)** | Simplifies operational burden, eliminates index bloat, clearer semantics | No audit trail of deletions; clients must implement their own if needed |
| **Offset-based pagination** | Simple, predictable, no cursor state required | Inefficient for large offsets; suitable for <10,000 total tasks |
| **Embedded Tomcat + Spring Boot** | Rapid development, built-in validation, transaction management, observability hooks | Requires Java runtime; not suitable for serverless deployments |

### Non-Functional Targets

- **Availability:** 99.5% monthly uptime
- **Latency:** <200ms p95 response time for all endpoints
- **Throughput:** Support 1,000 concurrent users
- **Data Consistency:** Strong consistency with explicit conflict detection
- **Scalability:** Single-instance deployment; horizontal scaling via load balancer + PostgreSQL migration (future)

---

## ARCHITECTURE OVERVIEW

### System Context Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                    Client Applications                            │
│  (Backend integrations, UI frontends, third-party tools)         │
│  - Developers integrating task management                        │
│  - Web/mobile frontends rendering task lists                     │
│  - Workflow automation tools                                     │
└────────────────────┬─────────────────────────────────────────────┘
                     │ HTTP/REST
                     │ (JSON request/response)
                     ▼
┌──────────────────────────────────────────────────────────────────┐
│              To-Do List API (Spring Boot 3.2+)                   │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  REST Controllers (HTTP Entry Points)                      │ │
│  │  - TaskController: handles all task endpoints              │ │
│  │  - HealthController: liveness/readiness probes             │ │
│  └────────────────────────────────────────────────────────────┘ │
│                           │                                      │
│  ┌────────────────────────▼────────────────────────────────────┐ │
│  │  Service Layer (Business Logic)                            │ │
│  │  - TaskService: state machine validation, filtering logic  │ │
│  │  - Concurrency conflict detection (version checking)       │ │
│  │  - Pagination & sorting orchestration                      │ │
│  └────────────────────────────────────────────────────────────┘ │
│                           │                                      │
│  ┌────────────────────────▼────────────────────────────────────┐ │
│  │  Data Access Layer (Repository)                            │ │
│  │  - TaskRepository: CRUD operations via Spring Data JPA     │ │
│  │  - Custom queries for filtering/sorting                    │ │
│  │  - Transaction management (Spring @Transactional)          │ │
│  └────────────────────────────────────────────────────────────┘ │
│                           │                                      │
│  ┌────────────────────────▼────────────────────────────────────┐ │
│  │  Cross-Cutting Concerns                                    │ │
│  │  - Request/Response logging (MDC with request ID)          │ │
│  │  - Rate limiting (per-IP token bucket)                     │ │
│  │  - Error handling & validation (Spring @ControllerAdvice)  │ │
│  │  - Metrics collection (Micrometer)                         │ │
│  └────────────────────────────────────────────────────────────┘ │
└────────────────────┬─────────────────────────────────────────────┘
                     │ JDBC
                     │ (SQL queries)
                     ▼
┌──────────────────────────────────────────────────────────────────┐
│                    SQLite Database                               │
│  (File-based, embedded in application server)                   │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  tasks table                                               │ │
│  │  - id (UUID, primary key)                                  │ │
│  │  - title, description, due_date, priority                 │ │
│  │  - status (NEW, IN_PROGRESS, COMPLETED, ARCHIVED)         │ │
│  │  - version (optimistic locking)                           │ │
│  │  - created_at, updated_at (timestamps)                    │ │
│  │  - Indexes: (status, created_at), (due_date), (created_at)│ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### Service Boundaries

The API is a **single, cohesive service** with no external service dependencies. All business logic is contained within the service:

- **Task Lifecycle Management:** State machine validation, status transitions, conflict detection
- **Data Persistence:** CRUD operations, filtering, sorting, pagination
- **Request Handling:** Validation, error handling, rate limiting, request tracing
- **Observability:** Logging, metrics, health checks

**Why not microservices?** At the stated scale (1,000 concurrent users, simple CRUD operations), a monolithic service is more maintainable and operationally simpler. If future requirements demand multi-tenancy, complex workflows, or separate scaling of read/write paths, the service can be refactored into separate services (e.g., Task Service, Notification Service, Analytics Service).

### Deployment Topology

```
┌─────────────────────────────────────────────────────────────┐
│                    Load Balancer (Optional)                 │
│  (For future HA; v1.0 is single-instance)                  │
└────────────────┬────────────────────────────────────────────┘
                 │
    ┌────────────┴────────────┐
    │                         │
    ▼                         ▼
┌─────────────────────┐  ┌─────────────────────┐
│  API Instance 1     │  │  API Instance 2     │
│  (Spring Boot JAR)  │  │  (Spring Boot JAR)  │
│  Port: 8080         │  │  Port: 8080         │
│  SQLite: local      │  │  SQLite: local      │
└─────────────────────┘  └─────────────────────┘
         │                       │
         └───────────┬───────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │  PostgreSQL (Future)   │
        │  (Multi-instance HA)   │
        └────────────────────────┘
```

**Current State (v1.0):** Single-instance deployment with embedded SQLite. API runs as a standalone Spring Boot JAR on a single server.

**Future State (v2.0+):** If HA is required, migrate to PostgreSQL and deploy multiple API instances behind a load balancer. Each instance remains stateless; all state is in the shared database.

---

## COMPONENT DESIGN

### Component 1: REST Controller Layer

**Responsibility:** Handle HTTP requests, parse input, invoke service layer, format responses, apply cross-cutting concerns (rate limiting, request tracing).

**Key Components:**

- **TaskController**
  - Endpoint: `POST /tasks` — Create a new task
  - Endpoint: `GET /tasks` — List tasks with pagination, filtering, sorting
  - Endpoint: `GET /tasks/{id}` — Retrieve a single task
  - Endpoint: `PATCH /tasks/{id}` — Update task status or fields
  - Endpoint: `DELETE /tasks/{id}` — Delete a task (hard-delete)
  - Responsibilities:
    - Parse and validate HTTP request (headers, body, query parameters)
    - Extract request ID from `X-Request-ID` header (or generate one)
    - Invoke TaskService for business logic
    - Format response with appropriate HTTP status code
    - Include request ID in response headers
    - Handle rate limiting (return 429 if limit exceeded)

- **HealthController**
  - Endpoint: `GET /health/live` — Liveness probe (process alive?)
  - Endpoint: `GET /health/ready` — Readiness probe (database accessible? schema initialized?)
  - Endpoint: `GET /health/startup` — Startup probe (migrations complete?)
  - Responsibilities:
    - Check process health (always 200 if running)
    - Check database connectivity (query a simple SELECT)
    - Check schema initialization (verify tasks table exists)
    - Return 503 if any check fails

**Interface Contracts:**

- **Input:** HTTP request with headers, path parameters, query parameters, JSON body
- **Output:** HTTP response with status code, headers (including `X-Request-ID`), JSON body
- **Error Handling:** Catch exceptions from service layer, translate to appropriate HTTP status codes (400, 409, 429, 500)

**Dependencies:**
- TaskService (injected via Spring @Autowired)
- RateLimiter (injected)
- RequestIdProvider (injected)

---

### Component 2: Service Layer

**Responsibility:** Implement business logic, state machine validation, concurrency conflict detection, filtering/sorting orchestration.

**Key Components:**

- **TaskService**
  - Method: `createTask(CreateTaskRequest)` → `TaskResponse`
    - Validate input (title required, max 255 chars; description max 2000 chars; due_date valid ISO 8601; priority valid enum)
    - Create Task entity with default values (status=NEW, priority=MEDIUM if not provided, version=1)
    - Persist to database
    - Return TaskResponse with generated ID and timestamps
    - Acceptance Criteria: AC1-AC6 from PRD Feature P0.1

  - Method: `listTasks(ListTasksRequest)` → `ListTasksResponse`
    - Validate pagination parameters (limit 1-100, default 20; offset ≥0)
    - Apply filters (status, due_date range, priority)
    - Apply sorting (default: created_at DESC)
    - Query database with pagination
    - Return paginated list with total count
    - Acceptance Criteria: AC1-AC3 from PRD Feature P0.2

  - Method: `getTask(taskId)` → `TaskResponse`
    - Query database by ID
    - Return task if found, throw TaskNotFoundException if not
    - Include version in response (needed for optimistic locking)

  - Method: `updateTaskStatus(taskId, newStatus, version)` → `TaskResponse`
    - Validate state transition (NEW→IN_PROGRESS, IN_PROGRESS→COMPLETED, COMPLETED→ARCHIVED, etc.)
    - Check version matches (optimistic locking)
    - Increment version on successful update
    - Persist to database
    - Return updated task with new version
    - Throw ConflictException if version mismatch (409 Conflict)
    - Throw InvalidStateTransitionException if transition not allowed (400 Bad Request)

  - Method: `deleteTask(taskId)` → void
    - Delete task from database (hard-delete)
    - Return 204 No Content on success
    - Throw TaskNotFoundException if task doesn't exist (404)

  - Method: `validateStateTransition(currentStatus, newStatus)` → boolean
    - Implement state machine rules:
      - NEW → IN_PROGRESS ✓
      - NEW → ARCHIVED ✓
      - IN_PROGRESS → COMPLETED ✓
      - IN_PROGRESS → ARCHIVED ✓
      - COMPLETED → ARCHIVED ✓
      - All other transitions → ✗
    - Return true if valid, false otherwise

**Dependencies:**
- TaskRepository (injected)
- TaskValidator (injected)

---

### Component 3: Data Access Layer (Repository)

**Responsibility:** Perform CRUD operations on tasks table, execute queries for filtering/sorting, manage transactions.

**Key Components:**

- **TaskRepository** (Spring Data JPA)
  - Extends `JpaRepository<Task, UUID>`
  - Method: `findById(UUID)` → `Optional<Task>` (inherited from JpaRepository)
  - Method: `save(Task)` → `Task` (inherited; handles both insert and update)
  - Method: `delete(Task)` → void (inherited; hard-delete)
  - Custom Query: `findAllByStatusAndCreatedAtOrderByCreatedAtDesc(Status, Pageable)` → `Page<Task>`
    - Filters by status, applies pagination, sorts by created_at DESC
  - Custom Query: `findAllByDueDateBetween(LocalDate, LocalDate, Pageable)` → `Page<Task>`
    - Filters by due_date range, applies pagination
  - Custom Query: `findAllByStatusAndDueDateBetweenAndPriority(Status, LocalDate, LocalDate, Priority, Pageable)` → `Page<Task>`
    - Combines multiple filters

**Transaction Management:**
- All write operations (create, update, delete) are wrapped in `@Transactional` at the service layer
- Optimistic locking is enforced via `@Version` annotation on Task entity
- If version mismatch occurs, Hibernate throws `OptimisticLockingFailureException`, which is caught and translated to 409 Conflict

**Dependencies:**
- Task entity (JPA-annotated)
- Spring Data JPA (provided by Spring Boot)

---

### Component 4: Cross-Cutting Concerns

**Responsibility:** Handle rate limiting, request tracing, error handling, metrics collection.

**Key Components:**

- **RateLimiter**
  - Tracks requests per IP address using in-memory token bucket
  - Limits:
    - GET /tasks: 100 requests/minute
    - POST /tasks: 20 requests/minute
    - PATCH /tasks/{id}: 50 requests/minute
    - DELETE /tasks/{id}: 50 requests/minute
  - Returns 429 Too Many Requests if limit exceeded
  - Includes `Retry-After` header with seconds to wait
  - Includes `X-RateLimit-*` headers in all responses

- **RequestIdProvider**
  - Extracts `X-Request-ID` header from incoming request
  - Generates UUID if not provided
  - Stores in MDC (Mapped Diagnostic Context) for logging
  - Includes in all response headers

- **GlobalExceptionHandler** (@ControllerAdvice)
  - Catches exceptions from controllers/services
  - Translates to appropriate HTTP status codes:
    - `ValidationException` → 400 Bad Request
    - `TaskNotFoundException` → 404 Not Found
    - `ConflictException` (version mismatch) → 409 Conflict
    - `RateLimitExceededException` → 429 Too Many Requests
    - `Exception` (unhandled) → 500 Internal Server Error
  - Formats error response with error code, message, request ID
  - Logs error with request ID for debugging

- **MetricsCollector** (Micrometer)
  - Tracks metrics:
    - Request count by endpoint and status code
    - Request latency (p50, p95, p99) by endpoint
    - Task count by status
    - Database query latency
  - Exposes metrics via `/actuator/metrics` endpoint (Spring Boot Actuator)

---

## DATA MODEL

### Entity: Task

**Purpose:** Represents a single task in the system.

**Attributes:**

| Attribute | Type | Constraints | Purpose |
|-----------|------|-----------|---------|
| `id` | UUID | Primary key, auto-generated | Unique identifier for the task |
| `title` | String | Required, 1-255 chars | Task name/summary |
| `description` | String | Optional, max 2000 chars | Detailed task description |
| `due_date` | LocalDate | Optional, ISO 8601 format | When the task is due |
| `priority` | Enum (LOW, MEDIUM, HIGH) | Optional, default MEDIUM | Task priority level |
| `status` | Enum (NEW, IN_PROGRESS, COMPLETED, ARCHIVED) | Required, default NEW | Current state of the task |
| `version` | Long | Required, default 1 | Optimistic locking version |
| `created_at` | Instant | Required, auto-set | Timestamp when task was created |
| `updated_at` | Instant | Required, auto-updated | Timestamp when task was last modified |

**State Machine:**

```
┌─────────┐
│   NEW   │ (Initial state)
└────┬────┘
     │
     ├─────────────────────────┐
     │                         │
     ▼                         ▼
┌──────────────┐         ┌──────────┐
│ IN_PROGRESS  │         │ ARCHIVED │
└────┬─────────┘         └──────────┘
     │
     ├─────────────────────────┐
     │                         │
     ▼                         ▼
┌───────────┐            ┌──────────┐
│ COMPLETED │            │ ARCHIVED │
└───────────┘            └──────────┘
```

**Valid Transitions:**
- NEW → IN_PROGRESS
- NEW → ARCHIVED
- IN_PROGRESS → COMPLETED
- IN_PROGRESS → ARCHIVED
- COMPLETED → ARCHIVED

**Invalid Transitions (rejected with 400 Bad Request):**
- NEW → COMPLETED (must go through IN_PROGRESS)
- COMPLETED → IN_PROGRESS (cannot revert)
- ARCHIVED → * (terminal state)
- Any transition to NEW (cannot revert to initial state)

**Indexes:**
- Primary key: `id`
- Composite: `(status, created_at)` — for filtering by status and sorting by creation time
- Single: `due_date` — for filtering by due date range
- Single: `created_at` — for default sorting

**Rationale for Attributes:**
- `version` enables optimistic locking; prevents lost writes during concurrent updates
- `created_at` and `updated_at` provide audit trail and enable sorting
- `status` enforces explicit state machine; prevents invalid task states
- `priority` allows filtering/sorting by importance (future feature)
- `due_date` enables deadline-based filtering and notifications (future feature)

---

### Data Relationships

**Task → Task:** None (no parent-child relationships in v1.0)

**Task → External Entities:** None (no foreign keys to users, projects, or other entities in v1.0)

**Rationale:** Tasks are standalone entities without user scoping or project associations. This simplifies the data model and aligns with the prototype scope. If multi-tenancy or project hierarchies are required in future versions, add `user_id` and `project_id` foreign keys.

---

### Data Consistency Guarantees

- **Strong Consistency:** All writes are immediately visible to subsequent reads (no eventual consistency)
- **ACID Transactions:** All operations are wrapped in database transactions; no partial updates
- **Optimistic Locking:** Concurrent updates to the same task are detected and rejected (409 Conflict); clients must retry
- **No Cascading Deletes:** Deleting a task does not affect other entities (none exist in v1.0)

---

## API CONTRACT OVERVIEW

### API Design Principles

1. **RESTful:** Resources (tasks) are identified by URIs; operations are HTTP verbs (POST, GET, PATCH, DELETE)
2. **Stateless:** Each request contains all information needed to process it; no session state on server
3. **Explicit Error Handling:** All errors include HTTP status code, error code, and human-readable message
4. **Versioning:** API version is implicit in the URL path (v1.0 is the baseline; future versions would be `/v2/tasks`)
5. **Pagination:** Large result sets are paginated with limit/offset; clients must handle multiple pages
6. **Idempotency:** Create operations support idempotency keys to prevent duplicate task creation on retry

### Endpoint Summary

| Method | Path | Purpose | Status Code |
|--------|------|---------|-------------|
| POST | `/tasks` | Create a new task | 201 Created |
| GET | `/tasks` | List tasks with pagination/filtering | 200 OK |
| GET | `/tasks/{id}` | Retrieve a single task | 200 OK |
| PATCH | `/tasks/{id}` | Update task status or fields | 200 OK |
| DELETE | `/tasks/{id}` | Delete a task | 204 No Content |
| GET | `/health/live` | Liveness probe | 200 OK / 503 Service Unavailable |
| GET | `/health/ready` | Readiness probe | 200 OK / 503 Service Unavailable |

### Request/Response Headers (All Endpoints)

**Request Headers:**
- `X-Request-ID` (optional, UUID): Unique identifier for this request; generated if not provided
- `Content-Type` (required for POST/PATCH): `application/json`
- `Accept` (optional): `application/json` (default)

**Response Headers:**
- `X-Request-ID` (UUID): Echo of request ID or generated value
- `Content-Type`: `application/json`
- `X-RateLimit-Limit` (integer): Maximum requests allowed in the current window
- `X-RateLimit-Remaining` (integer): Requests remaining in the current window
- `X-RateLimit-Reset` (unix timestamp): When the rate limit window resets

### Endpoint Specifications

#### Endpoint 1: Create Task

**Path:** `POST /tasks`

**Purpose:** Create a new task with a title and optional fields.

**Request Body Schema:**
```
{
  "title": "string (required, 1-255 chars)",
  "description": "string (optional, max 2000 chars)",
  "due_date": "string (optional, ISO 8601 date format: YYYY-MM-DD)",
  "priority": "string (optional, enum: LOW | MEDIUM | HIGH, default: MEDIUM)",
  "idempotency_key": "string (optional, UUID for idempotent retries)"
}
```

**Response Body Schema (201 Created):**
```
{
  "id": "uuid",
  "title": "string",
  "description": "string or null",
  "due_date": "string (ISO 8601 date) or null",
  "priority": "string (enum)",
  "status": "NEW",
  "version": 1,
  "created_at": "string (ISO 8601 timestamp)",
  "updated_at": "string (ISO 8601 timestamp)"
}
```

**Error Responses:**
- 400 Bad Request: Missing `title`, `title` exceeds 255 chars, invalid `due_date` format, invalid `priority` enum, `description` exceeds 2000 chars
- 409 Conflict: Duplicate `idempotency_key` with different payload
- 429 Too Many Requests: Rate limit exceeded (20 requests/minute)
- 500 Internal Server Error: Unhandled exception

**Acceptance Criteria (from PRD P0.1):**
- AC1: Accepts `title` and creates task in NEW state
- AC2: Accepts optional `description`, `due_date`, `priority`
- AC3: Rejects missing/invalid `title` with 400 error
- AC4: Returns 201 with task object including auto-generated `id`, `created_at`, `status`
- AC5: Supports idempotency key to prevent duplicate creation on retry
- AC6: Assigns default values: `status=NEW`, `priority=MEDIUM`

---

#### Endpoint 2: List Tasks

**Path:** `GET /tasks`

**Purpose:** Retrieve a paginated list of tasks with optional filtering and sorting.

**Query Parameters:**
```
limit: integer (optional, 1-100, default: 20)
  - Maximum number of tasks to return per page

offset: integer (optional, ≥0, default: 0)
  - Number of tasks to skip (for pagination)

status: string (optional, enum: NEW | IN_PROGRESS | COMPLETED | ARCHIVED)
  - Filter tasks by status; if not provided, return all statuses

priority: string (optional, enum: LOW | MEDIUM | HIGH)
  - Filter tasks by priority; if not provided, return all priorities

due_date_from: string (optional, ISO 8601 date format: YYYY-MM-DD)
  - Filter tasks with due_date >= this date

due_date_to: string (optional, ISO 8601 date format: YYYY-MM-DD)
  - Filter tasks with due_date <= this date

sort_by: string (optional, enum: created_at | due_date | priority, default: created_at)
  - Field to sort by

sort_order: string (optional, enum: ASC | DESC, default: DESC)
  - Sort order (ascending or descending)
```

**Response Body Schema (200 OK):**
```
{
  "data": [
    {
      "id": "uuid",
      "title": "string",
      "description": "string or null",
      "due_date": "string (ISO 8601 date) or null",
      "priority": "string (enum)",
      "status": "string (enum)",
      "version": integer,
      "created_at": "string (ISO 8601 timestamp)",
      "updated_at": "string (ISO 8601 timestamp)"
    },
    ...
  ],
  "pagination": {
    "limit": integer,
    "offset": integer,
    "total": integer,
    "has_more": boolean
  }
}
```

**Error Responses:**
- 400 Bad Request: Invalid `limit` (>100 or <1), invalid `offset` (<0), invalid `status`/`priority` enum, invalid date format
- 429 Too Many Requests: Rate limit exceeded (100 requests/minute)
- 500 Internal Server Error: Unhandled exception

**Acceptance Criteria (from PRD P0.2):**
- AC1: Supports limit/offset pagination; default limit=20, max limit=100
- AC2: Supports filtering by `status`
- AC3: Supports filtering by `due_date` range
- AC4: Supports sorting by `created_at`, `due_date`, `priority`
- AC5: Returns paginated response with total count and `has_more` flag
- AC6: Includes `version` in list responses (needed for optimistic locking)

---

#### Endpoint 3: Get Task

**Path:** `GET /tasks/{id}`

**Purpose:** Retrieve a single task by ID.

**Path Parameters:**
```
id: uuid (required)
  - Task ID to retrieve
```

**Response Body Schema (200 OK):**
```
{
  "id": "uuid",
  "title": "string",
  "description": "string or null",
  "due_date": "string (ISO 8601 date) or null",
  "priority": "string (enum)",
  "status": "string (enum)",
  "version": integer,
  "created_at": "string (ISO 8601 timestamp)",
  "updated_at": "string (ISO 8601 timestamp)"
}
```

**Error Responses:**
- 404 Not Found: Task with given `id` does not exist
- 429 Too Many Requests: Rate limit exceeded (100 requests/minute)
- 500 Internal Server Error: Unhandled exception

---

#### Endpoint 4: Update Task Status

**Path:** `PATCH /tasks/{id}`

**Purpose:** Update task status or other fields (title, description, due_date, priority).

**Path Parameters:**
```
id: uuid (required)
  - Task ID to update
```

**Request Body Schema:**
```
{
  "status": "string (optional, enum: NEW | IN_PROGRESS | COMPLETED | ARCHIVED)",
  "title": "string (optional, 1-255 chars)",
  "description": "string (optional, max 2000 chars, or null to clear)",
  "due_date": "string (optional, ISO 8601 date format, or null to clear)",
  "priority": "string (optional, enum: LOW | MEDIUM | HIGH)",
  "version": integer (required, current version of the task)
}
```

**Response Body Schema (200 OK):**
```
{
  "id": "uuid",
  "title": "string",
  "description": "string or null",
  "due_date": "string (ISO 8601 date) or null",
  "priority": "string (enum)",
  "status": "string (enum)",
  "version": integer (incremented),
  "created_at": "string (ISO 8601 timestamp)",
  "updated_at": "string (ISO 8601 timestamp)"
}
```

**Error Responses:**
- 400 Bad Request: Invalid `status` enum, invalid state transition (e.g., COMPLETED → IN_PROGRESS), invalid `title` length, invalid date format
- 404 Not Found: Task with given `id` does not exist
- 409 Conflict: `version` mismatch (optimistic locking failure); client must fetch latest version and retry
- 429 Too Many Requests: Rate limit exceeded (50 requests/minute)
- 500 Internal Server Error: Unhandled exception

**Concurrency Handling:**
- Client must include current `version` in request
- If `version` does not match database version, return 409 Conflict
- Client must fetch latest task (GET /tasks/{id}), extract new version, and retry PATCH with updated version
- This prevents lost writes during concurrent updates

---

#### Endpoint 5: Delete Task

**Path:** `DELETE /tasks/{id}`

**Purpose:** Delete a task (hard-delete; permanent removal).

**Path Parameters:**
```
id: uuid (required)
  - Task ID to delete
```

**Response (204 No Content):**
- No response body; task is permanently deleted

**Error Responses:**
- 404 Not Found: Task with given `id` does not exist
- 429 Too Many Requests: Rate limit exceeded (50 requests/minute)
- 500 Internal Server Error: Unhandled exception

**Important:** Deletion is permanent and cannot be undone. Clients should implement their own audit trail if needed.

---

#### Endpoint 6: Liveness Probe

**Path:** `GET /health/live`

**Purpose:** Check if the API process is running (used by container orchestration for restart decisions).

**Response (200 OK):**
```
{
  "status": "UP"
}
```

**Response (503 Service Unavailable):**
```
{
  "status": "DOWN",
  "reason": "Process deadlocked or crashed"
}
```

---

#### Endpoint 7: Readiness Probe

**Path:** `GET /health/ready`

**Purpose:** Check if the API is ready to serve requests (database accessible, schema initialized).

**Response (200 OK):**
```
{
  "status": "UP",
  "components": {
    "database": {
      "status": "UP"
    },
    "schema": {
      "status": "UP"
    }
  }
}
```

**Response (503 Service Unavailable):**
```
{
  "status": "DOWN",
  "components": {
    "database": {
      "status": "DOWN",
      "reason": "Cannot connect to SQLite database"
    },
    "schema": {
      "status": "DOWN",
      "reason": "tasks table does not exist"
    }
  }
}
```

---

## SECURITY DESIGN

### Authentication & Authorization

**Decision:** No authentication or authorization in v1.0.

**Rationale:**
- Per guardrails, authentication is not required unless explicitly stated in PRD
- PRD does not mention user accounts, login, or access control
- Tasks are not user-scoped; all tasks are visible to all clients
- Suitable for internal/prototype use; add auth layer if multi-tenant or public-facing

**Future Consideration:** If multi-tenancy is required, add:
- API key authentication (header-based)
- User/tenant scoping (add `user_id` and `tenant_id` to tasks table)
- Authorization checks (ensure user can only access their own tasks)

### Data Protection

**In Transit:**
- Require HTTPS (TLS 1.2+) for all API endpoints
- Enforce HSTS (HTTP Strict-Transport-Security) header to prevent downgrade attacks
- No sensitive data in URLs (use request body instead)

**At Rest:**
- SQLite database file stored on secure filesystem with restricted permissions (readable only by application user)
- No encryption of database file in v1.0 (suitable for internal use; add encryption if handling sensitive data)
- Backups stored securely with restricted access

**Logging & Monitoring:**
- Do not log sensitive data (task content is not sensitive; no passwords or API keys in logs)
- Include request ID in all logs for traceability
- Sanitize error messages (do not expose internal implementation details)

### Rate Limiting

**Purpose:** Prevent abuse and ensure fair resource allocation.

**Strategy:** Per-IP token bucket rate limiting (in-memory, no distributed state).

**Limits:**
- GET /tasks: 100 requests/minute per IP
- POST /tasks: 20 requests/minute per IP
- PATCH /tasks/{id}: 50 requests/minute per IP
- DELETE /tasks/{id}: 50 requests/minute per IP

**Implementation:**
- Track requests per IP in memory using a token bucket algorithm
- Decrement bucket on each request; refill at fixed rate
- Return 429 Too Many Requests if bucket is empty
- Include `X-RateLimit-*` headers in all responses

**Limitations:**
- In-memory tracking does not persist across server restarts
- In multi-instance deployments, each instance has its own rate limit bucket (not shared)
- If stricter rate limiting is needed, migrate to Redis-backed rate limiting

### Input Validation

**All Endpoints:**
- Validate request body against schema (Spring @Valid annotation)
- Reject requests with missing required fields (400 Bad Request)
- Reject requests with invalid data types (400 Bad Request)
- Reject requests with out-of-range values (400 Bad Request)

**Specific Validations:**
- `title`: Required, 1-255 characters, non-null
- `description`: Optional, max 2000 characters
- `due_date`: Optional, valid ISO 8601 date format (YYYY-MM-DD)
- `priority`: Optional, enum (LOW, MEDIUM, HIGH)
- `status`: Optional, enum (NEW, IN_PROGRESS, COMPLETED, ARCHIVED)
- `version`: Required for PATCH, must be a positive integer

**Error Response (400 Bad Request):**
```
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Validation failed",
    "details": [
      {
        "field": "title",
        "message": "must not be blank"
      },
      {
        "field": "due_date",
        "message": "must be a valid ISO 8601 date"
      }
    ]
  },
  "request_id": "uuid"
}
```

---

## SCALABILITY APPROACH

### Horizontal Scaling (Future)

**Current State (v1.0):** Single-instance deployment with embedded SQLite.

**Scaling Bottleneck:** SQLite does not support concurrent writes from multiple processes. To scale horizontally, migrate to PostgreSQL.

**Future Architecture (v2.0+):**
```
┌──────────────────────────────────────┐
│         Load Balancer                │
│  (Round-robin or least-connections)  │
└────────────────┬─────────────────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
    ▼            ▼            ▼
┌────────┐  ┌────────┐  ┌────────┐
│ API 1  │  │ API 2  │  │ API 3  │
│ (8080) │  │ (8080) │  │ (8080) │
└────────┘  └────────┘  └────────┘
    │            │            │
    └────────────┼────────────┘
                 │
                 ▼
        ┌─────────────────┐
        │  PostgreSQL     │
        │  (Shared DB)    │
        └─────────────────┘
```

**Migration Steps:**
1. Add PostgreSQL JDBC driver to classpath
2. Update Spring Data JPA configuration to use PostgreSQL
3. Run Flyway migrations against PostgreSQL
4. Deploy multiple API instances behind load balancer
5. Each instance remains stateless; all state is in PostgreSQL

### Vertical Scaling (Current)

**Memory:** Spring Boot + SQLite typically requires 256-512 MB heap. Increase if needed.

**CPU:** Single-threaded SQLite queries are CPU-bound. Increase CPU cores if needed.

**Disk:** SQLite database file grows with task count. Monitor disk usage; archive old tasks if needed.

### Caching Strategy

**Current State (v1.0):** No caching; all queries hit SQLite.

**Future Optimization:** If p95 latency exceeds 200ms, add Redis caching for frequently accessed queries:
- Cache list queries by (status, priority, sort_order) with 5-minute TTL
- Invalidate cache on create/update/delete operations
- Use cache-aside pattern (check cache, miss → query DB, populate cache)

### Database Indexing

**Indexes on tasks table:**
- Primary key: `id` (auto-created by database)
- Composite: `(status, created_at DESC)` — for filtering by status and sorting by creation time
- Single: `due_date` — for filtering by due date range
- Single: `created_at DESC` — for default sorting

**Rationale:**
- Composite index on (status, created_at) covers the most common query pattern (list tasks by status, sorted by creation time)
- Single indexes on due_date and created_at support other query patterns
- Indexes are created via Flyway migrations; no manual DDL

### Query Optimization

**Pagination:** Use limit/offset to avoid loading all tasks into memory. Default limit=20, max limit=100.

**Filtering:** Apply filters in WHERE clause (database-side), not in application code.

**Sorting:** Use database ORDER BY, not in-memory sorting.

**Lazy Loading:** Avoid N+1 queries; use Spring Data JPA projections if only a subset of fields is needed.

---

## DEPLOYMENT ARCHITECTURE

### Deployment Topology

**v1.0 (Single-Instance):**
```
┌─────────────────────────────────────┐
│         Application Server          │
│  (Linux VM, Docker container, etc.) │
│                                     │
│  ┌─────────────────────────────────┐│
│  │  Spring Boot JAR                ││
│  │  - Port: 8080                   ││
│  │  - Heap: 512 MB                 ││
│  │  - Threads: 200 (Tomcat)        ││
│  └─────────────────────────────────┘│
│                                     │
│  ┌─────────────────────────────────┐│
│  │  SQLite Database                ││
│  │  - File: /data/tasks.db         ││
│  │  - Size: ~100 MB (10k tasks)    ││
│  └─────────────────────────────────┘│
└─────────────────────────────────────┘
```

**Deployment Options:**

1. **Standalone JAR on Linux VM**
   - Build: `mvn clean package` → `target/todo-api-1.0.0.jar`
   - Run: `java -Xmx512m -jar todo-api-1.0.0.jar`
   - Database: `/data/tasks.db` (persistent volume)
   - Logs: `/var/log/todo-api/app.log`

2. **Docker Container**
   - Dockerfile: Multi-stage build (Maven build stage, runtime stage)
   - Image: `todo-api:1.0.0`
   - Run: `docker run -p 8080:8080 -v /data:/data todo-api:1.0.0`
   - Database: `/data/tasks.db` (mounted volume)

3. **Kubernetes Pod** (Future)
   - Deployment: 1 replica (single-instance)
   - Service: ClusterIP or LoadBalancer
   - PersistentVolume: For SQLite database file
   - Liveness probe: `GET /health/live`
   - Readiness probe: `GET /health/ready`

### Configuration Management

**Environment Variables:**
```
SPRING_DATASOURCE_URL=jdbc:sqlite:/data/tasks.db
SPRING_JPA_HIBERNATE_DDL_AUTO=validate
SPRING_JPA_SHOW_SQL=false
LOGGING_LEVEL_ROOT=INFO
LOGGING_LEVEL_COM_EXAMPLE_TODOAPI=DEBUG
SERVER_PORT=8080
SERVER_SERVLET_CONTEXT_PATH=/
```

**Application Properties (application.yml):**
```
spring:
  datasource:
    url: jdbc:sqlite:${SPRING_DATASOURCE_URL}
    driver-class-name: org.sqlite.JDBC
  jpa:
    hibernate:
      ddl-auto: validate
    show-sql: false
  flyway:
    enabled: true
    locations: classpath:db/migration
    baseline-on-migrate: true

server:
  port: 8080
  servlet:
    context-path: /

logging:
  level:
    root: INFO
    com.example.todoapi: DEBUG
  pattern:
    console: "%d{ISO8601} [%thread] %-5level %logger{36} - %msg%n"
    file: "%d{ISO8601} [%thread] %-5level %logger{36} - %msg%n"
  file:
    name: /var/log/todo-api/app.log
    max-size: 10MB
    max-history: 10
```

### Database Initialization

**Flyway Migrations:**
- Location: `src/main/resources/db/migration/`
- Naming: `V1__initial_schema.sql`, `V2__add_indexes.sql`, etc.
- Execution: Automatic on application startup (Spring Boot + Flyway integration)
- Baseline: If database already exists, Flyway validates schema matches migrations

**Initial Schema (V1__initial_schema.sql):**
```
CREATE TABLE tasks (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT,
  due_date DATE,
  priority TEXT DEFAULT 'MEDIUM',
  status TEXT DEFAULT 'NEW',
  version INTEGER DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX idx_tasks_status_created_at ON tasks(status, created_at DESC);
CREATE INDEX idx_tasks_due_date ON tasks(due_date);
CREATE INDEX idx_tasks_created_at ON tasks(created_at DESC);
```

### Backup & Recovery

**Backup Strategy:**
- Daily backup of SQLite database file to secure storage (S3, NFS, etc.)
- Backup includes full database file + transaction log
- Retention: 30 days of daily backups

**Recovery Procedure:**
1. Stop API application
2. Restore database file from backup
3. Verify schema integrity (Flyway baseline check)
4. Restart API application
5. Verify health checks pass

**Point-in-Time Recovery:**
- SQLite supports WAL (Write-Ahead Logging) mode for better crash recovery
- Enable WAL in Flyway migration: `PRAGMA journal_mode=WAL;`

---

## MONITORING & OBSERVABILITY STRATEGY

### Logging Strategy

**Log Levels:**
- DEBUG: Detailed information for debugging (SQL queries, request/response bodies)
- INFO: General informational messages (application startup, request summary)
- WARN: Warning messages (deprecated API usage, performance issues)
- ERROR: Error messages (exceptions, failed operations)

**Log Format:**
```
2024-01-15T10:30:45.123Z [http-nio-8080-exec-1] INFO  com.example.todoapi.controller.TaskController - [req-id: 550e8400-e29b-41d4-a716-446655440000] POST /tasks - status: 201, latency: 45ms
```

**Log Destinations:**
- Console: For local development and container logs
- File: `/var/log/todo-api/app.log` with rotation (10 MB per file, 10 files retained)
- Structured Logging: JSON format for production (enables log aggregation)

**Request Tracing:**
- Every request includes unique `X-Request-ID` header (UUID)
- Request ID is stored in MDC (Mapped Diagnostic Context)
- All log messages include request ID for correlation
- Request ID is returned in response headers

**Example Log Entry:**
```
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "logger": "com.example.todoapi.controller.TaskController",
  "message": "POST /tasks",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "method": "POST",
  "path": "/tasks",
  "status": 201,
  "latency_ms": 45,
  "user_agent": "curl/7.68.0"
}
```

### Metrics Collection

**Metrics Framework:** Micrometer (Spring Boot Actuator)

**Metrics Collected:**

| Metric | Type | Dimensions | Purpose |
|--------|------|-----------|---------|
| `http.requests.total` | Counter | endpoint, method, status | Total HTTP requests by endpoint and status |
| `http.requests.duration` | Timer | endpoint, method, status | Request latency (p50, p95, p99) by endpoint |
| `tasks.created.total` | Counter | — | Total tasks created |
| `tasks.completed.total` | Counter | — | Total tasks completed |
| `tasks.deleted.total` | Counter | — | Total tasks deleted |
| `tasks.by_status` | Gauge | status | Current task count by status |
| `db.query.duration` | Timer | query_type | Database query latency |
| `rate_limit.exceeded.total` | Counter | endpoint | Total rate limit violations |

**Metrics Endpoint:**
- `GET /actuator/metrics` — List all available metrics
- `GET /actuator/metrics/{metric_name}` — Get specific metric details

**Example Metrics Response:**
```
{
  "name": "http.requests.duration",
  "description": "HTTP request latency",
  "baseUnit": "milliseconds",
  "measurements": [
    {
      "statistic": "COUNT",
      "value": 1000
    },
    {
      "statistic": "TOTAL",
      "value": 45000
    },
    {
      "statistic": "MAX",
      "value": 250
    }
  ],
  "availableTags": [
    {
      "tag": "endpoint",
      "values": ["POST /tasks", "GET /tasks", "PATCH /tasks/{id}"]
    },
    {
      "tag": "status",
      "values": ["201", "200", "400", "409"]
    }
  ]
}
```

### Health Checks

**Liveness Probe (GET /health/live):**
- Checks if process is running
- Returns 200 OK if healthy, 503 Service Unavailable if not
- Used by container orchestration to restart unhealthy instances

**Readiness Probe (GET /health/ready):**
- Checks if API is ready to serve requests
- Verifies database connectivity
- Verifies schema initialization (tasks table exists)
- Returns 200 OK if ready, 503 Service Unavailable if not
- Used by load balancer to route traffic only to ready instances

**Startup Probe (GET /health/startup):**
- Checks if application startup is complete
- Verifies Flyway migrations have run
- Returns 200 OK if startup complete, 503 Service Unavailable if still starting
- Used by container orchestration to wait for startup before running liveness/readiness probes

### Alerting Strategy

**Alert Conditions:**

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| API Down | Liveness probe fails for 2 minutes | Critical | Page on-call engineer; restart container |
| Database Unavailable | Readiness probe fails for 5 minutes | Critical | Page on-call engineer; check database logs |
| High Error Rate | 5xx errors > 1% of requests | High | Page on-call engineer; check application logs |
| High Latency | p95 latency > 500ms for 10 minutes | Medium | Monitor; investigate slow queries |
| Rate Limit Exceeded | >100 rate limit violations in 5 minutes | Low | Log and monitor; may indicate abuse |
| Disk Space Low | <10% free space on database volume | High | Page on-call engineer; archive old tasks |

**Alert Delivery:**
- Email: For low/medium severity alerts
- PagerDuty: For high/critical severity alerts
- Slack: For all alerts (informational channel)

### Observability Dashboard

**Key Metrics to Display:**
- API uptime (% of time healthy)
- Request rate (requests/second by endpoint)
- Error rate (% of requests returning 5xx)
- Latency (p50, p95, p99 by endpoint)
- Task count by status (pie chart)
- Database size (MB)
- Rate limit violations (count)

**Tools:** Grafana + Prometheus (for metrics visualization)

---

## CONCURRENCY & CONSISTENCY MODEL

### Optimistic Locking Strategy

**Problem:** Multiple clients may attempt to update the same task simultaneously, leading to lost writes.

**Solution:** Optimistic locking with version field.

**Mechanism:**
1. Client fetches task: `GET /tasks/{id}` → receives `version=1`
2. Client modifies task locally
3. Client sends update: `PATCH /tasks/{id}` with `version=1` in request body
4. Server checks: Does database version match request version?
   - **Yes:** Update task, increment version to 2, return 200 OK with new version
   - **No:** Return 409 Conflict; client must fetch latest version and retry

**Example Conflict Scenario:**
```
Client A                          Server                          Client B
GET /tasks/123                    ────────────────────────────→   
                                  ← version=1, status=NEW
                                                                   GET /tasks/123
                                                                   ← version=1, status=NEW
PATCH /tasks/123                  ────────────────────────────→
  status=IN_PROGRESS              Update: version 1→2
  version=1                        ← 200 OK, version=2
                                                                   PATCH /tasks/123
                                                                     status=COMPLETED
                                                                     version=1
                                                                   ← 409 Conflict
                                                                   GET /tasks/123
                                                                   ← version=2, status=IN_PROGRESS
                                                                   PATCH /tasks/123
                                                                     status=COMPLETED
                                                                     version=2
                                                                   ← 200 OK, version=3
```

**Client Retry Logic:**
```
1. Attempt PATCH with current version
2. If 409 Conflict:
   a. Fetch latest task (GET /tasks/{id})
   b. Extract new version
   c. Reapply changes to latest version
   d. Retry PATCH with new version
3. If still 409 after 3 retries, return error to user
```

**Advantages:**
- No server-side locking; high concurrency
- Detects conflicts explicitly; clients can handle them
- Simple to implement; no distributed lock manager needed

**Disadvantages:**
- Requires clients to implement retry logic
- High-contention workloads may experience many retries
- Not suitable for real-time collaborative editing

### Consistency Guarantees

**Strong Consistency:** All writes are immediately visible to subsequent reads.
- After `PATCH /tasks/{id}` returns 200 OK, subsequent `GET /tasks/{id}` returns updated data
- After `POST /tasks` returns 201 Created, subsequent `GET /tasks` includes new task

**ACID Transactions:** All operations are wrapped in database transactions.
- Atomicity: Either entire operation succeeds or fails; no partial updates
- Consistency: Database constraints are enforced (e.g., status must be valid enum)
- Isolation: Concurrent transactions do not interfere with each other
- Durability: Committed data is persisted to disk

**No Eventual Consistency:** This is not a distributed system; all data is in a single SQLite database.

---

## ERROR HANDLING STRATEGY

### Error Response Format

**Standard Error Response:**
```
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      "field": "value",
      ...
    }
  },
  "request_id": "uuid"
}
```

**Example: Validation Error (400 Bad Request)**
```
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {
        "field": "title",
        "message": "must not be blank"
      },
      {
        "field": "due_date",
        "message": "must be a valid ISO 8601 date"
      }
    ]
  },
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Example: Conflict Error (409 Conflict)**
```
{
  "error": {
    "code": "CONFLICT",
    "message": "Task version mismatch; concurrent update detected",
    "details": {
      "current_version": 2,
      "requested_version": 1
    }
  },
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### HTTP Status Codes

| Status | Meaning | When to Use |
|--------|---------|------------|
| 200 OK | Request succeeded | GET, PATCH successful |
| 201 Created | Resource created | POST successful |
| 204 No Content | Request succeeded, no body | DELETE successful |
| 400 Bad Request | Invalid request | Validation error, invalid enum, missing required field |
| 404 Not Found | Resource not found | Task ID does not exist |
| 409 Conflict | Request conflicts with current state | Version mismatch (optimistic locking), invalid state transition |
| 429 Too Many Requests | Rate limit exceeded | Too many requests from same IP |
| 500 Internal Server Error | Server error | Unhandled exception, database error |
| 503 Service Unavailable | Service temporarily unavailable | Database down, schema not initialized |

### Error Codes

| Code | HTTP Status | Meaning | Retry? |
|------|-------------|---------|--------|
| VALIDATION_ERROR | 400 | Request validation failed | No; fix request |
| INVALID_STATE_TRANSITION | 400 | Task status transition not allowed | No; check state machine rules |
| NOT_FOUND | 404 | Task does not exist | No; verify task ID |
| CONFLICT | 409 | Version mismatch (optimistic locking) | Yes; fetch latest and retry |
| RATE_LIMIT_EXCEEDED | 429 | Too many requests | Yes; wait and retry |
| INTERNAL_ERROR | 500 | Unhandled exception | Yes; exponential backoff |
| SERVICE_UNAVAILABLE | 503 | Database or schema not available | Yes; wait and retry |

### Retry Strategy

**Idempotent Operations (GET, DELETE):**
- Safe to retry without side effects
- Retry on 429, 500, 503
- Use exponential backoff: 1s, 2s, 4s, 8s (max 3 retries)

**Non-Idempotent Operations (POST, PATCH):**
- POST: Use idempotency key to prevent duplicate task creation on retry
- PATCH: Use optimistic locking (version field) to detect conflicts
- Retry on 429, 500, 503, 409 (for PATCH)
- Use exponential backoff: 1s, 2s, 4s, 8s (max 3 retries)

**Example Retry Logic (Pseudocode):**
```
function retryWithBackoff(operation, maxRetries=3) {
  for attempt in 1..maxRetries {
    try {
      return operation()
    } catch (error) {
      if (error.status in [429, 500, 503]) {
        waitTime = 2^(attempt-1) * 1000  // exponential backoff
        sleep(waitTime)
        continue
      } else if (error.status == 409 && operation == PATCH) {
        // Optimistic locking conflict
        task = GET /tasks/{id}
        operation.version = task.version
        continue
      } else {
        throw error
      }
    }
  }
  throw "Max retries exceeded"
}
```

---

## DATA RETENTION & LIFECYCLE

### Task Lifecycle

```
Created (NEW)
    │
    ├─→ In Progress (IN_PROGRESS)
    │       │
    │       ├─→ Completed (COMPLETED)
    │       │       │
    │       │       └─→ Archived (ARCHIVED)
    │       │
    │       └─→ Archived (ARCHIVED)
    │
    └─→ Archived (ARCHIVED)

Archived (ARCHIVED) → [Permanent Deletion after 30 days]
```

### Retention Policy

**Active Tasks (NEW, IN_PROGRESS, COMPLETED):**
- Retained indefinitely
- Visible in list queries
- Can be updated or deleted by client

**Archived Tasks (ARCHIVED):**
- Retained for 30 days after archiving
- Visible in list queries (if client filters by status=ARCHIVED)
- Cannot be updated; can only be deleted

**Deleted Tasks:**
- Hard-deleted immediately (no soft-delete)
- Permanently removed from database
- Cannot be recovered

**Rationale:**
- Hard-delete simplifies operational burden (no purge job needed)
- Clients manage their own audit trail if needed
- If retention is required in future, add soft-delete with scheduled purge job

### Data Purge Strategy

**Current (v1.0):** No automatic purge; tasks are retained indefinitely.

**Future (v2.0+):** If retention policy is required:
1. Add `archived_at` timestamp to tasks table
2. Implement scheduled Spring `@Scheduled` task to run nightly
3. Query: `DELETE FROM tasks WHERE archived_at < NOW() - INTERVAL 30 DAY`
4. Log purge results (count of deleted tasks)
5. Alert if purge fails

---

## DESIGN DECISIONS & TRADE-OFFS

### Decision 1: Single Monolithic Service vs. Microservices

**Decision:** Single monolithic service.

**Rationale:**
- Scale is small (1,000 concurrent users, simple CRUD operations)
- No need for independent scaling of read vs. write paths
- Simpler deployment and operational burden
- Easier to debug and maintain

**Trade-off:**
- Cannot independently scale read vs. write paths
- Cannot use different technology stacks for different components
- If scale grows significantly, refactor to microservices

**Migration Path:**
- If future requirements demand multi-tenancy, add Task Service + Notification Service + Analytics Service
- Use event-driven architecture (Kafka) for inter-service communication

---

### Decision 2: SQLite vs. PostgreSQL

**Decision:** SQLite for v1.0; migrate to PostgreSQL for v2.0+ if HA required.

**Rationale:**
- SQLite is zero-configuration, file-based, suitable for prototype
- No separate database server to manage
- ACID transactions and strong consistency
- Sufficient for <10,000 tasks and <1,000 concurrent users

**Trade-off:**
- SQLite does not support concurrent writes from multiple processes
- Not suitable for multi-instance deployments
- Limited to single server; no replication or failover

**Migration Path:**
- Add PostgreSQL JDBC driver to classpath
- Update Spring Data JPA configuration
- Run Flyway migrations against PostgreSQL
- Deploy multiple API instances behind load balancer

---

### Decision 3: Hard-Delete vs. Soft-Delete

**Decision:** Hard-delete only; no soft-delete.

**Rationale:**
- Simplifies operational burden (no purge job needed)
- Eliminates index bloat from soft-deleted rows
- Clearer semantics (deleted = gone)
- Clients can implement their own audit trail if needed

**Trade-off:**
- No audit trail of deletions
- Cannot recover deleted tasks
- Compliance requirements (e.g., GDPR right to be forgotten) are satisfied immediately

**Alternative:** If retention is required, implement soft-delete with scheduled purge job (see Data Retention & Lifecycle section).

---

### Decision 4: Optimistic Locking vs. Pessimistic Locking

**Decision:** Optimistic locking with version field.

**Rationale:**
- No server-side locks; high concurrency
- Detects conflicts explicitly; clients can handle them
- Simple to implement; no distributed lock manager needed
- Suitable for low-contention workloads

**Trade-off:**
- Requires clients to implement retry logic
- High-contention workloads may experience many retries
- Not suitable for real-time collaborative editing

**Alternative:** If high-contention is a problem, use pessimistic locking (SELECT FOR UPDATE) or distributed locks (Redis).

---

### Decision 5: Offset-Based vs. Cursor-Based Pagination

**Decision:** Offset-based pagination with limit/offset.

**Rationale:**
- Simple, predictable, no cursor state required
- Clients can jump to arbitrary page
- Suitable for <10,000 total tasks

**Trade-off:**
- Inefficient for large offsets (e.g., offset=1,000,000)
- If results are sorted by creation time and new items are added, pagination may skip or duplicate items

**Alternative:** If pagination efficiency is a problem, use cursor-based pagination (keyset pagination) with `created_at` as cursor.

---

### Decision 6: No Authentication/Authorization

**Decision:** No auth in v1.0; add in v2.0+ if multi-tenant.

**Rationale:**
- Per guardrails, auth is not required unless explicitly stated in PRD
- PRD does not mention user accounts or access control
- Tasks are not user-scoped; all tasks visible to all clients
- Suitable for internal/prototype use

**Trade-off:**
- Not suitable for multi-tenant or public-facing deployments
- No user isolation; all clients see all tasks
- No audit trail of who created/modified tasks

**Migration Path:**
- Add API key authentication (header-based)
- Add user/tenant scoping (add `user_id` and `tenant_id` to tasks table)
- Add authorization checks (ensure user can only access their own tasks)

---

### Decision 7: Embedded Tomcat vs. Standalone Server

**Decision:** Embedded Tomcat (via Spring Boot).

**Rationale:**
- Simplifies deployment (single JAR file)
- No separate server installation/configuration- No separate server installation/configuration
- Spring Boot handles server lifecycle (startup, shutdown, graceful termination)

**Trade-off:**
- Requires Java runtime on deployment server
- Not suitable for serverless deployments (AWS Lambda, Google Cloud Functions)
- Slightly higher memory footprint than lightweight frameworks

**Alternative:** If serverless is required, refactor to AWS Lambda + API Gateway + DynamoDB.

---

### Decision 8: In-Memory Rate Limiting vs. Redis-Backed

**Decision:** In-memory rate limiting for v1.0; migrate to Redis for v2.0+ if multi-instance.

**Rationale:**
- Simple to implement; no external dependency
- Sufficient for single-instance deployment
- No network latency overhead

**Trade-off:**
- Rate limit state does not persist across server restarts
- In multi-instance deployments, each instance has its own rate limit bucket (not shared)
- Clients on different instances may exceed global rate limit

**Migration Path:**
- Add Redis JDBC client to classpath
- Implement rate limiting using Redis INCR + EXPIRE commands
- Rate limit state is shared across all instances

---

### Decision 9: Flyway for Database Migrations

**Decision:** Flyway for version-controlled schema migrations.

**Rationale:**
- Automatic schema initialization on startup
- Version-controlled migrations (tracked in Git)
- Rollback capability (via Flyway undo)
- Ensures schema consistency across deployments

**Trade-off:**
- Adds complexity to deployment process
- Requires careful migration design to avoid downtime
- Undo migrations must be manually written

**Alternative:** Manual SQL scripts or Liquibase (more complex but more flexible).

---

## OPEN QUESTIONS FOR STAKEHOLDER VALIDATION

### Product Questions

1. **Soft-Delete Retention:** The TRD mentions 30-day retention for deleted tasks, but this creates operational burden (scheduled purge job). Is 30-day retention a hard requirement, or can we hard-delete immediately?

2. **Task Ownership:** Are tasks user-scoped (each user sees only their own tasks), or are all tasks visible to all clients? This affects authentication/authorization design.

3. **Task Hierarchies:** Should tasks support parent-child relationships (subtasks)? This affects data model design.

4. **Custom Workflows:** Should the API support custom task states beyond (NEW, IN_PROGRESS, COMPLETED, ARCHIVED)? This affects state machine design.

5. **Notifications:** Should the API send notifications when tasks are created, completed, or overdue? This affects architecture (may require message queue).

6. **Audit Trail:** Should the API maintain an audit trail of who created/modified/deleted tasks? This affects data model (add user_id, action, timestamp).

7. **Bulk Operations:** Should the API support bulk create/update/delete operations? This affects API design and performance.

8. **Search:** Should the API support full-text search on task titles/descriptions? This affects indexing strategy.

---

### Technical Questions

1. **Multi-Instance Deployment:** Is high availability (HA) required for v1.0, or is single-instance acceptable? This affects database choice (SQLite vs. PostgreSQL).

2. **Data Backup:** What is the backup/recovery SLA? Daily backups? Point-in-time recovery? This affects backup strategy.

3. **Compliance:** Are there compliance requirements (GDPR, HIPAA, SOC 2)? This affects data protection and audit trail design.

4. **Performance Targets:** Are the latency targets (<200ms p95) achievable with SQLite, or should we use PostgreSQL from the start?

5. **Scalability Timeline:** When do we expect to exceed 1,000 concurrent users? This affects migration planning (SQLite → PostgreSQL).

6. **Monitoring:** Should we integrate with existing monitoring/alerting systems (Datadog, New Relic, Prometheus)? This affects observability design.

7. **API Versioning:** Should we support multiple API versions (v1, v2) for backward compatibility? This affects API design.

8. **Rate Limiting:** Are the proposed rate limits (20 POST/min, 100 GET/min) appropriate, or should they be adjusted?

---

### Operational Questions

1. **Deployment Environment:** Where will the API be deployed (on-premises, AWS, Azure, GCP, Kubernetes)? This affects deployment architecture.

2. **Disaster Recovery:** What is the RTO (Recovery Time Objective) and RPO (Recovery Point Objective)? This affects backup/recovery strategy.

3. **Maintenance Windows:** Are maintenance windows acceptable, or must the API be always-on? This affects deployment strategy.

4. **Logging & Monitoring:** Should logs be aggregated to a central system (ELK, Splunk, CloudWatch)? This affects logging strategy.

5. **Security Scanning:** Should the API undergo security scanning (SAST, DAST, dependency scanning)? This affects CI/CD pipeline.

6. **Load Testing:** What load testing is required before production deployment? This affects testing strategy.

---

## APPENDIX: GLOSSARY

| Term | Definition |
|------|-----------|
| **ACID** | Atomicity, Consistency, Isolation, Durability — properties of database transactions |
| **API** | Application Programming Interface — contract for communication between systems |
| **CRUD** | Create, Read, Update, Delete — basic operations on data |
| **HA** | High Availability — system continues operating despite failures |
| **HTTP** | HyperText Transfer Protocol — protocol for web communication |
| **HTTPS** | HTTP Secure — HTTP with TLS encryption |
| **Idempotency** | Property of operation that produces same result regardless of how many times it is executed |
| **JSON** | JavaScript Object Notation — lightweight data format |
| **JWT** | JSON Web Token — token-based authentication mechanism |
| **Latency** | Time delay between request and response |
| **MDC** | Mapped Diagnostic Context — mechanism for adding context to log messages |
| **Microservices** | Architectural style where application is composed of small, independent services |
| **Monolith** | Single, unified application (opposite of microservices) |
| **OAuth2** | Authorization framework for delegated access |
| **Optimistic Locking** | Concurrency control mechanism that detects conflicts after the fact |
| **Pagination** | Technique for dividing large result sets into smaller pages |
| **Pessimistic Locking** | Concurrency control mechanism that prevents conflicts by locking resources |
| **REST** | Representational State Transfer — architectural style for web APIs |
| **RTO** | Recovery Time Objective — maximum acceptable downtime |
| **RPO** | Recovery Point Objective — maximum acceptable data loss |
| **SLA** | Service Level Agreement — commitment to availability/performance |
| **SQL** | Structured Query Language — language for database queries |
| **SQLite** | Lightweight, file-based relational database |
| **State Machine** | System that transitions between discrete states based on inputs |
| **Throughput** | Number of requests processed per unit time |
| **TLS** | Transport Layer Security — encryption protocol |
| **Transaction** | Atomic unit of work that either fully succeeds or fully fails |
| **UUID** | Universally Unique Identifier — 128-bit identifier |
| **WAL** | Write-Ahead Logging — database technique for crash recovery |

---

## APPENDIX: ARCHITECTURE DECISION RECORD (ADR)

### ADR-001: Monolithic Service Architecture

**Status:** Accepted

**Context:** Need to build a task management API for 1,000 concurrent users with simple CRUD operations.

**Decision:** Use single monolithic service instead of microservices.

**Rationale:**
- Scale is small; no need for independent scaling
- Simpler deployment and operational burden
- Easier to debug and maintain
- Faster development cycle

**Consequences:**
- Cannot independently scale read vs. write paths
- If scale grows significantly, must refactor to microservices
- All components share same technology stack (Java/Spring)

**Alternatives Considered:**
- Microservices: More complex, overkill for current scale
- Serverless (AWS Lambda): Not suitable for long-running connections; higher latency

---

### ADR-002: SQLite for Data Persistence

**Status:** Accepted

**Context:** Need persistent storage for tasks; must choose between SQLite and PostgreSQL.

**Decision:** Use SQLite for v1.0; migrate to PostgreSQL for v2.0+ if HA required.

**Rationale:**
- Zero-configuration, file-based
- ACID transactions and strong consistency
- Sufficient for <10,000 tasks and <1,000 concurrent users
- No separate database server to manage

**Consequences:**
- Not suitable for multi-instance deployments
- Limited to single server; no replication or failover
- Must migrate to PostgreSQL if HA is required

**Alternatives Considered:**
- PostgreSQL: More complex setup; overkill for current scale
- DynamoDB: No strong consistency; eventual consistency model
- MongoDB: No ACID transactions; eventual consistency

---

### ADR-003: Optimistic Locking for Concurrency Control

**Status:** Accepted

**Context:** Multiple clients may attempt to update the same task simultaneously.

**Decision:** Use optimistic locking with version field.

**Rationale:**
- No server-side locks; high concurrency
- Detects conflicts explicitly; clients can handle them
- Simple to implement; no distributed lock manager needed

**Consequences:**
- Requires clients to implement retry logic
- High-contention workloads may experience many retries
- Not suitable for real-time collaborative editing

**Alternatives Considered:**
- Pessimistic locking: Simpler for clients; lower concurrency
- Distributed locks (Redis): More complex; external dependency

---

### ADR-004: Hard-Delete Only (No Soft-Delete)

**Status:** Accepted

**Context:** Need to decide on deletion semantics (hard-delete vs. soft-delete).

**Decision:** Hard-delete only; no soft-delete.

**Rationale:**
- Simplifies operational burden (no purge job needed)
- Eliminates index bloat from soft-deleted rows
- Clearer semantics (deleted = gone)

**Consequences:**
- No audit trail of deletions
- Cannot recover deleted tasks
- Clients must implement their own audit trail if needed

**Alternatives Considered:**
- Soft-delete with retention: More complex; requires purge job
- Soft-delete with immediate hard-delete: Defeats purpose of soft-delete

---

### ADR-005: No Authentication/Authorization in v1.0

**Status:** Accepted

**Context:** PRD does not mention user accounts or access control.

**Decision:** No authentication or authorization in v1.0; add in v2.0+ if multi-tenant.

**Rationale:**
- Per guardrails, auth is not required unless explicitly stated
- Tasks are not user-scoped; all tasks visible to all clients
- Suitable for internal/prototype use

**Consequences:**
- Not suitable for multi-tenant or public-facing deployments
- No user isolation; all clients see all tasks
- No audit trail of who created/modified tasks

**Alternatives Considered:**
- API key authentication: Simple; suitable for internal use
- OAuth2: Complex; suitable for public-facing APIs
- JWT: Token-based; suitable for distributed systems

---

### ADR-006: Offset-Based Pagination

**Status:** Accepted

**Context:** Need to paginate large result sets.

**Decision:** Use offset-based pagination with limit/offset.

**Rationale:**
- Simple, predictable, no cursor state required
- Clients can jump to arbitrary page
- Suitable for <10,000 total tasks

**Consequences:**
- Inefficient for large offsets
- If results are sorted by creation time and new items are added, pagination may skip or duplicate items

**Alternatives Considered:**
- Cursor-based pagination: More efficient; more complex
- Keyset pagination: Efficient; requires stable sort key

---

### ADR-007: Spring Boot for REST API Framework

**Status:** Accepted

**Context:** Need to build REST API quickly with minimal boilerplate.

**Decision:** Use Spring Boot 3.2+ with embedded Tomcat.

**Rationale:**
- Rapid REST API development
- Built-in validation, transaction management, observability
- Mature ecosystem with extensive documentation
- Reduces boilerplate code

**Consequences:**
- Requires Java runtime on deployment server
- Not suitable for serverless deployments
- Slightly higher memory footprint than lightweight frameworks

**Alternatives Considered:**
- Node.js/Express: Lighter; less suitable for production APIs at scale
- Python/FastAPI: Rapid prototyping; Python's GIL limits concurrency
- Go: Lightweight; smaller ecosystem for task management

---

### ADR-008: Flyway for Database Migrations

**Status:** Accepted

**Context:** Need version-controlled schema migrations.

**Decision:** Use Flyway for automatic schema initialization and migrations.

**Rationale:**
- Automatic schema initialization on startup
- Version-controlled migrations (tracked in Git)
- Ensures schema consistency across deployments
- Rollback capability

**Consequences:**
- Adds complexity to deployment process
- Requires careful migration design to avoid downtime
- Undo migrations must be manually written

**Alternatives Considered:**
- Manual SQL scripts: No version control; error-prone
- Liquibase: More complex; more flexible

---

## APPENDIX: COMPONENT INTERACTION DIAGRAM

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Client Application                          │
│  (Backend integration, UI frontend, third-party tool)              │
└────────────────────────┬────────────────────────────────────────────┘
                         │ HTTP/REST
                         │ (JSON request/response)
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    REST Controller Layer                            │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ TaskController                                               │  │
│  │ - POST /tasks                                                │  │
│  │ - GET /tasks                                                 │  │
│  │ - GET /tasks/{id}                                            │  │
│  │ - PATCH /tasks/{id}                                          │  │
│  │ - DELETE /tasks/{id}                                         │  │
│  └────────────────────┬─────────────────────────────────────────┘  │
│                       │ (invoke)                                    │
│  ┌────────────────────▼─────────────────────────────────────────┐  │
│  │ GlobalExceptionHandler (@ControllerAdvice)                  │  │
│  │ - Catch exceptions from controllers/services                │  │
│  │ - Translate to HTTP status codes                            │  │
│  │ - Format error responses                                    │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │ Cross-Cutting Concerns                                     │   │
│  │ - RateLimiter: Track requests per IP                       │   │
│  │ - RequestIdProvider: Extract/generate request ID           │   │
│  │ - MetricsCollector: Collect request metrics                │   │
│  └────────────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────────────┘
                         │ (invoke)
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Service Layer                                  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ TaskService                                                  │  │
│  │ - createTask(request)                                        │  │
│  │ - listTasks(request)                                         │  │
│  │ - getTask(id)                                                │  │
│  │ - updateTaskStatus(id, status, version)                     │  │
│  │ - deleteTask(id)                                             │  │
│  │ - validateStateTransition(current, new)                     │  │
│  └────────────────────┬─────────────────────────────────────────┘  │
│                       │ (invoke)                                    │
│  ┌────────────────────▼─────────────────────────────────────────┐  │
│  │ TaskValidator                                                │  │
│  │ - validateCreateRequest(request)                             │  │
│  │ - validateUpdateRequest(request)                             │  │
│  │ - validateStateTransition(current, new)                     │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────────┘
                         │ (invoke)
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   Data Access Layer                                 │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ TaskRepository (Spring Data JPA)                             │  │
│  │ - findById(id)                                               │  │
│  │ - save(task)                                                 │  │
│  │ - delete(task)                                               │  │
│  │ - findAllByStatusAndCreatedAt(status, pageable)             │  │
│  │ - findAllByDueDateBetween(from, to, pageable)               │  │
│  │ - findAllByStatusAndDueDateBetweenAndPriority(...)          │  │
│  └────────────────────┬─────────────────────────────────────────┘  │
│                       │ (JDBC queries)                              │
│  ┌────────────────────▼─────────────────────────────────────────┐  │
│  │ Hibernate ORM                                                │  │
│  │ - Map Task entity to database rows                           │  │
│  │ - Handle optimistic locking (@Version)                      │  │
│  │ - Manage transactions (@Transactional)                      │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────────┘
                         │ (JDBC)
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    SQLite Database                                  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ tasks table                                                  │  │
│  │ - id (UUID, PK)                                              │  │
│  │ - title, description, due_date, priority                    │  │
│  │ - status (NEW, IN_PROGRESS, COMPLETED, ARCHIVED)            │  │
│  │ - version (optimistic locking)                              │  │
│  │ - created_at, updated_at (timestamps)                       │  │
│  │                                                              │  │
│  │ Indexes:                                                     │  │
│  │ - (status, created_at DESC)                                 │  │
│  │ - (due_date)                                                │  │
│  │ - (created_at DESC)                                         │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## APPENDIX: REQUEST/RESPONSE FLOW EXAMPLE

### Example 1: Create Task (Happy Path)

```
Client Request:
POST /tasks HTTP/1.1
Host: api.example.com
Content-Type: application/json
X-Request-ID: 550e8400-e29b-41d4-a716-446655440000

{
  "title": "Implement user authentication",
  "description": "Add OAuth2 login to the application",
  "due_date": "2024-02-15",
  "priority": "HIGH"
}

Server Processing:
1. TaskController receives request
2. Extract X-Request-ID (or generate if not provided)
3. Store in MDC for logging
4. Validate request body (Spring @Valid)
5. Invoke TaskService.createTask(request)
6. TaskService validates input
7. Create Task entity with defaults (status=NEW, version=1)
8. Invoke TaskRepository.save(task)
9. Hibernate persists to SQLite
10. Return Task entity to controller
11. Format response

Server Response:
HTTP/1.1 201 Created
Content-Type: application/json
X-Request-ID: 550e8400-e29b-41d4-a716-446655440000
X-RateLimit-Limit: 20
X-RateLimit-Remaining: 19
X-RateLimit-Reset: 1705334400

{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "title": "Implement user authentication",
  "description": "Add OAuth2 login to the application",
  "due_date": "2024-02-15",
  "priority": "HIGH",
  "status": "NEW",
  "version": 1,
  "created_at": "2024-01-15T10:30:45.123Z",
  "updated_at": "2024-01-15T10:30:45.123Z"
}

Logging:
2024-01-15T10:30:45.123Z [http-nio-8080-exec-1] INFO  com.example.todoapi.controller.TaskController - [req-id: 550e8400-e29b-41d4-a716-446655440000] POST /tasks - status: 201, latency: 45ms
```

### Example 2: Update Task Status (Optimistic Locking Conflict)

```
Client A Request:
PATCH /tasks/f47ac10b-58cc-4372-a567-0e02b2c3d479 HTTP/1.1
Host: api.example.com
Content-Type: application/json
X-Request-ID: 550e8400-e29b-41d4-a716-446655440001

{
  "status": "IN_PROGRESS",
  "version": 1
}

Client B Request (simultaneous):
PATCH /tasks/f47ac10b-58cc-4372-a567-0e02b2c3d479 HTTP/1.1
Host: api.example.com
Content-Type: application/json
X-Request-ID: 550e8400-e29b-41d4-a716-446655440002

{
  "status": "COMPLETED",
  "version": 1
}

Server Processing (Client A):
1. TaskController receives request
2. Validate state transition: NEW → IN_PROGRESS ✓
3. Invoke TaskService.updateTaskStatus(id, IN_PROGRESS, version=1)
4. Query database: SELECT * FROM tasks WHERE id=... (version=1)
5. Update: SET status=IN_PROGRESS, version=2, updated_at=NOW()
6. Hibernate checks: version in database (1) == version in request (1) ✓
7. Persist update
8. Return updated task

Server Response (Client A):
HTTP/1.1 200 OK
Content-Type: application/json
X-Request-ID: 550e8400-e29b-41d4-a716-446655440001

{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "title": "Implement user authentication",
  "description": "Add OAuth2 login to the application",
  "due_date": "2024-02-15",
  "priority": "HIGH",
  "status": "IN_PROGRESS",
  "version": 2,
  "created_at": "2024-01-15T10:30:45.123Z",
  "updated_at": "2024-01-15T10:31:00.456Z"
}

Server Processing (Client B):
1. TaskController receives request
2. Validate state transition: NEW → COMPLETED ✗ (invalid)
3. Return 400 Bad Request

Server Response (Client B - Invalid Transition):
HTTP/1.1 400 Bad Request
Content-Type: application/json
X-Request-ID: 550e8400-e29b-41d4-a716-446655440002

{
  "error": {
    "code": "INVALID_STATE_TRANSITION",
    "message": "Cannot transition from NEW to COMPLETED; must go through IN_PROGRESS",
    "details": {
      "current_status": "IN_PROGRESS",
      "requested_status": "COMPLETED"
    }
  },
  "request_id": "550e8400-e29b-41d4-a716-446655440002"
}

Client B Retry Logic:
1. Receive 400 Bad Request
2. Fetch latest task: GET /tasks/f47ac10b-58cc-4372-a567-0e02b2c3d479
3. Receive: status=IN_PROGRESS, version=2
4. Validate state transition: IN_PROGRESS → COMPLETED ✓
5. Retry PATCH with updated version=2

Client B Retry Request:
PATCH /tasks/f47ac10b-58cc-4372-a567-0e02b2c3d479 HTTP/1.1
Host: api.example.com
Content-Type: application/json
X-Request-ID: 550e8400-e29b-41d4-a716-446655440002

{
  "status": "COMPLETED",
  "version": 2
}

Server Response (Client B - Retry Success):
HTTP/1.1 200 OK
Content-Type: application/json
X-Request-ID: 550e8400-e29b-41d4-a716-446655440002

{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "title": "Implement user authentication",
  "description": "Add OAuth2 login to the application",
  "due_date": "2024-02-15",
  "priority": "HIGH",
  "status": "COMPLETED",
  "version": 3,
  "created_at": "2024-01-15T10:30:45.123Z",
  "updated_at": "2024-01-15T10:31:15.789Z"
}
```

### Example 3: List Tasks with Filtering

```
Client Request:
GET /tasks?status=IN_PROGRESS&priority=HIGH&limit=10&offset=0&sort_by=due_date&sort_order=ASC HTTP/1.1
Host: api.example.com
X-Request-ID: 550e8400-e29b-41d4-a716-446655440003

Server Processing:
1. TaskController receives request
2. Parse query parameters
3. Validate: limit=10 (valid, ≤100), offset=0 (valid, ≥0)
4. Invoke TaskService.listTasks(status=IN_PROGRESS, priority=HIGH, limit=10, offset=0, sort_by=due_date, sort_order=ASC)
5. Build query: SELECT * FROM tasks WHERE status='IN_PROGRESS' AND priority='HIGH' ORDER BY due_date ASC LIMIT 10 OFFSET 0
6. Execute query via TaskRepository
7. Count total: SELECT COUNT(*) FROM tasks WHERE status='IN_PROGRESS' AND priority='HIGH'
8. Format response with pagination metadata

Server Response:
HTTP/1.1 200 OK
Content-Type: application/json
X-Request-ID: 550e8400-e29b-41d4-a716-446655440003
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 99
X-RateLimit-Reset: 1705334400

{
  "data": [
    {
      "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "title": "Implement user authentication",
      "description": "Add OAuth2 login to the application",
      "due_date": "2024-02-15",
      "priority": "HIGH",
      "status": "IN_PROGRESS",
      "version": 3,
      "created_at": "2024-01-15T10:30:45.123Z",
      "updated_at": "2024-01-15T10:31:15.789Z"
    },
    {
      "id": "a1b2c3d4-e5f6-47a8-b9c0-d1e2f3a4b5c6",
      "title": "Fix critical bug in payment processing",
      "description": "Payment fails for certain credit card types",
      "due_date": "2024-02-20",
      "priority": "HIGH",
      "status": "IN_PROGRESS",
      "version": 2,
      "created_at": "2024-01-14T14:22:10.456Z",
      "updated_at": "2024-01-15T09:15:30.123Z"
    }
  ],
  "pagination": {
    "limit": 10,
    "offset": 0,
    "total": 2,
    "has_more": false
  }
}
```

---

## APPENDIX: DEPLOYMENT CHECKLIST

### Pre-Deployment

- [ ] Code review completed and approved
- [ ] All tests passing (unit, integration, smoke)
- [ ] Security scanning completed (SAST, dependency check)
- [ ] Performance testing completed; latency targets met
- [ ] Load testing completed; throughput targets met
- [ ] Documentation updated (API docs, deployment guide, runbook)
- [ ] Backup strategy validated
- [ ] Monitoring/alerting configured
- [ ] Rollback plan documented

### Deployment

- [ ] Build JAR: `mvn clean package`
- [ ] Verify JAR size and dependencies
- [ ] Create Docker image (if using containers)
- [ ] Push image to registry
- [ ] Deploy to staging environment
- [ ] Run smoke tests against staging
- [ ] Verify health checks pass (liveness, readiness)
- [ ] Deploy to production
- [ ] Monitor metrics and logs for errors
- [ ] Verify API endpoints responding correctly
- [ ] Verify database connectivity and schema

### Post-Deployment

- [ ] Monitor error rate (should be <0.1%)
- [ ] Monitor latency (p95 should be <200ms)
- [ ] Monitor uptime (should be 100% in first hour)
- [ ] Check logs for warnings or errors
- [ ] Verify backups are running
- [ ] Notify stakeholders of successful deployment
- [ ] Schedule post-deployment review

---

## APPENDIX: RUNBOOK

### Incident: API Not Responding

**Symptoms:** Clients unable to reach API; liveness probe failing.

**Diagnosis:**
1. SSH to application server
2. Check process status: `ps aux | grep java`
3. Check logs: `tail -f /var/log/todo-api/app.log`
4. Check port: `netstat -tlnp | grep 8080`
5. Check disk space: `df -h`
6. Check memory: `free -h`

**Resolution:**
1. If process is not running, restart: `systemctl restart todo-api`
2. If port is in use, kill process: `lsof -i :8080` then `kill -9 <pid>`
3. If disk full, archive old logs: `gzip /var/log/todo-api/app.log.*`
4. If memory exhausted, increase heap: `JAVA_OPTS="-Xmx1024m"`
5. Check health endpoint: `curl http://localhost:8080/health/live`

---

### Incident: High Error Rate

**Symptoms:** >1% of requests returning 5xx errors.

**Diagnosis:**
1. Check application logs: `tail -f /var/log/todo-api/app.log | grep ERROR`
2. Check database connectivity: `curl http://localhost:8080/health/ready`
3. Check database size: `ls -lh /data/tasks.db`
4. Check disk space: `df -h`
5. Check metrics: `curl http://localhost:8080/actuator/metrics/http.requests.total`

**Resolution:**
1. If database is down, restart database service
2. If disk full, archive old data or add disk space
3. If database is corrupted, restore from backup
4. If application is deadlocked, restart: `systemctl restart todo-api`

---

### Incident: High Latency

**Symptoms:** p95 latency >500ms; clients reporting slow responses.

**Diagnosis:**
1. Check metrics: `curl http://localhost:8080/actuator/metrics/http.requests.duration`
2. Check slow queries: `tail -f /var/log/todo-api/app.log | grep "duration"`
3. Check database size: `ls -lh /data/tasks.db`
4. Check CPU usage: `top`
5. Check memory usage: `free -h`

**Resolution:**
1. If database is large (>1GB), archive old tasks or migrate to PostgreSQL
2. If CPU is high, increase CPU cores or optimize queries
3. If memory is high, increase heap or reduce batch size
4. If specific query is slow, add index or optimize query

---

### Incident: Database Corruption

**Symptoms:** Database errors; unable to read/write tasks.

**Diagnosis:**
1. Check database integrity: `sqlite3 /data/tasks.db "PRAGMA integrity_check;"`
2. Check logs for corruption errors
3. Check disk space (corruption often caused by full disk)

**Resolution:**
1. If corruption is minor, try repair: `sqlite3 /data/tasks.db "VACUUM;"`
2. If corruption is severe, restore from backup:
   - Stop API: `systemctl stop todo-api`
   - Restore backup: `cp /backup/tasks.db.backup /data/tasks.db`
   - Restart API: `systemctl start todo-api`
   - Verify health: `curl http://localhost:8080/health/ready`

---

## APPENDIX: FUTURE ROADMAP

### v1.0 (Current)
- Basic CRUD operations (create, list, retrieve, update, delete)
- Task state machine (NEW, IN_PROGRESS, COMPLETED, ARCHIVED)
- Pagination and filtering
- Optimistic locking for concurrency
- Single-instance deployment with SQLite

### v1.1 (Next)
- Bulk operations (bulk create, bulk update, bulk delete)
- Task search (full-text search on title/description)
- Task sorting by multiple fields
- Soft-delete with retention policy
- Audit trail (track who created/modified/deleted tasks)

### v2.0 (Future)
- Multi-tenancy (user-scoped tasks)
- Authentication/authorization (API keys, OAuth2)
- Task hierarchies (subtasks, parent-child relationships)
- Custom task states and workflows
- Notifications (email, webhook, Slack)
- Analytics (task completion rates, workflow metrics)
- PostgreSQL migration for HA
- Multi-instance deployment with load balancer
- Redis caching for performance
- GraphQL API (in addition to REST)

### v3.0 (Long-term)
- Microservices architecture (Task Service, Notification Service, Analytics Service)
- Event-driven architecture (Kafka for inter-service communication)
- Real-time collaboration (WebSocket support)
- Advanced analytics and reporting
- Machine learning (task prioritization, deadline prediction)
- Mobile app (iOS, Android)

---

## DOCUMENT SIGN-OFF

**Prepared By:** Engineering Leadership  
**Reviewed By:** Product Management, DevOps, Security  
**Approved By:** CTO / VP Engineering  
**Date:** [Current Date]  
**Version:** 1.0  
**Status:** Ready for Implementation

---

**END OF SOLUTION DESIGN DOCUMENT**