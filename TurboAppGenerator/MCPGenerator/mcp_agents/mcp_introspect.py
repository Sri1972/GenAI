"""
Deterministic source introspection — no LLM involved. Both entry points return
plain data the UI renders as checkboxes; the user's own edits (descriptions, which
tables/endpoints to keep) get merged back in before generation, not here.
"""

import sqlite3
from pathlib import Path

import httpx

# Tried in this order against a base URL — covers FastAPI's default, Java's
# springdoc-openapi default, WebAPIGenerator's own Java template (which sets
# springdoc.api-docs.path=/api-docs in application.properties, overriding the
# springdoc default), and the two most common generic Swagger conventions.
_WELL_KNOWN_SPEC_PATHS = ["/openapi.json", "/v3/api-docs", "/api-docs", "/swagger.json", "/swagger/v1/swagger.json"]


def introspect_sqlite(db_path: str) -> list[dict]:
    """
    List every user table in the given SQLite file with its columns and foreign
    keys. Opens read-only (uri mode=ro) — this must never be able to write to or
    lock the user's real database file.
    """
    path = Path(db_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"No file found at {db_path}")

    uri = f"file:{path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        table_names = [row[0] for row in cur.fetchall()]

        tables = []
        for table in table_names:
            cur.execute(f"PRAGMA table_info('{table}')")
            columns = [
                {"name": row[1], "type": row[2] or "TEXT", "primaryKey": bool(row[5]), "notNull": bool(row[3])}
                for row in cur.fetchall()
            ]
            cur.execute(f"PRAGMA foreign_key_list('{table}')")
            foreign_keys = [
                {"column": row[3], "referencesTable": row[2], "referencesColumn": row[4]}
                for row in cur.fetchall()
            ]
            tables.append({"name": table, "columns": columns, "foreignKeys": foreign_keys})
        return tables
    finally:
        conn.close()


def _basic_auth(username: str | None, password: str | None):
    return (username, password) if username else None


def introspect_openapi(base_url: str, username: str | None = None, password: str | None = None) -> dict | None:
    """
    Try well-known OpenAPI spec paths against base_url; parse the first one that
    responds with valid OpenAPI JSON into a flat list of endpoints. Returns None
    (not an error) if nothing is found, so the caller can fall back to asking the
    user for a spec URL/file directly instead of guessing at endpoints.
    """
    base_url = base_url.rstrip("/")
    auth = _basic_auth(username, password)
    for spec_path in _WELL_KNOWN_SPEC_PATHS:
        spec = _try_fetch_spec(base_url + spec_path, auth)
        if spec:
            return _parse_openapi_spec(base_url, spec)
    return None


def introspect_openapi_from_spec(base_url: str, spec: dict) -> dict:
    """Same parsing as introspect_openapi, but for a spec the user pasted/uploaded
    directly (a raw OpenAPI JSON document) when auto-detection found nothing."""
    return _parse_openapi_spec(base_url.rstrip("/"), spec)


def _try_fetch_spec(url: str, auth) -> dict | None:
    try:
        resp = httpx.get(url, auth=auth, timeout=8.0)
        if resp.status_code != 200:
            return None
        spec = resp.json()
        return spec if isinstance(spec, dict) and "paths" in spec else None
    except Exception:
        return None


def _parse_openapi_spec(base_url: str, spec: dict) -> dict:
    endpoints = []
    for path, methods in (spec.get("paths") or {}).items():
        if not isinstance(methods, dict):
            continue
        for method, op in methods.items():
            if method.lower() not in ("get", "post", "put", "patch", "delete") or not isinstance(op, dict):
                continue
            endpoints.append({
                "method": method.upper(),
                "path": path,
                "summary": op.get("summary") or op.get("operationId") or f"{method.upper()} {path}",
                "parameters": [
                    {"name": p.get("name"), "in": p.get("in"), "required": bool(p.get("required")),
                     "type": (p.get("schema") or {}).get("type", "string")}
                    for p in op.get("parameters", []) if isinstance(p, dict)
                ],
                "hasRequestBody": "requestBody" in op,
            })
    return {"baseUrl": base_url, "endpoints": endpoints}
