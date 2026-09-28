"""
Starts/stops live dev servers for standalone generated APIs.

Owns its own port pool and process table, entirely separate from WebUIGenerator's
web-app dev-server/companion-API pools (agents.uigen_agent's _dev_ports/_api_ports) —
no existing web-app start/stop code path is touched. Reuses WebUIGenerator's
free-port check and Java/Maven env resolution instead of duplicating them, since
WebUIGenerator stays on sys.path and owns the `agents` package name. wait_for_api
below is its own implementation, not reused from uigen_agent — it needs to check
this module's own _procs table to bail out early on a dead process, which the
shared one has no way to do.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from agents.uigen_agent import _port_is_free, resolve_java_maven_env

from api_config import PORTS_FILE, PORT_START

_procs: dict[str, subprocess.Popen] = {}
_ports: dict[str, int] = {}


def _load_ports() -> dict:
    if PORTS_FILE.exists():
        try:
            return json.loads(PORTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_ports():
    PORTS_FILE.write_text(json.dumps(_ports, indent=2), encoding="utf-8")


_ports.update(_load_ports())


def _next_port() -> int:
    assigned = set(_ports.values())
    port = PORT_START
    while port in assigned or not _port_is_free(port):
        port += 1
    return port


def _kill_port(port: int):
    """Best-effort: kill whatever is still bound to `port` on Windows."""
    if os.name != "nt" or not port:
        return
    try:
        out = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=10
        ).stdout
        for line in out.splitlines():
            if f":{port} " in line and "LISTENING" in line:
                pid = line.split()[-1]
                subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, timeout=10)
    except Exception:
        pass


def _pre_create_java_schema_with_fk(project_dir: Path) -> str | None:
    """
    Hibernate's community SQLite dialect, under ddl-auto=update, never emits a
    FOREIGN KEY clause for a @ManyToOne/@JoinColumn relationship — observed
    directly: a live `orders` table came back with a `customer_id` column but
    no constraint on it at all, so a bad row (referencing a customer that was
    never created) inserted successfully instead of failing. The data
    architect's own schema.sql already has the correct FOREIGN KEY clauses,
    but for Java it's otherwise unused — Spring's own schema/data init is
    force-disabled (see _ensure_java_seed_data_disabled_in_spring) specifically
    so the platform's own seeding owns the .db file instead.

    Create the tables from schema.sql directly, via sqlite3, before the app's
    very first startup ever. ddl-auto=update is additive — it creates a table
    only if one doesn't already exist, and otherwise just adds any missing
    columns — so Hibernate will find these properly-constrained tables already
    in place on startup and leave the constraint alone, rather than generating
    its own unconstrained version from scratch.

    Only makes sense the very first time: if the .db file already exists, the
    tables (and whatever constraints they got — or didn't, for a project
    generated before this fix existed) are already there, so this is a no-op.
    Non-fatal on any failure — Hibernate creating unconstrained tables itself
    is still a working app, just without this enforcement, which is exactly
    the situation before this function existed.
    """
    props_path = project_dir / "src/main/resources/application.properties"
    schema_path = project_dir / "src/main/resources/schema.sql"
    if not props_path.exists() or not schema_path.exists():
        return None

    import re as _re
    m = _re.search(r"spring\.datasource\.url\s*=\s*jdbc:sqlite:(\S+)", props_path.read_text(encoding="utf-8"))
    if not m:
        return None
    db_file = project_dir / m.group(1).split("?")[0]
    if db_file.exists():
        return None

    # The LLM sometimes points spring.datasource.url at a subdirectory (e.g.
    # ./data/app.db) rather than a flat filename in the project root like the
    # other generated projects use — observed directly: SQLite's JDBC driver
    # (and Python's sqlite3 right below) both refuse to create the file if
    # its parent directory doesn't exist yet, so the app crashed on its very
    # first startup with "path to './data/app.db' does not exist" before
    # Hibernate ever got a chance to run its own DDL. Safe regardless of
    # whether the LLM chose a flat filename or a subdirectory.
    db_file.parent.mkdir(parents=True, exist_ok=True)

    import sqlite3
    try:
        conn = sqlite3.connect(str(db_file))
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.executescript(schema_path.read_text(encoding="utf-8"))
            conn.commit()
        finally:
            conn.close()
        return f"pre-created {db_file.name} from schema.sql (with foreign-key constraints)"
    except Exception as e:
        db_file.unlink(missing_ok=True)
        return f"schema pre-create failed, falling back to Hibernate's own DDL — {e}"


def start_api_project(name: str, project_dir: Path, language: str) -> int:
    """
    Start the generated API's dev server (installing deps on first run) and return
    the assigned port. Idempotent — restarts cleanly if already running.
    """
    stop_api_project(name)

    port = _ports.get(name)
    if not port or not _port_is_free(port):
        port = _next_port()
    _ports[name] = port
    _save_ports()

    log_path = project_dir / "api_server.log"
    log_file = open(str(log_path), "w", encoding="utf-8", errors="replace")

    if language == "java":
        backend_dir = project_dir if (project_dir / "pom.xml").exists() else project_dir / "backend"
        env = os.environ.copy()
        # Spring Boot doesn't auto-load a .env file; the deterministic security
        # filters read System.getenv() directly, so merge an .env into the
        # subprocess env ourselves (same pattern as uigen_agent._start_java_api_server).
        # Prefer the protected copy outside the project dir — some generated apps
        # overwrite their own .env at runtime and, critically, don't preserve
        # API_AUTH_TYPE, which silently disables auth entirely on the next
        # restart if we trusted that file. Fall back to the in-project .env for
        # projects generated before this copy existed.
        from api_config import protected_env_file
        env_file = protected_env_file(name)
        if not env_file.exists():
            env_file = project_dir / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    if val.strip():
                        env[key.strip()] = val.strip()
        env["PORT"] = str(port)
        mvn_cmd = resolve_java_maven_env(env, backend_dir)

        # Seeding is no longer Spring's concern at all — application.properties
        # is deterministically forced to spring.sql.init.mode=never (see
        # _ensure_java_seed_data_disabled_in_spring) and seed_database() below
        # seeds the .db file directly via Python's sqlite3, called separately
        # once the app is confirmed up.
        schema_result = _pre_create_java_schema_with_fk(project_dir)
        if schema_result:
            print(f"[api-runner] {name}: {schema_result}", flush=True)
        run_args = [f"--server.port={port}"]

        # spring-boot:run compiles test sources by default even though it never
        # runs them — LLM-generated test code compiling cleanly is a separate
        # quality concern from "does the app start", so skip it entirely here.
        cmd = [mvn_cmd, "spring-boot:run", "-Dmaven.test.skip=true",
               f"-Dspring-boot.run.arguments={' '.join(run_args)}"]
        kwargs: dict = {"cwd": str(backend_dir), "env": env, "stdout": log_file, "stderr": log_file}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        proc = subprocess.Popen(cmd, **kwargs)
    else:
        # Install deps once per project (marker file avoids re-running pip install
        # on every restart).
        marker = project_dir / ".deps_installed"
        if not marker.exists():
            req = project_dir / "requirements.txt"
            if req.exists():
                install = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-q", "-r", str(req)],
                    cwd=str(project_dir), timeout=300, capture_output=True, text=True,
                )
                if install.returncode == 0:
                    marker.write_text("ok", encoding="utf-8")
                else:
                    # Don't write the marker on failure — otherwise every future
                    # start silently skips install forever, masking the real error.
                    log_file.write(f"pip install failed (exit {install.returncode}):\n{install.stderr}\n")
                    log_file.flush()
            else:
                marker.write_text("ok", encoding="utf-8")

        env = os.environ.copy()
        env["PORT"] = str(port)
        cmd = [sys.executable, "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", str(port)]
        kwargs = {"cwd": str(project_dir), "env": env, "stdout": log_file, "stderr": log_file}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        proc = subprocess.Popen(cmd, **kwargs)

    _procs[name] = proc
    print(f"[api-runner] Started {name} ({language}) on port {port} (PID {proc.pid})", flush=True)
    return port


def stop_api_project(name: str):
    proc = _procs.pop(name, None)
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
    _kill_port(_ports.get(name))


def release_port(name: str):
    """
    Drop a deleted project's port assignment. Without this, _next_port()'s
    `assigned = set(_ports.values())` check keeps treating a deleted project's
    port as taken forever — it never causes a real collision (there's no
    shortage of ports), but .ports.json otherwise accumulates a permanent,
    growing list of entries for projects that no longer exist on disk.
    """
    if _ports.pop(name, None) is not None:
        _save_ports()


def rename_port(old_name: str, new_name: str):
    """Carry a project's assigned port over to its new name — same port number,
    just re-keyed, matching how the running process is stopped/restarted under
    the new name rather than reassigned a fresh one."""
    port = _ports.pop(old_name, None)
    if port is not None:
        _ports[new_name] = port
        _save_ports()


def get_port(name: str) -> int | None:
    return _ports.get(name)


def is_running(name: str) -> bool:
    port = _ports.get(name)
    return bool(port and not _port_is_free(port))


def wait_for_api(name: str, port: int, timeout: int = 30) -> bool:
    """
    Poll /health until it responds, OR bail out as soon as the process itself
    has already exited — a compile/build failure typically exits Maven or
    uvicorn within seconds, and there's no reason to keep polling a port that
    will never open for the rest of a (Java-sized, up to 120s) timeout once
    the process is already dead.
    """
    import urllib.request as _ur
    import urllib.error as _ue

    deadline = time.time() + timeout
    while time.time() < deadline:
        proc = _procs.get(name)
        if proc is not None and proc.poll() is not None:
            return False
        try:
            _ur.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
            return True
        except _ue.HTTPError:
            return True
        except Exception:
            time.sleep(0.5)
    return False


def seed_database(name: str, project_dir: Path, language: str, force: bool = False,
                   known_db_path: Path | None = None) -> str:
    """
    Seed the generated app's own SQLite file directly via Python's stdlib
    sqlite3, deliberately NOT relying on Spring Boot's own data.sql auto-run
    (needed two specific properties set correctly and still hit a JDBC-driver
    timestamp-parsing quirk on read) or any FastAPI-side seeding code. Call
    once the app is confirmed up (wait_for_api returned True) — the tables
    only exist after the app's own startup (Hibernate ddl-auto / SQLAlchemy
    create_all), not before. Runs at most once per project ever, guarded by
    the same .seeded marker the old Spring-driven approach used.

    Returns a short, human-readable outcome string — the caller surfaces this
    in the Build Log via _progress(), since seeding happens after
    orchestrator.generate() has already returned and isn't part of any stage
    the pipeline itself reports on. Without that, a missing/failed seed step
    was invisible everywhere except this function's own print() (which
    doesn't get captured into server.log or the Build Log either), which was
    exactly why the empty-database case that motivated this function existed
    without any visible explanation the first time it happened.

    force=True bypasses the .seeded marker check — used by the caller's own
    repair loop (uigen_agent.py's _seed_new_pipeline_backend) to retry once
    the seed SQL has been corrected, since the marker is written up front
    (below) regardless of whether the attempt that follows actually
    succeeds, so a plain second call would otherwise always report
    "skipped (already seeded previously)" instead of really retrying.

    known_db_path: an explicit, ALREADY-KNOWN-CORRECT db file path, passed
    straight through to _find_app_db_file. Only WebUIGenerator's own
    launcher can supply this (it unconditionally overrides DB_PATH via an
    env var before starting the process, via java_backend_db_path — see
    that function's docstring), so only ITS call site
    (_seed_new_pipeline_backend) passes it. WebAPIGenerator's OWN launcher
    (start_api_project, this file) never sets that env var — a standalone
    WebAPIGenerator project's real db path is whatever the LLM's own config
    happened to choose, which only _find_app_db_file's existing regex/glob
    detection can discover. Defaulting to None keeps that call site's
    behavior completely unchanged.
    """
    seeded_marker = project_dir / ".seeded"
    if seeded_marker.exists() and not force:
        return "skipped (already seeded previously)"
    seeded_marker.write_text("ok", encoding="utf-8")

    seed_path = project_dir / ("src/main/resources/data.sql" if language == "java" else "seed_data.sql")
    if not seed_path.exists():
        return f"skipped — no seed file found at {seed_path.name}"

    db_file = _find_app_db_file(project_dir, language, known_db_path=known_db_path)
    if not db_file:
        return "skipped — no .db file found yet"

    import sqlite3
    try:
        conn = sqlite3.connect(str(db_file))
        try:
            # SQLite doesn't enforce foreign keys per connection unless asked —
            # without this, a batch that failed to produce a parent entity's
            # rows (see _coerce_files' bare-string handling) lets every child
            # row referencing it insert successfully anyway, leaving a
            # silently-broken database instead of a loud, diagnosable failure
            # right here at seed time.
            conn.execute("PRAGMA foreign_keys = ON")
            conn.executescript(seed_path.read_text(encoding="utf-8"))
            conn.commit()
        finally:
            conn.close()
        return f"seeded {db_file.name} from {seed_path.name}"
    except Exception as e:
        return f"failed — {e}"


def apply_pending_migrations(name: str, project_dir: Path, language: str) -> str:
    """
    Apply refine()'s recorded ALTER TABLE statements (migrations_pending.sql)
    directly against the app's own live SQLite file. Java never writes this
    file at all — Hibernate's spring.jpa.hibernate.ddl-auto=update already
    adds new @Column fields to the live table automatically on restart, so
    there's nothing for this function to do there. Python has no equivalent
    (SQLAlchemy's create_all() only creates missing tables, never alters an
    existing one), so refine() records the ALTER statements here instead;
    call this once, right after a Python refine's restart confirms the app
    is back up, same "bypass the app's own lifecycle" reasoning as
    seed_database — the table has to exist first, and Hibernate/SQLAlchemy
    both create tables only during their own app's startup.
    """
    if language != "python":
        return "skipped (Java applies new columns automatically via ddl-auto=update)"

    migrations_path = project_dir / "migrations_pending.sql"
    if not migrations_path.exists():
        return "skipped (no pending migrations)"
    sql = migrations_path.read_text(encoding="utf-8").strip()
    if not sql:
        migrations_path.unlink(missing_ok=True)
        return "skipped (no pending migrations)"

    db_file = _find_app_db_file(project_dir, language)
    if not db_file:
        return "skipped — no .db file found"

    import sqlite3
    try:
        conn = sqlite3.connect(str(db_file))
        try:
            conn.executescript(sql)
            conn.commit()
        finally:
            conn.close()
        count = sql.upper().count("ALTER TABLE")
        migrations_path.unlink(missing_ok=True)
        return f"applied {count} migration statement(s) to {db_file.name}"
    except Exception as e:
        return f"failed — {e}"


def java_backend_db_path(backend_dir: Path) -> Path:
    """
    The ONE place that decides where a WebUIGenerator-launched Java
    backend's real SQLite file lives — WebUIGenerator's own launcher
    (uigen_agent.py's _start_java_api_server) sets the DB_PATH environment
    variable to exactly this path before starting the process, which Spring
    resolves ahead of whatever default the LLM wrote into
    application.properties (env vars beat properties-file values). Both the
    launcher and _find_app_db_file below call this SAME function instead of
    each independently hardcoding "data.db" as a literal string — that
    duplication is exactly how a real split-brain happened: the LLM's own
    application.properties declared `DB_PATH=./data/wealth-advisor.db`,
    genuinely unrelated to this path, and only worked out by luck because
    _find_app_db_file's regex detection missed it and fell back to a glob
    that happened to land on the right file anyway.
    """
    return backend_dir / "data.db"


def _find_app_db_file(project_dir: Path, language: str, known_db_path: Path | None = None) -> Path | None:
    """
    Find the SQLite file the running app itself actually connects to — by
    reading its configured path, not by globbing *.db and hoping there's only
    one. There often isn't: usage.db (the deterministic rate-limiting/usage
    database) always sits in the same directory, and regenerating into an
    existing project folder without deleting it first can leave a
    differently-named .db file behind from an earlier attempt, since the
    bootstrap call picks its own filename fresh each generation rather than a
    fixed one — observed directly (automotive_dealership.db from the current
    generation, dealership.db orphaned from an earlier one, both matching
    "*.db"). Falls back to a glob, excluding usage.db, only if the configured
    path can't be determined at all.

    known_db_path: skip all of the detection below and use this path
    directly if it exists — see seed_database's docstring for exactly which
    callers may pass this and why (only ones that themselves control the
    env var Spring actually resolves DB_PATH from; guessing the same path
    here for a caller that DOESN'T control it could return a stale .db file
    from an earlier generation instead of letting the regex/glob detection
    below find the real current one).
    """
    if known_db_path is not None and known_db_path.exists():
        return known_db_path

    import re as _re

    if language == "java":

        # The LLM picks application.properties (key=value) OR
        # application.yml/.yaml (nested key: value) — check both syntaxes
        # against whichever of the three files actually exists, rather than
        # assuming .properties. Reproduced directly: a real generation used
        # .yml, which this used to silently miss entirely, falling through
        # to the *.db glob before the app had ever created any .db file —
        # "no seed file found" was never the issue, this was.
        for config_name, pattern in (
            ("application.properties", r"spring\.datasource\.url\s*=\s*jdbc:sqlite:(\S+)"),
            ("application.yml", r"url:\s*jdbc:sqlite:(\S+)"),
            ("application.yaml", r"url:\s*jdbc:sqlite:(\S+)"),
        ):
            config_path = project_dir / "src/main/resources" / config_name
            if not config_path.exists():
                continue
            m = _re.search(pattern, config_path.read_text(encoding="utf-8"))
            if m:
                # Strip any ?foreign_keys=true (or other) query string the URL
                # may carry — see _ensure_java_sqlite_foreign_keys_enabled —
                # it's a connection param, not part of the file path.
                candidate = project_dir / m.group(1).split("?")[0]
                if candidate.exists():
                    return candidate

        # Fallback: no spring.datasource.url in either properties/yaml file at
        # all — reproduced directly: a real generation instead wired its
        # DataSource entirely in Java (a @Bean method calling
        # DataSourceBuilder...url("jdbc:sqlite:./data/autopulse.db")), which
        # is a perfectly valid, equally common way to configure a Spring
        # datasource that the properties-file check above has no way to see.
        # Scan Java source for the same literal instead. Requires at least
        # one character between "sqlite:" and the closing quote so a
        # string-concatenation call (e.g. "jdbc:sqlite:" + DB_PATH, used by
        # the unrelated usage-tracking DB) doesn't match — there's no
        # literal path there for this regex to extract.
        java_src = project_dir / "src/main/java"
        if java_src.exists():
            for java_file in java_src.rglob("*.java"):
                content = java_file.read_text(encoding="utf-8", errors="ignore")
                m = _re.search(r'jdbc:sqlite:([^"]+)"', content)
                if m:
                    candidate = project_dir / m.group(1).split("?")[0]
                    if candidate.exists():
                        return candidate
                # Still no literal — a third, equally common shape: the
                # datasource URL is built by concatenating a @Value-injected
                # field (e.g. .setUrl("jdbc:sqlite:" + sqlitePath)), which
                # the literal-string regex above can never match by design.
                # Spring's ${key:default} placeholder syntax always carries
                # its OWN literal fallback value right there in the
                # annotation, though, regardless of what property NAME the
                # LLM chose (observed varying freely across generations:
                # DB_PATH one run, app.sqlite.path the next) — parse that
                # default out directly instead of needing to know the name.
                for vm in _re.finditer(r'@Value\s*\(\s*"\$\{[\w.]+:([^}"]+)\}"\s*\)', content):
                    candidate = project_dir / vm.group(1).split("?")[0]
                    if candidate.exists():
                        return candidate
    else:
        db_setup = project_dir / "src/database.py"
        if db_setup.exists():
            m = _re.search(r"sqlite(?:\+\w+)?:///(\S+?)[\"']", db_setup.read_text(encoding="utf-8"))
            if m:
                candidate = project_dir / m.group(1)
                if candidate.exists():
                    return candidate

    # Recursive, not top-level-only — reproduced directly: a real generation's
    # @Value default put the db file under a `data/` subdirectory
    # (./data/wealth-advisor.db), which a plain glob("*.db") at project_dir's
    # own top level can never see, even as a last resort.
    candidates = [p for p in project_dir.rglob("*.db") if p.name != "usage.db"]
    return candidates[0] if candidates else None
