"""
CrewOrchestrator - runs specialized agents through a stage-based pipeline
to build a complete web application.

Stages:
  1. architecture  - UX Architect defines page structure + navigation
  2. data_modeling - Data Architect designs schema + seed + types
  3. infrastructure - React UI + Services generate config files + App shell
  4. components    - Visual Design generates shared D3 charts/maps
  5. pages         - React UI + Visual Design + AI generate individual pages
  6. integration   - Services verifies API connections, React UI fixes tsc errors

Each stage produces artifacts that become context for the next stage.
"""

import json
import os
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Optional

from AgentPlatform.core.registry import get_agent

# ── SDK Agents feature flag ──────────────────────────────────────────────────
# Set USE_SDK_AGENTS=true in .env to use Claude SDK Tool Runner agents
# instead of the legacy BaseAgent + llm.py path.
USE_SDK_AGENTS = os.environ.get("USE_SDK_AGENTS", "").lower() in ("true", "1", "yes")


def _find_matching_brace_end(content: str, open_brace_idx: int) -> int:
    """Index just past the '}' that closes the '{' at open_brace_idx,
    tracking string/template literals so a brace character inside a quoted
    string doesn't corrupt the depth count. Returns len(content) if the
    input is truncated/unbalanced (no match found)."""
    depth = 1
    in_string = None
    i, n = open_brace_idx + 1, len(content)
    while i < n:
        ch = content[i]
        if in_string:
            if ch == "\\":
                i += 2
                continue
            if ch == in_string:
                in_string = None
        elif ch in ("'", '"', "`"):
            in_string = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return n


def _looks_like_stubbed_render(content: str) -> bool:
    """
    Detect a page component that computed real state/data but rendered
    nothing — syntactically valid (so tsc-based validation never flags it),
    but the page is blank at runtime. Signature: the exported default
    function's LAST return statement (in source order) is a bare `return
    null`, despite the function clearly doing non-trivial data work
    (useApi/useState/useMemo used 3+ times) — i.e. it built everything up and
    then never actually rendered the normal/success-path JSX.

    `body` is scoped to exactly this function via brace-matching (not "from
    the opening brace to end of file") — a page that defines a small helper
    or sub-component AFTER the main exported one (a pattern the page-gen
    prompt explicitly allows) previously had that trailing code's own
    returns treated as "the last return in the function", so a completely
    unrelated `return null` early-exit in a helper could mark a fully
    working page as stubbed and trigger a wasted regeneration.
    """
    if not content:
        return False
    m = re.search(r"export\s+default\s+function\s+\w+[^{]*\{", content)
    if not m:
        return False
    body_end = _find_matching_brace_end(content, m.end() - 1)
    body = content[m.end():body_end]
    returns = list(re.finditer(r"\breturn\b[^;{]*", body))
    if not returns:
        return False
    last_return = returns[-1].group(0).strip()
    is_bare_null = bool(re.match(r"return\s+null\s*$", last_return))
    substantial_logic = len(re.findall(r"\buseMemo\s*\(|\buseState\s*\(|\buseApi\s*\(", body)) >= 3
    return is_bare_null and substantial_logic


def _ends_inside_unterminated_string(content: str) -> bool:
    """
    Scan the whole file tracking whether we're inside a '...'/"..."/`...`
    string literal (respecting backslash escapes), and report whether the
    file ends while still inside one.

    Reproduced directly: a real RiskRadar.tsx generation stopped mid-call —
    `svg.append('g').attr('trans` — a single unclosed paren and a single
    unclosed quote. _looks_truncated's own bracket-imbalance check (below)
    is deliberately loose (threshold of 2+) so it doesn't false-positive on
    ordinary intentional-looking imbalance inside string/JSX text — but that
    same looseness let this exact truncation through, since one unclosed
    paren doesn't clear the threshold. An unterminated string at end-of-file
    has no such ambiguity: real, complete TSX/JS source is never left mid-
    string, so any hit here is truncation, full stop — this check exists to
    catch precisely the truncations too small to trip the bracket check.
    Not a real parser — doesn't skip over comments or regex literals, so a
    stray quote inside a `//` comment could in principle fool it, but that's
    rare enough in generated page code for this to be a strict improvement.
    """
    in_string = None  # None, or the quote character currently open
    i, n = 0, len(content)
    while i < n:
        ch = content[i]
        if in_string:
            if ch == "\\":
                i += 2
                continue
            if ch == in_string:
                in_string = None
        elif ch in ("'", '"', "`"):
            in_string = ch
        i += 1
    return in_string is not None


def _looks_truncated(content: str) -> bool:
    """
    Cheap, syntax-unaware truncation heuristic — catches a response cut off
    mid-expression by hitting max_tokens. Reproduced directly: a real
    RiskRadar.tsx generation ended 829 lines in, mid-template-literal, with
    dozens of un-closed braces/parens/brackets — but the JSON *envelope*
    around it still closed cleanly (the model happened to emit a trailing
    quote+brace before running out of budget), so chat_json's own
    truncation detector saw valid JSON and never raised. That leaves the
    broken TSX *content* with nothing else in the pipeline positioned to
    catch it: tsc-based validation runs later, against files already
    written to disk, by which point this is the only page-generation-time
    chance to retry instead of shipping dead code. Not a real parser (no
    string/JSX-text awareness), so only flags GROSS imbalance — several
    unclosed brackets, the signature of a response that just stops
    mid-expression — not the occasional intentional imbalance inside a
    string literal. Paired with _ends_inside_unterminated_string above,
    which catches the smaller truncations this threshold is too loose for.
    """
    if not content:
        return True
    if _ends_inside_unterminated_string(content):
        return True
    return any(
        abs(content.count(open_ch) - content.count(close_ch)) > 2
        for open_ch, close_ch in (("{", "}"), ("(", ")"), ("[", "]"))
    )


def _normalize_component_name(name: str) -> str:
    """
    Convert an arbitrary page name into a clean PascalCase identifier safe
    for use as a file name / JS import (e.g. "Global Map" -> "GlobalMap").
    Page names double as file names (src/pages/{name}.tsx) and import paths
    downstream, but nothing stops the architecture stage from emitting a
    human-readable name with spaces - normalize once at the source so every
    later stage sees the same clean identifier.
    """
    if not name:
        return name
    parts = re.split(r"[^a-zA-Z0-9]+", name)
    cleaned = "".join(p[:1].upper() + p[1:] for p in parts if p)
    return cleaned or name


def _normalize_architecture_pages(arch: dict) -> dict:
    """Normalize pages[].name (and matching navigation[].page entries) to
    clean identifiers in-place, keeping navigation[].label untouched for
    display purposes."""
    pages = arch.get("pages")
    if not isinstance(pages, list):
        return arch
    rename_map = {}
    for page in pages:
        if not isinstance(page, dict):
            continue
        raw_name = page.get("name")
        if not isinstance(raw_name, str):
            continue
        clean_name = _normalize_component_name(raw_name)
        if clean_name and clean_name != raw_name:
            rename_map[raw_name] = clean_name
            page["name"] = clean_name
    if rename_map:
        for nav in arch.get("navigation") or []:
            if isinstance(nav, dict) and nav.get("page") in rename_map:
                nav["page"] = rename_map[nav["page"]]
    return arch


def _extract_nav_labels_order(app_tsx: str) -> list[str]:
    """
    Recover the current sidebar order from an existing App.tsx by scanning
    for `label: '...'` entries in source order (dedup'd). On a refinement,
    the architecture stage regenerates pages[]/navigation[] from scratch each
    time - without real order info, a plain (alphabetized) list of existing
    page names was observed to silently re-sort the sidebar.
    """
    if not app_tsx:
        return []
    labels = re.findall(r"label:\s*['\"]([^'\"]+)['\"]", app_tsx)
    seen = set()
    ordered = []
    for label in labels:
        if label not in seen:
            seen.add(label)
            ordered.append(label)
    return ordered


def _extract_app_title(app_tsx: str) -> str:
    """Recover the current app title from an existing App.tsx's <Header .../>."""
    if not app_tsx:
        return ""
    m = re.search(r"<Header\s+[^>]*?(?:brandName|title)=[\"']([^\"']+)", app_tsx)
    return m.group(1) if m else ""


def _heal_seed_sql(schema_sql: str, seed_sql: str, progress: Optional[Callable] = None) -> str:
    """
    Validate every INSERT statement in seed.sql against schema.sql in a
    throwaway in-memory SQLite database, one statement (i.e. one table) at a
    time. Both backend runtimes (Java's DatabaseInitializer and Python's
    app_server_template) execute each table's seed as a single batch
    statement, so one malformed literal anywhere in a 50-row INSERT silently
    drops every row for that table with no page-level error - catch and
    LLM-repair it here, before the file ever ships.
    """
    from agents.llm import chat

    if not schema_sql or not seed_sql:
        return seed_sql

    statements = re.split(r"(?=INSERT\s+INTO)", seed_sql, flags=re.IGNORECASE)
    preamble = []
    insert_stmts = []
    for stmt in statements:
        stmt = stmt.strip()
        if not stmt:
            continue
        if re.match(r"INSERT\s+INTO", stmt, re.IGNORECASE):
            insert_stmts.append(stmt)
        else:
            preamble.append(stmt)

    if not insert_stmts:
        return seed_sql

    changed = False
    for i, stmt in enumerate(insert_stmts):
        current = stmt
        for attempt in range(2):
            conn = sqlite3.connect(":memory:")
            try:
                conn.executescript(schema_sql)
                conn.executescript(current)
                conn.close()
                break
            except sqlite3.Error as e:
                conn.close()
                if attempt == 1:
                    if progress:
                        progress(f"seed_heal:Could not auto-repair a seed statement, leaving as-is ({e})")
                    break
                if progress:
                    progress(f"seed_heal:Fixing malformed seed data ({e})...")
                fix_prompt = (
                    "This SQL INSERT statement fails against its schema with this SQLite error:\n"
                    f"{e}\n\n"
                    "Fix ONLY the malformed value(s) causing this error. Keep every row, every "
                    "column, and all other data exactly as-is otherwise. Return ONLY the "
                    "corrected SQL statement - no markdown fences, no commentary.\n\n"
                    f"Schema:\n{schema_sql}\n\n"
                    f"Statement:\n{current}"
                )
                try:
                    fixed = chat(
                        [{"role": "user", "content": fix_prompt}],
                        system="You are a SQL expert. Fix syntax/data errors in SQLite INSERT statements.",
                        max_tokens=8000,
                    ).strip()
                    if fixed.startswith("```"):
                        fixed = re.sub(r"^```[^\n]*\n", "", fixed)
                        fixed = re.sub(r"\n```$", "", fixed.rstrip())
                    if fixed:
                        current = fixed
                except Exception:
                    break
        if current != stmt:
            insert_stmts[i] = current
            changed = True

    if not changed:
        return seed_sql
    return "\n\n".join(preamble + insert_stmts)


# api_architect's entity field "type" values -> TypeScript. Kept deliberately
# small/explicit (not a generic fallback) so a type this doesn't recognize
# fails loudly (falls back to "any" but is visible in the output) rather than
# silently producing a wrong-but-plausible-looking interface.
_ENTITY_FIELD_TS_TYPES = {
    "string": "string", "integer": "number", "float": "number",
    "boolean": "boolean", "datetime": "string", "uuid": "string",
}


def _entities_to_typescript(entities: list[dict]) -> str:
    """Deterministically derive src/types.ts from api_architect's own
    entities[] JSON (name/table/fields/relationships) — no LLM call, since
    the shape is fully known once the architecture stage has run. Replaces
    data_architect's old job of hand-authoring types.ts to "exactly mirror"
    a schema it also had to freely design; here the schema-shape and the
    interface are derived from the exact same source, so they can't drift."""
    blocks = []
    for entity in entities:
        name = entity.get("name") or "Entity"
        fields = entity.get("fields", [])
        lines = [f"export interface {name} {{"]
        for field in fields:
            fname = field.get("name")
            if not fname:
                continue
            ts_type = _ENTITY_FIELD_TS_TYPES.get(field.get("type", ""), "any")
            optional = "" if field.get("required") else "?"
            lines.append(f"  {fname}{optional}: {ts_type}")
        lines.append("}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n" if blocks else ""


def _sdk_generate(agent_type: str, prompt: str, context: str = "",
                  stage: str = "", images_b64: list[str] | None = None,
                  max_tokens: int = 32000, temperature: float | None = None) -> dict:
    """Route to the appropriate SDK agent. Returns dict with 'files' key."""
    if agent_type == "ux_architect":
        from AgentPlatform.catalog.ux_architect.agent_sdk_prototype import run_ux_architect
        return run_ux_architect(prompt, images_b64=images_b64, max_tokens=max_tokens)
    elif agent_type == "data_architect":
        from AgentPlatform.catalog.data_architect.agent_sdk_prototype import run_data_architect
        return run_data_architect(prompt, context=context, images_b64=images_b64, max_tokens=max_tokens)
    elif agent_type == "data_architect_delta":
        from AgentPlatform.catalog.data_architect.agent_sdk_prototype import run_data_architect_delta
        return run_data_architect_delta(prompt, context=context, max_tokens=max_tokens)
    elif agent_type == "react_ui":
        from AgentPlatform.catalog.react_ui.agent_sdk_prototype import run_react_ui
        return run_react_ui(prompt, context=context, stage=stage, images_b64=images_b64,
                            max_tokens=max_tokens, temperature=temperature)
    elif agent_type == "visual_design":
        from AgentPlatform.catalog.visual_design.agent_sdk_prototype import run_visual_design
        return run_visual_design(prompt, context=context, stage=stage, images_b64=images_b64,
                                 max_tokens=max_tokens, temperature=temperature)
    elif agent_type == "ai_genai":
        from AgentPlatform.catalog.ai_genai.agent_sdk_prototype import run_ai_genai
        return run_ai_genai(prompt, context=context, stage=stage, images_b64=images_b64,
                            max_tokens=max_tokens, temperature=temperature)
    else:
        raise ValueError(f"Unknown SDK agent type: {agent_type}")


# Stage pipeline definition - who participates in each stage
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
        "agents": ["react_ui", "webui_integration_engineer"],
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
        "agents": ["webui_integration_engineer", "react_ui"],
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
        self.reference_images: list[dict] | None = None  # Figma screenshots: [{name, base64_data}]
        # Only set by the caller for a refine (uigen_agent.py's generate_project
        # already knows the existing project's directory before calling
        # generate(), since project_name_override is required to detect
        # refinement in the first place) — see _flush_stage.
        self.project_dir: Optional[Path] = None
        # Set by the caller (generate_project) — previously only ever
        # embedded as prose inside the user prompt via _augment_prompt, never
        # available to the orchestrator itself as a real value. Needed now
        # that _run_backend_generation has to make a real branching decision
        # (which language to pass to ApiCrewOrchestrator), not just phrasing.
        self.backend_type: str = "python"

    _ESSENTIAL_INFRA = {"package.json", "index.html", "src/main.tsx"}

    # "data_architect_delta" isn't a real catalog agent — it's the same
    # data_architect persona/role, just asked for a different (much smaller)
    # output shape on refine (see _run_data_modeling_refine). The legacy path
    # has no fixed output schema to conflict with (chat_json just parses
    # whatever comes back), so it only needs the real registry id; the SDK
    # path (_sdk_generate) needs its own dedicated schema/function, since its
    # structured-output schema is strict and the normal one requires
    # schema.sql/seed.sql/src/types.ts keys that a delta response won't have.
    _FAKE_AGENT_TYPES = {"data_architect_delta": "data_architect"}

    def _call_agent(self, agent_type: str, prompt: str, context: str = "",
                    stage: str = "", images_b64: list[str] | None = None,
                    max_tokens: int = 32000, temperature: float | None = None) -> dict:
        """Unified agent call - routes to SDK or legacy based on feature flag."""
        if USE_SDK_AGENTS:
            from agents.sdk_client import set_progress
            set_progress(self.progress)
            return _sdk_generate(agent_type, prompt, context=context,
                                 stage=stage, images_b64=images_b64, max_tokens=max_tokens,
                                 temperature=temperature)
        else:
            agent = get_agent(self._FAKE_AGENT_TYPES.get(agent_type, agent_type))
            return agent.generate(prompt, context=context, stage=stage,
                                  json_mode=True, max_tokens=max_tokens, images_b64=images_b64,
                                  temperature=temperature)

    @property
    def is_refinement(self) -> bool:
        """True only when the existing project has essential boilerplate (not just stray files)."""
        if not self.existing_files:
            return False
        return bool(self._ESSENTIAL_INFRA & set(self.existing_files.keys()))

    def _flush_stage(self):
        """Write everything currently in self.files to self.project_dir —
        additive only, same shape as WebAPIGenerator's _flush_to_disk. Only
        called during a refine (self.project_dir is only ever set by the
        caller when refining an existing project — see uigen_agent.py's
        generate_project), so a crash partway through no longer rolls the
        existing project back to its pre-refine state; whatever stages
        completed are already on disk. Deliberately NOT used for fresh
        generation: _write_files()'s final wipe-then-write still runs
        unchanged at the very end regardless of path, so this is a strict
        addition, not a replacement of that finalization step."""
        if not self.project_dir or not self.is_refinement:
            return
        for fpath, content in self.files.items():
            out = self.project_dir / fpath
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(content, encoding="utf-8")

    def _p(self, msg: str):
        if self.progress:
            self.progress(msg)
        try:
            print(f"[crew] {msg}", flush=True)
        except (UnicodeEncodeError, UnicodeDecodeError):
            print(f"[crew] {msg.encode('ascii', errors='replace').decode('ascii')}", flush=True)

    def _build_context(self, max_chars: int = 12000, keys: list[str] | None = None) -> str:
        """Build accumulated context from artifacts.

        If keys is provided, only include those specific artifacts.
        """
        parts = []
        items = self.artifacts.items() if keys is None else (
            (k, self.artifacts[k]) for k in keys if k in self.artifacts
        )
        for key, content in items:
            truncated = content[:max_chars] if len(content) > max_chars else content
            parts.append(f"=== {key} ===\n{truncated}")
        return "\n\n".join(parts)

    # ── Large-spec context extraction ────────────────────────────────────────

    _LARGE_SPEC_THRESHOLD = 8000  # chars - beyond this, extract relevant sections

    def _is_large_spec(self, user_prompt: str) -> bool:
        """Detect whether user_prompt contains a large tech spec that should be sectioned."""
        return len(user_prompt) > self._LARGE_SPEC_THRESHOLD

    def _extract_sections(self, text: str) -> list[tuple[str, str, int]]:
        """Split a large markdown document into (heading, body, start_pos) sections."""
        import re as _re
        sections: list[tuple[str, str, int]] = []
        # Match markdown headings (## or ### level)
        pattern = _re.compile(r'^(#{1,4})\s+(.+)', _re.MULTILINE)
        matches = list(pattern.finditer(text))
        for i, m in enumerate(matches):
            heading = m.group(2).strip()
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            sections.append((heading, body, m.start()))
        if not sections:
            sections.append(("Full Document", text, 0))
        return sections

    # Markers emitted by the UI's InstructionsModal structured upload
    _DOC_MARKERS = {
        'prd': '## PRD - Product Requirements',
        'trd': '## TRD - Technical Requirements',
        'specs': '## Specs - Technical Specifications',
        'notes': '## Additional Notes',
    }

    def _split_structured_docs(self, text: str) -> dict[str, str]:
        """Split text by structured document markers if present. Returns {prd, trd, specs, notes, rest}."""
        docs: dict[str, str] = {}
        markers_found = [(k, text.find(m)) for k, m in self._DOC_MARKERS.items() if m in text]
        if not markers_found:
            return {'rest': text}
        markers_found.sort(key=lambda x: x[1])
        for i, (key, pos) in enumerate(markers_found):
            start = pos + len(self._DOC_MARKERS[key])
            end = markers_found[i + 1][1] if i + 1 < len(markers_found) else len(text)
            # Strip separator lines
            content = text[start:end].strip().removeprefix('---').strip()
            docs[key] = content
        # Text before first marker
        before = text[:markers_found[0][1]].strip()
        if before:
            docs['rest'] = before
        return docs

    def _extract_structured(self, docs: dict[str, str], stage: str,
                            page_name: str = "", page_desc: str = "") -> str:
        """Route structured PRD/TRD/Specs documents to the right stage with budget control."""
        budget = 25000
        parts: list[str] = []
        used = 0

        def _add(label: str, content: str, max_chars: int):
            nonlocal used
            if not content:
                return
            chunk = f"## {label}\n\n{content[:max_chars]}"
            if len(content) > max_chars:
                chunk += "\n[...truncated]"
            parts.append(chunk)
            used += len(chunk)

        # Include the "rest" (user's prompt text before the documents) first
        rest = docs.get('rest', '')
        if rest:
            _add("App Description", rest, 3000)

        prd = docs.get('prd', '')
        trd = docs.get('trd', '')
        specs = docs.get('specs', '')
        notes = docs.get('notes', '')

        if stage == "data_modeling":
            # Data needs: TRD (architecture, data models), Specs (schema, API), PRD (context)
            _add("Technical Requirements (TRD)", trd, 12000)
            _add("Technical Specifications (data-relevant)", specs, 10000)
            _add("Product Requirements (summary)", prd, 4000)
        elif stage == "infrastructure":
            # Infra needs: TRD (tech stack), PRD (overview)
            _add("Technical Requirements (TRD)", trd, 8000)
            _add("Product Requirements (overview)", prd, 5000)
            _add("Technical Specifications (summary)", specs, 5000)
        elif stage == "components":
            # Components need: Specs (component design), PRD (feature context)
            _add("Technical Specifications (components)", specs, 12000)
            _add("Product Requirements (features)", prd, 6000)
            _add("Technical Requirements (summary)", trd, 4000)
        elif stage == "pages":
            # Pages need: Specs (detailed page spec), PRD (user stories), TRD (context)
            # For page-specific extraction, try to find relevant sub-sections
            if page_name or page_desc:
                page_specs = self._find_relevant_subsections(specs, page_name, page_desc, 12000)
                page_prd = self._find_relevant_subsections(prd, page_name, page_desc, 6000)
                _add(f"Specs (for {page_name})", page_specs, 12000)
                _add(f"Product Requirements (for {page_name})", page_prd, 6000)
            else:
                _add("Technical Specifications", specs, 12000)
                _add("Product Requirements", prd, 6000)
            _add("Technical Requirements (summary)", trd, 4000)
        else:
            # Fallback: balanced mix
            _add("Product Requirements", prd, 8000)
            _add("Technical Requirements", trd, 8000)
            _add("Technical Specifications", specs, 8000)

        if notes:
            _add("Additional Notes", notes, 3000)

        return "\n\n".join(parts)

    def _find_relevant_subsections(self, text: str, page_name: str, page_desc: str,
                                   max_chars: int) -> str:
        """Extract subsections of a document that are most relevant to a specific page."""
        if not text or len(text) <= max_chars:
            return text

        sections = self._extract_sections(text)
        # Score by relevance to page
        page_words = set(re.sub(r'([A-Z])', r' \1', page_name).lower().split()) if page_name else set()
        desc_words = set(page_desc.lower().split()) if page_desc else set()
        all_keywords = {w for w in (page_words | desc_words) if len(w) > 3}

        scored: list[tuple[float, str, str]] = []
        for heading, body, _ in sections:
            combined = (heading + " " + body[:300]).lower()
            score = sum(2 for w in all_keywords if w in combined)
            scored.append((score, heading, body))

        scored.sort(key=lambda x: -x[0])
        result_parts: list[str] = []
        chars_used = 0
        for score, heading, body in scored:
            chunk = f"### {heading}\n{body}"
            if chars_used + len(chunk) > max_chars:
                remaining = max_chars - chars_used
                if remaining > 300:
                    result_parts.append(chunk[:remaining] + "\n[...]")
                break
            result_parts.append(chunk)
            chars_used += len(chunk)

        return "\n\n".join(result_parts) if result_parts else text[:max_chars]

    def _extract_for_stage(self, user_prompt: str, stage: str,
                           page_name: str = "", page_desc: str = "") -> str:
        """Extract relevant portions of a large spec for a given pipeline stage.

        For short prompts (< threshold), returns user_prompt unchanged.
        For large specs, extracts only sections relevant to the current stage/page
        to keep agent context focused and within effective attention bounds.

        When structured documents (PRD/TRD/Specs) are detected, routes content
        intelligently:
          - data_modeling -> TRD (full) + Specs (data sections) + PRD (summary)
          - infrastructure -> PRD (summary) + TRD (tech stack sections)
          - components -> Specs (component sections) + PRD (feature list)
          - pages -> Specs (relevant page sections) + PRD (relevant features)
        """
        if not self._is_large_spec(user_prompt):
            return user_prompt

        # Check for structured document format
        structured = self._split_structured_docs(user_prompt)
        if len(structured) > 1 or 'prd' in structured:
            return self._extract_structured(structured, stage, page_name, page_desc)

        sections = self._extract_sections(user_prompt)

        # Keywords for relevance scoring by stage
        _DATA_KW = {"data model", "database", "schema", "table", "entity", "column",
                    "migration", "seed", "type", "interface", "enum", "foreign key",
                    "index", "constraint"}
        _FRONTEND_KW = {"frontend", "component", "page", "ui", "layout", "form",
                        "route", "navigation", "sidebar", "header", "style", "css",
                        "react", "hook", "store", "state"}
        _API_KW = {"api", "endpoint", "rest", "request", "response", "auth",
                   "middleware", "controller", "service", "rate limit", "status code"}
        _INFRA_KW = {"docker", "deploy", "ci", "cd", "kubernetes", "terraform",
                     "monitoring", "infrastructure", "nginx", "environment"}

        stage_keywords: set[str] = set()
        if stage == "data_modeling":
            stage_keywords = _DATA_KW | _API_KW
        elif stage == "infrastructure":
            stage_keywords = _FRONTEND_KW | {"package", "config", "vite", "typescript"}
        elif stage == "components":
            stage_keywords = _FRONTEND_KW | {"chart", "d3", "map", "visualization", "component"}
        elif stage == "pages":
            stage_keywords = _FRONTEND_KW | _API_KW
        elif stage == "integration":
            stage_keywords = _FRONTEND_KW | _API_KW | {"import", "type", "error"}
        else:
            return user_prompt

        # Score each section by keyword overlap
        scored: list[tuple[float, str, str]] = []
        for heading, body, _ in sections:
            combined = (heading + " " + body[:500]).lower()
            score = sum(1 for kw in stage_keywords if kw in combined)
            # Boost if page name or page description words appear
            if page_name:
                page_words = set(re.sub(r'([A-Z])', r' \1', page_name).lower().split())
                score += sum(2 for w in page_words if w in combined and len(w) > 3)
            if page_desc:
                desc_words = set(page_desc.lower().split())
                score += sum(1 for w in desc_words if w in combined and len(w) > 3)
            scored.append((score, heading, body))

        # Sort by relevance and take the top sections that fit within budget
        scored.sort(key=lambda x: -x[0])
        budget = 20000  # chars budget for extracted context
        parts: list[str] = []
        used = 0

        # Always include a short summary (first ~2000 chars as overview)
        overview = user_prompt[:2000]
        if len(user_prompt) > 2000:
            overview += "\n\n[... spec continues - relevant sections extracted below ...]\n"
        parts.append(overview)
        used += len(overview)

        for score, heading, body in scored:
            if score <= 0:
                break
            chunk = f"\n### {heading}\n{body}"
            if used + len(chunk) > budget:
                remaining = budget - used
                if remaining > 500:
                    chunk = chunk[:remaining] + "\n[...trimmed]"
                else:
                    break
            parts.append(chunk)
            used += len(chunk)

        return "\n".join(parts)

    def generate(self, user_prompt: str) -> dict:
        """
        Run the full multi-agent pipeline and return generated files.

        Returns: {"projectName": str, "title": str, "files": dict[str, str]}
        """
        if USE_SDK_AGENTS:
            self._p("crew:Pipeline mode: Claude SDK agents")
        else:
            self._p("crew:Pipeline mode: Legacy agents (BaseAgent + LiteLLM)")
        self._p("crew:Starting multi-agent generation pipeline...")

        # Stage 1: Architecture (skip if pre-approved from /api/draft)
        if self.approved_architecture:
            approved = _normalize_architecture_pages(self.approved_architecture)
            self.artifacts["architecture"] = json.dumps(approved, indent=2)
            self._p("crew:Stage 1/6 - Using pre-approved architecture (from draft)")
        else:
            self._run_architecture(user_prompt)
        self._flush_stage()

        # Stage 2: Data Modeling
        self._run_data_modeling(user_prompt)
        self._flush_stage()

        # Stage 3: Infrastructure
        self._run_infrastructure(user_prompt)
        self._flush_stage()

        # Stage 4: Shared Components
        self._run_components(user_prompt)
        self._flush_stage()

        # Stage 5: Pages (parallel)
        self._run_pages(user_prompt)
        self._flush_stage()

        # Stage 6: Integration verification
        self._run_integration(user_prompt)
        self._flush_stage()

        # Extract project metadata from architecture artifact
        project_name = self._extract_project_name(user_prompt)
        title = self._extract_title(user_prompt)

        self._p(f"crew:Pipeline complete - {len(self.files)} files generated")

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
            "schemaChanges": self.artifacts.get("schema_changes_summary", ""),
        }

    # ── Stage 1: Architecture ────────────────────────────────────────────────

    def _run_architecture(self, user_prompt: str):
        self._p("crew:Stage 1/6 - UX Architect designing app structure...")

        # In refinement mode, tell the architect about existing pages
        existing_pages_section = ""
        if self.existing_files:
            existing_page_names = [
                fpath.replace("src/pages/", "").replace(".tsx", "")
                for fpath in self.existing_files
                if fpath.startswith("src/pages/") and fpath.endswith(".tsx")
            ]
            if existing_page_names:
                # Recover the real sidebar order + title from the existing
                # App.tsx rather than an alphabetized page-name list - see
                # _extract_nav_labels_order's docstring for why. Matching is
                # by stripped/lowercased comparison since a nav label (display
                # text, may contain spaces, e.g. "Global Map") and the page
                # file name ("GlobalMap") aren't always textually identical.
                def _norm(s: str) -> str:
                    return re.sub(r"[^a-z0-9]", "", s.lower())

                existing_app_tsx = self.existing_files.get("src/App.tsx", "")
                nav_labels = _extract_nav_labels_order(existing_app_tsx)
                page_norm_to_name = {_norm(name): name for name in existing_page_names}
                ordered_names = []
                for label in nav_labels:
                    name = page_norm_to_name.get(_norm(label))
                    if name and name not in ordered_names:
                        ordered_names.append(name)
                for name in existing_page_names:
                    if name not in ordered_names:
                        ordered_names.append(name)

                existing_title = _extract_app_title(existing_app_tsx)
                title_line = (
                    f'The existing app title is "{existing_title}" - keep this exact title '
                    "unless the prompt explicitly asks you to rename the app.\n"
                    if existing_title else ""
                )

                existing_pages_section = f"""
IMPORTANT - REFINEMENT: This app already has these pages, in this exact sidebar order:
{', '.join(ordered_names)}.
{title_line}You MUST include ALL existing pages in your architecture output (pages[] and
navigation[]), in THIS EXACT ORDER, plus any NEW pages the prompt requests appended at the
end. Do NOT remove, rename, or reorder existing pages as a side effect of an unrelated change
- only reorder/rename/remove a page if the prompt explicitly asks you to.
"""

        # Architecture gets the most context (needs full picture) but cap at 50k
        arch_prompt = user_prompt[:50000] + ("...[spec truncated]" if len(user_prompt) > 50000 else "")

        prompt = f"""Design the complete app architecture for this application:

{arch_prompt}
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
- Derive page names, count, and types ENTIRELY from the requirements - do not default to generic templates.
- Name pages based on the app's domain (e.g. "Portfolio", "Timesheets", "DocumentViewer", "AiAssistant").
  Do NOT use generic pattern-names like "DataGrid", "KpiDashboard", "ChartPage".
- Every page must have a descriptive type that indicates its primary UI pattern:
  dashboard, data-table, charts, map, card-grid, wizard, data-chat, form, detail-view, or custom
- "dashboard" is a SPECIFIC pattern (KPI cards row + charts + optional table) that maps
  directly to a generic template — use it ONLY when that's genuinely the page's whole
  layout. If the spec describes a bespoke visual layout (e.g. a custom grid of tiles, a
  monitoring wall, a spatial/NOC-style arrangement, a Gantt timeline) or explicitly says
  the page is NOT a table/dashboard/map, use "custom" instead — even if the page ALSO
  shows live totals or metrics somewhere on it. Showing metrics doesn't make it a
  "dashboard" if the actual layout doesn't match that generic pattern; mislabeling it
  "dashboard" causes the wrong generic template to be used instead of building the
  bespoke layout the spec actually asked for.
- The description field is CRITICAL - it should fully describe what the page shows and how it's laid out.
  Include details about: what data it displays, what charts/tables/cards it has, what filters are available.
  Preserve any explicit layout constraints from the spec verbatim (e.g. "NOT a table",
  "grid layout", "spatial arrangement") — do not paraphrase them away.
- Page count should match the requirements (usually 4-8 pages)
- sharedComponents: only list D3 chart/map components that multiple pages share. Usually leave empty.
- dataEntities: list the main data tables the app needs
- hasAiFeatures: true if the app needs AI chat, NLQ, or LLM-powered features
"""

        arch_images = None
        if self.reference_images:
            arch_images = [img["base64_data"] for img in self.reference_images]
            prompt = (
                "You are looking at screenshot(s) from a completed Figma design. "
                "Your ONLY job is to EXTRACT - not redesign - the page structure from these screenshots.\n\n"
                "RULES FOR FIGMA EXTRACTION:\n"
                "- Each screenshot = one page. Count them and name them based on what you see.\n"
                "- Page names must reflect the VISIBLE title/heading in each screenshot (e.g., 'Sales Overview', 'Vehicle Inventory').\n"
                "- Page type must reflect EXACTLY what's shown: if you see charts -> 'charts', a data table -> 'data-table', etc.\n"
                "- Page description must describe ONLY what is VISIBLE in the screenshot - list the specific charts, tables, KPI cards, etc.\n"
                "  Example: 'Top row: 4 KPI cards. Below: grouped bar chart on left (60%), data table on right (40%). Bottom: donut chart left, horizontal bar chart right.'\n"
                "- DO NOT add pages that aren't in the screenshots.\n"
                "- DO NOT redesign or reinterpret what you see - describe it literally.\n"
                "- For chart descriptions, be EXPLICIT about chart type: 'simple vertical bar chart' vs 'grouped bar chart' vs 'donut chart' vs 'line chart'.\n"
                "  Count the bars per x-axis category: ONE bar = simple bar chart, MULTIPLE bars = grouped.\n\n"
                + prompt
            )

        result = self._call_agent("ux_architect", prompt, stage="architecture",
                                   images_b64=arch_images, max_tokens=4000)
        result = _normalize_architecture_pages(result)
        self.artifacts["architecture"] = json.dumps(result, indent=2)
        self._p(f"crew:Architecture defined - {len(result.get('pages', []))} pages planned")

    # ── Stage 2: Data Modeling ────────────────────────────────────────────────

    # Bare filename ("schema.sql", "schema_v2.sql", "seed_v3.sql", ...) for
    # every schema/seed file already on disk for this project, regardless of
    # the api/ vs backend/ prefix _bundle_api_server/_bundle_java_api_server
    # add — that prefix is re-derived from the CURRENT backend_type each
    # round, not something to preserve verbatim.
    _VERSIONED_SQL_RE = re.compile(r"^(?:api|backend)/((?:schema|seed)(?:_v\d+)?\.sql)$")

    def _existing_schema_seed_files(self) -> dict[str, str]:
        out = {}
        for path, content in self.existing_files.items():
            m = self._VERSIONED_SQL_RE.match(path)
            if m:
                out[m.group(1)] = content
        return out

    @staticmethod
    def _sql_file_version(filename: str) -> int:
        m = re.match(r"(?:schema|seed)_v(\d+)\.sql$", filename)
        return int(m.group(1)) if m else 1

    def _next_schema_version(self, existing: dict[str, str]) -> int:
        versions = [self._sql_file_version(name) for name in existing if name.startswith("schema")]
        return (max(versions) if versions else 1) + 1

    def _compute_cumulative_schema(self, existing: dict[str, str]) -> str:
        """Deterministic "what tables/columns currently exist" — executes
        every existing schema*.sql (v1 + all versions) in order against a
        throwaway in-memory DB, then reflects the result back as CREATE
        TABLE text via the same sqlite_master + PRAGMA table_info
        introspection uigen_agent.py's _introspect_live_schema already uses
        for the live DB. Unlike the live DB, this never goes stale just
        because the generated app hasn't been restarted since the last
        refine — it's derived purely from the generated files themselves.
        """
        ordered = sorted(
            (name for name in existing if name.startswith("schema")),
            key=self._sql_file_version,
        )
        conn = sqlite3.connect(":memory:")
        try:
            for name in ordered:
                try:
                    conn.executescript(existing[name])
                except sqlite3.Error as e:
                    self._p(f"data_modeling:Warning - {name} failed while building cumulative schema: {e}")
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()]
            statements = []
            for table in tables:
                cols = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
                col_defs = ", ".join(f"{c[1]} {c[2] or 'TEXT'}" for c in cols)
                if col_defs:
                    statements.append(f"CREATE TABLE IF NOT EXISTS {table} ({col_defs});")
            return "\n".join(statements)
        finally:
            conn.close()

    @staticmethod
    def _cumulative_seed_sql(existing: dict[str, str]) -> str:
        """Concatenation of every existing seed*.sql (v1 + all versions), in
        version order — used only to give the validation step (below) real
        row data to run backfill UPDATEs against; never shown to the LLM
        (that's the truncated-preview problem this whole fix exists to
        avoid — the model only needs column structure, not row values, to
        design a delta)."""
        ordered = sorted(
            (name for name in existing if name.startswith("seed")),
            key=CrewOrchestrator._sql_file_version,
        )
        return "\n\n".join(existing[name] for name in ordered)

    def _validate_schema_delta(self, cumulative_schema: str, cumulative_seed: str,
                                new_tables: list, altered_tables: list) -> tuple[bool, str]:
        """Same philosophy as _heal_seed_sql above: prove the proposed SQL
        actually runs, in a throwaway in-memory clone, before it ever ships —
        this is the check this whole bug was missing. Loads the actual
        cumulative seed DATA (not just structure) so a backfill UPDATE runs
        against real existing rows, same as it will in the deployed app, and
        so its affected-row-count is meaningful for the refine report.
        Mutates each table dict in place with a row count for that report."""
        conn = sqlite3.connect(":memory:")
        try:
            if cumulative_schema:
                conn.executescript(cumulative_schema)
            if cumulative_seed:
                try:
                    conn.executescript(cumulative_seed)
                except sqlite3.Error as e:
                    self._p(f"data_modeling:Warning - could not load cumulative seed data for validation ({e})")
            for t in new_tables:
                if not t.get("name") or not t.get("create_table_sql"):
                    return False, f"new_tables entry missing name/create_table_sql: {t}"
                conn.executescript(t["create_table_sql"])
            for t in altered_tables:
                if not t.get("name"):
                    return False, f"altered_tables entry missing name: {t}"
                for c in t.get("new_columns", []):
                    conn.execute(f"ALTER TABLE {t['name']} ADD COLUMN {c['name']} {c.get('type') or 'TEXT'}")
            for t in new_tables:
                if t.get("seed_insert_sql"):
                    conn.executescript(t["seed_insert_sql"])
                count = conn.execute(f"SELECT COUNT(*) FROM {t['name']}").fetchone()[0]
                if count == 0:
                    return False, f"new table '{t['name']}' has zero seed rows after running its seed_insert_sql"
                t["_seed_row_count"] = count
            for t in altered_tables:
                if t.get("backfill_update_sql"):
                    conn.executescript(t["backfill_update_sql"])
                    t["_backfill_row_count"] = conn.execute(f"SELECT COUNT(*) FROM {t['name']}").fetchone()[0]
        except sqlite3.Error as e:
            return False, str(e)
        finally:
            conn.close()
        return True, ""

    @staticmethod
    def _summarize_schema_delta(new_tables: list, altered_tables: list) -> str:
        parts = []
        for t in new_tables:
            rows = t.get("_seed_row_count")
            parts.append(f"Added table `{t['name']}`" + (f" ({rows} seed rows)" if rows else ""))
        for t in altered_tables:
            cols = ", ".join(f"`{c['name']}`" for c in t.get("new_columns", []))
            rows = t.get("_backfill_row_count")
            parts.append(
                f"Added column(s) {cols} to `{t['name']}`" + (f" (backfilled {rows} existing rows)" if rows else "")
            )
        return ". ".join(parts) + "." if parts else ""

    def _carry_forward_schema_files(self, existing: dict[str, str]):
        """_write_files (uigen_agent.py) wipes api/backend/ and writes only
        what's in self.files each round — without this, a prior refine's
        schema_v2.sql/seed_v2.sql would be silently deleted the moment a
        later refine doesn't happen to touch them. Mirrors the exact
        carry-forward pattern _run_pages already uses for unchanged pages."""
        for name, content in existing.items():
            self.files.setdefault(name, content)

    def _run_data_modeling_refine(self, user_prompt: str, pages: list, entities: list,
                                   existing: dict[str, str]):
        """Refine-mode data modeling: ask for ONLY this refine's delta (new
        tables / new columns on existing tables), never a full schema+seed
        reproduction. The old "reproduce everything, plus additions" prompt
        required the model to re-emit every prior table's schema AND 50+
        seed rows each, growing every refine, with only a truncated preview
        of the real seed.sql as context — on later refines this silently
        dropped seed data for the newest table under token pressure, with
        nothing downstream checking for it. This method and
        _validate_schema_delta below exist specifically to fix that."""
        from datetime import date as _date
        current_year = _date.today().year

        cumulative_schema = self._compute_cumulative_schema(existing)
        cumulative_seed = self._cumulative_seed_sql(existing)
        effective_prompt = self._extract_for_stage(user_prompt, "data_modeling")

        prompt = f"""This is a REFINE of an app that already has a database. The
schema below is ALREADY APPLIED — do not recreate, repeat, or re-describe any
of it. Your only job is to identify what THIS refine's new/changed
requirements actually need to add to the database, if anything.

App description (this refine's new/changed requirements): {effective_prompt}

Architecture:
- Pages planned: {json.dumps(pages, indent=2)}
- Data entities identified: {entities}

CURRENT schema (reference only - already exists exactly as shown):
```sql
{cumulative_schema}
```

Return a JSON object with ONLY the delta:
{{
  "new_tables": [
    {{"name": "...", "create_table_sql": "CREATE TABLE ...",
      "seed_insert_sql": "INSERT INTO ... VALUES (...), (...), ...;"}}
  ],
  "altered_tables": [
    {{"name": "...", "new_columns": [{{"name": "...", "type": "TEXT"}}],
      "backfill_update_sql": "UPDATE ... SET ... ;"}}
  ]
}}

If this refine needs no database changes at all, return empty arrays for both.

RULES (for anything you DO generate):
- Every new table has: id INTEGER PRIMARY KEY AUTOINCREMENT
- Use snake_case for table/column names
- new_tables' seed_insert_sql needs REALISTIC data (real names, plausible
  numbers), at least 20 rows (50+ for a main/primary table), multi-value
  syntax: INSERT INTO table VALUES (...), (...), (...);
- DATE FIELDS: use {current_year} and {current_year - 1} - never older than 2 years ago
- altered_tables' backfill_update_sql MUST give EVERY existing row of that
  table a real value for the new column(s) - a bare UPDATE with no WHERE
  clause, using a CASE expression over other existing columns for realistic
  variety where sensible (you don't have the actual row data, only the
  column structure shown above, so lean on other columns/ids for variety)
- NEVER leave a NOT NULL column null
"""
        result = self._call_agent("data_architect_delta", prompt, context=self._build_context(),
                                   stage="data_modeling", max_tokens=32000)
        new_tables = result.get("new_tables", []) or []
        altered_tables = result.get("altered_tables", []) or []

        if not new_tables and not altered_tables:
            self._p("crew:Stage 2/6 - No database changes needed for this refine")
            self._carry_forward_schema_files(existing)
            return

        ok, error = self._validate_schema_delta(cumulative_schema, cumulative_seed, new_tables, altered_tables)
        if not ok:
            self._p(f"crew:Data model delta failed validation ({error}), retrying once...")
            retry_prompt = prompt + (
                f"\n\nYour previous response failed with this SQLite error:\n{error}\n"
                "Fix it and return the corrected JSON."
            )
            result = self._call_agent("data_architect_delta", retry_prompt, context=self._build_context(),
                                       stage="data_modeling", max_tokens=32000)
            new_tables = result.get("new_tables", []) or []
            altered_tables = result.get("altered_tables", []) or []
            ok, error = self._validate_schema_delta(cumulative_schema, cumulative_seed, new_tables, altered_tables)
            if not ok:
                raise RuntimeError(
                    f"Data Architect could not produce valid SQL for this refine's database changes: {error}"
                )

        version = self._next_schema_version(existing)
        schema_parts = [t["create_table_sql"] for t in new_tables]
        schema_parts += [
            f"ALTER TABLE {t['name']} ADD COLUMN {c['name']} {c.get('type') or 'TEXT'};"
            for t in altered_tables for c in t.get("new_columns", [])
        ]
        seed_parts = [t["seed_insert_sql"] for t in new_tables if t.get("seed_insert_sql")]
        seed_parts += [t["backfill_update_sql"] for t in altered_tables if t.get("backfill_update_sql")]

        self.files[f"schema_v{version}.sql"] = "\n\n".join(schema_parts)
        self.files[f"seed_v{version}.sql"] = "\n\n".join(seed_parts)
        self._carry_forward_schema_files(existing)

        self.artifacts["schema_changes_summary"] = self._summarize_schema_delta(new_tables, altered_tables)
        self._p(f"crew:Stage 2/6 - Database delta: {len(new_tables)} new table(s), {len(altered_tables)} altered table(s)")

    def _run_data_modeling(self, user_prompt: str):
        self._p("crew:Stage 2/6 - Data Architect designing schema & seed data...")

        arch = json.loads(self.artifacts.get("architecture", "{}"))
        entities = arch.get("dataEntities", [])
        pages = arch.get("pages", [])

        # A project whose backend was built by the new named-route pipeline
        # (marked by api/.architecture.json — see _run_backend_generation)
        # takes its own refine path: WebAPIGenerator's own added/modified/
        # affected-entity diffing, not the old SQL-versioning delta below,
        # which assumes data_architect's single-file schema/seed shape with
        # no ORM. Checked BEFORE the old-pipeline check, since a new-pipeline
        # project's api/schema.sql would otherwise also satisfy
        # _existing_schema_seed_files() and incorrectly take the old path.
        backend_marker = "api/.architecture.json" if self.backend_type == "python" else "backend/.architecture.json"
        if backend_marker in self.existing_files:
            self._run_backend_refine(user_prompt, arch)
            return

        # A refine with an existing schema takes the scoped delta-only path
        # above instead of the fresh-generation path below — see
        # _run_data_modeling_refine's own docstring for why. A refine on a
        # project that never had a schema yet (existing_schema_seed empty)
        # falls through to fresh generation below, correctly, since there's
        # nothing to preserve.
        existing_schema_seed = self._existing_schema_seed_files()
        if existing_schema_seed:
            self._run_data_modeling_refine(user_prompt, pages, entities, existing_schema_seed)
            return

        # Fresh generation: real per-entity ORM + named-route API via the
        # same agents/pipeline WebAPIGenerator uses (see
        # _run_backend_generation) — replaces the old data_architect-only
        # (schema.sql/seed.sql/types.ts, no real backend code) path below,
        # for both Python and Java. AI/chat apps are supported too —
        # _run_backend_generation bundles the same DataChat sidecar the old
        # Java path already used.
        self._run_backend_generation(user_prompt, arch, pages, entities)
        return

        from datetime import date as _date
        current_year = _date.today().year

        # When Figma screenshots are available, add data-model-to-visual mapping rules
        figma_data_rules = ""
        if self.reference_images:
            figma_data_rules = """
FIGMA VISUAL -> DATA MODEL RULES (CRITICAL):
Look at the attached screenshots. The data model MUST match the chart types shown:
- SIMPLE bar chart (one bar per x-label) -> table with ONE row per x-axis value.
  Example: monthly_metrics (id, month, total_value, total_count) - one row per month.
  Do NOT add a breakdown/category column that would imply grouping.
- GROUPED bar chart (multiple bars per x-label) -> table with a categorical breakdown column.
  Example: metrics_by_category (id, month, category_name, value) - multiple rows per month.
- DONUT/PIE chart -> table with (category, value/percentage) per slice.
- LINE chart -> table with sequential x-values (dates/months) and y-value columns.
- The chart type in the screenshot is the TRUTH. The title might mention categories,
  but if there's only ONE bar per label in the visual, the data must be pre-aggregated.
  Do NOT add breakdown columns unless the screenshot clearly shows multiple bars per label.
"""

        # Extract data-relevant sections from large specs
        effective_prompt = self._extract_for_stage(user_prompt, "data_modeling")

        prompt = f"""Design the complete data layer for this application:

App description: {effective_prompt}

Architecture (from UX Architect):
- Pages planned: {json.dumps(pages, indent=2)}
- Data entities identified: {entities}
{figma_data_rules}
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
- DATE FIELDS: All dates in seed data MUST be RECENT - use the current year ({current_year}) and the prior year ({current_year - 1}). Spread dates across the last 18 months. NEVER use dates older than 2 years from today. This ensures "last 12 months" filters always show data.
- Include at least 50 rows per main table, 20+ for lookup tables
- TypeScript interfaces must use the EXACT SAME field names as the SQL columns
  (snake_case, NOT camelCase) - the REST API returns raw SQLite column names
  unconverted (no camelCase transformation happens anywhere in the pipeline),
  so a camelCase interface will not match the real API response shape and
  every page reading that field will fail to compile
- Include categorical columns for filtering, numeric for KPIs/charts, date for time-series
- Multi-value INSERT syntax: INSERT INTO table VALUES (...), (...), (...);
- NEVER use null for columns marked NOT NULL in seed.sql - use realistic placeholder values instead (e.g. '' for text, 0 for numbers)
- If any page is type "kpi-dashboard", you MUST create a 'kpis' table with columns:
  id, metric TEXT, value TEXT, change_pct REAL, direction TEXT ('up'/'down'/'neutral')
  Seed it with 4-6 realistic KPI rows (e.g. Total Revenue, Units Sold, Active Users, etc.)
"""

        # Pass screenshots to data modeler so it can see chart types and design matching schema
        data_images = None
        if self.reference_images:
            data_images = [img["base64_data"] for img in self.reference_images]

        try:
            result = self._call_agent("data_architect", prompt, context=self._build_context(),
                                       stage="data_modeling", images_b64=data_images, max_tokens=64000)
        except ValueError as e:
            # Schema + seed (50+ rows/table across every table) + TypeScript types
            # in one response can land right at the max_tokens ceiling for
            # data-heavy specs (e.g. a 150-row table) — truncation mid-response is
            # what actually raises "Could not extract JSON" here, not a formatting
            # error. Confirmed by observing the exact same prompt/max_tokens
            # succeed on a bare retry: it's a knife's-edge fit, not a deterministic
            # failure, so a higher ceiling (this call already doubled from 32000)
            # plus the retry below meaningfully reduces the odds of hitting it.
            if "Could not extract JSON" not in str(e):
                raise
            self._p("crew:Data Architect response was malformed/truncated, retrying...")
            result = self._call_agent("data_architect", prompt, context=self._build_context(),
                                       stage="data_modeling", images_b64=data_images, max_tokens=64000)
        files = result.get("files", {})
        self.files.update(files)
        if files.get("schema.sql") and files.get("seed.sql"):
            healed_seed = _heal_seed_sql(files["schema.sql"], files["seed.sql"], progress=self._p)
            if healed_seed != files["seed.sql"]:
                self.files["seed.sql"] = healed_seed
        self.artifacts["schema"] = files.get("schema.sql", "")
        self.artifacts["types"] = files.get("src/types.ts", "")
        self.artifacts["seed_preview"] = self.files.get("seed.sql", "")[:3000]
        self._p(f"crew:Data model complete - {len(files)} files")

    # Shared between _run_backend_generation (fresh) and _run_backend_refine
    # (added entities on a refine) — same caller-specific requirements
    # either way, since a refine's newly-added entities need the exact same
    # contract as a fresh entity would.
    _BACKEND_SUPPLEMENTAL_REQUIREMENTS = """Additional requirements specific to this caller:
- Route paths: do NOT version routes under /api/v1/, and do NOT pluralize
  or kebab-case the resource name. Every entity's routes MUST be
  /api/{table} and /api/{table}/{id} — {table} is EXACTLY that entity's
  table name from your own entities[] JSON, unchanged (e.g. table
  "chat_message" -> routes under /api/chat_message, NOT /api/v1/chat-
  messages or /api/chat_messages). A frontend that already knows each
  table's exact name builds these routes itself from that name — any
  version prefix, pluralization, or casing change breaks that.
- Every entity's field names MUST be snake_case (not camelCase) — a
  TypeScript interface is derived directly from your entities[] JSON and
  must exactly match whatever field names you choose.
- Do NOT generate a GET /{table}/aggregate endpoint yourself — that's added
  deterministically after your code is generated (see
  _fix_backend_route_conventions), since chart/KPI pages depend on it
  using an EXACT param/response contract that's cheaper to guarantee in
  code than to keep re-specifying correctly in a prompt.
- Also generate one deterministic GET /metadata endpoint (bare, not under
  any entity's path) returning {"tables": [{"name":..., "columns":
  [{"name":..., "type":...}]}]} for every entity — used by tooling
  (MCP/chat), not end users.
- List endpoints must return a plain JSON object shaped
  {"data": [...], "total": N, "limit": N, "offset": N, "hasMore": bool}
  — Python: a plain dict as already instructed; do not wrap it in any other
  envelope.
- Python only: every row inside that "data" list MUST already be an
  instance of the entity's own Pydantic response schema (e.g.
  StudentResponse.model_validate(row)), never a raw SQLAlchemy model
  instance. The route's response_model=dict gives Pydantic's serializer no
  type information to convert nested ORM objects automatically, so a list
  service that does `"data": rows` (rows straight from the repository call)
  crashes every single request with "Unable to serialize unknown type" —
  invisible until a real request is made, since the app still imports and
  boots fine.
- Seed data: 50-100 realistic rows per main table (this is a demo app, not
  a production API — favor a visibly realistic amount of data over the
  minimum needed to pass a test).
- Do NOT create a chat-message/conversation-history entity (e.g.
  ChatMessage, chat_messages, ChatLog) even if one of the pages is an AI
  chat/assistant interface. Chat history for that page is handled entirely
  by a separate sidecar service and lives only in the browser session for
  the duration of a conversation — it is never persisted to this API's
  database, so a table for it would be real generated code with zero
  callers, ever. Model entities only for the app's actual business data.
- Java only: whatever mechanism you use to configure the SQLite DataSource
  bean, the environment-variable/property key it reads MUST be literally
  named `DB_PATH` (e.g. `@Value("${DB_PATH:./data.db}")`) — NOT any other
  name (seen vary freely across generations: `app.sqlite.path`,
  `sqlite.db.path`, etc.). This platform's own launcher always sets an
  environment variable literally named `DB_PATH`, pointing at the real db
  file, before starting the process — a differently-named property can
  never receive that override (Spring only matches the exact key), so the
  app would silently create its database at whatever default path you
  picked instead of the one this platform expects it at, and the seeding
  step that runs right after startup would not be able to find it. Set the
  default value (used only if DB_PATH somehow isn't set) to `./data.db`."""

    # Where ApiCrewOrchestrator's own output actually puts schema.sql, per
    # language — Python: bare root-level file; Java: Spring's conventional
    # resource path. Looking this up by bare "schema.sql" for both (as if
    # they were the same) is what let Java's real schema go undetected.
    _BACKEND_SCHEMA_KEY = {"python": "schema.sql", "java": "src/main/resources/schema.sql"}

    def _fix_backend_route_conventions(self, backend_files: dict, entities: list, language: str = "python") -> dict:
        """
        Deterministic safety net for three conventions _BACKEND_SUPPLEMENTAL_
        REQUIREMENTS only asks for as free-text prompt instructions —
        each observed directly, not hypothetical, on real generations:
        (1) api_architect's own base role bakes in "/api/v1/" versioning and
        pluralized/kebab-cased resource names as a design principle, and a
        real generation still applied that despite this caller's override
        instruction (e.g. table "chat_message" -> prefix="/api/v1/chat-
        messages", not the requested /api/chat_message; same for Java's
        @RequestMapping);
        (2) a separate real generation never emitted the requested
        /metadata endpoint at all;
        (3) the aggregate endpoint is generated deterministically here, not
        by the LLM at all anymore (see _deterministic_aggregate_route_python/
        _java) — a real Python generation's own aggregate route was silently
        unreachable (declared after this file's GET /{id} route — Starlette
        matches path templates in registration order) and used a different
        param name (group_by, not the requested groupBy) besides. Verified
        directly that Java does NOT have the same ordering bug (Spring MVC
        prioritizes literal path segments over {variable} patterns
        regardless of declaration order) — the aggregate endpoint is still
        generated deterministically for Java too, for the same param-name-
        drift reason, just without needing any registration-order trick.
        Prompt text alone isn't a strong enough guarantee for any of these
        — same lesson as _heal_seed_sql/_validate_schema_delta earlier this
        session — so fix/replace each deterministically instead of trusting
        the instruction.
        """
        from AgentPlatform.core.codegen_batching import expected_route_path, snake_case

        for entity in entities:
            name = entity.get("name")
            if not name:
                continue
            table = entity.get("table") or snake_case(name)
            columns = {f.get("name") for f in entity.get("fields", []) if f.get("name")}
            route_path = expected_route_path(name, language)
            content = backend_files.get(route_path)

            if language == "java":
                if content:
                    fixed = re.sub(r'@RequestMapping\("[^"]*"\)', f'@RequestMapping("/api/{table}")', content, count=1)
                    if fixed != content:
                        self._p(f"skill:Fixed route mapping for {name} -> /api/{table} (LLM used a different convention)")
                    stripped = self._strip_java_duplicate_aggregate_method(fixed)
                    if stripped != fixed:
                        self._p(f"skill:Removed a duplicate GET .../aggregate method from {name}Controller.java "
                                f"— Spring MVC throws a hard 'Ambiguous mapping' BeanCreationException on this "
                                f"collision with the deterministic {name}AggregateController (FastAPI/Starlette "
                                f"would have just silently shadowed it, so this is Java-specific)")
                        fixed = stripped
                    if fixed != content:
                        backend_files[route_path] = fixed
                agg_path = f"src/main/java/com/api/controller/{name}AggregateController.java"
                if agg_path not in backend_files:
                    backend_files[agg_path] = self._deterministic_aggregate_route_java(name, table, columns)
                    # No registration-order trick needed for Java (see
                    # docstring) and no manual wiring either — Spring's
                    # component scan auto-discovers any @RestController
                    # under com.api, same as every other generated controller.
                continue

            if content:
                fixed = re.sub(r'prefix\s*=\s*"[^"]*"', f'prefix="/api/{table}"', content, count=1)
                if fixed != content:
                    backend_files[route_path] = fixed
                    self._p(f"skill:Fixed route prefix for {name} -> /api/{table} (LLM used a different convention)")

            # Deterministic aggregate endpoint (not LLM-authored — see
            # _BACKEND_SUPPLEMENTAL_REQUIREMENTS) — also sidesteps a real,
            # observed FastAPI route-ordering bug: an LLM-authored aggregate
            # route declared after this same file's GET /{id} route is
            # silently unreachable (Starlette matches "/aggregate" against
            # "/{id}" first), the exact gotcha app_server_template.py's own
            # aggregate route has a comment about. Registering this as its
            # OWN router, wired into main.py BEFORE the entity's own router
            # (see below), gives it matching priority regardless of
            # anything already inside the entity's own file — nothing there
            # needs to be edited or removed for this to work.
            entity_module_stem = snake_case(name)
            agg_module_stem = f"_{entity_module_stem}_aggregate"
            agg_path = f"src/routes/{agg_module_stem}.py"
            if agg_path not in backend_files:
                backend_files[agg_path] = self._deterministic_aggregate_route_python(table, columns)
                self._inject_router_before(backend_files, entity_module_stem, agg_module_stem,
                                            f"{entity_module_stem}_aggregate")

        tables_meta = [
            {
                "name": e.get("table") or snake_case(e.get("name", "")),
                "columns": [{"name": f.get("name"), "type": f.get("type")} for f in e.get("fields", [])],
            }
            for e in entities if e.get("name")
        ]

        if language == "java":
            has_metadata_route = any('"/api/metadata"' in v for v in backend_files.values())
            if not has_metadata_route:
                backend_files["src/main/java/com/api/controller/MetadataController.java"] = (
                    self._deterministic_metadata_route_java(tables_meta)
                )
                self._p("skill:Added deterministic GET /api/metadata endpoint (LLM didn't generate one)")
            return backend_files

        has_metadata_route = any('"/metadata"' in v or "'/metadata'" in v for v in backend_files.values())
        if "src/main.py" in backend_files and not has_metadata_route:
            backend_files["src/routes/_metadata.py"] = (
                "from fastapi import APIRouter\n\n"
                'router = APIRouter(prefix="/api")\n\n'
                f"_METADATA = {json.dumps({'tables': tables_meta}, indent=4)}\n\n\n"
                '@router.get("/metadata")\n'
                "async def get_metadata():\n"
                "    return _METADATA\n"
            )
            backend_files["src/main.py"] = backend_files["src/main.py"].rstrip() + (
                "\n\nfrom src.routes._metadata import router as _metadata_router\n"
                "app.include_router(_metadata_router)\n"
            )
            self._p("skill:Added deterministic GET /api/metadata endpoint (LLM didn't generate one)")

        return backend_files

    def _ensure_java_snake_case_json(self, backend_files: dict) -> dict:
        """
        Deterministic safety net for the same class of gap
        _fix_backend_route_conventions exists for, above: "Every entity's
        field names MUST be snake_case" (_BACKEND_SUPPLEMENTAL_
        REQUIREMENTS) gets satisfied at the SQL/@Column level (verified —
        entities correctly declare @Column(name="client_name")) but that
        instruction was written with Python/Pydantic's automatic case
        alignment in mind and doesn't actually cover Java's JSON output at
        all: ordinary, correct Java code uses camelCase fields/getters
        (clientName), and Jackson's default ObjectMapper serializes JSON
        property names from exactly that — the @Column annotation only
        affects the DB mapping, never JSON. Reproduced directly: every
        generated controller returns the raw entity (Position, not a
        response DTO) straight to Jackson, producing {"clientName": ...}
        instead of the {"client_name": ...} every skill template and
        LLM-authored page on this platform is written to read — silently
        emptying every field/column/chart that reads row.client_name (or
        similar) against a response object that only ever has
        row.clientName.

        One global Spring property fixes every controller's response shape
        at once, with no per-DTO/per-entity annotation needed for the LLM
        to remember — added here rather than relying on the prompt alone,
        same reasoning as every other deterministic fixer in this file
        and in api_orchestrator.py's own _ensure_java_* methods.
        """
        props_path = "src/main/resources/application.properties"
        props = backend_files.get(props_path)
        if props is None:
            return backend_files
        if re.search(r"^spring\.jackson\.property-naming-strategy\s*=", props, re.MULTILINE):
            return backend_files
        backend_files[props_path] = (
            props.rstrip() + "\n\n"
            "# Every generated page expects snake_case JSON field names matching the\n"
            "# SQL columns — Jackson's default naming strategy serializes from the Java\n"
            "# getter/field name instead (camelCase), so this must be forced globally.\n"
            "spring.jackson.property-naming-strategy=SNAKE_CASE\n"
        )
        self._p("skill:Forced spring.jackson.property-naming-strategy=SNAKE_CASE — Java "
                "getters are camelCase by convention, but every generated page expects "
                "snake_case JSON field names matching the SQL columns; without this, "
                "Jackson's default serialization silently breaks every field read on "
                "the frontend")
        return backend_files

    @staticmethod
    def _inject_router_before(backend_files: dict, entity_module_stem: str,
                               new_module_stem: str, new_var_prefix: str):
        """Insert `from src.routes.{new_module_stem} import router as
        {new_var_prefix}_router` + its app.include_router(...) call into
        src/main.py, positioned immediately before the entity's own
        include_router call — so FastAPI/Starlette (which matches routes in
        registration order across ALL routers, not just within one) tries
        the new router's routes first, regardless of what the entity's own
        file does internally. Keyed on the entity's MODULE PATH (guaranteed
        correct — api_services_engineer's own completeness check verifies
        this exact path), not on guessing the router variable's name."""
        main_path = "src/main.py"
        if main_path not in backend_files:
            return
        content = backend_files[main_path]
        insertion = (
            f"from src.routes.{new_module_stem} import router as {new_var_prefix}_router\n"
            f"app.include_router({new_var_prefix}_router)\n\n"
        )
        pattern = re.compile(
            rf"from src\.routes\.{re.escape(entity_module_stem)} import router as (\w+)\s*\n\s*app\.include_router\(\1\)"
        )
        m = pattern.search(content)
        if m:
            content = content[:m.start()] + insertion + content[m.start():]
        else:
            # Entity's own include_router call wasn't found in the expected
            # shape — append at the end rather than silently skipping;
            # correct as long as nothing else registers a colliding /{id}
            # route even later than this.
            content = content.rstrip() + "\n\n" + insertion
        backend_files[main_path] = content

    @staticmethod
    def _deterministic_aggregate_route_python(table: str, columns: set) -> str:
        """A GET /api/{table}/aggregate route, generated directly from the
        known schema instead of by the LLM — see _BACKEND_SUPPLEMENTAL_
        REQUIREMENTS for why (route-ordering bug, param-name drift,
        inconsistent filter support, all observed on real generations).
        column/groupBy/filter column names are validated against this
        entity's OWN known columns before being interpolated into SQL —
        they arrive as untrusted query params."""
        columns_repr = repr(sorted(columns))
        return f'''from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.database import get_db

router = APIRouter(prefix="/api/{table}")

_COLUMNS = {columns_repr}
_METRIC_SQL = {{"sum": "SUM", "avg": "AVG", "min": "MIN", "max": "MAX", "count": "COUNT"}}
_FILTER_OPS = {{"eq": "=", "ne": "!=", "gt": ">", "lt": "<", "gte": ">=", "lte": "<=", "like": "LIKE"}}


def _build_where(filter: str | None, params: dict) -> str:
    if not filter:
        return ""
    clauses = []
    for i, clause in enumerate(filter.split(";")):
        parts = clause.split(":", 2)
        if len(parts) != 3:
            continue
        col, op, val = parts
        if col not in _COLUMNS or op not in _FILTER_OPS:
            continue
        pname = f"f{{i}}"
        clauses.append(f'"{{col}}" {{_FILTER_OPS[op]}} :{{pname}}')
        params[pname] = f"%{{val}}%" if op == "like" else val
    return (" WHERE " + " AND ".join(clauses)) if clauses else ""


@router.get("/aggregate")
async def get_{table}_aggregate(
    metric: str = Query("count"),
    column: str | None = Query(None),
    groupBy: str | None = Query(None),
    filter: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    session: Session = Depends(get_db),
):
    metric_sql = _METRIC_SQL.get(metric.lower())
    if not metric_sql:
        raise HTTPException(400, f"Unknown metric '{{metric}}' — expected one of {{sorted(_METRIC_SQL)}}")
    if metric.lower() != "count":
        if not column or column not in _COLUMNS:
            raise HTTPException(400, f"column is required for metric '{{metric}}' and must be one of {{_COLUMNS}}")
        col_expr = f"{{metric_sql}}(\\"{{column}}\\")"
    else:
        col_expr = "COUNT(*)"
    if groupBy and groupBy not in _COLUMNS:
        raise HTTPException(400, f"groupBy must be one of {{_COLUMNS}}")

    params: dict = {{}}
    where_sql = _build_where(filter, params)

    if groupBy:
        sql = (
            f'SELECT "{{groupBy}}" AS group_value, {{col_expr}} AS value '
            f'FROM "{table}"{{where_sql}} GROUP BY "{{groupBy}}" ORDER BY value DESC LIMIT :_limit'
        )
        params["_limit"] = limit
        rows = session.execute(text(sql), params).fetchall()
        return {{"data": [{{"group": r[0], "value": r[1]}} for r in rows]}}

    sql = f'SELECT {{col_expr}} AS value FROM "{table}"{{where_sql}}'
    row = session.execute(text(sql), params).fetchone()
    return {{"value": (row[0] if row and row[0] is not None else 0)}}
'''

    @staticmethod
    def _strip_java_duplicate_aggregate_method(content: str) -> str:
        """
        Remove any '/aggregate'-mapped method from an LLM-authored entity
        controller. Reproduced directly on a real generation: the LLM wrote
        its own GET .../aggregate method in ExpenseController AS WELL AS
        the deterministic ExpenseAggregateController added separately
        below — Spring MVC treats two beans mapping the exact same
        path+HTTP-method as a hard BeanCreationException ("Ambiguous
        mapping") and refuses to start the whole app, unlike
        FastAPI/Starlette, which just silently shadows the losing route
        (why Python doesn't need this same removal step). Finds the
        @GetMapping/@RequestMapping annotation whose path mentions
        "aggregate", absorbs any Javadoc block immediately above it, then
        walks forward via brace counting to remove the whole method body —
        safe here since these are flat generated methods with no nested
        classes/lambdas deep enough to confuse a simple counter.
        """
        m = re.search(r'@(?:Get|Request)Mapping\((?:value\s*=\s*)?"[^"]*aggregate[^"]*"[^)]*\)', content, re.IGNORECASE)
        if not m:
            return content
        start = m.start()
        # Non-greedy-across-comments: (?:(?!\*/).)* stops at the FIRST */,
        # so this only absorbs the single Javadoc block immediately
        # preceding `start`, not every earlier comment in the file (plain
        # `.*?` with DOTALL would jump back to the file's very first /**
        # and swallow everything in between).
        doc_m = re.search(r'/\*\*(?:(?!\*/).)*\*/\s*$', content[:start], re.DOTALL)
        if doc_m:
            start = doc_m.start()
        brace_open = content.find("{", m.end())
        if brace_open == -1:
            return content
        depth = 0
        end = None
        for i in range(brace_open, len(content)):
            if content[i] == "{":
                depth += 1
            elif content[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end is None:
            return content
        while end < len(content) and content[end] == "\n":
            end += 1
            break
        return content[:start] + content[end:]

    @staticmethod
    def _deterministic_aggregate_route_java(entity_name: str, table: str, columns: set) -> str:
        """Java equivalent of _deterministic_aggregate_route_python — a
        standalone @RestController, auto-discovered by Spring's component
        scan (rooted at com.api, same as every other generated controller)
        with zero manual wiring needed. Confirmed directly (real generated
        app, real HTTP requests) that Spring MVC prioritizes a literal path
        segment like "/aggregate" over a sibling controller's "/{id}"
        pattern regardless of which class declares which or in what order
        — unlike FastAPI/Starlette, so no registration-order trick is
        needed here, just a plain, ordinary controller class. Builds its own
        JdbcTemplate from the injected DataSource rather than injecting
        JdbcTemplate itself — reproduced directly: Spring Boot's own
        JdbcTemplate autoconfiguration didn't fire in a real generated
        project (a custom DataSource bean shape api_data_architect
        sometimes generates, e.g. one class implementing DataSource
        directly rather than via DataSourceBuilder, doesn't reliably
        satisfy JdbcTemplateAutoConfiguration's conditions), which crashed
        the ENTIRE app at startup with UnsatisfiedDependencyException — a
        real DataSource bean is a much safer thing to depend on, since
        every one of these projects' JPA repositories already require one
        to exist. Raw SQL is validated against this entity's own known
        columns before interpolating anything from a query param into it."""
        columns_java = ", ".join(f'"{c}"' for c in sorted(columns))
        return f'''package com.api.controller;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

import javax.sql.DataSource;
import java.util.*;

@RestController
@RequestMapping("/api/{table}")
public class {entity_name}AggregateController {{

    private static final Set<String> COLUMNS = Set.of({columns_java});
    private static final Map<String, String> METRIC_SQL = Map.of(
            "sum", "SUM", "avg", "AVG", "min", "MIN", "max", "MAX", "count", "COUNT");
    private static final Map<String, String> FILTER_OPS = Map.of(
            "eq", "=", "ne", "!=", "gt", ">", "lt", "<", "gte", ">=", "lte", "<=", "like", "LIKE");

    private final JdbcTemplate jdbcTemplate;

    public {entity_name}AggregateController(DataSource dataSource) {{
        this.jdbcTemplate = new JdbcTemplate(dataSource);
    }}

    @GetMapping("/aggregate")
    public Map<String, Object> aggregate(
            @RequestParam(defaultValue = "count") String metric,
            @RequestParam(required = false) String column,
            @RequestParam(required = false) String groupBy,
            @RequestParam(required = false) String filter,
            @RequestParam(defaultValue = "100") int limit
    ) {{
        String metricSql = METRIC_SQL.get(metric.toLowerCase());
        if (metricSql == null) {{
            throw new IllegalArgumentException("Unknown metric '" + metric + "' — expected one of " + METRIC_SQL.keySet());
        }}
        String colExpr;
        if (!metric.equalsIgnoreCase("count")) {{
            if (column == null || !COLUMNS.contains(column)) {{
                throw new IllegalArgumentException("column is required for metric '" + metric + "' and must be one of " + COLUMNS);
            }}
            colExpr = metricSql + "(\\"" + column + "\\")";
        }} else {{
            colExpr = "COUNT(*)";
        }}
        if (groupBy != null && !COLUMNS.contains(groupBy)) {{
            throw new IllegalArgumentException("groupBy must be one of " + COLUMNS);
        }}

        List<Object> params = new ArrayList<>();
        String whereSql = buildWhere(filter, params);

        if (groupBy != null) {{
            String sql = "SELECT \\"" + groupBy + "\\" AS group_value, " + colExpr + " AS value FROM \\"{table}\\""
                    + whereSql + " GROUP BY \\"" + groupBy + "\\" ORDER BY value DESC LIMIT ?";
            params.add(limit);
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(sql, params.toArray());
            List<Map<String, Object>> data = new ArrayList<>();
            for (Map<String, Object> row : rows) {{
                Map<String, Object> item = new LinkedHashMap<>();
                item.put("group", row.get("group_value"));
                item.put("value", row.get("value"));
                data.add(item);
            }}
            return Map.of("data", data);
        }}

        String sql = "SELECT " + colExpr + " AS value FROM \\"{table}\\"" + whereSql;
        Object value = jdbcTemplate.queryForObject(sql, params.toArray(), Object.class);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("value", value != null ? value : 0);
        return result;
    }}

    private String buildWhere(String filter, List<Object> params) {{
        if (filter == null || filter.isEmpty()) return "";
        List<String> clauses = new ArrayList<>();
        for (String clause : filter.split(";")) {{
            String[] parts = clause.split(":", 3);
            if (parts.length != 3) continue;
            String col = parts[0], op = parts[1], val = parts[2];
            if (!COLUMNS.contains(col) || !FILTER_OPS.containsKey(op)) continue;
            clauses.add("\\"" + col + "\\" " + FILTER_OPS.get(op) + " ?");
            params.add(op.equals("like") ? "%" + val + "%" : val);
        }}
        return clauses.isEmpty() ? "" : " WHERE " + String.join(" AND ", clauses);
    }}
}}
'''

    @staticmethod
    def _deterministic_metadata_route_java(tables_meta: list) -> str:
        """Java equivalent of the Python _metadata.py route — a standalone
        @RestController, auto-discovered the same way as every other
        generated controller, no wiring needed. Uses a Java text block for
        the JSON literal rather than building Map objects — the shape is
        already fully known at generation time, so there's nothing to
        compute at request time."""
        metadata_json = json.dumps({"tables": tables_meta}, indent=4)
        # Text blocks forbid an unescaped closing """ sequence appearing
        # inside — never happens for this JSON shape, but escape defensively.
        metadata_json = metadata_json.replace('"""', '\\"\\"\\"')
        return f'''package com.api.controller;

import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class MetadataController {{

    @GetMapping(value = "/api/metadata", produces = MediaType.APPLICATION_JSON_VALUE)
    public String getMetadata() {{
        return """
{metadata_json}
""";
    }}
}}
'''

    def _run_backend_generation(self, user_prompt: str, arch: dict, pages: list, entities: list):
        """
        Real per-entity ORM + named-route backend, generated by running
        WebAPIGenerator's own ApiCrewOrchestrator as a sub-pipeline — the
        same agents (api_architect, api_data_architect, api_services_engineer)
        and the same adaptive-batching/completeness-check/boot-repair
        machinery it already uses for its own standalone APIs, not a
        second, WebUIGenerator-specific reimplementation. Replaces the old
        data_architect call (schema.sql/seed.sql/types.ts only, no real
        backend code — the API itself was a fixed, non-generated template).
        """
        self._p("crew:Stage 2/6 - Generating backend API (models, routes, seed data)...")

        project_name = arch.get("projectName") or "app"
        # Exclude any AI-chat-flavored page from entity inference — its
        # description talks about chatting/messages/conversation, which
        # repeatedly led the backend generator to infer and persist a
        # ChatMessage/chat_messages entity that nothing at runtime ever
        # reads or writes (chat history lives only in the DataChat sidecar's
        # request body / browser session, never in this API's database —
        # see the supplemental requirements' explicit instruction below,
        # kept as defense in depth for any other AI-flavored page wording).
        # Same type set _gen_custom_page uses to route a page to ai_genai —
        # the architect's raw `type` label for a chat page isn't always
        # literally "data-chat" (get_skill()'s own trigger/LLM matching is
        # what actually resolves it to that skill key later).
        _AI_CHAT_PAGE_TYPES = ("ai-chat", "data-chat", "copilot", "assistant")
        page_lines = "\n".join(
            f"- {p.get('name')}: {p.get('description', '')}"
            for p in pages if p.get("type") not in _AI_CHAT_PAGE_TYPES
        )
        backend_prompt = f"""Design and build the backend REST API for this application.

App description: {self._extract_for_stage(user_prompt, 'data_modeling')}

Pages this API must support (infer entities/fields from what each page needs):
{page_lines}

Data tables already identified by the UI architect (treat as a starting hint,
not an exhaustive list — add any table a page above actually needs): {entities}

{self._BACKEND_SUPPLEMENTAL_REQUIREMENTS}"""

        language = self.backend_type
        backend_prefix = "api" if language == "python" else "backend"

        from api_agents.api_orchestrator import ApiCrewOrchestrator
        api_crew = ApiCrewOrchestrator(progress=self.progress)
        result = api_crew.generate(
            backend_prompt,
            api_options={
                "language": language, "auth_type": "none", "rate_limit": 1000,
                "database": "sqlite", "include_docker": False, "include_tests": False,
            },
            project_name_override=project_name,
        )

        # api_crew.generate() flushes its own progress to a throwaway
        # directory under WebAPIGenerator's own generated/web-api/ (needed
        # for its own boot-check-and-repair, which starts a real server from
        # a real directory) — that directory was never registered as a real
        # WebAPIGenerator project (upsert_api_project is server.py's job, not
        # the orchestrator's), so it's pure scratch space once we have its
        # files in hand.
        if api_crew.project_dir and api_crew.project_dir.exists():
            import shutil
            shutil.rmtree(api_crew.project_dir, ignore_errors=True)

        backend_files = result.get("files", {})
        api_architecture = result.get("architecture", {})
        backend_files = self._fix_backend_route_conventions(backend_files, api_architecture.get("entities", []), language)
        if language == "java":
            backend_files = self._ensure_java_snake_case_json(backend_files)
        for path, content in backend_files.items():
            self.files[f"{backend_prefix}/{path}"] = content

        self.artifacts["api_architecture"] = json.dumps(api_architecture, indent=2)
        # Persisted (not just in-memory self.artifacts, which doesn't survive
        # past this one generate() call) — a later refine needs to read this
        # back to merge into it; its presence is also the marker that tells
        # _run_data_modeling this project uses the new named-route pipeline
        # at all, instead of the old data_architect one.
        self.files[f"{backend_prefix}/.architecture.json"] = json.dumps(api_architecture, indent=2)
        schema_sql = backend_files.get(self._BACKEND_SCHEMA_KEY[language], "")
        self.artifacts["schema"] = schema_sql
        if language == "java" and schema_sql:
            # Java's real schema.sql lives at the Spring-conventional
            # src/main/resources/schema.sql (backend/src/main/resources/
            # schema.sql once prefixed) — alias it to backend/schema.sql
            # too, matching the flat path the OLD Java pipeline always used
            # and that _ensure_schema_sql/_run_integration's schema checks
            # already look for. Without this, those checks see no schema at
            # all and _ensure_schema_sql fabricates a second, disconnected
            # one from types.ts — reproduced directly.
            self.files["backend/schema.sql"] = schema_sql
        self.artifacts["seed_preview"] = backend_files.get("seed_data.sql", "")[:3000]

        types_ts = _entities_to_typescript(api_architecture.get("entities", []))
        self.files["src/types.ts"] = types_ts
        self.artifacts["types"] = types_ts

        if arch.get("hasAiFeatures"):
            # Same DataChat sidecar the Java path already uses (real chat/
            # MCP support, unmodified) — bundled under datachat/ since api/
            # here is already the real named-route API, not a slot this
            # sidecar's own server file can take over the way it does for
            # the old pipeline. See _start_api_server's matching branch.
            from agents.skills.registry import SKILL_REGISTRY
            self._bundle_skill_backend(SKILL_REGISTRY["data-chat"]["backend"], self.files, subdir="datachat")

        self._p(f"crew:Backend generated - {len(backend_files)} files, "
                 f"{len(api_architecture.get('entities', []))} entities, "
                 f"{len(api_architecture.get('endpoints', []))} endpoints")

    def _run_backend_refine(self, user_prompt: str, arch: dict):
        """
        Refine a backend that was built by the new named-route pipeline —
        reuses ApiCrewOrchestrator.refine() directly (added/modified/
        affected-entity diffing, preserve-and-extend prompts for existing
        entities) instead of the old schema_v*.sql delta mechanism, which
        has no concept of an ORM model class to diff. Runs the sub-pipeline
        against this project's REAL api/ directory (unlike
        _run_backend_generation's fresh-generation path, which uses a
        throwaway scratch directory) — refine() reads/writes files directly
        via its own project_dir, so there's no separate merge-and-copy step.
        """
        self._p("crew:Stage 2/6 - Refining backend API...")

        language = self.backend_type
        backend_prefix = "api" if language == "python" else "backend"
        existing_architecture = json.loads(self.existing_files[f"{backend_prefix}/.architecture.json"])
        backend_dir = self.project_dir / backend_prefix
        refine_prompt = (
            f"{self._extract_for_stage(user_prompt, 'data_modeling')}\n\n"
            f"{self._BACKEND_SUPPLEMENTAL_REQUIREMENTS}"
        )

        from api_agents.api_orchestrator import ApiCrewOrchestrator
        api_crew = ApiCrewOrchestrator(progress=self.progress)
        result = api_crew.refine(
            project_dir=backend_dir,
            existing_architecture=existing_architecture,
            refine_prompt=refine_prompt,
            api_options={
                "language": language, "auth_type": "none", "rate_limit": 1000,
                "database": "sqlite",
            },
        )

        backend_files = result.get("files", {})
        api_architecture = result.get("architecture", existing_architecture)
        backend_files = self._fix_backend_route_conventions(backend_files, api_architecture.get("entities", []), language)
        for path, content in backend_files.items():
            self.files[f"{backend_prefix}/{path}"] = content

        self.artifacts["api_architecture"] = json.dumps(api_architecture, indent=2)
        self.files[f"{backend_prefix}/.architecture.json"] = json.dumps(api_architecture, indent=2)
        schema_sql = backend_files.get(self._BACKEND_SCHEMA_KEY[language], "")
        self.artifacts["schema"] = schema_sql
        if language == "java" and schema_sql:
            self.files["backend/schema.sql"] = schema_sql

        types_ts = _entities_to_typescript(api_architecture.get("entities", []))
        self.files["src/types.ts"] = types_ts
        self.artifacts["types"] = types_ts

        if arch.get("hasAiFeatures"):
            from agents.skills.registry import SKILL_REGISTRY
            self._bundle_skill_backend(SKILL_REGISTRY["data-chat"]["backend"], self.files, subdir="datachat")
        elif "datachat/app_server.py" in self.existing_files:
            # Was AI-chat, still is (this refine didn't ask to remove it) —
            # carry the sidecar forward unchanged, same as any other
            # untouched existing file.
            for path, content in self.existing_files.items():
                if path.startswith("datachat/"):
                    self.files[path] = content

        added = result.get("addedEntities", [])
        modified = result.get("modifiedEntities", [])
        self._p(f"crew:Backend refined - {len(added)} new entity(ies), {len(modified)} entity(ies) affected")

    # ── Stage 3: Infrastructure ──────────────────────────────────────────────

    def _run_infrastructure(self, user_prompt: str):
        arch = json.loads(self.artifacts.get("architecture", "{}"))
        pages = arch.get("pages", [])
        nav = arch.get("navigation", [])
        title = arch.get("title", "Generated App")

        from agents.prompts import _brand_section

        # In refinement mode, only regenerate App.tsx (new routes/nav); preserve everything else
        if self.is_refinement:
            self._p("crew:Stage 3/6 - Updating App.tsx for new routes (preserving infra)...")
            # Carry over all existing infra files as-is
            infra_files = [
                "index.html", "package.json", "vite.config.ts", "tsconfig.json",
                "tailwind.config.js", "postcss.config.js", "src/main.tsx",
                "src/index.css", "src/utils/formatters.ts",
            ]
            for fpath in infra_files:
                if fpath in self.existing_files:
                    self.files[fpath] = self.existing_files[fpath]
            # Also preserve hooks, utilities, data, and other non-page source files
            for fpath, content in self.existing_files.items():
                if (fpath.startswith("src/hooks/") or fpath.startswith("src/utils/")
                        or fpath.startswith("src/data/") or fpath.startswith("src/lib/")
                        or fpath.startswith("src/context/") or fpath.startswith("src/assets/")):
                    self.files[fpath] = content

            # Only regenerate App.tsx (needs updated lazy imports + routes + nav)
            existing_app_tsx = self.existing_files.get("src/App.tsx", "")
            prompt = f"""Update the App.tsx for this React application to include ALL pages and navigation items.

App: {title}

The COMPLETE list of pages (use React.lazy for each):
{json.dumps(pages, indent=2)}

The COMPLETE navigation:
{json.dumps(nav, indent=2)}

Here is the EXISTING App.tsx - update it to add routes/nav items for new pages while preserving the existing structure, styling, sidebar colors, and component usage:
```tsx
{existing_app_tsx}
```

Return JSON: {{"files": {{"src/App.tsx": "..."}}}}

CRITICAL RULES:
- Keep the EXACT same structure, layout, styling as the existing App.tsx
- ONLY add new React.lazy imports, new Route entries, and new sidebar items for pages that don't exist yet
- Use mobility-global-ds for Header, Sidebar, Footer (import from 'mobility-global-ds')
- BrowserRouter is in src/main.tsx - App.tsx must NOT add another
- Icons: inline SVG elements (16x16, stroke="currentColor")
- Sidebar items must use onClick navigation with useNavigate
- Do NOT change colors, spacing, or layout of existing sidebar/header
- LAYOUT: Sidebar is a FLEX CHILD (auto 240px). NO position:fixed, NO marginLeft on main.
  Use: <div style={{display:'flex',flex:1}}> -> <Sidebar .../> -> <main style={{flex:1}}>
- Do NOT pass style, open, or className props to Sidebar - it only accepts: items, theme, collapsed, footer
"""
            try:
                result = self._call_agent("react_ui", prompt, context=self._build_context(max_chars=6000),
                                           stage="infrastructure", max_tokens=16000)
            except ValueError as e:
                if "Could not extract JSON" not in str(e):
                    raise
                self._p("crew:React UI returned no JSON, retrying with a direct reminder...")
                retry_prompt = prompt + (
                    "\n\nIMPORTANT: Stop calling tools now and respond with ONLY the JSON object: "
                    '{"files": {"src/App.tsx": "<complete file content>"}}'
                )
                result = self._call_agent("react_ui", retry_prompt, context=self._build_context(max_chars=6000),
                                           stage="infrastructure", max_tokens=16000)
            files = result.get("files", {})
            self.files.update(files)
            self.artifacts["app_tsx"] = files.get("src/App.tsx", "")
            self._p(f"crew:Infrastructure complete - App.tsx updated, {len(infra_files)} files preserved")
            return

        self._p("crew:Stage 3/6 - React UI + Services building infrastructure...")

        # For large specs, only pass frontend/infra-relevant sections
        effective_prompt = self._extract_for_stage(user_prompt, "infrastructure")

        prompt = f"""Generate the infrastructure files for this React application:

App: {title}
Description: {effective_prompt}

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
- DO NOT add "mobility-global-ds" to package.json - it is resolved via vite alias, NOT npm
- Sidebar items MUST be a STATIC array defined at the top of App.tsx (not computed, not filtered).
  ALL nav items are always visible. Use onClick with useNavigate for navigation.
- Icons: inline SVG elements (16x16, stroke="currentColor")
- BrowserRouter is in src/main.tsx (with basename) - App.tsx must NOT add another
- Routes: define ALL routes inside a single <Routes> block. EVERY page gets exactly one <Route>.
  Use <Route path="/" element={{<Navigate to="/first-page" />}} /> for the default redirect.

LAYOUT RULES (CRITICAL - do NOT deviate):
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

        try:
            result = self._call_agent("react_ui", prompt, context=self._build_context(max_chars=6000),
                                       stage="infrastructure", max_tokens=16000)
        except ValueError as e:
            if "Could not extract JSON" not in str(e):
                raise
            self._p("crew:React UI returned no JSON, retrying with a direct reminder...")
            retry_prompt = prompt + (
                "\n\nIMPORTANT: Stop calling tools now and respond with ONLY the JSON object: "
                '{"files": {"path/to/file.tsx": "<complete file content>", ...}}'
            )
            result = self._call_agent("react_ui", retry_prompt, context=self._build_context(max_chars=6000),
                                       stage="infrastructure", max_tokens=16000)
        files = result.get("files", {})
        self.files.update(files)
        # Guarantee every planned page has a real route the moment App.tsx
        # exists — using the Stage-1 page list, not real page files (Stage 5
        # hasn't run yet), since that list is the exact contractual source
        # those files will be named from. Don't wait for Stage 6 to find out.
        if "src/App.tsx" in self.files:
            self.files["src/App.tsx"] = self._reconcile_app_routes(
                self.files["src/App.tsx"], [p["name"] for p in pages if p.get("name")]
            )
        self.artifacts["app_tsx"] = self.files.get("src/App.tsx", "")
        self._p(f"crew:Infrastructure complete - {len(files)} files")

    # ── Stage 4: Shared Components ───────────────────────────────────────────

    def _run_components(self, user_prompt: str):
        arch = json.loads(self.artifacts.get("architecture", "{}"))
        shared = arch.get("sharedComponents", [])

        if not shared:
            self._p("crew:Stage 4/6 - No shared components needed, skipping")
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
                self._p(f"crew:Stage 4/6 - All {len(shared)} components preserved from existing project")
                self.artifacts["components"] = json.dumps([f"src/components/{c}.tsx" for c in shared])
                return

        self._p(f"crew:Stage 4/6 - Visual Design generating {len(to_generate)} shared components...")

        from agents.prompts import PASS2_SYSTEM_PROMPT

        # Extract component-relevant context for large specs
        effective_prompt = self._extract_for_stage(user_prompt, "components")

        prompt = f"""Generate these shared components for a React/TypeScript app:

App description: {effective_prompt}

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

        try:
            result = self._call_agent("visual_design", prompt, context=self._build_context(max_chars=8000),
                                       stage="components", max_tokens=32000)
        except ValueError as e:
            # Same failure mode _gen_skill_page already retries on: the model can
            # get stuck re-invoking read_skill_template without ever concluding
            # with the JSON output, exhausting the tool loop's max rounds. One
            # retry with an explicit reminder resolves this reliably; without it,
            # this single bad turn kills the entire generation.
            if "Could not extract JSON" not in str(e):
                raise
            self._p("crew:Visual Design returned no JSON, retrying with a direct reminder...")
            retry_prompt = prompt + (
                "\n\nIMPORTANT: Stop calling tools now and respond with ONLY the JSON object: "
                '{"files": {"src/components/X.tsx": "<complete file content>", ...}}'
            )
            result = self._call_agent("visual_design", retry_prompt, context=self._build_context(max_chars=8000),
                                       stage="components", max_tokens=32000)
        files = result.get("files", {})
        self.files.update(files)
        self.artifacts["components"] = json.dumps(list(files.keys()))
        self._p(f"crew:Components complete - {len(files)} files")

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
        existing_page_names_lower: dict[str, str] = {}  # lowercase -> actual name on disk
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

        # Detect explicit "keep existing pages" intent - if found, preserve ALL existing
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

            # Page is new (not on disk) -> must generate
            if not page_exists:
                to_generate.append(page_info)
                continue

            # If prompt explicitly says keep all existing -> always preserve
            if keep_all_existing:
                to_preserve.append(page_info)
                continue

            # Page is explicitly mentioned with MODIFICATION INTENT -> regenerate.
            # Just naming a page ("after Analytics", "keep Dashboard") does NOT count.
            # Must have an action verb nearby: update/change/modify/redesign/redo/fix/improve/rework/replace
            name_lower = page_name.lower()
            name_spaced = re.sub(r'([a-z])([A-Z])', r'\1 \2', page_name).lower()
            name_variants = list(set([name_lower, name_spaced]))

            _MODIFY_VERBS = (
                r'(?:update|change|modify|redesign|redo|fix|improve|rework|replace|rebuild|'
                r'rewrite|revamp|overhaul|enhance|add\s+to|remove\s+from|refactor)'
            )

            is_mentioned_with_intent = False
            for variant in name_variants:
                escaped = re.escape(variant)
                # "update Dashboard", "modify the analytics page", "redo Global Map"
                pattern_before = _MODIFY_VERBS + r'\s+(?:the\s+)?' + escaped
                # "Dashboard: update the charts", "Analytics - redesign", "Analytics — redesign"
                pattern_after = escaped + r'\s*(?::|—|-)\s*' + _MODIFY_VERBS
                if re.search(pattern_before, prompt_lower) or re.search(pattern_after, prompt_lower):
                    is_mentioned_with_intent = True
                    break

            if is_mentioned_with_intent:
                to_generate.append(page_info)
            else:
                to_preserve.append(page_info)

        return to_generate, to_preserve

    def _run_pages(self, user_prompt: str):
        arch = json.loads(self.artifacts.get("architecture", "{}"))
        pages = arch.get("pages", [])

        if not pages:
            self._p("crew:Stage 5/6 - No pages defined, skipping")
            return

        # ── Selective regeneration: preserve unchanged pages ──────────────────
        to_generate, to_preserve = self._pages_to_regenerate(pages, user_prompt)

        if to_preserve:
            self._p(f"crew:Stage 5/6 - Preserving {len(to_preserve)} unchanged pages, generating {len(to_generate)}...")
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
            self._p(f"crew:Stage 5/6 - Generating {len(pages)} pages in parallel...")

        if not to_generate:
            self._p("crew:All pages preserved - nothing to regenerate")
            return

        # Try skill templates first for matching pages (config-only LLM call = much faster).
        # Fall back to full LLM generation for custom/unmatched pages.
        from agents.skills.registry import get_skill
        import token_tracker
        _parent_run_id = token_tracker.get_run_id()

        def _gen_page(page_info: dict) -> tuple[str, dict]:
            token_tracker.set_run_id(_parent_run_id)
            page_name = page_info["name"]
            page_type = page_info.get("type", "custom")
            page_desc = page_info.get("description", "")

            # Fast path: use pre-built skill template if page matches
            from agents.skills.registry import _get_template_path
            skill = get_skill(page_name, page_desc)
            # get_skill() makes its own mandatory LLM confirmation call — only
            # pay for a second one when page_type actually carries a distinct
            # signal worth trying. "custom" is the default placeholder for
            # every genuinely bespoke page (the common case for unmatched
            # pages), so retrying against it would just be a second guaranteed-
            # miss LLM call on every single one of them for nothing.
            if not skill and page_type and page_type.lower() not in ("custom", page_name.lower()):
                skill = get_skill(page_type, page_desc)
            if skill:
                tpl_path = _get_template_path(skill)
                if tpl_path:
                    skill_tsx = tpl_path.read_text(encoding="utf-8")
                    name, files = self._gen_skill_page(
                        page_name, skill, skill_tsx, user_prompt
                    )
                    # Skip inline validation for skill templates (pre-validated)
                    return name, files

            # Full LLM generation for custom pages
            name, files = self._gen_custom_page(page_name, page_type, page_desc, user_prompt)
            return name, files

        max_workers = min(len(to_generate), 4)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_gen_page, p): p for p in to_generate}
            completed = 0
            for fut in as_completed(futures):
                page_name, page_files = fut.result()
                page_files = self._fix_resize_observer_over_indirection(page_files)
                self.files.update(page_files)
                completed += 1
                self._p(f"crew:Page {completed}/{len(to_generate)}: {page_name} done")

    def _fix_resize_observer_over_indirection(self, files: dict) -> dict:
        """
        A recurring habit in hand-authored D3 components (not from any fixed
        template — reproduced independently across two unrelated
        generations): declare a container variable one hop from a ref
        (`const el = svgRef.current?.parentElement`), then measure width
        inside the resize callback via `el.parentElement?.clientWidth ||
        el.clientWidth` — an extra, unwarranted hop PAST the variable that's
        already the real container, so the chart measures its grandparent's
        width instead of its own (e.g. the full flex row holding 3 donut
        charts, instead of just one donut's own wrapper). The chart still
        renders — no crash, no console error, nothing tsc or QA's console-
        error checks would ever flag — just wildly oversized for its box,
        visually breaking the layout it sits in. Deterministic fix: for
        every container variable declared exactly one hop from a ref this
        way, correct any `X.parentElement?.clientWidth || X.clientWidth`
        measurement of it back down to `X.clientWidth` alone — X is already
        the container, not X's parent.
        """
        fixed = {}
        for path, content in files.items():
            if not path.endswith((".tsx", ".ts")) or not isinstance(content, str):
                fixed[path] = content
                continue
            new_content = content
            for m in re.finditer(r"const\s+(\w+)\s*=\s*\w+\.current\?\.parentElement\b", content):
                var = re.escape(m.group(1))
                new_content = re.sub(
                    rf"{var}\.parentElement\?\.clientWidth\s*\|\|\s*{var}\.clientWidth",
                    f"{m.group(1)}.clientWidth",
                    new_content,
                )
            if new_content != content:
                self._p(f"skill:Fixed over-indirected ResizeObserver container measurement in {path}")
            fixed[path] = new_content
        return fixed

    def _gen_skill_page(self, page_name: str, skill: dict, skill_tsx: str,
                        user_prompt: str) -> tuple[str, dict]:
        """Generate a page using the skill template (config-only LLM call)."""
        from agents.skills.registry import _get_config_path

        skill_key = skill["skill_key"]
        self._p(f"skill: {page_name} -> [{skill_key}] skill matched - filling config...")

        cfg_path = _get_config_path(skill)
        config_template = cfg_path.read_text(encoding="utf-8") if cfg_path else ""
        config_schema = skill.get("config_schema") or {}

        if not USE_SDK_AGENTS:
            agent = get_agent("react_ui")

        # Extra rules for chart/visualization skill configs
        chart_rules = ""
        if skill_key in ("charts", "visualization", "analytics"):
            chart_rules = """
CHART-SPECIFIC RULES:
- LIVE DATA ONLY — NEVER FABRICATE NUMBERS: every chart's data must come from a real table via
  `tableName` (fetched live from /api/{tableName} at runtime), NOT a hardcoded `data: [...]`
  array of numbers you invented. This applies to EVERY chart, including each entry inside a
  `charts: [...]` array in 'multi' mode — each sub-chart object supports its OWN `tableName` and
  is fetched independently, exactly like a top-level single chart. `data: [...]` may ONLY be used
  for genuinely static UI content that was never meant to be database-backed (e.g. a fixed legend).
  If the spec's example numbers (e.g. "70%, 40%, 28%") are illustrative, DERIVE the real equivalent
  from the schema instead of copying those exact numbers in — they are not real data.
- RADAR IS THE ONE EXCEPTION TO "LIVE DATA ONLY": a radar series has no per-row live fetch — its
  `values: number[]` (one number per axis) MUST be a static array you compute yourself. This is
  NOT the "fabricating numbers" this rule warns against, as long as each value is grounded in a
  real column (e.g. normalize carriers.on_time_pct, carriers.reliability_score, etc. to 0-100 per
  carrier per axis) rather than invented from nothing. Leaving `values: []` empty is WRONG — the
  chart renders nothing if you do. Do NOT add `field`/`tableName`/`aggMethod` to a radar series
  object; those belong only to the other chart types.
- GROUPING/AGGREGATION: aggregateSimple in the shared template already groups rows by `labelField`
  and computes `valueField` via `aggMethod` (default 'sum'; also supports 'avg'|'count'|'min'|'max')
  for bar/donut/pie/treemap/waterfall — e.g. tableName:'hourly_metrics', labelField:'hour',
  valueField:'revenue' correctly sums revenue per hour across all rows. Use `aggMethod:'avg'` for
  things like average rating/basket size per group instead of a meaningless sum.
- CROSS-TABLE GROUPING: if the label/group you need (e.g. store "format") lives on a DIFFERENT
  table than the metric (e.g. "revenue" is on hourly_metrics, "format" is on stores), set
  `joinTableName` (the other table), `joinKey` (the shared column, e.g. 'store_code'), and
  `joinFields` (array of column names to pull in, e.g. ['format']) alongside `tableName`. The
  template fetches both tables and joins them client-side before aggregating — do NOT try to
  fabricate the joined result yourself.
- WHEN A CONCEPT HAS NO REAL DATA PATH: if the spec describes a metric/category that has no
  corresponding column anywhere in the schema and can't be derived via grouping/join (e.g. a
  business narrative like "Seasonal Effect" or "Loyalty Signup" with no such column), do NOT
  invent a plausible-looking number for it. Instead simplify that chart to the closest concept
  that IS grounded in real columns (e.g. replace an ungroundable revenue-bridge stage with one
  backed by a real column such as promotions.revenue_attributed, or drop that stage/axis
  entirely) — the chart should end up smaller/simpler but every number in it must be real.
- LINE CHARTS: If the spec mentions multiple dimensions (e.g. "top 5 makes" or "by region"),
  you MUST include one series entry per dimension. Shape data as one row per x-value with a
  field per series. E.g. data=[{quarter:'Q1', SeriesA:100, SeriesB:80, SeriesC:60}] with 3 series entries.
- TABBED LAYOUT: When the spec says "two tabs" (e.g. "Tab 1 - Volume, Tab 2 - Revenue"), use
  layout='tabs' and give each tab a nested charts[] array. Each tab entry = {title:'Tab Label', charts:[...]}.
- GROUPED-BAR: Must have series[] with one entry per bar group, and groupKey for the x-axis category.
- AREA CHARTS: For stacked areas with multiple regions/categories, include ALL as separate series entries.
- NEVER leave a series[] array with only 1 entry when the spec says "multi-line" or "by top N".
"""

        # Extra rules for KPI dashboard configs
        if skill_key == "kpi-dashboard":
            chart_rules += """
KPI DASHBOARD RULES:
- ALWAYS set kpiTableName to a real table from schema.sql that contains KPI/metric rows.
  Look for tables named 'kpis', 'metrics', 'summary', 'overview', or similar.
- Set kpiMapping fields (label, value, change, direction) to REAL column names from that table.
- Set kpiCards to null - the skill template fetches data from the API at runtime.
- NEVER use static kpiCards with hardcoded '$0' or '0%' placeholder values.
- For chart1, chart2, and chart3 (if used): set tableName to a real table, set
  labelField/valueField/xField/series to real column names. Set data: null (fetched at runtime).
- If no suitable KPI table exists in the schema, set kpiTableName to the most relevant table
  and map its columns accordingly.
- THREE CHARTS: if the spec describes three distinct chart visualizations for this page
  (e.g. "two charts side by side, plus a full-width chart below"), you MUST use chart3 for
  the third one — do NOT drop one of the three or repurpose chart2's slot for a different
  chart than what the spec asked for. chart1 and chart2 render side by side; chart3 renders
  full-width below them. Leave chart3 as null only when the spec genuinely asks for two
  charts or fewer.
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
  The API returns raw SQL column names in snake_case - camelCase fields will NOT match.
- badgeColors variants: ONLY default|success|warning|error|info|accent
- NEVER import from '../data' - use tableName: 'table_name_from_schema'. Set dataExport: null.
- The config must be valid TypeScript with zero {{{{PLACEHOLDER}}}} tokens remaining
{chart_rules}"""

        # Config-only calls are usually small, but multi-widget "charts" pages
        # (e.g. 6-7 distinct chart configs in one file) can run well past 4000
        # tokens and get silently truncated — mid-fit truncation is what actually
        # raises "Could not extract JSON" here, not a formatting error. 12000
        # gives real headroom without meaningfully raising cost for the common
        # small-config case.
        config_max_tokens = 12000 if skill_key == "charts" else 4000

        try:
            if USE_SDK_AGENTS:
                result = self._call_agent("react_ui", prompt, stage="pages", max_tokens=config_max_tokens)
            else:
                result = agent.generate(prompt, stage="pages", json_mode=True, max_tokens=config_max_tokens)
        except ValueError as e:
            # The model occasionally responds to the read_skill_template tool result
            # with analysis prose ("Now I have the full template, let me...") and stops
            # without ever emitting the JSON — _extract_json then has no JSON to find.
            # One retry with an explicit, blunt reminder resolves this reliably; without
            # it, this single bad turn kills the whole generation (this page's future
            # propagates the exception up through the page ThreadPoolExecutor).
            if "Could not extract JSON" not in str(e):
                raise
            self._p(f"skill: {page_name} -> model returned no JSON, retrying with a direct reminder...")
            retry_prompt = prompt + (
                "\n\nIMPORTANT: Your previous response did not contain the JSON output. "
                "Do not explain or analyze — respond with ONLY the JSON object now: "
                f'{{"files": {{"src/config/{page_name}.config.ts": "<filled config>"}}}}'
            )
            if USE_SDK_AGENTS:
                result = self._call_agent("react_ui", retry_prompt, stage="pages", max_tokens=config_max_tokens)
            else:
                result = agent.generate(retry_prompt, stage="pages", json_mode=True, max_tokens=config_max_tokens)
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
                self._p(f"skill: {page_name} - line/area chart has <=1 series, regenerating...")
                fix_prompt = prompt + (
                    "\n\nCRITICAL FIX REQUIRED: Your previous output had a line or area chart "
                    "with only 1 series entry. The spec requires MULTIPLE series (one per dimension). "
                    "For example, 'top 5 makes' needs 5 series entries. "
                    "Shape data with one row per x-value and a separate numeric field per series. "
                    "NEVER output a line/area chart with fewer than 2 series entries."
                )
                try:
                    if USE_SDK_AGENTS:
                        result2 = self._call_agent("react_ui", fix_prompt, stage="pages", max_tokens=4000)
                    else:
                        result2 = agent.generate(fix_prompt, stage="pages", json_mode=True, max_tokens=4000)
                    result_files.update(result2.get("files", {}))
                except ValueError as e:
                    # Best-effort auto-fix: if the model returns no JSON on this retry
                    # too, keep the original (single-series) config rather than crash
                    # the whole generation over one cosmetic validation failure.
                    if "Could not extract JSON" not in str(e):
                        raise
                    self._p(f"skill: {page_name} - multi-series fix retry returned no JSON, keeping original config")

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
                self._p(f"skill: {page_name} - KPI config missing kpiTableName or has static zeros, regenerating...")
                fix_prompt = prompt + (
                    "\n\nCRITICAL FIX REQUIRED: Your previous output either used static kpiCards "
                    "with placeholder '$0' / '0%' values, or set kpiTableName to null. "
                    "You MUST set kpiTableName to a real table from schema.sql that contains KPI/metric rows "
                    "(look for 'kpis', 'metrics', 'summary', or pick the most relevant table). "
                    "Set kpiMapping fields to real column names. Set kpiCards: null so "
                    "the template fetches data dynamically from the API."
                )
                try:
                    if USE_SDK_AGENTS:
                        result2 = self._call_agent("react_ui", fix_prompt, stage="pages", max_tokens=4000)
                    else:
                        result2 = agent.generate(fix_prompt, stage="pages", json_mode=True, max_tokens=4000)
                    result_files.update(result2.get("files", {}))
                except ValueError as e:
                    if "Could not extract JSON" not in str(e):
                        raise
                    self._p(f"skill: {page_name} - KPI fix retry returned no JSON, keeping original config")

        # Patch the skill template import path
        page_path = f"src/pages/{page_name}.tsx"
        patched_tsx = re.sub(
            r"from\s+'(\.\./config/)[^']+\.config'",
            f"from '../config/{page_name}.config'",
            skill_tsx,
        )
        result_files[page_path] = patched_tsx

        # Bundle backend if skill has one — EXCEPT "data-chat" on a project
        # whose backend was built by the new named-route pipeline, where
        # it's normally already bundled once per project (not per page) by
        # _run_backend_generation/_run_backend_refine under datachat/, gated
        # on arch["hasAiFeatures"]. That gate is a SEPARATE, independent LLM
        # judgment from THIS page's own skill match (get_skill()'s own
        # trigger/LLM matching) — the two can disagree. Reproduced directly:
        # hasAiFeatures came back false for an app whose "Logistics AI" page
        # still resolved to "data-chat" here, so the dedicated bundle never
        # ran and the page shipped wired to a sidecar that was never
        # generated at all ("AI backend not running"). So checking the
        # unconditional new-pipeline marker (present for EVERY new-pipeline
        # project regardless of hasAiFeatures) is not a reliable proxy for
        # "the datachat bundle actually ran" — check the bundle itself.
        #
        # The OLD (pre-named-route) pipeline has no such dedicated bundle —
        # for THAT pipeline, this per-page call bundling data-chat's backend
        # under "api/" is the actual, only mechanism, and its server file
        # legitimately becomes the project's real API (see the comment above
        # _run_backend_generation's own datachat bundle call).
        backend_meta = skill.get("backend")
        if backend_meta:
            new_pipeline_marker = "api/.architecture.json" if self.backend_type == "python" else "backend/.architecture.json"
            is_new_pipeline = new_pipeline_marker in self.files
            if skill_key == "data-chat" and is_new_pipeline:
                if "datachat/app_server.py" not in self.files:
                    # hasAiFeatures missed it — bundle now, under datachat/
                    # specifically, never the default "api/" subdir (that's
                    # already the real named-route API for this pipeline).
                    self._bundle_skill_backend(backend_meta, result_files, subdir="datachat")
            else:
                self._bundle_skill_backend(backend_meta, result_files)

        self._p(f"skill:Done {page_name} -> [{skill_key}]")
        return page_name, result_files

    def _gen_custom_page(self, page_name: str, page_type: str, page_desc: str,
                         user_prompt: str) -> tuple[str, dict]:
        """Generate a page fully via LLM (no skill template match)."""
        self._p(f"crew:{page_name} -> generating full page with LLM...")

        # Unlike a skill page (fixed template code, only config varies), a
        # custom page is a fresh from-scratch implementation every time it's
        # generated - at the API's default temperature that can meaningfully
        # differ run to run (layout choices, structure) even for the
        # identical prompt. Low-but-not-zero keeps it close to deterministic
        # (see CUSTOM_GEN_TEMPERATURE's own comment for why not exactly 0).
        from agents.sdk_client import CUSTOM_GEN_TEMPERATURE

        # Decide which agent leads based on page type
        has_ai = page_type in ("ai-chat", "data-chat", "copilot", "assistant")
        has_visual = page_type in (
            "charts", "visualization", "analytics", "heatmap",
            "world-map", "usa-map", "country-map", "map", "choropleth", "geo",
        )

        if has_ai:
            agent_type = "ai_genai"
        elif has_visual:
            agent_type = "visual_design"
        else:
            agent_type = "react_ui"

        if not USE_SDK_AGENTS:
            agent = get_agent(agent_type)

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

        figma_mode = bool(self.reference_images)
        if figma_mode:
            design_instruction = (
                "Generate a complete, fully-working React page component.\n"
                "REPLICATE the attached Figma screenshot EXACTLY - same layout, same chart types, same structure."
            )
        else:
            design_instruction = (
                "Generate a complete, fully-working React page component.\n"
                "Design a UNIQUE layout tailored to the specific requirements below - do NOT follow a generic template."
            )

        # For large specs, extract only sections relevant to this specific page
        effective_prompt = self._extract_for_stage(
            user_prompt, "pages", page_name=page_name, page_desc=page_desc
        )

        prompt = f"""{design_instruction}

Page: {page_name}
Type: {page_type}
Description: {page_desc}

App description: {effective_prompt}
{existing_page_section}

Available database schema - use ONLY these exact table/column names. NEVER invent
columns that are not listed here. If a column doesn't exist, do NOT filter by it:
{self.artifacts.get('schema', '')[:3000]}

Shared components available: {self.artifacts.get('components', '[]')}

{contracts}

Return JSON: {{"files": {{"src/pages/{page_name}.tsx": "<complete page code>"}}}}

═══ DATA FETCHING (CRITICAL) ═══
- import {{ useApi, apiAggregate, apiPost, apiPut, apiDelete }} from '../hooks/useApi'
- READ: const {{ data, loading, error, refetch }} = useApi<RowType>('table_name')
  Pass ONLY the SQL table name (e.g. 'documents', 'resources', 'timesheets').
  DO NOT pass a URL path. DO NOT write useApi('/api/...').
  CRITICAL: the generic is the SINGLE-ROW type, NOT an array — `data` is already
  typed as RowType[] by the hook itself. useApi<RowType[]>(...) is WRONG (it makes
  `data` a RowType[][], which then fails to type-check anywhere you use it as a
  flat array) — always useApi<RowType>(...), never useApi<RowType[]>(...).
- The API returns SNAKE_CASE field names matching SQL columns exactly.
  Access: row.doc_type, row.created_date (NOT row.docType, row.createdDate).
- For aggregations: const result = await apiAggregate('table_name', {{ groupBy: 'column', agg: 'count' }})
- CREATE: const result = await apiPost('table_name', {{ col1: value1, col2: value2 }})
  Returns {{ data: insertedRow, id: newRowId }}. Call refetch() after to refresh the list.
- UPDATE: const result = await apiPut('table_name', rowId, {{ col1: newValue }})
  Returns {{ data: updatedRow }}. Call refetch() after to refresh the list.
- DELETE: const result = await apiDelete('table_name', rowId)
  Returns {{ deleted: true, id }}. Call refetch() after to refresh the list.
- For forms/wizards that SAVE data: wrap submission in try/catch, show success toast or error.
  Example:
    const handleSave = async () => {{
      try {{
        await apiPost('expenses', {{ description, amount, date: new Date().toISOString() }})
        refetch()  // refresh the data list
        setShowForm(false)
      }} catch (e: any) {{ setError(e.message) }}
    }}
- NEVER use raw fetch() for database data. NEVER import from '../data'.

═══ UI PATTERNS (use as building blocks, combine creatively) ═══
{pattern_guidance}

═══ COMPONENT IMPORTS (CRITICAL) ═══
- You may ONLY import from these sources:
  • 'mobility-global-ds' - SearchBar, Badge, Card, Header, Sidebar, Footer, etc.
  • '../hooks/useApi' - useApi, apiAggregate, apiPost, apiPut, apiDelete
  • '../components/ExportToolbar' - ExportToolbar (always available)
  • 'd3' - import * as d3 from 'd3'
  • 'react' / 'react-router-dom' / 'lucide-react'
- DO NOT import from '../components/DataTable', '../components/D3BarChart',
  '../components/WorldSalesMap', '../components/UsaMap', '../components/FilterDropdown',
  or ANY other custom component. These DO NOT EXIST. Build everything INLINE in the page file.
  If you need a chart, build it inline with D3. If you need a map, build it inline with D3 + topojson.
  If you need a table, build it inline with JSX. If you need a dropdown, use a <select> element.
- DO NOT create helper components in separate files. Everything goes in one page file.
  You CAN define sub-components (const MyChart = () => ...) at the top of the same file.

═══ D3 CHARTS (CRITICAL - prevent infinite loops) ═══
- ALWAYS use this EXACT ResizeObserver pattern (DO NOT deviate - observe the PARENT, NOT the SVG):
  const ref = useRef<SVGSVGElement>(null)
  const [dims, setDims] = useState({{w:0, h:0}})
  useEffect(() => {{
    const el = ref.current?.parentElement   // ← MUST be parentElement, NEVER ref.current directly
    if (!el) return
    const ro = new ResizeObserver(([e]) => {{
      const {{width}} = e.contentRect
      if (width > 0) setDims({{w: width, h: Math.min(width * 0.6, 300)}})
    }})
    ro.observe(el)
    return () => ro.disconnect()
  }}, [loading])  // ← depend on loading so observer sets up AFTER loading spinner is gone and SVGs mount
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
- Page must be FULLY COMPLETE - no TODOs, no stubs, no placeholders
- Design the layout to match the specific requirements - don't use a generic grid
- Use Tailwind CSS for layout and spacing
- Minimum 200 lines of actual implementation
- Make it visually polished: proper spacing, colors, badges, hover states
- ALL data values from the API may be null - always null-guard: (row.field ?? 0), (row.field ?? '')
"""

        # ── Match Figma screenshots to this page for visual reference ──────────
        page_images: list[str] | None = None
        if self.reference_images:
            page_name_lower = page_name.lower().replace("_", " ").replace("-", " ")
            matched = []
            for img in self.reference_images:
                img_name = img.get("name", "").lower().replace("_", " ").replace("-", " ")
                if (page_name_lower in img_name or img_name in page_name_lower
                        or any(w in img_name for w in page_name_lower.split() if len(w) > 3)):
                    matched.append(img["base64_data"])
            if matched:
                page_images = matched
            else:
                page_images = [img["base64_data"] for img in self.reference_images]

            if page_images:
                prompt = (
                    "═══ FIGMA REPLICATION MODE (THIS OVERRIDES ALL OTHER DESIGN DECISIONS) ═══\n"
                    "You are a PIXEL-PERFECT REPLICATOR. The attached screenshot(s) show the EXACT design from Figma.\n"
                    "Your job is to REPRODUCE what you see - NOT to design, NOT to improve, NOT to reinterpret.\n\n"
                    "MANDATORY REPLICATION RULES:\n"
                    "1. CHART TYPES - look at the screenshot and match EXACTLY:\n"
                    "   • Count bars per x-axis label: ONE bar = simple bar chart, MULTIPLE thin bars = grouped bar chart\n"
                    "   • Ring/hollow circle = donut chart. Full filled circle = pie chart.\n"
                    "   • Horizontal bars = horizontal bar chart. Vertical bars = vertical bar chart.\n"
                    "   • Line with area fill = area chart. Line without fill = line chart.\n"
                    "   • DO NOT change a simple bar chart into a grouped bar chart just because the title mentions categories.\n"
                    "   • DO NOT change chart types based on data model - match the VISUAL, period.\n"
                    "2. LAYOUT - replicate the exact grid structure:\n"
                    "   • Count KPI cards in the top row and match the number exactly.\n"
                    "   • Match column splits (60/40, 50/50, 70/30) as shown.\n"
                    "   • Match the number of rows and sections exactly.\n"
                    "3. COLORS - extract hex colors from the screenshot for charts, backgrounds, cards, text.\n"
                    "4. DATA - use ONLY columns from the schema. If you need a value shown in the screenshot\n"
                    "   that doesn't match a column, use the closest available column. NEVER invent columns.\n"
                    "5. COMPONENTS - match what's visible. If the screenshot shows a simple table, build a simple table.\n"
                    "   Don't add filters, search bars, or features not visible in the screenshot.\n\n"
                    "When in doubt: match the screenshot. The screenshot is ALWAYS right.\n"
                    "═══════════════════════════════════════════════════════════════════════════\n\n"
                    + prompt
                )

        try:
            page_context = self._build_context(max_chars=6000, keys=["architecture", "schema", "types"])
            if USE_SDK_AGENTS:
                result = self._call_agent(agent_type, prompt, context=page_context,
                                          stage="pages", images_b64=page_images, max_tokens=32000,
                                          temperature=CUSTOM_GEN_TEMPERATURE)
            else:
                result = agent.generate(
                    prompt, context=page_context,
                    stage="pages", json_mode=True, max_tokens=32000,
                    images_b64=page_images, temperature=CUSTOM_GEN_TEMPERATURE,
                )
        except RuntimeError as e:
            if "truncated" in str(e).lower() or "two-pass" in str(e).lower():
                self._p(f"crew: {page_name} response truncated - retrying with simplified prompt...")
                simplified_prompt = f"""Generate a React page component.

Page: {page_name}
Description: {page_desc}

Schema (use exact table/column names): {self.artifacts.get('schema', '')[:2000]}

Return JSON: {{"files": {{"src/pages/{page_name}.tsx": "<complete page code>"}}}}

RULES:
- import {{ useApi }} from '../hooks/useApi'
- SYNTAX: const {{ data, loading, error }} = useApi<RowType>('table_name') - pass ONLY the table name.
  The generic is the SINGLE-ROW type, not an array — `data` is already RowType[]. Never useApi<RowType[]>(...).
- API returns SNAKE_CASE field names matching SQL: row.doc_type, row.created_date (NOT camelCase)
- Show loading spinner, handle error state
- Page must be FULLY COMPLETE - no TODOs, no stubs
- Keep the implementation concise but fully functional
- D3 charts: useEffect + useRef + ResizeObserver, import * as d3 from 'd3'
- Use Tailwind CSS for layout
"""
                try:
                    if USE_SDK_AGENTS:
                        result = self._call_agent(agent_type, simplified_prompt, context="",
                                                  stage="pages", images_b64=page_images, max_tokens=32000,
                                                  temperature=CUSTOM_GEN_TEMPERATURE)
                    else:
                        result = agent.generate(
                            simplified_prompt, context="",
                            stage="pages", json_mode=True, max_tokens=32000,
                            images_b64=page_images, temperature=CUSTOM_GEN_TEMPERATURE,
                        )
                except ValueError as retry_e:
                    # The simplified-prompt retry above can ITSELF exhaust the
                    # tool-use loop without producing JSON (the same failure
                    # the sibling `except ValueError` below exists to repair) —
                    # but a ValueError raised from inside this `except
                    # RuntimeError` handler is not caught by that sibling
                    # clause (except clauses only guard the original `try`).
                    # Left unhandled, this escaped every per-page catch,
                    # propagated out of _gen_custom_page, and aborted the
                    # whole _run_pages ThreadPoolExecutor batch instead of
                    # being retried like every other page. Apply the same
                    # "stop calling tools" reminder here before giving up.
                    if "Could not extract JSON" not in str(retry_e):
                        raise
                    self._p(f"crew: {page_name} returned no JSON on simplified retry, retrying with a direct reminder...")
                    final_prompt = simplified_prompt + (
                        f"\n\nIMPORTANT: Stop calling tools now and respond with ONLY the JSON object: "
                        f'{{"files": {{"src/pages/{page_name}.tsx": "<complete file content>"}}}}'
                    )
                    if USE_SDK_AGENTS:
                        result = self._call_agent(agent_type, final_prompt, context="",
                                                  stage="pages", images_b64=page_images, max_tokens=32000,
                                                  temperature=CUSTOM_GEN_TEMPERATURE)
                    else:
                        result = agent.generate(
                            final_prompt, context="",
                            stage="pages", json_mode=True, max_tokens=32000,
                            images_b64=page_images, temperature=CUSTOM_GEN_TEMPERATURE,
                        )
            else:
                raise
        except ValueError as e:
            # Model exhausted the tool-use loop (read_skill_template) without ever
            # concluding with the JSON output — same failure _gen_skill_page and
            # _run_components already retry on. One retry with an explicit "stop
            # calling tools" reminder resolves this reliably.
            if "Could not extract JSON" not in str(e):
                raise
            self._p(f"crew: {page_name} returned no JSON, retrying with a direct reminder...")
            retry_prompt = prompt + (
                f"\n\nIMPORTANT: Stop calling tools now and respond with ONLY the JSON object: "
                f'{{"files": {{"src/pages/{page_name}.tsx": "<complete file content>"}}}}'
            )
            if USE_SDK_AGENTS:
                result = self._call_agent(agent_type, retry_prompt, context=page_context,
                                          stage="pages", images_b64=page_images, max_tokens=32000,
                                          temperature=CUSTOM_GEN_TEMPERATURE)
            else:
                result = agent.generate(
                    retry_prompt, context=page_context,
                    stage="pages", json_mode=True, max_tokens=32000,
                    images_b64=page_images, temperature=CUSTOM_GEN_TEMPERATURE,
                )

        # ── Completeness check: syntactically-valid but stubbed render ──────
        # tsc-based validation (elsewhere in the pipeline) only catches TYPE
        # errors — a component that builds up all its state/data via useApi/
        # useState/useMemo and then ends with a bare `return null` instead of
        # the actual JSX is perfectly valid TypeScript, so nothing else in the
        # pipeline flags it. Observed live: a custom LiveFloor.tsx computed the
        # full ticker/alerts/tile logic and then rendered nothing at all.
        result_files = result.get("files", {})
        page_path = f"src/pages/{page_name}.tsx"
        page_content = result_files.get(page_path, "")

        if _looks_truncated(page_content):
            self._p(f"crew: {page_name} response looks truncated mid-file (unbalanced "
                     f"braces/parens) - retrying with simplified prompt...")
            simplified_prompt = f"""Generate a React page component.

Page: {page_name}
Description: {page_desc}

Schema (use exact table/column names): {self.artifacts.get('schema', '')[:2000]}

Return JSON: {{"files": {{"src/pages/{page_name}.tsx": "<complete page code>"}}}}

RULES:
- import {{ useApi }} from '../hooks/useApi'
- SYNTAX: const {{ data, loading, error }} = useApi<RowType>('table_name') - pass ONLY the table name.
  The generic is the SINGLE-ROW type, not an array — `data` is already RowType[]. Never useApi<RowType[]>(...).
- API returns SNAKE_CASE field names matching SQL: row.doc_type, row.created_date (NOT camelCase)
- Show loading spinner, handle error state
- Page must be FULLY COMPLETE - no TODOs, no stubs
- Keep the implementation concise but fully functional
- D3 charts: useEffect + useRef + ResizeObserver, import * as d3 from 'd3'
- Use Tailwind CSS for layout
"""
            if USE_SDK_AGENTS:
                retry_result = self._call_agent(agent_type, simplified_prompt, context="",
                                                stage="pages", images_b64=page_images, max_tokens=32000,
                                                temperature=CUSTOM_GEN_TEMPERATURE)
            else:
                retry_result = agent.generate(
                    simplified_prompt, context="",
                    stage="pages", json_mode=True, max_tokens=32000,
                    images_b64=page_images, temperature=CUSTOM_GEN_TEMPERATURE,
                )
            retry_files = retry_result.get("files", {})
            retry_content = retry_files.get(page_path, "")
            if retry_content and not _looks_truncated(retry_content):
                result_files = retry_files
                page_content = retry_content
            else:
                self._p(f"crew: WARNING — {page_name} retry also looks truncated; "
                        f"keeping the longer of the two attempts")
                if len(retry_content) > len(page_content):
                    result_files = retry_files
                    page_content = retry_content

        if _looks_like_stubbed_render(page_content):
            self._p(f"crew: {page_name} computed data but rendered nothing (bare 'return null') - retrying...")
            stub_retry_prompt = prompt + (
                "\n\nIMPORTANT: Your previous response computed all the necessary state/data "
                "(useApi/useState/useMemo) but the component's actual render output ended in a "
                "bare `return null` instead of the real JSX described in the page spec above. "
                "Every conditional branch — loading, error, AND the successful/normal case — must "
                "render real JSX built from that computed data. Do NOT stub any branch with "
                "`return null` or a placeholder comment; the page must be visually complete."
            )
            if USE_SDK_AGENTS:
                retry_result = self._call_agent(agent_type, stub_retry_prompt, context=page_context,
                                                stage="pages", images_b64=page_images, max_tokens=32000)
            else:
                retry_result = agent.generate(
                    stub_retry_prompt, context=page_context,
                    stage="pages", json_mode=True, max_tokens=32000,
                    images_b64=page_images,
                )
            retry_files = retry_result.get("files", {})
            if retry_files.get(page_path):
                result_files = retry_files

        return page_name, result_files

    def _bundle_skill_backend(self, backend_meta: dict, result_files: dict, subdir: str = "api"):
        """Bundle backend server files for skills that need them. subdir
        defaults to "api" (the data-chat skill's own convention) but the new
        named-route pipeline's _run_backend_generation passes "datachat"
        instead, since api/ there is already the real named-route API."""
        from pathlib import Path
        from dotenv import dotenv_values

        # Moved out of this package to AgentPlatform/catalog/ — see
        # webui_integration_engineer's own docstring for why it's not still
        # named "services_engineer".
        templates_dir = Path(__file__).resolve().parent.parent.parent / "AgentPlatform" / "catalog" / "webui_integration_engineer" / "templates"
        parent_env_path = Path(__file__).parent.parent.parent / ".env"

        server_tpl = templates_dir / backend_meta["server_template"]
        env_tpl = templates_dir / backend_meta["env_template"]

        if server_tpl.exists():
            result_files[f"{subdir}/app_server.py"] = server_tpl.read_text(encoding="utf-8")

        mcp_template = backend_meta.get("mcp_template")
        if mcp_template:
            mcp_tpl = templates_dir / mcp_template
            if mcp_tpl.exists():
                result_files[f"{subdir}/mcp_server.py"] = mcp_tpl.read_text(encoding="utf-8")

        if env_tpl.exists():
            env_content = env_tpl.read_text(encoding="utf-8")
            parent_env = dotenv_values(parent_env_path) if parent_env_path.exists() else {}
            env_content = env_content.replace("{{LITELLM_API_BASE}}", parent_env.get("LITELLM_API_BASE", ""))
            env_content = env_content.replace("{{LITELLM_API_KEY}}", parent_env.get("LITELLM_API_KEY", ""))
            env_content = env_content.replace("{{LITELLM_SSL_CERT}}", parent_env.get("LITELLM_SSL_CERT", ""))
            env_content = env_content.replace("{{LITELLM_MODEL}}", parent_env.get("LITELLM_SONNET_46_MODEL", "claude-sonnet-4-6"))
            result_files[f"{subdir}/.env"] = env_content

        reqs = backend_meta.get("requirements", [])
        if reqs:
            result_files[f"{subdir}/requirements.txt"] = "\n".join(reqs) + "\n"

    @staticmethod
    def _reconcile_app_routes(app_tsx: str, expected_page_names: list[str]) -> str:
        """
        Deterministically guarantee every name in `expected_page_names` has a
        real `lazy(() => import('./pages/Name'))` + matching `<Route>` in
        app_tsx — never trust free-form LLM output for this alone, since it's
        pure plumbing fully derivable from data the pipeline already has as
        ground truth (no creative content involved). Reproduced directly: a
        fresh generation's own App.tsx stubbed two of five planned pages as
        inline `function X() { return <div>X</div> }` placeholders instead of
        real lazy imports, leaving real, fully-working page files unreachable
        with no error anywhere — the LLM had the exact page list and still
        got it wrong.

        Called from two points with two different notions of "expected":
        right after App.tsx is first generated (_run_infrastructure), using
        the Stage-1 page list — the real page files don't exist on disk yet
        at that point, but that list is the exact, contractual source they'll
        be named from (_normalize_component_name/_normalize_architecture_pages
        already cleaned it), so there's nothing to gain by waiting. And again
        at Stage 6 (_run_integration's Fix 9), using the real generated files,
        as a defense-in-depth backstop against anything that still drifted.
        """
        if not app_tsx:
            return app_tsx

        lazy_imports = re.findall(r"import\(['\"]\.\/pages\/(\w+)['\"]\)", app_tsx)
        lazy_imports_lower = [p.lower() for p in lazy_imports]

        missing_pages = [
            name for name in expected_page_names
            if name not in lazy_imports and name.lower() not in lazy_imports_lower
        ]
        for page_ref in missing_pages:
            print(f"  [integration] WARNING: Page '{page_ref}' has no route in App.tsx", flush=True)

        for page_name in missing_pages:
            lazy_line = f"const {page_name} = lazy(() => import('./pages/{page_name}'))\n"
            last_lazy = list(re.finditer(r"^const \w+ = lazy\(.+\)$", app_tsx, re.MULTILINE))
            if last_lazy:
                insert_pos = last_lazy[-1].end() + 1
                app_tsx = app_tsx[:insert_pos] + lazy_line + app_tsx[insert_pos:]
            else:
                import_end = 0
                for m in re.finditer(r"^import\s+.+$", app_tsx, re.MULTILINE):
                    import_end = m.end() + 1
                app_tsx = app_tsx[:import_end] + "\n" + lazy_line + app_tsx[import_end:]

            path_name = re.sub(r'([a-z])([A-Z])', r'\1-\2', page_name).lower()

            # A stub already occupying this exact route path (an LLM-invented
            # placeholder name from before the real page existed) must be
            # REPLACED in place, not left next to a second, newly-appended
            # <Route> for the same path — two <Route path="/x"> entries for
            # the same path is undefined/first-wins in React Router, which
            # would keep the dead stub winning even after this "fix".
            stub_route_re = re.compile(
                r'<Route\s+path="/' + re.escape(path_name) + r'"\s+element=\{<(\w+)\s*/>\}\s*/>'
            )
            stub_match = stub_route_re.search(app_tsx)
            if stub_match and stub_match.group(1) != page_name:
                app_tsx = stub_route_re.sub(
                    f'<Route path="/{path_name}" element={{<{page_name} />}} />',
                    app_tsx,
                )
                print(f"  [integration] Replaced stub '{stub_match.group(1)}' at /{path_name} with real page '{page_name}' in App.tsx", flush=True)
            else:
                route_line = f'            <Route path="/{path_name}" element={{<{page_name} />}} />\n'
                routes_end = app_tsx.rfind("</Routes>")
                if routes_end > 0:
                    app_tsx = app_tsx[:routes_end] + route_line + app_tsx[routes_end:]
                print(f"  [integration] Injected missing route for '{page_name}' in App.tsx", flush=True)

        # Also fix a lazy import pointing at a page name that doesn't exist
        # at all (typo/case mismatch) by snapping it to the closest real name.
        expected_lower = {n.lower(): n for n in expected_page_names}
        for page_ref in lazy_imports:
            if page_ref in expected_page_names:
                continue
            real = expected_lower.get(page_ref.lower())
            if real:
                app_tsx = app_tsx.replace(f"./pages/{page_ref}", f"./pages/{real}")
                print(f"  [integration] Fixed App.tsx: './pages/{page_ref}' -> './pages/{real}'", flush=True)

        return app_tsx

    # ── Stage 6: Integration ─────────────────────────────────────────────────

    def _run_integration(self, user_prompt: str):
        self._p("crew:Stage 6/6 - Services Engineer verifying API integration...")

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
                # INTEGER/REAL/TEXT/NUMERIC covers the old data_architect-
                # authored schema.sql; VARCHAR/BOOLEAN/DATETIME/FLOAT/DOUBLE/
                # CHAR/DECIMAL/DATE/TIME/BLOB cover SQLAlchemy's own DDL
                # output (the new named-route pipeline's schema.sql) — its
                # column types are real SQLite type affinities, just
                # different keywords than the old pipeline ever produced.
                cols = re.findall(
                    r"^\s*(\w+)\s+(?:INTEGER|REAL|TEXT|NUMERIC|VARCHAR|BOOLEAN|DATETIME|FLOAT|DOUBLE|CHAR|DECIMAL|DATE|TIME|BLOB)",
                    body, re.MULTILINE | re.IGNORECASE,
                )
                table_columns[table] = cols
                table_columns[table.lower()] = cols

        fixes_applied = 0

        for file_path, content in list(self.files.items()):
            if not file_path.endswith((".tsx", ".ts")) or not content:
                continue
            original = content

            # ── Fix 0: useApi called with URL path instead of table name ────
            # e.g. useApi('/api/data/documents') -> useApi('documents')
            # (old generic-template contract) or useApi('/api/documents') ->
            # useApi('documents') (new named-route contract).
            url_pattern = re.findall(r"useApi[<\w>\[\]]*\s*\(\s*['\"]\/api\/(?:data\/)?(\w+)['\"]", content)
            for table_ref in url_pattern:
                content = re.sub(
                    r"(useApi[<\w>\[\]]*\s*\(\s*)['\"]\/api\/(?:data\/)?" + re.escape(table_ref) + r"['\"]",
                    r"\g<1>'" + table_ref + "'",
                    content,
                )
                print(f"  [integration] Fixed useApi('/api/{table_ref}') -> useApi('{table_ref}') in {file_path}", flush=True)

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
                    print(f"  [integration] Fixed useApi('/{table_ref}') -> useApi('{actual_name}') in {file_path}", flush=True)

            # ── Fix 0b: useApi<RowType[]>(...) double-array generic mistake ──
            # useApi<T>'s `data` is already T[]; passing the array type as T
            # makes `data` a T[][], breaking every downstream use of it as a
            # flat array. "any[]" is deliberately excluded — that's still the
            # documented pattern in some older prompts and doesn't itself
            # produce a type error, only named-type usages do.
            fixed_generic = re.sub(r"useApi<(\w+)\[\]>", r"useApi<\1>", content)
            if fixed_generic != content:
                content = fixed_generic
                print(f"  [integration] Fixed useApi<T[]> -> useApi<T> double-array generic in {file_path}", flush=True)

            # ── Fix 1: Wrong table names in useApi calls ─────────────────────
            api_calls = re.findall(r"useApi[<\w>]*\s*\(\s*['\"](\w+)['\"]", content)
            for table_ref in api_calls:
                if table_ref in table_names:
                    continue
                if table_ref.lower() in table_names_lower:
                    correct = table_names_lower[table_ref.lower()]
                    content = content.replace(f"'{table_ref}'", f"'{correct}'")
                    content = content.replace(f'"{table_ref}"', f'"{correct}"')
                    print(f"  [integration] Fixed useApi('{table_ref}') -> '{correct}' in {file_path}", flush=True)
                else:
                    best = self._fuzzy_match_table(table_ref, table_names)
                    if best:
                        content = content.replace(f"'{table_ref}'", f"'{best}'")
                        content = content.replace(f'"{table_ref}"', f'"{best}"')
                        print(f"  [integration] Fixed useApi('{table_ref}') -> '{best}' (fuzzy) in {file_path}", flush=True)

            # ── Fix 2: Wrong table names in apiAggregate calls ────────────────
            agg_calls = re.findall(r"apiAggregate\s*\(\s*['\"](\w+)['\"]", content)
            for table_ref in agg_calls:
                if table_ref in table_names:
                    continue
                if table_ref.lower() in table_names_lower:
                    correct = table_names_lower[table_ref.lower()]
                    content = content.replace(f"'{table_ref}'", f"'{correct}'")
                    content = content.replace(f'"{table_ref}"', f'"{correct}"')

            # ── Fix 3: Wrong table names in fetch() calls to /api/... ────────
            # Matches both the old /api/data/{table} contract and the new
            # named-route /api/{table} one — deliberately excludes the
            # reserved /api/metadata path, which isn't a table reference.
            fetch_tables = re.findall(r"/api/(?:data/)?(\w+)", content)
            for table_ref in fetch_tables:
                if table_ref in table_names or table_ref == "metadata":
                    continue
                if table_ref.lower() in table_names_lower:
                    correct = table_names_lower[table_ref.lower()]
                    content = re.sub(
                        r"/api/(data/)?" + re.escape(table_ref) + r"\b",
                        lambda m: f"/api/{m.group(1) or ''}{correct}",
                        content,
                    )

            # ── Fix 4: Ensure useApi import exists when used ─────────────────
            has_useapi_import = "from '../hooks/useApi'" in content or "from '../../hooks/useApi'" in content
            if "useApi" in content and not has_useapi_import:
                if "src/pages/" in file_path or "src/components/" in file_path:
                    depth = "../" if "src/pages/" in file_path else "../../"
                    content = f"import {{ useApi, apiAggregate }} from '{depth}hooks/useApi'\n" + content
                    print(f"  [integration] Added useApi import to {file_path}", flush=True)

            # ── Fix 5: Config files - validate tableName field ────────────────
            if file_path.endswith(".config.ts"):
                table_in_config = re.search(r"tableName:\s*['\"](\w+)['\"]", content)
                if table_in_config:
                    tref = table_in_config.group(1)
                    if tref not in table_names:
                        if tref.lower() in table_names_lower:
                            correct = table_names_lower[tref.lower()]
                            content = content.replace(f"'{tref}'", f"'{correct}'")
                            content = content.replace(f'"{tref}"', f'"{correct}"')
                            print(f"  [integration] Fixed tableName '{tref}' -> '{correct}' in {file_path}", flush=True)
                        else:
                            best = self._fuzzy_match_table(tref, table_names)
                            if best:
                                content = content.replace(f"'{tref}'", f"'{best}'")
                                content = content.replace(f'"{tref}"', f'"{best}"')
                                print(f"  [integration] Fixed tableName '{tref}' -> '{best}' (fuzzy) in {file_path}", flush=True)

            # ── Fix 6: Config files - fix camelCase field refs to snake_case ──
            if file_path.endswith(".config.ts"):
                # Build a lookup: camelCase -> snake_case for all known columns
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
                        print(f"  [integration] Fixed field '{camel}' -> '{snake}' in {file_path}", flush=True)

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
                        # Check if the component is defined inline in this file
                        inline_def = re.search(
                            r"(?:function|const)\s+" + re.escape(comp_name) + r"\b",
                            content,
                        )
                        if inline_def:
                            # Component is defined locally - just remove the import
                            content = re.sub(
                                r"^import\s+.*?from\s+['\"]\.\.\/components\/" + re.escape(comp_name) + r"['\"].*\n?",
                                "", content, flags=re.MULTILINE,
                            )
                            print(f"  [integration] Removed import for inline component '{comp_name}' from {file_path}", flush=True)
                        else:
                            # Component file doesn't exist - create a stub file so the import resolves
                            stub_path = f"src/components/{comp_name}.tsx"
                            stub_content = (
                                "import React from 'react'\n\n"
                                f"export default function {comp_name}(props: any) {{\n"
                                f"  return (\n"
                                f"    <div className=\"w-full h-64 bg-slate-50 border border-dashed border-slate-300 rounded-lg flex items-center justify-center\">\n"
                                f"      <p className=\"text-slate-500 text-sm\">{comp_name} - component placeholder</p>\n"
                                f"    </div>\n"
                                f"  )\n"
                                f"}}\n"
                            )
                            self.files[stub_path] = stub_content
                            allowed_components.add(comp_name)
                            print(f"  [integration] Created stub for missing component '{comp_name}' referenced in {file_path}", flush=True)

            # ── Fix 8: Prevent D3 ResizeObserver infinite loops ────────────────
            if "ResizeObserver" in content and "setDims" not in content:
                # Check for the dangerous pattern: drawing inside ResizeObserver callback
                if re.search(r"ResizeObserver\(\s*\(\[?.*?\]?\)\s*=>\s*\{[^}]*selectAll", content, re.DOTALL):
                    print(f"  [integration] WARNING: {file_path} has D3 draw inside ResizeObserver - may cause infinite loop", flush=True)

            # ── Fix 8b: Undefined variable in ResizeObserver measure functions ────
            # Common LLM error: uses 'svgEl' or 'containerEl' in measure() but the
            # actual variable in scope is 'el' (from svgRef.current?.parentElement)
            if "ResizeObserver" in content:
                # Pattern: `const el = ...parentElement` then measure uses `svgEl` or other undefined var
                measure_blocks = re.finditer(
                    r"const\s+(\w+)\s*=\s*(?:svgRef|wrapRef|chartRef|containerRef)\.current(?:\?\.parentElement)?"
                    r".*?const\s+measure\s*=\s*\(\)\s*=>\s*\{([^}]+)\}",
                    content, re.DOTALL,
                )
                for mb in measure_blocks:
                    var_name = mb.group(1)  # e.g. 'el'
                    measure_body = mb.group(2)
                    # Find references to undefined *El variables in the measure body
                    undefined_refs = re.findall(r"\b(\w+El)\b", measure_body)
                    for ref in undefined_refs:
                        if ref != var_name and f"const {ref}" not in content[:mb.start()] and f"let {ref}" not in content[:mb.start()]:
                            content = content.replace(measure_body, measure_body.replace(ref, var_name))
                            print(f"  [integration] Fixed undefined '{ref}' -> '{var_name}' in ResizeObserver measure ({file_path})", flush=True)
                            break

            if content != original:
                self.files[file_path] = content
                fixes_applied += 1

        # ── Fix 9: Validate App.tsx lazy imports match actual pages ────────
        # Uses the real generated page files as ground truth — this is the
        # LAST line of defense, after _reconcile_app_routes has already run
        # once right after App.tsx was first generated (see
        # _run_infrastructure), using the Stage-1 page list as ground truth
        # instead (the real files don't exist yet at that point). Running it
        # again here, against reality, catches anything that slipped through
        # or changed between then and now.
        app_tsx = self.files.get("src/App.tsx", "")
        if app_tsx:
            actual_pages = {
                fpath.replace("src/pages/", "").replace(".tsx", "")
                for fpath in self.files
                if fpath.startswith("src/pages/") and fpath.endswith(".tsx")
            }
            app_tsx = self._reconcile_app_routes(app_tsx, sorted(actual_pages))
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

        # ── Fix 11: seed.sql null values for NOT NULL columns ─────────────
        seed_sql = self.files.get("seed.sql", "")
        if seed_sql and schema:
            # Find NOT NULL columns per table
            not_null_cols: dict[str, set[str]] = {}
            for table in table_names:
                col_pattern = re.compile(
                    r"CREATE TABLE\s+(?:IF NOT EXISTS\s+)?" + re.escape(table) + r"\s*\(([^;]+)\)",
                    re.IGNORECASE | re.DOTALL,
                )
                m = col_pattern.search(schema)
                if m:
                    body = m.group(1)
                    nn_cols = re.findall(r"^\s*(\w+)\s+\w+.*?NOT\s+NULL", body, re.MULTILINE | re.IGNORECASE)
                    if nn_cols:
                        not_null_cols[table] = set(nn_cols)

            # Replace literal null with empty string for NOT NULL columns
            if ",null," in seed_sql.lower() or ",null)" in seed_sql.lower() or "(null," in seed_sql.lower():
                original_seed = seed_sql
                seed_sql = re.sub(r",null([,)])", r",''\\1", seed_sql, flags=re.IGNORECASE)
                seed_sql = re.sub(r"\(null,", "('',", seed_sql, flags=re.IGNORECASE)
                if seed_sql != original_seed:
                    self.files["seed.sql"] = seed_sql
                    fixes_applied += 1
                    print("  [integration] Fixed null values in seed.sql for NOT NULL columns", flush=True)

        # ── Fix 12: Custom pages' row interface fields vs the real schema ──
        # A custom (non-skill-template) page often declares its own
        # `interface FooRow { field: type; ... }` right next to
        # `useApi<FooRow>('table')` — even though the generation prompt
        # already includes the literal real column list and explicitly
        # says "NEVER invent columns," the LLM can and does invent
        # differently-named fields anyway. Reproduced directly: a page
        # declared meeting_date/start_time/duration_minutes while the real
        # columns are date/time_slot/duration_min — every reference read
        # undefined, silently filtering all real rows out with no error
        # anywhere, since nothing else in this pipeline checks a custom
        # page's own interface against reality (the other Fix N's above
        # only check the literal table-name argument, never a page's own
        # field names). Detection is deterministic and free; repair
        # (renaming every usage consistently through a multi-hundred-line
        # file) needs an LLM call, only triggered when a real mismatch is
        # confirmed — never a fuzzy guess, since field names like
        # "meeting_date" vs "date" aren't lexically similar enough for
        # that to work reliably.
        for file_path, content in list(self.files.items()):
            if not file_path.startswith("src/pages/") or not file_path.endswith(".tsx") or not content:
                continue
            for api_m in re.finditer(r"useApi<(\w+)>\s*\(\s*['\"](\w+)['\"]", content):
                row_type, table = api_m.group(1), api_m.group(2)
                real_cols = table_columns.get(table) or table_columns.get(table.lower())
                if not real_cols:
                    continue
                real_cols_lower = {c.lower() for c in real_cols}
                iface_m = re.search(
                    r"interface\s+" + re.escape(row_type) + r"\s*\{([^}]*)\}", content, re.DOTALL,
                )
                if not iface_m:
                    continue
                field_names = re.findall(r"^\s*(\w+)\s*\??\s*:", iface_m.group(1), re.MULTILINE)
                bad_fields = [f for f in field_names if f.lower() not in real_cols_lower]
                if not bad_fields:
                    continue
                self._p(f"skill:{file_path.split('/')[-1]} references field(s) not in the real "
                        f"'{table}' schema: {', '.join(bad_fields)} — repairing...")
                diagnosis = (
                    f"This page's `interface {row_type}` declares field(s) that do NOT exist in "
                    f"the real '{table}' table: {', '.join(bad_fields)}.\n"
                    f"The real columns are: {', '.join(real_cols)}.\n"
                    f"Fix EVERY reference to the wrong field name(s) throughout this file — the "
                    f"interface declaration, all property access, all JSX — so it uses the real "
                    f"column names instead. Do not rename or change anything else."
                )
                try:
                    result = self._call_agent(
                        "react_ui",
                        f"{diagnosis}\n\nCurrent file content:\n```tsx\n{content}\n```\n\n"
                        f'Return JSON: {{"files": {{"{file_path}": "<complete corrected file content>"}}}}',
                        context=self._build_context(max_chars=2000),
                        stage="integration", max_tokens=16000,
                    )
                    new_content = result.get("files", {}).get(file_path)
                    if new_content and len(new_content) >= len(content) * 0.5:
                        self.files[file_path] = new_content
                        content = new_content
                        fixes_applied += 1
                        self._p(f"skill:Fixed field mismatch(es) in {file_path.split('/')[-1]}")
                    else:
                        print(f"  [integration] Rejected field-mismatch repair for {file_path} "
                              f"— looks incomplete, keeping original", flush=True)
                except Exception as ex:
                    print(f"  [integration] Field-mismatch repair failed for {file_path}: {ex}", flush=True)

        if fixes_applied:
            self._p(f"crew:Integration - fixed {fixes_applied} file(s)")
        else:
            self._p("crew:Integration check passed - all API references valid")

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
  - ROW ACTIONS: Add Edit/Delete buttons in the last column of each row.
    Edit opens a modal/inline form pre-filled with row data -> apiPut on save.
    Delete shows confirm dialog -> apiDelete on confirm -> refetch().
  - ADD NEW: "Add" button above the table opens a blank form -> apiPost on save -> refetch().
""")

        # Chart/visualization pattern
        if any(w in desc_lower for w in ["chart", "donut", "bar", "line", "visualization", "analytics", "stacked", "scatter", "heatmap"]):
            patterns.append("""
▸ D3 CHARTS (follow this exact pattern to avoid infinite loops):
  const chartRef = useRef<SVGSVGElement>(null)
  const [chartDims, setChartDims] = useState({w:0, h:0})
  // Step 1: Observe size (depend on loading so it re-runs after SVGs mount)
  useEffect(() => {
    const el = chartRef.current?.parentElement
    if (!el) return
    const ro = new ResizeObserver(([e]) => {
      const {width} = e.contentRect
      if (width > 0) setChartDims({w: width, h: Math.min(width*0.6, 280)})
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [loading])
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
  - Use compact formatting: $1.2M, 85%, 142 - no long decimals
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
  - Final step: review/summary showing all collected data, THEN SAVE:
    const handleSubmit = async () => {
      setSaving(true)
      try {
        await apiPost('table_name', formData)
        refetch() // refresh list data
        navigate('/success-page') // or close modal
      } catch (e: any) { setError(e.message) }
      finally { setSaving(false) }
    }
""")

        # Save/CRUD form pattern (any page with add/edit/delete functionality)
        if any(w in desc_lower for w in ["add", "edit", "save", "create", "new", "submit", "manage", "crud", "settings", "profile"]):
            patterns.append("""
▸ FORMS THAT SAVE DATA (CRITICAL - all forms must persist to backend):
  - import { apiPost, apiPut, apiDelete } from '../hooks/useApi'
  - CREATE: const handleCreate = async (formData) => {
      try { await apiPost('table_name', formData); refetch() } catch(e) { setError(e.message) }
    }
  - UPDATE: const handleUpdate = async (id, formData) => {
      try { await apiPut('table_name', id, formData); refetch() } catch(e) { setError(e.message) }
    }
  - DELETE: const handleDelete = async (id) => {
      if (!confirm('Delete this item?')) return
      try { await apiDelete('table_name', id); refetch() } catch(e) { setError(e.message) }
    }
  - Use refetch() from useApi to refresh the data list after any mutation.
  - Show loading state on submit buttons: disabled={saving} with spinner
  - Show success feedback: toast/banner "Saved successfully" that auto-dismisses
  - Show error feedback: red banner with error message from catch block
  - For inline editing: track editingId state, show input fields for that row, save on blur/Enter
  - For modal forms: useState<boolean>(false) for showModal, render form inside modal
  - NEVER leave forms as no-ops or local-state-only. ALL forms MUST call apiPost/apiPut/apiDelete.
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
