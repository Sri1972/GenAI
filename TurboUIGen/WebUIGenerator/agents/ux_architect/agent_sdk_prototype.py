"""
UX Architect Agent — SDK prototype.

Handles: Architecture definition (Stage 1) — pages, navigation, data entities.

Tools: validate_architecture, check_page_types (self-validation)
"""

import json
import yaml
from pathlib import Path

from agents.sdk_client import run_agent
from agents.sdk_tools import ToolDef

CONFIG_PATH = Path(__file__).parent / "config.yaml"


# ── Tool implementations (agent-specific) ────────────────────────────────────

def _validate_architecture(architecture_json: str) -> str:
    """Check architecture for structural issues."""
    try:
        arch = json.loads(architecture_json)
    except json.JSONDecodeError as e:
        return f"Invalid JSON: {e}"

    issues = []

    pages = arch.get("pages", [])
    nav = arch.get("navigation", [])

    if not pages:
        issues.append("No pages defined")

    page_names = [p.get("name", "") for p in pages]
    dupes = [n for n in page_names if page_names.count(n) > 1]
    if dupes:
        issues.append(f"Duplicate page names: {set(dupes)}")

    for item in nav:
        if item.get("page") not in page_names:
            issues.append(f"Nav item '{item.get('label')}' references non-existent page '{item.get('page')}'")

    if len(nav) > 8:
        issues.append(f"Too many nav items ({len(nav)}). Max is 8 — reduce cognitive load.")

    for p in pages:
        if not p.get("description") or len(p.get("description", "")) < 20:
            issues.append(f"Page '{p.get('name')}' has no meaningful description (needed for downstream agents)")

    if nav and not any(kw in nav[0].get("label", "").lower() for kw in ["dashboard", "overview", "home", "summary"]):
        issues.append(f"First nav item is '{nav[0].get('label')}' — should typically be a dashboard/overview page")

    if not arch.get("dataEntities"):
        issues.append("No dataEntities defined — Data Architect won't know what tables to create")

    if issues:
        return "Issues found:\n" + "\n".join(f"- {i}" for i in issues)
    return "Valid. Architecture passes all checks."


def _check_page_types(pages_json: str) -> str:
    """Validate page type consistency."""
    VALID_TYPES = {
        "dashboard", "data-table", "charts", "map", "card-grid",
        "wizard", "ai-chat", "form", "detail-view", "kpi-dashboard", "custom"
    }

    try:
        pages = json.loads(pages_json)
    except json.JSONDecodeError as e:
        return f"Invalid JSON: {e}"

    issues = []
    for p in pages:
        ptype = p.get("type", "")
        if ptype not in VALID_TYPES:
            issues.append(f"Page '{p.get('name')}': invalid type '{ptype}'. Use one of: {sorted(VALID_TYPES)}")

        desc = (p.get("description") or "").lower()
        if ptype == "charts" and not any(w in desc for w in ["chart", "graph", "plot", "visualization"]):
            issues.append(f"Page '{p.get('name')}' has type 'charts' but description mentions no charts")
        if ptype == "map" and not any(w in desc for w in ["map", "geo", "choropleth", "region"]):
            issues.append(f"Page '{p.get('name')}' has type 'map' but description mentions no map")

    if issues:
        return "Issues found:\n" + "\n".join(f"- {i}" for i in issues)
    return "All page types are valid and consistent with descriptions."


# ── ToolDef instances ────────────────────────────────────────────────────────

validate_architecture = ToolDef(
    schema={
        "name": "validate_architecture",
        "description": (
            "Validate the architecture JSON structure: check for duplicate page names, "
            "navigation items that reference non-existent pages, missing required fields, "
            "and too many nav items (max 8). Returns issues found or 'Valid'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "architecture_json": {
                    "type": "string",
                    "description": "The full architecture JSON string to validate",
                }
            },
            "required": ["architecture_json"],
        },
    },
    fn=_validate_architecture,
)

check_page_types = ToolDef(
    schema={
        "name": "check_page_types",
        "description": (
            "Check that page types are valid and match the described content. "
            "Valid types: dashboard, data-table, charts, map, card-grid, wizard, "
            "ai-chat, form, detail-view, kpi-dashboard, custom. "
            "Flags mismatches like a 'charts' type page with no chart mentioned in description."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pages_json": {
                    "type": "string",
                    "description": "JSON array of page objects (each with name, type, description)",
                }
            },
            "required": ["pages_json"],
        },
    },
    fn=_check_page_types,
)


# ── System prompt ────────────────────────────────────────────────────────────

def _build_system_prompt(stage: str = "architecture") -> str:
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


# ── Output schema ────────────────────────────────────────────────────────────

ARCHITECTURE_SCHEMA = {
    "name": "architecture_output",
    "schema": {
        "type": "object",
        "properties": {
            "projectName": {
                "type": "string",
                "description": "kebab-case project name"
            },
            "title": {
                "type": "string",
                "description": "Human readable app title"
            },
            "pages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "type": {"type": "string"},
                        "description": {"type": "string"}
                    },
                    "required": ["name", "type", "description"]
                }
            },
            "navigation": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "page": {"type": "string"},
                        "icon": {"type": "string"}
                    },
                    "required": ["label", "page", "icon"]
                }
            },
            "sharedComponents": {
                "type": "array",
                "items": {"type": "string"}
            },
            "dataEntities": {
                "type": "array",
                "items": {"type": "string"}
            },
            "hasAiFeatures": {
                "type": "boolean"
            }
        },
        "required": ["projectName", "title", "pages", "navigation", "dataEntities", "hasAiFeatures"]
    },
    "strict": True,
}


# ── Main entry point ─────────────────────────────────────────────────────────

def run_ux_architect(
    prompt: str,
    images_b64: list[str] | None = None,
    max_tokens: int = 4000,
) -> dict:
    """
    Run the UX Architect agent.

    Used by orchestrator for:
      - Stage 1 (architecture): defines pages, nav, data entities

    Replaces: get_agent("ux_architect").generate(prompt, stage="architecture", json_mode=True, ...)
    """
    messages = []

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
        system=_build_system_prompt(stage="architecture"),
        messages=messages,
        output_schema=ARCHITECTURE_SCHEMA,
        max_tokens=max_tokens,
    )
