# Gym Class Booking API

## Overview

A fitness studio's class-scheduling and booking system: gyms, trainers,
classes, members, and bookings. Different shape from the other sample
domains specifically to exercise a capacity-constrained many-to-many
booking (a class session has a fixed number of spots) with an automatic
waitlist that promotes the next waitlisted member the moment a spot frees
up — a cross-row business rule triggered by a cancellation, not just a
create.

## Suggested form settings (API options)

- Language: Python (FastAPI) or Java (Spring Boot) — either works
- Auth type: Basic Auth
- Rate limit: 100 (req/min)

---

## Resources

### Gyms
Fields: id, name, city, address, created_at.

### Trainers
Fields: id, gym_id (FK → gyms.id), first_name, last_name, specialty
(yoga / strength / cardio / cycling / pilates), created_at.

### ClassSessions
One scheduled occurrence of a class. Fields: id, gym_id (FK → gyms.id),
trainer_id (FK → trainers.id), class_name, session_datetime, capacity,
status (scheduled / completed / cancelled), created_at.

### Members
Fields: id, first_name, last_name, email (unique), membership_tier
(basic / premium), join_date, created_at.

### Bookings
Many-to-many join between ClassSessions and Members, with its own status.
Fields: id, class_session_id (FK → class_sessions.id), member_id
(FK → members.id), status (confirmed / waitlisted / cancelled),
booked_at, created_at.

---

## Endpoints

### Catalog
- `GET /gyms` — list all
- `GET /trainers` — list all; support `gym_id` filter
- `GET /class-sessions` — list all; support `gym_id`, `trainer_id`, and
  `status` filters
- `GET /class-sessions/{id}` — **complex join**: the session plus the
  trainer's name, the gym's name, current confirmed-booking count, and
  remaining capacity
- `POST /class-sessions` — create
- `POST /members` — create

### Bookings
- `POST /bookings` — book a member into a session; if confirmed bookings
  are already at `capacity`, create it with status `waitlisted` instead of
  rejecting outright; reject with 400 only if the member already has a
  non-cancelled booking for that same session
- `POST /bookings/{id}/cancel` — set status to `cancelled`; if this freed a
  confirmed spot, promote the earliest-booked `waitlisted` booking for the
  same session to `confirmed` in the same operation — a real cross-row
  side effect, not just a status flip on the row being cancelled
- `GET /bookings` — list all; support `member_id` and `status` filters

### Reporting (multi-table aggregates)
- `GET /members/{id}/booking-history` — **complex join**: every booking
  this member has made, each with the class name, trainer name, session
  datetime, and final status
- `GET /class-sessions/{id}/roster` — **complex join**: every confirmed
  booking for this session with the member's name, plus the waitlist in
  booked-at order with each waitlisted member's name
- `GET /trainers/{id}/utilization` — **complex join**: for this trainer,
  total sessions taught, average confirmed-bookings-to-capacity ratio
  across those sessions, and a per-session breakdown

---

## Data Rules

- `Members.email` must be unique; reject duplicates with 400.
- A ClassSession's confirmed-booking count must never exceed its
  `capacity` — enforced by routing overflow bookings to `waitlisted`
  instead of rejecting the request.
- Cancelling a `confirmed` booking must promote the oldest `waitlisted`
  booking (by `booked_at`) for the same session to `confirmed`, if one
  exists, in the same request — never left for a separate call.
- Cancelling an already-`waitlisted` or already-`cancelled` booking never
  promotes anyone.
- Seed data: 2 gyms, 4-6 trainers, 15 class sessions spread across both
  gyms and a mix of statuses, 12 members, and 40+ bookings — including at
  least 2 sessions deliberately overbooked into `waitlisted` bookings, so
  `/class-sessions/{id}/roster`'s waitlist section returns real, non-empty
  results out of the box.

---

## General Requirements

- Return proper HTTP status codes and JSON error bodies `{"error": "..."}`.
- All list endpoints should support pagination (`limit`/`offset`).
- Include a README with setup + run instructions, an entity-relationship
  summary, and where to find the generated Basic Auth credentials.
