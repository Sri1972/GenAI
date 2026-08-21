"""TurboUIGen integration for the roundtable engine (Phase C).

Bridges the ported meeting engine to the unified project workspace:
- meetings live under projects/<project>/roundtable/<meeting-id>/
- the project's read-only inputs/ are mounted into every persona (add_dirs)
- model + env routing goes through TurboUIGen's sdk_env (local / litellm / bedrock)
- the optional diagram is drawn with the vendored diagram-design skill

The engine core (meeting/coordinator/personas/chair/agent/workspace) is unchanged except
for the small `read_dirs` threading and the chair's diagram swap.
"""

from __future__ import annotations

from typing import Optional

from agents import projects as project_store
from agents import sdk_env
from agents.dataset_mcp import build_dataset_server

from .meeting import Meeting
from .types import MeetingConfig
from .personas import PERSONAS, CHAIR
from .workspace import new_meeting_id
from .agendas import DEFAULT_BUCKETS


def available_personas() -> list[dict]:
    """The roster for the setup screen: id, name, role, hue, one-line 'knows'."""
    out = []
    for pid, p in PERSONAS.items():
        out.append({
            "id": pid, "name": p.name, "role": p.role, "hue": p.hue,
            "knows": getattr(p, "knows", "") or "",
        })
    return out


# Only small text files are safe to instruct a persona to Read wholesale. A large CSV/binary
# read raw would blow the model's context window and kill the meeting — those belong to the
# app builder, not the discussion.
_READABLE_EXT = {".md", ".txt", ".json", ".yaml", ".yml", ".tsv", ".csv", ".log"}
_MAX_READABLE = 200 * 1024  # 200 KB


def _reference_note(project: str) -> tuple[str, tuple[str, ...]]:
    """A prose note pointing at the project's shared context, plus the dirs to grant read
    access to (inputs + prior artifacts + brief via the project root).

    Size-aware: only small text files are offered as "read these"; large or binary files are
    named but flagged as NOT to be read into the discussion (they're for the app builder).
    """
    from pathlib import Path
    root = project_store.project_dir(project)
    inputs = project_store.inputs_dir(project)
    brief = root / "brief.md"
    decisions = project_store.artifacts_dir(project) / "decisions"

    readable, heavy = [], []
    for i in project_store.list_inputs(project):
        name, size = i["name"], i.get("size", 0)
        ext = Path(name).suffix.lower()
        if ext in _READABLE_EXT and size <= _MAX_READABLE:
            readable.append(name)
        else:
            kind = "image" if ext in (".png", ".jpg", ".jpeg", ".webp", ".gif") else "large dataset/file"
            heavy.append(f"{name} ({kind}, {size // 1024} KB)")

    parts = []
    if readable:
        parts.append(
            f"Reference materials (read-only) are in {inputs} — read these if relevant to your "
            f"perspective and cite what you actually read: {', '.join(readable)}."
        )
    if heavy:
        parts.append(
            "The project also holds larger data files — NEVER Read these whole (they'd overflow "
            "your context). To reason from them, use the dataset tools: "
            "mcp__dataset__profile_dataset (columns + stats), mcp__dataset__sample_dataset (a few "
            "rows), and mcp__dataset__run_sql (DuckDB SQL over the file — aggregations/filters). "
            f"Cite real numbers you pull rather than guessing. Files: {', '.join(heavy)}."
        )
    if brief.exists():
        parts.append(f"The project brief (what's been decided so far) is at {brief} — read it "
                     "so you build on prior decisions rather than re-litigating them.")
    if decisions.exists() and any(decisions.glob("*.md")):
        parts.append(f"Earlier decisions from past meetings are in {decisions}.")
    if not parts:
        return "", ()
    return "\n\n" + " ".join(parts), (str(root),)


def build_meeting(
    *,
    project: str,
    topic: str,
    people: list[str],
    duration_minutes: int = 12,
    turn_order: str = "open",
    max_turns: Optional[int] = None,
    diagram: bool = True,
    provider: Optional[str] = None,
    meeting_id: Optional[str] = None,
    mode: str = "collaborate",
    agenda: Optional[list[str]] = None,
    architecture: str = "classic",
):
    """Construct a project-scoped Meeting ready to run().

    mode: 'collaborate' (personas ask the user + Chair checkpoints at halfway/pre-recap) or
    'autopilot' (run start→finish, user reviews at the end; interjection still allowed).
    """
    provider = sdk_env.resolve_provider(provider)
    # The duration slider now drives the real length: ~1.2 substantive turns per
    # minute, clamped so a short meeting still holds a real discussion + a close
    # and a long one can't run away with the token budget. Callers (CLI) may
    # still pin max_turns explicitly.
    if max_turns is None:
        max_turns = max(8, min(40, round(duration_minutes * 1.2)))
    collaborate = mode != "autopilot"
    env = sdk_env.cli_env_for(provider)
    model = sdk_env.model_for(provider)  # 'sonnet' for local; the pinned id otherwise

    note, read_dirs = _reference_note(project)
    # Prep runs only when there's material to research — reference files, a
    # dataset, or a brief/prior decisions. read_dirs is non-empty in exactly
    # those cases (_reference_note returns () when there's nothing to point at).
    has_material = bool(read_dirs)
    buckets = [b for b in (agenda or []) if b.strip()] or list(DEFAULT_BUCKETS)
    # Light frame so the room loosely covers the agenda; the Chair organizes the recap by it.
    agenda_note = "\n\nThe agenda for this meeting (cover these): " + "; ".join(buckets) + "."

    cfg_kwargs = dict(
        topic=topic + agenda_note + note,
        agenda=buckets,
        people=people,
        duration_minutes=duration_minutes,
        turn_order=turn_order,
        max_turns=max_turns,
        diagram=diagram,
        workspace_root=str(project_store.roundtable_dir(project)),
        questions=collaborate,     # collaborate: personas may ask the user directly
        checkpoints=collaborate,   # collaborate: Chair pauses at milestones to confirm direction
    )
    if has_material:
        # Homework needs room for a couple of tool calls (read a ref, query the
        # dataset) on top of the reply itself; the reactive turns stay short by
        # prompt, not by budget, so this only widens the tool ceiling.
        cfg_kwargs["agent_turns"] = 14
    if model:  # route every model through the selected provider's model
        cfg_kwargs["models"] = {pid: model for pid in people}
        cfg_kwargs["coordinator_model"] = model
        cfg_kwargs["recap_model"] = model

    cfg = MeetingConfig(**cfg_kwargs)
    # Derive the meeting-id from the CLEAN topic (not the appended reference note).
    mid = meeting_id or new_meeting_id(topic)
    # In-process DuckDB dataset tools, scoped to the project root so relative paths resolve.
    dataset_server = build_dataset_server(project_store.project_dir(project))
    if architecture == "debate":
        from .debate import DebateMeeting
        return DebateMeeting(cfg, meeting_id=mid, env=env, read_dirs=read_dirs,
                             dataset_server=dataset_server)
    return Meeting(cfg, meeting_id=mid, env=env, read_dirs=read_dirs,
                   dataset_server=dataset_server, prep=has_material)
