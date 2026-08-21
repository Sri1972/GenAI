---
name: fastapi-backend
description: How the generated app's SQLite + FastAPI backend works — the auto-generated REST surface (/api/data/{table}, /aggregate, /api/metadata, /api/chat) and the useApi hook contract. Load when writing schema.sql/seed.sql/types.ts or wiring pages to data.
---

# fastapi-backend

Every generated app has a Python FastAPI server (`api/app_server.py`, Python-managed —
do not edit it) that reads `api/schema.sql` + `api/seed.sql` into `data.db` and exposes an
auto-generated REST API per table. You author `api/schema.sql`, `api/seed.sql`,
`src/types.ts`, and the pages that consume the data.

## The API surface (auto-generated from your schema)
- `GET /api/data/{table}?sort=col&order=asc&limit=50` — rows (snake_case fields).
- `GET /api/data/{table}/{id}` · `POST/PUT/DELETE /api/data/{table}` — CRUD.
- `GET /api/data/{table}/aggregate?groupBy=col&metric=sum:amount` — grouped metrics.
- `GET /api/metadata` — tables/columns.
- `POST /api/chat` — LLM chat: body `{messages:[{role,content}], context}` (never `{message}`/`{prompt}`).

## Frontend contract
- Fetch with the pre-bundled hook: `import { useApi, apiAggregate } from '../hooks/useApi'`
  (`src/hooks/useApi.ts` is Python-managed — import, never recreate).
- Never `fetch('/api/...')` directly; never import from `../data`.
- Table + column names are snake_case and MUST match `schema.sql` exactly.

## schema.sql / seed.sql rules
- Every main table: ≥5 columns, ≥50 realistic seed rows (no `test`/`lorem`/`999` placeholders).
- No circular FKs. Use multi-row INSERT syntax.
- Each table needs a matching PascalCase interface in `src/types.ts`.

Reference implementations: `references/app_server_template.py`, `references/useApi.hook.ts`,
`references/datachat_api_server.py` (LLM data-chat backend).
