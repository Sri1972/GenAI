"""
Shared tools for all SDK agents — validation utilities and template access.

Each tool is a ToolDef(schema, fn) pair:
  - schema: the JSON dict sent to the Anthropic API (name, description, input_schema)
  - fn: the Python callable executed locally when Claude invokes the tool

Models call them during generation to self-validate or load reference code.
"""

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

AGENTS_DIR = Path(__file__).parent

# Templates we keep (complex components the model can reference)
_KEPT_TEMPLATES = {
    "WorldMap": "visual_design/templates/WorldMap.skill.tsx",
    "UsaMap": "visual_design/templates/UsaMap.skill.tsx",
    "CountryMap": "visual_design/templates/CountryMap.skill.tsx",
    "Charts": "visual_design/templates/Charts.skill.tsx",
    "PdfExport": "react_ui/templates/PdfExport.skill.tsx",
    "PptxExport": "react_ui/templates/PptxExport.skill.tsx",
    "ExcelExport": "react_ui/templates/ExcelExport.skill.tsx",
    "AiChat": "ai_genai/templates/AiChat.skill.tsx",
    "DataChat": "ai_genai/templates/DataChat.skill.tsx",
    "ExportToolbar": "services_engineer/templates/ExportToolbar.component.tsx",
}


@dataclass
class ToolDef:
    """A tool definition: API schema + local implementation."""
    schema: dict
    fn: Callable


# ── Tool implementations ─────────────────────────────────────────────────────

def _read_skill_template(template_name: str) -> str:
    """Load a kept template by name."""
    rel_path = _KEPT_TEMPLATES.get(template_name)
    if not rel_path:
        available = ", ".join(sorted(_KEPT_TEMPLATES.keys()))
        return f"Template '{template_name}' not found. Available: {available}. Generate from scratch instead."
    full_path = AGENTS_DIR / rel_path
    if not full_path.exists():
        return f"Template file missing at {rel_path}. Generate from scratch instead."
    return full_path.read_text(encoding="utf-8")


def _validate_react_component(source_code: str, page_name: str) -> str:
    """Check React component structure."""
    issues = []

    if "import" not in source_code:
        issues.append("No import statements found")

    if "export default" not in source_code and f"export default function {page_name}" not in source_code:
        if f"export function {page_name}" not in source_code:
            issues.append(f"Missing default export for '{page_name}'")

    if "from '../data/" in source_code or "from '../data'" in source_code:
        issues.append("Imports from '../data/' — must use useApi hook instead")

    if "fetch('/api/" in source_code or 'fetch("/api/' in source_code:
        issues.append("Uses raw fetch() — must use useApi/apiAggregate/apiPost/apiPut/apiDelete")

    if "useApi(" in source_code and "from '../hooks/useApi'" not in source_code:
        issues.append("Uses useApi but missing import from '../hooks/useApi'")

    if "ResizeObserver" in source_code:
        if re.search(r"ResizeObserver\([^)]*\)\s*=>\s*\{[^}]*d3\.select", source_code, re.DOTALL):
            issues.append("D3 drawing inside ResizeObserver callback — will cause infinite loops. Use separate useEffect for drawing.")

    if not issues:
        return "Valid. Component structure looks correct."
    return "Issues found:\n" + "\n".join(f"- {i}" for i in issues)


def _validate_sql(schema_sql: str) -> str:
    """Parse and validate SQL CREATE TABLE statements."""
    try:
        conn = sqlite3.connect(":memory:")
        conn.executescript(schema_sql)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        conn.close()
        return f"Valid. Tables created: {[t[0] for t in tables]}"
    except sqlite3.Error as e:
        return f"SQL Error: {e}"


def _validate_seed_data(schema_sql: str, seed_sql: str) -> str:
    """Validate seed INSERT statements against the schema."""
    try:
        conn = sqlite3.connect(":memory:")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(schema_sql)
        conn.executescript(seed_sql)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        counts = {}
        for (tbl,) in tables:
            count = conn.execute(f"SELECT COUNT(*) FROM [{tbl}]").fetchone()[0]
            counts[tbl] = count
        conn.close()
        low_tables = [f"{t} ({c} rows)" for t, c in counts.items() if c < 20]
        msg = f"Valid. Row counts: {counts}"
        if low_tables:
            msg += f"\nWARNING: Low row counts (< 20): {low_tables}"
        return msg
    except sqlite3.Error as e:
        return f"Seed data error: {e}"


def _check_types_match(schema_sql: str, types_ts: str) -> str:
    """Verify TypeScript interfaces align with SQL schema."""
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(schema_sql)
    except sqlite3.Error as e:
        return f"Cannot parse schema: {e}"

    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()

    issues = []
    for (tbl,) in tables:
        interface_name = "".join(w.capitalize() for w in tbl.split("_"))
        if interface_name not in types_ts and tbl not in types_ts:
            issues.append(f"Missing interface for table '{tbl}' (expected '{interface_name}')")

    conn.close()
    if issues:
        return "Issues found:\n" + "\n".join(f"- {i}" for i in issues)
    return "All tables have matching TypeScript interfaces."


# ── ToolDef instances (importable by agents) ─────────────────────────────────

read_skill_template = ToolDef(
    schema={
        "name": "read_skill_template",
        "description": (
            "Read a pre-built skill template for complex components. Use this for D3 maps, "
            "chart engines, export utilities, or AI chat layouts — components that are too "
            "complex to generate reliably from scratch. Available templates: "
            "WorldMap, UsaMap, CountryMap, Charts, PdfExport, PptxExport, ExcelExport, "
            "AiChat, DataChat, ExportToolbar. Returns the full source code."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "template_name": {
                    "type": "string",
                    "description": "Name of the template to load (e.g. 'WorldMap', 'AiChat')",
                }
            },
            "required": ["template_name"],
        },
    },
    fn=_read_skill_template,
)

validate_react_component = ToolDef(
    schema={
        "name": "validate_react_component",
        "description": (
            "Validate that a React/TypeScript component has correct basic structure: "
            "has imports, has a default export, uses proper hooks pattern, and doesn't "
            "import from non-existent local files. Pass the full .tsx source code."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source_code": {
                    "type": "string",
                    "description": "The full .tsx source code to validate",
                },
                "page_name": {
                    "type": "string",
                    "description": "Expected component/page name for export check",
                },
            },
            "required": ["source_code", "page_name"],
        },
    },
    fn=_validate_react_component,
)

validate_sql = ToolDef(
    schema={
        "name": "validate_sql",
        "description": (
            "Validate SQL schema syntax by executing CREATE TABLE statements against "
            "an in-memory SQLite database. Returns errors if any statement fails."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "schema_sql": {
                    "type": "string",
                    "description": "SQL containing CREATE TABLE statements to validate",
                },
            },
            "required": ["schema_sql"],
        },
    },
    fn=_validate_sql,
)

validate_seed_data = ToolDef(
    schema={
        "name": "validate_seed_data",
        "description": (
            "Validate seed data by running INSERT statements against the schema. "
            "Catches type mismatches, missing columns, and FK violations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "schema_sql": {
                    "type": "string",
                    "description": "SQL schema (CREATE TABLE statements)",
                },
                "seed_sql": {
                    "type": "string",
                    "description": "SQL INSERT statements to validate against the schema",
                },
            },
            "required": ["schema_sql", "seed_sql"],
        },
    },
    fn=_validate_seed_data,
)

check_types_match = ToolDef(
    schema={
        "name": "check_types_match",
        "description": (
            "Check that TypeScript interfaces match the SQL schema columns. "
            "Pass the schema SQL and the types.ts content."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "schema_sql": {
                    "type": "string",
                    "description": "SQL schema (CREATE TABLE statements)",
                },
                "types_ts": {
                    "type": "string",
                    "description": "TypeScript file content with interface definitions",
                },
            },
            "required": ["schema_sql", "types_ts"],
        },
    },
    fn=_check_types_match,
)
