"""
Tech L&D Agent's own FastAPI router -- generates and persists Learning &
Development / POC documentation for a typed topic. Mounted into the main
app by API/server.py under prefix "/land-d", same pattern as ContentAgents'
own router (see ContentAgents/ui/server.py).

Generation runs in a background thread and is polled (GET .../runs/{run_id}
/status), not awaited inline in the route -- same reasoning as
ContentAgents' LIBRARY_ITEM_RUNS: an LLM call inside an `async def` route
would block this whole process's single-threaded event loop for every other
request until it finished.
"""

import json
import shutil
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse

LAND_D_DIR = Path(__file__).resolve().parent
LIBRARY_DIR = LAND_D_DIR / "library"
LIBRARY_DIR.mkdir(exist_ok=True)

if str(LAND_D_DIR) not in sys.path:
    sys.path.insert(0, str(LAND_D_DIR))
from run import PERSONAS, generate_content  # noqa: E402

_CONTENT_AGENTS_DIR = LAND_D_DIR.parent / "ContentAgents"
if str(_CONTENT_AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_CONTENT_AGENTS_DIR))
from common.claude_cli import ClaudeCliError  # noqa: E402

router = APIRouter()

# run_id -> {"status": "running"|"complete"|"error", "log": [...], "result": {...}|None, "error": str|None}
# Same shape/reasoning as ContentAgents' LIBRARY_ITEM_RUNS.
RUNS: dict[str, dict] = {}


def _append_log(run_id: str, line: str) -> None:
    run = RUNS.get(run_id)
    if run is not None:
        run["log"].append(line)


def _item_dir(item_id: str) -> Path:
    d = LIBRARY_DIR / item_id
    if not d.exists():
        raise HTTPException(404, "Unknown L&D item")
    return d


def _read_item(item_id: str) -> dict:
    item_dir = _item_dir(item_id)
    info = json.loads((item_dir / "item.json").read_text(encoding="utf-8"))
    content = (item_dir / "content.md").read_text(encoding="utf-8")
    return {**info, "content": content}


def _run_generate_job(run_id: str, item_id: str, topic: str, persona: str, instructions: str) -> None:
    """Runs in a background thread -- writes a brand-new item's folder only
    once generation actually succeeds, so a failed first generation never
    leaves a half-created item behind for the list route to show."""
    run = RUNS[run_id]
    on_progress = lambda line: _append_log(run_id, line)  # noqa: E731
    try:
        content = generate_content(topic, persona, instructions, on_progress=on_progress)
        item_dir = LIBRARY_DIR / item_id
        item_dir.mkdir(parents=True)
        info = {
            "item_id": item_id,
            "title": topic.strip()[:80] or "Untitled",
            "topic": topic,
            "persona": persona,
            "instructions": instructions,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        (item_dir / "item.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
        (item_dir / "content.md").write_text(content, encoding="utf-8")
        run["result"] = {**info, "content": content}
        run["status"] = "complete"
    except ClaudeCliError as exc:
        run["error"] = str(exc)
        run["status"] = "error"
    except Exception as exc:
        run["error"] = str(exc)
        run["status"] = "error"


def _run_regenerate_job(run_id: str, item_id: str) -> None:
    """Re-runs generate_content() using whatever topic/persona/instructions
    are CURRENTLY saved on this item (edit those via PUT .../input first,
    same two-step pattern as video_creator's rerender-from-JSON flow)."""
    run = RUNS[run_id]
    on_progress = lambda line: _append_log(run_id, line)  # noqa: E731
    try:
        item_dir = _item_dir(item_id)
        info = json.loads((item_dir / "item.json").read_text(encoding="utf-8"))
        content = generate_content(
            info["topic"], info["persona"], info.get("instructions", ""), on_progress=on_progress,
        )
        (item_dir / "content.md").write_text(content, encoding="utf-8")
        run["result"] = {**info, "content": content}
        run["status"] = "complete"
    except ClaudeCliError as exc:
        run["error"] = str(exc)
        run["status"] = "error"
    except Exception as exc:
        run["error"] = str(exc)
        run["status"] = "error"


@router.get("/api/personas")
async def list_personas():
    return JSONResponse({
        "personas": [{"id": pid, "label": p["label"], "description": p["description"]} for pid, p in PERSONAS.items()],
    })


@router.post("/api/items")
async def create_item(topic: str = Form(...), persona: str = Form(...), instructions: str = Form("")):
    if not topic.strip():
        raise HTTPException(400, "A topic is required.")
    if persona not in PERSONAS:
        raise HTTPException(400, f"Unknown persona '{persona}'.")

    item_id = uuid.uuid4().hex[:12]
    run_id = uuid.uuid4().hex[:12]
    RUNS[run_id] = {"status": "running", "log": [], "result": None, "error": None}
    threading.Thread(
        target=_run_generate_job, daemon=True,
        args=(run_id, item_id, topic, persona, instructions),
    ).start()
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
            items.append(json.loads(info_path.read_text(encoding="utf-8")))
    items.sort(key=lambda it: it.get("created_at", ""), reverse=True)
    return JSONResponse({"items": items})


@router.get("/api/items/{item_id}")
async def get_item(item_id: str):
    return JSONResponse(_read_item(item_id))


@router.put("/api/items/{item_id}")
async def update_content(item_id: str, content: str = Form(...)):
    """Direct edit-and-save of the generated Markdown -- no LLM call at
    all, mirrors ContentAgents' library_update_metadata."""
    item_dir = _item_dir(item_id)
    (item_dir / "content.md").write_text(content, encoding="utf-8")
    return JSONResponse({"ok": True})


@router.put("/api/items/{item_id}/input")
async def update_input(item_id: str, topic: str = Form(...), persona: str = Form(...), instructions: str = Form("")):
    """Updates the saved topic/persona/instructions only -- call this right
    before POST .../regenerate, same two-step save-then-render pattern as
    video_creator's rerender-from-JSON flow."""
    if persona not in PERSONAS:
        raise HTTPException(400, f"Unknown persona '{persona}'.")
    item_dir = _item_dir(item_id)
    info = json.loads((item_dir / "item.json").read_text(encoding="utf-8"))
    info.update(topic=topic, persona=persona, instructions=instructions, title=topic.strip()[:80] or "Untitled")
    (item_dir / "item.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    return JSONResponse({"ok": True})


@router.post("/api/items/{item_id}/regenerate")
async def regenerate_item(item_id: str):
    _item_dir(item_id)  # 404s early if unknown, before spawning a thread
    run_id = uuid.uuid4().hex[:12]
    RUNS[run_id] = {"status": "running", "log": [], "result": None, "error": None}
    threading.Thread(target=_run_regenerate_job, daemon=True, args=(run_id, item_id)).start()
    return JSONResponse({"run_id": run_id})


@router.delete("/api/items/{item_id}")
async def delete_item(item_id: str):
    shutil.rmtree(_item_dir(item_id), ignore_errors=True)
    return JSONResponse({"ok": True})


@router.get("/api/items/{item_id}/download")
async def download_item(item_id: str):
    item_dir = _item_dir(item_id)
    info = json.loads((item_dir / "item.json").read_text(encoding="utf-8"))
    slug = "".join(c if c.isalnum() or c in "-_ " else "" for c in info.get("title", "ld-doc")).strip().replace(" ", "-") or "ld-doc"
    return FileResponse(item_dir / "content.md", filename=f"{slug}.md", media_type="text/markdown")
