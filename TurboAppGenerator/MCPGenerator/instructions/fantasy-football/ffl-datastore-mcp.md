# Fantasy Football — Datastore MCP

## Overview

Builds an MCP server directly on top of the SQLite database already
generated for the `ffl-python-1` Web API project — no need to go through
that API at all; the MCP's own generated backing API talks to the same
`.db` file directly. Good test of the datastore path end-to-end: table
descriptions the LLM has to infer on its own, plus a custom cross-table
tool (weekly fantasy score) that only the datastore path can build, since
it requires a join + aggregate no single existing endpoint provides.

## Source

- Source type: **Datastore (SQLite)**
- Database file (full path, not relative — the server resolves this
  against its own working directory, not against `WebAPIGenerator/`):
  `C:\Users\srikanth.c4\OneDrive - S&P Global\Work\SourceCode\GenAI\Agents\TurboAppGenerator\WebAPIGenerator\generated\web-api\ffl-python-1\ffl.db`

## Tables

Select all six:

- `leagues` — id, name, season_year, created_at
- `nfl_players` — id, full_name, nfl_team, position, created_at
- `fantasy_teams` — id, league_id, team_name, owner_name, created_at
- `player_weekly_stats` — id, nfl_player_id, week_number, fantasy_points,
  created_at
- `matchups` — id, league_id, week_number, team_a_id, team_b_id, created_at
- `roster_slots` — id, fantasy_team_id, nfl_player_id, is_starting,
  acquired_date, created_at

Leave every table/column description blank on purpose for this one — the
point is to confirm the LLM fills in sensible descriptions on its own (e.g.
inferring `is_starting` means "in the active lineup vs. on the bench", not
just echoing the column name back).

## Instructions (paste into the Instructions field)

```
Add a tool that computes a fantasy team's total score for a given week —
sum player_weekly_stats.fantasy_points for every player on that team's
roster where is_starting is true for that week (join roster_slots ->
player_weekly_stats on nfl_player_id and week_number). Also add a tool
that returns the full league standings for a season: for every fantasy
team in a league, their total points across all weeks and how many
matchups they've been part of.
```

## Suggested test questions (via "Try it")

- "What tables and tools do you have access to?" — confirms the
  LLM-authored descriptions read naturally, not just column-name echoes.
- "What's fantasy team [pick a team_name]'s score for week 3?" — exercises
  the custom weekly-score join tool.
- "Show me the league standings." — exercises the custom standings tool.
- "Which players are on [team]'s bench right now?" — should resolve via
  `roster_slots.is_starting = false` without you having to say that in the
  question.
