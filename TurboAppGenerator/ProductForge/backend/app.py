"""
Product Forge API routes — orchestrates agent collaboration.

An APIRouter, not its own FastAPI app: this is included directly into
TurboAppGenerator's own server.py under the /api/forge prefix (one process,
one port, one OpenAPI schema), not run as a separate app on its own port —
see server.py's own comment for why. No CORS middleware here for the same
reason: middleware is an app-level concept, and everything reaching this
router is already same-origin by construction. The frontend page itself
(a single static index.html) is served by server.py directly from
UI/public/forge/, not from here — see server.py's _forge_index.

Supports SSE streaming for real-time agent responses. Persists sessions to
disk so projects can be resumed and browsed.
"""

import asyncio
import json
import queue
import threading

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from orchestrator import ForgeSession, load_config, list_tech_stack_profiles

router = APIRouter()

# Active sessions (in-memory, also persisted to disk)
sessions: dict[str, ForgeSession] = {}
# SSE event queues per session
event_queues: dict[str, list[queue.Queue]] = {}


def broadcast_event(session_id: str, event: dict):
    """Send an event to all SSE subscribers for this session."""
    if session_id in event_queues:
        for q in event_queues[session_id]:
            q.put(event)


class StartRequest(BaseModel):
    name: str | None = None
    idea: str
    session_id: str | None = None
    draft_mode: bool = False
    tech_profile: str | None = None


class StageRequest(BaseModel):
    session_id: str


class RunFromStageRequest(BaseModel):
    session_id: str
    stage_idx: int


class RunSelectedRequest(BaseModel):
    session_id: str
    stage_ids: list[str]


class UpdateArtifactRequest(BaseModel):
    session_id: str
    artifact_name: str
    content: str


class UploadContextRequest(BaseModel):
    session_id: str
    name: str
    content: str


class StageParticipantsRequest(BaseModel):
    session_id: str
    stage_id: str
    agent_ids: list[str]


@router.post("/api/start")
async def start_session(req: StartRequest):
    """Start a new product forge session."""
    session = ForgeSession(
        req.idea, session_id=req.session_id, project_name=req.name,
        draft_mode=req.draft_mode, tech_profile=req.tech_profile,
    )
    sessions[session.session_id] = session
    event_queues[session.session_id] = []
    session.on_message = lambda evt: broadcast_event(session.session_id, evt)
    return {"session_id": session.session_id, "state": session.get_state()}


@router.get("/api/tech-profiles")
async def get_tech_profiles():
    """List available tech-stack guardrail profiles, for the new-project UI."""
    from orchestrator import load_tech_stack_guardrails
    config = load_tech_stack_guardrails()
    return {
        "profiles": list_tech_stack_profiles(),
        "default_profile": config.get("default_profile") if config else None,
    }


@router.get("/api/draft-model")
async def get_draft_model():
    """Which model Draft Mode would actually use right now (cheapest reachable
    one), for the new-project UI — before any session (and thus any per-run
    choice in get_state()) exists yet."""
    from agents.llm import pick_cheapest_reachable_model
    return pick_cheapest_reachable_model()


@router.post("/api/stage-participants")
async def set_stage_participants(req: StageParticipantsRequest):
    """Override one stage's agent roster for this session — only while that
    stage is still pending. Defaults live in agents.json; this never touches
    them, so every other session is unaffected."""
    session = sessions.get(req.session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)
    ok, message = session.set_stage_participants(req.stage_id, req.agent_ids)
    if not ok:
        return JSONResponse({"error": message}, status_code=400)
    return {"message": message, "state": session.get_state()}


@router.post("/api/run-stage")
async def run_stage(req: StageRequest):
    """Run the next stage in background, stream results via SSE."""
    session = sessions.get(req.session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)
    if session.status == "complete":
        return JSONResponse({"error": "Session already complete"}, status_code=400)
    if session.status == "running":
        return JSONResponse({"error": "Stage already running"}, status_code=409)

    def run_in_bg():
        session.run_stage()
        broadcast_event(req.session_id, {"type": "stage_done", "state": session.get_state()})

    thread = threading.Thread(target=run_in_bg, daemon=True)
    thread.start()
    return {"message": "Stage started", "state": session.get_state()}


@router.post("/api/run-all")
async def run_all(req: StageRequest):
    """Run all remaining stages in background."""
    session = sessions.get(req.session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)
    if session.status == "running":
        return JSONResponse({"error": "Already running"}, status_code=409)

    def run_in_bg():
        remaining = range(session.current_stage_idx, len(session.stages))
        for i in remaining:
            session.run_stage(i)
            if session.status == "cancelled":
                break
        else:
            session.status = "complete"
        broadcast_event(req.session_id, {"type": "forge_done", "state": session.get_state()})

    thread = threading.Thread(target=run_in_bg, daemon=True)
    thread.start()
    return {"message": "Running all stages", "state": session.get_state()}


@router.post("/api/run-selected")
async def run_selected(req: RunSelectedRequest):
    """Run remaining stages, generating only the selected artifacts (in pipeline order).

    Any artifact-producing stage not listed in stage_ids is skipped entirely — no
    discussion, no LLM calls, no file written. Non-artifact stages (e.g. ideation)
    always run.
    """
    session = sessions.get(req.session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)
    if session.status == "running":
        return JSONResponse({"error": "Already running"}, status_code=409)

    def run_in_bg():
        session.run_selected(req.stage_ids)
        broadcast_event(req.session_id, {"type": "forge_done", "state": session.get_state()})

    thread = threading.Thread(target=run_in_bg, daemon=True)
    thread.start()
    return {"message": "Running selected stages", "state": session.get_state()}


@router.post("/api/upgrade-quality")
async def upgrade_quality(req: StageRequest):
    """Upgrade a draft session to quality — runs critique-and-refine on all existing artifacts."""
    session = sessions.get(req.session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)
    if session.status == "running":
        return JSONResponse({"error": "Already running"}, status_code=409)
    if not session.draft_mode:
        return JSONResponse({"error": "Session is already in quality mode"}, status_code=400)

    def run_in_bg():
        session.upgrade_to_quality()
        broadcast_event(req.session_id, {"type": "forge_done", "state": session.get_state()})

    thread = threading.Thread(target=run_in_bg, daemon=True)
    thread.start()
    return {"message": "Upgrading to quality mode", "state": session.get_state()}


@router.post("/api/run-from-stage")
async def run_from_stage(req: RunFromStageRequest):
    """Run from a specific stage onwards (clears downstream artifacts/messages)."""
    session = sessions.get(req.session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)
    if session.status == "running":
        return JSONResponse({"error": "Already running"}, status_code=409)
    if req.stage_idx < 0 or req.stage_idx >= len(session.stages):
        return JSONResponse({"error": "Invalid stage index"}, status_code=400)

    def run_in_bg():
        session.run_from_stage(req.stage_idx)
        broadcast_event(req.session_id, {"type": "forge_done", "state": session.get_state()})

    thread = threading.Thread(target=run_in_bg, daemon=True)
    thread.start()
    return {"message": f"Running from stage {req.stage_idx}", "state": session.get_state()}


@router.post("/api/cancel")
async def cancel_run(req: StageRequest):
    """Request cooperative cancellation of whatever's running for this session.

    Takes effect at the next safe checkpoint (between agent turns or stages) in
    whichever background thread run-stage/run-all/run-selected/run-from-stage/
    upgrade-quality started — not immediately, since an LLM call already in
    flight isn't interrupted. The UI's Stop button should treat this as
    "stopping…" until the SSE stream reports status "cancelled".
    """
    session = sessions.get(req.session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)
    if session.status != "running":
        return JSONResponse({"error": "Nothing is currently running for this session"}, status_code=400)
    session.request_cancel()
    return {"message": "Cancellation requested", "state": session.get_state()}


@router.post("/api/update-artifact")
async def update_artifact(req: UpdateArtifactRequest):
    """Update an artifact's content (user edited it)."""
    session = sessions.get(req.session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)
    session.update_artifact(req.artifact_name, req.content)
    return {"message": "Artifact updated", "artifact_name": req.artifact_name}


@router.post("/api/upload-context")
async def upload_context(req: UploadContextRequest):
    """Upload a context document to be included in future stage generation."""
    session = sessions.get(req.session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)
    session.add_context_document(req.name, req.content)
    return {"message": "Context uploaded", "name": req.name}


@router.get("/api/stream/{session_id}")
async def stream_events(session_id: str):
    """SSE endpoint — streams events in real-time as agents work."""
    if session_id not in event_queues:
        return JSONResponse({"error": "Session not found"}, status_code=404)

    q = queue.Queue()
    event_queues[session_id].append(q)

    async def event_generator():
        try:
            while True:
                sent = False
                while not q.empty():
                    try:
                        event = q.get_nowait()
                        yield f"data: {json.dumps(event, default=str)}\n\n"
                        sent = True
                    except queue.Empty:
                        break
                if not sent:
                    await asyncio.sleep(0.05)
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if session_id in event_queues and q in event_queues[session_id]:
                event_queues[session_id].remove(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/api/state/{session_id}")
async def get_state(session_id: str):
    """Get current session state."""
    session = sessions.get(session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)
    return session.get_state()


@router.get("/api/messages/{session_id}")
async def get_messages(session_id: str, since: int = 0):
    """Get conversation messages (optionally since a given index)."""
    session = sessions.get(session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)
    messages = session.conversation_log[since:]
    return {"messages": messages, "total": len(session.conversation_log)}


@router.get("/api/artifacts/{session_id}")
async def get_artifacts(session_id: str):
    """Get all generated artifacts."""
    session = sessions.get(session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)
    return {"artifacts": session.artifacts}


@router.get("/api/artifact/{session_id}/{name}")
async def get_artifact(session_id: str, name: str):
    """Get a specific artifact content."""
    session = sessions.get(session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)
    content = session.artifacts.get(name)
    if content is None:
        return JSONResponse({"error": f"Artifact '{name}' not found"}, status_code=404)
    return {"name": name, "content": content}


@router.get("/api/artifact/{session_id}/{name}/versions")
async def get_artifact_versions(session_id: str, name: str):
    """Get version history for a specific artifact."""
    session = sessions.get(session_id)
    if not session:
        session = ForgeSession.load_session(session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)
    versions = session.artifact_versions.get(name, [])
    return {"artifact_name": name, "versions": versions}


@router.get("/api/artifact/{session_id}/{name}/version/{version_num}")
async def get_artifact_version_content(session_id: str, name: str, version_num: int):
    """Get the content of a specific artifact version."""
    session = sessions.get(session_id)
    if not session:
        session = ForgeSession.load_session(session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)
    versions = session.artifact_versions.get(name, [])
    version = next((v for v in versions if v["version"] == version_num), None)
    if not version:
        return JSONResponse({"error": f"Version {version_num} not found"}, status_code=404)
    version_path = session.output_dir / "versions" / version["filename"]
    if not version_path.exists():
        return JSONResponse({"error": "Version file missing from disk"}, status_code=404)
    content = version_path.read_text(encoding="utf-8")
    return {"artifact_name": name, "version": version, "content": content}


@router.get("/api/config")
async def get_config():
    """Get agent and stage configuration."""
    return load_config()


@router.get("/api/sessions")
async def list_sessions():
    """List all active sessions (in-memory)."""
    return [session.get_state() for session in sessions.values()]


@router.get("/api/projects")
async def list_projects():
    """List all persisted projects/sessions from disk."""
    return ForgeSession.list_sessions()


@router.get("/api/project/{session_id}")
async def get_project(session_id: str):
    """Load a persisted project's full data."""
    # Check in-memory first
    session = sessions.get(session_id)
    if session:
        return {
            "state": session.get_state(),
            "messages": session.conversation_log,
            "artifacts": session.artifacts,
            "token_usage": session.token_usage,
        }
    # Load from disk
    session = ForgeSession.load_session(session_id)
    if not session:
        return JSONResponse({"error": "Project not found"}, status_code=404)
    return {
        "state": session.get_state(),
        "messages": session.conversation_log,
        "artifacts": session.artifacts,
        "token_usage": session.token_usage,
    }


@router.post("/api/project/{session_id}/resume")
async def resume_project(session_id: str):
    """Resume a previously saved project."""
    if session_id in sessions:
        return {"session_id": session_id, "state": sessions[session_id].get_state()}
    session = ForgeSession.load_session(session_id)
    if not session:
        return JSONResponse({"error": "Project not found"}, status_code=404)
    sessions[session_id] = session
    event_queues[session_id] = []
    session.on_message = lambda evt: broadcast_event(session_id, evt)
    return {"session_id": session_id, "state": session.get_state()}


@router.delete("/api/project/{session_id}")
async def delete_project(session_id: str):
    """Delete a project: removes session file, artifacts folder, and in-memory state."""
    import os
    import shutil
    import stat
    import time

    session = sessions.get(session_id)
    if not session:
        session = ForgeSession.load_session(session_id)
    if not session:
        return JSONResponse({"error": "Project not found"}, status_code=404)

    # Remove artifact directory (with Windows/OneDrive permission handling)
    if session.output_dir.exists():
        def force_remove(func, path, exc_info):
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
            func(path)

        try:
            shutil.rmtree(session.output_dir, onexc=force_remove)
        except Exception:
            # Retry once after a short delay (OneDrive may release locks)
            time.sleep(0.5)
            try:
                shutil.rmtree(session.output_dir, onexc=force_remove)
            except Exception as e:
                return JSONResponse(
                    {"error": f"Could not fully delete artifacts folder (OneDrive may be syncing). Try again in a few seconds. Detail: {e}"},
                    status_code=500
                )

    # Remove session file
    from orchestrator import SESSIONS_DIR
    session_file = SESSIONS_DIR / f"{session_id}.json"
    if session_file.exists():
        session_file.unlink()

    # Remove from in-memory state
    sessions.pop(session_id, None)
    event_queues.pop(session_id, None)

    return {"message": "Project deleted", "session_id": session_id}


@router.get("/api/usage/{session_id}")
async def get_usage(session_id: str):
    """Get token usage and cost breakdown for a session."""
    session = sessions.get(session_id)
    if not session:
        session = ForgeSession.load_session(session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)
    return session.token_usage


# ── External Integration Endpoints (consumed by TurboUIGen etc.) ─────────────

@router.get("/api/export/projects")
async def export_projects():
    """List all completed projects with artifact names — for external tools like TurboUIGen."""
    projects = ForgeSession.list_sessions()
    result = []
    for p in projects:
        if not p.get("artifacts"):
            continue
        result.append({
            "session_id": p["session_id"],
            "project_name": p.get("project_name", ""),
            "product_idea": p.get("product_idea", ""),
            "folder_name": p.get("folder_name", ""),
            "status": p.get("status", ""),
            "artifacts": p.get("artifacts", []),
            "created_at": p.get("created_at", ""),
            "updated_at": p.get("updated_at", ""),
        })
    return {"projects": result}


@router.get("/api/export/project/{session_id}")
async def export_project_artifacts(session_id: str):
    """Return full artifact content for a project — for external import."""
    session = sessions.get(session_id)
    if not session:
        session = ForgeSession.load_session(session_id)
    if not session:
        return JSONResponse({"error": "Project not found"}, status_code=404)

    artifacts_content = {}
    for name, content in session.artifacts.items():
        artifacts_content[name] = content

    return {
        "session_id": session.session_id,
        "project_name": session.project_name,
        "product_idea": session.product_idea,
        "artifacts": artifacts_content,
    }


