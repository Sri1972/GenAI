# Fantasy Football (NFL) League API

## Overview

A fantasy football league manager: leagues, fantasy teams, real NFL
players, rosters, weekly matchups, and weekly stat lines. Different shape
from the other sample domains specifically to exercise a scored many-to-many
roster (a fantasy team's weekly score is the sum of its currently-started
players' stats for that specific week, computed by joining through the
roster, never stored) plus head-to-head matchups whose winner is derived
from two teams' computed weekly scores, not stored either.

## Suggested form settings (API options)

- Language: Python (FastAPI) or Java (Spring Boot) — either works
- Auth type: Basic Auth
- Rate limit: 100 (req/min)

---

## Resources

### Leagues
Fields: id, name, season_year, created_at.

### FantasyTeams
Fields: id, league_id (FK → leagues.id), team_name, owner_name, created_at.

### NflPlayers
Fields: id, full_name, nfl_team (e.g. "KC", "SF"), position
(QB / RB / WR / TE / K / DEF), created_at.

### RosterSlots
Many-to-many join between FantasyTeams and NflPlayers — which real player
is on which fantasy team's roster, and whether they're started or benched
for scoring purposes. Fields: id, fantasy_team_id (FK → fantasy_teams.id),
nfl_player_id (FK → nfl_players.id), is_starting, acquired_date, created_at.

### PlayerWeeklyStats
One row per NFL player, per week, per season — the source data weekly
fantasy scores are computed from. Fields: id, nfl_player_id
(FK → nfl_players.id), week_number (1-18), fantasy_points, created_at.

### Matchups
One head-to-head fantasy matchup per week. Fields: id, league_id
(FK → leagues.id), week_number, team_a_id (FK → fantasy_teams.id),
team_b_id (FK → fantasy_teams.id), created_at.

---

## Endpoints

### Catalog
- `GET /leagues` — list all
- `GET /fantasy-teams` — list all; support `league_id` filter
- `GET /fantasy-teams/{id}` — **complex join**: the team plus its full
  roster, each player's name/position/nfl_team and `is_starting` flag
- `GET /nfl-players` — list all; support `position` and `nfl_team` filters
- `POST /fantasy-teams` — create
- `POST /roster-slots` — add a real player to a fantasy team's roster
  (reject with 400 if that player is already on this team's roster)

### Scoring
- `PATCH /roster-slots/{id}/lineup` — flip `is_starting` true/false for one
  roster slot (setting a starting lineup for the week)
- `GET /fantasy-teams/{id}/weekly-score` — **complex join**: given a
  `week_number` query param, the sum of `fantasy_points` from
  PlayerWeeklyStats for every player on this team's roster where
  `is_starting` is true, plus a per-player breakdown — computed fresh
  every call, never a stored total
- `GET /matchups` — list all; support `league_id` and `week_number` filters
- `GET /matchups/{id}` — **complex join**: both teams' names plus each
  team's computed weekly score for that matchup's `week_number` (reusing
  the same scoring logic as `/weekly-score`) and the derived winner

### Reporting (multi-table aggregates)
- `GET /leagues/{id}/standings` — **complex join**: for every team in the
  league, wins/losses derived from every Matchup they've played by
  comparing both sides' computed weekly scores — never a stored win/loss
  count
- `GET /nfl-players/{id}/season-log` — **complex join**: every
  PlayerWeeklyStats row for this player across the season, in week order

---

## Data Rules

- A player can only be added once to the same fantasy team's roster —
  reject a duplicate `POST /roster-slots` with 400.
- A fantasy team's weekly score is ALWAYS computed on demand from
  PlayerWeeklyStats joined through currently-`is_starting` RosterSlots for
  that team — never cached or stored, so benching a player changes future
  score calculations immediately (but never rewrites a past week's
  already-computed result retroactively — scoring for a given past week
  uses that week's `is_starting` state at the time it's queried, which is
  the current state, matching how live fantasy platforms only show
  current lineups; there is no historical lineup snapshot in this model).
- A Matchup's winner is derived by comparing both teams' computed weekly
  scores for that matchup's specific `week_number` — never stored as a
  winner_id column.
- Seed data: 1 league with 6 fantasy teams, 40+ NFL players across all
  positions and several nfl_team values, 8-10 roster slots per fantasy
  team (mostly `is_starting=true`, a few benched), PlayerWeeklyStats for
  weeks 1-3 for every rostered player, and matchups for weeks 1-3 pairing
  up all 6 teams each week — enough that standings and weekly scores show
  real, differentiated, non-zero results out of the box.

---

## General Requirements

- Return proper HTTP status codes and JSON error bodies `{"error": "..."}`.
- All list endpoints should support pagination (`limit`/`offset`).
- Include a README with setup + run instructions, an entity-relationship
  summary, and where to find the generated Basic Auth credentials.
