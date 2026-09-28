# Library Management — Datastore MCP

## Overview

Datastore-source MCP on `library-java-1`'s SQLite file — confirms the
datastore path works identically regardless of which language actually
generated the underlying database (this one's a Java/Spring Boot project,
unlike the two Python ones above). The real point of this one: a genuine
many-to-many join (`book_authors`) feeding a popularity aggregate, plus a
date-driven "overdue" status that's derived, not stored.

## Source

- Source type: **Datastore (SQLite)**
- Database file (full path, not relative — the server resolves this
  against its own working directory, not against `WebAPIGenerator/`):
  `C:\Users\srikanth.c4\OneDrive - S&P Global\Work\SourceCode\GenAI\Agents\TurboAppGenerator\WebAPIGenerator\generated\web-api\library-java-1\library.db`

## Tables

Select all six:

- `authors` — id, name, birth_year, country, created_at
- `books` — id, title, isbn, publication_year, genre, total_copies,
  available_copies, created_at
- `book_authors` — id, book_id, author_id, created_at (the many-to-many
  join table)
- `members` — id, first_name, last_name, email, membership_date,
  membership_status, phone, created_at
- `loans` — id, book_id, member_id, loan_date, due_date, return_date,
  status, created_at
- `reservations` — id, book_id, member_id, reservation_date, status,
  created_at

Leave descriptions blank — this one's specifically to confirm the LLM
correctly infers that `book_authors` is a join table (not a "real" entity
worth its own list tool) purely from its shape (two FK columns, no other
data), the same judgment call the Web API generator's own architect has to
make.

## Instructions (paste into the Instructions field)

```
Add a tool that reports an author's total loan count across every book
they've written — join authors -> book_authors -> books -> loans, count
loans regardless of status. Add a second tool that lists a member's
currently overdue loans: status is "active" and due_date is before today,
each with the book's title.
```

## Suggested test questions (via "Try it")

- "Which author has the most loans across all their books?" — exercises
  the popularity tool and requires it to actually walk the three-table
  join, not just query `loans` alone.
- "Does [pick a member] have anything overdue right now?" — exercises the
  overdue tool; try it against a member you know has an overdue loan (see
  the library API's own seed data / `/members/{id}/summary` endpoint if
  you need to check which one).
- "How many copies of [pick a title] are available right now?" — a plain
  lookup, no custom tool needed — good contrast case.
