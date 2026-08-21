"""
PreToolUse / PostToolUse hooks for the SDK-native web-app builder.

These preserve two file-materialization invariants that used to live inside
uigen_agent._write_files, now that the agent writes files itself via Write/Edit:

  PostToolUse normalizer  — re-read the just-written file from disk and apply
                            sanitize() (+ _repair_json for .json), then rewrite if
                            changed. Reading from disk is shape-agnostic across
                            Write/Edit/MultiEdit (all land a final file on disk).
  PreToolUse guard        — deny writes outside the project sandbox or into
                            node_modules, and deny blank-file writes ("never write
                            blank files").

Registered on ClaudeAgentOptions.hooks. Both are built per-session over a
project_dir so the sandbox check is scoped correctly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .sanitize_js import sanitize

# Files Python owns and the agent must not clobber under acceptEdits.
PROTECTED_INFRA = {
    "vite.config.ts", "package.json", "tsconfig.json",
    "postcss.config.js", "tailwind.config.js",
    "src/main.tsx",
    "api/app_server.py", "api/.env", "api/requirements.txt",
    "src/hooks/useApi.ts",
}

_NORMALIZE_EXT = (".ts", ".tsx", ".js", ".jsx", ".json")
_WRITE_TOOLS = ("Write", "Edit", "MultiEdit")


def _rel(fp: str, project_dir: Path) -> str | None:
    try:
        return str(Path(fp).resolve().relative_to(project_dir.resolve())).replace("\\", "/")
    except (ValueError, OSError):
        return None


def _deny(reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def make_guard_write_hook(project_dir: Path) -> Callable:
    """PreToolUse: sandbox containment + protected-infra + empty-write guard."""

    async def guard_write_hook(input: dict, tool_use_id, context) -> dict[str, Any]:
        if input.get("tool_name") not in _WRITE_TOOLS:
            return {}
        tinput = input.get("tool_input") or {}
        fp = tinput.get("file_path", "")
        if not fp:
            return {}
        rel = _rel(fp, project_dir)
        if rel is None:
            return _deny(f"Write blocked outside project sandbox: {fp}")
        if "node_modules" in Path(rel).parts:
            return _deny(f"Write blocked into node_modules: {rel}")
        if rel in PROTECTED_INFRA:
            return _deny(
                f"'{rel}' is infrastructure managed by TurboUIGen and must not be edited. "
                "Author your app's schema/types/pages/components instead."
            )
        # never write blank files (Write only; Edit/MultiEdit operate on existing content)
        if input.get("tool_name") == "Write":
            content = tinput.get("content", "")
            if isinstance(content, str) and content.strip() == "":
                return _deny(f"Refusing to write a blank file: {rel}")
        return {}

    return guard_write_hook


def make_normalize_files_hook(project_dir: Path) -> Callable:
    """PostToolUse: normalize the just-written file to mirror old _write_files."""

    async def normalize_files_hook(input: dict, tool_use_id, context) -> dict[str, Any]:
        if input.get("tool_name") not in _WRITE_TOOLS:
            return {}
        fp = (input.get("tool_input") or {}).get("file_path")
        if not fp:
            return {}
        p = Path(fp)
        if p.suffix not in _NORMALIZE_EXT or not p.exists():
            return {}
        try:
            original = p.read_text(encoding="utf-8")
        except OSError:
            return {}
        content = original
        if p.suffix == ".json":
            try:
                from .uigen_agent import _repair_json  # lazy: heavy module
                content = _repair_json(content, str(p))
            except Exception:
                pass
        try:
            content = sanitize(content, str(p))
        except Exception:
            return {}
        if content != original:
            try:
                p.write_text(content, encoding="utf-8")
            except OSError:
                return {}
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": f"Auto-normalized {p.name} (sanitize/_repair_json) after write.",
                }
            }
        return {}

    return normalize_files_hook
