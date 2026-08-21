"""PersonaAgent — one Claude Agent SDK instance per colleague.

Each persona is a separate ``ClaudeSDKClient`` with its own subprocess, its own
system prompt, its own tool grant, its own private workspace and its own model.
They are differentiated on three independent axes:

    prompt      voice and point of view (stance / concession)
    tools+data  what they can actually look at
    workspace   where they can write

The middle one matters most. Personas that share tools and context converge —
you get one opinion in several voices. Give them genuinely different things to
look at and they disagree without being told to.

Sessions are persistent: connect once per meeting, send one message per turn.
Reconnecting per turn would spawn a CLI subprocess every time.
"""

from __future__ import annotations

from typing import Any, Callable

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from . import mcp as mcp_mod
from . import skills as skills_mod
from .structured import collect, usage_from_result
from .types import TURN_SCHEMA, Persona
from .workspace import Workspace

# Shared by every persona. The quality bar comes straight from the design
# handoff — these are the properties that separate a real discussion from
# agreeable mush.
_HOUSE_RULES = """\
You are in a working meeting with colleagues. You are not an assistant and \
you are not summarising — you are a participant with a job and a view.

How to speak:
- AT MOST 3 short sentences (~50 words). Spoken register, not written. No headings, no bullets.
- Make ONE sharp point per turn. If you're explaining three things, you're monologuing —
  pick the sharpest and stop. The others get their own turns; you don't have to pre-empt
  every objection in one breath.
- Say the thing. No preamble, no "great point", no restating what was said.
- Attach a number, a cost, or a specific observation whenever you can.
- Disagree when you disagree, and name who you are disagreeing with.
- When you concede, concede something SPECIFIC. "Good point" is not a concession.
- Never invent closure. If something is unresolved, leave it unresolved.
- You may refer to what you read, but describe it in plain language. Never \
mention tools, function calls, or filenames.

You will not always be the most important voice in the room. If the discussion \
has moved past your concern, say something short or hand it to someone better \
placed."""

# Sent when a persona finishes a turn without producing a payload — usually
# because it spent its turn budget reading. Deliberately blunt.
_RETRY_CUE = (
    "You didn't say anything. Stop looking things up and speak now, from what "
    "you already know. Two or three sentences."
)


# Each clause is opt-in from MeetingConfig so a room can be run with one on
# and one off. They are written as descriptions of how a good colleague works,
# not as rules to comply with -- an instruction to "always push back" produces
# manufactured conflict, which reads worse than agreement.
_BEHAVIOURS = {
    "independent_read": """\
Work out where you stand from what you know, before you weigh what anyone else \
has said. The view above is where you start, not a script: if someone gives you \
a better argument, move — and say plainly that you have moved, and what moved \
you. Agreeing because the room is agreeing is worth nothing to anyone.""",
    "strategic": """\
Think from your discipline, not only about this decision. What does this mean \
for your area in six months? What does it make harder later, what precedent \
does it set, what does it quietly rule out? Put that reasoning in your \
thinking; what you say out loud stays short and concrete.""",
    "questions": """\
If something you need is genuinely unclear — a constraint, a number, who this \
is for, what "done" means — ask the person who would know, rather than \
assuming and building on the assumption. One question at a time, and only when \
the answer would change what you say. If nobody in the room can answer it, ask \
the person who called the meeting.""",
    "devils_advocate": """\
If the room has settled on something quickly and you can see the strongest case \
against it, make that case — even when it is not your own position. Say that is \
what you are doing, so nobody mistakes it for your view.""",
}


def _system_prompt(
    p: Persona,
    topic: str,
    colleagues: list[Persona],
    behaviours: tuple[str, ...] = (),
) -> str:
    others = "\n".join(f"  - {c.name} — {c.knows}" for c in colleagues)
    how = "\n\n".join(_BEHAVIOURS[b] for b in behaviours if b in _BEHAVIOURS)
    how = f"\n\n{how}" if how else ""

    # Skills are this colleague's professional habits, not equipment. Framed
    # that way so they get applied rather than announced -- the house rules
    # already forbid naming tools, and "I used my triage skill" would read as
    # machinery in a transcript that is meant to sound like a room.
    habits = ""
    if p.skills:
        habits = (
            "\n\nHow you work:\n"
            "  You have professional habits written down — consult them when "
            "the situation calls for one, and apply them as your own judgement. "
            "Never mention that you consulted anything, and never name them.\n"
        )
    return f"""\
You are the {p.name} voice in this room. People address you as {p.name} — you \
speak for that discipline, not as a named individual.

What you know: {p.knows}

The view you hold and will defend:
  {p.stance}

The thing you will concede if pushed well, and only this:
  {p.concession}

You are meeting about:
  {topic}

Also in the room:
{others}
{habits}
{_HOUSE_RULES}{how}

Your private notes are in the working directory. The shared minutes are in \
./shared/minutes — read them to see what has already been said. You cannot \
write to the minutes; the Chair records the meeting."""


class PersonaAgent:
    """One colleague, backed by one SDK session."""

    def __init__(
        self,
        persona: Persona,
        workspace: Workspace,
        topic: str,
        colleagues: list[Persona],
        *,
        env: dict[str, str] | None = None,
        extra_mcp: dict[str, Any] | None = None,
        skill_pack: str | None = None,
        behaviours: tuple[str, ...] = (),
        turn_budget: int | None = None,
        read_dirs: tuple[str, ...] = (),
        dataset_server: Any = None,
        free_form: bool = False,
        actions_server: Any = None,
    ) -> None:
        self.persona = persona
        self.model = persona.model
        self.free_form = free_form
        # Running tally across every turn this colleague takes (prep + debate).
        self.usage: dict[str, float] = {
            "input_tokens": 0, "output_tokens": 0,
            "cache_read_tokens": 0, "cache_write_tokens": 0,
            "cost_usd": 0.0, "turns": 0,
        }

        # Skills arrive as a local plugin so `setting_sources` can stay empty.
        # The `Skill` tool has to be granted too — without it the skills load
        # and are simply never used, with no error. See skills.py.
        tools = list(persona.tools)
        plugins: list[dict[str, str]] = []
        if persona.skills:
            plugins = skills_mod.plugin_config(skill_pack)
            if "Skill" not in tools:
                tools.append("Skill")

        # An MCP server that is connected but not in the allowlist is worse
        # than one that is absent: it starts, costs nothing visible, and its
        # tools simply never fire. Grant them alongside the server itself.
        if extra_mcp:
            tools += [t for t in mcp_mod.tool_grants(list(extra_mcp)) if t not in tools]

        # In-process DuckDB dataset tools: let a persona reason FROM the data (query it) rather
        # than reading a big file into context. Merged as an extra MCP server + tool grants.
        mcp_servers = dict(extra_mcp or {})
        if dataset_server is not None:
            from agents.dataset_mcp import DATASET_TOOL_NAMES
            mcp_servers["dataset"] = dataset_server
            tools += [t for t in DATASET_TOOL_NAMES if t not in tools]

        # Free-form (debate) mode: no forced output schema — the persona speaks in prose and
        # calls the `meeting` action tools (propose/cite/defer_to/…) to record structure, the
        # way a real SDK agent naturally acts. See meeting_actions.py.
        if free_form and actions_server is not None:
            from agents.roundtable.meeting_actions import MEETING_ACTION_TOOLS
            mcp_servers["meeting"] = actions_server
            tools += [t for t in MEETING_ACTION_TOOLS if t not in tools]

        self._client: ClaudeSDKClient | None = None
        self._options = ClaudeAgentOptions(
            system_prompt=_system_prompt(persona, topic, colleagues, behaviours),
            tools=tools,
            allowed_tools=tools,
            plugins=plugins,
            skills=list(persona.skills),
            model=persona.model,
            cwd=str(workspace.private(persona.id)),
            # shared minutes + any project reference dirs (read-only uploads)
            add_dirs=[str(workspace.shared), *read_dirs],
            mcp_servers=mcp_servers,
            # Structured output only in classic mode; debate mode stays free-form.
            output_format=None if free_form else TURN_SCHEMA,
            # Deployment hygiene: ignore ambient CLAUDE.md / settings / MCP so
            # behaviour does not drift with whatever is on the host. Skills
            # come from the pack above instead of from settings discovery,
            # which is what lets this stay empty.
            setting_sources=[],
            strict_mcp_config=True,
            permission_mode="dontAsk",
            # Not a conversation budget -- a budget for the SDK turns spent
            # producing one contribution. Too low and the persona narrates
            # what it is about to do, runs out, and says nothing.
            max_turns=turn_budget or (30 if persona.skills else 6),
            env=env or {},
        )

    async def __aenter__(self) -> PersonaAgent:
        self._client = ClaudeSDKClient(options=self._options)
        await self._client.connect()
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        if self._client:
            await self._client.disconnect()
        return False

    def _absorb(self, msg: Any) -> None:
        u = usage_from_result(msg)
        for k in ("input_tokens", "output_tokens", "cache_read_tokens",
                  "cache_write_tokens", "cost_usd"):
            self.usage[k] += u[k]
        self.usage["turns"] += 1

    async def speak(
        self, cue: str, on_activity: Callable[[str, dict], None] | None = None
    ) -> dict[str, Any] | None:
        """Take a turn. ``cue`` is the facilitator's prompt for this turn.

        Returns the parsed turn payload (see TURN_SCHEMA), or ``None`` if the
        persona produced nothing usable. A session occasionally burns its
        ``max_turns`` on reading and never calls ``StructuredOutput``; one
        retry with a blunter cue recovers it. Silence is returned as ``None``
        rather than a placeholder so the loop can drop the turn instead of
        recording "(no response)" into the minutes.

        ``on_activity(tool, input)`` — if given — fires as the persona works, so
        the room can show what it's doing (reading a file, querying the data).
        Token/cost usage is tallied into ``self.usage`` regardless.
        """
        assert self._client is not None, "use PersonaAgent as an async context manager"
        for attempt in range(2):
            prompt = cue if attempt == 0 else _RETRY_CUE
            await self._client.query(prompt)
            payload = _normalise(await collect(
                self._client.receive_response(),
                on_activity=on_activity,
                on_result=self._absorb,
            ))
            if payload["text"].strip():
                return payload
        return None

    async def speak_free(
        self, cue: str, on_activity: Callable[[str, dict], None] | None = None
    ) -> str | None:
        """Debate mode: one free-form contribution. Returns the persona's prose (its assistant
        text), or None if it produced nothing. Structured side-effects (propose/cite/…) land in
        the actions buffer the meeting holds, not here. Usage is tallied into ``self.usage``."""
        assert self._client is not None, "use PersonaAgent as an async context manager"
        await self._client.query(cue)
        payload = _normalise(await collect(
            self._client.receive_response(),
            on_activity=on_activity,
            on_result=self._absorb,
        ))
        text = (payload.get("text") or "").strip()
        return text or None


def _normalise(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Fill in anything the model omitted so downstream code can index freely."""
    base = {
        "text": "",
        "why": "picking up the thread",
        "note": "",
        "thinking": "",
        "sources": [],
        "replying_to": "",
        "question_for": "",
        "agreed_text": "",
        "agreed_type": "",
    }
    if not payload:
        return base
    if "_text" in payload and len(payload) == 1:
        base["text"] = payload["_text"]
        return base
    base.update({k: v for k, v in payload.items() if v is not None})
    return base
