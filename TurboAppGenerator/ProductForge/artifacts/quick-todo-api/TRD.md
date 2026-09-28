# TECHNICAL REQUIREMENTS DOCUMENT (TRD)
## To-Do List API

**Document Version:** 1.0  
**Last Updated:** [Current Date]  
**Status:** Ready for Development  
**Owner:** Engineering Leadership

---

## TABLE OF CONTENTS

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Technology Stack](#technology-stack)
4. [Task State Model & Lifecycle](#task-state-model--lifecycle)
5. [Data Model](#data-model)
6. [API Design Principles](#api-design-principles)
7. [API Endpoints Specification](#api-endpoints-specification)
8. [Concurrency & Consistency Model](#concurrency--consistency-model)
9. [Error Handling & Validation](#error-handling--validation)
10. [Non-Functional Requirements](#non-functional-requirements)
11. [Security Architecture](#security-architecture)
12. [Observability & Monitoring](#observability--monitoring)
13. [Deployment & Operations](#deployment--operations)
14. [Data Retention & Compliance](#data-retention--compliance)
15. [Migration & Rollout Strategy](#migration--rollout-strategy)
16. [Open Questions & Future Considerations](#open-questions--future-considerations)

---

## EXECUTIVE SUMMARY

This Technical Requirements Document (TRD) translates the Product Requirements Document (PRD) into actionable technical specifications for the To-Do List API. It defines:

- **Architecture:** Single-service, stateless API backed by SQLite for task persistence
- **Technology Stack:** Java/Spring Boot for the backend, SQLite for data storage, deployed as a standalone JAR
- **Task Lifecycle:** Explicit state machine with four states (NEW, IN_PROGRESS, COMPLETED, ARCHIVED) and defined transition rules
- **Consistency Model:** Strong consistency with optimistic locking to prevent lost writes during concurrent updates
- **API Contract:** RESTful endpoints supporting task CRUD operations, pagination, filtering, and sorting
- **Non-Functional Targets:** 99.5% uptime, <200ms p95 latency, support for 1,000 concurrent users

**Key Decisions:**
- **No authentication/authorization:** Per guardrails, tasks are not user-scoped; API is open (suitable for prototype/internal use)
- **Soft-delete with retention:** Deleted tasks are marked as deleted and retained for 30 days before permanent purge
- **Optimistic locking:** Version field on tasks prevents lost writes; clients must handle 409 Conflict responses
- **Offset-based pagination:** Simple, predictable pagination with explicit sort order (created_at DESC by default)

---

## ARCHITECTURE OVERVIEW

### System Context

The To-Do List API is a **single-service, stateless backend** that manages task persistence and state transitions. It exposes a RESTful API for task lifecycle operations and is designed to be integrated into larger applications.

```
┌─────────────────────────────────────────────────────────────┐
│                    Client Applications                       │
│  (Backend integrations, UI frontends, third-party tools)    │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP/REST
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              To-Do List API (Spring Boot)                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  REST Controllers (Task endpoints)                   │   │
│  │  - POST /tasks (create)                              │   │
│  │  - GET /tasks (list with pagination/filtering)       │   │
│  │  - GET /tasks/{id} (retrieve)                        │   │
│  │  - PATCH /tasks/{id} (update status/fields)          │   │
│  │  - DELETE /tasks/{id} (soft-delete)                  │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Service Layer (Business Logic)                      │   │
│  │  - Task state machine validation                     │   │
│  │  - Concurrency conflict detection                    │   │
│  │  - Pagination & filtering logic                      │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Data Access Layer (Repository)                      │   │
│  │  - CRUD operations on tasks table                    │   │
│  │  - Query building for filters/sorting                │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────────────┘
                     │ JDBC
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    SQLite Database                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  tasks table                                         │   │
│  │  - id (UUID primary key)                             │   │
│  │  - title, description, due_date, priority           │   │
│  │  - status (state machine)                            │   │
│  │  - version (optimistic locking)                      │   │
│  │  - deleted_at (soft-delete marker)                   │   │
│  │  - created_at, updated_at (timestamps)               │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Service Boundaries

The API is a **single, cohesive service** with no external service dependencies. All business logic (state validation, filtering, pagination) is contained within the service. This simplifies deployment, reduces failure points, and aligns with the prototype/lightweight profile.

**Why not microservices?** At the stated scale (1,000 concurrent users, simple CRUD operations), a monolithic service is more maintainable and operationally simpler. If future requirements demand multi-tenancy, complex workflows, or separate scaling of read/write paths, the service can be refactored.

### Deployment Topology

- **Single JAR deployment:** Spring Boot application packaged as an executable JAR
- **Embedded SQLite:** Database file stored locally on the application server (no separate database server)
- **Stateless API servers:** Multiple instances can run behind a load balancer; each instance has its own SQLite file or shares a network-accessible SQLite file (see [Deployment & Operations](#deployment--operations) for details)
- **No external dependencies:** No message queues, caches, or third-party services

---

## TECHNOLOGY STACK

### Backend Runtime & Framework

| Component | Choice | Version | Rationale |
|-----------|--------|---------|-----------|
| **Language** | Java | 17 LTS | Mature, widely understood, excellent tooling. Spring Boot ecosystem is production-proven. |
| **Framework** | Spring Boot | 3.2+ | Rapid REST API development, built-in validation, transaction management, and observability hooks. Reduces boilerplate. |
| **Build Tool** | Maven | 3.9+ | Standard Java build tool; integrates with Spring Boot starter templates. |
| **HTTP Server** | Embedded Tomcat | (via Spring Boot) | Eliminates separate server deployment; Spring Boot packages Tomcat automatically. |

### Data Persistence

| Component | Choice | Version | Rationale |
|-----------|--------|---------|-----------|
| **Database** | SQLite | 3.43+ | Lightweight, file-based, zero-configuration. Suitable for prototype and small-to-medium scale. No separate database server to manage. Supports transactions and ACID guarantees. |
| **JDBC Driver** | sqlite-jdbc | 3.44+ | Pure Java SQLite driver; no native dependencies. |
| **ORM/Query Builder** | Spring Data JPA with Hibernate | (via Spring Boot) | Reduces boilerplate for CRUD operations; supports custom queries via `@Query` annotations. |
| **Database Migrations** | Flyway | 9.22+ | Version-controlled schema migrations; runs automatically on startup. Ensures schema consistency across deployments. |

### Testing & Quality

| Component | Choice | Version | Rationale |
|-----------|--------|---------|-----------|
| **Unit Testing** | JUnit 5 | (via Spring Boot) | Standard Java testing framework; integrated with Spring Boot test utilities. |
| **Mocking** | Mockito | (via Spring Boot) | Lightweight mocking for unit tests; reduces test complexity. |
| **Integration Testing** | Spring Boot Test + Testcontainers | (via Spring Boot) | Spin up embedded SQLite for integration tests; no external test database needed. |
| **Code Quality** | SonarQube (optional) | — | Optional for prototype; can be added later if code quality gates are required. |

### Why Not X?

| Alternative | Why Not | Trade-off |
|-------------|---------|-----------|
| **Node.js/Express** | Java/Spring is more suitable for a team with Java expertise and for long-term maintainability of a production API. Express is lighter but lacks built-in validation, transaction management, and observability. | If team is Node-first, Express would be acceptable; requires explicit validation and error handling libraries. |
| **Python/FastAPI** | FastAPI is excellent for rapid prototyping but less suitable for production APIs at scale. Python's GIL limits concurrency; Java's threading model is better for 1,000 concurrent users. | If team is Python-first and scale is <100 concurrent users, FastAPI would be acceptable. |
| **PostgreSQL** | SQLite is sufficient for prototype and small-scale deployments. PostgreSQL adds operational complexity (separate server, backups, replication). Can migrate to PostgreSQL later if scale demands it. | If scale exceeds SQLite's limits (>10GB data, >1,000 writes/sec), migrate to PostgreSQL. |
| **Redis Cache** | Caching is not required for prototype. API latency targets (<200ms) are achievable with SQLite + proper indexing. Cache adds complexity (invalidation, consistency). | If p95 latency exceeds 200ms, add Redis for frequently accessed queries (e.g., list tasks by status). |
| **Message Queue (RabbitMQ, Kafka)** | No asynchronous processing required. All operations are synchronous CRUD. Queues add operational complexity. | If future requirements include batch processing, notifications, or event streaming, add a queue. |

---

## TASK STATE MODEL & LIFECYCLE

### State Definitions

The task lifecycle is modeled as a **finite state machine** with four states:

| State | Description | Semantics | Transitions To |
|-------|-------------|-----------|-----------------|
| **NEW** | Task created but not yet started | Initial state; task is pending work | IN_PROGRESS, ARCHIVED, DELETED |
| **IN_PROGRESS** | Task is actively being worked on | Work has begun; task is not complete | COMPLETED, NEW (undo), ARCHIVED, DELETED |
| **COMPLETED** | Task work is finished | Task reached its goal; no further work expected | IN_PROGRESS (undo), ARCHIVED, DELETED |
| **ARCHIVED** | Task is no longer active but retained for history | Completed or abandoned tasks moved here for cleanup | IN_PROGRESS (restore), DELETED |
| **DELETED** | Task is marked for deletion (soft-delete) | Task is hidden from normal queries; retained for 30 days | (none — terminal state) |

### State Transition Rules

**Allowed Transitions (Decision Table):**

| Current State | Action | Target State | Allowed? | Notes |
|---------------|--------|--------------|----------|-------|
| NEW | Mark IN_PROGRESS | IN_PROGRESS | ✓ | Start work on task |
| NEW | Mark COMPLETED | COMPLETED | ✗ | Cannot skip to COMPLETED; must go through IN_PROGRESS first |
| NEW | Archive | ARCHIVED | ✓ | Abandon task without starting |
| NEW | Delete | DELETED | ✓ | Remove task |
| IN_PROGRESS | Mark COMPLETED | COMPLETED | ✓ | Finish work |
| IN_PROGRESS | Mark NEW | NEW | ✓ | Undo; revert to pending |
| IN_PROGRESS | Archive | ARCHIVED | ✓ | Pause and archive |
| IN_PROGRESS | Delete | DELETED | ✓ | Remove task |
| COMPLETED | Mark IN_PROGRESS | IN_PROGRESS | ✓ | Undo completion; revert to in-progress |
| COMPLETED | Archive | ARCHIVED | ✓ | Move completed task to archive |
| COMPLETED | Delete | DELETED | ✓ | Remove task |
| ARCHIVED | Mark IN_PROGRESS | IN_PROGRESS | ✓ | Restore archived task to active work |
| ARCHIVED | Delete | DELETED | ✓ | Permanently remove archived task |
| DELETED | (any) | — | ✗ | Terminal state; no transitions allowed |

**Rationale:**
- **No direct NEW → COMPLETED:** Enforces that work must be explicitly started (IN_PROGRESS) before completion. Prevents accidental completion of unstarted tasks.
- **Undo from COMPLETED/IN_PROGRESS:** Allows correction of state mistakes without deletion.
- **ARCHIVED as intermediate state:** Separates "completed/abandoned" tasks from "active" tasks without permanent deletion. Supports compliance and audit trails.
- **DELETED as terminal:** Soft-delete prevents accidental data loss; tasks are retained for 30 days before permanent purge.

### State Transition API

State transitions are triggered via the **PATCH /tasks/{id}** endpoint with a `status` field:

```
PATCH /tasks/{id}
{
  "status": "IN_PROGRESS"  // or COMPLETED, NEW, ARCHIVED, DELETED
}
```

The API validates the transition against the state machine. If the transition is invalid, the API returns **400 Bad Request** with error code `INVALID_STATE_TRANSITION`.

---

## DATA MODEL

### Task Entity

The `tasks` table is the core data structure. It stores all task information and metadata required for state management, concurrency control, and soft-delete.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Unique task identifier; generated on creation (UUID v4) |
| `title` | VARCHAR(255) | NOT NULL | Task title; required, max 255 characters |
| `description` | TEXT | NULL | Optional task description; max 2000 characters |
| `due_date` | DATE | NULL | Optional due date; ISO 8601 format (YYYY-MM-DD) |
| `priority` | ENUM | NOT NULL, DEFAULT 'MEDIUM' | Task priority: LOW, MEDIUM, HIGH |
| `status` | ENUM | NOT NULL, DEFAULT 'NEW' | Task state: NEW, IN_PROGRESS, COMPLETED, ARCHIVED, DELETED |
| `version` | INTEGER | NOT NULL, DEFAULT 1 | Optimistic locking version; incremented on each update |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Task creation timestamp (UTC) |
| `updated_at` | TIMESTAMP | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Last update timestamp (UTC); updated on every change |
| `deleted_at` | TIMESTAMP | NULL | Soft-delete timestamp (UTC); NULL if not deleted |

### Indexes

To support efficient querying and filtering:

| Index Name | Columns | Rationale |
|------------|---------|-----------|
| `idx_status` | `status` | Filter tasks by status (e.g., list all IN_PROGRESS tasks) |
| `idx_created_at` | `created_at` DESC | Default sort order for list operations |
| `idx_due_date` | `due_date` | Filter tasks by due date range |
| `idx_deleted_at` | `deleted_at` | Exclude soft-deleted tasks from queries |
| `idx_status_created_at` | `status`, `created_at` DESC | Combined index for common filter + sort patterns |

### Data Validation Rules

**Field-Level Validation:**

| Field | Rule | Error Code | HTTP Status |
|-------|------|-----------|-------------|
| `title` | Required; 1-255 characters; non-empty after trim | INVALID_TITLE | 400 |
| `description` | Optional; max 2000 characters | INVALID_DESCRIPTION | 400 |
| `due_date` | Optional; valid ISO 8601 date; must be >= today | INVALID_DUE_DATE | 400 |
| `priority` | Optional; must be one of: LOW, MEDIUM, HIGH | INVALID_PRIORITY | 400 |
| `status` | Must be one of: NEW, IN_PROGRESS, COMPLETED, ARCHIVED, DELETED | INVALID_STATUS | 400 |

**Business Logic Validation:**

| Rule | Trigger | Error Code | HTTP Status |
|------|---------|-----------|-------------|
| State transition allowed | PATCH /tasks/{id} with new status | INVALID_STATE_TRANSITION | 400 |
| Optimistic lock conflict | PATCH /tasks/{id} with stale version | CONFLICT | 409 |
| Task not found | GET/PATCH/DELETE /tasks/{id} for non-existent task | NOT_FOUND | 404 |
| Soft-deleted task hidden | GET/PATCH /tasks/{id} for deleted task | NOT_FOUND | 404 |

---

## API DESIGN PRINCIPLES

### RESTful Conventions

The API follows standard REST conventions:

- **Resources:** Tasks are the primary resource, identified by UUID
- **HTTP Methods:** 
  - POST for creation (idempotent via idempotency key)
  - GET for retrieval
  - PATCH for partial updates (status, priority, description)
  - DELETE for soft-deletion
- **Status Codes:** Standard HTTP status codes (201, 200, 400, 404, 409, 429, 500)
- **Content Type:** JSON for request/response bodies; `Content-Type: application/json`

### Versioning Strategy

The API uses **URL-based versioning** to support future breaking changes:

- **Current version:** `/api/v1/tasks`
- **Future versions:** `/api/v2/tasks` (if breaking changes are required)

This allows clients to opt-in to new versions without forced migration.

### Error Response Format

All error responses follow a consistent structure:

```
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      "field": "title",
      "reason": "Field is required"
    }
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req-12345"
}
```

**Fields:**
- `code`: Machine-readable error code (e.g., INVALID_TITLE, CONFLICT)
- `message`: Human-readable description
- `details`: Optional object with field-level error information
- `timestamp`: ISO 8601 timestamp of error
- `request_id`: Unique request identifier for tracing

### Pagination Design

**Offset-Based Pagination:**

The API uses offset-based pagination (limit/offset) for simplicity and predictability. This is suitable for the prototype scale; if pagination becomes a bottleneck, cursor-based pagination can be added later.

**Parameters:**
- `limit`: Number of tasks to return (default: 20, max: 100)
- `offset`: Number of tasks to skip (default: 0)

**Response Metadata:**
```
{
  "data": [ /* task objects */ ],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total": 150,
    "has_more": true
  }
}
```

**Sort Order:**
- Default: `created_at DESC` (newest tasks first)
- Supported: `created_at`, `due_date`, `priority`, `status`
- Direction: ASC or DESC (specified via `sort` parameter: `created_at:DESC`)

### Filtering Design

**Query Parameters:**

| Parameter | Type | Example | Behavior |
|-----------|------|---------|----------|
| `status` | enum (comma-separated) | `status=NEW,IN_PROGRESS` | Return tasks with any of the specified statuses |
| `priority` | enum (comma-separated) | `priority=HIGH,MEDIUM` | Return tasks with any of the specified priorities |
| `due_date_from` | ISO 8601 date | `due_date_from=2024-01-01` | Return tasks with due_date >= specified date |
| `due_date_to` | ISO 8601 date | `due_date_to=2024-12-31` | Return tasks with due_date <= specified date |
| `search` | string | `search=urgent` | Full-text search on title and description (case-insensitive substring match) |

**Filtering Logic:**
- Multiple filters are combined with AND logic (e.g., `status=NEW&priority=HIGH` returns tasks that are both NEW and HIGH priority)
- Comma-separated values within a single parameter use OR logic (e.g., `status=NEW,IN_PROGRESS` returns tasks that are either NEW or IN_PROGRESS)

### Idempotency

**Idempotency Key Header:**

To prevent duplicate task creation on retries, clients can provide an `Idempotency-Key` header:

```
POST /api/v1/tasks
Idempotency-Key: client-generated-uuid-or-string
{
  "title": "Buy groceries"
}
```

**Semantics:**
- **Retention Window:** Idempotency keys are retained for 24 hours
- **Collision Handling:** If the same idempotency key is used with a different request body within 24 hours, the API returns **409 Conflict** with error code `IDEMPOTENCY_KEY_CONFLICT`
- **Successful Retry:** If the same idempotency key is used with the same request body, the API returns the cached response (201 Created with the original task)
- **Expired Key:** If the idempotency key is older than 24 hours, it is treated as a new request

**Implementation:**
- Idempotency keys are stored in a separate `idempotency_keys` table with columns: `key`, `request_hash`, `response`, `created_at`
- On POST /tasks, the API checks if the key exists; if yes, returns the cached response; if no, processes the request and caches the response

---

## API ENDPOINTS SPECIFICATION

### Endpoint Summary

| Method | Path | Purpose | Auth | Rate Limit |
|--------|------|---------|------|-----------|
| POST | /api/v1/tasks | Create task | None | 100 req/min |
| GET | /api/v1/tasks | List tasks (paginated, filtered) | None | 1000 req/min |
| GET | /api/v1/tasks/{id} | Retrieve task | None | 1000 req/min |
| PATCH | /api/v1/tasks/{id} | Update task | None | 100 req/min |
| DELETE | /api/v1/tasks/{id} | Soft-delete task | None | 100 req/min |

### Endpoint Details

#### 1. POST /api/v1/tasks — Create Task

**Purpose:** Create a new task with the provided title and optional fields.

**Request:**
- **Headers:** `Content-Type: application/json`, `Idempotency-Key: <optional>`
- **Body:**
  ```
  {
    "title": "Buy groceries",
    "description": "Milk, eggs, bread",
    "due_date": "2024-01-20",
    "priority": "HIGH"
  }
  ```

**Response (201 Created):**
```
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Buy groceries",
  "description": "Milk, eggs, bread",
  "due_date": "2024-01-20",
  "priority": "HIGH",
  "status": "NEW",
  "version": 1,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

**Error Responses:**
- **400 Bad Request:** Missing/invalid `title`, invalid `due_date` format, invalid `priority` enum
- **409 Conflict:** Idempotency key collision (same key, different body)
- **429 Too Many Requests:** Rate limit exceeded (>100 req/min)
- **500 Internal Server Error:** Unexpected server error

**Acceptance Criteria:**
- AC1: Task created with status=NEW, priority=MEDIUM (default)
- AC2: UUID generated and returned in response
- AC3: Timestamps (created_at, updated_at) set to current UTC time
- AC4: Version field set to 1
- AC5: Idempotency key retained for 24 hours; same key + same body returns cached response

---

#### 2. GET /api/v1/tasks — List Tasks

**Purpose:** Retrieve a paginated, filtered, and sorted list of tasks.

**Request:**
- **Query Parameters:**
  ```
  GET /api/v1/tasks?status=NEW,IN_PROGRESS&priority=HIGH&due_date_from=2024-01-01&due_date_to=2024-12-31&limit=20&offset=0&sort=created_at:DESC&search=urgent
  ```

**Response (200 OK):**
```
{
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Buy groceries",
      "description": "Milk, eggs, bread",
      "due_date": "2024-01-20",
      "priority": "HIGH",
      "status": "NEW",
      "version": 1,
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z"
    },
    { /* more tasks */ }
  ],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total": 150,
    "has_more": true
  }
}
```

**Error Responses:**
- **400 Bad Request:** Invalid filter values (e.g., invalid date format, invalid status enum)
- **429 Too Many Requests:** Rate limit exceeded (>1000 req/min)
- **500 Internal Server Error:** Unexpected server error

**Acceptance Criteria:**
- AC1: Soft-deleted tasks (deleted_at IS NOT NULL) excluded from results
- AC2: Pagination metadata includes total count, has_more flag
- AC3: Default sort order is created_at DESC
- AC4: Filters combined with AND logic; comma-separated values use OR logic
- AC5: Search performs case-insensitive substring match on title and description
- AC6: Empty result set returns 200 OK with empty data array

---

#### 3. GET /api/v1/tasks/{id} — Retrieve Task

**Purpose:** Retrieve a single task by ID.

**Request:**
```
GET /api/v1/tasks/550e8400-e29b-41d4-a716-446655440000
```

**Response (200 OK):**
```
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Buy groceries",
  "description": "Milk, eggs, bread",
  "due_date": "2024-01-20",
  "priority": "HIGH",
  "status": "NEW",
  "version": 1,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

**Error Responses:**
- **404 Not Found:** Task does not exist or is soft-deleted
- **429 Too Many Requests:** Rate limit exceeded (>1000 req/min)
- **500 Internal Server Error:** Unexpected server error

**Acceptance Criteria:**
- AC1: Soft-deleted tasks return 404 Not Found
- AC2: Invalid UUID format returns 400 Bad Request

---

#### 4. PATCH /api/v1/tasks/{id} — Update Task

**Purpose:** Update task fields (status, priority, description, due_date) with optimistic locking.

**Request:**
- **Headers:** `Content-Type: application/json`
- **Body:**
  ```
  {
    "status": "IN_PROGRESS",
    "priority": "MEDIUM",
    "description": "Updated description",
    "due_date": "2024-01-25",
    "version": 1
  }
  ```

**Response (200 OK):**
```
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Buy groceries",
  "description": "Updated description",
  "due_date": "2024-01-25",
  "priority": "MEDIUM",
  "status": "IN_PROGRESS",
  "version": 2,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:35:00Z"
}
```

**Error Responses:**
- **400 Bad Request:** Invalid field values, invalid state transition
- **404 Not Found:** Task does not exist or is soft-deleted
- **409 Conflict:** Version mismatch (optimistic lock conflict)
- **429 Too Many Requests:** Rate limit exceeded (>100 req/min)
- **500 Internal Server Error:** Unexpected server error

**Acceptance Criteria:**
- AC1: Only provided fields are updated; omitted fields are unchanged
- AC2: Version field is required; mismatch returns 409 Conflict
- AC3: Version is incremented on successful update
- AC4: updated_at timestamp is set to current UTC time
- AC5: State transitions are validated against state machine
- AC6: Soft-deleted tasks cannot be updated (return 404)

---

#### 5. DELETE /api/v1/tasks/{id} — Soft-Delete Task

**Purpose:** Mark a task as deleted (soft-delete); task is hidden from queries but retained for 30 days.

**Request:**
```
DELETE /api/v1/tasks/550e8400-e29b-41d4-a716-446655440000
```

**Response (204 No Content):**
```
(empty body)
```

**Error Responses:**
- **404 Not Found:** Task does not exist or is already soft-deleted
- **429 Too Many Requests:** Rate limit exceeded (>100 req/min)
- **500 Internal Server Error:** Unexpected server error

**Acceptance Criteria:**
- AC1: Task status is set to DELETED, deleted_at is set to current UTC time
- AC2: Task is hidden from GET /tasks and GET /tasks/{id} (returns 404)
- AC3: Soft-deleted tasks are retained in database for 30 days
- AC4: After 30 days, soft-deleted tasks are permanently purged (via background job)
- AC5: Idempotent: deleting an already-deleted task returns 404

---

## CONCURRENCY & CONSISTENCY MODEL

### Consistency Guarantees

The API provides **strong consistency** for all operations:

- **Read-after-write:** After creating or updating a task, subsequent reads immediately reflect the change
- **Atomic updates:** Each PATCH operation is atomic; partial updates are not possible
- **No eventual consistency:** All operations are synchronous; no asynchronous replication or eventual consistency windows

### Optimistic Locking Strategy

To prevent lost writes during concurrent updates, the API uses **optimistic locking** with a version field:

**Mechanism:**
1. Client retrieves a task (e.g., GET /tasks/{id}); response includes `version: 1`
2. Client modifies the task and sends PATCH /tasks/{id} with `version: 1` in the request body
3. Server checks if the current version in the database matches the provided version
4. If versions match, the update is applied and version is incremented to 2
5. If versions don't match (another client updated the task), the server returns **409 Conflict** with error code `CONFLICT`
6. Client must retry: fetch the latest task (version 2), merge changes, and retry PATCH with version 2

**Error Response (409 Conflict):**
```
{
  "error": {
    "code": "CONFLICT",
    "message": "Task was modified by another client. Fetch the latest version and retry.",
    "details": {
      "current_version": 2,
      "provided_version": 1
    }
  },
  "timestamp": "2024-01-15T10:35:00Z",
  "request_id": "req-12345"
}
```

**Rationale:**
- Optimistic locking is simpler than pessimistic locking (no locks held during client processing)
- Suitable for low-contention scenarios (most tasks are not updated concurrently)
- If contention becomes high, pessimistic locking can be added later

### Isolation Level

SQLite transactions use **SERIALIZABLE** isolation level (SQLite's default for transactions):

- **Dirty reads:** Not possible; transactions see committed data only
- **Non-repeatable reads:** Not possible; transaction sees consistent snapshot
- **Phantom reads:** Not possible; transaction sees consistent snapshot

### Transaction Boundaries

**Single-statement transactions:**
- Each API operation (POST, PATCH, DELETE) is wrapped in a single database transaction
- Transaction commits on success; rolls back on validation error or database error
- No multi-statement transactions across API calls

**Example (PATCH /tasks/{id}):**
1. BEGIN TRANSACTION
2. SELECT task WHERE id = ? AND version = ? (check version)
3. UPDATE task SET status = ?, version = version + 1, updated_at = NOW() WHERE id = ?
4. COMMIT (or ROLLBACK if version mismatch)

---

## ERROR HANDLING & VALIDATION

### Validation Layers

**Layer 1: Input Validation (HTTP Request)**
- Content-Type must be application/json
- Request body must be valid JSON
- Required fields must be present
- Field types must match (e.g., due_date must be a string in ISO 8601 format)

**Layer 2: Field Validation (Business Rules)**
- title: 1-255 characters, non-empty after trim
- description: max 2000 characters
- due_date: valid ISO 8601 date, must be >= today
- priority: one of LOW, MEDIUM, HIGH
- status: one of NEW, IN_PROGRESS, COMPLETED, ARCHIVED, DELETED

**Layer 3: Business Logic Validation**
- State transitions must be allowed per state machine
- Version field must match current version (optimistic locking)
- Task must exist and not be soft-deleted

### Error Code Catalog

| Error Code | HTTP Status | Meaning | Example |
|-----------|-------------|---------|---------|
| INVALID_TITLE | 400 | Title is missing, empty, or exceeds 255 chars | `"title": ""` |
| INVALID_DESCRIPTION | 400 | Description exceeds 2000 chars | `"description": "..."` (>2000 chars) |
| INVALID_DUE_DATE | 400 | Due date is invalid format or in the past | `"due_date": "2023-01-01"` |
| INVALID_PRIORITY | 400 | Priority is not one of LOW, MEDIUM, HIGH | `"priority": "URGENT"` |
| INVALID_STATUS | 400 | Status is not a valid state | `"status": "UNKNOWN"` |
| INVALID_STATE_TRANSITION | 400 | State transition is not allowed | Transition from NEW to COMPLETED |
| INVALID_JSON | 400 | Request body is not valid JSON | Malformed JSON |
| MISSING_REQUIRED_FIELD | 400 | Required field is missing | Missing `title` in POST request |
| NOT_FOUND | 404 | Task does not exist or is soft-deleted | GET /tasks/invalid-id |
| CONFLICT | 409 | Version mismatch (optimistic lock conflict) | PATCH with stale version |
| IDEMPOTENCY_KEY_CONFLICT | 409 | Same idempotency key with different request body | POST with same key, different title |
| RATE_LIMIT_EXCEEDED | 429 | Too many requests | >100 POST requests/min |
| INTERNAL_SERVER_ERROR | 500 | Unexpected server error | Database connection failure |

### Validation Error Response Format

**Example (400 Bad Request with field-level errors):**
```
{
  "error": {
    "code": "INVALID_TITLE",
    "message": "Validation failed",
    "details": {
      "field": "title",
      "reason": "Title must be between 1 and 255 characters"
    }
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req-12345"
}
```

---

## NON-FUNCTIONAL REQUIREMENTS

### Performance Targets

| Metric | Target | Measurement | Notes |
|--------|--------|-------------|-------|
| **API Latency (p95)** | <200ms | All endpoints combined | Measured end-to-end (request received to response sent) |
| **API Latency (p99)** | <500ms | All endpoints combined | Tail latency; acceptable for occasional slow requests |
| **Throughput** | 1,000 concurrent users | Sustained load test | 1,000 concurrent connections; each user makes 1 request every 5 seconds |
| **List endpoint latency (p95)** | <200ms | GET /tasks with 10,000 tasks | Pagination with limit=20 |
| **Create endpoint latency (p95)** | <100ms | POST /tasks | Simple insert operation |

### Availability & Reliability

| Metric | Target | Measurement | Notes |
|--------|--------|-------------|-------|
| **Uptime SLA** | 99.5% | Monthly | Allows ~3.6 hours downtime per month |
| **Error Rate** | <0.1% | 5xx errors / total requests | Excludes 4xx client errors |
| **Data Loss** | Zero | Incidents per year | All data persisted to disk; no in-memory-only data |
| **Recovery Time (RTO)** | <5 minutes | Time to restore service after failure | Restart application; SQLite file is persistent |
| **Recovery Point (RPO)** | <1 minute | Data loss window | SQLite fsync on every transaction commit |

### Scalability

| Dimension | Limit | Notes |
|-----------|-------|-------|
| **Concurrent Users** | 1,000 | Sustained load; each user makes 1 request every 5 seconds |
| **Total Tasks** | 1,000,000 | Database size ~500MB (assuming 500 bytes per task) |
| **Requests per Second** | 200 | 1,000 concurrent users × 1 request per 5 seconds |
| **Database File Size** | 10GB | SQLite practical limit; beyond this, migrate to PostgreSQL |

### Security Requirements

| Requirement | Target | Implementation |
|-------------|--------|-----------------|
| **HTTPS** | Mandatory | All API endpoints served over HTTPS; HTTP redirects to HTTPS |
| **TLS Version** | 1.2+ | Disable TLS 1.0, 1.1 |
| **Cipher Suites** | Modern | Use strong cipher suites; disable weak ciphers |
| **CORS** | Restricted | Allow requests from known client origins only (configurable) |
| **Rate Limiting** | Per-IP | 100 POST/min, 1000 GET/min per IP address |
| **Input Validation** | Strict | All inputs validated; no SQL injection, XSS, or command injection |
| **Error Messages** | Non-leaky | Error messages do not reveal internal system details |

### Compliance & Data Retention

| Requirement | Target | Implementation |
|-------------|--------|-----------------|
| **Data Retention** | 30 days (soft-delete) | Soft-deleted tasks retained for 30 days; permanent purge after 30 days |
| **Audit Trail** | Implicit | created_at, updated_at, deleted_at timestamps provide audit trail |
| **GDPR Compliance** | Right to deletion | Soft-delete allows recovery; permanent purge after 30 days |
| **Data Encryption** | At-rest (optional) | SQLite database file can be encrypted using SQLCipher (future enhancement) |

---

## SECURITY ARCHITECTURE

### Authentication & Authorization

**Decision:** No authentication or authorization required.

**Rationale:** Per product guardrails, the API is designed for internal use or prototype deployment. No user accounts, login, or access control are implemented. All clients have equal access to all tasks.

**Future Enhancement:** If multi-tenancy or user-scoped tasks are required, add:
- JWT-based authentication (Bearer token in Authorization header)
- User ID claim in JWT; filter tasks by user_id
- RBAC for task ownership (only task creator can update/delete)

### Input Validation & Injection Prevention

**SQL Injection Prevention:**
- All database queries use parameterized statements (prepared statements)
- No string concatenation in SQL queries
- ORM (Hibernate) handles query building safely

**XSS Prevention:**
- API returns JSON; no HTML rendering
- Client is responsible for escaping/sanitizing data for display

**Command Injection Prevention:**
- No shell commands executed; no external process invocation
- All operations are in-process

### Rate Limiting

**Implementation:**
- Rate limiting enforced per IP address
- POST endpoints: 100 requests/minute
- GET endpoints: 1,000 requests/minute
- DELETE endpoints: 100 requests/minute

**Response (429 Too Many Requests):**
```
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Please retry after 60 seconds.",
    "details": {
      "retry_after": 60
    }
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req-12345"
}
```

**Headers:**
- `X-RateLimit-Limit: 100` (requests per minute)
- `X-RateLimit-Remaining: 42` (requests remaining)
- `X-RateLimit-Reset: 1705318200` (Unix timestamp when limit resets)

### HTTPS & TLS

**Requirements:**
- All API endpoints served over HTTPS only
- HTTP requests redirected to HTTPS (301 Moved Permanently)
- TLS 1.2 or higher
- Strong cipher suites (no weak ciphers)
- Certificate validation enforced

**Implementation:**
- Spring Boot configured with SSL/TLS
- Certificate provided by deployment environment (e.g., Let's Encrypt, self-signed for dev)

### CORS (Cross-Origin Resource Sharing)

**Configuration:**
- CORS enabled for known client origins (configurable)
- Allowed methods: GET, POST, PATCH, DELETE
- Allowed headers: Content-Type, Idempotency-Key
- Credentials: Not allowed (no cookies/auth)

**Example Configuration:**
```
allowed_origins: ["https://app.example.com", "https://admin.example.com"]
allowed_methods: ["GET", "POST", "PATCH", "DELETE"]
allowed_headers: ["Content-Type", "Idempotency-Key"]
max_age: 3600
```

---

## OBSERVABILITY & MONITORING

### Logging Strategy

**Log Levels:**
- **ERROR:** Unexpected errors, exceptions, validation failures, database errors
- **WARN:** Deprecated API usage, rate limit warnings, slow queries (>500ms)
- **INFO:** API request/response summary, task state transitions, startup/shutdown
- **DEBUG:** Detailed request/response bodies, SQL queries, internal state changes

**Log Format:**
```
[timestamp] [level] [request_id] [logger_name] message
2024-01-15T10:30:00.123Z INFO req-12345 com.example.api.TaskController POST /api/v1/tasks - status=201, duration=45ms
```

**Log Destinations:**
- **Development:** Console (stdout)
- **Production:** File (rolling logs, 100MB per file, 10 files retained) + centralized logging (e.g., ELK, Splunk)

### Metrics & Monitoring

**Key Metrics:**

| Metric | Type | Labels | Target |
|--------|------|--------|--------|
| `http_requests_total` | Counter | method, endpoint, status | Track all requests |
| `http_request_duration_seconds` | Histogram | method, endpoint | p50, p95, p99 latencies |
| `http_requests_in_flight` | Gauge | method, endpoint | Current concurrent requests |
| `task_state_transitions_total` | Counter | from_state, to_state | Track state machine usage |
| `database_query_duration_seconds` | Histogram | query_type | SELECT, INSERT, UPDATE, DELETE latencies |
| `idempotency_key_cache_hits_total` | Counter | — | Idempotency key cache effectiveness |
| `soft_deleted_tasks_total` | Gauge | — | Number of soft-deleted tasks pending purge |

**Alerting Rules:**

| Alert | Condition | Action |
|-------|-----------|--------|
| High Error Rate | 5xx errors > 1% for 5 minutes | Page on-call engineer |
| High Latency | p95 latency > 500ms for 10 minutes | Page on-call engineer |
| Rate Limit Abuse | >10,000 rate-limited requests from single IP in 1 hour | Block IP, alert security |
| Database Error | Database connection failures for 2 consecutive attempts | Page on-call engineer |
| Disk Space | SQLite file > 8GB | Alert ops team; plan migration to PostgreSQL |

### Distributed Tracing

**Implementation:**
- Request ID generated for every API request (UUID)
- Request ID propagated through all logs and metrics
- Trace ID included in error responses for debugging

**Example:**
```
POST /api/v1/tasks
Request-ID: req-12345

Response:
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  ...
}

Logs:
[2024-01-15T10:30:00Z] INFO req-12345 POST /api/v1/tasks - status=201
[2024-01-15T10:30:00Z] DEBUG req-12345 INSERT INTO tasks (id, title, ...) VALUES (...)
```

### Health Checks

**Endpoint:** `GET /health`

**Response (200 OK):**
```
{
  "status": "UP",
  "components": {
    "database": {
      "status": "UP"
    },
    "diskSpace": {
      "status": "UP",
      "details": {
        "total": "100GB",
        "free": "50GB",
        "threshold": "10GB"
      }
    }
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Checks:**
- Database connectivity (SELECT 1)
- Disk space (SQLite file location)
- Memory usage

---

## DEPLOYMENT & OPERATIONS

### Deployment Topology

**Single-Instance Deployment (Development/Prototype):**
```
┌─────────────────────────────────────┐
│  Server (Linux/macOS/Windows)       │
│  ┌─────────────────────────────────┐│
│  │ Spring Boot JAR (port 8080)     ││
│  │ ┌───────────────────────────────┤│
│  │ │ SQLite Database File          ││
│  │ │ (tasks.db, local filesystem)  ││
│  │ └───────────────────────────────┤│
│  └─────────────────────────────────┘│
└─────────────────────────────────────┘
```

**Multi-Instance Deployment (Production):**
```
┌──────────────────────────────────────────────────────────┐
│  Load Balancer (nginx, HAProxy, or cloud LB)             │
│  - HTTPS termination                                     │
│  - Rate limiting per IP                                  │
│  - Health check polling                                  │
└────────────────┬─────────────────────────────────────────┘
                 │
    ┌────────────┼────────────┐
    ▼            ▼            ▼
┌────────┐  ┌────────┐  ┌────────┐
│Instance│  │Instance│  │Instance│
│   1    │  │   2    │  │   3    │
│(JAR)   │  │(JAR)   │  │(JAR)   │
│SQLite  │  │SQLite  │  │SQLite  │
└────────┘  └────────┘  └────────┘
    │            │            │
    └────────────┼────────────┘
                 │
         ┌───────▼────────┐
         │ Shared Storage │
         │ (NFS/S3/etc)   │
         │ tasks.db       │
         └────────────────┘
```

**[ASSUMPTION]** For multi-instance deployments, SQLite database file is stored on shared network storage (NFS, S3, or similar) accessible by all instances. This ensures data consistency across instances. Alternative: Each instance has its own SQLite file and uses a distributed consensus mechanism (e.g., Raft) to synchronize state (more complex; not recommended for prototype).

### Deployment Process

**Build:**
1. Clone repository
2. Run `mvn clean package` to build executable JAR
3. JAR includes embedded Tomcat and all dependencies

**Deploy:**
1. Copy JAR to server
2. Create `application.properties` file with configuration (database path, port, etc.)
3. Run `java -jar todo-api-1.0.0.jar`
4. Spring Boot automatically runs Flyway migrations on startup
5. API is ready to accept requests

**Configuration (application.properties):**
```
server.port=8080
server.ssl.enabled=true
server.ssl.key-store=/path/to/keystore.jks
server.ssl.key-store-password=password

spring.datasource.url=jdbc:sqlite:/data/tasks.db
spring.datasource.driver-class-name=org.sqlite.JDBC
spring.jpa.database-platform=org.hibernate.dialect.SQLiteDialect

logging.level.root=INFO
logging.level.com.example.api=DEBUG
```

### Scaling Strategy

**Vertical Scaling (Single Instance):**
- Increase server CPU/memory
- Increase JVM heap size (`-Xmx4g`)
- Optimize database indexes
- Suitable up to ~10,000 concurrent users

**Horizontal Scaling (Multiple Instances):**
- Deploy multiple instances behind load balancer
- Share SQLite database file on network storage
- Load balancer distributes requests across instances
- Suitable for >10,000 concurrent users

**Database Scaling (Beyond SQLite):**
- If SQLite becomes bottleneck (>10GB data, >1,000 writes/sec), migrate to PostgreSQL
- PostgreSQL supports replication, sharding, and higher throughput
- Migration path: Export SQLite data, import into PostgreSQL, update connection string

### Backup & Recovery

**Backup Strategy:**
- SQLite database file backed up daily to off-site storage (S3, cloud backup service)
- Backup includes full database snapshot
- Retention: 30 days of daily backups

**Recovery Procedure:**
1. Stop API instances
2. Restore SQLite database file from backup
3. Restart API instances
4. Verify data integrity (run health checks)

**RTO/RPO:**
- RTO (Recovery Time Objective): <5 minutes (restore from backup, restart instances)
- RPO (Recovery Point Objective): <1 day (daily backups)

### Monitoring & Alerting

**Monitoring Stack:**
- Prometheus for metrics collection
- Grafana for dashboards
- AlertManager for alerting

**Key Dashboards:**
- API latency (p50, p95, p99)
- Error rate (5xx errors)
- Throughput (requests/sec)
- Database size and growth
- Concurrent users

---

## DATA RETENTION & COMPLIANCE

### Soft-Delete Retention Policy

**Retention Window:** 30 days

**Process:**
1. When task is deleted (DELETE /tasks/{id}), status is set to DELETED and deleted_at is set to current timestamp
2. Task is hidden from all queries (GET /tasks, GET /tasks/{id} return 404)
3. After 30 days, task is permanently purged from database (via background job)

**Background Job (Purge Soft-Deleted Tasks):**
- Runs daily at 2:00 AM UTC
- Deletes all tasks where deleted_at < NOW() - 30 days
- Logs number of tasks purged
- Alerts if purge fails

**Implementation:**
```
@Scheduled(cron = "0 2 * * * UTC")
public void purgeSoftDeletedTasks() {
  LocalDateTime cutoffDate = LocalDateTime.now().minusDays(30);
  int purged = taskRepository.deleteByDeletedAtBefore(cutoffDate);
  logger.info("Purged {} soft-deleted tasks", purged);
}
```

### GDPR Compliance

**Right to Deletion:**
- Users can request deletion of their tasks via DELETE /tasks/{id}
- Soft-delete allows recovery within 30 days
- After 30 days, permanent purge ensures data is unrecoverable

**Data Portability:**
- Users can export their tasks via GET /tasks (returns all tasks in JSON format)
- No built-in export endpoint; clients can fetch and serialize

**Audit Trail:**
- created_at, updated_at, deleted_at timestamps provide audit trail
- Implicit history of task lifecycle

### Data Encryption

**At-Rest Encryption (Optional Enhancement):**
- SQLite database file can be encrypted using SQLCipher
- Requires additional configuration and performance overhead
- Recommended for production deployments handling sensitive data

**In-Transit Encryption:**
- All API endpoints served over HTTPS (TLS 1.2+)
- Data encrypted in transit

---

## MIGRATION & ROLLOUT STRATEGY

### Phased Rollout

**Phase 1: Internal Testing (Week 1)**
- Deploy to internal staging environment
- Run smoke tests, load tests, security tests
- Validate against acceptance criteria

**Phase 2: Beta Release (Week 2-3)**
- Deploy to production with limited traffic (10% of requests)
- Monitor metrics, error rates, latency
- Gather feedback from early adopters

**Phase 3: General Availability (Week 4)**
- Increase traffic to 100%
- Monitor for issues
- Publish documentation and API reference

### Backward Compatibility

**API Versioning:**
- Current version: `/api/v1/tasks`
- Future breaking changes: `/api/v2/tasks`
- Clients can opt-in to new versions without forced migration

**Database Migrations:**
- Flyway manages schema migrations
- Migrations are versioned and applied automatically on startup
- Rollback: Revert to previous version, Flyway will not re-apply migrations

### Rollback Plan

**If Critical Issues Detected:**
1. Revert to previous JAR version
2. Restart API instances
3. Flyway will not re-apply migrations (idempotent)
4. Data remains intact; no data loss

**If Database Corruption Detected:**
1. Stop API instances
2. Restore SQLite database from backup
3. Restart API instances
4. Investigate root cause

---

## OPEN QUESTIONS & FUTURE CONSIDERATIONS

### Unresolved Questions

1. **Multi-Tenancy:** Should tasks be scoped to users/organizations? Current design assumes single-tenant (all tasks shared). If multi-tenancy is required, add user_id/org_id fields and authentication.

2. **Task Relationships:** Should tasks support parent-child relationships (subtasks)? Current design treats tasks as independent. If hierarchies are required, add parent_id field and recursive queries.

3. **Bulk Operations:** Should the API support bulk create/update/delete? Current design supports single-task operations. If bulk operations are required, add POST /tasks/bulk, PATCH /tasks/bulk endpoints.

4. **Webhooks/Events:** Should the API emit events when tasks are created/updated/deleted? Current design is synchronous. If event streaming is required, add webhook support or message queue integration.

5. **Custom Fields:** Should tasks support custom fields (user-defined metadata)? Current design has fixed fields. If custom fields are required, add JSON metadata column or separate key-value table.

6. **Audit Trail:** Should the API maintain detailed audit trail (who changed what, when)? Current design has implicit audit via timestamps. If detailed audit is required, add audit_log table.

### Future Enhancements

1. **Caching:** Add Redis cache for frequently accessed queries (list tasks by status) if latency exceeds targets
2. **Full-Text Search:** Enhance search with Elasticsearch for better relevance and performance
3. **Analytics:** Add analytics endpoint to track task completion rates, cycle time, etc.
4. **Notifications:** Add webhook support to notify external systems of task state changes
5. **Integrations:** Add OAuth2 support for third-party integrations (e.g., Slack, Teams)
6. **Mobile App:** Build native mobile app (iOS/Android) consuming the API
7. **GraphQL:** Add GraphQL endpoint as alternative to REST API
8. **Database Migration:** Migrate from SQLite to PostgreSQL for higher scale

### Technology Debt & Maintenance

1. **Dependency Updates:** Keep Spring Boot, Hibernate, and other dependencies up-to-date for security patches
2. **Code Quality:** Establish code review process, automated testing, and static analysis
3. **Documentation:** Maintain API documentation (OpenAPI/Swagger) and keep it in sync with implementation
4. **Performance Optimization:** Monitor metrics and optimize slow queries, add indexes as needed
5. **Security Audits:** Conduct regular security audits and penetration testing

---

## APPENDIX: GLOSSARY

| Term | Definition |
|------|-----------|
| **Soft-Delete** | Marking a record as deleted without physically removing it from the database; allows recovery and audit trail |
| **Optimistic Locking** | Concurrency control mechanism using version numbers; detects conflicts but doesn't prevent them |
| **Idempotency** | Property of an operation that produces the same result regardless of how many times it is executed |
| **State Machine** | Formal model of task lifecycle with defined states and allowed transitions |
| **Pagination** | Dividing large result sets into smaller pages for efficient retrieval |
| **Rate Limiting** | Restricting number of requests from a client within a time window |
| **ACID** | Atomicity, Consistency, Isolation, Durability; guarantees of database transactions |
| **CORS** | Cross-Origin Resource Sharing; mechanism for allowing cross-origin requests |
| **TLS** | Transport Layer Security; cryptographic protocol for secure communication |
| **UUID** | Universally Unique Identifier; 128-bit identifier with extremely low collision probability |
| **REST** | Representational State Transfer; architectural style for web APIs |
| **JSON** | JavaScript Object Notation; lightweight data interchange format |
| **HTTP** | HyperText Transfer Protocol; application-layer protocol for web communication |

---

## APPENDIX: REFERENCES

- [Spring Boot Documentation](https://spring.io/projects/spring-boot)
- [SQLite Documentation](https://www.sqlite.org/docs.html)
- [REST API Best Practices](https://restfulapi.net/)
- [HTTP Status Codes](https://httpwg.org/specs/rfc7231.html#status.codes)
- [JSON Schema](https://json-schema.org/)
- [OWASP Security Guidelines](https://owasp.org/)
- [Flyway Database Migrations](https://flywaydb.org/)

---

**Document End**