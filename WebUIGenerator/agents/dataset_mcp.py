"""
The `dataset` in-process MCP server — safe, bounded querying of medium datasets.

Gives every agent (the web-app builder AND the roundtable personas) a way to work with
CSV/Parquet/JSON files WITHOUT ever loading raw rows into the model's context — which is
exactly what crashed a meeting when a persona tried to `Read` an 88 MB CSV. DuckDB does the
heavy lifting in-process (it queries files directly with SQL, no full load), and every tool
returns only compact, row-capped results.

Same mechanism as `turboui_mcp`: `create_sdk_mcp_server` + `@tool`, wired via
`mcp_servers={"dataset": build_dataset_server(...)}`. No subprocess.

Tools (all read-only):
  list_datasets(directory)      — data files in a dir, with size + type
  profile_dataset(path)         — schema, row count, per-column stats (DuckDB SUMMARIZE)
  sample_dataset(path, n)       — first n rows (capped)
  run_sql(sql, limit)           — run SQL over files ('SELECT ... FROM ''/abs/x.csv''') , row-capped
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any, Optional

import duckdb
from claude_agent_sdk import tool, create_sdk_mcp_server, ToolAnnotations

_RO = ToolAnnotations(readOnlyHint=True)

# Real-world CSVs (like the used-car sample) routinely break DuckDB's default sniffer —
# unquoted commas, ragged rows — which collapses the whole header into one column and makes
# every "column not found" query fail. These options make the reader tolerant: skip the bad
# rows instead of aborting, pad short rows, and sniff the schema from the whole file.
_CSV_OPTS = "ignore_errors=true, null_padding=true, sample_size=-1"
# Quoted paths ending in .csv/.tsv inside an agent's SQL, so run_sql can transparently upgrade
# `FROM 'x.csv'` to the robust reader.
_CSV_LIT = re.compile(r"'([^']*\.(?:csv|tsv))'", re.I)

DATASET_TOOL_NAMES = [
    "mcp__dataset__list_datasets",
    "mcp__dataset__profile_dataset",
    "mcp__dataset__sample_dataset",
    "mcp__dataset__run_sql",
]

_DATA_EXT = {".csv", ".tsv", ".parquet", ".json", ".jsonl", ".ndjson"}
_MAX_ROWS = 500          # hard cap on rows any tool returns
_MAX_OUTPUT = 16_000     # hard cap on characters returned (context safety)
_MAX_CELL = 80           # truncate individual cell values
# Only read-only statements may run — first keyword must be one of these.
_SQL_OK = {"select", "with", "from", "describe", "summarize", "explain", "show", "pragma", "table", "values"}


def _text(s: str, is_error: bool = False) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": s}], "is_error": is_error}


def _cap(s: str) -> str:
    return s if len(s) <= _MAX_OUTPUT else s[:_MAX_OUTPUT] + "\n… (output truncated)"


def _md_table(columns: list[str], rows: list[tuple]) -> str:
    def cell(v: Any) -> str:
        s = "" if v is None else str(v)
        s = s.replace("\n", " ").replace("|", "\\|")
        return s if len(s) <= _MAX_CELL else s[: _MAX_CELL - 1] + "…"
    head = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    body = "\n".join("| " + " | ".join(cell(c) for c in r) + " |" for r in rows)
    return "\n".join([head, sep, body]) if rows else head + "\n" + sep + "\n_(no rows)_"


def build_dataset_server(base_dir: Optional[Path] = None):
    """Create the in-process dataset server. `base_dir` (a project root) lets relative paths
    like 'inputs/car_prices.csv' resolve; run_sql should use absolute paths inside its SQL.

    Concurrency: the roundtable runs personas' dataset queries in PARALLEL (asyncio.gather over
    N personas, each tool call dispatched to a worker thread). A single DuckDB connection is NOT
    safe for concurrent use across threads, so every call gets its OWN short-lived in-memory
    connection instead. There is no cross-call state to keep — each query reads a file directly
    (`FROM 'file.csv'`), we never create tables/views — so per-call isolation is free and the
    race is designed out rather than locked around (a lock would serialize the parallelism we
    want)."""

    def _resolve(path: str) -> Path:
        p = Path(path)
        if not p.is_absolute() and base_dir is not None:
            p = (base_dir / path)
        return p

    def _q(path: str) -> str:  # SQL string literal for a file path
        return str(_resolve(path)).replace("'", "''")

    def _source(path: str) -> str:
        """A SQL source expression for a file WE build the query around — the robust CSV reader
        for csv/tsv, a plain literal for parquet/json (which have real schemas)."""
        rp = _resolve(path)
        lit = str(rp).replace("'", "''")
        if rp.suffix.lower() in (".csv", ".tsv"):
            return f"read_csv_auto('{lit}', {_CSV_OPTS})"
        return f"'{lit}'"

    def _harden(sql: str) -> str:
        """Transparently upgrade `FROM 'x.csv'` in an agent's SQL to the robust reader — unless
        it already spelled out read_csv itself (don't double-wrap)."""
        if "read_csv" in sql.lower():
            return sql
        return _CSV_LIT.sub(lambda m: f"read_csv_auto('{m.group(1)}', {_CSV_OPTS})", sql)

    def _query(sql: str, limit: int) -> tuple[list[str], list[tuple]]:
        """Run one read-only statement on a fresh, isolated connection. Runs inside a worker
        thread (via to_thread); the fresh connection is what makes that thread-safe."""
        con = duckdb.connect(":memory:")
        try:
            cur = con.execute(sql)
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchmany(limit)
            return cols, rows
        finally:
            con.close()

    def _profile(path: str) -> tuple[int, list[str], list[tuple]]:
        """Count + SUMMARIZE on one fresh connection (two statements, same thread, sequential)."""
        con = duckdb.connect(":memory:")
        try:
            src = _source(path)
            total = con.execute(f"SELECT count(*) FROM {src}").fetchone()[0]
            cur = con.execute(f"SUMMARIZE SELECT * FROM {src}")
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchmany(_MAX_ROWS)
            return total, cols, rows
        finally:
            con.close()

    @tool("list_datasets",
          "List data files (CSV/Parquet/JSON/TSV) in a directory with their size and type. "
          "Use it to discover what's available in a project's inputs/ before querying.",
          {"type": "object", "properties": {"directory": {"type": "string", "description": "absolute dir path (e.g. the project's inputs/)"}},
           "required": ["directory"]}, annotations=_RO)
    async def list_datasets(args: dict[str, Any]) -> dict[str, Any]:
        d = _resolve(args.get("directory", ""))
        if not d.is_dir():
            return _text(f"Not a directory: {d}", is_error=True)
        rows = []
        for p in sorted(d.iterdir()):
            if p.is_file() and p.suffix.lower() in _DATA_EXT:
                rows.append((p.name, f"{p.stat().st_size // 1024} KB", p.suffix.lower().lstrip(".")))
        if not rows:
            return _text(f"No data files in {d}.")
        return _text(_md_table(["file", "size", "type"], rows))

    @tool("profile_dataset",
          "Profile a dataset file: column names + types, total row count, and per-column stats "
          "(min, max, approx distinct, mean, quartiles, null %). Reads only summary stats — never "
          "raw rows — so it's safe on very large files. Pass the file's absolute path.",
          {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}, annotations=_RO)
    async def profile_dataset(args: dict[str, Any]) -> dict[str, Any]:
        path = args.get("path", "")
        rp = _resolve(path)
        if not rp.exists():
            return _text(f"File not found: {rp}. Use the absolute path from the project's inputs/.", is_error=True)
        try:
            total, cols, rows = await asyncio.to_thread(_profile, path)
            return _text(_cap(f"**{rp.name}** — {total:,} rows\n\n" + _md_table(cols, rows)))
        except Exception as e:
            return _text(f"Could not profile {rp.name}: {type(e).__name__}: {e}", is_error=True)

    @tool("sample_dataset",
          "Return the first n rows of a dataset file (n capped at 50) so you can see the shape of "
          "the data. Pass the file's absolute path.",
          {"type": "object", "properties": {"path": {"type": "string"}, "n": {"type": "integer", "description": "rows (default 10, max 50)"}},
           "required": ["path"]}, annotations=_RO)
    async def sample_dataset(args: dict[str, Any]) -> dict[str, Any]:
        path = args.get("path", "")
        n = max(1, min(50, int(args.get("n", 10))))
        rp = _resolve(path)
        if not rp.exists():
            return _text(f"File not found: {rp}.", is_error=True)
        try:
            cols, rows = await asyncio.to_thread(_query, f"SELECT * FROM {_source(path)} LIMIT {n}", n)
            return _text(_cap(_md_table(cols, rows)))
        except Exception as e:
            return _text(f"Could not sample {rp.name}: {type(e).__name__}: {e}", is_error=True)

    @tool("run_sql",
          "Run a READ-ONLY DuckDB SQL query over dataset files and return up to `limit` rows. "
          "Reference files directly by absolute path, e.g. "
          "SELECT make, avg(sellingprice) FROM '/abs/inputs/car_prices.csv' GROUP BY make ORDER BY 2 DESC. "
          "DuckDB reads the file without loading it fully, so this scales to large files — use it for "
          "aggregations/filters and let the query do the work rather than reading rows yourself. "
          "Only SELECT/WITH/DESCRIBE/SUMMARIZE queries are allowed.",
          {"type": "object", "properties": {
              "sql": {"type": "string"},
              "limit": {"type": "integer", "description": "max rows to return (default 50, max 500)"}},
           "required": ["sql"]}, annotations=_RO)
    async def run_sql(args: dict[str, Any]) -> dict[str, Any]:
        sql = (args.get("sql") or "").strip().rstrip(";")
        limit = max(1, min(_MAX_ROWS, int(args.get("limit", 50))))
        if not sql:
            return _text("Empty SQL.", is_error=True)
        first = sql.split(None, 1)[0].lower()
        if first not in _SQL_OK:
            return _text(f"Only read-only queries are allowed (got '{first}'). Use SELECT/WITH/DESCRIBE/SUMMARIZE.", is_error=True)
        try:
            cols, rows = await asyncio.to_thread(_query, _harden(sql), limit)
            note = f"\n\n_(showing up to {limit} rows)_" if len(rows) >= limit else ""
            return _text(_cap(_md_table(cols, rows) + note))
        except Exception as e:
            return _text(f"Query failed: {type(e).__name__}: {e}", is_error=True)

    return create_sdk_mcp_server(
        name="dataset", version="1.0.0",
        tools=[list_datasets, profile_dataset, sample_dataset, run_sql],
    )
