# Automotive Forecasting — API-source MCP (self-discovery test)

## Overview

API-source MCP wrapping the already-running automotive forecasting Web
API — now backend-agnostic on purpose: this test points at a **Java**
build of the same API (previously tested against the Python build), to
confirm discovery genuinely doesn't care about backend language — it only
ever talks to the API's own OpenAPI/Swagger spec over HTTP, never touches
its source.

This variant also switches from a manually-curated endpoint list to
**`POST /api/mcp/generate-from-instructions`** — the new instructions-only
entry point. Instead of running the endpoints through the Web UI's
browse → introspect → check-boxes flow, this test hands the source (base
URL + credentials) and guidance to the endpoint as one plain-text blob and
lets it discover the real endpoints itself via `introspect_openapi()`
against the live spec — nothing here tells it what endpoints exist.

## Source

- Source type: **API**
- Base URL: `http://127.0.0.1:8400` (the Java build currently running there)
- Auth: Basic — `admin` / `c1dJh6LJYV8FnP50` (as already updated — re-check
  the project's own `.env` if it's since changed)

## Endpoints

Not listed here — that's the point of this test. `/api/mcp/generate-from-instructions`
discovers them itself by probing `http://127.0.0.1:8400`'s own OpenAPI/Swagger
spec (see `introspect_openapi()` in `mcp_agents/mcp_introspect.py`); nothing
in this file tells it what endpoints exist. If discovery finds fewer than
expected, that's a real signal the Java build isn't exposing its spec the
same way the Python one did — worth comparing against `GET /openapi.json`
(or whichever path it serves) on both directly.

## Instructions (the single text blob this endpoint takes)

```
Build an MCP server for the automotive forecasting API at http://127.0.0.1:8400.
It uses Basic Auth — username admin, password c1dJh6LJYV8FnP50.

Discover its real endpoints yourself rather than assuming any — I'm not
listing them here on purpose. Write tool descriptions that make the unit of
each report explicit (per vehicle program vs. per plant vs. per region vs.
per component) since there are enough endpoints here that a vague
description could get mixed up with a similarly-named one for a different
entity.
```

## How to test

```bash
curl -s -X POST http://localhost:3000/api/mcp/generate-from-instructions \
  -H "Content-Type: application/json" \
  -d '{
    "projectName": "auto-forecast-mcp",
    "instructions": "Build an MCP server for the automotive forecasting API at http://127.0.0.1:8400. It uses Basic Auth -- username admin, password c1dJh6LJYV8FnP50. Discover its real endpoints yourself rather than assuming any -- I am not listing them here on purpose. Write tool descriptions that make the unit of each report explicit (per vehicle program vs. per plant vs. per region vs. per component) since there are enough endpoints here that a vague description could get mixed up with a similarly-named one for a different entity."
  }'
# -> {"requestId": "...", "status": "running", "projectName": "auto-forecast-mcp"}

# Poll until status is "completed" or "failed":
curl -s http://localhost:3000/api/jobs/<requestId>
```

(Port `3000` assumes the default `TURBOUI_PORT` — swap in whatever port
your TurboAppGenerator instance is actually running on.)

## Suggested test questions (via "Try it", once the MCP server is up)

- "How accurate were the sales forecasts for [pick a program]?"
- "Which components are highest-risk for [pick a program]?"
- "How utilized is [pick a plant]?"
- "What's the powertrain mix in [pick a region]?" — confirms it resolves
  "region" correctly rather than confusing it with a plant or program.
- "Who supplies [pick a component]?"
