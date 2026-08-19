"""
Draft Preview — converts architecture JSON into a visual Markdown wireframe.
Called by the /api/draft endpoint to show the user what will be built.
"""

import json
from typing import Optional


# Page type → ASCII layout sketch
_PAGE_LAYOUTS = {
    "kpi-dashboard": [
        "┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐",
        "│  KPI 1  │ │  KPI 2  │ │  KPI 3  │ │  KPI 4  │",
        "└─────────┘ └─────────┘ └─────────┘ └─────────┘",
        "┌──────────────────────┐ ┌──────────────────────┐",
        "│                      │ │                      │",
        "│    Bar Chart         │ │    Donut Chart       │",
        "│                      │ │                      │",
        "└──────────────────────┘ └──────────────────────┘",
        "┌─────────────────────────────────────────────────┐",
        "│              Line Chart (full width)            │",
        "└─────────────────────────────────────────────────┘",
    ],
    "data-grid": [
        "┌─────────────────────────────────────────────────┐",
        "│ [Search...] [Filter ▼] [Filter ▼] [Reset]  N rows│",
        "├─────────────────────────────────────────────────┤",
        "│ [Excel ↓] [PDF ↓]                              │",
        "├────┬────────┬────────┬────────┬────────┬───────┤",
        "│ #  │ Col A  │ Col B  │ Col C  │ Col D  │ Col E │",
        "├────┼────────┼────────┼────────┼────────┼───────┤",
        "│ 1  │ data   │ data   │ data   │ data   │ data  │",
        "│ 2  │ data   │ data   │ data   │ data   │ data  │",
        "│ .. │  ...   │  ...   │  ...   │  ...   │  ...  │",
        "├────┴────────┴────────┴────────┴────────┴───────┤",
        "│            ◀ Page 1 of N ▶                      │",
        "└─────────────────────────────────────────────────┘",
    ],
    "charts": [
        "┌─────────────────────────────────────────────────┐",
        "│  [Tab 1] [Tab 2]                               │",
        "├─────────────────────────────────────────────────┤",
        "│                                                 │",
        "│         Multi-line / Area Chart                 │",
        "│                                                 │",
        "├─────────────────────────────────────────────────┤",
        "│                                                 │",
        "│         Grouped Bar / Stacked Chart             │",
        "│                                                 │",
        "└─────────────────────────────────────────────────┘",
    ],
    "world-map": [
        "┌─────────────────────────────────────────────────┐",
        "│ [Make ▼]  [Quarter ▼]                          │",
        "├─────────────────────────────────────────────────┤",
        "│                                                 │",
        "│          🌍 World Choropleth Map                │",
        "│          (colored by sales volume)              │",
        "│                                                 │",
        "├─────────────────────────────────────────────────┤",
        "│ Region  │ Volume │ Revenue │ Top Make           │",
        "│─────────┼────────┼─────────┼────────────────────│",
        "│ Americas│  xxx   │  $xxx   │ Toyota             │",
        "└─────────────────────────────────────────────────┘",
    ],
    "usa-map": [
        "┌─────────────────────────────────────────────────┐",
        "│ [Make ▼]                                        │",
        "├─────────────────────────────────────────────────┤",
        "│                                                 │",
        "│          🇺🇸 USA Choropleth Map                 │",
        "│          (colored by state volume)              │",
        "│                                                 │",
        "├─────────────────────────────────────────────────┤",
        "│ State │ Make │ Volume │ Revenue │ Growth        │",
        "│───────┼──────┼────────┼─────────┼──────────────│",
        "│  CA   │ Tesla│  xxx   │  $xxx   │ +12%         │",
        "└─────────────────────────────────────────────────┘",
    ],
    "ai-chat": [
        "┌─────────────────────────────────────────────────┐",
        "│  AI Assistant                                   │",
        "├─────────────────────────────────────────────────┤",
        "│                                                 │",
        "│  🤖 How can I help you today?                   │",
        "│                                                 │",
        "│  👤 Show me sales by region                     │",
        "│                                                 │",
        "│  🤖 Here's a breakdown of sales...             │",
        "│     ┌──────────────────────┐                   │",
        "│     │ (inline chart/table) │                   │",
        "│     └──────────────────────┘                   │",
        "├─────────────────────────────────────────────────┤",
        "│  [Type your message...              ] [Send]   │",
        "└─────────────────────────────────────────────────┘",
    ],
    "settings-form": [
        "┌─────────────────────────────────────────────────┐",
        "│  Settings                                       │",
        "├─────────────────────────────────────────────────┤",
        "│  Label:    [________________]                   │",
        "│  Option:   [Dropdown ▼     ]                   │",
        "│  Toggle:   [●━━] On                            │",
        "│  Theme:    ○ Light  ● Dark  ○ System           │",
        "├─────────────────────────────────────────────────┤",
        "│                          [Cancel] [Save]       │",
        "└─────────────────────────────────────────────────┘",
    ],
}

_DEFAULT_LAYOUT = [
    "┌─────────────────────────────────────────────────┐",
    "│                                                 │",
    "│         (Custom page layout)                    │",
    "│                                                 │",
    "└─────────────────────────────────────────────────┘",
]


def format_draft_markdown(architecture: dict, prompt: str = "") -> str:
    """Convert architecture JSON to a visual Markdown wireframe preview."""
    lines = []

    project_name = architecture.get("projectName", "app")
    title = architecture.get("title", project_name)
    pages = architecture.get("pages", [])
    navigation = architecture.get("navigation", [])
    data_entities = architecture.get("dataEntities", [])
    shared_components = architecture.get("sharedComponents", [])
    has_ai = architecture.get("hasAiFeatures", False)

    # Header
    lines.append(f"# 📋 Draft: {title}")
    lines.append("")
    lines.append(f"**Project:** `{project_name}`  ")
    lines.append(f"**Pages:** {len(pages)}  ")
    lines.append(f"**Data tables:** {', '.join(data_entities) if data_entities else 'TBD'}  ")
    if has_ai:
        lines.append("**AI features:** Yes  ")
    lines.append("")

    # Navigation sidebar preview
    lines.append("---")
    lines.append("## 🧭 Navigation")
    lines.append("")
    lines.append("```")
    lines.append(f"┌────────────────────┐")
    lines.append(f"│  {title[:18]:<18}│")
    lines.append(f"├────────────────────┤")
    for nav in navigation:
        icon = nav.get("icon", "○")
        label = nav.get("label", nav.get("page", "?"))
        lines.append(f"│  {icon:<3} {label:<15}│")
    lines.append(f"└────────────────────┘")
    lines.append("```")
    lines.append("")

    # Page wireframes
    lines.append("---")
    lines.append("## 📄 Pages")
    lines.append("")

    for page in pages:
        name = page.get("name", "?")
        ptype = page.get("type", "custom")
        desc = page.get("description", "")

        lines.append(f"### {name}")
        lines.append(f"**Type:** `{ptype}` — {desc}")
        lines.append("")
        lines.append("```")
        layout = _PAGE_LAYOUTS.get(ptype, _DEFAULT_LAYOUT)
        for row in layout:
            lines.append(row)
        lines.append("```")
        lines.append("")

    # Data model preview
    lines.append("---")
    lines.append("## 🗄️ Data Model")
    lines.append("")
    lines.append("| Table | Purpose |")
    lines.append("|-------|---------|")
    for entity in data_entities:
        lines.append(f"| `{entity}` | Auto-generated from requirements |")
    lines.append("")
    lines.append("All data served via REST API (`/api/data/{table_name}`). Frontend uses `useApi` hook.")
    lines.append("")

    # Shared components
    if shared_components:
        lines.append("---")
        lines.append("## 🧩 Shared Components")
        lines.append("")
        for comp in shared_components:
            lines.append(f"- `{comp}` — reusable across multiple pages")
        lines.append("")

    # Summary
    lines.append("---")
    lines.append("## ✅ Ready to Build?")
    lines.append("")
    lines.append("If this looks good, confirm to generate the full application.")
    lines.append("If you'd like changes, describe what to modify and a new draft will be generated.")
    lines.append("")

    return "\n".join(lines)


def generate_draft(prompt: str, instructions: str = "", project_name: Optional[str] = None) -> dict:
    """
    Run only Stage 1 (UX Architect) and return architecture + Markdown preview.
    This is fast (~5-10s) and cheap (~4K tokens).
    When project_name is given and the project already exists, passes existing file
    context so the architect knows about existing pages (refinement draft).
    """
    import re
    from pathlib import Path
    from agents.orchestrator import CrewOrchestrator

    user_content = prompt
    if instructions:
        user_content = f"{prompt}\n\n## Detailed Instructions\n\n{instructions}"

    orchestrator = CrewOrchestrator(progress=lambda s: None)

    # If this is a refinement (existing project), load existing files for context
    if project_name:
        from config import WEB_APPS_DIR
        slug = re.sub(r"[^a-z0-9-]", "-", project_name.lower()).strip("-")
        existing_dir = WEB_APPS_DIR / slug
        if existing_dir.exists():
            existing_files: dict[str, str] = {}
            for fp in existing_dir.rglob("*"):
                if fp.is_file() and fp.suffix in (".tsx", ".ts", ".css", ".sql", ".py", ".html", ".json", ".js"):
                    rel = fp.relative_to(existing_dir).as_posix()
                    if rel.startswith("node_modules/") or rel.startswith("."):
                        continue
                    try:
                        existing_files[rel] = fp.read_text(encoding="utf-8")
                    except Exception:
                        pass
            if existing_files:
                orchestrator.existing_files = existing_files
            # Read schema for context
            schema_f = existing_dir / "api" / "schema.sql"
            if not schema_f.exists():
                schema_f = existing_dir / "schema.sql"
            if schema_f.exists():
                orchestrator.existing_context = {
                    "schema": schema_f.read_text(encoding="utf-8"),
                }

    orchestrator._run_architecture(user_content)

    architecture = json.loads(orchestrator.artifacts.get("architecture", "{}"))
    markdown = format_draft_markdown(architecture, prompt)

    return {
        "architecture": architecture,
        "markdown": markdown,
        "projectName": architecture.get("projectName", project_name or "app"),
        "title": architecture.get("title", "App"),
        "pageCount": len(architecture.get("pages", [])),
    }
