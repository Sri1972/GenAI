# TECHNICAL REQUIREMENTS DOCUMENT (TRD)
## Internal Notes App with Tags and Search

**Document Version:** 1.0  
**Last Updated:** [Current Date]  
**Status:** Ready for Development  
**Owner:** Engineering Leadership

---

## TABLE OF CONTENTS

1. [Architecture Overview](#architecture-overview)
2. [Technology Stack](#technology-stack)
3. [Data Model & Persistence](#data-model--persistence)
4. [Service Boundaries & API Design](#service-boundaries--api-design)
5. [Authentication & Authorization](#authentication--authorization)
6. [Search & Discovery](#search--discovery)
7. [Non-Functional Requirements](#non-functional-requirements)
8. [Deployment & Operations](#deployment--operations)
9. [Security & Compliance](#security--compliance)
10. [Observability & Monitoring](#observability--monitoring)
11. [Assumptions & Open Questions](#assumptions--open-questions)
12. [Acceptance Criteria](#acceptance-criteria)

---

## ARCHITECTURE OVERVIEW

### System Context

This is a **single-organization, single-tenant internal application** designed for a mid-market organization (100–1000 employees) to centralize team note-taking with tagging and search capabilities.

**Key Architectural Decisions:**

1. **Monolithic Deployment** — All logic (API, search, auth) runs in a single backend service. No microservices, no separate search cluster. Rationale: Single-tenant scope, team-scale usage, and operational simplicity outweigh the complexity of distributed systems.

2. **Client-Server Architecture** — Browser-based frontend communicates with a single REST API backend. No real-time sync, no WebSocket complexity. Rationale: Notes are not collaborative (no simultaneous editing); eventual consistency is acceptable.

3. **Embedded Search** — Full-text search is handled by the database (SQLite FTS5 or equivalent), not a separate search service (Elasticsearch, Meilisearch). Rationale: Single-tenant, team-scale data volume does not justify operational overhead of a dedicated search cluster.

4. **No Authentication Layer** — All users within the organization are trusted; no login, no session management, no OAuth. Access control is enforced at the **data layer** (all notes visible to all authenticated users within the org). Rationale: This is an internal tool; the organization's network perimeter provides the security boundary. Adding auth would increase complexity without proportional security benefit for this use case.

   > **[ASSUMPTION]** This product is deployed behind the organization's VPN or firewall. External access is not in scope. If external access becomes a requirement, authentication must be added in a future phase.

5. **Single Database** — All data (notes, tags, users, audit logs) stored in a single SQLite database. No sharding, no replication. Rationale: Single-tenant, team-scale data volume; SQLite is sufficient for 100–1000 users creating 5–10 notes per week.

   > **[ASSUMPTION]** Data volume at 6 months: ~500 notes/month × 6 months = 3,000 notes. Audit logs: ~10 actions per note (create, edits, views) = 30,000 audit entries. SQLite handles this comfortably.

### High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         Browser (Frontend)                       │
│  - React SPA (Vite)                                              │
│  - Note creation, editing, search UI                             │
│  - Tag management                                                │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP/REST
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Backend API (Spring Boot)                     │
│  - Note CRUD endpoints                                           │
│  - Search & filtering                                            │
│  - Tag management                                                │
│  - Audit logging                                                 │
│  - User context (from HTTP headers or env)                       │
└────────────────────────┬────────────────────────────────────────┘
                         │ SQL
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SQLite Database                               │
│  - notes table                                                   │
│  - tags table                                                    │
│  - note_tags junction table                                      │
│  - audit_logs table                                              │
│  - users table (minimal: id, email, created_at)                 │
└─────────────────────────────────────────────────────────────────┘
```

### Service Boundaries

**Single Backend Service** — Responsible for:
- **Note Management** — Create, read, update, delete notes
- **Tag Management** — Create, list, and apply tags to notes
- **Search & Filtering** — Full-text search, tag-based filtering, date range filtering
- **Audit Logging** — Log all create/read/update/delete actions with user context
- **User Context** — Resolve current user from request headers (e.g., `X-User-Email` or environment variable)

**No External Dependencies** — This product does NOT integrate with:
- Email, Slack, or other messaging platforms
- External authentication providers (OAuth, LDAP, SAML)
- Cloud storage (S3, Google Drive)
- Analytics or monitoring services (beyond local logging)

---

## TECHNOLOGY STACK

### Frontend

| Category | Choice | Version | Rationale |
|----------|--------|---------|-----------|
| **Language** | TypeScript | Latest | Type safety for a team-maintained codebase |
| **Framework** | React | 18+ | Component-based UI, large ecosystem, team familiarity |
| **Build Tool** | Vite | Latest | Fast dev server, minimal config, modern bundling |
| **Styling** | Tailwind CSS | Latest | Utility-first CSS, rapid UI development, no custom CSS |
| **HTTP Client** | Fetch API (native) | — | No external dependency; sufficient for simple REST calls |
| **State Management** | React Context + useState | — | Lightweight; no Redux/Zustand needed for this scope |
| **Testing** | Manual testing + browser console | — | Prototype stage; automated tests out of scope |

**Why Not X?**
- **Vue / Angular** — React is the team's assumed baseline; no reason to diverge.
- **Next.js / Remix** — Server-side rendering not needed; static SPA is simpler.
- **Redux / Zustand** — State is simple (notes list, current note, search query); Context is sufficient.
- **Axios / React Query** — Fetch API is native and sufficient; no need for abstraction layer.

### Backend

| Category | Choice | Version | Rationale |
|----------|--------|---------|-----------|
| **Language** | Java | 17+ | Mature, performant, excellent for REST APIs; Spring Boot ecosystem |
| **Framework** | Spring Boot | 3.x | Rapid REST API development, built-in security, dependency injection |
| **Build Tool** | Maven | 3.9+ | Standard Java build tool; no learning curve |
| **HTTP Server** | Embedded Tomcat (Spring Boot default) | — | No separate server deployment needed |
| **Database Driver** | JDBC (SQLite) | Latest | Native SQLite support; no ORM overhead for this scope |
| **Logging** | SLF4J + Logback | Latest | Standard Java logging; console output sufficient for prototype |

**Why Not X?**
- **Python (FastAPI)** — Java/Spring is the assumed team baseline; no reason to diverge.
- **Node.js (Express)** — Java is more suitable for a team-scale backend; better performance, type safety.
- **Go** — Overkill for single-service, single-tenant scope; Java is more maintainable long-term.
- **Hibernate / JPA ORM** — SQLite + JDBC is simpler for this data model; no complex relationships justify ORM overhead.

### Database

| Category | Choice | Version | Rationale |
|----------|--------|---------|-----------|
| **Database** | SQLite | 3.40+ | Single-tenant, team-scale data; no server setup; full-text search (FTS5) built-in |
| **File Location** | Local filesystem (backend server) | — | Simple backup; no managed database service needed |
| **Full-Text Search** | SQLite FTS5 | Built-in | Native full-text search; no separate search service |
| **Backup Strategy** | Daily file-level backup to shared storage | — | Simple, reliable; no database-specific tooling needed |

**Why Not X?**
- **PostgreSQL** — Overkill for single-tenant, team-scale data; adds operational complexity (server setup, backups, monitoring).
- **DynamoDB / Cloud Firestore** — Requires cloud infrastructure; not justified for internal tool.
- **Elasticsearch / Meilisearch** — Separate search service adds operational burden; SQLite FTS5 is sufficient.
- **MongoDB** — Document database not needed; relational schema is clearer for notes + tags + audit logs.

### Deployment & Hosting

| Category | Choice | Rationale |
|----------|--------|-----------|
| **Hosting** | On-premises or private cloud (behind VPN) | Internal tool; no public internet exposure |
| **Container** | Docker (optional) | Simplifies deployment; not mandatory for prototype |
| **Orchestration** | None (single instance) | No Kubernetes, no load balancing; single backend instance sufficient |
| **Reverse Proxy** | Nginx or Apache (optional) | Can sit in front of Spring Boot for SSL termination, static file serving |

**Why Not X?**
- **AWS / Azure / GCP** — Not justified for internal tool; on-premises is simpler and cheaper.
- **Kubernetes** — Single instance does not need orchestration; adds operational overhead.
- **Serverless (Lambda, Cloud Functions)** — Stateful database connection management is simpler with a persistent server.

### Summary Table

| Layer | Technology | Version | Notes |
|-------|-----------|---------|-------|
| **Frontend** | React + Vite + TypeScript + Tailwind | Latest | Single-page app; no build complexity |
| **Backend** | Spring Boot + Java | 3.x / 17+ | Monolithic REST API |
| **Database** | SQLite + FTS5 | 3.40+ | Embedded, file-based; full-text search built-in |
| **Logging** | SLF4J + Logback | Latest | Console output; no external service |
| **Deployment** | Docker (optional) + Nginx (optional) | Latest | On-premises or private cloud |

---

## DATA MODEL & PERSISTENCE

### Core Entities

#### 1. **Note**
Represents a single note created by a user.

| Field | Type | Constraints | Purpose |
|-------|------|-----------|---------|
| `id` | UUID | Primary Key | Unique identifier |
| `title` | String (255 chars) | NOT NULL | Note title; searchable |
| `content` | Text | NOT NULL | Note body; searchable via FTS5 |
| `created_by` | String (email) | NOT NULL, FK → User | Creator's email; used for audit and filtering |
| `created_at` | Timestamp | NOT NULL, default=NOW | Creation time; used for sorting and filtering |
| `updated_at` | Timestamp | NOT NULL, default=NOW | Last modification time; updated on every edit |
| `updated_by` | String (email) | NOT NULL | User who last modified the note |
| `is_deleted` | Boolean | default=false | Soft delete flag for audit compliance |
| `deleted_at` | Timestamp | Nullable | Timestamp of deletion (if soft-deleted) |
| `deleted_by` | String (email) | Nullable | User who deleted the note |

**Rationale for Soft Delete:**
- Audit compliance requires tracking who deleted what and when.
- Hard delete would lose this information.
- Soft delete allows recovery if needed.
- Queries must filter `WHERE is_deleted = false` by default.

**Rationale for `updated_by`:**
- Audit trail requires knowing who made each change.
- Supports "edited by X at Y" UI display.

#### 2. **Tag**
Represents a user-created tag used to organize notes.

| Field | Type | Constraints | Purpose |
|-------|------|-----------|---------|
| `id` | UUID | Primary Key | Unique identifier |
| `name` | String (50 chars) | NOT NULL, UNIQUE | Tag name (e.g., "bug", "decision", "meeting") |
| `created_at` | Timestamp | NOT NULL, default=NOW | Creation time |
| `usage_count` | Integer | default=0 | Number of notes with this tag; used for analytics |

**Rationale:**
- Tags are **organization-wide, shared taxonomy** — not per-user.
- `UNIQUE` constraint prevents duplicate tag names.
- `usage_count` is denormalized for performance (avoids COUNT query on every tag list).
- Tags are **ad-hoc, user-created** (not admin-managed) — users can create tags on-the-fly when creating/editing notes.

#### 3. **Note_Tag** (Junction Table)
Maps notes to tags (many-to-many relationship).

| Field | Type | Constraints | Purpose |
|-------|------|-----------|---------|
| `note_id` | UUID | Primary Key (part 1), FK → Note | Reference to note |
| `tag_id` | UUID | Primary Key (part 2), FK → Tag | Reference to tag |
| `created_at` | Timestamp | NOT NULL, default=NOW | When this tag was applied to the note |

**Rationale:**
- Composite primary key ensures no duplicate tag assignments to a note.
- `created_at` tracks when a tag was applied (useful for audit).

#### 4. **User**
Minimal user record for audit and context.

| Field | Type | Constraints | Purpose |
|-------|------|-----------|---------|
| `email` | String (255 chars) | Primary Key | User's email; used as unique identifier |
| `created_at` | Timestamp | NOT NULL, default=NOW | First time user accessed the app |
| `last_seen_at` | Timestamp | Nullable | Last activity timestamp (for analytics) |

**Rationale:**
- Email is the primary key (no separate `id` needed).
- Minimal record; no password, no roles, no profile data.
- `last_seen_at` is optional, used for "active users" analytics.

#### 5. **AuditLog**
Immutable log of all actions for compliance and debugging.

| Field | Type | Constraints | Purpose |
|-------|------|-----------|---------|
| `id` | UUID | Primary Key | Unique identifier |
| `user_email` | String (255 chars) | NOT NULL | User who performed the action |
| `action` | Enum (CREATE, READ, UPDATE, DELETE) | NOT NULL | Type of action |
| `resource_type` | Enum (NOTE, TAG) | NOT NULL | What was acted upon |
| `resource_id` | UUID | NOT NULL | ID of the resource (note_id or tag_id) |
| `timestamp` | Timestamp | NOT NULL, default=NOW | When the action occurred |
| `changes` | JSON (optional) | Nullable | For UPDATE actions: old and new values (e.g., `{"title": {"old": "...", "new": "..."}}`) |
| `ip_address` | String (45 chars) | Nullable | Source IP (if available from request) |

**Rationale:**
- Immutable log; never updated or deleted.
- `action` enum prevents typos and enables filtering.
- `changes` JSON captures what changed (for UPDATE actions); useful for compliance audits.
- `ip_address` is optional; useful for security investigations.
- Retention: Keep all audit logs indefinitely (or per org policy).

### Data Relationships

```
User (email)
  ├─ 1:N ─→ Note (created_by, updated_by)
  └─ 1:N ─→ AuditLog (user_email)

Note (id)
  ├─ N:M ─→ Tag (via Note_Tag)
  └─ 1:N ─→ AuditLog (resource_id)

Tag (id)
  ├─ N:M ─→ Note (via Note_Tag)
  └─ 1:N ─→ AuditLog (resource_id)
```

### Full-Text Search Index

SQLite FTS5 virtual table for efficient full-text search:

**Virtual Table: `notes_fts`**
- Indexes: `title`, `content`
- Tokenizer: Default (whitespace-based)
- Triggers: Automatically updated when `notes` table is modified

**Rationale:**
- FTS5 enables phrase search, boolean operators, and relevance ranking.
- Virtual table is kept in sync with the main `notes` table via triggers.
- No separate search service needed.

### Query Patterns

**High-Frequency Queries:**

1. **Search notes by keyword** — `SELECT * FROM notes_fts WHERE notes_fts MATCH 'keyword' AND is_deleted = false`
2. **Filter notes by tag** — `SELECT n.* FROM notes n JOIN note_tags nt ON n.id = nt.note_id WHERE nt.tag_id = ? AND n.is_deleted = false`
3. **List all tags** — `SELECT * FROM tags ORDER BY usage_count DESC`
4. **Get note by ID** — `SELECT * FROM notes WHERE id = ? AND is_deleted = false`
5. **Audit trail for a note** — `SELECT * FROM audit_logs WHERE resource_id = ? AND resource_type = 'NOTE' ORDER BY timestamp DESC`

**Indexes:**
- Primary keys (automatic)
- `notes.created_by` (for filtering by creator)
- `notes.created_at` (for date range filtering)
- `notes.is_deleted` (for soft delete filtering)
- `note_tags.tag_id` (for tag-based filtering)
- `audit_logs.resource_id` (for audit trail queries)
- `audit_logs.timestamp` (for time-range audit queries)

---

## SERVICE BOUNDARIES & API DESIGN

### REST API Endpoints

All endpoints return JSON. Base path: `/api/v1`

#### **Notes Resource**

| Method | Endpoint | Purpose | Request Body | Response | Status Codes |
|--------|----------|---------|--------------|----------|--------------|
| **POST** | `/notes` | Create a new note | `{ title, content, tags: [tag_names] }` | `{ id, title, content, created_by, created_at, tags }` | 201 Created, 400 Bad Request |
| **GET** | `/notes/{id}` | Retrieve a single note | — | `{ id, title, content, created_by, created_at, updated_at, updated_by, tags }` | 200 OK, 404 Not Found |
| **PUT** | `/notes/{id}` | Update a note | `{ title, content, tags: [tag_names] }` | `{ id, title, content, updated_at, updated_by, tags }` | 200 OK, 400 Bad Request, 404 Not Found |
| **DELETE** | `/notes/{id}` | Soft-delete a note | — | `{ id, deleted_at, deleted_by }` | 204 No Content, 404 Not Found |
| **GET** | `/notes` | List notes with search & filtering | Query params (see below) | `{ notes: [...], total_count, page, page_size }` | 200 OK, 400 Bad Request |

**Query Parameters for `GET /notes`:**

| Parameter | Type | Example | Purpose |
|-----------|------|---------|---------|
| `search` | String | `search=bug%20fix` | Full-text search on title + content |
| `tags` | CSV | `tags=bug,urgent` | Filter by tags (AND logic: notes with ALL specified tags) |
| `created_after` | ISO8601 | `created_after=2024-01-01T00:00:00Z` | Filter notes created after this date |
| `created_before` | ISO8601 | `created_before=2024-12-31T23:59:59Z` | Filter notes created before this date |
| `created_by` | Email | `created_by=sarah@org.com` | Filter notes created by a specific user |
| `page` | Integer | `page=1` | Page number (1-indexed); default=1 |
| `page_size` | Integer | `page_size=20` | Results per page; default=20, max=100 |
| `sort_by` | Enum | `sort_by=created_at` | Sort field: `created_at` (default), `updated_at`, `relevance` (only with search) |
| `sort_order` | Enum | `sort_order=desc` | Sort direction: `asc` or `desc` (default) |

**Response Example:**
```json
{
  "notes": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Database migration notes",
      "content": "Migrated from MySQL to PostgreSQL...",
      "created_by": "sarah@org.com",
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T14:22:00Z",
      "updated_by": "sarah@org.com",
      "tags": ["database", "migration", "completed"]
    }
  ],
  "total_count": 42,
  "page": 1,
  "page_size": 20
}
```

#### **Tags Resource**

| Method | Endpoint | Purpose | Request Body | Response | Status Codes |
|--------|----------|---------|--------------|----------|--------------|
| **GET** | `/tags` | List all tags | — | `{ tags: [...], total_count }` | 200 OK |
| **POST** | `/tags` | Create a new tag | `{ name }` | `{ id, name, usage_count, created_at }` | 201 Created, 400 Bad Request, 409 Conflict (duplicate) |
| **DELETE** | `/tags/{id}` | Delete a tag | — | — | 204 No Content, 404 Not Found, 409 Conflict (in use) |

**Response Example:**
```json
{
  "tags": [
    { "id": "...", "name": "bug", "usage_count": 12, "created_at": "2024-01-01T..." },
    { "id": "...", "name": "decision", "usage_count": 8, "created_at": "2024-01-02T..." }
  ],
  "total_count": 2
}
```

**Rationale for Tag Deletion:**
- Deleting a tag should fail (409 Conflict) if it's still applied to any notes.
- This prevents orphaned tag references and ensures data consistency.
- Users must first remove the tag from all notes before deleting it.

#### **Audit Logs Resource**

| Method | Endpoint | Purpose | Query Params | Response | Status Codes |
|--------|----------|---------|--------------|----------|--------------|
| **GET** | `/audit-logs` | List audit logs | `resource_type`, `resource_id`, `user_email`, `action`, `created_after`, `created_before`, `page`, `page_size` | `{ logs: [...], total_count, page }` | 200 OK, 400 Bad Request |

**Response Example:**
```json
{
  "logs": [
    {
      "id": "...",
      "user_email": "sarah@org.com",
      "action": "CREATE",
      "resource_type": "NOTE",
      "resource_id": "550e8400-e29b-41d4-a716-446655440000",
      "timestamp": "2024-01-15T10:30:00Z",
      "changes": null,
      "ip_address": "192.168.1.100"
    },
    {
      "id": "...",
      "user_email": "sarah@org.com",
      "action": "UPDATE",
      "resource_type": "NOTE",
      "resource_id": "550e8400-e29b-41d4-a716-446655440000",
      "timestamp": "2024-01-15T14:22:00Z",
      "changes": {
        "title": { "old": "Database notes", "new": "Database migration notes" }
      },
      "ip_address": "192.168.1.100"
    }
  ],
  "total_count": 2,
  "page": 1
}
```

**Access Control:**
- Audit logs are **read-only** and **admin-only** (see Authorization section).
- Non-admin users cannot access `/audit-logs`.

#### **User Context Endpoint** (Optional)

| Method | Endpoint | Purpose | Response | Status Codes |
|--------|----------|---------|----------|--------------|
| **GET** | `/me` | Get current user info | `{ email, created_at, last_seen_at }` | 200 OK |

**Rationale:**
- Allows frontend to display "logged in as" info.
- Useful for debugging user context issues.

### Error Handling

All error responses follow this format:

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Title is required",
    "details": {
      "field": "title"
    }
  }
}
```

**Common Error Codes:**

| Code | HTTP Status | Meaning |
|------|-------------|---------|
| `INVALID_REQUEST` | 400 | Malformed request or validation failure |
| `NOT_FOUND` | 404 | Resource does not exist |
| `CONFLICT` | 409 | Resource already exists (e.g., duplicate tag) or operation violates constraints |
| `UNAUTHORIZED` | 401 | User not authenticated (should not occur in this design) |
| `FORBIDDEN` | 403 | User lacks permission (e.g., non-admin accessing audit logs) |
| `INTERNAL_ERROR` | 500 | Server error |

### API Versioning

- Current version: `v1` (in URL path: `/api/v1`)
- Future versions (if needed) will use `/api/v2`, etc.
- No breaking changes to `v1` without a major version bump.

---

## AUTHENTICATION & AUTHORIZATION

### Authentication Model

**No Login Required** — This is an internal tool deployed behind the organization's VPN/firewall. All users within the network are trusted.

**User Identification:**
- Current user is identified via **HTTP header** or **environment variable**.
- Recommended header: `X-User-Email` (set by reverse proxy or SSO layer).
- Fallback: Environment variable `CURRENT_USER_EMAIL` (for testing/local development).

**Example Request:**
```
GET /api/v1/notes
X-User-Email: sarah@org.com
```

**Backend Responsibility:**
- Extract user email from header/env on every request.
- Validate that email is non-empty and well-formed.
- Return 400 Bad Request if user email is missing or invalid.
- Pass user email to all service methods for audit logging.

> **[ASSUMPTION]** The organization's reverse proxy (Nginx, Apache, or SSO layer) is responsible for setting the `X-User-Email` header. The backend trusts this header and does not validate it against an external directory.

### Authorization Model

**Role-Based Access Control (RBAC)** — Two roles:

| Role | Permissions | Notes |
|------|-------------|-------|
| **User** (default) | Create, read, update, delete own notes; read all notes; create/list tags; apply tags to notes | All authenticated users are "User" role |
| **Admin** | All User permissions + read audit logs; delete any note; delete tags | Determined by email whitelist (see below) |

**Admin Whitelist:**
- Admins are identified by email address.
- Whitelist is stored in environment variable: `ADMIN_EMAILS` (comma-separated).
- Example: `ADMIN_EMAILS=alex@org.com,admin@org.com`

**Access Control Rules:**

| Action | User | Admin | Notes |
|--------|------|-------|-------|
| Create note | ✓ | ✓ | Any authenticated user |
| Read own notes | ✓ | ✓ | Creator can always read their own notes |
| Read others' notes | ✓ | ✓ | All notes are visible to all users (no private notes) |
| Update own notes | ✓ | ✓ | Only creator can update their own notes |
| Update others' notes | ✗ | ✓ | Only admins can edit notes created by others |
| Delete own notes | ✓ | ✓ | Creator can soft-delete their own notes |
| Delete others' notes | ✗ | ✓ | Only admins can delete notes created by others |
| Create tag | ✓ | ✓ | Any authenticated user |
| List tags | ✓ | ✓ | All users can see all tags |
| Delete tag | ✗ | ✓ | Only admins can delete tags |
| Read audit logs | ✗ | ✓ | Only admins can access audit logs |
| Export audit logs | ✗ | ✓ | Only admins can export audit logs for compliance |

**Implementation:**
- Every endpoint checks user role before executing business logic.
- If user lacks permission, return 403 Forbidden.
- Audit log records the attempted action (even if denied).

**Example Authorization Check (pseudocode):**
```
PUT /api/v1/notes/{id}
  user_email = extract from X-User-Email header
  note = fetch from database
  
  if note.created_by != user_email AND user_email NOT IN ADMIN_EMAILS:
    return 403 Forbidden
  
  update note
  log audit entry
  return 200 OK
```

### Data Visibility

**All notes are visible to all authenticated users** — There are no private notes or team-scoped visibility.

**Rationale:**
- PRD states "team visibility" and "institutional knowledge" as goals.
- Restricting visibility would fragment the knowledge base.
- If future requirements demand private notes or team-scoped access, this can be added in a later phase (requires schema changes and authorization logic).

> **[ASSUMPTION]** If the organization later requires private notes or team-scoped access, the data model must be extended with a `visibility` field (e.g., `PUBLIC`, `TEAM`, `PRIVATE`) and authorization logic must be updated accordingly.

---

## SEARCH & DISCOVERY

### Full-Text Search

**Scope:**
- Search indexes: `title` and `content` fields of notes.
- Search does NOT index tags (tag filtering is handled separately).

**Search Behavior:**
- Case-insensitive.
- Phrase search supported: `"exact phrase"` returns notes containing the exact phrase.
- Boolean operators supported: `AND`, `OR`, `NOT` (SQLite FTS5 syntax).
- Wildcard search: `bug*` matches "bug", "bugs", "bugfix", etc.
- Relevance ranking: Results ranked by relevance (title matches weighted higher than content matches).

**Example Queries:**
- `search=database` — Notes containing "database" in title or content
- `search="database migration"` — Notes containing the exact phrase "database migration"
- `search=database AND migration` — Notes containing both "database" AND "migration"
- `search=bug NOT fixed` — Notes containing "bug" but NOT "fixed"

**API Endpoint:**
```
GET /api/v1/notes?search=database&page=1&page_size=20
```

**Response:**
- Results sorted by relevance (highest relevance first).
- If `sort_by=created_at` is specified, results are sorted by creation date instead (relevance ranking is ignored).

### Tag-Based Filtering

**Scope:**
- Filter notes by one or more tags.
- AND logic: A note must have ALL specified tags to be included in results.

**Example Queries:**
- `tags=bug` — Notes with tag "bug"
- `tags=bug,urgent` — Notes with BOTH "bug" AND "urgent" tags
- `tags=bug,urgent,high-priority` — Notes with ALL three tags

**API Endpoint:**
```
GET /api/v1/notes?tags=bug,urgent&page=1&page_size=20
```

**Combining Search and Tags:**
```
GET /api/v1/notes?search=database&tags=migration,completed&page=1&page_size=20
```
- Returns notes containing "database" in title/content AND tagged with both "migration" and "completed".

### Date Range Filtering

**Scope:**
- Filter notes by creation date.
- Supports `created_after` and `created_before` parameters.

**Example Queries:**
- `created_after=2024-01-01T00:00:00Z` — Notes created on or after Jan 1, 2024
- `created_before=2024-12-31T23:59:59Z` — Notes created on or before Dec 31, 2024
- `created_after=2024-01-01T00:00:00Z&created_before=2024-12-31T23:59:59Z` — Notes created in 2024

**API Endpoint:**
```
GET /api/v1/notes?created_after=2024-01-01T00:00:00Z&created_before=2024-12-31T23:59:59Z
```

### Creator Filtering

**Scope:**
- Filter notes by creator email.

**Example Query:**
```
GET /api/v1/notes?created_by=sarah@org.com
```

### Sorting

**Supported Sort Fields:**
- `created_at` (default) — Sort by note creation date
- `updated_at` — Sort by last modification date
- `relevance` — Sort by search relevance (only valid when `search` parameter is present)

**Sort Order:**
- `asc` — Ascending (oldest first)
- `desc` (default) — Descending (newest first)

**Example Queries:**
```
GET /api/v1/notes?sort_by=created_at&sort_order=asc  # Oldest first
GET /api/v1/notes?search=bug&sort_by=relevance&sort_order=desc  # Most relevant first
```

### Pagination

**Cursor-Based Pagination** (recommended for scalability):
- `page` — Page number (1-indexed); default=1
- `page_size` — Results per page; default=20, max=100

**Response Includes:**
- `total_count` — Total number of matching notes (across all pages)
- `page` — Current page number
- `page_size` — Results per page
- `has_next` — Boolean indicating if there are more pages

**Example:**
```
GET /api/v1/notes?search=database&page=2&page_size=20

Response:
{
  "notes": [...],
  "total_count": 150,
  "page": 2,
  "page_size": 20,
  "has_next": true
}
```

### Performance Targets

| Operation | Target Latency | Notes |
|-----------|-----------------|-------|
| Full-text search (1000 notes) | < 200ms | Includes database query + JSON serialization |
| Tag filtering (1000 notes) | < 100ms | Simple JOIN query |
| List all tags | < 50ms | Small result set |
| Pagination (20 results) | < 100ms | Offset-based query |

**Optimization Strategies:**
- Index on `notes.title`, `notes.content` (via FTS5 virtual table)
- Index on `note_tags.tag_id` for tag filtering
- Index on `notes.created_at` for date range filtering
- Limit `page_size` to 100 to prevent large result sets

---

## NON-FUNCTIONAL REQUIREMENTS

### Performance

#### Latency Targets

| Operation | Target | Measurement |
|-----------|--------|-------------|
| Create note | < 500ms | POST /notes |
| Retrieve single note | < 100ms | GET /notes/{id} |
| Update note | < 500ms | PUT /notes/{id} |
| Delete note | < 200ms | DELETE /notes/{id} |
| List notes (paginated, 20 results) | < 200ms | GET /notes?page=1&page_size=20 |
| Search notes (full-text, 1000 notes) | < 200ms | GET /notes?search=keyword |
| Filter by tags | < 100ms | GET /notes?tags=tag1,tag2 |
| List all tags | < 50ms | GET /tags |

**Measurement Method:**
- End-to-end latency from client request to response (includes network round-trip, database query, JSON serialization).
- Measured on a single backend instance with typical hardware (4 CPU cores, 8GB RAM).
- Excludes client-side rendering time.

#### Throughput

| Scenario | Target | Notes |
|----------|--------|-------|
| Concurrent users | 100+ | Single backend instance should handle 100 concurrent users without degradation |
| Requests per second | 50+ RPS | Peak load during business hours |
| Notes created per day | 500+ | Typical usage: 5–10 notes per user per week × 100 users |

#### Data Volume

| Metric | Estimate (6 months) | Estimate (1 year) |
|--------|---------------------|-------------------|
| Total notes | 3,000 | 6,000 |
| Total audit log entries | 30,000 | 60,000 |
| Database file size | < 100 MB | < 200 MB |

**Rationale:**
- SQLite can comfortably handle 10,000+ notes with proper indexing.
- No sharding or replication needed at this scale.

### Availability & Reliability

#### Uptime Target

- **99.5% uptime** (4.38 hours downtime per month)
- Measured over a calendar month
- Excludes planned maintenance windows (communicated in advance)

**Rationale:**
- Internal tool; not customer-facing; 99.5% is reasonable.
- Single instance (no redundancy); downtime is possible during deployments or hardware failures.

#### Failure Modes & Recovery

| Failure Mode | Impact | Recovery Strategy |
|--------------|--------|-------------------|
| Backend service crash | All users unable to access app | Automatic restart (systemd, Docker, or orchestration) |
| Database file corruption | Data loss or app unavailability | Restore from daily backup |
| Network connectivity loss | Users cannot reach backend | Depends on network infrastructure; out of scope |
| Disk full | Database cannot write; app fails | Monitoring alert; manual intervention to free disk space |

**Backup Strategy:**
- Daily file-level backup of SQLite database file.
- Backup stored on shared network storage (NAS, S3, or equivalent).
- Retention: Keep 30 days of daily backups.
- Recovery time objective (RTO): < 1 hour (restore from backup and restart service).
- Recovery point objective (RPO): < 24 hours (data loss limited to last backup).

#### Graceful Degradation

- No graceful degradation; app is all-or-nothing.
- If backend is unavailable, frontend displays "Service Unavailable" message.
- No offline mode or local caching.

### Scalability

#### Horizontal Scaling (Future)

- **Current Design:** Single backend instance + single SQLite database.
- **Future Scaling:** If organization grows beyond 1000 users or 10,000 notes:
  - Add load balancer in front of multiple backend instances.
  - Migrate SQLite to PostgreSQL (shared database for all instances).
  - Add caching layer (Redis) for frequently accessed data.
  - Consider separating search into a dedicated service (Elasticsearch).

#### Vertical Scaling (Current)

- Single backend instance can be scaled up (more CPU, more RAM) to handle increased load.
- SQLite performance degrades gracefully as data volume increases; no hard limits until 100,000+ notes.

### Security

#### Data Protection

- **Encryption at Rest:** SQLite database file should be stored on encrypted filesystem (e.g., LUKS, BitLocker, or cloud provider encryption).
- **Encryption in Transit:** All API communication over HTTPS (TLS 1.2+).
- **Data Retention:** Keep audit logs indefinitely (or per org policy); soft-deleted notes retained for 90 days before hard deletion (optional).

#### Access Control

- See [Authentication & Authorization](#authentication--authorization) section.
- All access decisions logged in audit trail.

#### Audit & Compliance

- All create/read/update/delete actions logged with user, timestamp, and changes.
- Audit logs are immutable and cannot be deleted by non-admins.
- Admins can export audit logs for compliance reporting.

### Observability

#### Logging

- **Log Level:** INFO (default), DEBUG (for troubleshooting)
- **Log Output:** Console (stdout/stderr); can be redirected to file or centralized logging service
- **Log Format:** Structured JSON (recommended) or plain text
- **Retention:** Keep logs for 30 days (or per org policy)

**Logged Events:**
- API request/response (method, path, status code, latency)
- Database operations (query, execution time)
- Errors and exceptions (stack trace, context)
- Audit events (user, action, resource, timestamp)

#### Metrics

- **Application Metrics:**
  - Request latency (p50, p95, p99)
  - Request throughput (requests per second)
  - Error rate (5xx, 4xx errors)
  - Database query latency
  - Cache hit rate (if caching is added)

- **System Metrics:**
  - CPU usage
  - Memory usage
  - Disk usage
  - Network I/O

- **Business Metrics:**
  - Daily active users (DAU)
  - Monthly active users (MAU)
  - Notes created per day
  - Search queries per day
  - Average notes per user

**Monitoring Tools:**
- Local: Prometheus + Grafana (optional; out of scope for prototype)
- Cloud: CloudWatch (AWS), Azure Monitor, Google Cloud Monitoring (if deployed to cloud)
- Minimal: Application logs + manual inspection

#### Tracing

- Not required for prototype; can be added later if needed.
- If added: Use OpenTelemetry for distributed tracing across services.

#### Alerting

- **Critical Alerts:**
  - Backend service down (no response to health check)
  - Database unavailable
  - Disk usage > 90%
  - Error rate > 5%

- **Warning Alerts:**
  - Request latency p95 > 1 second
  - Memory usage > 80%
  - Backup failed

---

## DEPLOYMENT & OPERATIONS

### Deployment Topology

```
┌─────────────────────────────────────────────────────────────┐
│                    Organization Network                      │
│                   (Behind VPN/Firewall)                      │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Reverse Proxy (Nginx/Apache)            │   │
│  │  - SSL/TLS termination                               │   │
│  │  - Set X-User-Email header (from SSO or LDAP)        │   │
│  │  - Route to backend                                  │   │
│  └────────────────────┬─────────────────────────────────┘   │
│                       │                                       │
│  ┌────────────────────▼─────────────────────────────────┐   │
│  │         Spring Boot Backend (Single Instance)        │   │
│  │  - REST API                                          │   │
│  │  - Embedded Tomcat                                   │   │
│  │  - SQLite JDBC driver                                │   │
│  └────────────────────┬─────────────────────────────────┘   │
│                       │                                       │
│  ┌────────────────────▼─────────────────────────────────┐   │
│  │         SQLite Database (Local File)                 │   │
│  │  - /var/lib/notes-app/notes.db                       │   │
│  │  - Backed up daily to NAS/S3                         │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │         Static File Server (Nginx)                  │   │
│  │  - Serves React SPA (index.html, JS, CSS)           │   │
│  │  - Can be same Nginx instance as reverse proxy      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Deployment Options

#### Option 1: Docker Container (Recommended)

**Dockerfile:**
- Base image: `openjdk:17-slim` (for backend) or `node:18-slim` (for frontend build)
- Multi-stage build: Build frontend (React) in one stage, copy artifacts to backend stage
- Expose port 8080 (backend) and 80 (static files)
- Health check: `curl http://localhost:8080/health`

**Docker Compose (for local development):**
- Backend service (Spring Boot)
- Frontend service (Nginx serving React SPA)
- Optional: PostgreSQL (if migrating from SQLite)

**Deployment:**
- Push Docker image to private registry (Docker Hub, ECR, or on-premises registry)
- Deploy to on-premises Docker host or private cloud (OpenStack, vSphere, etc.)
- Use systemd or Docker Compose to manage container lifecycle

#### Option 2: Bare Metal / VM

**Prerequisites:**
- Java 17+ runtime
- Nginx or Apache (reverse proxy)
- SQLite (included with most Linux distributions)

**Deployment Steps:**
1. Build backend JAR file (Spring Boot fat JAR)
2. Build frontend (React SPA) and copy to Nginx document root
3. Copy JAR to `/opt/notes-app/`
4. Create systemd service file to manage backend process
5. Configure Nginx to reverse proxy to backend and serve static files
6. Start services

**Systemd Service File Example:**
```
[Unit]
Description=Notes App Backend
After=network.target

[Service]
Type=simple
User=notes-app
WorkingDirectory=/opt/notes-app
ExecStart=/usr/bin/java -jar notes-app.jar
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Configuration Management

**Environment Variables:**

| Variable | Example | Purpose |
|----------|---------|---------|
| `ADMIN_EMAILS` | `alex@org.com,admin@org.com` | Comma-separated list of admin email addresses |
| `DATABASE_URL` | `jdbc:sqlite:/var/lib/notes-app/notes.db` | SQLite database file path |
| `SERVER_PORT` | `8080` | Backend HTTP port |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARN, ERROR) |
| `BACKUP_PATH` | `/mnt/backup/notes-app/` | Path to backup directory |
| `MAX_UPLOAD_SIZE` | `10MB` | Maximum note content size (optional) |

**Configuration File (application.properties or application.yml):**
```
spring.application.name=notes-app
spring.datasource.url=jdbc:sqlite:${DATABASE_URL}
spring.datasource.driver-class-name=org.sqlite.JDBC
server.port=${SERVER_PORT:8080}
logging.level.root=${LOG_LEVEL:INFO}
```

### Deployment Checklist

- [ ] Backend JAR built and tested locally
- [ ] Frontend React SPA built and tested locally
- [ ] Docker image built and pushed to registry (if using Docker)
- [ ] Database file created and initialized with schema
- [ ] Nginx/Apache configured with SSL/TLS and reverse proxy rules
- [ ] X-User-Email header configured (from SSO or reverse proxy)
- [ ] Admin email whitelist configured
- [ ] Backup script created and scheduled (daily)
- [ ] Health check endpoint tested
- [ ] Smoke tests passed (create note, search, list tags)
- [ ] Audit logs verified
- [ ] Documentation updated (deployment runbook, troubleshooting guide)

### Operational Runbooks

#### Backup & Recovery

**Daily Backup:**
```bash
#!/bin/bash
BACKUP_DIR="/mnt/backup/notes-app"
DB_FILE="/var/lib/notes-app/notes.db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

cp $DB_FILE $BACKUP_DIR/notes_$TIMESTAMP.db
# Keep only last 30 days of backups
find $BACKUP_DIR -name "notes_*.db" -mtime +30 -delete
```

**Restore from Backup:**
```bash
#!/bin/bash
BACKUP_FILE="/mnt/backup/notes-app/notes_20240115_100000.db"
DB_FILE="/var/lib/notes-app/notes.db"

# Stop backend service
systemctl stop notes-app

# Restore backup
cp $BACKUP_FILE $DB_FILE

# Start backend service
systemctl start notes-app
```

#### Health Check

**Endpoint:** `GET /health`

**Response (Healthy):**
```json
{
  "status": "UP",
  "database": "UP",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Response (Unhealthy):**
```json
{
  "status": "DOWN",
  "database": "DOWN",
  "error": "Cannot connect to database",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### Scaling Up

**If backend is CPU-bound:**
1. Increase CPU cores on VM or container
2. Increase Java heap size: `-Xmx4g` (adjust based on available RAM)
3. Monitor performance; if still insufficient, add load balancer and multiple backend instances

**If backend is I/O-bound (database):**
1. Migrate SQLite to PostgreSQL (requires schema migration)
2. Add read replicas for read-heavy workloads
3. Add caching layer (Redis) for frequently accessed data

---

## SECURITY & COMPLIANCE

### Data Classification

| Data Type | Classification | Handling |
|-----------|-----------------|----------|
| Note content | Internal | Encrypted at rest; accessible only to authenticated users |
| User email | Internal | Stored in database; used for audit logging |
| Audit logs | Internal | Immutable; accessible only to admins |
| Backup files | Internal | Encrypted; stored on secure network storage |

### Threat Model

| Threat | Likelihood | Impact | Mitigation |
|--------|-----------|--------|-----------|
| Unauthorized access to notes | Low | High | Network perimeter (VPN/firewall); no public internet exposure |
| Data breach via backup | Low | High | Encrypt backup files; restrict access to backup storage |
| Accidental data deletion | Medium | High | Soft delete; daily backups; audit trail |
| Insider threat (malicious admin) | Low | High | Audit logs track all admin actions; no way to hide changes |
| SQL injection | Low | High | Use parameterized queries (JDBC prepared statements); no string concatenation |
| Cross-site scripting (XSS) | Medium | Medium | Sanitize user input; use React's built-in XSS protection |
| Cross-site request forgery (CSRF) | Low | Medium | CSRF tokens not needed (no cookies; stateless API) |

### Compliance Requirements

#### SOC 2 Type II

**Required Controls:**
- Access control: RBAC with audit logging ✓
- Data protection: Encryption at rest and in transit ✓
- Availability: 99.5% uptime target ✓
- Audit logging: All actions logged with user, timestamp, changes ✓
- Backup & recovery: Daily backups with RTO < 1 hour ✓

#### HIPAA (if handling health data)

**Required Controls:**
- Encryption at rest (AES-256) ✓
- Encryption in transit (TLS 1.2+) ✓
- Access control with audit logging ✓
- Data retention policy ✓
- Breach notification procedures (out of scope for this doc)

#### GDPR (if handling EU resident data)

**Required Controls:**
- Data minimization: Collect only necessary data ✓
- Right to deletion: Soft delete allows recovery; hard delete after 90 days (configurable) ✓
- Data portability: Export audit logs (admin feature) ✓
- Privacy by design: No unnecessary data collection ✓

### Security Checklist

- [ ] All API communication over HTTPS (TLS 1.2+)
- [ ] Database file encrypted at rest (filesystem-level encryption)
- [ ] Backup files encrypted
- [ ] Admin email whitelist configured
- [ ] X-User-Email header validated on every request
- [ ] Parameterized queries used (no SQL injection)
- [ ] Input validation on all endpoints (title, content, tag names)
- [ ] Output encoding (JSON serialization prevents XSS)
- [ ] Rate limiting (optional; can be added if needed)
- [ ] CORS headers configured (if frontend is on different domain)
- [ ] Security headers configured (X-Frame-Options, X-Content-Type-Options, etc.)
- [ ] Audit logs tested and verified
- [ ] Backup & recovery tested
- [ ] Penetration testing completed (optional)

---

## OBSERVABILITY & MONITORING

### Logging Strategy

#### Application Logs

**Log Levels:**
- **DEBUG:** Detailed information for troubleshooting (SQL queries, request/response bodies)
- **INFO:** General information (API requests, user actions, startup/shutdown)
- **WARN:** Warning conditions (slow queries, deprecated API usage)
- **ERROR:** Error conditions (exceptions, failed operations)

**Log Format (JSON):**
```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "INFO",
  "logger": "com.example.notesapp.api.NotesController",
  "message": "Note created",
  "user_email": "sarah@org.com",
  "note_id": "550e8400-e29b-41d4-a716-446655440000",
  "duration_ms": 145,
  "request_id": "req-12345"
}
```

**Log Destinations:**
- Console (stdout/stderr) — Captured by container runtime or systemd journal
- File (optional) — `/var/log/notes-app/notes-app.log`
- Centralized logging (optional) — ELK Stack, Splunk, or cloud provider logging service

#### Audit Logs

**Stored in Database** — Immutable audit_logs table (see Data Model section).

**Audit Log Entry:**
```json
{
  "id": "...",
  "user_email": "sarah@org.com",
  "action": "CREATE",
  "resource_type": "NOTE",
  "resource_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:30:00Z",
  "changes": null,
  "ip_address": "192.168.1.100"
}
```

**Audit Log Export:**
- Admins can export audit logs via API: `GET /api/v1/audit-logs?created_after=...&created_before=...`
- Export format: JSON or CSV
- Used for compliance reporting and investigations

### Metrics

#### Application Metrics

**Collected by Backend:**
- Request latency (p50, p95, p99)
- Request throughput (requests per second)
- Error rate (5xx, 4xx errors)
- Database query latency
- Active connections

**Exposed via Metrics Endpoint (optional):**
- `GET /metrics` — Prometheus-format metrics
- Requires Spring Boot Actuator dependency

**Example Metrics:**
```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",path="/api/v1/notes",status="200"} 1234

# HELP http_request_duration_seconds HTTP request latency
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{method="GET",path="/api/v1/notes",le="0.1"} 1000
http_request_duration_seconds_bucket{method="GET",path="/api/v1/notes",le="0.5"} 1200
http_request_duration_seconds_bucket{method="GET",path="/api/v1/notes",le="1.0"} 1230
```

#### System Metrics

**Collected by OS / Container Runtime:**
- CPU usage (%)
- Memory usage (%)
- Disk usage (%)
- Network I/O (bytes/sec)
- Process count

**Monitoring Tools:**
- Local: `top`, `htop`, `df`, `iostat`
- Container: Docker stats, Kubernetes metrics
- Cloud: CloudWatch, Azure Monitor, Google Cloud Monitoring

#### Business Metrics

**Collected by Backend (via audit logs):**
- Daily active users (DAU)
- Monthly active users (MAU)
- Notes created per day
- Search queries per day
- Average notes per user
- Tag usage distribution

**Calculation (from audit logs):**
```sql
-- DAU
SELECT COUNT(DISTINCT user_email) 
FROM audit_logs 
WHERE DATE(timestamp) = CURRENT_DATE;

-- Notes created per day
SELECT COUNT(*) 
FROM audit_logs 
WHERE action = 'CREATE' AND resource_type = 'NOTE' 
AND DATE(timestamp) = CURRENT_DATE;

-- Tag usage
SELECT tag_id, COUNT(*) as usage_count 
FROM note_tags 
GROUP BY tag_id 
ORDER BY usage_count DESC;
```

### Alerting

#### Alert Rules

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| Backend Down | No response to health check for 2 minutes | Critical | Page on-call engineer |
| Database Unavailable | Database connection fails | Critical | Page on-call engineer |
| High Error Rate | Error rate > 5% for 5 minutes | High | Alert ops team |
| High Latency | p95 latency > 1 second for 10 minutes | Medium | Alert ops team |
| Disk Full | Disk usage > 90% | High | Alert ops team |
| Backup Failed | Backup job failed | High | Alert ops team |

#### Alert Destinations

- Email (to ops team)
- Slack (to #alerts channel)
- PagerDuty (for critical alerts)
- SMS (for critical alerts, optional)

### Dashboards

#### Operations Dashboard

**Metrics:**
- Backend uptime (%)
- Request latency (p50, p95, p99)
- Error rate (%)
- Database query latency
- CPU/memory usage
- Disk usage
- Active connections

**Refresh Rate:** 1 minute

#### Business Dashboard

**Metrics:**
- Daily active users (DAU)
- Monthly active users (MAU)
- Notes created per day
- Search queries per day
- Top tags (by usage)
- Notes per user (average, median, p95)

**Refresh Rate:** 1 hour

---

## ASSUMPTIONS & OPEN QUESTIONS

### Assumptions Made

1. **Single-Tenant Deployment** — This product is deployed for a single organization, not as a multi-tenant SaaS. If multi-tenant is required, the data model, access control, and deployment topology must be redesigned.

2. **Internal Network Only** — The app is deployed behind the organization's VPN/firewall. External access is not in scope. If external access is required, authentication must be added.

3. **No Real-Time Collaboration** — Notes are not edited simultaneously by multiple users. Eventual consistency is acceptable. If real-time collaboration is required, WebSocket support and conflict resolution must be added.

4. **User Identification via Header** — The organization's reverse proxy or SSO layer sets the `X-User-Email` header. The backend trusts this header and does not validate it against an external directory. If this assumption is invalid, authentication must be added.

5. **All Notes Visible to All Users** — There are no private notes or team-scoped visibility. All authenticated users can read all notes. If privacy is required, the data model and authorization logic must be extended.

6. **Ad-Hoc Tag Creation** — Users can create tags on-the-fly when creating/editing notes. Tags are not pre-defined by admins. If tag governance is required, the tag creation flow must be restricted to admins.

7. **SQLite is Sufficient** — Single-tenant, team-scale data volume (3,000–6,000 notes at 6–12 months) does not require PostgreSQL or other managed database. If data volume exceeds 100,000 notes or concurrent users exceed 1,000, migration to PostgreSQL is recommended.

8. **No Offline Mode** — The app requires internet connectivity to the backend. No offline-first or local-first architecture. If offline mode is required, local storage and sync logic must be added.

9. **No Real-Time Notifications** — Users are not notified when others create or edit notes. If real-time notifications are required, WebSocket or polling must be added.

10. **Soft Delete Only** — Notes are soft-deleted (marked as deleted) and retained for audit purposes. Hard deletion is not supported for non-admins. If hard deletion is required, audit implications must be considered.

### Open Questions for Product Team

1. **Multi-Tenancy** — Is this a single-tenant deployment for one organization, or a multi-tenant SaaS for multiple organizations? If multi-tenant, how should data be isolated?

2. **External Access** — Can external users (contractors, partners) access the app? If yes, authentication must be added.

3. **Private Notes** — Should users be able to create private notes visible only to themselves? Or are all notes visible to all users?

4. **Team-Scoped Access** — Should notes be scoped to teams (e.g., "Engineering" team, "Product" team)? Or are all notes organization-wide?

5. **Tag Governance** — Should tag creation be restricted to admins, or can any user create tags?

6. **Data Retention** — How long should soft-deleted notes be retained before hard deletion? (Recommended: 90 days)

7. **Audit Log Retention** — How long should audit logs be retained? (Recommended: indefinitely, or per compliance requirements)

8. **Export/Import** — Should users be able to export notes (e.g., as Markdown or PDF)? Should admins be able to import notes from other systems?

9. **Versioning** — Should the app track note edit history (e.g., "view previous versions")? Or only the current version?

10. **Notifications** — Should users be notified when others mention them in notes (e.g., "@sarah")? Or when notes are shared with them?

11. **Integration** — Should the app integrate with other tools (Slack, email, calendar)? Or is it standalone?

12. **Mobile Support** — Should the app support mobile devices (iOS, Android)? Or is web-only sufficient?

---

## ACCEPTANCE CRITERIA

### Functional Acceptance Criteria

#### Notes Management

- [ ] **Create Note** — User can create a note with title, content, and tags. Note is immediately visible to all users. Audit log records creation.
- [ ] **Read Note** — User can view a single note by ID. Audit log records view (optional; can be disabled for performance).
- [ ] **Update Note** — User can edit title, content, and tags of their own notes. `updated_at` and `updated_by` are updated. Audit log records changes.
- [ ] **Delete Note** — User can soft-delete their own notes. Note is marked as deleted but retained in database. Audit log records deletion.
- [ ] **List Notes** — User can list all non-deleted notes with pagination. Default sort is by `created_at` (newest first).
- [ ] **Admin Delete** — Admin can delete any note (including notes created by others). Soft delete applies.
- [ ] **Admin Edit** — Admin can edit any note (including notes created by others). `updated_by` reflects the admin, not the original creator.

#### Search & Filtering

- [ ] **Full-Text Search** — User can search notes by keyword. Results include notes matching keyword in title or content. Results are ranked by relevance.
- [ ] **Tag Filtering** — User can filter notes by one or more tags. AND logic applies (note must have all specified tags).
- [ ] **Date Range Filtering** — User can filter notes by creation date (before/after).
- [ ] **Creator Filtering** — User can filter notes by creator email.
- [ ] **Combined Filtering** — User can combine search, tag filtering, date range, and creator filtering in a single query.
- [ ] **Pagination** — Results are paginated with configurable page size (default 20, max 100).
- [ ] **Sorting** — User can sort by `created_at`, `updated_at`, or `relevance` (if searching).

#### Tag Management

- [ ] **Create Tag** — User can create a new tag by name. Tag is immediately available for use.
- [ ] **List Tags** — User can list all tags sorted by usage count (most used first).
- [ ] **Apply Tag** — User can apply tags to notes when creating or editing.
- [ ] **Remove Tag** — User can remove tags from notes.
- [ ] **Delete Tag** — Admin can delete a tag if it's not applied to any notes. Deletion fails (409 Conflict) if tag is in use.
- [ ] **Tag Uniqueness** — Tag names are unique; duplicate tag names are rejected (409 Conflict).

#### Audit Logging

- [ ] **Log Create** — Audit log records note creation with user, timestamp, note ID.
- [ ] **Log Update** — Audit log records note updates withuser, timestamp, note ID, and changes (old and new values).
- [ ] **Log Delete** — Audit log records note deletion with user, timestamp, note ID.
- [ ] **Log Read** — Audit log records note reads (optional; can be disabled for performance).
- [ ] **Log Tag Operations** — Audit log records tag creation and deletion.
- [ ] **Immutable Logs** — Audit logs cannot be modified or deleted by any user (including admins).
- [ ] **Admin Export** — Admin can export audit logs for a date range in JSON or CSV format.

#### Authorization

- [ ] **User Can Edit Own Notes** — User can edit notes they created.
- [ ] **User Cannot Edit Others' Notes** — User cannot edit notes created by others (403 Forbidden).
- [ ] **User Can Delete Own Notes** — User can soft-delete notes they created.
- [ ] **User Cannot Delete Others' Notes** — User cannot delete notes created by others (403 Forbidden).
- [ ] **Admin Can Edit Any Note** — Admin can edit any note, including those created by others.
- [ ] **Admin Can Delete Any Note** — Admin can delete any note.
- [ ] **Admin Can Delete Tags** — Admin can delete tags.
- [ ] **User Cannot Delete Tags** — Non-admin user cannot delete tags (403 Forbidden).
- [ ] **Admin Can Access Audit Logs** — Admin can query and export audit logs.
- [ ] **User Cannot Access Audit Logs** — Non-admin user cannot access audit logs (403 Forbidden).

#### User Context

- [ ] **User Email Extracted** — Backend extracts user email from `X-User-Email` header on every request.
- [ ] **User Email Validated** — Backend validates that user email is non-empty and well-formed. Returns 400 Bad Request if invalid.
- [ ] **User Email Missing** — Backend returns 400 Bad Request if `X-User-Email` header is missing.
- [ ] **Admin Whitelist** — Admin status is determined by email whitelist in `ADMIN_EMAILS` environment variable.
- [ ] **Admin Whitelist Honored** — Only emails in whitelist are treated as admins; all others are regular users.

### Non-Functional Acceptance Criteria

#### Performance

- [ ] **Create Note Latency** — Creating a note completes in < 500ms (p95).
- [ ] **Search Latency** — Full-text search on 1000 notes completes in < 200ms (p95).
- [ ] **Tag Filter Latency** — Filtering by tags completes in < 100ms (p95).
- [ ] **List Tags Latency** — Listing all tags completes in < 50ms (p95).
- [ ] **Pagination Latency** — Retrieving a page of 20 notes completes in < 200ms (p95).
- [ ] **Concurrent Users** — Backend handles 100 concurrent users without degradation (latency remains within targets).
- [ ] **Throughput** — Backend handles 50+ requests per second without errors.

#### Availability

- [ ] **Health Check Endpoint** — `GET /health` returns 200 OK with status "UP" when backend is healthy.
- [ ] **Health Check Detects Failures** — Health check returns 503 Service Unavailable when database is unreachable.
- [ ] **Automatic Restart** — Backend service automatically restarts if it crashes (systemd or container runtime).
- [ ] **Uptime Target** — Backend achieves 99.5% uptime over a calendar month (excluding planned maintenance).

#### Security

- [ ] **HTTPS Only** — All API communication is over HTTPS (TLS 1.2+). HTTP requests are redirected to HTTPS.
- [ ] **No SQL Injection** — All database queries use parameterized statements (JDBC prepared statements). No string concatenation.
- [ ] **Input Validation** — All user inputs (title, content, tag names) are validated for length and format. Invalid inputs are rejected with 400 Bad Request.
- [ ] **Output Encoding** — All responses are JSON-encoded. No unescaped HTML or JavaScript in responses.
- [ ] **CORS Headers** — CORS headers are configured correctly. Frontend can communicate with backend.
- [ ] **Security Headers** — Response headers include `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `X-XSS-Protection: 1; mode=block`.
- [ ] **Database Encryption** — SQLite database file is stored on encrypted filesystem (LUKS, BitLocker, or cloud provider encryption).
- [ ] **Backup Encryption** — Backup files are encrypted.
- [ ] **Audit Trail Complete** — All create/read/update/delete actions are logged with user, timestamp, and changes.

#### Observability

- [ ] **Application Logs** — Backend logs all API requests, database operations, and errors to console (stdout/stderr).
- [ ] **Log Format** — Logs are in structured JSON format (or plain text with consistent format).
- [ ] **Log Level Configuration** — Log level can be configured via `LOG_LEVEL` environment variable.
- [ ] **Request Tracing** — Each request has a unique `request_id` that is logged and can be used to trace request flow.
- [ ] **Error Logging** — Errors include stack traces and context (user, request, operation).
- [ ] **Metrics Endpoint** — `GET /metrics` exposes Prometheus-format metrics (optional; can be added later).
- [ ] **Audit Log Queries** — Audit logs can be queried by date range, user, action, and resource type.

#### Data Integrity

- [ ] **Soft Delete** — Deleted notes are marked as deleted but retained in database. Queries filter out deleted notes by default.
- [ ] **Audit Trail Immutable** — Audit logs cannot be modified or deleted by any user.
- [ ] **Backup & Recovery** — Daily backups are created and can be restored. Recovery time is < 1 hour.
- [ ] **Data Consistency** — No orphaned records (e.g., note_tags referencing deleted notes). Foreign key constraints are enforced.
- [ ] **Concurrent Updates** — If two users update the same note simultaneously, the last update wins (last-write-wins semantics). No data corruption.

### UI/UX Acceptance Criteria

#### Frontend Functionality

- [ ] **Create Note Form** — User can enter title, content, and select/create tags. Form validates required fields. Submit button creates note.
- [ ] **Note List View** — User sees list of notes with title, creator, creation date, and tags. List is paginated.
- [ ] **Search Bar** — User can enter search query. Results update in real-time (or on Enter key).
- [ ] **Tag Filter** — User can select tags to filter notes. Multiple tags can be selected (AND logic).
- [ ] **Date Range Filter** — User can select date range to filter notes.
- [ ] **Creator Filter** — User can select creator to filter notes.
- [ ] **Sort Options** — User can sort by creation date, update date, or relevance (if searching).
- [ ] **Note Detail View** — User can click on a note to view full content. Edit and delete buttons are visible.
- [ ] **Edit Note** — User can edit title, content, and tags. Changes are saved immediately.
- [ ] **Delete Note** — User can delete their own notes. Confirmation dialog is shown before deletion.
- [ ] **Tag Management** — User can view all tags and their usage count. Admin can delete tags.
- [ ] **User Context** — App displays current user email (e.g., "Logged in as sarah@org.com").
- [ ] **Error Messages** — App displays clear error messages when operations fail (e.g., "Note not found", "Permission denied").
- [ ] **Loading States** — App shows loading spinner while fetching data.
- [ ] **Empty States** — App shows helpful message when no notes match search/filter criteria.

#### Responsive Design

- [ ] **Desktop** — App is fully functional on desktop browsers (Chrome, Firefox, Safari, Edge).
- [ ] **Tablet** — App is usable on tablet devices (iPad, Android tablets). Layout adapts to smaller screens.
- [ ] **Mobile** — App is usable on mobile devices (iPhone, Android phones). Layout adapts to small screens. Touch-friendly buttons.

#### Accessibility

- [ ] **Keyboard Navigation** — All UI elements are accessible via keyboard (Tab, Enter, Escape).
- [ ] **Screen Reader Support** — App is compatible with screen readers (ARIA labels, semantic HTML).
- [ ] **Color Contrast** — Text has sufficient contrast ratio (WCAG AA standard: 4.5:1 for normal text).
- [ ] **Focus Indicators** — Focused elements have visible focus indicators.

### Deployment Acceptance Criteria

- [ ] **Docker Image Builds** — Docker image builds successfully without errors.
- [ ] **Docker Image Runs** — Docker container starts and backend is accessible on port 8080.
- [ ] **Database Initialized** — SQLite database is created and schema is initialized on first run.
- [ ] **Configuration via Environment** — All configuration (admin emails, database path, log level) can be set via environment variables.
- [ ] **Health Check Works** — `GET /health` returns 200 OK when backend is running.
- [ ] **Backup Script Works** — Daily backup script runs successfully and creates backup file.
- [ ] **Restore Script Works** — Backup can be restored and app continues to function.
- [ ] **Systemd Service Works** — Backend service can be started, stopped, and restarted via systemd.
- [ ] **Nginx Reverse Proxy Works** — Nginx is configured to reverse proxy to backend and serve static files.
- [ ] **SSL/TLS Works** — HTTPS is enabled and certificates are valid.
- [ ] **X-User-Email Header Works** — Nginx sets `X-User-Email` header and backend receives it.

### Compliance Acceptance Criteria

- [ ] **Audit Logs Complete** — All create/read/update/delete actions are logged.
- [ ] **Audit Logs Immutable** — Audit logs cannot be modified or deleted.
- [ ] **Audit Log Export** — Admin can export audit logs for compliance reporting.
- [ ] **Data Retention Policy** — Soft-deleted notes are retained for 90 days (configurable).
- [ ] **Backup Retention** — Daily backups are retained for 30 days.
- [ ] **Encryption at Rest** — Database file is encrypted on filesystem.
- [ ] **Encryption in Transit** — All API communication is over HTTPS.
- [ ] **Access Control Enforced** — Authorization rules are enforced on all endpoints.
- [ ] **No Data Leakage** — Non-admin users cannot access audit logs or other users' private data.

---

## APPENDIX: TECHNOLOGY DECISION RATIONALE

### Why Spring Boot (Java) for Backend?

**Chosen:** Spring Boot 3.x with Java 17+

**Rationale:**
- **Maturity:** Spring Boot is battle-tested for REST APIs at scale. Excellent ecosystem (Spring Data, Spring Security, Spring Actuator).
- **Performance:** Java's JIT compilation and garbage collection are well-optimized for server workloads. Handles 100+ concurrent users easily.
- **Type Safety:** Java's static typing catches errors at compile time, reducing runtime bugs.
- **Operational Excellence:** Spring Boot fat JAR is self-contained; no separate application server needed. Embedded Tomcat handles HTTP.
- **Team Familiarity:** Assumed baseline for the team; no learning curve.

**Why Not X?**
- **Python (FastAPI):** Slower than Java; GIL limits concurrency. Suitable for I/O-bound workloads but not ideal for a general-purpose backend.
- **Node.js (Express):** Single-threaded event loop; less suitable for CPU-bound operations. Requires more careful memory management.
- **Go:** Overkill for single-service, single-tenant scope. Go's simplicity is wasted on a monolith.
- **.NET (C#):** Requires Windows Server or Linux with .NET runtime. Java is more portable and has broader Linux support.

### Why SQLite for Database?

**Chosen:** SQLite 3.40+ with FTS5 full-text search

**Rationale:**
- **Simplicity:** File-based database; no server setup, no connection pooling, no replication. Single file to backup.
- **Sufficient for Scale:** Single-tenant, team-scale data (3,000–6,000 notes) is well within SQLite's capabilities. SQLite handles 100,000+ records comfortably.
- **Full-Text Search:** FTS5 virtual table provides powerful full-text search without a separate search service (Elasticsearch, Meilisearch).
- **ACID Compliance:** SQLite provides ACID guarantees; data integrity is assured.
- **Embedded:** No external dependency; database is embedded in backend process.
- **Backup:** Simple file-level backup; no database-specific tooling needed.

**Why Not X?**
- **PostgreSQL:** Overkill for single-tenant, team-scale data. Adds operational complexity (server setup, backups, monitoring, connection pooling). Migration path exists if data volume exceeds 100,000 notes.
- **MySQL:** Similar to PostgreSQL; overkill for this scale. SQLite is simpler.
- **MongoDB:** Document database not needed; relational schema is clearer for notes + tags + audit logs. No schema flexibility benefit.
- **DynamoDB / Firestore:** Requires cloud infrastructure; not justified for internal tool. Adds cost and operational complexity.
- **Elasticsearch:** Overkill for search; SQLite FTS5 is sufficient. Elasticsearch adds operational burden (cluster management, backups, monitoring).

### Why React + Vite for Frontend?

**Chosen:** React 18+ with Vite, TypeScript, Tailwind CSS

**Rationale:**
- **React:** Component-based UI; large ecosystem; team familiarity. Excellent for building interactive UIs.
- **Vite:** Fast dev server and build tool. Minimal configuration. Modern bundling (ES modules).
- **TypeScript:** Type safety catches errors at development time. Improves code quality and maintainability.
- **Tailwind CSS:** Utility-first CSS framework. Rapid UI development without writing custom CSS. Consistent design system.

**Why Not X?**
- **Vue / Angular:** React is the assumed baseline; no reason to diverge.
- **Next.js / Remix:** Server-side rendering not needed. Static SPA is simpler and faster.
- **Svelte:** Smaller ecosystem; less team familiarity. React is safer choice.
- **Plain HTML/CSS/JS:** No component reusability; harder to maintain as app grows.

### Why No Authentication?

**Chosen:** No login, no authentication, no session management

**Rationale:**
- **Internal Tool:** Deployed behind organization's VPN/firewall. Network perimeter provides security boundary.
- **Simplicity:** No auth layer means no session management, no password hashing, no OAuth integration. Reduces complexity and attack surface.
- **User Identification:** User email is provided by reverse proxy (via `X-User-Email` header) or SSO layer. Backend trusts this header.
- **Compliance:** Audit logs track all actions with user email. No need for login audit trail.

**Why Not X?**
- **JWT / OAuth2:** Adds complexity without proportional security benefit for internal tool. Requires token management, refresh logic, etc.
- **Session-Based Auth:** Requires session storage (Redis, database). Adds operational complexity.
- **LDAP / Active Directory:** Possible, but adds complexity. Reverse proxy can handle LDAP integration and set `X-User-Email` header.

**Future Consideration:**
If external access becomes a requirement, authentication must be added. Recommended approach: OAuth2 with organization's identity provider (Okta, Azure AD, Google Workspace).

### Why No Microservices?

**Chosen:** Monolithic backend (single Spring Boot service)

**Rationale:**
- **Single-Tenant Scope:** No need to scale services independently.
- **Operational Simplicity:** Single service is easier to deploy, monitor, and debug than multiple services.
- **Data Consistency:** All data in single database; no distributed transaction complexity.
- **Team Size:** Small team can maintain single monolith more easily than multiple services.

**Why Not X?**
- **Microservices:** Adds complexity (service discovery, inter-service communication, distributed tracing, eventual consistency). Not justified for single-tenant, team-scale app.
- **Serverless (Lambda, Cloud Functions):** Stateful database connection management is simpler with persistent server. Serverless adds cold-start latency and complexity.

**Future Consideration:**
If organization grows to 10,000+ users or 100,000+ notes, consider:
- Separating search into dedicated service (Elasticsearch)
- Adding caching layer (Redis)
- Migrating to PostgreSQL
- Adding load balancer for multiple backend instances

---

## APPENDIX: MIGRATION PATHS

### SQLite to PostgreSQL

**When to Migrate:**
- Data volume exceeds 100,000 notes
- Concurrent users exceed 1,000
- Need for read replicas or high availability

**Migration Steps:**
1. Set up PostgreSQL instance (on-premises or cloud)
2. Create schema in PostgreSQL (same as SQLite)
3. Write migration script to copy data from SQLite to PostgreSQL
4. Update backend configuration to use PostgreSQL JDBC driver
5. Run migration script (can be done during maintenance window)
6. Test thoroughly on staging environment
7. Deploy to production
8. Keep SQLite backup for rollback (if needed)

**Rollback Plan:**
- Keep SQLite database as backup for 30 days
- If PostgreSQL migration fails, revert to SQLite and investigate issues

### Single Instance to Multiple Instances

**When to Scale:**
- Single instance CPU/memory is maxed out
- Need for high availability (no single point of failure)

**Scaling Steps:**
1. Set up load balancer (Nginx, HAProxy, or cloud provider load balancer)
2. Deploy multiple backend instances behind load balancer
3. Migrate SQLite to PostgreSQL (shared database for all instances)
4. Configure backend instances to connect to PostgreSQL
5. Test load balancing and failover
6. Monitor performance and adjust instance count as needed

**Considerations:**
- All instances must connect to same database (PostgreSQL)
- Session state must be stored in database or Redis (not in-memory)
- Audit logs and backups must be coordinated across instances

### Adding Caching Layer

**When to Add:**
- Database queries are slow (p95 latency > 500ms)
- High read-to-write ratio (many searches, few updates)

**Caching Strategy:**
1. Add Redis instance (on-premises or cloud)
2. Cache frequently accessed data:
   - All tags (invalidate on tag create/delete)
   - Recent notes (invalidate on note create/update/delete)
   - Search results (invalidate on note create/update/delete)
3. Implement cache invalidation logic in backend
4. Monitor cache hit rate and adjust TTL as needed

**Considerations:**
- Cache invalidation is complex; must be done carefully to avoid stale data
- Redis adds operational complexity (monitoring, backups, failover)
- Only add if performance metrics justify the complexity

---

## APPENDIX: GLOSSARY

| Term | Definition |
|------|-----------|
| **DAU** | Daily Active Users — number of unique users who access the app on a given day |
| **MAU** | Monthly Active Users — number of unique users who access the app in a given month |
| **RTO** | Recovery Time Objective — maximum acceptable downtime after a failure |
| **RPO** | Recovery Point Objective — maximum acceptable data loss (time since last backup) |
| **SLA** | Service Level Agreement — commitment to uptime and performance targets |
| **RBAC** | Role-Based Access Control — authorization model based on user roles (User, Admin) |
| **ACID** | Atomicity, Consistency, Isolation, Durability — database transaction properties |
| **FTS** | Full-Text Search — search capability that indexes and searches text content |
| **JWT** | JSON Web Token — stateless authentication token |
| **OAuth2** | Open Authorization 2.0 — standard protocol for delegated authentication |
| **LDAP** | Lightweight Directory Access Protocol — protocol for accessing directory services (e.g., Active Directory) |
| **CORS** | Cross-Origin Resource Sharing — mechanism for allowing cross-origin HTTP requests |
| **XSS** | Cross-Site Scripting — security vulnerability where attacker injects malicious scripts |
| **CSRF** | Cross-Site Request Forgery — security vulnerability where attacker tricks user into performing unwanted action |
| **SQL Injection** | Security vulnerability where attacker injects malicious SQL code |
| **Soft Delete** | Marking a record as deleted without removing it from database (allows recovery and audit trail) |
| **Hard Delete** | Permanently removing a record from database (cannot be recovered) |
| **Immutable** | Cannot be changed or deleted after creation |
| **Denormalization** | Storing redundant data to improve query performance (e.g., `usage_count` on tags table) |
| **Parameterized Query** | SQL query with placeholders for parameters (prevents SQL injection) |
| **Virtual Table** | SQLite feature for implementing custom table-like objects (e.g., FTS5 for full-text search) |
| **Trigger** | Database object that automatically executes in response to events (e.g., INSERT, UPDATE, DELETE) |
| **Index** | Database structure that speeds up queries on indexed columns |
| **Foreign Key** | Database constraint that ensures referential integrity between tables |
| **Composite Key** | Primary key consisting of multiple columns |
| **Junction Table** | Table that implements many-to-many relationship between two other tables |
| **Pagination** | Dividing large result sets into smaller pages for easier navigation |
| **Relevance Ranking** | Ordering search results by how well they match the search query |
| **Boolean Operators** | Logical operators (AND, OR, NOT) used in search queries |
| **Phrase Search** | Searching for exact phrase (e.g., "database migration") |
| **Wildcard Search** | Searching with wildcards (e.g., "bug*" matches "bug", "bugs", "bugfix") |
| **Tokenizer** | Component that breaks text into tokens (words) for indexing and searching |
| **Reverse Proxy** | Server that sits in front of backend and forwards requests to it (e.g., Nginx, Apache) |
| **SSL/TLS** | Secure Sockets Layer / Transport Layer Security — protocols for encrypted communication |
| **HTTPS** | HTTP over SSL/TLS — secure version of HTTP |
| **Health Check** | Endpoint that reports whether service is healthy and ready to serve requests |
| **Graceful Degradation** | Continuing to function (possibly with reduced functionality) when part of system fails |
| **Horizontal Scaling** | Adding more instances of a service to handle increased load |
| **Vertical Scaling** | Adding more resources (CPU, RAM) to a single instance |
| **Load Balancer** | Component that distributes requests across multiple instances |
| **Failover** | Automatic switching to backup system when primary system fails |
| **Replication** | Copying data from one database to another for redundancy or read scaling |
| **Sharding** | Partitioning data across multiple databases based on a key (e.g., user ID) |
| **Eventual Consistency** | Data consistency model where all replicas eventually converge to same state (may be temporarily inconsistent) |
| **Last-Write-Wins** | Conflict resolution strategy where most recent write takes precedence |
| **Audit Trail** | Log of all actions performed on a system (who, what, when) |
| **Compliance** | Adherence to regulatory requirements (e.g., SOC 2, HIPAA, GDPR) |
| **Data Classification** | Categorizing data by sensitivity level (e.g., Public, Internal, Confidential) |
| **Threat Model** | Analysis of potential security threats and mitigations |
| **Penetration Testing** | Security testing where authorized attacker attempts to break into system |
| **Observability** | Ability to understand system behavior through logs, metrics, and traces |
| **Instrumentation** | Adding code to collect logs, metrics, and traces |
| **Prometheus** | Open-source monitoring and alerting system |
| **Grafana** | Open-source visualization platform for metrics |
| **ELK Stack** | Elasticsearch, Logstash, Kibana — open-source log aggregation and analysis platform |
| **Splunk** | Commercial log aggregation and analysis platform |
| **CloudWatch** | AWS monitoring and logging service |
| **Azure Monitor** | Azure monitoring and logging service |
| **Google Cloud Monitoring** | Google Cloud monitoring and logging service |
| **OpenTelemetry** | Open standard for distributed tracing and metrics collection |
| **Distributed Tracing** | Tracking requests across multiple services to understand system behavior |
| **Systemd** | Linux system and service manager |
| **Docker** | Container platform for packaging and running applications |
| **Docker Compose** | Tool for defining and running multi-container Docker applications |
| **Kubernetes** | Container orchestration platform for managing containerized applications at scale |
| **CI/CD** | Continuous Integration / Continuous Deployment — automated build, test, and deployment pipeline |
| **Git** | Version control system for tracking code changes |
| **GitHub Actions** | CI/CD platform integrated with GitHub |
| **Maven** | Build tool for Java projects |
| **Gradle** | Alternative build tool for Java projects |
| **npm** | Package manager for JavaScript/Node.js |
| **Vite** | Modern build tool and dev server for frontend projects |
| **Webpack** | Module bundler for JavaScript |
| **Babel** | JavaScript transpiler for converting modern JavaScript to older syntax |
| **ESLint** | JavaScript linter for catching code quality issues |
| **Jest** | JavaScript testing framework |
| **Vitest** | Modern JavaScript testing framework (alternative to Jest) |
| **Postman** | Tool for testing and documenting APIs |
| **Swagger / OpenAPI** | Standard for documenting REST APIs |
| **REST** | Representational State Transfer — architectural style for building APIs |
| **GraphQL** | Query language for APIs (alternative to REST) |
| **gRPC** | High-performance RPC framework (alternative to REST) |
| **JSON** | JavaScript Object Notation — lightweight data format |
| **CSV** | Comma-Separated Values — simple text format for tabular data |
| **XML** | Extensible Markup Language — text format for structured data |
| **YAML** | YAML Ain't Markup Language — human-readable data format |
| **HTTP** | HyperText Transfer Protocol — protocol for web communication |
| **HTTP Status Codes** | Standardized codes indicating result of HTTP request (e.g., 200 OK, 404 Not Found, 500 Internal Server Error) |
| **REST API** | API following REST architectural principles |
| **Endpoint** | URL path for a specific API operation |
| **Request** | HTTP message sent by client to server |
| **Response** | HTTP message sent by server to client |
| **Request Body** | Data sent in HTTP request (usually JSON) |
| **Response Body** | Data sent in HTTP response (usually JSON) |
| **Query Parameter** | Parameter passed in URL query string (e.g., `?search=keyword`) |
| **Path Parameter** | Parameter passed in URL path (e.g., `/notes/{id}`) |
| **Header** | Metadata sent with HTTP request or response |
| **Status Code** | Numeric code indicating result of HTTP request |
| **Error Code** | Application-specific code indicating type of error |
| **Error Message** | Human-readable description of error |
| **Validation** | Checking that input data is correct format and within acceptable range |
| **Sanitization** | Removing or escaping potentially dangerous characters from input |
| **Encoding** | Converting data to specific format (e.g., JSON encoding, URL encoding) |
| **Decoding** | Converting data from specific format back to original form |
| **Serialization** | Converting object to format suitable for storage or transmission (e.g., JSON) |
| **Deserialization** | Converting serialized data back to object |
| **Schema** | Definition of structure and constraints for data (e.g., database schema, JSON schema) |
| **Migration** | Process of changing database schema or data format |
| **Rollback** | Reverting to previous state after failed operation or deployment |

---

## DOCUMENT SIGN-OFF

**Document Owner:** Engineering Leadership  
**Last Updated:** [Current Date]  
**Status:** Ready for Development  
**Next Review:** After 3 months of production use

**Approvals:**

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Product Manager | — | — | — |
| Engineering Lead | — | — | — |
| Security Officer | — | — | — |
| IT Operations | — | — | — |

---

**END OF TECHNICAL REQUIREMENTS DOCUMENT**