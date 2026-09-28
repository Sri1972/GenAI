# Gym Class Booking — Datastore MCP

## Overview

Datastore-source MCP on `gym-class-booking-python-1`'s SQLite file.
Different join shape from the fantasy-football one: capacity/utilization
across a booking table, rather than a scoring aggregate — good test of
whether the LLM's custom-tool SQL correctly counts booking rows per
session rather than just listing them.

## Source

- Source type: **Datastore (SQLite)**
- Database file (full path, not relative — the server resolves this
  against its own working directory, not against `WebAPIGenerator/`):
  `C:\Users\srikanth.c4\OneDrive - S&P Global\Work\SourceCode\GenAI\Agents\TurboAppGenerator\WebAPIGenerator\generated\web-api\gym-class-booking-python-1\gym_class_booking.db`

## Tables

Select all five:

- `gyms` — id, name, city, address, created_at
- `members` — id, first_name, last_name, email, membership_tier, join_date,
  created_at
- `trainers` — id, gym_id, first_name, last_name, specialty, created_at
- `class_sessions` — id, gym_id, trainer_id, class_name, session_datetime,
  capacity, status, created_at
- `bookings` — id, class_session_id, member_id, status, booked_at,
  created_at

This time, type in a couple of real descriptions yourself first (e.g. for
`class_sessions.capacity`: "maximum number of members that can book this
session") and leave the rest blank — good test that the LLM fills in the
gaps without touching what you already wrote.

## Instructions (paste into the Instructions field)

```
Add a tool that reports a class session's current booking count and
remaining capacity — count bookings for that session with status not
"cancelled", compared against class_sessions.capacity. Add a second tool
that reports a trainer's full upcoming schedule: every class_session they
lead with status "scheduled", each with its booking count.
```

## Suggested test questions (via "Try it")

- "How full is [pick a class_name] on [its session_datetime]?" — exercises
  the capacity tool.
- "What's [pick a trainer]'s upcoming schedule look like?" — exercises the
  trainer-schedule tool.
- "Which gym has the most members?" — a plain aggregate the LLM should be
  able to answer even without a dedicated custom tool, straight off the
  mechanical list tools.
