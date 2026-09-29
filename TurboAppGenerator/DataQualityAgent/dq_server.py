"""
Data Quality Agent's own FastAPI router -- profiles a data source, generates
a Python or Java data-quality-check project, and executes it, all under
prefix "/data-quality" (mounted by API/server.py). Named dq_server, not
server, for the same sys.modules-collision reason LandDAgent's own module
is named l_and_d_server (see API/server.py's comment on that).

Generation and execution both run in a background thread and are polled
(GET .../runs/{run_id}/status) -- same reasoning as every other agent in
this app: an LLM call or a subprocess run inside an `async def` route would
block this whole process's single-threaded event loop for every other
request until it finished.
"""

import json
import re
import shutil
import sys
import threading
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

DQ_DIR = Path(__file__).resolve().parent
LIBRARY_DIR = DQ_DIR / "library"
LIBRARY_DIR.mkdir(exist_ok=True)

if str(DQ_DIR) not in sys.path:
    sys.path.insert(0, str(DQ_DIR))
from run import (  # noqa: E402
    DB_TYPES, LANGUAGES, PARQUET_LANGUAGES, _run_timeout_seconds, check_entry_exists, fetch_s3_bytes, generate_code,
    parse_dq_result, profile_database, profile_delimited, profile_excel, profile_parquet, run_java, run_python,
    strip_wrapping_quotes, validate_java, validate_python,
)

_CONTENT_AGENTS_DIR = DQ_DIR.parent / "ContentAgents"
if str(_CONTENT_AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_CONTENT_AGENTS_DIR))
from common.claude_cli import ClaudeCliError  # noqa: E402

router = APIRouter()

RUNS: dict[str, dict] = {}


def _append_log(run_id: str, line: str) -> None:
    run = RUNS.get(run_id)
    if run is not None:
        run["log"].append(line)


def _item_dir(item_id: str) -> Path:
    d = LIBRARY_DIR / item_id
    if not d.exists():
        raise HTTPException(404, "Unknown Data Quality item")
    return d


def _read_item(item_id: str) -> dict:
    item_dir = _item_dir(item_id)
    info = json.loads((item_dir / "item.json").read_text(encoding="utf-8"))
    files = []
    files_dir = item_dir / "files"
    if files_dir.exists():
        for f in sorted(files_dir.rglob("*")):
            # Skip __pycache__/*.pyc, .class, .deps_installed marker etc. --
            # binary/build artifacts that running/validating the generated
            # code leaves behind, never something to show or zip up.
            if "__pycache__" in f.parts or "target" in f.parts or f.suffix in (".pyc", ".class") or f.name == ".deps_installed":
                continue
            if f.is_file():
                files.append({"path": str(f.relative_to(files_dir)).replace("\\", "/"),
                              "content": f.read_text(encoding="utf-8", errors="replace")})
    last_result = None
    result_path = item_dir / "last_result.json"
    if result_path.exists():
        last_result = json.loads(result_path.read_text(encoding="utf-8"))
    return {**info, "files": files, "last_result": last_result}


def _uploaded_source_path(item_dir: Path) -> Path | None:
    matches = list(item_dir.glob("source_data.*"))
    return matches[0] if matches else None


# ── Generate ──────────────────────────────────────────────────────────────

def _run_generate_job(run_id: str, item_id: str, form: dict, file_bytes: bytes | None, file_ext: str | None) -> None:
    run = RUNS[run_id]
    on_progress = lambda line: _append_log(run_id, line)  # noqa: E731
    try:
        source_kind = form["source_kind"]
        language = form["language"]
        on_progress("Profiling the data source...")

        extra: dict = {}
        if source_kind in ("excel", "delimited", "parquet"):
            data = file_bytes
            if form.get("s3_path"):
                on_progress(f"Fetching {form['s3_path']} from S3...")
                data = fetch_s3_bytes(form["s3_path"])
            if not data:
                raise ValueError("No file was uploaded and no S3 path was given.")
            if source_kind == "excel":
                profile = profile_excel(data, form["has_header"], form.get("pasted_columns", ""))
                extra["has_header"] = form["has_header"]
            elif source_kind == "delimited":
                profile = profile_delimited(data, form.get("delimiter") or ",", form["has_header"], form.get("pasted_columns", ""))
                extra["delimiter"] = form.get("delimiter") or ","
                extra["has_header"] = form["has_header"]
            else:
                # Parquet's schema is embedded in the file -- no
                # has_header/pasted_columns concept applies.
                profile = profile_parquet(data)
        else:
            profile = profile_database(
                form["db_type"], form.get("host", ""), form.get("port", ""), form.get("database", ""),
                form.get("username", ""), form.get("password", ""), form.get("table", ""), form.get("pasted_schema", ""),
            )
            extra["db_type"] = form["db_type"]
            extra["table"] = form.get("table", "")
            if profile.get("source") == "pasted_schema_fallback":
                on_progress(f"Live DB connection failed ({profile.get('connection_error', 'unknown error')[:150]}) -- using pasted schema instead.")

        code = generate_code(profile, form["rules"], language, source_kind, extra, on_progress=on_progress)

        item_dir = LIBRARY_DIR / item_id
        files_dir = item_dir / "files"
        files_dir.mkdir(parents=True)
        for f in code["files"]:
            path = files_dir / f["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f["content"], encoding="utf-8")

        if file_bytes and source_kind in ("excel", "delimited", "parquet") and not form.get("s3_path"):
            (item_dir / f"source_data.{file_ext or 'bin'}").write_bytes(file_bytes)

        on_progress("Checking the generated code compiles...")
        validation_error = validate_python(files_dir) if language == "python" else validate_java(files_dir)
        if validation_error is None:
            validation_error = check_entry_exists(files_dir, language, code["run"]["entry"])

        info = {
            "item_id": item_id, "title": form["title"],  # == the project name (see create_item's validation)
            "source_kind": source_kind, "language": language, "rules": form["rules"],
            "run": code["run"], "created_at": datetime.now(timezone.utc).isoformat(),
            "source_meta": {k: v for k, v in {**form, "password": None}.items()
                             if k not in ("rules", "source_kind", "language", "title")},
            "validation_error": validation_error,
        }
        if form.get("save_credentials") and source_kind == "database" and form.get("password"):
            (item_dir / "connection.json").write_text(json.dumps({"password": form["password"]}), encoding="utf-8")
            info["credentials_saved"] = True

        (item_dir / "item.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
        run["result"] = _read_item(item_id)
        run["status"] = "complete"
    except ClaudeCliError as exc:
        run["error"] = str(exc)
        run["status"] = "error"
    except Exception as exc:
        run["error"] = str(exc)
        run["status"] = "error"


_PROJECT_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


@router.post("/api/items")
async def create_item(
    project_name: str = Form(...),
    source_kind: str = Form(...), language: str = Form(...), rules: str = Form(...),
    file: UploadFile | None = None, s3_path: str = Form(""),
    has_header: bool = Form(True), pasted_columns: str = Form(""), delimiter: str = Form(","),
    db_type: str = Form(""), host: str = Form(""), port: str = Form(""), database: str = Form(""),
    username: str = Form(""), password: str = Form(""), table: str = Form(""), pasted_schema: str = Form(""),
    save_credentials: bool = Form(False),
):
    project_name = project_name.strip()
    if not project_name:
        raise HTTPException(400, "A project name is required.")
    if not _PROJECT_NAME_RE.match(project_name):
        raise HTTPException(400, "Project name can only contain letters, numbers, hyphens, and underscores -- no spaces (it becomes the folder name on disk).")
    if (LIBRARY_DIR / project_name).exists():
        raise HTTPException(400, f"A project named '{project_name}' already exists -- pick a different name.")
    if source_kind not in ("excel", "delimited", "parquet", "database"):
        raise HTTPException(400, f"Unknown source_kind '{source_kind}'")
    if language not in LANGUAGES:
        raise HTTPException(400, f"Unknown language '{language}'")
    if source_kind == "parquet" and language not in PARQUET_LANGUAGES:
        raise HTTPException(400, "Parquet sources only support Python -- Java Parquet support needs a heavy extra dependency that isn't wired up here.")
    if not rules.strip():
        raise HTTPException(400, "Data quality rules are required.")
    if source_kind == "database" and db_type not in DB_TYPES:
        raise HTTPException(400, f"Unknown db_type '{db_type}'")
    if source_kind in ("excel", "delimited", "parquet") and not file and not s3_path.strip():
        raise HTTPException(400, "Either upload a file or provide an S3 path.")

    file_bytes = await file.read() if file else None
    file_ext = Path(file.filename).suffix.lstrip(".") if file and file.filename else None

    # Windows Explorer's "Copy as path" wraps paths in literal double
    # quotes -- a real user pasted exactly that into the SQLite database
    # path field and it broke both profiling and execution. Strip it here,
    # once, so every downstream use (profiling now, execution later via
    # the saved source_meta) sees the clean path.
    s3_path = strip_wrapping_quotes(s3_path)
    host = strip_wrapping_quotes(host)
    database = strip_wrapping_quotes(database)

    form = dict(source_kind=source_kind, language=language, rules=rules, title=project_name, s3_path=s3_path,
                has_header=has_header, pasted_columns=pasted_columns, delimiter=delimiter,
                db_type=db_type, host=host, port=port, database=database, username=username, password=password,
                table=table, pasted_schema=pasted_schema, save_credentials=save_credentials)

    # The project name itself is the folder name (see _PROJECT_NAME_RE
    # above) -- not a random id -- per explicit request, so items are easy
    # to find on disk by name.
    item_id = project_name
    run_id = uuid.uuid4().hex[:12]
    RUNS[run_id] = {"status": "running", "log": [], "result": None, "error": None}
    threading.Thread(target=_run_generate_job, daemon=True, args=(run_id, item_id, form, file_bytes, file_ext)).start()
    return JSONResponse({"run_id": run_id})


@router.get("/api/items/runs/{run_id}/status")
async def item_run_status(run_id: str):
    run = RUNS.get(run_id)
    if run is None:
        raise HTTPException(404, "Unknown run")
    return JSONResponse(run)


@router.get("/api/items")
async def list_items():
    items = []
    for d in LIBRARY_DIR.iterdir():
        info_path = d / "item.json"
        if info_path.exists():
            info = json.loads(info_path.read_text(encoding="utf-8"))
            items.append({k: info.get(k) for k in ("item_id", "title", "source_kind", "language", "created_at")})
    items.sort(key=lambda it: it.get("created_at", ""), reverse=True)
    return JSONResponse({"items": items})


@router.get("/api/items/{item_id}")
async def get_item(item_id: str):
    return JSONResponse(_read_item(item_id))


@router.put("/api/items/{item_id}/file")
async def update_file(item_id: str, path: str = Form(...), content: str = Form(...)):
    item_dir = _item_dir(item_id)
    file_path = (item_dir / "files" / path).resolve()
    if not str(file_path).startswith(str((item_dir / "files").resolve())):
        raise HTTPException(400, "Invalid file path.")
    file_path.write_text(content, encoding="utf-8")
    return JSONResponse({"ok": True})


# ── Run ───────────────────────────────────────────────────────────────────

def _run_execute_job(run_id: str, item_id: str, password: str | None) -> None:
    run = RUNS[run_id]
    on_progress = lambda line: _append_log(run_id, line)  # noqa: E731
    try:
        item_dir = _item_dir(item_id)
        info = json.loads((item_dir / "item.json").read_text(encoding="utf-8"))
        files_dir = item_dir / "files"
        language = info["language"]
        run_spec = info["run"]
        entry = run_spec["entry"]
        env_vars: dict[str, str] = {}
        size_bytes = 0

        if info["source_kind"] in ("excel", "delimited", "parquet"):
            source_path = _uploaded_source_path(item_dir)
            meta = info.get("source_meta", {})
            if meta.get("s3_path"):
                on_progress("Re-fetching the source file from S3...")
                data = fetch_s3_bytes(meta["s3_path"])
                ext = meta["s3_path"].rsplit(".", 1)[-1] if "." in meta["s3_path"] else "bin"
                source_path = item_dir / f"_s3_fetch.{ext}"
                source_path.write_bytes(data)
            if not source_path or not source_path.exists():
                raise ValueError("Original source file is no longer available -- regenerate this item.")
            size_bytes = source_path.stat().st_size
            # Env var, not a CLI arg -- a real path (e.g. this very repo's
            # own OneDrive path) can contain spaces, which Maven's
            # -Dexec.args silently mangles. See run.py's run_java docstring.
            env_vars["DQ_SOURCE_FILE"] = str(source_path)
        else:
            meta = info.get("source_meta", {})
            conn_path = item_dir / "connection.json"
            real_password = password
            if not real_password and conn_path.exists():
                real_password = json.loads(conn_path.read_text(encoding="utf-8")).get("password")
            env_vars = {
                "DB_TYPE": meta.get("db_type", ""), "DB_HOST": meta.get("host", ""),
                "DB_PORT": meta.get("port", ""), "DB_NAME": meta.get("database", ""),
                "DB_USER": meta.get("username", ""), "DB_PASSWORD": real_password or "",
                "DB_TABLE": meta.get("table", ""),
            }

        on_progress(f"Running the {language} checks{' (this file is large -- may take a while)' if size_bytes > 5_000_000 else ''}...")
        timeout = _run_timeout_seconds(size_bytes)
        exec_result = run_python(files_dir, entry, env_vars, timeout) if language == "python" \
            else run_java(files_dir, entry, env_vars, timeout)

        dq_result = parse_dq_result(exec_result["stdout"])
        result = {**exec_result, "dq_result": dq_result, "ran_at": datetime.now(timezone.utc).isoformat()}
        (item_dir / "last_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        run["result"] = _read_item(item_id)
        run["status"] = "complete"
    except Exception as exc:
        run["error"] = str(exc)
        run["status"] = "error"


@router.post("/api/items/{item_id}/run")
async def run_item(item_id: str, password: str = Form("")):
    _item_dir(item_id)
    run_id = uuid.uuid4().hex[:12]
    RUNS[run_id] = {"status": "running", "log": [], "result": None, "error": None}
    threading.Thread(target=_run_execute_job, daemon=True, args=(run_id, item_id, password or None)).start()
    return JSONResponse({"run_id": run_id})


@router.put("/api/items/{item_id}/rename")
async def rename_item(item_id: str, new_name: str = Form(...)):
    """Renaming is just a folder rename + an item.json update -- safe to do
    freely, unlike renaming a Java package/class. The project name is
    never fed into generate_code()'s prompt (see create_item/_run_generate_
    job above), so nothing inside the generated files -- package names,
    class names, pom.xml's artifactId, anything -- ever references it."""
    new_name = new_name.strip()
    if not new_name:
        raise HTTPException(400, "A project name is required.")
    if not _PROJECT_NAME_RE.match(new_name):
        raise HTTPException(400, "Project name can only contain letters, numbers, hyphens, and underscores -- no spaces (it becomes the folder name on disk).")
    old_dir = _item_dir(item_id)
    if new_name == item_id:
        return JSONResponse(_read_item(item_id))
    new_dir = LIBRARY_DIR / new_name
    if new_dir.exists():
        raise HTTPException(400, f"A project named '{new_name}' already exists -- pick a different name.")

    old_dir.rename(new_dir)
    info_path = new_dir / "item.json"
    info = json.loads(info_path.read_text(encoding="utf-8"))
    info["item_id"] = new_name
    info["title"] = new_name
    info_path.write_text(json.dumps(info, indent=2), encoding="utf-8")
    return JSONResponse(_read_item(new_name))


@router.delete("/api/items/{item_id}")
async def delete_item(item_id: str):
    shutil.rmtree(_item_dir(item_id), ignore_errors=True)
    return JSONResponse({"ok": True})


@router.get("/api/items/{item_id}/download")
async def download_item(item_id: str):
    item_dir = _item_dir(item_id)
    files_dir = item_dir / "files"
    zip_path = item_dir / "project.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files_dir.rglob("*"):
            if "__pycache__" in f.parts or "target" in f.parts or f.suffix in (".pyc", ".class") or f.name == ".deps_installed":
                continue
            if f.is_file():
                zf.write(f, arcname=str(f.relative_to(files_dir)))
    info = json.loads((item_dir / "item.json").read_text(encoding="utf-8"))
    slug = "".join(c if c.isalnum() or c in "-_ " else "" for c in info.get("title", "dq-project")).strip().replace(" ", "-") or "dq-project"
    return FileResponse(zip_path, filename=f"{slug}.zip", media_type="application/zip")
