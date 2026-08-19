"""
React UI Engineer Agent — SDK prototype.

Handles: Infrastructure generation (Stage 3), Page generation (Stage 5),
and skill config filling for kept templates.

Tools: validate_react_component, read_skill_template
"""

import yaml
from pathlib import Path

from agents.sdk_client import run_agent
from agents.sdk_tools import read_skill_template

CONFIG_PATH = Path(__file__).parent / "config.yaml"

# Output schema for file generation (all React UI calls return files)
FILES_SCHEMA = {
    "name": "react_files_output",
    "schema": {
        "type": "object",
        "properties": {
            "files": {
                "type": "object",
                "additionalProperties": {"type": "string"}
            }
        },
        "required": ["files"]
    },
    "strict": True,
}


def _build_system_prompt(stage: str = "pages") -> str:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

    parts = [config["role"]]

    if config.get("skills"):
        parts.append("\n## YOUR SKILLS")
        for s in config["skills"]:
            parts.append(f"- **{s['name']}**: {s['description']}")

    if config.get("guidelines"):
        parts.append("\n## GUIDELINES")
        for g in config["guidelines"]:
            parts.append(f"- {g}")

    if config.get("guardrails"):
        parts.append("\n## GUARDRAILS (You MUST follow these)")
        for g in config["guardrails"]:
            parts.append(f"- {g}")

    if stage and stage in config.get("stage_roles", {}):
        parts.append(f"\n## YOUR ROLE IN THIS STAGE\n{config['stage_roles'][stage]}")

    parts.append("\nFor complex visualizations (D3 maps, chart engines, PDF/Excel exports), "
                 "use the read_skill_template tool to load the reference implementation. "
                 "For standard pages (tables, forms, cards, dashboards), generate from scratch.")

    return "\n".join(parts)


def run_react_ui(
    prompt: str,
    context: str = "",
    stage: str = "pages",
    images_b64: list[str] | None = None,
    max_tokens: int = 32000,
) -> dict:
    """
    Run the React UI agent.

    Used by orchestrator for:
      - Stage 3 (infrastructure): generates App.tsx, package.json, vite.config, etc.
      - Stage 5 (pages): generates full page components
      - Skill config: fills config for kept skill templates

    Replaces: get_agent("react_ui").generate(prompt, context=..., stage=..., json_mode=True, ...)
    """
    messages = []

    if context:
        messages.append({"role": "user", "content": f"Context from previous stages:\n{context}"})
        messages.append({"role": "assistant", "content": "I've reviewed the context. What should I generate?"})

    if images_b64:
        content = [{"type": "text", "text": "Reference screenshots from the Figma design:"}]
        for img in images_b64:
            media_type = "image/png" if not img.startswith("/9j/") else "image/jpeg"
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": img}
            })
        content.append({"type": "text", "text": prompt})
        messages.append({"role": "user", "content": content})
    else:
        messages.append({"role": "user", "content": prompt})

    return run_agent(
        system=_build_system_prompt(stage=stage),
        messages=messages,
        tools=[read_skill_template],
        output_schema=FILES_SCHEMA,
        max_tokens=max_tokens,
    )
