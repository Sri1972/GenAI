"""
Tech L&D Agent: generates Learning & Development material or POC/use-case
documentation for a typed technical topic, via one of a few trainer
personas. Pure text generation (no critique loop, no tool use) -- a single
Claude Code CLI call per generate/regenerate, same posture as ContentAgents'
simpler creator agents.

Reuses ContentAgents/common/claude_cli.py (the shared, pure-stdlib subprocess
wrapper around the Claude Code CLI that every ContentAgents agent already
calls, and that already reads the app-wide model-picker selection) rather
than duplicating it -- see the sys.path setup below.

Personas live in their own personas/<id>/config.yaml files (id, name,
description, role), not inlined here -- same subdir-plus-config.yaml
convention as AgentPlatform/catalog/<agent_id>/config.yaml (see
AgentPlatform/core/base_agent.py), so adding/editing a persona never means
touching this file. Deliberately NOT built on AgentPlatform's own BaseAgent,
though -- that class calls WebUIGenerator's own LLM client (agents.llm);
this still goes through run_claude_text() below, unchanged.
"""

import sys
from pathlib import Path
from typing import Callable

import yaml

ROOT = Path(__file__).resolve().parent.parent  # TurboAppGenerator/
_CONTENT_AGENTS_DIR = ROOT / "ContentAgents"
if str(_CONTENT_AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_CONTENT_AGENTS_DIR))

from common.claude_cli import run_claude_text  # noqa: E402

ProgressFn = Callable[[str], None]

PERSONAS_DIR = Path(__file__).resolve().parent / "personas"


def _load_personas() -> dict[str, dict[str, str]]:
    configs = []
    for config_path in PERSONAS_DIR.glob("*/config.yaml"):
        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        configs.append(cfg)
    # `order` controls display order in the UI's persona picker (lower
    # first) -- NOT alphabetical by directory name, which would silently
    # reshuffle the picker any time a persona got renamed/added.
    configs.sort(key=lambda cfg: cfg.get("order", 999))
    return {
        cfg["id"]: {"label": cfg["name"], "description": cfg["description"], "system_prompt": cfg["role"]}
        for cfg in configs
    }


PERSONAS: dict[str, dict[str, str]] = _load_personas()


def generate_content(topic: str, persona: str, instructions: str = "", on_progress: ProgressFn | None = None) -> str:
    """Generates the Markdown content for one L&D item. `persona` must be a
    key of PERSONAS. Raises ClaudeCliError (from common.claude_cli) on
    failure -- callers should let it propagate to their own error handling,
    same as every ContentAgents creator agent does."""
    if persona not in PERSONAS:
        raise ValueError(f"Unknown persona '{persona}' -- choices are {list(PERSONAS)}")

    if on_progress:
        on_progress(f"Writing {PERSONAS[persona]['label'].lower()} content for \"{topic}\"...")

    prompt = f"TOPIC: {topic}"
    if instructions.strip():
        prompt += f"\n\nADDITIONAL INSTRUCTIONS: {instructions.strip()}"

    return run_claude_text(prompt, system_prompt=PERSONAS[persona]["system_prompt"], allowed_tools=[])
