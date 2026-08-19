"""
Base agent class for TurboUIGen.
Each agent loads its config.yaml from its own directory, builds a system prompt,
and calls the LLM.

Directory layout per agent (same pattern as product-forge):
    agents/<agent_id>/
        config.yaml   — role, skills, guidelines, guardrails, stage_roles
        agent.py      — Python class extending BaseAgent with custom validate_output()
        templates/    — (optional) skill templates (.skill.tsx, .config.ts)
"""

import yaml
from pathlib import Path
from typing import Optional


AGENTS_DIR = Path(__file__).parent


class BaseAgent:
    AGENT_ID: str = ""

    def __init__(self):
        self._config: dict = {}
        self._load_config()

    def _load_config(self):
        config_path = AGENTS_DIR / self.AGENT_ID / "config.yaml"
        if config_path.exists():
            self._config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        else:
            raise FileNotFoundError(f"Config not found: {config_path}")

    @property
    def templates_dir(self) -> Path:
        """Path to this agent's templates/ directory."""
        return AGENTS_DIR / self.AGENT_ID / "templates"

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
    def role(self) -> str:
        return self._config.get("role", "")

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

    def system_prompt(self, stage: Optional[str] = None) -> str:
        """Build the full system prompt for this agent, optionally scoped to a stage."""
        parts = [self.role]

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
                 images_b64: list[str] | None = None) -> str | dict:
        """Call the LLM with this agent's system prompt + context + user prompt.

        images_b64: optional list of base64-encoded PNG/JPEG images to include
                    as visual references in the user message (vision mode).
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
            return chat_json(messages, system=system, max_tokens=max_tokens, temperature=0.1)
        else:
            return chat(messages, system=system, max_tokens=max_tokens, temperature=0.2)

    def validate_output(self, output: str) -> tuple[bool, str]:
        """Validate agent output. Override in subclasses for agent-specific checks."""
        if not output or len(output.strip()) < 50:
            return False, "Output too short or empty"
        return True, "OK"

    def __repr__(self):
        return f"<{self.__class__.__name__} id={self.AGENT_ID} name={self.name}>"
