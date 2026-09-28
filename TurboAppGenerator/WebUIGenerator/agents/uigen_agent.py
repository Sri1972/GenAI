"""
UIGen Agent — core logic for generating, running, stopping and deleting projects.
Used by both the FastAPI server (main.py) and the CLI client.
"""

import json
import os
import re
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

from dotenv import load_dotenv

from .llm import chat, model_id as _llm_model_id
from .prompts import DS_ROOT
from .qa_agent import run_qa

load_dotenv(Path(__file__).parent.parent.parent / ".env")  # TurboUIGen/.env

import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    project_url as _project_url, health_url as _health_url,
    HTML_PORT_START, REACT_PORT_START, API_PORT_START,
    WEB_APPS_DIR, REGISTRY_FILE as _REG_FILE, PORTS_FILE as _PRT_FILE,
    GENERATED_ROOT,
)

NODE_PATH = r"C:\Program Files\nodejs"
DEPLOYMENT = _llm_model_id()  # for compatibility — shows model in health endpoint

# Web apps (React/Vite + HTML) go into generated/web-apps/
GENERATED_DIR  = WEB_APPS_DIR
_PORTS_FILE    = _PRT_FILE
_REGISTRY_FILE = _REG_FILE

# In-memory state (shared within the process)
_dev_servers: dict[str, subprocess.Popen] = {}
_api_servers: dict[str, subprocess.Popen] = {}
_dev_ports:   dict[str, int]              = {}
_api_ports:   dict[str, int]              = {}
_datachat_ports: dict[str, int]           = {}

# Guards every "is this port already taken? if not, compute the next free
# one and reserve it" sequence across _dev_ports/_api_ports/_datachat_ports.
# Reproduced directly: two projects' Start requests close together each
# independently computed "next free port", saw nothing reserved yet (the
# other's real process hadn't bound its port at the OS level either), and
# both ended up assigned the same number — one project's process then
# silently won the real bind and the other was never actually reachable.
# The check-then-reserve sequence itself is fast (dict reads + a handful of
# quick local socket probes + one small JSON write), so serializing it costs
# concurrent requests at most a few milliseconds each — nowhere near the
# real work (LLM calls, npm/Maven builds) that happens entirely outside
# this lock.
_ports_lock = threading.Lock()


# ── Project registry (fast JSON index, no directory scanning) ──────────────────

def _load_registry() -> dict:
    if _REGISTRY_FILE.exists():
        try:
            data = json.loads(_REGISTRY_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def _save_registry(reg: dict):
    _REGISTRY_FILE.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")


def registry_upsert(name: str, **kwargs):
    """Add or update a project entry in the registry."""
    reg = _load_registry()
    entry = reg.get(name, {"name": name})
    entry.update(kwargs)
    reg[name] = entry
    _save_registry(reg)


def registry_set_port(name: str, port: int, proj_type: str = "react"):
    """Persist port assignment so it survives API restarts."""
    registry_upsert(name, port=port, type=proj_type)


def registry_remove(name: str):
    reg = _load_registry()
    reg.pop(name, None)
    _save_registry(reg)


# ── Port persistence ───────────────────────────────────────────────────────────

def _load_ports() -> tuple[dict, dict, dict]:
    """Load ports from disk. Returns (vite_ports, api_ports, datachat_ports).
    Supports both old format { "name": port } and new { "name": { "vite": N, "api": N, "datachat": N } }.
    """
    vite = {}
    api = {}
    datachat = {}
    if _PORTS_FILE.exists():
        try:
            raw = json.loads(_PORTS_FILE.read_text())
            for name, val in raw.items():
                if isinstance(val, dict):
                    if val.get("vite"):
                        vite[name] = val["vite"]
                    if val.get("api"):
                        api[name] = val["api"]
                    if val.get("datachat"):
                        datachat[name] = val["datachat"]
                elif isinstance(val, int):
                    vite[name] = val
        except Exception:
            pass
    return vite, api, datachat


def _save_ports():
    """Save unified ports file with vite, api, and datachat ports per project."""
    data = {}
    all_names = set(_dev_ports.keys()) | set(_api_ports.keys()) | set(_datachat_ports.keys())
    for name in sorted(all_names):
        entry = {}
        if name in _dev_ports:
            entry["vite"] = _dev_ports[name]
        if name in _api_ports:
            entry["api"] = _api_ports[name]
        if name in _datachat_ports:
            entry["datachat"] = _datachat_ports[name]
        data[name] = entry
    _PORTS_FILE.write_text(json.dumps(data, indent=2))


_vite_loaded, _api_loaded, _datachat_loaded = _load_ports()
_dev_ports.update(_vite_loaded)
_api_ports.update(_api_loaded)
_datachat_ports.update(_datachat_loaded)


def _port_is_free(port: int) -> bool:
    """Return True if nothing is bound to this port on localhost right now."""
    import socket as _sock
    with _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM) as s:
        s.setsockopt(_sock.SOL_SOCKET, _sock.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _next_port() -> int:
    """Return the lowest port >= REACT_PORT_START that is both free on the OS
    and not currently assigned to another project."""
    assigned = set(_dev_ports.values())
    port = REACT_PORT_START
    while port in assigned or not _port_is_free(port):
        port += 1
    return port


def _next_api_port() -> int:
    """Return the lowest port >= API_PORT_START that is both free on the OS
    and not currently assigned to another project's API server OR DataChat
    sidecar. Reproduced directly: this used to check only _api_ports, so a
    brand-new project's main API port could land on a number a DIFFERENT
    project's DataChat sidecar had already reserved in _datachat_ports (that
    assignment code itself checks both pools — this one-sided gap was the
    actual mismatch) — neither project's own OS-level _port_is_free() check
    catches it either, since the sidecar hadn't actually bound the port yet
    at the moment this ran, only reserved it in the dict. Whichever process
    then won the real bind left the other crashing on a port already in
    use, surfacing as a completely unrelated-looking API failure."""
    assigned = set(_api_ports.values()) | set(_datachat_ports.values())
    port = API_PORT_START
    while port in assigned or not _port_is_free(port):
        port += 1
    return port


# ── Helpers ────────────────────────────────────────────────────────────────────

def wait_for_port(port: int, timeout: int = 60) -> bool:
    """Wait until Vite is actually serving HTTP (not just TCP-open from a dying process)."""
    import urllib.request as _ur
    import urllib.error as _ue
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            _ur.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
            return True
        except _ue.HTTPError:
            return True   # got an HTTP error — server IS running
        except Exception:
            time.sleep(1)
    return False


def _wait_for_api(port: int, timeout: int = 15) -> bool:
    """Wait until the Python API server responds to /health."""
    import urllib.request as _ur
    import urllib.error as _ue
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            _ur.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
            return True
        except _ue.HTTPError:
            return True
        except Exception:
            time.sleep(0.5)
    print(f"[_wait_for_api] WARNING: API server on port {port} not ready after {timeout}s", flush=True)
    return False


def _live_schema_column_types(live_schema_sql: str) -> dict[str, dict[str, str]]:
    """table -> {column: sql_type}, parsed from _introspect_live_schema's
    output (one `CREATE TABLE IF NOT EXISTS name (col type, ...);` per real
    table, reflected straight from PRAGMA table_info)."""
    tables: dict[str, dict[str, str]] = {}
    for m in re.finditer(
        r'CREATE TABLE(?:\s+IF NOT EXISTS)?\s+"?(\w+)"?\s*\(([^;]*)\)\s*;',
        live_schema_sql, re.IGNORECASE,
    ):
        table, body = m.group(1), m.group(2)
        cols: dict[str, str] = {}
        for col_def in body.split(","):
            col_m = re.match(r'\s*"?(\w+)"?\s+(\w+)', col_def)
            if col_m:
                cols[col_m.group(1)] = col_m.group(2)
        tables[table] = cols
    return tables


def _split_top_level_commas(s: str) -> list[str]:
    """Split a row tuple's inner text on commas, ignoring commas inside a
    quoted string value — same quote-aware shape used for the identical
    problem in WebAPIGenerator's api_orchestrator.py."""
    parts, buf, in_str, i = [], [], False, 0
    while i < len(s):
        ch = s[i]
        if in_str:
            if ch == "'" and s[i:i + 2] == "''":
                buf.append("''")
                i += 2
                continue
            if ch == "'":
                in_str = False
            buf.append(ch)
        else:
            if ch == "'":
                in_str = True
                buf.append(ch)
            elif ch == ",":
                parts.append("".join(buf))
                buf = []
                i += 1
                continue
            else:
                buf.append(ch)
        i += 1
    parts.append("".join(buf))
    return parts


def _seed_sql_has_type_mismatch(seed_sql: str, live_schema_sql: str) -> list[str]:
    """
    Flags a seed INSERT whose literal value can't possibly fit the REAL,
    already-booted database's column type — specifically, a single-quoted
    string literal landing in a column the live schema declares numeric.
    Reproduced directly: seed data written to match schema.sql's (wrong)
    TEXT declaration for a column Hibernate actually built as INTEGER
    (string ids like 'pos-001' inserted into a real `id integer` column)
    failed with "datatype mismatch" and left the table permanently empty —
    checked here, against the REAL schema, right before the actual insert
    is attempted, instead of finding out only after it fails. Intentionally
    narrow (not a full SQL type checker): targets exactly the failure
    signature that has actually occurred, cheaply, from text already in
    hand. Returns one description per distinct table.column problem found.
    """
    from AgentPlatform.core.codegen_batching import sql_type_category
    live_tables = _live_schema_column_types(live_schema_sql)
    seen: set[tuple[str, str]] = set()
    problems: list[str] = []
    for insert_m in re.finditer(r'INSERT INTO\s+"?(\w+)"?\s*\(([^)]+)\)\s*VALUES', seed_sql, re.IGNORECASE):
        table, cols_text = insert_m.group(1), insert_m.group(2)
        live_cols = live_tables.get(table)
        if not live_cols:
            continue
        columns = [c.strip().strip('"').strip('`') for c in cols_text.split(",")]
        numeric_idxs = [
            i for i, c in enumerate(columns)
            if sql_type_category(live_cols.get(c, "")) in ("integer", "real")
        ]
        if not numeric_idxs:
            continue
        stmt_end = seed_sql.find(";", insert_m.end())
        stmt = seed_sql[insert_m.end():stmt_end if stmt_end != -1 else len(seed_sql)]
        for row_m in re.finditer(r'\(([^()]*)\)', stmt):
            values = _split_top_level_commas(row_m.group(1))
            for i in numeric_idxs:
                key = (table, columns[i])
                if key in seen or i >= len(values):
                    continue
                if values[i].strip().startswith("'"):
                    seen.add(key)
                    problems.append(
                        f"{table}.{columns[i]}: seed data inserts a quoted string value, but "
                        f"the REAL live column is {live_cols[columns[i]]}"
                    )
    return problems


def _repair_seed_sql(seed_sql: str, live_schema_sql: str, problem_text: str) -> str | None:
    """
    Ask an LLM to fix seed SQL that doesn't match the REAL, live database
    schema — mirrors _qa_heal/_tsc_heal's shape elsewhere in this file
    (problem description + current content in, corrected content out).
    Returns None on any failure so the caller falls back to its existing
    warning path rather than let a best-effort repair crash the whole
    post-generation flow.
    """
    from agents.llm import chat
    system = (
        "You are fixing SQL INSERT seed data so it matches the REAL, "
        "already-created database schema exactly. Fix ONLY the type "
        "mismatches described — do not rewrite unrelated rows, and do not "
        "add or remove any table. Return ONLY the corrected SQL — no "
        "markdown fences, no explanation."
    )
    prompt = (
        f"The REAL database schema (already created — ground truth):\n{live_schema_sql}\n\n"
        f"Problem(s) found:\n{problem_text}\n\n"
        f"Current seed SQL:\n{seed_sql}\n\n"
        "Return the complete corrected seed SQL — every INSERT statement, not just the fixed ones."
    )
    max_tok = min(64000, max(8000, len(seed_sql) // 3 + 2000))
    try:
        fixed = chat([{"role": "user", "content": prompt}], system=system, max_tokens=max_tok).strip()
    except Exception:
        return None
    fixed = _extract_code_from_llm_response(fixed)
    if not fixed or "INSERT INTO" not in fixed.upper():
        return None
    return fixed


def _ensure_tables_exist_or_restart(project_dir: Path, backend_type: str, api_port: int, _p=None) -> bool:
    """
    Deterministic recovery for "the app booted but its tables were never
    created" — no LLM involved. Reproduced directly: a Python project's
    src/models/__init__.py was missing, so create_all() ran against empty
    metadata and silently produced a live, responding API with zero tables;
    the ONLY way that specific symptom was ever going to get fixed is by
    re-running the app's own table-creation step with the now-correct
    files, not by asking an LLM to interpret a "no such table" traceback
    that never even names the file that's actually missing.

    Deliberately narrow: this does NOT run schema.sql to force-create
    tables — schema.sql is a separate, LLM-written artifact that's already
    been caught drifting from what the ORM models actually declare (see
    _reconcile_schema_types_with_entities); forcing it in here would risk
    creating tables with the wrong columns/types instead of fixing the real
    problem. Restarting the API is the deterministic equivalent of "give
    create_all()/Hibernate ddl-auto another real run" — safe because it's
    idempotent (CREATE TABLE IF NOT EXISTS / ddl-auto=update never
    disturbs a table that already has real rows in it).

    Returns True if the expected tables exist (already, or after the
    restart), False if they're still missing — callers should skip seeding
    and warn loudly rather than let seed_database() fail with "no such
    table" for the second time.
    """
    backend_prefix = "backend" if backend_type == "java" else "api"
    arch_path = project_dir / backend_prefix / ".architecture.json"
    if not arch_path.exists():
        return True  # old pipeline — no per-entity table list to check against
    try:
        arch = json.loads(arch_path.read_text(encoding="utf-8"))
    except Exception:
        return True
    expected_tables = {e.get("table") for e in arch.get("entities", []) if e.get("table")}
    if not expected_tables:
        return True

    def _live_tables() -> set:
        try:
            from api_agents.api_runner import _find_app_db_file
            db_path = _find_app_db_file(project_dir / backend_prefix, backend_type)
        except ImportError:
            return set()
        if not db_path or not db_path.exists():
            return set()
        import sqlite3
        try:
            conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
            try:
                return {r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()}
            finally:
                conn.close()
        except Exception:
            return set()

    if expected_tables & _live_tables():
        return True  # at least some of this app's own tables are real — not the zero-tables case

    if _p:
        _p("skill:None of this app's expected tables exist in the live database — "
           "restarting the API once so its own table-creation step gets a fresh run...")
    project_name = project_dir.name
    old_proc = _api_servers.get(project_name)
    if old_proc:
        try:
            old_proc.terminate()
        except Exception:
            pass
    new_proc = _start_api_server(project_dir, api_port=api_port)
    if new_proc:
        _api_servers[project_name] = new_proc
    if not _wait_for_api(api_port, timeout=180 if backend_type == "java" else 15):
        if _p:
            _p("skill:WARNING — API did not come back up after the restart attempt")
        return False

    if expected_tables & _live_tables():
        if _p:
            _p("skill:Tables exist after the restart")
        return True
    if _p:
        _p("crew:WARNING — expected tables still don't exist after restarting the API once "
           "— this needs a source-code fix, not something a data restart can recover; "
           "the database will start empty")
    return False


def _seed_new_pipeline_backend(project_dir: Path, backend_type: str, api_port: int = 0, _p=None):
    """
    New pipeline (CrewOrchestrator._run_backend_generation): api_services_engineer's
    own generated code deliberately never seeds itself (Spring's data.sql
    auto-run is explicitly disabled via spring.sql.init.mode=never; Python's
    bootstrap likewise never writes its own seeding code) — WebAPIGenerator's
    OWN pipeline never relies on the app's own startup to seed either, for
    the exact reasons seed_database's docstring explains (a JDBC-driver
    timestamp-parsing quirk on read, among others). Its own server.py calls
    seed_database()/apply_pending_migrations() once the app is confirmed up;
    reused verbatim here rather than reimplemented, since this project's
    generated backend is now literally the same output that function was
    built for. Safe to call unconditionally on ANY project (old pipeline or
    new, either language) — its own file-existence checks (seed_data.sql /
    src/main/resources/data.sql, neither of which the OLD pipeline's
    templates ever write) make it a no-op there.

    Unlike the compile-check and boot-check loops elsewhere in this
    pipeline, a seed failure used to just log one line and leave every
    table permanently empty, with no retry — the one failure class in this
    whole pipeline that wasn't self-healing. Now: validated against the
    REAL, already-booted schema (via _introspect_live_schema, the same
    function refine() uses to see the real schema instead of trusting a
    possibly-stale schema.sql) BEFORE the first real attempt, and given one
    real LLM-repair retry if it still fails — same shape as _qa_heal/
    _tsc_heal's repair loops above, just for this one remaining gap.
    """
    backend_dir = project_dir / ("backend" if backend_type == "java" else "api")
    if not backend_dir.exists():
        return
    try:
        from api_agents.api_runner import seed_database, apply_pending_migrations, java_backend_db_path
    except ImportError:
        return
    project_name = project_dir.name
    seed_path = backend_dir / ("src/main/resources/data.sql" if backend_type == "java" else "seed_data.sql")
    # Only THIS launcher can guarantee this path is correct (it unconditionally
    # sets the DB_PATH env var Spring resolves to exactly this — see
    # java_backend_db_path's docstring), so only here is it safe to hand
    # straight to seed_database instead of letting it re-detect from scratch.
    # WebAPIGenerator's OWN standalone launcher does no such override, so its
    # own call site (API/server.py) correctly omits this and keeps relying on
    # seed_database's regex/glob detection, unchanged.
    known_db_path = java_backend_db_path(backend_dir) if backend_type == "java" else None

    if api_port and not _ensure_tables_exist_or_restart(project_dir, backend_type, api_port, _p):
        return  # tables genuinely don't exist and a restart didn't fix it — nothing to seed

    def _try_repair(problem_text: str) -> bool:
        if not seed_path.exists():
            return False
        live_schema = _introspect_live_schema(project_dir)
        if not live_schema:
            return False
        fixed = _repair_seed_sql(seed_path.read_text(encoding="utf-8"), live_schema, problem_text)
        if not fixed:
            return False
        seed_path.write_text(fixed, encoding="utf-8")
        return True

    def _clear_seeded_tables():
        """
        seed_database() runs the whole seed file as one conn.executescript()
        — which commits each statement as it executes, not atomically as a
        whole — so a failure partway through (a bad row further down in the
        file) still leaves every EARLIER statement's rows committed to disk.
        Reproduced directly: a malformed string literal broke the `trades`
        INSERT, but `positions`' own INSERT (earlier in the same file) had
        already committed; retrying the (now-fixed) seed file from the top
        re-ran that same positions INSERT against rows that already existed,
        failing with a totally different, more confusing error (UNIQUE
        constraint) that looks unrelated to the original problem. A retry
        must start from an empty slate, not layer on top of whatever a
        partial first attempt left behind.
        """
        try:
            from api_agents.api_runner import _find_app_db_file
            db_file = _find_app_db_file(backend_dir, backend_type, known_db_path=known_db_path)
        except ImportError:
            return
        if not db_file or not db_file.exists():
            return
        import sqlite3
        try:
            conn = sqlite3.connect(str(db_file))
            try:
                tables = [r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()]
                for table in tables:
                    conn.execute(f'DELETE FROM "{table}"')
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass

    # Pre-check against the REAL schema before the first real attempt —
    # this is exactly where the schema.sql-vs-entity divergence this whole
    # feature exists to close would otherwise silently reach a real INSERT
    # and fail. Cheap: reuses the seed file + live schema already in hand.
    live_schema_sql = _introspect_live_schema(project_dir)
    if live_schema_sql and seed_path.exists():
        mismatches = _seed_sql_has_type_mismatch(seed_path.read_text(encoding="utf-8"), live_schema_sql)
        if mismatches:
            if _p:
                _p(f"skill:Seed data doesn't match the real database schema "
                   f"({len(mismatches)} column(s)) — attempting an automatic fix before seeding...")
            _try_repair("\n".join(f"- {m}" for m in mismatches))

    seed_result = seed_database(project_name, backend_dir, backend_type, known_db_path=known_db_path)
    print(f"[seed] {seed_result}", flush=True)
    if _p:
        _p(f"skill:Seeding — {seed_result}")

    attempts = 1
    while seed_result.startswith("failed") and attempts < 2:
        if _p:
            _p(f"skill:Seeding failed ({seed_result}) — attempting an automatic repair...")
        if not _try_repair(seed_result):
            if _p:
                _p("skill:Automatic seed repair produced no usable fix — giving up")
            break
        _clear_seeded_tables()
        seed_result = seed_database(project_name, backend_dir, backend_type, force=True, known_db_path=known_db_path)
        print(f"[seed] {seed_result}", flush=True)
        if _p:
            _p(f"skill:Seeding retry — {seed_result}")
        attempts += 1

    if seed_result.startswith("failed"):
        if _p:
            _p(f"crew:WARNING — seeding failed and could not be automatically repaired "
               f"({seed_result}); the database will start empty.")

    migration_result = apply_pending_migrations(project_name, backend_dir, backend_type)
    if not migration_result.startswith("skipped"):
        print(f"[seed] {migration_result}", flush=True)
        if _p:
            _p(f"skill:Migrations — {migration_result}")


def _build_mcp_metadata_file(project_dir: Path, backend_type: str, _p=None):
    """
    Persists a metadata file the DataChat sidecar's MCP tools read from,
    instead of re-discovering the schema/routes live on every single tool
    call. Reuses MCPGenerator's own introspection logic verbatim
    (mcp_agents.mcp_introspect — the exact functions its "connect a
    database/API" UI flow calls) rather than a second, WebUIGenerator-
    specific implementation of the same thing.

    Runs post-boot (same timing as seeding — needs the real .db file and a
    live API to introspect, neither of which exist at pure generation
    time). Includes the FULL endpoint list from the real running API's
    OpenAPI spec, not just the generic per-table routes query_table/
    aggregate_table already know how to call — this is what lets a custom,
    hand-specified join/aggregate endpoint (if the app's own requirements
    asked for one) become usable from chat automatically, once
    mcp_server_template.py's list_custom_endpoints/call_endpoint tools are
    pointed at it, without writing per-endpoint tool code for it.

    Safe to call unconditionally, same as _seed_new_pipeline_backend —
    every check below is a plain existence check with an early return, and
    re-running it (e.g. on every restart) just refreshes the file, which is
    the right behavior if a refine ever added a new endpoint.
    """
    is_java_backend = backend_type == "java"
    candidate_subdirs = ("datachat", "api") if is_java_backend else ("datachat",)
    datachat_dir = None
    for subdir in candidate_subdirs:
        candidate = project_dir / subdir
        if (candidate / "app_server.py").exists():
            datachat_dir = candidate
            break
    if datachat_dir is None:
        return  # no DataChat/MCP sidecar in this project at all

    # The LLM names this file per-app (supply_chain.db, wealth-advisor.db,
    # ...) — there's no fixed convention to guess, so this must read the
    # app's OWN configured path the same way api_runner's seeding/boot-check
    # already does, not assume a literal "data.db". Reproduced directly: a
    # real generation's application.properties pointed at supply_chain.db,
    # so the old fixed-name-guess here always missed it and silently
    # skipped mcp_metadata.json for every Java project that didn't happen to
    # name its file "data.db".
    from api_agents.api_runner import _find_app_db_file
    backend_prefix = "backend" if is_java_backend else "api"
    db_path = _find_app_db_file(project_dir / backend_prefix, backend_type)
    if db_path is None:
        return  # app hasn't actually booted yet (no live .db file)

    api_port = _api_ports.get(project_dir.name)
    if not api_port:
        return

    try:
        from mcp_agents.mcp_introspect import introspect_sqlite, introspect_openapi
    except ImportError:
        return  # MCPGenerator not on sys.path in this process — skip, not fatal

    try:
        tables = introspect_sqlite(str(db_path))
    except Exception as e:
        if _p:
            _p(f"skill:MCP metadata: could not introspect the database ({e}) — skipping")
        return

    try:
        api_meta = introspect_openapi(f"http://localhost:{api_port}")
    except Exception:
        api_meta = None
    endpoints = api_meta["endpoints"] if api_meta else []

    metadata_path = datachat_dir / "mcp_metadata.json"
    try:
        metadata_path.write_text(
            json.dumps({"tables": tables, "endpoints": endpoints}, indent=2, default=str),
            encoding="utf-8",
        )
        if _p:
            _p(f"skill:MCP metadata refreshed — {len(tables)} table(s), {len(endpoints)} endpoint(s)")
    except Exception as e:
        if _p:
            _p(f"skill:MCP metadata: could not write metadata file ({e})")


_NPM_STRIP_FROM_PKG = {"mobility-global-ds", "@mobility-global/ds"}


def _npm_install(project_dir: Path) -> tuple[bool, str]:
    # Strip packages that are resolved via vite alias (not on npm)
    pj = project_dir / "package.json"
    if pj.exists():
        import re as _re
        txt = pj.read_text(encoding="utf-8")
        for pkg in _NPM_STRIP_FROM_PKG:
            txt = _re.sub(r',?\s*"' + _re.escape(pkg) + r'"\s*:\s*"[^"]*"', '', txt)
        pj.write_text(txt, encoding="utf-8")

    env = os.environ.copy()
    env["PATH"] = NODE_PATH + ";" + env.get("PATH", "")
    node_exe = Path(NODE_PATH) / "node.exe"
    npm_js   = Path(NODE_PATH) / "node_modules" / "npm" / "bin" / "npm-cli.js"
    result = subprocess.run(
        [str(node_exe), str(npm_js), "install"],
        cwd=str(project_dir),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    return result.returncode == 0, result.stdout + result.stderr


# ── Shared node_modules ────────────────────────────────────────────────────────
# All generated React apps share the same base packages. We install them once
# into SHARED_NM_DIR and junction each project's node_modules there, skipping
# the ~60s per-project npm install entirely.

_LEGACY_SHARED_NM_DIR = GENERATED_DIR.parent / "shared-node-modules"


def _needs_clean_paths() -> bool:
    """Return True if any project path contains characters that break Vite @fs/ URLs.
    On a clean Linux/AWS deployment the paths have no & or spaces, so junctions are
    unnecessary.  On Windows with OneDrive paths like 'S&P Global' they are required.
    """
    bad_chars = set("&")
    probe_paths = [str(_LEGACY_SHARED_NM_DIR), str(DS_ROOT)]
    return any(c in p for p in probe_paths for c in bad_chars)


def _clean_junction_base() -> Path:
    """Return the base directory for clean-path junctions.
    Respects TURBOUI_JUNCTION_DIR env var so it can be overridden in any environment.
    Falls back to <home>/.turboui-junctions which is writable without admin rights.
    """
    override = os.environ.get("TURBOUI_JUNCTION_DIR", "").strip()
    if override:
        return Path(override)
    return Path.home() / ".turboui-junctions"


_NEEDS_JUNCTIONS = _needs_clean_paths()
_JUNCTION_BASE   = _clean_junction_base() if _NEEDS_JUNCTIONS else None

# When paths contain & (OneDrive 'S&P Global'), store shared-node-modules at a clean path.
# Vite calls fs.realpathSync() to generate @fs/ URLs, which follows all junction chains to
# the final real directory. If that directory is at a clean path, @fs/ URLs contain no &.
SHARED_NM_DIR = (_JUNCTION_BASE / "shared-nm") if _NEEDS_JUNCTIONS else _LEGACY_SHARED_NM_DIR

# Forward-slash paths for use inside vite.config.ts — Vite requires forward slashes.
# SHARED_NM_DIR is already at a clean path, so _SHARED_NM_JUNCTION needs no extra junction.
_DS_CLEAN_JUNCTION  = (_JUNCTION_BASE / "mgds").as_posix() if _NEEDS_JUNCTIONS else Path(DS_ROOT).as_posix()
_SHARED_NM_JUNCTION = (SHARED_NM_DIR / "node_modules").as_posix()

# Canonical set of packages all generated apps use
_SHARED_PACKAGE_JSON = {
    "name": "turboui-shared-deps",
    "version": "1.0.0",
    "private": True,
    "dependencies": {
        "react": "^18.2.0",
        "react-dom": "^18.2.0",
        "react-router-dom": "^6.22.3",
        "recharts": "^2.12.2",
        "lucide-react": "^0.378.0",
        "d3": "^7.9.0",
        "d3-sankey": "^0.12.3",
        "topojson-client": "^3.1.0",
        "us-atlas": "^3.0.1",
        "world-atlas": "^2.0.2",
        "leaflet": "^1.9.4",
        "react-leaflet": "^4.2.1",
    },
    "devDependencies": {
        "typescript": "^5.4.5",
        "@types/react": "^18.2.79",
        "@types/react-dom": "^18.2.25",
        "@types/d3": "^7.4.3",
        "@types/d3-sankey": "^0.12.5",
        "@types/topojson-client": "^3.1.5",
        "@types/leaflet": "^1.9.14",
        "vite": "^5.2.8",
        "@vitejs/plugin-react": "^4.2.1",
        "tailwindcss": "^3.4.3",
        "postcss": "^8.4.38",
        "autoprefixer": "^10.4.19",
    },
}

# Packages the LLM commonly adds — pre-installed so they're always available
_EXTRA_PACKAGES = [
    "date-fns", "axios", "clsx", "classnames",
    "react-hook-form", "zod", "framer-motion",
    "@tanstack/react-table", "react-select",
    # Skill dependencies — always available so skill templates just work
    "pptxgenjs",        # PptxExport.skill.tsx
    "xlsx",             # ExcelExport.skill.tsx (SheetJS)
    "jspdf",            # PdfExport.skill.tsx
    "jspdf-autotable",  # PdfExport.skill.tsx — table rendering plugin
]


def _ensure_shared_nm() -> tuple[bool, str]:
    """Create and populate the shared node_modules folder if it doesn't exist."""
    SHARED_NM_DIR.mkdir(parents=True, exist_ok=True)
    nm = SHARED_NM_DIR / "node_modules"
    pj = SHARED_NM_DIR / "package.json"

    # Write package.json only if it doesn't exist or is outdated
    import json as _json
    current_pj = _json.dumps(_SHARED_PACKAGE_JSON, indent=2, sort_keys=True)
    if not pj.exists() or pj.read_text(encoding="utf-8").strip() != current_pj.strip():
        pj.write_text(current_pj, encoding="utf-8")

    env = os.environ.copy()
    env["PATH"] = NODE_PATH + ";" + env.get("PATH", "")
    node_exe = Path(NODE_PATH) / "node.exe"
    npm_js   = Path(NODE_PATH) / "node_modules" / "npm" / "bin" / "npm-cli.js"

    # Run npm install only if base packages are missing
    if not nm.exists() or not (nm / "vite").exists() or not (nm / "react").exists():
        r = subprocess.run(
            [str(node_exe), str(npm_js), "install"],
            cwd=str(SHARED_NM_DIR), env=env, capture_output=True, text=True, timeout=300,
        )
        if r.returncode != 0:
            return False, r.stdout + r.stderr

    # Install any extra packages not yet present (picked up whenever list changes)
    def _pkg_dir(p: str) -> Path:
        # scoped packages like @tanstack/react-table live under node_modules/@tanstack/react-table
        parts = p.split("/")
        return nm.joinpath(*parts) if p.startswith("@") else nm / p
    extra = [p for p in _EXTRA_PACKAGES if not _pkg_dir(p).exists()]
    if extra:
        subprocess.run(
            [str(node_exe), str(npm_js), "install", "--save-optional"] + extra,
            cwd=str(SHARED_NM_DIR), env=env, capture_output=True, text=True, timeout=120,
        )

    return True, "shared node_modules ready"


def _link_shared_nm(
    project_dir: Path,
    project_deps: dict,
    progress=None,
) -> tuple[bool, str]:
    """
    Link project_dir/node_modules to the shared node_modules store.
    On Windows paths containing & (e.g. OneDrive S&P Global), uses a clean-path
    junction so Vite never generates @fs/ URLs with & in them.
    On Linux/AWS with clean paths, uses a plain symlink directly to the real dir.
    Any packages the project needs that aren't in the shared store are installed
    there first — making them available to all future projects too.
    """
    nm_target = SHARED_NM_DIR / "node_modules"   # real path — where npm installs
    nm_link   = project_dir / "node_modules"

    # Install any missing packages into the shared store FIRST (before touching the link)
    # Packages that don't exist on npm — the LLM hallucinates these
    _BLOCKED_PACKAGES = {
        "@types/us-atlas", "@types/world-atlas", "@types/topojson",
        "@types/topojson-specification", "@types/geojson-vt",
        "mobility-global-ds", "@mobility-global/ds",
    }

    def _nm_exists(pkg: str) -> bool:
        parts = pkg.split("/")
        return nm_target.joinpath(*parts).exists() if pkg.startswith("@") else (nm_target / pkg).exists()
    missing = [p for p in project_deps if not _nm_exists(p) and p not in _BLOCKED_PACKAGES]

    if missing:
        if progress:
            progress(f"Installing new packages into shared store: {', '.join(missing)}")
        env = os.environ.copy()
        env["PATH"] = NODE_PATH + os.pathsep + env.get("PATH", "")
        node_exe = Path(NODE_PATH) / "node.exe"
        npm_js   = Path(NODE_PATH) / "node_modules" / "npm" / "bin" / "npm-cli.js"
        r = subprocess.run(
            [str(node_exe), str(npm_js), "install"] + missing,
            cwd=str(SHARED_NM_DIR), env=env, capture_output=True, text=True, timeout=120,
        )
        if r.returncode != 0:
            return False, f"Failed to install {missing}:\n{r.stdout + r.stderr}"
        if progress:
            progress(f"Added to shared store (available to all projects): {', '.join(missing)}")

    # If the link already points at the right target, nothing to do
    if _is_junction(nm_link) or nm_link.is_symlink():
        try:
            resolved = Path(os.readlink(str(nm_link)) if nm_link.is_symlink()
                            else str(nm_link))
            if resolved.resolve() == nm_target.resolve():
                return True, "junction already correct"
        except Exception:
            pass
        nm_link.unlink(missing_ok=True)
    elif nm_link.exists():
        # Real directory (e.g. legacy per-project install) — remove it.
        # Use cmd /c rmdir on Windows: handles locked files better than shutil.rmtree.
        if os.name == "nt":
            subprocess.run(
                ["cmd", "/c", "rmdir", "/s", "/q", str(nm_link)],
                capture_output=True, timeout=60,
            )
        else:
            shutil.rmtree(str(nm_link), ignore_errors=True)
        if nm_link.exists():
            return False, f"Could not remove existing node_modules at {nm_link}"

    # Create the junction / symlink to shared-nm
    if os.name == "nt":
        r = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(nm_link), str(nm_target)],
            capture_output=True, text=True,
        )
        return r.returncode == 0, r.stdout + r.stderr
    else:
        nm_link.symlink_to(nm_target)
        return True, "symlinked to shared node_modules"


def _is_junction(path: Path) -> bool:
    """Check if a path is a Windows directory junction."""
    try:
        return path.stat().st_reparse_tag == 0xA0000003  # IO_REPARSE_TAG_MOUNT_POINT
    except Exception:
        import os as _os
        try:
            return bool(_os.stat(str(path)).st_file_attributes & 0x400)
        except Exception:
            return False


def _get_project_deps(project_dir: Path) -> dict:
    """Read dependency names from the project's package.json."""
    import json as _json
    pj = project_dir / "package.json"
    if not pj.exists():
        return {}
    try:
        d = _json.loads(pj.read_text(encoding="utf-8"))
        return {**d.get("dependencies", {}), **d.get("devDependencies", {})}
    except Exception:
        return {}


def _scan_imports_from_files(project_dir: Path) -> set[str]:
    """
    Scan all .ts/.tsx source files for actual import statements (static and dynamic)
    and return the set of third-party package names referenced.

    This catches packages the LLM uses in code but forgot to add to package.json —
    a common failure mode that causes runtime 'module not found' errors.
    """
    # Matches: import X from 'pkg', import { X } from 'pkg', import 'pkg'
    _static_import = re.compile(r"""(?:import|export)\s+.*?from\s+['"]([^./][^'"]*?)['"]""")
    # Matches: await import('pkg'), import('pkg')
    _dynamic_import = re.compile(r"""import\s*\(\s*['"]([^./][^'"]*?)['"]""")
    # Matches: require('pkg')
    _require = re.compile(r"""require\s*\(\s*['"]([^./][^'"]*?)['"]""")

    packages: set[str] = set()

    # Built-in/virtual modules to skip
    _BUILTINS = {"react", "react-dom", "react-dom/client", "react-router-dom",
                 "vite", "@vitejs/plugin-react", "typescript",
                 "mobility-global-ds", "tailwindcss", "postcss", "autoprefixer"}

    for fpath in project_dir.rglob("*"):
        if fpath.suffix not in (".ts", ".tsx", ".js", ".jsx"):
            continue
        if "node_modules" in fpath.parts:
            continue
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for pat in (_static_import, _dynamic_import, _require):
            for m in pat.finditer(content):
                raw = m.group(1)
                # Extract package name: 'd3-sankey' from 'd3-sankey/src/foo'
                # Scoped: '@tanstack/react-table' from '@tanstack/react-table/core'
                if raw.startswith("@"):
                    parts = raw.split("/")
                    pkg = "/".join(parts[:2]) if len(parts) >= 2 else raw
                else:
                    pkg = raw.split("/")[0]
                packages.add(pkg)

    # Remove builtins and packages already known to be handled by aliases
    packages -= _BUILTINS
    return packages


# Ensure shared deps are installed at import time (runs once in background on first use)
_shared_nm_ready: bool = False


def _ensure_shared_nm_once() -> tuple[bool, str]:
    global _shared_nm_ready
    if _shared_nm_ready:
        # Even if ready, verify extra packages exist (catches partial installs)
        nm = SHARED_NM_DIR / "node_modules"
        def _pkg_dir(p: str) -> Path:
            parts = p.split("/")
            return nm.joinpath(*parts) if p.startswith("@") else nm / p
        missing = [p for p in _EXTRA_PACKAGES if not _pkg_dir(p).exists()]
        if missing:
            print(f"[_ensure_shared_nm_once] Missing packages detected: {missing}", flush=True)
            _shared_nm_ready = False
        else:
            return True, "ready"
    ok, log = _ensure_shared_nm()
    if ok:
        _shared_nm_ready = True
    return ok, log


def _start_vite(project_dir: Path, port: int) -> subprocess.Popen:
    # Clear Vite's dep cache so pre-bundling runs fresh every time.
    # Stale .vite/deps causes "Failed to fetch dynamically imported module" errors.
    import shutil
    _vite_cache = project_dir / "node_modules" / ".vite"
    if _vite_cache.exists():
        shutil.rmtree(_vite_cache, ignore_errors=True)

    node_exe = Path(NODE_PATH) / "node.exe"
    vite_js = Path(_SHARED_NM_JUNCTION) / "vite" / "bin" / "vite.js"
    if not vite_js.exists():
        vite_js = project_dir / "node_modules" / "vite" / "bin" / "vite.js"
    env = os.environ.copy()
    env["PATH"] = NODE_PATH + os.pathsep + env.get("PATH", "")
    # --preserve-symlinks stops Node from calling realpathSync on module paths,
    # so @fs/ URLs stay at the clean junction path instead of resolving to OneDrive.
    if _NEEDS_JUNCTIONS:
        existing = env.get("NODE_OPTIONS", "")
        if "--preserve-symlinks" not in existing:
            env["NODE_OPTIONS"] = (existing + " --preserve-symlinks").strip()
    # Redirect output to a log file so the pipe buffer never fills and blocks the process.
    log_file = open(str(project_dir / "vite.log"), "w", encoding="utf-8", errors="replace")
    kwargs: dict = {"cwd": str(project_dir), "env": env, "stdout": log_file, "stderr": log_file}
    if os.name == "nt":
        # DETACHED_PROCESS makes the server survive TurboUIGen restarts
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    return subprocess.Popen([str(node_exe), str(vite_js), "--port", str(port), "--host", "0.0.0.0"], **kwargs)


def _start_datachat_server(project_dir: Path, datachat_port: int, data_api_port: int = 0,
                            subdir: str = "api") -> subprocess.Popen | None:
    """Start the DataChat Python API server on its own port (alongside a Java
    backend, at api/app_server.py — the default; or alongside the new named-
    route pipeline, whose real API already owns api/, at datachat/app_server.py)."""
    server_file = project_dir / subdir / "app_server.py"
    if not server_file.exists():
        return None
    cwd = str(server_file.parent)
    env = os.environ.copy()
    env["API_PORT"] = str(datachat_port)
    if data_api_port:
        env["DATA_API_BASE"] = f"http://localhost:{data_api_port}"
    log_file = open(str(project_dir / "datachat_server.log"), "w", encoding="utf-8", errors="replace")
    kwargs: dict = {"cwd": cwd, "env": env, "stdout": log_file, "stderr": log_file}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    proc = subprocess.Popen(["python", str(server_file)], **kwargs)
    print(f"[datachat_server] Started DataChat API on port {datachat_port} (PID {proc.pid})", flush=True)
    return proc


def _start_api_server(project_dir: Path, api_port: int = 8080) -> subprocess.Popen | None:
    """Start the API server for generated apps (Python or Java Spring Boot)."""
    # Check if this is a Java Spring Boot project
    backend_type_file = project_dir / "backend" / ".backend_type"
    if backend_type_file.exists():
        backend_type = backend_type_file.read_text(encoding="utf-8").strip()
        if backend_type == "java-springboot":
            # Also start DataChat Python server if it exists alongside Java backend
            datachat_server = project_dir / "api" / "app_server.py"
            if datachat_server.exists():
                project_name = project_dir.name
                # Reuse the port already baked into this project's vite.config.ts / .env at
                # generation time (see the datachat_port allocation in uigen_agent's file-gen
                # path) — recomputing here would see that reservation as "taken by itself" and
                # drift to a different port than what the frontend proxy is configured for.
                with _ports_lock:
                    dc_port = _datachat_ports.get(project_name)
                    if not dc_port or not _port_is_free(dc_port):
                        assigned = set(_api_ports.values()) | set(_datachat_ports.values()) | {api_port}
                        dc_port = api_port + 1
                        while dc_port in assigned or not _port_is_free(dc_port):
                            dc_port += 1
                    _datachat_ports[project_name] = dc_port
                    _save_ports()
                # Patch the api/.env to use the datachat port
                env_file = project_dir / "api" / ".env"
                if env_file.exists():
                    import re as _re_dc
                    env_text = env_file.read_text(encoding="utf-8")
                    patched = _re_dc.sub(r"API_PORT=\d+", f"API_PORT={dc_port}", env_text)
                    if patched != env_text:
                        env_file.write_text(patched, encoding="utf-8")
                dc_proc = _start_datachat_server(project_dir, dc_port, data_api_port=api_port)
                if dc_proc:
                    _api_servers[f"{project_name}:datachat"] = dc_proc
            return _start_java_api_server(project_dir, api_port)

    # New pipeline, Java backend (real per-entity JPA + named routes,
    # generated via ApiCrewOrchestrator — see
    # CrewOrchestrator._run_backend_generation with backend_type="java").
    # No .backend_type marker (that's an old-pipeline-only sentinel written
    # by _bundle_java_api_server) — backend/pom.xml existing at all is the
    # real signal. _start_java_api_server itself is already fully generic
    # (just runs `mvn spring-boot:run` against whatever's under backend/),
    # so it works unchanged for this layout too.
    if (project_dir / "backend" / "pom.xml").exists():
        datachat_server = project_dir / "datachat" / "app_server.py"
        if datachat_server.exists():
            project_name = project_dir.name
            with _ports_lock:
                dc_port = _datachat_ports.get(project_name)
                if not dc_port or not _port_is_free(dc_port):
                    assigned = set(_api_ports.values()) | set(_datachat_ports.values()) | {api_port}
                    dc_port = api_port + 1
                    while dc_port in assigned or not _port_is_free(dc_port):
                        dc_port += 1
                _datachat_ports[project_name] = dc_port
                _save_ports()
            env_file = project_dir / "datachat" / ".env"
            if env_file.exists():
                import re as _re_dc
                env_text = env_file.read_text(encoding="utf-8")
                patched = _re_dc.sub(r"API_PORT=\d+", f"API_PORT={dc_port}", env_text)
                if patched != env_text:
                    env_file.write_text(patched, encoding="utf-8")
            dc_proc = _start_datachat_server(project_dir, dc_port, data_api_port=api_port, subdir="datachat")
            if dc_proc:
                _api_servers[f"{project_name}:datachat"] = dc_proc
        return _start_java_api_server(project_dir, api_port)

    api_dir = project_dir / "api"

    # New pipeline (real per-entity ORM + named routes, generated via
    # ApiCrewOrchestrator — see CrewOrchestrator._run_backend_generation):
    # the entry point is a real package at api/src/main.py, not a
    # standalone script, and MUST be started as a module
    # (`uvicorn src.main:app`) the same way WebAPIGenerator's own
    # api_runner.py starts its projects — `python src/main.py` directly
    # would not even define a running server, let alone resolve its own
    # `from src....` imports correctly.
    if (api_dir / "src" / "main.py").exists():
        marker = api_dir / ".deps_installed"
        if not marker.exists():
            req = api_dir / "requirements.txt"
            if req.exists():
                install = subprocess.run(
                    [_sys.executable, "-m", "pip", "install", "-q", "-r", str(req)],
                    cwd=str(api_dir), timeout=300, capture_output=True, text=True,
                )
                if install.returncode == 0:
                    marker.write_text("ok", encoding="utf-8")
                else:
                    print(f"[api_server] pip install failed (exit {install.returncode}): "
                          f"{install.stderr[-2000:]}", flush=True)
            else:
                marker.write_text("ok", encoding="utf-8")

        env = os.environ.copy()
        env["API_PORT"] = str(api_port)
        env["PORT"] = str(api_port)
        cmd = [_sys.executable, "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", str(api_port)]
        log_file = open(str(project_dir / "api_server.log"), "w", encoding="utf-8", errors="replace")
        kwargs: dict = {"cwd": str(api_dir), "env": env, "stdout": log_file, "stderr": log_file}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        proc = subprocess.Popen(cmd, **kwargs)
        print(f"[api_server] Started Python API server (named-route pipeline) on port {api_port} "
              f"(PID {proc.pid}, cwd={api_dir})", flush=True)

        # AI-chat apps under this pipeline get their chat/MCP support from
        # the same DataChat sidecar the Java path already uses (see
        # CrewOrchestrator._run_backend_generation) — bundled under
        # datachat/ since api/ is already the real named-route API here.
        datachat_server = project_dir / "datachat" / "app_server.py"
        if datachat_server.exists():
            project_name = project_dir.name
            with _ports_lock:
                dc_port = _datachat_ports.get(project_name)
                if not dc_port or not _port_is_free(dc_port):
                    assigned = set(_api_ports.values()) | set(_datachat_ports.values()) | {api_port}
                    dc_port = api_port + 1
                    while dc_port in assigned or not _port_is_free(dc_port):
                        dc_port += 1
                _datachat_ports[project_name] = dc_port
                _save_ports()
            env_file = project_dir / "datachat" / ".env"
            if env_file.exists():
                import re as _re_dc
                env_text = env_file.read_text(encoding="utf-8")
                patched = _re_dc.sub(r"API_PORT=\d+", f"API_PORT={dc_port}", env_text)
                if patched != env_text:
                    env_file.write_text(patched, encoding="utf-8")
            dc_proc = _start_datachat_server(project_dir, dc_port, data_api_port=api_port, subdir="datachat")
            if dc_proc:
                _api_servers[f"{project_name}:datachat"] = dc_proc

        return proc

    server_file = api_dir / "app_server.py"

    # Legacy fallback: check root-level files from older generations
    if not server_file.exists():
        server_file = project_dir / "app_server.py"
    if not server_file.exists():
        server_file = project_dir / "api_server.py"
    if not server_file.exists():
        # Auto-bundle if schema.sql exists but server was never bundled
        schema_found = (api_dir / "schema.sql").exists() or (project_dir / "schema.sql").exists()
        if schema_found:
            tmpl = _SKILLS_DIR / "app_server_template.py"
            if tmpl.exists():
                api_dir.mkdir(exist_ok=True)
                server_file = api_dir / "app_server.py"
                server_file.write_text(tmpl.read_text(encoding="utf-8"), encoding="utf-8")
                # Move schema/seed into api/ if they're at root level
                for f in ("schema.sql", "seed.sql"):
                    root_f = project_dir / f
                    if root_f.exists() and not (api_dir / f).exists():
                        root_f.rename(api_dir / f)
                print(f"[api_server] Auto-bundled api/app_server.py (schema.sql present)", flush=True)
            else:
                return None
        else:
            return None

    # Use the server file's parent as cwd so relative paths (schema.sql, .env) resolve
    cwd = str(server_file.parent)
    env = os.environ.copy()
    env["API_PORT"] = str(api_port)
    log_file = open(str(project_dir / "api_server.log"), "w", encoding="utf-8", errors="replace")
    kwargs: dict = {"cwd": cwd, "env": env, "stdout": log_file, "stderr": log_file}
    if os.name == "nt":
        # DETACHED_PROCESS makes the server survive TurboUIGen restarts
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    proc = subprocess.Popen(["python", str(server_file)], **kwargs)
    print(f"[api_server] Started Python API server on port {api_port} (PID {proc.pid}, cwd={cwd})", flush=True)
    return proc


def resolve_java_maven_env(env: dict, backend_dir: Path) -> str:
    """
    Mutate `env` in place to set JAVA_HOME (detecting it if missing) and prepend
    Java/Maven to PATH, then return the resolved `mvn` command to invoke.

    Shared by _start_java_api_server (web-app companion backends) and
    WebAPIGenerator's api_runner (standalone Java APIs) — both need identical
    JAVA_HOME/MAVEN_HOME resolution, so this lives here once rather than duplicated.
    """
    # Ensure JAVA_HOME is set — detect if missing
    if not env.get("JAVA_HOME"):
        for candidate in [r"C:\Program Files\Java\jdk-21", r"C:\Program Files\Java\jdk-17"]:
            if Path(candidate).exists():
                env["JAVA_HOME"] = candidate
                break

    # Add Java and Maven to PATH
    java_home = env.get("JAVA_HOME", "")
    maven_home = env.get("MAVEN_HOME", "")
    extra_path = ""
    if java_home:
        extra_path += str(Path(java_home) / "bin") + os.pathsep
    if maven_home:
        extra_path += str(Path(maven_home) / "bin") + os.pathsep
    if extra_path:
        env["PATH"] = extra_path + env.get("PATH", "")

    # Prefer system mvn over mvnw (avoids download issues)
    mvn_cmd = None
    if maven_home:
        system_mvn = Path(maven_home) / "bin" / ("mvn.cmd" if os.name == "nt" else "mvn")
        if system_mvn.exists():
            mvn_cmd = str(system_mvn)
    if not mvn_cmd:
        # MAVEN_HOME not set — shutil.which still finds it on PATH, and (critically
        # on Windows) resolves the .cmd extension itself. A bare "mvn" string handed
        # straight to subprocess.Popen fails with WinError 2: CreateProcess doesn't
        # append PATHEXT extensions the way cmd.exe's own shell resolution would —
        # same root cause as the tsc/WinError193 issue documented in qa_agent.py.
        import shutil as _shutil
        mvn_cmd = _shutil.which("mvn")
    if not mvn_cmd:
        mvnw = backend_dir / ("mvnw.cmd" if os.name == "nt" else "mvnw")
        mvn_cmd = str(mvnw) if mvnw.exists() else ("mvn.cmd" if os.name == "nt" else "mvn")
    return mvn_cmd


def _start_java_api_server(project_dir: Path, api_port: int = 8080) -> subprocess.Popen | None:
    """Start the Java Spring Boot API server."""
    backend_dir = project_dir / "backend"
    pom_file = backend_dir / "pom.xml"
    if not pom_file.exists():
        print("[api_server] WARNING: backend/pom.xml not found", flush=True)
        return None

    env = os.environ.copy()

    # Read backend/.env for JAVA_HOME and MAVEN_HOME
    backend_env_file = backend_dir / ".env"
    if backend_env_file.exists():
        for line in backend_env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                if val.strip():
                    env[key.strip()] = val.strip()

    # Set PORT and DB_PATH AFTER reading .env so dynamic port always wins.
    # DB_PATH comes from api_runner's own java_backend_db_path — the SAME
    # function _find_app_db_file (the later seeding step) consults, so the
    # launcher and the seeder can never independently disagree about where
    # this project's real database file lives.
    from api_agents.api_runner import java_backend_db_path
    env["PORT"] = str(api_port)
    env["DB_PATH"] = str(java_backend_db_path(backend_dir))

    mvn_cmd = resolve_java_maven_env(env, backend_dir)
    java_home = env.get("JAVA_HOME", "")

    log_file = open(str(project_dir / "api_server.log"), "w", encoding="utf-8", errors="replace")
    kwargs: dict = {"cwd": str(backend_dir), "env": env, "stdout": log_file, "stderr": log_file}
    if os.name == "nt":
        # CREATE_NO_WINDOW prevents a visible CMD prompt for .cmd batch files
        # while CREATE_NEW_PROCESS_GROUP allows independent termination
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW

    # spring-boot:run compiles test sources by default even though it never runs
    # them — LLM-generated test code compiling cleanly is a separate quality
    # concern from "does the app start", so skip it entirely here.
    cmd = [mvn_cmd, "spring-boot:run", "-Dmaven.test.skip=true",
           f"-Dspring-boot.run.arguments=--server.port={api_port}"]
    proc = subprocess.Popen(cmd, **kwargs)
    print(f"[api_server] Started Java Spring Boot server on port {api_port} (PID {proc.pid}, JAVA_HOME={java_home})", flush=True)
    return proc


def _stop_api_server(project_name: str):
    """Stop the API server process for a project (and its DataChat sidecar, if any)."""
    for key in (project_name, f"{project_name}:datachat"):
        proc = _api_servers.pop(key, None)
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=8)
            except Exception:
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                except Exception:
                    pass
    # Kill any process on this project's API port and DataChat port
    for port in (_api_ports.get(project_name), _datachat_ports.get(project_name)):
        if port:
            try:
                subprocess.run(
                    f'for /f "tokens=5" %a in (\'netstat -ano ^| findstr "LISTENING" ^| findstr ":{port} "\') do taskkill /PID %a /F',
                    shell=True, capture_output=True, timeout=5,
                )
            except Exception:
                pass


def _make_junction(link: Path, target: Path):
    """Create a Windows directory junction link → target."""
    link.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
    )


def _ensure_ds_junction():
    """Create a clean-path junction for UIDesignSystem if the project path contains
    characters (like &) that break Vite @fs/ URLs.  No-op on clean deployments."""
    if not _NEEDS_JUNCTIONS:
        return
    junc = Path(_DS_CLEAN_JUNCTION)
    if not junc.exists():
        _make_junction(junc, DS_ROOT)


def _ensure_nm_junction():
    """No-op — SHARED_NM_DIR is now stored at a clean path, no junction needed."""
    pass


# Create junctions at import time (only when the path contains & or spaces)
_ensure_ds_junction()
_ensure_nm_junction()


def _link_ds_into_project(project_dir: Path):
    """No-op — DS is resolved via C:/TurboUI/mgds junction in vite.config.ts."""
    pass


# ── Post-processors (extracted to postprocessors.py) ──────────────────────────
from agents.postprocessors import (
    _patch_vite_for_ds, _fix_chart_container, _fix_self_wrapping_charts,
    _fix_badge_variants, _fix_prop_contracts, _patch_map_components,
    _patch_dynamic_imports, _patch_index_html, _patch_highcharts_more,
    _ensure_tsconfig_vite_types, run_all_postprocessors,
)


# ── Boilerplate safety net ────────────────────────────────────────────────────

def _ensure_boilerplate(files: dict, project_name: str) -> dict:
    """Ensure essential boilerplate files exist. Generates from templates if missing."""
    if "index.html" not in files:
        title = project_name.replace("-", " ").title()
        files["index.html"] = (
            '<!DOCTYPE html>\n<html lang="en">\n  <head>\n'
            '    <meta charset="UTF-8" />\n'
            '    <link rel="icon" type="image/svg+xml" href="./vite.svg" />\n'
            '    <meta name="viewport" content="width=device-width, initial-scale=1.0" />\n'
            f'    <title>{title}</title>\n'
            '    <link rel="preconnect" href="https://fonts.googleapis.com" />\n'
            '    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />\n'
            '    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />\n'
            '  </head>\n  <body>\n    <div id="root"></div>\n'
            '    <script type="module" src="/src/main.tsx"></script>\n'
            '  </body>\n</html>\n'
        )
        print(f"[boilerplate] Generated missing index.html", flush=True)

    if "package.json" not in files:
        files["package.json"] = (
            '{\n  "name": "' + project_name + '",\n'
            '  "private": true,\n  "version": "0.1.0",\n  "type": "module",\n'
            '  "scripts": {\n    "dev": "vite",\n    "build": "tsc && vite build",\n    "preview": "vite preview"\n  },\n'
            '  "dependencies": {\n'
            '    "react": "^18.2.0",\n    "react-dom": "^18.2.0",\n'
            '    "react-router-dom": "^6.22.0",\n    "lucide-react": "^0.344.0",\n'
            '    "d3": "^7.9.0"\n  },\n'
            '  "devDependencies": {\n'
            '    "typescript": "^5.3.3",\n    "@types/react": "^18.2.56",\n'
            '    "@types/react-dom": "^18.2.19",\n    "@types/d3": "^7.4.3",\n'
            '    "vite": "^5.1.4",\n    "@vitejs/plugin-react": "^4.2.1",\n'
            '    "tailwindcss": "^3.4.1",\n    "postcss": "^8.4.35",\n'
            '    "autoprefixer": "^10.4.18"\n  }\n}\n'
        )
        print(f"[boilerplate] Generated missing package.json", flush=True)

    if "tsconfig.json" not in files:
        files["tsconfig.json"] = (
            '{\n  "compilerOptions": {\n    "target": "ES2020",\n    "useDefineForClassFields": true,\n'
            '    "lib": ["ES2020", "DOM", "DOM.Iterable"],\n    "module": "ESNext",\n'
            '    "skipLibCheck": true,\n    "moduleResolution": "bundler",\n'
            '    "allowImportingTsExtensions": true,\n    "resolveJsonModule": true,\n'
            '    "isolatedModules": true,\n    "noEmit": true,\n    "jsx": "react-jsx",\n'
            '    "strict": true,\n    "noUnusedLocals": false,\n    "noUnusedParameters": false,\n'
            '    "noFallthroughCasesInSwitch": true,\n    "types": ["vite/client"]\n'
            '  },\n  "include": ["src"]\n}\n'
        )
        print(f"[boilerplate] Generated missing tsconfig.json", flush=True)

    if "postcss.config.js" not in files:
        files["postcss.config.js"] = "export default {\n  plugins: {\n    tailwindcss: {},\n    autoprefixer: {}\n  }\n}\n"
        print(f"[boilerplate] Generated missing postcss.config.js", flush=True)

    if "tailwind.config.js" not in files:
        files["tailwind.config.js"] = (
            "/** @type {import('tailwindcss').Config} */\nexport default {\n"
            "  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],\n"
            "  theme: { extend: { fontFamily: { sans: ['Inter', 'sans-serif'] } } },\n"
            "  plugins: []\n}\n"
        )
        print(f"[boilerplate] Generated missing tailwind.config.js", flush=True)

    if "src/main.tsx" not in files:
        files["src/main.tsx"] = (
            "import React from 'react'\n"
            "import ReactDOM from 'react-dom/client'\n"
            "import { BrowserRouter } from 'react-router-dom'\n"
            "import App from './App'\n"
            "import './index.css'\n\n"
            "const BASE = import.meta.env.BASE_URL.replace(/\\/$/, '') || ''\n\n"
            "ReactDOM.createRoot(document.getElementById('root')!).render(\n"
            "  <React.StrictMode>\n"
            "    <BrowserRouter basename={BASE} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>\n"
            "      <App />\n"
            "    </BrowserRouter>\n"
            "  </React.StrictMode>\n)\n"
        )
        print(f"[boilerplate] Generated missing src/main.tsx", flush=True)

    if "src/index.css" not in files:
        files["src/index.css"] = (
            "@tailwind base;\n@tailwind components;\n@tailwind utilities;\n\n"
            "* { box-sizing: border-box; }\n\n"
            "body {\n  margin: 0;\n  padding: 0;\n"
            "  font-family: 'Inter', sans-serif;\n"
            "  background-color: #F1F5F9;\n  color: #1E293B;\n}\n"
        )
        print(f"[boilerplate] Generated missing src/index.css", flush=True)

    return files


# ── API Server bundling ───────────────────────────────────────────────────────
# Moved out of this package to AgentPlatform/catalog/ — see
# webui_integration_engineer's own docstring for why it's not still named
# "services_engineer".
_SKILLS_DIR = Path(__file__).resolve().parent.parent.parent / "AgentPlatform" / "catalog" / "webui_integration_engineer" / "templates"

def _bundle_frontend_only(files: dict) -> dict:
    """New pipeline (CrewOrchestrator._run_backend_generation, either
    language): the backend is already real, per-project generated code —
    not this function's job to build or overwrite. But useApi.hook.ts and
    ExportToolbar.tsx are backend-agnostic, universally-needed frontend
    pieces that _bundle_api_server/_bundle_java_api_server are ALSO the only
    thing that bundles — skip straight to those two instead of returning
    empty-handed (a page that imports either would otherwise fail to
    resolve the module at all)."""
    hook_template = _SKILLS_DIR / "useApi.hook.ts"
    if hook_template.exists():
        files["src/hooks/useApi.ts"] = hook_template.read_text(encoding="utf-8")
    export_toolbar = _SKILLS_DIR / "ExportToolbar.component.tsx"
    if export_toolbar.exists():
        files["src/components/ExportToolbar.tsx"] = export_toolbar.read_text(encoding="utf-8")
    return files


def _bundle_api_server(files: dict, backend_type: str = "python") -> dict:
    """If schema.sql is present, bundle API server into api/ subfolder + useApi hook."""
    if "schema.sql" not in files and "api/schema.sql" not in files and "backend/schema.sql" not in files:
        return files

    if backend_type == "java":
        if "backend/schema.sql" in files and "schema.sql" not in files:
            return _bundle_frontend_only(files)
        return _bundle_java_api_server(files)

    if "api/schema.sql" in files and "schema.sql" not in files:
        return _bundle_frontend_only(files)

    # Move schema.sql and seed.sql into api/ subfolder
    files["api/schema.sql"] = files.pop("schema.sql")
    if "seed.sql" in files:
        seed_content = files.pop("seed.sql")
        # Fix LLM-generated backslash escapes: \' → '' (SQL standard)
        seed_content = seed_content.replace("\\'", "''")
        files["api/seed.sql"] = seed_content

    # Move any versioned migration files too (schema_v2.sql, seed_v2.sql, ...
    # from a refine's incremental DB delta — see
    # CrewOrchestrator._run_data_modeling_refine). Same move, same escape fix.
    for key in [k for k in files if re.match(r"^(schema|seed)_v\d+\.sql$", k)]:
        content = files.pop(key)
        if key.startswith("seed_"):
            content = content.replace("\\'", "''")
        files[f"api/{key}"] = content

    # 1. Bundle app_server.py template into api/
    server_template = _SKILLS_DIR / "app_server_template.py"
    if server_template.exists():
        files["api/app_server.py"] = server_template.read_text(encoding="utf-8")
    else:
        print("[_bundle_api_server] WARNING: app_server_template.py not found", flush=True)
        return files

    # 1b. Bundle mcp_server.py — the real MCP server mounted at /mcp by
    # app_server_template.py; DATA_API_BASE defaults to this same process's
    # own port for the pure-Python case (set in app_server_template.py before
    # importing this module).
    mcp_template = _SKILLS_DIR / "mcp_server_template.py"
    if mcp_template.exists():
        files["api/mcp_server.py"] = mcp_template.read_text(encoding="utf-8")

    # 2. Bundle useApi hook
    hook_template = _SKILLS_DIR / "useApi.hook.ts"
    if hook_template.exists():
        files["src/hooks/useApi.ts"] = hook_template.read_text(encoding="utf-8")

    # 3. Bundle ExportToolbar shared component
    export_toolbar = _SKILLS_DIR / "ExportToolbar.component.tsx"
    if export_toolbar.exists():
        files["src/components/ExportToolbar.tsx"] = export_toolbar.read_text(encoding="utf-8")

    # 3. Fill and bundle .env into api/
    env_template = _SKILLS_DIR / "app_server_env_template.txt"
    if env_template.exists():
        from dotenv import dotenv_values
        parent_env = dotenv_values(Path(__file__).parent.parent.parent / ".env")
        env_content = env_template.read_text(encoding="utf-8")
        env_content = env_content.replace("{{LITELLM_API_BASE}}", parent_env.get("LITELLM_API_BASE", ""))
        env_content = env_content.replace("{{LITELLM_API_KEY}}", parent_env.get("LITELLM_API_KEY", ""))
        env_content = env_content.replace("{{LITELLM_SSL_CERT}}", parent_env.get("LITELLM_SSL_CERT", ""))
        env_content = env_content.replace("{{LITELLM_MODEL}}", parent_env.get("LITELLM_SONNET_46_MODEL", "claude-sonnet-4-6"))
        files["api/.env"] = env_content

    # 4. Bundle requirements.txt into api/
    files["api/requirements.txt"] = "fastapi\nuvicorn\npython-dotenv\nopenai\nhttpx\nopenpyxl\nPyMuPDF\nfastmcp\nanthropic[bedrock]\n"

    print(f"[_bundle_api_server] Bundled into api/: app_server.py + schema.sql + .env + requirements.txt", flush=True)
    return files


_SPRINGBOOT_DIR = _SKILLS_DIR / "springboot"

def _bundle_java_api_server(files: dict) -> dict:
    """Bundle a Spring Boot backend instead of the Python FastAPI server."""
    # Move schema.sql and seed.sql into backend/ (Spring Boot working dir)
    files["backend/schema.sql"] = files.pop("schema.sql")
    if "seed.sql" in files:
        seed_content = files.pop("seed.sql")
        seed_content = seed_content.replace("\\'", "''")
        files["backend/seed.sql"] = seed_content

    # Move any versioned migration files too (schema_v2.sql, seed_v2.sql, ...
    # from a refine's incremental DB delta — see
    # CrewOrchestrator._run_data_modeling_refine).
    for key in [k for k in files if re.match(r"^(schema|seed)_v\d+\.sql$", k)]:
        content = files.pop(key)
        if key.startswith("seed_"):
            content = content.replace("\\'", "''")
        files[f"backend/{key}"] = content

    # Bundle all Spring Boot template files
    if not _SPRINGBOOT_DIR.exists():
        print("[_bundle_api_server] WARNING: springboot template dir not found", flush=True)
        return files

    for f in _SPRINGBOOT_DIR.rglob("*"):
        if f.is_file():
            rel = f.relative_to(_SPRINGBOOT_DIR).as_posix()
            try:
                files[f"backend/{rel}"] = f.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                pass

    # Bundle useApi hook (same frontend hook — just hits /api/{table})
    hook_template = _SKILLS_DIR / "useApi.hook.ts"
    if hook_template.exists():
        files["src/hooks/useApi.ts"] = hook_template.read_text(encoding="utf-8")

    # Bundle ExportToolbar shared component
    export_toolbar = _SKILLS_DIR / "ExportToolbar.component.tsx"
    if export_toolbar.exists():
        files["src/components/ExportToolbar.tsx"] = export_toolbar.read_text(encoding="utf-8")

    # Mark backend type in a metadata file so _start_api_server knows what to launch
    files["backend/.backend_type"] = "java-springboot"

    # Generate .env with auto-detected Java/Maven paths
    java_home = os.environ.get("JAVA_HOME", "")
    maven_home = os.environ.get("MAVEN_HOME", os.environ.get("M2_HOME", ""))
    if not java_home:
        # Try to detect from common Windows locations
        for candidate in [r"C:\Program Files\Java\jdk-21", r"C:\Program Files\Java\jdk-17"]:
            if Path(candidate).exists():
                java_home = candidate
                break
    if not maven_home:
        for candidate in [r"C:\Program Files\Maven\3.9.16", r"C:\Program Files\Maven\apache-maven-3.9.9"]:
            if Path(candidate).exists():
                maven_home = candidate
                break
    env_template = _SPRINGBOOT_DIR / "env_template.txt"
    if env_template.exists():
        env_content = env_template.read_text(encoding="utf-8")
        env_content = env_content.replace("{{JAVA_HOME}}", java_home)
        env_content = env_content.replace("{{MAVEN_HOME}}", maven_home)
        # Propagate LiteLLM credentials so ChatController can reach the LLM proxy
        litellm_vars = ["LITELLM_API_BASE", "LITELLM_API_KEY", "LITELLM_SONNET_46_MODEL", "LITELLM_SSL_CERT"]
        litellm_lines = []
        for var in litellm_vars:
            val = os.environ.get(var, "")
            if val:
                litellm_lines.append(f"{var}={val}")
        if litellm_lines:
            env_content += "\n# LiteLLM (AI Concierge)\n" + "\n".join(litellm_lines) + "\n"
        files["backend/.env"] = env_content

    print(f"[_bundle_api_server] Bundled Java Spring Boot backend into backend/", flush=True)
    return files


def _ensure_schema_sql(files: dict, force: bool = False) -> dict:
    """
    Safety net: if the LLM generated API-first signals (useApi imports, tableName in configs)
    but forgot to include schema.sql, auto-generate it from src/types.ts.
    When force=True, skip signal detection — always generate if schema.sql is missing.
    """
    if "schema.sql" in files or "api/schema.sql" in files or "backend/schema.sql" in files:
        return files

    if not force:
        # Detect API-first signals
        has_use_api = any("useApi" in (v if isinstance(v, str) else "") for v in files.values())
        has_table_name = any("tableName" in (v if isinstance(v, str) else "") for k, v in files.items() if k.endswith(".config.ts"))
        if not has_use_api and not has_table_name:
            return files

    types_content = files.get("src/types.ts", "")
    if not types_content or not isinstance(types_content, str):
        print("[_ensure_schema_sql] WARNING: src/types.ts is missing or empty — cannot generate schema", flush=True)
        return files

    print("[_ensure_schema_sql] schema.sql missing — generating from types.ts", flush=True)

    import re
    interfaces = re.findall(
        r"export\s+interface\s+(\w+)\s*\{([^}]+)\}",
        types_content, re.DOTALL
    )
    if not interfaces:
        print("[_ensure_schema_sql] WARNING: no interfaces found in types.ts", flush=True)
        return files

    def _to_snake(name: str) -> str:
        s = re.sub(r"([A-Z])", r"_\1", name).lstrip("_").lower()
        return s

    def _ts_to_sqlite(ts_type: str) -> str:
        ts_type = ts_type.strip().rstrip(";").strip()
        if "number" in ts_type:
            if "[]" in ts_type:
                return "TEXT"
            if "null" in ts_type:
                return "REAL"
            return "REAL"
        return "TEXT"

    schema_lines = []
    table_names = []
    for iface_name, body in interfaces:
        # Skip helper/aggregation interfaces — only process primary data types
        fields = re.findall(r"(\w+)\s*[?]?\s*:\s*([^\n;]+)", body)
        if not fields or len(fields) < 3:
            continue
        # Only process interfaces that have an 'id' field — those are DB tables
        field_names = [f[0] for f in fields]
        if "id" not in field_names:
            continue

        # Convert interface name to table name (e.g. GlobalSale -> global_sales)
        table = _to_snake(iface_name)
        if not table.endswith("s"):
            table += "s"

        cols = []
        for fname, ftype in fields:
            if fname == "id":
                cols.append("  id INTEGER PRIMARY KEY AUTOINCREMENT")
            else:
                sqlite_type = _ts_to_sqlite(ftype)
                # Improve type detection from field name
                if any(x in fname for x in ["revenue", "growth", "share", "pct", "bound"]):
                    sqlite_type = "REAL"
                elif any(x in fname for x in ["units", "_count", "dealer_count"]) or fname.endswith("_id"):
                    sqlite_type = "INTEGER"
                nullable = "null" in ftype.lower()
                null_str = "" if nullable else " NOT NULL"
                cols.append(f"  {fname} {sqlite_type}{null_str}")

        if cols:
            schema_lines.append(
                f"CREATE TABLE IF NOT EXISTS {table} (\n"
                + ",\n".join(cols)
                + "\n);"
            )
            table_names.append(table)

    if schema_lines:
        files["schema.sql"] = "\n\n".join(schema_lines)
        print(f"[_ensure_schema_sql] Generated schema.sql with tables: {table_names}", flush=True)

        # Generate seed data via LLM call
        schema_text = files["schema.sql"]
        seed_prompt = (
            "Generate realistic seed.sql INSERT statements for the following SQLite schema.\n"
            "Rules:\n"
            "- At least 40-60 rows per main data table, fewer for small lookup tables\n"
            "- Use realistic values — real country names, real car brands, plausible numbers\n"
            "- Return ONLY valid SQL INSERT statements, no comments or explanations\n"
            "- Use single quotes for strings, NULL (not 'null') for nulls\n\n"
            f"Schema:\n{schema_text}"
        )
        try:
            from agents.llm import chat as _chat_llm
            seed_content = _chat_llm(
                [{"role": "user", "content": seed_prompt}],
                system="You are a SQL data generator. Return ONLY valid SQLite INSERT statements.",
                max_tokens=16000,
            )
            if seed_content and "INSERT" in seed_content.upper():
                seed_content = _extract_code_from_llm_response(seed_content)
                files["seed.sql"] = seed_content
                print(f"[_ensure_schema_sql] Generated seed.sql via LLM ({len(seed_content)} chars)", flush=True)
            else:
                files["seed.sql"] = f"-- Placeholder: seed data generation failed\n"
                print(f"[_ensure_schema_sql] LLM seed generation returned no INSERT statements", flush=True)
        except Exception as e:
            files["seed.sql"] = f"-- Placeholder: seed data generation failed ({e})\n"
            print(f"[_ensure_schema_sql] Seed LLM call failed: {e}", flush=True)

    return files








def _repair_json(content: str, rel_path: str) -> str:
    """Validate JSON content and attempt common repairs if invalid."""
    import json, re
    content = _extract_code_from_llm_response(content.strip())
    try:
        json.loads(content, strict=False)
        return content
    except json.JSONDecodeError:
        pass
    # Common fix 1: trailing commas before ] or }
    fixed = re.sub(r",\s*([}\]])", r"\1", content)
    try:
        json.loads(fixed, strict=False)
        print(f"[_repair_json] Fixed trailing commas in {rel_path}", flush=True)
        return fixed
    except json.JSONDecodeError:
        pass
    # Common fix 2: single quotes → double quotes
    fixed2 = fixed.replace("'", '"')
    try:
        json.loads(fixed2, strict=False)
        print(f"[_repair_json] Fixed quotes in {rel_path}", flush=True)
        return fixed2
    except json.JSONDecodeError:
        pass
    # Common fix 3: truncated JSON — attempt to close open brackets/braces
    depth_bracket = fixed.count("[") - fixed.count("]")
    depth_brace = fixed.count("{") - fixed.count("}")
    if depth_bracket > 0 or depth_brace > 0:
        # Remove trailing comma if present
        closed = re.sub(r",\s*$", "", fixed)
        closed += "]" * depth_bracket + "}" * depth_brace
        try:
            json.loads(closed, strict=False)
            print(f"[_repair_json] Closed truncated JSON in {rel_path}", flush=True)
            return closed
        except json.JSONDecodeError:
            pass
    # Common fix 4: JS-style comments
    no_comments = re.sub(r"//.*?$", "", fixed, flags=re.MULTILINE)
    no_comments = re.sub(r"/\*.*?\*/", "", no_comments, flags=re.DOTALL)
    try:
        json.loads(no_comments, strict=False)
        print(f"[_repair_json] Stripped comments in {rel_path}", flush=True)
        return no_comments
    except json.JSONDecodeError:
        pass
    print(f"[_repair_json] WARNING: Could not repair {rel_path} — writing as-is", flush=True)
    return content


_PRESERVE_FILES = {".history.json", ".buildlog.json", ".meta.json", ".docker.json", ".architecture.md", ".architecture.html", "screenshots", "docker", "app.db", "data.db"}

def _write_files(project_dir: Path, files: dict):
    project_dir.mkdir(parents=True, exist_ok=True)

    # Preserve database files from subdirectories (e.g. api/data.db) before wipe
    _saved_dbs: dict[Path, bytes] = {}
    for db_name in ("data.db", "app.db"):
        for db_file in project_dir.rglob(db_name):
            if "node_modules" not in db_file.parts:
                _saved_dbs[db_file] = db_file.read_bytes()

    for child in project_dir.iterdir():
        if child.name in ("node_modules",) or child.name in _PRESERVE_FILES:
            continue
        try:
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
        except Exception:
            pass

    # Restore preserved database files
    for db_path, db_bytes in _saved_dbs.items():
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path.write_bytes(db_bytes)
    from agents.sanitize_js import sanitize
    for rel_path, content in files.items():
        fp = project_dir / rel_path
        fp.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, list):
            content = "\n".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            )
        # Skip empty content entirely — never write blank files
        if not content or not content.strip():
            print(f"[_write_files] Skipping empty content for {rel_path}", flush=True)
            continue
        if rel_path.endswith(".json"):
            content = _repair_json(content, rel_path)
        content = sanitize(content, rel_path)
        fp.write_text(content, encoding="utf-8")
    # Junction must be created after node_modules exists (npm install runs after _write_files)
    # So we call _link_ds_into_project separately after npm install.


_REQUIRED_COMPONENT_SOURCES: dict[str, str] = {
    "FilterDropdown": """\
import { useMemo } from 'react'

type Option = string | { value: string; label: string }

interface Props {
  value: string
  options: Option[]
  onChange: (value: string) => void
  label?: string
  className?: string
}

export default function FilterDropdown({ value, options, onChange, label, className = '' }: Props) {
  const normalized = useMemo(() =>
    options.map((o) => typeof o === 'string' ? { value: o, label: o } : o),
    [options]
  )
  return (
    <div className={`flex flex-col gap-[4px] ${className}`}>
      {label && <span className="text-[11px] font-medium text-[#9CA3AF] uppercase tracking-wide">{label}</span>}
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="h-[40px] min-w-[140px] appearance-none pl-[12px] pr-[32px] rounded-[8px] border border-[#E5E7EB] bg-white text-[14px] text-[#132445] outline-none focus:border-[#0064D2] cursor-pointer"
        >
          {normalized.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <svg className="w-4 h-4 absolute right-[10px] top-1/2 -translate-y-1/2 text-[#9CA3AF] pointer-events-none" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 9l6 6 6-6" />
        </svg>
      </div>
    </div>
  )
}
export { FilterDropdown }
""",
    "Pagination": """\
interface Props {
  page: number
  pageCount: number
  onChange: (page: number) => void
}

export default function Pagination({ page, pageCount, onChange }: Props) {
  if (pageCount <= 1) return null
  const pages: (number | '...')[] = []
  if (pageCount <= 7) {
    for (let i = 1; i <= pageCount; i++) pages.push(i)
  } else {
    pages.push(1)
    if (page > 3) pages.push('...')
    for (let i = Math.max(2, page - 1); i <= Math.min(pageCount - 1, page + 1); i++) pages.push(i)
    if (page < pageCount - 2) pages.push('...')
    pages.push(pageCount)
  }
  const btn = (label: string | number, target: number, disabled: boolean) => (
    <button
      key={String(label)}
      disabled={disabled}
      onClick={() => !disabled && onChange(target)}
      className="h-[32px] min-w-[32px] px-[8px] rounded-[6px] text-[13px] font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
      style={{
        backgroundColor: target === page ? '#0064D2' : 'transparent',
        color: target === page ? '#FFFFFF' : '#374151',
        border: target === page ? 'none' : '1px solid #E5E7EB',
      }}
    >
      {label}
    </button>
  )
  return (
    <div className="flex items-center gap-[4px]">
      {btn('\\u2039', page - 1, page <= 1)}
      {pages.map((p, i) =>
        p === '...'
          ? <span key={`e${i}`} className="px-[4px] text-[#9CA3AF] text-[13px]">\\u2026</span>
          : btn(p, p as number, (p as number) === page)
      )}
      {btn('\\u203a', page + 1, page >= pageCount)}
    </div>
  )
}
export { Pagination }
""",
    "PersonaCard": """\
interface Persona {
  id?: string | number
  name: string
  role?: string
  description?: string
  accent?: string
  color?: string
  avatar?: string
  [key: string]: any
}

interface Props {
  persona: Persona
  active: boolean
  onClick: () => void
}

export default function PersonaCard({ persona, active, onClick }: Props) {
  const accent = persona.accent ?? persona.color ?? '#0064D2'
  const initials = persona.name.split(' ').map((w: string) => w[0]).join('').slice(0, 2).toUpperCase()
  return (
    <button
      onClick={onClick}
      className="w-full text-left p-[12px] rounded-[10px] border transition-all"
      style={{
        borderColor: active ? accent : '#E5E7EB',
        backgroundColor: active ? `${accent}12` : '#FFFFFF',
        boxShadow: active ? `0 0 0 2px ${accent}40` : 'none',
      }}
    >
      <div className="flex items-center gap-[10px]">
        {persona.avatar ? (
          <img src={persona.avatar} alt={persona.name} className="w-[36px] h-[36px] rounded-full object-cover flex-shrink-0" />
        ) : (
          <div
            className="w-[36px] h-[36px] rounded-full flex items-center justify-center text-white text-[13px] font-bold flex-shrink-0"
            style={{ backgroundColor: accent }}
          >
            {initials}
          </div>
        )}
        <div className="min-w-0">
          <div className="text-[13px] font-semibold truncate" style={{ color: '#132445' }}>{persona.name}</div>
          {persona.role && <div className="text-[11px] truncate" style={{ color: '#9CA3AF' }}>{persona.role}</div>}
        </div>
      </div>
    </button>
  )
}
export { PersonaCard }
""",
}


def _build_usa_map_wrapper(wrapped_name: str) -> str:
    """Build a UsaSalesMap.tsx that wraps whatever USA map variant was generated."""
    return f"""\
import {wrapped_name} from './{wrapped_name}'

const ABBR_TO_STATE: Record<string, string> = {{
  AL: 'Alabama', AK: 'Alaska', AZ: 'Arizona', AR: 'Arkansas', CA: 'California',
  CO: 'Colorado', CT: 'Connecticut', DE: 'Delaware', FL: 'Florida', GA: 'Georgia',
  HI: 'Hawaii', ID: 'Idaho', IL: 'Illinois', IN: 'Indiana', IA: 'Iowa',
  KS: 'Kansas', KY: 'Kentucky', LA: 'Louisiana', ME: 'Maine', MD: 'Maryland',
  MA: 'Massachusetts', MI: 'Michigan', MN: 'Minnesota', MS: 'Mississippi', MO: 'Missouri',
  MT: 'Montana', NE: 'Nebraska', NV: 'Nevada', NH: 'New Hampshire', NJ: 'New Jersey',
  NM: 'New Mexico', NY: 'New York', NC: 'North Carolina', ND: 'North Dakota', OH: 'Ohio',
  OK: 'Oklahoma', OR: 'Oregon', PA: 'Pennsylvania', RI: 'Rhode Island', SC: 'South Carolina',
  SD: 'South Dakota', TN: 'Tennessee', TX: 'Texas', UT: 'Utah', VT: 'Vermont',
  VA: 'Virginia', WA: 'Washington', WV: 'West Virginia', WI: 'Wisconsin', WY: 'Wyoming',
  DC: 'District of Columbia',
}}

const STATE_TO_ABBR: Record<string, string> = Object.fromEntries(
  Object.entries(ABBR_TO_STATE).map(([k, v]) => [v, k])
) as Record<string, string>

export interface StateSaleRow {{
  state: string
  make: string
  units: number
  abbr?: string
}}

interface Props {{
  stateSales: StateSaleRow[]
  makeFilter?: string
  height?: number
  selectedState?: string
  onStateClick?: (stateName: string) => void
}}

export default function UsaSalesMap({{ stateSales, makeFilter, height, selectedState: _selectedState, onStateClick }}: Props) {{
  const rows = stateSales.map((r) => ({{
    ...r,
    abbr: r.abbr ?? STATE_TO_ABBR[r.state] ?? r.state,
  }}))
  return (
    <{wrapped_name}
      stateSales={{{{rows}}}}
      makeFilter={{{{makeFilter ?? 'All'}}}}
      height={{{{height}}}}
      onStateClick={{{{onStateClick ? (abbr: string) => {{{{
        const name = ABBR_TO_STATE[abbr] ?? abbr
        onStateClick(name)
      }}}} : undefined}}}}
    />
  )
}}
export {{ UsaSalesMap }}
"""


def _ensure_required_components(files: dict) -> dict:
    """
    Guarantee FilterDropdown, Pagination, and PersonaCard always exist.
    Also creates UsaSalesMap.tsx if pages need it but only a variant was generated.
    """
    # Inject missing required components
    for name, source in _REQUIRED_COMPONENT_SOURCES.items():
        comp_path = f"src/components/{name}.tsx"
        if comp_path not in files:
            files[comp_path] = source
            print(f"[_ensure_required_components] injected {comp_path}", flush=True)

    # If pages import UsaSalesMap but the component doesn't exist, create a wrapper
    pages_want_usa = any(
        "UsaSalesMap" in content
        for path, content in files.items()
        if path.startswith("src/pages/")
    )
    usa_exists = "src/components/UsaSalesMap.tsx" in files
    if pages_want_usa and not usa_exists:
        _USA_VARIANTS = ("USStateMap", "USSalesMap", "UsStateMap", "UsStateSalesMap")
        actual = None
        for fp in files:
            fname = fp.split("/")[-1].replace(".tsx", "")
            if fname in _USA_VARIANTS or any(v in fname for v in _USA_VARIANTS):
                if "World" not in fname:
                    actual = fname
                    break
        if actual:
            files["src/components/UsaSalesMap.tsx"] = _build_usa_map_wrapper(actual)
            print(f"[_ensure_required_components] created UsaSalesMap.tsx wrapping {actual}", flush=True)

    return files


def _looks_incomplete(content: str, original: str | None = None) -> str | None:
    """Cheap truncation heuristic for LLM-produced "fixed" file content.
    An LLM repair call that gets cut off mid-statement still very often
    returns something that LOOKS like a plausible response (no JSON error,
    no exception) — this is exactly what silently corrupted Forecast.tsx:
    a heal pass's truncated output was accepted and written to disk with no
    check at all. Balance-counting isn't a real parser (doesn't account for
    braces/parens inside strings or comments), but a genuine truncation's
    imbalance is large enough (a whole missing closing tail) that this still
    catches it reliably, cheaply, on every heal call's output.
    """
    for open_ch, close_ch, name in (("{", "}", "braces"), ("(", ")", "parens"), ("[", "]", "brackets")):
        o, c = content.count(open_ch), content.count(close_ch)
        if o != c:
            return f"unbalanced {name} ({o} '{open_ch}' vs {c} '{close_ch}')"
    if original:
        # A genuine targeted fix rewrites at most a few lines — reproduced
        # directly: a tsc_heal repair for App.tsx came back as just the one
        # import + JSX line it was told to fix, dropping the entire rest of
        # the file (export default function, routes, Sidebar, everything).
        # That fragment was perfectly brace/paren/bracket-balanced, so it
        # passed every check above and silently overwrote a working file
        # with a 2-line stub. A response drastically shorter than what it
        # was fixing has dropped real content, not deliberately trimmed it.
        orig_len, fixed_len = len(original.strip()), len(content.strip())
        if orig_len > 200 and fixed_len < orig_len * 0.5:
            return f"drastically shorter than original ({fixed_len} vs {orig_len} chars)"
        if "export" in original and "export" not in content:
            return "original had an export statement, fix has none"
    return None


def _extract_code_from_llm_response(text: str) -> str:
    """
    Recover real file content from an LLM repair response that may be
    wrapped in a markdown code fence with a stray fragment BEFORE it.
    Reproduced directly: a _tsc_heal repair response came back as
    "<br>\\n\\n```tsx\\n<real, complete, valid code>\\n```" — every one of
    this file's repair loops (_tsc_heal, _esbuild_syntax_check, _qa_heal,
    _repair_seed_sql) only ever checked `text.startswith("````")`, which
    never fires when ANYTHING (even one stray tag) precedes the fence, so
    the wrapper was written straight into App.tsx as-is. It then also
    slipped past _looks_incomplete (brace/paren/bracket counts are
    unaffected by non-code wrapper text), and confused tsc into a cascade
    of unrelated-looking JSX parse errors on the next run — "no data on
    most screens" was every single page failing to boot because of this
    one file.

    Searches for a fenced block ANYWHERE in the response (not just at
    position 0) and returns just its content if found. Otherwise, strips
    any leading prose up to the first line that looks like real code
    (import/const/function/interface/a comment) — same idea _qa_heal used
    to do ad hoc, now shared. Returns the input unchanged if neither shape
    is detected, which is the common, uncontaminated case.
    """
    text = text.strip()
    fence_m = re.search(r"```(?:[A-Za-z]*)?\n([\s\S]*?)\n```", text)
    if fence_m:
        return fence_m.group(1).strip()
    if not text.startswith(("import ", "//", "/*", "'use")):
        code_m = re.search(r"^(import |// |/\*)", text, re.MULTILINE)
        if code_m and code_m.start() > 0:
            leading = text[:code_m.start()]
            if not any(kw in leading for kw in ["from ", "export ", "const ", "function ", "interface "]):
                return text[code_m.start():].strip()
    return text


def _tsc_heal(project_dir: Path, files: dict, progress=None) -> dict:
    """
    Write files, run tsc --noEmit, feed errors back to LLM for targeted fixes.
    Loops up to 3 rounds. Returns the (possibly fixed) files dict.
    """
    import re as _re
    import subprocess as _sp
    from agents.component_contracts import build_component_api_section
    from agents.prompts import ds_component_api_section
    from agents.llm import chat

    contracts_section = build_component_api_section() + "\n\n" + ds_component_api_section()

    TSC_SYSTEM = (
        "You are a TypeScript expert fixing compilation errors in a React/TypeScript app. "
        "Fix ONLY the reported errors. Do not rewrite unrelated code. "
        "Return ONLY the corrected file content — no markdown fences, no explanation."
    )

    for round_n in range(3):
        # Write current state to disk so tsc can read it
        for rel_path, content in files.items():
            fp = project_dir / rel_path
            fp.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, list):
                content = "\n".join(
                    item.get("text", "") if isinstance(item, dict) else str(item)
                    for item in content
                )
            if not content or not content.strip():
                continue
            if rel_path.endswith(".json"):
                content = _repair_json(content, rel_path)
            fp.write_text(content, encoding="utf-8")

        # Invoke tsc's JS entry point directly via node.exe — NOT the
        # node_modules/.bin/tsc.cmd wrapper via shell=True. That combination
        # silently breaks on this exact codebase's own real path: cmd.exe
        # treats '&' as a command separator, and this repo lives under
        # "...OneDrive - S&P Global\...", so cmd.exe splits the invocation
        # right after "S" and fails with "'P' is not recognized as an
        # internal or external command" — a real, non-crashing exit code,
        # just not one whose stdout matches the TS-error-line regex below,
        # so this whole check has been silently finding zero parseable
        # errors and giving up every single round, completely invisible
        # (this function's own failure path only ever prints(), never
        # progress()s, so nothing showed in any Build Log either). Same
        # root cause, same fix already proven and in production for
        # qa_agent.py's own _tsc_check — this is the last caller still on
        # the broken pattern.
        tsc_js = project_dir / "node_modules" / "typescript" / "lib" / "tsc.js"
        if not tsc_js.exists():
            print("[tsc_heal] tsc not found — skipping", flush=True)
            return files
        node_exe = Path(NODE_PATH) / "node.exe"
        tsc_env = os.environ.copy()
        tsc_env["PATH"] = NODE_PATH + os.pathsep + tsc_env.get("PATH", "")

        result = _sp.run(
            [str(node_exe), str(tsc_js), "--noEmit", "--pretty", "false"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=60,
            env=tsc_env,
        )
        if result.returncode == 0:
            print(f"[tsc_heal] Clean after round {round_n}", flush=True)
            return files

        # Parse errors grouped by file
        errors_by_file: dict[str, list[str]] = {}
        for line in (result.stdout + result.stderr).splitlines():
            m = _re.match(r"^(src/[^(]+)\((\d+),\d+\):\s*error\s*(TS\d+):\s*(.+)$", line)
            if m:
                fpath, lineno, code, msg = m.groups()
                errors_by_file.setdefault(fpath, []).append(f"  Line {lineno} [{code}]: {msg}")

        if not errors_by_file:
            print(f"[tsc_heal] Round {round_n+1}: tsc failed but no parseable errors — stopping", flush=True)
            break

        total_errors = sum(len(v) for v in errors_by_file.values())
        print(f"[tsc_heal] Round {round_n+1}: {total_errors} errors in {len(errors_by_file)} files", flush=True)
        if progress:
            progress(f"tsc_heal:Fixing {total_errors} TypeScript errors (round {round_n+1}/3)…")

        # Fix each erroring file via LLM
        any_fixed = False
        for file_path, error_lines in errors_by_file.items():
            if file_path not in files:
                continue

            # ── Quick fix: "Cannot find name" errors can often be fixed without LLM ──
            content = files[file_path]
            quick_fixed = False
            for err in error_lines:
                # Pattern: "Cannot find name 'svgEl'" in a ResizeObserver context
                m_name = _re.search(r"Cannot find name '(\w+El)'", err)
                if m_name:
                    bad_var = m_name.group(1)
                    # Find the correct variable from nearby scope (const el = ...Ref.current)
                    scope_match = _re.search(
                        r"const\s+(\w+)\s*=\s*\w+Ref\.current",
                        content[:content.find(bad_var)] if bad_var in content else "",
                    )
                    if scope_match:
                        good_var = scope_match.group(1)
                        content = content.replace(bad_var, good_var)
                        quick_fixed = True
                        print(f"[tsc_heal] Quick fix: '{bad_var}' → '{good_var}' in {file_path}", flush=True)

            if quick_fixed:
                files[file_path] = content
                any_fixed = True
                continue

            error_text = "\n".join(error_lines)
            # Scale max_tokens to file size — large files need more output budget
            file_tokens_estimate = len(files[file_path]) // 3
            heal_max_tokens = max(8000, min(64000, file_tokens_estimate + 2000))
            prompt = (
                f"Fix these TypeScript compilation errors. Change ONLY what is needed.\n\n"
                f"{contracts_section}\n\n"
                f"File: {file_path}\n"
                f"Errors:\n{error_text}\n\n"
                f"Current file content:\n{files[file_path]}"
            )
            try:
                fixed = chat(
                    [{"role": "user", "content": prompt}],
                    system=TSC_SYSTEM,
                    max_tokens=heal_max_tokens,
                ).strip()
                fixed = _extract_code_from_llm_response(fixed)
                if fixed and fixed != files[file_path]:
                    reason = _looks_incomplete(fixed, files[file_path])
                    if reason:
                        print(f"[tsc_heal] Rejected fix for {file_path} - looks incomplete ({reason}), keeping original", flush=True)
                    else:
                        files[file_path] = fixed
                        any_fixed = True
                        print(f"[tsc_heal] Fixed {file_path}", flush=True)
            except Exception as ex:
                print(f"[tsc_heal] LLM fix failed for {file_path}: {ex}", flush=True)

        if not any_fixed:
            print("[tsc_heal] No files changed — stopping early", flush=True)
            break

    return files


def _esbuild_syntax_check(project_dir: Path, files: dict, progress=None) -> dict:
    """
    Run esbuild on each .tsx/.ts file to catch parse errors tsc misses
    (unterminated strings, invalid JSX, etc.).
    Only fixes files with genuine PARSE errors (not import resolution).
    Caps at 5 LLM repair calls to avoid runaway time.
    """
    import subprocess as _sp
    import platform as _platform
    from concurrent.futures import ThreadPoolExecutor as _ThreadPoolExecutor
    from agents.llm import chat

    esbuild_name = "esbuild.cmd" if _platform.system() == "Windows" else "esbuild"
    esbuild_bin = project_dir / "node_modules" / ".bin" / esbuild_name
    if not esbuild_bin.exists():
        import os as _os
        junction_dir = _os.environ.get("TURBOUI_JUNCTION_DIR", "")
        if junction_dir:
            shared_esbuild = Path(junction_dir) / "shared-nm" / "node_modules" / ".bin" / esbuild_name
            if shared_esbuild.exists():
                esbuild_bin = shared_esbuild
            else:
                return files
        else:
            return files

    outfile = "NUL" if _platform.system() == "Windows" else "/dev/null"

    ESBUILD_FIX_SYSTEM = (
        "You are fixing a syntax error reported by esbuild in a React/TypeScript file. "
        "Fix ONLY the reported error (unterminated string, missing bracket, etc.). "
        "Return ONLY the corrected file content — no markdown fences, no explanation."
    )

    # Only parse errors matter — filter out import resolution and module-not-found
    IGNORE_PATTERNS = ["Could not resolve", "No loader", "not found", "ENOENT"]

    for round_n in range(2):
        errors_found = {}
        for rel_path, content in files.items():
            if not (rel_path.endswith(".tsx") or rel_path.endswith(".ts")):
                continue
            if rel_path.endswith(".d.ts") or "node_modules" in rel_path:
                continue
            file_path = project_dir / rel_path
            if not file_path.exists():
                continue
            loader = "tsx" if rel_path.endswith(".tsx") else "ts"
            try:
                result = _sp.run(
                    [str(esbuild_bin), str(file_path), f"--loader={loader}", f"--outfile={outfile}"],
                    capture_output=True, text=True, timeout=15,
                    cwd=str(project_dir),
                )
                if result.returncode != 0 and result.stderr:
                    stderr = result.stderr.strip()
                    # Skip import/resolution errors — only keep parse errors
                    if any(pat in stderr for pat in IGNORE_PATTERNS):
                        continue
                    errors_found[rel_path] = stderr
            except Exception:
                continue

        if not errors_found:
            if round_n > 0:
                print(f"[esbuild_check] Clean after round {round_n}", flush=True)
            return files

        # Cap at 5 files to avoid runaway LLM calls
        if len(errors_found) > 5:
            print(f"[esbuild_check] Round {round_n+1}: {len(errors_found)} files with errors — capping at 5", flush=True)
            errors_found = dict(list(errors_found.items())[:5])
        else:
            print(f"[esbuild_check] Round {round_n+1}: {len(errors_found)} files with parse errors", flush=True)

        if progress:
            progress(f"esbuild_check:Fixing {len(errors_found)} parse errors (round {round_n+1}/2)…")

        def _fix_one(rel_path: str, err_output: str) -> bool:
            """Repair a single file's parse error. Runs on its own thread —
            each iteration reads/writes a DIFFERENT rel_path's entry in
            `files` and its own file on disk, and issues its own independent
            LLM call + esbuild verification subprocess, so nothing here is
            shared mutable state across files. Returns True if this file was
            fixed."""
            file_content = files.get(rel_path, "")
            if not file_content:
                return False
            err_lines = [l for l in err_output.split("\n") if "error:" in l.lower() or "ERROR" in l][:5]
            err_summary = "\n".join(err_lines) if err_lines else err_output[:500]
            # Scale to file size like _tsc_heal does — a fixed 32000 ceiling
            # is exactly what let a full rewrite of a large file (e.g. the
            # ~1400-line Charts.skill.tsx template) get cut off mid-statement.
            file_tokens_estimate = len(file_content) // 3
            heal_max_tokens = max(8000, min(64000, file_tokens_estimate + 2000))

            try:
                fixed = chat(
                    messages=[{"role": "user", "content": (
                        f"File: {rel_path}\n\n"
                        f"esbuild errors:\n{err_summary}\n\n"
                        f"Full file content:\n```\n{file_content}\n```\n\n"
                        "Fix the syntax error and return the corrected file."
                    )}],
                    system=ESBUILD_FIX_SYSTEM,
                    max_tokens=heal_max_tokens,
                )
                if fixed and fixed.strip() and fixed.strip() != file_content.strip():
                    fixed = _extract_code_from_llm_response(fixed)
                    reason = _looks_incomplete(fixed, file_content)
                    if reason:
                        print(f"[esbuild_check] Rejected fix for {rel_path} - looks incomplete ({reason}), keeping original", flush=True)
                        return False

                    # Verify the fix actually clears the parse error before
                    # accepting it — this is exactly the check that was
                    # missing when Forecast.tsx got silently corrupted: the
                    # old code wrote whatever came back with no check at all.
                    fp = project_dir / rel_path
                    original_on_disk = fp.read_text(encoding="utf-8") if fp.exists() else file_content
                    fp.write_text(fixed, encoding="utf-8")
                    loader = "tsx" if rel_path.endswith(".tsx") else "ts"
                    try:
                        verify = _sp.run(
                            [str(esbuild_bin), str(fp), f"--loader={loader}", f"--outfile={outfile}"],
                            capture_output=True, text=True, timeout=15, cwd=str(project_dir),
                        )
                        verify_ok = verify.returncode == 0
                    except Exception:
                        verify_ok = False

                    if verify_ok:
                        files[rel_path] = fixed
                        print(f"[esbuild_check] Fixed {rel_path}", flush=True)
                        return True
                    else:
                        fp.write_text(original_on_disk, encoding="utf-8")
                        print(f"[esbuild_check] Fix for {rel_path} still fails esbuild - keeping original", flush=True)
            except Exception as ex:
                print(f"[esbuild_check] LLM fix failed for {rel_path}: {ex}", flush=True)
            return False

        # Parallel, not sequential — each file's LLM repair call + esbuild
        # verification is fully independent of every other file's (capped at
        # 5 files/round already), so running them one at a time only added
        # wall-clock latency for no benefit.
        with _ThreadPoolExecutor(max_workers=min(len(errors_found), 5)) as _pool:
            any_fixed = any(_pool.map(_fix_one, errors_found.keys(), errors_found.values()))

        if not any_fixed:
            break

    return files


def _qa_heal(project_dir: Path, project_name: str, port: int,
             qa_report, files: dict, progress=None, max_rounds: int = 2):
    """
    Feed QA errors back to LLM for targeted fixes. Re-runs QA after each round.
    Returns (final_qa_report, fixed_files).
    """
    import re as _re

    QA_HEAL_SYSTEM = (
        "You are fixing runtime errors in a React/TypeScript page. "
        "The errors were detected by automated QA (browser console errors, missing imports, NaN values). "
        "Fix ONLY the specific errors listed. Do not rewrite unrelated code.\n\n"
        "OUTPUT FORMAT: Your response must be ONLY the complete .tsx file content starting with 'import'. "
        "Do NOT include any explanation, analysis, commentary, or prose. "
        "Do NOT start with 'Looking at', 'The issue is', 'Here is', 'I need to', or similar. "
        "The FIRST character of your response MUST be the letter 'i' in 'import'.\n\n"
        "CRITICAL RULES:\n"
        "- useApi syntax: useApi<any[]>('table_name') — pass ONLY the SQL table name\n"
        "- API returns SNAKE_CASE fields matching SQL: row.doc_type NOT row.docType\n"
        "- DO NOT import from '../components/...' unless it's ExportToolbar\n"
        "- D3 charts: useRef MUST be on a container <div> (NOT the <svg>). Container div MUST have minHeight.\n"
        "- D3 ResizeObserver: ALWAYS call measure()/render() immediately BEFORE ro.observe(). Never rely on RO alone.\n"
        "- NEVER use ref.current?.parentElement — ref the container div directly.\n"
        "- Null-guard all numeric values: Number(x) || 0\n"
    )

    for round_n in range(max_rounds):
        # Group errors by page file
        errors_by_page: dict[str, list[str]] = {}
        for finding in qa_report.findings:
            if finding.severity != "error":
                continue
            # Map route to page file
            route = finding.file  # e.g. "/timesheets" or "src/pages/Capacity.tsx"
            if route.startswith("/"):
                # Convert route like "/timesheets" to page file
                page_name = route.strip("/").replace("-", "").title()
                # Try to find matching page file
                for fpath in files:
                    if fpath.startswith("src/pages/") and fpath.endswith(".tsx"):
                        fname = fpath.replace("src/pages/", "").replace(".tsx", "")
                        if fname.lower() == page_name.lower() or fname.lower() == route.strip("/").lower():
                            page_name = fname
                            break
                page_file = f"src/pages/{page_name}.tsx"
            elif route.startswith("src/"):
                # Strip line number suffix from tsc output (e.g. "src/pages/Foo.tsx:42")
                page_file = route.split(":")[0]
            else:
                continue

            if page_file in files:
                errors_by_page.setdefault(page_file, []).append(
                    f"  [{finding.category}] {finding.message}"
                )

        if not errors_by_page:
            print(f"[qa_heal] No fixable page errors found — done", flush=True)
            break

        total_errors = sum(len(v) for v in errors_by_page.values())
        print(f"[qa_heal] Round {round_n+1}/{max_rounds}: {total_errors} errors in {len(errors_by_page)} pages", flush=True)
        if progress:
            progress(f"crew:QA auto-fix round {round_n+1} — fixing {total_errors} errors in {len(errors_by_page)} pages…")

        any_fixed = False
        for page_file, error_lines in errors_by_page.items():
            error_text = "\n".join(error_lines)
            current_code = files.get(page_file, "")
            if not current_code:
                continue

            # Read the schema for context
            schema = ""
            schema_path = project_dir / "api" / "schema.sql"
            if not schema_path.exists():
                schema_path = project_dir / "schema.sql"
            if schema_path.exists():
                try:
                    schema = schema_path.read_text(encoding="utf-8")[:3000]
                except Exception:
                    pass

            prompt = (
                f"Fix these runtime/build errors in {page_file}.\n\n"
                f"Errors found by QA:\n{error_text}\n\n"
                f"Database schema (use these exact table/column names):\n{schema}\n\n"
                f"Current file content:\n```tsx\n{current_code}\n```"
            )
            try:
                # Scale to file size, same as _tsc_heal above — a fixed 16000
                # ceiling is exactly what silently truncated a large
                # skill-template-derived page (e.g. the ~1400-line
                # Charts.skill.tsx) when this call asked for the "complete
                # file content" back: the response ran out of budget mid-
                # statement, and (before the check below existed) that
                # truncated output was accepted and written straight to disk.
                file_tokens_estimate = len(current_code) // 3
                heal_max_tokens = max(8000, min(64000, file_tokens_estimate + 2000))
                fixed = chat(
                    [{"role": "user", "content": prompt}],
                    system=QA_HEAL_SYSTEM,
                    max_tokens=heal_max_tokens,
                ).strip()
                fixed = _extract_code_from_llm_response(fixed)
                if fixed and fixed != files[page_file] and len(fixed) > 50:
                    reason = _looks_incomplete(fixed, files[page_file])
                    if reason:
                        print(f"[qa_heal] Rejected fix for {page_file} - looks incomplete ({reason}), keeping original", flush=True)
                    else:
                        files[page_file] = fixed
                        any_fixed = True
                        print(f"[qa_heal] Fixed {page_file}", flush=True)
            except Exception as ex:
                print(f"[qa_heal] LLM fix failed for {page_file}: {ex}", flush=True)

        if not any_fixed:
            print("[qa_heal] No files changed — stopping early", flush=True)
            break

        # Write fixed files (Vite HMR will pick them up)
        for rel_path, content in files.items():
            if not content or not content.strip():
                continue
            fp = project_dir / rel_path
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content, encoding="utf-8")

        # Give Vite a moment to recompile via HMR
        import time
        time.sleep(3)

        # Re-run QA
        if progress:
            progress(f"crew:Re-running QA after fix round {round_n+1}…")
        qa_report = run_qa(project_name, port, project_dir)

        if qa_report.passed:
            print(f"[qa_heal] QA passed after round {round_n+1}!", flush=True)
            if progress:
                progress(f"crew:QA passed after auto-fix! Score: {qa_report.score}/100")
            break
        else:
            remaining = sum(1 for f in qa_report.findings if f.severity == "error")
            print(f"[qa_heal] Still {remaining} errors after round {round_n+1}", flush=True)

    return qa_report, files


# ── Public API ─────────────────────────────────────────────────────────────────

def kill_server(project_name: str, forget_port: bool = False):
    """Stop both Vite and API server processes and wait for them to fully exit."""
    _stop_api_server(project_name)
    proc = _dev_servers.pop(project_name, None)
    if proc:
        try:
            proc.terminate()
            proc.wait(timeout=8)
        except Exception:
            try:
                proc.kill()
                proc.wait(timeout=5)
            except Exception:
                pass
    # Also kill any node processes still holding the port (Windows orphan processes).
    # Use "LISTENING" filter so we only kill the process bound to the port,
    # not uvicorn's ESTABLISHED proxy connections to Vite (which would kill the API server).
    port = _dev_ports.get(project_name)
    if port:
        try:
            import subprocess
            subprocess.run(
                f'for /f "tokens=5" %a in (\'netstat -ano ^| findstr "LISTENING" ^| findstr ":{port} "\') do taskkill /PID %a /F',
                shell=True, capture_output=True, timeout=5,
            )
        except Exception:
            pass
    if forget_port:
        _dev_ports.pop(project_name, None)
        _save_ports()


def _augment_prompt(prompt: str, backend_type: str = "python") -> str:
    """Append mandatory system constraints to every generation prompt."""
    if backend_type == "java":
        backend_desc = "a Java Spring Boot + JDBC + SQLite backend"
    else:
        backend_desc = "a SQLite database + Python FastAPI backend"

    notes = [
        "TECH STACK (MANDATORY — override any spec/TRD): "
        "This platform generates React 18 + TypeScript + Tailwind CSS + Vite frontend apps "
        f"with {backend_desc}. "
        "If the instructions/specs mention other technologies (PostgreSQL, Redis, Express, "
        "Node.js backend, MongoDB, AWS services, Docker, Kubernetes, etc.), IGNORE those "
        "technology choices and use the TurboUIGen stack instead. "
        "Extract the BUSINESS LOGIC, DATA MODELS, UI REQUIREMENTS, and USER FLOWS from "
        "the specs — but implement them using our stack. "
        "Do NOT generate backend code, Docker files, CI/CD pipelines, or infrastructure.",
        "DATA ARCHITECTURE (MANDATORY): ALL app data MUST live in a SQLite database. "
        "A schema.sql, seed.sql, and API server are ALWAYS created. "
        "The frontend NEVER contains hardcoded data — it fetches everything via REST API "
        "(useApi hook → GET /api/data/{tableName}). This applies to EVERY app regardless "
        "of what the user prompt says.",
        "CHART REMINDER: Use D3.js (useEffect + useRef + SVG) for any charts built from scratch. "
        "Do NOT use Highcharts — it breaks in Vite ESM mode. "
        "D3 pattern: useRef on container DIV (not SVG), container has minHeight, "
        "call render() immediately then pass render to ResizeObserver. Never use parentElement.",
        "MAP DATA — static imports only (dynamic import/fetch = blank maps): "
        "CORRECT: import usaTopo from 'us-atlas/states-10m.json' "
        "FORBIDDEN: fetch() or d3.json() for TopoJSON.",
    ]
    return prompt + "\n\n[SYSTEM NOTES — follow these exactly]\n" + "\n".join(notes)


def _introspect_live_schema(existing_dir: Path) -> str | None:
    """
    Reconstruct a schema.sql-equivalent by reading the REAL, live SQLite
    database's actual table/column structure (via PRAGMA table_info), instead
    of trusting schema.sql's text — see the call site for why that text can
    drift out of sync with what the API actually returns. Fully generic: the
    output is derived entirely from whatever tables/columns genuinely exist in
    this specific project's database, nothing here is specific to any table,
    column, or app. Checked in the same conventional locations both backend
    templates default to (api/data.db for Python, backend/data.db for Java);
    returns None (caller falls back to the schema.sql file) if no database
    exists yet — e.g. a refinement requested before the app has ever run.
    """
    import sqlite3
    # Same fixed-filename mistake _build_mcp_metadata_file used to make —
    # the LLM names this file per-app (pmo_command_center.db, store_ops.db,
    # ...), not "data.db". Reuse the same real detection api_runner already
    # has instead of guessing a literal name a second time.
    is_java_backend = (existing_dir / "backend" / "pom.xml").exists()
    backend_subdir = "backend" if is_java_backend else "api"
    try:
        from api_agents.api_runner import _find_app_db_file
        db_path = _find_app_db_file(existing_dir / backend_subdir, "java" if is_java_backend else "python")
    except ImportError:
        db_path = None
    if db_path is None:
        return None

    try:
        conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
        try:
            cur = conn.cursor()
            tables = [r[0] for r in cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()]
            statements = []
            for table in tables:
                cols = cur.execute(f'PRAGMA table_info("{table}")').fetchall()
                # PRAGMA table_info columns: (cid, name, type, notnull, dflt_value, pk)
                col_defs = ", ".join(f"{c[1]} {c[2] or 'TEXT'}" for c in cols)
                if col_defs:
                    statements.append(f"CREATE TABLE IF NOT EXISTS {table} ({col_defs});")
            return "\n".join(statements) if statements else None
        finally:
            conn.close()
    except Exception:
        return None


def generate_project(prompt: str, progress=None, project_name_override: str | None = None,
                     architecture: dict | None = None,
                     reference_images: list[dict] | None = None,
                     backend_type: str = "python") -> dict:
    """
    Generate a React/TS/Tailwind project from a prompt.
    progress(step: str) is called at each stage for CLI/UI feedback.
    architecture: pre-approved architecture from /api/draft (skips Stage 1 if provided).
    reference_images: list of Figma screenshots [{name, base64_data}] for visual fidelity.
    backend_type: "python" (FastAPI + SQLite) or "java" (Spring Boot + JDBC/SQLite).
    Returns project info dict.
    """
    if not os.environ.get("LITELLM_API_BASE") and not os.environ.get("LITELLM_API_KEY"):
        raise RuntimeError("LiteLLM credentials not configured in .env (LITELLM_API_BASE, LITELLM_API_KEY)")

    def _p(s):
        if progress:
            progress(s)

    _p("llm")

    # ── Detect refinement: if project already exists, read existing state ──────
    existing_schema = ""
    existing_seed = ""
    existing_files: dict[str, str] = {}
    _existing_dir = None
    if project_name_override:
        _existing_dir = GENERATED_DIR / re.sub(r"[^a-z0-9-]", "-", project_name_override.lower()).strip("-")
        if _existing_dir.exists():
            # Prefer the REAL, live database's actual structure over schema.sql's
            # text. Once any table exists, both backends run schema.sql through
            # "CREATE TABLE IF NOT EXISTS" on every startup (_init_db for Python,
            # DatabaseInitializer for Java) — which silently no-ops for tables that
            # already exist. So a later schema.sql edit that renames or re-cases a
            # column NEVER actually reaches the live database: the table keeps its
            # original structure regardless of what schema.sql now claims, and the
            # REST API keeps reflecting that original structure. Introspecting the
            # actual .db file is the only way to see what the API will really
            # return — confirmed live: a project's schema.sql had drifted to
            # camelCase columns while the live database (and thus the API) still
            # used the original snake_case ones, and every page generated against
            # the (stale) schema.sql text crashed reading fields that don't exist
            # in the real API response.
            existing_schema = _introspect_live_schema(_existing_dir) or ""

            # Schema/seed FILE fallback — used for the seed preview always (seed
            # VALUES drifting isn't this bug; the file is a fine approximation for
            # prompt context), and for schema only when no live .db exists yet
            # (e.g. a refinement immediately after generation, before the app has
            # ever been started to create the database).
            _schema_f = _existing_dir / "api" / "schema.sql"
            _seed_f = _existing_dir / "api" / "seed.sql"
            if not _schema_f.exists():
                for _candidate_dir in ("backend", ""):
                    _candidate = _existing_dir / _candidate_dir / "schema.sql" if _candidate_dir else _existing_dir / "schema.sql"
                    if _candidate.exists():
                        _schema_f = _candidate
                        _seed_f = _candidate.parent / "seed.sql"
                        break
            if not existing_schema and _schema_f.exists():
                existing_schema = _schema_f.read_text(encoding="utf-8")
            if _seed_f.exists():
                existing_seed = _seed_f.read_text(encoding="utf-8")

            # Read all existing source files for selective regeneration
            for fp in _existing_dir.rglob("*"):
                if fp.is_file() and fp.suffix in (".tsx", ".ts", ".css", ".sql", ".py", ".html", ".json", ".js", ".txt", ".java", ".properties", ".xml"):
                    rel = fp.relative_to(_existing_dir).as_posix()
                    if rel.startswith("node_modules/") or rel.startswith("."):
                        continue
                    try:
                        existing_files[rel] = fp.read_text(encoding="utf-8")
                    except Exception:
                        pass
            if existing_files:
                _p(f"crew:Detected existing project ({len(existing_files)} files) — selective regeneration mode")

    from agents.orchestrator import CrewOrchestrator
    _p("crew:Initializing multi-agent pipeline…")
    orchestrator = CrewOrchestrator(progress=_p)
    orchestrator.backend_type = backend_type
    if existing_schema:
        orchestrator.existing_context = {
            "schema": existing_schema,
            "seed_preview": existing_seed[:5000],
        }
    if existing_files:
        orchestrator.existing_files = existing_files
        # Lets the orchestrator flush additively after each stage instead of
        # only at the very end — see CrewOrchestrator._flush_stage. Safe to
        # set unconditionally here: _existing_dir is only non-None when
        # existing_files was actually populated from it, a few lines above.
        orchestrator.project_dir = _existing_dir
    if architecture:
        orchestrator.approved_architecture = architecture
    if reference_images:
        orchestrator.reference_images = reference_images
    data = orchestrator.generate(_augment_prompt(prompt, backend_type=backend_type))

    if project_name_override:
        project_name = re.sub(r"[^a-z0-9-]", "-", project_name_override.lower()).strip("-") or "app"
    else:
        project_name = re.sub(r"[^a-z0-9-]", "-", data.get("projectName", "app").lower()).strip("-") or "app"
    files = data.get("files", {})
    if not files:
        raise RuntimeError("LLM returned no files")

    # Assign or reuse port — also persist to registry so it survives restarts
    with _ports_lock:
        port = _dev_ports.get(project_name) or _next_port()
        _dev_ports[project_name] = port
        _save_ports()
    registry_upsert(project_name, port=port, type="react")

    project_dir = GENERATED_DIR / project_name

    # ── Ensure essential boilerplate (safety net for partial/refinement builds) ──
    files = _ensure_boilerplate(files, project_name)
    # ── ALL apps use SQLite + API — ensure schema.sql always exists ─────────
    files = _ensure_schema_sql(files, force=True)
    # ── Bundle API server + useApi hook (always — every app has an API) ────
    files = _bundle_api_server(files, backend_type=backend_type)

    # Assign API port if this project has an API server
    has_api_files = (
        "api/app_server.py" in files or "app_server.py" in files
        or "api_server.py" in files
        or "api/schema.sql" in files or "schema.sql" in files
        or "backend/.backend_type" in files
        # New pipeline, Java backend (CrewOrchestrator._run_backend_generation
        # with backend_type="java") — no .backend_type marker, that's an
        # old-pipeline-only sentinel; backend/schema.sql (aliased there
        # deterministically) or backend/pom.xml existing at all is the real
        # signal that a real Spring Boot backend was actually generated.
        or "backend/schema.sql" in files or "backend/pom.xml" in files
    )
    with _ports_lock:
        api_port = _api_ports.get(project_name)
        if has_api_files and not api_port:
            api_port = _next_api_port()
            _api_ports[project_name] = api_port
            _save_ports()

        # Detect dual-server case: Java backend + DataChat Python coexist → allocate separate DataChat port
        datachat_port = _datachat_ports.get(project_name, 0)
        has_java_backend = "backend/.backend_type" in files or "backend/pom.xml" in files
        has_datachat = "api/app_server.py" in files
        if has_java_backend and has_datachat and not datachat_port:
            assigned = set(_api_ports.values()) | set(_datachat_ports.values()) | {api_port or 0}
            dc_port = (api_port or API_PORT_START) + 1
            while dc_port in assigned or not _port_is_free(dc_port):
                dc_port += 1
            datachat_port = dc_port
            _datachat_ports[project_name] = datachat_port
            _save_ports()

        # Same dual-server need for the new named-route pipeline: its real API
        # (api/src/main.py) has no native /api/chat the way app_server_template.py
        # does, so an AI-chat app gets the same sidecar bundled under datachat/
        # (see CrewOrchestrator._run_backend_generation) and needs its own port
        # too — unlike the Java case above, this doesn't require a separate
        # "main backend" check, since datachat/app_server.py is only ever
        # bundled when the sidecar is actually needed.
        has_new_pipeline_datachat = "datachat/app_server.py" in files
        if has_new_pipeline_datachat and not datachat_port:
            assigned = set(_api_ports.values()) | set(_datachat_ports.values()) | {api_port or 0}
            dc_port = (api_port or API_PORT_START) + 1
            while dc_port in assigned or not _port_is_free(dc_port):
                dc_port += 1
            datachat_port = dc_port
            _datachat_ports[project_name] = datachat_port
            _save_ports()

    # Patch .env with the correct dynamic API port — skipped for the new
    # named-route pipeline's OWN api/.env (that file belongs to the real
    # API, not a chat sidecar; its actual bind port comes from uvicorn's
    # --port flag in _start_api_server, not this file, so patching it here
    # with a datachat port would just be actively wrong, not just unused).
    if api_port and "api/.env" in files and "api/.architecture.json" not in files:
        import re as _re_env
        target_api_env_port = datachat_port if datachat_port else api_port
        files["api/.env"] = _re_env.sub(r"API_PORT=\d+", f"API_PORT={target_api_env_port}", files["api/.env"])
        # When DataChat runs alongside a separate data backend, set DATA_API_BASE so it can
        # call the REST API via tool calls (MCP-style data access)
        data_api_url = f"http://localhost:{api_port}"
        if "DATA_API_BASE=" in files["api/.env"]:
            files["api/.env"] = _re_env.sub(r"DATA_API_BASE=.*", f"DATA_API_BASE={data_api_url}", files["api/.env"])
        else:
            files["api/.env"] += f"\n# Data REST API (main backend)\nDATA_API_BASE={data_api_url}\n"
    # New pipeline's own sidecar env — datachat/.env, not api/.env (see above).
    if datachat_port and api_port and "datachat/.env" in files:
        import re as _re_env
        files["datachat/.env"] = _re_env.sub(r"API_PORT=\d+", f"API_PORT={datachat_port}", files["datachat/.env"])
        data_api_url = f"http://localhost:{api_port}"
        if "DATA_API_BASE=" in files["datachat/.env"]:
            files["datachat/.env"] = _re_env.sub(r"DATA_API_BASE=.*", f"DATA_API_BASE={data_api_url}", files["datachat/.env"])
        else:
            files["datachat/.env"] += f"\n# Data REST API (main backend)\nDATA_API_BASE={data_api_url}\n"
    # For Java backend, patch application.properties and backend/.env with the port
    if api_port and "backend/src/main/resources/application.properties" in files:
        import re as _re_env
        files["backend/src/main/resources/application.properties"] = _re_env.sub(
            r"server\.port=\$\{PORT:\d+\}", f"server.port=${{PORT:{api_port}}}",
            files["backend/src/main/resources/application.properties"]
        )
    if api_port and "backend/.env" in files:
        import re as _re_env
        files["backend/.env"] = _re_env.sub(r"PORT=\d+", f"PORT={api_port}", files["backend/.env"])

    # Wire the design system alias and run all post-processors
    # Pass project_name + port + api_port so _inject_api_proxy builds the full server block
    # (port, host, proxy with base-path rewrite) — no separate port injection needed.
    files = run_all_postprocessors(files, project_dir=project_dir, project_name=project_name, port=port, api_port=api_port or 0, datachat_port=datachat_port)
    files = _ensure_required_components(files)

    # Ensure port is set even for non-API projects (where _inject_api_proxy is a no-op)
    vite = files.get("vite.config.ts", "")
    if vite and f"port: {port}" not in vite:
        vite = vite.replace(
            "defineConfig({\n",
            f"defineConfig({{\n  server: {{ port: {port}, host: '0.0.0.0' }},\n",
        )
        if f"port: {port}" not in vite:
            vite = vite.replace(
                "defineConfig({",
                f"defineConfig({{ server: {{ port: {port}, host: '0.0.0.0' }},",
            )
        files["vite.config.ts"] = vite

    _p("write")
    kill_server(project_name)
    _write_files(project_dir, files)

    _p("install")
    # Ensure shared node_modules exist, then junction the project to them
    ok, log = _ensure_shared_nm_once()
    if not ok:
        raise RuntimeError(f"Shared npm install failed:\n{log[-2000:]}")
    project_deps = _get_project_deps(project_dir)
    # Scan actual source imports — catches packages the LLM uses but didn't add to package.json
    scanned_imports = _scan_imports_from_files(project_dir)
    for pkg in scanned_imports:
        if pkg not in project_deps:
            project_deps[pkg] = "latest"
    ok2, log2 = _link_shared_nm(project_dir, project_deps, progress=_p)
    if not ok2:
        # Fall back to per-project install if junction fails
        ok3, log3 = _npm_install(project_dir)
        if not ok3:
            raise RuntimeError(f"npm install failed:\n{log3[-2000:]}")
    _link_ds_into_project(project_dir)

    # Verify all imported modules exist in node_modules — install any missing ones NOW
    nm_dir = project_dir / "node_modules"
    if nm_dir.exists():
        _final_imports = _scan_imports_from_files(project_dir)
        _missing_final = []
        for pkg in _final_imports:
            parts = pkg.split("/")
            pkg_path = nm_dir.joinpath(*parts) if pkg.startswith("@") else nm_dir / pkg
            if not pkg_path.exists():
                _missing_final.append(pkg)
        if _missing_final:
            _p(f"install:Installing missing modules: {', '.join(_missing_final)}")
            print(f"[generate] Missing modules detected after link: {_missing_final}", flush=True)
            env = os.environ.copy()
            env["PATH"] = NODE_PATH + os.pathsep + env.get("PATH", "")
            node_exe = Path(NODE_PATH) / "node.exe"
            npm_js = Path(NODE_PATH) / "node_modules" / "npm" / "bin" / "npm-cli.js"
            subprocess.run(
                [str(node_exe), str(npm_js), "install"] + _missing_final,
                cwd=str(SHARED_NM_DIR), env=env, capture_output=True, text=True, timeout=120,
            )
            print(f"[generate] Installed missing modules: {_missing_final}", flush=True)

    # Run tsc self-heal AFTER node_modules is present so tsc resolves types
    files = _tsc_heal(project_dir, files, progress=_p)
    # Re-write any files that were healed
    _write_files(project_dir, files)

    _p("start")
    # Start API server first (if app_server.py or Spring Boot backend exists), then Vite
    has_api = (
        (project_dir / "api" / "app_server.py").exists()
        or (project_dir / "app_server.py").exists()
        or (project_dir / "api" / "schema.sql").exists()
        or (project_dir / "backend" / ".backend_type").exists()
        # New pipeline, Java backend — see has_api_files's matching comment above.
        or (project_dir / "backend" / "schema.sql").exists()
        or (project_dir / "backend" / "pom.xml").exists()
    )
    api_port = _api_ports.get(project_name)
    if has_api:
        if not api_port:
            with _ports_lock:
                api_port = _api_ports.get(project_name) or _next_api_port()
                _api_ports[project_name] = api_port
                _save_ports()
        api_proc = _start_api_server(project_dir, api_port=api_port)
    else:
        api_proc = None
    if api_proc:
        _api_servers[project_name] = api_proc
        # 90s was reproduced directly as too tight for a fresh Java project:
        # Maven's own dependency resolution + compile (before the JVM even
        # starts) plus Spring Boot/Hibernate startup took ~101s on a real
        # generation, so this gate gave up 11s before the app actually
        # responded — silently skipping BOTH seeding and MCP metadata with
        # no error anywhere (this exact function's own timeout warning
        # print()s to the console/server.log only, never to the Build Log),
        # which is why "no data in the tables" showed no error at all. The
        # app was never actually broken — QA's own, separate readiness wait
        # ran later and found it up fine, which is what made this so
        # confusing: everything else about the app worked.
        api_timeout = 180 if backend_type == "java" else 15
        if _wait_for_api(api_port, timeout=api_timeout):
            _seed_new_pipeline_backend(project_dir, backend_type, api_port=api_port, _p=_p)
            _build_mcp_metadata_file(project_dir, backend_type, _p)
        elif _p:
            _p(f"crew:WARNING — API server on port {api_port} did not respond within {api_timeout}s "
               f"— skipping seeding and MCP metadata for now. If the app comes up shortly after "
               f"(check Docker/Start), restart it once to trigger both.")
    proc = _start_vite(project_dir, port)
    _dev_servers[project_name] = proc

    if not wait_for_port(port, timeout=60):
        raise RuntimeError("Vite dev server did not start in time")

    # Wait for Vite dependency pre-bundling to complete before QA.
    # Vite writes _metadata.json once all deps are optimized — without this,
    # lazy-loaded pages fail with "Failed to fetch dynamically imported module".
    _deps_dir = project_dir / "node_modules" / ".vite" / "deps"
    _prebundle_deadline = time.time() + 30
    while time.time() < _prebundle_deadline:
        if (_deps_dir / "_metadata.json").exists():
            print("[generate] Vite dep pre-bundling complete", flush=True)
            break
        time.sleep(1)
    else:
        print("[generate] WARNING: Vite _metadata.json not found after 30s — proceeding anyway", flush=True)

    _p("qa")
    qa_report = run_qa(project_name, port, project_dir)

    # ── QA-Heal loop: if QA found fixable errors, feed them to LLM and retry ──
    if not qa_report.passed and qa_report.pages_fail:
        _p("crew:QA found errors — attempting auto-fix…")
        qa_report, files = _qa_heal(
            project_dir, project_name, port, qa_report, files, progress=_p
        )
        # _qa_heal's own fixes are full-file LLM rewrites, not guaranteed
        # internally consistent — reproduced directly: a rewrite renamed a
        # ResizeObserver callback's outer variable (chasing _qa_heal's own
        # system-prompt rule against `ref.current?.parentElement`) but left
        # a stale reference to the old name two lines later, a real
        # `Cannot find name` TypeScript error. _tsc_heal only ever runs
        # once, BEFORE this point (before the app even boots) — nothing
        # re-checks TypeScript correctness after _qa_heal's own rewrites,
        # so that regression shipped straight to the browser as a runtime
        # crash with zero build-time signal. Re-run the same self-heal pass
        # against whatever _qa_heal just changed.
        files = _tsc_heal(project_dir, files, progress=_p)
        _write_files(project_dir, files)

    # One last check, right before this returns: tsc_heal/qa_heal above can
    # each rewrite App.tsx while fixing something unrelated, shown only
    # App.tsx and its own error — exactly how App.tsx got corrupted earlier
    # this session (a tsc_heal repair dropped two routes it never saw as
    # its job to keep). Re-run the same route reconciliation
    # orchestrator.py's own Stage 6 already does, against whatever tsc_heal/
    # qa_heal just left behind, so a page that survived generation but lost
    # its route to a later repair pass doesn't ship silently broken.
    _app_tsx_path = "src/App.tsx"
    if _app_tsx_path in files:
        from agents.orchestrator import CrewOrchestrator
        _actual_pages = sorted({
            fpath[len("src/pages/"):-len(".tsx")]
            for fpath in files
            if fpath.startswith("src/pages/") and fpath.endswith(".tsx")
        })
        _fixed_app_tsx = CrewOrchestrator._reconcile_app_routes(files[_app_tsx_path], _actual_pages)
        if _fixed_app_tsx != files[_app_tsx_path]:
            files[_app_tsx_path] = _fixed_app_tsx
            _write_files(project_dir, files)

    _p("ready")
    return {
        "projectName":   project_name,
        "title":         data.get("title", project_name),
        "description":   data.get("description", ""),
        "port":          port,
        "url":           "/app/" + project_name + "/",
        "files":         list(files.keys()),
        "qa":            qa_report.to_dict(),
        "schemaChanges": data.get("schemaChanges", ""),
    }


def start_project(project_name: str) -> dict:
    project_dir = GENERATED_DIR / project_name
    if not project_dir.exists():
        raise RuntimeError(f"Project '{project_name}' not found")

    # Computed up front (cheap file-existence checks only) so both the
    # "vite already tracked/healthy" early-return branches below can also
    # verify the API server independently before short-circuiting.
    has_api = (
        (project_dir / "api" / "app_server.py").exists()
        or (project_dir / "app_server.py").exists()
        or (project_dir / "api_server.py").exists()
        or (project_dir / "api" / "schema.sql").exists()
        or (project_dir / "schema.sql").exists()
        or (project_dir / "backend" / ".backend_type").exists()
        or (project_dir / "backend" / "pom.xml").exists()
        or (project_dir / "backend" / "schema.sql").exists()
    )

    def _restart_dead_api_if_needed():
        """
        Vite being tracked as alive says nothing about the backend API
        process — reproduced directly: a project's Java process died
        independently (crashed, or was killed outside this module's own
        tracking) while Vite kept running, and the next Start click
        short-circuited on "vite already tracked as running" without ever
        checking the API, leaving every page on that project silently
        unable to reach it — clicking Start looked like it succeeded
        (same response shape either way) but changed nothing. Only starts
        a new API process when the project's own assigned port isn't
        actually listening — cheap and a no-op if the API is already fine.

        Dispatches to _start_java_api_server directly for a new-pipeline
        Java project (backend/pom.xml present) instead of the generic
        _start_api_server — that function's OWN Java branch is gated on the
        legacy backend/.backend_type marker file, which new-pipeline
        projects never write (they use backend/pom.xml directly), so for
        one of these it silently fell through toward _start_api_server's
        Python-oriented fallback logic, found none of app_server.py/
        schema.sql in the locations it checks (a Java project's schema.sql
        lives at backend/schema.sql, not api/schema.sql or the project
        root), and returned None — a dead new-pipeline Java API's restart
        was a complete, silent no-op.
        """
        if not has_api:
            return
        is_java = (project_dir / "backend" / "pom.xml").exists()
        api_port = _api_ports.get(project_name)
        if api_port and not _port_is_free(api_port):
            return  # something's already listening — assume it's healthy
        if not api_port:
            with _ports_lock:
                api_port = _api_ports.get(project_name) or _next_api_port()
                _api_ports[project_name] = api_port
                _save_ports()
        api_proc = (
            _start_java_api_server(project_dir, api_port=api_port) if is_java
            else _start_api_server(project_dir, api_port=api_port)
        )
        if api_proc:
            _api_servers[project_name] = api_proc
            if _wait_for_api(api_port, timeout=180 if is_java else 15):
                backend_kind = "java" if is_java else "python"
                _seed_new_pipeline_backend(project_dir, backend_kind, api_port=api_port)
                _build_mcp_metadata_file(project_dir, backend_kind)

    def _restart_dead_datachat_if_needed():
        """
        The DataChat sidecar is a SEPARATE process from the main API, and
        its death is invisible to _restart_dead_api_if_needed above — that
        function only ever calls _start_datachat_server as a side effect of
        restarting a DEAD main API, so if the main API stays alive (the
        common case: it's a more stable, longer-running process) while
        DataChat dies independently, nothing ever notices or relaunches it.
        Reproduced directly: the AI Strategist page reported "AI backend
        not running" after a restart even though every other page's data
        kept working fine, because the main Java API never actually needed
        restarting at all — only DataChat had died, and no code path checks
        it on its own. Checks both locations a DataChat sidecar can live in
        (datachat/ for the new named-route pipeline, api/ for the legacy
        pipeline's Java-co-located case — see _start_api_server's own
        embedded datachat logic for that second case, which has the exact
        same "only checked as a side effect of the main API restarting" gap
        this closes independently of it).

        The "api" location is only ever a DataChat sidecar when the MAIN
        backend is Java (Spring Boot/Maven, never a Python app_server.py at
        all) — for a Python backend, api/app_server.py IS the main API
        itself, not a sidecar, so checking it here for a Python project
        would misidentify the main API as a dead DataChat process and spawn
        a redundant second copy of it on a different port.
        """
        is_java_backend = (project_dir / "backend" / "pom.xml").exists()
        candidate_subdirs = ("datachat", "api") if is_java_backend else ("datachat",)
        for subdir in candidate_subdirs:
            datachat_server = project_dir / subdir / "app_server.py"
            if not datachat_server.exists():
                continue
            dc_port = _datachat_ports.get(project_name)
            if dc_port and not _port_is_free(dc_port):
                return  # already listening — assume it's healthy
            if not dc_port:
                with _ports_lock:
                    assigned = set(_api_ports.values()) | set(_datachat_ports.values())
                    dc_port = max(assigned, default=8211) + 1
                    while dc_port in assigned or not _port_is_free(dc_port):
                        dc_port += 1
                    _datachat_ports[project_name] = dc_port
                    _save_ports()
            dc_proc = _start_datachat_server(
                project_dir, dc_port, data_api_port=_api_ports.get(project_name, 0), subdir=subdir
            )
            if dc_proc:
                _api_servers[f"{project_name}:datachat"] = dc_proc
            return

    if project_name in _dev_servers:
        port = _dev_ports[project_name]
        _restart_dead_api_if_needed()
        _restart_dead_datachat_if_needed()
        return {"projectName": project_name, "port": port, "url": "/app/" + project_name + "/"}
    # Check if a detached server from a previous session is still alive on the saved port
    port = _dev_ports.get(project_name)
    if port and _health_check(port, "react", project_name):
        _restart_dead_api_if_needed()
        _restart_dead_datachat_if_needed()
        return {"projectName": project_name, "port": port, "url": "/app/" + project_name + "/"}
    port = _dev_ports.get(project_name)
    if not port:
        with _ports_lock:
            port = _dev_ports.get(project_name) or _next_port()
            _dev_ports[project_name] = port
            _save_ports()
    # Rewrite vite config with clean DS alias + proxy server/base/port block
    vite_cfg = project_dir / "vite.config.ts"
    base = "/app/" + project_name + "/"
    patched = _patch_vite_for_ds({})["vite.config.ts"]
    # Inject base + server block before the closing })
    # Add /api proxy if project has a Python API server (or schema.sql that will trigger auto-bundle)
    proxy_section = ""
    # Assign or reuse API port for this project
    api_port = _api_ports.get(project_name)
    if has_api and not api_port:
        with _ports_lock:
            api_port = _api_ports.get(project_name) or _next_api_port()
            _api_ports[project_name] = api_port
            _save_ports()

    if has_api and api_port:
        # Check if DataChat runs on a separate port (Java backend + Python DataChat coexist)
        dc_port = _datachat_ports.get(project_name)
        datachat_lines = ""
        if dc_port:
            datachat_lines = (
                f"      '/api/chat': {{ target: 'http://localhost:{dc_port}', changeOrigin: true }},\n"
                f"      '/api/ingest': {{ target: 'http://localhost:{dc_port}', changeOrigin: true }},\n"
                f"      '/app/{project_name}/api/chat': {{ target: 'http://localhost:{dc_port}', changeOrigin: true, rewrite: (path) => path.replace(/^\\/app\\/{project_name}/, '') }},\n"
                f"      '/app/{project_name}/api/ingest': {{ target: 'http://localhost:{dc_port}', changeOrigin: true, rewrite: (path) => path.replace(/^\\/app\\/{project_name}/, '') }},\n"
            )
        proxy_section = (
            "    proxy: {\n"
            + datachat_lines +
            f"      '/api': {{ target: 'http://localhost:{api_port}', changeOrigin: true }},\n"
            f"      '/app/{project_name}/api': {{ target: 'http://localhost:{api_port}', changeOrigin: true, rewrite: (path) => path.replace(/^\\/app\\/{project_name}/, '') }},\n"
            "    },\n"
        )

    server_block = (
        "  base: '" + base + "',\n"
        "  server: {\n"
        "    port: " + str(port) + ",\n"
        "    host: '0.0.0.0',\n"
        "    hmr: false,\n"
        "    allowedHosts: ['localhost'],\n"
        "    warmup: { clientFiles: ['./src/App.tsx', './src/pages/*.tsx'] },\n"
        + proxy_section +
        "    fs: { allow: ['..', '" + _DS_CLEAN_JUNCTION + "', '" + _SHARED_NM_JUNCTION + "'] },\n"
        "  },\n"
    )
    # Add trailing-slash redirect plugin so /app/project-name works without trailing /
    base_no_slash = base.rstrip("/")
    trailing_slash_plugin = (
        f"function trailingSlash() {{\n"
        f"  return {{\n"
        f"    name: 'trailing-slash',\n"
        f"    configureServer(server) {{\n"
        f"      server.middlewares.use((req, res, next) => {{\n"
        f"        if (req.url === '{base_no_slash}') {{\n"
        f"          res.writeHead(301, {{ Location: '{base}' }});\n"
        f"          res.end();\n"
        f"          return;\n"
        f"        }}\n"
        f"        next();\n"
        f"      }});\n"
        f"    }},\n"
        f"  }};\n"
        f"}}\n"
    )
    patched = patched.replace(
        "import { defineConfig } from 'vite'\nimport react from '@vitejs/plugin-react'\n",
        "import { defineConfig } from 'vite'\nimport react from '@vitejs/plugin-react'\n" + trailing_slash_plugin
    )
    patched = patched.replace("plugins: [react()]", "plugins: [react(), trailingSlash()]")
    patched = patched.replace("})\n", server_block + "})\n", 1)
    vite_cfg.write_text(patched, encoding="utf-8")
    # Ensure shared node_modules exist (installs any missing packages like xlsx, jspdf)
    _ensure_shared_nm_once()
    # Ensure node_modules are linked (junction to shared, or fall back to real install)
    nm = project_dir / "node_modules"
    if not nm.exists():
        ok_s = True
        deps = _get_project_deps(project_dir)
        for pkg in _scan_imports_from_files(project_dir):
            if pkg not in deps:
                deps[pkg] = "latest"
        _link_shared_nm(project_dir, deps)
    _link_ds_into_project(project_dir)
    # Start API server if app_server.py exists
    if has_api:
        if not api_port:
            with _ports_lock:
                api_port = _api_ports.get(project_name) or _next_api_port()
                _api_ports[project_name] = api_port
                _save_ports()
        # Patch .env on disk so it matches the assigned port
        import re as _re_env
        env_file = project_dir / "api" / ".env"
        if env_file.exists():
            env_text = env_file.read_text(encoding="utf-8")
            patched_env = _re_env.sub(r"API_PORT=\d+", f"API_PORT={api_port}", env_text)
            if patched_env != env_text:
                env_file.write_text(patched_env, encoding="utf-8")
        # Java backend: patch PORT in backend/.env and server.port in application.properties
        backend_env = project_dir / "backend" / ".env"
        if backend_env.exists():
            env_text = backend_env.read_text(encoding="utf-8")
            patched_env = _re_env.sub(r"PORT=\d+", f"PORT={api_port}", env_text)
            if patched_env != env_text:
                backend_env.write_text(patched_env, encoding="utf-8")
        app_props = project_dir / "backend" / "src" / "main" / "resources" / "application.properties"
        if app_props.exists():
            props_text = app_props.read_text(encoding="utf-8")
            patched_props = _re_env.sub(r"server\.port=\d+", f"server.port={api_port}", props_text)
            if patched_props != props_text:
                app_props.write_text(patched_props, encoding="utf-8")
        api_proc = _start_api_server(project_dir, api_port=api_port)
        if api_proc:
            _api_servers[project_name] = api_proc
            is_java = (project_dir / "backend" / "pom.xml").exists()
            if _wait_for_api(api_port, timeout=180 if is_java else 15):
                backend_kind = "java" if is_java else "python"
                _seed_new_pipeline_backend(project_dir, backend_kind, api_port=api_port)
                _build_mcp_metadata_file(project_dir, backend_kind)
    proc = _start_vite(project_dir, port)
    _dev_servers[project_name] = proc
    wait_for_port(port, timeout=60)
    reg = _load_registry().get(project_name, {})
    return {"projectName": project_name, "port": port, "apiPort": api_port, "url": "/app/" + project_name + "/",
            "title": reg.get("title", project_name), "architecture": reg.get("architecture", {})}


def stop_project(project_name: str):
    kill_server(project_name, forget_port=False)


def delete_project(project_name: str, progress=None):
    """
    progress(step: str), if given, is called at each stage — same pattern as
    generate_project()'s progress callback. This can genuinely take up to
    ~90s (subprocess calls, multiple retries, sleeps for OneDrive/Vite lock
    release), and without any visible progress it silently looks identical to
    "instant" from the caller's side, which is what made it possible to fire a
    second request (e.g. a new generation for the same name) before the
    delete had actually finished.
    """
    def _p(s: str):
        if progress:
            progress(s)

    _p("Stopping dev server...")
    kill_server(project_name, forget_port=True)
    # Wait for file handles to release (Vite watchers, OneDrive sync)
    _p("Waiting for file handles to release...")
    time.sleep(2)
    project_dir = GENERATED_DIR / project_name
    if not project_dir.exists():
        _p("Project directory already gone — nothing to delete.")
        return
    import subprocess as _sp

    # Remove .vite cache (Vite holds locks on these)
    vite_cache = project_dir / ".vite"
    if vite_cache.exists():
        _p("Clearing Vite cache...")
        shutil.rmtree(vite_cache, ignore_errors=True)

    # Remove node_modules — if it's a junction to shared-node-modules, just unlink it
    node_modules = project_dir / "node_modules"
    if node_modules.exists():
        _p("Removing node_modules (this can take a while)...")
        try:
            result = _sp.run(
                ["cmd", "/c", "fsutil", "reparsepoint", "query", str(node_modules)],
                capture_output=True, timeout=5,
            )
            if result.returncode == 0:
                _sp.run(["cmd", "/c", "rmdir", str(node_modules)], capture_output=True, timeout=10)
            else:
                _sp.run(
                    ["cmd", "/c", "rd", "/s", "/q", str(node_modules)],
                    capture_output=True, timeout=30,
                )
        except Exception:
            shutil.rmtree(node_modules, ignore_errors=True)
        time.sleep(0.5)

    # Retry deletion up to 3 times — OneDrive and Windows can hold file locks briefly
    for attempt in range(3):
        _p(f"Removing project files (attempt {attempt + 1}/3)...")
        shutil.rmtree(project_dir, ignore_errors=True)
        if not project_dir.exists():
            break
        # Fallback: force with rd /s /q
        try:
            _sp.run(
                ["cmd", "/c", "rd", "/s", "/q", str(project_dir)],
                capture_output=True, timeout=30,
            )
        except Exception:
            pass
        if not project_dir.exists():
            break
        # Wait progressively longer for locks to release
        wait_s = 2 * (attempt + 1)
        _p(f"Files still locked — waiting {wait_s}s before retrying...")
        time.sleep(wait_s)

    if project_dir.exists():
        _p("WARNING: could not fully delete — some files may be locked by OneDrive or another process.")
        print(f"[delete_project] WARNING: could not fully delete {project_dir} — files may be locked by OneDrive or another process", flush=True)
    else:
        _p("Project files removed.")


def _migrate_existing_projects():
    """One-time migration: scan disk and populate registry for pre-existing projects."""
    if _REGISTRY_FILE.exists():
        return  # already migrated
    reg = {}
    if not GENERATED_DIR.exists():
        return
    for d in sorted(GENERATED_DIR.iterdir()):
        if not d.is_dir() or not (d / "package.json").exists():
            continue
        try:
            pkg = json.loads((d / "package.json").read_text())
        except Exception:
            pkg = {}
        try:
            meta = json.loads((d / ".meta.json").read_text()) if (d / ".meta.json").exists() else {}
        except Exception:
            meta = {}
        reg[d.name] = {
            "name":        d.name,
            "title":       pkg.get("description", d.name),
            "hasApp":      (d / "src").exists(),
            "type":        "react",
            "source":      meta.get("source", "prompt"),
            "sourceLabel": meta.get("label", "Instructions"),
            "figmaUrl":    meta.get("figma_url", ""),
            "prompt":      meta.get("prompt", ""),
        }
    _save_registry(reg)


_migrate_existing_projects()


def _health_check(port: int, proj_type: str = "react", name: str = "") -> bool:
    """
    Check if a project server is alive and serving content.
    - HTML projects (figma): GET http://localhost:{port}/_health → {"status":"ok"}
    - React/Vite projects:   GET http://localhost:{port}/         → any 200/304 response
    Both checks timeout in 200ms.
    """
    if not port:
        return False
    import urllib.request
    import urllib.error
    try:
        if proj_type == "html":
            url = _health_url(port, "html")
        else:
            # Vite dev server — just check the root responds
            url = _health_url(port, "react")
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=0.2) as resp:
            return resp.status < 500
    except Exception:
        return False


def _check_health_parallel(checks: list[tuple[int, str, str]]) -> dict[int, bool]:
    """
    Run health checks for all projects concurrently.
    checks = list of (port, proj_type, name)
    Returns {port: is_healthy}
    """
    if not checks:
        return {}
    from concurrent.futures import ThreadPoolExecutor, as_completed
    results: dict[int, bool] = {}
    unique = {p: (pt, n) for p, pt, n in checks if p}
    with ThreadPoolExecutor(max_workers=min(len(unique), 20)) as ex:
        future_map = {
            ex.submit(_health_check, p, pt, n): p
            for p, (pt, n) in unique.items()
        }
        for fut in as_completed(future_map):
            p = future_map[fut]
            try:
                results[p] = fut.result()
            except Exception:
                results[p] = False
    return results


def list_projects() -> list[dict]:
    """
    Fast project list from registry JSON.
    Port checks run in parallel so 20 projects take the same time as 1.
    """
    from agents.figma_to_web_using_playwright_agent import _html_servers, _html_ports
    reg = _load_registry()
    if not reg:
        return []

    # Re-sync in-memory ports from disk (may have changed via another process)
    _vite_disk, _api_disk, _datachat_disk = _load_ports()
    _dev_ports.update(_vite_disk)
    _api_ports.update(_api_disk)
    _datachat_ports.update(_datachat_disk)

    # Collect all ports first
    port_map: dict[str, int | None] = {}
    type_map: dict[str, str] = {}
    for name, entry in reg.items():
        proj_type = entry.get("type", "react")
        type_map[name] = proj_type
        if proj_type == "html":
            port_map[name] = _html_ports.get(name) or entry.get("port")
        else:
            port_map[name] = _dev_ports.get(name) or entry.get("port")

    # Parallel health checks — skip projects whose process we own (already know they're running)
    checks_needed = [
        (port_map[name], type_map[name], name)
        for name in reg
        if port_map.get(name)
        and name not in _dev_servers
        and name not in _html_servers
    ]
    health = _check_health_parallel(checks_needed)

    projects = []
    for name, entry in sorted(reg.items()):
        proj_type = entry.get("type", "react")
        port = port_map.get(name)

        # Process-based check is instant; port check uses parallel results
        if proj_type == "html":
            running = (name in _html_servers) or bool(health.get(port))
            url = ("/figma-app/" + name + "/") if (running and port) else None
        else:
            running = (name in _dev_servers) or bool(health.get(port))
            url = ("/app/" + name + "/") if (running and port) else None

        # Detect backend type: disk markers first, then registry fallback
        proj_dir = GENERATED_DIR / name
        bt_file = proj_dir / "backend" / ".backend_type"
        if bt_file.exists():
            _bt_raw = bt_file.read_text(encoding="utf-8").strip()
            _bt = "java" if "java" in _bt_raw else _bt_raw
        elif (proj_dir / "backend" / "pom.xml").exists():
            _bt = "java"
        elif entry.get("backendType"):
            _bt = entry["backendType"]
        else:
            _bt = "python"

        projects.append({
            "name":        name,
            "title":       entry.get("title", name),
            "port":        port,
            "apiPort":     _api_ports.get(name),
            "url":         url,
            "running":     running,
            "hasApp":      entry.get("hasApp", False),
            "type":        proj_type,
            "source":      entry.get("source", "prompt"),
            "sourceLabel": entry.get("sourceLabel", "Instructions"),
            "figmaUrl":    entry.get("figmaUrl", ""),
            "prompt":      entry.get("prompt", ""),
            "backendType": _bt,
        })
    return projects
