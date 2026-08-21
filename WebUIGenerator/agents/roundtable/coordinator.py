"""Turn selection.

Two strategies, matching the two options the design exposes to users:

  "round"  RoundRobin  — everyone speaks every round, in order. Predictable,
                         and reads like it.
  "open"   Hybrid      — the design's recommendation. Opening turns are fixed
                         (no model call spent deciding who obviously speaks
                         first), then a cheap coordinator call picks the
                         speaker from the state of the discussion.

The Hybrid coordinator is deliberately a *small* model call returning one id.
It is the highest-frequency call in the system — one per turn — so it should
stay cheap.
"""

from __future__ import annotations

from claude_agent_sdk import ClaudeAgentOptions, query

from .structured import collect

from .types import MeetingState, Persona

SELECT_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "speaker": {"type": "string", "description": "The persona id."},
            "why": {
                "type": "string",
                "description": "2-5 words, lowercase, human. Shown in the UI.",
            },
        },
        "required": ["speaker", "why"],
        "additionalProperties": False,
    },
}


class RoundRobin:
    def __init__(self, people: list[Persona]) -> None:
        self.people = people
        self._i = 0

    async def next(self, state: MeetingState) -> tuple[str, str]:
        p = self.people[self._i % len(self.people)]
        self._i += 1
        return p.id, "taking their turn"


class Hybrid:
    """Fixed opening, then coordinator-picked."""

    def __init__(self, people: list[Persona], model: str = "claude-haiku-4-5") -> None:
        self.people = people
        self.model = model

    async def next(self, state: MeetingState) -> tuple[str, str]:
        spoken_turns = [t for t in state.turns if t.who not in ("chair", "you")]

        # Opening is fixed — don't spend a model call deciding who starts.
        if len(spoken_turns) == 0:
            return self.people[0].id, "started us off"
        if len(spoken_turns) == 1:
            return self.people[1].id, "the other side of it"

        # Being named is a strong signal, but it used to be an absolute one:
        # a persona named in every turn took the floor indefinitely, which is
        # how one room ran 3/3/2/0. Now it only promotes someone who is still
        # within the fairness cap. A question that genuinely must be answered
        # bypasses this path entirely -- the loop routes it directly.
        last = spoken_turns[-1]
        eligible = self._eligible(state)
        for p in self.people:
            if (
                p.id != last.who
                and p.id in eligible
                and p.name.lower() in last.text.lower()
            ):
                return p.id, "named directly"

        return await self._pick(state)

    # How far ahead of the quietest person anyone is allowed to get. One is
    # round-robin in disguise; unbounded is the failure this exists to fix --
    # a run where one persona took three turns before another took one.
    LEAD = 2

    def _counts(self, state: MeetingState) -> tuple[dict[str, int], str]:
        spoken = [t.who for t in state.turns if t.who not in ("chair", "you")]
        return {p.id: spoken.count(p.id) for p in self.people}, (
            spoken[-1] if spoken else ""
        )

    def _eligible(self, state: MeetingState) -> set[str]:
        """Who may speak: not the last voice, and not too far ahead."""
        counts, last_who = self._counts(state)
        eligible = {p.id for p in self.people if p.id != last_who}
        if eligible:
            floor = min(counts[pid] for pid in eligible)
            # Strict: someone on floor+LEAD is already LEAD ahead, and letting
            # them speak would put them LEAD+1 ahead.
            eligible = {pid for pid in eligible if counts[pid] < floor + self.LEAD}
        return eligible

    async def _pick(self, state: MeetingState) -> tuple[str, str]:
        recent = "\n".join(
            f"{t.who}: {t.text}" for t in state.turns[-5:] if t.who != "chair"
        )
        counts, _ = self._counts(state)
        eligible = self._eligible(state)

        def label(p: Persona) -> str:
            if p.id not in eligible:
                return "  [has had the floor enough -- do not pick]"
            if counts[p.id] == 0:
                return "  [has not spoken yet]"
            return f"  [{counts[p.id]} turns so far]"

        roster = "\n".join(
            f"  {p.id} — holds: {p.stance}{label(p)}" for p in self.people
        )

        options = ClaudeAgentOptions(
            system_prompt=(
                "You choose who speaks next in a meeting. Pick the person "
                "whose concern is most live right now — someone who would "
                "genuinely interject, not whoever is next in line. Prefer "
                "someone who will disagree with what was just said over "
                "someone who will agree. Give people who have not spoken a "
                "chance if their concern is relevant. Never pick whoever "
                "spoke last, and never pick anyone marked 'do not pick' — "
                "they have had the floor enough."
            ),
            tools=[],
            model=self.model,
            output_format=SELECT_SCHEMA,
            setting_sources=[],
            strict_mcp_config=True,
            skills=[],
            permission_mode="dontAsk",
            max_turns=3,  # the StructuredOutput call itself costs a turn
        )

        prompt = (
            f"Topic: {state.config.topic}\n\n"
            f"In the room:\n{roster}\n\n"
            f"Last few turns:\n{recent}\n\n"
            "Who speaks next?"
        )

        # A coordinator failure is recoverable -- the fairness fallback below
        # picks a defensible speaker. Never let it end the meeting.
        try:
            data = await collect(query(prompt=prompt, options=options))
        except Exception:  # noqa: BLE001 - any SDK failure, same handling
            data = None

        if data:
            speaker = data.get("speaker", "")
            if speaker in eligible:
                return speaker, data.get("why", "coming in")

        # Fall back to whoever has spoken least among the eligible.
        if not eligible:  # single-person room
            return self.people[0].id, "the only one here"
        fewest = min(counts[pid] for pid in eligible)
        pick = next(
            p.id for p in self.people if p.id in eligible and counts[p.id] == fewest
        )
        return pick, "hasn't had a say yet"


def build(order: str, people: list[Persona], model: str = "claude-haiku-4-5"):
    return RoundRobin(people) if order == "round" else Hybrid(people, model)
