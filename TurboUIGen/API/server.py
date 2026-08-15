#!/usr/bin/env python3
"""TurboUIGen — FastAPI server. Serves the UI and exposes the agent as a REST API."""

import asyncio
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# sys.path is configured by run.py before this module is loaded.
# WebUIGenerator/ and FigmaMockupGenerator/ are already on sys.path.

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response, RedirectResponse
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

app = FastAPI(title="TurboUIGen")
_executor = ThreadPoolExecutor(max_workers=4)

_ROOT   = Path(__file__).resolve().parent.parent   # TurboUIGen/
UI_DIST = _ROOT / "UI" / "dist"
UI_DEV  = _ROOT / "UI" / "index.html"


class GenerateRequest(BaseModel):
    prompt: str
    project_name: str | None = None
    figma_url: str | None = None
    instructions: str = ""   # optional Markdown instructions appended to prompt
    architecture: dict | None = None  # pre-approved architecture from /api/draft (skips Stage 1)


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

class CreateProjectRequest(BaseModel):
    name: str


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

        _url_type_m = _re2.search(r"figma\.com/(file|design|proto|make)/", req.figma_url, _re2.IGNORECASE)
        _url_type = _url_type_m.group(1).lower() if _url_type_m else "design"
        _is_rest = _url_type in ("design", "file")
        if _is_rest:
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
        _write_meta(project_name, req.figma_url.strip(), req.prompt,
                    title=raw.get("title", ""), has_app=True)
        _append_buildlog(project_name, _progress_logs.get(request_id, []),
                         event="Built from Figma", duration_s=_time.time()-_t0)

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
    )

    project_name = result["projectName"]
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


def _run_refine(project_name: str, prompt: str, request_id: str, comment: str = "", instructions: str = "") -> dict:
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

        # ── Smart context selection ────────────────────────────────────────────
        # Extract meaningful keywords from BOTH prompt and instructions for relevance scoring.
        import re as _re_kw
        _kw_source = prompt + " " + ((instructions or "").strip()[:5000])
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
        _instructions_len = len((instructions or "").strip())
        _MAX_PER_FILE = 30_000   # ~900 lines — large enough for most pages
        _MAX_TOTAL    = max(30_000, 70_000 - min(_instructions_len, 30_000))

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

        instructions_trimmed = (instructions or "").strip()
        if instructions_trimmed:
            _progress(f"llm_codegen:Applying detailed instructions ({len(instructions_trimmed)} chars)…")

        refine_user = (
            f"Existing project files:\n{file_context}\n\n"
            f"Refinement request: {prompt}"
        )
        if instructions_trimmed:
            refine_user += f"\n\n## Detailed Instructions\n\n{instructions_trimmed}"
        refine_user += "\n\nReturn only the files that need to change as JSON with key 'files'."

        _progress("llm_codegen:Generating updated files…")

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

        # ── Two-pass fallback: if single-shot fails, first identify which files
        # need to change, then generate each one individually ─────────────────
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
                _progress(f"llm_codegen:Two-pass — generating: {target_path}")
                _fc2 = ""
                _fc2_budget = 25_000
                if target_path in existing:
                    _target_content = existing[target_path][:40_000]
                    _fc2 += f"\n// FILE: {target_path}\n{_target_content}\n"
                _schema_key = "api/schema.sql" if "api/schema.sql" in existing else "schema.sql"
                _structural = [_schema_key, "src/types.ts", "src/App.tsx"]
                for _ep in _structural:
                    if _ep in existing and _ep != target_path:
                        _snippet = existing[_ep][:8_000]
                        if len(_fc2) + len(_snippet) < _fc2_budget:
                            _fc2 += f"\n// FILE: {_ep}\n{_snippet}\n"

                gen_user = (
                    f"Existing project files:\n{_fc2}\n\n"
                    f"Refinement request: {prompt}\n\n"
                )
                if _instr2:
                    gen_user += f"## Detailed Instructions\n\n{_instr2}\n\n"
                gen_user += (
                    f"Generate the COMPLETE updated content for: {target_path}\n"
                    f"Return JSON: {{\"files\": {{\"{target_path}\": \"<complete file content>\"}}}}"
                )

                try:
                    gen_data = chat_json(
                        messages=[{"role": "user", "content": gen_user}],
                        system=refine_system,
                        max_tokens=64000,
                        temperature=0.1,
                    )
                    for k, v in gen_data.get("files", {}).items():
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

            if not result_files:
                raise RuntimeError("Two-pass: no files were generated")
            return {"files": result_files}

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
        from agents.uigen_agent import (
            _dev_ports, _dev_servers, _save_ports, _next_port,
            _write_files, wait_for_port, kill_server, _start_vite,
            _ensure_shared_nm_once, _link_shared_nm,
            _get_project_deps, _npm_install, _scan_imports_from_files,
            _bundle_api_server, _ensure_schema_sql, _api_ports, _next_api_port,
        )

        # ── API-first: ensure schema exists, bundle API server ────────────────
        files = _ensure_schema_sql(files)
        files = _bundle_api_server(files)

        port = _dev_ports.get(project_name) or _next_port()
        _dev_ports[project_name] = port

        # Assign API port if this project has an API server
        has_api_files = (
            "api/app_server.py" in files or "app_server.py" in files
            or "api_server.py" in files
            or "api/schema.sql" in files or "schema.sql" in files
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

        _progress("start")
        # Start API server if present
        if has_api_files and api_port:
            from agents.uigen_agent import _start_api_server, _api_servers
            import time as _time2
            _progress(f"llm_codegen:Starting API server on port {api_port}…")
            api_proc = _start_api_server(project_dir, api_port=api_port)
            if api_proc:
                _api_servers[project_name] = api_proc
                _time2.sleep(2)

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
    loop = asyncio.get_event_loop()
    try:
        if req.architecture:
            # Pre-approved draft → use the multi-agent pipeline with selective regeneration
            result = await loop.run_in_executor(
                _executor, _run_refine_with_architecture, project_name, req, request_id
            )
        else:
            result = await loop.run_in_executor(
                _executor, _run_refine, project_name, req.prompt, request_id, req.comment, req.instructions
            )
        result["requestId"] = request_id
        return result
    except Exception as e:
        import traceback
        detail = f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1500:]}"
        print(f"\n[REFINE ERROR]\n{detail}\n")
        raise HTTPException(500, detail)
    finally:
        async def _cleanup():
            await asyncio.sleep(60)
            _progress_logs.pop(request_id, None)
        asyncio.create_task(_cleanup())


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

    from agents.uigen_agent import generate_project

    instructions = (req.instructions or "").strip()
    user_content = req.prompt
    if instructions:
        user_content = f"{req.prompt}\n\n## Detailed Instructions\n\n{instructions}"

    result = generate_project(
        user_content,
        progress=_progress,
        project_name_override=project_name,
        architecture=req.architecture,
    )

    _progress("ready")
    _append_history(project_name, "Refined (pipeline)", detail=req.prompt[:200],
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
    """Poll current generation progress without needing a request ID."""
    return {"id": _latest_request_id, "log": _progress_logs.get(_latest_request_id, [])}


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


@app.post("/api/generate")
async def api_generate(req: GenerateRequest):
    global _latest_request_id
    import uuid
    request_id = uuid.uuid4().hex
    _progress_logs[request_id] = []
    _latest_request_id = request_id   # set BEFORE spawning so poll can start immediately
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(_executor, _run_generate, req, request_id)
        result["requestId"] = request_id
        return result
    except Exception as e:
        import traceback
        detail = f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1500:]}"
        print(f"\n[ERROR /api/generate]\n{detail}\n")
        raise HTTPException(500, detail)
    finally:
        async def _cleanup():
            await asyncio.sleep(60)
            _progress_logs.pop(request_id, None)
        asyncio.create_task(_cleanup())


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

def _dispatch_delete(project_name: str):
    from agents.figma_to_web_using_playwright_agent import is_figma_project, kill_figma_server
    if is_figma_project(project_name):
        kill_figma_server(project_name, forget_port=True)
    delete_project(project_name)
    registry_remove(project_name)


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
    from agents.docker_agent import build_image, get_status

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
    _dispatch_delete(project_name)
    return {"deleted": project_name}


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
  pres.author = opts.author || 'AutoPulse Global'
  pres.company = 'AutoPulse Global'
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
    slide.addText('AutoPulse Global', { x: 0.4, y: 7.0, w: 6, h: 0.3, fontSize: 9, color: '9CA3AF', fontFace: 'Arial' })
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
    subtitle: 'AI Concierge Insight',
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
        # (the LLM might use forecastData without importing it from a data submodule)
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
    port = _resolve_vite_port(project_name)
    if not port:
        # Auto-start the project if it has a registered port but process isn't running
        port = await _auto_start_project(project_name)
        if not port:
            raise HTTPException(503, "Project not running")
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
        # Connection refused — Vite server died. Try to auto-start once.
        port = await _auto_start_project(project_name)
        if not port:
            raise HTTPException(502, "Proxy error: " + str(e))
        # Retry the request after auto-start
        base_url = "http://127.0.0.1:" + str(port) + "/app/" + project_name + "/"
        target = _safe_proxy_url(base_url, path, str(request.query_params))
        try:
            http_req = _ureq.Request(target, data=body or None,
                                      method=request.method, headers=fwd_headers)
            with _ureq.urlopen(http_req, timeout=proxy_timeout) as resp:
                content = resp.read()
                headers = {k: v for k, v in resp.headers.items()
                           if k.lower() not in ("transfer-encoding", "connection", "keep-alive")}
                return Response(content=content, status_code=resp.status,
                                headers=headers, media_type=resp.headers.get("content-type"))
        except Exception as e2:
            raise HTTPException(502, "Proxy error after auto-start: " + str(e2))
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

# Web apps live in WebUIGenerator/generated/ (config already loaded from WebUIGenerator)
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
