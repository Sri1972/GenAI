"""
Project store — the unified per-project workspace (Phase A).

A *project* is a persistent workspace that spans every interface in the app (roundtable,
web-app builder, future lenses). On disk:

    generated/projects/<slug>/
      project.json          # metadata
      inputs/               # user-uploaded reference material — READ-ONLY to interfaces
      roundtable/           # brainstorming meetings (<meeting-id>/…)
      webapp/               # web-app prototypes (<app-id>/…)
      artifacts/            # promoted cross-interface outputs (diagrams, decks, exports)

The legacy flat store (generated/web-apps/*) is untouched; this is the new model.
Pure filesystem + JSON — no servers, no SDK. Safe to import anywhere.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import sys
_CFG = Path(__file__).resolve().parent.parent
if str(_CFG) not in sys.path:
    sys.path.insert(0, str(_CFG))
from config import PROJECTS_DIR, WEB_APPS_DIR  # noqa: E402

_SUBDIRS = ("inputs", "roundtable", "webapp", "artifacts")

# Engagement mode: how involved the user wants to be. "collaborate" (human-in-the-loop:
# agents propose, checkpoint, and bring the user along) or "autopilot" (human-on-the-loop:
# agents run to completion, user reviews at the end). Chosen per-activity; this is the
# project-level DEFAULT.
MODES = ("collaborate", "autopilot")
DEFAULT_MODE = "collaborate"

# A project-scoped web-app is addressed by a single routing KEY of the form
# "<project>--<app-id>". Double-hyphen is a safe delimiter because slugify() collapses
# repeated hyphens, so a real project/app slug never contains "--". The key flows through
# the whole existing serving stack (ports, sessions, /app/<key>/ proxy) unchanged; only the
# physical directory it maps to differs (projects/<project>/webapp/<app-id> vs web-apps/<slug>).
KEY_SEP = "--"


# ── slug / paths ──────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    """Filesystem-safe slug: lowercase, hyphen-separated, alnum only."""
    s = re.sub(r"[^a-z0-9-]+", "-", (name or "").lower()).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    return s or "project"


def project_dir(slug: str) -> Path:
    return PROJECTS_DIR / slug


def inputs_dir(slug: str) -> Path:
    return project_dir(slug) / "inputs"


def roundtable_dir(slug: str) -> Path:
    return project_dir(slug) / "roundtable"


def webapp_root(slug: str) -> Path:
    return project_dir(slug) / "webapp"


def webapp_dir(slug: str, app_id: str) -> Path:
    return webapp_root(slug) / slugify(app_id)


def artifacts_dir(slug: str) -> Path:
    return project_dir(slug) / "artifacts"


def _meta_path(slug: str) -> Path:
    return project_dir(slug) / "project.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ── CRUD ──────────────────────────────────────────────────────────────────────

def exists(slug: str) -> bool:
    return _meta_path(slug).exists()


def create_project(name: str, description: str = "") -> dict:
    """Scaffold a new project workspace. Raises ValueError if the slug is taken."""
    slug = slugify(name)
    if exists(slug):
        raise ValueError(f"A project named '{slug}' already exists.")
    d = project_dir(slug)
    for sub in _SUBDIRS:
        (d / sub).mkdir(parents=True, exist_ok=True)
    meta = {
        "slug": slug,
        "name": name.strip() or slug,
        "description": (description or "").strip(),
        "defaultMode": DEFAULT_MODE,
        "created": _now(),
        "updated": _now(),
    }
    _write_meta(slug, meta)
    return _decorate(meta)


def set_default_mode(slug: str, mode: str) -> dict | None:
    """Update the project's default engagement mode. Returns the updated project or None."""
    if mode not in MODES:
        raise ValueError(f"Unknown mode '{mode}'. Use one of {MODES}.")
    meta = get_project(slug)
    if not meta:
        return None
    meta = {k: v for k, v in meta.items() if k not in ("webapps", "inputs")}
    meta["defaultMode"] = mode
    meta["updated"] = _now()
    _write_meta(slug, meta)
    return _decorate(meta)


def default_mode(slug: str) -> str:
    meta = get_project(slug)
    m = (meta or {}).get("defaultMode", DEFAULT_MODE)
    return m if m in MODES else DEFAULT_MODE


def _write_meta(slug: str, meta: dict) -> None:
    _meta_path(slug).write_text(json.dumps(meta, indent=2), encoding="utf-8")


def get_project(slug: str) -> dict | None:
    slug = slugify(slug)
    p = _meta_path(slug)
    if not p.exists():
        return None
    try:
        meta = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return _decorate(meta)


def list_projects() -> list[dict]:
    """All projects, newest-first by created time."""
    out: list[dict] = []
    if not PROJECTS_DIR.exists():
        return out
    for d in PROJECTS_DIR.iterdir():
        if not d.is_dir():
            continue
        meta = get_project(d.name)
        if meta:
            out.append(meta)
    out.sort(key=lambda m: m.get("created", ""), reverse=True)
    return out


def delete_project(slug: str) -> bool:
    slug = slugify(slug)
    d = project_dir(slug)
    if not d.exists():
        return False
    shutil.rmtree(d, ignore_errors=True)
    return True


def touch(slug: str) -> None:
    """Bump the project's updated timestamp (best-effort)."""
    meta = get_project(slug)
    if not meta:
        return
    meta = {k: v for k, v in meta.items() if k not in ("webapps", "inputs")}
    meta["updated"] = _now()
    _write_meta(slug, meta)


def _decorate(meta: dict) -> dict:
    """Attach live-derived fields (counts) without persisting them."""
    slug = meta.get("slug", "")
    return {
        **meta,
        "defaultMode": meta.get("defaultMode", DEFAULT_MODE),
        "webapps": list_webapps(slug),
        "inputs": list_inputs(slug),
    }


# ── inputs (read-only reference material) ──────────────────────────────────────

def _safe_filename(filename: str) -> str:
    base = Path(filename or "").name           # strip any path components
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._") or "file"
    return base


def save_input_file(slug: str, filename: str, data: bytes) -> dict:
    """Write an uploaded reference file into the project's inputs/ dir."""
    slug = slugify(slug)
    if not exists(slug):
        raise ValueError(f"Project '{slug}' does not exist.")
    d = inputs_dir(slug)
    d.mkdir(parents=True, exist_ok=True)
    name = _safe_filename(filename)
    # de-dupe: foo.txt → foo-1.txt
    target = d / name
    if target.exists():
        stem, suffix = target.stem, target.suffix
        i = 1
        while (d / f"{stem}-{i}{suffix}").exists():
            i += 1
        target = d / f"{stem}-{i}{suffix}"
    target.write_bytes(data)
    touch(slug)
    return _input_entry(target)


def list_inputs(slug: str) -> list[dict]:
    slug = slugify(slug)
    d = inputs_dir(slug)
    if not d.exists():
        return []
    return sorted(
        (_input_entry(p) for p in d.iterdir() if p.is_file()),
        key=lambda e: e["name"],
    )


def delete_input(slug: str, filename: str) -> bool:
    slug = slugify(slug)
    target = inputs_dir(slug) / _safe_filename(filename)
    if target.exists() and target.is_file():
        target.unlink()
        touch(slug)
        return True
    return False


def _input_entry(p: Path) -> dict:
    try:
        size = p.stat().st_size
    except OSError:
        size = 0
    return {"name": p.name, "size": size}


# ── webapp prototypes ──────────────────────────────────────────────────────────

def brief_path(slug: str) -> Path:
    return project_dir(slug) / "brief.md"


def read_brief(slug: str) -> str:
    p = brief_path(slug)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def write_brief(slug: str, text: str) -> None:
    """Overwrite the project brief (user-editable)."""
    brief_path(slug).write_text(text, encoding="utf-8")
    touch(slug)


def record_decision(slug: str, meeting_id: str, topic: str, recap: dict) -> dict:
    """Persist a roundtable's outcome as shared project context (Phase E):
    - artifacts/decisions/<meeting-id>.md — the full recap
    - append a synthesized, user-editable entry to brief.md
    Returns {decisionFile, briefUpdated}.
    """
    slug = slugify(slug)
    decisions = artifacts_dir(slug) / "decisions"
    decisions.mkdir(parents=True, exist_ok=True)

    commitments = recap.get("commitments") or []
    still_open = recap.get("still_open") or []
    sections = recap.get("sections") or []
    commit_lines = [f"- **{c.get('who','')}** — {c.get('what','')}" for c in commitments] or ["- (none recorded)"]
    open_lines = [f"- {o}" for o in still_open] or ["- (nothing left open)"]

    lines = [f"# {recap.get('headline') or topic}", "", f"_Meeting {meeting_id} · {_now()}_", ""]
    if sections:  # agenda-structured minutes
        for s in sections:
            items = s.get("items") or []
            if not items:
                continue
            lines += [f"## {s.get('bucket','')}", *[f"- {it}" for it in items], ""]
    else:  # legacy recap shape
        lines += ["## Decision", recap.get("decision", "") or "", "", recap.get("argument", "") or "", ""]
    lines += ["## Who's doing what", *commit_lines, "", "## Still open", *open_lines, ""]
    dfile = decisions / f"{meeting_id}.md"
    dfile.write_text("\n".join(lines), encoding="utf-8")

    # Synthesized brief entry (the recap is already synthesized — append it as the throughline).
    entry = [
        f"\n## {_now()} — {topic}",
        f"**Decided:** {recap.get('decision','').strip() or recap.get('headline','')}",
    ]
    if still_open:
        entry.append(f"**Still open:** {'; '.join(still_open[:3])}{' …' if len(still_open) > 3 else ''}")
    entry.append(f"_(from roundtable {meeting_id})_\n")
    p = brief_path(slug)
    header = "" if p.exists() else f"# {get_project(slug).get('name', slug) if get_project(slug) else slug} — project brief\n\nWhat the team has established so far. Auto-appended after each roundtable; edit freely.\n"
    with p.open("a", encoding="utf-8") as fh:
        if header:
            fh.write(header)
        fh.write("\n".join(entry) + "\n")
    touch(slug)
    return {"decisionFile": dfile.name, "briefUpdated": True}


def list_webapps(slug: str) -> list[str]:
    """The app-ids of prototypes under this project's webapp/ dir."""
    root = webapp_root(slug)
    if not root.exists():
        return []
    return sorted(d.name for d in root.iterdir() if d.is_dir())


def next_app_id(slug: str) -> str:
    """Auto-name the next prototype: app-1, app-2, … (first free)."""
    existing = set(list_webapps(slug))
    i = 1
    while f"app-{i}" in existing:
        i += 1
    return f"app-{i}"


def create_webapp(slug: str) -> str:
    """Reserve a new auto-named prototype dir. Returns its app-id."""
    slug = slugify(slug)
    if not exists(slug):
        raise ValueError(f"Project '{slug}' does not exist.")
    app_id = next_app_id(slug)
    webapp_dir(slug, app_id).mkdir(parents=True, exist_ok=True)
    touch(slug)
    return app_id


def delete_webapp(slug: str, app_id: str) -> bool:
    d = webapp_dir(slug, app_id)
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
        touch(slug)
        return True
    return False


def rename_webapp(slug: str, app_id: str, new_app_id: str) -> str:
    """Rename a prototype directory. Returns the new app-id. Raises ValueError on conflict."""
    slug = slugify(slug)
    src = webapp_dir(slug, app_id)
    if not src.exists():
        raise ValueError(f"Prototype '{app_id}' not found.")
    new_id = slugify(new_app_id)
    dst = webapp_dir(slug, new_id)
    if new_id == slugify(app_id):
        return new_id
    if dst.exists():
        raise ValueError(f"A prototype named '{new_id}' already exists.")
    src.rename(dst)
    touch(slug)
    return new_id


# ── routing-key <-> physical dir ───────────────────────────────────────────────

def make_key(project_slug: str, app_id: str) -> str:
    return f"{slugify(project_slug)}{KEY_SEP}{slugify(app_id)}"


def parse_key(key: str) -> tuple[str, str] | None:
    """(project, app_id) for a project-scoped key, else None (a legacy flat slug)."""
    if KEY_SEP in key:
        proj, app = key.split(KEY_SEP, 1)
        return proj, app
    return None


def dir_for_key(key: str) -> Path:
    """Physical project_dir for a routing key.
    Project key '<proj>--<app>' → projects/<proj>/webapp/<app>; legacy key → web-apps/<key>."""
    parsed = parse_key(key)
    if parsed:
        return webapp_dir(parsed[0], parsed[1])
    return WEB_APPS_DIR / key
