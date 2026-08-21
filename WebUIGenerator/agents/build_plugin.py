"""
Generator for the `turbo-uigen` skills plugin.

Builds `agents/agent_sdk/` (the plugin root wired into ClaudeAgentOptions.plugins):
  .claude-plugin/plugin.json
  skills/<name>/SKILL.md + references/<copied template files>

Skills are generated from the SAME sources the legacy harness uses — the SKILL_REGISTRY
(agents/skills/registry.py) and the template files under each role's templates/ dir — so
there is one source of truth and no drift. `read_skill_template` is retired; the model
now reads a skill's references/ files directly.

Subagents are NOT built here — they are constructed programmatically from config.yaml in
agent_defs.py (single mechanism, no .md-frontmatter guessing).

Run:  python -m agents.build_plugin      (or import build() )
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .skills import registry as reg

AGENTS_DIR = Path(__file__).parent
PLUGIN_DIR = AGENTS_DIR / "agent_sdk"
SKILLS_DIR = PLUGIN_DIR / "skills"

# registry key -> skill directory name (mostly identical; "charts" -> "d3-charts")
COMPLEX_SKILLS = {
    "charts": "d3-charts",
    "world-map": "world-map",
    "usa-map": "usa-map",
    "country-map": "country-map",
    "pdf-export": "pdf-export",
    "pptx-export": "pptx-export",
    "excel-export": "excel-export",
    "ai-chat": "ai-chat",
    "data-chat": "data-chat",
}

TEMPLATE_DIRS = {
    "react_ui": AGENTS_DIR / "react_ui" / "templates",
    "visual_design": AGENTS_DIR / "visual_design" / "templates",
    "ai_genai": AGENTS_DIR / "ai_genai" / "templates",
    "services_engineer": AGENTS_DIR / "services_engineer" / "templates",
}


def _template_path(owner: str, filename: str) -> Path | None:
    p = TEMPLATE_DIRS.get(owner, AGENTS_DIR) / filename
    if p.exists():
        return p
    for d in TEMPLATE_DIRS.values():  # fallback search
        if (d / filename).exists():
            return d / filename
    return None


def _schema_lines(config_schema: dict) -> str:
    return "\n".join(f"- `{k}` — {v}" for k, v in (config_schema or {}).items())


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _copy_ref(src: Path | None, dest_dir: Path, warnings: list[str], label: str) -> str | None:
    if src is None or not src.exists():
        warnings.append(f"missing reference for {label}")
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest_dir / src.name)
    return src.name


def _build_complex_skill(reg_key: str, dir_name: str, warnings: list[str]) -> None:
    meta = reg.SKILL_REGISTRY.get(reg_key)
    if not meta:
        warnings.append(f"registry missing '{reg_key}'")
        return
    owner = meta["owner_agent"]
    skill_dir = SKILLS_DIR / dir_name
    refs = skill_dir / "references"

    tmpl = _copy_ref(_template_path(owner, meta["template"]), refs, warnings, f"{reg_key} template")
    cfg = _copy_ref(_template_path(owner, meta.get("config_file", "")), refs, warnings, f"{reg_key} config")

    triggers = ", ".join(meta.get("triggers", [])[:10])
    desc = f"{meta['description']} Use when a page needs: {triggers}."
    if len(desc) > 1000:
        desc = desc[:997] + "..."

    body = [f"---\nname: {dir_name}\ndescription: {desc}\n---\n", f"# {dir_name}\n"]
    body.append("## When to use\n")
    body.append(f"Trigger keywords: {', '.join(meta.get('triggers', []))}.\n")
    body.append("## How to build\n")
    if tmpl:
        body.append(
            f"This capability ships a full, tested reference implementation. **Read "
            f"`references/{tmpl}`** — it already implements the component. You have two options:\n"
            f"1. COPY VERBATIM — write it to the target page path unchanged.\n"
        )
    if cfg:
        body.append(
            f"2. FILL SCAFFOLD — read `references/{cfg}` and replace every `{{{{PLACEHOLDER}}}}` "
            f"with real fields, writing the config alongside the component.\n"
        )
    body.append("\n## Config contract\n")
    body.append(_schema_lines(meta.get("config_schema", {})) or "(see the config reference file)")
    body.append(
        "\n\n## House rules\n"
        "- D3 only for charts/maps (never Highcharts/Recharts/Chart.js).\n"
        "- Data comes from `useApi(tableName)` → `GET /api/data/{tableName}` (snake_case fields). "
        "Never import from `../data`.\n"
    )
    if reg_key == "data-chat" and meta.get("backend"):
        b = meta["backend"]
        body.append(
            f"\n## Backend\nThis skill needs a backend: server `{b['server_template']}`, "
            f"env `{b['env_template']}`, python deps: {', '.join(b['requirements'])}. "
            f"See the `fastapi-backend` skill.\n"
        )
    _write(skill_dir / "SKILL.md", "\n".join(body))


def _build_export_toolbar(warnings: list[str]) -> None:
    skill_dir = SKILLS_DIR / "export-toolbar"
    refs = skill_dir / "references"
    name = _copy_ref(_template_path("services_engineer", "ExportToolbar.component.tsx"), refs,
                     warnings, "export-toolbar")
    body = f"""---
name: export-toolbar
description: The shared ExportToolbar React component used by data pages to offer CSV/Excel/PDF exports. Use when a page (data table, dashboard) needs a consistent export toolbar.
---

# export-toolbar

The `ExportToolbar` component is a shared, TurboUIGen-managed export UI. It is already
bundled into every generated app at `src/components/ExportToolbar.tsx` (Python seeds it) —
**import it, do not re-create it**: `import ExportToolbar from '../components/ExportToolbar'`.

Reference source: `references/{name or 'ExportToolbar.component.tsx'}` (for prop shapes only).
"""
    _write(skill_dir / "SKILL.md", body)


D3_VIZ_PATTERNS = """---
name: d3-viz-patterns
description: Canonical D3 + React patterns for charts and maps in TurboUIGen — the mandatory recipe for responsive, tooltip-enabled, non-leaking D3 visualizations. Load before hand-writing any D3 chart or map.
---

# d3-viz-patterns

Mandatory patterns for ALL D3 work (charts and maps). Violating these causes the QA
static checks to fail.

## Rendering
- `useEffect` + `useRef<HTMLDivElement>` on the CONTAINER div (not the `<svg>`); give the
  container a `minHeight`.
- `d3.select(ref.current).select('svg').remove()` before every re-render.
- Wrap in a `ResizeObserver` for responsive width — but call `render()` IMMEDIATELY once,
  then hand it to the observer. Never do D3 drawing *inside* the observer callback only
  (infinite-loop / blank-on-first-paint).
- Never hardcode chart width; derive it from the container.
- Never use `parentElement` to size.

## Tooltips
- React state + an absolutely-positioned `<div>` inside the container. NEVER SVG `<text>`
  tooltips.

## Maps (TopoJSON is imported statically, never fetched)
- USA: `import usaTopo from 'us-atlas/states-10m.json'` + `d3.geoAlbersUsa()`.
- World: `import worldTopo from 'world-atlas/countries-110m.json'` + `d3.geoNaturalEarth1()`.
- Sub-national: public GeoJSON URL (see the country-map skill).
- Maps with hover MUST also support `.on('click', ...)` for select/drill-down.

## Data
- `useApi<any[]>('table_name')` → `/api/data/table_name`; fields are snake_case.
- Numeric guards: `Number(x) || 0`.
- "top 5 brands" means the config MUST have 5 series entries, not 1. Every series needs a
  value for every x — zero is valid, missing is not.

## Libraries
- D3 only. Never Highcharts, Recharts, Chart.js.
"""


def _build_fastapi_backend(warnings: list[str]) -> None:
    skill_dir = SKILLS_DIR / "fastapi-backend"
    refs = skill_dir / "references"
    for fn in ("app_server_template.py", "useApi.hook.ts", "datachat_api_server.py",
               "app_server_env_template.txt", "datachat_env_template.txt"):
        _copy_ref(_template_path("services_engineer", fn), refs, warnings, f"fastapi:{fn}")
    body = """---
name: fastapi-backend
description: How the generated app's SQLite + FastAPI backend works — the auto-generated REST surface (/api/data/{table}, /aggregate, /api/metadata, /api/chat) and the useApi hook contract. Load when writing schema.sql/seed.sql/types.ts or wiring pages to data.
---

# fastapi-backend

Every generated app has a Python FastAPI server (`api/app_server.py`, Python-managed —
do not edit it) that reads `api/schema.sql` + `api/seed.sql` into `data.db` and exposes an
auto-generated REST API per table. You author `api/schema.sql`, `api/seed.sql`,
`src/types.ts`, and the pages that consume the data.

## The API surface (auto-generated from your schema)
- `GET /api/data/{table}?sort=col&order=asc&limit=50` — rows (snake_case fields).
- `GET /api/data/{table}/{id}` · `POST/PUT/DELETE /api/data/{table}` — CRUD.
- `GET /api/data/{table}/aggregate?groupBy=col&metric=sum:amount` — grouped metrics.
- `GET /api/metadata` — tables/columns.
- `POST /api/chat` — LLM chat: body `{messages:[{role,content}], context}` (never `{message}`/`{prompt}`).

## Frontend contract
- Fetch with the pre-bundled hook: `import { useApi, apiAggregate } from '../hooks/useApi'`
  (`src/hooks/useApi.ts` is Python-managed — import, never recreate).
- Never `fetch('/api/...')` directly; never import from `../data`.
- Table + column names are snake_case and MUST match `schema.sql` exactly.

## schema.sql / seed.sql rules
- Every main table: ≥5 columns, ≥50 realistic seed rows (no `test`/`lorem`/`999` placeholders).
- No circular FKs. Use multi-row INSERT syntax.
- Each table needs a matching PascalCase interface in `src/types.ts`.

Reference implementations: `references/app_server_template.py`, `references/useApi.hook.ts`,
`references/datachat_api_server.py` (LLM data-chat backend).
"""
    _write(skill_dir / "SKILL.md", body)


def build() -> dict:
    """(Re)generate the whole plugin. Idempotent — wipes skills/ first."""
    warnings: list[str] = []
    if SKILLS_DIR.exists():
        shutil.rmtree(SKILLS_DIR)
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    for reg_key, dir_name in COMPLEX_SKILLS.items():
        _build_complex_skill(reg_key, dir_name, warnings)
    _build_export_toolbar(warnings)
    _write(SKILLS_DIR / "d3-viz-patterns" / "SKILL.md", D3_VIZ_PATTERNS)
    _build_fastapi_backend(warnings)

    plugin_json = {
        "name": "turbo-uigen",
        "description": "TurboUIGen web-app builder skills: D3 charts/maps, exports, AI chat, "
                       "and the SQLite+FastAPI backend contract.",
        "version": "1.0.0",
        "author": {"name": "TurboUIGen"},
    }
    _write(PLUGIN_DIR / ".claude-plugin" / "plugin.json", json.dumps(plugin_json, indent=2) + "\n")

    skill_names = sorted(p.parent.name for p in SKILLS_DIR.glob("*/SKILL.md"))
    return {"skills": skill_names, "warnings": warnings, "plugin_dir": str(PLUGIN_DIR)}


if __name__ == "__main__":
    result = build()
    print(f"Built plugin at {result['plugin_dir']}")
    print(f"Skills ({len(result['skills'])}): {', '.join(result['skills'])}")
    if result["warnings"]:
        print("WARNINGS:")
        for w in result["warnings"]:
            print(f"  - {w}")
    else:
        print("No warnings — all reference files copied.")
