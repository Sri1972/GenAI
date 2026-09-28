"""
Video Creator — turns a content brief into a short scripted video (MP4).

Renders through the "motion kit" (see remotion_project/src/motion,
primitives, storyboard) -- a small library of spring-based motion
primitives (kineticTitle, staggerList, countUp, chartBuild, drawPath,
gsapTextBurst, peopleCrowd, iconMotion, diagramFlow) composed via a
zod-validated storyboard JSON. Same "LLM decides WHAT, code renders HOW"
split the rest of this codebase already uses (ppt_creator's slide plans,
visualization_agent's D3 charts) -- Claude never writes animation code,
only fills a fixed schema; StoryboardVideo.tsx renders it deterministically.

Unlike every other agent in this codebase, planning here is NOT a single
headless JSON-in/JSON-out call. Claude directs: it writes the storyboard,
renders keyframe stills via scripts/keyframes.mjs, views them, and revises
before handing off to the deterministic Remotion render -- a real critique
loop, using Bash/Read/Write tool access for this one call (see
_direct_storyboard). The file Claude ends up writing on disk is the
artifact of record; Python re-validates it defensively before ever
rendering it, the same "never trust the LLM's output blindly" posture
_coerce_scene/validate_spec always had here, just against a richer schema.

Requires Node.js/npm on PATH. On first use, `npm install` runs once inside
remotion_project/ (cached afterward via its own node_modules). On a machine
behind a TLS-inspecting corporate proxy, that first install may fail with
UNABLE_TO_GET_ISSUER_CERT_LOCALLY -- fix once, machine-wide, with:
    npm config set cafile <path to an exported trusted CA bundle>
(export one from the Windows cert store with a short PowerShell one-liner
if needed; see project chat history / README for the exact command).

Usage:
    python run.py --brief "A 3-scene recap of Q3 revenue" --out out.mp4
"""

import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
import wave
from pathlib import Path
from typing import Callable

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.claude_cli import extract_json, run_claude  # noqa: E402

REMOTION_PROJECT_DIR = Path(__file__).resolve().parent / "remotion_project"
REMOTION_CLI = REMOTION_PROJECT_DIR / "node_modules" / "@remotion" / "cli" / "remotion-cli.js"
COMPOSITION_ID = "Storyboard"

# Must exactly match remotion_project/src/storyboard/schema.ts's elementSchema
# discriminated union -- the ONLY primitives that exist. Claude only ever
# picks a shape from this fixed menu; how each one actually animates is
# entirely owned by the matching file under remotion_project/src/primitives/.
ELEMENT_TYPES = (
    "kineticTitle", "staggerList", "countUp", "chartBuild", "drawPath",
    "gsapTextBurst", "peopleCrowd", "iconMotion", "diagramFlow", "brandIcon",
    "animatedGif",
)
# Must exactly match remotion_project/src/primitives/IconMotion.tsx's
# ICON_NAMES -- same fixed-menu reasoning as ELEMENT_TYPES above, one level
# down (which icon a "iconMotion"/"diagramFlow" node may name).
ICON_NAMES = (
    "Settings", "Cog", "Wrench", "RefreshCw",  # process/gear -- spins in place
    "Car", "Truck", "Bus", "Bike",  # vehicles -- drives across with speed lines
    "Rocket",  # launch/growth -- rises at an angle
    "Lightbulb",  # idea/emphasis -- pulses
    "Globe", "TrendingUp", "Target", "ShieldCheck", "Cloud", "Smartphone", "Laptop", "Database", "Zap",  # gentle float
    "Store", "Factory", "Handshake", "Warehouse", "Users",  # business/automotive roles -- also gentle float
)
LAYOUTS = ("center", "stack", "split", "row")
TRANSITION_TYPES = ("none", "fade", "slide", "wipe", "flip")

# Shared AWS/GCP/Azure service icon catalog (see ContentAgents/icons/) --
# same shared source ppt_creator's CLOUD_ICON_CATALOG reads, just resolved
# as bare service names per provider here (video_creator's "brandIcon"
# element carries "provider" and "icon" as separate fields, unlike
# ppt_creator's single "<provider>:<service>" string) -- this dict is only
# used for defensive validation (see _coerce_element); the actual SVGs are
# read by Remotion from remotion_project/public/icons/ (synced by
# ContentAgents/icons/sync_to_video_creator.py), not from this path.
SHARED_ICONS_DIR = Path(__file__).resolve().parent.parent / "icons"
try:
    BRAND_ICON_CATALOG = json.loads((SHARED_ICONS_DIR / "catalog.json").read_text(encoding="utf-8"))
except (FileNotFoundError, json.JSONDecodeError):
    BRAND_ICON_CATALOG = {}

# Deliberately NOT a bundled catalog like ICON_NAMES/BRAND_ICON_CATALOG --
# this kit never sources/downloads animated GIFs itself (most "cool" GIFs
# online are memes/copyrighted footage with no clear license for embedding
# in business content). This folder is empty until the USER drops their own
# properly-licensed .gif files into it (see gifs/README.md); the catalog is
# whatever's actually there at request time, discovered fresh each call.
GIFS_DIR = Path(__file__).resolve().parent / "gifs"
PUBLIC_GIFS_DIR = REMOTION_PROJECT_DIR / "public" / "gifs"


def _available_gif_names() -> list[str]:
    if not GIFS_DIR.is_dir():
        return []
    return sorted(p.stem for p in GIFS_DIR.glob("*.gif"))


def _sync_gifs() -> None:
    """Stages whatever .gif files currently sit in GIFS_DIR into
    remotion_project/public/gifs/ -- Remotion can only serve files from
    inside its own public/ dir via staticFile(), same reason the shared
    icon SVGs get synced there (see ContentAgents/icons/
    sync_to_video_creator.py). Cheap enough (a handful of files at most) to
    just re-run at the start of every generate() call instead of requiring
    a separate manual sync step the user would have to remember."""
    if not GIFS_DIR.is_dir():
        return
    PUBLIC_GIFS_DIR.mkdir(parents=True, exist_ok=True)
    for gif_file in GIFS_DIR.glob("*.gif"):
        dest = PUBLIC_GIFS_DIR / gif_file.name
        if dest.exists():
            dest.chmod(0o666)  # OneDrive can mark a previously-synced file read-only
        shutil.copy(gif_file, dest)


def _is_valid_node_icon(icon) -> bool:
    """A diagramFlow node's icon is either a plain ICON_NAMES entry or a
    "<provider>:<service>" cloud icon (e.g. "aws:ec2") -- the one place a
    generic-icon element also accepts the cloud catalog, since a flow chain
    naturally mixes several service icons in one visual object and there's
    no separate "flow of brand icons" element type."""
    if not isinstance(icon, str):
        return False
    if icon in ICON_NAMES:
        return True
    if ":" in icon:
        provider, service = icon.split(":", 1)
        return service in BRAND_ICON_CATALOG.get(provider, {})
    return False
# Windows' own built-in SAPI5 voices (via pyttsx3) -- fully offline, no
# cloud TTS service, no API key, no cost. Matched by substring against
# whatever pyttsx3.getProperty("voices") actually reports on this machine.
VOICES = ("David", "Hazel", "Zira")
NARRATION_DIR_NAME = "narration"  # subfolder of remotion_project/public/ -- see synthesize_narration

FPS = 30
DEFAULT_DURATION = 90  # frames, 3s @ 30fps -- fallback for a scene missing its own duration
MIN_DURATION = 45  # 1.5s -- below this a scene is on/off screen too fast to read (schema.ts itself rejects <30)
# Must match schema.ts's TRANSITION_DEFAULT_FRAMES -- the default overlap a
# scene's own transitionIn eats from the two scenes it sits between, used to
# estimate the REAL rendered length the same way schema.ts's totalDuration()
# does (see _total_duration below).
TRANSITION_DEFAULT_FRAMES = 18
# Used when the brief states no target length at all (see _scene_cap) --
# matches the system prompt's own untargeted "4-8 scenes" guidance range.
DEFAULT_MAX_SCENES = 24
MAX_SCENES_CEILING = 180
# Render cost is fundamentally PER-FRAME (real Chromium work: layout, CSS
# filters, screenshot capture), not per-scene -- a video with fewer, LONGER
# scenes needs just as much render time as one with many short scenes at
# the same total duration. Scaling this off scene COUNT (the previous
# design) starved a real 2-minute/18-scene request of enough time (it got
# capped at 1080s = 18 scenes * 60s, and was killed short of finishing) even
# though the actual bottleneck -- 3600 frames at ~0.3s/frame measured on
# this machine -- needed closer to 1100-1200s. PER_FRAME below has real
# margin over that measurement for slower machines/heavier scenes.
RENDER_TIMEOUT_SECONDS_PER_FRAME = 0.6
RENDER_TIMEOUT_SECONDS_MIN = 300
RENDER_TIMEOUT_SECONDS_CEILING = 3600
# The critique-loop call (write storyboard -> render keyframe stills -> view
# -> revise) takes real wall-clock time beyond just one LLM turn. A real
# 8-scene/45s video with MAX_CRITIQUE_PASSES=3 took 25-30+ minutes in
# practice (each pass re-renders EVERY scene's keyframes and re-views every
# still -- the cost is multiplicative per pass, not additive) -- far past
# what's acceptable for a live request. Cut to exactly ONE pass: still a
# real self-review (write once, render+view once, revise once if needed),
# just not open-ended iteration. Timeout tightened to match -- this budget
# assumes 1 pass, not 3.
DIRECTOR_TIMEOUT_SECONDS_PER_SCENE = 60
DIRECTOR_TIMEOUT_SECONDS_MIN = 480
DIRECTOR_TIMEOUT_SECONDS_CEILING = 1500
# Repeated in the prompt as an instruction, not something Python can enforce
# from outside a single run_claude() call (it returns only the final result,
# not a transcript of every Bash/Read call Claude made) -- the real hard
# stop against an infinite loop is DIRECTOR_TIMEOUT_SECONDS_* above.
MAX_CRITIQUE_PASSES = 1


def _scene_cap(target_frames: int | None) -> int:
    """How many scenes validate_storyboard will keep. No detected target
    length -> the same fixed default as always. A detected target length
    scales the cap up so a long request doesn't get silently truncated back
    down to a short video -- bounded by MAX_SCENES_CEILING regardless."""
    if not target_frames:
        return DEFAULT_MAX_SCENES
    # ~90 frames/scene is a rough average across the primitive mix; +20%
    # buffer for scenes that need to run a bit longer (e.g. a staggerList
    # with 5 items, or a diagramFlow with several nodes).
    estimated = -(-target_frames // 90 * 12 // 10)  # ceil(target_frames/90 * 1.2) without importing math
    return min(MAX_SCENES_CEILING, max(DEFAULT_MAX_SCENES, estimated))


def _render_timeout_seconds(total_frames: int) -> int:
    return min(RENDER_TIMEOUT_SECONDS_CEILING, max(RENDER_TIMEOUT_SECONDS_MIN, round(total_frames * RENDER_TIMEOUT_SECONDS_PER_FRAME)))


def _director_timeout_seconds(target_frames: int | None) -> int:
    scenes_estimate = _scene_cap(target_frames) if target_frames else 6
    return min(DIRECTOR_TIMEOUT_SECONDS_CEILING, max(DIRECTOR_TIMEOUT_SECONDS_MIN, scenes_estimate * DIRECTOR_TIMEOUT_SECONDS_PER_SCENE))


# Detects a stated target length in the brief (e.g. "a 1 minute video", "30
# seconds", "a minute long") so it can be handed to Claude as an exact frame
# count instead of a vague "make it about X long".
_DURATION_RE = re.compile(r"\b(\d+(?:\.\d+)?)[\s-]*(seconds?|secs?|minutes?|mins?)\b", re.IGNORECASE)


def _detect_target_seconds(brief: str) -> float | None:
    m = _DURATION_RE.search(brief)
    if m:
        value = float(m.group(1))
        return value * 60 if m.group(2).lower().startswith("min") else value
    if re.search(r"\bhalf an?\s+minute\b", brief, re.IGNORECASE):
        return 30.0
    if re.search(r"\ba\s+minute\b", brief, re.IGNORECASE):
        return 60.0
    return None


SYSTEM_PROMPT = """You are the Video Creator's director. You have Bash, Read,
and Write tool access for THIS call -- use them for real, following the
workflow below exactly. The brief given to you below is already complete;
do not ask anyone anything.

You are directing a short motion-designed video built entirely from a fixed
library of primitives (the "storyboard" system) -- you choose story, pacing,
and which primitive fits each beat. A hand-written renderer turns your JSON
into the actual video deterministically. Never write animation code -- only
ever fill the schema below.

## Workflow (follow every step, in order)

1. Plan the story as 4-8 beats (one idea per beat = one scene), matching the
   brief and any target length given below.
2. Write your storyboard as JSON to the exact STORYBOARD PATH given below
   (create it, and any parent directory that doesn't already exist), using
   the schema and primitives documented below.
3. Render critique stills ONCE with Bash, from the Remotion project (your
   working directory is already set there):
       node scripts/keyframes.mjs <STORYBOARD PATH>
   This writes 2 PNG stills per scene into out/keyframes/.
4. Read every still it wrote (Read supports viewing images) and check the
   critique checklist below. You get exactly ONE render -- fix whatever
   you can identify directly in the JSON at the STORYBOARD PATH without
   re-rendering to confirm (there's no time budget for a second pass), then
   move on. Only re-run step 3 if you genuinely cannot judge the fix's
   correctness without seeing it (rare) -- never as a routine second look.
5. Finish by replying with a short confirmation only, e.g. {"ready": true}.
   The FILE at the STORYBOARD PATH -- not your reply text -- is what
   actually gets rendered, so it must already be the final, fully revised
   version before you stop.

Never skip steps 3-4. Most problems (overflow, crowding, ghosting,
wrapping) are only visible in a rendered frame, not in the raw JSON.

## Storyboard schema

{
  "fps": 30, "width": 1280, "height": 720,
  "grain": false,
  "theme": {"accent": "#...", "accent2": "#..."},
  "scenes": [
    {
      "id": "<unique-slug, e.g. intro>",
      "durationInFrames": 120,
      "layout": "center" | "stack" | "split" | "row",
      "camera": {"from": 1, "to": 1.07, "driftX": 0, "driftY": -20, "rotate": 0} | false,
      "motionBlur": false,
      "transitionIn": {"type": "fade" | "slide" | "wipe" | "flip" | "none",
                        "direction": "from-right", "durationInFrames": 18},
      "elements": [ /* 1+ primitives, see below */ ]
    }
  ]
}

"theme" is optional -- omit it to use the kit's own default palette, or
override just accent/accent2 for a brand moment. Every scene automatically
gets a themed, softly animated background -- never add your own background
color or a "style" field, there isn't one.

"fps"/"width"/"height"/"grain" are all optional -- omit them to get the
defaults (30fps, 1280x720, no grain), which is right for almost every
request. Rendering is real per-frame Chromium work, and both a larger
canvas and grain (a per-frame noise filter) cost real time proportional to
pixel area -- confirmed directly, grain alone adds roughly 40% to render
time. Only set "width"/"height" higher, or "grain": true, if the brief
specifically needs a large/cinematic deliverable and says so; never as a
routine default.

Layouts: "center" stacks elements in a centred column (most scenes). "stack"
is a left-aligned column. "row" puts elements side by side (good for 2-3
stats). "split" puts the first element on the left half and the rest
stacked on the right.

## Primitives (put ONLY these inside "elements")

All "delay" values are frames from the start of the scene.

- "kineticTitle": any headline or line of text. {"type": "kineticTitle",
  "text": "...", "splitBy": "word"|"char", "effect": "rise"|"blur"|"scale",
  "size": "hero"|"title"|"heading"|"body"|"caption", "color":
  "ink"|"accent"|"accent2"|"muted", "preset": "snappy"|"gentle"|"bouncy"|
  "heavy", "stagger": "tight"|"normal"|"loose", "align": "left"|"center",
  "delay": N}
- "staggerList": 2-6 short points entering one after another. {"type":
  "staggerList", "items": ["...", ...], "highlight": <index to emphasize>,
  "stagger": ..., "preset": ..., "delay": N}
- "countUp": one hero number counting up. {"type": "countUp", "to": N,
  "from": N, "prefix": "...", "suffix": "...", "decimals": N, "label":
  "...", "color": "ink"|"accent"|"accent2", "durationInFrames": N,
  "delay": N}
- "chartBuild": a comparison or growth chart, 2-8 bars. {"type":
  "chartBuild", "data": [{"label": "...", "value": N}, ...], "highlight":
  <index>, "valueSuffix": "...", "stagger": ..., "delay": N}
- "drawPath": a flow/journey/trend line drawing itself in. {"type":
  "drawPath", "d": "<SVG path data in a 1000x600 box>", "nodes": [{"at":
  0-1, "label": "..."}, ...], "color": "accent"|"accent2"|"ink",
  "durationInFrames": N, "delay": N}
- "gsapTextBurst": one punchy closing line, <=3 words. {"type":
  "gsapTextBurst", "text": "...", "underline": true|false, "delay": N}
- "peopleCrowd": a small illustrated crowd or single mascot for a warm,
  human beat -- use sparingly (at most 1-2 per video), never as the main
  way to deliver information. {"type": "peopleCrowd", "count": 1-8, "pose":
  "wave"|"standing" (only matters when count is 1), "heading": "..."
  (optional), "caption": "..." (optional), "delay": N}
- "iconMotion": a single animated concept icon -- use when a concrete
  visual noun makes the point better than more text; sparingly, at most 1-2
  per video. {"type": "iconMotion", "icon": "<name from the list below>",
  "heading": "..." (optional), "caption": "..." (optional), "color":
  "ink"|"accent"|"accent2", "delay": N}. "icon" MUST be exactly one of:
  Settings, Cog, Wrench, RefreshCw (process/mechanism), Car, Truck, Bus,
  Bike (automotive/transport/delivery), Rocket (launch/growth/ambition),
  Lightbulb (an idea), Globe, TrendingUp, Target, ShieldCheck, Cloud,
  Smartphone, Laptop, Database, Zap (general concepts), Store (dealership/
  retail location), Factory (OEM/manufacturer), Handshake (supplier/
  partnership), Warehouse (parts/supply chain/inventory), Users (owners/
  customers as a group). Never invent a name outside this list.
- "diagramFlow": a left-to-right chain of 2-5 icon+label nodes connected by
  drawn-in arrows -- THIS is the primitive for a process, sequence of
  steps, pipeline, or the players in a flow (e.g. "how a referral program
  works," "the steps in our onboarding") -- prefer it over "staggerList"
  for that kind of content. {"type": "diagramFlow", "nodes": [{"label":
  "...", "icon": "<name from the icon list above>", "caption": "..."
  (optional)}, ...] (2-5 nodes), "heading": "..." (optional), "delay": N}.
  Keep each "label" to 2-4 words. Each node's "icon" is either a name from
  the icon list above (same constraint as "iconMotion" -- never invent one),
  OR "<provider>:<service>" (e.g. "aws:ec2") if the brief is about a
  specific cloud provider's services -- read ContentAgents/icons/
  catalog.json for valid service names, exactly as described for
  "brandIcon" below. When the brief IS about a specific provider, use that
  provider's real icons for every node in the chain, not a mix of real and
  generic ones -- a flow of AWS services should show AWS icons throughout,
  including in a "how they work together" summary, not just in each
  service's own standalone scene.
- "brandIcon": a real AWS/GCP/Azure service glyph -- use this INSTEAD OF
  "iconMotion" whenever the brief is actually about a specific cloud
  provider's services or architecture (never for a generic
  process/mechanism/vehicle concept -- that's still "iconMotion").
  {"type": "brandIcon", "provider": "aws"|"gcp"|"azure", "icon": "<a
  service name for that provider>", "heading": "..." (optional), "caption":
  "..." (optional), "delay": N}. Before using this, Read the file
  ContentAgents/icons/catalog.json (a sibling of this project's own
  directory, i.e. ../icons/catalog.json from your working directory) --
  its top-level keys are "aws"/"gcp"/"azure", and each one's keys are the
  only valid "icon" names for that provider. Never invent a service name;
  if the exact service isn't in the catalog, pick the closest real one
  that IS there rather than guessing a name. Never mix two different
  providers' icons in the same video unless the brief explicitly compares
  providers.
- "animatedGif": plays a real animated GIF the user has supplied (never one
  you'd invent or assume exists). {"type": "animatedGif", "name": "<name
  from AVAILABLE GIFS below>", "heading": "..." (optional), "caption": "..."
  (optional), "delay": N}. If AVAILABLE GIFS below is empty, or nothing in
  it actually fits this beat, do NOT use this primitive at all -- fall back
  to a regular primitive instead. Never invent a name.

Sizes: hero 132px, title 88px, heading 60px, body 40px, caption 28px.
Spring presets: "snappy" (default -- confident, tiny overshoot), "gentle"
(no overshoot -- backgrounds, large surfaces), "bouncy" (playful overshoot
-- one hero moment per video at most), "heavy" (weighty, slow start --
big numbers, charts, closing titles).

## Motion rules

- Choreograph, don't dump. Elements in a scene enter in reading order.
  Space element delays 12-30 frames apart. Nothing important appears at
  delay 0 -- start at 4-10 so the scene's own transition finishes first.
- Hold the frame. After the last element settles, hold >=30 frames before
  the scene ends. Rough reading time: text words / 3 = seconds of hold.
- Vary transitions with purpose. "fade" for calm continuity, "slide" for
  moving to the next item in a sequence, "wipe" for a topic change, "flip"
  for a reveal or finale. Don't use the same transition three times running.
- Alternate camera direction. Push in on one scene ("from":1,"to":1.07),
  pull out on the next ("from":1.05,"to":1), or drift sideways. Use
  "camera": false for dense data scenes (chartBuild/diagramFlow) where
  movement hurts legibility.
- Motion blur is expensive to render (it samples each frame multiple times)
  and rarely adds enough to justify that cost -- default to "motionBlur":
  false (or omit it) on every scene. Only set it true for a single hero
  gsapTextBurst/fast-slide moment if the brief specifically calls for a
  cinematic feel, never as a routine choice, and never on a scene with
  countUp or chartBuild -- changing digits/bars ghost.
- One accent moment per scene -- use "highlight" or accent2 on the single
  thing the viewer should remember, not several.
- Effects by tone: corporate/calm -> "rise" + "snappy"/"gentle". Cinematic
  -> "blur" + "heavy". Energetic/social -> "scale" + "bouncy", splitBy:
  "char".

## Keyframe critique checklist (check every still from step 3)

- Text is fully inside the frame with real margin. Nothing clips or
  overflows its column.
- Headlines don't leave a single orphaned word on the last line -- shorten
  the text or drop one size if they do.
- In the "hold" still, every element has finished animating and is legible.
- The accent colour is on one thing only.
- No ghosted/doubled text (a motion blur problem).
- The frame isn't crowded -- more than ~4 elements or ~25 words on screen
  means split the scene into two.

## Narration

If narration is ON for this request (a NARRATION line will say so below),
write a "narration" field directly on every scene object that should have a
spoken line -- a sibling of "id"/"durationInFrames"/"elements", e.g.
{"id": "...", "durationInFrames": 120, "narration": "...", "elements": [...]}.
Write it the way a person would actually SAY it out loud -- fuller and more
natural than the on-screen text, not a verbatim readout of it (e.g. an
on-screen countUp might show "$4.8M" while the narration says "That's four
point eight million dollars in savings this year"). Omit "narration"
entirely on a scene that doesn't need a spoken line (e.g. a fast
title-only beat). If narration is OFF for this request, never write this
field at all.

## Rules

- Pick 4-8 scenes for a well-paced story matching the brief -- typically an
  opening kineticTitle beat, one or more staggerList/countUp/chartBuild/
  diagramFlow beats with the actual content, optionally one peopleCrowd
  beat for a human touch, and a closing gsapTextBurst or kineticTitle beat.
  EXCEPTION: if a TARGET LENGTH line appears below, ignore the "4-8 scenes"
  guideline and instead add MORE scenes (never make any single scene
  unnaturally long) until scene durations sum to approximately that length.
- durationInFrames at 30fps: a title-only scene usually needs 60-100 frames
  (2-3s); a scene built around a staggerList of N items needs roughly
  60 + 20*N frames; a countUp/chartBuild scene usually needs 90-150 frames;
  a diagramFlow scene needs roughly 60 + 45*len(nodes) frames. Never go
  below 60 frames for any scene -- the schema itself rejects anything under
  30, but faster than 60 is too quick to read anyway.
- CRITICAL -- never fabricate specific numbers, names, or claims that
  aren't in the brief or connected reference content. If the brief gives
  real figures, use them exactly (e.g. in a "countUp" or "chartBuild"). If
  it's a general/creative brief with no real data, that's fine -- just
  don't invent fake statistics and present them as real.
"""

# Reused by NARRATIVE_EDIT_SYSTEM_PROMPT below -- schema/primitives/motion
# rules/narration/rules are exactly as valid for a targeted JSON update as
# for directing from scratch; only the tool-using critique-loop workflow
# and the keyframe-viewing checklist are specific to that call, not this one.
_schema_start = SYSTEM_PROMPT.index("## Storyboard schema")
_checklist_start = SYSTEM_PROMPT.index("## Keyframe critique checklist")
_narration_start = SYSTEM_PROMPT.index("## Narration")
SHARED_SCHEMA_DOCS = SYSTEM_PROMPT[_schema_start:_checklist_start] + SYSTEM_PROMPT[_narration_start:]

NARRATIVE_EDIT_SYSTEM_PROMPT = """You are updating an EXISTING storyboard for
a motion-designed video, given its CURRENT JSON and a plain-English
narrative describing what it should say/show now (that narrative was
generated FROM the current JSON, then hand-edited by a person -- it is the
source of truth for what changed). Match each narrative scene to the JSON
scene with the same "(id: ...)" marker. If the narrative describes a scene
whose id doesn't exist yet, add a new scene for it. If a scene's id from
the JSON is missing from the narrative entirely, remove that scene. For
every scene that DOES still exist in both, update only what the narrative
actually changed (text, numbers, labels, icons) -- preserve everything the
narrative didn't mention (durationInFrames, layout, camera, motionBlur,
transitionIn, theme, delay, styling choices like preset/color/effect)
exactly as it already is in the current JSON. This is a targeted edit, not
a fresh draft -- never regenerate scenes the narrative left alone.

Output ONLY the updated storyboard JSON, no prose, matching this exact
schema (never invent an element type or icon name outside what's listed
here):
""" + SHARED_SCHEMA_DOCS


def _describe_element(el: dict) -> str:
    """One human-readable line describing a single element -- the building
    block of storyboard_to_narrative() below. Deliberately plain language,
    not field names -- meant to be edited by someone who's never seen the
    JSON, not machine-parsed back (the reverse direction goes through
    Claude, via NARRATIVE_EDIT_SYSTEM_PROMPT, precisely because free-text
    edits need real language understanding to map back onto the schema)."""
    etype = el.get("type")
    if etype == "kineticTitle":
        return f'Title: "{el.get("text", "")}"'
    if etype == "staggerList":
        items = "; ".join(f'"{i}"' for i in el.get("items", []))
        return f"Bullet points: {items}"
    if etype == "countUp":
        prefix, suffix = el.get("prefix", ""), el.get("suffix", "")
        label = f' ("{el["label"]}")' if el.get("label") else ""
        return f'Big number: {prefix}{el.get("to")}{suffix}{label}'
    if etype == "chartBuild":
        parts = ", ".join(f'{d.get("label")}={d.get("value")}' for d in el.get("data", []))
        return f"Chart: {parts}"
    if etype == "drawPath":
        nodes = el.get("nodes") or []
        if nodes:
            return "Drawn-in path/trend line, labeled: " + ", ".join(f'"{n.get("label")}"' for n in nodes)
        return "Drawn-in path/trend line (no labels)"
    if etype == "gsapTextBurst":
        return f'Punchy closing line: "{el.get("text", "")}"'
    if etype == "peopleCrowd":
        bits = [f'{el.get("count", 3)} illustrated people']
        if el.get("heading"):
            bits.append(f'heading "{el["heading"]}"')
        if el.get("caption"):
            bits.append(f'caption "{el["caption"]}"')
        return "; ".join(bits)
    if etype == "iconMotion":
        heading = f' -- "{el["heading"]}"' if el.get("heading") else ""
        return f'Icon ({el.get("icon")}){heading}'
    if etype == "brandIcon":
        heading = f' -- "{el["heading"]}"' if el.get("heading") else ""
        return f'{(el.get("provider") or "").upper()} icon ({el.get("icon")}){heading}'
    if etype == "diagramFlow":
        chain = " -> ".join(f'{n.get("label")} ({n.get("icon")})' for n in el.get("nodes", []))
        heading = f'"{el["heading"]}": ' if el.get("heading") else ""
        return f"Process flow: {heading}{chain}"
    if etype == "animatedGif":
        heading = f' -- "{el["heading"]}"' if el.get("heading") else ""
        return f'Animated GIF ({el.get("name")}){heading}'
    return f"({etype})"


def storyboard_to_narrative(storyboard: dict) -> str:
    """The read side of the narrative view: a deterministic, no-LLM-needed
    plain-English description of exactly what's in the storyboard right
    now, one block per scene. The "(id: ...)" marker is load-bearing --
    NARRATIVE_EDIT_SYSTEM_PROMPT matches edited scenes back to the JSON by
    it, so never strip it out when showing this to a user to edit."""
    lines = []
    for i, scene in enumerate(storyboard.get("scenes", []), start=1):
        seconds = scene.get("durationInFrames", 0) / FPS
        lines.append(f'Scene {i} (id: {scene.get("id")}, ~{seconds:.1f}s):')
        for el in scene.get("elements", []):
            lines.append(f"  - {_describe_element(el)}")
        if scene.get("narration"):
            lines.append(f'  Narration (spoken aloud): "{scene["narration"]}"')
        lines.append("")
    return "\n".join(lines).strip()


def apply_narrative(storyboard: dict, narrative: str, on_progress: ProgressFn | None = None) -> dict:
    """The write side: turns a hand-edited narrative back into an updated
    storyboard JSON via one targeted, tool-less LLM call -- NOT a critique
    loop (no keyframe rendering/viewing here), so meaningfully faster than
    directing from scratch. Returns the validated, updated storyboard;
    caller is responsible for re-rendering it (see server.py's
    library_rerender_video, reused unchanged for this)."""
    if on_progress:
        on_progress("Updating the storyboard from your edited narrative...")
    prompt = (
        f"CURRENT STORYBOARD JSON:\n{json.dumps(storyboard)}\n\n"
        f"EDITED NARRATIVE:\n{narrative}\n\n"
        "Produce the updated storyboard JSON described in your instructions."
    )
    result = run_claude(prompt, system_prompt=NARRATIVE_EDIT_SYSTEM_PROMPT, allowed_tools=[])
    return validate_storyboard(extract_json(result["result"]))


def _coerce_element(raw: dict) -> dict | None:
    """Defensive validation before this ever reaches Remotion -- mirrors the
    same "never trust the LLM's output blindly" posture the old per-scene
    _coerce_scene always had, just against the richer element schema. An
    unrecognized element type or one missing its required content is
    dropped rather than handed to the renderer; every OTHER optional field
    is passed through untouched and left for Remotion's own zod parse (the
    exact, final gate) to catch, the same light-touch defensive net as
    before -- this pass only guards against structurally missing content."""
    if not isinstance(raw, dict):
        return None
    etype = raw.get("type")
    if etype not in ELEMENT_TYPES:
        return None
    out: dict = {"type": etype}
    if isinstance(raw.get("delay"), (int, float)):
        out["delay"] = raw["delay"]

    if etype == "kineticTitle":
        if not raw.get("text"):
            return None
        out["text"] = str(raw["text"])
        for k in ("splitBy", "effect", "size", "weight", "preset", "stagger", "color", "align"):
            if k in raw:
                out[k] = raw[k]
        return out
    if etype == "staggerList":
        items = [str(i) for i in (raw.get("items") or []) if str(i).strip()]
        if not items:
            return None
        out["items"] = items[:6]
        for k in ("preset", "stagger", "highlight"):
            if k in raw:
                out[k] = raw[k]
        return out
    if etype == "countUp":
        if not isinstance(raw.get("to"), (int, float)):
            return None
        out["to"] = raw["to"]
        for k in ("from", "label", "prefix", "suffix", "decimals", "durationInFrames", "color"):
            if k in raw:
                out[k] = raw[k]
        return out
    if etype == "chartBuild":
        data = [d for d in (raw.get("data") or [])
                if isinstance(d, dict) and d.get("label") and isinstance(d.get("value"), (int, float))]
        if len(data) < 2:
            return None
        out["data"] = data[:8]
        for k in ("highlight", "stagger", "valueSuffix"):
            if k in raw:
                out[k] = raw[k]
        return out
    if etype == "drawPath":
        if not raw.get("d"):
            return None
        out["d"] = str(raw["d"])
        for k in ("durationInFrames", "strokeWidth", "color", "showHead", "nodes"):
            if k in raw:
                out[k] = raw[k]
        return out
    if etype == "gsapTextBurst":
        if not raw.get("text"):
            return None
        out["text"] = str(raw["text"])[:40]
        for k in ("size", "underline"):
            if k in raw:
                out[k] = raw[k]
        return out
    if etype == "peopleCrowd":
        count = raw.get("count")
        out["count"] = max(1, min(int(count), 8)) if isinstance(count, (int, float)) else 3
        for k in ("pose", "heading", "caption", "preset"):
            if k in raw:
                out[k] = raw[k]
        return out
    if etype == "iconMotion":
        if raw.get("icon") not in ICON_NAMES:
            return None
        out["icon"] = raw["icon"]
        for k in ("heading", "caption", "durationInFrames", "color"):
            if k in raw:
                out[k] = raw[k]
        return out
    if etype == "diagramFlow":
        nodes = []
        for n in (raw.get("nodes") or []):
            if not isinstance(n, dict) or not n.get("label") or not _is_valid_node_icon(n.get("icon")):
                continue
            node = {"label": str(n["label"]), "icon": n["icon"]}
            if n.get("caption"):
                node["caption"] = str(n["caption"])
            nodes.append(node)
        if len(nodes) < 2:
            return None
        out["nodes"] = nodes[:5]
        if raw.get("heading"):
            out["heading"] = str(raw["heading"])
        return out
    if etype == "brandIcon":
        provider = raw.get("provider")
        icon = raw.get("icon")
        if provider not in BRAND_ICON_CATALOG or icon not in BRAND_ICON_CATALOG.get(provider, {}):
            return None
        out["provider"] = provider
        out["icon"] = icon
        for k in ("heading", "caption"):
            if raw.get(k):
                out[k] = str(raw[k])
        return out
    if etype == "animatedGif":
        name = raw.get("name")
        if not isinstance(name, str) or name not in _available_gif_names():
            return None
        out["name"] = name
        for k in ("heading", "caption"):
            if raw.get(k):
                out[k] = str(raw[k])
        return out
    return None


def _coerce_scene(raw: dict, used_ids: set) -> dict | None:
    if not isinstance(raw, dict):
        return None
    elements = [e for e in (_coerce_element(r) for r in (raw.get("elements") or [])) if e]
    if not elements:
        return None
    duration = raw.get("durationInFrames")
    duration = int(duration) if isinstance(duration, (int, float)) and duration > 0 else DEFAULT_DURATION
    duration = max(duration, MIN_DURATION)
    scene_id = str(raw.get("id") or f"scene-{len(used_ids) + 1}")
    if scene_id in used_ids:
        scene_id = f"{scene_id}-{len(used_ids) + 1}"  # schema.ts's scene ids must be unique (used as React keys + keyframe filenames)
    used_ids.add(scene_id)
    scene: dict = {"id": scene_id, "durationInFrames": duration, "elements": elements}
    if raw.get("layout") in LAYOUTS:
        scene["layout"] = raw["layout"]
    if raw.get("camera") is False:
        scene["camera"] = False
    elif isinstance(raw.get("camera"), dict):
        scene["camera"] = raw["camera"]
    if isinstance(raw.get("motionBlur"), bool):
        scene["motionBlur"] = raw["motionBlur"]
    ti = raw.get("transitionIn")
    if isinstance(ti, dict) and ti.get("type") in TRANSITION_TYPES:
        scene["transitionIn"] = ti
    if raw.get("narration"):
        scene["narration"] = str(raw["narration"]).strip()
    return scene


def _total_duration(scenes: list[dict]) -> int:
    """Mirrors schema.ts's own totalDuration() -- each scene's transitionIn
    overlaps the scene before it, so the real rendered length is shorter
    than the raw sum of durationInFrames by one overlap per cut."""
    total = 0
    for i, s in enumerate(scenes):
        tf = 0
        if i > 0:
            ti = s.get("transitionIn")
            if ti and ti.get("type") != "none":
                tf = int(ti.get("durationInFrames") or TRANSITION_DEFAULT_FRAMES)
        total += s["durationInFrames"] - tf
    return max(total, 1)


def validate_storyboard(raw: dict, target_frames: int | None = None, enforce_length: bool = True) -> dict:
    """Coerces/validates whatever the critique loop wrote into something
    safe to render -- always succeeds (falls back to a single title-only
    scene if every scene was somehow malformed), so a render is never
    silently skipped just because one field needs fixing up.

    `enforce_length=False` (used by generate_series's per-part planning)
    skips the target-length stretch correction -- there, a part ending a
    bit early or late at a natural stopping point IS the intended behavior."""
    used_ids: set = set()
    scenes = [s for s in (_coerce_scene(r, used_ids) for r in (raw.get("scenes") or [])) if s]
    if not scenes:
        scenes = [{
            "id": "fallback", "durationInFrames": DEFAULT_DURATION,
            "elements": [{"type": "kineticTitle", "text": raw.get("title") or "Untitled video"}],
        }]
    scenes = scenes[:_scene_cap(target_frames)]

    if target_frames and enforce_length:
        total = _total_duration(scenes)
        if total and target_frames / total > 1.05:
            scale = min(target_frames / total, 1.4)
            for s in scenes:
                s["durationInFrames"] = max(MIN_DURATION, round(s["durationInFrames"] * scale))

    storyboard: dict = {"scenes": scenes}
    if isinstance(raw.get("theme"), dict):
        storyboard["theme"] = raw["theme"]
    if isinstance(raw.get("grain"), bool):
        storyboard["grain"] = raw["grain"]
    for k in ("fps", "width", "height"):
        if isinstance(raw.get(k), (int, float)):
            storyboard[k] = raw[k]
    return storyboard


ProgressFn = Callable[[str], None]


TTS_WORKER = Path(__file__).resolve().parent / "tts_worker.py"
NARRATION_TIMEOUT_SECONDS = 30


def _wav_duration_seconds(path: Path) -> float:
    with contextlib.closing(wave.open(str(path), "rb")) as wf:
        return wf.getnframes() / wf.getframerate()


def synthesize_narration(scenes: list[dict], voice: str, on_progress: ProgressFn | None = None) -> list[Path]:
    """Generates one WAV per scene that has a "narration" line, via the OS's
    own offline TTS (pyttsx3/SAPI5 on Windows) -- no cloud call, no API key.
    Mutates each scene in place: adds "narrationFile" (the filename
    StoryboardVideo.tsx's <Audio> plays, resolved via Remotion's
    staticFile()) and extends durationInFrames so the scene stays on screen
    at least as long as the narration takes to say plus a short buffer --
    never shorter than what was already planned, since a target-length fit
    (validate_storyboard) already ran before this and shouldn't be undone.

    Each scene's synthesis runs in its own tts_worker.py subprocess rather
    than calling pyttsx3 directly here -- SAPI5/COM has strict thread-
    affinity requirements on Windows, and this function is called from a
    background worker thread whenever a video renders through a live
    server, not just a plain top-level script; calling pyttsx3 directly
    from that thread reliably hangs forever with no error and no way to
    time out. A subprocess always gets a fresh process with its own real
    main thread, sidestepping that entirely, and lets a real timeout be
    enforced below -- a scene whose narration fails to synthesize in time
    is skipped (rendered silently) rather than hanging the whole video.

    Returns the audio file paths written, so the caller can delete them
    after rendering -- they're per-render temp assets staged into
    remotion_project/public/ for Remotion to read, not permanent files."""
    audio_dir = REMOTION_PROJECT_DIR / "public" / NARRATION_DIR_NAME
    audio_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    narrated = [s for s in scenes if s.get("narration")]
    if narrated and on_progress:
        on_progress(f"Recording narration for {len(narrated)} scene(s)...")
    for scene in scenes:
        text = scene.get("narration")
        if not text:
            continue
        out_path = audio_dir / f"narration_{uuid.uuid4().hex[:10]}.wav"
        text_path = audio_dir / f".tts_text_{uuid.uuid4().hex[:8]}.txt"
        text_path.write_text(text, encoding="utf-8")
        try:
            subprocess.run(
                [sys.executable, str(TTS_WORKER), str(text_path), voice, str(out_path)],
                timeout=NARRATION_TIMEOUT_SECONDS, capture_output=True, text=True,
            )
        except subprocess.TimeoutExpired:
            continue
        finally:
            text_path.unlink(missing_ok=True)
        if not out_path.exists():
            continue
        written.append(out_path)
        needed_frames = round(_wav_duration_seconds(out_path) * FPS) + 20
        scene["durationInFrames"] = max(scene["durationInFrames"], needed_frames)
        scene["narrationFile"] = out_path.name
    return written


def ensure_remotion_installed(on_progress: ProgressFn | None = None):
    if REMOTION_CLI.exists():
        return
    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError("npm was not found on PATH -- Node.js/npm must be installed to render videos.")
    if on_progress:
        on_progress("Setting up the video renderer for the first time (installing dependencies)...")
    # shell=True here is safe -- the command is a fixed literal string with
    # no interpolated/untrusted input; it's only needed because Windows npm
    # ships as npm.cmd, which Python's subprocess can't exec directly
    # without a shell.
    subprocess.run("npm install", cwd=REMOTION_PROJECT_DIR, shell=True, check=True,
                    capture_output=True, text=True)


def _direct_storyboard(brief: str, storyboard_path: Path, target_frames: int | None, voice: str | None,
                        context: str | None, on_progress: ProgressFn | None, extra_note: str = "") -> dict:
    """The critique-loop call: Claude gets Bash/Read/Write access (never
    used elsewhere in this codebase's headless agents, see this file's own
    module docstring) to write the storyboard, render+view keyframe stills,
    and revise before finishing. Returns the RAW dict read back off
    `storyboard_path` -- not yet validated (see validate_storyboard), and
    may still carry a top-level "isFinal" key if `extra_note` asked for one
    (see generate_series)."""
    ensure_remotion_installed(on_progress)
    _sync_gifs()
    storyboard_path.unlink(missing_ok=True)
    # Best-effort: avoid stale stills from a previous run being mistaken for
    # this one's own critique pass. Not a real concurrency guard (see
    # module docstring) -- just keeps the common single-request case clean.
    shutil.rmtree(REMOTION_PROJECT_DIR / "out" / "keyframes", ignore_errors=True)

    duration_note = (
        f"\n\nTARGET LENGTH: approximately {target_frames / FPS:.0f} seconds "
        f"({target_frames} frames at {FPS}fps) -- see the scene-count exception in your instructions above."
    ) if target_frames else ""
    narration_note = (
        "\n\nNARRATION: on -- write a \"narration\" field (per your instructions above) on every scene that "
        "should have a spoken line; this video will be read aloud by a text-to-speech voice."
    ) if voice else ""
    gif_names = _available_gif_names()
    gif_note = (
        f"\n\nAVAILABLE GIFS: {', '.join(gif_names)}" if gif_names
        else "\n\nAVAILABLE GIFS: none -- do not use \"animatedGif\" at all for this request."
    )
    prompt = (
        f"BRIEF: {brief}" + duration_note + narration_note + gif_note
        + (f"\n\nREFERENCE CONTENT:\n{context}" if context else "")
        + extra_note
        + f"\n\nSTORYBOARD PATH (write/revise your JSON here -- this exact file is what gets rendered): {storyboard_path}"
        + f"\n\nMAX CRITIQUE PASSES: {MAX_CRITIQUE_PASSES}"
    )
    if on_progress:
        on_progress("Directing the video: writing and critiquing the storyboard...")
    run_claude(
        prompt, system_prompt=SYSTEM_PROMPT,
        allowed_tools=["Bash", "Read", "Write"],
        cwd=str(REMOTION_PROJECT_DIR), timeout=_director_timeout_seconds(target_frames),
    )
    if not storyboard_path.exists():
        raise RuntimeError("The director step finished without writing a storyboard file.")
    try:
        return json.loads(storyboard_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"The director step wrote an invalid storyboard file: {exc}") from exc


def render_video(storyboard: dict, out_path: Path, on_progress: ProgressFn | None = None):
    ensure_remotion_installed(on_progress)
    out_path = out_path.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Must be absolute -- the render subprocess below runs with
    # cwd=REMOTION_PROJECT_DIR, not this process's own cwd, so a relative
    # path here would be resolved against the WRONG directory.
    props_path = out_path.parent / f".video-props-{uuid.uuid4().hex[:8]}.json"
    props_path.write_text(json.dumps(storyboard), encoding="utf-8")

    if on_progress:
        on_progress(f"Rendering {len(storyboard['scenes'])} scene(s)...")
    # Remotion's own default concurrency caps at min(8, cpuCount/2) -- on a
    # machine with more than 16 cores that leaves real parallelism on the
    # table for no reason (confirmed: this machine has 14 cores, default
    # resolved to 7). Use every core explicitly instead of trusting that cap.
    concurrency = os.cpu_count() or 4
    proc = subprocess.Popen(
        ["node", str(REMOTION_CLI), "render", COMPOSITION_ID, str(out_path.resolve()),
         f"--props={props_path}", f"--concurrency={concurrency}"],
        cwd=REMOTION_PROJECT_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
    )
    timed_out = False

    def _kill_on_timeout():
        nonlocal timed_out
        timed_out = True
        # proc.kill() alone only kills the node.exe wrapper on Windows --
        # any headless-Chromium child process it spawned for the render
        # survives as an orphan (Windows doesn't kill child trees on
        # TerminateProcess). taskkill /T kills the whole tree.
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)

    timeout_seconds = _render_timeout_seconds(_total_duration(storyboard["scenes"]))
    timer = threading.Timer(timeout_seconds, _kill_on_timeout)
    timer.start()
    output_lines: list[str] = []
    last_emit = 0.0
    try:
        # Remotion prints a "Rendered X/Y" line roughly per frame and an
        # "Encoded X/Y" line during the ffmpeg pass -- both streamed here
        # (throttled to ~1/sec) so a slow render shows real, live progress.
        for line in proc.stdout:
            line = _ANSI_RE.sub("", line).strip()
            if not line:
                continue
            output_lines.append(line)
            now = time.monotonic()
            if on_progress and (now - last_emit >= 1.0 or line.startswith(("Encoded", "+"))):
                on_progress(line)
                last_emit = now
        proc.wait()
    finally:
        timer.cancel()
        props_path.unlink(missing_ok=True)

    if timed_out:
        raise RuntimeError(f"Video rendering timed out after {timeout_seconds}s.")
    if proc.returncode != 0:
        raise RuntimeError(f"Video rendering failed: {chr(10).join(output_lines[-30:])}")
    if on_progress:
        on_progress("Video rendered.")


def _render_spec(storyboard: dict, out_path: Path, voice: str | None, on_progress: ProgressFn | None) -> None:
    """Shared by generate() and generate_series(): synthesize narration (if
    requested) then render, always cleaning up the per-render narration WAVs
    afterward regardless of whether the render itself succeeded."""
    narration_files: list[Path] = []
    try:
        if voice:
            narration_files = synthesize_narration(storyboard["scenes"], voice, on_progress=on_progress)
        render_video(storyboard, out_path, on_progress=on_progress)
    finally:
        for f in narration_files:
            f.unlink(missing_ok=True)


# How long each part runs in split mode (see generate_series) -- "5 minutes"
# per the feature request, with a tolerance either side so a part can end at
# whatever natural story beat falls closest to that instead of being forced
# to hit the number exactly.
SEGMENT_TARGET_SECONDS = 300
SEGMENT_TOLERANCE_SECONDS = 15
# Safety cap on how many parts generate_series will produce.
MAX_SEGMENTS = 12


def _scene_gist(scene: dict) -> str:
    """One short phrase describing what a scene actually says, for the recap
    text fed into later parts' prompts (see _segment_prompt_note) -- not the
    full scene JSON, just enough for Claude to know what's already been
    covered so it continues the story instead of repeating it."""
    for el in scene.get("elements", []):
        etype = el.get("type")
        if etype in ("kineticTitle", "gsapTextBurst"):
            return el.get("text", "")
        if etype == "staggerList":
            return "; ".join(el.get("items", [])[:2])
        if etype == "countUp":
            return f'{el.get("to")} ({el.get("label") or ""})'
        if etype in ("peopleCrowd", "iconMotion"):
            return el.get("heading") or el.get("caption") or etype
        if etype == "diagramFlow":
            return el.get("heading") or ", ".join(n.get("label", "") for n in el.get("nodes", [])[:3])
    return scene.get("id", "scene")


def _segment_prompt_note(part: int, recap: str) -> str:
    lo, hi = SEGMENT_TARGET_SECONDS - SEGMENT_TOLERANCE_SECONDS, SEGMENT_TARGET_SECONDS + SEGMENT_TOLERANCE_SECONDS
    recap_block = (
        f"\n\nPARTS ALREADY COVERED (do not repeat this content):\n{recap}"
        if recap else "\n\nThis is the FIRST part -- there is no prior content yet."
    )
    return (
        f"\n\nMULTI-PART VIDEO: this is part {part} of a longer video being produced as several separate "
        f"~{SEGMENT_TARGET_SECONDS // 60}-minute video files instead of one long one. Plan roughly "
        f"{SEGMENT_TARGET_SECONDS} seconds ({SEGMENT_TARGET_SECONDS // 60}:00) of NEW content for this part, "
        f"but end at whatever natural stopping point in the story falls closest to that -- anywhere from "
        f"{lo // 60}:{lo % 60:02d} to {hi // 60}:{hi % 60:02d} is completely fine. Never cut a thought off "
        f"mid-way just to hit the length exactly." + recap_block +
        "\n\nAlso add a top-level \"isFinal\": true or false field to the SAME storyboard JSON file "
        "(alongside \"scenes\") -- true if this part reasonably wraps up the whole topic and no further "
        f"part is needed, false if there's clearly more of the brief left to cover in a next part. (After "
        f"part {MAX_SEGMENTS} this will be forced to stop regardless, so wrap up the topic within a "
        "reasonable number of parts rather than dragging it out.)"
    )


def generate_series(brief: str, out_dir: Path, context: str | None = None, on_progress: ProgressFn | None = None,
                     voice: str | None = None) -> list[tuple[dict, Path]]:
    """Split mode: directs and renders a brief as several
    ~SEGMENT_TARGET_SECONDS video files instead of one long one. Each part
    is its own critique-loop call, told what prior parts already covered
    (see _segment_prompt_note), choosing its own natural stopping point
    rather than being forced to hit an exact frame count
    (validate_storyboard's enforce_length=False) -- stops once a part
    reports "isFinal" or MAX_SEGMENTS is reached. Renders part_1.mp4,
    part_2.mp4, etc. directly into out_dir, one at a time."""
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[tuple[dict, Path]] = []
    recap_lines: list[str] = []
    part = 1
    while True:
        if on_progress:
            on_progress(f"Directing part {part}...")
        storyboard_path = out_dir / f".storyboard-part{part}-{uuid.uuid4().hex[:8]}.json"
        extra_note = _segment_prompt_note(part, "\n".join(recap_lines))
        try:
            raw = _direct_storyboard(
                brief, storyboard_path, SEGMENT_TARGET_SECONDS * FPS, voice, context, on_progress, extra_note=extra_note,
            )
        finally:
            storyboard_path.unlink(missing_ok=True)
        is_final = bool(raw.get("isFinal")) or part >= MAX_SEGMENTS
        storyboard = validate_storyboard(raw, target_frames=None, enforce_length=False)

        out_path = out_dir / f"part_{part}.mp4"
        if on_progress:
            on_progress(f"Rendering part {part}...")
        _render_spec(storyboard, out_path, voice, on_progress)
        results.append((storyboard, out_path))
        recap_lines.append(f"Part {part}: " + "; ".join(_scene_gist(s) for s in storyboard["scenes"]))

        if is_final:
            break
        part += 1
    return results


def generate(brief: str, out_path: Path, context: str | None = None, on_progress: ProgressFn | None = None,
             voice: str | None = None) -> dict:
    """Shared by the CLI below and both server handlers (library-mode +
    workflow-node-mode): direct the storyboard (critique loop), validate it,
    optionally synthesize narration, then render deterministically. Returns
    the storyboard (used as this item's library metadata). `on_progress`, if
    given, is called with short human-readable status lines as each real
    step happens."""
    if on_progress:
        on_progress("Directing the video with Claude...")
    target_seconds = _detect_target_seconds(brief)
    target_frames = round(target_seconds * FPS) if target_seconds else None

    out_path = out_path.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    storyboard_path = out_path.parent / f".storyboard-{uuid.uuid4().hex[:8]}.json"
    try:
        raw = _direct_storyboard(brief, storyboard_path, target_frames, voice, context, on_progress)
    finally:
        storyboard_path.unlink(missing_ok=True)
    storyboard = validate_storyboard(raw, target_frames=target_frames)
    _render_spec(storyboard, out_path, voice, on_progress)
    return storyboard


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", required=True, help="What the video should be about")
    ap.add_argument("--context", help="Optional reference content to base the video on")
    ap.add_argument("--voice", choices=VOICES, help="Narrate the video with this local voice (omit for no narration)")
    ap.add_argument("--out", default="output.mp4")
    ap.add_argument("--split", action="store_true",
                     help=f"Produce several ~{SEGMENT_TARGET_SECONDS // 60}-minute videos instead of one long one")
    args = ap.parse_args()

    if args.split:
        out_dir = Path(args.out).parent if Path(args.out).suffix else Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        results = generate_series(args.brief, out_dir, context=args.context, voice=args.voice)
        for i, (storyboard, path) in enumerate(results, start=1):
            print(f"Part {i}: {len(storyboard['scenes'])} scene(s) -> {path}")
        return

    storyboard = generate(args.brief, Path(args.out), context=args.context, voice=args.voice)
    print(json.dumps(storyboard, indent=2))
    print(f"\nWritten to {args.out}")


if __name__ == "__main__":
    main()
