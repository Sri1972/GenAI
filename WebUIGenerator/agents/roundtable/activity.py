"""Turn a raw tool call into a short, human line for the meeting UI.

The point is to bring the user along while a persona does its homework — "Data
is profiling car_prices.csv" reads very differently from a spinner. Kept
deliberately terse; the detail lives in the eventual turn, not here.
"""

from __future__ import annotations

import os


def _name(inp: dict, *keys: str) -> str:
    for k in keys:
        v = inp.get(k)
        if v:
            return os.path.basename(str(v))
    return ""


def friendly(tool: str, inp: dict) -> str | None:
    """A present-tense phrase for a tool call, or None to skip (too noisy)."""
    inp = inp or {}
    t = tool.split("__")[-1]  # drop mcp__server__ prefix

    if t == "profile_dataset":
        f = _name(inp, "path", "file", "name")
        return f"profiling {f}" if f else "profiling the dataset"
    if t == "sample_dataset":
        f = _name(inp, "path", "file", "name")
        return f"sampling rows from {f}" if f else "sampling the data"
    if t == "run_sql":
        return "querying the data"
    if t == "list_datasets":
        return "looking at what data is available"
    if t == "Read":
        f = _name(inp, "file_path", "path")
        return f"reading {f}" if f else "reading the material"
    if t in ("Grep", "Glob"):
        return "searching the material"
    if t == "Bash":
        return "running a quick check"
    if t in ("Write", "Edit"):
        f = _name(inp, "file_path", "path")
        return f"jotting notes in {f}" if f else "jotting down notes"
    if t == "WebFetch" or t == "WebSearch":
        return "checking a reference"
    if t == "Skill":
        return "using a skill"
    # Unknown tool: show a cleaned-up name rather than nothing.
    return t.replace("_", " ")
