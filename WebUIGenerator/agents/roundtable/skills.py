"""The skill pack — professional habits a colleague can be given.

Skills reach a persona as a **local plugin**, not through the CLI's normal
settings discovery. That is deliberate. Enabling ``setting_sources=["project"]``
(the other way to make skills discoverable) also loads any ``CLAUDE.md`` above
the persona's working directory — and since workspaces live inside this repo,
personas would start the meeting knowing they are part of a software project
instead of being colleagues at a table. Verified: with ``project`` sources a
persona reports "Agent Roundtable conversation engine framework" as its
context. The plugin route keeps ``setting_sources=[]`` and leaks nothing.

Three things are required together, and two of them fail *silently* when
missing — the same trap as the non-existent tool names in ``personas.py``:

    plugins=[{"type": "local", "path": <pack>}]   where the skills live
    skills=["ticket-triage", ...]                 which ones this persona sees
    "Skill" in tools/allowed_tools                without this, nothing loads

``skills`` is a **context filter, not a sandbox**: a skill not listed for a
persona is hidden from its listing and refused by the Skill tool, but the file
is still on disk and a persona with ``Bash`` or ``Read`` could go and read it.
Good enough for differentiating a room; not a boundary to rely on.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

PACK = Path(__file__).resolve().parents[2] / "skillpack"

# Skills the Chair uses after the meeting, not skills a colleague brings to
# one. Both produce artifacts — a deck, a diagram — that take minutes to make,
# blow through any sane turn budget, and land somewhere nobody in the room can
# see. They belong to the record, so they run once, from the recap. Listing
# them here keeps them out of the per-persona picker.
RECAP_ONLY = {"pptx", "drawio-skill"}

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def pack_path(pack: str | Path | None = None) -> Path:
    return Path(pack) if pack else PACK


def packs(pack: str | Path | None = None) -> list[Path]:
    """Every plugin root to load: ours, then anything vendored.

    Two roots rather than one directory because they have different rules.
    ``skillpack/`` is written here and committed. ``skillpack/vendor/`` is
    fetched from other people's repositories, is gitignored, and can carry
    licences that are not ours to redistribute — Anthropic's pptx skill is
    "All rights reserved". Keeping them apart means updating a third-party
    skill is a re-fetch, and the repo's diff stays about our own work.
    """
    root = pack_path(pack)
    vendor = root / "vendor"
    return [p for p in (root, vendor) if (p / "skills").is_dir()]


def available(pack: str | Path | None = None) -> list[dict[str, Any]]:
    """Every skill in the pack: id, name, description, path.

    ``id`` is the **directory name**, because that is what the runtime matches
    on — verified, because it is easy to get backwards. A skill whose
    frontmatter ``name`` differs from its directory (Anthropic's pptx skill is
    ``name: pptx`` in ``pptx-skill/``) loads under the directory name and
    silently grants nothing under the other:

        skills=["pptx"]        -> no skills at all
        skills=["pptx-skill"]  -> roundtable:pptx-skill

    The frontmatter name is kept as ``title`` for display only.
    """
    found: list[dict[str, Any]] = []
    for root in packs(pack):
        for d in sorted((root / "skills").iterdir()):
            skill = d / "SKILL.md"
            if not d.is_dir() or not skill.is_file():
                continue
            meta = _frontmatter(skill.read_text(encoding="utf-8"))
            found.append(
                {
                    "id": d.name,  # what the runtime matches — do not "fix" this
                    "title": meta.get("name") or d.name,
                    "description": meta.get("description", ""),
                    "vendored": root.name == "vendor",
                    "recap_only": d.name in RECAP_ONLY,
                    "path": str(skill),
                }
            )
    return sorted(found, key=lambda s: s["id"])


def _frontmatter(text: str) -> dict[str, str]:
    """Just the top-level scalars — enough for name and description."""
    match = _FRONTMATTER.match(text)
    if not match:
        return {}
    out: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep and not key.startswith(" "):
            out[key.strip()] = value.strip().strip("\"'")
    return out


def plugin_config(pack: str | Path | None = None) -> list[dict[str, str]]:
    """The ``plugins`` value for a persona that has been given skills."""
    return [{"type": "local", "path": str(p)} for p in packs(pack)]
