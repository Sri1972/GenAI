# Youth Sports League API

## Overview

A recreational sports league's team/schedule/results system: teams, players,
coaches, games, and standings. Different shape from the other sample domains
specifically to exercise standings computed entirely at read time from a
history of individual game results (wins/losses/ties/points for/against),
never stored as a running total, plus a schedule that references the same
Teams table twice (home and away) in one row.

## Suggested form settings (API options)

- Language: Python (FastAPI) or Java (Spring Boot) — either works
- Auth type: Basic Auth
- Rate limit: 100 (req/min)

---

## Resources

### Teams
Fields: id, name, city, division (north / south / east / west), created_at.

### Coaches
Fields: id, team_id (FK → teams.id), first_name, last_name, email (unique),
created_at.

### Players
Fields: id, team_id (FK → teams.id), first_name, last_name, jersey_number,
position, birth_date, created_at.

### Games
One row per scheduled/played game — referencing Teams twice. Fields: id,
home_team_id (FK → teams.id), away_team_id (FK → teams.id), game_date,
venue, status (scheduled / final / postponed / cancelled), home_score
(nullable until final), away_score (nullable until final), created_at.

### PlayerGameStats
Per-player, per-game stats — the source data standings/leaderboards read
from. Fields: id, game_id (FK → games.id), player_id (FK → players.id),
points_scored, minutes_played, created_at.

---

## Endpoints

### Catalog
- `GET /teams` — list all; support `division` filter
- `GET /teams/{id}` — **complex join**: the team plus its full player
  roster and coaching staff
- `GET /players` — list all; support `team_id` filter
- `POST /teams` — create
- `POST /players` — create

### Schedule & Results
- `GET /games` — list all; support `team_id` (matches either home OR away)
  and `status` filters
- `POST /games` — create a scheduled game (status defaults to `scheduled`)
- `PATCH /games/{id}/result` — record `home_score`/`away_score` and set
  `status` to `final` in one call; reject with 400 if the game is already
  `final` or `cancelled`
- `GET /games/{id}` — **complex join**: the game plus both teams' names and
  every PlayerGameStats row for it, each with the player's name

### Standings & Leaderboards (multi-table aggregates, computed at read time)
- `GET /standings` — **complex join**: for every team, wins/losses/ties,
  points-for, points-against, and point differential — all derived by
  scanning every `final` Game where the team played as either home OR away,
  never stored as a running total; support a `division` filter
- `GET /teams/{id}/schedule` — **complex join**: every game this team is
  part of (home or away), each with the opponent's name and, if final, the
  result from this team's perspective (win/loss/tie)
- `GET /players/{id}/season-stats` — **complex join**: total points scored
  and total minutes played across every PlayerGameStats row for this
  player, plus a per-game breakdown with the opponent's name and date

---

## Data Rules

- A Game's `home_score`/`away_score` are only ever set together, via the
  result endpoint — never independently, and never before `status` becomes
  `final`.
- Standings (wins/losses/ties/points-for/points-against) are NEVER stored
  columns anywhere — always recomputed from the full Games history at
  request time, so a corrected result immediately changes standings on the
  next read.
- A team's win/loss/tie for a given final game depends on which side (home
  or away) it played — this must be resolved correctly in both directions,
  not just for the home team.
- Seed data: 8 teams across all 4 divisions, 3-5 players per team, 1-2
  coaches per team, 20+ games (a mix of `final`, `scheduled`, and at least 1
  `postponed`/`cancelled`) spread across all teams so every team has played
  a realistic mix of home and away games, and PlayerGameStats for every
  `final` game's participating players — enough that `/standings` shows
  realistic, differentiated records across teams out of the box.

---

## General Requirements

- Return proper HTTP status codes and JSON error bodies `{"error": "..."}`.
- All list endpoints should support pagination (`limit`/`offset`).
- Include a README with setup + run instructions, an entity-relationship
  summary, and where to find the generated Basic Auth credentials.
