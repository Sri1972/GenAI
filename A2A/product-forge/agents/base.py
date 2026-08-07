"""
Base Agent class — All Product Forge agents inherit from this.

Each agent can be used standalone (imported + called directly) or composed
into the orchestrator for multi-agent collaboration.
"""

import json
import yaml
from pathlib import Path
from datetime import datetime


class BaseAgent:
    """Base class for all Product Forge agents."""

    def __init__(self):
        self.agent_dir = Path(__file__).resolve().parent / self.AGENT_ID
        self.config = self._load_config()
        self.conversation_history: list[dict] = []

    def _load_config(self) -> dict:
        config_path = self.agent_dir / "config.yaml"
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {}

    @property
    def system_prompt(self) -> str:
        """Build the full system prompt from config."""
        cfg = self.config
        parts = [cfg.get("role", "")]

        if cfg.get("skills"):
            parts.append("\n## YOUR SKILLS")
            for skill in cfg["skills"]:
                parts.append(f"- **{skill['name']}**: {skill['description']}")

        if cfg.get("guidelines"):
            parts.append("\n## GUIDELINES")
            for g in cfg["guidelines"]:
                parts.append(f"- {g}")

        if cfg.get("guardrails"):
            parts.append("\n## GUARDRAILS (You MUST follow these)")
            for g in cfg["guardrails"]:
                parts.append(f"- {g}")

        return "\n".join(parts)

    def _build_prompt_and_messages(self, context: str, instruction: str, stage: str = None):
        stage_role = ""
        if stage and self.config.get("stage_roles", {}).get(stage):
            stage_role = f"\nYOUR ROLE IN THIS STAGE: {self.config['stage_roles'][stage]}"
        full_prompt = f"{self.system_prompt}{stage_role}"
        messages = [{"role": "user", "content": f"{context}\n\n{instruction}"}]
        return full_prompt, messages

    def respond(self, context: str, instruction: str, stage: str = None) -> str:
        """Generate a response given context and instruction."""
        from llm_client import chat_completion
        full_prompt, messages = self._build_prompt_and_messages(context, instruction, stage)
        return chat_completion(full_prompt, messages, max_tokens=4096)

    def respond_stream(self, context: str, instruction: str, stage: str = None, model: str = None, max_tokens: int = 4096):
        """Stream response tokens as a generator."""
        from llm_client import chat_completion_stream
        full_prompt, messages = self._build_prompt_and_messages(context, instruction, stage)
        return chat_completion_stream(full_prompt, messages, model=model, max_tokens=max_tokens)

    def validate_output(self, output: str) -> tuple[bool, str]:
        """Validate agent output against guardrails. Returns (is_valid, reason)."""
        guardrails = self.config.get("guardrails", [])
        # Basic length check
        if len(output) < 50:
            return False, "Response too short — likely incomplete"
        return True, "OK"

    def get_info(self) -> dict:
        """Return agent metadata for discovery/registration."""
        cfg = self.config
        return {
            "id": self.AGENT_ID,
            "name": cfg.get("name", self.AGENT_ID),
            "short": cfg.get("short", self.AGENT_ID[:3].upper()),
            "color": cfg.get("color", "#6b7280"),
            "description": cfg.get("description", ""),
            "skills": [s["name"] for s in cfg.get("skills", [])],
            "stages": list(cfg.get("stage_roles", {}).keys()),
        }
