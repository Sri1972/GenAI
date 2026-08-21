"""Core data types.

The ``Turn`` shape mirrors the design handoff exactly (see
``docs/architecture.md`` → Turn) so the UI described in the design doc can be
built against this engine without a translation layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

AgreedType = Literal["decision", "constraint", "commitment"]
TurnOrder = Literal["open", "round"]


@dataclass
class AgreedItem:
    """An entry in the "Agreed so far" rail."""

    text: str
    type: AgreedType
    who: str
    at: str


@dataclass
class Persona:
    """A colleague at the table.

    ``stance`` and ``concession`` are what stop personas collapsing into one
    voice: the stance is what they defend, the concession is the specific
    thing they will give up. The design doc calls the concession out as the
    thing that "makes them feel like a colleague rather than a position".
    """

    id: str
    name: str
    role: str
    hue: int
    stance: str
    concession: str
    knows: str
    tools: list[str] = field(default_factory=lambda: ["Read"])
    skills: list[str] = field(default_factory=list)
    model: str = "claude-sonnet-5"


@dataclass
class Turn:
    """One contribution to the transcript. Append-only."""

    id: str
    who: str  # persona id | "chair" | "you"
    text: str
    why: str  # human-readable reason they're speaking now
    at: str  # "m:ss"
    note: str | None = None  # one sentence on what they consulted
    thinking: str | None = None  # plain-language reasoning (detail panel)
    sources: list[str] = field(default_factory=list)
    quote: str | None = None  # the turn being replied to
    quote_role: str | None = None
    agreed: AgreedItem | None = None

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "who": self.who,
            "text": self.text,
            "why": self.why,
            "at": self.at,
            "note": self.note,
            "thinking": self.thinking,
            "sources": self.sources,
            "quote": self.quote,
            "quoteRole": self.quote_role,
        }
        if self.agreed:
            d["agreed"] = {"text": self.agreed.text, "type": self.agreed.type}
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Turn:
        """Inverse of ``to_dict`` — for replaying a saved transcript."""
        agreed = d.get("agreed")
        return cls(
            id=d["id"],
            who=d["who"],
            text=d["text"],
            why=d.get("why", ""),
            at=d.get("at", "0:00"),
            note=d.get("note"),
            thinking=d.get("thinking"),
            sources=d.get("sources") or [],
            quote=d.get("quote"),
            quote_role=d.get("quoteRole"),
            agreed=(
                AgreedItem(
                    text=agreed["text"],
                    type=agreed["type"],
                    who=agreed.get("who", ""),
                    at=agreed.get("at", d.get("at", "")),
                )
                if agreed
                else None
            ),
        )


# Models the CLI runtime accepts, cheapest first. Prices are per million
# tokens (input/output) and are here so the UI can show what a choice costs
# rather than making you look it up.
MODELS: dict[str, tuple[str, float, float]] = {
    "claude-haiku-4-5": ("Haiku 4.5", 1.0, 5.0),
    "claude-sonnet-5": ("Sonnet 5", 3.0, 15.0),
    "claude-opus-5": ("Opus 5", 5.0, 25.0),
    "claude-fable-5": ("Fable 5", 10.0, 50.0),
}

# Verified present in CLI 2.1.23x. Grep/Glob/TodoWrite/MultiEdit are not --
# see personas.py. A persona granted a missing tool loses the capability
# silently, so the UI picks from this list rather than free text.
TOOLS = ["Read", "Bash", "Write", "Edit", "WebSearch", "WebFetch"]


@dataclass
class MeetingConfig:
    topic: str
    people: list[str]  # persona ids
    duration_minutes: int = 12
    turn_order: TurnOrder = "open"
    max_turns: int = 14
    workspace_root: str = "workspaces"

    # Agenda "buckets" the Chair organizes the recap into (PM-style minutes). Empty → a default.
    agenda: list[str] = field(default_factory=list)

    # Per-persona overrides, keyed by persona id. Empty means "use the
    # roster default" -- these exist so a room can be re-run with one axis
    # changed and the difference attributed to that axis.
    models: dict[str, str] = field(default_factory=dict)
    tools: dict[str, list[str]] = field(default_factory=dict)
    skills: dict[str, list[str]] = field(default_factory=dict)
    notes: dict[str, str] = field(default_factory=dict)  # seeds private workspaces
    # persona id -> MCP server names from roundtable.mcp.SERVERS. Tokens are
    # never stored here; they come from the environment when the meeting runs.
    mcp: dict[str, list[str]] = field(default_factory=dict)
    skill_pack: str | None = None  # defaults to the repo's skillpack/

    coordinator_model: str = "claude-haiku-4-5"
    recap_model: str = "claude-sonnet-5"

    # How many SDK turns a persona gets to produce one contribution. Six is
    # plenty to read the minutes and answer; a persona with skills needs far
    # more, because loading a skill and acting on it are turns too. Measured:
    # at six, a persona asked to draw a diagram spends its whole budget on
    # preamble and produces nothing at all -- the meeting gets a fragment of
    # "let me check whether draw.io is available" instead of a contribution.
    agent_turns: int = 6
    agent_turns_with_skills: int = 30

    # Build a slide deck from the recap once the meeting is over. Off by
    # default: it is slow, and it needs the pptx skill's own toolchain
    # (pptxgenjs, LibreOffice, markitdown) which is not assumed present.
    deck: bool = False

    # Draw a diagram of the meeting, if one is warranted. The judgement is
    # part of the step: a cheap call decides whether a picture says anything
    # the recap does not, and most meetings are prose.
    diagram: bool = False

    # Behaviours, each switchable so a room can be run with one on and one off
    # and the difference attributed. Defaults are on because that is the
    # interesting room; turn them off to get the previous behaviour back.
    independent_read: bool = True  # form your own view before engaging
    strategic: bool = True  # reason from the domain, not just the decision
    questions: bool = True  # ask, and be answered, instead of assuming
    devils_advocate: bool = True  # argue the other side when the room converges

    # COLLABORATE mode: the Chair pauses the room at milestones (halfway + before the recap)
    # to bring the user in and confirm direction before continuing. Off = AUTOPILOT (run through).
    checkpoints: bool = False


@dataclass
class MeetingState:
    """Everything the loop and the renderer need. Mirrors the design doc's
    state model, minus the purely-visual fields."""

    config: MeetingConfig
    turns: list[Turn] = field(default_factory=list)
    agreed: list[AgreedItem] = field(default_factory=list)
    elapsed: int = 0  # seconds
    running: bool = False
    speaking: str | None = None
    spoken: set[str] = field(default_factory=set)

    @property
    def clock(self) -> str:
        return f"{self.elapsed // 60}:{self.elapsed % 60:02d}"

    def add(self, turn: Turn) -> None:
        self.turns.append(turn)
        if turn.who not in ("chair", "you"):
            self.spoken.add(turn.who)
        if turn.agreed:
            self.agreed.append(turn.agreed)


# JSON schema the persona agents are constrained to. Keys match Turn fields so
# the parsed object maps straight across.
TURN_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": (
                    "What you say — AT MOST 3 short sentences, ~50 words. Terse, spoken. "
                    "Make ONE sharp point per turn; don't pre-empt every objection. "
                    "If it's running long, cut it."
                ),
            },
            "why": {
                "type": "string",
                "description": (
                    "Why you are speaking now, 2-5 words, lowercase, human. "
                    "e.g. 'pushing back, hard', 'on what it costs'"
                ),
            },
            "note": {
                "type": "string",
                "description": (
                    "One plain sentence on what you consulted. Never a tool "
                    "call. e.g. 'Read through eight months of requests.'"
                ),
            },
            "thinking": {
                "type": "string",
                "description": "One or two sentences of plain-language reasoning.",
            },
            "sources": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Plain-English source descriptions, not filenames.",
            },
            "replying_to": {
                "type": "string",
                "description": "Persona id you are answering, or empty string.",
            },
            "question_for": {
                "type": "string",
                "description": (
                    "If you are asking a direct question that must be answered "
                    "before you can go further: the persona id you are asking, "
                    "or 'you' for the person who called the meeting. Otherwise "
                    "empty. Only when the answer would change what you say - "
                    "rhetorical questions do not count."
                ),
            },
            "agreed_text": {
                "type": "string",
                "description": (
                    "If this turn settles something, the settled statement. "
                    "Otherwise empty string. Be strict - most turns settle nothing."
                ),
            },
            "agreed_type": {
                "type": "string",
                "enum": ["decision", "constraint", "commitment", ""],
            },
        },
        "required": [
            "text",
            "why",
            "note",
            "thinking",
            "sources",
            "replying_to",
            "question_for",
            "agreed_text",
            "agreed_type",
        ],
        "additionalProperties": False,
    },
}
