"""
The `turboui` in-process MCP server for the SDK-native web-app builder.

Wraps TurboUIGen's existing, tested Python capabilities as Claude Agent SDK tools
so the builder agent can self-validate, type-check, QA, and run/preview its own app:

  validators   : validate_sql, validate_seed_data, check_types_match,
                 validate_react_component            (reused from sdk_tools.py)
  structured   : validate_architecture, check_page_types, validate_data_layer
                 (new — replace run_agent's schema enforcement for the architect roles)
  build/verify : tsc_check, run_qa                   (run_qa reuses qa_agent.run_qa)
  lifecycle    : start_app, stop_app, get_app_status, get_app_logs
                 (thin wrappers over callables injected via ProjectContext, so this
                  module stays decoupled from uigen_agent's in-flux internals)

`read_skill_template` is intentionally NOT exposed — native Skills + Read supersede it.

Everything runs in the same Python process as ClaudeSDKClient, so the wrapped
functions are imported and called directly (blocking ones via asyncio.to_thread).
"""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from claude_agent_sdk import tool, create_sdk_mcp_server, ToolAnnotations

from . import sdk_tools as st

# ── Project context (per-session state the tools close over) ──────────────────

@dataclass
class ProjectContext:
    """Everything the turboui tools need about the project under construction.

    Lifecycle callables are injected by the builder/session so this module does not
    hard-import uigen_agent internals (which are being made cross-platform in parallel).
    """
    project_name: str
    project_dir: Path
    port: int = 0
    api_port: int = 0
    # injected lifecycle hooks (all optional; tools degrade gracefully if unset)
    start_fn: Optional[Callable[[], dict]] = None          # -> {"url","port","apiPort"}
    stop_fn: Optional[Callable[[], None]] = None
    status_fn: Optional[Callable[[], dict]] = None          # -> {"running":bool, ...}
    logs_fn: Optional[Callable[[int], str]] = None          # (tail) -> str

    def preview_url(self) -> str:
        return f"/app/{self.project_name}/"


_RO = ToolAnnotations(readOnlyHint=True)
_ERR_MARKERS = ("SQL Error", "Seed data error", "Cannot parse", "Issues found")
_EMPTY_SCHEMA = {"type": "object", "properties": {}}


def _text(s: str, is_error: bool = False) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": s}], "is_error": is_error}


def _looks_failed(out: str) -> bool:
    return any(m in out for m in _ERR_MARKERS) and not out.startswith(("Valid", "All "))


# ── Validators (reuse sdk_tools fns verbatim; schemas reused as-is) ───────────

def _wrap_validator(tdef: st.ToolDef):
    s = tdef.schema

    @tool(s["name"], s["description"], s["input_schema"], annotations=_RO)
    async def handler(args: dict[str, Any], _fn=tdef.fn) -> dict[str, Any]:
        out = str(_fn(**args))
        return _text(out, is_error=_looks_failed(out))

    return handler


# ── New structured-output validators (architect roles self-validate) ──────────

_VALID_PAGE_TYPES = {
    "dashboard", "data-table", "charts", "map", "card-grid", "wizard",
    "ai-chat", "form", "detail-view", "kpi-dashboard", "custom",
}


def _validate_architecture(architecture_json: str) -> str:
    """Validate the UX architect's ARCHITECTURE_SCHEMA JSON (mirrors ux_architect checks)."""
    try:
        arch = json.loads(architecture_json)
    except json.JSONDecodeError as e:
        return f"Cannot parse: invalid JSON — {e}"
    issues: list[str] = []
    pages = arch.get("pages") or []
    nav = arch.get("navigation") or []
    if not pages:
        issues.append("No pages defined")
    names = [p.get("name") for p in pages]
    dupes = {n for n in names if n and names.count(n) > 1}
    if dupes:
        issues.append(f"Duplicate page names: {sorted(dupes)}")
    for p in pages:
        desc = (p.get("description") or "").strip()
        if len(desc) < 20:
            issues.append(f"Page '{p.get('name')}' description too thin (<20 chars) — every page needs real content")
    page_names = set(names)
    for n in nav:
        tgt = n.get("page")
        if tgt and tgt not in page_names:
            issues.append(f"Navigation item '{n.get('label')}' references non-existent page '{tgt}'")
    if len(nav) > 8:
        issues.append(f"Too many top-level nav items ({len(nav)} > 8) — cognitive overload")
    if nav:
        first = (nav[0].get("label") or "").lower() + (nav[0].get("page") or "").lower()
        if not any(k in first for k in ("dashboard", "overview", "home")):
            issues.append("First navigation item should be a dashboard/overview/home")
    if "dataEntities" not in arch:
        issues.append("Missing 'dataEntities'")
    if "hasAiFeatures" not in arch:
        issues.append("Missing 'hasAiFeatures'")
    if issues:
        return "Issues found:\n" + "\n".join(f"- {i}" for i in issues)
    return "Valid. Architecture looks correct."


def _check_page_types(pages_json: str) -> str:
    """Verify every page.type is a recognized type."""
    try:
        pages = json.loads(pages_json)
    except json.JSONDecodeError as e:
        return f"Cannot parse: invalid JSON — {e}"
    if isinstance(pages, dict):
        pages = pages.get("pages", [])
    issues: list[str] = []
    for p in pages:
        t = p.get("type")
        if t not in _VALID_PAGE_TYPES:
            issues.append(f"Page '{p.get('name')}' has invalid type '{t}' (valid: {sorted(_VALID_PAGE_TYPES)})")
    if issues:
        return "Issues found:\n" + "\n".join(f"- {i}" for i in issues)
    return "Valid. All page types recognized."


def _validate_data_layer(schema_sql: str, seed_sql: str, types_ts: str) -> str:
    """Combined data-architect gate: schema + seed + TS interfaces in one call."""
    parts = [
        st.validate_sql.fn(schema_sql),
        st.validate_seed_data.fn(schema_sql, seed_sql),
        st.check_types_match.fn(schema_sql, types_ts),
    ]
    return "\n".join(parts)


def _structured_tool(name, description, schema, fn):
    @tool(name, description, schema, annotations=_RO)
    async def handler(args: dict[str, Any]) -> dict[str, Any]:
        out = str(fn(**args))
        return _text(out, is_error=_looks_failed(out))

    return handler


# ── tsc_check (read-only typecheck, errors grouped by file) ───────────────────

_TSC_ERR = re.compile(r"^(?P<file>[^(]+)\((?P<line>\d+),\d+\): error (?P<code>TS\d+): (?P<msg>.+)$")


def _run_tsc(project_dir: Path) -> str:
    tsc = None
    for cand in ("node_modules/.bin/tsc", "node_modules/.bin/tsc.cmd"):
        p = project_dir / cand
        if p.exists():
            tsc = str(p)
            break
    if not tsc:
        return "tsc not found in node_modules — cannot typecheck (is the project linked?)."
    try:
        proc = subprocess.run(
            [tsc, "--noEmit", "--pretty", "false"],
            cwd=str(project_dir), capture_output=True, text=True, timeout=120,
        )
    except subprocess.TimeoutExpired:
        return "tsc timed out after 120s."
    if proc.returncode == 0:
        return "Clean. No TypeScript errors."
    by_file: dict[str, list[str]] = {}
    for line in (proc.stdout + "\n" + proc.stderr).splitlines():
        m = _TSC_ERR.match(line.strip())
        if m:
            by_file.setdefault(m["file"], []).append(f"  L{m['line']} {m['code']}: {m['msg']}")
    if not by_file:
        return f"tsc failed (rc={proc.returncode}) but produced no parseable errors:\n{proc.stdout[-1500:]}"
    out = [f"{len(by_file)} file(s) with TypeScript errors:"]
    for f, errs in by_file.items():
        out.append(f"\n{f}")
        out.extend(errs)
    return "\n".join(out)


# ── Server builder ────────────────────────────────────────────────────────────

def build_turboui_server(ctx: ProjectContext):
    validators = [
        _wrap_validator(st.validate_sql),
        _wrap_validator(st.validate_seed_data),
        _wrap_validator(st.check_types_match),
        _wrap_validator(st.validate_react_component),
    ]

    architecture_schema = {
        "type": "object",
        "properties": {"architecture_json": {"type": "string", "description": "Full architecture JSON to validate"}},
        "required": ["architecture_json"],
    }
    pages_schema = {
        "type": "object",
        "properties": {"pages_json": {"type": "string", "description": "JSON array of pages (or {pages:[...]})"}},
        "required": ["pages_json"],
    }
    data_schema = {
        "type": "object",
        "properties": {
            "schema_sql": {"type": "string"},
            "seed_sql": {"type": "string"},
            "types_ts": {"type": "string"},
        },
        "required": ["schema_sql", "seed_sql", "types_ts"],
    }

    structured = [
        _structured_tool("validate_architecture",
                         "Validate the app architecture JSON (pages, navigation, dataEntities, hasAiFeatures). "
                         "Call before returning the architecture: catches empty/duplicate pages, thin descriptions, "
                         "dangling nav references, >8 nav items, and a non-dashboard first nav item.",
                         architecture_schema, _validate_architecture),
        _structured_tool("check_page_types",
                         "Check that every page.type is a recognized TurboUIGen page type "
                         "(dashboard, data-table, charts, map, card-grid, wizard, ai-chat, form, detail-view, "
                         "kpi-dashboard, custom).",
                         pages_schema, _check_page_types),
        _structured_tool("validate_data_layer",
                         "One-shot data-layer gate: validates schema.sql, seed.sql, and src/types.ts together "
                         "(SQL executes, seed inserts, TS interfaces match tables). Call before finishing the data model.",
                         data_schema, _validate_data_layer),
    ]

    @tool("tsc_check", "Run `tsc --noEmit` in the project and return TypeScript errors grouped by file. "
                       "Read-only. Use it to drive the type-check heal loop (fix only the reported files/lines).",
          _EMPTY_SCHEMA, annotations=_RO)
    async def tsc_check(args: dict[str, Any]) -> dict[str, Any]:
        out = await asyncio.to_thread(_run_tsc, ctx.project_dir)
        return _text(out, is_error=not out.startswith("Clean"))

    @tool("run_qa", "Run the full QA sign-off (static checks, tsc, Playwright/HTTP route probes) on the RUNNING app. "
                    "The app must already be started (call start_app first). Takes up to ~3 minutes. "
                    "Returns a JSON QAReport; is_error when it does not pass.",
          _EMPTY_SCHEMA)
    async def run_qa_tool(args: dict[str, Any]) -> dict[str, Any]:
        if ctx.status_fn is not None:
            status = await asyncio.to_thread(ctx.status_fn)
            if not status.get("running"):
                return _text("App is not running. Call start_app first, then run_qa.", is_error=True)
        try:
            from .qa_agent import run_qa as _run_qa
        except Exception as e:  # pragma: no cover - import guard
            return _text(f"QA unavailable: {e}", is_error=True)
        report = await asyncio.to_thread(_run_qa, ctx.project_name, ctx.port, ctx.project_dir)
        return _text(json.dumps(report.to_dict(), indent=2), is_error=not report.passed)

    @tool("start_app", "Build & serve this app (Vite + API server). Idempotent — reuses a running server. "
                       "Returns the preview URL and ports.", _EMPTY_SCHEMA)
    async def start_app(args: dict[str, Any]) -> dict[str, Any]:
        if ctx.start_fn is None:
            return _text("start_app is not wired in this context.", is_error=True)
        info = await asyncio.to_thread(ctx.start_fn)
        return _text(json.dumps(info))

    @tool("stop_app", "Stop this app's Vite and API server processes.", _EMPTY_SCHEMA)
    async def stop_app(args: dict[str, Any]) -> dict[str, Any]:
        if ctx.stop_fn is None:
            return _text("stop_app is not wired in this context.", is_error=True)
        await asyncio.to_thread(ctx.stop_fn)
        return _text(f"Stopped {ctx.project_name}.")

    @tool("get_app_status", "Report whether the app is running, plus its port and preview URL.",
          _EMPTY_SCHEMA, annotations=_RO)
    async def get_app_status(args: dict[str, Any]) -> dict[str, Any]:
        status = {"running": False, "url": ctx.preview_url(), "port": ctx.port, "apiPort": ctx.api_port}
        if ctx.status_fn is not None:
            status.update(await asyncio.to_thread(ctx.status_fn))
        return _text(json.dumps(status))

    @tool("get_app_logs", "Return the last N lines of vite.log / api_server.log for diagnosis.",
          {"type": "object", "properties": {"tail": {"type": "integer", "description": "lines to return (default 120)"}}},
          annotations=_RO)
    async def get_app_logs(args: dict[str, Any]) -> dict[str, Any]:
        n = int(args.get("tail", 120))
        if ctx.logs_fn is not None:
            return _text(await asyncio.to_thread(ctx.logs_fn, n))
        chunks = []
        for name in ("vite.log", "api_server.log"):
            p = ctx.project_dir / name
            if p.exists():
                tail = "\n".join(p.read_text(errors="replace").splitlines()[-n:])
                chunks.append(f"=== {name} (last {n}) ===\n{tail}")
        return _text("\n\n".join(chunks) or "(no logs yet)")

    return create_sdk_mcp_server(
        name="turboui", version="1.0.0",
        tools=[*validators, *structured, tsc_check, run_qa_tool,
               start_app, stop_app, get_app_status, get_app_logs],
    )


# Wire tool names (for allowed_tools) — single source of truth
TURBOUI_TOOL_NAMES = [
    "mcp__turboui__validate_sql",
    "mcp__turboui__validate_seed_data",
    "mcp__turboui__check_types_match",
    "mcp__turboui__validate_react_component",
    "mcp__turboui__validate_architecture",
    "mcp__turboui__check_page_types",
    "mcp__turboui__validate_data_layer",
    "mcp__turboui__tsc_check",
    "mcp__turboui__run_qa",
    "mcp__turboui__start_app",
    "mcp__turboui__stop_app",
    "mcp__turboui__get_app_status",
    "mcp__turboui__get_app_logs",
]
