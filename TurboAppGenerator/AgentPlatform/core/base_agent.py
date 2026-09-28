"""
Shared base agent class for every persona agent in AgentPlatform/catalog/.

Each agent loads its config.yaml from its own catalog/<agent_id>/ directory,
builds a system prompt, and calls the shared LLM client (agents.llm, owned by
WebUIGenerator — this module has no LLM client of its own).

Two calling conventions are both supported here, merged from the two
previously-separate BaseAgent implementations this replaces
(WebUIGenerator/agents/base_agent.py, ProductForge/agents/base.py) — kept
genuinely separate rather than unified into one, so neither pipeline's actual
prompt text changes as a result of this merge:
  - generate(prompt, context, stage, ...)              — WebUIGenerator's
  - respond(context, instruction, stage) / respond_stream(...) — ProductForge's

Directory layout per agent:
    catalog/<agent_id>/
        config.yaml   — id, name, short, color, description, role, skills,
                         guidelines, guardrails, stage_roles
        agent.py      — subclass with a custom validate_output()
        templates/    — (optional) skill templates
"""

import yaml
from pathlib import Path
from typing import Optional

CATALOG_DIR = Path(__file__).resolve().parent.parent / "catalog"
SHARED_DIR = Path(__file__).resolve().parent / "shared"


class BaseAgent:
    AGENT_ID: str = ""

    def __init__(self):
        self._config: dict = {}
        self._load_config()

    def _load_config(self):
        config_path = CATALOG_DIR / self.AGENT_ID / "config.yaml"
        if config_path.exists():
            self._config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        else:
            raise FileNotFoundError(f"Config not found: {config_path}")

    @property
    def templates_dir(self) -> Path:
        """Path to this agent's templates/ directory."""
        return CATALOG_DIR / self.AGENT_ID / "templates"

    @property
    def name(self) -> str:
        return self._config.get("name", self.AGENT_ID)

    @property
    def short(self) -> str:
        return self._config.get("short", self.AGENT_ID[:3].upper())

    @property
    def color(self) -> str:
        return self._config.get("color", "#6366f1")

    @property
    def description(self) -> str:
        return self._config.get("description", "")

    @property
    def kind(self) -> str:
        """documentation (respond()-only, prose into a ProductForge
        artifact) | execution (generate(json_mode=True), produces real
        files) | design (structured architecture/spec JSON consumed by
        execution agents, not a human reader or a build step)."""
        return self._config.get("kind", "")

    @property
    def role(self) -> str:
        return self._config.get("role", "")

    @property
    def includes(self) -> list[str]:
        return self._config.get("includes", [])

    def _role_with_includes(self) -> str:
        """Role text followed by any shared principle blocks named in
        config.yaml's `includes:` (resolved against core/shared/)."""
        parts = [self.role]
        for filename in self.includes:
            shared_path = SHARED_DIR / filename
            parts.append(shared_path.read_text(encoding="utf-8").strip())
        return "\n\n".join(parts)

    @property
    def skills(self) -> list[dict]:
        return self._config.get("skills", [])

    @property
    def guidelines(self) -> list[str]:
        return self._config.get("guidelines", [])

    @property
    def guardrails(self) -> list[str]:
        return self._config.get("guardrails", [])

    @property
    def stage_roles(self) -> dict[str, str]:
        return self._config.get("stage_roles", {})

    # ── WebUIGenerator calling convention ────────────────────────────────

    def system_prompt(self, stage: Optional[str] = None) -> str:
        """Build the full system prompt, optionally scoped to a stage."""
        parts = [self._role_with_includes()]

        if self.skills:
            parts.append("\n## YOUR SKILLS")
            for s in self.skills:
                parts.append(f"- **{s['name']}**: {s['description']}")

        if self.guidelines:
            parts.append("\n## GUIDELINES")
            for g in self.guidelines:
                parts.append(f"- {g}")

        if self.guardrails:
            parts.append("\n## GUARDRAILS (You MUST follow these)")
            for g in self.guardrails:
                parts.append(f"- {g}")

        if stage and stage in self.stage_roles:
            parts.append(f"\n## YOUR ROLE IN THIS STAGE\n{self.stage_roles[stage]}")

        return "\n".join(parts)

    def generate(self, prompt: str, context: str = "", stage: str = "",
                 max_tokens: int = 32000, json_mode: bool = False,
                 images_b64: list[str] | None = None,
                 temperature: float | None = None) -> str | dict:
        """Call the LLM with this agent's system prompt + context + user prompt.

        images_b64: optional list of base64-encoded PNG/JPEG images to include
                    as visual references in the user message (vision mode).
        temperature: overrides the default (0.1 for json_mode, 0.2 otherwise)
                    when explicitly passed. Added so callers on the legacy
                    (non-SDK-agents) path — e.g. WebUIGenerator's
                    CUSTOM_GEN_TEMPERATURE for deterministic custom-page
                    generation — can actually get that value applied; every
                    existing caller that doesn't pass this keeps today's
                    hardcoded defaults unchanged.
        """
        from agents.llm import chat, chat_json

        system = self.system_prompt(stage=stage)
        messages = []
        if context:
            messages.append({"role": "user", "content": f"Context from previous stages:\n{context}"})
            messages.append({"role": "assistant", "content": "I've reviewed the context. What should I generate?"})

        if images_b64:
            content: list[dict] = [
                {"type": "text", "text": "Reference screenshots from the Figma design (replicate this visual layout):"}
            ]
            for img in images_b64:
                media_type = "image/png" if not img.startswith("/9j/") else "image/jpeg"
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{media_type};base64,{img}"},
                })
            content.append({"type": "text", "text": prompt})
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": prompt})

        if json_mode:
            return chat_json(messages, system=system, max_tokens=max_tokens,
                              temperature=temperature if temperature is not None else 0.1)
        else:
            return chat(messages, system=system, max_tokens=max_tokens,
                        temperature=temperature if temperature is not None else 0.2)

    # ── ProductForge calling convention ──────────────────────────────────

    def _build_prompt_and_messages(self, context: str, instruction: str, stage: str = None):
        parts = [self._role_with_includes()]
        if self.skills:
            parts.append("\n## YOUR SKILLS")
            for s in self.skills:
                parts.append(f"- **{s['name']}**: {s['description']}")
        if self.guidelines:
            parts.append("\n## GUIDELINES")
            for g in self.guidelines:
                parts.append(f"- {g}")
        if self.guardrails:
            parts.append("\n## GUARDRAILS (You MUST follow these)")
            for g in self.guardrails:
                parts.append(f"- {g}")

        stage_role = ""
        if stage and stage in self.stage_roles:
            stage_role = f"\nYOUR ROLE IN THIS STAGE: {self.stage_roles[stage]}"
        full_prompt = "\n".join(parts) + stage_role
        messages = [{"role": "user", "content": f"{context}\n\n{instruction}"}]
        return full_prompt, messages

    def respond(self, context: str, instruction: str, stage: str = None) -> str:
        """Generate a response given context and instruction (ProductForge convention)."""
        from agents.llm import chat
        full_prompt, messages = self._build_prompt_and_messages(context, instruction, stage)
        return chat(messages, system=full_prompt, max_tokens=4096)

    def respond_stream(self, context: str, instruction: str, stage: str = None,
                        model: str = None, max_tokens: int = 4096):
        """Stream response tokens as a generator (ProductForge convention)."""
        from agents.llm import chat_stream_with_usage
        full_prompt, messages = self._build_prompt_and_messages(context, instruction, stage)
        token_gen, _usage_ref = chat_stream_with_usage(messages, system=full_prompt, model=model, max_tokens=max_tokens)
        return token_gen

    # ── Shared ────────────────────────────────────────────────────────────

    def validate_output(self, output: str) -> tuple[bool, str]:
        """Validate agent output. Override in subclasses for agent-specific checks."""
        if not output or len(output.strip()) < 50:
            return False, "Output too short or empty"
        return True, "OK"

    def get_info(self) -> dict:
        """Return agent metadata for discovery/registration (ProductForge convention)."""
        return {
            "id": self.AGENT_ID,
            "name": self.name,
            "short": self.short,
            "color": self.color,
            "description": self.description,
            "kind": self.kind,
            "skills": [s["name"] for s in self.skills],
            "stages": list(self.stage_roles.keys()),
        }

    def __repr__(self):
        return f"<{self.__class__.__name__} id={self.AGENT_ID} name={self.name}>"
