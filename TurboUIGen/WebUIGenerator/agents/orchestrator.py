"""
CrewOrchestrator — runs specialized agents through a stage-based pipeline
to build a complete web application.

Stages:
  1. architecture  — UX Architect defines page structure + navigation
  2. data_modeling — Data Architect designs schema + seed + types
  3. infrastructure — React UI + Services generate config files + App shell
  4. components    — Visual Design generates shared D3 charts/maps
  5. pages         — React UI + Visual Design + AI generate individual pages
  6. integration   — Services verifies API connections, React UI fixes tsc errors

Each stage produces artifacts that become context for the next stage.
"""

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from .registry import get_agent


# Stage pipeline definition — who participates in each stage
STAGES = [
    {
        "id": "architecture",
        "name": "App Architecture",
        "agents": ["ux_architect"],
        "description": "Define page structure, navigation, and layout",
    },
    {
        "id": "data_modeling",
        "name": "Data Modeling",
        "agents": ["data_architect"],
        "description": "Design database schema, seed data, and TypeScript types",
    },
    {
        "id": "infrastructure",
        "name": "Infrastructure",
        "agents": ["react_ui", "services_engineer"],
        "description": "Generate config files, App.tsx shell, routing, and API setup",
    },
    {
        "id": "components",
        "name": "Shared Components",
        "agents": ["visual_design", "react_ui"],
        "description": "Generate reusable chart, map, and UI components",
    },
    {
        "id": "pages",
        "name": "Page Generation",
        "agents": ["react_ui", "visual_design", "ai_genai"],
        "description": "Generate all page components with full functionality",
    },
    {
        "id": "integration",
        "name": "Integration & Fixes",
        "agents": ["services_engineer", "react_ui"],
        "description": "Verify API connections and fix TypeScript errors",
    },
]


class CrewOrchestrator:
    """
    Orchestrates multiple specialized agents to build a web application.

    Replaces the monolithic 3-pass LLM approach with agents that collaborate:
    - UX Architect defines WHAT pages to build and HOW they're structured
    - Data Architect designs the data layer (schema, seed, types)
    - React UI Engineer builds the actual React components
    - Visual Design Engineer handles D3 charts and maps
    - Services Engineer connects frontend to backend API
    - AI/GenAI Engineer handles chat/LLM-powered features
    """

    def __init__(self, progress: Optional[Callable] = None):
        self.progress = progress
        self.artifacts: dict[str, str] = {}
        self.files: dict[str, str] = {}
        self.existing_context: dict[str, str] = {}  # set by caller for refinement
        self.existing_files: dict[str, str] = {}    # all existing project files (for selective regen)
        self.approved_architecture: dict | None = None  # pre-approved from /api/draft

    _ESSENTIAL_INFRA = {"package.json", "index.html", "src/main.tsx"}

    @property
    def is_refinement(self) -> bool:
        """True only when the existing project has essential boilerplate (not just stray files)."""
        if not self.existing_files:
            return False
        return bool(self._ESSENTIAL_INFRA & set(self.existing_files.keys()))

    def _p(self, msg: str):
        if self.progress:
            self.progress(msg)
        print(f"[crew] {msg}", flush=True)

    def _build_context(self, max_chars: int = 12000) -> str:
        """Build accumulated context from all artifacts so far."""
        parts = []
        for key, content in self.artifacts.items():
            truncated = content[:max_chars] if len(content) > max_chars else content
            parts.append(f"=== {key} ===\n{truncated}")
        return "\n\n".join(parts)

    def generate(self, user_prompt: str) -> dict:
        """
        Run the full multi-agent pipeline and return generated files.

        Returns: {"projectName": str, "title": str, "files": dict[str, str]}
        """
        self._p("crew:Starting multi-agent generation pipeline…")

        # Stage 1: Architecture (skip if pre-approved from /api/draft)
        if self.approved_architecture:
            self.artifacts["architecture"] = json.dumps(self.approved_architecture, indent=2)
            self._p("crew:Stage 1/6 — Using pre-approved architecture (from draft)")
        else:
            self._run_architecture(user_prompt)

        # Stage 2: Data Modeling
        self._run_data_modeling(user_prompt)

        # Stage 3: Infrastructure
        self._run_infrastructure(user_prompt)

        # Stage 4: Shared Components
        self._run_components(user_prompt)

        # Stage 5: Pages (parallel)
        self._run_pages(user_prompt)

        # Stage 6: Integration verification
        self._run_integration(user_prompt)

        # Extract project metadata from architecture artifact
        project_name = self._extract_project_name(user_prompt)
        title = self._extract_title(user_prompt)

        self._p(f"crew:Pipeline complete — {len(self.files)} files generated")

        # Parse architecture for return value
        import json as _json
        try:
            arch = _json.loads(self.artifacts.get("architecture", "{}"))
        except Exception:
            arch = {}

        return {
            "projectName": project_name,
            "title": title,
            "description": "",
            "files": self.files,
            "architecture": arch,
        }

    # ── Stage 1: Architecture ────────────────────────────────────────────────

    def _run_architecture(self, user_prompt: str):
        self._p("crew:Stage 1/6 — UX Architect designing app structure…")
        agent = get_agent("ux_architect")

        # In refinement mode, tell the architect about existing pages
        existing_pages_section = ""
        if self.existing_files:
            existing_page_names = sorted(
                fpath.replace("src/pages/", "").replace(".tsx", "")
                for fpath in self.existing_files
                if fpath.startswith("src/pages/") and fpath.endswith(".tsx")
            )
            if existing_page_names:
                existing_pages_section = f"""
IMPORTANT — REFINEMENT: This app already has these pages: {', '.join(existing_page_names)}.
You MUST include ALL existing pages in your architecture output (pages[] and navigation[]),
plus any NEW pages the prompt requests. Do NOT remove existing pages.
"""

        prompt = f"""Design the complete app architecture for this application:

{user_prompt}
{existing_pages_section}
Return a JSON object with this exact structure:
{{
  "projectName": "kebab-case-name",
  "title": "Human Readable App Title",
  "pages": [
    {{"name": "PageName", "type": "page-type", "description": "Detailed description of what this page shows and its layout"}},
    ...
  ],
  "navigation": [
    {{"label": "Page Label", "page": "PageName", "icon": "grid"}},
    ...
  ],
  "sharedComponents": [],
  "dataEntities": ["table_one", "table_two"],
  "hasAiFeatures": true/false
}}

RULES:
- Derive page names, count, and types ENTIRELY from the requirements — do not default to generic templates.
- Name pages based on the app's domain (e.g. "Portfolio", "Timesheets", "DocumentViewer", "AiAssistant").
  Do NOT use generic pattern-names like "DataGrid", "KpiDashboard", "ChartPage".
- Every page must have a descriptive type that indicates its primary UI pattern:
  dashboard, data-table, charts, map, card-grid, wizard, ai-chat, form, detail-view, or custom
- The description field is CRITICAL — it should fully describe what the page shows and how it's laid out.
  Include details about: what data it displays, what charts/tables/cards it has, what filters are available.
- Page count should match the requirements (usually 4-8 pages)
- sharedComponents: only list D3 chart/map components that multiple pages share. Usually leave empty.
- dataEntities: list the main data tables the app needs
- hasAiFeatures: true if the app needs AI chat, NLQ, or LLM-powered features
"""

        result = agent.generate(prompt, stage="architecture", json_mode=True, max_tokens=4000)
        self.artifacts["architecture"] = json.dumps(result, indent=2)
        self._p(f"crew:Architecture defined — {len(result.get('pages', []))} pages planned")

    # ── Stage 2: Data Modeling ────────────────────────────────────────────────

    def _run_data_modeling(self, user_prompt: str):
        self._p("crew:Stage 2/6 — Data Architect designing schema & seed data…")
        agent = get_agent("data_architect")

        arch = json.loads(self.artifacts.get("architecture", "{}"))
        entities = arch.get("dataEntities", [])
        pages = arch.get("pages", [])

        # Check if this is a refinement with existing schema to preserve
        existing_schema_section = ""
        if self.existing_context.get("schema"):
            existing_schema_section = f"""
IMPORTANT — REFINEMENT MODE:
This is an update to an EXISTING app. The current schema.sql is shown below.
You MUST include ALL existing tables unchanged in your output, plus any new tables.
DO NOT drop, rename, or modify existing tables. Only ADD new ones.

EXISTING schema.sql (MUST be preserved in full):
```sql
{self.existing_context['schema']}
```

EXISTING seed.sql preview (preserve ALL existing seed data and ADD new):
```sql
{self.existing_context.get('seed_preview', '')[:4000]}
```
"""

        prompt = f"""Design the complete data layer for this application:

App description: {user_prompt}

Architecture (from UX Architect):
- Pages planned: {json.dumps(pages, indent=2)}
- Data entities identified: {entities}
{existing_schema_section}
Generate a JSON object with:
{{
  "files": {{
    "schema.sql": "CREATE TABLE statements for ALL tables...",
    "seed.sql": "INSERT statements with 50+ realistic rows per table...",
    "src/types.ts": "TypeScript interfaces matching all tables..."
  }}
}}

CRITICAL: EVERY app MUST have a schema.sql, seed.sql, and src/types.ts.
All app data lives in SQLite and is served through a REST API.
There is NO static data, NO hardcoded JSON, NO frontend data files.
Even if the user prompt doesn't mention a database, YOU MUST design one.

RULES:
- Every table has: id INTEGER PRIMARY KEY AUTOINCREMENT
- Use snake_case for table/column names in SQL
- Every page's data needs must be satisfied by the schema
- Seed data must be REALISTIC (real countries, real names, plausible numbers)
- Include at least 50 rows per main table, 20+ for lookup tables
- TypeScript interfaces must exactly mirror SQL columns (camelCase field names)
- Include categorical columns for filtering, numeric for KPIs/charts, date for time-series
- Multi-value INSERT syntax: INSERT INTO table VALUES (...), (...), (...);
- If any page is type "kpi-dashboard", you MUST create a 'kpis' table with columns:
  id, metric TEXT, value TEXT, change_pct REAL, direction TEXT ('up'/'down'/'neutral')
  Seed it with 4-6 realistic KPI rows (e.g. Total Revenue, Units Sold, Active Users, etc.)
"""

        result = agent.generate(
            prompt, context=self._build_context(), stage="data_modeling",
            json_mode=True, max_tokens=32000,
        )
        files = result.get("files", {})
        self.files.update(files)
        self.artifacts["schema"] = files.get("schema.sql", "")
        self.artifacts["types"] = files.get("src/types.ts", "")
        self.artifacts["seed_preview"] = files.get("seed.sql", "")[:3000]
        self._p(f"crew:Data model complete — {len(files)} files")

    # ── Stage 3: Infrastructure ──────────────────────────────────────────────

    def _run_infrastructure(self, user_prompt: str):
        arch = json.loads(self.artifacts.get("architecture", "{}"))
        pages = arch.get("pages", [])
        nav = arch.get("navigation", [])
        title = arch.get("title", "Generated App")

        from agents.prompts import _brand_section

        # In refinement mode, only regenerate App.tsx (new routes/nav); preserve everything else
        if self.is_refinement:
            self._p("crew:Stage 3/6 — Updating App.tsx for new routes (preserving infra)…")
            # Carry over all existing infra files as-is
            infra_files = [
                "index.html", "package.json", "vite.config.ts", "tsconfig.json",
                "tailwind.config.js", "postcss.config.js", "src/main.tsx",
                "src/index.css", "src/utils/formatters.ts",
            ]
            for fpath in infra_files:
                if fpath in self.existing_files:
                    self.files[fpath] = self.existing_files[fpath]
            # Also preserve hooks and any other utility files
            for fpath, content in self.existing_files.items():
                if fpath.startswith("src/hooks/") or fpath.startswith("src/utils/"):
                    self.files[fpath] = content

            # Only regenerate App.tsx (needs updated lazy imports + routes + nav)
            existing_app_tsx = self.existing_files.get("src/App.tsx", "")
            agent = get_agent("react_ui")
            prompt = f"""Update the App.tsx for this React application to include ALL pages and navigation items.

App: {title}

The COMPLETE list of pages (use React.lazy for each):
{json.dumps(pages, indent=2)}

The COMPLETE navigation:
{json.dumps(nav, indent=2)}

Here is the EXISTING App.tsx — update it to add routes/nav items for new pages while preserving the existing structure, styling, sidebar colors, and component usage:
```tsx
{existing_app_tsx}
```

Return JSON: {{"files": {{"src/App.tsx": "..."}}}}

CRITICAL RULES:
- Keep the EXACT same structure, layout, styling as the existing App.tsx
- ONLY add new React.lazy imports, new Route entries, and new sidebar items for pages that don't exist yet
- Use mobility-global-ds for Header, Sidebar, Footer (import from 'mobility-global-ds')
- BrowserRouter is in src/main.tsx — App.tsx must NOT add another
- Icons: inline SVG elements (16x16, stroke="currentColor")
- Sidebar items must use onClick navigation with useNavigate
- Do NOT change colors, spacing, or layout of existing sidebar/header
- LAYOUT: Sidebar is a FLEX CHILD (auto 240px). NO position:fixed, NO marginLeft on main.
  Use: <div style={{display:'flex',flex:1}}> → <Sidebar .../> → <main style={{flex:1}}>
- Do NOT pass style, open, or className props to Sidebar — it only accepts: items, theme, collapsed, footer
"""
            result = agent.generate(
                prompt, context=self._build_context(max_chars=6000), stage="infrastructure",
                json_mode=True, max_tokens=16000,
            )
            files = result.get("files", {})
            self.files.update(files)
            self.artifacts["app_tsx"] = files.get("src/App.tsx", "")
            self._p(f"crew:Infrastructure complete — App.tsx updated, {len(infra_files)} files preserved")
            return

        self._p("crew:Stage 3/6 — React UI + Services building infrastructure…")
        agent = get_agent("react_ui")

        prompt = f"""Generate the infrastructure files for this React application:

App: {title}
Description: {user_prompt}

Pages (use React.lazy for each):
{json.dumps(pages, indent=2)}

Navigation:
{json.dumps(nav, indent=2)}

Types already defined:
{self.artifacts.get('types', '')}

Generate a JSON object with:
{{
  "files": {{
    "index.html": "...",
    "package.json": "...",
    "vite.config.ts": "...",
    "tsconfig.json": "...",
    "tailwind.config.js": "...",
    "postcss.config.js": "...",
    "src/main.tsx": "...",
    "src/index.css": "...",
    "src/App.tsx": "...",
    "src/utils/formatters.ts": "..."
  }}
}}

CRITICAL RULES:
- src/App.tsx: use React.lazy + Suspense for EVERY page import
- Use mobility-global-ds for Header, Sidebar, Footer (import from 'mobility-global-ds')
- DO NOT add "mobility-global-ds" to package.json — it is resolved via vite alias, NOT npm
- Sidebar items MUST be a STATIC array defined at the top of App.tsx (not computed, not filtered).
  ALL nav items are always visible. Use onClick with useNavigate for navigation.
- Icons: inline SVG elements (16x16, stroke="currentColor")
- BrowserRouter is in src/main.tsx (with basename) — App.tsx must NOT add another
- Routes: define ALL routes inside a single <Routes> block. EVERY page gets exactly one <Route>.
  Use <Route path="/" element={{<Navigate to="/first-page" />}} /> for the default redirect.

LAYOUT RULES (CRITICAL — do NOT deviate):
- The Sidebar component from mobility-global-ds is a FLEX CHILD. It renders at 240px width automatically.
- DO NOT use position:fixed or position:absolute on the Sidebar.
- DO NOT pass style, open, or className props to the Sidebar (it only accepts: items, sections, footer, collapsed, theme).
- DO NOT use marginLeft on the main content area. The flex layout handles spacing naturally.
- The layout structure MUST be exactly:
    <div style={{{{ display:'flex', flexDirection:'column', minHeight:'100vh' }}}}>
      <Header ... />
      <div style={{{{ display:'flex', flex:1, overflow:'hidden' }}}}>
        <Sidebar theme="dark" items={{sidebarItems}} />
        <main style={{{{ flex:1, overflowY:'auto', padding:16 }}}}>
          <Suspense fallback={{...}}>
            <Routes>...</Routes>
          </Suspense>
        </main>
      </div>
    </div>
- NO wrapper divs with marginTop around the flex container. NO fixed positioning anywhere.
- package.json must include: react, react-dom, react-router-dom, lucide-react, d3, us-atlas, world-atlas, topojson-client
- DO NOT put mobility-global-ds in package.json dependencies or devDependencies
- devDependencies: typescript, @types/react, @types/react-dom, @types/d3, vite, @vitejs/plugin-react, tailwindcss, postcss, autoprefixer
- vite.config.ts: alias 'mobility-global-ds' to path.resolve(__dirname, '../UIDesignSystem/src/index.ts')
- tsconfig.json: NO "references" field, NO tsconfig.node.json
- src/main.tsx: include BASE_URL basename for BrowserRouter

{_brand_section()}

src/main.tsx must be EXACTLY:
import React from 'react'
import ReactDOM from 'react-dom/client'
import {{ BrowserRouter }} from 'react-router-dom'
import App from './App'
import './index.css'

const BASE = import.meta.env.BASE_URL.replace(/\\/$/, '') || ''

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter basename={{BASE}} future={{{{ v7_startTransition: true, v7_relativeSplatPath: true }}}}>
      <App />
    </BrowserRouter>
  </React.StrictMode>
)
"""

        result = agent.generate(
            prompt, context=self._build_context(max_chars=6000), stage="infrastructure",
            json_mode=True, max_tokens=16000,
        )
        files = result.get("files", {})
        self.files.update(files)
        self.artifacts["app_tsx"] = files.get("src/App.tsx", "")
        self._p(f"crew:Infrastructure complete — {len(files)} files")

    # ── Stage 4: Shared Components ───────────────────────────────────────────

    def _run_components(self, user_prompt: str):
        arch = json.loads(self.artifacts.get("architecture", "{}"))
        shared = arch.get("sharedComponents", [])

        if not shared:
            self._p("crew:Stage 4/6 — No shared components needed, skipping")
            # In refinement mode, carry over all existing components
            if self.is_refinement:
                for fpath, content in self.existing_files.items():
                    if fpath.startswith("src/components/") and fpath.endswith(".tsx"):
                        self.files[fpath] = content
            return

        # In refinement mode, preserve components that already exist on disk
        to_generate = shared
        if self.is_refinement:
            existing_components = {
                fpath.replace("src/components/", "").replace(".tsx", "")
                for fpath in self.existing_files
                if fpath.startswith("src/components/") and fpath.endswith(".tsx")
            }
            to_generate = [c for c in shared if c not in existing_components]
            preserved = [c for c in shared if c in existing_components]
            for comp_name in preserved:
                comp_path = f"src/components/{comp_name}.tsx"
                if comp_path in self.existing_files:
                    self.files[comp_path] = self.existing_files[comp_path]
            # Also carry over any extra components not in the architecture list
            for fpath, content in self.existing_files.items():
                if fpath.startswith("src/components/") and fpath.endswith(".tsx"):
                    if fpath not in self.files:
                        self.files[fpath] = content

            if not to_generate:
                self._p(f"crew:Stage 4/6 — All {len(shared)} components preserved from existing project")
                self.artifacts["components"] = json.dumps([f"src/components/{c}.tsx" for c in shared])
                return

        self._p(f"crew:Stage 4/6 — Visual Design generating {len(to_generate)} shared components…")
        agent = get_agent("visual_design")

        from agents.prompts import PASS2_SYSTEM_PROMPT

        prompt = f"""Generate these shared components for a React/TypeScript app:

App description: {user_prompt}

Components to generate:
{chr(10).join(f"- src/components/{c}.tsx" for c in to_generate)}

Available types:
{self.artifacts.get('types', '')}

Schema (for understanding data shape):
{self.artifacts.get('schema', '')[:3000]}

Return JSON: {{"files": {{"src/components/X.tsx": "...", ...}}}}

RULES:
- Use D3 with useEffect + useRef + ResizeObserver pattern for all charts/maps
- Static imports for map data: import usaTopo from 'us-atlas/states-10m.json'
- All charts must have interactive React-state tooltips
- Follow canonical prop contracts (SalesMap: stateSales+makeFilter, etc.)
- Export both default and named exports
- useMemo all data arrays used as useEffect dependencies
"""

        result = agent.generate(
            prompt, context=self._build_context(max_chars=8000), stage="components",
            json_mode=True, max_tokens=32000,
        )
        files = result.get("files", {})
        self.files.update(files)
        self.artifacts["components"] = json.dumps(list(files.keys()))
        self._p(f"crew:Components complete — {len(files)} files")

    # ── Stage 5: Pages (parallel generation) ─────────────────────────────────

    def _pages_to_regenerate(self, pages: list[dict], user_prompt: str) -> tuple[list[dict], list[dict]]:
        """
        In refinement mode, determine which pages need regeneration vs which can be preserved.
        Returns (pages_to_generate, pages_to_preserve).

        Conservative by default: existing pages are preserved UNLESS they are explicitly
        named or described in the user prompt with clear intent to modify them.
        """
        if not self.existing_files:
            return pages, []

        # Find existing page files on disk (case-insensitive lookup)
        existing_page_names: set[str] = set()
        existing_page_names_lower: dict[str, str] = {}  # lowercase → actual name on disk
        for fpath in self.existing_files:
            if fpath.startswith("src/pages/") and fpath.endswith(".tsx"):
                name = fpath.replace("src/pages/", "").replace(".tsx", "")
                existing_page_names.add(name)
                existing_page_names_lower[name.lower()] = name

        # Strip system notes from prompt before matching (they contain noise like "KpiDashboard")
        prompt_for_matching = user_prompt
        sys_notes_idx = prompt_for_matching.find("[SYSTEM NOTES")
        if sys_notes_idx > 0:
            prompt_for_matching = prompt_for_matching[:sys_notes_idx]
        prompt_lower = prompt_for_matching.lower()

        # Detect explicit "keep existing pages" intent — if found, preserve ALL existing
        _keep_all_phrases = [
            "keep all existing pages",
            "keep existing pages unchanged",
            "do not modify existing pages",
            "don't modify existing pages",
            "do not change existing pages",
            "don't change existing pages",
            "leave existing pages",
            "existing pages unchanged",
            "do not update existing pages",
            "don't update existing pages",
        ]
        keep_all_existing = any(phrase in prompt_lower for phrase in _keep_all_phrases)

        to_generate = []
        to_preserve = []

        for page_info in pages:
            page_name = page_info["name"]

            # Case-insensitive check: if page exists on disk (even with slightly different casing)
            page_exists = (
                page_name in existing_page_names
                or page_name.lower() in existing_page_names_lower
            )

            # Page is new (not on disk) → must generate
            if not page_exists:
                to_generate.append(page_info)
                continue

            # If prompt explicitly says keep all existing → always preserve
            if keep_all_existing:
                to_preserve.append(page_info)
                continue

            # Page is explicitly mentioned in the prompt with modification intent → regenerate
            # Use STRICT matching: the exact page name (or its space-separated form) must appear
            # as a distinct phrase in the prompt, not just as a substring of another word.
            name_lower = page_name.lower()
            # "Dashboard" → check for "dashboard" as a word boundary
            # "SalesGrid" → check for "sales grid" or "salesgrid"
            name_spaced = re.sub(r'([a-z])([A-Z])', r'\1 \2', page_name).lower()
            name_variants = list(set([name_lower, name_spaced]))

            is_mentioned = False
            for variant in name_variants:
                # Word-boundary match: prevent "dashboard" matching inside "KpiDashboard"
                if re.search(r'\b' + re.escape(variant) + r'\b', prompt_lower):
                    is_mentioned = True
                    break

            if is_mentioned:
                to_generate.append(page_info)
            else:
                to_preserve.append(page_info)

        return to_generate, to_preserve

    def _run_pages(self, user_prompt: str):
        arch = json.loads(self.artifacts.get("architecture", "{}"))
        pages = arch.get("pages", [])

        if not pages:
            self._p("crew:Stage 5/6 — No pages defined, skipping")
            return

        # ── Selective regeneration: preserve unchanged pages ──────────────────
        to_generate, to_preserve = self._pages_to_regenerate(pages, user_prompt)

        if to_preserve:
            self._p(f"crew:Stage 5/6 — Preserving {len(to_preserve)} unchanged pages, generating {len(to_generate)}…")
            # Copy existing page files directly into self.files
            for page_info in to_preserve:
                page_name = page_info["name"]
                page_path = f"src/pages/{page_name}.tsx"
                config_path = f"src/config/{page_name}.config.ts"
                if page_path in self.existing_files:
                    self.files[page_path] = self.existing_files[page_path]
                if config_path in self.existing_files:
                    self.files[config_path] = self.existing_files[config_path]
        else:
            self._p(f"crew:Stage 5/6 — Generating {len(pages)} pages in parallel…")

        if not to_generate:
            self._p("crew:All pages preserved — nothing to regenerate")
            return

        # All pages are generated fully by the agents (no skill templates).
        # The agents use reference patterns for common UI elements but design unique layouts.
        def _gen_page(page_info: dict) -> tuple[str, dict]:
            page_name = page_info["name"]
            page_type = page_info.get("type", "custom")
            page_desc = page_info.get("description", "")
            return self._gen_custom_page(page_name, page_type, page_desc, user_prompt)

        max_workers = min(len(to_generate), 4)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_gen_page, p): p for p in to_generate}
            completed = 0
            for fut in as_completed(futures):
                page_name, page_files = fut.result()
                self.files.update(page_files)
                completed += 1
                self._p(f"crew:Page {completed}/{len(to_generate)}: {page_name} done")

    def _gen_skill_page(self, page_name: str, skill: dict, skill_tsx: str,
                        user_prompt: str) -> tuple[str, dict]:
        """Generate a page using the skill template (config-only LLM call)."""
        from agents.skills.registry import load_config_template, get_config_schema

        skill_key = skill["skill_key"]
        self._p(f"skill:⚡ {page_name} → [{skill_key}] skill matched — filling config…")

        config_template = load_config_template(page_name) or ""
        config_schema = get_config_schema(page_name) or {}

        agent = get_agent("react_ui")

        # Extra rules for chart/visualization skill configs
        chart_rules = ""
        if skill_key in ("charts", "visualization", "analytics"):
            chart_rules = """
CHART-SPECIFIC RULES:
- LINE CHARTS: If the spec mentions multiple dimensions (e.g. "top 5 makes" or "by region"),
  you MUST include one series entry per dimension. Shape data as one row per x-value with a
  field per series. E.g. data=[{quarter:'Q1', Tesla:100, Toyota:80, BMW:60}] with 3 series entries.
- TABBED LAYOUT: When the spec says "two tabs" (e.g. "Tab 1 — Volume, Tab 2 — Revenue"), use
  layout='tabs' and give each tab a nested charts[] array. Each tab entry = {title:'Tab Label', charts:[...]}.
- GROUPED-BAR: Must have series[] with one entry per bar group, and groupKey for the x-axis category.
- AREA CHARTS: For stacked areas with multiple regions/categories, include ALL as separate series entries.
- DATA AGGREGATION: Compute data arrays in the config file (import raw data, aggregate with .filter/.reduce).
  Ensure every x-value has a value for every series (use 0 for missing, never undefined).
- NEVER leave a series[] array with only 1 entry when the spec says "multi-line" or "by top N".
"""

        # Extra rules for KPI dashboard configs
        if skill_key == "kpi-dashboard":
            chart_rules += """
KPI DASHBOARD RULES:
- ALWAYS set kpiTableName to a real table from schema.sql that contains KPI/metric rows.
  Look for tables named 'kpis', 'metrics', 'summary', 'overview', or similar.
- Set kpiMapping fields (label, value, change, direction) to REAL column names from that table.
- Set kpiCards to null — the skill template fetches data from the API at runtime.
- NEVER use static kpiCards with hardcoded '$0' or '0%' placeholder values.
- For chart1 and chart2: set tableName to a real table, set labelField/valueField/xField/series
  to real column names. Set data: null (fetched at runtime).
- If no suitable KPI table exists in the schema, set kpiTableName to the most relevant table
  and map its columns accordingly.
"""

        prompt = f"""Fill in this config file for the '{page_name}' page.
The page uses the generic '{skill_key}' skill template.

App description: {user_prompt}

Available database schema and types:
{self.artifacts.get('schema', '')[:4000]}
{self.artifacts.get('types', '')[:3000]}

Config schema:
{chr(10).join(f"  {k}: {v}" for k, v in config_schema.items())}

Config template to fill in:
{config_template}

Return JSON: {{"files": {{"src/config/{page_name}.config.ts": "<filled config>"}}}}

RULES:
- CRITICAL: Replace EVERY {{{{PLACEHOLDER}}}} with real values from the schema
- Use table names and column names EXACTLY as they appear in schema.sql (snake_case)
- Field names in config (listBadgeField, key, searchFields, etc.) MUST use snake_case matching SQL columns.
  Example: 'doc_type' NOT 'docType', 'created_date' NOT 'createdDate', 'parent_doc_id' NOT 'parentDocId'.
  The API returns raw SQL column names in snake_case — camelCase fields will NOT match.
- badgeColors variants: ONLY default|success|warning|error|info|accent
- NEVER import from '../data' — use tableName: 'table_name_from_schema'. Set dataExport: null.
- The config must be valid TypeScript with zero {{{{PLACEHOLDER}}}} tokens remaining
{chart_rules}"""

        result = agent.generate(prompt, stage="pages", json_mode=True, max_tokens=4000)
        result_files = result.get("files", {})

        # ── Chart config validation: ensure multi-series for line/area charts ──
        if skill_key == "charts":
            config_path = f"src/config/{page_name}.config.ts"
            config_content = result_files.get(config_path, "")
            needs_fix = False

            # Check top-level line/area with only 1 series
            if re.search(r"chartType:\s*['\"](?:line|area)['\"]", config_content):
                series_matches = re.findall(r"series:\s*\[([^\]]*)\]", config_content)
                if series_matches:
                    first_series = series_matches[0]
                    entry_count = len(re.findall(r"field:", first_series))
                    if entry_count <= 1:
                        needs_fix = True

            # Check nested charts[] entries with type 'line' or 'area' that have <=1 series
            nested_line = re.findall(
                r"type:\s*['\"](?:line|area)['\"][^}]*?series:\s*\[([^\]]*)\]",
                config_content, re.DOTALL
            )
            for s_block in nested_line:
                if len(re.findall(r"field:", s_block)) <= 1:
                    needs_fix = True
                    break

            if needs_fix:
                self._p(f"skill:⚠️  {page_name} — line/area chart has ≤1 series, regenerating…")
                fix_prompt = prompt + (
                    "\n\nCRITICAL FIX REQUIRED: Your previous output had a line or area chart "
                    "with only 1 series entry. The spec requires MULTIPLE series (one per dimension). "
                    "For example, 'top 5 makes' needs 5 series entries. "
                    "Shape data with one row per x-value and a separate numeric field per series. "
                    "NEVER output a line/area chart with fewer than 2 series entries."
                )
                result2 = agent.generate(fix_prompt, stage="pages", json_mode=True, max_tokens=4000)
                result_files.update(result2.get("files", {}))

        # ── KPI config validation: ensure kpiTableName is set, not static zeros ──
        if skill_key == "kpi-dashboard":
            config_path = f"src/config/{page_name}.config.ts"
            config_content = result_files.get(config_path, "")
            has_static_zeros = bool(re.search(
                r"kpiCards:\s*\[[\s\S]*?value:\s*['\"][\$]?0['\"]", config_content
            ))
            missing_table = bool(re.search(
                r"kpiTableName:\s*null", config_content
            )) or "kpiTableName" not in config_content
            if has_static_zeros or missing_table:
                self._p(f"skill:⚠️  {page_name} — KPI config missing kpiTableName or has static zeros, regenerating…")
                fix_prompt = prompt + (
                    "\n\nCRITICAL FIX REQUIRED: Your previous output either used static kpiCards "
                    "with placeholder '$0' / '0%' values, or set kpiTableName to null. "
                    "You MUST set kpiTableName to a real table from schema.sql that contains KPI/metric rows "
                    "(look for 'kpis', 'metrics', 'summary', or pick the most relevant table). "
                    "Set kpiMapping fields to real column names. Set kpiCards: null so "
                    "the template fetches data dynamically from the API."
                )
                result2 = agent.generate(fix_prompt, stage="pages", json_mode=True, max_tokens=4000)
                result_files.update(result2.get("files", {}))

        # Patch the skill template import path
        page_path = f"src/pages/{page_name}.tsx"
        patched_tsx = re.sub(
            r"from\s+'(\.\./config/)[^']+\.config'",
            f"from '../config/{page_name}.config'",
            skill_tsx,
        )
        result_files[page_path] = patched_tsx

        # Bundle backend if skill has one
        backend_meta = skill.get("backend")
        if backend_meta:
            self._bundle_skill_backend(backend_meta, result_files)

        self._p(f"skill:✓ {page_name} → [{skill_key}] done")
        return page_name, result_files

    def _gen_custom_page(self, page_name: str, page_type: str, page_desc: str,
                         user_prompt: str) -> tuple[str, dict]:
        """Generate a page fully via LLM (no skill template match)."""
        self._p(f"crew:✏️  {page_name} → generating full page with LLM…")

        # Decide which agent leads based on page type
        has_ai = page_type in ("ai-chat", "data-chat", "copilot", "assistant")
        has_visual = page_type in (
            "charts", "visualization", "analytics", "heatmap",
            "world-map", "usa-map", "country-map", "map", "choropleth", "geo",
        )

        if has_ai:
            agent = get_agent("ai_genai")
        elif has_visual:
            agent = get_agent("visual_design")
        else:
            agent = get_agent("react_ui")

        from agents.component_contracts import build_component_api_section
        contracts = build_component_api_section()

        # In refinement mode, provide existing page code as reference
        existing_page_section = ""
        page_path = f"src/pages/{page_name}.tsx"
        if self.existing_files.get(page_path):
            existing_page_section = f"""
REFINEMENT: This page already exists. Below is its current code.
Preserve all working functionality and add/modify only what the prompt requests.
If the prompt adds features, keep all existing features intact.

Current {page_name}.tsx:
```tsx
{self.existing_files[page_path][:8000]}
```
"""

        # Build pattern-specific guidance based on page type
        pattern_guidance = self._get_pattern_guidance(page_type, page_desc)

        prompt = f"""Generate a complete, fully-working React page component.
Design a UNIQUE layout tailored to the specific requirements below — do NOT follow a generic template.

Page: {page_name}
Type: {page_type}
Description: {page_desc}

App description: {user_prompt}
{existing_page_section}

Available database schema (use EXACT table/column names from here):
{self.artifacts.get('schema', '')[:3000]}

Shared components available: {self.artifacts.get('components', '[]')}

{contracts}

Return JSON: {{"files": {{"src/pages/{page_name}.tsx": "<complete page code>"}}}}

═══ DATA FETCHING (CRITICAL) ═══
- import {{ useApi, apiAggregate }} from '../hooks/useApi'
- SYNTAX: const {{ data, loading, error }} = useApi<any[]>('table_name')
  Pass ONLY the SQL table name (e.g. 'documents', 'resources', 'timesheets').
  DO NOT pass a URL path. DO NOT write useApi('/api/data/...').
- The API returns SNAKE_CASE field names matching SQL columns exactly.
  Access: row.doc_type, row.created_date (NOT row.docType, row.createdDate).
- For aggregations: const result = await apiAggregate('table_name', {{ groupBy: 'column', agg: 'count' }})
- NEVER use raw fetch() for database data. NEVER import from '../data'.

═══ UI PATTERNS (use as building blocks, combine creatively) ═══
{pattern_guidance}

═══ COMPONENT IMPORTS (CRITICAL) ═══
- You may ONLY import from these sources:
  • 'mobility-global-ds' — SearchBar, Badge, Card, Header, Sidebar, Footer, etc.
  • '../hooks/useApi' — useApi, apiAggregate
  • '../components/ExportToolbar' — ExportToolbar (always available)
  • 'd3' — import * as d3 from 'd3'
  • 'react' / 'react-router-dom' / 'lucide-react'
- DO NOT import from '../components/DataTable', '../components/D3BarChart', or any
  other custom component. These DO NOT EXIST. Build everything INLINE in the page file.
  If you need a chart, build it inline with D3. If you need a table, build it inline with JSX.
- DO NOT create helper components in separate files. Everything goes in one page file.
  You CAN define sub-components (const MyChart = () => ...) at the top of the same file.

═══ D3 CHARTS (CRITICAL — prevent infinite loops) ═══
- ALWAYS use this exact ResizeObserver pattern:
  const ref = useRef<SVGSVGElement>(null)
  const [dims, setDims] = useState({{w:0, h:0}})
  useEffect(() => {{
    const el = ref.current?.parentElement
    if (!el) return
    const ro = new ResizeObserver(([e]) => {{
      const {{width}} = e.contentRect
      if (width > 0) setDims({{w: width, h: Math.min(width * 0.6, 300)}})
    }})
    ro.observe(el)
    return () => ro.disconnect()
  }}, [])  // ← EMPTY dependency array — observe once only
- Draw in a SEPARATE useEffect that depends on [data, dims]:
  useEffect(() => {{
    if (!ref.current || dims.w === 0 || !data?.length) return
    const svg = d3.select(ref.current)
    svg.selectAll('*').remove()
    // ... draw chart ...
  }}, [data, dims])
- NEVER put chart drawing inside the ResizeObserver callback
- NEVER set state inside the draw useEffect
- Null-guard ALL numeric computations: Number(row.value) || 0, filter out NaN before d3 scales
- EVERY chart MUST have hover tooltips on ALL interactive elements (bars, slices, dots, paths):
  const [tooltip, setTooltip] = useState<{{x:number,y:number,content:string}}|null>(null)
  .on('mouseenter', (event, d) => setTooltip({{x: event.offsetX, y: event.offsetY, content: `...`}}))
  .on('mousemove', (event) => setTooltip(prev => prev ? {{...prev, x: event.offsetX, y: event.offsetY}} : null))
  .on('mouseleave', () => setTooltip(null))
  Render: {{tooltip && <div style={{position:'absolute',left:tooltip.x+12,top:tooltip.y-28,...}}>{{tooltip.content}}</div>}}
  The chart container MUST have position:'relative' for the tooltip to anchor correctly.

═══ GENERAL RULES ═══
- SearchBar onChange receives a STRING (not event): onChange={{v => setQ(v)}}
- Show a loading spinner while data is loading; show error message on failure
- Page must be FULLY COMPLETE — no TODOs, no stubs, no placeholders
- Design the layout to match the specific requirements — don't use a generic grid
- Use Tailwind CSS for layout and spacing
- Minimum 200 lines of actual implementation
- Make it visually polished: proper spacing, colors, badges, hover states
- ALL data values from the API may be null — always null-guard: (row.field ?? 0), (row.field ?? '')
"""

        try:
            result = agent.generate(
                prompt, context=self._build_context(max_chars=6000),
                stage="pages", json_mode=True, max_tokens=32000,
            )
        except RuntimeError as e:
            if "truncated" in str(e).lower() or "two-pass" in str(e).lower():
                self._p(f"crew:⚠️  {page_name} response truncated — retrying with simplified prompt…")
                simplified_prompt = f"""Generate a React page component.

Page: {page_name}
Description: {page_desc}

Schema (use exact table/column names): {self.artifacts.get('schema', '')[:2000]}

Return JSON: {{"files": {{"src/pages/{page_name}.tsx": "<complete page code>"}}}}

RULES:
- import {{ useApi }} from '../hooks/useApi'
- SYNTAX: const {{ data, loading, error }} = useApi<any[]>('table_name') — pass ONLY the table name
- API returns SNAKE_CASE field names matching SQL: row.doc_type, row.created_date (NOT camelCase)
- Show loading spinner, handle error state
- Page must be FULLY COMPLETE — no TODOs, no stubs
- Keep the implementation concise but fully functional
- D3 charts: useEffect + useRef + ResizeObserver, import * as d3 from 'd3'
- Use Tailwind CSS for layout
"""
                result = agent.generate(
                    simplified_prompt, context="",
                    stage="pages", json_mode=True, max_tokens=32000,
                )
            else:
                raise
        return page_name, result.get("files", {})

    def _bundle_skill_backend(self, backend_meta: dict, result_files: dict):
        """Bundle backend server files for skills that need them."""
        from pathlib import Path
        from dotenv import dotenv_values

        templates_dir = Path(__file__).parent / "services_engineer" / "templates"
        parent_env_path = Path(__file__).parent.parent.parent / ".env"

        server_tpl = templates_dir / backend_meta["server_template"]
        env_tpl = templates_dir / backend_meta["env_template"]

        if server_tpl.exists():
            result_files["api/app_server.py"] = server_tpl.read_text(encoding="utf-8")
        if env_tpl.exists():
            env_content = env_tpl.read_text(encoding="utf-8")
            parent_env = dotenv_values(parent_env_path) if parent_env_path.exists() else {}
            env_content = env_content.replace("{{LITELLM_API_BASE}}", parent_env.get("LITELLM_API_BASE", ""))
            env_content = env_content.replace("{{LITELLM_API_KEY}}", parent_env.get("LITELLM_API_KEY", ""))
            env_content = env_content.replace("{{LITELLM_SSL_CERT}}", parent_env.get("LITELLM_SSL_CERT", ""))
            env_content = env_content.replace("{{LITELLM_MODEL}}", parent_env.get("LITELLM_SONNET_46_MODEL", "claude-sonnet-4-6"))
            result_files["api/.env"] = env_content

        reqs = backend_meta.get("requirements", [])
        if reqs:
            result_files["api/requirements.txt"] = "\n".join(reqs) + "\n"

    # ── Stage 6: Integration ─────────────────────────────────────────────────

    def _run_integration(self, user_prompt: str):
        self._p("crew:Stage 6/6 — Services Engineer verifying API integration…")

        schema = self.artifacts.get("schema", "")
        table_names = re.findall(r"CREATE TABLE\s+(?:IF NOT EXISTS\s+)?(\w+)", schema, re.IGNORECASE)
        table_names_lower = {t.lower(): t for t in table_names}

        # Extract column names per table from schema
        table_columns: dict[str, list[str]] = {}
        for table in table_names:
            col_pattern = re.compile(
                r"CREATE TABLE\s+(?:IF NOT EXISTS\s+)?" + re.escape(table) + r"\s*\(([^;]+)\)",
                re.IGNORECASE | re.DOTALL,
            )
            m = col_pattern.search(schema)
            if m:
                body = m.group(1)
                cols = re.findall(r"^\s*(\w+)\s+(?:INTEGER|REAL|TEXT|NUMERIC)", body, re.MULTILINE | re.IGNORECASE)
                table_columns[table] = cols
                table_columns[table.lower()] = cols

        fixes_applied = 0

        for file_path, content in list(self.files.items()):
            if not file_path.endswith((".tsx", ".ts")) or not content:
                continue
            original = content

            # ── Fix 0: useApi called with URL path instead of table name ────
            # e.g. useApi('/api/data/documents') → useApi('documents')
            url_pattern = re.findall(r"useApi[<\w>\[\]]*\s*\(\s*['\"]\/api\/data\/(\w+)['\"]", content)
            for table_ref in url_pattern:
                content = re.sub(
                    r"(useApi[<\w>\[\]]*\s*\(\s*)['\"]\/api\/data\/" + re.escape(table_ref) + r"['\"]",
                    r"\g<1>'" + table_ref + "'",
                    content,
                )
                print(f"  [integration] Fixed useApi('/api/data/{table_ref}') → useApi('{table_ref}') in {file_path}", flush=True)

            # Also fix useApi with any other URL-like paths (e.g. '/documents')
            slash_pattern = re.findall(r"useApi[<\w>\[\]]*\s*\(\s*['\"]\/(\w+)['\"]", content)
            for table_ref in slash_pattern:
                if table_ref in table_names or table_ref.lower() in table_names_lower:
                    actual_name = table_ref if table_ref in table_names else table_names_lower[table_ref.lower()]
                    content = re.sub(
                        r"(useApi[<\w>\[\]]*\s*\(\s*)['\"]/" + re.escape(table_ref) + r"['\"]",
                        r"\g<1>'" + actual_name + "'",
                        content,
                    )
                    print(f"  [integration] Fixed useApi('/{table_ref}') → useApi('{actual_name}') in {file_path}", flush=True)

            # ── Fix 1: Wrong table names in useApi calls ─────────────────────
            api_calls = re.findall(r"useApi[<\w>]*\s*\(\s*['\"](\w+)['\"]", content)
            for table_ref in api_calls:
                if table_ref in table_names:
                    continue
                if table_ref.lower() in table_names_lower:
                    correct = table_names_lower[table_ref.lower()]
                    content = content.replace(f"'{table_ref}'", f"'{correct}'")
                    content = content.replace(f'"{table_ref}"', f'"{correct}"')
                    print(f"  [integration] Fixed useApi('{table_ref}') → '{correct}' in {file_path}", flush=True)
                else:
                    best = self._fuzzy_match_table(table_ref, table_names)
                    if best:
                        content = content.replace(f"'{table_ref}'", f"'{best}'")
                        content = content.replace(f'"{table_ref}"', f'"{best}"')
                        print(f"  [integration] Fixed useApi('{table_ref}') → '{best}' (fuzzy) in {file_path}", flush=True)

            # ── Fix 2: Wrong table names in apiAggregate calls ────────────────
            agg_calls = re.findall(r"apiAggregate\s*\(\s*['\"](\w+)['\"]", content)
            for table_ref in agg_calls:
                if table_ref in table_names:
                    continue
                if table_ref.lower() in table_names_lower:
                    correct = table_names_lower[table_ref.lower()]
                    content = content.replace(f"'{table_ref}'", f"'{correct}'")
                    content = content.replace(f'"{table_ref}"', f'"{correct}"')

            # ── Fix 3: Wrong table names in fetch() calls to /api/data/ ──────
            fetch_tables = re.findall(r"/api/data/(\w+)", content)
            for table_ref in fetch_tables:
                if table_ref in table_names:
                    continue
                if table_ref.lower() in table_names_lower:
                    correct = table_names_lower[table_ref.lower()]
                    content = content.replace(f"/api/data/{table_ref}", f"/api/data/{correct}")

            # ── Fix 4: Ensure useApi import exists when used ─────────────────
            has_useapi_import = "from '../hooks/useApi'" in content or "from '../../hooks/useApi'" in content
            if "useApi" in content and not has_useapi_import:
                if "src/pages/" in file_path or "src/components/" in file_path:
                    depth = "../" if "src/pages/" in file_path else "../../"
                    content = f"import {{ useApi, apiAggregate }} from '{depth}hooks/useApi'\n" + content
                    print(f"  [integration] Added useApi import to {file_path}", flush=True)

            # ── Fix 5: Config files — validate tableName field ────────────────
            if file_path.endswith(".config.ts"):
                table_in_config = re.search(r"tableName:\s*['\"](\w+)['\"]", content)
                if table_in_config:
                    tref = table_in_config.group(1)
                    if tref not in table_names:
                        if tref.lower() in table_names_lower:
                            correct = table_names_lower[tref.lower()]
                            content = content.replace(f"'{tref}'", f"'{correct}'")
                            content = content.replace(f'"{tref}"', f'"{correct}"')
                            print(f"  [integration] Fixed tableName '{tref}' → '{correct}' in {file_path}", flush=True)
                        else:
                            best = self._fuzzy_match_table(tref, table_names)
                            if best:
                                content = content.replace(f"'{tref}'", f"'{best}'")
                                content = content.replace(f'"{tref}"', f'"{best}"')
                                print(f"  [integration] Fixed tableName '{tref}' → '{best}' (fuzzy) in {file_path}", flush=True)

            # ── Fix 6: Config files — fix camelCase field refs to snake_case ──
            if file_path.endswith(".config.ts"):
                # Build a lookup: camelCase → snake_case for all known columns
                camel_to_snake: dict[str, str] = {}
                for cols in table_columns.values():
                    for col in cols:
                        if "_" in col:
                            # Convert snake_case to camelCase for matching
                            parts = col.split("_")
                            camel = parts[0] + "".join(p.capitalize() for p in parts[1:])
                            camel_to_snake[camel] = col
                # Find camelCase strings in config that should be snake_case
                for camel, snake in camel_to_snake.items():
                    if f"'{camel}'" in content or f'"{camel}"' in content:
                        content = content.replace(f"'{camel}'", f"'{snake}'")
                        content = content.replace(f'"{camel}"', f'"{snake}"')
                        print(f"  [integration] Fixed field '{camel}' → '{snake}' in {file_path}", flush=True)

            # ── Fix 7: Remove imports of non-existent local components ────────
            if file_path.startswith("src/pages/"):
                # Find all relative imports from ../components/
                local_imports = re.findall(
                    r"^import\s+.*?from\s+['\"]\.\.\/components\/(\w+)['\"].*$",
                    content, re.MULTILINE,
                )
                allowed_components = {"ExportToolbar"}
                # Also allow any component that actually exists in self.files
                for fpath in self.files:
                    if fpath.startswith("src/components/") and fpath.endswith(".tsx"):
                        comp_name = fpath.replace("src/components/", "").replace(".tsx", "")
                        allowed_components.add(comp_name)

                for comp_name in local_imports:
                    if comp_name not in allowed_components:
                        # Remove the import line entirely
                        content = re.sub(
                            r"^import\s+.*?from\s+['\"]\.\.\/components\/" + re.escape(comp_name) + r"['\"].*\n?",
                            "", content, flags=re.MULTILINE,
                        )
                        # Also remove any JSX usage of this component (replace with a div placeholder)
                        content = re.sub(
                            r"<" + re.escape(comp_name) + r"\s[^/>]*/>",
                            "/* removed: " + comp_name + " */", content,
                        )
                        content = re.sub(
                            r"<" + re.escape(comp_name) + r"[\s>].*?</" + re.escape(comp_name) + r">",
                            "/* removed: " + comp_name + " */", content, flags=re.DOTALL,
                        )
                        print(f"  [integration] Removed missing component import '{comp_name}' from {file_path}", flush=True)

            # ── Fix 8: Prevent D3 ResizeObserver infinite loops ────────────────
            if "ResizeObserver" in content and "setDims" not in content:
                # Check for the dangerous pattern: drawing inside ResizeObserver callback
                if re.search(r"ResizeObserver\(\s*\(\[?.*?\]?\)\s*=>\s*\{[^}]*selectAll", content, re.DOTALL):
                    print(f"  [integration] WARNING: {file_path} has D3 draw inside ResizeObserver — may cause infinite loop", flush=True)

            if content != original:
                self.files[file_path] = content
                fixes_applied += 1

        # ── Fix 9: Validate App.tsx lazy imports match actual pages ────────
        app_tsx = self.files.get("src/App.tsx", "")
        if app_tsx:
            # Find all lazy import paths like: lazy(() => import('./pages/Dashboard'))
            lazy_imports = re.findall(r"import\(['\"]\.\/pages\/(\w+)['\"]\)", app_tsx)
            actual_pages = {
                fpath.replace("src/pages/", "").replace(".tsx", "")
                for fpath in self.files
                if fpath.startswith("src/pages/") and fpath.endswith(".tsx")
            }
            for page_ref in lazy_imports:
                if page_ref not in actual_pages:
                    print(f"  [integration] WARNING: App.tsx imports './pages/{page_ref}' but file doesn't exist", flush=True)
                    # Try to find a close match
                    for actual in actual_pages:
                        if actual.lower() == page_ref.lower():
                            app_tsx = app_tsx.replace(f"./pages/{page_ref}", f"./pages/{actual}")
                            print(f"  [integration] Fixed App.tsx: './pages/{page_ref}' → './pages/{actual}'", flush=True)
                            break
            # Check for pages that exist but aren't routed
            for actual in actual_pages:
                if actual not in lazy_imports and actual.lower() not in [p.lower() for p in lazy_imports]:
                    print(f"  [integration] WARNING: Page '{actual}' exists but has no route in App.tsx", flush=True)
            if app_tsx != self.files.get("src/App.tsx", ""):
                self.files["src/App.tsx"] = app_tsx
                fixes_applied += 1

        # ── Fix 10: Fix Sidebar layout (no fixed position, no marginLeft) ────
        app_tsx = self.files.get("src/App.tsx", "")
        if app_tsx:
            app_changed = False
            # Remove position:fixed/absolute applied to Sidebar wrapper or style prop
            if "position: 'fixed'" in app_tsx or 'position: "fixed"' in app_tsx or "position:'fixed'" in app_tsx:
                if "Sidebar" in app_tsx:
                    # Rewrite: remove style prop on Sidebar entirely (it doesn't accept it)
                    app_tsx_new = re.sub(
                        r"(<Sidebar\b[^>]*?)\s+style=\{\{[^}]*\}\}",
                        r"\1", app_tsx
                    )
                    if app_tsx_new != app_tsx:
                        app_tsx = app_tsx_new
                        app_changed = True
                        print("  [integration] Removed invalid style prop from Sidebar", flush=True)

            # Remove open prop from Sidebar (not a valid prop)
            if re.search(r"<Sidebar\b[^>]*\bopen=", app_tsx):
                app_tsx = re.sub(r"(<Sidebar\b[^>]*?)\s+open=\{[^}]*\}", r"\1", app_tsx)
                app_changed = True
                print("  [integration] Removed invalid 'open' prop from Sidebar", flush=True)

            # Remove marginLeft on main that mirrors sidebar width
            if re.search(r"marginLeft:\s*['\"]?240", app_tsx) or re.search(r"marginLeft:\s*sidebarOpen", app_tsx):
                app_tsx = re.sub(r"marginLeft:\s*sidebarOpen\s*\?\s*'240px'\s*:\s*'0'[,\s]*", "", app_tsx)
                app_tsx = re.sub(r"marginLeft:\s*['\"]240px['\"][,\s]*", "", app_tsx)
                app_changed = True
                print("  [integration] Removed marginLeft from main content (Sidebar is flex child)", flush=True)

            # Remove marginTop on the flex container (header is in flow, not fixed)
            if re.search(r"marginTop:\s*['\"]?64", app_tsx):
                app_tsx = re.sub(r"marginTop:\s*['\"]64px['\"][,\s]*", "", app_tsx)
                app_changed = True
                print("  [integration] Removed marginTop from flex container", flush=True)

            if app_changed:
                self.files["src/App.tsx"] = app_tsx
                fixes_applied += 1

        if fixes_applied:
            self._p(f"crew:Integration — fixed {fixes_applied} file(s)")
        else:
            self._p("crew:Integration check passed — all API references valid")

    @staticmethod
    def _get_pattern_guidance(page_type: str, page_desc: str) -> str:
        """Return relevant UI pattern snippets based on page type and description."""
        patterns = []
        desc_lower = (page_desc or "").lower() + " " + (page_type or "").lower()

        # Data table pattern
        if any(w in desc_lower for w in ["table", "grid", "list", "registry", "records", "log", "data"]):
            patterns.append("""
▸ DATA TABLE:
  - useState for filters (search, dropdowns), useMemo for filtered/sorted data
  - Pagination: const pageData = filtered.slice((page-1)*perPage, page*perPage)
  - Sortable headers: onClick toggles sortKey/sortDir state
  - Render badges for categorical fields: <span className="px-2 py-0.5 text-xs rounded-full bg-green-100 text-green-700">{row.status}</span>
  - Progress bars: <div className="w-full bg-gray-200 rounded-full h-2"><div className="bg-blue-500 h-2 rounded-full" style={{width:`${row.completion}%`}}/></div>
  - EXPORT: import { ExportToolbar } from '../components/ExportToolbar'
    <ExportToolbar data={filtered} columns={[{key:'name',header:'Name'},{key:'budget',header:'Budget',format:'currency'}]} title="Title" filename="export" />
""")

        # Chart/visualization pattern
        if any(w in desc_lower for w in ["chart", "donut", "bar", "line", "visualization", "analytics", "stacked", "scatter", "heatmap"]):
            patterns.append("""
▸ D3 CHARTS (follow this exact pattern to avoid infinite loops):
  const chartRef = useRef<SVGSVGElement>(null)
  const [chartDims, setChartDims] = useState({w:0, h:0})
  // Step 1: Observe size ONCE (empty dep array!)
  useEffect(() => {
    const el = chartRef.current?.parentElement
    if (!el) return
    const ro = new ResizeObserver(([e]) => {
      const {width} = e.contentRect
      if (width > 0) setChartDims({w: width, h: Math.min(width*0.6, 280)})
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  // Step 2: Draw when data OR dims change (NEVER set state here!)
  useEffect(() => {
    if (!chartRef.current || chartDims.w === 0 || !data?.length) return
    const svg = d3.select(chartRef.current).attr('width', chartDims.w).attr('height', chartDims.h)
    svg.selectAll('*').remove()
    // ... build scales, axes, shapes ...
  }, [data, chartDims])
  // JSX: <div style={{width:'100%'}}><svg ref={chartRef}/></div>

  CRITICAL: NEVER draw inside the ResizeObserver callback. NEVER setState inside the draw useEffect.
  Always null-guard values: const val = Number(row.field) || 0
  For multiple charts: use separate refs (chart1Ref, chart2Ref) and separate useEffects.
  Color palette: d3.schemeTableau10
""")

        # KPI/metrics pattern
        if any(w in desc_lower for w in ["kpi", "metric", "overview", "summary", "dashboard", "stat"]):
            patterns.append("""
▸ KPI/STAT CARDS:
  - Compute from fetched data: const totalBudget = data.reduce((s,r) => s + r.budget, 0)
  - Render as flex row of cards with: label (small, muted), value (large, bold), optional change indicator
  - Color indicators: green for positive, red for negative, gray for neutral
  - Use compact formatting: $1.2M, 85%, 142 — no long decimals
  - Can include sparklines or mini-bars inside cards using inline SVG
""")

        # Filter/search pattern
        if any(w in desc_lower for w in ["filter", "search", "dropdown", "sort"]):
            patterns.append("""
▸ FILTERS & SEARCH:
  - SearchBar from 'mobility-global-ds': <SearchBar placeholder="Search..." onChange={v => setSearch(v)} />
  - Dropdowns: <select value={filter} onChange={e => setFilter(e.target.value)} className="...">
    <option value="">All</option>{options.map(o => <option key={o} value={o}>{o}</option>)}</select>
  - Reset button clears all filters: onClick={() => { setSearch(''); setFilter(''); ... }}
  - Count badge: <span className="text-xs bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full">{filtered.length} results</span>
  - useMemo to derive filtered data from all filter states + raw data
""")

        # Wizard/form pattern
        if any(w in desc_lower for w in ["wizard", "create", "form", "step", "multi-step", "guided"]):
            patterns.append("""
▸ MULTI-STEP WIZARD:
  - useState<number>(0) for currentStep
  - Steps array: const steps = [{title:'Step 1', component: <StepOne />}, ...]
  - Progress bar: steps.map((s,i) => <div className={i <= currentStep ? 'bg-indigo-500' : 'bg-gray-200'} />)
  - Navigation: "Back" disables on step 0, "Next" validates before advancing
  - Form state: useState<Record<string,any>>({}) accumulates across steps
  - Final step: review/summary showing all collected data
""")

        # AI chat pattern
        if any(w in desc_lower for w in ["chat", "ai", "assistant", "conversation", "copilot", "persona"]):
            patterns.append("""
▸ AI CHAT:
  - Messages state: useRef<{role:'user'|'assistant', content:string}[]>([]) for conversation history
  - Submit: append user message to history, set loading, POST to `${BASE_URL}/api/chat` with
    body: { messages: conversationHistory, context: sampleContext }
    The 'messages' field is REQUIRED and must be an array of {role, content} objects (OpenAI format).
    Do NOT send {message: string} or {prompt: string}. Send full conversation array each request.
  - AbortController with 180s timeout. Retry on 502/503/504 (max 2 retries, 3s delay).
  - Response: {type: 'text'|'chart'|'table'|'map', response: string, data?: object}
  - Render: messages with user=dark bubble (ml-auto), AI=light bubble
  - Typing indicator: {loading && <div className="animate-pulse">...</div>}
  - Prompt buttons: pre-filled suggestions user can click to send
  - Personas: useState for active persona, prepend persona systemContext to user message content
  - Context: on mount, fetch sample rows from tables to pass as sampleContext in chat requests
""")

        # Map pattern
        if any(w in desc_lower for w in ["map", "geo", "choropleth", "world", "country", "region"]):
            patterns.append("""
▸ MAPS (D3 + TopoJSON):
  - import worldTopo from 'world-atlas/countries-110m.json' (or 'us-atlas/states-10m.json')
  - import * as topojson from 'topojson-client'
  - const features = topojson.feature(worldTopo, worldTopo.objects.countries).features
  - Projection: d3.geoNaturalEarth1() (world) or d3.geoAlbersUsa() (US)
  - Color scale: d3.scaleQuantize().domain([min,max]).range(d3.schemeBlues[7])
  - Hover tooltip with country/state name + value
""")

        # Card grid pattern
        if any(w in desc_lower for w in ["card", "grid", "tile", "gallery", "portfolio"]):
            patterns.append("""
▸ CARD GRID:
  - CSS grid: className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
  - Each card: rounded-xl border shadow-sm p-5 hover:shadow-md transition
  - Card content: title, subtitle, badges, progress bar, metadata row
  - Responsive: cards reflow from 3-col to 2-col to 1-col on smaller screens
""")

        if not patterns:
            patterns.append("""
▸ GENERAL:
  - Design a layout that best serves the page description
  - Use cards to group related content
  - Use flex/grid for responsive layouts
  - Include meaningful interactions (hover states, click handlers, toggles)
""")

        return "\n".join(patterns)

    @staticmethod
    def _fuzzy_match_table(ref: str, table_names: list[str]) -> str | None:
        """Find the closest table name using simple heuristics."""
        ref_lower = ref.lower().replace("_", "")
        best = None
        best_score = 0
        for t in table_names:
            t_lower = t.lower().replace("_", "")
            # Check if one contains the other
            if ref_lower in t_lower or t_lower in ref_lower:
                score = min(len(ref_lower), len(t_lower))
                if score > best_score:
                    best = t
                    best_score = score
            # Check shared prefix
            shared = 0
            for a, b in zip(ref_lower, t_lower):
                if a == b:
                    shared += 1
                else:
                    break
            if shared >= 4 and shared > best_score:
                best = t
                best_score = shared
        return best

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _extract_project_name(self, user_prompt: str) -> str:
        arch = json.loads(self.artifacts.get("architecture", "{}"))
        name = arch.get("projectName", "")
        if not name:
            words = re.sub(r"[^a-z0-9\s]", "", user_prompt.lower()).split()[:3]
            name = "-".join(words) if words else "app"
        return re.sub(r"[^a-z0-9-]", "-", name.lower()).strip("-") or "app"

    def _extract_title(self, user_prompt: str) -> str:
        arch = json.loads(self.artifacts.get("architecture", "{}"))
        return arch.get("title", "Generated App")
