"""The Chair — facilitator, and the only writer of the minutes.

Per the design handoff the Chair is a distinct lightweight agent that:
  - opens with the frame
  - issues a halfway time check
  - calls the closing round
  - acknowledges user interruptions

and **never contributes substance**. Its turns render quieter and appear
faster (340ms vs 1200ms in the UI).

It runs on a cheap model. Most of its turns are template text; only the
closing frame and the recap are generated.
"""

from __future__ import annotations

import random
import subprocess
from pathlib import Path
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, query

from . import skills as skills_mod
from .structured import collect

from .types import MeetingState, Persona
from .workspace import Workspace

_DECK_NAME = "recap.pptx"
_DIAGRAM_NAME = "recap-diagram.drawio"
# TurboUIGen: the meeting's optional diagram is drawn with the vendored diagram-design skill
# (self-contained HTML/SVG), rendered in the Brainstorming tab's right artifact panel.
_DIAGRAM_DESIGN_DIR = Path(__file__).resolve().parents[1] / "vendor_plugins" / "diagram-design"
_DIAGRAM_HTML = "recap-diagram.html"


def _node_env() -> dict[str, str]:
    """NODE_PATH pointing at the global module root, if there is one.

    Empty dict when npm isn't installed — the deck step degrades to a note
    rather than an exception, like every other missing dependency here.
    """
    try:
        root = subprocess.run(
            ["npm", "root", "-g"], check=True, capture_output=True, text=True, timeout=10
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return {}
    return {"NODE_PATH": root} if root else {}

RECAP_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "headline": {
                "type": "string",
                "description": (
                    "The conclusion as a sentence, not a label. e.g. 'Ship the "
                    "small version — but pay for the plumbing now.'"
                ),
            },
            "decision": {"type": "string"},
            "argument": {
                "type": "string",
                "description": (
                    "One paragraph: the argument that won and the objection "
                    "that shaped it, naming people. This is the whole value."
                ),
            },
            "commitments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "who": {"type": "string"},
                        "what": {"type": "string"},
                    },
                    "required": ["who", "what"],
                    "additionalProperties": False,
                },
            },
            "still_open": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Genuinely unresolved things. Never invent closure. If "
                    "nobody costed something, say so."
                ),
            },
        },
        "required": ["headline", "decision", "argument", "commitments", "still_open"],
        "additionalProperties": False,
    },
}

# Agenda-structured recap — the Chair files outcomes under the meeting's agenda buckets (PM minutes).
AGENDA_RECAP_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "headline": {
                "type": "string",
                "description": "The conclusion as a sentence, not a label.",
            },
            "sections": {
                "type": "array",
                "description": "One entry per agenda bucket, IN ORDER, using the exact bucket names given.",
                "items": {
                    "type": "object",
                    "properties": {
                        "bucket": {"type": "string"},
                        "items": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Concrete outcomes the meeting reached for this bucket. "
                                           "Empty list if it wasn't covered — never invent content.",
                        },
                    },
                    "required": ["bucket", "items"],
                    "additionalProperties": False,
                },
            },
            "commitments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"who": {"type": "string"}, "what": {"type": "string"}},
                    "required": ["who", "what"],
                    "additionalProperties": False,
                },
            },
            "still_open": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Genuinely unresolved things. Never invent closure.",
            },
        },
        "required": ["headline", "sections", "commitments", "still_open"],
        "additionalProperties": False,
    },
}


def opening(topic: str, people: list[Persona]) -> str:
    names = ", ".join(p.name for p in people[:-1])
    last = people[-1].name
    return (
        f"Right — we're here to work out: {topic}. "
        f"{names} and {last} are in the room. "
        "Let's hear where people actually stand before we try to agree anything."
    )


def halfway(state: MeetingState) -> str:
    return (
        f"We're about halfway. {state.clock} gone. "
        "If there's a disagreement still live, now is the time to have it."
    )


def closing() -> str:
    return (
        "Let's close. One commitment each — something you will actually do, "
        "in the first person. Anything still unresolved, say so plainly rather "
        "than tidying it away."
    )


async def build_deck(
    recap: dict[str, Any],
    workspace: Workspace,
    topic: str,
    model: str = "claude-sonnet-5",
    skill_pack: str | None = None,
) -> tuple[str | None, str]:
    """Turn the finished recap into a slide deck. Returns (path, detail).

    Deliberately *after* the meeting rather than inside a turn. A deck is not
    a contribution to a conversation: it takes minutes, its own instructions
    mandate a build-validate-render-inspect loop that no turn budget would
    survive, and the result is an artifact nobody in the room can see. The
    recap already has the shape of a deck — a headline, the argument that
    won, who is doing what, what is still open — so this runs once, from
    that, with the whole meeting already decided.

    Writes into ``shared/``, which keeps the rule that only the Chair writes
    there. Never raises: a missing dependency must not throw away a meeting
    that has already been paid for.
    """
    lines = [f"# {recap.get('headline', topic)}", ""]
    if recap.get("decision"):
        lines += ["## The decision", recap["decision"], ""]
    if recap.get("argument"):
        lines += ["## How we got there", recap["argument"], ""]
    if recap.get("commitments"):
        lines += ["## Who's doing what"]
        lines += [f"- {c.get('who')}: {c.get('what')}" for c in recap["commitments"]]
        lines.append("")
    if recap.get("still_open"):
        lines += ["## Still open"] + [f"- {s}" for s in recap["still_open"]]

    prompt = (
        "Build a slide deck from these minutes of a meeting that has just "
        "finished. Write it as the Chair would: the decision and the argument "
        "that produced it, who committed to what, and what is genuinely still "
        "open — do not resolve anything the minutes leave open.\n\n"
        f"The question was: {topic}\n\n"
        + "\n".join(lines)
        + f"\n\nSave it as {_DECK_NAME} in the current directory."
    )

    options = ClaudeAgentOptions(
        system_prompt=(
            "You produce the written record of a meeting. You are not a "
            "participant and you add no opinions of your own."
        ),
        tools=["Read", "Write", "Bash", "Skill"],
        allowed_tools=["Read", "Write", "Bash", "Skill"],
        plugins=skills_mod.plugin_config(skill_pack),
        skills=["pptx"],
        model=model,
        cwd=str(workspace.shared),
        setting_sources=[],
        strict_mcp_config=True,
        permission_mode="dontAsk",
        # The skill's own workflow is build, validate, render to images,
        # inspect every slide, fix, re-render. Six turns is not in the region.
        max_turns=60,
        # The deck runs in the meeting's shared directory, and node does not
        # search the global module root from an arbitrary cwd -- so a
        # globally installed pptxgenjs is invisible there and the skill falls
        # back to `npm install`, dropping node_modules into every meeting.
        env=_node_env(),
    )

    try:
        await collect(query(prompt=prompt, options=options))
    except Exception as exc:  # noqa: BLE001 - any SDK failure, same handling
        return None, f"{type(exc).__name__}: {exc}"

    made = sorted(workspace.shared.glob("*.pptx"))
    if not made:
        return None, "the skill ran but produced no .pptx (check its dependencies)"
    return str(made[0]), f"{made[0].name}, {made[0].stat().st_size // 1024} KB"


DIAGRAM_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "draw": {
                "type": "boolean",
                "description": (
                    "True only if a diagram would tell someone who wasn't in "
                    "the room something the words do not. Most meetings do "
                    "not need one. A decision, a list of commitments, or a "
                    "disagreement about priority is prose, not a picture."
                ),
            },
            "kind": {
                "type": "string",
                "description": (
                    "What sort: 'architecture', 'user journey', 'sequence', "
                    "'state', 'flow'. Empty if not drawing."
                ),
            },
            "subject": {
                "type": "string",
                "description": (
                    "One sentence: exactly what the diagram should show, in "
                    "terms taken from the meeting. Empty if not drawing."
                ),
            },
            "why": {
                "type": "string",
                "description": (
                    "One sentence on the judgement, either way. If declining, "
                    "say what makes this meeting prose rather than a picture."
                ),
            },
        },
        "required": ["draw", "kind", "subject", "why"],
        "additionalProperties": False,
    },
}


async def build_diagram(
    recap: dict[str, Any],
    turns: list[Any],
    workspace: Workspace,
    topic: str,
    judge_model: str = "claude-haiku-4-5",
    model: str = "claude-sonnet-5",
    skill_pack: str | None = None,
    env: dict[str, str] | None = None,
    force: bool = False,
    on_result=None,
) -> tuple[str | None, str]:
    """Draw a diagram of the meeting — but only if one is warranted.

    Two steps on purpose. A cheap call decides *whether* a picture would say
    anything the recap does not, and what it should show; only then does the
    expensive drawing run. Without that split, "no diagram" and "the diagram
    failed" look identical from the outside, and every meeting gets a picture
    whether or not it earns one.

    Never raises. Returns (path or None, why).
    """
    said = "\n".join(
        f"{t.who}: {t.text}" for t in turns if t.who not in ("chair", "you")
    )
    verdict_prompt = (
        f"A meeting has just finished. The question was: {topic}\n\n"
        f"What was said:\n{said}\n\n"
        f"What was decided: {recap.get('headline', '')}\n"
        f"{recap.get('argument', '')}\n\n"
        "Would a diagram tell a reader something these words do not? Judge it "
        "honestly — most meetings are prose."
    )

    verdict = None
    if force:  # on-demand / "draw again": skip the judge, always draw
        verdict = {"draw": True, "kind": "diagram",
                   "subject": recap.get("headline", "") or recap.get("decision", "")}
    if verdict is None:
        try:
            verdict = await collect(
                query(
                    prompt=verdict_prompt,
                    options=ClaudeAgentOptions(
                        system_prompt=(
                            "You decide whether a meeting is worth diagramming. "
                            "You are not eager: a picture that restates a list is "
                            "worse than no picture."
                        ),
                        tools=[],
                        model=judge_model,
                        output_format=DIAGRAM_SCHEMA,
                        setting_sources=[],
                        strict_mcp_config=True,
                        skills=[],
                        permission_mode="dontAsk",
                        max_turns=3,
                    ),
                ),
                on_result=on_result,
            )
        except Exception as exc:  # noqa: BLE001
            return None, f"could not decide: {type(exc).__name__}: {exc}"

    if not verdict or not verdict.get("draw"):
        return None, (verdict or {}).get("why") or "judged that no diagram was needed"

    kind = verdict.get("kind", "diagram")
    subject = verdict.get("subject", "")
    prompt = (
        f"Draw a {kind} diagram of what this meeting settled.\n\n"
        f"It should show: {subject}\n\n"
        f"The question was: {topic}\n\n{said}\n\n"
        f"Save it as {_DIAGRAM_HTML} in the current directory as a single "
        "self-contained HTML file. Draw only what the meeting actually "
        "established — do not invent components, steps, or names nobody mentioned."
    )

    try:
        await collect(
            query(
                prompt=prompt,
                options=ClaudeAgentOptions(
                    system_prompt=(
                        "You draw the diagram a meeting earned, using the "
                        "diagram-design skill. You add nothing that was not discussed."
                    ),
                    tools=["Read", "Write", "Bash", "Skill"],
                    allowed_tools=["Read", "Write", "Bash", "Skill"],
                    plugins=[{"type": "local", "path": str(_DIAGRAM_DESIGN_DIR)}],
                    skills=["diagram-design"],
                    model=model,
                    cwd=str(workspace.shared),
                    setting_sources=[],
                    strict_mcp_config=True,
                    permission_mode="dontAsk",
                    max_turns=40,
                    env=env or {},
                ),
            ),
            on_result=on_result,
        )
    except Exception as exc:  # noqa: BLE001
        return None, f"{kind}: drawing failed — {type(exc).__name__}: {exc}"

    made = sorted(workspace.shared.glob("*.html"))
    if not made:
        return None, f"{kind}: the skill ran but produced nothing"
    return str(made[0]), f"{kind} — {verdict.get('why', '')}"


_ASSIGN_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "assignments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "bucket": {"type": "string"},
                        "persona": {"type": "string", "description": "persona id"},
                    },
                    "required": ["bucket", "persona"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["assignments"],
        "additionalProperties": False,
    },
}


async def assign_agenda(agenda, people, model="claude-haiku-4-5", env=None, on_result=None) -> dict:
    """Facilitator hands out pre-reads: map each agenda section to the ONE person best placed
    to research it. Returns {persona_id: [buckets]}. One cheap call; never raises (round-robin
    fallback) — this is what keeps prep 'targeted' rather than everyone-does-everything."""
    roster = "\n".join(f"- {p.id}: {p.role or p.name} — {p.stance}" for p in people)
    buckets = "\n".join(f"- {b}" for b in agenda)
    prompt = (
        f"Agenda sections:\n{buckets}\n\nPeople in the room:\n{roster}\n\n"
        "Assign each agenda section to the ONE person best placed to go research it and form a "
        "view before the meeting. Use the persona ids exactly. One person may own two sections; "
        "not everyone must get one."
    )
    options = ClaudeAgentOptions(
        system_prompt="You assign meeting pre-work to the right people, tersely.",
        tools=[], model=model, output_format=_ASSIGN_SCHEMA, setting_sources=[],
        strict_mcp_config=True, skills=[], permission_mode="dontAsk", max_turns=3, env=env or {},
    )
    ids = {p.id for p in people}
    out: dict[str, list[str]] = {}
    try:
        data = await collect(query(prompt=prompt, options=options), on_result=on_result)
        for a in (data or {}).get("assignments", []):
            pid, b = a.get("persona"), a.get("bucket")
            if pid in ids and b:
                out.setdefault(pid, []).append(b)
    except Exception:  # noqa: BLE001
        out = {}
    if not out:  # round-robin fallback
        for i, b in enumerate(agenda):
            out.setdefault(people[i % len(people)].id, []).append(b)
    return out


def checkpoint(kind: str) -> str:
    """COLLABORATE mode: the Chair turns to the user at a milestone to confirm direction."""
    if kind == "halfway":
        return (
            "Let me pause us here and check with you. This is roughly where we've landed so far "
            "— is this the direction you want, or is there something you'd like us to weigh "
            "before we push toward a decision? Say the word and we'll carry on."
        )
    return (
        "Before I write this up — this is the direction we're closing on. Good to lock it in, "
        "or is there something you want us to revisit first?"
    )


def push_back(name: str) -> str:
    """Name someone to argue the other side.

    Used when the room has converged without anyone testing the position —
    the failure the design doc warns about as loudly as it warns about
    manufactured conflict, which is why this fires on a convergence signal
    rather than on a timer.
    """
    return (
        f"We're agreeing quickly. {name}, make the strongest case against what "
        "we've just landed on — whether or not it's your own view. If it "
        "survives that, we'll know it's worth something."
    )


# Varied, context-aware acknowledgements — a real facilitator doesn't say the same line
# eight times, and doesn't say "that changes the brief" when you just agreed or asked a question.
_ACK = {
    "agree": [
        "Good — that's settled, then.", "Noted, we'll keep it.", "Agreed. Moving on.",
        "Right, that one stays.", "Good, we're aligned on that.",
    ],
    "question": [
        "Good question — let's take it.", "Fair to check that. Everyone?",
        "Worth pausing on — let's get you an answer.", "Hold on, that's worth a proper look.",
        "Let's not skip that one.",
    ],
    "steer": [
        "Hold on — that changes the brief.", "Let's fold that in.",
        "That shifts things — worth taking now.", "New input for the room — let's weigh it.",
        "Good catch, let's not lose that.", "That's a real change — everyone, take it in.",
    ],
    # A "keep going / don't wait on me" nudge — acknowledge the handoff, don't re-open anything.
    "continue": [
        "Right — we'll carry on.", "Understood, we'll keep at it.",
        "Will do — back to it.", "Good, we'll press on.", "Carrying on.",
    ],
}


def acknowledge(target: str | None = None, kind: str = "steer") -> str:
    """The Chair takes the user's interjection. Varied and context-aware: `kind` is one of
    'agree' | 'question' | 'steer'. `target` names a specific colleague when the user addressed one."""
    base = random.choice(_ACK.get(kind, _ACK["steer"]))
    # A "carry on" nudge isn't aimed at a colleague — never tack "over to you" onto it.
    if target and target != "all" and kind != "continue":
        who = target.title()
        if kind == "question":
            return f"{who}, that's for you — {base.lower()}"
        return f"{who}, over to you. {base}"
    return base


async def write_recap(
    state: MeetingState, model: str = "claude-sonnet-5",
    agenda: list[str] | None = None, on_result=None,
) -> dict[str, Any]:
    """Generate the Recap screen's content from the transcript.

    A one-shot ``query()`` rather than a persistent session — it runs once, at
    the end, and needs no tools.
    """
    transcript = "\n\n".join(
        f"[{t.at}] {t.who}: {t.text}" for t in state.turns if t.who != "chair"
    )
    agreed = "\n".join(f"- ({a.type}) {a.text} — {a.who}" for a in state.agreed)
    use_agenda = bool(agenda)

    options = ClaudeAgentOptions(
        system_prompt=(
            "You write up meetings like a sharp project manager taking minutes — not a status "
            "reporter. Name people. Say which argument won and which objection shaped it. Leave "
            "unresolved things unresolved — that is a feature, not a gap."
        ),
        tools=[],
        model=model,
        output_format=AGENDA_RECAP_SCHEMA if use_agenda else RECAP_SCHEMA,
        setting_sources=[],
        strict_mcp_config=True,
        skills=[],
        permission_mode="dontAsk",
        # Not 1. With output_format the model spends a turn on the
        # StructuredOutput call and needs another to finish, and the SDK
        # raises rather than returning what it has.
        max_turns=4,
    )

    topic = state.config.topic.split("\n\n")[0]
    if use_agenda:
        buckets = "\n".join(f"- {b}" for b in agenda)
        prompt = (
            f"The question was: {topic}\n\n"
            f"The discussion:\n{transcript}\n\n"
            f"Settled during the meeting:\n{agreed or '(nothing recorded)'}\n\n"
            "Write it up as a facilitator's minutes, organized under EXACTLY these agenda "
            f"sections (same names, same order):\n{buckets}\n\n"
            "Under each section, list the concrete outcomes the meeting actually reached "
            "(decisions, agreements, points settled) as short bullet strings. If a section "
            "wasn't covered, give it an empty list — never invent content to fill a bucket. "
            "Then who's doing what, and what's genuinely still open."
        )
    else:
        prompt = (
            f"The question was: {topic}\n\n"
            f"The discussion:\n{transcript}\n\n"
            f"Settled during the meeting:\n{agreed or '(nothing recorded)'}\n\n"
            "Write the recap."
        )

    # This runs after the meeting is paid for. A failure here must not throw
    # away the transcript that has already been generated.
    try:
        data = await collect(query(prompt=prompt, options=options), on_result=on_result)
    except Exception as exc:  # noqa: BLE001 - any SDK failure, same handling
        data = None
        reason = f"The recap could not be generated: {exc}"
    else:
        reason = "The recap could not be parsed."

    if not data or "headline" not in data:
        fallback: dict[str, Any] = {
            "headline": "The meeting did not produce a clean recap.",
            "commitments": [],
            "still_open": [reason],
        }
        if use_agenda:
            fallback["sections"] = [{"bucket": b, "items": []} for b in (agenda or [])]
        else:
            fallback["decision"] = ""
            fallback["argument"] = (data or {}).get("_text", "")[:800]
        return fallback
    return data
