"""
Product Forge Orchestrator — Manages multi-agent collaboration through product stages.

Each stage has participants who discuss/collaborate, then produce an artifact.
Conversations flow: ideation -> PRD -> TRD -> design -> stories -> tasks -> test_cases -> review

Two-tier LLM strategy:
- Discussion rounds use the cheaper DRAFT model (Haiku) for speed/cost
- Artifact generation rounds use the premium ARTIFACT model (Sonnet) for quality + higher token limit

Uses standalone agent packages from the agents/ directory. Each agent has its own
config.yaml with skills, guardrails, and guidelines.
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

AGENTS_DIR = Path(__file__).resolve().parent.parent / "agents"
CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "artifacts"
SESSIONS_DIR = Path(__file__).resolve().parent.parent / "sessions"

sys.path.insert(0, str(AGENTS_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def load_config():
    with open(CONFIG_DIR / "agents.json", encoding="utf-8") as f:
        return json.load(f)


def get_agent_instance(agent_id: str):
    """Dynamically load and instantiate an agent from its package."""
    from base import BaseAgent
    import importlib.util

    agent_file = AGENTS_DIR / agent_id / "agent.py"
    if not agent_file.exists():
        return None

    spec = importlib.util.spec_from_file_location(f"agent_{agent_id}", agent_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if (isinstance(attr, type) and issubclass(attr, BaseAgent)
                and attr is not BaseAgent and hasattr(attr, 'AGENT_ID')):
            return attr()
    return None


class ForgeSession:
    """A single product forge session — takes an idea through all stages."""

    def __init__(self, product_idea: str, session_id: str = None, project_name: str = None, draft_mode: bool = False):
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.project_name = project_name or ""
        self.product_idea = product_idea
        self.draft_mode = draft_mode
        self.folder_name = slugify(project_name) if project_name else slugify(product_idea)
        self.config = load_config()
        self.stages = self.config["stages"]
        self.conversation_log: list[dict] = []
        self.artifacts: dict[str, str] = {}
        self.current_stage_idx = 0
        self.status = "ready"
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
            chat_completion_stream_with_usage, calculate_cost
        )

        instance = self._agents.get(agent_id)
        context = self._build_context(stage_id)
        info = self._get_agent_info(agent_id)

        # Select model tier based on whether this is artifact generation
        # In draft mode: use cheap model for everything (including artifacts)
        if self.draft_mode:
            model = DRAFT_MODEL
            max_tokens = DEFAULT_MAX_TOKENS_ARTIFACT if is_artifact_round else DEFAULT_MAX_TOKENS_DISCUSSION
        elif is_artifact_round:
            model = ARTIFACT_MODEL
            max_tokens = DEFAULT_MAX_TOKENS_ARTIFACT
        else:
            model = DRAFT_MODEL
            max_tokens = DEFAULT_MAX_TOKENS_DISCUSSION

        # Emit "agent is starting to speak"
        msg_id = str(uuid.uuid4())[:8]
        self._emit("message_start", {
            "msg_id": msg_id,
            "stage": stage_id,
            "round": round_num,
            "agent_id": agent_id,
            "agent_name": info.get("name", agent_id),
            "agent_short": info.get("short", agent_id[:3].upper()),
            "agent_color": info.get("color", "#6b7280"),
            "model": model,
            "is_artifact": is_artifact_round,
        })

        full_response = ""
        usage_ref = {"model": model, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}

        try:
            if instance:
                full_prompt, messages = instance._build_prompt_and_messages(context, task_instruction, stage=stage_id)
            else:
                agent_cfg = self._get_agent_info(agent_id)
                full_prompt = agent_cfg.get("role", f"You are a {agent_cfg.get('name', agent_id)}.")
                messages = [{"role": "user", "content": f"{context}\n\n{task_instruction}"}]

            token_gen, usage_ref = chat_completion_stream_with_usage(
                full_prompt, messages, model=model, max_tokens=max_tokens
            )

            chunk_buffer = ""
            for token in token_gen:
                full_response += token
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

    def run_stage(self, stage_idx: int = None):
        """Run a single stage of the forge."""
        if stage_idx is not None:
            self.current_stage_idx = stage_idx
        stage = self.stages[self.current_stage_idx]
        stage_id = stage["id"]
        self.status = "running"

        self._emit("stage_start", {
            "stage": stage_id,
            "stage_name": stage["name"],
            "description": stage["description"],
            "participants": stage["participants"],
        })

        # Discussion rounds (in draft mode: cap at 1 round for speed/cost)
        max_rounds = 1 if self.draft_mode else stage["rounds"]
        for round_num in range(1, max_rounds + 1):
            self._emit("round_start", {"stage": stage_id, "round": round_num})
            is_final_round = (round_num == max_rounds)
            is_artifact_stage = bool(stage.get("artifact"))

            for agent_id in stage["participants"]:
                info = self._get_agent_info(agent_id)

                # Determine if this is the artifact-producing call
                is_artifact_round = is_final_round and is_artifact_stage

                if round_num == 1 and stage_id == "ideation":
                    instruction = (
                        f"We're starting ideation for a new product. "
                        f"The idea is: {self.product_idea}\n\n"
                        f"Share your initial thoughts, questions, and concerns from your perspective as {info['name']}."
                    )
                elif is_artifact_round and stage_id == "specs":
                    instruction = (
                        f"Based on all prior artifacts (PRD, TRD, Solution Design, Epics, Tasks), produce a "
                        f"complete TECHNICAL SPECIFICATION document (SPECS.md) that a developer can drop directly "
                        f"into GitHub Copilot, Cursor, or Claude Code to generate working code.\n\n"
                        f"The spec MUST include:\n"
                        f"1. **Project Structure** — Full file/folder tree with purpose of each file\n"
                        f"2. **Data Models** — Every entity with fields, types, constraints, relationships\n"
                        f"3. **API Contracts** — Every endpoint: method, path, request schema, response schema, status codes, auth\n"
                        f"4. **Component Specs** — Each UI component: props, state, behavior, events\n"
                        f"5. **Business Logic** — Key algorithms, validation rules, state machines\n"
                        f"6. **Configuration** — Environment variables, feature flags, defaults\n"
                        f"7. **Dependencies** — Exact packages with versions\n\n"
                        f"Use code blocks for schemas and type definitions. Be precise enough that an AI coding agent "
                        f"can implement each piece without asking clarifying questions. No prose summaries — only specs.\n\n"
                        f"GROUNDING RULE: Only spec features and requirements explicitly stated in the PRD, TRD, or "
                        f"Solution Design. Do NOT invent new features, integrations, or capabilities not mentioned in those documents. "
                        f"If something is ambiguous, note it as a decision needed — do not assume."
                    )
                    instruction = self._build_delta_aware_instruction(instruction, stage)
                elif is_artifact_round:
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
                    )
                    instruction = self._build_delta_aware_instruction(instruction, stage)
                else:
                    instruction = (
                        f"Continue the discussion for stage '{stage['name']}'. "
                        f"Build on what others have said, add your expertise, "
                        f"challenge assumptions, and push for clarity. Round {round_num}."
                    )

                self._agent_respond_streaming(agent_id, stage_id, instruction, round_num, is_artifact_round=is_artifact_round)

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
                    f"5. **Quality gaps** — sections that are too thin or lack actionable detail\n\n"
                    f"Be specific. Reference exact sections. This critique will be used to produce a revised final version."
                )
                critiques = []
                for agent_id in stage["participants"]:
                    info = self._get_agent_info(agent_id)
                    agent_critique_instruction = critique_instruction.replace("{agent_name}", info.get("name", agent_id))
                    response = self._agent_respond_streaming(
                        agent_id, stage_id, agent_critique_instruction, critique_round, is_artifact_round=False
                    )
                    critiques.append(response)

                # Refine: lead participant rewrites incorporating critique
                refine_round = stage["rounds"] + 2
                self._emit("round_start", {"stage": stage_id, "round": refine_round, "round_type": "refine"})

                lead_agent = stage["participants"][0]
                refine_instruction = (
                    f"Your colleagues have critiqued the draft of '{stage['artifact']}'. "
                    f"Based on their feedback, produce the FINAL REVISED version of the artifact.\n\n"
                    f"Rules:\n"
                    f"- Fix all valid issues raised in the critiques\n"
                    f"- Remove any hallucinated content (features/tech not in original requirements)\n"
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

        for stage in self.stages:
            if not stage.get("artifact"):
                continue
            artifact_name = stage["artifact"]
            if artifact_name not in self.artifacts:
                continue

            stage_id = stage["id"]
            self._emit("stage_start", {
                "stage": stage_id,
                "stage_name": f"{stage['name']} (Quality Pass)",
                "description": f"Critique and refine {artifact_name}",
                "participants": stage["participants"],
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
                f"5. **Quality gaps** — sections that are too thin or lack actionable detail\n\n"
                f"Be specific. Reference exact sections. This critique will be used to produce a revised final version."
            )
            for agent_id in stage["participants"]:
                info = self._get_agent_info(agent_id)
                agent_critique = critique_instruction.replace("{agent_name}", info.get("name", agent_id))
                self._agent_respond_streaming(agent_id, stage_id, agent_critique, critique_round, is_artifact_round=False)

            # Refine round
            refine_round = 2
            self._emit("round_start", {"stage": stage_id, "round": refine_round, "round_type": "refine"})

            lead_agent = stage["participants"][0]
            refine_instruction = (
                f"Your colleagues have critiqued the draft of '{artifact_name}'. "
                f"Based on their feedback, produce the FINAL REVISED version of the artifact.\n\n"
                f"Rules:\n"
                f"- Fix all valid issues raised in the critiques\n"
                f"- Remove any hallucinated content (features/tech not in original requirements)\n"
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

    def run_all(self):
        """Run all stages sequentially."""
        self.status = "running"
        for i in range(len(self.stages)):
            self.run_stage(i)
        self.status = "complete"
        self._emit("forge_complete", {
            "artifacts": list(self.artifacts.keys()),
            "output_dir": str(self.output_dir),
        })
        self._save_session()

    def _save_session(self):
        """Persist session state to disk for later retrieval."""
        session_data = {
            "session_id": self.session_id,
            "project_name": self.project_name,
            "product_idea": self.product_idea,
            "draft_mode": self.draft_mode,
            "folder_name": self.folder_name,
            "created_at": self.created_at,
            "updated_at": datetime.now().isoformat(),
            "status": self.status,
            "current_stage_idx": self.current_stage_idx,
            "artifacts": self.artifacts,
            "artifact_versions": self.artifact_versions,
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
        session = cls(data["product_idea"], session_id=data["session_id"], project_name=data.get("project_name", ""), draft_mode=data.get("draft_mode", False))
        session.created_at = data.get("created_at", "")
        session.status = data["status"]
        session.current_stage_idx = data["current_stage_idx"]
        session.artifacts = data.get("artifacts", {})
        session.artifact_versions = data.get("artifact_versions", {})
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
        return {
            "session_id": self.session_id,
            "project_name": self.project_name,
            "product_idea": self.product_idea,
            "draft_mode": self.draft_mode,
            "folder_name": self.folder_name,
            "created_at": self.created_at,
            "status": self.status,
            "current_stage": self.current_stage_idx,
            "total_stages": len(self.stages),
            "stages": [
                {
                    "id": s["id"],
                    "name": s["name"],
                    "status": "complete" if i < self.current_stage_idx
                        else "running" if i == self.current_stage_idx and self.status == "running"
                        else "pending",
                }
                for i, s in enumerate(self.stages)
            ],
            "artifacts": list(self.artifacts.keys()),
            "artifact_versions": self.artifact_versions,
            "message_count": len([m for m in self.conversation_log if m["type"] == "message"]),
            "token_usage": self.token_usage,
        }
