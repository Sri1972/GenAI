"""The meeting loop.

Emits events as an async generator so the same engine can drive a terminal
renderer today and an SSE stream to the design's Room screen later, without
the loop knowing which. Event shapes are stable:

    {"type": "turn" | "speaking" | "passed" | "question" | "agreed"
             | "recap" | "deck" | "done", ...}

``question`` means a persona asked *you* something and the loop is now
waiting — nothing advances until ``interject()`` is called (or ``wrap_up()``).
Questions between personas never surface as an event: the asked colleague is
simply routed to speak next.

The design doc's loop advances a wall clock and jumps it per turn so a
twelve-minute meeting completes in about a minute. Here the clock advances per
turn only — real model latency already paces it.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import random
import re
from dataclasses import replace
from typing import Any, AsyncIterator

from . import activity as activity_mod
from . import chair as chair_mod
from . import coordinator as coord_mod
from . import mcp as mcp_mod
from . import personas as roster_mod
from .agent import PersonaAgent
from .structured import usage_from_result
from .types import AgreedItem, MeetingConfig, MeetingState, Persona, Turn
from .workspace import Workspace, new_meeting_id


def _name(who: str) -> str:
    """Display name for any turn-author id — including non-personas ('you') and anything the
    model might put in `replying_to`/`question_for`. Must NEVER raise: a hallucinated id used
    to crash the whole meeting (KeyError: 'you')."""
    if who == "you":
        return "You"
    try:
        return roster_mod.get(who).name   # handles 'chair' too
    except KeyError:
        return (who or "").replace("-", " ").replace("_", " ").title() or "Someone"


_AGREE_RE = re.compile(r"\b(agree|agreed|yes|yep|yeah|sounds good|great point|good point|makes sense|nice|ok|okay|sure|exactly)\b", re.I)
_Q_START_RE = re.compile(r"^(what|why|how|should|do we|have we|did we|is|are|can|could|would|when|where|who|which)\b", re.I)
# The user handing the floor back — "keep going", not "change course". Two tiers:
# a short "just proceed" nudge, and unambiguous "release" phrases that hold at any length.
_CONTINUE_RE = re.compile(
    r"\b(carry on|keep going|keep at it|keep it going|go ahead|go on|proceed|continue)\b", re.I)
_RELEASE_RE = re.compile(
    r"\b(don'?t (keep )?wait(ing)?( on)?( me)?|without me|amongst your?selves|among your?selves|"
    r"you (all |guys )?decide|leave it to you|carry on without)\b", re.I)
# A message that opens with a directive is a steer even if it contains an assent word — "make
# SURE we cover X" must not read as agreement just because _AGREE_RE matches "sure".
_DIRECTIVE_RE = re.compile(
    r"^(make sure|make|ensure|cover|add|include|cut|drop|remove|avoid|focus|check|consider|"
    r"look at|don'?t forget|remember to|let'?s|we should|we need|prioriti|explore|use|build)\b",
    re.I)


def _classify_interjection(said: str) -> str:
    """Rough intent of a user interjection so the Chair can react appropriately: 'continue' (a
    'keep going / don't wait on me' nudge — resume, DON'T treat as a new direction), 'agree' (a
    short assent — no reply needed), 'question' (wants an answer), or 'steer'.

    'continue' must win over 'steer' — otherwise "carry on" gets acked as a course-correction
    ("that changes the brief") and drags the room back. A bare short nudge counts; so does an
    unambiguous release phrase at any length. A longer message with real content ("keep going on
    pricing but drop EV") stays a steer, since only the short form matches _CONTINUE_RE there."""
    s = said.strip()
    if "?" not in s and (_RELEASE_RE.search(s) or (len(s) <= 45 and _CONTINUE_RE.search(s))):
        return "continue"
    if "?" in s or _Q_START_RE.match(s):
        return "question"
    # A directive opener is a steer even if an assent word appears in it — check before 'agree'.
    if _DIRECTIVE_RE.match(s):
        return "steer"
    if len(s) <= 40 and _AGREE_RE.search(s):
        return "agree"
    return "steer"


def _named_personas(said: str, agent_ids) -> list[str]:
    """Persona ids the user named in free text ('what does Data think?', 'Product and Design') —
    so we can route the reply to them instead of letting the coordinator guess."""
    low = said.lower()
    found: list[str] = []
    for pid in agent_ids:
        name = _name(pid).lower()
        if re.search(rf"\b{re.escape(pid)}\b", low) or (name and re.search(rf"\b{re.escape(name)}\b", low)):
            if pid not in found:
                found.append(pid)
    return found


class Meeting:
    def __init__(
        self,
        config: MeetingConfig,
        *,
        meeting_id: str | None = None,
        env: dict[str, str] | None = None,
        mcp_tokens: dict[str, str] | None = None,
        read_dirs: tuple[str, ...] = (),
        dataset_server: object = None,
        prep: bool = False,
    ) -> None:
        self.config = config
        self.read_dirs = read_dirs
        self.dataset_server = dataset_server
        self.prep = prep   # run a targeted homework phase before the discussion
        # Facilitator/orchestration model spend (assignment, recap, diagram) —
        # kept apart from per-persona spend so the breakdown stays honest.
        self._orch: dict[str, float] = {
            "input_tokens": 0, "output_tokens": 0,
            "cache_read_tokens": 0, "cache_write_tokens": 0,
            "cost_usd": 0.0, "turns": 0,
        }
        self.state = MeetingState(config=config)
        self.people = [self._configure(p) for p in roster_mod.roster(config.people)]
        # Its own directory unless told otherwise, so a run never overwrites
        # the evidence from the last one.
        self.meeting_id = meeting_id or new_meeting_id(config.topic)
        self.workspace = Workspace(config.workspace_root, self.meeting_id)
        self.env = env or {}
        # Credentials are a runtime argument, never configuration. Keeping
        # them off MeetingConfig means nothing that serialises a config can
        # ever write a token to disk — the transcript records which servers a
        # persona had, not how it got in. Falls back to the environment.
        self._mcp_tokens = mcp_tokens or {}
        self._agents: dict[str, PersonaAgent] = {}
        self._n = 0
        self._inbox: list[tuple[str, str]] = []
        self._paused = False
        self._stopped = False
        # Set when a persona has asked *you* something. The loop waits on it
        # exactly like a pause, but it is a separate flag so answering the
        # question doesn't silently flip the user's own Hold It toggle.
        self._awaiting_you: str | None = None
        self._advocate_called = False
        # COLLABORATE checkpoints: the loop pauses here until the user continues/steers.
        self._awaiting_checkpoint = False
        self._checkpoints_done: set[str] = set()

    def _getenv(self, key: str) -> str | None:
        """A token passed in for this meeting, else the environment."""
        return self._mcp_tokens.get(key) or os.environ.get(key)

    def _behaviours(self) -> tuple[str, ...]:
        """Which behaviour clauses this meeting's personas get."""
        cfg = self.config
        return tuple(
            name
            for name, on in (
                ("independent_read", cfg.independent_read),
                ("strategic", cfg.strategic),
                ("questions", cfg.questions),
                ("devils_advocate", cfg.devils_advocate),
            )
            if on
        )

    def _configure(self, p: Persona) -> Persona:
        """Apply this meeting's per-persona overrides.

        Returns a copy — the roster in ``personas.py`` is module-level state
        shared by every meeting in the process, so mutating it would leak one
        experiment's settings into the next.
        """
        changes: dict[str, Any] = {}
        if model := self.config.models.get(p.id):
            changes["model"] = model
        if tools := self.config.tools.get(p.id):
            changes["tools"] = list(tools)
        if skills := self.config.skills.get(p.id):
            changes["skills"] = list(skills)
        return replace(p, **changes) if changes else p

    # -- controls, driven from whatever is rendering ----------------------
    #
    # The design's Room screen has three of these: the composer, "Hold it"
    # and "Wrap up". They are plain flags read between turns rather than
    # mid-turn cancellation -- a persona already composing gets to finish,
    # which is also what happens when you interrupt a real meeting.

    def interject(self, text: str, target: str = "all") -> None:
        """Say something into the meeting. Handled before the next turn.

        Also answers a pending question — a persona that asked you something
        is waiting on exactly this, so anything you say releases it.
        """
        # If a colleague asked YOU something, your reply goes back to them (not the whole table).
        if target == "all" and self._awaiting_you:
            target = self._awaiting_you
        self._inbox.append((text, target))
        self._awaiting_you = None
        self._awaiting_checkpoint = False   # steering at a checkpoint also releases it

    def resume(self) -> None:
        """Release a collaborate-mode checkpoint without saying anything ("continue")."""
        self._awaiting_checkpoint = False

    def hold(self, paused: bool = True) -> None:
        """Pause between turns. The clock only advances per turn, so it stops."""
        self._paused = paused

    def wrap_up(self) -> None:
        """Stop taking turns and go straight to the recap."""
        self._stopped = True

    async def _checkpoint(self, kind: str, announce: bool = True):
        """One pause of a checkpoint: (optionally) the Chair turns to the user, then the loop
        waits until they continue (resume()) or steer (interject())."""
        if announce:
            t = Turn(id=f"t{self._n + 1}", who="chair", text=chair_mod.checkpoint(kind),
                     why="checking with you", at=self.state.clock)
            self._record(t)
            yield {"type": "turn", "turn": t}
        self._awaiting_checkpoint = True
        yield {"type": "checkpoint", "kind": kind}
        while self._awaiting_checkpoint and not self._stopped:
            await asyncio.sleep(0.1)

    async def _run_checkpoint(self, kind: str, picker):
        """A checkpoint: the Facilitator turns to the user ONCE, waits, and if they steer the room
        answers once — then the meeting proceeds. It does NOT re-pause and sit waiting: a user who
        wants to say more just interjects again (which pauses the room). Re-pausing on every reply
        was what trapped the user saying 'carry on' three times to escape."""
        async for ev in self._checkpoint(kind, announce=True):
            yield ev
        # They continued/wrapped (empty inbox) → proceed. They steered → answer once, then proceed;
        # a 'continue'/'agree' nudge is acknowledged inside _respond_to_inbox with no forced reply.
        if not self._stopped and self._inbox:
            async for ev in self._respond_to_inbox(picker, len(self.people)):
                yield ev

    async def _respond_to_inbox(self, picker, rounds: int):
        """After a checkpoint, if the user steered, let the room actually answer (up to `rounds`
        turns) before we move on. Used at the closing checkpoint, where the main loop is over."""
        n = 0
        while self._inbox and not self._stopped and n < rounds:
            n += 1
            said, target = self._inbox.pop(0)
            kind = _classify_interjection(said)
            for t in (
                Turn(id=f"t{self._n + 1}", who="you", text=said, why="you stepped in", at=self.state.clock),
                Turn(id=f"t{self._n + 2}", who="chair", text=chair_mod.acknowledge(target, kind),
                     why="taking your point", at=self.state.clock),
            ):
                self._record(t)
                yield {"type": "turn", "turn": t}
            if kind in ("agree", "continue"):
                continue   # assent or "keep going" — acknowledge, no reply

            # Who answers: an explicit target, else whoever you named in the text, else the
            # coordinator's pick (two voices for a substantive point).
            if target != "all" and target in self._agents:
                responders = [target]
            else:
                responders = _named_personas(said, self._agents)
                if not responders:
                    pid, _ = await picker.next(self.state)
                    responders = [pid]
                    if len(said.split()) >= 18:  # a meaty steer earns a second voice
                        pid2, _ = await picker.next(self.state)
                        if pid2 not in responders:
                            responders.append(pid2)

            for pid in responders:
                if pid not in self._agents:
                    continue
                yield {"type": "speaking", "who": pid}
                payload = await self._agents[pid].speak(self._cue(pid, "answering you"))
                self._tick()
                if not payload:
                    yield {"type": "passed", "who": pid}
                    continue
                turn = self._turn_from(pid, "answering you", payload)
                self._record(turn)
                yield {"type": "turn", "turn": turn}
                if turn.agreed:
                    yield {"type": "agreed", "item": turn.agreed}

    # -- transcript -------------------------------------------------------

    def _tick(self, seconds: int | None = None) -> None:
        self.state.elapsed = min(
            self.state.elapsed + (seconds or random.randint(18, 44)),
            self.config.duration_minutes * 60,
        )

    def _absorb_orch(self, msg: Any) -> None:
        u = usage_from_result(msg)
        for k in ("input_tokens", "output_tokens", "cache_read_tokens",
                  "cache_write_tokens", "cost_usd"):
            self._orch[k] += u[k]
        self._orch["turns"] += 1

    def _usage_snapshot(self) -> dict[str, Any]:
        """Per-person + per-model + total token/cost picture, as of right now."""
        by_person: list[dict[str, Any]] = []
        by_model: dict[str, dict[str, float]] = {}
        totals = {"input_tokens": 0, "output_tokens": 0,
                  "cache_read_tokens": 0, "cost_usd": 0.0}

        def fold(model: str, u: dict[str, float]) -> None:
            m = by_model.setdefault(
                model or "—",
                {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cost_usd": 0.0},
            )
            for k in ("input_tokens", "output_tokens", "cache_read_tokens", "cost_usd"):
                m[k] += u[k]
                totals[k] += u[k]

        for p in self.people:
            agent = self._agents.get(p.id)
            if not agent:
                continue
            u = agent.usage
            by_person.append({
                "who": p.id, "name": p.name, "model": agent.model,
                "input_tokens": int(u["input_tokens"]), "output_tokens": int(u["output_tokens"]),
                "cache_read_tokens": int(u["cache_read_tokens"]),
                "cost_usd": round(u["cost_usd"], 4), "turns": int(u["turns"]),
            })
            fold(agent.model, u)

        if self._orch["turns"]:
            fold(self.config.recap_model or self.config.coordinator_model or "—", self._orch)

        return {
            "by_person": by_person,
            "by_model": [
                {"model": k, **{kk: (round(vv, 4) if kk == "cost_usd" else int(vv))
                                for kk, vv in v.items()}}
                for k, v in by_model.items()
            ],
            "facilitator": {
                "input_tokens": int(self._orch["input_tokens"]),
                "output_tokens": int(self._orch["output_tokens"]),
                "cost_usd": round(self._orch["cost_usd"], 4),
            },
            "totals": {
                "input_tokens": int(totals["input_tokens"]),
                "output_tokens": int(totals["output_tokens"]),
                "cache_read_tokens": int(totals["cache_read_tokens"]),
                "cost_usd": round(totals["cost_usd"], 4),
            },
        }

    def _record(self, turn: Turn) -> None:
        """Append to state and to the shared minutes. Facilitator-only write."""
        self.state.add(turn)
        self._n += 1
        who = _name(turn.who)
        body = f"# {who} — {turn.at}\n\n_{turn.why}_\n\n{turn.text}\n"
        if turn.note:
            body += f"\n> {turn.note}\n"
        self.workspace.record(self._n, turn.who, body)

    def _prep_cue(self, buckets: list[str]) -> str:
        focus = "; ".join(buckets)
        return (
            f"Before we start, go do your homework on your part of the agenda: {focus}. "
            "Read the reference material that's relevant, run any analysis you need with your "
            "tools (the dataset tools if there's data), then open the meeting with your PREPARED "
            "position: where you land, the specific evidence you actually found, and your one top "
            "concern. Cite what you looked at -- don't guess. Keep it to 3 short sentences."
        )

    async def _run_prep(self, cfg) -> AsyncIterator[dict[str, Any]]:
        """Assign agenda sections to the best-fit people, let them research in
        parallel, then surface each prepared opening as a turn (in a stable
        order). Failures are silent -- a persona that can't prep just doesn't
        get a prepared opening and speaks reactively later."""
        assignments = await chair_mod.assign_agenda(
            cfg.agenda, self.people, cfg.coordinator_model, self.env,
            on_result=self._absorb_orch,
        )
        assignments = {p: b for p, b in assignments.items() if p in self._agents}
        if not assignments:
            return

        order = [p.id for p in self.people if p.id in assignments]
        yield {"type": "preparing", "who": order,
               "buckets": {p: assignments[p] for p in order}}

        # Personas research concurrently; their tool calls are funnelled through
        # a queue so the single run() stream can narrate all of them live rather
        # than the user staring at a static "doing homework" line.
        queue: asyncio.Queue = asyncio.Queue()

        async def _one(pid: str):
            def on_act(tool: str, inp: dict) -> None:
                phrase = activity_mod.friendly(tool, inp)
                if phrase:
                    queue.put_nowait({"type": "activity", "who": pid, "text": phrase})
            try:
                payload = await self._agents[pid].speak(self._prep_cue(assignments[pid]), on_act)
            except Exception:  # noqa: BLE001
                payload = None
            queue.put_nowait({"type": "_done", "who": pid, "payload": payload})
            return pid

        task = asyncio.ensure_future(asyncio.gather(*(_one(p) for p in order)))
        results: dict[str, Any] = {}
        while len(results) < len(order):
            ev = await queue.get()
            if ev.get("type") == "_done":
                results[ev["who"]] = ev["payload"]
                yield {"type": "prepared", "who": ev["who"]}   # this card is finished
            else:
                yield ev
        await task  # surface nothing, but let the gather close cleanly

        for pid in order:
            payload = results.get(pid)
            if not payload:
                continue
            turn = self._turn_from(pid, "prepared position", payload)
            self._record(turn)
            self._tick()
            yield {"type": "turn", "turn": turn}
            if turn.agreed:
                yield {"type": "agreed", "item": turn.agreed}
        yield {"type": "usage", "usage": self._usage_snapshot()}

    def _turn_from(self, pid: str, why: str, payload: dict[str, Any]) -> Turn:
        agreed = None
        text = (payload.get("agreed_text") or "").strip()
        kind = (payload.get("agreed_type") or "").strip()
        if text and kind in ("decision", "constraint", "commitment"):
            agreed = AgreedItem(
                text=text, type=kind, who=_name(pid), at=self.state.clock
            )

        quote = None
        quote_role = None
        target = (payload.get("replying_to") or "").strip()
        if target:
            prior = [t for t in self.state.turns if t.who == target]
            if prior:
                quote = prior[-1].text[:110]
                quote_role = _name(target)

        return Turn(
            id=f"t{self._n + 1}",
            who=pid,
            text=payload.get("text", ""),
            why=payload.get("why") or why,
            at=self.state.clock,
            note=payload.get("note") or None,
            thinking=payload.get("thinking") or None,
            sources=payload.get("sources") or [],
            quote=quote,
            quote_role=quote_role,
            agreed=agreed,
        )

    def _converged(self) -> bool:
        """True when the last three turns show nobody testing anything.

        ``quote`` is set whenever a turn answered someone, so a run of turns
        that answer nobody is a room talking past each other or nodding along.
        Two settled items in three turns is the same smell from the other
        direction: agreement arriving faster than argument.
        """
        spoken = [t for t in self.state.turns if t.who not in ("chair", "you")]
        if len(spoken) < 3:
            return False
        recent = spoken[-3:]
        return not any(t.quote for t in recent) or sum(bool(t.agreed) for t in recent) >= 2

    def _advocate_pick(self, last_who: str) -> str | None:
        """Whoever has been quietest — most likely to hold an untested view."""
        spoken = [t.who for t in self.state.turns if t.who not in ("chair", "you")]
        eligible = [p.id for p in self.people if p.id != last_who]
        return min(eligible, key=spoken.count) if eligible else None

    _TASKS = {
        "answer": (
            "You were asked a direct question. Answer it plainly first — and if "
            "you cannot, say so and say who could. Then say what it changes."
        ),
        "advocate": (
            "The Chair has asked you to argue the other side. Make the "
            "strongest case against what the room just landed on, even if it "
            "isn't your own view, and say plainly that's what you're doing."
        ),
    }

    def _cue(self, pid: str, why: str, closing: bool = False, task: str = "") -> str:
        """What the facilitator says to a persona to prompt its turn."""
        recent = [t for t in self.state.turns[-4:] if t.who != "chair"]
        if not recent:
            context = "You are opening. Say where you stand and why."
        else:
            lines = "\n".join(
                f"{'The person who called the meeting' if t.who == 'you' else _name(t.who)}: {t.text}"
                for t in recent
            )
            context = f"What's just been said:\n\n{lines}"

        if closing:
            instruction = (
                "Close with one commitment — something you will do, first "
                "person. If something is unresolved, say so plainly. No new "
                "questions: there is no time left to answer them."
            )
        elif task in self._TASKS:
            instruction = self._TASKS[task]
        else:
            instruction = f"You're coming in now because: {why}. Say your piece."
        return f"{context}\n\n{instruction}"

    # -- the loop ---------------------------------------------------------

    async def run(self) -> AsyncIterator[dict[str, Any]]:
        cfg = self.config
        self.workspace.setup(cfg.people, cfg.topic)
        self.workspace.seed_notes(cfg.notes)
        self.state.running = True

        async with contextlib.AsyncExitStack() as stack:
            for p in self.people:
                agent = await stack.enter_async_context(
                    PersonaAgent(
                        p,
                        self.workspace,
                        cfg.topic,
                        self.people,
                        env=self.env,
                        extra_mcp=mcp_mod.resolve(cfg.mcp.get(p.id, []), self._getenv),
                        skill_pack=cfg.skill_pack,
                        behaviours=self._behaviours(),
                        turn_budget=(
                            cfg.agent_turns_with_skills
                            if p.skills
                            else cfg.agent_turns
                        ),
                        read_dirs=self.read_dirs,
                        dataset_server=self.dataset_server,
                    )
                )
                self._agents[p.id] = agent

            # Chair opens.
            opening = Turn(
                id="t0",
                who="chair",
                text=chair_mod.opening(cfg.topic, self.people),
                why="setting the frame",
                at=self.state.clock,
            )
            self._record(opening)
            yield {"type": "turn", "turn": opening}

            # Homework: when there's material to research and an agenda to
            # divide, the Facilitator hands each section to the person best
            # placed to dig in. Those people research in parallel and open with
            # a prepared, grounded position -- so the prep is not a wasted call,
            # it *is* the first round of the meeting.
            if self.prep and cfg.agenda:
                async for ev in self._run_prep(cfg):
                    yield ev

            picker = coord_mod.build(cfg.turn_order, self.people, cfg.coordinator_model)
            halfway_done = False
            next_up: tuple[str, str, str] | None = None  # pid, why, task

            # Reserve the tail for the closing round, but never more than a
            # third of the meeting -- otherwise a short run is nothing but
            # commitments.
            closing_len = min(len(self.people), max(1, cfg.max_turns // 3))
            closing_at = cfg.max_turns - closing_len

            for i in range(cfg.max_turns):
                closing = i >= closing_at

                while (self._paused or self._awaiting_you) and not self._stopped:
                    await asyncio.sleep(0.1)
                if self._stopped:
                    break

                # Anything the user said goes in before the next turn, and
                # the Chair acknowledges it -- the design's interruption
                # sequence, minus the focus-to-pause trigger.
                forced: str | None = None
                while self._inbox:
                    said, target = self._inbox.pop(0)
                    kind = _classify_interjection(said)
                    for t in (
                        Turn(
                            id=f"t{self._n + 1}",
                            who="you",
                            text=said,
                            why="you stepped in",
                            at=self.state.clock,
                        ),
                        Turn(
                            id=f"t{self._n + 2}",
                            who="chair",
                            text=chair_mod.acknowledge(target, kind),
                            why="taking your point",
                            at=self.state.clock,
                        ),
                    ):
                        self._record(t)
                        yield {"type": "turn", "turn": t}
                    if kind in ("agree", "continue"):
                        continue   # assent or "keep going" — acknowledge, force no reply
                    if target != "all" and target in self._agents:
                        forced = target
                    else:
                        named = _named_personas(said, self._agents)
                        if named:
                            forced = named[0]

                if closing and i == closing_at:
                    t = Turn(
                        id=f"t{self._n + 1}",
                        who="chair",
                        text=chair_mod.closing(),
                        why="calling the close",
                        at=self.state.clock,
                    )
                    self._record(t)
                    yield {"type": "turn", "turn": t}

                # Precedence: you outrank an unanswered question, which
                # outranks a devil's-advocate call, which outranks the
                # coordinator. Each forced turn is spent once and then the
                # coordinator's fairness cap applies again.
                task = ""
                if forced:
                    pid, why = forced, "you brought them in"
                elif next_up:
                    pid, why, task = next_up
                    next_up = None
                else:
                    pid, why = await picker.next(self.state)
                yield {"type": "speaking", "who": pid}

                payload = await self._agents[pid].speak(
                    self._cue(pid, why, closing, task)
                )
                self._tick()

                # A persona that produced nothing (twice) is passing, not
                # speaking. Recording it would put "(no response)" in the
                # minutes and count against their turn share.
                if payload is None:
                    yield {"type": "passed", "who": pid}
                    continue

                turn = self._turn_from(pid, why, payload)
                self._record(turn)
                yield {"type": "turn", "turn": turn}
                if turn.agreed:
                    yield {"type": "agreed", "item": turn.agreed}
                yield {"type": "usage", "usage": self._usage_snapshot()}

                # A question only counts if there is still room to answer it.
                # Asked during the closing round it would hang unanswered --
                # which is exactly what happened before this existed.
                asked = (payload.get("question_for") or "").strip().lower()
                if cfg.questions and asked and not closing:
                    if asked == "you":
                        self._awaiting_you = pid
                        yield {
                            "type": "question",
                            "who": pid,
                            "text": turn.text,
                            "at": turn.at,
                        }
                    elif asked in self._agents and asked != pid:
                        next_up = (
                            asked,
                            f"answering {_name(pid)}",
                            "answer",
                        )

                # Nobody has tested what the room just settled on: name someone
                # to argue the other side. Once per meeting, and never during
                # the close, so it cannot become a tic.
                if (
                    cfg.devils_advocate
                    and not self._advocate_called
                    and not closing
                    and next_up is None
                    and not self._awaiting_you
                    and self._converged()
                ):
                    advocate = self._advocate_pick(pid)
                    if advocate:
                        self._advocate_called = True
                        t = Turn(
                            id=f"t{self._n + 1}",
                            who="chair",
                            text=chair_mod.push_back(_name(advocate)),
                            why="testing the agreement",
                            at=self.state.clock,
                        )
                        self._record(t)
                        yield {"type": "turn", "turn": t}
                        next_up = (advocate, "arguing the other side", "advocate")

                # Halfway time check.
                halfway_s = (cfg.duration_minutes * 60) // 2
                if not halfway_done and self.state.elapsed >= halfway_s and not closing:
                    halfway_done = True
                    t = Turn(
                        id=f"t{self._n + 1}",
                        who="chair",
                        text=chair_mod.halfway(self.state),
                        why="time check",
                        at=self.state.clock,
                    )
                    self._record(t)
                    yield {"type": "turn", "turn": t}

                    # COLLABORATE checkpoint: interactive pause — steer as much as you like, continue when ready.
                    if cfg.checkpoints and "halfway" not in self._checkpoints_done:
                        self._checkpoints_done.add("halfway")
                        async for ev in self._run_checkpoint("halfway", picker):
                            yield ev

            # COLLABORATE checkpoint before the write-up. Kept INSIDE the async-with so the
            # personas are still connected — if the user steers here, the room answers before
            # the recap instead of the feedback being silently dropped.
            if cfg.checkpoints and not self._stopped and "closing" not in self._checkpoints_done:
                self._checkpoints_done.add("closing")
                async for ev in self._run_checkpoint("closing", picker):
                    yield ev

        self.state.running = False
        yield {"type": "usage", "usage": self._usage_snapshot()}
        recap = await chair_mod.write_recap(
            self.state, cfg.recap_model, agenda=cfg.agenda or None, on_result=self._absorb_orch,
        )
        self.workspace.save_transcript(
            {
                "meeting_id": self.meeting_id,
                "topic": cfg.topic,
                "people": cfg.people,
                "duration_minutes": cfg.duration_minutes,
                # What this room was actually configured with, so two runs
                # can be compared rather than just re-watched.
                "setup": {
                    "models": {p.id: p.model for p in self.people},
                    "tools": {p.id: p.tools for p in self.people},
                    "skills": {p.id: p.skills for p in self.people if p.skills},
                    # Server names only — never the tokens that reached them.
                    "mcp": {k: v for k, v in cfg.mcp.items() if v},
                    "notes": {k: v for k, v in cfg.notes.items() if v.strip()},
                    "coordinator_model": cfg.coordinator_model,
                    "recap_model": cfg.recap_model,
                },
                "elapsed": self.state.elapsed,
                "turns": [t.to_dict() for t in self.state.turns],
                "agreed": [
                    {"text": a.text, "type": a.type, "who": a.who, "at": a.at}
                    for a in self.state.agreed
                ],
                "recap": recap,
                "usage": self._usage_snapshot(),
            }
        )
        yield {"type": "recap", "recap": recap}

        # After the transcript is safely written, so a failure here costs the
        # deck and nothing else.
        if cfg.diagram:
            path, detail = await chair_mod.build_diagram(
                recap,
                self.state.turns,
                self.workspace,
                cfg.topic,
                cfg.coordinator_model,
                cfg.recap_model,
                cfg.skill_pack,
                env=self.env,
                on_result=self._absorb_orch,
            )
            yield {"type": "diagram", "path": path, "detail": detail}

        if cfg.deck:
            path, detail = await chair_mod.build_deck(
                recap, self.workspace, cfg.topic, cfg.recap_model, cfg.skill_pack
            )
            yield {"type": "deck", "path": path, "detail": detail}

        yield {"type": "usage", "usage": self._usage_snapshot()}
        yield {"type": "done", "state": self.state}
