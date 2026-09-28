"""
MCPGenerator project registry — same shape/pattern as
WebAPIGenerator/api_agents/api_registry.py, pointed at this project's own registry
file so MCP projects never mix with web-app or API projects.
"""

import json
import threading
from datetime import datetime, timezone

from mcp_config import REGISTRY_FILE, MCP_DIR

# Per-project locks guarding .buildlog.json's read-modify-write below — same
# fix, same reasoning as api_registry.py's own _lock_for: without it, two
# concurrent writers to the SAME project's buildlog (e.g. a generate job
# still running in one background thread while something else appends an
# entry for that same project) race on read-then-write and one write silently
# clobbers the other's entry instead of both landing. Guarded by its own lock
# since dict.setdefault on _buildlog_locks itself isn't atomic either — the
# standard "lock to create a lock" pattern.
_buildlog_locks: dict[str, threading.Lock] = {}
_buildlog_locks_guard = threading.Lock()


def _lock_for(name: str) -> threading.Lock:
    with _buildlog_locks_guard:
        return _buildlog_locks.setdefault(name, threading.Lock())


def _load_registry() -> dict:
    if REGISTRY_FILE.exists():
        try:
            data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def _save_registry(reg: dict):
    REGISTRY_FILE.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")


def list_mcp_projects() -> list[dict]:
    reg = _load_registry()
    return sorted(reg.values(), key=lambda p: p.get("createdAt", ""), reverse=True)


def upsert_mcp_project(name: str, **kwargs) -> dict:
    reg = _load_registry()
    entry = reg.get(name, {"name": name})
    entry.update(kwargs)
    reg[name] = entry
    _save_registry(reg)
    return entry


def get_mcp_project(name: str) -> dict | None:
    return _load_registry().get(name)


def remove_mcp_project(name: str):
    reg = _load_registry()
    reg.pop(name, None)
    _save_registry(reg)


def rename_mcp_project(old_name: str, new_name: str) -> dict:
    reg = _load_registry()
    entry = reg.pop(old_name, {"name": old_name})
    entry["name"] = new_name
    if entry.get("title") == old_name:
        entry["title"] = new_name
    reg[new_name] = entry
    _save_registry(reg)
    return entry


# ── Build log + metadata (mirrors api_registry.py's buildlog/architecture shape) ──

def append_mcp_buildlog(name: str, log_lines: list[str], event: str = "", duration_s: float = 0.0):
    buildlog_file = MCP_DIR / name / ".buildlog.json"
    with _lock_for(name):
        buildlog_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            runs = json.loads(buildlog_file.read_text(encoding="utf-8")) if buildlog_file.exists() else []
        except Exception:
            runs = []
        runs.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "duration_s": round(duration_s, 1),
            "lines": log_lines,
        })
        buildlog_file.write_text(json.dumps(runs, indent=2, ensure_ascii=False), encoding="utf-8")


def get_mcp_buildlog(name: str) -> list[dict]:
    buildlog_file = MCP_DIR / name / ".buildlog.json"
    if not buildlog_file.exists():
        return []
    try:
        runs = json.loads(buildlog_file.read_text(encoding="utf-8"))
        return runs if isinstance(runs, list) else []
    except Exception:
        return []


# ── Project history — same shape/pattern as api_registry.py's own
# append_api_history (itself mirroring the Web App tab's .history.json) — a
# semantic record of what was actually asked for on each generate/update,
# distinct from the buildlog's raw progress lines. MCP has no separate
# "headline vs. detail" prompt split the way Web App/API do (Instructions is
# the one and only freeform text concept here), so it's stored under
# `prompt` — the same field name the History tab's rendering already treats
# as the primary, always-shown text.
def append_mcp_history(name: str, event: str, prompt: str = "", comment: str = ""):
    history_file = MCP_DIR / name / ".history.json"
    with _lock_for(name):
        history_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            history = json.loads(history_file.read_text(encoding="utf-8")) if history_file.exists() else []
        except Exception:
            history = []
        entry = {
            "event": event,
            "detail": "",
            "figmaUrl": "",
            "prompt": prompt,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if comment:
            entry["comment"] = comment
        history.append(entry)
        history_file.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")


def get_mcp_history(name: str) -> list[dict]:
    history_file = MCP_DIR / name / ".history.json"
    if not history_file.exists():
        return []
    try:
        history = json.loads(history_file.read_text(encoding="utf-8"))
        return history if isinstance(history, list) else []
    except Exception:
        return []


def save_mcp_metadata(name: str, metadata: dict):
    meta_file = MCP_DIR / name / "metadata.json"
    meta_file.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")


def get_mcp_metadata(name: str) -> dict | None:
    meta_file = MCP_DIR / name / "metadata.json"
    if not meta_file.exists():
        return None
    try:
        return json.loads(meta_file.read_text(encoding="utf-8"))
    except Exception:
        return None
