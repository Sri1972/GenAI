"""
Brainstorming roundtable endpoints (Phase C).

SSE stream of the ported meeting engine (agents/roundtable), scoped to a project. A meeting
is created, then its `run()` async generator is streamed to the browser as text/event-stream;
control endpoints (interject / hold / wrap_up) act on the live Meeting via a server-side registry.

Mounted on the main app via `app.include_router(roundtable_router)`.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel

from agents import projects as store
from agents.roundtable import turbo
from agents.roundtable import agendas
from agents.roundtable.workspace import meetings as list_meetings_on_disk

roundtable_router = APIRouter(prefix="/api/roundtable", tags=["roundtable"])


# ── in-process registry of live meetings ───────────────────────────────────────

class MeetingSession:
    def __init__(self, project: str, meeting, topic: str, people: list[str]):
        self.project = project
        self.meeting = meeting
        self.topic = topic
        self.people = people
        self.started = False
        self.done = False
        self.recap: dict | None = None


_MEETINGS: dict[str, MeetingSession] = {}


def _key(project: str, mid: str) -> str:
    return f"{project}::{mid}"


def _session_or_404(project: str, mid: str) -> MeetingSession:
    s = _MEETINGS.get(_key(store.slugify(project), mid))
    if s is None:
        raise HTTPException(status_code=404, detail="Meeting not found (create it first).")
    return s


# ── request models ──────────────────────────────────────────────────────────────

class CreateMeetingRequest(BaseModel):
    topic: str
    people: list[str]
    duration_minutes: int = 12
    turn_order: str = "open"
    diagram: bool = True
    provider: str | None = None
    mode: str = "collaborate"   # 'collaborate' | 'autopilot'
    agenda: list[str] = []      # bucket names the Chair organizes the recap into
    architecture: str = "classic"   # 'classic' | 'debate' (A/B toggle for the engine)


class InterjectRequest(BaseModel):
    text: str
    target: str = "all"


class HoldRequest(BaseModel):
    paused: bool = True


# ── event serialization ─────────────────────────────────────────────────────────

def _asdict(x):
    return dataclasses.asdict(x) if dataclasses.is_dataclass(x) else x


def _serialize(project: str, mid: str, ev: dict) -> dict:
    ev = dict(ev)
    t = ev.get("type")
    if "turn" in ev and hasattr(ev["turn"], "to_dict"):
        ev["turn"] = ev["turn"].to_dict()
    if "item" in ev:
        ev["item"] = _asdict(ev["item"])
    if t in ("diagram", "deck"):
        p = ev.pop("path", None)
        name = Path(p).name if p else None
        ev["file"] = name
        if t == "diagram" and name:
            ev["url"] = f"/api/roundtable/{project}/meetings/{mid}/artifact/{name}"
    if t == "done":
        st = ev.pop("state", None)
        if st is not None:
            ev["summary"] = {
                "turns": len(st.turns), "agreed": len(st.agreed), "elapsed": st.elapsed,
            }
    return ev


def _sse(d: dict) -> str:
    return f"data: {json.dumps(d)}\n\n"


# ── endpoints ────────────────────────────────────────────────────────────────────

@roundtable_router.get("/personas")
def personas():
    return JSONResponse(turbo.available_personas())


@roundtable_router.get("/agenda-templates")
def agenda_templates():
    return JSONResponse(agendas.templates())


@roundtable_router.post("/{project}/meetings")
def create_meeting(project: str, req: CreateMeetingRequest):
    slug = store.slugify(project)
    if not store.exists(slug):
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found.")
    if not (req.topic or "").strip():
        raise HTTPException(status_code=400, detail="Tell them what you need to work out.")
    if len(req.people) < 2:
        raise HTTPException(status_code=400, detail="You need at least two people in the room.")
    meeting = turbo.build_meeting(
        project=slug, topic=req.topic.strip(), people=req.people,
        duration_minutes=req.duration_minutes, turn_order=req.turn_order,
        diagram=req.diagram, provider=req.provider, mode=req.mode, agenda=req.agenda,
        architecture=req.architecture,
    )
    mid = meeting.meeting_id
    _MEETINGS[_key(slug, mid)] = MeetingSession(slug, meeting, req.topic.strip(), req.people)
    return JSONResponse(
        {"meetingId": mid, "topic": req.topic.strip(), "people": req.people}, status_code=201)


@roundtable_router.post("/{project}/meetings/{mid}/stream")
async def stream(project: str, mid: str):
    sess = _session_or_404(project, mid)
    if sess.started:
        raise HTTPException(status_code=409, detail="This meeting is already streaming.")
    sess.started = True

    async def gen():
        # Drive the meeting generator with a heartbeat: during a checkpoint pause (or a slow
        # persona turn) no events flow, and an idle SSE connection can be dropped — which would
        # cancel the whole meeting. We wait on the next event with a timeout WITHOUT cancelling
        # it (asyncio.wait leaves the pending task alone), and emit an SSE keepalive comment on
        # timeout so the connection stays warm and the meeting keeps running.
        agen = sess.meeting.run().__aiter__()
        pending = asyncio.ensure_future(agen.__anext__())
        try:
            while True:
                done, _ = await asyncio.wait({pending}, timeout=15)
                if not done:
                    yield ": keepalive\n\n"
                    continue
                try:
                    ev = pending.result()
                except StopAsyncIteration:
                    break
                pending = asyncio.ensure_future(agen.__anext__())
                if ev.get("type") == "recap":
                    sess.recap = ev.get("recap")   # keep for on-demand / regenerate
                    try:
                        store.record_decision(sess.project, mid, sess.topic, sess.recap or {})
                    except Exception:
                        pass
                yield _sse(_serialize(sess.project, mid, ev))
        except Exception as e:  # last-resort guard
            import traceback
            traceback.print_exc()   # so mid-meeting failures are diagnosable in server.log
            yield _sse({"type": "error", "error": f"{type(e).__name__}: {e}"})
        finally:
            if not pending.done():
                pending.cancel()
            try:
                await agen.aclose()   # run the meeting's cleanup (disconnect personas)
            except Exception:
                pass
            sess.done = True

    return StreamingResponse(
        gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@roundtable_router.post("/{project}/meetings/{mid}/interject")
def interject(project: str, mid: str, req: InterjectRequest):
    sess = _session_or_404(project, mid)
    sess.meeting.interject(req.text, req.target)
    return JSONResponse({"status": "queued", "target": req.target})


@roundtable_router.post("/{project}/meetings/{mid}/hold")
def hold(project: str, mid: str, req: HoldRequest):
    sess = _session_or_404(project, mid)
    sess.meeting.hold(req.paused)
    return JSONResponse({"status": "paused" if req.paused else "resumed"})


@roundtable_router.post("/{project}/meetings/{mid}/wrap_up")
def wrap_up(project: str, mid: str):
    sess = _session_or_404(project, mid)
    sess.meeting.wrap_up()
    return JSONResponse({"status": "wrapping up"})


@roundtable_router.post("/{project}/meetings/{mid}/continue")
def continue_meeting(project: str, mid: str):
    """Release a collaborate-mode checkpoint (the user chose to continue without steering)."""
    sess = _session_or_404(project, mid)
    sess.meeting.resume()
    return JSONResponse({"status": "resumed"})


@roundtable_router.get("/{project}/meetings")
def list_meetings(project: str):
    slug = store.slugify(project)
    if not store.exists(slug):
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found.")
    return JSONResponse(list_meetings_on_disk(store.roundtable_dir(slug)))


def _minute_body(md: str) -> str:
    """Strip a minute file's markdown scaffolding (# byline, _why_, > reasoning) → the said text."""
    keep = [
        ln for ln in md.splitlines()
        if ln.strip() and not ln.startswith("#") and not ln.startswith(">")
        and not (ln.startswith("_") and ln.rstrip().endswith("_"))
    ]
    return "\n".join(keep).strip()


def _brief_topic(base) -> str:
    brief = base / "shared" / "brief.md"
    if not brief.exists():
        return ""
    parts = brief.read_text(encoding="utf-8").split("\n\n")
    return parts[1].strip() if len(parts) > 1 else ""


@roundtable_router.get("/{project}/meetings/{mid}")
def get_meeting(project: str, mid: str):
    """A past meeting for the history panel: the full transcript if it finished, else the
    turns reconstructed from the per-turn minutes (best-effort) for an unfinished one."""
    slug = store.slugify(project)
    base = store.roundtable_dir(slug) / mid
    if not base.is_dir():
        raise HTTPException(status_code=404, detail="Meeting not found.")

    tx = base / "shared" / "transcript.json"
    if tx.exists():
        try:
            data = json.loads(tx.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        return JSONResponse({
            "id": mid, "complete": True,
            "topic": data.get("topic", "").split("\n\n")[0],
            "people": data.get("people", []),
            "turns": data.get("turns", []),
            "agreed": data.get("agreed", []),
            "recap": data.get("recap"),
            "usage": data.get("usage"),
        })

    minutes = base / "shared" / "minutes"
    turns = []
    if minutes.is_dir():
        for f in sorted(minutes.glob("*.md")):
            who = f.stem.split("-", 1)[1] if "-" in f.stem else f.stem
            try:
                turns.append({"who": who, "text": _minute_body(f.read_text(encoding="utf-8"))})
            except OSError:
                continue
    return JSONResponse({
        "id": mid, "complete": False, "topic": _brief_topic(base),
        "people": [], "turns": turns, "agreed": [], "recap": None,
    })


@roundtable_router.get("/{project}/meetings/{mid}/artifact/{name}")
def artifact(project: str, mid: str, name: str):
    slug = store.slugify(project)
    f = store.roundtable_dir(slug) / mid / "shared" / Path(name).name
    if not f.exists() or not f.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return HTMLResponse(f.read_text(encoding="utf-8"))


@roundtable_router.post("/{project}/meetings/{mid}/diagram")
async def draw_diagram(project: str, mid: str):
    """Draw (or re-draw) the meeting's diagram on demand — 'Draw this up' / 'Draw again'."""
    sess = _session_or_404(project, mid)
    if not sess.recap:
        raise HTTPException(status_code=400, detail="Let the meeting reach a recap first.")
    from agents.roundtable import chair as chair_mod
    m = sess.meeting
    path, detail = await chair_mod.build_diagram(
        sess.recap, m.state.turns, m.workspace, sess.topic,
        m.config.coordinator_model, m.config.recap_model, m.config.skill_pack,
        env=m.env, force=True,
    )
    if not path:
        return JSONResponse({"file": None, "detail": detail})
    name = Path(path).name
    return JSONResponse({
        "file": name, "detail": detail,
        "url": f"/api/roundtable/{sess.project}/meetings/{mid}/artifact/{name}",
    })


@roundtable_router.post("/{project}/meetings/{mid}/artifact/{name}/promote")
def promote_artifact(project: str, mid: str, name: str):
    """Approve a diagram: copy it into the project's shared artifacts/ dir."""
    import shutil
    slug = store.slugify(project)
    src = store.roundtable_dir(slug) / mid / "shared" / Path(name).name
    if not src.exists():
        raise HTTPException(status_code=404, detail="Artifact not found.")
    dst_dir = store.artifacts_dir(slug) / "diagrams"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / f"{mid}-{Path(name).name}"
    shutil.copy2(src, dst)
    store.touch(slug)
    return JSONResponse({"status": "approved", "artifact": f"diagrams/{dst.name}"})
