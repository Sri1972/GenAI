# TaskFlow API — Minimal Test API

## Overview

A simple task-management REST API, sized to validate the API-generation pipeline end-to-end
(architecture → data modeling → implementation → security → testing → packaging) without a
large surface area to debug if something breaks.

## Suggested form settings (API options)

- Language: Python (FastAPI)
- Auth type: None (keep the first test minimal — try Basic Auth on a later run)
- Rate limit: 0 (off)

---

## Resources

### Users
Fields: id, name, email (unique), created_at.

### Tasks
Fields: id, title, description, status (todo / in_progress / done), priority (low / medium / high),
due_date, owner_id (foreign key → users.id), created_at, updated_at.

---

## Endpoints

### Users
- `GET /users` — list all users
- `GET /users/{id}` — get one user
- `POST /users` — create a user
- `PUT /users/{id}` — update a user
- `DELETE /users/{id}` — delete a user

### Tasks
- `GET /tasks` — list all tasks; support optional query params `status` and `owner_id` to filter
- `GET /tasks/{id}` — get one task
- `POST /tasks` — create a task
- `PUT /tasks/{id}` — update a task (partial updates allowed)
- `DELETE /tasks/{id}` — delete a task
- `GET /tasks/{id}/owner` — return the full user record for the task's owner_id

---

## Data Rules

- `owner_id` must reference an existing user — reject task creation/update with a 400 if the
  referenced user doesn't exist.
- `status` and `priority` are constrained to the exact enum values listed above — reject
  anything else with a 400 and a clear error message.
- Seed the database with 5 users and 15 tasks spread across all status/priority values, with
  due dates spread across the next 60 days.

---

## General Requirements

- Return proper HTTP status codes (200/201/204/400/404) and JSON error bodies `{"error": "..."}`.
- Include a README with setup + run instructions.
