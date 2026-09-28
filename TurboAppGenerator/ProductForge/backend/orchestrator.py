"""
Product Forge Orchestrator — Manages multi-agent collaboration through product stages.

Each stage has participants who discuss/collaborate, then produce an artifact.
Conversations flow: ideation -> PRD -> TRD -> design -> stories -> tasks -> test_cases -> review

Two-tier LLM strategy:
- Discussion rounds use the cheaper DRAFT model (Haiku) for speed/cost
- Artifact generation rounds use the premium ARTIFACT model (Sonnet) for quality + higher token limit

Uses the shared persona-agent catalog (AgentPlatform/catalog/, via
AgentPlatform.core.registry) — each agent has its own config.yaml with
skills, guardrails, and guidelines.
"""

import json
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable


def slugify(text: str, max_len: int = 50) -> str:
    """Convert text to a filesystem-safe folder name."""
    slug = text.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug[:max_len]

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "artifacts"
SESSIONS_DIR = Path(__file__).resolve().parent.parent / "sessions"

sys.path.insert(0, str(Path(__file__).resolve().parent))

SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def load_config():
    with open(CONFIG_DIR / "agents.json", encoding="utf-8") as f:
        return json.load(f)


# Stages where technology choices actually get made — the only stages the
# tech-stack guardrails config (if present) gets injected into.
TECH_STACK_GUARDRAIL_STAGES = {"trd", "design", "specs", "tasks"}

# What belongs in each artifact, and — just as important — what doesn't and
# where that content actually belongs instead. Without this, agents tend to
# echo whatever's in the raw product idea or prior artifacts regardless of
# which document they're currently writing (e.g. a PRD restating the user's
# own "SQLite database" mention as a Technical Architecture section with
# CREATE TABLE statements). Injected into every artifact stage's generation
# instruction below, keyed by stage id (see agents.json's "stages" list).
STAGE_SCOPE = {
    "prd": (
        "PRD.md covers business requirements only — the problem, personas, goals/success "
        "metrics, and WHAT the feature set is. Do NOT mention specific technologies, "
        "frameworks, databases, tables, schemas, or API endpoints — even if the product idea "
        "itself mentions them. Technology and architecture decisions belong in TRD.md and "
        "SOLUTION_DESIGN.md, not here."
    ),
    "trd": (
        "TRD.md covers business rules, data flows, integration points, and NAMED technology "
        "choices with rationale — not implementation. Do NOT include SQL, schemas, API "
        "request/response payloads, or code — those belong in SPECS.md. Do NOT re-derive the "
        "business problem or personas already covered in PRD.md — reference them briefly instead."
    ),
    "design": (
        "SOLUTION_DESIGN.md covers architecture, component design, and conceptual data/API "
        "models at a diagram/description level — not implementation. Do NOT include full SQL "
        "DDL, complete field-by-field API request/response schemas, or code — those belong in "
        "SPECS.md. Do NOT restate the business requirements already in PRD.md."
    ),
    "stories": (
        "EPICS_AND_STORIES.md covers epics and user stories with acceptance criteria only — "
        "WHAT needs to be built and how success is verified, from a user's perspective. Do NOT "
        "include technical implementation breakdown (that belongs in TASKS.md) or "
        "architecture/schema details (those belong in TRD.md / SOLUTION_DESIGN.md)."
    ),
    "tasks": (
        "TASKS.md covers implementation task breakdown with effort estimates — the work items "
        "needed to build each story. Do NOT include actual code, SQL, or API contracts (those "
        "belong in SPECS.md) or re-derive acceptance criteria already defined in "
        "EPICS_AND_STORIES.md."
    ),
    "specs": (
        "SPECS.md is the ONLY document in this pipeline where code, SQL DDL, type definitions, "
        "and full API contracts belong — every other document (PRD, TRD, SOLUTION_DESIGN, "
        "EPICS_AND_STORIES, TASKS) is intentionally kept at a conceptual/business level. Be as "
        "precise and code-ready as possible here."
    ),
    "test_cases": (
        "TEST_CASES.md covers test case definitions only — preconditions, steps, expected "
        "results. Do NOT redefine feature requirements (already in PRD.md / "
        "EPICS_AND_STORIES.md) or propose implementation changes."
    ),
    "review": (
        "REVIEW.md covers cross-artifact review findings only — gaps, inconsistencies, and "
        "risks found across the other artifacts. Do NOT introduce new requirements, features, "
        "or technology decisions — flag issues for the appropriate owning document instead."
    ),
}


def load_tech_stack_guardrails() -> dict | None:
    """Load the optional tech-stack guardrails config. Returns None if not configured."""
    path = CONFIG_DIR / "tech_stack_guardrails.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def list_tech_stack_profiles() -> list[dict]:
    """Return [{id, label, description}] for all configured profiles — for a UI picker."""
    config = load_tech_stack_guardrails()
    if not config:
        return []
    return [
        {"id": pid, "label": p.get("label", pid), "description": p.get("description", "")}
        for pid, p in config.get("profiles", {}).items()
    ]


def resolve_tech_stack_profile(config: dict | None, profile_id: str | None) -> tuple[str | None, dict | None]:
    """Pick a profile from the guardrails config.

    Falls back to the config's default_profile, then to whichever profile is
    listed first, if the requested id doesn't exist. Returns (id, profile_dict),
    or (None, None) if no guardrails config / no profiles are defined.
    """
    if not config:
        return None, None
    profiles = config.get("profiles", {})
    if not profiles:
        return None, None
    pid = profile_id if profile_id in profiles else config.get("default_profile")
    if pid not in profiles:
        pid = next(iter(profiles))
    return pid, profiles[pid]


def _format_tech_stack_guardrails(config: dict, profile: dict) -> str:
    """Render the resolved tech-stack profile as a prompt-ready instruction block."""
    lines = ["## TECH STACK GUARDRAILS (MANDATORY DEFAULTS)", f"Active profile: {profile.get('label', '')}"]
    for rule in config.get("shared_rules", []):
        lines.append(f"- {rule}")
    for rule in profile.get("rules", []):
        lines.append(f"- {rule}")
    for key, spec in profile.get("components", {}).items():
        lines.append(f"\n### {spec.get('label', key)}")
        if spec.get("primary"):
            lines.append(f"- Default choice: {spec['primary']}")
        if spec.get("allowed_alternatives"):
            lines.append(f"- Also allowed: {', '.join(spec['allowed_alternatives'])}")
        if spec.get("prohibited"):
            lines.append(f"- Do NOT use: {', '.join(spec['prohibited'])}")
        if spec.get("notes"):
            lines.append(f"- Notes: {spec['notes']}")
    return "\n".join(lines)


def get_agent_instance(agent_id: str):
    """Instantiate an agent from the shared AgentPlatform catalog.

    Previously loaded each agent.py by file path via importlib
    (importlib.util.spec_from_file_location) specifically to dodge a Python
    package-name collision (this file's own ProductForge/agents package vs.
    WebUIGenerator's same-named agents package). AgentPlatform is a uniquely
    named package with no such collision, so a normal registry lookup works.
    """
    from AgentPlatform.core.registry import get_agent
    try:
        return get_agent(agent_id)
    except ValueError:
        return None


class ForgeSession:
    """A single product forge session — takes an idea through all stages."""

    def __init__(self, product_idea: str, session_id: str = None, project_name: str = None, draft_mode: bool = False, tech_profile: str = None):
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.project_name = project_name or ""
        self.product_idea = product_idea
        self.draft_mode = draft_mode
        self.folder_name = slugify(project_name) if project_name else slugify(product_idea)
        self.config = load_config()
        self.tech_stack_config = load_tech_stack_guardrails()
        self.tech_profile_id, self._tech_profile = resolve_tech_stack_profile(self.tech_stack_config, tech_profile)
        self.stages = self.config["stages"]
        self.conversation_log: list[dict] = []
        self.artifacts: dict[str, str] = {}
        self.current_stage_idx = 0
        self.status = "ready"
        # Cooperative stop request (see request_cancel/_check_cancelled) — checked
        # between agent turns/stages, not persisted, since it only ever makes sense
        # for the in-memory session a background thread is actively running.
        self._cancel_requested = False
        self.on_message: Callable | None = None
        self.created_at = datetime.now().isoformat()
        self.output_dir = ARTIFACTS_DIR / self.folder_name
        if self.output_dir.exists():
            self.output_dir = ARTIFACTS_DIR / f"{self.folder_name}_{self.session_id}"

        # Token usage tracking
        self.token_usage: dict = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost_usd": 0.0,
            "by_stage": {},
            "by_artifact": {},
            "by_model": {},
        }

        # Artifact version history
        self.artifact_versions: dict[str, list[dict]] = {}

        # Stage ids that were deliberately skipped via run_selected()
        self.skipped_stages: set[str] = set()

        # Per-session participant overrides — {stage_id: [agent_id, ...]}.
        # Defaults (self.stages[i]["participants"]) cover most projects; this
        # lets a user add/remove an agent for one stage in one session without
        # touching the shared config. Only settable for a stage that hasn't
        # started yet — see set_stage_participants() and _effective_participants().
        self.stage_participants_override: dict[str, list[str]] = {}

        # Delta-aware regeneration state (populated only during run_from_stage)
        self._rerun_delta: str | None = None
        self._rerun_previous_artifacts: dict[str, str] | None = None

        # Load agent instances from standalone packages
        self._agents = {}
        for agent_cfg in self.config["agents"]:
            aid = agent_cfg["id"]
            instance = get_agent_instance(aid)
            if instance:
                self._agents[aid] = instance
            else:
                self._agents[aid] = None

    def _ensure_output_dir(self):
        """Create the output directory on first write."""
        if not self.output_dir.exists():
            self.output_dir.mkdir(parents=True, exist_ok=True)

    def _version_artifact(self, artifact_name: str, reason: str = ""):
        """Save current artifact content as a versioned snapshot before overwriting."""
        if artifact_name not in self.artifacts:
            return
        versions_dir = self.output_dir / "versions"
        versions_dir.mkdir(parents=True, exist_ok=True)
        version_num = len([
            v for v in self.artifact_versions.get(artifact_name, [])
        ]) + 1
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = artifact_name.rsplit(".", 1)[0] if "." in artifact_name else artifact_name
        ext = artifact_name.rsplit(".", 1)[1] if "." in artifact_name else "md"
        version_filename = f"{base_name}_v{version_num}_{timestamp}.{ext}"
        version_path = versions_dir / version_filename
        version_path.write_text(self.artifacts[artifact_name], encoding="utf-8")

        if artifact_name not in self.artifact_versions:
            self.artifact_versions[artifact_name] = []
        self.artifact_versions[artifact_name].append({
            "version": version_num,
            "filename": version_filename,
            "timestamp": datetime.now().isoformat(),
            "reason": reason,
            "char_count": len(self.artifacts[artifact_name]),
        })

    def _get_agent_info(self, agent_id: str) -> dict:
        """Get agent display info."""
        instance = self._agents.get(agent_id)
        if instance:
            return instance.get_info()
        for a in self.config["agents"]:
            if a["id"] == agent_id:
                return a
        return {"id": agent_id, "name": agent_id, "short": agent_id[:3].upper(), "color": "#6b7280"}

    def _effective_participants(self, stage: dict) -> list[str]:
        """This stage's real participant list — the user's override for this
        session if one was set via set_stage_participants(), else the shared
        config default. The first entry is always the lead/author (see
        run_stage()'s final round) regardless of which list this came from."""
        return self.stage_participants_override.get(stage["id"], stage["participants"])

    def _stage_status(self, stage_idx: int) -> str:
        """Same status logic get_state() renders per stage, callable for one
        stage without building the whole list — used to gate
        set_stage_participants() to stages that haven't started yet."""
        stage_id = self.stages[stage_idx]["id"]
        if stage_id in self.skipped_stages:
            return "skipped"
        if stage_idx < self.current_stage_idx:
            return "complete"
        if stage_idx == self.current_stage_idx and self.status == "running":
            return "running"
        return "pending"

    def set_stage_participants(self, stage_id: str, agent_ids: list[str]) -> tuple[bool, str]:
        """Override one stage's participant list for this session only —
        the shared config default is untouched, and every OTHER session
        keeps using it. Only allowed while the stage is still "pending" (not
        yet started): once a stage has run, its artifact already reflects
        whoever actually participated, so changing the roster after the fact
        would be misleading rather than useful.
        """
        stage_idx = next((i for i, s in enumerate(self.stages) if s["id"] == stage_id), None)
        if stage_idx is None:
            return False, f"Unknown stage '{stage_id}'"
        if self._stage_status(stage_idx) != "pending":
            return False, "This stage has already started — its team can't be changed now"

        seen = set()
        deduped = [a for a in agent_ids if not (a in seen or seen.add(a))]
        if not deduped:
            return False, "A stage needs at least one participant"
        known_ids = {a["id"] for a in self.config["agents"]}
        unknown = [a for a in deduped if a not in known_ids]
        if unknown:
            return False, f"Unknown agent id(s): {', '.join(unknown)}"

        self.stage_participants_override[stage_id] = deduped
        self._save_session()
        return True, "OK"

    def _emit(self, event_type: str, data: dict):
        entry = {
            "id": str(uuid.uuid4())[:8],
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            **data,
        }
        self.conversation_log.append(entry)
        if self.on_message:
            self.on_message(entry)
        return entry

    def _track_usage(self, stage_id: str, model: str, input_tokens: int, output_tokens: int, cost: float, is_artifact: bool = False, artifact_name: str = None):
        """Track token usage for cost reporting."""
        self.token_usage["total_input_tokens"] += input_tokens
        self.token_usage["total_output_tokens"] += output_tokens
        self.token_usage["total_cost_usd"] += cost

        if stage_id not in self.token_usage["by_stage"]:
            self.token_usage["by_stage"][stage_id] = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
        self.token_usage["by_stage"][stage_id]["input_tokens"] += input_tokens
        self.token_usage["by_stage"][stage_id]["output_tokens"] += output_tokens
        self.token_usage["by_stage"][stage_id]["cost_usd"] += cost

        if model not in self.token_usage["by_model"]:
            self.token_usage["by_model"][model] = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "calls": 0}
        self.token_usage["by_model"][model]["input_tokens"] += input_tokens
        self.token_usage["by_model"][model]["output_tokens"] += output_tokens
        self.token_usage["by_model"][model]["cost_usd"] += cost
        self.token_usage["by_model"][model]["calls"] += 1

        if is_artifact and artifact_name:
            self.token_usage["by_artifact"][artifact_name] = {
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost,
            }

    def _build_context(self, stage_id: str) -> str:
        """Build conversation context from prior stages."""
        context_parts = [f"PRODUCT IDEA: {self.product_idea}\n"]
        if self._tech_profile and stage_id in TECH_STACK_GUARDRAIL_STAGES:
            context_parts.append(_format_tech_stack_guardrails(self.tech_stack_config, self._tech_profile) + "\n")
        for artifact_name, content in self.artifacts.items():
            context_parts.append(f"--- {artifact_name} ---\n{content[:10000]}\n")
        stage_msgs = [
            m for m in self.conversation_log
            if m.get("stage") == stage_id and m["type"] == "message"
        ]
        if stage_msgs:
            context_parts.append("--- DISCUSSION SO FAR ---")
            for m in stage_msgs[-12:]:
                info = self._get_agent_info(m["agent_id"])
                context_parts.append(f"\n[{info.get('name', m['agent_id'])}]: {m['content'][:2000]}")
        return "\n".join(context_parts)

    def _agent_respond_streaming(self, agent_id: str, stage_id: str, task_instruction: str, round_num: int, is_artifact_round: bool = False) -> str:
        """Get a streaming response from an agent, emitting tokens in real-time.

        Uses DRAFT_MODEL for discussion rounds and ARTIFACT_MODEL for artifact generation.
        """
        from llm_client import (
            DRAFT_MODEL, ARTIFACT_MODEL,
            DEFAULT_MAX_TOKENS_DISCUSSION, DEFAULT_MAX_TOKENS_ARTIFACT,
            DEFAULT_MAX_TOKENS_ARTIFACT_DRAFT, TRUNCATION_FINISH_REASONS,
            calculate_cost,
        )
        # Same LiteLLM/Bedrock client the rest of the platform uses (see
        # WebUIGenerator/agents/llm.py) instead of this project's own,
        # simpler one — llm_client now only holds model-tier/pricing config,
        # not a second client implementation.
        from agents.llm import chat_stream_with_usage, get_selected_model, pick_cheapest_reachable_model

        instance = self._agents.get(agent_id)
        context = self._build_context(stage_id)
        info = self._get_agent_info(agent_id)

        # Select model tier based on whether this is artifact generation.
        # Draft mode doesn't just want "Haiku" — it wants whatever's cheapest
        # AND actually reachable right now, so a provider hiccup on the
        # hardcoded cheap model doesn't quietly break every draft run, and a
        # newly-added cheaper model gets picked up automatically. That choice
        # is passed as force_model below so it genuinely gets used instead of
        # being silently overridden by the header's own global selection
        # (which is what happens to every other model tier picked here).
        force_model = None
        if self.draft_mode:
            draft_choice = pick_cheapest_reachable_model()
            model = draft_choice["model"] if draft_choice else DRAFT_MODEL
            if draft_choice:
                force_model = (draft_choice["provider"], draft_choice["model"])
            max_tokens = DEFAULT_MAX_TOKENS_ARTIFACT_DRAFT if is_artifact_round else DEFAULT_MAX_TOKENS_DISCUSSION
        elif is_artifact_round:
            model = ARTIFACT_MODEL
            max_tokens = DEFAULT_MAX_TOKENS_ARTIFACT
        else:
            model = DRAFT_MODEL
            max_tokens = DEFAULT_MAX_TOKENS_DISCUSSION

        # Emit "agent is starting to speak"
        msg_id = str(uuid.uuid4())[:8]
        # Outside draft mode, chat_stream_with_usage() below always defers to
        # the header's global model selection regardless of the `model` tier
        # picked above — so report the model that's actually going to be
        # used, not the guess. In draft mode, force_model above IS what's
        # actually going to be used, so report that instead.
        effective_model = model if force_model else get_selected_model()["model"]
        self._emit("message_start", {
            "msg_id": msg_id,
            "stage": stage_id,
            "round": round_num,
            "agent_id": agent_id,
            "agent_name": info.get("name", agent_id),
            "agent_short": info.get("short", agent_id[:3].upper()),
            "agent_color": info.get("color", "#6b7280"),
            "model": effective_model,
            "is_artifact": is_artifact_round,
        })

        full_response = ""
        usage_ref = {"model": model, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}

        def _stream_and_accumulate(token_gen) -> str:
            """Consume a token generator, emitting chunks to listeners, and return the full text."""
            text = ""
            chunk_buffer = ""
            for token in token_gen:
                text += token
                chunk_buffer += token
                if len(chunk_buffer) >= 20 or '\n' in chunk_buffer:
                    if self.on_message:
                        self.on_message({
                            "type": "token",
                            "msg_id": msg_id,
                            "content": chunk_buffer,
                            "timestamp": datetime.now().isoformat(),
                        })
                    chunk_buffer = ""
            if chunk_buffer and self.on_message:
                self.on_message({
                    "type": "token",
                    "msg_id": msg_id,
                    "content": chunk_buffer,
                    "timestamp": datetime.now().isoformat(),
                })
            return text

        try:
            if instance:
                full_prompt, messages = instance._build_prompt_and_messages(context, task_instruction, stage=stage_id)
            else:
                agent_cfg = self._get_agent_info(agent_id)
                full_prompt = agent_cfg.get("role", f"You are a {agent_cfg.get('name', agent_id)}.")
                messages = [{"role": "user", "content": f"{context}\n\n{task_instruction}"}]

            token_gen, usage_ref = chat_stream_with_usage(
                messages, system=full_prompt, model=model, max_tokens=max_tokens, force_model=force_model
            )
            full_response = _stream_and_accumulate(token_gen)
            usage_ref["cost_usd"] = calculate_cost(
                usage_ref.get("model", model), usage_ref["input_tokens"], usage_ref["output_tokens"]
            )

            # The model may hit the max_tokens ceiling before finishing a long
            # artifact. Rather than ship a truncated document, keep asking it to
            # continue exactly where it left off until it reports a natural stop.
            MAX_CONTINUATIONS = 6
            continuations = 0
            while (
                usage_ref.get("finish_reason") in TRUNCATION_FINISH_REASONS
                and full_response
                and continuations < MAX_CONTINUATIONS
            ):
                continuations += 1
                continuation_messages = messages + [
                    {"role": "assistant", "content": full_response},
                    {"role": "user", "content": (
                        "Your previous response was cut off before it was complete. "
                        "Continue EXACTLY where you left off — do not repeat, summarize, "
                        "or rewrite any content already written above. Resume mid-sentence "
                        "if needed and keep going until the document is fully complete."
                    )},
                ]
                cont_gen, cont_usage_ref = chat_stream_with_usage(
                    continuation_messages, system=full_prompt, model=model, max_tokens=max_tokens, force_model=force_model
                )
                continuation_text = _stream_and_accumulate(cont_gen)
                if not continuation_text:
                    break
                full_response += continuation_text
                usage_ref["input_tokens"] += cont_usage_ref.get("input_tokens", 0)
                usage_ref["output_tokens"] += cont_usage_ref.get("output_tokens", 0)
                usage_ref["finish_reason"] = cont_usage_ref.get("finish_reason")
                usage_ref["cost_usd"] = calculate_cost(
                    usage_ref.get("model", model), usage_ref["input_tokens"], usage_ref["output_tokens"]
                )
        except Exception as e:
            full_response = f"[Error: LLM unavailable — {e}]"
            if self.on_message:
                self.on_message({
                    "type": "token",
                    "msg_id": msg_id,
                    "content": full_response,
                    "timestamp": datetime.now().isoformat(),
                })

        # Estimate tokens from response length if usage not reported by API
        if usage_ref["output_tokens"] == 0 and full_response:
            estimated_output = len(full_response) // 4
            estimated_input = len(context + task_instruction) // 4
            usage_ref["output_tokens"] = estimated_output
            usage_ref["input_tokens"] = estimated_input
            usage_ref["cost_usd"] = calculate_cost(model, estimated_input, estimated_output)

        # Track usage
        stage_cfg = next((s for s in self.stages if s["id"] == stage_id), {})
        artifact_name = stage_cfg.get("artifact") if is_artifact_round else None
        self._track_usage(
            stage_id, model,
            usage_ref["input_tokens"], usage_ref["output_tokens"], usage_ref["cost_usd"],
            is_artifact=is_artifact_round, artifact_name=artifact_name,
        )

        # Validate against guardrails
        if instance and full_response and not full_response.startswith("[Error"):
            is_valid, reason = instance.validate_output(full_response)
            if not is_valid:
                full_response += f"\n\n> **Guardrail Warning**: {reason}"

        # Emit complete message with usage info
        self._emit("message", {
            "msg_id": msg_id,
            "stage": stage_id,
            "round": round_num,
            "agent_id": agent_id,
            "agent_name": info.get("name", agent_id),
            "agent_short": info.get("short", agent_id[:3].upper()),
            "agent_color": info.get("color", "#6b7280"),
            "content": full_response,
            "model": model,
            "is_artifact": is_artifact_round,
            "usage": {
                "input_tokens": usage_ref["input_tokens"],
                "output_tokens": usage_ref["output_tokens"],
                "cost_usd": round(usage_ref["cost_usd"], 6),
            },
        })

        return full_response

    def request_cancel(self):
        """Ask whatever's currently running (run_stage/run_selected/run_from_stage/
        upgrade_to_quality, on its background thread) to stop. Cooperative — takes
        effect at the next safe checkpoint (between agent turns or stages), not
        mid-LLM-call, so a call already in flight still finishes."""
        self._cancel_requested = True

    def _check_cancelled(self) -> bool:
        """Consume a pending cancel request, if any, and finalize the session as
        'cancelled'. Callers that get True back must stop and return immediately —
        the trailing "complete"/"paused" status logic further down the same method
        must NOT run afterwards, or it would silently overwrite this."""
        if not self._cancel_requested:
            return False
        self._cancel_requested = False
        self.status = "cancelled"
        self._emit("forge_cancelled", {
            "stage": self.stages[self.current_stage_idx]["id"] if self.current_stage_idx < len(self.stages) else None,
        })
        self._save_session()
        return True

    def run_stage(self, stage_idx: int = None):
        """Run a single stage of the forge."""
        if self._check_cancelled():
            return
        if stage_idx is not None:
            self.current_stage_idx = stage_idx
        stage = self.stages[self.current_stage_idx]
        stage_id = stage["id"]
        participants = self._effective_participants(stage)
        self.status = "running"
        # Persist immediately, not just at the stage's end — the project list
        # (left panel) reads this on-disk snapshot, not the live in-memory
        # session, so without this it kept showing the previous checkpoint's
        # "paused"/"complete" for the entire duration of the stage that's
        # actually running right now.
        self._save_session()

        self._emit("stage_start", {
            "stage": stage_id,
            "stage_name": stage["name"],
            "description": stage["description"],
            "participants": participants,
        })

        # Discussion rounds (in draft mode: cap at 1 round for speed/cost)
        max_rounds = 1 if self.draft_mode else stage["rounds"]
        # The same "first participant is the lead" convention the
        # critique/refine round below already uses (lead_agent =
        # participants[0]) — reused here so the final round below
        # has exactly one author instead of every participant independently
        # attempting the whole document.
        lead_agent_id = participants[0] if participants else None
        lead_info = self._get_agent_info(lead_agent_id) if lead_agent_id else {}

        for round_num in range(1, max_rounds + 1):
            if self._check_cancelled():
                return
            self._emit("round_start", {"stage": stage_id, "round": round_num})
            is_final_round = (round_num == max_rounds)
            is_artifact_stage = bool(stage.get("artifact"))

            # In the final round of an artifact stage, only the lead actually
            # writes the document — every OTHER participant used to be asked,
            # independently, to "produce the final artifact" too, and only
            # whichever agent happened to be LAST in the participant list
            # actually got saved (last_msgs[-1] below); everyone else's full
            # document attempt was generated and silently discarded. That was
            # real, wasted cost on every multi-participant stage (Design's 6
            # participants, TRD's 3, Tasks' 5) and made "who actually authors
            # this" depend on list order rather than intent. Non-lead
            # participants now give final input INSTEAD of a competing draft,
            # and speak before the lead so their input is already in context
            # when the lead writes.
            if is_final_round and is_artifact_stage and lead_agent_id:
                round_participants = [a for a in participants if a != lead_agent_id] + [lead_agent_id]
            else:
                round_participants = participants

            for agent_id in round_participants:
                if self._check_cancelled():
                    return
                info = self._get_agent_info(agent_id)
                is_lead = (agent_id == lead_agent_id)

                # Only the lead's final-round call actually produces the artifact.
                is_artifact_round = is_final_round and is_artifact_stage and is_lead

                if round_num == 1 and stage_id == "ideation":
                    instruction = (
                        f"We're starting ideation for a new product. "
                        f"The idea is: {self.product_idea}\n\n"
                        f"Share your initial thoughts, questions, and concerns from your perspective as {info['name']}."
                    )
                elif is_final_round and is_artifact_stage and not is_lead:
                    instruction = (
                        f"This is the final round before '{stage['artifact']}' is written. Give your final, "
                        f"specific input from your perspective as {info['name']} — concrete requirements, risks, "
                        f"gaps, or domain details that MUST be reflected in the document. Be concise and specific. "
                        f"You are NOT writing the document itself — {lead_info.get('name', lead_agent_id)} will "
                        f"incorporate your input when they write it right after you."
                    )
                elif is_artifact_round and stage.get("sections"):
                    # Multi-pass sectional generation — skip single-shot, handled after loop
                    instruction = None
                elif is_artifact_round:
                    # Stages that should NOT contain implementation code
                    no_code_stages = {"trd", "design", "tasks", "stories", "review"}
                    no_code_rule = ""
                    if stage_id in no_code_stages:
                        no_code_rule = (
                            "\n\nNO-CODE RULE: Do NOT include implementation code, code snippets, or code blocks in this document. "
                            "Describe architecture, decisions, and requirements at a CONCEPTUAL level using prose, "
                            "bullet points, tables, and text-based diagrams. Implementation code (schemas, types, SQL, API contracts) "
                            "belongs exclusively in SPECS.md — not here.\n"
                            "HOWEVER, you MUST still include enough technical depth for a development team to act on: "
                            "name specific technologies, libraries, and versions to use; describe data entities and their relationships; "
                            "list API endpoint paths and their purpose; specify architecture patterns and service boundaries; "
                            "define acceptance criteria precisely. The goal is a technically rich document that tells developers "
                            "WHAT to build and WHY, without dictating the exact code HOW."
                        )

                    scope_rule = ""
                    stage_scope = STAGE_SCOPE.get(stage_id)
                    if stage_scope:
                        scope_rule = f"\n\nDOCUMENT SCOPE — stay in your lane: {stage_scope}"

                    instruction = (
                        f"Based on all discussions and prior artifacts, produce the final "
                        f"'{stage['artifact']}' artifact content. Write comprehensive, "
                        f"well-structured markdown suitable for a real product team. "
                        f"Be thorough and complete — cover ALL sections described in the table of contents. "
                        f"Do NOT truncate or abbreviate. This is the definitive document that the team will work from.\n\n"
                        f"GROUNDING RULE: Only include requirements, features, and decisions that are explicitly stated in "
                        f"the product description or prior artifacts. Do NOT invent features, integrations, technology choices, "
                        f"or capabilities not mentioned in the provided context. If you need to make an assumption, clearly "
                        f"label it as '[ASSUMPTION]' so it can be validated. Trace every major item back to input context."
                        f"{scope_rule}"
                        f"{no_code_rule}"
                    )
                    instruction = self._build_delta_aware_instruction(instruction, stage)
                else:
                    instruction = (
                        f"Continue the discussion for stage '{stage['name']}'. "
                        f"Build on what others have said, add your expertise, "
                        f"challenge assumptions, and push for clarity. Round {round_num}."
                    )

                if instruction is not None:
                    self._agent_respond_streaming(agent_id, stage_id, instruction, round_num, is_artifact_round=is_artifact_round)

        # Multi-pass sectional generation for stages with "sections" config
        if stage.get("sections") and stage.get("artifact"):
            if self._generate_sectional_artifact(stage, stage_id):
                return  # cancelled partway through — status/save already handled
            self._emit("stage_complete", {"stage": stage_id, "stage_name": stage["name"]})
            self.current_stage_idx += 1
            if self.current_stage_idx >= len(self.stages):
                self.status = "complete"
            else:
                self.status = "paused"
            self._save_session()
            return

        # Save artifact if this stage produces one
        if stage.get("artifact"):
            last_msgs = [
                m for m in self.conversation_log
                if m.get("stage") == stage_id and m["type"] == "message"
            ]
            if last_msgs:
                artifact_content = last_msgs[-1]["content"]
                self.artifacts[stage["artifact"]] = artifact_content
                self._ensure_output_dir()
                artifact_path = self.output_dir / stage["artifact"]
                artifact_path.write_text(artifact_content, encoding="utf-8")

                # --- Critique-and-Refine Round (skipped in draft mode) ---
                if self.draft_mode:
                    self._emit("artifact_created", {
                        "stage": stage_id,
                        "artifact_name": stage["artifact"],
                        "path": str(artifact_path),
                    })
                    self._emit("stage_complete", {"stage": stage_id, "stage_name": stage["name"]})
                    self.current_stage_idx += 1
                    if self.current_stage_idx >= len(self.stages):
                        self.status = "complete"
                    else:
                        self.status = "paused"
                    self._save_session()
                    return

                critique_round = stage["rounds"] + 1
                self._emit("round_start", {"stage": stage_id, "round": critique_round, "round_type": "critique"})

                # Critique: all participants review the draft
                critique_instruction = (
                    f"A draft of '{stage['artifact']}' has been produced. Your job is to CRITIQUE it.\n\n"
                    f"Review the draft critically from your perspective as {'{agent_name}'}. Identify:\n"
                    f"1. **Missing items** — requirements from the PRD/context that aren't covered\n"
                    f"2. **Inconsistencies** — contradictions with prior artifacts or within the document\n"
                    f"3. **Hallucinations** — features, technologies, or details that were NOT in the original requirements\n"
                    f"4. **Ambiguities** — vague language that would block implementation\n"
                    f"5. **Quality gaps** — sections that are too thin or lack actionable detail\n"
                    f"6. **Scope violations** — content that belongs in a different pipeline document rather than "
                    f"this one (e.g. implementation code/schemas in a business document, or business requirements "
                    f"re-derived in a technical document) — flag it for removal here\n\n"
                    f"Be specific. Reference exact sections. This critique will be used to produce a revised final version."
                )
                critiques = []
                for agent_id in participants:
                    if self._check_cancelled():
                        return
                    info = self._get_agent_info(agent_id)
                    agent_critique_instruction = critique_instruction.replace("{agent_name}", info.get("name", agent_id))
                    response = self._agent_respond_streaming(
                        agent_id, stage_id, agent_critique_instruction, critique_round, is_artifact_round=False
                    )
                    critiques.append(response)

                # Refine: lead participant rewrites incorporating critique
                refine_round = stage["rounds"] + 2
                self._emit("round_start", {"stage": stage_id, "round": refine_round, "round_type": "refine"})

                lead_agent = participants[0]
                refine_instruction = (
                    f"Your colleagues have critiqued the draft of '{stage['artifact']}'. "
                    f"Based on their feedback, produce the FINAL REVISED version of the artifact.\n\n"
                    f"Rules:\n"
                    f"- Fix all valid issues raised in the critiques\n"
                    f"- Remove any hallucinated content (features/tech not in original requirements)\n"
                    f"- Remove any scope violations (content that belongs in a different pipeline document)\n"
                    f"- Fill gaps that were identified as missing\n"
                    f"- Resolve inconsistencies with prior artifacts\n"
                    f"- Keep everything that was already correct\n"
                    f"- Mark any remaining open questions as '[DECISION NEEDED]'\n\n"
                    f"Output the complete revised document. Do NOT summarize changes — output the full artifact."
                )
                revised_content = self._agent_respond_streaming(
                    lead_agent, stage_id, refine_instruction, refine_round, is_artifact_round=True
                )

                # Update artifact with refined version
                if revised_content and not revised_content.startswith("[Error"):
                    self._version_artifact(stage["artifact"], reason="pre-critique draft")
                    artifact_content = revised_content
                    self.artifacts[stage["artifact"]] = artifact_content
                    artifact_path.write_text(artifact_content, encoding="utf-8")

                self._emit("artifact_created", {
                    "stage": stage_id,
                    "artifact_name": stage["artifact"],
                    "path": str(artifact_path),
                })

        self._emit("stage_complete", {"stage": stage_id, "stage_name": stage["name"]})
        self.current_stage_idx += 1
        if self.current_stage_idx >= len(self.stages):
            self.status = "complete"
        else:
            self.status = "paused"

        # Persist session after each stage
        self._save_session()

    def _generate_sectional_artifact(self, stage: dict, stage_id: str) -> bool:
        """Generate a large artifact in multiple passes (one per section group).

        Each section is generated as a separate LLM call, then all are concatenated
        into the final artifact file. This guarantees completion regardless of document size.

        Returns True if a cancel request interrupted generation partway through —
        run_stage() must return immediately in that case rather than treating this
        stage as complete.
        """
        sections = stage["sections"]
        artifact_name = stage["artifact"]
        participants = self._effective_participants(stage)
        lead_agent = participants[0]
        all_parts = []

        stage_scope = STAGE_SCOPE.get(stage_id)
        scope_line = f"\n\nDOCUMENT SCOPE — stay in your lane: {stage_scope}" if stage_scope else ""
        base_grounding = (
            "GROUNDING RULE: Only spec features and requirements explicitly stated in the PRD, TRD, or "
            "Solution Design. Do NOT invent new features, integrations, or capabilities not mentioned in those documents. "
            "If something is ambiguous, note it as a decision needed — do not assume.\n\n"
            "Use code blocks for schemas and type definitions. Be precise enough that an AI coding agent "
            "can implement each piece without asking clarifying questions. No prose summaries — only specs."
            f"{scope_line}"
        )

        for i, section in enumerate(sections):
            if self._check_cancelled():
                return True
            section_round = i + 1
            self._emit("round_start", {
                "stage": stage_id,
                "round": section_round,
                "round_type": "section",
                "section_title": section["title"],
            })

            prior_sections_summary = ""
            if all_parts:
                prior_sections_summary = (
                    f"\n\nYou have already generated the following sections (DO NOT repeat them):\n"
                    f"Sections completed: {', '.join(s['title'] for s in sections[:i])}\n"
                )

            instruction = (
                f"You are generating part {i + 1} of {len(sections)} of the '{artifact_name}' document.\n\n"
                f"## Section to generate: {section['title']}\n\n"
                f"{section['instruction']}\n\n"
                f"{base_grounding}\n"
                f"{prior_sections_summary}\n"
                f"Based on all prior artifacts (PRD, TRD, Solution Design, Epics, Tasks), generate ONLY this section. "
                f"Be thorough and complete for this section — do not abbreviate or truncate. "
                f"{'Start with the document header and table of contents.' if i == 0 else 'Continue directly from the previous section — no document header needed.'}"
            )

            instruction = self._build_delta_aware_instruction(instruction, stage)
            section_content = self._agent_respond_streaming(
                lead_agent, stage_id, instruction, section_round, is_artifact_round=True
            )
            if section_content and not section_content.startswith("[Error"):
                all_parts.append(section_content)

        # Concatenate all sections into the final artifact
        artifact_content = "\n\n---\n\n".join(all_parts)
        self.artifacts[artifact_name] = artifact_content
        self._ensure_output_dir()
        artifact_path = self.output_dir / artifact_name
        artifact_path.write_text(artifact_content, encoding="utf-8")

        self._emit("artifact_created", {
            "stage": stage_id,
            "artifact_name": artifact_name,
            "path": str(artifact_path),
            "sections_generated": len(all_parts),
        })

        # Critique-and-refine on the combined artifact (skip in draft mode)
        if not self.draft_mode and all_parts:
            critique_round = len(sections) + 1
            self._emit("round_start", {"stage": stage_id, "round": critique_round, "round_type": "critique"})

            critique_instruction = (
                f"A multi-section '{artifact_name}' has been produced in {len(sections)} passes. "
                f"Review the COMBINED document for:\n"
                f"1. **Consistency** — do sections contradict each other?\n"
                f"2. **Completeness** — are there gaps between sections?\n"
                f"3. **Redundancy** — is anything duplicated across sections?\n"
                f"4. **Cross-references** — do API contracts match data models? Do components reference correct endpoints?\n"
                f"5. **Hallucinations** — anything not grounded in the PRD/TRD?\n\n"
                f"Be specific about what needs fixing."
            )
            for agent_id in participants:
                if self._check_cancelled():
                    return True
                self._agent_respond_streaming(agent_id, stage_id, critique_instruction, critique_round, is_artifact_round=False)

            # Refine pass — but section by section to avoid hitting limits again
            refine_round = len(sections) + 2
            self._emit("round_start", {"stage": stage_id, "round": refine_round, "round_type": "refine"})

            refined_parts = []
            for i, (section, part) in enumerate(zip(sections, all_parts)):
                if self._check_cancelled():
                    return True
                refine_instruction = (
                    f"Based on the critique feedback, revise ONLY this section of '{artifact_name}':\n\n"
                    f"## Section: {section['title']}\n\n"
                    f"Current content:\n```\n{part[:6000]}\n{'...[truncated for context]' if len(part) > 6000 else ''}\n```\n\n"
                    f"Fix issues raised in the critique. Output the REVISED section only. "
                    f"Preserve everything that was already correct."
                )
                revised = self._agent_respond_streaming(
                    lead_agent, stage_id, refine_instruction, refine_round, is_artifact_round=True
                )
                if revised and not revised.startswith("[Error"):
                    refined_parts.append(revised)
                else:
                    refined_parts.append(part)

            # Update artifact with refined version
            self._version_artifact(artifact_name, reason="pre-critique draft")
            artifact_content = "\n\n---\n\n".join(refined_parts)
            self.artifacts[artifact_name] = artifact_content
            artifact_path.write_text(artifact_content, encoding="utf-8")

        self._save_session()
        return False

    def _build_delta_aware_instruction(self, base_instruction: str, stage: dict) -> str:
        """Wrap artifact instruction with delta-awareness when re-running a stage.

        If we have a previous version of this artifact AND know what changed upstream,
        tell the LLM to revise only what's affected rather than regenerating from scratch.
        """
        delta = getattr(self, '_rerun_delta', None)
        prev_artifacts = getattr(self, '_rerun_previous_artifacts', None)
        artifact_name = stage.get("artifact")

        if not delta or not prev_artifacts or not artifact_name:
            return base_instruction
        if artifact_name not in prev_artifacts:
            return base_instruction

        previous_content = prev_artifacts[artifact_name]
        # Truncate to avoid exceeding context limits — show first/last sections
        if len(previous_content) > 8000:
            truncated = previous_content[:4000] + "\n\n... [MIDDLE SECTIONS OMITTED FOR BREVITY] ...\n\n" + previous_content[-4000:]
        else:
            truncated = previous_content

        delta_instruction = (
            f"## DELTA-AWARE REGENERATION\n\n"
            f"You are RE-RUNNING this stage because upstream artifacts were modified. "
            f"Instead of generating from scratch, use the PREVIOUS version of this artifact as your starting point "
            f"and apply ONLY the changes required by the upstream modifications.\n\n"
            f"### What changed upstream:\n{delta}\n\n"
            f"### Previous version of {artifact_name} (your starting point):\n"
            f"```\n{truncated}\n```\n\n"
            f"### Your task:\n"
            f"1. Analyze how the upstream changes affect this artifact\n"
            f"2. Preserve ALL sections that are NOT impacted by the changes\n"
            f"3. Modify ONLY the sections that need to reflect the upstream delta\n"
            f"4. If the changes are purely cosmetic/comments with no semantic impact, "
            f"reproduce the previous artifact essentially unchanged\n"
            f"5. Output the COMPLETE artifact (not just the changes)\n\n"
            f"STABILITY RULE: Do NOT reorganize, rephrase, or restructure sections that are unaffected. "
            f"Your goal is minimal, targeted revision — not a rewrite.\n\n"
            f"---\n\n"
            f"{base_instruction}"
        )
        return delta_instruction

    def _compute_upstream_delta(self, stage_idx: int) -> str | None:
        """Compute what changed in upstream artifacts since the last run.

        Returns a summary of changes if any upstream artifact was modified,
        or None if we can't determine what changed (first run, etc).
        """
        current_stage = self.stages[stage_idx]
        upstream_stages = self.stages[:stage_idx]
        deltas = []
        for s in upstream_stages:
            artifact_name = s.get("artifact")
            if not artifact_name or artifact_name not in self.artifacts:
                continue
            versions = self.artifact_versions.get(artifact_name, [])
            if not versions:
                continue
            latest_version = versions[-1]
            version_path = self.output_dir / "versions" / latest_version["filename"]
            if not version_path.exists():
                continue
            previous_content = version_path.read_text(encoding="utf-8")
            current_content = self.artifacts[artifact_name]
            if previous_content.strip() == current_content.strip():
                continue
            # Find the actual diff lines
            prev_lines = previous_content.splitlines()
            curr_lines = current_content.splitlines()
            added = [l for l in curr_lines if l not in prev_lines]
            removed = [l for l in prev_lines if l not in curr_lines]
            if added or removed:
                delta_summary = f"\n### Changes in {artifact_name}:\n"
                if added:
                    delta_summary += "**Added/Modified lines:**\n"
                    for line in added[:50]:  # Cap at 50 lines to avoid token explosion
                        delta_summary += f"  + {line}\n"
                    if len(added) > 50:
                        delta_summary += f"  ... and {len(added) - 50} more lines\n"
                if removed:
                    delta_summary += "**Removed lines:**\n"
                    for line in removed[:30]:
                        delta_summary += f"  - {line}\n"
                    if len(removed) > 30:
                        delta_summary += f"  ... and {len(removed) - 30} more lines\n"
                deltas.append(delta_summary)
        return "\n".join(deltas) if deltas else None

    def run_from_stage(self, stage_idx: int):
        """Run from a specific stage onwards using delta-aware regeneration.

        Instead of generating from scratch, provides the LLM with:
        1. The full upstream context (so it can reason about cross-cutting impacts)
        2. The specific delta (what changed upstream)
        3. The previous downstream artifact as a base (for stability)

        This produces more deterministic results — only modifying what the delta affects.
        """
        # Compute delta BEFORE we clear anything
        upstream_delta = self._compute_upstream_delta(stage_idx)

        # Stash previous downstream artifacts for delta-aware regeneration
        previous_artifacts: dict[str, str] = {}
        for s in self.stages[stage_idx:]:
            if s.get("artifact") and s["artifact"] in self.artifacts:
                previous_artifacts[s["artifact"]] = self.artifacts[s["artifact"]]

        # Now clear downstream
        stage_ids_to_clear = [s["id"] for s in self.stages[stage_idx:]]
        self.conversation_log = [
            m for m in self.conversation_log
            if m.get("stage") not in stage_ids_to_clear
        ]
        for s in self.stages[stage_idx:]:
            if s.get("artifact") and s["artifact"] in self.artifacts:
                self._version_artifact(s["artifact"], reason="re-run from stage")
                del self.artifacts[s["artifact"]]

        # Store delta context for use during stage execution
        self._rerun_delta = upstream_delta
        self._rerun_previous_artifacts = previous_artifacts

        self.current_stage_idx = stage_idx
        self.status = "running"
        for i in range(stage_idx, len(self.stages)):
            self.run_stage(i)
            if self.status == "cancelled":
                self._rerun_delta = None
                self._rerun_previous_artifacts = None
                return
        self.status = "complete"

        # Cleanup
        self._rerun_delta = None
        self._rerun_previous_artifacts = None

        self._emit("forge_complete", {
            "artifacts": list(self.artifacts.keys()),
            "output_dir": str(self.output_dir),
        })
        self._save_session()

    def update_artifact(self, artifact_name: str, content: str):
        """Update an artifact's content (user edited it). Persists to disk."""
        self._version_artifact(artifact_name, reason="user edit")
        self.artifacts[artifact_name] = content
        self._ensure_output_dir()
        artifact_path = self.output_dir / artifact_name
        artifact_path.write_text(content, encoding="utf-8")
        self._emit("artifact_updated", {
            "artifact_name": artifact_name,
            "path": str(artifact_path),
        })
        self._save_session()

    def add_context_document(self, name: str, content: str):
        """Add a user-uploaded document as additional context (treated like an artifact)."""
        self.artifacts[name] = content
        self._ensure_output_dir()
        artifact_path = self.output_dir / name
        artifact_path.write_text(content, encoding="utf-8")
        self._emit("context_uploaded", {
            "artifact_name": name,
            "path": str(artifact_path),
        })
        self._save_session()

    def upgrade_to_quality(self):
        """Upgrade a draft run to quality: run critique-and-refine on all existing artifacts using Sonnet."""
        from llm_client import ARTIFACT_MODEL, DEFAULT_MAX_TOKENS_ARTIFACT

        self.draft_mode = False
        self.status = "running"
        self._save_session()  # see run_stage()'s own save — same reason

        for stage in self.stages:
            if self._check_cancelled():
                return
            if not stage.get("artifact"):
                continue
            artifact_name = stage["artifact"]
            if artifact_name not in self.artifacts:
                continue

            stage_id = stage["id"]
            participants = self._effective_participants(stage)
            self._emit("stage_start", {
                "stage": stage_id,
                "stage_name": f"{stage['name']} (Quality Pass)",
                "description": f"Critique and refine {artifact_name}",
                "participants": participants,
            })

            # Critique round
            critique_round = 1
            self._emit("round_start", {"stage": stage_id, "round": critique_round, "round_type": "critique"})

            critique_instruction = (
                f"A draft of '{artifact_name}' has been produced. Your job is to CRITIQUE it.\n\n"
                f"Review the draft critically from your perspective as {{agent_name}}. Identify:\n"
                f"1. **Missing items** — requirements from the PRD/context that aren't covered\n"
                f"2. **Inconsistencies** — contradictions with prior artifacts or within the document\n"
                f"3. **Hallucinations** — features, technologies, or details that were NOT in the original requirements\n"
                f"4. **Ambiguities** — vague language that would block implementation\n"
                f"5. **Quality gaps** — sections that are too thin or lack actionable detail\n"
                f"6. **Scope violations** — content that belongs in a different pipeline document rather than "
                f"this one (e.g. implementation code/schemas in a business document, or business requirements "
                f"re-derived in a technical document) — flag it for removal here\n\n"
                f"Be specific. Reference exact sections. This critique will be used to produce a revised final version."
            )
            for agent_id in participants:
                if self._check_cancelled():
                    return
                info = self._get_agent_info(agent_id)
                agent_critique = critique_instruction.replace("{agent_name}", info.get("name", agent_id))
                self._agent_respond_streaming(agent_id, stage_id, agent_critique, critique_round, is_artifact_round=False)

            # Refine round
            refine_round = 2
            self._emit("round_start", {"stage": stage_id, "round": refine_round, "round_type": "refine"})

            lead_agent = participants[0]
            refine_instruction = (
                f"Your colleagues have critiqued the draft of '{artifact_name}'. "
                f"Based on their feedback, produce the FINAL REVISED version of the artifact.\n\n"
                f"Rules:\n"
                f"- Fix all valid issues raised in the critiques\n"
                f"- Remove any hallucinated content (features/tech not in original requirements)\n"
                f"- Remove any scope violations (content that belongs in a different pipeline document)\n"
                f"- Fill gaps that were identified as missing\n"
                f"- Resolve inconsistencies with prior artifacts\n"
                f"- Keep everything that was already correct\n"
                f"- Mark any remaining open questions as '[DECISION NEEDED]'\n\n"
                f"Output the complete revised document. Do NOT summarize changes — output the full artifact."
            )
            revised_content = self._agent_respond_streaming(
                lead_agent, stage_id, refine_instruction, refine_round, is_artifact_round=True
            )

            if revised_content and not revised_content.startswith("[Error"):
                self._version_artifact(artifact_name, reason="pre-quality-upgrade draft")
                self.artifacts[artifact_name] = revised_content
                self._ensure_output_dir()
                artifact_path = self.output_dir / artifact_name
                artifact_path.write_text(revised_content, encoding="utf-8")

            self._emit("stage_complete", {"stage": stage_id, "stage_name": stage["name"]})

        self.status = "complete"
        self._emit("forge_complete", {
            "artifacts": list(self.artifacts.keys()),
            "output_dir": str(self.output_dir),
        })
        self._save_session()

    def run_selected(self, stage_ids: list[str] | None = None):
        """Run all remaining stages, skipping any artifact-producing stage not in stage_ids.

        A skipped stage runs no discussion rounds, makes no LLM calls, and produces
        no artifact — it's simply left out of self.artifacts, so any later stage that
        IS selected won't see it in its context. Non-artifact stages (e.g. ideation)
        always run since they aren't part of the artifact selection.

        Pass stage_ids=None to run everything (equivalent to the old run_all).
        """
        self.status = "running"
        for i in range(self.current_stage_idx, len(self.stages)):
            if self._check_cancelled():
                return
            stage = self.stages[i]
            if stage.get("artifact") and stage_ids is not None and stage["id"] not in stage_ids:
                self.skipped_stages.add(stage["id"])
                self._emit("stage_skipped", {"stage": stage["id"], "stage_name": stage["name"]})
                self.current_stage_idx = i + 1
                self._save_session()
                continue
            self.run_stage(i)
            if self.status == "cancelled":
                return
        self.status = "complete"
        self._emit("forge_complete", {
            "artifacts": list(self.artifacts.keys()),
            "output_dir": str(self.output_dir),
        })
        self._save_session()

    def run_all(self):
        """Run all stages sequentially."""
        self.run_selected(None)

    def _save_session(self):
        """Persist session state to disk for later retrieval."""
        session_data = {
            "session_id": self.session_id,
            "project_name": self.project_name,
            "product_idea": self.product_idea,
            "draft_mode": self.draft_mode,
            "tech_profile": self.tech_profile_id,
            "folder_name": self.folder_name,
            "created_at": self.created_at,
            "updated_at": datetime.now().isoformat(),
            "status": self.status,
            "current_stage_idx": self.current_stage_idx,
            "artifacts": self.artifacts,
            "artifact_versions": self.artifact_versions,
            "skipped_stages": sorted(self.skipped_stages),
            "stage_participants_override": self.stage_participants_override,
            "token_usage": self.token_usage,
            "output_dir": str(self.output_dir),
            "conversation_log": self.conversation_log,
        }
        session_file = SESSIONS_DIR / f"{self.session_id}.json"
        session_file.write_text(json.dumps(session_data, default=str, indent=2), encoding="utf-8")

    @classmethod
    def load_session(cls, session_id: str) -> "ForgeSession | None":
        """Load a previously saved session from disk."""
        session_file = SESSIONS_DIR / f"{session_id}.json"
        if not session_file.exists():
            return None
        data = json.loads(session_file.read_text(encoding="utf-8"))
        session = cls(
            data["product_idea"], session_id=data["session_id"], project_name=data.get("project_name", ""),
            draft_mode=data.get("draft_mode", False), tech_profile=data.get("tech_profile"),
        )
        session.created_at = data.get("created_at", "")
        session.status = data["status"]
        session.current_stage_idx = data["current_stage_idx"]
        session.artifacts = data.get("artifacts", {})
        session.artifact_versions = data.get("artifact_versions", {})
        session.skipped_stages = set(data.get("skipped_stages", []))
        session.stage_participants_override = data.get("stage_participants_override", {})
        session.token_usage = data.get("token_usage", session.token_usage)
        session.conversation_log = data.get("conversation_log", [])
        session.output_dir = Path(data["output_dir"])
        return session

    @classmethod
    def list_sessions(cls) -> list[dict]:
        """List all persisted sessions (summary only)."""
        sessions = []
        for f in sorted(SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                sessions.append({
                    "session_id": data["session_id"],
                    "project_name": data.get("project_name", ""),
                    "product_idea": data["product_idea"],
                    "folder_name": data.get("folder_name", ""),
                    "created_at": data.get("created_at", ""),
                    "updated_at": data.get("updated_at", ""),
                    "status": data["status"],
                    "current_stage": data["current_stage_idx"],
                    "total_stages": len(data.get("artifacts", {})),
                    "artifacts": list(data.get("artifacts", {}).keys()),
                    "token_usage": {
                        "total_input_tokens": data.get("token_usage", {}).get("total_input_tokens", 0),
                        "total_output_tokens": data.get("token_usage", {}).get("total_output_tokens", 0),
                        "total_cost_usd": data.get("token_usage", {}).get("total_cost_usd", 0.0),
                    },
                })
            except (json.JSONDecodeError, KeyError):
                continue
        return sessions

    def get_state(self) -> dict:
        draft_model = None
        if self.draft_mode:
            from agents.llm import pick_cheapest_reachable_model
            # Cached in agents/llm.py, so this is a cheap lookup on every
            # call, not a fresh probe — and it self-updates if the cheapest
            # reachable model changes mid-session (e.g. Haiku goes down).
            draft_model = pick_cheapest_reachable_model()
        return {
            "session_id": self.session_id,
            "project_name": self.project_name,
            "product_idea": self.product_idea,
            "draft_mode": self.draft_mode,
            "draft_model": draft_model,
            "tech_profile": self.tech_profile_id,
            "folder_name": self.folder_name,
            "created_at": self.created_at,
            "status": self.status,
            "current_stage": self.current_stage_idx,
            "total_stages": len(self.stages),
            "stages": [
                {
                    "id": s["id"],
                    "name": s["name"],
                    "artifact": s.get("artifact"),
                    "status": "skipped" if s["id"] in self.skipped_stages
                        else "complete" if i < self.current_stage_idx
                        else "running" if i == self.current_stage_idx and self.status == "running"
                        else "pending",
                    # Effective participants — the override if this session
                    # set one for this stage, else the shared config default
                    # (also available separately via GET /api/config, which
                    # the UI diffs against this to know what's customized).
                    "participants": self._effective_participants(s),
                }
                for i, s in enumerate(self.stages)
            ],
            "artifacts": list(self.artifacts.keys()),
            "artifact_versions": self.artifact_versions,
            "message_count": len([m for m in self.conversation_log if m["type"] == "message"]),
            "token_usage": self.token_usage,
        }
