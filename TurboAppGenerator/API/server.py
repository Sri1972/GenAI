#!/usr/bin/env python3
"""TurboUIGen — FastAPI server. Serves the UI and exposes the agent as a REST API."""

import asyncio
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# sys.path is configured by run.py before this module is loaded.
# WebUIGenerator/, WebAPIGenerator/ and FigmaMockupGenerator/ are already on sys.path.

# Ensure .env is loaded even if this module is imported outside of run.py
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import MCP_URL, TURBOUI_PORT, project_url as _project_url

from agents.uigen_agent import (
    delete_project,
    generate_project,
    list_projects,
    registry_remove,
    registry_upsert,
    start_project,
    stop_project,
)

# Per-request progress log: request_id -> list of messages
_progress_logs: dict[str, list[str]] = {}
# Latest active request id (for polling without knowing the id)
_latest_request_id: str = ""
# Per-project latest request id (for tab-scoped polling)
_project_request_ids: dict[str, str] = {}

# Job state for async/persistent generation
# Maps request_id -> { status, project_name, result, error }
_jobs: dict[str, dict] = {}
_JOBS_DIR: Path | None = None  # initialized after GENERATED_DIR available

# Delete progress: project_slug -> list of step messages, so the UI can show
# real activity instead of an unexplained multi-second wait (delete_project()
# can legitimately take up to ~90s: stopping the dev server, releasing Vite/
# OneDrive file locks, removing node_modules, retrying rmtree).
_delete_progress_logs: dict[str, list[str]] = {}

# Per-project locks guarding each project's .buildlog.json read-modify-write
# (see _append_buildlog below and WebAPIGenerator's identical fix in
# api_agents/api_registry.py) — without this, two concurrent writers to the
# same project's buildlog race on read-then-write and one silently clobbers
# the other's entry.
_buildlog_locks: dict[str, threading.Lock] = {}
_buildlog_locks_guard = threading.Lock()


def _lock_for_buildlog(project_name: str) -> threading.Lock:
    with _buildlog_locks_guard:
        return _buildlog_locks.setdefault(project_name, threading.Lock())
# project_slug -> True while a delete is actively in-flight. Checked by
# api_generate so a "from scratch" regeneration can't start writing into a
# directory a concurrent delete is still tearing down (see api_delete for the
# matching check in the other direction) — this is what silently wiped out a
# freshly-completed generation before this pair of guards existed.
_deletes_in_progress: set[str] = set()

app = FastAPI(title="TurboUIGen")
_executor = ThreadPoolExecutor(max_workers=4)

_ROOT   = Path(__file__).resolve().parent.parent   # TurboUIGen/
UI_DIST = _ROOT / "UI" / "dist"
UI_DEV  = _ROOT / "UI" / "index.html"


@app.on_event("startup")
async def _startup_cleanup():
    """Remove orphaned entries from .ports.json that no longer have a directory on disk."""
    try:
        from agents.uigen_agent import GENERATED_DIR, _dev_ports, _api_ports, _save_ports
        import json as _json_su
        from config import PORTS_FILE
        if not PORTS_FILE.exists():
            return
        existing_dirs = {d.name for d in GENERATED_DIR.iterdir() if d.is_dir()} if GENERATED_DIR.exists() else set()
        orphaned_vite = [k for k in list(_dev_ports.keys()) if k not in existing_dirs]
        orphaned_api = [k for k in list(_api_ports.keys()) if k not in existing_dirs]
        for k in orphaned_vite:
            _dev_ports.pop(k, None)
        for k in orphaned_api:
            _api_ports.pop(k, None)
        if orphaned_vite or orphaned_api:
            _save_ports()
            print(f"[startup] Cleaned {len(orphaned_vite) + len(orphaned_api)} orphaned port entries", flush=True)
    except Exception as e:
        print(f"[startup] Port cleanup skipped: {e}", flush=True)

    # Jobs are persisted to .jobs/<id>.json with their last-known status, but the
    # live progress log a client polls (/api/generate/progress/{id}) only ever
    # lives in memory. If the server process dies or restarts while a job's
    # background thread is running, the persisted file is left saying "running"
    # forever — nothing else will ever update it — while the log it depends on
    # has reset to empty. A job cannot possibly still be running immediately
    # after a fresh process start, so reconcile that here rather than leaving it
    # to accumulate as a permanent zombie that the UI shows as stuck at 0 progress.
    try:
        import json as _json_jobs
        jobs_dir = _get_jobs_dir()
        stale = 0
        for f in jobs_dir.glob("*.json"):
            try:
                job = _json_jobs.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if job.get("status") == "running":
                job["status"] = "failed"
                job["error"] = "Server restarted while this job was running — no result was saved. Please try again."
                f.write_text(_json_jobs.dumps(job, indent=2, ensure_ascii=False), encoding="utf-8")
                stale += 1
        if stale:
            print(f"[startup] Marked {stale} stale 'running' job(s) as failed (server was restarted mid-generation)", flush=True)
    except Exception as e:
        print(f"[startup] Stale job cleanup skipped: {e}", flush=True)

    # Product Forge (mounted below, under /forge) persists each session as its
    # own JSON file with a "status" field, separately from the .jobs/ store
    # above — same "stale running after a restart" problem, but nothing
    # reconciles it today, so a session left at "running" by a killed process
    # shows as permanently "Running" in the project list (and its Delete
    # button stays disabled, since the UI derives that from this same status)
    # forever, since Product Forge's generation threads are in-process and
    # can't possibly have survived the restart. Mirrors the job cleanup above.
    try:
        import json as _json_forge
        from datetime import datetime as _dt_forge
        from orchestrator import SESSIONS_DIR as _FORGE_SESSIONS_DIR
        stale = 0
        for f in _FORGE_SESSIONS_DIR.glob("*.json"):
            try:
                data = _json_forge.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if data.get("status") == "running":
                data["status"] = "paused"
                data["updated_at"] = _dt_forge.now().isoformat()
                f.write_text(_json_forge.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                stale += 1
        if stale:
            print(f"[startup] Marked {stale} stale 'running' Product Forge session(s) as 'paused' (server was restarted mid-run)", flush=True)
    except Exception as e:
        print(f"[startup] Product Forge session cleanup skipped: {e}", flush=True)


class GenerateRequest(BaseModel):
    prompt: str
    project_name: str | None = None
    figma_url: str | None = None
    instructions: str = ""   # optional Markdown instructions appended to prompt
    architecture: dict | None = None  # pre-approved architecture from /api/draft (skips Stage 1)
    backend_type: str = "python"  # "python" (FastAPI) or "java" (Spring Boot)
    mode: str = "webapp"  # "webapp" (React + backend) or "api" (standalone API)
    api_options: dict | None = None  # API mode config: {language, auth_type, rate_limit, database, endpoints, include_docker, include_tests}


class DraftRequest(BaseModel):
    prompt: str
    project_name: str | None = None
    instructions: str = ""

class RefineRequest(BaseModel):
    prompt: str
    project_name: str
    comment: str = ""         # optional user note shown in history
    instructions: str = ""    # optional Markdown instructions
    architecture: dict | None = None  # pre-approved architecture from /api/draft (uses pipeline instead of diff)
    backend_type: str = "python"  # "python" (FastAPI) or "java" (Spring Boot)

class CreateProjectRequest(BaseModel):
    name: str

class RenameProjectRequest(BaseModel):
    new_name: str

class ApiRefineRequest(BaseModel):
    prompt: str
    instructions: str = ""   # optional Markdown instructions appended to prompt
    comment: str = ""        # optional user note shown in history


class McpIntrospectSqliteRequest(BaseModel):
    dbPath: str


class McpIntrospectApiRequest(BaseModel):
    baseUrl: str
    username: str | None = None
    password: str | None = None


class McpIntrospectFromSpecRequest(BaseModel):
    baseUrl: str
    spec: dict


class McpGenerateRequest(BaseModel):
    projectName: str
    sourceType: str  # "datastore" | "api"
    sourceConfig: dict
    instructions: str = ""
    comment: str = ""        # optional user note shown in history


class McpGenerateFromInstructionsRequest(BaseModel):
    """Alternative entry point to MCP generation: no pre-built sourceConfig --
    the source (a database file path and/or an API base URL, with
    credentials if it needs auth) must already be stated concretely in
    `instructions` itself. See _run_mcp_generate_from_instructions."""
    projectName: str
    instructions: str
    comment: str = ""


class McpChatMessage(BaseModel):
    role: str
    content: str


class McpChatRequest(BaseModel):
    messages: list[McpChatMessage]


# ── Serve UI ──────────────────────────────────────────────────────────────────

if UI_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(UI_DIST / "assets")), name="assets")

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    # Production build
    if (UI_DIST / "index.html").exists():
        return FileResponse(UI_DIST / "index.html")
    # Dev fallback
    if UI_DEV.exists():
        return FileResponse(UI_DEV)
    return HTMLResponse("<h2>UI not built. Run: cd ui && npm install && npm run build</h2>")

@app.get("/logo.png")
async def serve_logo():
    """Serve the Mobility Global logo from UI/dist/logo.png."""
    logo = UI_DIST / "logo.png"
    if logo.exists():
        return FileResponse(str(logo), media_type="image/png")
    raise HTTPException(404, "Logo not found")

@app.get("/health")
async def health():
    from agents.llm import model_id
    return {"status": "ok", "model": model_id()}


# ── Global model picker (Header, all tabs) ───────────────────────────────────
# The actual choice lists now live in agents/llm.py (LITELLM_MODEL_CHOICES /
# BEDROCK_MODEL_CHOICES) — that's also where Product Forge's Draft Mode reads
# them from to rank by cost, so there's one source of truth instead of two
# copies that could drift apart.

@app.get("/api/models")
async def api_list_models():
    from agents.llm import LITELLM_MODEL_CHOICES, BEDROCK_MODEL_CHOICES, get_selected_model, is_using_fallback
    return {
        "litellm": LITELLM_MODEL_CHOICES,
        "bedrock": BEDROCK_MODEL_CHOICES,
        "current": get_selected_model(),
        "using_fallback": is_using_fallback(),
    }


class SelectModelRequest(BaseModel):
    provider: str
    model: str


@app.post("/api/models/select")
async def api_select_model(req: SelectModelRequest):
    from agents.llm import set_selected_model, check_model_reachable
    set_selected_model(req.provider, req.model)
    ok, error = check_model_reachable(req.provider, req.model)
    return {"ok": ok, "error": None if ok else error}


@app.get("/api/ds-info")
async def ds_info():
    """Return the active design system config — DS root path and Storybook URL."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config_ds import DS_ROOT, STORYBOOK_URL
    return {
        "ds_root": str(DS_ROOT),
        "storybook_url": STORYBOOK_URL,
    }


# ── Product Forge — a genuine part of this app now, not a mounted sub-app ──
# Not started or stopped separately; if TurboAppGenerator is running, so is
# this. A full copy of Product Forge's own source (agents/, backend/,
# config/ — see ../A2A/product-forge, the original standalone app this was
# copied from, left untouched) lives at ./ProductForge here.
#
# backend/app.py defines an APIRouter (not its own FastAPI app — deliberately
# changed from the original's `app = FastAPI(...)`, since a Mount would have
# kept it as a second, separate OpenAPI schema/docs page and a second app
# object; include_router below gives one unified schema instead, same as
# every other route in this file). Its own routes already have their OWN
# `/api/...` paths baked into every decorator (e.g. `/api/projects`, which
# collided outright with this platform's own Web UI project list at that
# exact path) — prefix="/forge" below (not "/api/forge" — that would stutter
# into "/api/forge/api/config" and, worse, silently fall through to this
# app's own SPA catch-all instead of a clean 404, since it's an unmatched
# path) is what actually resolves the collision, not an edit to app.py.
#
# Its frontend (a single static index.html, no build step) lives at
# UI/public/forge/ instead of inside ProductForge/ — see _forge_index below.
# It hardcodes an absolute `http://localhost:8010` base for every
# fetch()/EventSource() call, which doesn't exist as a listening port at all
# in this design — rewritten to /forge (matching the prefix below) in the
# served HTML only, never in the file on disk.
#
# Wrapped in try/except so a problem here (Product Forge missing, or its
# own import failing) can never take the rest of this platform down with it
# — same reasoning as every other "secondary feature" guard in this file.
_forge_mount_error: str | None = None
try:
    _FORGE_BACKEND_DIR = Path(__file__).resolve().parent.parent / "ProductForge" / "backend"
    if not (_FORGE_BACKEND_DIR / "app.py").exists():
        _forge_mount_error = f"Product Forge not found at {_FORGE_BACKEND_DIR}"
    else:
        if str(_FORGE_BACKEND_DIR) not in sys.path:
            sys.path.insert(0, str(_FORGE_BACKEND_DIR))
        from app import router as _forge_router  # noqa: E402  Product Forge's own routes, unmodified

        @app.get("/forge")
        @app.get("/forge/")
        async def _forge_index():
            # Copied verbatim into UI/dist/forge/ by the same `vite build`
            # that produces everything else this server serves — see
            # UI_DIST/logo.png just above for the same pattern.
            html = (UI_DIST / "forge" / "index.html").read_text(encoding="utf-8")
            return HTMLResponse(html.replace("http://localhost:8010", "/forge"))

        app.include_router(_forge_router, prefix="/forge")
except Exception as _e:
    _forge_mount_error = f"Product Forge failed to load: {_e}"


@app.get("/api/forge/status")
async def api_forge_status():
    return {"installed": _forge_mount_error is None, "error": _forge_mount_error}


# ── ContentAgents — its API only, not an embedded frontend. A full copy of
# ContentAgents' own source lives at ./ContentAgents here (the original
# standalone app at ../ContentAgents is left untouched). ui/server.py there
# exports an APIRouter (`router`), included below under prefix
# "/content-agents" for one unified OpenAPI schema instead of a second
# app/process — this backs the native "Utility Agents" tab in this app's own
# UI (see UI/src/hooks/contentAgentsApi.ts), which replaced an earlier
# iframe-based integration entirely, so there's no frontend/index route to
# serve here anymore, unlike Product Forge above. The "Workflow" tab used to
# live here too, but it orchestrates WebUIGenerator/WebAPIGenerator/
# MCPGenerator/ProductForge as much as it does ContentAgents, so it's its own
# top-level module now — see the Workflow mount block right below.
_content_agents_mount_error: str | None = None
try:
    _CONTENT_AGENTS_UI_DIR = Path(__file__).resolve().parent.parent / "ContentAgents" / "ui"
    if not (_CONTENT_AGENTS_UI_DIR / "server.py").exists():
        _content_agents_mount_error = f"ContentAgents not found at {_CONTENT_AGENTS_UI_DIR}"
    else:
        if str(_CONTENT_AGENTS_UI_DIR) not in sys.path:
            sys.path.insert(0, str(_CONTENT_AGENTS_UI_DIR))
        from server import router as _content_agents_router  # noqa: E402  ContentAgents' own routes, unmodified

        app.include_router(_content_agents_router, prefix="/content-agents")
except Exception as _e:
    _content_agents_mount_error = f"ContentAgents failed to load: {_e}"


@app.get("/api/content-agents/status")
async def api_content_agents_status():
    return {"installed": _content_agents_mount_error is None, "error": _content_agents_mount_error}


# ── Workflow — the DAG-of-agents engine behind the "Workflow" tab. Depends on
# ContentAgents (mounted just above) for its reader/creator agent packages and
# its library store, and reaches WebUIGenerator/WebAPIGenerator/MCPGenerator/
# ProductForge over HTTP loopback against this same process (unchanged either
# way), so mount order relative to ContentAgents doesn't matter. Included
# below under prefix "/workflows", distinct from ContentAgents' own
# "/content-agents" prefix.
_workflow_mount_error: str | None = None
try:
    _WORKFLOW_DIR = Path(__file__).resolve().parent.parent / "Workflow"
    if not (_WORKFLOW_DIR / "workflow_server.py").exists():
        _workflow_mount_error = f"Workflow not found at {_WORKFLOW_DIR}"
    else:
        if str(_WORKFLOW_DIR) not in sys.path:
            sys.path.insert(0, str(_WORKFLOW_DIR))
        from workflow_server import router as _workflow_router  # noqa: E402  Workflow's own routes, unmodified

        app.include_router(_workflow_router, prefix="/workflows")
except Exception as _e:
    _workflow_mount_error = f"Workflow failed to load: {_e}"


@app.get("/api/workflow/status")
async def api_workflow_status():
    return {"installed": _workflow_mount_error is None, "error": _workflow_mount_error}


# ── Pipeline info (agents + skills) — for the UI's "Agents & Skills" panel ──

_AGENT_DESCRIPTIONS = {
    "ux_architect":      "UX Architect — defines what pages to build and how they're structured",
    "data_architect":    "Data Architect — designs the data layer (schema, seed data, TypeScript types)",
    "react_ui":          "React UI Engineer — builds the React components (infra, pages, config)",
    "visual_design":     "Visual Design Engineer — builds D3 charts, maps, and shared visual components",
    "webui_integration_engineer": "WebUI Integration Engineer — connects the frontend to the backend API, fixes integration issues",
    "ai_genai":          "AI/GenAI Engineer — builds chat/LLM-powered pages",
}


@app.get("/api/pipeline-info")
async def api_pipeline_info():
    """Return the generation pipeline's agents (from orchestrator.STAGES) and
    available UI skills (from skills.registry.SKILL_REGISTRY), for display in
    the UI. Single source of truth — no duplicated agent/skill lists."""
    from agents.orchestrator import STAGES
    from agents.skills.registry import SKILL_REGISTRY

    agents = []
    seen = set()
    for stage in STAGES:
        for agent_id in stage["agents"]:
            if agent_id in seen:
                continue
            seen.add(agent_id)
            agents.append({
                "id": agent_id,
                "description": _AGENT_DESCRIPTIONS.get(agent_id, agent_id),
                "stages": [s["name"] for s in STAGES if agent_id in s["agents"]],
            })

    skills = [
        {
            "key": key,
            "description": meta.get("description", ""),
            "categories": meta.get("categories", []),
        }
        for key, meta in SKILL_REGISTRY.items()
    ]

    return {"agents": agents, "skills": skills}


# ── Draft Preview ────────────────────────────────────────────────────────────

@app.post("/api/draft")
async def api_draft(req: DraftRequest):
    """
    Run only Stage 1 (UX Architect) and return a Markdown wireframe preview.
    Fast (~5-10s), cheap (~4K tokens). User approves before full generation.
    """
    import asyncio
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            _executor,
            lambda: _run_draft(req),
        )
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))


def _run_draft(req: DraftRequest) -> dict:
    from agents.draft_preview import generate_draft
    result = generate_draft(
        prompt=req.prompt,
        instructions=req.instructions or "",
        project_name=req.project_name or None,
    )
    # Persist draft to project directory so it survives restarts
    _save_draft_to_disk(req.project_name or result.get("projectName", ""), result)
    return result


def _save_draft_to_disk(project_name: str, draft: dict):
    """Save draft JSON to .draft.json inside the project directory."""
    import json as _json, re as _re
    from agents.uigen_agent import GENERATED_DIR
    slug = _re.sub(r"[^a-z0-9-]", "-", project_name.lower()).strip("-")
    if not slug:
        return
    project_dir = GENERATED_DIR / slug
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / ".draft.json").write_text(_json.dumps(draft, indent=2), encoding="utf-8")


@app.get("/api/projects/{project_name}/draft")
async def api_get_draft(project_name: str):
    """Load a previously saved draft from disk."""
    import json as _json
    from agents.uigen_agent import GENERATED_DIR
    draft_file = GENERATED_DIR / project_name / ".draft.json"
    if not draft_file.exists():
        return None
    try:
        return _json.loads(draft_file.read_text(encoding="utf-8"))
    except Exception:
        return None


# ── API ───────────────────────────────────────────────────────────────────────

@app.get("/api/projects")
async def api_list():
    return list_projects()


@app.post("/api/projects/create")
async def api_create_project(req: CreateProjectRequest):
    import re
    from agents.uigen_agent import GENERATED_DIR
    name = re.sub(r"[^a-z0-9-]", "-", req.name.lower()).strip("-")
    if not name:
        raise HTTPException(400, "Invalid project name")
    project_dir = GENERATED_DIR / name
    project_dir.mkdir(parents=True, exist_ok=True)
    # Register with no app yet
    registry_upsert(name, title=name, hasApp=False, type="react", source="prompt",
                    sourceLabel="Instructions", figmaUrl="", prompt="")
    return {"name": name}


@app.post("/api/projects/{project_name}/rename")
async def api_rename_project(project_name: str, req: RenameProjectRequest):
    """Rename a project — updates folder, registry, ports, and any running servers."""
    import re
    from agents.uigen_agent import (
        GENERATED_DIR, _dev_ports, _api_ports, _dev_servers, _api_servers, _save_ports,
    )

    new_name = re.sub(r"[^a-z0-9-]", "-", req.new_name.lower()).strip("-")
    if not new_name:
        raise HTTPException(400, "Invalid new project name")
    if new_name == project_name:
        return {"name": new_name, "oldName": project_name}

    old_dir = GENERATED_DIR / project_name
    new_dir = GENERATED_DIR / new_name

    if not old_dir.exists():
        raise HTTPException(404, f"Project '{project_name}' not found")
    if new_dir.exists():
        raise HTTPException(409, f"Project '{new_name}' already exists")

    # Stop running servers first (they hold file locks)
    if project_name in _dev_servers:
        _dispatch_stop(project_name)

    # Rename directory
    old_dir.rename(new_dir)

    # Update ports
    if project_name in _dev_ports:
        _dev_ports[new_name] = _dev_ports.pop(project_name)
    if project_name in _api_ports:
        _api_ports[new_name] = _api_ports.pop(project_name)
    _save_ports()

    # Update registry — read old entry, remove, re-add under new name
    from agents.uigen_agent import _load_registry, _save_registry
    reg = _load_registry()
    entry = reg.pop(project_name, {})
    entry["name"] = new_name
    if entry.get("title") == project_name:
        entry["title"] = new_name
    reg[new_name] = entry
    _save_registry(reg)

    # Update per-project request tracking
    if project_name in _project_request_ids:
        _project_request_ids[new_name] = _project_request_ids.pop(project_name)

    # Update job files that reference the old project name
    import json as _json_rename
    jobs_dir = _get_jobs_dir()
    for job_file in jobs_dir.glob("*.json"):
        try:
            job_data = _json_rename.loads(job_file.read_text(encoding="utf-8"))
            if job_data.get("projectName") == project_name:
                job_data["projectName"] = new_name
                job_file.write_text(_json_rename.dumps(job_data, indent=2, ensure_ascii=False), encoding="utf-8")
                # Also update in-memory cache
                rid = job_file.stem
                if rid in _jobs:
                    _jobs[rid]["projectName"] = new_name
        except Exception:
            pass

    return {"name": new_name, "oldName": project_name}


def _append_history(project_name: str, event: str, detail: str = "",
                    figma_url: str = "", prompt: str = "", comment: str = "",
                    instructions: str = ""):
    """Append an event to the project's .history.json file. No truncation."""
    from agents.uigen_agent import GENERATED_DIR
    import json as _json
    from datetime import datetime, timezone
    history_file = GENERATED_DIR / project_name / ".history.json"
    try:
        history = _json.loads(history_file.read_text(encoding="utf-8")) if history_file.exists() else []
    except Exception:
        history = []
    entry = {
        "event":     event,
        "detail":    detail,
        "figmaUrl":  figma_url,
        "prompt":    prompt,      # full prompt, no truncation
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if comment:
        entry["comment"] = comment
    if instructions:
        entry["instructions"] = instructions
    history.append(entry)
    history_file.write_text(_json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")


def _append_buildlog(project_name: str, log_lines: list[str],
                     event: str = "", duration_s: float = 0.0):
    """Append a build run's log to .buildlog.json — oldest first, never truncated."""
    from agents.uigen_agent import GENERATED_DIR
    import json as _json
    from datetime import datetime, timezone
    buildlog_file = GENERATED_DIR / project_name / ".buildlog.json"
    with _lock_for_buildlog(project_name):
        try:
            runs = _json.loads(buildlog_file.read_text(encoding="utf-8")) if buildlog_file.exists() else []
        except Exception:
            runs = []
        runs.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event":     event,
            "duration_s": round(duration_s, 1),
            "lines":     log_lines,
        })
        buildlog_file.write_text(_json.dumps(runs, indent=2, ensure_ascii=False), encoding="utf-8")


def _generate_architecture(project_name: str, event: str = "Generated", backend_type: str = "python"):
    """Scan project files on disk and generate a .architecture.md document."""
    from agents.uigen_agent import GENERATED_DIR
    from datetime import datetime, timezone
    import re as _re_arch

    project_dir = GENERATED_DIR / project_name
    if not project_dir.exists():
        return

    arch_file = project_dir / ".architecture.md"

    # Detect backend type from disk
    bt_file = project_dir / "backend" / ".backend_type"
    if bt_file.exists():
        _bt_raw = bt_file.read_text(encoding="utf-8").strip()
        backend_type = "java" if "java" in _bt_raw else _bt_raw
    elif (project_dir / "backend" / "pom.xml").exists():
        backend_type = "java"

    # New-pipeline projects have a real .architecture.json with the live,
    # per-entity named-route endpoint list — the API Endpoints section below
    # is a stale /api/data/{table} guess that predates that pipeline, so it's
    # skipped here in favor of the live API & MCP panel the UI fetches separately.
    has_new_pipeline = (project_dir / "backend" / ".architecture.json").exists() or (project_dir / "api" / ".architecture.json").exists()

    # Scan pages from src/pages/
    pages_dir = project_dir / "src" / "pages"
    pages: list[str] = []
    if pages_dir.exists():
        pages = sorted(f.stem for f in pages_dir.iterdir() if f.suffix == ".tsx")

    # Scan shared components from src/components/
    comps_dir = project_dir / "src" / "components"
    components: list[str] = []
    if comps_dir.exists():
        components = sorted(f.name for f in comps_dir.iterdir() if f.suffix in (".tsx", ".ts"))

    # Scan hooks
    hooks_dir = project_dir / "src" / "hooks"
    hooks: list[str] = []
    if hooks_dir.exists():
        hooks = sorted(f.name for f in hooks_dir.iterdir() if f.suffix in (".ts", ".tsx"))

    # Parse schema.sql for table names
    tables: list[str] = []
    schema_paths = [
        project_dir / "api" / "schema.sql",
        project_dir / "backend" / "schema.sql",
        project_dir / "schema.sql",
    ]
    schema_content = ""
    for sp in schema_paths:
        if sp.exists():
            schema_content = sp.read_text(encoding="utf-8")
            break
    if schema_content:
        tables = _re_arch.findall(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", schema_content, _re_arch.IGNORECASE)

    # Build markdown
    lines = []
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines.append(f"# Architecture: {project_name}")
    lines.append("")
    lines.append(f"**Last updated:** {ts} ({event})")
    lines.append(f"**Backend:** {'Java Spring Boot (JDBC + SQLite)' if backend_type == 'java' else 'Python FastAPI (SQLite)'}")
    lines.append(f"**Frontend:** React 18 + TypeScript + Vite + Tailwind CSS")
    lines.append(f"**Pages:** {len(pages)} | **Tables:** {len(tables)} | **Components:** {len(components)}")
    lines.append("")

    # Component diagram
    lines.append("---")
    lines.append("## Component Overview")
    lines.append("")
    lines.append("```")
    lines.append("┌─────────────────────────────────────────────────────────────┐")
    lines.append("│                        FRONTEND                             │")
    lines.append("│  ┌─────────┐   ┌─────────────┐   ┌──────────────────────┐  │")
    lines.append("│  │  App.tsx │──▶│  Router      │──▶│  Pages (*.tsx)       │  │")
    lines.append("│  └─────────┘   └─────────────┘   └──────────┬───────────┘  │")
    lines.append("│                                              │              │")
    lines.append("│                              ┌───────────────┼───────────┐  │")
    lines.append("│                              │  Components   │  Hooks    │  │")
    lines.append("│                              └───────────────┼───────────┘  │")
    lines.append("│                                              │              │")
    lines.append("│                                     useApi() │              │")
    lines.append("└──────────────────────────────────────────────┼──────────────┘")
    lines.append("                                               │ /api/data/{table}")
    lines.append("┌──────────────────────────────────────────────┼──────────────┐")
    lines.append("│                        BACKEND               │              │")
    if backend_type == "java":
        lines.append("│  ┌───────────────────────┐   ┌──────────────▼───────────┐  │")
        lines.append("│  │  DynamicApiController  │◀──│  TableService            │  │")
        lines.append("│  └───────────────────────┘   └──────────────┬───────────┘  │")
        lines.append("│                                              │              │")
        lines.append("│                                   JdbcTemplate              │")
        lines.append("│                                              │              │")
    else:
        lines.append("│  ┌───────────────────────┐   ┌──────────────▼───────────┐  │")
        lines.append("│  │  FastAPI Routes        │◀──│  app_server.py           │  │")
        lines.append("│  └───────────────────────┘   └──────────────┬───────────┘  │")
        lines.append("│                                              │              │")
        lines.append("│                                      sqlite3 module         │")
        lines.append("│                                              │              │")
    lines.append("│                                     ┌────────▼────────┐        │")
    lines.append("│                                     │  SQLite (data.db)│        │")
    lines.append("│                                     └─────────────────┘        │")
    lines.append("└─────────────────────────────────────────────────────────────────┘")
    lines.append("```")
    lines.append("")

    # Pages section
    lines.append("---")
    lines.append("## Pages")
    lines.append("")
    lines.append("| Page | File | Data Tables Used |")
    lines.append("|------|------|-----------------|")
    for page in pages:
        page_file = pages_dir / f"{page}.tsx"
        used_tables = []
        if page_file.exists():
            content = page_file.read_text(encoding="utf-8")
            for t in tables:
                if t in content:
                    used_tables.append(t)
        lines.append(f"| {page} | `src/pages/{page}.tsx` | {', '.join(used_tables) or '—'} |")
    lines.append("")

    # Components section
    if components:
        lines.append("---")
        lines.append("## Shared Components")
        lines.append("")
        lines.append("| Component | File |")
        lines.append("|-----------|------|")
        for comp in components:
            lines.append(f"| {comp.replace('.tsx','').replace('.ts','')} | `src/components/{comp}` |")
        lines.append("")

    # Hooks section
    if hooks:
        lines.append("---")
        lines.append("## Hooks")
        lines.append("")
        lines.append("| Hook | File | Purpose |")
        lines.append("|------|------|---------|")
        for hook in hooks:
            purpose = "API data fetching" if "api" in hook.lower() else "Custom logic"
            lines.append(f"| {hook.replace('.ts','')} | `src/hooks/{hook}` | {purpose} |")
        lines.append("")

    # Backend section
    lines.append("---")
    lines.append("## Backend")
    lines.append("")
    if backend_type == "java":
        lines.append("**Stack:** Spring Boot 3.3 + JdbcTemplate + SQLite JDBC")
        lines.append("")
        lines.append("| Layer | File | Responsibility |")
        lines.append("|-------|------|---------------|")
        if has_new_pipeline:
            lines.append("| Routes | Per-entity REST controllers | See API & MCP panel below for the live endpoint list |")
        else:
            lines.append("| Controller | `backend/src/main/java/.../DynamicApiController.java` | REST endpoints, request routing |")
            lines.append("| Service | `backend/src/main/java/.../TableService.java` | Business logic, query building |")
        lines.append("| Config | `backend/src/main/resources/application.properties` | Server port, DB path |")
        lines.append("| Schema | `backend/schema.sql` | Table definitions |")
        lines.append("| Seed | `backend/seed.sql` | Initial data |")
        lines.append("| Build | `backend/pom.xml` | Maven dependencies |")
        lines.append("| Env | `backend/.env` | JAVA_HOME, MAVEN_HOME, PORT |")
    else:
        lines.append("**Stack:** Python FastAPI + sqlite3 + Uvicorn")
        lines.append("")
        lines.append("| Layer | File | Responsibility |")
        lines.append("|-------|------|---------------|")
        lines.append("| Server | `api/app_server.py` | REST endpoints, DB queries, AI chat |")
        lines.append("| Schema | `api/schema.sql` | Table definitions |")
        lines.append("| Seed | `api/seed.sql` | Initial data |")
        lines.append("| Env | `api/.env` | LLM config, API port |")
        lines.append("| Deps | `api/requirements.txt` | Python packages |")
    lines.append("")

    # Data model
    if tables:
        lines.append("---")
        lines.append("## Data Model")
        lines.append("")
        lines.append("| Table | Columns |")
        lines.append("|-------|---------|")
        for table in tables:
            # Extract columns for this table from schema
            pattern = rf"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?{_re_arch.escape(table)}\s*\((.*?)\)"
            match = _re_arch.search(pattern, schema_content, _re_arch.DOTALL | _re_arch.IGNORECASE)
            if match:
                cols_raw = match.group(1)
                cols = [c.strip().split()[0] for c in cols_raw.split(",") if c.strip() and not c.strip().upper().startswith(("PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "CONSTRAINT"))]
                lines.append(f"| `{table}` | {', '.join(cols[:8])}{' ...' if len(cols) > 8 else ''} |")
            else:
                lines.append(f"| `{table}` | — |")
        lines.append("")

    # API endpoints
    lines.append("---")
    lines.append("## API Endpoints")
    lines.append("")
    if has_new_pipeline:
        lines.append("_See the API & MCP panel below for the live, per-project endpoint list (including custom join endpoints)._")
    else:
        lines.append("| Method | Endpoint | Description |")
        lines.append("|--------|----------|-------------|")
        for table in tables:
            lines.append(f"| GET | `/api/data/{table}` | List all {table} (paginated) |")
        lines.append("| POST | `/api/chat` | AI chat endpoint |")
    lines.append("")

    # File tree
    lines.append("---")
    lines.append("## File Structure")
    lines.append("")
    lines.append("```")
    lines.append(f"{project_name}/")
    lines.append("├── src/")
    lines.append("│   ├── pages/")
    for p in pages:
        lines.append(f"│   │   └── {p}.tsx")
    lines.append("│   ├── components/")
    for c in components[:5]:
        lines.append(f"│   │   └── {c}")
    if len(components) > 5:
        lines.append(f"│   │   └── ... ({len(components) - 5} more)")
    lines.append("│   ├── hooks/")
    for h in hooks:
        lines.append(f"│   │   └── {h}")
    lines.append("│   ├── App.tsx")
    lines.append("│   └── main.tsx")
    if backend_type == "java":
        lines.append("├── backend/")
        lines.append("│   ├── src/main/java/com/turboui/app/")
        lines.append("│   │   ├── controller/DynamicApiController.java")
        lines.append("│   │   ├── service/TableService.java")
        lines.append("│   │   └── Application.java")
        lines.append("│   ├── src/main/resources/application.properties")
        lines.append("│   ├── schema.sql")
        lines.append("│   ├── seed.sql")
        lines.append("│   ├── pom.xml")
        lines.append("│   └── .env")
    else:
        lines.append("├── api/")
        lines.append("│   ├── app_server.py")
        lines.append("│   ├── schema.sql")
        lines.append("│   ├── seed.sql")
        lines.append("│   ├── .env")
        lines.append("│   └── requirements.txt")
    lines.append("├── package.json")
    lines.append("├── vite.config.ts")
    lines.append("├── tailwind.config.js")
    lines.append("└── index.html")
    lines.append("```")
    lines.append("")

    # Write to disk
    arch_file.write_text("\n".join(lines), encoding="utf-8")

    # Generate HTML version
    _generate_architecture_html(project_dir, project_name, backend_type, pages, components, hooks, tables, schema_content, ts, event)


def _generate_architecture_html(
    project_dir, project_name: str, backend_type: str,
    pages: list, components: list, hooks: list, tables: list,
    schema_content: str, timestamp: str, event: str
):
    """Generate a rich, visually stunning HTML architecture document using CSS boxes and proper tree layout."""
    import re as _re

    html_file = project_dir / ".architecture.html"

    # See _generate_architecture's has_new_pipeline comment — the API Endpoints
    # and Controller/Service rows below are stale for the new named-route
    # pipeline, so they're replaced with a pointer to the live API & MCP panel.
    has_new_pipeline = (project_dir / "backend" / ".architecture.json").exists() or (project_dir / "api" / ".architecture.json").exists()

    # Extract table columns for data model
    table_data = []
    for table in tables:
        pattern = rf"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?{_re.escape(table)}\s*\((.*?)\)"
        match = _re.search(pattern, schema_content, _re.DOTALL | _re.IGNORECASE)
        cols = []
        if match:
            cols_raw = match.group(1)
            cols = [c.strip().split()[0] for c in cols_raw.split(",")
                    if c.strip() and not c.strip().upper().startswith(("PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "CONSTRAINT"))]
        table_data.append({"name": table, "columns": cols[:10]})

    # Detect page-table relationships
    pages_dir = project_dir / "src" / "pages"
    page_tables = {}
    for page in pages:
        page_file = pages_dir / f"{page}.tsx"
        used = []
        if page_file.exists():
            pg_content = page_file.read_text(encoding="utf-8")
            for t in tables:
                if t in pg_content:
                    used.append(t)
        page_tables[page] = used

    backend_label = "Java Spring Boot (JDBC + SQLite)" if backend_type == "java" else "Python FastAPI (SQLite)"
    backend_icon_char = "☕" if backend_type == "java" else "\U0001f40d"

    # --- Build component diagram backend boxes ---
    if backend_type == "java":
        backend_boxes = """
            <div class="arch-box backend-box">
              <div class="box-label">DynamicApiController</div>
              <div class="box-sublabel">REST endpoints</div>
            </div>
            <div class="arch-box backend-box">
              <div class="box-label">TableService</div>
              <div class="box-sublabel">Business logic</div>
            </div>
            <div class="arch-box backend-box">
              <div class="box-label">JdbcTemplate</div>
              <div class="box-sublabel">Query execution</div>
            </div>"""
    else:
        backend_boxes = """
            <div class="arch-box backend-box">
              <div class="box-label">FastAPI Routes</div>
              <div class="box-sublabel">REST endpoints</div>
            </div>
            <div class="arch-box backend-box">
              <div class="box-label">app_server.py</div>
              <div class="box-sublabel">Business logic</div>
            </div>
            <div class="arch-box backend-box">
              <div class="box-label">sqlite3</div>
              <div class="box-sublabel">DB module</div>
            </div>"""

    # --- Build file tree HTML ---
    tree_lines = []
    tree_lines.append(f'<li class="tree-dir"><span class="dir-name">{project_name}/</span><ul>')
    # src/
    tree_lines.append('<li class="tree-dir"><span class="dir-name">src/</span><ul>')
    tree_lines.append('<li class="tree-dir"><span class="dir-name">pages/</span><ul>')
    for p in pages:
        tree_lines.append(f'<li class="tree-file"><span class="file-name">{p}.tsx</span></li>')
    tree_lines.append('</ul></li>')
    tree_lines.append('<li class="tree-dir"><span class="dir-name">components/</span><ul>')
    for c in components[:8]:
        tree_lines.append(f'<li class="tree-file"><span class="file-name">{c}</span></li>')
    if len(components) > 8:
        tree_lines.append(f'<li class="tree-file"><span class="file-more">... +{len(components)-8} more</span></li>')
    tree_lines.append('</ul></li>')
    tree_lines.append('<li class="tree-dir"><span class="dir-name">hooks/</span><ul>')
    for h in hooks:
        tree_lines.append(f'<li class="tree-file"><span class="file-name">{h}</span></li>')
    tree_lines.append('</ul></li>')
    tree_lines.append('<li class="tree-file"><span class="file-name">App.tsx</span></li>')
    tree_lines.append('<li class="tree-file"><span class="file-name">main.tsx</span></li>')
    tree_lines.append('</ul></li>')  # close src/

    if backend_type == "java":
        tree_lines.append('<li class="tree-dir"><span class="dir-name">backend/</span><ul>')
        tree_lines.append('<li class="tree-dir"><span class="dir-name">src/main/java/.../</span><ul>')
        tree_lines.append('<li class="tree-file"><span class="file-name">DynamicApiController.java</span></li>')
        tree_lines.append('<li class="tree-file"><span class="file-name">TableService.java</span></li>')
        tree_lines.append('<li class="tree-file"><span class="file-name">Application.java</span></li>')
        tree_lines.append('</ul></li>')
        tree_lines.append('<li class="tree-file"><span class="file-name">application.properties</span></li>')
        tree_lines.append('<li class="tree-file"><span class="file-name">schema.sql</span></li>')
        tree_lines.append('<li class="tree-file"><span class="file-name">pom.xml</span></li>')
        tree_lines.append('<li class="tree-file"><span class="file-name">.env</span></li>')
        tree_lines.append('</ul></li>')
    else:
        tree_lines.append('<li class="tree-dir"><span class="dir-name">api/</span><ul>')
        tree_lines.append('<li class="tree-file"><span class="file-name">app_server.py</span></li>')
        tree_lines.append('<li class="tree-file"><span class="file-name">schema.sql</span></li>')
        tree_lines.append('<li class="tree-file"><span class="file-name">seed.sql</span></li>')
        tree_lines.append('<li class="tree-file"><span class="file-name">.env</span></li>')
        tree_lines.append('<li class="tree-file"><span class="file-name">requirements.txt</span></li>')
        tree_lines.append('</ul></li>')

    tree_lines.append('<li class="tree-file"><span class="file-name">package.json</span></li>')
    tree_lines.append('<li class="tree-file"><span class="file-name">vite.config.ts</span></li>')
    tree_lines.append('<li class="tree-file"><span class="file-name">tailwind.config.js</span></li>')
    tree_lines.append('<li class="tree-file"><span class="file-name">index.html</span></li>')
    tree_lines.append('</ul></li>')
    tree_html = "\n      ".join(tree_lines)

    # --- Table rows ---
    pages_rows = ""
    for page in pages:
        used = page_tables.get(page, [])
        tags = "".join(f'<span class="tag">{t}</span>' for t in used) if used else '<span class="dim">—</span>'
        pages_rows += f'        <tr><td class="cell-name">{page}</td><td class="cell-path">src/pages/{page}.tsx</td><td>{tags}</td></tr>\n'

    comp_rows = ""
    for comp in components:
        comp_name = comp.replace(".tsx", "").replace(".ts", "")
        comp_rows += f'        <tr><td class="cell-name">{comp_name}</td><td class="cell-path">src/components/{comp}</td></tr>\n'

    data_rows = ""
    for td in table_data:
        col_tags = "".join(f'<span class="col-tag">{c}</span>' for c in td["columns"][:8])
        if len(td["columns"]) > 8:
            col_tags += f'<span class="col-tag more">+{len(td["columns"])-8}</span>'
        data_rows += f'        <tr><td class="cell-name">{td["name"]}</td><td>{col_tags or "—"}</td></tr>\n'

    if has_new_pipeline:
        api_rows = '        <tr><td colspan="3">See the API &amp; MCP panel below for the live, per-project endpoint list (including custom join endpoints).</td></tr>\n'
    else:
        api_rows = ""
        for table in tables:
            api_rows += f'        <tr><td><span class="method get">GET</span></td><td class="cell-path">/api/data/{table}</td><td>List {table} (paginated)</td></tr>\n'
        api_rows += '        <tr><td><span class="method post">POST</span></td><td class="cell-path">/api/chat</td><td>AI chat endpoint</td></tr>\n'

    if backend_type == "java":
        controller_service_rows = (
            '<tr><td class="cell-name">Routes</td><td class="cell-path">Per-entity REST controllers</td><td>See API &amp; MCP panel below</td></tr>'
            if has_new_pipeline else
            '<tr><td class="cell-name">Controller</td><td class="cell-path">DynamicApiController.java</td><td>REST endpoints, routing</td></tr>\n'
            '        <tr><td class="cell-name">Service</td><td class="cell-path">TableService.java</td><td>Business logic, queries</td></tr>'
        )
        backend_rows = f"""
        {controller_service_rows}
        <tr><td class="cell-name">Config</td><td class="cell-path">application.properties</td><td>Port, DB path</td></tr>
        <tr><td class="cell-name">Schema</td><td class="cell-path">schema.sql</td><td>Table definitions</td></tr>
        <tr><td class="cell-name">Build</td><td class="cell-path">pom.xml</td><td>Maven dependencies</td></tr>
        <tr><td class="cell-name">Env</td><td class="cell-path">.env</td><td>JAVA_HOME, PORT</td></tr>"""
    else:
        backend_rows = """
        <tr><td class="cell-name">Server</td><td class="cell-path">app_server.py</td><td>REST + DB queries</td></tr>
        <tr><td class="cell-name">Schema</td><td class="cell-path">schema.sql</td><td>Table definitions</td></tr>
        <tr><td class="cell-name">Seed</td><td class="cell-path">seed.sql</td><td>Initial data</td></tr>
        <tr><td class="cell-name">Deps</td><td class="cell-path">requirements.txt</td><td>Python packages</td></tr>
        <tr><td class="cell-name">Env</td><td class="cell-path">.env</td><td>LLM config, port</td></tr>"""

    backend_stack = "Spring Boot 3.3 + JdbcTemplate + SQLite JDBC" if backend_type == "java" else "Python FastAPI + sqlite3 + Uvicorn"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Architecture — {project_name}</title>
<style>
:root {{
  --bg-primary: #0f172a;
  --bg-card: rgba(30,41,59,0.7);
  --border: rgba(148,163,184,0.12);
  --text-primary: #f1f5f9;
  --text-secondary: #94a3b8;
  --text-dim: #64748b;
  --accent-blue: #60a5fa;
  --accent-purple: #a78bfa;
  --accent-green: #4ade80;
  --accent-amber: #fbbf24;
  --accent-cyan: #22d3ee;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; background: var(--bg-primary); color: var(--text-primary); min-height: 100vh; padding: 2rem; }}
.container {{ max-width: 1200px; margin: 0 auto; }}
h1 {{ font-size: 1.6rem; font-weight: 700; background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0.3rem; }}
.subtitle {{ color: var(--text-secondary); font-size: 0.75rem; margin-bottom: 1.5rem; }}
.meta-row {{ display: flex; gap: 0.6rem; flex-wrap: wrap; margin-bottom: 2rem; }}
.chip {{ background: rgba(99,102,241,0.12); border: 1px solid rgba(99,102,241,0.25); border-radius: 9999px; padding: 0.3rem 0.75rem; font-size: 0.68rem; font-weight: 500; color: #a5b4fc; }}

.section {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: 1rem; padding: 1.5rem; margin-bottom: 1.5rem; backdrop-filter: blur(8px); }}
.section-hdr {{ font-size: 0.85rem; font-weight: 600; color: var(--text-primary); margin-bottom: 1.2rem; display: flex; align-items: center; gap: 0.5rem; }}
.section-hdr .icon {{ width: 1.5rem; height: 1.5rem; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 0.85rem; }}

/* Component Diagram */
.arch-diagram {{ display: flex; flex-direction: column; align-items: center; gap: 0; }}
.arch-layer {{ width: 100%; max-width: 720px; border: 2px solid; border-radius: 14px; padding: 1.4rem 1.2rem 1.2rem; position: relative; }}
.arch-layer.frontend {{ border-color: rgba(96,165,250,0.4); background: rgba(96,165,250,0.04); }}
.arch-layer.backend {{ border-color: rgba(167,139,250,0.4); background: rgba(167,139,250,0.04); }}
.arch-layer.database {{ border-color: rgba(251,191,36,0.4); background: rgba(251,191,36,0.04); max-width: 220px; }}
.layer-label {{ position: absolute; top: -0.55rem; left: 1.2rem; background: var(--bg-primary); padding: 0 0.6rem; font-size: 0.62rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; }}
.frontend .layer-label {{ color: var(--accent-blue); }}
.backend .layer-label {{ color: var(--accent-purple); }}
.database .layer-label {{ color: var(--accent-amber); }}
.layer-content {{ display: flex; flex-wrap: wrap; gap: 0.6rem; justify-content: center; align-items: stretch; }}
.arch-box {{ border: 1.5px solid rgba(148,163,184,0.2); border-radius: 10px; padding: 0.7rem 1rem; background: rgba(15,23,42,0.7); text-align: center; min-width: 110px; transition: border-color 0.2s, transform 0.2s; }}
.arch-box:hover {{ transform: translateY(-2px); }}
.arch-box .box-label {{ font-size: 0.7rem; font-weight: 600; color: var(--text-primary); white-space: nowrap; }}
.arch-box .box-sublabel {{ font-size: 0.58rem; color: var(--text-dim); margin-top: 0.2rem; }}
.frontend-box {{ border-color: rgba(96,165,250,0.35); }}
.frontend-box:hover {{ border-color: var(--accent-blue); }}
.backend-box {{ border-color: rgba(167,139,250,0.35); }}
.backend-box:hover {{ border-color: var(--accent-purple); }}
.db-box {{ border-color: rgba(251,191,36,0.35); }}
.db-box:hover {{ border-color: var(--accent-amber); }}

/* Connectors */
.connector {{ display: flex; align-items: center; justify-content: center; height: 3rem; position: relative; }}
.connector-line {{ width: 2px; height: 100%; background: var(--accent-green); opacity: 0.6; }}
.connector-arrow {{ position: absolute; bottom: -1px; width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 7px solid var(--accent-green); }}
.connector-label {{ position: absolute; left: calc(50% + 1rem); top: 50%; transform: translateY(-50%); font-size: 0.6rem; color: var(--accent-green); font-weight: 600; font-family: 'JetBrains Mono', monospace; background: var(--bg-primary); padding: 0.15rem 0.5rem; border-radius: 4px; border: 1px solid rgba(74,222,128,0.2); white-space: nowrap; }}

/* Tables */
.grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }}
@media (max-width: 768px) {{ .grid-2 {{ grid-template-columns: 1fr; }} }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.72rem; }}
th {{ text-align: left; padding: 0.55rem 0.7rem; background: rgba(99,102,241,0.08); color: var(--accent-purple); font-weight: 600; font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid var(--border); }}
td {{ padding: 0.5rem 0.7rem; border-bottom: 1px solid rgba(148,163,184,0.05); color: #cbd5e1; vertical-align: top; }}
tr:hover td {{ background: rgba(99,102,241,0.04); }}
.cell-name {{ font-weight: 600; color: var(--text-primary); }}
.cell-path {{ font-family: 'JetBrains Mono', 'Fira Code', monospace; font-size: 0.64rem; color: var(--accent-cyan); }}
.tag {{ display: inline-block; background: rgba(99,102,241,0.15); color: #c4b5fd; padding: 0.12rem 0.45rem; border-radius: 4px; font-size: 0.58rem; font-weight: 500; margin: 0.1rem 0.12rem; }}
.col-tag {{ display: inline-block; background: rgba(74,222,128,0.1); color: #86efac; padding: 0.1rem 0.4rem; border-radius: 3px; font-size: 0.56rem; font-weight: 500; margin: 0.06rem 0.08rem; font-family: 'JetBrains Mono', monospace; }}
.col-tag.more {{ background: rgba(251,191,36,0.12); color: #fcd34d; }}
.dim {{ color: var(--text-dim); }}
.method {{ display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.58rem; font-weight: 700; font-family: monospace; min-width: 2.8rem; text-align: center; }}
.method.get {{ background: rgba(74,222,128,0.12); color: #86efac; }}
.method.post {{ background: rgba(96,165,250,0.12); color: #93c5fd; }}

/* File Tree */
.file-tree {{ list-style: none; padding: 0; }}
.file-tree ul {{ list-style: none; padding-left: 0; margin: 0; }}
.file-tree li {{ position: relative; padding-left: 1.5rem; }}
.file-tree li::before {{ content: ''; position: absolute; left: 0.5rem; top: 0; height: 100%; width: 1px; background: rgba(148,163,184,0.15); }}
.file-tree li::after {{ content: ''; position: absolute; left: 0.5rem; top: 0.85rem; width: 0.7rem; height: 1px; background: rgba(148,163,184,0.25); }}
.file-tree li:last-child::before {{ height: 0.85rem; }}
.file-tree > li::before, .file-tree > li::after {{ display: none; }}
.file-tree > li {{ padding-left: 0; }}
.tree-dir > span, .tree-file > span {{ display: inline-block; padding: 0.15rem 0; line-height: 1.7; }}
.dir-name {{ font-weight: 600; color: var(--accent-blue); font-size: 0.72rem; cursor: default; }}
.dir-name::before {{ content: '\U0001f4c2 '; }}
.file-name {{ color: #cbd5e1; font-family: 'JetBrains Mono', monospace; font-size: 0.66rem; }}
.file-name::before {{ content: ''; display: inline-block; width: 0.5rem; height: 0.5rem; background: var(--accent-cyan); opacity: 0.5; border-radius: 2px; margin-right: 0.4rem; vertical-align: middle; }}
.file-more {{ color: var(--text-dim); font-style: italic; font-size: 0.64rem; }}
</style>
</head>
<body>
<div class="container">
  <h1>\U0001f3d7️ {project_name}</h1>
  <p class="subtitle">Architecture Document &middot; {event} &middot; {timestamp}</p>

  <div class="meta-row">
    <span class="chip">{backend_icon_char} {backend_label}</span>
    <span class="chip">⚛️ React 18 + TypeScript + Vite</span>
    <span class="chip">\U0001f3a8 Tailwind CSS</span>
    <span class="chip">\U0001f4c4 {len(pages)} Pages</span>
    <span class="chip">\U0001f5c4️ {len(tables)} Tables</span>
    <span class="chip">\U0001f9e9 {len(components)} Components</span>
  </div>

  <div class="section">
    <div class="section-hdr"><div class="icon">\U0001f517</div> Component Architecture</div>
    <div class="arch-diagram">
      <div class="arch-layer frontend">
        <div class="layer-label">Frontend</div>
        <div class="layer-content">
          <div class="arch-box frontend-box">
            <div class="box-label">App.tsx</div>
            <div class="box-sublabel">Entry point</div>
          </div>
          <div class="arch-box frontend-box">
            <div class="box-label">Router</div>
            <div class="box-sublabel">Page navigation</div>
          </div>
          <div class="arch-box frontend-box">
            <div class="box-label">Pages ({len(pages)})</div>
            <div class="box-sublabel">UI views</div>
          </div>
          <div class="arch-box frontend-box">
            <div class="box-label">Components ({len(components)})</div>
            <div class="box-sublabel">Reusable UI</div>
          </div>
          <div class="arch-box frontend-box">
            <div class="box-label">useApi</div>
            <div class="box-sublabel">Data hooks</div>
          </div>
        </div>
      </div>

      <div class="connector">
        <div class="connector-line"></div>
        <div class="connector-arrow"></div>
        <div class="connector-label">HTTP /api/*</div>
      </div>

      <div class="arch-layer backend">
        <div class="layer-label">Backend — {backend_stack}</div>
        <div class="layer-content">{backend_boxes}
        </div>
      </div>

      <div class="connector">
        <div class="connector-line"></div>
        <div class="connector-arrow"></div>
        <div class="connector-label">JDBC / sqlite3</div>
      </div>

      <div class="arch-layer database">
        <div class="layer-label">Database</div>
        <div class="layer-content">
          <div class="arch-box db-box">
            <div class="box-label">SQLite</div>
            <div class="box-sublabel">data.db &middot; {len(tables)} tables</div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class="grid-2">
    <div class="section">
      <div class="section-hdr"><div class="icon">\U0001f4c4</div> Pages</div>
      <table>
        <thead><tr><th>Page</th><th>File</th><th>Data</th></tr></thead>
        <tbody>
{pages_rows}        </tbody>
      </table>
    </div>
    <div class="section">
      <div class="section-hdr"><div class="icon">\U0001f9e9</div> Shared Components</div>
      <table>
        <thead><tr><th>Component</th><th>File</th></tr></thead>
        <tbody>
{comp_rows}        </tbody>
      </table>
    </div>
  </div>

  <div class="grid-2">
    <div class="section">
      <div class="section-hdr"><div class="icon">{backend_icon_char}</div> Backend Layer</div>
      <table>
        <thead><tr><th>Layer</th><th>File</th><th>Role</th></tr></thead>
        <tbody>{backend_rows}
        </tbody>
      </table>
    </div>
    <div class="section">
      <div class="section-hdr"><div class="icon">\U0001f5c4️</div> Data Model</div>
      <table>
        <thead><tr><th>Table</th><th>Columns</th></tr></thead>
        <tbody>
{data_rows}        </tbody>
      </table>
    </div>
  </div>

  <div class="section">
    <div class="section-hdr"><div class="icon">\U0001f310</div> API Endpoints</div>
    <table>
      <thead><tr><th>Method</th><th>Endpoint</th><th>Description</th></tr></thead>
      <tbody>
{api_rows}      </tbody>
    </table>
  </div>

  <div class="section">
    <div class="section-hdr"><div class="icon">\U0001f4c1</div> File Structure</div>
    <ul class="file-tree">
      {tree_html}
    </ul>
  </div>

</div>
</body>
</html>"""

    html_file.write_text(html, encoding="utf-8")


def _generate_api_architecture_html(
    project_dir, project_name: str, language: str, auth_type: str, rate_limit,
    architecture: dict, timestamp: str,
):
    """
    Rich HTML architecture document for a generated standalone API — same
    visual language (CSS boxes, layered diagram, file tree) as web apps'
    _generate_architecture_html, but built from API concepts (entities,
    endpoints, auth/rate-limiting/usage-metering) instead of pages/components.
    """
    html_file = project_dir / ".architecture.html"

    # The architect LLM's output shape isn't schema-enforced, so defensively
    # drop any entries that don't come back as dicts rather than letting a
    # stray string/list blow up the whole generation job over a cosmetic doc.
    entities = [e for e in (architecture.get("entities") or []) if isinstance(e, dict)]
    endpoints = [e for e in (architecture.get("endpoints") or []) if isinstance(e, dict)]

    backend_label = "Java Spring Boot (JDBC + SQLite)" if language == "java" else "Python FastAPI (SQLite)"
    backend_icon_char = "☕" if language == "java" else "\U0001f40d"
    backend_stack = "Spring Boot 3.3 + Spring Security + SQLite JDBC" if language == "java" else "Python FastAPI + sqlite3 + Uvicorn"

    if language == "java":
        backend_boxes = """
            <div class="arch-box backend-box">
              <div class="box-label">@RestController</div>
              <div class="box-sublabel">REST endpoints</div>
            </div>
            <div class="arch-box backend-box">
              <div class="box-label">Service layer</div>
              <div class="box-sublabel">Business logic</div>
            </div>
            <div class="arch-box backend-box">
              <div class="box-label">JdbcTemplate</div>
              <div class="box-sublabel">Query execution</div>
            </div>"""
        tree_backend = """<li class="tree-dir"><span class="dir-name">src/main/java/com/api/</span><ul>
      <li class="tree-file"><span class="file-name">Application.java</span></li>
      <li class="tree-dir"><span class="dir-name">security/</span><ul>
        <li class="tree-file"><span class="file-name">SecurityConfig.java</span></li>
        <li class="tree-file"><span class="file-name">RateLimitFilter.java</span></li>
        <li class="tree-file"><span class="file-name">UsageTrackingFilter.java</span></li>
      </ul></li>
      </ul></li>
      <li class="tree-dir"><span class="dir-name">src/main/resources/</span><ul>
      <li class="tree-file"><span class="file-name">application.properties</span></li>
      <li class="tree-file"><span class="file-name">data.sql</span></li>
      </ul></li>
      <li class="tree-file"><span class="file-name">pom.xml</span></li>"""
    else:
        backend_boxes = """
            <div class="arch-box backend-box">
              <div class="box-label">FastAPI Routes</div>
              <div class="box-sublabel">REST endpoints</div>
            </div>
            <div class="arch-box backend-box">
              <div class="box-label">src/main.py</div>
              <div class="box-sublabel">Business logic</div>
            </div>
            <div class="arch-box backend-box">
              <div class="box-label">sqlite3</div>
              <div class="box-sublabel">DB module</div>
            </div>"""
        tree_backend = """<li class="tree-dir"><span class="dir-name">src/</span><ul>
      <li class="tree-file"><span class="file-name">main.py</span></li>
      <li class="tree-file"><span class="file-name">security_bootstrap.py</span></li>
      <li class="tree-dir"><span class="dir-name">middleware/</span><ul>
        <li class="tree-file"><span class="file-name">basic_auth.py</span></li>
        <li class="tree-file"><span class="file-name">rate_limit.py</span></li>
        <li class="tree-file"><span class="file-name">usage_tracking.py</span></li>
      </ul></li>
      </ul></li>
      <li class="tree-file"><span class="file-name">requirements.txt</span></li>"""

    auth_box = f"""
            <div class="arch-box backend-box">
              <div class="box-label">{"Basic Auth" if auth_type == "basic" else "No Auth"}</div>
              <div class="box-sublabel">Every request</div>
            </div>""" if auth_type == "basic" else ""

    entity_rows = ""
    for e in entities:
        fields = [f for f in (e.get("fields") or []) if isinstance(f, dict)]
        field_tags = "".join(
            f'<span class="col-tag">{f.get("name")}: {f.get("type")}{"" if f.get("required") else "?"}</span>'
            for f in fields[:10]
        )
        entity_rows += f'        <tr><td class="cell-name">{e.get("name","")} <span class="cell-path">{e.get("table","")}</span></td><td>{field_tags or "—"}</td></tr>\n'

    method_class = {"GET": "get", "POST": "post", "PUT": "post", "PATCH": "post", "DELETE": "post"}
    endpoint_rows = ""
    for ep in endpoints:
        m = (ep.get("method") or "GET").upper()
        endpoint_rows += (
            f'        <tr><td><span class="method {method_class.get(m,"get")}">{m}</span></td>'
            f'<td class="cell-path">{ep.get("path","")}</td><td>{ep.get("description","")}</td></tr>\n'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Architecture — {project_name}</title>
<style>
:root {{
  --bg-primary: #0f172a;
  --bg-card: rgba(30,41,59,0.7);
  --border: rgba(148,163,184,0.12);
  --text-primary: #f1f5f9;
  --text-secondary: #94a3b8;
  --text-dim: #64748b;
  --accent-blue: #60a5fa;
  --accent-purple: #a78bfa;
  --accent-green: #4ade80;
  --accent-amber: #fbbf24;
  --accent-cyan: #22d3ee;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; background: var(--bg-primary); color: var(--text-primary); min-height: 100vh; padding: 2rem; }}
.container {{ max-width: 1200px; margin: 0 auto; }}
h1 {{ font-size: 1.6rem; font-weight: 700; background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0.3rem; }}
.subtitle {{ color: var(--text-secondary); font-size: 0.75rem; margin-bottom: 1.5rem; }}
.meta-row {{ display: flex; gap: 0.6rem; flex-wrap: wrap; margin-bottom: 2rem; }}
.chip {{ background: rgba(99,102,241,0.12); border: 1px solid rgba(99,102,241,0.25); border-radius: 9999px; padding: 0.3rem 0.75rem; font-size: 0.68rem; font-weight: 500; color: #a5b4fc; }}
.section {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: 1rem; padding: 1.5rem; margin-bottom: 1.5rem; backdrop-filter: blur(8px); }}
.section-hdr {{ font-size: 0.85rem; font-weight: 600; color: var(--text-primary); margin-bottom: 1.2rem; display: flex; align-items: center; gap: 0.5rem; }}
.section-hdr .icon {{ width: 1.5rem; height: 1.5rem; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 0.85rem; }}
.arch-diagram {{ display: flex; flex-direction: column; align-items: center; gap: 0; }}
.arch-layer {{ width: 100%; max-width: 720px; border: 2px solid; border-radius: 14px; padding: 1.4rem 1.2rem 1.2rem; position: relative; }}
.arch-layer.frontend {{ border-color: rgba(96,165,250,0.4); background: rgba(96,165,250,0.04); }}
.arch-layer.backend {{ border-color: rgba(167,139,250,0.4); background: rgba(167,139,250,0.04); }}
.arch-layer.database {{ border-color: rgba(251,191,36,0.4); background: rgba(251,191,36,0.04); max-width: 220px; }}
.layer-label {{ position: absolute; top: -0.55rem; left: 1.2rem; background: var(--bg-primary); padding: 0 0.6rem; font-size: 0.62rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; }}
.frontend .layer-label {{ color: var(--accent-blue); }}
.backend .layer-label {{ color: var(--accent-purple); }}
.database .layer-label {{ color: var(--accent-amber); }}
.layer-content {{ display: flex; flex-wrap: wrap; gap: 0.6rem; justify-content: center; align-items: stretch; }}
.arch-box {{ border: 1.5px solid rgba(148,163,184,0.2); border-radius: 10px; padding: 0.7rem 1rem; background: rgba(15,23,42,0.7); text-align: center; min-width: 110px; transition: border-color 0.2s, transform 0.2s; }}
.arch-box:hover {{ transform: translateY(-2px); }}
.arch-box .box-label {{ font-size: 0.7rem; font-weight: 600; color: var(--text-primary); white-space: nowrap; }}
.arch-box .box-sublabel {{ font-size: 0.58rem; color: var(--text-dim); margin-top: 0.2rem; }}
.frontend-box {{ border-color: rgba(96,165,250,0.35); }}
.frontend-box:hover {{ border-color: var(--accent-blue); }}
.backend-box {{ border-color: rgba(167,139,250,0.35); }}
.backend-box:hover {{ border-color: var(--accent-purple); }}
.db-box {{ border-color: rgba(251,191,36,0.35); }}
.db-box:hover {{ border-color: var(--accent-amber); }}
.connector {{ display: flex; align-items: center; justify-content: center; height: 3rem; position: relative; }}
.connector-line {{ width: 2px; height: 100%; background: var(--accent-green); opacity: 0.6; }}
.connector-arrow {{ position: absolute; bottom: -1px; width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 7px solid var(--accent-green); }}
.connector-label {{ position: absolute; left: calc(50% + 1rem); top: 50%; transform: translateY(-50%); font-size: 0.6rem; color: var(--accent-green); font-weight: 600; font-family: 'JetBrains Mono', monospace; background: var(--bg-primary); padding: 0.15rem 0.5rem; border-radius: 4px; border: 1px solid rgba(74,222,128,0.2); white-space: nowrap; }}
.grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }}
@media (max-width: 768px) {{ .grid-2 {{ grid-template-columns: 1fr; }} }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.72rem; }}
th {{ text-align: left; padding: 0.55rem 0.7rem; background: rgba(99,102,241,0.08); color: var(--accent-purple); font-weight: 600; font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid var(--border); }}
td {{ padding: 0.5rem 0.7rem; border-bottom: 1px solid rgba(148,163,184,0.05); color: #cbd5e1; vertical-align: top; }}
tr:hover td {{ background: rgba(99,102,241,0.04); }}
.cell-name {{ font-weight: 600; color: var(--text-primary); }}
.cell-path {{ font-family: 'JetBrains Mono', 'Fira Code', monospace; font-size: 0.64rem; color: var(--accent-cyan); }}
.col-tag {{ display: inline-block; background: rgba(74,222,128,0.1); color: #86efac; padding: 0.1rem 0.4rem; border-radius: 3px; font-size: 0.56rem; font-weight: 500; margin: 0.06rem 0.08rem; font-family: 'JetBrains Mono', monospace; }}
.method {{ display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.58rem; font-weight: 700; font-family: monospace; min-width: 2.8rem; text-align: center; }}
.method.get {{ background: rgba(74,222,128,0.12); color: #86efac; }}
.method.post {{ background: rgba(96,165,250,0.12); color: #93c5fd; }}
.file-tree {{ list-style: none; padding: 0; }}
.file-tree ul {{ list-style: none; padding-left: 0; margin: 0; }}
.file-tree li {{ position: relative; padding-left: 1.5rem; }}
.file-tree li::before {{ content: ''; position: absolute; left: 0.5rem; top: 0; height: 100%; width: 1px; background: rgba(148,163,184,0.15); }}
.file-tree li::after {{ content: ''; position: absolute; left: 0.5rem; top: 0.85rem; width: 0.7rem; height: 1px; background: rgba(148,163,184,0.25); }}
.file-tree li:last-child::before {{ height: 0.85rem; }}
.file-tree > li::before, .file-tree > li::after {{ display: none; }}
.file-tree > li {{ padding-left: 0; }}
.tree-dir > span, .tree-file > span {{ display: inline-block; padding: 0.15rem 0; line-height: 1.7; }}
.dir-name {{ font-weight: 600; color: var(--accent-blue); font-size: 0.72rem; cursor: default; }}
.dir-name::before {{ content: '\U0001f4c2 '; }}
.file-name {{ color: #cbd5e1; font-family: 'JetBrains Mono', monospace; font-size: 0.66rem; }}
.file-name::before {{ content: ''; display: inline-block; width: 0.5rem; height: 0.5rem; background: var(--accent-cyan); opacity: 0.5; border-radius: 2px; margin-right: 0.4rem; vertical-align: middle; }}
</style>
</head>
<body>
<div class="container">
  <h1>\U0001f310 {project_name}</h1>
  <p class="subtitle">API Architecture Document &middot; {timestamp}</p>

  <div class="meta-row">
    <span class="chip">{backend_icon_char} {backend_label}</span>
    <span class="chip">\U0001f512 {"Basic Auth" if auth_type == "basic" else "No auth"}</span>
    <span class="chip">⏱️ {rate_limit} req/min</span>
    <span class="chip">\U0001f5c4️ {len(entities)} Entities</span>
    <span class="chip">\U0001f310 {len(endpoints)} Endpoints</span>
  </div>

  <div class="section">
    <div class="section-hdr"><div class="icon">\U0001f517</div> Component Architecture</div>
    <div class="arch-diagram">
      <div class="arch-layer frontend">
        <div class="layer-label">Client</div>
        <div class="layer-content">
          <div class="arch-box frontend-box">
            <div class="box-label">Any HTTP client</div>
            <div class="box-sublabel">curl, Postman, browser</div>
          </div>
          <div class="arch-box frontend-box">
            <div class="box-label">Swagger / OpenAPI docs</div>
            <div class="box-sublabel">Interactive try-it-out</div>
          </div>
        </div>
      </div>

      <div class="connector">
        <div class="connector-line"></div>
        <div class="connector-arrow"></div>
        <div class="connector-label">HTTPS</div>
      </div>

      <div class="arch-layer backend">
        <div class="layer-label">API — {backend_stack}</div>
        <div class="layer-content">{auth_box}
            <div class="arch-box backend-box">
              <div class="box-label">Rate Limiter</div>
              <div class="box-sublabel">{rate_limit} req/min</div>
            </div>
            <div class="arch-box backend-box">
              <div class="box-label">Usage Tracker</div>
              <div class="box-sublabel">Always on</div>
            </div>{backend_boxes}
        </div>
      </div>

      <div class="connector">
        <div class="connector-line"></div>
        <div class="connector-arrow"></div>
        <div class="connector-label">JDBC / sqlite3</div>
      </div>

      <div class="arch-layer database">
        <div class="layer-label">Database</div>
        <div class="layer-content">
          <div class="arch-box db-box">
            <div class="box-label">SQLite</div>
            <div class="box-sublabel">{len(entities)} tables</div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class="section">
    <div class="section-hdr"><div class="icon">\U0001f5c4️</div> Data Model</div>
    <table>
      <thead><tr><th>Entity</th><th>Fields</th></tr></thead>
      <tbody>
{entity_rows or '        <tr><td colspan="2" class="dim">No entities recorded</td></tr>\n'}      </tbody>
    </table>
  </div>

  <div class="section">
    <div class="section-hdr"><div class="icon">\U0001f310</div> API Endpoints</div>
    <table>
      <thead><tr><th>Method</th><th>Path</th><th>Description</th></tr></thead>
      <tbody>
{endpoint_rows or '        <tr><td colspan="3" class="dim">No endpoints recorded</td></tr>\n'}      </tbody>
    </table>
  </div>

  <div class="section">
    <div class="section-hdr"><div class="icon">\U0001f4c1</div> File Structure</div>
    <ul class="file-tree">
      <li class="tree-dir"><span class="dir-name">{project_name}/</span><ul>
      {tree_backend}
      <li class="tree-file"><span class="file-name">Dockerfile</span></li>
      <li class="tree-file"><span class="file-name">.env</span></li>
      <li class="tree-file"><span class="file-name">README.md</span></li>
      </ul></li>
    </ul>
  </div>

</div>
</body>
</html>"""

    html_file.write_text(html, encoding="utf-8")


# ── User-friendly error messages ─────────────────────────────────────────────

def _friendly_error(raw: str) -> str:
    """Convert raw exception text into a short, actionable message."""
    r = raw.lower()
    # Checked FIRST and on its own: when the LiteLLM fallback ALSO fails after
    # Bedrock (the primary) does, the combined "Both Bedrock and LiteLLM failed"
    # message still contains "503"/"litellm" from the embedded LiteLLM error
    # text — so the standalone "LiteLLM is unavailable" check below used to
    # match first and silently swallow the fact that Bedrock was tried and
    # failed too, hiding the actual (often more actionable) Bedrock error from
    # the user entirely. Matched on keywords rather than a fixed phrase so it
    # doesn't silently stop matching if the primary/fallback order changes again.
    if "bedrock" in r and "litellm" in r and "failed" in r:
        if "security token" in r and "expired" in r:
            return "Both LLM backends failed. AWS credentials have expired and LiteLLM is also unavailable. Refresh your SSO session (e.g. `aws sso login`) and try again."
        if "403" in r and "bedrock" in r:
            return "Both LLM backends failed. AWS Bedrock access was denied (403) and LiteLLM is also unavailable — check credentials/invoke permissions."
        return f"Both LLM backends failed. Raw detail: {raw[:400]}"
    if "security token" in r and "expired" in r:
        return "AWS credentials expired. Please refresh your SSO session (e.g. `aws sso login`) and try again."
    if "403" in r and "bedrock" in r:
        return "AWS Bedrock access denied (403). Check that your credentials are valid and you have invoke permissions."
    if "503 service unavailable" in r and "litellm" in r.replace(" ", ""):
        return "LiteLLM proxy is unavailable (503). No healthy backends. Check that the proxy is running."
    if "connectionerror" in r or "connecterror" in r:
        return "Cannot connect to LLM backend. Check network connectivity and proxy settings."
    if "authenticationerror" in r or "401" in r:
        return "LLM authentication failed. Check your API key in .env."
    if "timeout" in r:
        return "LLM request timed out. The service may be overloaded — try again in a moment."
    # Fallback: take first line, cap at 200 chars
    first_line = raw.split('\n')[0]
    return first_line[:200] if len(first_line) > 200 else first_line


# ── Job persistence (survives browser close) ─────────────────────────────────

def _get_jobs_dir() -> Path:
    from agents.uigen_agent import GENERATED_DIR
    jobs_dir = GENERATED_DIR.parent / ".jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    return jobs_dir


def _save_job(request_id: str, job: dict):
    """Persist job state to disk so it survives browser disconnects."""
    import json as _json
    _jobs[request_id] = job
    jobs_file = _get_jobs_dir() / f"{request_id}.json"
    jobs_file.write_text(_json.dumps(job, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_job(request_id: str) -> dict | None:
    """Load a job from memory or disk."""
    if request_id in _jobs:
        return _jobs[request_id]
    jobs_file = _get_jobs_dir() / f"{request_id}.json"
    if jobs_file.exists():
        import json as _json
        try:
            job = _json.loads(jobs_file.read_text(encoding="utf-8"))
            _jobs[request_id] = job
            return job
        except Exception:
            return None
    return None


def _load_active_jobs() -> list[dict]:
    """Load all active (running) jobs from disk."""
    import json as _json
    jobs_dir = _get_jobs_dir()
    active = []
    if not jobs_dir.exists():
        return active
    for f in jobs_dir.iterdir():
        if f.suffix == ".json":
            try:
                job = _json.loads(f.read_text(encoding="utf-8"))
                if job.get("status") == "running":
                    job["requestId"] = f.stem
                    active.append(job)
            except Exception:
                pass
    return active


def _write_meta(project_name: str, figma_url: str | None, prompt: str | None,
                title: str = "", has_app: bool = True, instructions: str = ""):
    """Persist how a project was created, update the fast registry, and log history."""
    from agents.uigen_agent import GENERATED_DIR
    import json as _json
    if figma_url and (prompt or "").strip():
        source, label = "figma+prompt", "Figma + Instructions"
    elif figma_url:
        source, label = "figma", "Figma"
    else:
        source, label = "prompt", "Instructions"
    meta = {
        "source":    source,
        "label":     label,
        "figma_url": figma_url or "",
        "prompt":    prompt or "",    # full text, no truncation
    }
    (GENERATED_DIR / project_name / ".meta.json").write_text(_json.dumps(meta, indent=2))
    # Log to history — full text, no truncation
    if figma_url:
        event = "Built from Figma" + (" + Instructions" if (prompt or "").strip() else "")
        detail = figma_url
    else:
        event = "Generated from prompt"
        detail = ""
    _append_history(project_name, event, detail, figma_url=figma_url or "", prompt=prompt or "",
                    instructions=instructions)
    # Update fast registry
    registry_upsert(
        project_name,
        title=title or project_name,
        hasApp=has_app,
        type="react",
        source=source,
        sourceLabel=label,
        figmaUrl=figma_url or "",
        prompt=prompt or "",    # full text
    )


def _run_generate(req: GenerateRequest, request_id: str = "") -> dict:
    import re, traceback, time as _t_gen
    _t_gen_start = _t_gen.time()

    def _progress(msg: str):
        if request_id:
            from datetime import datetime as _dt
            elapsed = _t_gen.time() - _t_gen_start
            ts = _dt.now().strftime("%H:%M:%S")
            stamped = f"[{ts} +{elapsed:.1f}s] {msg}"
            _progress_logs.setdefault(request_id, []).append(stamped)

    try:
        return _run_generate_inner(req, request_id, _progress)
    except Exception as e:
        tb = traceback.format_exc()
        err_str = str(e)
        # Surface common LiteLLM / connectivity errors with actionable messages
        if "AuthenticationError" in type(e).__name__ or "401" in err_str:
            raise RuntimeError(
                "LiteLLM authentication failed. "
                "Check that LITELLM_API_KEY is correct in .env."
            )
        if "Both LiteLLM and Bedrock failed" in err_str:
            raise  # Already has a clear message with both errors
        if "ConnectError" in type(e).__name__ or ("Connection" in err_str and "Bedrock" not in err_str):
            raise RuntimeError(
                "Cannot connect to LiteLLM proxy and Bedrock fallback also failed. "
                "Check that LITELLM_API_BASE is reachable (or AWS credentials for Bedrock). "
                f"Original error: {err_str[:300]}"
            )
        try:
            print(f"\n{'='*60}\n[GENERATE ERROR] {type(e).__name__}: {e}\n{tb}\n{'='*60}\n", flush=True)
        except UnicodeEncodeError:
            safe = f"\n{'='*60}\n[GENERATE ERROR] {type(e).__name__}: {e}\n{tb}\n{'='*60}\n"
            print(safe.encode("utf-8", errors="replace").decode("ascii", errors="replace"), flush=True)
        raise


def _run_generate_inner(req: GenerateRequest, request_id: str, _progress) -> dict:
    import re
    import time as _time
    _t0 = _time.time()

    import token_tracker
    token_tracker.reset(request_id)
    token_tracker.set_run_id(request_id)

    from agents.uigen_agent import (
        GENERATED_DIR, _next_port, _dev_ports, _dev_servers, _save_ports,
        _write_files, _npm_install, _start_vite, wait_for_port, kill_server,
        _patch_vite_for_ds,
    )

    # ── Figma URL → Screenshots + Wiring → Requirements → React/SQLite pipeline ──
    if req.figma_url and req.figma_url.strip():
        import re as _re2
        from agents.figma_to_web_using_api_agent import run as figma_run

        _progress("figma_api")
        _progress("screenshot_start")
        raw = figma_run(
            figma_url=req.figma_url.strip(),
            prompt=req.prompt or "",
            screenshots_only=False,
            project_name_override=req.project_name or None,
            progress_callback=_progress,
        )
        _progress(f"screenshot_done:{len(raw.get('screenshots', []))}")

        project_name = raw["project_name"]
        _project_request_ids[project_name] = request_id
        _write_meta(project_name, req.figma_url.strip(), req.prompt,
                    title=raw.get("title", ""), has_app=True)
        _append_buildlog(project_name, _progress_logs.get(request_id, []),
                         event="Built from Figma", duration_s=_time.time()-_t0)
        _generate_architecture(project_name, event="Built from Figma")

        # ── Token usage summary ───────────────────────────────────────────────
        for _line in token_tracker.format_summary(request_id, elapsed=_time.time() - _t0):
            _progress(f"llm_codegen:{_line}")

        _progress("ready")
        return {
            "projectName": project_name,
            "title":       raw.get("title", project_name),
            "description": f"Generated from Figma: {req.figma_url.strip()[:60]}",
            "port":        raw.get("port"),
            "url":         raw.get("url"),
            "files":       raw.get("files", []),
            "type":        "react",
        }

    # ── API mode → ApiCrewOrchestrator pipeline (WebAPIGenerator) ─────────────
    if req.mode == "api":
        from api_agents.api_orchestrator import ApiCrewOrchestrator
        from api_agents.api_registry import upsert_api_project, append_api_buildlog, save_api_architecture, append_api_history
        from api_agents.api_runner import start_api_project, wait_for_api, seed_database
        from api_config import WEB_API_DIR, project_url as _api_project_url
        from datetime import datetime, timezone

        instructions = (req.instructions or "").strip()
        user_content = req.prompt
        if instructions:
            user_content = f"{req.prompt}\n\n## Detailed Requirements\n\n{instructions}"

        _progress("api:architecture")
        api_options = req.api_options or {}
        if not api_options.get("language"):
            api_options["language"] = req.backend_type or "python"
        language = api_options["language"]

        # Register the project→request-id mapping BEFORE the (multi-minute,
        # blocking) orchestrator call — not after, like the line below used to
        # be the only place this happened. Registering only after meant
        # /api/generate/progress/project/{name} returned an empty id for the
        # project's own name the entire time generation was running, so the
        # UI's Build Log tab (which polls that endpoint) saw nothing until
        # generation had already finished. Same slug rule the orchestrator
        # itself applies to project_name_override, so this matches whatever
        # name it ends up using when an override is given.
        if req.project_name:
            import re as _re_slug
            _expected_name = _re_slug.sub(r"[^a-z0-9-]", "-", req.project_name.lower()).strip("-") or "api-project"
            _project_request_ids[_expected_name] = request_id
            # Persist the submitted config now, not only once generation
            # finishes — the left panel's config form is local React state
            # that resets to its defaults on any remount (e.g. reconnecting
            # to an in-progress job after navigating away and back), which
            # was showing the wrong language/auth/rate-limit while a
            # generation was still running. Reading from the registry entry
            # instead of that local state survives a remount correctly.
            upsert_api_project(
                _expected_name,
                language=language,
                authType=api_options.get("auth_type", "none"),
                rateLimit=api_options.get("rate_limit", 100),
            )
            # .buildlog.json previously didn't exist at all until generation
            # fully finished (the only append_api_buildlog call was after
            # orchestrator.generate() returned) — running two generations
            # concurrently and switching between their Build Log tabs mid-run
            # looked like entries from one project bleeding into the other,
            # when really neither had anything persisted yet. Create the file
            # with a real first entry the moment generation actually starts.
            append_api_buildlog(_expected_name, ["Generation started..."],
                                 event="Generating", duration_s=0)

        orchestrator = ApiCrewOrchestrator(progress=_progress)
        result = orchestrator.generate(user_content, api_options=api_options,
                                        project_name_override=req.project_name or None)

        project_name = result["projectName"]
        _project_request_ids[project_name] = request_id

        # The orchestrator already flushes every file to disk incrementally as
        # each stage/entity finishes (see ApiCrewOrchestrator._flush_to_disk) —
        # specifically so a failure late in the pipeline, or even a runtime
        # startup crash after generation itself "succeeds", doesn't discard
        # already-generated work. This is now a redundant-but-harmless final
        # rewrite of the same content for the success path, not the only place
        # files get written.
        project_dir = WEB_API_DIR / project_name
        project_dir.mkdir(parents=True, exist_ok=True)
        for fpath, content in result["files"].items():
            out = project_dir / fpath
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(content, encoding="utf-8")

        # Also keep a copy of .env outside the project directory — some
        # generated apps overwrite their own .env at runtime (see
        # protected_env_file's docstring), so the runner and auth-forwarding
        # endpoints read from this untouchable copy instead of trusting
        # whatever the project's own .env currently says.
        if ".env" in result["files"]:
            from api_config import protected_env_file
            protected_env_file(project_name).write_text(result["files"][".env"], encoding="utf-8")

        _progress("api:starting")
        port = start_api_project(project_name, project_dir, language)
        # Java/Spring Boot cold starts (JPA + embedded Tomcat, plus Maven
        # resolving dependencies on a machine's first-ever Java generation)
        # have been observed taking longer than 60s, tripping this into
        # "start_failed" moments before the app actually would have come up —
        # this call already runs inside the background job, not the HTTP
        # response, so a longer wait here doesn't block anything user-facing.
        started = wait_for_api(project_name, port, timeout=120 if language == "java" else 45)
        if started:
            # Tables only exist once the app's own startup (Hibernate ddl-auto /
            # SQLAlchemy create_all) has actually run, hence AFTER wait_for_api
            # confirms it's up, not before. Report the outcome — this happens
            # after generate() already returned, so nothing else would show
            # a missing/failed seed step anywhere the UI can see it.
            _progress(f"api:seeding — {seed_database(project_name, project_dir, language)}")
        else:
            # Explicit, not silent — otherwise a boot failure here (e.g. a
            # Spring context error unrelated to seeding at all) reads later as
            # "seeding is broken", when actually seeding was correctly never
            # attempted because there's no app/tables yet to seed. The next
            # successful Start (after whatever actually broke the boot gets
            # fixed) runs seed_database() itself — see /api/webapi/start/{name}.
            _progress("api:seeding — skipped, app did not start within the timeout; "
                       "fix the boot failure (see api_server.log) and Start again to seed")

        upsert_api_project(
            project_name,
            # Prefer the user's own typed name over the architect LLM's own
            # title choice when one was actually given — project_name_override
            # already forces the folder/registry KEY to match what was typed,
            # but the LLM's title always won for the DISPLAYED name, which the
            # UI shows far more prominently than the slug. That's exactly the
            # nothing-matches-what-I-typed impression this fixes: the name was
            # never actually being overridden anywhere the user could see it.
            title=req.project_name if req.project_name else result.get("title", project_name),
            description=result.get("description", ""),
            language=language,
            authType=api_options.get("auth_type", "none"),
            port=port,
            status="running" if started else "start_failed",
            createdAt=datetime.now(timezone.utc).isoformat(),
        )

        _elapsed = _time.time() - _t0
        for _line in token_tracker.format_summary(request_id, elapsed=_elapsed):
            _progress(f"llm_codegen:{_line}")

        if result.get("architecture"):
            save_api_architecture(project_name, result["architecture"])
            try:
                # The HTML doc is a cosmetic visualization built from
                # LLM-produced architecture JSON, whose exact shape isn't
                # schema-enforced — a stray non-dict field would otherwise
                # raise here and fail the ENTIRE job even though the API is
                # already generated, started, and registered as running by
                # this point. Never let this secondary feature take the
                # primary pipeline down with it.
                _generate_api_architecture_html(
                    project_dir, project_name, language,
                    api_options.get("auth_type", "none"), api_options.get("rate_limit", 0),
                    result["architecture"], datetime.now(timezone.utc).isoformat(),
                )
            except Exception as _arch_html_err:
                print(f"[api-architecture-html] failed for {project_name}: {_arch_html_err}", flush=True)
        append_api_buildlog(project_name, _progress_logs.get(request_id, []),
                            event="Generated API from prompt", duration_s=_elapsed)
        append_api_history(project_name, "Generated", prompt=req.prompt, instructions=req.instructions or "")

        _progress("api:ready")
        result["type"] = "api"
        result["files"] = sorted(result["files"].keys())
        result["port"] = port if started else None
        result["url"] = _api_project_url(port) if started else None
        if not started:
            result["warning"] = "Generated files were written, but the dev server didn't come up in time — check api_server.log in the project folder."
        return result

    # ── Text prompt → Multi-agent pipeline → React/TS/Tailwind/Vite ──────────
    from agents.uigen_agent import generate_project

    # Build the full user message — append Markdown instructions if provided
    instructions = (req.instructions or "").strip()
    user_content = req.prompt
    if instructions:
        _progress(f"llm_codegen:Applying detailed instructions ({len(instructions)} chars)…")
        user_content = (
            f"{req.prompt}\n\n"
            f"## Detailed Instructions\n\n{instructions}"
        )

    # Resolve project name override
    project_name_override = None
    if req.project_name:
        project_name_override = re.sub(r"[^a-z0-9-]", "-", req.project_name.lower()).strip("-") or None

    result = generate_project(
        user_content,
        progress=_progress,
        project_name_override=project_name_override,
        architecture=req.architecture,
        backend_type=req.backend_type,
    )

    project_name = result["projectName"]
    _project_request_ids[project_name] = request_id
    _write_meta(project_name, req.figma_url, req.prompt, title=result.get("title", project_name),
                has_app=True, instructions=instructions)

    # Save architecture as draft for future reference
    if result.get("architecture"):
        from agents.draft_preview import format_draft_markdown
        arch = result["architecture"]
        draft_data = {
            "architecture": arch,
            "markdown": format_draft_markdown(arch, req.prompt),
            "projectName": project_name,
            "title": result.get("title", project_name),
            "pageCount": len(arch.get("pages", [])),
        }
        _save_draft_to_disk(project_name, draft_data)

    # ── Token usage summary ───────────────────────────────────────────────────
    _elapsed = _time.time() - _t0
    for _line in token_tracker.format_summary(request_id, elapsed=_elapsed):
        _progress(f"llm_codegen:{_line}")

    _append_buildlog(project_name, _progress_logs.get(request_id, []),
                     event="Generated from prompt", duration_s=_elapsed)
    _generate_architecture(project_name, event="Generated", backend_type=req.backend_type)
    _progress("ready")
    result["type"] = "react"
    return result


def _validate_json_files(files: dict, prompt: str, instructions: str, _progress) -> dict:
    """
    Scan all .json data files in files dict. If any are empty or invalid JSON,
    regenerate them using the LLM based on the data schema in types.ts and index.ts.
    """
    import json

    broken: list[str] = []
    for path, content in files.items():
        if not path.endswith(".json"):
            continue
        # Skip config files — only data files in src/data/ matter
        if not path.startswith("src/data/"):
            continue
        # Normalize list content (LLM sometimes returns list of dicts or strings)
        if isinstance(content, list):
            content = "\n".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            )
            files[path] = content
        text = content.strip() if content else ""
        if not text:
            broken.append(path)
            continue
        try:
            json.loads(text)
        except json.JSONDecodeError:
            # Try the repair function first
            from agents.uigen_agent import _repair_json
            repaired = _repair_json(text, path)
            try:
                json.loads(repaired)
                files[path] = repaired
            except json.JSONDecodeError:
                broken.append(path)

    if not broken:
        return files

    _progress(f"llm_codegen:⚠️ {len(broken)} broken/empty JSON file(s) detected — regenerating…")

    # Gather context: types.ts tells us the schema, index.ts shows what fields are needed
    types_ts = files.get("src/types.ts", "")
    index_ts = files.get("src/data/index.ts", "")

    from agents.llm import chat_json

    for bp in broken:
        # Infer what this file should contain from its name and the type definitions
        file_name = bp.split("/")[-1].replace(".json", "")
        regen_prompt = (
            f"The data file '{bp}' is missing or broken. Generate realistic dummy data for it.\n\n"
            f"Type definitions (src/types.ts):\n{types_ts[:6000]}\n\n"
            f"Data index (src/data/index.ts):\n{index_ts[:3000]}\n\n"
        )
        if instructions:
            regen_prompt += f"Context from instructions:\n{instructions[:3000]}\n\n"
        regen_prompt += (
            f"Generate 20-50 records of realistic data for '{file_name}' matching the TypeScript types above.\n"
            f"Return JSON: {{\"data\": [<array of records>]}}\n"
            f"IMPORTANT: Must be valid JSON. Use null (not undefined) for missing values."
        )
        try:
            result = chat_json(
                messages=[{"role": "user", "content": regen_prompt}],
                system="You are a data generator. Return ONLY valid JSON matching the requested schema.",
                max_tokens=16000,
                temperature=0.2,
            )
            regen_data = result.get("data", result.get("files", {}).get(bp))
            if regen_data:
                files[bp] = json.dumps(regen_data, indent=2)
                _progress(f"llm_codegen:✓ Regenerated {bp} ({len(regen_data) if isinstance(regen_data, list) else '?'} records)")
            else:
                # Fallback: write empty array so Vite doesn't crash
                files[bp] = "[]"
                _progress(f"llm_codegen:⚠️ Could not regenerate {bp} — wrote empty array")
        except Exception as e:
            # Last resort: empty array is valid JSON and won't crash Vite
            files[bp] = "[]"
            _progress(f"llm_codegen:⚠️ Failed to regenerate {bp}: {e} — wrote empty array")

    return files


def _run_refine(project_name: str, prompt: str, request_id: str, comment: str = "", instructions: str = "", backend_type: str = "") -> dict:
    """
    Update an existing project's code based on a refinement prompt.
    Reads all existing source files, sends them + prompt to Claude, writes updated files back.
    """
    import re, traceback
    import time as _time
    _t0 = _time.time()

    import token_tracker
    token_tracker.reset(request_id)
    token_tracker.set_run_id(request_id)

    from agents.uigen_agent import GENERATED_DIR
    from agents.figma_to_web_using_playwright_agent import is_figma_project

    def _progress(msg: str):
        if request_id:
            from datetime import datetime as _dt
            elapsed = _time.time() - _t0
            ts = _dt.now().strftime("%H:%M:%S")
            stamped = f"[{ts} +{elapsed:.1f}s] {msg}"
            _progress_logs.setdefault(request_id, []).append(stamped)

    project_dir = GENERATED_DIR / project_name
    if not project_dir.exists():
        raise RuntimeError(f"Project '{project_name}' not found")

    _progress("llm")

    if is_figma_project(project_name):
        # HTML project — read existing files
        _progress("llm_codegen:Reading existing HTML project files")
        existing: dict[str, str] = {}
        for f in project_dir.rglob("*"):
            if f.is_file() and f.suffix in (".html", ".css", ".js", ".json"):
                rel = f.relative_to(project_dir).as_posix()
                try:
                    existing[rel] = f.read_text(encoding="utf-8")
                except Exception:
                    pass

        from agents.figma_to_web_using_playwright_agent import _parse_multifile
        from agents.llm import chat

        _HTML_REFINE_SYSTEM = (
            "You are an expert web developer updating an existing multi-file HTML/CSS/JS web app.\n\n"
            "OUTPUT RULES:\n"
            "- Use === path === blocks for every changed file\n"
            "- Output the COMPLETE file content — no truncation, no ellipsis, no '// ... rest unchanged'\n"
            "- Output ONLY files that change; omit unchanged files entirely\n"
            "- Do NOT wrap content in markdown fences\n"
            "- Do NOT add <script> or </script> tags inside .js files — they are loaded externally\n\n"
            "DATA RULES:\n"
            "- Use ONE JSON file per entity (e.g. data/inventory.json, data/oems.json)\n"
            "- If a data/app.json exists and you need new data, split it into separate files\n"
            "- Each data file is a JSON array of records with consistent fields\n"
            "- New data files get 8-15 rows of realistic dummy data\n\n"
            "API RULES (js/api.js):\n"
            "- Keep the existing module pattern (IIFE returning named functions)\n"
            "- Add one function per new data entity\n"
            "- Read-functions support filter params (q, status, etc.) even if UI doesn't use them yet\n"
            "- Mutations (add/update/delete) update the in-memory _store so changes persist for the session\n"
            "- Login accepts any non-empty userId+password — stub only\n\n"
            "CHART RULES:\n"
            "- Use D3.js ONLY — remove any Chart.js usage if present\n"
            "- If index.html loads chart.js CDN, replace it with: <script src=\"https://cdn.jsdelivr.net/npm/d3@7\"></script>\n"
            "- All chart code goes in js/charts.js with functions: renderBarChart(id, data, opts), renderLineChart(id, data, opts), renderDonutChart(id, data, opts)\n"
            "- Each function appends an SVG into document.getElementById(id), with mouseover tooltips\n"
            "- Chart containers in HTML: <div id='chart-id' style='position:relative;width:100%;height:220px;'></div>\n"
            "- app.js calls API then passes data to chart functions\n\n"
            "BEHAVIOUR RULES:\n"
            "- Preserve all existing functionality; only change what the user asked for\n"
            "- Wire new interactive elements (filters, modals, forms) to the API functions\n"
        )

        # Build file listing — skip screenshots and wiring.json, no truncation for code files
        SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
        SKIP_FILES = {"wiring.json"}
        file_context = ""
        for path, content in sorted(existing.items()):
            if any(path.endswith(s) for s in SKIP_SUFFIXES):
                continue
            if path.split("/")[-1] in SKIP_FILES:
                continue
            # Generous limit — complex files need full context
            snippet = content[:8000] + ("\n...[truncated — file continues]" if len(content) > 8000 else "")
            file_context += f"\n=== {path} ===\n{snippet}\n"

        refine_prompt = (
            f"Here are the current project files:\n{file_context}\n\n"
            f"User's update request:\n{prompt}\n\n"
            "Apply the requested changes. Output the complete updated content for every file that changes, "
            "using === path === blocks. Output ONLY the files that need changes."
        )

        _progress("llm_codegen:Applying refinements with Claude")
        raw = chat(
            messages=[{"role": "user", "content": refine_prompt}],
            system=_HTML_REFINE_SYSTEM,
            max_tokens=64000,
            temperature=0.2,
        )
        _, _, updated_files = _parse_multifile(raw)

        if not updated_files:
            raise RuntimeError("Claude returned no files — try a more specific prompt")

        # Strip stray <script> tags from .js files
        import re as _re3
        for rel_path in list(updated_files.keys()):
            if rel_path.endswith(".js"):
                c = updated_files[rel_path]
                c = _re3.sub(r"\s*</script>\s*$", "", c)
                c = _re3.sub(r"^\s*<script[^>]*>\s*", "", c)
                updated_files[rel_path] = c.strip()

        # Enforce data/api.js/charts.js/D3 rules on changed files merged with existing
        from agents.figma_to_web_using_api_agent import _enforce_rules as _enf
        merged = {**existing, **updated_files}
        merged = _enf(merged)
        # Only write files that were in updated_files or newly created by enforcer
        for k in list(merged.keys()):
            if k not in existing or merged[k] != existing.get(k):
                updated_files[k] = merged[k]
        # Remove app.json if enforcer split it
        if "data/app.json" in updated_files and "data/app.json" not in merged:
            del updated_files["data/app.json"]

        # Write updated files (only ones that changed)
        _progress("write")
        written = []
        from agents.uigen_agent import _repair_json
        from agents.sanitize_js import sanitize as _sanitize
        for rel_path, content in updated_files.items():
            fp = project_dir / rel_path
            fp.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, list):
                content = "\n".join(
                    item.get("text", "") if isinstance(item, dict) else str(item)
                    for item in content
                )
            if not content or not content.strip():
                if fp.exists():
                    continue
            if rel_path.endswith(".json"):
                content = _repair_json(content, rel_path)
            content = _sanitize(content, rel_path)
            fp.write_text(content, encoding="utf-8")
            written.append(rel_path)

        # Restart HTML server
        from agents.figma_to_web_using_playwright_agent import (
            kill_figma_server, start_figma_project, _html_ports
        )
        _progress("start")
        kill_figma_server(project_name, forget_port=False)
        result = start_figma_project(project_name)
        _append_history(project_name, "Refined", prompt=prompt, comment=comment,
                        instructions=instructions or "")
        _append_buildlog(project_name, _progress_logs.get(request_id, []),
                         event="Refined", duration_s=_time.time()-_t0)
        _progress("ready")
        return {**result, "files": written, "type": "html"}

    else:
        # React/Vite project — read ALL existing source files (src/ + root-level config + api/)
        _progress("llm_codegen:Reading existing React project files")
        src_dir = project_dir / "src"
        api_dir = project_dir / "api"
        existing: dict[str, str] = {}
        # Root-level files that must survive a refine
        for name in ("package.json", "index.html", "tsconfig.json",
                     "tailwind.config.js", "postcss.config.js"):
            fp = project_dir / name
            if fp.exists():
                try:
                    existing[name] = fp.read_text(encoding="utf-8")
                except Exception:
                    pass
        # src/ tree
        for f in src_dir.rglob("*") if src_dir.exists() else []:
            if f.is_file() and f.suffix in (".tsx", ".ts", ".css", ".json"):
                rel = f.relative_to(project_dir).as_posix()
                try:
                    existing[rel] = f.read_text(encoding="utf-8")
                except Exception:
                    pass
        # api/ tree — preserve API server, schema, seed, .env
        for f in api_dir.rglob("*") if api_dir.exists() else []:
            if f.is_file() and (f.suffix in (".py", ".sql", ".txt") or f.name == ".env"):
                rel = f.relative_to(project_dir).as_posix()
                try:
                    existing[rel] = f.read_text(encoding="utf-8")
                except Exception:
                    pass
        # backend/ tree — preserve Java Spring Boot files
        backend_dir = project_dir / "backend"
        for f in backend_dir.rglob("*") if backend_dir.exists() else []:
            if f.is_file() and (f.suffix in (".java", ".xml", ".properties", ".sql") or f.name in (".env", ".backend_type")):
                if "target" in f.parts or ".mvn" in f.parts:
                    continue
                rel = f.relative_to(project_dir).as_posix()
                try:
                    existing[rel] = f.read_text(encoding="utf-8")
                except Exception:
                    pass

        from agents.llm import chat, chat_json

        # Lightweight system prompt for refine — NOT the full 52k generation prompt.
        # The full SYSTEM_PROMPT is 13k tokens and leaves almost no room for files.
        refine_system = (
            "You are an expert React/TypeScript developer updating an existing app built with:\n"
            "- React 18 + Vite + TypeScript\n"
            "- Tailwind CSS for styling\n"
            "- D3.js for all charts and maps (NO recharts, highcharts, or react-simple-maps)\n"
            "- mobility-global-ds for Header, Sidebar, Card, Button, Badge etc.\n"
            "- react-router-dom v6 for routing\n"
            "- topojson-client + us-atlas + world-atlas for map rendering\n\n"
            "RULES:\n"
            "- Keep all existing pages and functionality unless told to remove them\n"
            "- Only add/modify what the user explicitly requests\n"
            "- Return ONLY the files that need to change, keyed by their relative path\n"
            "- Response must be valid JSON with a single top-level key: 'files'\n"
            "- CRITICAL: Each returned file must be the COMPLETE file content — no truncation, no '// ... rest unchanged', no ellipsis, no '// existing code here' placeholders\n"
            "- CRITICAL: Preserve EVERY existing import, function, component, and data structure unless explicitly asked to change it\n"
            "- CRITICAL: If a file has 500 lines, your returned version must also have ~500 lines — do NOT collapse or omit sections\n"
            "- Do NOT use react-simple-maps, highcharts, recharts, or chart.js\n"
            "- For maps: use D3 + topojson, geo.id numeric lookup, NUMERIC_TO_ISO2 table\n"
            "- useMemo ALL data arrays passed as useEffect deps to prevent blink/loop\n"
            "- ALL D3 charts MUST have hover tooltips via React state (useState<{x,y,text}|null>). "
            "Container needs position:'relative'. Render tooltip as absolute-positioned div.\n"
            "- API-FIRST: Do NOT create src/data/*.json files or import from '../data/'. "
            "All data comes from the SQLite database via /api/data/{table}. "
            "Use the useApi hook (src/hooks/useApi.ts) to fetch data. "
            "New tables go in schema.sql + seed.sql, NOT JSON files.\n"
            "- AI CHAT /api/chat: The endpoint expects body {messages: [{role:'user',content:'...'},...], context?: {...}}. "
            "The 'messages' field is REQUIRED and must be an array of {role, content} objects (OpenAI format). "
            "Do NOT send {message: string} or {prompt: string}. Maintain conversation history and send full array each request.\n"
        )

        instructions_trimmed = (instructions or "").strip()
        if instructions_trimmed:
            _progress(f"llm_codegen:Applying detailed instructions ({len(instructions_trimmed)} chars)…")

        # ── Smart context selection ────────────────────────────────────────────
        # Restored from the single-shot-first design (removed earlier this session
        # when two-pass became the unconditional path): most refines touch a small
        # number of files and don't need per-file add/modify classification badly
        # enough to justify N+1 LLM calls when 1 call reliably does the job. Extract
        # meaningful keywords from BOTH prompt and instructions for relevance scoring.
        import re as _re_kw
        _kw_source = prompt + " " + instructions_trimmed[:5000]
        _kw_raw = set(w.lower() for w in _re_kw.findall(r'[a-zA-Z]{4,}', _kw_source))
        _STOP_KW = {
            'this', 'that', 'with', 'from', 'have', 'will', 'your', 'page', 'show',
            'when', 'click', 'please', 'make', 'into', 'data', 'file', 'comp',
            'also', 'just', 'need', 'want', 'more', 'like', 'then', 'they', 'there',
            'been', 'were', 'where', 'which', 'what', 'their', 'some', 'would',
            'should', 'could', 'working', 'please', 'allow', 'based', 'within',
            'following', 'using', 'work', 'code', 'adds', 'added', 'existing',
            'include', 'return', 'button', 'table', 'filter', 'each', 'below',
            'above', 'section', 'component', 'display', 'update', 'react',
            'import', 'export', 'const', 'function', 'string', 'number',
        }
        _kws = _kw_raw - _STOP_KW

        # Always include these structural files regardless of relevance
        _ESSENTIAL = {
            "src/types.ts", "src/data/index.ts", "src/App.tsx",
            "package.json", "src/main.tsx",
        }

        def _file_relevance(path: str, content: str) -> int:
            pl = path.lower()
            cl = content[:3000].lower()
            score = 0
            for kw in _kws:
                if kw in pl:
                    score += 20   # filename match is highly relevant
                if kw in cl:
                    score += 2    # content match is a weak signal
            return score

        # Score every non-essential file
        _scored: list[tuple[int, str]] = []
        for _p in existing:
            if _p not in _ESSENTIAL:
                _scored.append((_file_relevance(_p, existing[_p]), _p))
        _scored.sort(key=lambda x: -x[0])

        # Build context within a total character budget.
        # Bedrock context window ~200k tokens (~800k chars). Target ≤60k input chars for files
        # to leave room for instructions + output.
        # Only include files that scored > 0 (have at least one keyword match).
        _MAX_PER_FILE = 30_000   # ~900 lines — large enough for most pages
        _MAX_TOTAL    = max(30_000, 70_000 - min(len(instructions_trimmed), 30_000))

        def _snip(c: str) -> str:
            return c[:_MAX_PER_FILE] + ("\n...[truncated]" if len(c) > _MAX_PER_FILE else "")

        file_context = ""
        _ctx_total = 0
        _included: set[str] = set()

        # 1. Essential files always in (but snipped to 15k each — they're structural reference)
        _ESSENTIAL_SNIP = 15_000
        for _p in _ESSENTIAL:
            if _p in existing:
                s = existing[_p][:_ESSENTIAL_SNIP] + ("\n...[truncated]" if len(existing[_p]) > _ESSENTIAL_SNIP else "")
                file_context += f"\n// FILE: {_p}\n{s}\n"
                _ctx_total += len(s)
                _included.add(_p)

        # 2. Relevant non-essential files (score > 0) until budget exhausted
        for _score, _p in _scored:
            if _score == 0:
                break
            if _ctx_total >= _MAX_TOTAL:
                break
            s = _snip(existing[_p])
            file_context += f"\n// FILE: {_p}\n{s}\n"
            _ctx_total += len(s)
            _included.add(_p)

        _skipped = [p for _, p in _scored if p not in _included]
        _progress(
            f"llm_codegen:Context: {len(_included)} files / {_ctx_total:,} chars sent"
            + (f"; {len(_skipped)} irrelevant files omitted" if _skipped else "")
        )
        # ── End smart context selection ────────────────────────────────────────

        refine_user = (
            f"Existing project files:\n{file_context}\n\n"
            f"Refinement request: {prompt}"
        )
        if instructions_trimmed:
            refine_user += f"\n\n## Detailed Instructions\n\n{instructions_trimmed}"
        refine_user += "\n\nReturn only the files that need to change as JSON with key 'files'."

        _progress("llm_codegen:Generating updated files…")

        # ── Heartbeat: emit progress during long LLM calls ─────────────────────
        import threading as _threading
        class _RefineHeartbeat:
            def __init__(self, interval: int = 30):
                self._interval = interval
                self._start = _time.time()
                self._stop_event = _threading.Event()
                self._thread = _threading.Thread(target=self._run, daemon=True)
            def start(self):
                self._thread.start()
            def stop(self):
                self._stop_event.set()
            def _run(self):
                while not self._stop_event.wait(self._interval):
                    elapsed = int(_time.time() - self._start)
                    _progress(f"llm_codegen:...still generating ({elapsed}s elapsed)")

        # ── Page-preservation logic for refine path ─────────────────────────────
        # Detect existing page files and determine which should be protected
        import re as _re_pages
        _existing_page_files: set[str] = set()
        for _fp in existing:
            if _fp.startswith("src/pages/") and _fp.endswith(".tsx"):
                _existing_page_files.add(_fp)

        # Detect "keep existing pages" intent
        _prompt_and_instr = (prompt + " " + instructions_trimmed).lower()
        _KEEP_PHRASES = [
            "keep all existing pages", "keep existing pages",
            "do not modify existing pages", "don't modify existing pages",
            "do not change existing pages", "don't change existing pages",
            "leave existing pages", "existing pages unchanged",
            "do not update existing pages", "don't update existing pages",
            "keep all existing pages and data unchanged",
        ]
        _keep_existing = any(ph in _prompt_and_instr for ph in _KEEP_PHRASES)

        def _page_explicitly_mentioned(page_path: str) -> bool:
            """Check if a page file is explicitly mentioned in the prompt/instructions."""
            name = page_path.replace("src/pages/", "").replace(".tsx", "")
            name_lower = name.lower()
            name_spaced = _re_pages.sub(r'([a-z])([A-Z])', r'\1 \2', name).lower()
            for variant in set([name_lower, name_spaced]):
                if _re_pages.search(r'\b' + _re_pages.escape(variant) + r'\b', _prompt_and_instr):
                    return True
            return False

        def _filter_preserved_pages(file_list: list[str]) -> list[str]:
            """Remove existing page files that should be preserved from the change list."""
            filtered = []
            for f in file_list:
                if f in _existing_page_files:
                    if _keep_existing:
                        _progress(f"llm_codegen:⊘ Preserving {f} (keep-existing-pages)")
                        continue
                    if not _page_explicitly_mentioned(f):
                        _progress(f"llm_codegen:⊘ Preserving {f} (not mentioned in prompt)")
                        continue
                filtered.append(f)
            return filtered

        # ── Two-pass refine: first identify which files need to change, then
        # generate each one individually (each call classified add vs modify) ────
        def _two_pass_refine() -> dict:
            _progress("llm_codegen:Two-pass mode — identifying files to change…")
            # Trim instructions to 4k chars for Pass 1 (enough to understand what's needed)
            _instr_p1 = instructions_trimmed[:4_000] + ("…[trimmed]" if len(instructions_trimmed) > 4_000 else "")
            # Pass 1: ask which files need to change (tiny response)
            # MUST include instructions — without them the model can't know what to create/modify
            id_user = f"Refinement request: {prompt}\n\n"
            if _instr_p1:
                id_user += f"## Detailed Instructions\n\n{_instr_p1}\n\n"
            id_user += (
                f"Available files:\n" + "\n".join(f"  - {p}" for p in existing) + "\n\n"
                "Based on the refinement request and instructions above, list ONLY the file paths "
                "that need to be created or modified. Include new files that don't exist yet. "
                "Do NOT include existing page files that the user did not ask to change. "
                "Return JSON: {\"files\": [\"path1\", \"path2\", ...]}"
            )
            id_data = chat_json(
                messages=[{"role": "user", "content": id_user}],
                system=refine_system,
                max_tokens=2000,
                temperature=0.1,
            )
            to_change = id_data.get("files", [])
            if not to_change:
                raise RuntimeError("Two-pass: model returned no files to change")
            # Filter out preserved pages BEFORE expensive generation
            to_change = _filter_preserved_pages(to_change)
            if not to_change:
                raise RuntimeError("Two-pass: all identified files are preserved — nothing to generate")
            _progress(f"llm_codegen:Two-pass — generating {len(to_change)} file(s)…")

            # Pass 2: generate each file in PARALLEL (I/O-bound LLM calls)
            result_files: dict[str, str] = {}
            _instr2 = instructions_trimmed[:5_000] + ("…[trimmed]" if len(instructions_trimmed) > 5_000 else "")

            def _gen_one_file(target_path: str) -> tuple[str, str]:
                # Deterministic classification — no LLM guesswork needed, `existing` already
                # tells us the truth. This is the hook point for treating adds and modifies
                # differently: adds get a clean-slate prompt (nothing to preserve, so a
                # generation slip can't corrupt unrelated code); modifies get the full current
                # content plus an explicit instruction to leave everything else byte-for-byte
                # alone, which is what actually failed before (a full-file "regenerate ~900
                # lines, mostly unchanged" transcription introduced a stray-quote typo).
                _is_new = target_path not in existing
                _original_content = existing.get(target_path, "")
                _progress(f"llm_codegen:{'Creating new' if _is_new else 'Modifying existing'} file: {target_path}")
                _fc2 = ""
                _fc2_budget = 25_000
                if not _is_new:
                    _target_content = _original_content[:40_000]
                    _fc2 += f"\n// FILE: {target_path} (CURRENT CONTENT — preserve this exactly except for the requested change)\n{_target_content}\n"
                _schema_key = next(
                    (k for k in ("api/schema.sql", "backend/schema.sql", "schema.sql") if k in existing),
                    "schema.sql"
                )
                _structural = [_schema_key, "src/types.ts", "src/App.tsx"]
                for _ep in _structural:
                    if _ep in existing and _ep != target_path:
                        _snippet = existing[_ep][:8_000]
                        if len(_fc2) + len(_snippet) < _fc2_budget:
                            _fc2 += f"\n// FILE: {_ep} (reference only, for conventions/imports — do not reproduce)\n{_snippet}\n"

                gen_user = (
                    f"Existing project files:\n{_fc2}\n\n"
                    f"Refinement request: {prompt}\n\n"
                )
                if _instr2:
                    gen_user += f"## Detailed Instructions\n\n{_instr2}\n\n"
                if _is_new:
                    gen_user += (
                        f"Create the COMPLETE content for the NEW file: {target_path}\n"
                        f"This file does not exist yet, so there is nothing existing to preserve or "
                        f"risk breaking. Use the reference files above only to match naming/import "
                        f"conventions and real table/column names — do not reproduce their content.\n"
                        f"Return JSON: {{\"files\": {{\"{target_path}\": \"<complete file content>\"}}}}"
                    )
                else:
                    gen_user += (
                        f"Apply the requested change to the EXISTING file {target_path} shown above "
                        f"under 'CURRENT CONTENT'.\n"
                        f"CRITICAL: Preserve every line not directly affected by the requested change, "
                        f"character-for-character. Do NOT paraphrase, reformat, reorder, or re-type "
                        f"unrelated code from memory — copy it exactly as shown. Only the specific "
                        f"lines needed to satisfy the request should differ from the current content.\n"
                        f"Return the COMPLETE updated file (not a diff, not just the changed lines) as "
                        f"JSON: {{\"files\": {{\"{target_path}\": \"<complete file content>\"}}}}"
                    )

                try:
                    gen_data = chat_json(
                        messages=[{"role": "user", "content": gen_user}],
                        system=refine_system,
                        max_tokens=64000,
                        temperature=0.1,
                    )
                    for k, v in gen_data.get("files", {}).items():
                        # Modify-safety heuristic: a legitimate edit rarely shrinks a
                        # substantial file by more than half — that shape usually means
                        # the model dropped unrelated content while transcribing. Warn
                        # rather than silently reject/revert, since some refines genuinely
                        # do ask to simplify or trim a file.
                        if not _is_new and _original_content:
                            _orig_lines = _original_content.count("\n")
                            _new_lines = v.count("\n")
                            if _orig_lines > 20 and _new_lines < _orig_lines * 0.5:
                                _progress(
                                    f"llm_codegen:⚠️ {k} shrank from {_orig_lines} to {_new_lines} "
                                    f"lines — verify nothing unrelated was dropped."
                                )
                        return k, v
                except RuntimeError as _e2:
                    if "truncated" not in str(_e2).lower():
                        raise
                    _progress(f"llm_codegen:Two-pass — {target_path} too large for JSON, using raw mode…")
                    raw_user = (
                        f"Existing file:\n{existing.get(target_path, '')[:40_000]}\n\n"
                        f"Refinement request: {prompt}\n\n"
                    )
                    if _instr2:
                        raw_user += f"## Detailed Instructions\n\n{_instr2}\n\n"
                    raw_user += (
                        f"Generate the COMPLETE updated content for {target_path}.\n"
                        f"Output ONLY the file content. No JSON wrapping, no markdown fences, no explanation."
                    )
                    raw_content = chat(
                        messages=[{"role": "user", "content": raw_user}],
                        system="You are a React/TypeScript code generator. Output only raw file content.",
                        max_tokens=64000,
                        temperature=0.1,
                    )
                    if raw_content.startswith("```"):
                        lines = raw_content.splitlines()
                        raw_content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
                    return target_path, raw_content.strip()
                return target_path, ""

            from concurrent.futures import ThreadPoolExecutor as _TPE, as_completed as _as_completed
            with _TPE(max_workers=min(4, len(to_change))) as pool:
                futures = {pool.submit(_gen_one_file, tp): tp for tp in to_change}
                for fut in _as_completed(futures):
                    try:
                        k, v = fut.result()
                        if k and v:
                            result_files[k] = v
                            _progress(f"llm_codegen:✓ {k} generated ({len(v):,} chars)")
                    except Exception as _fe:
                        _progress(f"llm_codegen:⚠️ {futures[fut]} failed: {_fe}")

            # A file whose generation call fails (e.g. chat_json exhausts its own 2
            # internal attempts without valid JSON) is silently absent from
            # result_files above — nothing there raises. Left alone, that meant a
            # refine could "succeed" with e.g. App.tsx correctly wired to import a
            # new page while the page file itself was never written, breaking the
            # whole app on the next Vite build. Retry each missing file once more,
            # sequentially (parallel resource contention is one plausible reason the
            # first attempt failed), before giving up.
            _failed = [tp for tp in to_change if tp not in result_files]
            if _failed:
                _progress(f"llm_codegen:⚠️ Retrying {len(_failed)} failed file(s) sequentially: {', '.join(_failed)}")
                for tp in _failed:
                    try:
                        k, v = _gen_one_file(tp)
                        if k and v:
                            result_files[k] = v
                            _progress(f"llm_codegen:✓ {k} generated on retry ({len(v):,} chars)")
                    except Exception as _fe2:
                        _progress(f"llm_codegen:⚠️ {tp} failed again: {_fe2}")

            _still_failed = [tp for tp in to_change if tp not in result_files]
            if _still_failed:
                raise RuntimeError(
                    f"Two-pass: could not generate {len(_still_failed)} file(s) after retry: "
                    f"{', '.join(_still_failed)}. Refusing to report success with missing files — "
                    f"please retry the refine."
                )

            if not result_files:
                raise RuntimeError("Two-pass: no files were generated")
            return {"files": result_files}

        # Single-shot first, two-pass only as a fallback: one combined call is
        # dramatically faster than N+1 calls (one to list changed files, one per
        # file) for the common case of a refine touching a handful of files, and
        # that per-file isolation's real value — deterministic add/modify
        # classification, no risk of a big new page crowding out a small schema
        # change — only earns its cost when the single call actually can't cope
        # (truncates, or the context genuinely overflows). This mirrors the
        # single-shot-first design this session had removed in favor of always
        # isolating files; that removal fixed a real corruption bug but made every
        # refine several times slower than it needs to be for the common case.
        _hb = _RefineHeartbeat(interval=30)
        _hb.start()
        try:
            try:
                data = chat_json(
                    messages=[{"role": "user", "content": refine_user}],
                    system=refine_system,
                    max_tokens=64000,
                    temperature=0.1,
                )
            except RuntimeError as _e:
                if "truncated" in str(_e).lower() or "overflow" in str(_e).lower() or "context" in str(_e).lower():
                    _progress("llm_codegen:Single-pass truncated — switching to two-pass refine…")
                    data = _two_pass_refine()
                else:
                    raise
        finally:
            _hb.stop()

        updated_files = data.get("files", {})
        if not updated_files:
            raise RuntimeError("Claude returned no files")

        # Filter out preserved pages from single-pass result too
        _allowed_pages = set(_filter_preserved_pages(list(updated_files.keys())))
        for _fp_check in list(updated_files.keys()):
            if _fp_check in _existing_page_files and _fp_check not in _allowed_pages:
                del updated_files[_fp_check]

        # Merge: keep all existing files, overlay only what Claude changed
        files = {**existing, **updated_files}

        # ── Validate JSON data files — regenerate any that are empty or invalid ──
        files = _validate_json_files(files, prompt, instructions_trimmed, _progress)

        # Fix common LLM mistakes — local fixers first, then full postprocessor suite
        files = _fix_json_named_imports(files)
        files = _fix_data_index(files)
        files = _fix_main_tsx(files, project_name)
        files = _fix_custom_components(files)
        files = _fix_ds_imports(files)
        files = _fix_pptx_export(files)
        files = _fix_d3_chart_code(files)
        from agents.postprocessors import _fix_useapi_full_path, _fix_useapi_default_import
        files = _fix_useapi_default_import(files)
        files = _fix_useapi_full_path(files)
        # Nine refine-only regex heuristics (_fix_unquoted_object_keys through
        # _fix_common_syntax) used to run here on every refine, unconditionally,
        # over the FULL merged file set — not just files this refine changed.
        # None of them exist in TurboUIGen's refine (the reference implementation
        # this pipeline was forked from), and several turned out to have real
        # false-positive corruption bugs (e.g. _fix_unquoted_object_keys mistaking
        # `const m: Record<...>` for an unquoted object key, _fix_lucide_icons
        # turning `onClose` into `onX`) that silently re-broke already-correct,
        # untouched files on every subsequent refine. Removed rather than kept
        # patching one bug at a time — generation doesn't need them either.
        from agents.uigen_agent import (
            _dev_ports, _dev_servers, _save_ports, _next_port,
            _write_files, wait_for_port, kill_server, _start_vite,
            _ensure_shared_nm_once, _link_shared_nm,
            _get_project_deps, _npm_install, _scan_imports_from_files,
            _bundle_api_server, _ensure_schema_sql, _api_ports, _next_api_port,
        )

        # ── API-first: ensure schema exists, bundle API server ────────────────
        # For refine: disk is the source of truth for backend type (project already exists)
        bt_file = project_dir / "backend" / ".backend_type"
        if bt_file.exists():
            _bt_raw = bt_file.read_text(encoding="utf-8").strip()
            backend_type = "java" if "java" in _bt_raw else _bt_raw
        elif (project_dir / "backend" / "pom.xml").exists():
            backend_type = "java"
        elif not backend_type:
            backend_type = "python"

        files = _ensure_schema_sql(files)
        files = _bundle_api_server(files, backend_type=backend_type)

        # ── Completeness check: did the LLM actually add tables it was asked to? ──
        # A single multi-file refine call can return syntactically valid, complete
        # JSON that simply omits a file entirely — chat_json's truncation detection
        # can't catch this since nothing was cut off, the model just didn't write it.
        # This has silently dropped schema.sql table additions before (new page ships
        # fine, but its useApi() call 400s against a table that was never created).
        _requested_tables = set(
            m.group(1) for m in re.finditer(
                r"add\s+(?:a\s+new\s+|a\s+|the\s+)?[`'\"]?(\w+)[`'\"]?\s+table\b",
                f"{prompt}\n{instructions_trimmed}", re.IGNORECASE,
            )
        )
        if _requested_tables:
            _schema_key_check = next(
                (k for k in ("backend/schema.sql", "api/schema.sql", "schema.sql") if k in files),
                None,
            )
            _schema_text = files.get(_schema_key_check, "") if _schema_key_check else ""
            _missing_tables = [
                t for t in _requested_tables
                if not re.search(rf"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?{re.escape(t)}\b", _schema_text, re.IGNORECASE)
            ]
            if _missing_tables and _schema_key_check:
                _progress(
                    f"llm_codegen:⚠️ {', '.join(_missing_tables)} table(s) missing from "
                    f"{_schema_key_check} — asking Claude to add just that…"
                )
                _seed_key_check = _schema_key_check.replace("schema.sql", "seed.sql")
                _seed_text = files.get(_seed_key_check, "")
                _heal_user = (
                    f"Current {_schema_key_check}:\n{_schema_text}\n\n"
                    f"Current {_seed_key_check} (tail, for style reference):\n{_seed_text[-4000:]}\n\n"
                    f"The following table(s) were supposed to be added per these instructions but are "
                    f"missing: {', '.join(_missing_tables)}\n\n"
                    f"Original instructions:\n{instructions_trimmed}\n\n"
                    f"Add ONLY the missing table(s) — append CREATE TABLE IF NOT EXISTS statements to "
                    f"the existing {_schema_key_check} content, and append 50 realistic seed rows per "
                    f"table as INSERT statements to the existing {_seed_key_check} content. "
                    f"Return the COMPLETE updated content for both files (everything that already "
                    f"existed, plus your additions) as JSON: "
                    f"{{\"files\": {{\"{_schema_key_check}\": \"...\", \"{_seed_key_check}\": \"...\"}}}}"
                )
                try:
                    _heal_data = chat_json(
                        messages=[{"role": "user", "content": _heal_user}],
                        system=refine_system, max_tokens=16000, temperature=0.1,
                    )
                    _heal_files = _heal_data.get("files", {})
                    _still_missing = _missing_tables
                    if _schema_key_check in _heal_files:
                        _healed_schema = _heal_files[_schema_key_check]
                        _still_missing = [
                            t for t in _missing_tables
                            if not re.search(rf"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?{re.escape(t)}\b", _healed_schema, re.IGNORECASE)
                        ]
                        if not _still_missing:
                            files[_schema_key_check] = _healed_schema
                            if _seed_key_check in _heal_files:
                                files[_seed_key_check] = _heal_files[_seed_key_check]
                            _progress(f"llm_codegen:✓ Added missing table(s) to {_schema_key_check}")
                    if _still_missing:
                        _progress(
                            f"llm_codegen:⚠️ Could not auto-add {', '.join(_still_missing)} — "
                            f"try refining again with a more targeted prompt (e.g. "
                            f"\"add the {_still_missing[0]} table to schema.sql\")."
                        )
                except Exception as _heal_err:
                    _progress(
                        f"llm_codegen:⚠️ Auto-heal for missing table(s) failed ({_heal_err}) — "
                        f"try refining again with a more targeted prompt."
                    )

        port = _dev_ports.get(project_name) or _next_port()
        _dev_ports[project_name] = port

        # Assign API port if this project has an API server
        has_api_files = (
            "api/app_server.py" in files or "app_server.py" in files
            or "api_server.py" in files
            or "api/schema.sql" in files or "schema.sql" in files
            or "backend/.backend_type" in files or "backend/pom.xml" in files
        )
        api_port = _api_ports.get(project_name)
        if has_api_files and not api_port:
            api_port = _next_api_port()
            _api_ports[project_name] = api_port
        _save_ports()

        # Patch .env with the correct dynamic API port
        if api_port and "api/.env" in files:
            import re as _re_env
            files["api/.env"] = _re_env.sub(r"API_PORT=\d+", f"API_PORT={api_port}", files["api/.env"])

        # Patch Java application.properties with the correct dynamic API port
        if api_port and "backend/src/main/resources/application.properties" in files:
            import re as _re_props
            files["backend/src/main/resources/application.properties"] = _re_props.sub(
                r"server\.port=\d+", f"server.port={api_port}",
                files["backend/src/main/resources/application.properties"]
            )
        # Also patch backend/.env for Java backend
        if api_port and "backend/.env" in files:
            import re as _re_benv
            files["backend/.env"] = _re_benv.sub(r"PORT=\d+", f"PORT={api_port}", files["backend/.env"])

        # Run the FULL postprocessor suite (includes table name validation,
        # vite config injection, DS aliasing, badge fixes, etc.)
        from agents.postprocessors import run_all_postprocessors
        files = run_all_postprocessors(
            files, project_dir=project_dir, project_name=project_name,
            port=port, api_port=api_port or 0,
        )

        _progress("write")
        kill_server(project_name)
        _write_files(project_dir, files)

        # Install any new packages the LLM added (e.g. highcharts, d3, etc.)
        _progress("install")
        ok_shared, _ = _ensure_shared_nm_once()
        if ok_shared:
            project_deps = _get_project_deps(project_dir)
            # Scan actual source imports to catch packages the LLM uses but didn't declare
            scanned_imports = _scan_imports_from_files(project_dir)
            for pkg in scanned_imports:
                if pkg not in project_deps:
                    project_deps[pkg] = "latest"
            def _pkg_progress(msg: str):
                _progress(f"llm_codegen:{msg}")
            ok, npm_log = _link_shared_nm(project_dir, project_deps, progress=_pkg_progress)
            if not ok:
                ok, npm_log = _npm_install(project_dir)
        else:
            ok, npm_log = _npm_install(project_dir)
        if not ok:
            raise RuntimeError(f"npm install failed:\n{npm_log[-2000:]}")

        # tsc validation used to run here (_typecheck_and_autofix) — removed along
        # with the 9 postprocessors above, for the same reason: doesn't exist in
        # TurboUIGen's refine, adds a subprocess spawn + potential LLM repair call
        # to every refine, and generation ships fine without it.
        _progress("start")
        # Start API server if present
        if has_api_files and api_port:
            from agents.uigen_agent import _start_api_server, _api_servers, _wait_for_api
            _progress(f"llm_codegen:Starting API server on port {api_port}…")
            api_proc = _start_api_server(project_dir, api_port=api_port)
            if api_proc:
                _api_servers[project_name] = api_proc
                # A fixed 2s sleep here used to be the only wait — nowhere near
                # enough for a Java/Spring Boot backend, which recompiles and
                # restarts on every refine (~8s+ observed). The frontend's first
                # page-load fetches would race ahead of the still-starting
                # backend and fail with 500s that looked like a real bug but
                # cleared up on a manual refresh. Matches generate_project's
                # health-check wait instead of a guess.
                api_timeout = 90 if backend_type == "java" else 15
                _wait_for_api(api_port, timeout=api_timeout)

        proc = _start_vite(project_dir, port)
        _dev_servers[project_name] = proc
        if not wait_for_port(port, timeout=90):
            # Vite failed but keep API server alive so data endpoints work on retry
            _progress("llm_codegen:⚠️ Vite slow to start — retrying…")
            kill_server(project_name)
            if has_api_files and api_port:
                api_proc = _start_api_server(project_dir, api_port=api_port)
                if api_proc:
                    _api_servers[project_name] = api_proc
                    _wait_for_api(api_port, timeout=90 if backend_type == "java" else 15)
            proc = _start_vite(project_dir, port)
            _dev_servers[project_name] = proc
            if not wait_for_port(port, timeout=60):
                raise RuntimeError("Vite dev server did not start in time")

        _append_history(project_name, "Refined", prompt=prompt, comment=comment,
                        instructions=instructions or "")

        # ── Token usage summary ───────────────────────────────────────────────
        _elapsed = _time.time() - _t0
        for _line in token_tracker.format_summary(request_id, elapsed=_elapsed):
            _progress(f"llm_codegen:{_line}")

        _append_buildlog(project_name, _progress_logs.get(request_id, []),
                         event="Refined", duration_s=_elapsed)
        _generate_architecture(project_name, event="Refined", backend_type=backend_type)
        _progress("ready")
        return {
            "projectName": project_name,
            "port": port,
            "url": "/app/" + project_name + "/",
            "files": list(files.keys()),
            "type": "react",
        }


@app.post("/api/refine/{project_name}")
async def api_refine(project_name: str, req: RefineRequest):
    global _latest_request_id
    import uuid
    request_id = uuid.uuid4().hex
    _progress_logs[request_id] = []
    _latest_request_id = request_id
    _project_request_ids[project_name] = request_id
    loop = asyncio.get_event_loop()

    _save_job(request_id, {
        "status": "running",
        "projectName": project_name,
        "prompt": req.prompt[:200],
        "result": None,
        "error": None,
    })

    async def _run_in_bg():
        try:
            # Always route through the multi-agent pipeline (same code path as
            # fresh generation) rather than the old single-shot diff mechanism
            # (_run_refine) - this gives refine the same crew:Stage N/6 progress,
            # and the same seed/schema validation and page-naming fixes that
            # only ever ran during generation. req.architecture is None in the
            # common case; generate_project() handles that by running Stage 1
            # normally (informed by existing pages) instead of skipping it.
            result = await loop.run_in_executor(
                _executor, _run_refine_with_architecture, project_name, req, request_id
            )
            result["requestId"] = request_id
            _save_job(request_id, {
                "status": "completed",
                "projectName": project_name,
                "result": result,
                "error": None,
            })
        except Exception as e:
            import traceback
            raw_detail = f"{type(e).__name__}: {e}"
            friendly = _friendly_error(raw_detail)
            print(f"\n[REFINE ERROR]\n{raw_detail}\n{traceback.format_exc()[-1500:]}\n")

            from datetime import datetime as _dt_err2
            _progress_logs.setdefault(request_id, []).append(
                f"[{_dt_err2.now().strftime('%H:%M:%S')} +0.0s] error:{friendly}"
            )
            _append_buildlog(project_name, _progress_logs.get(request_id, []),
                             event="Refine failed", duration_s=0)

            _save_job(request_id, {
                "status": "failed",
                "projectName": project_name,
                "result": None,
                "error": friendly,
            })
        finally:
            async def _cleanup():
                await asyncio.sleep(300)
                _progress_logs.pop(request_id, None)
            asyncio.create_task(_cleanup())

    asyncio.create_task(_run_in_bg())

    return {"requestId": request_id, "status": "running", "projectName": project_name}


def _run_refine_with_architecture(project_name: str, req: RefineRequest, request_id: str) -> dict:
    """Refine using the multi-agent pipeline with pre-approved architecture (selective page regen)."""
    import time as _time
    _t0 = _time.time()

    import token_tracker
    token_tracker.reset(request_id)
    token_tracker.set_run_id(request_id)

    def _progress(msg: str):
        if request_id:
            from datetime import datetime as _dt
            elapsed = _time.time() - _t0
            ts = _dt.now().strftime("%H:%M:%S")
            stamped = f"[{ts} +{elapsed:.1f}s] {msg}"
            _progress_logs.setdefault(request_id, []).append(stamped)

    from agents.uigen_agent import generate_project, GENERATED_DIR

    instructions = (req.instructions or "").strip()
    user_content = req.prompt
    if instructions:
        user_content = f"{req.prompt}\n\n## Detailed Instructions\n\n{instructions}"

    # Disk is the source of truth for backend type on an existing project -
    # don't trust req.backend_type's Pydantic default ("python") to override
    # an existing Java project just because the caller didn't set it.
    backend_type = req.backend_type
    project_dir = GENERATED_DIR / project_name
    bt_file = project_dir / "backend" / ".backend_type"
    if bt_file.exists():
        _bt_raw = bt_file.read_text(encoding="utf-8").strip()
        backend_type = "java" if "java" in _bt_raw else _bt_raw
    elif (project_dir / "backend" / "pom.xml").exists():
        backend_type = "java"
    elif not backend_type:
        backend_type = "python"

    result = generate_project(
        user_content,
        progress=_progress,
        project_name_override=project_name,
        architecture=req.architecture,
        backend_type=backend_type,
    )

    _progress("ready")
    detail = req.prompt[:200]
    if result.get("schemaChanges"):
        detail += f"\n\nDatabase changes: {result['schemaChanges']}"
    _append_history(project_name, "Refined (pipeline)", detail=detail,
                    prompt=req.prompt, comment=req.comment or "", instructions=instructions)

    # Save architecture as draft for reference
    if result.get("architecture"):
        from agents.draft_preview import format_draft_markdown
        arch = result["architecture"]
        draft_data = {
            "architecture": arch,
            "markdown": format_draft_markdown(arch, req.prompt),
            "projectName": project_name,
            "title": result.get("title", project_name),
            "pageCount": len(arch.get("pages", [])),
        }
        _save_draft_to_disk(project_name, draft_data)

    _generate_architecture(project_name, event="Refined (pipeline)", backend_type=backend_type)
    return result


@app.get("/api/projects/{project_name}/history")
async def api_history(project_name: str):
    from agents.uigen_agent import GENERATED_DIR
    history_file = GENERATED_DIR / project_name / ".history.json"
    if not history_file.exists():
        return []
    try:
        import json as _json
        return _json.loads(history_file.read_text(encoding="utf-8"))
    except Exception:
        return []


@app.get("/api/generate/progress/latest")
async def api_progress_latest():
    """Poll current generation progress without needing a request ID (legacy/global)."""
    return {"id": _latest_request_id, "log": _progress_logs.get(_latest_request_id, [])}


@app.get("/api/generate/progress/project/{project_name}")
async def api_progress_by_project(project_name: str):
    """Poll progress scoped to a specific project (tab-safe)."""
    rid = _project_request_ids.get(project_name, "")
    return {"id": rid, "log": _progress_logs.get(rid, [])}


@app.get("/api/generate/progress/{request_id}")
async def api_progress(request_id: str):
    return {"log": _progress_logs.get(request_id, [])}


@app.get("/api/projects/{project_name}/buildlog")
async def api_project_buildlog(project_name: str):
    """Return persisted build log runs for a project, oldest first."""
    from agents.uigen_agent import GENERATED_DIR
    import json as _json
    buildlog_file = GENERATED_DIR / project_name / ".buildlog.json"
    if not buildlog_file.exists():
        return {"runs": []}
    try:
        runs = _json.loads(buildlog_file.read_text(encoding="utf-8"))
        return {"runs": runs if isinstance(runs, list) else []}
    except Exception:
        return {"runs": []}


@app.get("/api/projects/{project_name}/architecture")
async def api_project_architecture(project_name: str):
    """Return persisted architecture markdown for a project."""
    from agents.uigen_agent import GENERATED_DIR
    arch_file = GENERATED_DIR / project_name / ".architecture.md"
    if not arch_file.exists():
        return {"markdown": "", "exists": False}
    try:
        return {"markdown": arch_file.read_text(encoding="utf-8"), "exists": True}
    except Exception:
        return {"markdown": "", "exists": False}


@app.get("/api/projects/{project_name}/architecture.html")
async def api_project_architecture_html(project_name: str):
    """Return persisted architecture HTML for a project."""
    from agents.uigen_agent import GENERATED_DIR
    from fastapi.responses import HTMLResponse
    html_file = GENERATED_DIR / project_name / ".architecture.html"
    if not html_file.exists():
        return HTMLResponse("<p>No architecture yet.</p>", status_code=404)
    try:
        return HTMLResponse(html_file.read_text(encoding="utf-8"))
    except Exception:
        return HTMLResponse("<p>Error reading architecture.</p>", status_code=500)


_API_DETAILS_ALWAYS_GENERIC_PATHS = {"/api/metadata", "/metadata", "/health"}


def _generic_paths_for_tables(table_names: list) -> set:
    """Exact generic per-table paths, computed from REAL table names — not a
    regex/shape heuristic. Mirrors
    AgentPlatform/catalog/webui_integration_engineer/templates/mcp_server_template.py's
    `_generic_paths_for_tables`, proven this session against a real failure
    where a shape-based pattern misclassified a hyphenated custom endpoint
    (`/api/client-summary`) as generic. Duplicated rather than imported
    because that file is a standalone template shipped into every generated
    app and this is a separate platform process."""
    paths = set()
    for name in table_names:
        for shape in ("/api/{t}", "/api/{t}/{{id}}", "/api/{t}/aggregate",
                       "/api/data/{t}", "/api/data/{t}/{{id}}", "/api/data/{t}/aggregate"):
            paths.add(shape.format(t=name))
    return paths


def _mark_custom_endpoints(endpoints: list, table_names: list) -> list:
    """Flag each endpoint as custom (hand-built join/aggregate) vs. generic
    per-table CRUD, using the exact-path-set logic above."""
    generic = _API_DETAILS_ALWAYS_GENERIC_PATHS | _generic_paths_for_tables(table_names)
    marked = []
    for e in endpoints:
        path = e.get("path", "")
        is_custom = e.get("method") == "GET" and "{" not in path and path not in generic
        marked.append({**e, "custom": is_custom})
    return marked


_MCP_STATIC_TOOLS = [
    {"name": "list_tables", "description": "List every table name available in this app's database."},
    {"name": "get_api_metadata", "description": "Get full schema for every table: column names, types, categorical values, numeric ranges."},
    {"name": "query_table", "description": "Fetch rows from a table, with optional filtering/sorting."},
    {"name": "aggregate_table", "description": "Aggregate a table (sum/avg/min/max/count), optionally grouped by another column."},
    {"name": "list_custom_endpoints", "description": "List custom join/aggregate endpoints beyond the generic per-table routes above."},
    {"name": "call_endpoint", "description": "Call a specific custom endpoint discovered via list_custom_endpoints."},
]


@app.get("/api/projects/{project_name}/api-details")
async def api_project_api_details(project_name: str):
    """Live API surface + MCP tool details for a project, sourced from
    .architecture.json and mcp_metadata.json — unlike the static
    .architecture.html snapshot, this reflects the real named-route
    endpoints (including custom join endpoints) and, when the app has
    DataChat/MCP enabled, exactly what the AI chat can call."""
    from agents.uigen_agent import GENERATED_DIR
    import json as _json

    project_dir = GENERATED_DIR / project_name

    arch_data = None
    for p in (project_dir / "backend" / ".architecture.json", project_dir / "api" / ".architecture.json"):
        if p.exists():
            try:
                arch_data = _json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                arch_data = None
            break

    if not arch_data:
        return {
            "hasArchitecture": False, "entities": [], "endpoints": [],
            "hasMcp": False, "mcpTools": [], "mcpCustomEndpoints": [],
        }

    entities = arch_data.get("entities", [])
    table_names = [e.get("table") for e in entities if e.get("table")]
    endpoints = _mark_custom_endpoints(arch_data.get("endpoints", []), table_names)

    mcp_data = None
    for p in (project_dir / "datachat" / "mcp_metadata.json", project_dir / "api" / "mcp_metadata.json"):
        if p.exists():
            try:
                mcp_data = _json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                mcp_data = None
            break

    has_mcp = mcp_data is not None
    mcp_custom_endpoints = []
    if has_mcp:
        mcp_table_names = [t.get("name") for t in mcp_data.get("tables", []) if t.get("name")]
        mcp_generic = _API_DETAILS_ALWAYS_GENERIC_PATHS | _generic_paths_for_tables(mcp_table_names)
        for e in mcp_data.get("endpoints", []):
            path = e.get("path", "")
            if e.get("method") == "GET" and "{" not in path and path not in mcp_generic:
                mcp_custom_endpoints.append({
                    "path": path,
                    "description": e.get("summary") or e.get("description") or "",
                })

    return {
        "hasArchitecture": True,
        "entities": entities,
        "endpoints": endpoints,
        "hasMcp": has_mcp,
        "mcpTools": _MCP_STATIC_TOOLS if has_mcp else [],
        "mcpCustomEndpoints": mcp_custom_endpoints,
    }


@app.get("/api/projects/{project_name}/db-explorer")
async def api_project_db_explorer(project_name: str):
    """Live SQLite snapshot for a project — real table names, columns, row
    counts and up to 5 sample rows, read directly from the .db file the
    running app actually connects to. Reuses the same path-resolution
    (_find_app_db_file) and table/column introspection (introspect_sqlite)
    already used elsewhere for MCP tooling and schema-drift detection,
    rather than re-deriving either — only the row-count/sample-row query
    loop below is new."""
    from agents.uigen_agent import GENERATED_DIR
    from api_agents.api_runner import _find_app_db_file
    from mcp_agents.mcp_introspect import introspect_sqlite
    import sqlite3 as _sqlite3

    project_dir = GENERATED_DIR / project_name

    if (project_dir / "backend").is_dir():
        language, backend_dir = "java", project_dir / "backend"
    elif (project_dir / "api").is_dir():
        language, backend_dir = "python", project_dir / "api"
    else:
        return {"hasDatabase": False}

    db_path = _find_app_db_file(backend_dir, language)
    if db_path is None or not db_path.exists():
        return {"hasDatabase": False}

    try:
        tables = introspect_sqlite(str(db_path))
    except Exception as e:
        raise HTTPException(400, f"Couldn't read that SQLite file: {e}")

    # Second, short-lived read-only connection just for counts/samples —
    # introspect_sqlite's own connection is already closed by the time it
    # returns, and its return shape is shared with the MCP introspect route
    # above, so it isn't changed to also carry row data.
    try:
        conn = _sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = _sqlite3.Row
        cur = conn.cursor()
        for t in tables:
            # Table name came straight out of introspect_sqlite's own
            # sqlite_master query above — never caller input — safe to
            # interpolate into the identifier position.
            name = t["name"]
            cur.execute(f'SELECT COUNT(*) AS c FROM "{name}"')
            t["rowCount"] = cur.fetchone()["c"]
            cur.execute(f'SELECT * FROM "{name}" LIMIT 5')
            t["sampleRows"] = [dict(row) for row in cur.fetchall()]
        conn.close()
    except Exception as e:
        raise HTTPException(400, f"Couldn't read row data: {e}")

    return {
        "hasDatabase": True,
        "dbName": db_path.name,
        "dbPath": str(db_path.relative_to(project_dir)).replace("\\", "/"),
        "tables": tables,
    }


@app.post("/api/generate")
async def api_generate(req: GenerateRequest):
    """
    Fire-and-forget generation. Returns requestId immediately.
    The job runs in background and survives browser disconnects.
    Poll /api/jobs/{requestId} for status/result, or /api/generate/progress/{requestId} for logs.
    """
    global _latest_request_id

    # Reverse of the check in api_delete: a delete for this same project name
    # may still be tearing down its directory (up to ~90s) on a separate
    # thread pool thread. Starting a new generation into that same path while
    # delete is still running is exactly the race that silently wiped out a
    # freshly-completed generation before this pair of guards existed.
    if req.project_name:
        import re as _re_gen_check
        _check_slug = _re_gen_check.sub(r"[^a-z0-9-]", "-", req.project_name.lower()).strip("-")
        if _check_slug in _deletes_in_progress:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"'{req.project_name}' is currently being deleted. "
                    f"Wait for the delete to finish before creating/regenerating it."
                ),
            )

    import uuid
    request_id = uuid.uuid4().hex
    _progress_logs[request_id] = []
    _latest_request_id = request_id

    # Track per-project request id for tab-scoped polling
    import re as _re_gen
    project_slug = ""
    if req.project_name:
        project_slug = _re_gen.sub(r"[^a-z0-9-]", "-", req.project_name.lower()).strip("-")
    if project_slug:
        _project_request_ids[project_slug] = request_id
        # Store backend_type in the WEB APP registry immediately so its UI
        # reflects it during build — but only for actual web-app generations.
        # This ran unconditionally for every mode, including "api", which
        # silently created a stub entry (registry_upsert creates one if it
        # doesn't exist) in the Web UI's own registry for every API project
        # too — that's why API projects were showing up in the Web UI sidebar.
        if req.mode != "api":
            registry_upsert(project_slug, backendType=req.backend_type or "python")

    # Persist initial job state
    _save_job(request_id, {
        "status": "running",
        "projectName": project_slug or None,
        "prompt": req.prompt[:200],
        "result": None,
        "error": None,
    })

    # Launch in background — does NOT block the HTTP response
    loop = asyncio.get_event_loop()

    async def _run_in_bg():
        try:
            result = await loop.run_in_executor(_executor, _run_generate, req, request_id)
            result["requestId"] = request_id
            _save_job(request_id, {
                "status": "completed",
                "projectName": result.get("projectName"),
                "result": result,
                "error": None,
            })
        except Exception as e:
            import traceback
            raw_detail = f"{type(e).__name__}: {e}"
            friendly = _friendly_error(raw_detail)
            print(f"\n[ERROR /api/generate bg] {raw_detail}\n{traceback.format_exc()[-1500:]}\n")

            # Write error to progress log so polling sees it
            from datetime import datetime as _dt_err
            _progress_logs.setdefault(request_id, []).append(
                f"[{_dt_err.now().strftime('%H:%M:%S')} +0.0s] error:{friendly}"
            )

            # Persist buildlog on failure so it survives browser close — API
            # projects live in their own registry/buildlog store (WebAPIGenerator's
            # web-api/, not WebUIGenerator's web-apps/), so a failed API generation
            # must not fall through to _append_buildlog's hardcoded web-app path
            # (that raised its own FileNotFoundError here, masking the real error).
            pname = project_slug or None
            if pname:
                if req.mode == "api":
                    from api_agents.api_registry import append_api_buildlog
                    append_api_buildlog(pname, _progress_logs.get(request_id, []),
                                        event="Failed", duration_s=0)
                else:
                    _append_buildlog(pname, _progress_logs.get(request_id, []),
                                     event="Failed", duration_s=0)

            _save_job(request_id, {
                "status": "failed",
                "projectName": pname,
                "result": None,
                "error": friendly,
            })
        finally:
            # Clean up in-memory progress logs after 5 minutes
            async def _cleanup():
                await asyncio.sleep(300)
                _progress_logs.pop(request_id, None)
            asyncio.create_task(_cleanup())

    asyncio.create_task(_run_in_bg())

    return {"requestId": request_id, "status": "running", "projectName": project_slug or None}


@app.get("/api/jobs/{request_id}")
async def api_job_status(request_id: str):
    """Check the status of a generation job. Returns status, result (if done), or error."""
    job = _load_job(request_id)
    if not job:
        raise HTTPException(404, f"Job '{request_id}' not found")
    return {"requestId": request_id, **job}


@app.get("/api/jobs")
async def api_list_jobs():
    """List all active (running) jobs — useful for reconnecting after browser close."""
    return {"jobs": _load_active_jobs()}


def _dispatch_start(project_name: str) -> dict:
    from agents.figma_to_web_using_playwright_agent import is_figma_project, start_figma_project
    if is_figma_project(project_name):
        return start_figma_project(project_name)
    return start_project(project_name)

def _dispatch_stop(project_name: str):
    from agents.figma_to_web_using_playwright_agent import is_figma_project, kill_figma_server
    if is_figma_project(project_name):
        kill_figma_server(project_name, forget_port=False)
    else:
        stop_project(project_name)

def _dispatch_delete(project_name: str, progress=None):
    def _p(s: str):
        if progress:
            progress(s)

    from agents.figma_to_web_using_playwright_agent import is_figma_project, kill_figma_server
    if is_figma_project(project_name):
        _p("Stopping Figma preview server...")
        kill_figma_server(project_name, forget_port=True)

    # Clean up Docker container and image
    try:
        from agents.docker_agent import (
            delete_container, image_tag, _docker,
            _load_container_ports, _save_container_ports,
        )
        _p("Removing Docker container/image (if any)...")
        delete_container(project_name)
        _docker(["rmi", "-f", image_tag(project_name)], timeout=30)
        # Free the port
        ports = _load_container_ports()
        if project_name in ports:
            del ports[project_name]
            _save_container_ports(ports)
    except Exception:
        pass

    delete_project(project_name, progress=progress)
    _p("Removing from project registry...")
    registry_remove(project_name)
    _p("Delete complete.")


# ── WebAPIGenerator — standalone API projects (separate from web-app projects) ──

@app.get("/api/webapi/projects")
async def api_webapi_list():
    from api_agents.api_registry import list_api_projects
    return list_api_projects()


@app.post("/api/webapi/projects/create")
async def api_webapi_create(req: CreateProjectRequest):
    """
    Create an empty "draft" API project entry — mirrors POST /api/projects/create
    for web apps. Lets the sidebar show the project immediately (name + status)
    before any generation has run, matching the Web UI tab's create-then-configure
    flow instead of a single form that blocks for minutes.
    """
    import re
    from datetime import datetime, timezone
    from api_agents.api_registry import upsert_api_project, get_api_project
    from api_config import WEB_API_DIR

    name = re.sub(r"[^a-z0-9-]", "-", req.name.lower()).strip("-")
    if not name:
        raise HTTPException(400, "Invalid project name")
    if get_api_project(name):
        raise HTTPException(400, f"Project '{name}' already exists")

    (WEB_API_DIR / name).mkdir(parents=True, exist_ok=True)
    upsert_api_project(
        name, title=name, description="", language=None, authType=None,
        port=None, status="draft", createdAt=datetime.now(timezone.utc).isoformat(),
    )
    return {"name": name}


@app.post("/api/webapi/start/{project_name}")
async def api_webapi_start(project_name: str):
    from api_agents.api_registry import get_api_project, upsert_api_project, append_api_buildlog
    from api_agents.api_runner import start_api_project, wait_for_api, seed_database
    from api_config import WEB_API_DIR, project_url as _api_project_url

    entry = get_api_project(project_name)
    if not entry:
        raise HTTPException(404, f"API project '{project_name}' not found")
    project_dir = WEB_API_DIR / project_name
    if not project_dir.exists():
        raise HTTPException(404, f"Project folder for '{project_name}' not found")

    language = entry.get("language", "python")
    loop = asyncio.get_event_loop()
    port = await loop.run_in_executor(
        _executor, start_api_project, project_name, project_dir, language
    )
    started = await loop.run_in_executor(
        _executor, wait_for_api, project_name, port, 120 if language == "java" else 45
    )
    if started:
        # This endpoint has no live progress log the way generation does, so
        # the only way a missing/failed seed step would ever be visible here
        # is an explicit Build Log entry — same reason the generate flow
        # reports this via _progress().
        seed_status = await loop.run_in_executor(_executor, seed_database, project_name, project_dir, language)
        append_api_buildlog(project_name, [f"Seeding: {seed_status}"], event="Started", duration_s=0)
    upsert_api_project(project_name, port=port, status="running" if started else "start_failed")
    return {"name": project_name, "port": port, "url": _api_project_url(port) if started else None, "running": started}


@app.post("/api/webapi/stop/{project_name}")
async def api_webapi_stop(project_name: str):
    from api_agents.api_registry import upsert_api_project
    from api_agents.api_runner import stop_api_project
    stop_api_project(project_name)
    upsert_api_project(project_name, status="stopped")
    return {"name": project_name, "running": False}


@app.delete("/api/webapi/projects/{project_name}")
async def api_webapi_delete(project_name: str):
    import shutil
    from api_agents.api_registry import remove_api_project
    from api_agents.api_runner import release_port, stop_api_project
    from api_agents.api_docker import delete_container, delete_image, release_container_port
    from api_config import WEB_API_DIR, protected_env_file

    stop_api_project(project_name)
    # Best-effort — most projects never had a Docker container/image, and
    # Docker itself may not even be running; either way this must never block
    # deleting the project.
    try:
        delete_container(project_name)
        delete_image(project_name)
    except Exception:
        pass
    release_container_port(project_name)
    project_dir = WEB_API_DIR / project_name

    if project_dir.exists():
        # Don't use ignore_errors=True: a .db file left open by an external
        # client (DBeaver, etc.) makes rmtree fail on Windows, but swallowing
        # that silently used to still remove the registry entry — the project
        # vanished from the UI while its folder (and the locked file) stayed
        # orphaned on disk with no way to find or retry it.
        stuck = []
        shutil.rmtree(project_dir, onerror=lambda fn, path, exc: stuck.append(Path(path).name))
        if project_dir.exists():
            names = ", ".join(sorted(set(stuck))) or "some files"
            raise HTTPException(
                409,
                f"Couldn't fully delete '{project_name}' — {names} appear to be open in "
                f"another program (e.g. a DB client connected to the .db file). Close it "
                f"and try again.",
            )

    protected_env_file(project_name).unlink(missing_ok=True)
    remove_api_project(project_name)
    release_port(project_name)
    return {"deleted": project_name}


@app.post("/api/webapi/projects/{project_name}/rename")
async def api_webapi_rename(project_name: str, req: RenameProjectRequest):
    """Rename a Web API project — mirrors the Web UI apps' rename endpoint,
    but also carries over this project's own extra state: the live dev-server
    port, any Docker image/container, and the protected .env copy kept outside
    the project directory."""
    import re
    from api_agents.api_registry import rename_api_project
    from api_agents.api_runner import stop_api_project, rename_port
    from api_agents.api_docker import rename_docker
    from api_config import WEB_API_DIR, protected_env_file

    new_name = re.sub(r"[^a-z0-9-]", "-", req.new_name.lower()).strip("-")
    if not new_name:
        raise HTTPException(400, "Invalid new project name")
    if new_name == project_name:
        return {"name": new_name, "oldName": project_name}

    old_dir = WEB_API_DIR / project_name
    new_dir = WEB_API_DIR / new_name
    if not old_dir.exists():
        raise HTTPException(404, f"Project '{project_name}' not found")
    if new_dir.exists():
        raise HTTPException(409, f"Project '{new_name}' already exists")

    # Stop first — it holds a file lock on the project dir (and, for Java, the
    # target/ build output), same reason the Web UI rename stops the dev server
    # before moving the folder.
    stop_api_project(project_name)
    rename_docker(project_name, new_name)
    old_dir.rename(new_dir)
    rename_port(project_name, new_name)

    old_env = protected_env_file(project_name)
    if old_env.exists():
        old_env.rename(protected_env_file(new_name))

    rename_api_project(project_name, new_name)
    return {"name": new_name, "oldName": project_name}


# ── MCPGenerator — standalone MCP server projects ────────────────────────────

@app.get("/api/mcp/projects")
async def api_mcp_list():
    from mcp_agents.mcp_registry import list_mcp_projects
    return list_mcp_projects()


@app.post("/api/mcp/projects/create")
async def api_mcp_create(req: CreateProjectRequest):
    """Create an empty "draft" MCP project entry — mirrors
    POST /api/webapi/projects/create so the sidebar shows the project
    immediately, before any source has been picked or generation has run."""
    import re
    from datetime import datetime, timezone
    from mcp_agents.mcp_registry import upsert_mcp_project, get_mcp_project
    from mcp_config import MCP_DIR

    name = re.sub(r"[^a-z0-9-]", "-", req.name.lower()).strip("-")
    if not name:
        raise HTTPException(400, "Invalid project name")
    if get_mcp_project(name):
        raise HTTPException(400, f"Project '{name}' already exists")

    (MCP_DIR / name).mkdir(parents=True, exist_ok=True)
    upsert_mcp_project(
        name, title=name, sourceType=None, port=None, status="draft",
        createdAt=datetime.now(timezone.utc).isoformat(),
    )
    return {"name": name}


@app.post("/api/mcp/introspect/sqlite")
async def api_mcp_introspect_sqlite(req: McpIntrospectSqliteRequest):
    from mcp_agents.mcp_introspect import introspect_sqlite
    try:
        tables = introspect_sqlite(req.dbPath)
    except FileNotFoundError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(400, f"Couldn't read that SQLite file: {e}")
    return {"tables": tables}


@app.post("/api/mcp/introspect/api")
async def api_mcp_introspect_api(req: McpIntrospectApiRequest):
    from mcp_agents.mcp_introspect import introspect_openapi
    spec = introspect_openapi(req.baseUrl, req.username, req.password)
    if spec is None:
        return {"found": False}
    return {"found": True, **spec}


@app.post("/api/mcp/introspect/api/from-spec")
async def api_mcp_introspect_api_from_spec(req: McpIntrospectFromSpecRequest):
    """Fallback for when auto-detection finds nothing — the user pastes a spec
    URL's raw JSON (fetched client-side or by hand) directly."""
    from mcp_agents.mcp_introspect import introspect_openapi_from_spec
    try:
        spec = introspect_openapi_from_spec(req.baseUrl, req.spec)
    except Exception as e:
        raise HTTPException(400, f"Couldn't parse that OpenAPI spec: {e}")
    return {"found": True, **spec}


@app.post("/api/mcp/start/{project_name}")
async def api_mcp_start(project_name: str):
    from mcp_agents.mcp_registry import get_mcp_project, upsert_mcp_project
    from mcp_agents.mcp_runner import start_mcp_project, wait_for_mcp
    from mcp_config import MCP_DIR, project_url as _mcp_project_url

    entry = get_mcp_project(project_name)
    if not entry:
        raise HTTPException(404, f"MCP project '{project_name}' not found")
    project_dir = MCP_DIR / project_name
    if not project_dir.exists():
        raise HTTPException(404, f"Project folder for '{project_name}' not found")

    loop = asyncio.get_event_loop()

    # A datastore-sourced MCP server's tools call its backing API over real
    # HTTP — that API has to actually be up first, or every tool call fails.
    backing_name = entry.get("backingApiProject")
    if backing_name:
        await loop.run_in_executor(_executor, _start_backing_api, backing_name)

    port = await loop.run_in_executor(_executor, start_mcp_project, project_name, project_dir)
    started = await loop.run_in_executor(_executor, wait_for_mcp, project_name, port, 60)
    upsert_mcp_project(project_name, port=port, status="running" if started else "start_failed")
    return {"name": project_name, "port": port, "url": _mcp_project_url(port) if started else None, "running": started}


@app.post("/api/mcp/stop/{project_name}")
async def api_mcp_stop(project_name: str):
    from mcp_agents.mcp_registry import get_mcp_project, upsert_mcp_project
    from mcp_agents.mcp_runner import stop_mcp_project
    stop_mcp_project(project_name)
    upsert_mcp_project(project_name, status="stopped")

    # Stop the backing API too, if this project has one — leaving it running
    # after its only consumer stopped just wastes a port for no reason, and
    # matches the "one Start/Stop button" mental model the MCP tab presents.
    entry = get_mcp_project(project_name)
    backing_name = entry.get("backingApiProject") if entry else None
    if backing_name:
        from api_agents.api_runner import stop_api_project
        from api_agents.api_registry import upsert_api_project
        stop_api_project(backing_name)
        upsert_api_project(backing_name, status="stopped")

    return {"name": project_name, "running": False}


def _start_backing_api(backing_name: str):
    """Shared by generate and start — (re)starts a datastore MCP project's
    backing WebAPIGenerator project and waits for it to come up."""
    from api_agents.api_registry import get_api_project, upsert_api_project
    from api_agents.api_runner import start_api_project, wait_for_api
    from api_config import WEB_API_DIR

    entry = get_api_project(backing_name)
    if not entry:
        return None
    backing_dir = WEB_API_DIR / backing_name
    port = start_api_project(backing_name, backing_dir, "python")
    started = wait_for_api(backing_name, port, timeout=45)
    upsert_api_project(backing_name, port=port, status="running" if started else "start_failed")
    return port if started else None


@app.delete("/api/mcp/projects/{project_name}")
async def api_mcp_delete(project_name: str):
    import shutil
    from mcp_agents.mcp_registry import get_mcp_project, remove_mcp_project
    from mcp_agents.mcp_runner import release_port, stop_mcp_project
    from mcp_config import MCP_DIR, protected_env_file

    entry = get_mcp_project(project_name)
    stop_mcp_project(project_name)
    project_dir = MCP_DIR / project_name

    if project_dir.exists():
        stuck = []
        shutil.rmtree(project_dir, onerror=lambda fn, path, exc: stuck.append(Path(path).name))
        if project_dir.exists():
            names = ", ".join(sorted(set(stuck))) or "some files"
            raise HTTPException(
                409,
                f"Couldn't fully delete '{project_name}' — {names} appear to be open in "
                f"another program. Close it and try again.",
            )

    protected_env_file(project_name).unlink(missing_ok=True)
    remove_mcp_project(project_name)
    release_port(project_name)

    # Clean up the backing API this MCP project owns — it's not independently
    # useful once the MCP server that generated it is gone, and leaving it
    # behind would silently orphan a project in the Web API tab with no link
    # back to why it exists.
    backing_name = entry.get("backingApiProject") if entry else None
    if backing_name:
        import shutil as _shutil
        from api_agents.api_registry import remove_api_project
        from api_agents.api_runner import stop_api_project, release_port as release_api_port
        from api_config import WEB_API_DIR, protected_env_file as api_protected_env_file

        stop_api_project(backing_name)
        backing_dir = WEB_API_DIR / backing_name
        if backing_dir.exists():
            _shutil.rmtree(backing_dir, ignore_errors=True)
        api_protected_env_file(backing_name).unlink(missing_ok=True)
        remove_api_project(backing_name)
        release_api_port(backing_name)

    return {"deleted": project_name}


@app.post("/api/mcp/projects/{project_name}/rename")
async def api_mcp_rename(project_name: str, req: RenameProjectRequest):
    import re
    from mcp_agents.mcp_registry import get_mcp_project, rename_mcp_project
    from mcp_agents.mcp_runner import stop_mcp_project, rename_port
    from mcp_config import MCP_DIR, protected_env_file

    new_name = re.sub(r"[^a-z0-9-]", "-", req.new_name.lower()).strip("-")
    if not new_name:
        raise HTTPException(400, "Invalid new project name")
    if new_name == project_name:
        return {"name": new_name, "oldName": project_name}

    old_dir = MCP_DIR / project_name
    new_dir = MCP_DIR / new_name
    if not old_dir.exists():
        raise HTTPException(404, f"Project '{project_name}' not found")
    if new_dir.exists():
        raise HTTPException(409, f"Project '{new_name}' already exists")

    entry = get_mcp_project(project_name)
    stop_mcp_project(project_name)
    old_dir.rename(new_dir)
    rename_port(project_name, new_name)

    old_env = protected_env_file(project_name)
    if old_env.exists():
        old_env.rename(protected_env_file(new_name))

    # Carry the backing API's registration over to the new name too — same
    # port (rename_port there just re-keys it), so the MCP project's own
    # BACKING_API_BASE_URL env var is still correct with no regeneration.
    backing_name = entry.get("backingApiProject") if entry else None
    new_backing_name = None
    if backing_name:
        from api_agents.api_registry import rename_api_project
        from api_agents.api_runner import stop_api_project, rename_port as rename_api_port
        from api_config import WEB_API_DIR, protected_env_file as api_protected_env_file

        new_backing_name = f"{new_name}-api"
        old_backing_dir = WEB_API_DIR / backing_name
        new_backing_dir = WEB_API_DIR / new_backing_name
        if old_backing_dir.exists() and not new_backing_dir.exists():
            stop_api_project(backing_name)
            old_backing_dir.rename(new_backing_dir)
            rename_api_port(backing_name, new_backing_name)
            old_api_env = api_protected_env_file(backing_name)
            if old_api_env.exists():
                old_api_env.rename(api_protected_env_file(new_backing_name))
            rename_api_project(backing_name, new_backing_name)

    rename_mcp_project(project_name, new_name)
    if new_backing_name:
        from mcp_agents.mcp_registry import upsert_mcp_project
        upsert_mcp_project(new_name, backingApiProject=new_backing_name)
    return {"name": new_name, "oldName": project_name}


@app.get("/api/mcp/projects/{project_name}/buildlog")
async def api_mcp_buildlog(project_name: str):
    from mcp_agents.mcp_registry import get_mcp_buildlog
    return get_mcp_buildlog(project_name)


@app.get("/api/mcp/projects/{project_name}/history")
async def api_mcp_history(project_name: str):
    from mcp_agents.mcp_registry import get_mcp_history
    return get_mcp_history(project_name)


@app.get("/api/mcp/projects/{project_name}/metadata")
async def api_mcp_metadata(project_name: str):
    from mcp_agents.mcp_registry import get_mcp_metadata
    metadata = get_mcp_metadata(project_name)
    if metadata is None:
        raise HTTPException(404, f"No metadata found for '{project_name}'")
    return metadata


@app.post("/api/mcp/projects/{project_name}/chat")
async def api_mcp_chat(project_name: str, req: McpChatRequest):
    """
    Backs the "Try it" tab's chat tester — connects to the project's own live
    MCP endpoint as a real client and lets an LLM answer using its tools (see
    mcp_agents/mcp_chat.py). Stateless: the frontend resends the full
    transcript each turn, same as WebUIGenerator's own DataChat /api/chat.
    """
    from mcp_agents.mcp_registry import get_mcp_project
    from mcp_agents.mcp_chat import run_chat_turn

    entry = get_mcp_project(project_name)
    if not entry:
        raise HTTPException(404, f"MCP project '{project_name}' not found")
    if entry.get("status") != "running" or not entry.get("port"):
        raise HTTPException(409, f"'{project_name}' isn't running — start it first")

    mcp_url = f"http://127.0.0.1:{entry['port']}/mcp"
    try:
        result = await run_chat_turn(mcp_url, [m.dict() for m in req.messages])
    except Exception as e:
        raise HTTPException(502, f"Chat failed: {e}")
    return result


def _run_mcp_generate_from_instructions(project_name: str, req: McpGenerateFromInstructionsRequest,
                                         request_id: str) -> dict:
    """
    Alternative entry point to MCP generation: turns free-text instructions
    into a real sourceConfig, then delegates entirely to _run_mcp_generate --
    everything past that point (custom-tool design, backing API generation,
    starting the server) is the exact same tested path the manual
    browse-and-checkbox UI already uses.

    The one rule that matters here: never hallucinate a schema. An LLM call
    only ever extracts a path/URL the instructions *already state explicitly*
    -- the actual tables/endpoints always come from real introspection
    (opening the real SQLite file, or probing the real API's own OpenAPI
    spec), never from the LLM's imagination. If the instructions don't name
    a concrete source, or introspection can't reach/read it, this fails
    loudly with a specific reason rather than silently building an empty or
    made-up MCP server.
    """
    from datetime import datetime
    from agents.llm import chat_json
    from mcp_agents.mcp_introspect import introspect_sqlite, introspect_openapi

    def _progress(msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        _progress_logs.setdefault(request_id, []).append(f"[{ts}] {msg}")

    _progress("mcp:extracting source details from instructions")
    extraction = chat_json(
        [{"role": "user", "content": req.instructions}],
        system=(
            "You are checking whether product/build instructions for an MCP (Model "
            "Context Protocol) server already state a CONCRETE, EXACT source to connect "
            "to -- either a local SQLite database file path, or a running API's base URL "
            "(plus a username/password if one is mentioned). Never invent, guess, "
            "complete, or assume any path or URL that is not explicitly written in the "
            "text -- if it's ambiguous, vague, or simply absent, treat it as missing.\n\n"
            "Respond with ONLY a JSON object, no prose:\n"
            '{"sourceType": "datastore"|"api"|"both"|null, "dbPath": string|null, '
            '"baseUrl": string|null, "username": string|null, "password": string|null, '
            '"missing": boolean, "reason": string}\n'
            '"reason" must name exactly what is missing (e.g. "no database file path or '
            'API base URL was mentioned") when missing is true, else "".'
        ),
    )
    if extraction.get("missing") or not extraction.get("sourceType"):
        raise ValueError(
            extraction.get("reason")
            or "The instructions don't state a concrete database file path or API base URL "
               "-- add one (with credentials if it needs auth) and try again."
        )

    source_type = extraction["sourceType"]
    source_config: dict = {}

    if source_type in ("datastore", "both"):
        db_path = (extraction.get("dbPath") or "").strip()
        if not db_path:
            raise ValueError("Instructions say to use a database, but no exact file path was given.")
        _progress(f"mcp:reading database schema at {db_path}")
        try:
            tables = introspect_sqlite(db_path)
        except FileNotFoundError:
            raise ValueError(f"Database file not found at '{db_path}' — check the path in your instructions.")
        except Exception as e:
            raise ValueError(f"Couldn't read the database at '{db_path}': {e}")
        if not tables:
            raise ValueError(f"'{db_path}' has no tables to build MCP tools from.")
        source_config["dbPath"] = db_path
        source_config["tables"] = tables
        source_config["allTables"] = tables

    if source_type in ("api", "both"):
        base_url = (extraction.get("baseUrl") or "").strip()
        if not base_url:
            raise ValueError("Instructions say to use an API, but no exact base URL was given.")
        _progress(f"mcp:discovering API endpoints at {base_url}")
        spec = introspect_openapi(base_url, extraction.get("username"), extraction.get("password"))
        if not spec or not spec.get("endpoints"):
            raise ValueError(
                f"Could not find an OpenAPI/Swagger spec at '{base_url}' -- instructions-based "
                "MCP creation needs a reachable, self-describing API. If it doesn't expose one, "
                "use the manual MCP builder to paste a spec directly instead."
            )
        source_config["baseUrl"] = spec["baseUrl"]
        source_config["authType"] = "basic" if extraction.get("username") else "none"
        source_config["username"] = extraction.get("username")
        source_config["password"] = extraction.get("password")
        source_config["endpoints"] = spec["endpoints"]
        source_config["allEndpoints"] = spec["endpoints"]

    built_req = McpGenerateRequest(
        projectName=req.projectName, sourceType=source_type, sourceConfig=source_config,
        instructions=req.instructions, comment=req.comment,
    )
    return _run_mcp_generate(project_name, built_req, request_id)


def _run_mcp_generate(project_name: str, req: McpGenerateRequest, request_id: str) -> dict:
    """
    Generate an MCP server project — structured input (a source type + the
    tables/endpoints the user picked and described in the UI), not a free-text
    prompt, so this doesn't go through the shared /api/generate multiplexer
    the way Web UI/Web API generation does. Mirrors _run_api_refine's dispatch
    shape instead (same background-executor + progress-log + buildlog pattern),
    since that endpoint's input is similarly structured rather than prompt-driven.
    """
    import re
    import time as _time
    from datetime import datetime, timezone
    _t0 = _time.time()

    def _progress(msg: str):
        elapsed = _time.time() - _t0
        ts = datetime.now().strftime("%H:%M:%S")
        _progress_logs.setdefault(request_id, []).append(f"[{ts} +{elapsed:.1f}s] {msg}")

    from mcp_agents.mcp_orchestrator import McpCrewOrchestrator
    from mcp_agents.mcp_registry import (
        upsert_mcp_project, save_mcp_metadata, append_mcp_buildlog, get_mcp_metadata, append_mcp_history,
    )
    from mcp_agents.mcp_runner import start_mcp_project, wait_for_mcp
    from mcp_config import MCP_DIR, protected_env_file, project_url as _mcp_project_url

    name = re.sub(r"[^a-z0-9-]", "-", project_name.lower()).strip("-") or "mcp-project"
    _project_request_ids[name] = request_id
    project_dir = MCP_DIR / name
    project_dir.mkdir(parents=True, exist_ok=True)

    # Persist from the start, not just at the end — same reasoning as
    # WebAPIGenerator's own generate/refine (see api_generate/_run_api_refine):
    # a generate on one MCP project running concurrently with one on another
    # should never leave either's Build Log tab showing stale/no activity for
    # the whole duration. Previously this only appended once, at completion.
    append_mcp_buildlog(name, ["Generation started..."], event="Generating", duration_s=0)

    # Only re-run the custom-tool designer if the instructions text actually
    # changed since the last successful generate — otherwise clicking Update
    # for an unrelated reason (e.g. tweaking one description) would silently
    # keep adding near-duplicate tools every time, since the LLM isn't
    # deterministic about naming the same request the same way twice.
    previous_metadata = get_mcp_metadata(name) or {}
    instructions_changed = req.instructions.strip() != (previous_metadata.get("instructions") or "").strip()

    orchestrator = McpCrewOrchestrator(progress=_progress)
    source_config = dict(req.sourceConfig)
    backing_name = None

    # "both" runs each branch below independently (not elif) — a combined
    # project needs its own backing API generated for the datastore half
    # AND the additional-endpoints instructions pass for the API half,
    # exactly as each already runs standalone for a single-source project.
    if req.sourceType in ("datastore", "both"):
        # A datastore source needs its own standalone backing API generated,
        # registered, and started FIRST — the MCP server's tools call it over
        # real HTTP once it's up, on a genuinely different port (see
        # mcp_orchestrator's module docstring for why this is two processes,
        # not one). Reuses WebAPIGenerator's own registry/runner directly so
        # this project is visible/manageable in the Web API tab like any other.
        from api_agents.api_registry import upsert_api_project
        from api_agents.api_runner import start_api_project, wait_for_api
        from api_config import WEB_API_DIR

        backing_name = f"{name}-api"
        backing_dir = WEB_API_DIR / backing_name
        backing_dir.mkdir(parents=True, exist_ok=True)

        # Custom (join/business-logic) tools already in sourceConfig are
        # whatever the frontend currently has (LLM-designed then possibly
        # user-edited, or removed) — always carried through as-is. New
        # instructions ADD to that list rather than replacing it, so a
        # regenerate never silently discards a tool the user already
        # reviewed/edited. Designed against the FULL schema (allTables), not
        # just the tables checked for mechanical list/get tools — a join tool
        # should be able to use a table nobody wanted a raw tool for.
        # Validate EVERY custom tool's SQL, not just newly LLM-designed ones —
        # a tool carried through from the request could be one the user just
        # hand-edited in the Metadata tab, and that edit never went through
        # design_custom_tools' own validation. Unlike a dropped LLM proposal
        # (logged and silently skipped, since the user never saw or asked for
        # that exact SQL), a user's own edit failing this check must be a
        # loud, clear rejection — silently dropping or "fixing" someone's own
        # edit would be far more confusing than just telling them why it
        # didn't apply.
        existing_custom_tools = source_config.get("customTools", [])
        for ct in existing_custom_tools:
            if not McpCrewOrchestrator._is_safe_select_sql(ct.get("sql", "")):
                raise ValueError(
                    f"Custom tool '{ct.get('name')}' has SQL that isn't a plain read-only "
                    f"SELECT/WITH statement (no writes, no PRAGMA, no stacked statements) — "
                    f"fix it in the Metadata tab and try again."
                )
        if req.instructions.strip() and instructions_changed:
            _progress("mcp:processing instructions")
            all_tables = source_config.get("allTables") or source_config["tables"]
            selected_names = {t["name"] for t in source_config["tables"]}
            processed = orchestrator.design_custom_tools(
                all_tables, req.instructions,
                selected_table_names=selected_names,
                existing_names={t["name"] for t in existing_custom_tools},
            )
            source_config["customTools"] = existing_custom_tools + processed["customTools"]
            # Instructions asking to expose a whole table directly (not just
            # use it in a join) — pull the full table def from allTables so
            # it gets real list_/get_ tools too, not just appear in a join's SQL.
            all_by_name = {t["name"]: t for t in all_tables}
            for tname in processed["additionalTables"]:
                if tname in all_by_name:
                    source_config["tables"].append(all_by_name[tname])
        else:
            source_config["customTools"] = existing_custom_tools

        _progress("mcp:generating backing API")
        orchestrator.generate_backing_api(
            backing_dir, backing_name, source_config["dbPath"], source_config["tables"],
            source_config["customTools"],
        )
        upsert_api_project(
            backing_name, title=backing_name,
            description=f"Read-only backing API for MCP server '{name}' (generated, not hand-authored)",
            language="python", authType="none", port=None, status="draft",
            createdAt=datetime.now(timezone.utc).isoformat(),
        )

        _progress("mcp:starting backing API")
        backing_port = start_api_project(backing_name, backing_dir, "python")
        backing_started = wait_for_api(backing_name, backing_port, timeout=45)
        upsert_api_project(backing_name, port=backing_port, status="running" if backing_started else "start_failed")
        if not backing_started:
            raise RuntimeError(f"Backing API '{backing_name}' failed to start — check its own Build Log/logs")
        source_config["backingApiProject"] = backing_name
        source_config["backingApiBaseUrl"] = f"http://127.0.0.1:{backing_port}"

    if req.sourceType in ("api", "both") and req.instructions.strip() and instructions_changed:
        # No composite/join tools for the API source yet (see
        # mcp_orchestrator's module docstring — different mechanism, out of
        # scope for this pass) — instructions here only expand which
        # endpoints get mechanical tools, same "additionalTables" idea as the
        # datastore source's own instructions handling above.
        _progress("mcp:processing instructions")
        all_endpoints = source_config.get("allEndpoints") or source_config["endpoints"]
        selected_keys = {f"{e['method']} {e['path']}" for e in source_config["endpoints"]}
        additional_keys = orchestrator.select_additional_endpoints(all_endpoints, selected_keys, req.instructions)
        all_by_key = {f"{e['method']} {e['path']}": e for e in all_endpoints}
        for key in additional_keys:
            if key in all_by_key:
                source_config["endpoints"].append(all_by_key[key])

    _progress("mcp:generating")
    result = orchestrator.generate(project_dir, name, req.sourceType, source_config, {}, req.instructions)
    save_mcp_metadata(name, result["metadata"])

    # Same rationale as WebAPIGenerator's protected_env_file — the runner/other
    # endpoints should read credentials from a copy outside the project dir.
    if ".env" in result["files"]:
        protected_env_file(name).write_text(result["files"][".env"], encoding="utf-8")

    _progress("mcp:starting")
    port = start_mcp_project(name, project_dir)
    started = wait_for_mcp(name, port, timeout=45)

    upsert_mcp_project(
        name, title=name, sourceType=req.sourceType, port=port,
        backingApiProject=backing_name,
        status="running" if started else "start_failed",
        createdAt=datetime.now(timezone.utc).isoformat(),
    )

    elapsed = _time.time() - _t0
    append_mcp_buildlog(name, _progress_logs.get(request_id, []), event="Generated MCP server", duration_s=elapsed)
    append_mcp_history(name, "Updated" if previous_metadata else "Generated",
                        prompt=req.instructions, comment=req.comment)
    _progress("mcp:ready")

    return {
        "projectName": name,
        "port": port,
        "url": _mcp_project_url(port) if started else None,
        "running": started,
        "tools": result["tools"],
    }


@app.post("/api/mcp/generate")
async def api_mcp_generate(req: McpGenerateRequest):
    import uuid
    request_id = uuid.uuid4().hex
    _progress_logs[request_id] = []
    _project_request_ids[req.projectName] = request_id
    loop = asyncio.get_event_loop()

    _save_job(request_id, {
        "status": "running", "projectName": req.projectName, "result": None, "error": None,
    })

    async def _run_in_bg():
        try:
            result = await loop.run_in_executor(_executor, _run_mcp_generate, req.projectName, req, request_id)
            result["requestId"] = request_id
            _save_job(request_id, {
                "status": "completed", "projectName": result["projectName"], "result": result, "error": None,
            })
        except Exception as e:
            import traceback
            raw_detail = f"{type(e).__name__}: {e}"
            friendly = _friendly_error(raw_detail)
            print(f"\n[MCP GENERATE ERROR]\n{raw_detail}\n{traceback.format_exc()[-1500:]}\n", flush=True)

            from datetime import datetime as _dt_err
            _progress_logs.setdefault(request_id, []).append(
                f"[{_dt_err.now().strftime('%H:%M:%S')} +0.0s] error:{friendly}"
            )
            _save_job(request_id, {
                "status": "failed", "projectName": req.projectName, "result": None, "error": friendly,
            })
        finally:
            async def _cleanup():
                await asyncio.sleep(300)
                _progress_logs.pop(request_id, None)
            asyncio.create_task(_cleanup())

    asyncio.create_task(_run_in_bg())
    return {"requestId": request_id, "status": "running", "projectName": req.projectName}


@app.post("/api/mcp/generate-from-instructions")
async def api_mcp_generate_from_instructions(req: McpGenerateFromInstructionsRequest):
    """Same async job contract as /api/mcp/generate (poll /api/jobs/{id} +
    /api/generate/progress/{id}) -- the only difference is this one derives
    its own sourceConfig from `instructions` instead of requiring the caller
    to already have one. See _run_mcp_generate_from_instructions."""
    import uuid
    request_id = uuid.uuid4().hex
    _progress_logs[request_id] = []
    _project_request_ids[req.projectName] = request_id
    loop = asyncio.get_event_loop()

    _save_job(request_id, {
        "status": "running", "projectName": req.projectName, "result": None, "error": None,
    })

    async def _run_in_bg():
        try:
            result = await loop.run_in_executor(
                _executor, _run_mcp_generate_from_instructions, req.projectName, req, request_id,
            )
            result["requestId"] = request_id
            _save_job(request_id, {
                "status": "completed", "projectName": result["projectName"], "result": result, "error": None,
            })
        except Exception as e:
            import traceback
            raw_detail = f"{type(e).__name__}: {e}"
            friendly = _friendly_error(raw_detail)
            print(f"\n[MCP GENERATE-FROM-INSTRUCTIONS ERROR]\n{raw_detail}\n{traceback.format_exc()[-1500:]}\n", flush=True)

            from datetime import datetime as _dt_err
            _progress_logs.setdefault(request_id, []).append(
                f"[{_dt_err.now().strftime('%H:%M:%S')} +0.0s] error:{friendly}"
            )
            _save_job(request_id, {
                "status": "failed", "projectName": req.projectName, "result": None, "error": friendly,
            })
        finally:
            async def _cleanup():
                await asyncio.sleep(300)
                _progress_logs.pop(request_id, None)
            asyncio.create_task(_cleanup())

    asyncio.create_task(_run_in_bg())
    return {"requestId": request_id, "status": "running", "projectName": req.projectName}


def _run_api_refine(project_name: str, req: ApiRefineRequest, request_id: str) -> dict:
    """
    Update an already-generated API project — additive only (new entities,
    new fields, new endpoints). Mirrors the Web UI's own refine dispatch
    pattern (_run_refine_with_architecture): runs synchronously inside the
    background thread executor, reports progress the same way generation
    does, and restarts the app afterward so the new/changed code actually
    takes effect.
    """
    import time as _time
    _t0 = _time.time()

    def _progress(msg: str):
        from datetime import datetime as _dt
        elapsed = _time.time() - _t0
        ts = _dt.now().strftime("%H:%M:%S")
        _progress_logs.setdefault(request_id, []).append(f"[{ts} +{elapsed:.1f}s] {msg}")

    from api_agents.api_orchestrator import ApiCrewOrchestrator
    from api_agents.api_registry import (
        get_api_project, get_api_architecture, save_api_architecture,
        append_api_buildlog, upsert_api_project, append_api_history,
    )
    from api_agents.api_runner import start_api_project, wait_for_api, apply_pending_migrations
    from api_config import WEB_API_DIR, project_url as _api_project_url

    entry = get_api_project(project_name)
    if not entry:
        raise HTTPException(404, f"API project '{project_name}' not found")
    existing_architecture = get_api_architecture(project_name)
    if not existing_architecture:
        raise HTTPException(409, f"No saved architecture found for '{project_name}' — this project "
                                  f"was generated before architecture persistence, or its architecture "
                                  f"file is missing; refine can't safely merge changes without it")

    project_dir = WEB_API_DIR / project_name
    if not project_dir.exists():
        raise HTTPException(404, f"Project folder for '{project_name}' not found")
    language = entry.get("language", "python")
    api_options = {
        "language": language,
        "auth_type": entry.get("authType", "none"),
        "rate_limit": entry.get("rateLimit", 100),
        "database": "sqlite",
    }

    _progress("api:refining")
    # Same "persist from the start, not just at the end" reasoning as generate
    # (see api_generate) — a refine on one project running concurrently with
    # a generate/refine on another should never leave either's Build Log tab
    # showing stale/no activity for the whole duration.
    append_api_buildlog(project_name, ["Refine started..."], event="Refining", duration_s=0)
    orchestrator = ApiCrewOrchestrator(progress=_progress)
    # Same append pattern as /api/generate's own instructions handling —
    # instructions was previously only wired into the initial Generate call,
    # with no equivalent field for Refine at all, so any business-logic notes
    # (as opposed to a one-line "add field X") had nowhere to go once a
    # project already existed.
    instructions = (req.instructions or "").strip()
    refine_prompt = req.prompt
    if instructions:
        refine_prompt = f"{req.prompt}\n\n## Detailed Requirements\n\n{instructions}"
    result = orchestrator.refine(project_dir, existing_architecture, refine_prompt, api_options)
    save_api_architecture(project_name, result["architecture"])

    _progress("api:restarting")
    port = start_api_project(project_name, project_dir, language)
    started = wait_for_api(project_name, port, timeout=120 if language == "java" else 45)
    if started:
        # Tables/columns for brand-new entities are created automatically on
        # this restart (Hibernate ddl-auto=update / SQLAlchemy create_all) —
        # only Python's new-column-on-an-existing-table case needs this extra
        # step, since neither framework's own auto-migration alters existing
        # tables; see apply_pending_migrations's own docstring for why.
        _progress(f"api:migrating — {apply_pending_migrations(project_name, project_dir, language)}")

    upsert_api_project(project_name, port=port, status="running" if started else "start_failed")

    elapsed = _time.time() - _t0
    append_api_buildlog(project_name, _progress_logs.get(request_id, []),
                        event="Refined API", duration_s=elapsed)
    append_api_history(project_name, "Refined", prompt=req.prompt, comment=req.comment, instructions=instructions)
    _progress("api:ready")

    return {
        "projectName": project_name,
        "port": port,
        "url": _api_project_url(port) if started else None,
        "running": started,
        "addedEntities": result.get("addedEntities", []),
        "modifiedEntities": result.get("modifiedEntities", []),
    }


@app.post("/api/webapi/projects/{project_name}/refine")
async def api_webapi_refine(project_name: str, req: ApiRefineRequest):
    import uuid
    request_id = uuid.uuid4().hex
    _progress_logs[request_id] = []
    _project_request_ids[project_name] = request_id
    loop = asyncio.get_event_loop()

    _save_job(request_id, {
        "status": "running",
        "projectName": project_name,
        "prompt": req.prompt[:200],
        "result": None,
        "error": None,
    })

    async def _run_in_bg():
        try:
            result = await loop.run_in_executor(_executor, _run_api_refine, project_name, req, request_id)
            result["requestId"] = request_id
            _save_job(request_id, {
                "status": "completed", "projectName": project_name, "result": result, "error": None,
            })
        except Exception as e:
            import traceback
            raw_detail = f"{type(e).__name__}: {e}"
            friendly = _friendly_error(raw_detail)
            print(f"\n[API REFINE ERROR]\n{raw_detail}\n{traceback.format_exc()[-1500:]}\n", flush=True)

            from datetime import datetime as _dt_err
            _progress_logs.setdefault(request_id, []).append(
                f"[{_dt_err.now().strftime('%H:%M:%S')} +0.0s] error:{friendly}"
            )
            from api_agents.api_registry import append_api_buildlog
            append_api_buildlog(project_name, _progress_logs.get(request_id, []),
                                event="Refine failed", duration_s=0)

            _save_job(request_id, {
                "status": "failed", "projectName": project_name, "result": None, "error": friendly,
            })
        finally:
            async def _cleanup():
                await asyncio.sleep(300)
                _progress_logs.pop(request_id, None)
            asyncio.create_task(_cleanup())

    asyncio.create_task(_run_in_bg())
    return {"requestId": request_id, "status": "running", "projectName": project_name}


def _read_stored_basic_auth_creds(project_name: str) -> tuple[str, str] | None:
    """
    Read the project's stored Basic Auth credentials — prefers the protected
    .env copy outside the project directory (see protected_env_file's
    docstring: some generated apps overwrite their own .env at runtime, so
    that copy is the only reliably correct source), falling back to the
    in-project .env for projects generated before that copy existed.
    """
    from api_config import WEB_API_DIR, protected_env_file

    env_file = protected_env_file(project_name)
    if not env_file.exists():
        env_file = WEB_API_DIR / project_name / ".env"
    if not env_file.exists():
        return None
    creds = {}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("API_BASIC_AUTH_") and "=" in line:
            key, _, val = line.partition("=")
            creds[key.strip()] = val.strip()
    if creds.get("API_BASIC_AUTH_USERNAME") and creds.get("API_BASIC_AUTH_PASSWORD"):
        return creds["API_BASIC_AUTH_USERNAME"], creds["API_BASIC_AUTH_PASSWORD"]
    return None


def _basic_auth_header(username: str, password: str) -> str:
    import base64
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"


@app.get("/api/webapi/projects/{project_name}/usage")
async def api_webapi_usage(project_name: str, request: Request):
    from api_agents.api_registry import get_api_project

    entry = get_api_project(project_name)
    if not entry or not entry.get("port"):
        raise HTTPException(404, f"API project '{project_name}' not found or not running")

    # /usage is behind the project's own auth like every other route. Forward an
    # incoming Authorization header verbatim — this lets the frontend's custom
    # Basic Auth login form (ApiGeneratorPage.tsx) verify arbitrary credentials
    # via this same same-origin endpoint (avoids CORS entirely, since the browser
    # only ever talks to this platform server, not the generated API's port
    # directly). Falls back to the stored credentials when no header is given,
    # so the automatic Usage-tab refresh keeps working unattended.
    headers = {}
    incoming_auth = request.headers.get("authorization")
    if incoming_auth:
        headers["Authorization"] = incoming_auth
    elif entry.get("authType") == "basic":
        creds = _read_stored_basic_auth_creds(project_name)
        if creds:
            headers["Authorization"] = _basic_auth_header(*creds)

    import httpx
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"http://localhost:{entry['port']}/usage", headers=headers)
    except Exception as e:
        raise HTTPException(502, f"Could not reach running API's /usage endpoint: {e}")

    if resp.status_code == 401:
        raise HTTPException(401, "Invalid credentials")
    resp.raise_for_status()
    return resp.json()


@app.post("/api/webapi/projects/{project_name}/usage/reset")
async def api_webapi_usage_reset(project_name: str):
    """
    Wipes the running API's usage log — a dev/test convenience now that the
    rate limiter is backed by that same table (see rate_limit_status /
    UsageDb.rateLimitStatus) rather than an in-memory counter a restart used
    to clear for free.
    """
    from api_agents.api_registry import get_api_project

    entry = get_api_project(project_name)
    if not entry or not entry.get("port"):
        raise HTTPException(404, f"API project '{project_name}' not found or not running")

    headers = {}
    if entry.get("authType") == "basic":
        creds = _read_stored_basic_auth_creds(project_name)
        if creds:
            headers["Authorization"] = _basic_auth_header(*creds)

    import httpx
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(f"http://localhost:{entry['port']}/usage/reset", headers=headers)
    except Exception as e:
        raise HTTPException(502, f"Could not reach running API's /usage/reset endpoint: {e}")

    if resp.status_code == 401:
        raise HTTPException(401, "Invalid credentials")
    resp.raise_for_status()
    return resp.json()


@app.get("/api/webapi/projects/{project_name}/buildlog")
async def api_webapi_buildlog(project_name: str):
    from api_agents.api_registry import get_api_buildlog
    return {"runs": get_api_buildlog(project_name)}


@app.get("/api/webapi/projects/{project_name}/history")
async def api_webapi_history(project_name: str):
    from api_agents.api_registry import get_api_history
    return get_api_history(project_name)


@app.get("/api/webapi/projects/{project_name}/architecture")
async def api_webapi_architecture(project_name: str):
    from api_agents.api_registry import get_api_architecture
    arch = get_api_architecture(project_name)
    return {"architecture": arch, "exists": arch is not None}


@app.get("/api/webapi/projects/{project_name}/architecture.html")
async def api_webapi_architecture_html(project_name: str):
    """Return the persisted architecture HTML doc, mirroring the web-app equivalent."""
    from api_config import WEB_API_DIR
    html_file = WEB_API_DIR / project_name / ".architecture.html"
    if not html_file.exists():
        return HTMLResponse("<p>No architecture yet.</p>", status_code=404)
    try:
        return HTMLResponse(html_file.read_text(encoding="utf-8"))
    except Exception:
        return HTMLResponse("<p>Could not read architecture document.</p>", status_code=500)


@app.api_route(
    "/api/webapi/projects/{project_name}/docs-proxy/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
)
async def api_webapi_docs_proxy(project_name: str, path: str, request: Request):
    """
    Same-origin reverse proxy for the generated API's interactive docs (Swagger UI /
    FastAPI's /docs). Chrome now blocks `user:pass@host` iframe URLs outright (the
    embedded-credentials technique this replaced), and a bare cross-origin iframe
    would otherwise trigger the native Basic Auth popup the custom login form exists
    to avoid. Every proxied request gets the stored credentials injected server-side
    — the frontend's login form is a UX gate in front of this, not a channel for
    passing through arbitrary credentials.
    """
    import json as _json

    from api_agents.api_registry import get_api_project

    entry = get_api_project(project_name)
    if not entry or not entry.get("port") or entry.get("status") != "running":
        raise HTTPException(404, f"API project '{project_name}' not found or not running")

    proxy_base = f"/api/webapi/projects/{project_name}/docs-proxy"
    target_url = f"http://localhost:{entry['port']}/{path}"

    headers = {}
    if entry.get("authType") == "basic":
        creds = _read_stored_basic_auth_creds(project_name)
        if creds:
            headers["Authorization"] = _basic_auth_header(*creds)

    body = await request.body()

    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.request(
                request.method, target_url,
                params=request.query_params.multi_items(), headers=headers,
                content=body or None,
            )
    except Exception as e:
        raise HTTPException(502, f"Could not reach running API: {e}")

    content_type = resp.headers.get("content-type", "")
    content = resp.content

    # Redirects (e.g. springdoc's /swagger-ui.html -> /swagger-ui/index.html?...)
    # would otherwise send the browser straight at the real API's own origin,
    # escaping the proxy entirely — rewrite absolute-path Locations to stay under
    # our prefix. Also drop WWW-Authenticate: with creds injected server-side, a
    # 401 here is exceptional, and the header would otherwise make some browsers
    # attempt (and fail) their own native Basic Auth prompt inside the iframe.
    response_headers = {}
    location = resp.headers.get("location")
    if location:
        response_headers["location"] = proxy_base + location if location.startswith("/") else location

    if path.endswith("swagger-ui/swagger-initializer.js"):
        # The webjar's own swagger-initializer.js ships with a hardcoded
        # petstore.swagger.io demo URL and a stale "configUrl" that springdoc's
        # SwaggerIndexTransformer is supposed to patch at request time — it
        # doesn't fire for every springdoc/webjar version combination generated
        # apps end up with, so the demo spec loads instead of the real one.
        # Deterministically replace it rather than depending on that transformer
        # ever running. The actual spec path isn't always the default
        # /v3/api-docs — generated projects have been observed overriding
        # springdoc.api-docs.path in application.properties — so probe for it
        # live instead of hardcoding one path. Whichever path is used, it's
        # relative to swagger-ui/index.html (the document swagger-ui-bundle.js
        # resolves fetch() against), so it lands on this same proxy's own
        # equivalent path, not springdoc's real one.
        spec_path = "v3/api-docs"
        try:
            async with httpx.AsyncClient(timeout=5) as probe:
                probe_resp = await probe.get(f"http://localhost:{entry['port']}/v3/api-docs", headers=headers)
                if probe_resp.status_code != 200 or "openapi" not in probe_resp.text[:200]:
                    alt_resp = await probe.get(f"http://localhost:{entry['port']}/api-docs", headers=headers)
                    if alt_resp.status_code == 200 and "openapi" in alt_resp.text[:200]:
                        spec_path = "api-docs"
        except Exception:
            pass
        content = (
            "window.onload = function() {\n"
            "  window.ui = SwaggerUIBundle({\n"
            f'    url: "../{spec_path}",\n'
            "    dom_id: '#swagger-ui',\n"
            "    deepLinking: true,\n"
            "    presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],\n"
            "    plugins: [SwaggerUIBundle.plugins.DownloadUrl],\n"
            '    layout: "StandaloneLayout"\n'
            "  });\n"
            "};\n"
        ).encode("utf-8")
    elif "application/json" in content_type:
        try:
            data = _json.loads(content)
            if isinstance(data, dict) and "openapi" in data:
                # Swagger UI's "Try it out" execute calls use servers[0].url as
                # their base — point it back at this proxy so those calls stay
                # authenticated and same-origin instead of hitting the real port
                # directly.
                data["servers"] = [{"url": proxy_base}]
                content = _json.dumps(data).encode("utf-8")
        except Exception:
            pass
    elif "text/html" in content_type and b"/openapi.json" in content:
        # FastAPI's /docs page hardcodes an absolute-path reference to its spec
        # inline in a <script> tag (single-quoted in FastAPI's own template);
        # rewrite it to stay under the proxy prefix. springdoc's swagger-ui.html
        # needs no such rewrite — its configUrl is supplied via query string by
        # the frontend, already proxy-prefixed.
        content = content.replace(b"/openapi.json", f"{proxy_base}/openapi.json".encode("utf-8"))

    return Response(
        content=content,
        status_code=resp.status_code,
        media_type=content_type or None,
        headers=response_headers,
    )


def _find_row_array(obj, depth: int = 0):
    """
    Recursively find the first array-of-objects in an arbitrary JSON response —
    generated APIs don't all wrap list responses the same way (some use
    {"data": [...]}, others nest it further as {"data": {"data": [...], ...}}),
    so this is a best-effort heuristic rather than a fixed-shape parse.
    """
    if depth > 4:
        return None
    if isinstance(obj, list) and obj and all(isinstance(x, dict) for x in obj):
        return obj
    if isinstance(obj, dict):
        for v in obj.values():
            found = _find_row_array(v, depth + 1)
            if found:
                return found
    return None


@app.get("/api/webapi/projects/{project_name}/examples")
async def api_webapi_examples(project_name: str, request: Request):
    """
    Ready-to-run example requests for every endpoint, built from a real sample
    row pulled live from that resource's list endpoint — not generic Swagger
    placeholders. Path params get a real ID substituted in; POST/PUT/PATCH bodies
    reuse real field values (minus server-generated ones like id/created_at).
    """
    import json as _json
    import re as _re

    from api_agents.api_registry import get_api_project, get_api_architecture

    entry = get_api_project(project_name)
    if not entry or not entry.get("port") or entry.get("status") != "running":
        raise HTTPException(404, f"API project '{project_name}' not found or not running")

    arch = get_api_architecture(project_name)
    endpoints = (arch or {}).get("endpoints") or []
    entities = (arch or {}).get("entities") or []
    if not endpoints:
        return {"examples": []}

    base_url = f"http://localhost:{entry['port']}"

    # Forward an incoming Authorization header (same convention as /usage), else
    # fall back to the stored credentials so this works unattended too.
    headers = {}
    auth_display = None  # (username, password), used to build a copy-pasteable curl -u
    incoming_auth = request.headers.get("authorization")
    if incoming_auth:
        headers["Authorization"] = incoming_auth
    elif entry.get("authType") == "basic":
        creds = _read_stored_basic_auth_creds(project_name)
        if creds:
            auth_display = creds
            headers["Authorization"] = _basic_auth_header(*creds)

    def base_path(p: str) -> str:
        return _re.sub(r"/\{[^}]+\}.*$", "", p)

    def build_curl(method: str, path: str, body: dict | None) -> str:
        parts = ["curl"]
        if auth_display:
            parts.append(f"-u {auth_display[0]}:{auth_display[1]}")
        if method != "GET":
            parts.append(f"-X {method}")
        parts.append(f"'{base_url}{path}'")
        if body is not None:
            parts.append("-H 'Content-Type: application/json'")
            parts.append(f"-d '{_json.dumps(body)}'")
        return " ".join(parts)

    import httpx
    sample_by_base: dict[str, dict | None] = {}
    examples = []

    async with httpx.AsyncClient(timeout=5) as client:
        for ep in endpoints:
            method = (ep.get("method") or "GET").upper()
            path = ep.get("path") or ""
            bpath = base_path(path)

            if bpath not in sample_by_base:
                sample_by_base[bpath] = None
                try:
                    resp = await client.get(f"{base_url}{bpath}", headers=headers)
                    if resp.status_code == 200:
                        rows = _find_row_array(resp.json())
                        if rows:
                            sample_by_base[bpath] = rows[0]
                except Exception:
                    pass

            sample = sample_by_base.get(bpath)

            resolved_path = path
            for m in _re.finditer(r"\{(\w+)\}", path):
                param = m.group(1)
                value = None
                if sample:
                    value = next((v for k, v in sample.items() if k.lower() == param.lower()), None)
                    if value is None:
                        value = next((v for k, v in sample.items() if k.lower() == "id"), None)
                    if value is None:
                        value = next(iter(sample.values()), None)
                resolved_path = resolved_path.replace(m.group(0), str(value) if value is not None else f"{{{param}}}")

            body = None
            if method in ("POST", "PUT", "PATCH") and sample:
                skip = {"id", "created_at", "createdat", "updated_at", "updatedat"}
                body = {k: v for k, v in sample.items() if k.lower() not in skip}

            entity_name = next(
                (e.get("name") for e in entities
                 if e.get("table") and e["table"].lower() in bpath.lower()),
                None,
            )

            examples.append({
                "entity": entity_name,
                "method": method,
                "path": resolved_path,
                "description": ep.get("description", ""),
                "curl": build_curl(method, resolved_path, body),
                "body": body,
            })

    return {"examples": examples}


# ── API Docker endpoints — opt-in, separate from generation ─────────────────
# Mirrors the Web UI's /api/projects/{name}/docker/* endpoints (agents.docker_agent)
# exactly in shape/lifecycle, but backed by api_agents.api_docker — no React
# frontend to vite-build here, so building an image just needs the API's own
# (on-demand-generated) Dockerfile.

@app.get("/api/webapi/projects/{project_name}/docker/status")
async def api_webapi_docker_status(project_name: str):
    from api_agents.api_docker import get_status
    return get_status(project_name)


def _run_webapi_docker_build(project_name: str, request_id: str) -> dict:
    import time as _t
    _t0 = _t.time()
    from api_agents.api_docker import build_image, get_status, is_docker_available
    from api_agents.api_registry import get_api_project, get_api_architecture
    from api_config import WEB_API_DIR

    if not is_docker_available():
        raise RuntimeError("Docker Desktop is not running. Please start Docker Desktop and try again.")

    entry = get_api_project(project_name)
    if not entry:
        raise RuntimeError(f"Project '{project_name}' not found")
    project_dir = WEB_API_DIR / project_name
    if not project_dir.exists():
        raise RuntimeError(f"Project '{project_name}' not found")

    def _progress(msg: str):
        from datetime import datetime as _dt
        elapsed = _t.time() - _t0
        ts = _dt.now().strftime("%H:%M:%S")
        _progress_logs.setdefault(request_id, []).append(f"[{ts} +{elapsed:.1f}s] {msg}")

    architecture = get_api_architecture(project_name) or {}
    ok, out = build_image(project_name, project_dir, entry.get("language", "python"), architecture, progress=_progress)
    if not ok:
        lower = out.lower()
        if any(k in lower for k in ("grpc", "eof", "connection refused", "not found", "daemon", "pipe")):
            raise RuntimeError(
                "Docker Desktop is not fully running. Please ensure Docker Desktop is started "
                "and ready (check the whale icon in the system tray), then try again."
            )
        raise RuntimeError(out)
    _progress("docker_build:done")
    return get_status(project_name)


@app.post("/api/webapi/projects/{project_name}/docker/build")
async def api_webapi_docker_build(project_name: str):
    global _latest_request_id
    import uuid
    request_id = uuid.uuid4().hex
    _progress_logs[request_id] = []
    _latest_request_id = request_id
    _project_request_ids[project_name] = request_id
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(_executor, _run_webapi_docker_build, project_name, request_id)
        result["requestId"] = request_id
        return result
    except Exception as e:
        raise HTTPException(500, f"{type(e).__name__}: {e}")
    finally:
        async def _cleanup():
            await asyncio.sleep(120)
            _progress_logs.pop(request_id, None)
        asyncio.create_task(_cleanup())


@app.get("/api/webapi/projects/{project_name}/docker/download")
async def api_webapi_docker_download(project_name: str):
    from api_agents.api_docker import save_image
    ok, tar_path, err = save_image(project_name)
    if not ok:
        raise HTTPException(500, err)
    if not tar_path.exists():
        raise HTTPException(404, "tar file not found")
    return FileResponse(str(tar_path), media_type="application/octet-stream", filename=f"{project_name}.tar")


@app.post("/api/webapi/projects/{project_name}/docker/run")
async def api_webapi_docker_run(project_name: str):
    from api_agents.api_docker import run_container, get_status
    from api_agents.api_registry import get_api_project
    entry = get_api_project(project_name)
    if not entry:
        raise HTTPException(404, f"Project '{project_name}' not found")
    loop = asyncio.get_event_loop()
    ok, out = await loop.run_in_executor(_executor, run_container, project_name, entry.get("language", "python"))
    if not ok:
        raise HTTPException(500, out)
    return get_status(project_name)


@app.post("/api/webapi/projects/{project_name}/docker/stop")
async def api_webapi_docker_stop(project_name: str):
    from api_agents.api_docker import stop_container, get_status
    await asyncio.get_event_loop().run_in_executor(_executor, stop_container, project_name)
    return get_status(project_name)


@app.post("/api/webapi/projects/{project_name}/docker/start")
async def api_webapi_docker_start_container(project_name: str):
    from api_agents.api_docker import start_container, get_status
    loop = asyncio.get_event_loop()
    ok, out = await loop.run_in_executor(_executor, start_container, project_name)
    if not ok:
        raise HTTPException(500, out)
    return get_status(project_name)


@app.delete("/api/webapi/projects/{project_name}/docker/container")
async def api_webapi_docker_delete_container(project_name: str):
    from api_agents.api_docker import delete_container, get_status
    await asyncio.get_event_loop().run_in_executor(_executor, delete_container, project_name)
    return get_status(project_name)


@app.get("/api/projects/{project_name}/qa")
async def api_qa(project_name: str):
    """Run QA checks on an existing project and return the report."""
    from agents.uigen_agent import GENERATED_DIR
    from agents.qa_agent import run_qa
    project_dir = GENERATED_DIR / project_name
    if not project_dir.exists():
        raise HTTPException(404, f"Project '{project_name}' not found")
    from agents.uigen_agent import _dev_ports
    port = _dev_ports.get(project_name, 0)
    loop = asyncio.get_event_loop()
    report = await loop.run_in_executor(None, run_qa, project_name, port, project_dir)
    return report.to_dict()


@app.post("/api/start/{project_name}")
async def api_start(project_name: str):
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(_executor, _dispatch_start, project_name)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/stop/{project_name}")
async def api_stop(project_name: str):
    _dispatch_stop(project_name)
    # Return updated project info so UI can refresh without extra call
    projects = list_projects()
    project = next((p for p in projects if p["name"] == project_name), {"stopped": project_name})
    return project


# ── Docker endpoints ──────────────────────────────────────────────────────────

@app.get("/api/projects/{project_name}/docker/status")
async def api_docker_status(project_name: str):
    from agents.docker_agent import get_status
    return get_status(project_name)


def _run_docker_build(project_name: str, request_id: str) -> dict:
    import time as _t
    _t0 = _t.time()
    from agents.uigen_agent import GENERATED_DIR
    from agents.docker_agent import build_image, get_status, is_docker_available

    if not is_docker_available():
        raise RuntimeError("Docker Desktop is not running. Please start Docker Desktop and try again.")

    project_dir = GENERATED_DIR / project_name
    if not project_dir.exists():
        raise RuntimeError(f"Project '{project_name}' not found")

    def _progress(msg: str):
        from datetime import datetime as _dt
        elapsed = _t.time() - _t0
        ts = _dt.now().strftime("%H:%M:%S")
        _progress_logs.setdefault(request_id, []).append(
            f"[{ts} +{elapsed:.1f}s] {msg}"
        )

    ok, out = build_image(project_name, project_dir, progress=_progress)
    if not ok:
        # Detect Docker connectivity issues and provide a friendly message
        lower = out.lower()
        if any(k in lower for k in ("grpc", "eof", "connection refused", "not found", "daemon", "pipe")):
            raise RuntimeError(
                "Docker Desktop is not fully running. Please ensure Docker Desktop is started "
                "and ready (check the whale icon in the system tray), then try again."
            )
        raise RuntimeError(out)
    _progress(f"docker_build:done")
    return get_status(project_name)


@app.post("/api/projects/{project_name}/docker/build")
async def api_docker_build(project_name: str):
    global _latest_request_id
    import uuid
    request_id = uuid.uuid4().hex
    _progress_logs[request_id] = []
    _latest_request_id = request_id
    _project_request_ids[project_name] = request_id
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            _executor, _run_docker_build, project_name, request_id
        )
        result["requestId"] = request_id
        return result
    except Exception as e:
        import traceback
        raise HTTPException(500, f"{type(e).__name__}: {e}")
    finally:
        async def _cleanup():
            await asyncio.sleep(120)
            _progress_logs.pop(request_id, None)
        asyncio.create_task(_cleanup())


@app.get("/api/projects/{project_name}/docker/download")
async def api_docker_download(project_name: str):
    from agents.docker_agent import save_image
    ok, tar_path, err = save_image(project_name)
    if not ok:
        raise HTTPException(500, err)
    if not tar_path.exists():
        raise HTTPException(404, "tar file not found")
    return FileResponse(
        str(tar_path),
        media_type="application/octet-stream",
        filename=f"{project_name}.tar",
    )


@app.post("/api/projects/{project_name}/docker/run")
async def api_docker_run(project_name: str):
    from agents.docker_agent import run_container, get_status
    loop = asyncio.get_event_loop()
    ok, out = await loop.run_in_executor(_executor, run_container, project_name)
    if not ok:
        raise HTTPException(500, out)
    return get_status(project_name)


@app.post("/api/projects/{project_name}/docker/stop")
async def api_docker_stop(project_name: str):
    from agents.docker_agent import stop_container, get_status
    await asyncio.get_event_loop().run_in_executor(_executor, stop_container, project_name)
    return get_status(project_name)


@app.post("/api/projects/{project_name}/docker/start")
async def api_docker_start_container(project_name: str):
    from agents.docker_agent import start_container, get_status
    loop = asyncio.get_event_loop()
    ok, out = await loop.run_in_executor(_executor, start_container, project_name)
    if not ok:
        raise HTTPException(500, out)
    return get_status(project_name)


@app.delete("/api/projects/{project_name}/docker/container")
async def api_docker_delete_container(project_name: str):
    from agents.docker_agent import delete_container, get_status
    await asyncio.get_event_loop().run_in_executor(_executor, delete_container, project_name)
    return get_status(project_name)


@app.get("/api/projects/{project_name}/screenshots")
async def api_project_screenshots(project_name: str):
    """Return base64-encoded screenshots for a project, from its screenshots/ subfolder."""
    import base64 as _b64
    from agents.uigen_agent import GENERATED_DIR
    screenshots_dir = GENERATED_DIR / project_name / "screenshots"
    if not screenshots_dir.exists():
        return {"screenshots": []}
    shots = []
    for f in sorted(screenshots_dir.iterdir()):
        if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            try:
                b64 = _b64.b64encode(f.read_bytes()).decode()
                shots.append({
                    "filename": f.name,
                    "data":     b64,
                    "mimetype": "image/png" if f.suffix.lower() == ".png" else "image/jpeg",
                })
            except Exception:
                pass
    return {"screenshots": shots, "count": len(shots)}


@app.get("/api/figma/webapp-screenshots/{project_name}")
async def api_figma_webapp_screenshots(project_name: str):
    """Return base64-encoded screenshots for a figma-mockup project."""
    import base64 as _b64
    screenshots_dir = _FIGMA_PROJECTS_DIR / project_name / "screenshots"
    if not screenshots_dir.exists():
        return {"screenshots": [], "count": 0}
    shots = []
    for f in sorted(screenshots_dir.iterdir()):
        if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            try:
                b64 = _b64.b64encode(f.read_bytes()).decode()
                shots.append({
                    "filename": f.name,
                    "data":     b64,
                    "mimetype": "image/png" if f.suffix.lower() == ".png" else "image/jpeg",
                })
            except Exception:
                pass
    return {"screenshots": shots, "count": len(shots)}


@app.delete("/api/delete/{project_name}")
async def api_delete(project_name: str):
    # delete_project() is a slow, synchronous, blocking call (subprocess calls,
    # retries, sleeps for OneDrive/Vite file-lock release — can take up to ~90s)
    # while a generation job for the same name runs concurrently on a SEPARATE
    # thread pool executor thread, unaffected by this endpoint blocking the main
    # event loop. With no lock between them, deleting a project that still has
    # an active generation job racing against it can let this rmtree finish
    # AFTER that job finishes writing its output, silently wiping out a
    # generation the job store still reports as "completed" — observed live:
    # a fresh multi-page app vanished from disk entirely right after finishing.
    import re as _re_del
    project_slug = _re_del.sub(r"[^a-z0-9-]", "-", project_name.lower()).strip("-")
    active_request_id = _project_request_ids.get(project_slug)
    if active_request_id:
        active_job = _load_job(active_request_id)
        if active_job and active_job.get("status") == "running":
            raise HTTPException(
                status_code=409,
                detail=(
                    f"A generation is currently in progress for '{project_name}'. "
                    f"Wait for it to finish (or fail) before deleting — deleting now "
                    f"can silently wipe out the generation's output once it completes."
                ),
            )
    _delete_progress_logs[project_slug] = []
    _deletes_in_progress.add(project_slug)

    def _record(step: str):
        import datetime as _dt
        _delete_progress_logs[project_slug].append(f"[{_dt.datetime.now().strftime('%H:%M:%S')}] {step}")
        print(f"[delete:{project_name}] {step}", flush=True)

    try:
        # Run the actual (blocking) delete work in the thread pool rather than
        # directly on the event loop — this endpoint still only returns once
        # delete_project() has genuinely finished (awaited below, so callers
        # can rely on "response received" meaning "done"), but the event loop
        # itself stays free to service the progress-polling endpoint below
        # while the delete is in flight, instead of freezing the whole server.
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor, lambda: _dispatch_delete(project_name, _record))
    finally:
        _deletes_in_progress.discard(project_slug)
    return {"deleted": project_name}


@app.get("/api/delete/progress/{project_name}")
async def api_delete_progress(project_name: str):
    """Poll while a delete is in flight to show real step-by-step activity
    instead of an unexplained multi-second wait (see api_delete)."""
    import re as _re_del2
    project_slug = _re_del2.sub(r"[^a-z0-9-]", "-", project_name.lower()).strip("-")
    return {
        "inProgress": project_slug in _deletes_in_progress,
        "log": _delete_progress_logs.get(project_slug, []),
    }


@app.get("/api/projects/{project_name}/files")
async def api_project_files(project_name: str):
    """Return all source files for a React project so Sandpack can render them in-browser."""
    from agents.uigen_agent import GENERATED_DIR
    project_dir = GENERATED_DIR / project_name
    if not project_dir.exists():
        raise HTTPException(404, f"Project '{project_name}' not found")

    files: dict[str, str] = {}
    # Collect files Sandpack needs: package.json, vite config, index.html, all src/**
    targets = [
        project_dir / "package.json",
        project_dir / "vite.config.ts",
        project_dir / "index.html",
        project_dir / "tsconfig.json",
        project_dir / "postcss.config.js",
        project_dir / "tailwind.config.js",
    ]
    for f in targets:
        if f.exists():
            try:
                files[f.name] = f.read_text(encoding="utf-8")
            except Exception:
                pass

    src_dir = project_dir / "src"
    if src_dir.exists():
        for f in src_dir.rglob("*"):
            if f.is_file() and f.suffix in (".tsx", ".ts", ".css", ".json", ".js"):
                rel = f.relative_to(project_dir).as_posix()
                try:
                    files[rel] = f.read_text(encoding="utf-8")
                except Exception:
                    pass

    return {"files": files, "project": project_name}


@app.get("/sandbox/{project_name}")
async def sandbox_page(project_name: str):
    """Serve the main SPA for the sandbox preview route."""
    if (UI_DIST / "index.html").exists():
        return FileResponse(UI_DIST / "index.html")
    if UI_DEV.exists():
        return FileResponse(UI_DEV)
    return HTMLResponse("<h2>UI not built.</h2>")


_CANONICAL_PPTX_EXPORT = '''\
import pptxgen from 'pptxgenjs'

export type ChartKind = 'bar' | 'line' | 'donut' | 'groupedBar' | 'area'

export interface ChartSpec {
  kind: ChartKind
  title: string
  bars?: { label: string; value: number; color: string }[]
  categories?: string[]
  series?: { label: string; color: string; values: number[] }[]
  valueFormat?: string
}

export interface SlideContent {
  title: string
  subtitle?: string
  body?: string
  chart?: ChartSpec | null
}

export interface DeckOptions {
  title: string
  subtitle?: string
  author?: string
  primaryColor?: string
  slides: SlideContent[]
}

const BRAND_DARK = '0D1B2A'
const BRAND_BLUE = '0064D2'
const TEXT_GRAY = '6B7280'

function stripHash(c?: string): string {
  if (!c) return BRAND_BLUE
  return c.replace(/^#/, '').toUpperCase()
}

function addChartToSlide(
  pres: pptxgen,
  slide: pptxgen.Slide,
  chart: ChartSpec,
  region: { x: number; y: number; w: number; h: number }
): void {
  const { x, y, w, h } = region

  if ((chart.kind === 'bar' || chart.kind === 'donut') && chart.bars && chart.bars.length) {
    const labels = chart.bars.map((b) => b.label)
    const values = chart.bars.map((b) => b.value)
    const colors = chart.bars.map((b) => stripHash(b.color))

    if (chart.kind === 'donut') {
      slide.addChart(pres.ChartType.doughnut, [{ name: chart.title, labels, values }], {
        x, y, w, h,
        chartColors: colors,
        holeSize: 55,
        showLegend: true,
        legendPos: 'r',
        legendFontSize: 9,
        showValue: false,
        showPercent: true,
        dataLabelColor: 'FFFFFF',
        dataLabelFontSize: 9,
      })
    } else {
      slide.addChart(pres.ChartType.bar, [{ name: chart.title, labels, values }], {
        x, y, w, h,
        barDir: 'bar',
        chartColors: colors,
        showLegend: false,
        showValue: true,
        dataLabelFontSize: 8,
        dataLabelColor: '333333',
        catAxisLabelFontSize: 9,
        valAxisLabelFontSize: 8,
        valAxisHidden: false,
      })
    }
    return
  }

  if ((chart.kind === 'line' || chart.kind === 'area') && chart.series && chart.categories) {
    const cats = chart.categories
    const dataSeries = chart.series.map((s) => ({ name: s.label, labels: cats, values: s.values }))
    const colors = chart.series.map((s) => stripHash(s.color))
    slide.addChart(
      chart.kind === 'area' ? pres.ChartType.area : pres.ChartType.line,
      dataSeries,
      {
        x, y, w, h,
        chartColors: colors,
        showLegend: true,
        legendPos: 'b',
        legendFontSize: 9,
        lineSize: 2,
        lineSmooth: chart.kind === 'line',
        catAxisLabelFontSize: 9,
        valAxisLabelFontSize: 8,
        showValue: false,
      }
    )
    return
  }

  if (chart.kind === 'groupedBar' && chart.series && chart.categories) {
    const cats = chart.categories
    const dataSeries = chart.series.map((s) => ({ name: s.label, labels: cats, values: s.values }))
    const colors = chart.series.map((s) => stripHash(s.color))
    slide.addChart(pres.ChartType.bar, dataSeries, {
      x, y, w, h,
      barDir: 'col',
      barGrouping: 'clustered',
      chartColors: colors,
      showLegend: true,
      legendPos: 'b',
      legendFontSize: 9,
      catAxisLabelFontSize: 9,
      valAxisLabelFontSize: 8,
    })
    return
  }

  if (chart.bars && chart.bars.length) {
    const labels = chart.bars.map((b) => b.label)
    const values = chart.bars.map((b) => b.value)
    const colors = chart.bars.map((b) => stripHash(b.color))
    slide.addChart(pres.ChartType.bar, [{ name: chart.title, labels, values }], {
      x, y, w, h,
      barDir: 'bar',
      chartColors: colors,
      showLegend: false,
      showValue: true,
      dataLabelFontSize: 8,
      catAxisLabelFontSize: 9,
      valAxisLabelFontSize: 8,
    })
  }
}

export async function exportDeck(opts: DeckOptions): Promise<void> {
  const pres = new pptxgen()
  pres.author = opts.author || document.title || 'App'
  pres.company = opts.author || document.title || 'App'
  pres.title = opts.title
  pres.layout = 'LAYOUT_WIDE'

  const accent = stripHash(opts.primaryColor || BRAND_BLUE)

  const titleSlide = pres.addSlide()
  titleSlide.background = { color: BRAND_DARK }
  titleSlide.addShape(pres.ShapeType.rect, { x: 0, y: 2.4, w: 0.18, h: 1.9, fill: { color: accent } })
  titleSlide.addText(opts.title, { x: 0.6, y: 2.4, w: 11.5, h: 1.0, fontSize: 40, bold: true, color: 'FFFFFF', fontFace: 'Arial' })
  if (opts.subtitle) {
    titleSlide.addText(opts.subtitle, { x: 0.62, y: 3.5, w: 11.5, h: 0.6, fontSize: 18, color: 'B8C2CC', fontFace: 'Arial' })
  }
  titleSlide.addText('Generated ' + new Date().toLocaleDateString(), { x: 0.62, y: 6.6, w: 11.5, h: 0.4, fontSize: 11, color: TEXT_GRAY, fontFace: 'Arial' })

  for (const sc of opts.slides) {
    const slide = pres.addSlide()
    slide.background = { color: 'FFFFFF' }
    slide.addShape(pres.ShapeType.rect, { x: 0, y: 0, w: '100%', h: 0.75, fill: { color: BRAND_DARK } })
    slide.addShape(pres.ShapeType.rect, { x: 0, y: 0, w: 0.12, h: 0.75, fill: { color: accent } })
    slide.addText(sc.title, { x: 0.35, y: 0, w: 11, h: 0.75, fontSize: 22, bold: true, color: 'FFFFFF', fontFace: 'Arial', valign: 'middle' })
    if (sc.subtitle) {
      slide.addText(sc.subtitle, { x: 0.4, y: 0.95, w: 12.3, h: 0.4, fontSize: 13, italic: true, color: TEXT_GRAY, fontFace: 'Arial' })
    }
    const hasChart = !!sc.chart
    const bodyY = sc.subtitle ? 1.45 : 1.05
    if (hasChart && sc.body) {
      slide.addText(sc.body, { x: 0.4, y: bodyY, w: 5.2, h: 5.4, fontSize: 13, color: '374151', fontFace: 'Arial', valign: 'top', lineSpacingMultiple: 1.3 })
      addChartToSlide(pres, slide, sc.chart!, { x: 5.9, y: bodyY, w: 6.8, h: 5.4 })
    } else if (hasChart) {
      addChartToSlide(pres, slide, sc.chart!, { x: 0.6, y: bodyY, w: 12.1, h: 5.6 })
    } else if (sc.body) {
      slide.addText(sc.body, { x: 0.4, y: bodyY, w: 12.3, h: 5.6, fontSize: 14, color: '374151', fontFace: 'Arial', valign: 'top', lineSpacingMultiple: 1.35 })
    }
    slide.addText(opts.author || document.title || 'App', { x: 0.4, y: 7.0, w: 6, h: 0.3, fontSize: 9, color: '9CA3AF', fontFace: 'Arial' })
  }

  const safeName = opts.title.replace(/[^a-z0-9]+/gi, '-').toLowerCase()
  await pres.writeFile({ fileName: `${safeName}.pptx` })
}

export async function exportSingleChart(
  chart: ChartSpec,
  title?: string,
  body?: string,
  primaryColor?: string
): Promise<void> {
  await exportDeck({
    title: title || chart.title,
    subtitle: 'Chart Export',
    primaryColor,
    slides: [{ title: chart.title, body, chart }],
  })
}
'''


def _fix_pptx_export(files: dict) -> dict:
    """
    Ensures every generated React app has a canonical pptxExport.ts utility in
    src/utils/, and patches any page that still uses a JSON-blob PPTX stub.

    Steps:
      1. Always inject src/utils/pptxExport.ts with the canonical implementation
         (exportDeck, exportSingleChart, ChartSpec, DeckOptions types).
      2. Adds pptxgenjs to package.json dependencies.
      3. Rewrites any page that uses the old JSON-blob export stub pattern.
    """
    import re as _re
    import json as _json

    # ── Step 1: always inject the canonical pptxExport.ts ───────────────────
    # Only overwrite if the file doesn't exist OR is the old/stub version
    existing_pptx = files.get("src/utils/pptxExport.ts", "")
    if "exportDeck" not in existing_pptx or "addChartToSlide" not in existing_pptx:
        files["src/utils/pptxExport.ts"] = _CANONICAL_PPTX_EXPORT
        print("[_fix_pptx_export] injected canonical pptxExport.ts", flush=True)

    # ── Step 2: ensure pptxgenjs in package.json ────────────────────────────
    if "package.json" in files:
        try:
            pkg = _json.loads(files["package.json"])
            deps = pkg.setdefault("dependencies", {})
            if "pptxgenjs" not in deps:
                deps["pptxgenjs"] = "^4.0.0"
                files["package.json"] = _json.dumps(pkg, indent=2)
                print("[_fix_pptx_export] added pptxgenjs to package.json", flush=True)
        except Exception:
            pass

    # ── Step 2: rewrite JSON-blob export pattern in .tsx files ──────────────
    _JSON_BLOB_PAT = _re.compile(
        r"function\s+export\w*\([^)]*\)\s*\{[^}]*new Blob\(\[JSON\.stringify[^\}]+\}",
        _re.DOTALL
    )
    _IMPORT_PAT = _re.compile(r"^import\s+", _re.MULTILINE)

    for path, content in list(files.items()):
        if not path.endswith(".tsx"):
            continue
        # Only touch files that have the JSON blob export pattern AND reference slides/PPTX/templates
        has_blob = "new Blob" in content and "JSON.stringify" in content and "application/json" in content
        has_slides = any(k in content for k in (
            "slideTemplates", "exportSlides", "handleExport", "exportToPptx", "toPowerPoint", "template"
        ))
        if not (has_blob and has_slides):
            continue

        # Add pptxgenjs import if not already there
        if "pptxgenjs" not in content:
            # Insert after the last existing import line
            content = _re.sub(
                r"((?:import[^\n]+\n)+)",
                r"\1import PptxGenJS from 'pptxgenjs'\n",
                content, count=1
            )

        # Replace the export function body with a real pptxgenjs implementation
        _REAL_EXPORT = '''async function exportSlides(templateName: string) {
    const template = (typeof slideTemplates !== 'undefined' ? slideTemplates : []).find((t: any) => t.name === templateName)
    const accent = ((template?.primary ?? template?.accent ?? '#0064D2') as string).replace('#', '')
    const pptx = new PptxGenJS()
    pptx.layout = 'LAYOUT_WIDE'

    // Cover slide
    const cover = pptx.addSlide()
    cover.background = { color: '0D1B2A' }
    cover.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: '100%', h: 0.1, fill: { color: accent } })
    cover.addText(typeof projectTitle !== 'undefined' ? projectTitle : 'Report', { x: 0.6, y: 1.4, w: 8.8, h: 0.7, fontSize: 32, bold: true, color: 'FFFFFF', fontFace: 'Calibri' })
    cover.addText(templateName, { x: 0.6, y: 2.2, w: 8.8, h: 0.45, fontSize: 20, color: accent, fontFace: 'Calibri' })
    cover.addText(new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }), { x: 0.6, y: 2.8, w: 8.8, h: 0.3, fontSize: 12, color: '9CA3AF', fontFace: 'Calibri' })
    cover.addShape(pptx.ShapeType.rect, { x: 0, y: 5.3, w: '100%', h: 0.1, fill: { color: accent } })

    // Content slide from conversation
    const msgs = typeof messages !== 'undefined' ? messages : []
    msgs.filter((m: any) => (m.role === 'ai' || m.sender === 'ai') && m.text?.length > 20).forEach((m: any, idx: number) => {
      const sl = pptx.addSlide()
      sl.background = { color: 'FFFFFF' }
      sl.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: '100%', h: 0.1, fill: { color: accent } })
      sl.addText(`${idx + 1}`, { x: 9.1, y: 0.15, w: 0.5, h: 0.22, fontSize: 9, color: '9CA3AF', align: 'right', fontFace: 'Calibri' })
      sl.addText(m.text ?? '', { x: 0.4, y: 0.45, w: 9.2, h: 4.6, fontSize: 12, color: '132445', fontFace: 'Calibri', valign: 'top', breakLine: true, wrap: true })
      if (m.chart?.data?.length) {
        const chartData = [{ name: 'Value', labels: m.chart.data.map((d: any) => d.label), values: m.chart.data.map((d: any) => d.value) }]
        const chartColors = m.chart.data.map((d: any) => (d.color ?? '#0064D2').replace('#', ''))
        sl.addChart(m.chart.type === 'donut' ? pptx.ChartType.doughnut : pptx.ChartType.bar, chartData, { x: 5.2, y: 0.5, w: 4.2, h: 4.0, chartColors, showLegend: true, legendFontSize: 9, dataLabelFontSize: 9 })
      }
      sl.addShape(pptx.ShapeType.rect, { x: 0, y: 5.3, w: '100%', h: 0.1, fill: { color: accent } })
    })

    const filename = 'report-' + templateName.toLowerCase().replace(/[ ]+/g, '-') + '-' + new Date().toISOString().slice(0,10) + '.pptx'
    await pptx.writeFile({ fileName: filename })
    setToast?.('Exported: ' + filename)
    setTimeout(() => setToast?.(null), 3500)
  }'''

        # Replace the old JSON-blob export function.
        # Matches any of these patterns the LLM may generate:
        #   async function exportSlides(...)  { ... }
        #   async function handleExport(...)  { ... }
        #   const handleExport = async (...) => { ... }
        #   const exportSlides = async (...) => { ... }
        #   const handleExport = useCallback(async (...) => { ... }, [...])
        # Use a lambda so Python never interprets _REAL_EXPORT as a regex template.
        _FUNC_PATS = [
            r"(?:async\s+)?function\s+(?:export\w+|handleExport)\s*\([^)]*\)\s*\{.*?\n  \}",
            r"const\s+(?:export\w+|handleExport)\s*=\s*(?:useCallback\s*\()?\s*async\s*\([^)]*\)\s*=>\s*\{.*?\n  \}(?:\s*,\s*\[[^\]]*\]\s*\))?",
        ]
        new_content = content
        for pat in _FUNC_PATS:
            replaced = _re.sub(pat, lambda _: _REAL_EXPORT, new_content, count=1, flags=_re.DOTALL)
            if replaced != new_content:
                new_content = replaced
                break
        if new_content != content:
            files[path] = new_content
            print(f"[_fix_pptx_export] rewrote export function in {path}", flush=True)

    return files


def _fix_d3_chart_code(files: dict) -> dict:
    """
    Fix two systematic D3 bugs that appear in LLM-generated chart code and inline
    chart renderers (e.g. AI Concierge ChartView):

    1. INVALID CSS SELECTOR — `g.selectAll(`circle.${s.label}`)` or
       `g.selectAll(`circle.${series.label}`)` where the label value contains
       spaces, parentheses, $, %, (, ), etc. — these make CSS selectors that
       crash with "not a valid selector" at runtime.
       Fix: replace the pattern with a numbered class (`dot-series-N`) derived
       from the series index.

    2. UNSAFE d3.format() — `const fmt = d3.format(spec.valueFormat)` or
       `d3.format(cfg.valueFormat)` where valueFormat can be an arbitrary string
       like 'currency', '$,.0f', 'compact', etc.  d3.format() throws on unknown
       specifiers.
       Fix: wrap in the safeFormat helper that handles named aliases and catches
       d3.format() exceptions, falling back to ',.0f'.
    """
    import re as _re

    _SAFE_FORMAT_HELPER = '''// Safe D3 format — handles 'currency', 'compact', '$,.0f', etc. without crashing
function safeFormat(fmtStr: string | undefined): (v: number) => string {
  if (!fmtStr) return d3.format(',.0f')
  const lower = fmtStr.toLowerCase()
  if (lower === 'currency') return (v: number) => {
    const n = Number(v) || 0
    if (Math.abs(n) >= 1e9) return '$' + d3.format(',.1f')(n / 1e9) + 'B'
    if (Math.abs(n) >= 1e6) return '$' + d3.format(',.1f')(n / 1e6) + 'M'
    if (Math.abs(n) >= 1e3) return '$' + d3.format(',.1f')(n / 1e3) + 'K'
    return '$' + d3.format(',.0f')(n)
  }
  if (lower === 'compact' || lower === 'number') return (v: number) => {
    const n = Number(v) || 0
    if (Math.abs(n) >= 1e9) return d3.format(',.1f')(n / 1e9) + 'B'
    if (Math.abs(n) >= 1e6) return d3.format(',.1f')(n / 1e6) + 'M'
    if (Math.abs(n) >= 1e3) return d3.format(',.1f')(n / 1e3) + 'K'
    return d3.format(',.0f')(n)
  }
  try { return d3.format(fmtStr) } catch { return d3.format(',.0f') }
}'''

    for path, content in list(files.items()):
        if not path.endswith('.tsx'):
            continue
        if 'd3' not in content:
            continue

        changed = False

        # ── Fix 1: invalid CSS selector from label text ──────────────────────
        # Patterns:
        #   g.selectAll(`circle.${s.label}`)
        #   g.selectAll(`circle.${series.label}`)
        #   g.selectAll(`circle.${ser.label}`)
        #   g.selectAll(`circle.${s.name}`)
        # Replace with index-based class: `circle.dot-series-${si}`
        # The forEach loop var is typically (s, si) or (s, i) — we look for the
        # enclosing forEach and ensure an index parameter is available.
        _SELECTOR_PAT = _re.compile(
            r'\.selectAll\s*\(`circle\.\$\{[^}]+\}`\)',
            _re.DOTALL
        )
        if _SELECTOR_PAT.search(content):
            # Step 1a: ensure forEach callbacks include an index parameter
            # Match: .forEach((s) =>  or  .forEach((s, i) =>  etc.
            content = _re.sub(
                r'\.forEach\s*\(\s*\((\w+)\)\s*=>',
                r'.forEach((\1, _si) =>',
                content
            )
            # Step 1b: replace the bad selectAll
            content = _SELECTOR_PAT.sub('.selectAll(`circle.dot-series-${_si}`)', content)
            # Step 1c: ensure join('circle') sets the matching class
            # After the .attr('cx', ...) / .attr('cy', ...) / .attr('r', ...)
            # chain from the replaced selectAll, inject .attr('class', `dot-series-${_si}`)
            # We do this by finding .join('circle') after the fixed selectAll and adding the class attr
            content = _re.sub(
                r'(\.selectAll\(`circle\.dot-series-\$\{_si\}`\)[^;]+\.join\(\'circle\'\))',
                r"\1\n          .attr('class', `dot-series-${_si}`)",
                content
            )
            changed = True
            print(f"[_fix_d3_chart_code] fixed invalid CSS selector in {path}", flush=True)

        # ── Fix 2: unsafe d3.format() on user-supplied format string ─────────
        # Patterns to fix:
        #   const fmt = d3.format(spec.valueFormat)
        #   const fmt = spec.valueFormat ? d3.format(spec.valueFormat) : d3.format(',.0f')
        #   const fmt = d3.format(cfg.valueFormat)   (already has try/catch in Charts.skill via fmt())
        # Only fix the direct assignment patterns that have no try/catch protection
        _DIRECT_FORMAT_PAT = _re.compile(
            r'(const\s+\w+\s*=\s*)(?:[\w.]+\?\s*)?d3\.format\((?:spec|cfg|config)\.valueFormat\)(?:\s*:\s*d3\.format\([\'"][^"\']+[\'"]\))?'
        )
        if _DIRECT_FORMAT_PAT.search(content) and 'safeFormat' not in content:
            # Inject safeFormat helper before the component function that uses d3
            # Find first function/const that has d3 usage and insert before it
            insert_marker = _re.search(r'\nfunction ChartView', content)
            if not insert_marker:
                insert_marker = _re.search(r'\nexport default function', content)
            if insert_marker:
                content = content[:insert_marker.start()] + '\n' + _SAFE_FORMAT_HELPER + content[insert_marker.start():]

            # Replace the direct d3.format call with safeFormat
            content = _DIRECT_FORMAT_PAT.sub(r'\1safeFormat(\2.valueFormat ?? \3.valueFormat)', content)
            # Simpler targeted replacement — handle the exact patterns seen in concierge
            content = _re.sub(
                r'spec\.valueFormat \? d3\.format\(spec\.valueFormat\) : d3\.format\([\'"],.0f[\'"]\)',
                'safeFormat(spec.valueFormat)',
                content
            )
            content = _re.sub(
                r'd3\.format\(spec\.valueFormat\)',
                'safeFormat(spec.valueFormat)',
                content
            )
            content = _re.sub(
                r'd3\.format\(cfg\.valueFormat\)(?!\s*\))',  # not already inside try{}
                'safeFormat(cfg.valueFormat)',
                content
            )
            changed = True
            print(f"[_fix_d3_chart_code] wrapped d3.format with safeFormat in {path}", flush=True)

        if changed:
            files[path] = content

    return files


def _fix_ds_imports(files: dict) -> dict:
    """
    The LLM sometimes imports custom chart/map components from 'mobility-global-ds'
    (the design system) even though they don't exist there — causing a SyntaxError
    that crashes the entire page at runtime.

    Non-DS components the LLM hallucinates as DS exports:
      D3BarChart, D3LineChart, D3DonutChart, D3PieChart, D3AreaChart,
      WorldSalesMap, SalesMap, UsStatesMap, UsaMap,
      MultiLineChart, GroupedBarChart, StackedAreaChart,
      HorizontalBarChart, ForecastChart, VarianceBarChart, AgingInventoryChart

    Strategy: for any page/component that imports these from mobility-global-ds,
    rewrite the import to pull from '../components/<Name>' instead.
    If the page file is under src/components/, use './<Name>' instead.
    """
    import re as _re

    # Components that are NEVER in mobility-global-ds
    _NON_DS = {
        'D3BarChart', 'D3LineChart', 'D3DonutChart', 'D3PieChart', 'D3AreaChart',
        'WorldSalesMap', 'SalesMap', 'UsStatesMap', 'UsaMap', 'UsStateMap',
        'MultiLineChart', 'GroupedBarChart', 'StackedAreaChart',
        'HorizontalBarChart', 'ForecastChart', 'VarianceBarChart',
        'AgingInventoryChart', 'RevenueRegionBar', 'MakeDonut', 'RevenueTrendLine',
    }

    for path, content in list(files.items()):
        if not path.endswith('.tsx') and not path.endswith('.ts'):
            continue
        if 'mobility-global-ds' not in content:
            continue

        changed = False
        is_component = 'src/components/' in path

        # Find all: import { A, B, C } from 'mobility-global-ds'
        for m in _re.finditer(
            r"import\s+\{([^}]+)\}\s+from\s+'mobility-global-ds'",
            content
        ):
            imported = [x.strip() for x in m.group(1).split(',')]
            bad = [x for x in imported if x in _NON_DS]
            good = [x for x in imported if x not in _NON_DS]

            if not bad:
                continue

            changed = True
            prefix = '.' if is_component else '../components'

            # Rebuild: keep DS imports for valid components, add local imports for bad ones
            replacement = ''
            if good:
                replacement += f"import {{ {', '.join(good)} }} from 'mobility-global-ds'\n"
            for comp in bad:
                replacement += f"import {comp} from '{prefix}/{comp}'\n"

            content = content.replace(m.group(0), replacement.rstrip('\n'), 1)

        if changed:
            files[path] = content
            print(f"[_fix_ds_imports] fixed bad DS imports in {path}", flush=True)

    return files



# _fix_unescaped_quotes removed — replaced by centralized agents.sanitize_js module


def _fix_json_named_imports(files: dict) -> dict:
    """
    Fix the LLM's common mistake of using named imports from JSON files or
    importing from individual data modules instead of the barrel index.
    JSON files only have a default export in Vite — named imports crash at runtime.

    Rewrites imports AND renames all usages in the file body:
      import { forecastData } from '../data/forecast'  →  import { forecast } from '../data'
      + all references to forecastData become forecast
    """
    import re

    # Common LLM renames: forecastData->forecast, kpiData->kpis, etc.
    alias_map = {
        "forecastData": "forecast",
        "kpiData": "kpis",
        "kpisData": "kpis",
        "salesData": "globalSales",
        "globalSalesData": "globalSales",
        "stateSalesData": "stateSales",
        "inventoryData": "inventory",
    }

    for path in list(files.keys()):
        if not path.endswith((".tsx", ".ts")):
            continue
        if path.startswith("src/data/"):
            continue
        content = files[path]
        if not isinstance(content, str):
            continue

        changed = False
        lines = content.split("\n")
        renames: dict[str, str] = {}

        for i, line in enumerate(lines):
            # Match: import { ... } from '../data/somefile' or '../data/somefile.json'
            m = re.match(
                r"(import\s+\{)([^}]+)(\}\s+from\s+['\"])(\.\.?/data/\w+)(\.json)?(['\"])",
                line
            )
            if not m:
                continue

            prefix = m.group(1)
            names_str = m.group(2)
            mid = m.group(3)
            data_path = m.group(4)
            quote = m.group(6)

            base_path = data_path.rsplit("/", 1)[0]  # '../data' or './data'

            names = [n.strip() for n in names_str.split(",")]
            fixed_names = []
            for n in names:
                real_name = alias_map.get(n, n)
                if real_name != n:
                    renames[n] = real_name
                fixed_names.append(real_name)

            new_line = f"{prefix} {', '.join(fixed_names)} {mid}{base_path}{quote}"
            if new_line != line:
                lines[i] = new_line
                changed = True

        if changed:
            content = "\n".join(lines)

        # Rename all usages in the file body for any aliased imports
        for old_name, new_name in renames.items():
            if old_name in content:
                content = re.sub(r"\b" + re.escape(old_name) + r"\b", new_name, content)
                changed = True

        # Also do a global pass for alias_map names even if not caught by import rewriting
        # (the LLM might use forecastData without importing it from a data submodule) —
        # but only for legacy static-JSON pages. API-first pages legitimately declare a
        # local variable with these exact names from a live useApi() call (e.g.
        # `const { data: salesData } = useApi('sales')`), and this pass has no way to
        # tell that apart from the JSON-import mistake it's meant to catch — it would
        # rename that local variable out from under the destructuring that just declared it.
        if "useApi(" not in content:
            for old_name, new_name in alias_map.items():
                if old_name in content:
                    content = re.sub(r"\b" + re.escape(old_name) + r"\b", new_name, content)
                    changed = True

        if changed:
            files[path] = content

    return files


def _fix_data_index(files: dict) -> dict:
    """
    Fix a common LLM mistake in src/data/index.ts where it imports a JSON file
    with the same name as the re-export constant, causing a redeclaration error.

    Bad:  import vehicleSales from './vehicleSales.json'
          export const vehicleSales = vehicleSales as VehicleSale[]

    Fixed: import vehicleSalesRaw from './vehicleSales.json'
           export const vehicleSales = vehicleSalesRaw as VehicleSale[]
    """
    import re as _re
    key = "src/data/index.ts"
    if key not in files:
        return files
    src = files[key]
    # Find all default imports from json files and check if the same name is re-exported
    # Pattern: import FOO from './FOO.json'  followed later by  export const FOO = FOO as ...
    import_pattern = _re.compile(r"^import (\w+) from '\.\/(\w+)\.json'", _re.MULTILINE)
    changed = False
    for m in import_pattern.finditer(src):
        var = m.group(1)
        # Check if there's a redeclaration: export const <var> = <var>
        if _re.search(r"export const " + var + r"\s*=\s*" + var + r"\b", src):
            raw = var + "Raw"
            src = src.replace(f"import {var} from", f"import {raw} from", 1)
            src = _re.sub(r"(export const " + var + r"\s*=\s*)" + var + r"\b", r"\g<1>" + raw, src)
            changed = True
    if changed:
        files[key] = src
    return files


def _inject_vite_server(cfg: str, project_name: str, port: int) -> str:
    """Patch a vite.config.ts string to add base + server block for the FastAPI proxy.
    _patch_vite_for_ds now produces a multi-line config ending with })\n — inject before it.
    """
    import re as _re
    from agents.uigen_agent import _DS_CLEAN_JUNCTION, _SHARED_NM_JUNCTION
    base = "/app/" + project_name + "/"
    fs_allow = "['..', '" + _DS_CLEAN_JUNCTION + "', '" + _SHARED_NM_JUNCTION + "']"
    server_block = (
        "  base: '" + base + "',\n"
        "  server: {\n"
        "    port: " + str(port) + ",\n"
        "    host: '0.0.0.0',\n"
        "    hmr: false,\n"
        "    allowedHosts: ['localhost'],\n"
        "    fs: { allow: " + fs_allow + " },\n"
        "  },\n"
    )

    # Already has base+server — update port, base, and ensure fs.allow is present
    if "base:" in cfg and "server:" in cfg:
        cfg = _re.sub(r"base:\s*'[^']*'", "base: '" + base + "'", cfg, count=1)
        cfg = _re.sub(r"port:\s*\d+", "port: " + str(port), cfg, count=1)
        if _SHARED_NM_JUNCTION not in cfg:
            if "fs:" in cfg:
                # Update existing fs.allow to include both junctions
                cfg = _re.sub(r"fs:\s*\{[^}]*\}", "fs: { allow: " + fs_allow + " }", cfg, count=1)
            else:
                cfg = cfg.replace(
                    "    allowedHosts:",
                    "    fs: { allow: " + fs_allow + " },\n    allowedHosts:",
                    1,
                )
        return cfg

    # Multi-line form from _patch_vite_for_ds: inject before closing })
    if "})\n" in cfg:
        return cfg.replace("})\n", server_block + "})\n", 1)

    # Single-line fallback (LLM-generated)
    return _re.sub(
        r"defineConfig\(\{",
        "defineConfig({ base: '" + base + "', server: { port: " + str(port) + ", host: '0.0.0.0', hmr: false, allowedHosts: ['localhost'], fs: { allow: " + fs_allow + " } },",
        cfg, count=1,
    )


def _fix_main_tsx(files: dict, project_name: str) -> dict:
    """
    Replace src/main.tsx with the canonical boilerplate that:
    - Uses import.meta.env.BASE_URL as the BrowserRouter basename (set by Vite's `base` config)
    - Enables React Router v7 future flags to silence deprecation warnings
    This ensures routes always resolve correctly regardless of the sub-path the app is served under.
    """
    files["src/main.tsx"] = (
        "import React from 'react'\n"
        "import ReactDOM from 'react-dom/client'\n"
        "import { BrowserRouter } from 'react-router-dom'\n"
        "import App from './App'\n"
        "import './index.css'\n"
        "\n"
        "const BASE = import.meta.env.BASE_URL.replace(/\\/$/, '') || ''\n"
        "\n"
        "ReactDOM.createRoot(document.getElementById('root')!).render(\n"
        "  <React.StrictMode>\n"
        "    <BrowserRouter basename={BASE} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>\n"
        "      <App />\n"
        "    </BrowserRouter>\n"
        "  </React.StrictMode>\n"
        ")\n"
    )
    return files


def _fix_custom_components(files: dict) -> dict:
    """
    Fix three systematic issues with LLM-generated custom components that shadow or
    conflict with the Design System:

    1. DEFAULT-EXPORT / NAMED-IMPORT MISMATCH
       LLM generates:  export default function Card(...)
       Pages import:   import { Card } from '../components/Card'
       Fix: add a named re-export alongside the default so both work.

    2. MAP COMPONENT PROP CRASH — undefined.forEach
       LLM types props as required arrays (sales: StateSale[]) but pages may pass
       undefined; the component crashes immediately in useMemo.
       Fix: add a defensive `?? []` guard at the top of map components.

    3. DATATABLE / TABS / DROPDOWN PROP MISMATCH
       LLM generates custom versions with prop names like `data` (not `rows`) or
       `tabs` (not `items`). Pages call them with DS-style props.
       Fix: add prop aliases so both calling conventions work.
    """
    import re as _re

    for path, content in list(files.items()):
        if not path.endswith(".tsx"):
            continue
        changed = False
        fname = path.split("/")[-1].replace(".tsx", "")

        # ── Fix 1: add named export alongside default export ─────────────────
        # Matches:  export default function Foo(  OR  export default function Foo<
        # and adds: export { Foo } at the end if it doesn't already have one.
        default_fn_match = _re.search(
            r"export\s+default\s+function\s+(\w+)\s*[\(<]", content
        )
        if default_fn_match:
            fn_name = default_fn_match.group(1)
            # Only add if there's no named export of the same symbol already
            named_export_exists = bool(_re.search(
                r"export\s*\{[^}]*\b" + fn_name + r"\b[^}]*\}", content
            ))
            if not named_export_exists:
                # Append named re-export at end of file
                content = content.rstrip() + f"\nexport {{ {fn_name} }}\n"
                changed = True

        # ── Fix 2: map component prop defaults (undefined crash guard) ────────
        is_map_component = (
            ("UsStatesMap" in fname or "UsaSalesMap" in fname or "SalesMap" in fname)
            and "World" not in fname
        ) or "WorldSalesMap" in fname

        if is_map_component:
            # Pattern: function Foo({ sales, ... }: Props) — add = [] default
            # Guards for 'sales: StateSale[]' typed required prop
            for prop_name in ("sales", "data", "stateSales"):
                # Replace `{ sales,` or `{ sales }` with `{ sales = [],`
                patched = _re.sub(
                    r"(\{\s*" + prop_name + r")\s*([,}])",
                    r"\1 = []" + r"\2",
                    content,
                    count=1
                )
                if patched != content:
                    content = patched
                    changed = True
                    break  # only patch the first matching prop name

        # ── Fix 3: DataTable — accept both `rows` and `data` prop names ─────────
        if fname == "DataTable":
            # The LLM uses either `data` or `rows`; pages call it either way.
            # Make the interface and destructuring accept both, then unify to `items`.
            if "const items" not in content and "items: T[]" not in content:
                has_data_prop = bool(_re.search(r"\bdata\s*[?:]", content))
                has_rows_prop = bool(_re.search(r"\brows\s*[?:]", content))
                if has_data_prop or has_rows_prop:
                    # Step 1: make both optional in Props interface
                    content = _re.sub(r"\brows\s*:\s*T\[\]", "rows?: T[]", content, count=1)
                    content = _re.sub(r"\bdata\s*:\s*T\[\]", "data?: T[]", content, count=1)
                    # Step 2: ensure both props exist in the interface
                    if "data?" not in content:
                        content = _re.sub(r"(\brows\??\s*:\s*T\[\])", r"\1\n  data?: T[]", content, count=1)
                    if "rows?" not in content:
                        content = _re.sub(r"(\bdata\??\s*:\s*T\[\])", r"\1\n  rows?: T[]", content, count=1)
                    # Step 3: ensure both props are in the function destructuring
                    has_data_destruct = bool(_re.search(r"DataTable<T>\(\{[^}]*\bdata\b", content))
                    has_rows_destruct = bool(_re.search(r"DataTable<T>\(\{[^}]*\brows\b", content))
                    if has_data_destruct and not has_rows_destruct:
                        content = _re.sub(
                            r"(export default function DataTable<T>\(\{[^}]*\bdata)\b",
                            r"\1, rows",
                            content, count=1
                        )
                    elif has_rows_destruct and not has_data_destruct:
                        content = _re.sub(
                            r"(export default function DataTable<T>\(\{[^}]*\brows)\b",
                            r"\1, data",
                            content, count=1
                        )
                    # Step 4: inject items alias after the opening brace
                    content = _re.sub(
                        r"(export default function DataTable<T>\([^)]+\)\s*\{)",
                        r"\1\n  const items: T[] = rows ?? data ?? []",
                        content, count=1
                    )
                    # Step 5: replace bare `rows`/`data` usages in body with `items`
                    content = _re.sub(
                        r"(?<!\w)(rows|data)(?=\.map|\.filter|\.sort|\.find|\.length|\[)",
                        "items", content
                    )
                    # Step 6: fix useMemo deps and make rowKey accept string or function
                    content = _re.sub(r"\[(rows|data),\s*sort", "[items, sort", content)
                    # rowKey may be a string (key name) or a function — handle both
                    content = _re.sub(
                        r"rowKey\s*\?\s*rowKey\(row\)\s*:\s*String\(i\)",
                        "rowKey ? (typeof rowKey === 'function' ? rowKey(row) : String((row as any)[rowKey])) : String(i)",
                        content
                    )
                    content = content.replace(
                        "rowKey(row)",
                        "typeof rowKey === 'function' ? rowKey(row) : String((row as any)[rowKey!])"
                    )
                    # Make rowKey prop optional and accept string | function
                    content = _re.sub(
                        r"\browKey\s*:\s*\(row:\s*T\)\s*=>\s*string",
                        "rowKey?: ((row: T) => string) | string",
                        content
                    )
                    changed = True

        # ── Fix 3b: Tabs — accept both string[] and {id,label}[] ──────────────
        if fname == "Tabs":
            if "typeof t === 'string'" not in content:
                # Widen the type and make the renderer dual-mode
                content = _re.sub(r"\btabs\s*:\s*string\[\]", "tabs: (string | { id: string; label: string })[]", content)
                content = _re.sub(
                    r"\{[^}]*\.map\(\s*\(t(?:,\s*i)?\)\s*=>",
                    lambda m: m.group(0),  # leave map call intact; fix body below
                    content
                )
                # Replace `{t}` or `>{t}<` (the tab label render) with dual-mode
                content = _re.sub(
                    r"(?<!['\"])\{t\}(?!['\"])",
                    "{typeof t === 'string' ? t : t.label}",
                    content
                )
                # Replace `key={t}` with dual-mode key
                content = _re.sub(r"key=\{t\}", "key={typeof t === 'string' ? t : t.id}", content)
                changed = True

        # ── Fix 3c: Dropdown — accept both string[] and {value,label}[] ─────
        # LLM generates options: { value: string; label: string }[] but callers
        # pass plain string[] (MAKES, SCENARIOS, etc.) → options render blank.
        if fname == "Dropdown":
            if "{ value: string; label: string }[]" in content and "type Option" not in content:
                content = content.replace(
                    "{ value: string; label: string }[]",
                    "Option[]"
                )
                # Inject type alias before the interface/function
                content = _re.sub(
                    r"(interface Props|^export default function Dropdown)",
                    "type Option = string | { value: string; label: string }\n\n\\1",
                    content, count=1, flags=_re.MULTILINE
                )
                # Fix the options.map render to handle both forms
                content = _re.sub(
                    r"options\.map\(\s*\(o\)\s*=>\s*\(\s*<option[^>]*key=\{o\.value\}[^>]*value=\{o\.value\}[^>]*>\{o\.label\}<\/option>\s*\)\s*\)",
                    "options.map((o) => { const v = typeof o === 'string' ? o : o.value; const l = typeof o === 'string' ? o : o.label; return <option key={v} value={v}>{l}</option> })",
                    content
                )
                # Simpler fallback for other map patterns
                if "typeof o === 'string'" not in content:
                    content = _re.sub(
                        r"\{options\.map\(([^)]+)\)\s*=>\s*\(\s*<option[^/]*/>\s*\)\s*\}",
                        lambda m: m.group(0),  # leave alone if pattern differs
                        content
                    )
                    content = content.replace(
                        "{options.map((o) => (\n          <option key={o.value} value={o.value}>{o.label}</option>\n        ))}",
                        "{options.map((o) => { const v = typeof o === 'string' ? o : o.value; const l = typeof o === 'string' ? o : o.label; return <option key={v} value={v}>{l}</option> })}"
                    )
                changed = True

        # ── Fix 4: Badge — accept optional color and bg inline style props ─────
        # Pages call <Badge color="#..." bg="#..."> but generated Badge only takes
        # a `variant` string, so custom colours are silently ignored.
        if fname == "Badge":
            if "color?" not in content and "bg?" not in content:
                # Add color and bg to props interface
                content = _re.sub(
                    r"(\bvariant\??\s*:\s*\w+)",
                    r"\1; color?: string; bg?: string",
                    content, count=1
                )
                # Add to destructuring (after variant)
                content = _re.sub(
                    r"(\{\s*variant\b[^}]*?\})",
                    lambda m: m.group(0).replace("}", ", color, bg }") if ", color" not in m.group(0) else m.group(0),
                    content, count=1
                )
                # Apply inline style override on the root span/element
                if "style={{" not in content:
                    content = _re.sub(
                        r"(<span\b[^>]*className[^>]*>)",
                        r'\1',  # placeholder — real injection below
                        content, count=1
                    )
                    content = _re.sub(
                        r"(return\s*\(\s*<span\b)([^>]*>)",
                        r"\1\2",
                        content, count=1
                    )
                    # Add style prop to outermost span
                    content = _re.sub(
                        r"(<span\b)([^>]*className=\{[^}]+\})([^>]*>)",
                        r"\1\2 style={{ ...(color ? { color } : {}), ...(bg ? { background: bg } : {}) }}\3",
                        content, count=1
                    )
                changed = True

        if changed:
            files[path] = content
            comp = path.split("/")[-1]
            print(f"[_fix_custom_components] patched {comp}", flush=True)

    # ── Fix 5: GroupedBarChart prop name — groups= → data= ──────────────────
    # LLM sometimes passes groups={...} instead of data={...} to GroupedBarChart.
    for path, content in list(files.items()):
        if not path.endswith(".tsx"):
            continue
        if "GroupedBarChart" not in content:
            continue
        patched = _re.sub(
            r'(<GroupedBarChart\b[^>]*?)\bgroups\s*=\s*(\{[^}]+\})',
            r'\1data=\2',
            content
        )
        if patched != content:
            files[path] = patched
            print(f"[_fix_custom_components] fixed GroupedBarChart groups→data in {path}", flush=True)

    # ── Fix 6: NorthAmerica / UsStateMap drill-down scrollIntoView ───────────
    # Pages that have selectedState + UsStateMap drill-down panel but no
    # scrollIntoView call won't auto-scroll to the panel on state click.
    for path, content in list(files.items()):
        if not path.endswith(".tsx"):
            continue
        if "UsStateMap" not in content or "selectedState" not in content:
            continue
        if "scrollIntoView" in content:
            continue
        # Need useRef + useEffect for scroll — ensure they're imported
        if "useRef" not in content:
            content = _re.sub(
                r"(import \{[^}]+)\}\s*from\s*'react'",
                lambda m: m.group(0).replace("}", ", useRef, useEffect }").replace(
                    "useRef, useEffect , useRef, useEffect", "useRef, useEffect"
                ).replace("useEffect , useRef", "useRef, useEffect"),
                content, count=1
            )
        elif "useEffect" not in content:
            content = _re.sub(
                r"(import \{[^}]+)\}\s*from\s*'react'",
                lambda m: m.group(0).replace("}", ", useEffect }"),
                content, count=1
            )
        # Inject drillRef declaration after the selectedState useState line
        if "drillRef" not in content:
            content = _re.sub(
                r"(const \[selectedState,\s*setSelectedState\][^\n]+\n)",
                r"\1  const drillRef = useRef<HTMLDivElement>(null)\n"
                r"  useEffect(() => {\n"
                r"    if (selectedState && drillRef.current)\n"
                r"      drillRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' })\n"
                r"  }, [selectedState])\n",
                content, count=1
            )
            # Attach ref to the drill-down panel div (first div after selectedState && )
            content = _re.sub(
                r'(\{selectedState &&[^(]*\([^)]*\) *\{[^}]*return \(\s*<div)(\s+className="[^"]*bg-white[^"]*")',
                r'\1 ref={drillRef}\2',
                content, count=1
            )
        files[path] = content
        print(f"[_fix_custom_components] injected scrollIntoView drill-down in {path}", flush=True)

    # ── Fix 7: FilterDropdown — accept both string[] and {label,value}[] options ─
    # GlobalMap passes {label,value}[] but FilterDropdown only handles string[].
    for path, content in list(files.items()):
        if not path.endswith(".tsx"):
            continue
        fname = path.split("/")[-1].replace(".tsx", "")
        if fname != "FilterDropdown":
            continue
        if "typeof o === 'string'" in content:
            continue  # already dual-mode
        # Replace the options.map with a dual-mode renderer
        patched = _re.sub(
            r"options\.map\s*\(\s*\(o\)\s*=>\s*\([^)]*<option[^>]*>[^<]*</option>[^)]*\)\s*\)",
            "options.map((o) => { const v = typeof o === 'string' ? o : (o as any).value; const l = typeof o === 'string' ? o : (o as any).label; return <option key={v} value={v}>{l}</option> })",
            content
        )
        # Also widen the type annotation so TS doesn't complain
        patched = _re.sub(r"\boptions\s*:\s*string\[\]", "options: (string | { value: string; label: string })[]", patched)
        if patched != content:
            files[path] = patched
            print(f"[_fix_custom_components] made FilterDropdown accept objects in {path}", flush=True)

    # ── Fix 9: D3GroupedBar groupKeys → series/groupKey ─────────────────────────
    # Analytics passes groupKeys={QUARTERS} but D3GroupedBar expects groupKey (string) + series.
    # When a page calls <D3GroupedBar groupKeys={arr}> with no series prop, inject a series
    # derived from the array, or at minimum remove groupKeys to prevent a crash.
    for path, content in list(files.items()):
        if not path.endswith(".tsx"):
            continue
        if "D3GroupedBar" not in content or "groupKeys=" not in content:
            continue
        # If series prop is also present, just rename groupKeys to something harmless via removal
        if "series=" in content:
            patched = _re.sub(r'\bgroupKeys=\{[^}]+\}\s*', '', content)
        else:
            # Replace groupKeys={QUARTERS} with series auto-derived inline
            patched = _re.sub(
                r'\bgroupKeys=\{([^}]+)\}',
                r'series={(\1 as string[]).map((k, i) => ({ name: k, color: ["#0064D2","#420E71","#059669","#D97706"][i % 4] }))}',
                content
            )
        if patched != content:
            files[path] = patched
            print(f"[_fix_custom_components] fixed D3GroupedBar groupKeys in {path}", flush=True)

    # ── Fix 8: SalesMap import — normalize all variant names to match actual file ─
    # The LLM generates various names: SalesMap, UsaSalesMap, UsaSalesMap, USSalesMap.
    # Detect which USA map file actually exists in the project, then fix all imports.
    usa_map_files = [p for p in files if p.endswith(".tsx") and
                     any(n in p.split("/")[-1] for n in ("UsaSalesMap", "USSalesMap", "UsStateMap", "UsStateSalesMap"))]
    # Pick the canonical name from the actual component file
    _canonical_usa_map = None
    if usa_map_files:
        _canonical_usa_map = usa_map_files[0].split("/")[-1].replace(".tsx", "")

    for path, content in list(files.items()):
        if not path.endswith(".tsx"):
            continue
        patched = content
        # Fix bare 'SalesMap' (no US prefix) → canonical name
        if "from '../components/SalesMap'" in patched or "from './SalesMap'" in patched:
            target = _canonical_usa_map or "UsaSalesMap"
            patched = patched.replace("from '../components/SalesMap'", f"from '../components/{target}'")
            patched = patched.replace("from './SalesMap'", f"from './{target}'")
            patched = _re.sub(r"\bimport SalesMap from", f"import {target} from", patched)
            patched = _re.sub(r"\bSalesMap\b(?=\s+|/>|>)", target, patched)
        # Fix mismatched variant (e.g. page imports UsaSalesMap but file is USSalesMap)
        if _canonical_usa_map:
            for wrong_name in ("UsaSalesMap", "USSalesMap", "UsStateMap", "UsStateSalesMap"):
                if wrong_name == _canonical_usa_map:
                    continue
                if f"from '../components/{wrong_name}'" in patched:
                    patched = patched.replace(f"from '../components/{wrong_name}'", f"from '../components/{_canonical_usa_map}'")
                    patched = _re.sub(rf"\bimport {wrong_name} from", f"import {_canonical_usa_map} from", patched)
                    patched = _re.sub(rf"\b{wrong_name}\b(?=\s+|/>|>|{{)", _canonical_usa_map, patched)
        if patched != content:
            files[path] = patched
            print(f"[_fix_custom_components] normalized USA map import in {path}", flush=True)

    # ── Fix 10: D3GroupedBar — fix callers using wrong props ─────────────────────
    # LLM pages call D3GroupedBar with various wrong prop combos:
    #   groups={...}  instead of  series={...}  (wrong prop name)
    #   data.group/values shape  instead of  flat {[groupKey]: str, [seriesKey]: n}
    # Also fix missing groupKey by inferring it from the data shape.
    for path, content in list(files.items()):
        if not path.endswith(".tsx") or "D3GroupedBar" not in content:
            continue
        patched = content
        # groups= → series=  (wrong prop name, D3GroupedBar uses series not groups)
        patched = _re.sub(r'\bgroups=(\{[^}]+\})', r'series=\1', patched)
        # groupKeys= with no series → already handled by Fix 9 above; skip if series present
        if patched != content:
            files[path] = patched
            print(f"[_fix_custom_components] fixed D3GroupedBar groups→series in {path}", flush=True)

    # ── Fix 11: D3StackedArea — ensure xKey prop is present ──────────────────────
    # D3StackedArea requires xKey to know which field is the x-axis label.
    # LLM often omits it; detect the data's label field and inject xKey.
    for path, content in list(files.items()):
        if not path.endswith(".tsx") or "D3StackedArea" not in content:
            continue
        patched = content
        # Find <D3StackedArea ...> tags that have no xKey= prop
        def _inject_xkey(m: "_re.Match") -> str:
            tag = m.group(0)
            if "xKey=" in tag:
                return tag
            # Try to detect xKey from data= or data variable name patterns
            # If data has a "label" field → xKey="label"; else "x"
            xkey = "label" if '"label"' in tag or "'label'" in tag else "x"
            # Also check if data variable is nearby and has 'label:' in its definition
            return tag.replace("<D3StackedArea", f'<D3StackedArea xKey="{xkey}"', 1)
        patched = _re.sub(r"<D3StackedArea\b[^>]*/?>", _inject_xkey, patched, flags=_re.DOTALL)
        if patched != content:
            files[path] = patched
            print(f"[_fix_custom_components] injected xKey into D3StackedArea in {path}", flush=True)

    # ── Fix 12: Tabs active= string → number index ────────────────────────────────
    # When Tabs component expects active: number but page passes active={tab} where
    # tab is a string (tab id), the wrong tab is always highlighted.
    # Detect pattern and insert a TAB_IDS array + index lookup.
    for path, content in list(files.items()):
        if not path.endswith(".tsx") or "D3" not in content:
            continue  # only analytics-style pages need this
        fname = path.split("/")[-1]
        if fname not in ("Analytics.tsx", "Forecast.tsx", "Dashboard.tsx"):
            continue
        if "Tabs" not in content:
            continue
        # Check if Tabs is called with active={tab} where tab is a string state variable
        # and onChange={setTab} (which is a string setter)
        if _re.search(r"<Tabs\b[^>]*\bactive=\{tab\}", content) and \
           _re.search(r"\bconst \[tab,\s*setTab\]\s*=\s*useState\s*\(\s*'", content):
            # Extract tab ids from the tabs array literal in this file
            tab_ids_match = _re.findall(r"id:\s*'([^']+)'", content)
            if tab_ids_match and "TAB_IDS" not in content:
                ids_str = ", ".join(f"'{t}'" for t in tab_ids_match)
                # Inject TAB_IDS constant before the return statement
                content = _re.sub(
                    r"(  return\s*\()",
                    f"  const TAB_IDS = [{ids_str}]\n\n  \\1",
                    content, count=1
                )
                # Fix active prop
                content = content.replace("active={tab}", "active={TAB_IDS.indexOf(tab)}")
                # Fix onChange prop — setTab receives an index, need to map back
                content = content.replace("onChange={setTab}", "onChange={(i) => setTab(TAB_IDS[i] ?? tab)}")
                files[path] = content
                print(f"[_fix_custom_components] fixed Tabs active string→index in {path}", flush=True)

    # ── Fix 13: PersonaCard selected= → active= ───────────────────────────────────
    # LLM pages use selected={...} but PersonaCard component uses active prop.
    for path, content in list(files.items()):
        if not path.endswith(".tsx") or "PersonaCard" not in content:
            continue
        patched = _re.sub(r'\bselected=(\{[^}]+\})(?=[^>]*(?:/>|PersonaCard))', r'active=\1', content)
        # Also handle selected={expr} immediately on PersonaCard JSX tag
        patched = _re.sub(
            r'(<PersonaCard\b[^>]*?)\bselected=(\{[^}]+\})',
            r'\1active=\2',
            patched, flags=_re.DOTALL
        )
        if patched != content:
            files[path] = patched
            print(f"[_fix_custom_components] fixed PersonaCard selected→active in {path}", flush=True)

    return files


def _fix_unquoted_object_keys(files: dict) -> dict:
    """Fix object keys that contain spaces but aren't quoted.

    LLMs sometimes generate: { white pearl: '#F8FAFC', midnight blue: '#1E3A5F' }
    This must be:             { 'white pearl': '#F8FAFC', 'midnight blue': '#1E3A5F' }
    """
    import re as _re
    # Reserved words that can legitimately precede a bare identifier + colon in real
    # TypeScript (e.g. `const m: Record<...>`, `let x: string`) — never a real
    # object-literal key. Without this exclusion, the pattern below also matches
    # `useMemo(() => {\n  const m: Record<...>` (the `{` opens a function body, not
    # an object literal) and corrupts it into `{'const m': Record<...>`, silently
    # breaking any file it touches, changed or not — this bit real users twice.
    _JS_KEYWORDS = {
        "const", "let", "var", "function", "return", "if", "else", "for", "while",
        "switch", "case", "default", "class", "interface", "type", "enum",
        "export", "import", "new", "typeof", "in", "of", "extends", "implements",
        "async", "await", "yield", "try", "catch", "finally", "throw", "do",
        "public", "private", "protected", "readonly", "static", "abstract",
    }
    pattern = _re.compile(
        r"([{,]\s*)"                    # capture the { or , plus whitespace
        r"([a-zA-Z][a-zA-Z0-9]* "      # start: word char + space (signals multi-word key)
        r"[a-zA-Z][a-zA-Z0-9 ]*)"      # rest of multi-word key
        r"(\s*:\s*)"                    # colon separator
    )

    def _quote_if_safe(m: _re.Match) -> str:
        first_word = m.group(2).split(" ", 1)[0].lower()
        if first_word in _JS_KEYWORDS:
            return m.group(0)
        return f"{m.group(1)}'{m.group(2)}'{m.group(3)}"

    for path, content in list(files.items()):
        if not (path.endswith(".tsx") or path.endswith(".ts")):
            continue
        patched = pattern.sub(_quote_if_safe, content)
        if patched != content:
            files[path] = patched
            print(f"[_fix_unquoted_object_keys] quoted multi-word keys in {path}", flush=True)
    return files


def _fix_resize_observer_refs(files: dict) -> dict:
    """Fix undefined variable references in ResizeObserver callbacks.

    LLMs sometimes use a variable name (e.g. svgRect) that was never declared,
    when the actual element reference is assigned to a different variable.
    Pattern: const el = ref.current; ... observer callback uses `svgRect` or similar.
    Fix: replace undeclared refs with the correct element variable from the enclosing scope.
    """
    import re as _re
    ro_block_pattern = _re.compile(
        r"(const\s+(\w+)\s*=\s*\w+Ref\.current[^;]*;)"   # const el = someRef.current
        r"(.*?)"                                            # body between
        r"(new\s+ResizeObserver\s*\(\s*(?:\([^)]*\)|entries)\s*=>\s*\{)"  # new ResizeObserver((...) => {
        r"(.*?)"                                            # observer body
        r"(\}\s*\))",                                       # closing })
        _re.DOTALL
    )
    for path, content in list(files.items()):
        if not path.endswith(".tsx"):
            continue
        if "ResizeObserver" not in content:
            continue

        patched = content
        for match in ro_block_pattern.finditer(content):
            el_var = match.group(2)
            observer_body = match.group(5)
            # Look for <identifier>.parentElement or <identifier>.clientWidth
            # where <identifier> is NOT the el_var and NOT a known global
            ref_pattern = _re.compile(r"\b([a-zA-Z_]\w*)\.(parentElement|clientWidth|clientHeight|getBoundingClientRect)\b")
            for ref_match in ref_pattern.finditer(observer_body):
                used_var = ref_match.group(1)
                if used_var == el_var:
                    continue
                if used_var in ("window", "document", "this", "entries", "entry", "Math", "console"):
                    continue
                # Check if this variable is declared anywhere in the observer body
                decl_pattern = _re.compile(r"\b(?:const|let|var)\s+" + _re.escape(used_var) + r"\b")
                if decl_pattern.search(observer_body):
                    continue
                # Also check the block between el declaration and observer
                between_block = match.group(3)
                if decl_pattern.search(between_block):
                    continue
                # This is likely an undefined ref — replace with el_var
                patched = patched.replace(
                    f"{used_var}.{ref_match.group(2)}",
                    f"{el_var}.{ref_match.group(2)}"
                )
                print(f"[_fix_resize_observer_refs] replaced {used_var}→{el_var} in {path}", flush=True)

        if patched != content:
            files[path] = patched
    return files


def _fix_resize_observer_setdims(files: dict) -> dict:
    """Fix infinite-loop caused by ResizeObserver + setDims creating new objects every call.

    Pattern: setDims({ w, h: ... }) inside a measure/ResizeObserver callback always creates
    a new object reference, triggering re-renders even when dimensions haven't changed.
    The D3 effect re-draws, changing element size, firing the observer again → infinite loop.

    Fix: replace setDims({ w, h }) with setDims(prev => ...) that returns the same ref
    when values haven't changed.
    """
    import re as _re
    # Match: setDims({ w, h: <expr> }) or setDims({ w: <expr>, h: <expr> })
    pattern = _re.compile(
        r"setDims\(\s*\{\s*"
        r"(w(?:\s*:\s*[^,}]+)?)\s*,\s*"
        r"(h\s*:\s*[^}]+)"
        r"\s*\}\s*\)"
    )
    for path_key, content in list(files.items()):
        if not path_key.endswith(".tsx"):
            continue
        if "ResizeObserver" not in content or "setDims" not in content:
            continue

        patched = content
        for match in pattern.finditer(content):
            original = match.group(0)
            w_part = match.group(1).strip()
            h_part = match.group(2).strip()

            # Extract the value expressions
            if ":" in w_part:
                w_expr = w_part.split(":", 1)[1].strip()
            else:
                w_expr = "w"
            h_expr = h_part.split(":", 1)[1].strip()

            replacement = (
                f"setDims(prev => {{ const _w = {w_expr}; const _h = {h_expr}; "
                f"return (prev.w === _w && prev.h === _h) ? prev : {{ w: _w, h: _h }} }})"
            )
            patched = patched.replace(original, replacement, 1)

        if patched != content:
            files[path_key] = patched
            print(f"[_fix_resize_observer_setdims] fixed infinite-loop setDims in {path_key}", flush=True)
    return files


def _typecheck_and_autofix(project_dir, progress_fn):
    """Check tsc --noEmit once, attempt one round of auto-fixes if needed, done.

    This catches errors BEFORE the user sees a broken app. Fixes patterns like:
    - Unused imports/variables (auto-removable)
    - useApi<T[]> double-generic (already caught by post-processor but might reappear)
    - Missing module declarations (add @ts-nocheck as last resort)

    Deliberately does NOT re-run tsc to verify the fix and loop again (it used to,
    up to 3 total tsc invocations) — each re-check is a full subprocess spawn plus,
    on failure, more LLM-driven fixes, and this step already runs after every file
    is generated and written to disk. QA-heal (browser-based, later in the pipeline)
    catches anything a fix here didn't fully resolve, so paying for verification
    twice was pure latency with no reliability benefit.
    """
    import subprocess, re as _re
    from pathlib import Path
    from agents.uigen_agent import NODE_PATH

    # Invoke tsc's JS entry point directly via node.exe rather than the node_modules/.bin
    # shim — on Windows, the extensionless `.bin/tsc` file is a Unix shell script (not a
    # native Win32 binary), so subprocess.run([tsc_bin, ...]) fails with
    # "OSError: [WinError 193] %1 is not a valid Win32 application". Direct-node invocation
    # is the same pattern uigen_agent.py already uses for npm/vite.
    tsc_js = project_dir / "node_modules" / "typescript" / "lib" / "tsc.js"
    if not tsc_js.exists():
        return  # No typescript installed, skip

    node_exe = Path(NODE_PATH) / "node.exe"
    env = os.environ.copy()
    env["PATH"] = NODE_PATH + os.pathsep + env.get("PATH", "")

    try:
        result = subprocess.run(
            [str(node_exe), str(tsc_js), "--noEmit", "--skipLibCheck"],
            cwd=str(project_dir), env=env, capture_output=True, text=True, timeout=60,
            encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        # tsc is a best-effort quality gate here, not a requirement — every file
        # has already been generated and written to disk by this point. A slow
        # type-check (cold cache, larger project) doesn't mean anything is wrong
        # with the generated code, so it must never turn an otherwise-successful
        # refine/generation into a hard failure by propagating uncaught.
        progress_fn("llm_codegen:⚠️ Type check timed out after 60s — skipping validation")
        return
    if result.returncode == 0:
        progress_fn("llm_codegen:✅ Type checks passed")
        return

    errors = result.stdout + result.stderr
    error_lines = [l for l in errors.split("\n") if "error TS" in l]
    real_errors = [l for l in error_lines if "TS6133" not in l and "TS2307" not in l]

    if not real_errors:
        progress_fn(f"llm_codegen:✅ Only minor warnings ({len(error_lines)} unused vars/missing types)")
        return

    # One auto-fix pass — not verified by a second tsc run, see docstring.
    fixed_count = 0
    for err_line in real_errors:
        # Pattern: src/pages/File.tsx(line,col): error TS2339: Property 'X' does not exist on type 'Y[]'
        m = _re.match(r"(.+?)\((\d+),\d+\):\s*error\s+TS\d+", err_line)
        if not m:
            continue
        file_rel = m.group(1).replace("\\", "/")
        file_path = project_dir / file_rel
        if not file_path.exists():
            continue

        # Fix: add @ts-nocheck to files with many type errors (>5 in same file)
        file_errors = [e for e in real_errors if file_rel in e]
        if len(file_errors) >= 5:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            if "// @ts-nocheck" not in content and "@ts-nocheck" not in content:
                file_path.write_text("// @ts-nocheck\n" + content, encoding="utf-8")
                fixed_count += 1
                print(f"  [typecheck-fix] added @ts-nocheck to {file_rel} ({len(file_errors)} errors)", flush=True)

        # Fix: useApi<T[]> → useApi<T>
        if "useApi<" in err_line or "does not exist on type" in err_line:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            patched = _re.sub(r"useApi<(\w+)\[\]>", r"useApi<\1>", content)
            if patched != content:
                file_path.write_text(patched, encoding="utf-8")
                fixed_count += 1

        # Fix: stray quotes around a declaration immediately before a type
        # annotation, e.g. 'const m': Record<string, number> = {} — an LLM
        # transcription slip (seen recurring across refine calls) that turns
        # valid `const m: Record<...>` into invalid quoted-string-then-colon.
        if "Expected \";\" but found \":\"" in err_line:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            patched = _re.sub(
                r"""(['"])((?:const|let|var)\s+\w+)\1(\s*:)""",
                r"\2\3", content,
            )
            if patched != content:
                file_path.write_text(patched, encoding="utf-8")
                fixed_count += 1
                print(f"  [typecheck-fix] removed stray quotes around declaration in {file_rel}", flush=True)

    if fixed_count == 0:
        progress_fn(f"llm_codegen:⚠️ {len(real_errors)} type errors (could not auto-fix)")
    else:
        progress_fn(f"llm_codegen:🔧 Fixed {fixed_count} issue(s) (unverified — QA will catch anything remaining)")


def _fix_undeclared_rect_in_measure(files: dict) -> dict:
    """Fix 'rect is not defined' in measure/ResizeObserver callback functions.

    Scope-aware: checks each useEffect/function block independently so that
    a `const rect = ...` in one event handler doesn't mask an undeclared `rect`
    in a different scope (e.g. a measure callback).
    """
    import re as _re

    _DOM_ELEMENT_PROPS = {"parentElement", "clientWidth", "clientHeight", "offsetWidth",
                          "offsetHeight", "scrollWidth", "scrollHeight", "children", "style"}
    _BLOCK_START = _re.compile(r"^\s*(?:useEffect|useLayoutEffect)\s*\(\s*\(\)\s*=>\s*\{")

    for path, content in list(files.items()):
        if not path.endswith(".tsx"):
            continue
        if "rect" not in content:
            continue

        lines = content.split("\n")
        patched_lines = list(lines)
        did_patch = False

        # Split file into useEffect blocks and check each for undeclared rect
        i = 0
        while i < len(lines):
            if not _BLOCK_START.match(lines[i]):
                i += 1
                continue
            # Found a useEffect block — find its extent
            block_start = i
            depth = lines[i].count("{") - lines[i].count("}")
            j = i + 1
            while j < len(lines) and depth > 0:
                depth += lines[j].count("{") - lines[j].count("}")
                j += 1
            block_end = j
            block_text = "\n".join(lines[block_start:block_end])

            # Check this block specifically
            block_uses_rect = bool(_re.search(r"\brect\b", block_text))
            block_declares_rect = bool(_re.search(r"\b(?:const|let|var)\s+rect\b", block_text))
            block_rect_is_param = bool(_re.search(r"\(\s*(?:\[?\s*)?rect\b", block_text))

            if block_uses_rect and not block_declares_rect and not block_rect_is_param:
                # Find element variable within this block
                el_match = _re.search(r"const\s+(\w+)\s*=\s*(\w+Ref)\.current", block_text)
                el_var = el_match.group(1) if el_match else None

                if el_var:
                    rect_props = set(_re.findall(r"\brect\.(\w+)", block_text))
                    uses_dom_props = bool(rect_props & _DOM_ELEMENT_PROPS)

                    if uses_dom_props:
                        # Case 1: rect.parentElement/clientWidth → meant the element variable
                        for k in range(block_start, block_end):
                            if _re.search(r"\brect\b", patched_lines[k]) and not _re.search(r"\b(?:const|let|var)\s+rect\b", patched_lines[k]):
                                patched_lines[k] = _re.sub(r"\brect\b", el_var, patched_lines[k])
                                did_patch = True
                    else:
                        # Case 2: rect.width/height → insert getBoundingClientRect()
                        for k in range(block_start, block_end):
                            line = patched_lines[k]
                            func_match = _re.match(r"(\s*)(const\s+\w+\s*=\s*\(?[^)]*\)?\s*=>\s*\{|function\s+\w+\s*\([^)]*\)\s*\{)", line)
                            if func_match and "measure" in line.lower():
                                indent = func_match.group(1)
                                patched_lines.insert(k + 1, f"{indent}  const rect = {el_var}?.getBoundingClientRect(); if (!rect) return;")
                                did_patch = True
                                break
            i = block_end

        if did_patch:
            files[path] = "\n".join(patched_lines)
            print(f"[_fix_undeclared_rect] patched scope-aware rect in {path}", flush=True)
    return files


def _fix_useapi_double_generic(files: dict) -> dict:
    """Fix useApi<Row[]> → useApi<Row> (the hook already returns T[])."""
    import re as _re
    for path, content in list(files.items()):
        if not path.endswith(".tsx"):
            continue
        if "useApi<" not in content:
            continue
        patched = _re.sub(r"useApi<(\w+)\[\]>", r"useApi<\1>", content)
        if patched != content:
            files[path] = patched
            print(f"[_fix_useapi_double_generic] fixed useApi<T[]>→useApi<T> in {path}", flush=True)
    return files


def _fix_media_in_inline_styles(files: dict) -> dict:
    """Remove @media queries from JSX inline style objects.

    LLMs sometimes put CSS media queries inside style={{ ... }} props, which React
    does not support and emits a console warning. These must be in CSS/Tailwind classes.
    """
    import re as _re

    for path, content in list(files.items()):
        if not path.endswith(".tsx"):
            continue
        if "@media" not in content:
            continue

        lines = content.split("\n")
        new_lines = []
        skip_depth = 0
        in_media_block = False

        for line in lines:
            # Detect @media inside a style object: '@media (...)': { ... }
            if not in_media_block and _re.search(r"""['"]@media\s*\([^)]*\)['"]\s*:\s*\{""", line):
                in_media_block = True
                skip_depth = line.count("{") - line.count("}")
                continue
            if in_media_block:
                skip_depth += line.count("{") - line.count("}")
                if skip_depth <= 0:
                    in_media_block = False
                continue
            # Also catch single-line @media entries: '@media (...)': '...',
            if _re.search(r"""['"]@media\s*\([^)]*\)['"]\s*:""", line):
                continue
            new_lines.append(line)

        if len(new_lines) < len(lines):
            files[path] = "\n".join(new_lines)
            print(f"[_fix_media_in_inline_styles] removed @media from inline styles in {path}", flush=True)
    return files


def _fix_lucide_icons(files: dict) -> dict:
    """Fix hallucinated lucide-react icon names that don't exist in the package."""
    _ICON_MAP = {
        "FilePdf": "FileText",
        "FileCsv": "FileSpreadsheet",
        "FileExcel": "FileSpreadsheet",
        "FileWord": "FileText",
        "FilePowerpoint": "Presentation",
        "ChartLine": "TrendingUp",
        "ChartBar": "BarChart2",
        "ChartPie": "PieChart",
        "ChartArea": "AreaChart",
        "MapPinned": "MapPin",
        "UserCircle": "CircleUser",
        "DollarSign": "CircleDollarSign",
        "Logout": "LogOut",
        "Login": "LogIn",
        "Trashcan": "Trash2",
        "Hamburger": "Menu",
        "Close": "X",
        "Reload": "RefreshCw",
        "PDF": "FileText",
    }
    import re as _re
    for path_key, content in list(files.items()):
        if not (path_key.endswith(".tsx") or path_key.endswith(".ts")):
            continue
        if "lucide-react" not in content:
            continue
        patched = content
        for bad, good in _ICON_MAP.items():
            if bad in patched:
                # Word-boundary match, not naive substring replace: a bare substring
                # replace also rewrites unrelated identifiers that merely contain the
                # icon name, e.g. "Close" inside the extremely common `onClose` prop —
                # turning every onClose handler into onX and breaking every caller
                # that still passes onClose=.
                patched = _re.sub(r"\b" + _re.escape(bad) + r"\b", good, patched)
        # Dedupe imports after renaming (e.g. FileText imported twice)
        def _dedup_lucide_import(m):
            names = [n.strip() for n in m.group(1).split(",")]
            unique = list(dict.fromkeys(names))
            return "import { " + ", ".join(unique) + " } from 'lucide-react'"
        patched = _re.sub(
            r"import\s*\{\s*([^}]+)\s*\}\s*from\s*['\"]lucide-react['\"]",
            _dedup_lucide_import, patched
        )
        if patched != content:
            files[path_key] = patched
            print(f"[_fix_lucide_icons] fixed invalid icon names in {path_key}", flush=True)
    return files


def _fix_unbalanced_parens(files: dict) -> dict:
    """Fix common LLM bug: missing closing paren in onChange handlers with nested Math.max/min/Number."""
    import re as _re
    # Pattern: onChange={e => set(Math.max(min, Math.min(max, Number(e.target.value) || min))}
    # Missing one ) before the }
    pattern = _re.compile(
        r"(Number\([^)]*\)\s*\|\|\s*\w+)\)(\})"
    )
    for path_key, content in list(files.items()):
        if not path_key.endswith(".tsx"):
            continue
        if "Math.max" not in content or "Math.min" not in content:
            continue
        patched = content
        # Find lines with unbalanced parens in onChange/set patterns
        lines = patched.split("\n")
        fixed_lines = []
        changed = False
        for line in lines:
            if "Math.max" in line and "Math.min" in line and "Number(" in line:
                open_count = line.count("(")
                close_count = line.count(")")
                if open_count > close_count:
                    # Add missing closing parens before the last )}
                    diff = open_count - close_count
                    line = _re.sub(r"\)\}", ")" * (diff + 1) + "}", line)
                    changed = True
            fixed_lines.append(line)
        if changed:
            files[path_key] = "\n".join(fixed_lines)
            print(f"[_fix_unbalanced_parens] fixed missing parens in {path_key}", flush=True)
    return files


def _fix_common_syntax(files: dict) -> dict:
    """Fix common LLM-generated JS/TSX syntax errors that crash esbuild/Vite before tsc can catch them."""
    import re as _re

    for path_key, content in list(files.items()):
        if not (path_key.endswith(".tsx") or path_key.endswith(".ts")):
            continue

        original = content

        # 1. Duplicate export default — keep only the last one
        export_default_matches = list(_re.finditer(r"^export default ", content, _re.MULTILINE))
        if len(export_default_matches) > 1:
            # Remove all but the last export default statement
            for match in export_default_matches[:-1]:
                line_start = match.start()
                line_end = content.index("\n", line_start) if "\n" in content[line_start:] else len(content)
                # Replace with a comment so line numbers stay stable
                content = content[:line_start] + "// (removed duplicate export default)" + content[line_end:]

        # 2. Unterminated string literals (backticks, single quotes in JSX style props)
        # 2a is gated on the file's TOTAL backtick count being odd, not each line's
        # own count: a legitimate multi-line template literal (extremely common in
        # this codebase's Tailwind-class-string and D3-selector patterns) opens on
        # one line and closes on another, so each of those two lines individually
        # has an odd per-line count — checking per-line flagged both as "unterminated"
        # and injected a spurious closing backtick into each, turning the opening
        # line into an empty template literal and truncating everything after it.
        # Only a genuinely truncated response leaves the file with an odd TOTAL count.
        _file_backticks_odd = len(_re.findall(r"(?<!\\)`", content)) % 2 != 0
        lines = content.split("\n")
        fixed_lines = []
        for line in lines:
            # 2a. Unterminated backtick template literals
            backticks = len(_re.findall(r"(?<!\\)`", line))
            if _file_backticks_odd and backticks % 2 != 0:
                stripped = line.rstrip()
                if stripped.endswith("${") or "=> {" in stripped:
                    fixed_lines.append(line)
                else:
                    line = _re.sub(r"([^`]*`[^`]*)([;}\s]*)$", r"\1`\2", line)
                    fixed_lines.append(line)
            # 2b. Unterminated single-quote strings in JSX style props
            #     e.g. style={{ padding: '11px   (line ends without closing ')
            elif _re.search(r":\s*'[^']*$", line) and ("style" in line or "style" in "\n".join(fixed_lines[-3:])):
                line = _re.sub(r"(:\s*'[^']*)$", r"\1'", line)
                fixed_lines.append(line)
            else:
                fixed_lines.append(line)
        content = "\n".join(fixed_lines)

        # 3. Mismatched brackets in JSX map/filter expressions
        #    Pattern: .map(x => (...)} or .filter(x => (...)}
        content = _re.sub(
            r"(\.\s*(?:map|filter|reduce|forEach|flatMap|find)\s*\([^)]*=>\s*\([^}]*)\)\}",
            lambda m: _fix_map_brackets(m.group(0)),
            content
        )

        # 4. Missing closing > on self-closing JSX tags
        #    Pattern: <Component prop="val" / without >
        content = _re.sub(
            r"(<[A-Z]\w+[^>]*/)\s*$",
            r"\1>",
            content,
            flags=_re.MULTILINE
        )

        if content != original:
            files[path_key] = content
            print(f"[_fix_common_syntax] patched syntax issues in {path_key}", flush=True)

    return files


def _fix_map_brackets(expr: str) -> str:
    """Fix bracket mismatch in .map/.filter expressions by balancing ( and )."""
    open_parens = expr.count("(")
    close_parens = expr.count(")")
    open_braces = expr.count("{")
    close_braces = expr.count("}")
    # If there are more ( than ), add missing ) before final }
    if open_parens > close_parens:
        diff = open_parens - close_parens
        expr = _re_sub_last(r"\}", ")" * diff + "}", expr)
    return expr


def _re_sub_last(pattern: str, repl: str, text: str) -> str:
    """Replace last occurrence of pattern in text."""
    import re as _re
    matches = list(_re.finditer(pattern, text))
    if not matches:
        return text
    last = matches[-1]
    return text[:last.start()] + repl + text[last.end():]


def _safe_proxy_url(base_url: str, path: str, qs: str) -> str:
    """Build a proxy target URL, percent-encoding any unsafe characters in the path.
    FastAPI decodes path params, so spaces and & from @fs/ DS paths arrive unencoded
    and urllib rejects them. Re-encode everything except already-safe URL characters.
    """
    import urllib.parse as _up
    # Encode the path segment: keep / @ : . _ - ~ (safe for URL paths) but encode spaces & etc.
    encoded_path = _up.quote(path, safe="/@:._-~!$'()*+,;=")
    url = base_url + encoded_path
    if qs:
        url += "?" + qs
    return url


def _resolve_vite_port(project_name: str) -> int | None:
    """Get the current Vite dev port for a project, only if it's actually listening."""
    from agents.uigen_agent import _dev_ports, _dev_servers, _PORTS_FILE
    import json as _json
    import socket as _socket
    port = _dev_ports.get(project_name)
    try:
        disk_ports = _json.loads(_PORTS_FILE.read_text())
        val = disk_ports.get(project_name)
        if isinstance(val, dict):
            disk_port = val.get("vite")
        elif isinstance(val, int):
            disk_port = val
        else:
            disk_port = None
        if disk_port and disk_port != port:
            _dev_ports[project_name] = disk_port
            port = disk_port
    except Exception:
        pass
    if not port:
        return None
    # Quick check: is anything actually listening on that port?
    if project_name not in _dev_servers:
        try:
            with _socket.create_connection(("127.0.0.1", port), timeout=0.3):
                return port
        except (OSError, ConnectionRefusedError):
            return None
    return port


_auto_start_in_progress: set = set()

async def _auto_start_project(project_name: str) -> int | None:
    """Try to auto-start a project's Vite server. Returns the port or None."""
    if project_name in _auto_start_in_progress:
        return None
    _auto_start_in_progress.add(project_name)
    try:
        from agents.uigen_agent import GENERATED_DIR
        project_dir = GENERATED_DIR / project_name
        if not project_dir.exists():
            return None
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_executor, _dispatch_start, project_name)
        return result.get("port") if isinstance(result, dict) else None
    except Exception:
        return None
    finally:
        _auto_start_in_progress.discard(project_name)


@app.api_route("/app/{project_name}/{path:path}", methods=["GET","POST","PUT","DELETE","OPTIONS","HEAD"])
async def proxy_vite(project_name: str, path: str, request: Request):
    """Reverse-proxy requests for a React/Vite project through FastAPI (same-origin for iframe)."""
    import urllib.request as _ureq
    import urllib.error as _uerr
    from agents.uigen_agent import _api_ports

    # Route API requests directly to the backend server (bypasses Vite proxy issues with base path)
    if path.startswith("api/") or path == "api":
        from agents.uigen_agent import _datachat_ports
        api_port = _api_ports.get(project_name)
        # Route chat/ingest to DataChat server when it runs on a separate port
        dc_port = _datachat_ports.get(project_name)
        if dc_port and (path.startswith("api/chat") or path.startswith("api/ingest")):
            api_port = dc_port
        if api_port:
            api_target = f"http://127.0.0.1:{api_port}/{path}"
            qs = str(request.query_params)
            if qs:
                api_target += "?" + qs
            try:
                body = await request.body()
                fwd_headers = {k: v for k, v in request.headers.items()
                               if k.lower() not in ("host", "content-length")}
                http_req = _ureq.Request(api_target, data=body or None,
                                          method=request.method, headers=fwd_headers)
                with _ureq.urlopen(http_req, timeout=150) as resp:
                    content = resp.read()
                    headers = {k: v for k, v in resp.headers.items()
                               if k.lower() not in ("transfer-encoding", "connection", "keep-alive")}
                    return Response(content=content, status_code=resp.status,
                                    headers=headers, media_type=resp.headers.get("content-type"))
            except _uerr.HTTPError as e:
                return Response(content=e.read(), status_code=e.code)
            except (_uerr.URLError, OSError):
                raise HTTPException(502, f"Backend API server not reachable on port {api_port}")

    port = _resolve_vite_port(project_name)
    if not port:
        raise HTTPException(503, "Project not running. Start it from the sidebar.")
    # Vite is configured with base='/app/{name}/' so all its assets live under that prefix
    base_url = "http://127.0.0.1:" + str(port) + "/app/" + project_name + "/"
    target = _safe_proxy_url(base_url, path, str(request.query_params))
    try:
        body = await request.body()
        fwd_headers = {k: v for k, v in request.headers.items()
                       if k.lower() not in ("host", "content-length")}
        http_req = _ureq.Request(target, data=body or None,
                                  method=request.method, headers=fwd_headers)
        # LLM chat calls can take 60-120s; use longer timeout for API paths
        proxy_timeout = 150 if "/api/" in path else 30
        with _ureq.urlopen(http_req, timeout=proxy_timeout) as resp:
            content = resp.read()
            headers = {k: v for k, v in resp.headers.items()
                       if k.lower() not in ("transfer-encoding", "connection", "keep-alive")}
            return Response(content=content, status_code=resp.status,
                            headers=headers, media_type=resp.headers.get("content-type"))
    except _uerr.HTTPError as e:
        return Response(content=e.read(), status_code=e.code)
    except (_uerr.URLError, OSError) as e:
        raise HTTPException(502, "App not reachable. It may have stopped — start it from the sidebar.")
    except Exception as e:
        raise HTTPException(502, "Proxy error: " + str(e))


@app.get("/app/{project_name}", include_in_schema=False)
async def proxy_vite_root(project_name: str, request: Request):
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/app/" + project_name + "/", status_code=302)


@app.api_route("/figma-app/{project_name}/{path:path}", methods=["GET","POST","PUT","DELETE","OPTIONS","HEAD"])
async def proxy_figma(project_name: str, path: str, request: Request):
    """Reverse-proxy requests for an HTML/Figma project through FastAPI (same-origin for iframe)."""
    import urllib.request as _ureq
    import urllib.error as _uerr
    from agents.figma_to_web_using_playwright_agent import _html_ports
    port = _html_ports.get(project_name)
    if not port:
        raise HTTPException(503, "Project not running")
    # HTML server serves files under /{project_name}/ — keep that prefix
    target = "http://127.0.0.1:" + str(port) + "/" + project_name + "/" + path
    qs = str(request.query_params)
    if qs:
        target += "?" + qs
    try:
        body = await request.body()
        fwd_headers = {k: v for k, v in request.headers.items()
                       if k.lower() not in ("host", "content-length")}
        http_req = _ureq.Request(target, data=body or None,
                                  method=request.method, headers=fwd_headers)
        with _ureq.urlopen(http_req, timeout=30) as resp:
            content = resp.read()
            headers = {k: v for k, v in resp.headers.items()
                       if k.lower() not in ("transfer-encoding", "connection", "keep-alive")}
            return Response(content=content, status_code=resp.status,
                            headers=headers, media_type=resp.headers.get("content-type"))
    except _uerr.HTTPError as e:
        return Response(content=e.read(), status_code=e.code)
    except Exception as e:
        raise HTTPException(502, "Proxy error: " + str(e))


@app.get("/figma-app/{project_name}", include_in_schema=False)
async def proxy_figma_root(project_name: str):
    return RedirectResponse(url="/figma-app/" + project_name + "/", status_code=302)


# ── Figma Mockup Projects ────────────────────────────────────────────────────
# Stored in generated/figma-mockups/<project-name>/project-figma-mockup.json

import json as _json
from datetime import datetime, timezone

# Generated apps live in WebUIGenerator/generated/ (config already loaded from WebUIGenerator)
from config import WEB_APPS_DIR as GENERATED_DIR, GENERATED_ROOT

# Figma mockups live in FigmaMockupGenerator/generated/ — load that config explicitly
import importlib.util as _ilu
_fmc_spec = _ilu.spec_from_file_location(
    "figma_config",
    str(Path(__file__).resolve().parent.parent / "FigmaMockupGenerator" / "config.py")
)
_fmc = _ilu.module_from_spec(_fmc_spec)
_fmc_spec.loader.exec_module(_fmc)
_FIGMA_PROJECTS_DIR = _fmc.FIGMA_MOCKUPS_DIR  # FigmaMockupGenerator/generated/figma-mockups/


def _figma_proj_dir(name: str) -> Path:
    return _FIGMA_PROJECTS_DIR / name


def _load_figma_project(name: str) -> dict:
    f = _figma_proj_dir(name) / "project-figma-mockup.json"
    if f.exists():
        try: return _json.loads(f.read_text(encoding="utf-8"))
        except: pass
    return {}


def _save_figma_project(name: str, data: dict):
    d = _figma_proj_dir(name)
    d.mkdir(parents=True, exist_ok=True)
    (d / "project-figma-mockup.json").write_text(_json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_figma_buildlog_live(name: str, lines: list[str]):
    """Overwrite .buildlog.current.json with the latest in-progress log lines."""
    d = _figma_proj_dir(name)
    if not d.exists():
        return
    try:
        (d / ".buildlog.current.json").write_text(
            _json.dumps({"live": True, "lines": lines}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def _save_figma_buildlog(name: str, log_lines: list[str], event: str = ""):
    """Append a completed build run to .buildlog.json and remove the live file."""
    from datetime import datetime, timezone
    d = _figma_proj_dir(name)
    if not d.exists():
        return
    # Remove live file — build is done
    try:
        live_file = d / ".buildlog.current.json"
        if live_file.exists():
            live_file.unlink()
    except Exception:
        pass
    log_file = d / ".buildlog.json"
    try:
        runs = _json.loads(log_file.read_text(encoding="utf-8")) if log_file.exists() else []
    except Exception:
        runs = []
    runs.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event":     event,
        "lines":     log_lines,
    })
    log_file.write_text(_json.dumps(runs, indent=2, ensure_ascii=False), encoding="utf-8")


def _append_figma_history(name: str, event: str, prompt: str = "",
                          figma_url: str = "", instructions: str = "",
                          source_url: str = ""):
    """Append a history entry to .history.json in the figma project folder.
    Mirrors the webapp pattern: separate file, never truncated, oldest-first."""
    from datetime import datetime, timezone
    d = _figma_proj_dir(name)
    if not d.exists():
        return
    history_file = d / ".history.json"
    try:
        history = _json.loads(history_file.read_text(encoding="utf-8")) if history_file.exists() else []
    except Exception:
        history = []
    entry = {
        "event":     event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prompt":    prompt,
        "figmaUrl":  figma_url,
    }
    if instructions:
        entry["instructions"] = instructions
    if source_url:
        entry["source_url"] = source_url
    history.append(entry)
    history_file.write_text(_json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")


class FigmaProjectCreateRequest(BaseModel):
    name: str


class FigmaProjectUpdateRequest(BaseModel):
    prompt: str
    mode: str = "create"
    screens: list[str] = []
    figma_url: str = ""
    notes: str = ""


@app.get("/api/figma/projects")
def api_list_figma_projects():
    _FIGMA_PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    projects = []
    for d in sorted(_FIGMA_PROJECTS_DIR.iterdir()):
        if d.is_dir() and (d / "project-figma-mockup.json").exists():
            data = _load_figma_project(d.name)
            # Read history from dedicated .history.json; fall back to embedded array
            history_file = d / ".history.json"
            try:
                history = _json.loads(history_file.read_text(encoding="utf-8")) if history_file.exists() else data.get("history", [])
            except Exception:
                history = data.get("history", [])
            projects.append({
                "name":       d.name,
                "title":      data.get("title", d.name),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
                "screens":    data.get("screens", []),
                "figma_url":  data.get("figma_url", ""),
                "notes":      data.get("notes", ""),
                "history":    history,
            })
    return projects


@app.post("/api/figma/projects/create")
def api_create_figma_project(req: FigmaProjectCreateRequest):
    import re as _re
    name = _re.sub(r"[^a-z0-9-]", "-", req.name.lower()).strip("-")
    if not name:
        raise HTTPException(400, "Invalid project name")
    now = datetime.now(timezone.utc).isoformat()
    data = {
        "title":      req.name,
        "created_at": now,
        "updated_at": now,
        "screens":    [],
        "figma_url":  "",
        "notes":      "",
    }
    _save_figma_project(name, data)
    return {"name": name, **data}


@app.post("/api/figma/projects/{name}/update")
def api_update_figma_project(name: str, req: FigmaProjectUpdateRequest):
    data = _load_figma_project(name)
    if not data:
        raise HTTPException(404, f"Figma project '{name}' not found")
    now = datetime.now(timezone.utc).isoformat()
    # Append to history
    history_entry = {
        "timestamp": now,
        "prompt":    req.prompt,
        "mode":      req.mode,
        "screens":   req.screens or data.get("screens", []),
    }
    data.setdefault("history", []).append(history_entry)
    # Update fields
    if req.screens:  data["screens"]   = req.screens
    if req.figma_url: data["figma_url"] = req.figma_url
    if req.notes:    data["notes"]     = req.notes
    data["updated_at"] = now
    _save_figma_project(name, data)
    return {"name": name, **data}


@app.get("/api/figma/projects/{name}/buildlog")
def api_figma_get_buildlog(name: str):
    """Return the most recent build log lines for a Figma project.
    Prefers .buildlog.current.json (live build in progress) over .buildlog.json."""
    d = _figma_proj_dir(name)
    # Live build in progress — return current lines
    live_file = d / ".buildlog.current.json"
    if live_file.exists():
        try:
            data = _json.loads(live_file.read_text(encoding="utf-8"))
            return {"log": data.get("lines", []), "timestamp": None, "live": True}
        except Exception:
            pass
    # Completed build — return latest run
    log_file = d / ".buildlog.json"
    if not log_file.exists():
        return {"log": [], "timestamp": None}
    try:
        runs = _json.loads(log_file.read_text(encoding="utf-8"))
        latest = runs[-1] if runs else {}
        return {"log": latest.get("lines", []), "timestamp": latest.get("timestamp")}
    except Exception:
        return {"log": [], "timestamp": None}


@app.delete("/api/figma/projects/{name}")
def api_delete_figma_project(name: str):
    import shutil as _shutil
    import stat as _stat
    import time as _time
    d = _figma_proj_dir(name)
    if not d.exists():
        return {"deleted": name}

    def _on_error(func, path, exc_info):
        # On Windows, files may be read-only or locked by OneDrive/antivirus.
        # Try making the file writable and retry once.
        try:
            import os as _os
            _os.chmod(path, _stat.S_IWRITE)
            func(path)
        except Exception:
            pass  # best-effort — skip files that can't be removed

    _shutil.rmtree(d, onerror=_on_error)
    # If directory still exists (some files locked), try again after a short wait
    if d.exists():
        _time.sleep(0.5)
        _shutil.rmtree(d, onerror=_on_error)
    return {"deleted": name}


# ── Figma Wireframe API ───────────────────────────────────────────────────────

class WireframeRequest(BaseModel):
    prompt: str
    mode: str = "new"            # new | edit | replace (legacy: create → new, append → edit)
    confirmed: bool = False      # True = user confirmed overwrite (skip CONFIRM check)
    project_name: str = ""       # optional — save run to this figma project
    figma_url: str = ""          # optional — store in project metadata
    apply_brand: bool = False    # True = apply Mobility Global brand colors
    instructions: str = ""       # optional Markdown instructions appended to prompt


@app.get("/api/figma/mcp/status")
async def api_figma_mcp_status():
    """Check if the Figma MCP server and relay are reachable."""
    import urllib.request as _req
    import urllib.error as _err
    try:
        with _req.urlopen(f"{MCP_URL}/", timeout=3) as r:
            import json as _json
            data = _json.loads(r.read())
            return {
                "mcp_server":     True,
                "relay_connected": data.get("relay_connected", False),
                "tools":          data.get("tools", 0),
            }
    except Exception:
        return {"mcp_server": False, "relay_connected": False, "tools": 0}


def _run_wireframe(req: WireframeRequest, request_id: str) -> dict:
    import sys, time as _tw
    from pathlib import Path as _Path
    from datetime import datetime as _dt

    _tw_start = _tw.time()

    _wireframe_dir = str(_Path(__file__).resolve().parent.parent / "FigmaMockupGenerator" / "figma" / "wireframe")
    if _wireframe_dir not in sys.path:
        sys.path.insert(0, _wireframe_dir)

    from prompt_to_figma_agent import run_agent
    import token_tracker
    token_tracker.reset(request_id)
    token_tracker.set_run_id(request_id)

    messages = []
    def on_progress(text: str):
        clean = (text or "").strip()
        if clean:
            elapsed = _tw.time() - _tw_start
            ts = _dt.now().strftime("%H:%M:%S")
            stamped = f"[{ts} +{elapsed:.1f}s] {clean}"
            messages.append(stamped)
            _progress_logs.setdefault(request_id, []).append(stamped)
            if req.project_name:
                _write_figma_buildlog_live(req.project_name, messages)

    # Append Markdown instructions to the prompt if provided
    instructions_trimmed = (req.instructions or "").strip()
    effective_prompt = req.prompt
    if instructions_trimmed:
        effective_prompt = (
            f"{req.prompt}\n\n"
            f"## Detailed Instructions\n\n{instructions_trimmed}"
        )

    result = run_agent(effective_prompt, stream_callback=on_progress, mode=req.mode,
                       apply_brand=req.apply_brand, confirmed=req.confirmed)

    # ── Handle structured error/confirm codes from run_agent ──────────────────
    ERROR_MESSAGES = {
        "ERROR:NO_MCP_SERVER":
            "Cannot reach the Figma MCP server. Make sure "
            "FigmaMockupGenerator\\figma\\mcp\\start.bat is running.",
        "ERROR:NO_TOOLS":
            "MCP server is running but has no tools. Restart "
            "FigmaMockupGenerator\\figma\\mcp\\start.bat.",
        "ERROR:NO_FIGMA_FILE":
            "No Figma file is open. Please open a Figma file in Figma Desktop, "
            "then run the Desktop Bridge plugin (Plugins → Development → "
            "Figma Desktop Bridge → Run) and wait for 'Local Ready'.",
        "ERROR:BRIDGE_NOT_CONNECTED":
            "Figma Desktop Bridge plugin is not running. Open Figma Desktop, "
            "go to Plugins → Development → Figma Desktop Bridge → Run, "
            "and wait for 'Local Ready' before building.",
        "ERROR:RELAY_NOT_CONNECTED":
            "The Figma relay is not connected to the Desktop Bridge plugin. "
            "Check that the 'Figma Relay' window opened by start.bat is still running "
            "and shows no errors. If it crashed, re-run start.bat. "
            "The plugin panel should show 'Local Ready' (not just 'READY').",
    }

    # run_agent returns either a plain string (error/confirm) or a dict {result, figma_url}
    result_str  = result if isinstance(result, str) else result.get("result", "")
    figma_url   = result.get("figma_url", "") if isinstance(result, dict) else ""

    if result_str in ERROR_MESSAGES:
        return {
            "result":    result_str,
            "error":     ERROR_MESSAGES[result_str],
            "error_code": result_str,
            "log":       messages,
        }

    # Existing frames confirmation signal
    if isinstance(result_str, str) and result_str.startswith("CONFIRM:EXISTING_FRAMES:"):
        parts = result_str.split(":", 3)
        frame_count = int(parts[2]) if len(parts) > 2 else 0
        frame_names = parts[3] if len(parts) > 3 else ""
        return {
            "result":        result_str,
            "needs_confirm": True,
            "error_code":    "EXISTING_FRAMES",
            "frame_count":   frame_count,
            "frame_names":   frame_names,
            "message": (
                f"Your Figma file already has {frame_count} frame(s): {frame_names}. "
                f"Choose what to do: 'edit' modifies existing or adds new screens, "
                f"'replace' rebuilds specific screens, or cancel to keep as-is."
            ),
            "log": messages,
        }

    # Persist run to figma project metadata (figma_url + updated_at only)
    if req.project_name:
        try:
            proj = _load_figma_project(req.project_name)
            if proj:
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc).isoformat()
                saved_url = figma_url or req.figma_url
                if saved_url:
                    proj["figma_url"] = saved_url
                proj["updated_at"] = now
                _save_figma_project(req.project_name, proj)
        except Exception:
            pass
        try:
            _save_figma_buildlog(req.project_name, messages, event="prompt")
        except Exception:
            pass
        try:
            saved_figma_url = figma_url or req.figma_url
            _append_figma_history(
                req.project_name,
                event="Built from prompt" if req.mode in ("new", "replace") else "Edited",
                prompt=req.prompt,
                figma_url=saved_figma_url,
                instructions=instructions_trimmed,
            )
        except Exception:
            pass

    # ── Token usage summary ─────────────────────────────────────────────────
    _elapsed = _tw.time() - _tw_start
    for line in token_tracker.format_summary(request_id, elapsed=_elapsed):
        on_progress(line)

    return {"result": result_str, "figma_url": figma_url, "log": messages, "project_name": req.project_name or ""}


@app.post("/api/figma/wireframe")
async def api_figma_wireframe(req: WireframeRequest):
    global _latest_request_id
    import uuid
    request_id = uuid.uuid4().hex
    _progress_logs[request_id] = []
    _latest_request_id = request_id
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(_executor, _run_wireframe, req, request_id)
        result["requestId"] = request_id
        return result
    except Exception as e:
        import traceback
        raise HTTPException(500, f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1000:]}")
    finally:
        async def _cleanup():
            await asyncio.sleep(120)
            _progress_logs.pop(request_id, None)
        asyncio.create_task(_cleanup())


# ── Web App → Figma Wireframe API ────────────────────────────────────────────

class WebAppToFigmaRequest(BaseModel):
    url: str                         # live web app URL to screenshot
    project_name: str = ""           # optional — save run to this figma project
    figma_url: str = ""              # optional — store in project metadata
    max_pages: int = 12              # max pages to screenshot
    nav_click_depth: int = 2         # how many nav links to follow
    instructions: str = ""          # optional extra instructions for the Figma build
    viewport_width: int = 1440
    viewport_height: int = 900
    login_username: str = ""         # optional — auto-fill login form
    login_password: str = ""         # optional — auto-fill login form


def _run_webapp_to_figma(req: WebAppToFigmaRequest, request_id: str) -> dict:
    import sys, time as _tw
    from pathlib import Path as _Path
    from datetime import datetime as _dt

    _tw_start = _tw.time()

    _wireframe_dir = str(_Path(__file__).resolve().parent.parent / "FigmaMockupGenerator" / "figma" / "wireframe")
    if _wireframe_dir not in sys.path:
        sys.path.insert(0, _wireframe_dir)

    from webapp_to_figma_agent import run_agent
    import token_tracker
    token_tracker.reset(request_id)
    token_tracker.set_run_id(request_id)

    messages = []
    def on_progress(text: str):
        clean = (text or "").strip()
        if clean:
            elapsed = _tw.time() - _tw_start
            ts = _dt.now().strftime("%H:%M:%S")
            stamped = f"[{ts} +{elapsed:.1f}s] {clean}"
            messages.append(stamped)
            _progress_logs.setdefault(request_id, []).append(stamped)
            if req.project_name:
                _write_figma_buildlog_live(req.project_name, messages)

    result = run_agent(
        url=req.url,
        stream_callback=on_progress,
        max_pages=req.max_pages,
        nav_click_depth=req.nav_click_depth,
        extra_instructions=req.instructions,
        viewport_width=req.viewport_width,
        viewport_height=req.viewport_height,
        project_name=req.project_name,
        login_username=req.login_username,
        login_password=req.login_password,
    )

    ERROR_MESSAGES = {
        "ERROR:NO_MCP_SERVER":
            "Cannot reach the Figma MCP server. Make sure "
            "FigmaMockupGenerator\\figma\\mcp\\start.bat is running.",
        "ERROR:NO_TOOLS":
            "MCP server is running but has no tools. Restart "
            "FigmaMockupGenerator\\figma\\mcp\\start.bat.",
        "ERROR:NO_FIGMA_FILE":
            "No Figma file is open. Open a Figma file in Figma Desktop, "
            "run the Desktop Bridge plugin and wait for 'Local Ready'.",
        "ERROR:BRIDGE_NOT_CONNECTED":
            "Figma Desktop Bridge plugin is not running. Open Figma Desktop, "
            "go to Plugins → Development → Figma Desktop Bridge → Run.",
        "ERROR:RELAY_NOT_CONNECTED":
            "The Figma relay is not connected to the Desktop Bridge plugin. "
            "Check that the 'Figma Relay' window opened by start.bat is still running. "
            "If it crashed, re-run start.bat. The plugin should show 'Local Ready'.",
        "ERROR:NO_PAGES_CAPTURED":
            "Playwright could not capture any pages from the URL. "
            "Make sure the web app is running and accessible.",
    }

    result_str = result if isinstance(result, str) else result.get("result", "")
    figma_url  = result.get("figma_url", "") if isinstance(result, dict) else ""

    if result_str in ERROR_MESSAGES:
        return {"result": result_str, "error": ERROR_MESSAGES[result_str],
                "error_code": result_str, "log": messages}

    if isinstance(result_str, str) and result_str.startswith("ERROR:PLAYWRIGHT:"):
        return {"result": result_str,
                "error": f"Playwright error: {result_str.split(':', 2)[-1]} — "
                         "make sure Playwright is installed: pip install playwright && playwright install chromium",
                "error_code": "PLAYWRIGHT_ERROR", "log": messages}

    # Persist to figma project metadata (figma_url + updated_at only)
    if req.project_name:
        try:
            proj = _load_figma_project(req.project_name)
            if proj:
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc).isoformat()
                saved_url = figma_url or req.figma_url
                if saved_url:
                    proj["figma_url"] = saved_url
                proj["updated_at"] = now
                _save_figma_project(req.project_name, proj)
        except Exception:
            pass
        try:
            _save_figma_buildlog(req.project_name, messages, event="webapp-import")
        except Exception:
            pass
        try:
            saved_figma_url = figma_url or req.figma_url
            _append_figma_history(
                req.project_name,
                event="Web app import",
                figma_url=saved_figma_url,
                source_url=req.url,
            )
        except Exception:
            pass

    # ── Token usage summary ─────────────────────────────────────────────────
    _elapsed = _tw.time() - _tw_start
    for line in token_tracker.format_summary(request_id, elapsed=_elapsed):
        on_progress(line)

    return {"result": result_str, "figma_url": figma_url, "log": messages, "project_name": req.project_name or ""}


def _rewrite_sandbox_url(url: str) -> str:
    """Rewrite /sandbox/<name> to /app/<name>/ so Playwright hits the real app, not the iframe wrapper."""
    import re
    m = re.match(r"(https?://[^/]+)/sandbox/([^/?#]+)(.*)", url)
    if m:
        origin, name, rest = m.group(1), m.group(2), m.group(3)
        return f"{origin}/app/{name}/{rest}"
    return url


@app.get("/api/figma/webapp-discover")
async def api_webapp_discover(url: str, max_pages: int = 50, nav_depth: int = 4,
                               login_username: str = "", login_password: str = "",
                               project_name: str = ""):
    """Crawl a web app URL with Playwright, return discovered pages, and cache
    the full screenshot/SVG data in the figma project folder if project_name is given."""
    import sys, uuid, time as _tw
    from pathlib import Path as _Path
    from datetime import datetime as _dt

    global _latest_request_id

    url = _rewrite_sandbox_url(url)

    _wireframe_dir = str(_Path(__file__).resolve().parent.parent / "FigmaMockupGenerator" / "figma" / "wireframe")
    if _wireframe_dir not in sys.path:
        sys.path.insert(0, _wireframe_dir)

    from webapp_to_figma_agent import _take_screenshots

    _tw_start = _tw.time()
    request_id = uuid.uuid4().hex
    _progress_logs[request_id] = []
    _latest_request_id = request_id

    messages = []
    def on_progress(text: str):
        clean = (text or "").strip()
        if clean:
            elapsed = _tw.time() - _tw_start
            ts = _dt.now().strftime("%H:%M:%S")
            stamped = f"[{ts} +{elapsed:.1f}s] {clean}"
            messages.append(stamped)
            _progress_logs.setdefault(request_id, []).append(stamped)

    def _run():
        # Resolve screenshots_dir so PNGs and SVGs are saved during discovery
        screenshots_dir = None
        if project_name:
            _fmc_root = _Path(__file__).resolve().parent.parent / "FigmaMockupGenerator"
            screenshots_dir = _fmc_root / "generated" / "figma-mockups" / project_name / "screenshots"
            screenshots_dir.mkdir(parents=True, exist_ok=True)

        pages = _take_screenshots(url, max_pages=max_pages, nav_click_depth=nav_depth,
                                  login_username=login_username, login_password=login_password,
                                  emit=on_progress, screenshots_dir=screenshots_dir)

        # Save full cache (b64 + SVG nodes) so the build step can skip re-screenshotting
        if project_name and screenshots_dir and pages:
            cache = {
                "url": url,
                "cached_at": _dt.utcnow().isoformat() + "Z",
                "max_pages": max_pages,
                "nav_depth": nav_depth,
                "login_username": login_username,
                "pages": [
                    {k: v for k, v in p.items() if k != "screenshot_b64"}  # b64 kept separately
                    for p in pages
                ],
            }
            # Store b64 images inline — they are needed by the vision analysis step.
            # Strip element_screenshots (SVG/canvas extractions) — they must be re-extracted
            # during Build so the improved color-wait logic applies to the live DOM.
            cache["pages"] = [
                {k: v for k, v in p.items() if k != "element_screenshots"}
                for p in pages
            ]
            cache_file = screenshots_dir / ".discover_cache.json"
            try:
                cache_file.write_text(_json.dumps(cache, ensure_ascii=False), encoding="utf-8")
                on_progress(f"[CACHE] Discover data saved — build will reuse these screenshots")
            except Exception:
                pass

        return [{"title": p["title"], "url": p["url"], "nav_label": p["nav_label"],
                 "depth": p.get("depth", 0)} for p in pages]

    loop = asyncio.get_event_loop()
    try:
        pages = await loop.run_in_executor(_executor, _run)
        max_depth_found = max((p["depth"] for p in pages), default=0)
        if project_name and messages:
            try:
                _save_figma_buildlog(project_name, messages, event="discover")
            except Exception:
                pass
        return {"pages": pages, "count": len(pages), "max_depth": max_depth_found,
                "requestId": request_id, "log": messages}
    except Exception as e:
        raise HTTPException(500, f"Discovery failed: {e}")
    finally:
        async def _cleanup():
            await asyncio.sleep(60)
            _progress_logs.pop(request_id, None)
        asyncio.create_task(_cleanup())


@app.post("/api/figma/webapp-to-figma")
async def api_webapp_to_figma(req: WebAppToFigmaRequest):
    req.url = _rewrite_sandbox_url(req.url)
    global _latest_request_id
    import uuid
    request_id = uuid.uuid4().hex
    _progress_logs[request_id] = []
    _latest_request_id = request_id
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(_executor, _run_webapp_to_figma, req, request_id)
        result["requestId"] = request_id
        return result
    except Exception as e:
        import traceback
        raise HTTPException(500, f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1000:]}")
    finally:
        async def _cleanup():
            await asyncio.sleep(300)
            _progress_logs.pop(request_id, None)
        asyncio.create_task(_cleanup())


@app.get("/{full_path:path}", response_class=HTMLResponse)
async def spa_fallback(full_path: str):
    """SPA catch-all — return index.html for any unknown path so React Router handles it."""
    if (UI_DIST / "index.html").exists():
        return FileResponse(UI_DIST / "index.html")
    return HTMLResponse("<h2>UI not built.</h2>", status_code=404)


if __name__ == "__main__":
    from config import API_URL, TURBOUI_PORT as _port
    print(f"\nTurboUIGen running at {API_URL}\n")
    uvicorn.run("api.server:app", host="0.0.0.0", port=_port, reload=False)
