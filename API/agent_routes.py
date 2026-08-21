"""
Conversational agent SSE endpoints (Phase 4).

Mounted on the main FastAPI app via `app.include_router(agent_router)`.
Streams the SDK-native builder's events to the browser as text/event-stream.
"""

from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from agents.agent_session import SESSIONS

agent_router = APIRouter(prefix="/api/agent", tags=["agent"])


class MessageRequest(BaseModel):
    message: str
    provider: str | None = None
    mode: str | None = None   # 'collaborate' | 'autopilot'


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


@agent_router.post("/{project}/message")
async def agent_message(project: str, req: MessageRequest):
    """Stream one conversational turn (generate on first message, refine after)."""
    session = SESSIONS.get(project, provider=req.provider)

    async def gen():
        try:
            async for event in session.send_message_stream(req.message, mode=req.mode):
                yield _sse(event)
        except Exception as e:  # last-resort guard
            yield _sse({"type": "error", "error": f"{type(e).__name__}: {e}"})
            yield _sse({"type": "done", "session_id": session.session_id})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@agent_router.post("/{project}/open")
async def agent_open(project: str):
    """Reopen a project: link + start its Vite/API servers so the live preview works,
    without running an agent turn. Safe on an already-built app (no wipe/re-seed)."""
    session = SESSIONS.get(project)
    try:
        status = await session.ensure_serving()
        return JSONResponse(status)
    except Exception as e:
        return JSONResponse(
            {"project": project, "previewUrl": f"/app/{project}/", "running": False,
             "error": f"{type(e).__name__}: {e}"},
            status_code=200,
        )


@agent_router.post("/{project}/interrupt")
async def agent_interrupt(project: str):
    session = SESSIONS.get(project)
    await session.interrupt()
    return {"status": "interrupted"}


@agent_router.get("/{project}/status")
async def agent_status(project: str):
    session = SESSIONS.get(project)
    return JSONResponse(session.status())
