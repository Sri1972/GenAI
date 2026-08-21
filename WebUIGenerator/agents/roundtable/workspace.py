"""Workspace layout.

Each persona gets a private working directory (``cwd``) and read access to a
shared minutes directory (``add_dirs``). That is the whole isolation model:

    workspaces/2026-08-15-143201-sharing-or-a-proper-search/
      ├── shared/
      │   ├── brief.md          the question, written once by the facilitator
      │   ├── transcript.json   the whole meeting, written at the end
      │   └── minutes/          append-only, one file per turn
      │       ├── 001-product.md
      │       └── 002-engineering.md
      ├── product/              private
      ├── engineering/          private
      └── chair/

One directory per meeting, named by ``new_meeting_id`` — timestamp first so
they sort chronologically, topic after so they're recognisable. Meetings are
never overwritten: every run leaves its own trace, and ``meetings()`` lists
them newest first.

Append-only, one file per turn, is deliberate: it removes write contention
between agents entirely and makes turn order explicit in the filenames.

Only the facilitator writes to ``minutes/``. Personas read it. That is
enforced by tool grant (personas get Read, not Write) rather than by
filesystem permissions — see docs/architecture.md → Isolation is advisory.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


def new_meeting_id(topic: str, when: datetime | None = None) -> str:
    """A directory name for one meeting: sortable timestamp, then the topic.

    Sortable first so the filesystem lists meetings in the order they
    happened; the topic follows so a directory is recognisable without
    opening it.
    """
    stamp = (when or datetime.now()).strftime("%Y-%m-%d-%H%M%S")
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:48].rstrip("-")
    return f"{stamp}-{slug}" if slug else stamp


def meetings(root: str | Path = "workspaces") -> list[dict[str, Any]]:
    """Every meeting on disk, newest first.

    Includes meetings that never finished — they have minutes but no
    transcript, and losing them from the list would hide exactly the runs
    worth looking at. ``complete`` says which is which.
    """
    base = Path(root)
    if not base.is_dir():
        return []

    found: list[dict[str, Any]] = []
    for d in base.iterdir():
        shared = d / "shared"
        if not d.is_dir() or not shared.is_dir():
            continue
        transcript = shared / "transcript.json"
        data: dict[str, Any] = {}
        if transcript.exists():
            try:
                data = json.loads(transcript.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = {}
        minutes = _listing(shared / "minutes")
        found.append(
            {
                "id": d.name,
                "path": str(d),
                "topic": data.get("topic") or _brief_topic(shared) or d.name,
                "people": data.get("people") or [],
                "turns": len(minutes),
                "complete": bool(data),
                "when": (transcript if transcript.exists() else d).stat().st_mtime,
            }
        )
    return sorted(found, key=lambda m: m["when"], reverse=True)


def _brief_topic(shared: Path) -> str:
    """The question, for a meeting that never wrote a transcript."""
    brief = shared / "brief.md"
    if not brief.exists():
        return ""
    body = brief.read_text(encoding="utf-8").split("\n\n", 1)
    return body[1].strip() if len(body) > 1 else ""


def _listing(path: Path) -> list[tuple[str, int]]:
    """Files directly in ``path``, name and size, sorted. Never raises."""
    if not path.is_dir():
        return []
    return sorted(
        (f.name, f.stat().st_size) for f in path.iterdir() if f.is_file()
    )


class Workspace:
    def __init__(self, root: str | Path, meeting_id: str) -> None:
        self.base = Path(root).resolve() / meeting_id
        self.shared = self.base / "shared"
        self.minutes = self.shared / "minutes"

    def setup(self, people: list[str], topic: str, fresh: bool = True) -> None:
        if fresh and self.base.exists():
            shutil.rmtree(self.base)
        self.minutes.mkdir(parents=True, exist_ok=True)
        for pid in [*people, "chair"]:
            (self.base / pid).mkdir(parents=True, exist_ok=True)
        (self.shared / "brief.md").write_text(
            f"# The question\n\n{topic}\n", encoding="utf-8"
        )

    def private(self, pid: str) -> Path:
        return self.base / pid

    def describe(self, people: list[str]) -> dict[str, Any]:
        """The layout as it exists on disk right now.

        Reports rather than assumes: directories that have not been created
        yet come back with ``exists: False`` and no files, so the same shape
        renders before a meeting starts and while one is running.

        ``access`` is what the *tool grant* allows, not what the filesystem
        enforces. Personas get ``Read`` on the shared directory and no
        ``Write``, which is why the minutes stay append-only — but a persona
        granted ``Write``, ``Edit`` or ``Bash`` can reach outside its own
        directory, and callers should say so rather than imply a sandbox.
        """
        return {
            "base": str(self.base),
            "shared": {
                "path": str(self.shared),
                "exists": self.shared.exists(),
                "files": _listing(self.shared),
                "minutes": _listing(self.minutes),
            },
            "private": {
                pid: {
                    "path": str(self.private(pid)),
                    "exists": self.private(pid).exists(),
                    "files": _listing(self.private(pid)),
                }
                for pid in [*people, "chair"]
            },
        }

    def seed_notes(self, notes: dict[str, str]) -> None:
        """Drop private notes into each persona's working directory.

        This is the "data" axis of persona differentiation, and the one that
        matters most: personas sharing tools and context converge no matter
        what their prompts say. Giving one of them something the others
        cannot see is what makes a disagreement real rather than plausible.
        """
        for pid, text in notes.items():
            if text and text.strip():
                (self.private(pid) / "notes.md").write_text(
                    f"# Your notes\n\n{text.strip()}\n", encoding="utf-8"
                )

    @property
    def transcript(self) -> Path:
        return self.shared / "transcript.json"

    def save_transcript(self, data: dict[str, Any]) -> Path:
        """The whole meeting as one JSON file.

        The minutes are for the agents to read mid-meeting; this is for
        everything downstream — replaying a meeting into the UI without
        spending anything, and holding a run as a regression baseline.
        """
        self.transcript.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return self.transcript

    def record(self, index: int, who: str, text: str) -> Path:
        """Append a turn to the shared minutes. Facilitator-only."""
        path = self.minutes / f"{index:03d}-{who}.md"
        path.write_text(text, encoding="utf-8")
        return path
