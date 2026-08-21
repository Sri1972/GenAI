"""
Programmatic subagent definitions for the SDK-native builder.

Builds one claude_agent_sdk.AgentDefinition per role, assembled from that role's
config.yaml (the single source of truth — same content the legacy _build_system_prompt
used) plus a role-specific tool whitelist, model, and (for the structured architect
roles) an OUTPUT CONTRACT that requires self-validation via the mcp__turboui__* tools.

Chosen over plugin agents/*.md to avoid a second definition mechanism (the review flagged
the two-mechanism drift risk) and any .md-frontmatter guessing.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from claude_agent_sdk import AgentDefinition

AGENTS_DIR = Path(__file__).parent

# role dir -> (subagent name, model, tool whitelist, output_contract)
_READONLY_VALIDATORS = [
    "mcp__turboui__validate_sql", "mcp__turboui__validate_seed_data",
    "mcp__turboui__check_types_match", "mcp__turboui__validate_react_component",
    "mcp__turboui__validate_architecture", "mcp__turboui__check_page_types",
    "mcp__turboui__validate_data_layer",
]
_CODEGEN_TOOLS = [
    "Read", "Write", "Edit", "MultiEdit", "Glob", "Grep",
    "mcp__turboui__validate_react_component", "mcp__turboui__validate_data_layer",
    "mcp__turboui__tsc_check",
]

_ARCH_CONTRACT = (
    "\n## OUTPUT CONTRACT\n"
    "Return ONLY the architecture JSON (projectName, title, pages[], navigation[], "
    "dataEntities[], hasAiFeatures). BEFORE returning, call "
    "`mcp__turboui__validate_architecture` on the full JSON and "
    "`mcp__turboui__check_page_types` on pages[], and fix every reported issue."
)
_DATA_CONTRACT = (
    "\n## OUTPUT CONTRACT\n"
    "Author `api/schema.sql`, `api/seed.sql`, and `src/types.ts`. BEFORE finishing, call "
    "`mcp__turboui__validate_data_layer` with all three and fix every reported issue "
    "(SQL must execute, seed must insert, every table needs a matching TS interface)."
)

_ROLE_SPECS = {
    "ux_architect": dict(
        name="ux-architect", model="sonnet",
        tools=["Read", "Glob", "Grep",
               "mcp__turboui__validate_architecture", "mcp__turboui__check_page_types"],
        contract=_ARCH_CONTRACT,
        skills=[],
    ),
    "data_architect": dict(
        name="data-architect", model="sonnet",
        tools=["Read", "Write", "Edit", "Glob", "Grep",
               "mcp__turboui__validate_sql", "mcp__turboui__validate_seed_data",
               "mcp__turboui__check_types_match", "mcp__turboui__validate_data_layer"],
        contract=_DATA_CONTRACT,
        skills=["turbo-uigen:fastapi-backend"],
    ),
    "react_ui": dict(
        name="react-ui-engineer", model="sonnet",
        tools=_CODEGEN_TOOLS, contract="",
        skills=["turbo-uigen:pdf-export", "turbo-uigen:pptx-export", "turbo-uigen:excel-export",
                "turbo-uigen:export-toolbar", "turbo-uigen:d3-viz-patterns"],
    ),
    "visual_design": dict(
        name="visual-design-engineer", model="sonnet",
        tools=_CODEGEN_TOOLS, contract="",
        skills=["turbo-uigen:d3-charts", "turbo-uigen:world-map", "turbo-uigen:usa-map",
                "turbo-uigen:country-map", "turbo-uigen:d3-viz-patterns"],
    ),
    "ai_genai": dict(
        name="ai-genai-engineer", model="sonnet",
        tools=_CODEGEN_TOOLS, contract="",
        skills=["turbo-uigen:ai-chat", "turbo-uigen:data-chat"],
    ),
    "services_engineer": dict(
        name="services-engineer", model="sonnet",
        tools=_CODEGEN_TOOLS + ["mcp__turboui__validate_sql"], contract="",
        skills=["turbo-uigen:fastapi-backend", "turbo-uigen:data-chat"],
    ),
}


def _assemble_prompt(config: dict, contract: str) -> str:
    """Mirror the legacy _build_system_prompt assembly; embed ALL stage_roles."""
    parts = [config["role"].rstrip()]
    if config.get("skills"):
        parts.append("\n## YOUR SKILLS")
        for s in config["skills"]:
            parts.append(f"- **{s['name']}**: {s['description'].strip()}")
    if config.get("guidelines"):
        parts.append("\n## GUIDELINES")
        parts.extend(f"- {g}" for g in config["guidelines"])
    if config.get("guardrails"):
        parts.append("\n## GUARDRAILS (You MUST follow these)")
        parts.extend(f"- {g}" for g in config["guardrails"])
    if config.get("stage_roles"):
        parts.append("\n## STAGE RESPONSIBILITIES")
        for stage, text in config["stage_roles"].items():
            parts.append(f"### {stage}\n{text.strip()}")
    if contract:
        parts.append(contract)
    return "\n".join(parts)


def build_agents() -> dict[str, AgentDefinition]:
    """Return {subagent_name: AgentDefinition} for all six roles, from config.yaml."""
    agents: dict[str, AgentDefinition] = {}
    for role_dir, spec in _ROLE_SPECS.items():
        cfg_path = AGENTS_DIR / role_dir / "config.yaml"
        config = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        agents[spec["name"]] = AgentDefinition(
            description=" ".join((config.get("description") or "").split())[:1000],
            prompt=_assemble_prompt(config, spec["contract"]),
            tools=spec["tools"],
            model=spec["model"],
            skills=spec["skills"] or None,
        )
    return agents


ROLE_AGENT_NAMES = [spec["name"] for spec in _ROLE_SPECS.values()]
