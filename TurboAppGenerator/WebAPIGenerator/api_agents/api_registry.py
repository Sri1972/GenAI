"""
WebAPIGenerator project registry — same shape/pattern as WebUIGenerator's
agents/uigen_agent.py _load_registry/_save_registry/registry_upsert, but pointed at
this project's own registry file so API projects never mix with web-app projects.
"""

import json
import threading
from datetime import datetime, timezone

from api_config import REGISTRY_FILE, WEB_API_DIR

# Per-project locks guarding .buildlog.json's read-modify-write below — without
# this, two concurrent writers to the SAME project's buildlog (e.g. a generate
# job still running in one background thread while the user clicks Start,
# which also appends a "Seeding: ..." entry) race on read-then-write and one
# write silently clobbers the other's entry instead of both landing. Guarded
# by its own lock since dict.setdefault on _buildlog_locks itself isn't atomic
# either — this is the standard "lock to create a lock" pattern.
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


def list_api_projects() -> list[dict]:
    reg = _load_registry()
    return sorted(reg.values(), key=lambda p: p.get("createdAt", ""), reverse=True)


def upsert_api_project(name: str, **kwargs) -> dict:
    reg = _load_registry()
    entry = reg.get(name, {"name": name})
    entry.update(kwargs)
    reg[name] = entry
    _save_registry(reg)
    return entry


def get_api_project(name: str) -> dict | None:
    return _load_registry().get(name)


def remove_api_project(name: str):
    reg = _load_registry()
    reg.pop(name, None)
    _save_registry(reg)


def rename_api_project(old_name: str, new_name: str) -> dict:
    reg = _load_registry()
    entry = reg.pop(old_name, {"name": old_name})
    entry["name"] = new_name
    if entry.get("title") == old_name:
        entry["title"] = new_name
    reg[new_name] = entry
    _save_registry(reg)
    return entry


# ── Build log + architecture (mirrors the shape WebUIGenerator's ProjectDetailPage
# expects — BuildLogRun {timestamp, event, duration_s, lines} — so the same tab
# rendering logic works for API projects too) ───────────────────────────────────

def append_api_buildlog(name: str, log_lines: list[str], event: str = "", duration_s: float = 0.0):
    buildlog_file = WEB_API_DIR / name / ".buildlog.json"
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


def get_api_buildlog(name: str) -> list[dict]:
    buildlog_file = WEB_API_DIR / name / ".buildlog.json"
    if not buildlog_file.exists():
        return []
    try:
        runs = json.loads(buildlog_file.read_text(encoding="utf-8"))
        return runs if isinstance(runs, list) else []
    except Exception:
        return []


# ── Project history — same shape/pattern as the Web App tab's own
# .history.json (server.py's _append_history/api_history) — a semantic
# record of what was actually asked for on each generate/refine (the prompt/
# comment/instructions text itself), distinct from the buildlog's raw
# progress lines. Reuses the SAME per-project lock as the buildlog above —
# a different file, but sharing one lock per project is simpler than a
# second lock dict and the two are never contended against each other in
# practice (history is appended once, right after a generate/refine
# completes, not interleaved with buildlog's own frequent progress writes).
def append_api_history(name: str, event: str, prompt: str = "", comment: str = "", instructions: str = ""):
    history_file = WEB_API_DIR / name / ".history.json"
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
        if instructions:
            entry["instructions"] = instructions
        history.append(entry)
        history_file.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")


def get_api_history(name: str) -> list[dict]:
    history_file = WEB_API_DIR / name / ".history.json"
    if not history_file.exists():
        return []
    try:
        history = json.loads(history_file.read_text(encoding="utf-8"))
        return history if isinstance(history, list) else []
    except Exception:
        return []


def save_api_architecture(name: str, architecture: dict):
    arch_file = WEB_API_DIR / name / ".architecture.json"
    arch_file.write_text(json.dumps(architecture, indent=2, ensure_ascii=False), encoding="utf-8")


def get_api_architecture(name: str) -> dict | None:
    arch_file = WEB_API_DIR / name / ".architecture.json"
    if not arch_file.exists():
        return None
    try:
        return json.loads(arch_file.read_text(encoding="utf-8"))
    except Exception:
        return None
