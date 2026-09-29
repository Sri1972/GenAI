"""
Data Quality Agent: profiles a data source (Excel file, delimited/CSV file,
or a database table), generates a runnable Python or Java project
implementing user-described data-quality checks against it, and executes
that project server-side, reporting pass/fail results.

Fully independent of WebUIGenerator/WebAPIGenerator -- no imports from
either, no shared execution/runner code, own generated-code storage
(see dq_server.py's LIBRARY_DIR). The only cross-module import is
ContentAgents/common/claude_cli.py's thin, generic Claude-CLI subprocess
wrapper (same reuse LandDAgent/run.py already established) -- profiling,
the generation prompt, and execution are all self-contained here.
"""

import csv
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

import openpyxl

ROOT = Path(__file__).resolve().parent.parent  # TurboAppGenerator/
_CONTENT_AGENTS_DIR = ROOT / "ContentAgents"
if str(_CONTENT_AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_CONTENT_AGENTS_DIR))

from common.claude_cli import ClaudeCliError, extract_json, run_claude_text  # noqa: E402

ProgressFn = Callable[[str], None]


def _slice_json_candidate(text: str) -> str:
    """Same fence-stripping/brace-finding extract_json() itself does, just
    returning the raw substring instead of parsing it -- lets
    _parse_generated_json below try a repair pass on exactly the same
    slice extract_json would have handed to json.loads()."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    start_candidates = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if not start_candidates:
        raise ValueError(f"No JSON found in text: {text[:500]}")
    start = min(start_candidates)
    end = max(text.rfind("}"), text.rfind("]")) + 1
    return text[start:end]


def _repair_control_chars_in_strings(text: str) -> str:
    """Best-effort repair for a common LLM mistake in JSON responses that
    embed source code: a literal raw newline/tab/carriage-return left
    inside a JSON string value instead of properly escaped as \\n/\\t/\\r
    (this is what json.loads reports as "Invalid control character").
    Walks the text tracking whether it's inside a string literal (toggling
    on an unescaped '"'), and escapes any raw control character found
    there; everything outside strings (structural whitespace) is
    untouched."""
    out = []
    in_string = False
    escape = False
    for ch in text:
        if in_string:
            if escape:
                out.append(ch)
                escape = False
            elif ch == "\\":
                out.append(ch)
                escape = True
            elif ch == '"':
                in_string = False
                out.append(ch)
            elif ch == "\n":
                out.append("\\n")
            elif ch == "\r":
                out.append("\\r")
            elif ch == "\t":
                out.append("\\t")
            else:
                out.append(ch)
        else:
            if ch == '"':
                in_string = True
            out.append(ch)
    return "".join(out)


def _parse_generated_json(result_text: str) -> dict | list:
    """extract_json() as the fast path (works for the common case); on
    failure, retries json.loads() on the same slice after
    _repair_control_chars_in_strings() -- a cheap, purely mechanical fix
    for one whole class of malformed response, tried before ever burning a
    second LLM call over it (see generate_code's retry loop below, which
    only kicks in if this also fails)."""
    try:
        return extract_json(result_text)
    except Exception:
        candidate = _slice_json_candidate(result_text)
        return json.loads(_repair_control_chars_in_strings(candidate))

def strip_wrapping_quotes(s: str) -> str:
    """Windows Explorer's "Copy as path" wraps the copied path in literal
    double quotes (e.g. '"C:\\Users\\...\\orders.sqlite"') -- a real user
    pasted exactly that into the SQLite database-path field, and the
    quotes ended up embedded in the path used both to profile and to run
    the generated code, producing a "does not exist" error against a
    nonsense concatenated path. Strips one matching pair of leading/
    trailing quotes (single or double) if present; leaves the string
    alone otherwise."""
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1].strip()
    return s


DB_TYPES = ("postgresql", "mysql", "sqlserver", "oracle", "sqlite")
LANGUAGES = ("python", "java")
# Parquet is Python-only -- real Java Parquet support needs Apache Parquet +
# Hadoop client dependencies (heavy, fragile to get working via a single
# Maven exec:java call), not worth it for this agent's scope.
PARQUET_LANGUAGES = ("python",)

SAMPLE_ROWS = 5


# ── Profiling (deterministic, no LLM call) ──────────────────────────────

def _infer_type(values: list[str]) -> str:
    if not values:
        return "empty"
    def _is_int(v):
        try:
            int(v); return True
        except (ValueError, TypeError):
            return False
    def _is_float(v):
        try:
            float(v); return True
        except (ValueError, TypeError):
            return False
    if all(_is_int(v) for v in values):
        return "integer"
    if all(_is_float(v) for v in values):
        return "float"
    return "string"


def _profile_rows(header: list[str], rows: list[list], sample_rows: int = SAMPLE_ROWS) -> dict:
    """Shared column-profile builder for both Excel and delimited sources."""
    columns = []
    for i, name in enumerate(header):
        col_values = [r[i] if i < len(r) else None for r in rows]
        non_null = [str(v) for v in col_values if v not in (None, "")]
        columns.append({
            "name": name,
            "inferred_type": _infer_type(non_null),
            "sample_values": non_null[:sample_rows],
            "null_count": len(col_values) - len(non_null),
        })
    return {"columns": columns, "row_count": len(rows)}


def parse_pasted_columns(text: str) -> list[str]:
    """A pasted header row, in comma-, tab-, or pipe-delimited form."""
    text = (text or "").strip()
    if not text:
        return []
    for sep in ("\t", "|", ","):
        if sep in text:
            return [c.strip() for c in text.split(sep)]
    return text.split()


def profile_excel(data: bytes, has_header: bool, pasted_columns: str) -> dict:
    wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
    ws = wb.worksheets[0]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    if has_header:
        header = [str(h) if h is not None else f"col_{i}" for i, h in enumerate(rows[0])] if rows else []
        data_rows = rows[1:]
    else:
        cols = parse_pasted_columns(pasted_columns)
        width = len(rows[0]) if rows else len(cols)
        header = cols if cols else [f"col_{i}" for i in range(width)]
        data_rows = rows
    return {"sheet": ws.title, **_profile_rows(header, data_rows)}


def profile_delimited(data: bytes, delimiter: str, has_header: bool, pasted_columns: str) -> dict:
    text = data.decode("utf-8", errors="replace")
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter or ","))
    if has_header:
        header = rows[0] if rows else []
        data_rows = rows[1:]
    else:
        cols = parse_pasted_columns(pasted_columns)
        width = len(rows[0]) if rows else len(cols)
        header = cols if cols else [f"col_{i}" for i in range(width)]
        data_rows = rows
    return _profile_rows(header, data_rows)


def profile_parquet(data: bytes) -> dict:
    """Parquet's schema (column names + types) is embedded in the file
    itself -- no has_header/pasted_columns concept needed, unlike Excel/
    delimited sources."""
    import pandas as pd
    df = pd.read_parquet(io.BytesIO(data))
    header = list(df.columns)
    rows = df.astype(object).where(df.notna(), None).values.tolist()
    return _profile_rows(header, rows)


def fetch_s3_bytes(s3_path: str) -> bytes:
    """Uses boto3's default credential chain -- the same AWS_PROFILE/
    AWS_REGION already configured for Bedrock elsewhere in this app, no
    separate AWS-key input fields in the UI."""
    import boto3
    if not s3_path.startswith("s3://"):
        raise ValueError(f"Not an s3:// path: {s3_path}")
    bucket, _, key = s3_path[len("s3://"):].partition("/")
    obj = boto3.client("s3").get_object(Bucket=bucket, Key=key)
    return obj["Body"].read()


def _build_engine(db_type: str, host: str, port: str, database: str, username: str, password: str):
    from sqlalchemy import create_engine
    if db_type == "sqlite":
        return create_engine(f"sqlite:///{database}")
    dialect = {
        "postgresql": "postgresql+psycopg2",
        "mysql": "mysql+pymysql",
        "sqlserver": "mssql+pyodbc",
        "oracle": "oracle+oracledb",
    }.get(db_type)
    if not dialect:
        raise ValueError(f"Unknown db_type '{db_type}'")
    suffix = "?driver=ODBC+Driver+17+for+SQL+Server" if db_type == "sqlserver" else ""
    url = f"{dialect}://{username}:{password}@{host}:{port}/{database}{suffix}"
    return create_engine(url, connect_args={"connect_timeout": 5} if db_type not in ("sqlserver", "sqlite") else {})


def parse_pasted_schema(text: str) -> list[dict]:
    """Best-effort fallback grounding when a live DB connection isn't
    possible: each line `col_name[: type]`, or a single comma-separated
    line of bare column names."""
    text = (text or "").strip()
    if not text:
        return []
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if len(lines) == 1 and "," in lines[0]:
        return [{"name": c.strip(), "inferred_type": "unknown", "sample_values": [], "null_count": None}
                for c in lines[0].split(",") if c.strip()]
    columns = []
    for line in lines:
        name, _, typ = line.partition(":")
        columns.append({"name": name.strip(), "inferred_type": typ.strip() or "unknown",
                         "sample_values": [], "null_count": None})
    return columns


def profile_database(db_type: str, host: str, port: str, database: str, username: str,
                      password: str, table: str, pasted_schema: str) -> dict:
    """Tries a real read-only connection first (accurate columns/samples);
    ANY failure (missing driver, bad creds, network) falls back to
    parse_pasted_schema() rather than raising -- generation should never
    hard-fail just because a live DB probe didn't work."""
    try:
        engine = _build_engine(db_type, host, port, database, username, password)
        from sqlalchemy import inspect, text as sql_text
        insp = inspect(engine)
        cols = insp.get_columns(table)
        columns = {c["name"]: {"name": c["name"], "inferred_type": str(c["type"]),
                                "sample_values": [], "null_count": None} for c in cols}
        with engine.connect() as conn:
            rows = [dict(r._mapping) for r in conn.execute(sql_text(f"SELECT * FROM {table} LIMIT {SAMPLE_ROWS}"))]
        for col_name, col in columns.items():
            col["sample_values"] = [str(r[col_name]) for r in rows if r.get(col_name) is not None][:SAMPLE_ROWS]
        return {"table": table, "columns": list(columns.values()), "source": "live_connection"}
    except Exception as exc:
        return {"table": table, "columns": parse_pasted_schema(pasted_schema),
                "source": "pasted_schema_fallback", "connection_error": str(exc)[:500]}


# ── Code generation (one Claude call, JSON contract) ────────────────────

SYSTEM_PROMPT = """You are a senior data engineer writing a small, real, \
runnable {language} program that checks a data source against a list of \
data-quality rules described in plain English, given a profile of the \
source's real columns/types/sample values (or a live database table).

You will receive a JSON object describing:
- source_kind: "excel" | "delimited" | "parquet" | "database"
- profile: real column names, inferred types, sample values, null counts
  (for "database" sources, may instead come from a pasted schema if a live
  connection wasn't possible -- check "source"/"connection_error" fields)
- delimiter, has_header (for "delimited" sources only)
- db_type, table (for "database" sources only)
- rules: the user's data-quality rules, in their own words

Write {language} code that:
- Reads the actual data at runtime (NOT the sample values you were shown --
  those are just for grounding column names/types) using ONLY these fixed
  environment variable names (never a command-line argument -- the real
  file path may contain spaces, and CLI-arg passing through Maven/shell
  layers is unreliable with those):
  - excel/delimited/parquet sources: the file path is in environment
    variable DQ_SOURCE_FILE (Python: os.environ["DQ_SOURCE_FILE"]; Java:
    System.getenv("DQ_SOURCE_FILE")). Excel: parse with the appropriate
    library (Python: openpyxl; Java: Apache POI). Delimited: use the given
    delimiter and has_header flag exactly -- Java specifically:
    line.split(java.util.regex.Pattern.quote(DELIMITER), -1), NEVER a
    manually backslash-escaped regex literal like "\\|". Splitting on a
    Pattern.quote(...)'d delimiter needs zero escaping in the Java source;
    a raw escaped literal needs Java string escaping AND regex escaping
    AND this whole response's own JSON-string escaping all at once, and a
    dropped backslash there has produced invalid JSON before. Parquet
    (Python only -- you will never be asked for Java here):
    pandas.read_parquet(path) or pyarrow.parquet.read_table(path); the
    schema/column names are embedded in the file, there's no delimiter/
    header to worry about.
  - database sources: connect using these environment variables: DB_TYPE,
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, DB_TABLE. Pick the
    right driver/import for db_type (postgresql/mysql/sqlserver/oracle/
    sqlite -- sqlite uses DB_NAME as the file path, no host/port/user/pass).
- Implements each data-quality rule as a separate, named check against the
  REAL data (not the samples), each producing a clear pass/fail + a detail
  message.
- Matches each rule's referenced field to the REAL column list
  SEMANTICALLY, not by requiring an exact literal string match -- e.g. a
  rule mentioning "signup date" should match a real column named
  "created_at" or "signup_dt" if that's clearly the closest reasonable
  column, case-insensitively, allowing for common abbreviations/synonyms.
  When you do this, say so in the check's name, e.g. "signup_date_valid
  (matched to column: created_at)", so a mismatch is easy to catch by eye.
  Only report "no matching column found" (naming the columns that DO
  exist, like you already should) when there genuinely isn't a reasonable
  candidate -- never silently guess at an unrelated column just to avoid
  reporting "not found".
- For every FAILING check, the detail message must let someone find the
  actual bad data without re-running anything themselves: state the total
  failing count, then up to 10 concrete examples, each showing (a) that
  row's 1-indexed position in the source ("row 7") -- and ALSO a natural
  identifier column's value if one obviously exists (e.g. "id=42"), (b)
  the actual offending value(s) for the column(s) that rule is about. e.g.
  "3 rows failed: row 4 (id=12, age=-5), row 9 (id=41, age=210), row 15
  (id=58, age=999)" -- never just a bare list of ids/row numbers with no
  values, and never just "3 rows failed" with no examples at all.
- Prints a readable report to stdout, and as the VERY LAST line prints
  exactly: DQ_RESULT_JSON: <single-line JSON> -- where the JSON is
  {{"passed": bool, "checks": [{{"name": str, "passed": bool, "detail": str}}],
  "summary": str}}. "passed" is true only if every check passed.
- Exits with status code 0 if all checks passed, 1 otherwise.
- Is a complete, runnable project for {language} -- Python: a manifest
  named exactly "requirements.txt" (only real, necessary packages: pandas/
  openpyxl for excel/delimited, pandas+pyarrow for parquet, sqlalchemy+the
  right DB driver for db sources -- never invent a package that doesn't
  exist). Java: a Maven "pom.xml" that
  includes the exec-maven-plugin (so `mvn -q compile exec:java
  -Dexec.mainClass=...` runs it directly) plus any real dependency needed
  (Apache POI for Excel, the right JDBC driver for db sources).
- Splits into multiple files by concern -- NOT one monolithic file -- same
  spirit as a well-organized small project, easier to read one piece at a
  time:
  - Python: "main.py" (entry point only -- orchestrates reading the data,
    running the checks, printing the report + DQ_RESULT_JSON line, and the
    exit code), "reader.py" (reads the source into a list of row dicts --
    the ONLY file that knows about excel/delimited/parquet/db specifics),
    "checks.py" (one function per data-quality rule, each returning a
    {{"name","passed","detail"}}-shaped result), plus "requirements.txt".
  - Java: "Main.java" (same entry-point-only role as main.py),
    "DataReader.java" (reads the source into a List<Map<String, Object>>
    or similar -- same isolation as reader.py), "Checks.java" (one static
    method per rule), "CheckResult.java" (the small pass/fail/detail
    holder class the other two use), plus "pom.xml". Use a consistent
    package (e.g. com.dq) across all of them.
  Keep it plain -- no interfaces/abstract classes/design patterns for a
  project this size, just plain functions/classes split by what they do.

Output ONLY this JSON object, no prose/preamble/markdown fences:
{{
  "files": [{{"path": "relative/file/path", "content": "full file text"}}],
  "run": {{
    "entry": "main.py, OR the fully-qualified Java main class (e.g. com.dq.Main)"
  }}
}}"""


def generate_code(profile: dict, rules: str, language: str, source_kind: str,
                   extra: dict, on_progress: ProgressFn | None = None) -> dict:
    if language not in LANGUAGES:
        raise ValueError(f"Unknown language '{language}'")

    payload = {"source_kind": source_kind, "profile": profile, "rules": rules, **extra}
    prompt = "INPUT:\n" + json.dumps(payload, indent=2)
    system_prompt = SYSTEM_PROMPT.format(language=language)

    # A response with generated source code embedded in a JSON string needs
    # 2-3 levels of escaping to line up at once (e.g. Java's own regex
    # escaping THEN this response's JSON-string escaping) -- LLMs
    # occasionally drop a backslash there, which breaks JSON parsing
    # outright. One retry (a fresh call, not a repair attempt) resolves it
    # almost always, so this is cheap insurance against a rare but real
    # failure mode rather than a normal code path.
    last_error: Exception | None = None
    for attempt in range(2):
        if on_progress:
            on_progress(f"Writing {language} data-quality check code..." if attempt == 0
                         else "That response wasn't valid JSON -- retrying once...")
        result_text = run_claude_text(prompt, system_prompt=system_prompt, allowed_tools=[])
        try:
            parsed = _parse_generated_json(result_text)
        except Exception as exc:
            last_error = exc
            continue
        if not isinstance(parsed, dict) or "files" not in parsed or "run" not in parsed:
            last_error = ClaudeCliError("Generated response was missing 'files'/'run'.")
            continue
        return parsed
    raise ClaudeCliError(f"Generated response wasn't valid after 2 attempts ({last_error}) -- try regenerating.")


# ── Lightweight validation (before execution) ────────────────────────────

def validate_python(files_dir: Path) -> str | None:
    """Syntax-checks every .py file without leaving __pycache__/*.pyc
    behind in files_dir -- compiles to a throwaway file in the system temp
    dir instead (cfile=os.devnull/'nul' isn't accepted by py_compile on
    Windows: it refuses to byte-compile onto a special device file)."""
    import py_compile
    import tempfile
    for f in files_dir.rglob("*.py"):
        fd, tmp_cfile = tempfile.mkstemp(suffix=".pyc")
        os.close(fd)
        try:
            py_compile.compile(str(f), cfile=tmp_cfile, doraise=True)
        except py_compile.PyCompileError as exc:
            return str(exc)
        finally:
            os.unlink(tmp_cfile)
    return None


def validate_java(files_dir: Path) -> str | None:
    mvn = shutil.which("mvn")
    if not mvn:
        return "Maven ('mvn') not found on PATH -- cannot compile/run Java code here."
    proc = subprocess.run([mvn, "-q", "compile"], cwd=str(files_dir),
                           capture_output=True, text=True, timeout=180)
    if proc.returncode != 0:
        return (proc.stderr or proc.stdout)[-3000:]
    return None


def check_entry_exists(files_dir: Path, language: str, entry: str) -> str | None:
    """py_compile/mvn compile only check whatever files DO exist -- neither
    one notices if the response's "run.entry" points at a file that was
    never actually written (seen directly: a real generation once produced
    only reader.py + requirements.txt, no main.py, and still reported
    validation_error: None). This catches that class of problem too."""
    if language == "python":
        exists = (files_dir / entry).exists()
    else:
        exists = (files_dir / "src" / "main" / "java" / (entry.replace(".", "/") + ".java")).exists()
    if exists:
        return None
    return f"Generated response declared its entry point as '{entry}', but that file was never written -- try regenerating."


# ── Execution ─────────────────────────────────────────────────────────────

def _run_timeout_seconds(size_bytes: int) -> int:
    mb = size_bytes / (1024 * 1024)
    return min(600, max(60, round(60 + mb * 30)))


def parse_dq_result(stdout: str) -> dict | None:
    marker = "DQ_RESULT_JSON:"
    for line in stdout.splitlines():
        if line.strip().startswith(marker):
            try:
                return json.loads(line.strip()[len(marker):].strip())
            except json.JSONDecodeError:
                return None
    return None


def run_python(files_dir: Path, entry: str, env_vars: dict, timeout: int) -> dict:
    """env_vars carries DQ_SOURCE_FILE (file sources) or the DB_* vars
    (database sources) -- never a CLI argument, since a real file path can
    contain spaces (this repo's own path does) and that's unreliable to
    round-trip through Maven/shell argument layers (see run_java below,
    where this bit the team directly during testing)."""
    log_prefix = ""
    req = files_dir / "requirements.txt"
    marker = files_dir / ".deps_installed"
    if req.exists() and not marker.exists():
        install = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", str(req)],
                                  cwd=str(files_dir), capture_output=True, text=True, timeout=300)
        if install.returncode == 0:
            marker.write_text("ok", encoding="utf-8")
        else:
            log_prefix = f"pip install failed (exit {install.returncode}):\n{install.stderr}\n\n"
    cmd = [sys.executable, entry]
    env = {**os.environ, **env_vars}
    try:
        proc = subprocess.run(cmd, cwd=str(files_dir), env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "stdout": log_prefix, "stderr": f"Timed out after {timeout}s."}
    return {"returncode": proc.returncode, "stdout": log_prefix + proc.stdout, "stderr": proc.stderr}


def run_java(files_dir: Path, entry: str, env_vars: dict, timeout: int) -> dict:
    """See run_python's docstring -- DQ_SOURCE_FILE/DB_* are passed via
    env_vars, never `-Dexec.args`: that property is whitespace-split by
    exec-maven-plugin, which silently truncated a real path at its first
    space during testing (a OneDrive path containing " - S&P Global")."""
    mvn = shutil.which("mvn")
    if not mvn:
        return {"returncode": -1, "stdout": "", "stderr": "Maven ('mvn') not found on PATH."}
    cmd = [mvn, "-q", "compile", "exec:java", f"-Dexec.mainClass={entry}"]
    env = {**os.environ, **env_vars}
    try:
        proc = subprocess.run(cmd, cwd=str(files_dir), env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "stdout": "", "stderr": f"Timed out after {timeout}s."}
    return {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
