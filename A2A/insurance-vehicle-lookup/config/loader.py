"""
Config Loader — Reads skills, guardrails, guidelines, and agent configs from YAML files.

Assembles them into a complete system prompt for each agent.
"""

from pathlib import Path
from typing import Optional

import yaml

CONFIG_DIR = Path(__file__).resolve().parent


def load_yaml(filepath: Path) -> dict:
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_agent_config(agent_name: str) -> dict:
    path = CONFIG_DIR / "agents" / f"{agent_name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Agent config not found: {path}")
    return load_yaml(path)


def load_skill(skill_name: str) -> dict:
    path = CONFIG_DIR / "skills" / f"{skill_name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Skill config not found: {path}")
    return load_yaml(path)


def load_guardrails(guardrail_name: str) -> dict:
    path = CONFIG_DIR / "guardrails" / f"{guardrail_name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Guardrails config not found: {path}")
    return load_yaml(path)


def load_guideline(guideline_name: str) -> dict:
    path = CONFIG_DIR / "guidelines" / f"{guideline_name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Guideline config not found: {path}")
    return load_yaml(path)


def list_skills() -> list[str]:
    skills_dir = CONFIG_DIR / "skills"
    return [f.stem for f in skills_dir.glob("*.yaml")]


def list_guardrails() -> list[str]:
    guardrails_dir = CONFIG_DIR / "guardrails"
    return [f.stem for f in guardrails_dir.glob("*.yaml")]


def list_guidelines() -> list[str]:
    guidelines_dir = CONFIG_DIR / "guidelines"
    return [f.stem for f in guidelines_dir.glob("*.yaml")]


def build_system_prompt(
    agent_name: str,
    skill_name: str,
    guardrail_name: Optional[str] = None,
    guideline_names: Optional[list[str]] = None,
) -> str:
    """
    Assemble a complete system prompt from config files.

    Combines: agent identity + skill instructions + guardrails + guidelines
    """
    agent = load_agent_config(agent_name)
    skill = load_skill(skill_name)

    sections = []

    # 1. Agent identity
    sections.append(f"# Agent Identity\n{skill['role']}")

    # 2. Core skill instructions
    sections.append(f"# Instructions\n{skill['instructions']}")

    # 3. Underwriting rules (if present in skill)
    if "underwriting_rules" in skill:
        import json
        rules_str = json.dumps(skill["underwriting_rules"], indent=2)
        sections.append(f"# Underwriting Rules\n```json\n{rules_str}\n```")

    # 4. Response format
    if "response_format" in skill:
        sections.append(f"# Response Format\n{skill['response_format']}")

    # 5. Guardrails
    if guardrail_name:
        guardrails = load_guardrails(guardrail_name)
        guardrail_text = _format_guardrails(guardrails)
        sections.append(f"# Guardrails & Constraints\n{guardrail_text}")

    # 6. Guidelines
    if guideline_names:
        for gname in guideline_names:
            guideline = load_guideline(gname)
            guideline_text = _format_guideline(guideline)
            sections.append(f"# Guideline: {guideline.get('description', gname)}\n{guideline_text}")

    return "\n\n---\n\n".join(sections)


def _format_guardrails(guardrails: dict) -> str:
    lines = []
    for section_key, section_value in guardrails.items():
        if section_key in ("guardrail_id", "applies_to", "version", "description"):
            continue
        if isinstance(section_value, list):
            lines.append(f"\n## {section_key.replace('_', ' ').title()}")
            for item in section_value:
                if isinstance(item, dict):
                    if "rule" in item:
                        lines.append(f"- {item['rule']}")
                    elif "condition" in item:
                        lines.append(f"- IF: {item['condition']} → THEN: {item['action']}")
                else:
                    lines.append(f"- {item}")
    return "\n".join(lines)


def _format_guideline(guideline: dict) -> str:
    lines = []
    for section_key, section_value in guideline.items():
        if section_key in ("guideline_id", "version", "description"):
            continue
        if isinstance(section_value, list):
            lines.append(f"\n## {section_key.replace('_', ' ').title()}")
            for item in section_value:
                lines.append(f"- {item}")
    return "\n".join(lines)
