"""
The single canonical ClaudeAgentOptions factory for the SDK-native web-app builder.

Every consumer (Phase 1 tool tests, the Phase 3 builder, the Phase 4 AgentSession)
imports build_options() from here so there is exactly ONE options construction — the
adversarial review's top finding was three dimensions each building a different,
contradictory options object. All fields snake_case; single MCP key "turboui";
read_skill_template retired; `tools` explicit (never None).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from claude_agent_sdk import (
    ClaudeAgentOptions,
    HookMatcher,
    PermissionResultAllow,
    PermissionResultDeny,
)

from . import sdk_env
from . import projects as project_store
from .turboui_mcp import ProjectContext, build_turboui_server, TURBOUI_TOOL_NAMES
from .dataset_mcp import build_dataset_server, DATASET_TOOL_NAMES
from .agent_hooks import make_guard_write_hook, make_normalize_files_hook
from .agent_defs import build_agents

# The turbo-uigen plugin (subagents + skills) lands in Phase 2. Wire it only when present
# so the factory is usable during Phase 1 bring-up.
AGENT_SDK_DIR = Path(__file__).parent / "agent_sdk"
# Vendored third-party skill plugins (kept out of agent_sdk/, which build_plugin.build() wipes).
# diagram-design (cathrynlavery, MIT): 38 editorial diagram types as self-contained HTML/SVG.
DIAGRAM_DESIGN_DIR = Path(__file__).parent / "vendor_plugins" / "diagram-design"

BUILDER_BUDGET_USD = float(os.environ.get("TURBOUI_BUILDER_BUDGET_USD", "8"))

# Autonomous mode: auto-allow builtins (Bash OMITTED → routes to the bash gate).
_BUILTIN_ALLOWED = ["Read", "Write", "Edit", "MultiEdit", "Glob", "Grep", "TodoWrite", "Task"]
# HITL mode: only read-only tools are auto-allowed; edits/bash/side-effecting tools fall
# through to can_use_tool so the conversational UI can surface a permission prompt.
_BUILTIN_ALLOWED_HITL = ["Read", "Glob", "Grep"]
_TURBOUI_READONLY = [
    "mcp__turboui__validate_sql", "mcp__turboui__validate_seed_data",
    "mcp__turboui__check_types_match", "mcp__turboui__validate_react_component",
    "mcp__turboui__validate_architecture", "mcp__turboui__check_page_types",
    "mcp__turboui__validate_data_layer", "mcp__turboui__tsc_check",
    "mcp__turboui__get_app_status", "mcp__turboui__get_app_logs",
]

# ── Cross-cutting invariants (system_prompt append) ───────────────────────────
# Hoisted once from the four codegen roles' overlapping guardrails so they apply
# uniformly to the main session and every subagent, instead of being copied 6×.
SHARED_INVARIANTS = """\
# You are the TurboUIGen builder — you work like Claude Code, through a chat.

You are in a live, already-running React 18 + TypeScript + Tailwind + Vite project (dev
server + SQLite/FastAPI API are running; your file edits hot-reload into the user's preview
automatically). You work with ONE person across a normal, ongoing conversation.

## Shared project context (read this first)
- This app lives inside a shared PROJECT that may already hold context from earlier work.
  Before building something new, quietly check these read-only locations (they're on your
  accessible paths — use Read/Glob, they're above your working directory in the project root):
  `brief.md` (the project's current understanding + decisions so far), `inputs/` (reference
  material the user uploaded — docs, tickets, specs), and `artifacts/` (prior outputs, e.g.
  a roundtable's decision record under `artifacts/decisions/` and diagrams under
  `artifacts/diagrams/`). If any exist, read the relevant ones and build in line with what's
  already been decided rather than starting from scratch. Never write to these — they belong
  to the whole project; only edit files inside your own app directory.
- CAUTION with data files (e.g. a CSV/Parquet/JSON in `inputs/`): NEVER `Read` one whole — it
  will overflow your context. Use the **`dataset` tools** instead: `mcp__dataset__profile_dataset`
  (columns + stats), `mcp__dataset__sample_dataset` (a few rows), and `mcp__dataset__run_sql`
  (DuckDB SQL over the file — aggregations/filters run without loading it). Let the query do the
  work. If you need it as app data, use `run_sql` to pull a representative subset and write that
  into `api/seed.sql` (a few thousand rows) rather than loading the whole file.

## How to work
- Treat each message as a turn in a conversation. If the request is clear enough, go ahead
  and build it (write the files). If it's vague or you have a real choice to make, ask a
  short clarifying question or two and STOP — wait for their reply before building. Don't
  guess when a quick question would do; don't over-interrogate when the intent is clear.
- Build by writing files directly (schema.sql, seed.sql, src/types.ts, src/App.tsx,
  src/pages/*, src/components/*). The preview updates live as you write — no need to start
  servers or run a build.
- To change an existing app, just edit the relevant files. Everything else keeps working.
- You're talking to a NON-technical person. Speak in short, concrete BEATS — one line per
  meaningful step, and lead with the OUTCOME ("Added a revenue-by-region chart", not "Now I'm
  going to create a component that will…"). Plain language about the app and its features;
  never mention files, code, SQL, tools, or subagents. No filler, no pre-announcing in several
  sentences — just do it and report the result in a line. Crisp and to the point.
- END-OF-BUILD SUMMARY: whenever you finish building or make a substantive change, close your
  message with a summary block the app renders as a card — a fenced code block tagged
  `turbo-summary` containing JSON with these keys (each item ONE short plain-language line):
      ```turbo-summary
      {"built": ["what you added/changed", "..."],
       "howToUse": "one sentence on how to use it",
       "assumed": ["any assumption you made", "..."],
       "next": ["a suggested next step", "..."]}
      ```
  Only include it after real work — never after a plain question or a one-line answer. Omit any
  key that has nothing to say (e.g. no `assumed` if you assumed nothing).

## Deliverables when you build an app
- api/schema.sql — SQLite tables (snake_case, ≥5 columns on main tables).
- api/seed.sql — realistic sample data. Aim for ~15–30 rows per main table (enough to feel
  real, not so much it's slow to produce). Don't hand-type hundreds of rows — if you want
  more volume, write a short throwaway script (e.g. python) to generate seed.sql, run it,
  then delete the script. No 'test'/'lorem'/999 placeholder values.
- src/types.ts — one PascalCase interface per table.
- src/App.tsx — import your pages, define <Routes>, add a Sidebar/Header from mobility-global-ds.
- src/pages/*.tsx and any src/components/*.tsx — real content, no empty stubs.
Validate the data layer with mcp__turboui__validate_data_layer and typecheck with
mcp__turboui__tsc_check before you consider a build done.

## House rules (apply to every file you write)

- CHARTS/MAPS: use D3 only. NEVER use Highcharts, Recharts, Chart.js, or any other
  charting library.
- DATA: never import from `../data` or `../../data` — those modules do not exist. All
  data flows through `useApi(tableName)` → `GET /api/data/{tableName}` and `apiAggregate`.
  Fields returned by the API are snake_case (matching the SQL columns).
- DESIGN SYSTEM: use the `mobility-global-ds` components for all standard UI (Button,
  Input, Card, DataTable, Badge, KpiCard, Header, Sidebar, Footer, Modal, Alert, Tabs,
  Pagination, ProgressBar, Avatar, Tooltip, Breadcrumb, SearchBar, Dropdown). Never
  hand-roll a component the design system already provides.
- AI FEATURES: call the backend with the EXACT contract `POST /api/chat` with body
  `{messages: [{role, content}], context}`. Never `{message}` or `{prompt}`.
- SQL tables/columns are snake_case; TypeScript interfaces are PascalCase/camelCase and
  must mirror the schema.
- INFRASTRUCTURE files are managed by TurboUIGen and must not be edited: vite.config.ts,
  package.json, tsconfig.json, src/main.tsx, api/app_server.py, api/.env,
  src/hooks/useApi.ts. Author schema/types/pages/components instead.
- Never write blank files. Self-validate with the mcp__turboui__* tools before finishing.
"""

# Commands the Bash gate refuses even under acceptEdits.
_DESTRUCTIVE = (
    "rm -rf", "rm -r ", "sudo ", "mkfs", "shutdown", "reboot", "dd if=",
    ":(){", "> /dev", "chmod -r 000", "mklink", "rmdir /s", "git push", "npm publish",
)


def make_bash_gate(ctx: ProjectContext):
    """can_use_tool callback — only Bash reaches here (edits auto-accepted, MCP/read auto-allowed)."""

    async def bash_gate(tool_name: str, tool_input: dict, context):
        if tool_name != "Bash":
            return PermissionResultAllow()
        cmd = (tool_input.get("command") or "").lower()
        if any(tok in cmd for tok in _DESTRUCTIVE):
            return PermissionResultDeny(message=f"Blocked destructive command in bash gate: {cmd[:80]}")
        return PermissionResultAllow()

    return bash_gate


_MODE_COLLABORATE = """

## Working style — COLLABORATE (the user wants to be brought along)
- Before building anything substantial, propose a SHORT plan first — the pages/features you'll
  create, in a few plain-language lines — and STOP. Wait for their go-ahead before building.
- After each meaningful milestone (the data, a page, a feature), pause: give the crisp summary
  and ask what they'd like next or whether to adjust, before continuing. Don't run ahead.
- When there's a real choice to make, ask rather than assume."""

_MODE_AUTOPILOT = """

## Working style — AUTOPILOT (the user will review at the end)
- Make sensible assumptions and build the whole thing end-to-end WITHOUT stopping for approval.
- Only stop to ask if you are genuinely blocked by something you cannot reasonably assume.
- When done, present the finished app with the end-of-build summary for review."""


def _mode_clause(mode: Optional[str]) -> str:
    if mode == "collaborate":
        return _MODE_COLLABORATE
    if mode == "autopilot":
        return _MODE_AUTOPILOT
    return ""


def build_options(
    ctx: ProjectContext,
    *,
    hitl: bool = False,
    resume_session_id: Optional[str] = None,
    provider: Optional[str] = None,
    can_use_tool=None,
    mode: Optional[str] = None,
) -> ClaudeAgentOptions:
    """Construct the one canonical options object for a builder/session over `ctx`.

    `provider` selects the model backend: 'litellm' | 'bedrock' | 'local'
    (default: TURBOUI_MODEL_PROVIDER env, else 'litellm').
    `can_use_tool` overrides the default bash gate — the Phase 4 AgentSession injects
    its permission-queue callback here for HITL.
    """
    provider = sdk_env.resolve_provider(provider)

    # Stream Claude's native thinking + text deltas to the UI (MAX_THINKING_TOKENS turns on
    # extended thinking; include_partial_messages emits the token-level StreamEvents).
    env = sdk_env.cli_env_for(provider)
    env.setdefault("MAX_THINKING_TOKENS", os.environ.get("TURBOUI_MAX_THINKING_TOKENS", "6000"))

    kwargs = dict(
        system_prompt={"type": "preset", "preset": "claude_code", "append": SHARED_INVARIANTS + _mode_clause(mode)},
        tools={"type": "preset", "preset": "claude_code"},  # explicit — guarantees Write/Edit/Bash exist
        cwd=str(ctx.project_dir),
        agents=build_agents(),
        mcp_servers={"turboui": build_turboui_server(ctx)},
        allowed_tools=(
            [*_BUILTIN_ALLOWED_HITL, *_TURBOUI_READONLY] if hitl
            else [*_BUILTIN_ALLOWED, *TURBOUI_TOOL_NAMES]
        ),
        permission_mode="default" if hitl else "acceptEdits",
        can_use_tool=can_use_tool or make_bash_gate(ctx),
        hooks={
            "PreToolUse": [HookMatcher("Write|Edit|MultiEdit", [make_guard_write_hook(ctx.project_dir)], timeout=10)],
            "PostToolUse": [HookMatcher("Write|Edit|MultiEdit", [make_normalize_files_hook(ctx.project_dir)], timeout=15)],
        },
        max_turns=None,
        max_budget_usd=BUILDER_BUDGET_USD,
        include_partial_messages=True,
        env=env,
        setting_sources=[],  # skills/agents come from the plugin, not cwd discovery
    )

    model = sdk_env.model_for(provider)
    if model:  # local provider may leave this unset → CLI uses its own default
        kwargs["model"] = model

    # Phase E — shared project context. For a project-scoped build (key "<proj>--<app>"),
    # give the agent READ access to the project's shared brief, reference uploads, and prior
    # artifacts, so a build stands on decisions already made in the roundtable. Writes stay
    # guarded to the webapp dir by the PreToolUse hook; add_dirs only grants reads.
    parsed = project_store.parse_key(ctx.project_name)
    if parsed:
        proj_root = project_store.project_dir(parsed[0])
        if proj_root.exists():
            kwargs["add_dirs"] = [str(proj_root)]

    # In-process DuckDB dataset tools — safe, bounded querying of CSV/Parquet/JSON in the
    # project (profile/sample/run_sql) so the builder never reads a big data file into context.
    base_dir = project_store.project_dir(parsed[0]) if parsed else None
    kwargs["mcp_servers"]["dataset"] = build_dataset_server(base_dir)
    kwargs["allowed_tools"] = [*kwargs["allowed_tools"], *DATASET_TOOL_NAMES]

    # Phase 2: light up subagents + skills when the plugin is present.
    # Vendored third-party plugins (e.g. diagram-design) are added alongside so their skills
    # are available to every SDK path — the web-app builder and the roundtable alike.
    local_plugins = [
        {"type": "local", "path": str(d)}
        for d in (AGENT_SDK_DIR, DIAGRAM_DESIGN_DIR) if d.exists()
    ]
    if local_plugins:
        kwargs["plugins"] = local_plugins
        kwargs["skills"] = "all"

    if resume_session_id:
        kwargs["resume"] = resume_session_id

    return ClaudeAgentOptions(**kwargs)
