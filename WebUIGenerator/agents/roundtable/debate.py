"""The `debate` engine — a supervisor + society-of-mind hybrid, SDK-native.

An alternative to the classic Meeting, built to A/B against it. Three ideas, layered:

  1. Supervisor fan-out (opening positions): every persona researches in its own fresh
     context, in parallel, and opens with a grounded position. No cross-talk yet.
  2. Society-of-mind debate (rounds): for R≤3 rounds each persona SEES the others' latest
     positions and must sharpen, defend, or concede. One rotating ADVERSARIAL slot per round
     breaks the sycophancy cascade; the question is re-injected each round to fight drift.
  3. Synthesis: the same facilitator recap, which surfaces what stayed open.

The SDK-native bet: personas speak FREE-FORM (no output schema) and record structure by
calling the `meeting` action tools (propose/cite/concede/…). Structure is a byproduct of the
agent acting, not a cage on its language. Fairness is structural (one turn per persona per
round) so there's no coordinator model call.

Interface parity with Meeting (run/interject/hold/wrap_up/resume + state/workspace/config/
meeting_id) so the API session and routes work unchanged.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import replace
from typing import Any, AsyncIterator

from . import activity as activity_mod
from . import chair as chair_mod
from . import personas as roster_mod
from .agent import PersonaAgent
from .meeting import _name  # crash-proof display-name helper
from .meeting_actions import build_actions_server
from .structured import usage_from_result
from .types import AgreedItem, MeetingConfig, MeetingState, Turn
from .workspace import Workspace, new_meeting_id

_AGREED_KINDS = {"decision", "constraint", "commitment"}


class DebateMeeting:
    def __init__(
        self,
        config: MeetingConfig,
        *,
        meeting_id: str | None = None,
        env: dict[str, str] | None = None,
        read_dirs: tuple[str, ...] = (),
        dataset_server: Any = None,
    ) -> None:
        self.config = config
        self.env = env or {}
        self.read_dirs = read_dirs
        self.dataset_server = dataset_server
        self.meeting_id = meeting_id or new_meeting_id(config.topic)
        self.workspace = Workspace(config.workspace_root, self.meeting_id)
        self.people = [self._configure(p) for p in roster_mod.roster(config.people)]
        self.state = MeetingState(config=config)

        self._agents: dict[str, PersonaAgent] = {}
        self._buffers: dict[str, list[dict]] = {}
        self._positions: dict[str, str] = {}     # persona id -> latest stated position
        self._n = 0

        # controls (same semantics as Meeting)
        self._paused = False
        self._stopped = False
        self._inbox: list[tuple[str, str]] = []
        self._awaiting_you: str | None = None

        self._orch = {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0,
                      "cache_write_tokens": 0, "cost_usd": 0.0, "turns": 0}

    def _configure(self, p):
        """Apply this meeting's per-persona overrides (model/tools/skills) on a copy — the
        module roster is shared process-wide, so never mutate it."""
        changes: dict[str, Any] = {}
        if model := self.config.models.get(p.id):
            changes["model"] = model
        if tools := self.config.tools.get(p.id):
            changes["tools"] = list(tools)
        if skills := self.config.skills.get(p.id):
            changes["skills"] = list(skills)
        return replace(p, **changes) if changes else p

    # ── external controls ────────────────────────────────────────────────────
    def interject(self, text: str, target: str = "all") -> None:
        if target == "all" and self._awaiting_you:
            target = self._awaiting_you
        self._inbox.append((text, target))
        self._awaiting_you = None

    def resume(self) -> None:
        self._paused = False

    def hold(self, paused: bool = True) -> None:
        self._paused = paused

    def wrap_up(self) -> None:
        self._stopped = True

    # ── helpers ──────────────────────────────────────────────────────────────
    def _absorb_orch(self, msg: Any) -> None:
        u = usage_from_result(msg)
        for k in ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens", "cost_usd"):
            self._orch[k] += u[k]
        self._orch["turns"] += 1

    def _usage_snapshot(self) -> dict[str, Any]:
        by_person, by_model = [], {}
        totals = {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cost_usd": 0.0}

        def fold(model, u):
            m = by_model.setdefault(model or "—",
                {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cost_usd": 0.0})
            for k in ("input_tokens", "output_tokens", "cache_read_tokens", "cost_usd"):
                m[k] += u[k]; totals[k] += u[k]

        for p in self.people:
            a = self._agents.get(p.id)
            if not a:
                continue
            u = a.usage
            by_person.append({"who": p.id, "name": p.name, "model": a.model,
                "input_tokens": int(u["input_tokens"]), "output_tokens": int(u["output_tokens"]),
                "cache_read_tokens": int(u["cache_read_tokens"]), "cost_usd": round(u["cost_usd"], 4),
                "turns": int(u["turns"])})
            fold(a.model, u)
        if self._orch["turns"]:
            fold(self.config.recap_model or self.config.coordinator_model or "—", self._orch)
        return {
            "by_person": by_person,
            "by_model": [{"model": k, **{kk: (round(vv, 4) if kk == "cost_usd" else int(vv)) for kk, vv in v.items()}} for k, v in by_model.items()],
            "facilitator": {"input_tokens": int(self._orch["input_tokens"]), "output_tokens": int(self._orch["output_tokens"]), "cost_usd": round(self._orch["cost_usd"], 4)},
            "totals": {k: (round(v, 4) if k == "cost_usd" else int(v)) for k, v in totals.items()},
        }

    def _record(self, turn: Turn) -> None:
        self.state.add(turn)
        self._n += 1
        self.state.elapsed = min(self.state.elapsed + 25, self.config.duration_minutes * 60)
        body = f"# {_name(turn.who)} — {turn.at}\n\n_{turn.why}_\n\n{turn.text}\n"
        if turn.note:
            body += f"\n> {turn.note}\n"
        self.workspace.record(self._n, turn.who, body)

    def _drain_actions(self, pid: str) -> dict[str, Any]:
        """Turn the persona's tool calls this turn into the structured side of a Turn."""
        buf = self._buffers.get(pid, [])
        actions, sources, notes = list(buf), [], []
        agreed = None
        question = None
        buf.clear()
        for a in actions:
            act = a.get("action")
            if act == "cite":
                sources.append(a["source"] if not a.get("claim") else f'{a["claim"]} — {a["source"]}')
            elif act == "propose":
                if a["kind"] in _AGREED_KINDS and agreed is None:
                    agreed = AgreedItem(text=a["text"], type=a["kind"], who=_name(pid), at=self.state.clock)
                else:
                    notes.append(f'{a["kind"]}: {a["text"]}')
            elif act == "concede":
                notes.append(f'concedes: {a["point"]}')
            elif act == "defer_to":
                notes.append(f'→ {_name(a["who"])}')
            elif act == "ask_user":
                question = a["question"]
        return {"sources": sources, "agreed": agreed, "note": "; ".join(notes), "question": question}

    def _num_rounds(self) -> int:
        # Du et al.: 3 rounds capture most of the gain. Scale gently with the meeting length.
        return max(1, min(3, self.config.max_turns // max(1, len(self.people))))

    # ── cue builders ─────────────────────────────────────────────────────────
    def _topic(self) -> str:
        return self.config.topic.split("\n\n")[0]

    def _opening_cue(self) -> str:
        return (
            f"The question on the table: {self._topic()}\n\n"
            "You're opening. First do your homework through YOUR lens — read the reference "
            "material that matters to you, query the data with your tools if there's data, then "
            "state where you actually stand, grounded in what you found. Call cite() for each real "
            "piece of evidence and propose() for anything concrete (a decision, constraint, risk, "
            "or assumption to validate). Speak plainly, a few sentences — don't pad."
        )

    def _round_cue(self, pid: str, rnd: int, adversary: str) -> str:
        others = "\n".join(
            f"- {_name(o)}: {self._positions[o]}" for o in self._positions if o != pid
        ) or "(no one has spoken yet)"
        adv = ""
        if pid == adversary:
            adv = ("\nYou are the designated skeptic this round: argue against where the room is "
                   "converging. Find the strongest objection nobody has raised — even if it isn't "
                   "your instinct. A debate is only worth having if someone tests it.")
        return (
            f"Round {rnd}. Keep the question in view: {self._topic()}\n\n"
            f"Where the others just landed:\n{others}\n\n"
            "Now sharpen, defend, or change your position in light of that. If someone genuinely "
            "moved you, say so with concede(). Land concrete outcomes with propose(), back claims "
            f"with cite(), and hand off with defer_to() if the next point is someone else's.{adv}\n"
            "Keep it tight — one sharp contribution, a few sentences."
        )

    # ── phases ────────────────────────────────────────────────────────────────
    async def _turn(self, pid: str, cue: str, why: str) -> AsyncIterator[dict[str, Any]]:
        def on_act(tool, inp):
            phrase = activity_mod.friendly(tool, inp)
            if phrase and not tool.endswith(("propose", "cite", "ask_user", "defer_to", "concede")):
                self._activity_q.put_nowait({"type": "activity", "who": pid, "text": phrase})

        text = await self._agents[pid].speak_free(cue, on_act)
        extra = self._drain_actions(pid)
        if not text:
            yield {"type": "passed", "who": pid}
            return
        self._positions[pid] = text
        turn = Turn(id=f"t{self._n + 1}", who=pid, text=text, why=why, at=self.state.clock,
                    note=extra["note"] or None, sources=extra["sources"], agreed=extra["agreed"])
        self._record(turn)
        yield {"type": "turn", "turn": turn}
        if turn.agreed:
            yield {"type": "agreed", "item": turn.agreed}
        if extra["question"]:
            self._awaiting_you = pid
            yield {"type": "question", "who": pid, "text": extra["question"], "at": turn.at}
        yield {"type": "usage", "usage": self._usage_snapshot()}

    async def _opening_positions(self) -> AsyncIterator[dict[str, Any]]:
        order = [p.id for p in self.people]
        yield {"type": "preparing", "who": order, "buckets": {}}
        q: asyncio.Queue = asyncio.Queue()

        async def one(pid):
            def on_act(tool, inp):
                phrase = activity_mod.friendly(tool, inp)
                if phrase and not tool.endswith(("propose", "cite", "ask_user", "defer_to", "concede")):
                    q.put_nowait({"type": "activity", "who": pid, "text": phrase})
            try:
                text = await self._agents[pid].speak_free(self._opening_cue(), on_act)
            except Exception:  # noqa: BLE001
                text = None
            q.put_nowait({"type": "_done", "who": pid, "text": text})

        task = asyncio.ensure_future(asyncio.gather(*(one(p) for p in order)))
        results: dict[str, Any] = {}
        while len(results) < len(order):
            ev = await q.get()
            if ev.get("type") == "_done":
                results[ev["who"]] = ev["text"]
                yield {"type": "prepared", "who": ev["who"]}
            else:
                yield ev
        await task

        for pid in order:
            text = results.get(pid)
            extra = self._drain_actions(pid)
            if not text:
                continue
            self._positions[pid] = text
            turn = Turn(id=f"t{self._n + 1}", who=pid, text=text, why="opening position",
                        at=self.state.clock, note=extra["note"] or None,
                        sources=extra["sources"], agreed=extra["agreed"])
            self._record(turn)
            yield {"type": "turn", "turn": turn}
            if turn.agreed:
                yield {"type": "agreed", "item": turn.agreed}
        yield {"type": "usage", "usage": self._usage_snapshot()}

    async def _drain_user(self) -> AsyncIterator[dict[str, Any]]:
        """Fold any user interjection in as a 'you' turn between persona turns, and feed it to the
        room as a steer (added to every persona's next-round view via _positions)."""
        while self._inbox:
            said, _target = self._inbox.pop(0)
            t = Turn(id=f"t{self._n + 1}", who="you", text=said, why="you stepped in", at=self.state.clock)
            self._record(t)
            self._positions["you"] = said   # the room sees the user's steer next turn
            yield {"type": "turn", "turn": t}

    # ── main loop ──────────────────────────────────────────────────────────────
    async def run(self) -> AsyncIterator[dict[str, Any]]:
        cfg = self.config
        self.workspace.setup(cfg.people, cfg.topic)
        self.workspace.seed_notes(cfg.notes)
        self.state.running = True
        self._activity_q = asyncio.Queue()  # unused drain target for sequential turns

        async with contextlib.AsyncExitStack() as stack:
            for p in self.people:
                server, buf = build_actions_server()
                agent = await stack.enter_async_context(PersonaAgent(
                    p, self.workspace, cfg.topic, self.people, env=self.env,
                    behaviours=(), turn_budget=cfg.agent_turns, read_dirs=self.read_dirs,
                    dataset_server=self.dataset_server, free_form=True, actions_server=server,
                ))
                self._agents[p.id] = agent
                self._buffers[p.id] = buf

            # Facilitator frames it (template — no model call).
            opening = Turn(id="t0", who="chair", text=chair_mod.opening(cfg.topic, self.people),
                           why="setting the frame", at=self.state.clock)
            self._record(opening)
            yield {"type": "turn", "turn": opening}

            # Phase 1 — opening positions (parallel, grounded).
            async for ev in self._opening_positions():
                yield ev

            # Phase 2 — debate rounds.
            rounds = self._num_rounds()
            for r in range(rounds):
                if self._stopped:
                    break
                yield {"type": "round", "n": r + 1, "of": rounds}
                adversary = self.people[r % len(self.people)].id
                order = self.people[r % len(self.people):] + self.people[:r % len(self.people)]
                prior_agreed = len(self.state.agreed)
                for p in order:
                    while (self._paused or self._awaiting_you) and not self._stopped:
                        await asyncio.sleep(0.1)
                    if self._stopped:
                        break
                    async for ev in self._drain_user():
                        yield ev
                    yield {"type": "speaking", "who": p.id}
                    async for ev in self._turn(p.id, self._round_cue(p.id, r + 1, adversary), f"round {r + 1}"):
                        yield ev
                # Convergence: a full round that settled nothing new is a room going in circles.
                if not self._stopped and len(self.state.agreed) == prior_agreed and r >= 1:
                    break

            # Phase 3 — synthesis.
            self.state.running = False
            yield {"type": "usage", "usage": self._usage_snapshot()}
            recap = await chair_mod.write_recap(
                self.state, cfg.recap_model, agenda=cfg.agenda or None, on_result=self._absorb_orch)
            self.workspace.save_transcript({
                "meeting_id": self.meeting_id, "topic": cfg.topic, "people": cfg.people,
                "duration_minutes": cfg.duration_minutes, "engine": "debate",
                "setup": {"models": {p.id: p.model for p in self.people}, "coordinator_model": cfg.coordinator_model, "recap_model": cfg.recap_model},
                "elapsed": self.state.elapsed,
                "turns": [t.to_dict() for t in self.state.turns],
                "agreed": [{"text": a.text, "type": a.type, "who": a.who, "at": a.at} for a in self.state.agreed],
                "recap": recap, "usage": self._usage_snapshot(),
            })
            yield {"type": "recap", "recap": recap}

            if cfg.diagram:
                path, detail = await chair_mod.build_diagram(
                    recap, self.state.turns, self.workspace, cfg.topic,
                    cfg.coordinator_model, cfg.recap_model, cfg.skill_pack,
                    env=self.env, on_result=self._absorb_orch)
                yield {"type": "diagram", "path": path, "detail": detail}

        yield {"type": "usage", "usage": self._usage_snapshot()}
        yield {"type": "done", "state": self.state}
