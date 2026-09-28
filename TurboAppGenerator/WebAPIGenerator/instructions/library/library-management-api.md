# Library Management API

## Overview

A public library's catalog and circulation system: authors ↔ books (a real
many-to-many, not a single-owner relationship), members, loans, and
reservations. Different shape from the other sample domains specifically to
exercise a many-to-many catalog relationship, date-driven business rules
(due dates, overdue detection) computed at read time rather than stored, and
aggregate reporting across that many-to-many join (an author's total loan
count across every book they've written).

## Suggested form settings (API options)

- Language: Python (FastAPI) or Java (Spring Boot) — either works
- Auth type: Basic Auth
- Rate limit: 100 (req/min)

---

## Resources

### Authors
Fields: id, name, birth_year, country, created_at.

### Books
Fields: id, title, isbn (unique), publication_year, genre
(fiction / non-fiction / science / biography / children), total_copies,
available_copies (starts equal to total_copies, decremented/incremented by
loan activity — never edited directly by a client), created_at.

### BookAuthors
Many-to-many join table between Books and Authors — a book can have more
than one author, an author can have written more than one book. Fields: id,
book_id (FK → books.id), author_id (FK → authors.id), created_at.

### Members
Fields: id, first_name, last_name, email (unique), phone, membership_date,
membership_status (active / suspended / expired), created_at.

### Loans
Fields: id, book_id (FK → books.id), member_id (FK → members.id), loan_date,
due_date (loan_date + 14 days, computed at creation), return_date
(nullable — set when returned), status (active / returned / overdue),
created_at.

### Reservations
Fields: id, book_id (FK → books.id), member_id (FK → members.id),
reservation_date, status (pending / fulfilled / cancelled), created_at.

---

## Endpoints

### Catalog
- `GET /authors` — list all
- `GET /books` — list all; support `genre` and `author_id` filters (the
  latter via the BookAuthors join)
- `GET /books/{id}` — **complex join**: the book plus every author's name
  (via BookAuthors), and its current `available_copies`
- `POST /authors` — create
- `POST /books` — create (with an `author_ids` array — creates the
  BookAuthors rows in the same call)

### Members
- `GET /members` — list all; support `membership_status` filter
- `POST /members` — create

### Loans & Reservations
- `POST /loans` — create a loan for a book/member; reject with 400 if
  `available_copies` is 0, or if the member's `membership_status` isn't
  `active`; on success, decrement the book's `available_copies` by 1 and
  set `due_date` = today + 14 days
- `POST /loans/{id}/return` — set `return_date` = today, `status` =
  `returned`; increment the book's `available_copies` by 1
- `GET /loans` — list all; support `member_id` and `status` filters
- `GET /members/{id}/loans` — **complex join**: every loan by this member,
  each with the book's title and author name(s), and a computed `overdue`
  boolean (`status == 'active' AND due_date < today`) — not a stored column,
  derived at read time

### Reporting (multi-table aggregates)
- `GET /books/{id}/loan-history` — **complex join**: every loan ever placed
  for this book, each with the borrowing member's name and loan/return dates
- `GET /members/{id}/summary` — **complex join**: total loans ever placed,
  count currently active, count currently overdue, and the list of
  currently-overdue loans with book title and due date
- `GET /authors/{id}/popularity` — **complex join**: total loan count across
  every book this author has written (authors → book_authors → books →
  loans), plus a per-book breakdown

---

## Data Rules

- `Books.isbn` and `Members.email` must be unique; reject duplicates with
  400.
- `Loans.due_date` is always `loan_date + 14 days`, computed once at
  creation — never recalculated later even if business rules change.
- A loan can only be created if the book's `available_copies > 0` and the
  member's `membership_status == 'active'` — reject with 400 and a clear
  message otherwise.
- Returning a loan must set both `return_date` and `status` and increment
  `available_copies` in the same operation.
- "Overdue" is never a value a client sets directly — it's derived from
  `status == 'active' AND due_date < today` wherever it's reported.
- Seed data: 8 authors, 12 books (with at least 3 books having 2+ authors,
  to actually exercise the many-to-many join), 10 members across all three
  statuses, 15 loans (a mix of returned, active-not-yet-due, and
  active-overdue — at least 4 overdue so `/summary` and the overdue lists
  return real, non-empty results), 5 reservations — enough that every
  complex-join endpoint above returns realistic, multi-row results out of
  the box.

---

## General Requirements

- Return proper HTTP status codes and JSON error bodies `{"error": "..."}`.
- All list endpoints should support pagination (`limit`/`offset`).
- Include a README with setup + run instructions, an entity-relationship
  summary, and where to find the generated Basic Auth credentials.
