# requirements.txt:
# fastmcp
# httpx

"""
Shared MCP (Model Context Protocol) server for the AI-chat feature.

Backend-agnostic by design: every tool talks only to DATA_API_BASE's REST API
— never a database connection directly — so the exact same module works
mounted inside any of:
  - app_server_template.py (pure-Python, old generic-template backend):
    DATA_API_BASE points back at this same process's own port, routes are
    /api/metadata, /api/data/{table}.
  - datachat_api_server.py (sidecar): DATA_API_BASE points at a separate
    backend's port — either the old generic-template shape above, a Java
    Spring Boot backend (same /api/data/{table} shape), or the new named-
    route pipeline (CrewOrchestrator._run_backend_generation), which serves
    /api/metadata and /api/{table} instead (no /data/ segment).
Every table-data call below tries the new named-route shape first and falls
back to the old /api/data/{table} shape on a non-2xx — this file doesn't
know in advance which backend it's talking to, so it can't just pick one.

Exposes a SMALL, STATIC set of tools rather than one dynamically-generated tool
per table. Real MCP clients call tools/list once at session init and expect a
stable set — regenerating tools per-table after a lazy discovery step (the
previous "MCP-style" design) has no meaning to a client connecting independently
of this app's own chat loop. Each tool's docstring tells the LLM to call
get_api_metadata first, which is the (former) per-table discovery step exposed
as a normal tool result instead of baked into N different tool schemas.
"""

import json
import os
from pathlib import Path
from typing import Any

import httpx
from fastmcp import FastMCP

DATA_API_BASE = os.getenv("DATA_API_BASE", "http://localhost:8080")

# Written post-boot by WebUIGenerator's _build_mcp_metadata_file (reuses
# MCPGenerator's own introspection logic — mcp_agents.mcp_introspect — to
# capture the real database schema AND the real API's full OpenAPI endpoint
# list, including any custom join/aggregate route the app's own requirements
# asked for). Read by list_custom_endpoints/call_endpoint below.
_METADATA_FILE = Path(__file__).resolve().parent / "mcp_metadata.json"

_data_client = httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0))

mcp = FastMCP("data-api")

# --- Lazy, cached table/column discovery (same shape as the old _discover_api) ---
_tables_cache: list[dict[str, Any]] | None = None


def _infer_column_meta(col_name: str, values: list) -> dict:
    """Infer column type and valid values from sample data."""
    meta: dict[str, Any] = {"name": col_name}
    non_empty = [v for v in values if v is not None and str(v).strip() != ""]
    if not non_empty:
        meta["type"] = "text"
        return meta

    numeric_count = sum(
        1 for v in non_empty
        if isinstance(v, (int, float)) or (isinstance(v, str) and v.replace(".", "", 1).replace("-", "", 1).isdigit())
    )
    if numeric_count == len(non_empty):
        meta["type"] = "numeric"
        nums = [float(v) for v in non_empty]
        meta["range"] = [min(nums), max(nums)]
        return meta

    unique = sorted(set(str(v) for v in non_empty))
    if len(unique) <= 20:
        meta["type"] = "categorical"
        meta["values"] = unique
    else:
        meta["type"] = "text"
        meta["sample_values"] = unique[:5]
    return meta


async def _discover_tables() -> list[dict[str, Any]]:
    """Discover table names, then sample each one to infer rich column metadata
    (type, categorical values, numeric ranges) — cached after the first call."""
    global _tables_cache
    if _tables_cache is not None:
        return _tables_cache

    table_names: list[str] = []
    try:
        resp = await _data_client.get(f"{DATA_API_BASE}/api/metadata")
        if resp.status_code == 200:
            meta = resp.json()
            raw_tables = meta.get("tables", [])
            if raw_tables and isinstance(raw_tables[0], dict):
                table_names = [t.get("table") or t.get("name") for t in raw_tables]
            else:
                table_names = raw_tables
        else:
            # Spring Boot fallback shape
            resp = await _data_client.get(f"{DATA_API_BASE}/api/tables")
            if resp.status_code == 200:
                table_names = resp.json().get("tables", [])
    except Exception as e:
        print(f"[mcp_server] WARNING: could not discover tables: {e}", flush=True)
        return []

    tables: list[dict[str, Any]] = []
    for name in table_names:
        entry: dict[str, Any] = {"name": name, "columns": [], "rowCount": 0}
        try:
            resp = await _data_client.get(f"{DATA_API_BASE}/api/{name}", params={"limit": 50})
            if resp.status_code != 200:
                resp = await _data_client.get(f"{DATA_API_BASE}/api/data/{name}", params={"limit": 50})
            if resp.status_code == 200:
                result = resp.json()
                rows = result.get("data", result if isinstance(result, list) else [])
                entry["rowCount"] = result.get("total", len(rows))
                if rows:
                    for col_name in rows[0].keys():
                        col_values = [r.get(col_name) for r in rows]
                        entry["columns"].append(_infer_column_meta(col_name, col_values))
        except Exception:
            pass
        tables.append(entry)

    _tables_cache = tables
    return tables


@mcp.tool()
async def list_tables() -> list[str]:
    """List every table name available in this app's database."""
    tables = await _discover_tables()
    return [t["name"] for t in tables]


@mcp.tool()
async def get_api_metadata() -> str:
    """
    Get full schema for every table: real column names, inferred types
    (numeric/categorical/text), valid categorical values, and numeric ranges.
    Call this FIRST before query_table/aggregate_table so you use real
    table/column names instead of guessing.
    """
    tables = await _discover_tables()
    return json.dumps(tables, default=str)


@mcp.tool()
async def query_table(table: str, filter: str = "", sort: str = "", order: str = "asc", limit: int = 100) -> str:
    """
    Fetch rows from a table, with optional filtering/sorting.
    Filter syntax: column:op:value (op is one of eq, ne, gt, lt, gte, lte, like, in);
    separate multiple filters with semicolons, e.g. "status:eq:Active;region:eq:West".
    Call get_api_metadata first if you don't already know this table's real column names.
    """
    params: dict[str, Any] = {"limit": min(limit, 1000)}
    if filter:
        params["filter"] = filter
    if sort:
        params["sort"] = sort
    if order:
        params["order"] = order
    resp = await _data_client.get(f"{DATA_API_BASE}/api/{table}", params=params)
    if resp.status_code != 200:
        resp = await _data_client.get(f"{DATA_API_BASE}/api/data/{table}", params=params)
    if resp.status_code != 200:
        return json.dumps({"error": f"GET /api/{table} returned {resp.status_code}", "detail": resp.text[:300]})
    return json.dumps(resp.json(), default=str)


@mcp.tool()
async def aggregate_table(table: str, metric: str, column: str = "", groupBy: str = "", filter: str = "") -> str:
    """
    Aggregate a table. metric is one of: sum, avg, min, max, count.
    column is required for sum/avg/min/max (the numeric column to aggregate) —
    not needed for count. groupBy optionally groups results by another column.
    filter uses the same column:op:value syntax as query_table.
    """
    params: dict[str, Any] = {"metric": metric}
    if column:
        params["column"] = column
    if groupBy:
        params["groupBy"] = groupBy
    if filter:
        params["filter"] = filter
    resp = await _data_client.get(f"{DATA_API_BASE}/api/{table}/aggregate", params=params)

    if resp.status_code in (400, 404, 500):
        # Old /api/data/{table} URL shape, same (named) param names — the
        # old pure-Python generic-template backend.
        resp = await _data_client.get(f"{DATA_API_BASE}/api/data/{table}/aggregate", params=params)

    if resp.status_code in (400, 404, 500):
        # Spring Boot backend historically used a different aggregate param
        # shape — kept as a fallback since it predates this refactor and the
        # exact Java-side param contract wasn't re-verified here.
        sb_params: dict[str, str] = {"agg": metric}
        if groupBy:
            sb_params["group_by"] = groupBy
        if column:
            sb_params["agg"] = f"{metric}({column})"
        resp = await _data_client.get(f"{DATA_API_BASE}/api/data/{table}/aggregate", params=sb_params)

    if resp.status_code != 200:
        return json.dumps({"error": f"GET /api/{table}/aggregate returned {resp.status_code}", "detail": resp.text[:300]})
    result = resp.json()
    if isinstance(result, list):
        return json.dumps({"data": result}, default=str)
    return json.dumps(result, default=str)


def _load_metadata_file() -> dict | None:
    """None if the metadata file hasn't been written yet — e.g. right after
    a fresh boot, before the platform's own post-boot step has run for the
    first time. Callers treat that as "no custom endpoints known", not an
    error — the generic query_table/aggregate_table tools work regardless."""
    if not _METADATA_FILE.exists():
        return None
    try:
        return json.loads(_METADATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


_ALWAYS_GENERIC_PATHS = {"/api/metadata", "/health"}


def _generic_paths_for_tables(table_names: list[str]) -> set[str]:
    """
    Exact generic per-table paths query_table/aggregate_table already
    cover, computed from the REAL table names in the metadata file — NOT a
    regex pattern matched against path SHAPE. A shape-based pattern like
    `/api/{single-segment}` can't tell a real table route (/api/positions)
    apart from an equally single-segment CUSTOM endpoint (/api/client-
    summary) — reproduced directly: a hyphenated custom path matched the
    exact same "one word-ish segment after /api/" shape a table route
    does, and got silently misclassified as generic, filtering out the one
    endpoint this whole feature exists to surface.
    """
    paths = set()
    for name in table_names:
        for shape in ("/api/{t}", "/api/{t}/{{id}}", "/api/{t}/aggregate",
                       "/api/data/{t}", "/api/data/{t}/{{id}}", "/api/data/{t}/aggregate"):
            paths.add(shape.format(t=name))
    return paths


def _custom_get_endpoints() -> list[dict]:
    """GET endpoints from the metadata file that are neither a generic
    per-table route NOR path-parameterized (call_endpoint below only
    supports query parameters, not substituting {id}-style path segments —
    the join/aggregate endpoints this exists for are naturally query-param
    shaped, same as the generic /aggregate route already is)."""
    metadata = _load_metadata_file()
    if not metadata:
        return []
    table_names = [t.get("name") for t in metadata.get("tables", []) if t.get("name")]
    generic_paths = _ALWAYS_GENERIC_PATHS | _generic_paths_for_tables(table_names)
    return [
        e for e in metadata.get("endpoints", [])
        if e.get("method") == "GET"
        and "{" not in e.get("path", "")
        and e.get("path") not in generic_paths
    ]


@mcp.tool()
async def list_custom_endpoints() -> str:
    """
    List any CUSTOM API endpoints this app has beyond the generic per-table
    routes query_table/aggregate_table already cover — e.g. a hand-built
    endpoint that joins multiple tables or computes a specific cross-table
    metric. Call this when a question needs something a SINGLE table's
    rows can't answer (query_table/aggregate_table only ever look at one
    table at a time). If a relevant endpoint is listed, call it with
    call_endpoint. Returns an empty list if this app has no such endpoints
    — that's normal, not an error; most apps only have the generic routes.
    """
    custom = [
        {"method": e["method"], "path": e["path"], "summary": e.get("summary"),
         "parameters": e.get("parameters", [])}
        for e in _custom_get_endpoints()
    ]
    return json.dumps({"endpoints": custom})


@mcp.tool()
async def call_endpoint(path: str, params: dict[str, Any] | None = None) -> str:
    """
    Call a specific custom endpoint discovered via list_custom_endpoints.
    `path` MUST be exactly one of the paths that tool returned — this does
    NOT accept an arbitrary path you make up, only ones already confirmed
    to exist. GET only, query parameters only (no {id}-style path
    parameters — list_custom_endpoints never returns those).
    """
    known_paths = {e["path"] for e in _custom_get_endpoints()}
    if path not in known_paths:
        return json.dumps({
            "error": f"'{path}' is not a known custom GET endpoint — call list_custom_endpoints first "
                     f"and use one of the paths it returns exactly."
        })
    resp = await _data_client.get(f"{DATA_API_BASE}{path}", params=params or {})
    if resp.status_code != 200:
        return json.dumps({"error": f"GET {path} returned {resp.status_code}", "detail": resp.text[:300]})
    return json.dumps(resp.json(), default=str)


# ASGI sub-app for mounting into the host FastAPI app:
#   from mcp_server import mcp_asgi_app
#   app = FastAPI(lifespan=mcp_asgi_app.lifespan)   # REQUIRED — see module docstring
#   app.mount("/mcp", mcp_asgi_app)
#
# path="/" avoids double-nesting: http_app()'s default internal route is
# already "/mcp", so mounting that under an EXTERNAL "/mcp" prefix without
# this would make the real endpoint "/mcp/mcp", not "/mcp" (confirmed by
# live-testing a real MCP client against both forms before writing this).
mcp_asgi_app = mcp.http_app(path="/", transport="streamable-http")
