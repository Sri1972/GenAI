"""
Data Architect Agent — SDK prototype.

Handles: Data modeling (Stage 2) — SQL schema, seed data, TypeScript types.

Tools: validate_sql, validate_seed_data, check_types_match
"""

import yaml
from pathlib import Path

from agents.sdk_client import run_agent

CONFIG_PATH = Path(__file__).parent / "config.yaml"

DATA_LAYER_SCHEMA = {
    "name": "data_layer_output",
    "schema": {
        "type": "object",
        "properties": {
            "files": {
                "type": "object",
                "properties": {
                    "schema.sql": {
                        "type": "string",
                        "description": "CREATE TABLE statements for all tables"
                    },
                    "seed.sql": {
                        "type": "string",
                        "description": "INSERT statements with 50+ rows per table"
                    },
                    "src/types.ts": {
                        "type": "string",
                        "description": "TypeScript interfaces matching all tables"
                    }
                },
                "required": ["schema.sql", "seed.sql", "src/types.ts"]
            }
        },
        "required": ["files"]
    },
    "strict": True,
}


def _build_system_prompt(stage: str = "data_modeling") -> str:
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


    return "\n".join(parts)


def run_data_architect(
    prompt: str,
    context: str = "",
    images_b64: list[str] | None = None,
    max_tokens: int = 32000,
) -> dict:
    """
    Run the Data Architect agent.

    Used by orchestrator for:
      - Stage 2 (data_modeling): generates schema.sql, seed.sql, src/types.ts

    Replaces: get_agent("data_architect").generate(prompt, context=..., stage="data_modeling", json_mode=True, ...)
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
        system=_build_system_prompt(stage="data_modeling"),
        messages=messages,
        output_schema=DATA_LAYER_SCHEMA,
        max_tokens=max_tokens,
    )
