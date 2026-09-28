"""
Minimal FastAPI test harness for the six ContentAgents.

Each agent is invoked exactly as automation would: as a standalone
`run.py` subprocess (same code path as any external workflow caller), so
what you see working here is what a real workflow step would see too.

Usage:
    pip install -r ../requirements.txt
    python server.py
    -> open http://localhost:8420
"""

import asyncio
import json
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import httpx
from fastapi import APIRouter, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.routing import APIRoute
from PIL import Image
from pydantic import BaseModel

CONTENT_AGENTS_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = Path(__file__).resolve().parent / "uploads"
LIBRARY_DIR = CONTENT_AGENTS_DIR / "library"
UPLOADS_DIR.mkdir(exist_ok=True)
LIBRARY_DIR.mkdir(exist_ok=True)

sys.path.insert(0, str(CONTENT_AGENTS_DIR))
sys.path.insert(0, str(CONTENT_AGENTS_DIR / "site_crawler"))  # run.py's own `from crawl import ...` needs this on sys.path
from common.claude_cli import (  # noqa: E402
    ClaudeCliError, MODEL_CHOICES, extract_json, get_selected_model, run_claude, set_selected_model,
)
from excel_parser.run import SYSTEM_PROMPT as EXCEL_BATCH_PROMPT  # noqa: E402
from excel_parser.run import scan_workbook  # noqa: E402
from pdf_parser.run import SYSTEM_PROMPT as PDF_BATCH_PROMPT  # noqa: E402
from pdf_parser.run import scan_pdf  # noqa: E402
from media_parser.run import extract_audio, extract_keyframes, has_video_stream, transcribe  # noqa: E402
from site_crawler.crawl import crawl_site  # noqa: E402
from excel_creator.run import SYSTEM_PROMPT as EXCEL_CREATOR_PROMPT  # noqa: E402
from excel_creator.run import build_xlsx  # noqa: E402
from pdf_creator.run import SYSTEM_PROMPT as PDF_CREATOR_PROMPT  # noqa: E402
from pdf_creator.run import build_pdf  # noqa: E402
from ppt_creator.run import generate as ppt_generate  # noqa: E402
from visualization_agent.run import generate as viz_generate  # noqa: E402
from visualization_agent.run import read_csv_text as viz_read_csv_text  # noqa: E402
from visualization_agent.run import read_data_file as viz_read_data_file  # noqa: E402
from video_creator.run import VOICES as VIDEO_VOICES  # noqa: E402
from video_creator.run import generate as video_generate  # noqa: E402
from video_creator.run import generate_series as video_generate_series  # noqa: E402
from video_creator.run import render_video as video_render  # noqa: E402
from video_creator.run import validate_storyboard as video_validate_storyboard  # noqa: E402
from video_creator.run import storyboard_to_narrative as video_storyboard_to_narrative  # noqa: E402
from video_creator.run import apply_narrative as video_apply_narrative  # noqa: E402

READER_AGENTS = ("excel_parser", "pdf_parser", "image_parser", "media_parser", "site_crawler")
CREATOR_AGENTS = ("excel_creator", "pdf_creator", "ppt_creator", "visualization_agent", "video_creator")

# AWS credentials/SSO sessions expire silently and the CLI call then fails
# with a Bedrock auth error -- recognize that case specifically so the UI
# tells you what to actually do instead of a raw stack trace.
_AWS_AUTH_HINTS = ("expiredtoken", "unrecognizedclient", "not authorized", "accessdenied",
                   "invalidsignature", "could not be validated", "credentials")


def _friendly_error_message(raw: str) -> str:
    if any(hint in raw.lower() for hint in _AWS_AUTH_HINTS):
        return ("Your AWS/Bedrock credentials appear to have expired or lost access. "
                "Refresh them (re-run your AWS SSO/credential login), then stop and restart "
                "the ContentAgents UI server (start.bat) and try again.")
    return f"The agent call failed: {raw[:500] if raw.strip() else 'no error detail was returned by the CLI.'}"


class ContentAgentsRoute(APIRoute):
    """Scopes ContentAgents' friendly-error JSON responses to only this
    router's own routes -- APIRouter has no @exception_handler of its own,
    and registering one globally on the host app (TurboAppGenerator) would
    change error behavior for every other tab's routes too."""

    def get_route_handler(self) -> Callable:
        original_handler = super().get_route_handler()

        async def custom_handler(request: Request):
            try:
                return await original_handler(request)
            except HTTPException:
                raise
            except ClaudeCliError as exc:
                return JSONResponse(status_code=502, content={"error": _friendly_error_message(str(exc))})
            except Exception as exc:
                return JSONResponse(status_code=500, content={"error": _friendly_error_message(str(exc))})

        return custom_handler


router = APIRouter(route_class=ContentAgentsRoute)

_OUTPUT_LINE_RE = re.compile(r"to (\S.*\.\w+)\s*$", re.MULTILINE)

LIBRARY_AGENTS = ("excel_parser", "pdf_parser", "image_parser", "media_parser", "site_crawler",
                   "excel_creator", "pdf_creator", "ppt_creator", "visualization_agent", "video_creator")

# chat_id -> {"agent": str, "claude_session_id": str, "dir": Path, "allowed_tools": list[str], "persistent": bool}
CHAT_SESSIONS: dict[str, dict] = {}

# run_id -> {"status": "running"|"complete"|"error", "log": [str, ...], "result": dict | None, "error": str | None}
# Tracks in-flight/finished library-item creation jobs so the frontend can
# POLL instead of holding one HTTP request open for the entire generation.
# Same reasoning/shape as Workflow/workflow_server.py's WORKFLOW_RUNS --
# needed because calling any of these agents' generate() functions directly
# inside an async route (the original design here) blocks FastAPI's
# single-threaded event loop for the ENTIRE call, freezing the whole server
# -- not just this one request -- for every other tab/user until it
# finishes. Confirmed directly: a plain GET / hung for minutes during a real
# video_creator generation. video_creator alone can take 5-20+ minutes, so
# this isn't a cosmetic gap -- the server was genuinely unusable meanwhile.
LIBRARY_ITEM_RUNS: dict[str, dict] = {}


def _append_library_log(run_id: str, line: str) -> None:
    run = LIBRARY_ITEM_RUNS.get(run_id)
    if run is not None:
        run["log"].append(line)

# Every library-backed chat session gets real tool access scoped to that
# item's own folder, so Claude can query the full underlying data when the
# curated metadata's summary isn't enough for an exact/complete answer --
# instead of just reasoning off a static sample. Images don't need Bash
# (there's nothing to query beyond re-looking at the picture); the rest do.
LIBRARY_CHAT_TOOLS = {
    "excel_parser": ["Bash", "Read"],
    "pdf_parser": ["Bash", "Read"],
    "image_parser": ["Read"],
    "media_parser": ["Bash", "Read"],
    "site_crawler": ["Bash", "Read"],
    "excel_creator": ["Bash", "Read"],
    "pdf_creator": ["Bash", "Read"],
    "ppt_creator": ["Bash", "Read"],
    "visualization_agent": ["Bash", "Read"],
    "video_creator": ["Read"],
}

CHAT_LIBRARY_SYSTEM_PROMPTS = {
    "excel_parser": """You are chatting with a user about an Excel workbook.
Below is curated metadata describing it (sheets, columns, inferred meaning,
data-quality notes) -- it may have been edited by the user, so trust it over
your own guesses about what the data means. The full original workbook is
saved at ./original.xlsx in your current working directory. If a question
needs an exact or complete answer that the metadata's sample values can't
give you (e.g. filtering or counting across every row), use Bash to write
and run a short Python script (openpyxl is available) against
./original.xlsx to compute the precise answer -- don't guess or extrapolate
from samples when you can just compute it exactly.""",
    "pdf_parser": """You are chatting with a user about a PDF document.
Below is curated metadata describing it (outline, section summaries) -- it
may have been edited by the user, so trust it over your own guesses. The
full original PDF is saved at ./original.pdf in your current working
directory. If a question needs the exact text of a page/section beyond what
the metadata's summary covers, use Bash to run a short Python script
(PyMuPDF, imported as `fitz`, is available) against ./original.pdf to pull
the exact text rather than guessing from the summary.""",
    "image_parser": """You are chatting with a user about an image. Below is
curated metadata describing it (description, detected text, structured
data) -- it may have been edited by the user, so trust it over your own
guesses. The image's exact filename in your current working directory is
given in the first message -- Read it again whenever a question needs
closer visual inspection than the metadata already covers.""",
    "media_parser": """You are chatting with a user about a video/audio
file. Below is curated metadata describing it (summary, topics, timeline)
-- it may have been edited by the user, so trust it over your own guesses.
The metadata's "timeline" entries are YOUR OWN paraphrased descriptions, not
verbatim transcript text -- they are not sufficient for any question asking
for exact wording, an exact quote, or a precise timestamp.

You have Bash and Read tool access right now, scoped to this item's own
folder. The full timestamped transcript is saved at ./transcript.json (run
e.g. `cat transcript.json` or grep it), and any video keyframe images sit
in your current working directory (Read them again for visual detail).
Whenever a question needs exactness the paraphrased metadata can't
guarantee, actually run Bash to check ./transcript.json before answering --
never claim you lack access to it or to the recording's content; you have
direct access to the real transcript file, not just a summary of it.""",
    "site_crawler": """You are chatting with a user about a website that was
crawled. Below is curated metadata describing it (summary, sections,
per-page summaries) -- it may have been edited by the user, so trust it
over your own guesses. The metadata's per-page "summary" entries are YOUR
OWN paraphrased descriptions, not the page's actual text -- they are not
sufficient for any question asking for exact wording or specific details a
summary could easily omit.

You have Bash and Read tool access right now, scoped to this item's own
folder. The full crawl data -- every discovered page's complete text and
links -- is saved at ./crawl.json (run e.g. `cat crawl.json` or grep it),
and screenshots are in ./screenshots/ (Read them for visual confirmation).
Whenever a question needs exactness the paraphrased metadata can't
guarantee, actually run Bash to check ./crawl.json before answering -- never
claim you lack access to the site's content; you have direct access to the
full crawl data, not just a summary of it.""",
    "excel_creator": """You are chatting with a user about an Excel workbook
you generated. Below is the content plan (sheets/headers/rows) used to build
it -- it may have been edited by the user, so trust it over your own memory
of what you generated. The actual file is saved at ./original.xlsx in your
current working directory. If asked to verify exact values, or to make a
change, use Bash (openpyxl is available) to inspect or rebuild
./original.xlsx directly -- don't just recall from the plan.""",
    "pdf_creator": """You are chatting with a user about a PDF document you
generated. Below is the content plan (sections/paragraphs/tables) used to
build it -- it may have been edited by the user, so trust it over your own
memory of what you generated. The actual file is saved at ./original.pdf in
your current working directory. If asked to verify exact content, use Bash
(PyMuPDF, imported as `fitz`, is available) to inspect ./original.pdf
directly -- don't just recall from the plan.""",
    "ppt_creator": """You are chatting with a user about a slide deck you
generated. Below is the content plan (slides, bullets, speaker notes) used
to build it -- it may have been edited by the user, so trust it over your
own memory of what you generated. The actual file is saved at
./original.pptx in your current working directory. If asked to verify
exact content, use Bash (python-pptx, imported as `pptx`, is available) to
inspect ./original.pptx directly -- don't just recall from the plan.""",
    "visualization_agent": """You are chatting with a user about a chart/map
visualization you generated. Below is the spec (title, summary, chart types
and column mappings) used to build it -- it may have been edited by the
user, so trust it over your own memory. The rendered file is saved at
./original.html and the exact underlying data rows are saved at ./data.json
in your current working directory. If asked about specific values, trends,
or anything beyond the summary, use Bash to inspect ./data.json directly
(e.g. with a short Python script) rather than guessing from the spec.""",
    "video_creator": """You are chatting with a user about a short scripted
video you generated. Below is the exact script (every scene's type, text,
colors, and timing) used to render it -- it may have been edited by the
user, so trust it over your own memory of what you originally wrote. The
rendered file is saved at ./original.mp4 in your current working directory,
but you have no way to actually watch it -- answer from the script JSON
itself (which is the complete, exact source of everything that appears on
screen), and say so plainly if asked about something the script doesn't
capture (e.g. exact visual timing/animation feel, which you'd need to watch
the video to judge).""",
}

# Batch, one-shot metadata-drafting prompts -- used once at library-item
# creation time to produce the editable metadata.json (distinct from the
# CHAT_LIBRARY_SYSTEM_PROMPTS above, which drive the ongoing conversation).
IMAGE_BATCH_PROMPT = """You are the Image Parsing Agent. Read the image file
at the path you're given and produce a structured metadata JSON describing
it precisely -- read exact numbers/labels/text directly off the image
rather than guessing.

Respond with ONLY a single JSON object, no prose, matching this shape:
{
  "description": "...",
  "detected_text": "...",
  "structured_data": {},
  "tags": ["..."]
}
Use "structured_data" for anything tabular/numeric you can read precisely
(e.g. chart values, form fields); leave it as {} if the image has none."""

MEDIA_BATCH_PROMPT = """You are the Video/Audio Parsing Agent. You are given
a timestamped transcript and, for video, periodic keyframe images. Produce
a structured metadata JSON summarizing it.

Respond with ONLY a single JSON object, no prose, matching this shape:
{
  "summary": "...",
  "topics": ["..."],
  "timeline": [{"timestamp": 0.0, "description": "..."}]
}"""

SITE_CRAWLER_BATCH_PROMPT = """You are the Website Crawling Agent. You are
given the aggregated text content of every page discovered on a site (plus
a few screenshots). Produce a structured metadata JSON site map.

Respond with ONLY a single JSON object, no prose, matching this shape:
{
  "summary": "...",
  "sections": ["..."],
  "pages": [{"url": "...", "title": "...", "summary": "..."}]
}"""


def _start_chat(agent: str, prompt: str, allowed_tools: list[str], session_dir: Path,
                timeout: int = 900, system_prompt: str | None = None, persistent: bool = False) -> dict:
    result = run_claude(prompt, system_prompt=system_prompt, allowed_tools=allowed_tools,
                         cwd=str(session_dir), timeout=timeout)
    chat_id = session_dir.name if not persistent else uuid.uuid4().hex[:12]
    CHAT_SESSIONS[chat_id] = {"agent": agent, "claude_session_id": result["session_id"],
                               "dir": session_dir, "allowed_tools": allowed_tools, "persistent": persistent}
    return {"chat_id": chat_id, "answer": result["result"]}


@router.post("/api/chat/message")
async def chat_message(chat_id: str = Form(...), message: str = Form(...)):
    session = CHAT_SESSIONS.get(chat_id)
    if not session:
        raise HTTPException(404, "Unknown chat_id -- the server may have restarted since this chat started.")
    result = run_claude(message, resume=session["claude_session_id"],
                         allowed_tools=session["allowed_tools"], cwd=str(session["dir"]))
    session["claude_session_id"] = result["session_id"]
    return JSONResponse({"answer": result["result"]})


@router.delete("/api/chat/{chat_id}")
async def chat_end(chat_id: str):
    session = CHAT_SESSIONS.pop(chat_id, None)
    if session and not session.get("persistent"):
        shutil.rmtree(session["dir"], ignore_errors=True)
    return JSONResponse({"ok": True})


# --- Library: persisted items (all 5 chat agents) with LLM-drafted, user-editable metadata ---

def _item_dir(item_id: str) -> Path:
    d = LIBRARY_DIR / item_id
    if not d.exists():
        raise HTTPException(404, "Unknown library item")
    return d


def _create_video_series_items(brief: str, context: str | None, voice: str | None,
                                 on_progress: Callable[[str], None] | None = None) -> list[dict]:
    """Split mode: video_creator produces several separate library items
    (one per ~5-minute part -- see video_creator.run.generate_series)
    instead of the usual single item, so this bypasses the generic
    single-item flow below entirely. Renders into a scratch directory first
    since the number of parts (and therefore how many item ids/dirs are
    needed) isn't known until generate_series actually finishes."""
    tmp_dir = LIBRARY_DIR / f"_tmp_series_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True)
    try:
        parts = video_generate_series(brief, tmp_dir, context=context, voice=voice, on_progress=on_progress)
        total = len(parts)
        items = []
        for i, (spec, part_path) in enumerate(parts, start=1):
            item_id = uuid.uuid4().hex[:12]
            item_dir = LIBRARY_DIR / item_id
            item_dir.mkdir(parents=True)
            shutil.move(str(part_path), str(item_dir / "original.mp4"))
            (item_dir / "metadata.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
            input_info = {"brief": brief}
            if context:
                input_info["context"] = context
            if voice:
                input_info["voice"] = voice
            item_info = {
                "item_id": item_id, "agent": "video_creator",
                "filename": f"{spec.get('title') or 'Generated video'} (Part {i} of {total})",
                "uploaded_at": datetime.now(timezone.utc).isoformat(), "input": input_info,
            }
            (item_dir / "item.json").write_text(json.dumps(item_info, indent=2), encoding="utf-8")
            items.append({**item_info, "metadata": spec})
        return items
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _run_library_item_job(run_id: str, agent: str, *, file_bytes: bytes | None, file_name: str | None,
                            url: str | None, max_pages: int, max_depth: int, keyframe_interval: int,
                            brief: str | None, context: str | None, question: str | None, voice: str | None,
                            split: bool, slides: int | None) -> None:
    """Runs entirely in a background thread (see the route below) -- never
    call this directly from the async route itself, that's exactly the
    blocking-the-whole-server bug this exists to avoid. Writes its outcome
    into LIBRARY_ITEM_RUNS[run_id] for the status route to poll instead of
    returning anything or raising up through a request context that no
    longer exists by the time this finishes."""
    run = LIBRARY_ITEM_RUNS[run_id]
    on_progress = lambda line: _append_library_log(run_id, line)  # noqa: E731
    try:
        if agent == "video_creator" and split:
            chosen_voice = voice if voice in VIDEO_VOICES else None
            on_progress("Directing part 1...")
            items = _create_video_series_items(brief, context or None, chosen_voice, on_progress=on_progress)
            run["result"] = {"items": items}
            run["status"] = "complete"
            return

        item_id = uuid.uuid4().hex[:12]
        item_dir = LIBRARY_DIR / item_id
        item_dir.mkdir(parents=True)
        filename: str
        metadata: dict | None = None
        result = None

        if agent == "excel_parser":
            filename = file_name
            original_path = item_dir / f"original{Path(filename).suffix or '.xlsx'}"
            original_path.write_bytes(file_bytes)
            on_progress("Scanning workbook structure...")
            scan = scan_workbook(original_path, 15)
            prompt = (f"Here is the raw structural scan of an Excel workbook:\n\n{json.dumps(scan, indent=2)}\n\n"
                      "Produce the metadata JSON described in your instructions.")
            on_progress("Summarizing with Claude...")
            result = run_claude(prompt, system_prompt=EXCEL_BATCH_PROMPT, allowed_tools=[])

        elif agent == "pdf_parser":
            filename = file_name
            original_path = item_dir / f"original{Path(filename).suffix or '.pdf'}"
            original_path.write_bytes(file_bytes)
            on_progress("Extracting PDF content...")
            scan = scan_pdf(original_path, 4000)
            # A targeted question makes PDF_BATCH_PROMPT (imported straight from
            # pdf_parser.run.SYSTEM_PROMPT, which already handles this) answer
            # from the FULL per-page extraction instead of drafting just a
            # browsing-friendly outline. That distinction matters a lot for a
            # long, list-heavy document (e.g. hundreds of names + numbers) --
            # no outline short enough to browse can losslessly carry that much
            # detail, so a downstream creator chained after this reader (e.g.
            # Visualization Agent) has nothing real to work with unless this
            # reader was actually asked for the specific values it needs.
            q = (question or "").strip()
            prompt = (f"Here is the per-page extraction of a PDF:\n\n{json.dumps(scan, indent=2)}\n\n"
                      + (f"Question: {q}" if q else "No specific question -- just produce the outline."))
            on_progress("Summarizing with Claude...")
            result = run_claude(prompt, system_prompt=PDF_BATCH_PROMPT, allowed_tools=[])

        elif agent == "image_parser":
            filename = file_name
            original_path = item_dir / f"original{Path(filename).suffix or '.png'}"
            original_path.write_bytes(file_bytes)
            read_path = original_path
            with Image.open(original_path) as im:
                if max(im.size) > 2000:
                    im.thumbnail((2000, 2000))
                    read_path = item_dir / f"resized{original_path.suffix}"
                    im.save(read_path)
            prompt = f'Read the image at "{read_path.name}" and produce the metadata JSON described in your instructions.'
            on_progress("Reading image and summarizing with Claude...")
            result = run_claude(prompt, system_prompt=IMAGE_BATCH_PROMPT, allowed_tools=["Read"], cwd=str(item_dir))

        elif agent == "media_parser":
            filename = file_name
            original_path = item_dir / f"original{Path(filename).suffix or '.mp4'}"
            original_path.write_bytes(file_bytes)
            on_progress("Extracting audio...")
            wav_path = item_dir / "audio.wav"
            extract_audio(original_path, wav_path)
            keyframes = extract_keyframes(original_path, item_dir, keyframe_interval) if has_video_stream(original_path) else []
            on_progress("Transcribing audio...")
            transcript = transcribe(wav_path, "base")
            (item_dir / "transcript.json").write_text(json.dumps(transcript, indent=2), encoding="utf-8")
            prompt_parts = [f"TRANSCRIPT (timestamped, seconds):\n{json.dumps(transcript, indent=2)}"]
            if keyframes:
                prompt_parts.append("\nKEYFRAME IMAGES (filenames, one every "
                                     f"{keyframe_interval}s, in order): " + ", ".join(Path(k).name for k in keyframes))
            prompt_parts.append("\nProduce the metadata JSON described in your instructions.")
            on_progress("Summarizing with Claude...")
            result = run_claude("\n".join(prompt_parts), system_prompt=MEDIA_BATCH_PROMPT,
                                 allowed_tools=["Read"], cwd=str(item_dir), timeout=1800)

        elif agent == "site_crawler":
            filename = url
            screenshots_dir = item_dir / "screenshots"
            on_progress("Crawling the site...")
            # crawl_site is async, but this whole function runs in a plain
            # background thread with no event loop of its own -- asyncio.run
            # gives it one for just this call, same as running it standalone.
            crawl = asyncio.run(crawl_site(url, max_pages=max_pages, max_depth=max_depth,
                                            respect_robots=True, screenshots_dir=screenshots_dir))
            (item_dir / "crawl.json").write_text(json.dumps(crawl, indent=2), encoding="utf-8")
            condensed_pages = [{"url": p["url"], "title": p["title"], "text": p["text"]} for p in crawl["pages"]]
            screenshots = [f"screenshots/{Path(p['screenshot']).name}" for p in crawl["pages"] if p["screenshot"]][:5]
            prompt_parts = [f"PAGES DISCOVERED ({len(condensed_pages)} of {crawl['pages_visited']} visited):\n"
                             f"{json.dumps(condensed_pages, indent=2)}"]
            if screenshots:
                prompt_parts.append(f"\nSCREENSHOTS (read via Read tool for visual confirmation): {', '.join(screenshots)}")
            if crawl["errors"]:
                prompt_parts.append(f"\nCRAWL ERRORS/SKIPS: {json.dumps(crawl['errors'], indent=2)}")
            prompt_parts.append("\nProduce the metadata JSON described in your instructions.")
            on_progress("Summarizing with Claude...")
            result = run_claude("\n".join(prompt_parts), system_prompt=SITE_CRAWLER_BATCH_PROMPT,
                                 allowed_tools=["Read"], cwd=str(item_dir), timeout=900)

        elif agent == "excel_creator":
            prompt_parts = [f"BRIEF: {brief}"]
            if context:
                prompt_parts.append(f"\nREFERENCE CONTENT:\n{context}")
            on_progress("Drafting the workbook with Claude...")
            result = run_claude("\n".join(prompt_parts), system_prompt=EXCEL_CREATOR_PROMPT, allowed_tools=[])
            plan = extract_json(result["result"])
            build_xlsx(plan, item_dir / "original.xlsx")
            filename = plan.get("title") or "Generated workbook"
            metadata = plan

        elif agent == "pdf_creator":
            prompt_parts = [f"BRIEF: {brief}"]
            if context:
                prompt_parts.append(f"\nREFERENCE CONTENT:\n{context}")
            on_progress("Drafting the document with Claude...")
            result = run_claude("\n".join(prompt_parts), system_prompt=PDF_CREATOR_PROMPT, allowed_tools=[])
            plan = extract_json(result["result"])
            build_pdf(plan, item_dir / "original.pdf")
            filename = plan.get("title") or "Generated document"
            metadata = plan

        elif agent == "ppt_creator":
            template_path = None
            if file_bytes:
                template_path = item_dir / f"template{Path(file_name).suffix or '.pptx'}"
                template_path.write_bytes(file_bytes)
            on_progress("Drafting the deck with Claude...")
            plan = ppt_generate(brief, item_dir / "original.pptx", template_path=template_path,
                                 images_dir=item_dir / "template_images", slides=slides)
            filename = plan.get("title") or "Generated deck"
            metadata = plan

        elif agent == "visualization_agent":
            rows = columns = None
            if file_bytes:
                rows, columns = viz_read_data_file(file_bytes, file_name)
            elif context:
                stripped = context.strip()
                if stripped.startswith("[") or stripped.startswith("{"):
                    rows, columns = viz_read_data_file(context.encode("utf-8"), "context.json")
                else:
                    rows, columns = viz_read_csv_text(context)
            if (file_bytes or context) and not rows:
                raise ValueError("No data rows could be parsed from the given input.")
            on_progress("Building the visualization...")
            if rows:
                spec = viz_generate(brief, item_dir / "original.html", rows=rows, columns=columns)
            else:
                # No file/paste given -- let Claude supply real, well-known data
                # itself if the brief calls for it (see visualization_agent's
                # SYSTEM_PROMPT case 3); it returns an empty chart rather than
                # guess if it doesn't actually know the answer.
                spec = viz_generate(brief, item_dir / "original.html", raw_context=None)
                rows = spec.get("data") or []
            (item_dir / "data.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
            filename = spec.get("title") or "Visualization"
            metadata = spec

        else:  # video_creator
            chosen_voice = voice if voice in VIDEO_VOICES else None
            spec = video_generate(brief, item_dir / "original.mp4", context=context or None,
                                   voice=chosen_voice, on_progress=on_progress)
            filename = spec.get("title") or "Generated video"
            metadata = spec

        if metadata is None:
            metadata = extract_json(result["result"])
        (item_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        # What was actually typed to produce this item -- only the fields
        # actually submitted, so opening a past item later can show the original
        # ask instead of just its drafted output (previously this was discarded
        # the moment the request finished, with no way to recover it).
        raw_input = {"brief": brief, "context": context, "question": question,
                     "voice": voice if voice in VIDEO_VOICES else None,
                     "slides": str(slides) if slides else None}
        input_info = {k: v for k, v in raw_input.items() if v}
        item_info = {"item_id": item_id, "agent": agent, "filename": filename,
                     "uploaded_at": datetime.now(timezone.utc).isoformat()}
        if input_info:
            item_info["input"] = input_info
        (item_dir / "item.json").write_text(json.dumps(item_info, indent=2), encoding="utf-8")
        run["result"] = {**item_info, "metadata": metadata}
        run["status"] = "complete"
    except ClaudeCliError as exc:
        run["error"] = _friendly_error_message(str(exc))
        run["status"] = "error"
    except Exception as exc:
        run["error"] = _friendly_error_message(str(exc))
        run["status"] = "error"


@router.post("/api/library/items")
async def library_create_item(agent: str = Form(...), file: UploadFile | None = None,
                                url: str | None = Form(None), max_pages: int = Form(20),
                                max_depth: int = Form(5), keyframe_interval: int = Form(30),
                                brief: str | None = Form(None), context: str | None = Form(None),
                                question: str | None = Form(None), voice: str | None = Form(None),
                                split: bool = Form(False), slides: int | None = Form(None)):
    if agent not in LIBRARY_AGENTS:
        raise HTTPException(400, f"Library isn't supported for agent '{agent}' yet.")
    # Fast, synchronous validation -- fails immediately with a real 400,
    # same as before, rather than starting a background job just to report
    # "you forgot the brief" a moment later through the status poll.
    _brief_required_labels = {
        "excel_creator": "Excel Creator", "pdf_creator": "PDF Creator", "ppt_creator": "PPT Creator",
        "visualization_agent": "Visualization Agent", "video_creator": "Video Creator",
    }
    if agent in _brief_required_labels and not brief:
        raise HTTPException(400, f"A brief is required for the {_brief_required_labels[agent]}.")
    if agent == "site_crawler" and not url:
        raise HTTPException(400, "A URL is required for the Website Crawler.")
    if agent == "media_parser" and not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        raise HTTPException(400, "ffmpeg not found on the server's PATH. Install ffmpeg to use this agent.")

    # UploadFile.read() is async and only valid inside this request's own
    # context -- read the bytes now, before handing off to a plain
    # background thread that has no access to the request/event loop at all.
    file_bytes = await file.read() if file else None
    file_name = file.filename if file else None

    run_id = uuid.uuid4().hex[:12]
    LIBRARY_ITEM_RUNS[run_id] = {"status": "running", "log": [], "result": None, "error": None}
    threading.Thread(
        target=_run_library_item_job, daemon=True,
        args=(run_id, agent),
        kwargs=dict(file_bytes=file_bytes, file_name=file_name, url=url, max_pages=max_pages,
                    max_depth=max_depth, keyframe_interval=keyframe_interval, brief=brief, context=context,
                    question=question, voice=voice, split=split, slides=slides),
    ).start()
    return JSONResponse({"run_id": run_id})


@router.get("/api/library/items/runs/{run_id}/status")
async def library_item_run_status(run_id: str):
    run = LIBRARY_ITEM_RUNS.get(run_id)
    if run is None:
        raise HTTPException(404, "Unknown run")
    return JSONResponse(run)


@router.get("/api/library/items")
async def library_list_items():
    items = []
    for d in LIBRARY_DIR.iterdir():
        info_path = d / "item.json"
        if info_path.exists():
            items.append(json.loads(info_path.read_text(encoding="utf-8")))
    items.sort(key=lambda it: it.get("uploaded_at", ""), reverse=True)
    return JSONResponse({"items": items})


@router.get("/api/library/items/{item_id}")
async def library_get_item(item_id: str):
    item_dir = _item_dir(item_id)
    item_info = json.loads((item_dir / "item.json").read_text(encoding="utf-8"))
    metadata = json.loads((item_dir / "metadata.json").read_text(encoding="utf-8"))
    return JSONResponse({**item_info, "metadata": metadata})


@router.get("/api/library/items/{item_id}/download")
async def library_download_item(item_id: str):
    item_dir = _item_dir(item_id)
    original = next((f for f in item_dir.glob("original.*")), None)
    if not original:
        raise HTTPException(404, "This item has no downloadable file (e.g. a website crawl).")
    if original.suffix == ".html":
        # No `filename=` -- that's what makes FileResponse set
        # Content-Disposition: attachment and force a download. A
        # visualization's whole point is to be viewed interactively, not
        # saved as a file first -- serve it inline so opening this URL in a
        # new tab renders the actual charts/map.
        return FileResponse(original, media_type="text/html")
    if original.suffix == ".mp4":
        # Same reasoning as .html above: serving inline (no `filename=`)
        # lets the browser show its native <video> player -- which already
        # has its own save/download control -- instead of forcing a save
        # dialog before the user has even seen the video.
        return FileResponse(original, media_type="video/mp4")
    return FileResponse(original, filename=original.name)


@router.put("/api/library/items/{item_id}/metadata")
async def library_update_metadata(item_id: str, metadata: str = Form(...)):
    item_dir = _item_dir(item_id)
    try:
        parsed = json.loads(metadata)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, f"Invalid JSON: {exc}")
    (item_dir / "metadata.json").write_text(json.dumps(parsed, indent=2), encoding="utf-8")
    return JSONResponse({"ok": True})


def _run_rerender_video_job(run_id: str, item_id: str) -> None:
    """Runs in a background thread (see the route below) -- re-renders
    original.mp4 straight from this item's CURRENT metadata.json (the
    storyboard, likely just hand-edited via the metadata panel/Save button
    above) with no LLM call at all. Same LIBRARY_ITEM_RUNS/on_progress
    polling mechanism as a fresh library_create_item job, reused rather
    than building a second one."""
    run = LIBRARY_ITEM_RUNS[run_id]
    on_progress = lambda line: _append_library_log(run_id, line)  # noqa: E731
    try:
        item_dir = _item_dir(item_id)
        item_info = json.loads((item_dir / "item.json").read_text(encoding="utf-8"))
        raw = json.loads((item_dir / "metadata.json").read_text(encoding="utf-8"))
        storyboard = video_validate_storyboard(raw)
        video_render(storyboard, item_dir / "original.mp4", on_progress=on_progress)
        # validate_storyboard may have cleaned up something (e.g. dropped an
        # invalid element the user's hand-edit introduced) -- persist what
        # ACTUALLY got rendered, not the raw edit, so the metadata panel
        # reflects the real video rather than silently drifting from it.
        (item_dir / "metadata.json").write_text(json.dumps(storyboard, indent=2), encoding="utf-8")
        run["result"] = {**item_info, "metadata": storyboard}
        run["status"] = "complete"
    except ClaudeCliError as exc:
        run["error"] = _friendly_error_message(str(exc))
        run["status"] = "error"
    except Exception as exc:
        run["error"] = _friendly_error_message(str(exc))
        run["status"] = "error"


@router.post("/api/library/items/{item_id}/rerender")
async def library_rerender_video(item_id: str):
    """Re-renders a video_creator item's .mp4 directly from its current
    (possibly hand-edited) storyboard JSON -- no directing/critique-loop
    LLM call, just the deterministic render step. Polled the same way as a
    fresh library_create_item job (GET .../runs/{run_id}/status)."""
    item_dir = _item_dir(item_id)
    item_info = json.loads((item_dir / "item.json").read_text(encoding="utf-8"))
    if item_info.get("agent") != "video_creator":
        raise HTTPException(400, "Re-render from JSON is only supported for Video Creator items.")

    run_id = uuid.uuid4().hex[:12]
    LIBRARY_ITEM_RUNS[run_id] = {"status": "running", "log": [], "result": None, "error": None}
    threading.Thread(target=_run_rerender_video_job, args=(run_id, item_id), daemon=True).start()
    return JSONResponse({"run_id": run_id})


@router.get("/api/library/items/{item_id}/narrative")
async def library_video_narrative(item_id: str):
    """Plain-English read view of a video_creator item's current storyboard
    -- deterministic, no LLM call, safe to compute on every request. An
    alternative editing surface to the raw JSON (see the metadata panel)
    for users who'd rather not risk breaking the JSON by hand."""
    item_dir = _item_dir(item_id)
    item_info = json.loads((item_dir / "item.json").read_text(encoding="utf-8"))
    if item_info.get("agent") != "video_creator":
        raise HTTPException(400, "The narrative view is only available for Video Creator items.")
    raw = json.loads((item_dir / "metadata.json").read_text(encoding="utf-8"))
    storyboard = video_validate_storyboard(raw)
    return JSONResponse({"narrative": video_storyboard_to_narrative(storyboard)})


def _run_apply_narrative_job(run_id: str, item_id: str, narrative: str) -> None:
    """Runs in a background thread -- turns a hand-edited narrative back
    into an updated storyboard JSON via one targeted LLM call (see
    apply_narrative) and saves it to metadata.json. Does NOT re-render the
    video; the existing "Re-render video from this JSON" button (see
    _run_rerender_video_job above) covers that as a separate, explicit
    step, same as editing the JSON directly."""
    run = LIBRARY_ITEM_RUNS[run_id]
    on_progress = lambda line: _append_library_log(run_id, line)  # noqa: E731
    try:
        item_dir = _item_dir(item_id)
        item_info = json.loads((item_dir / "item.json").read_text(encoding="utf-8"))
        raw = json.loads((item_dir / "metadata.json").read_text(encoding="utf-8"))
        storyboard = video_validate_storyboard(raw)
        updated = video_apply_narrative(storyboard, narrative, on_progress=on_progress)
        (item_dir / "metadata.json").write_text(json.dumps(updated, indent=2), encoding="utf-8")
        run["result"] = {**item_info, "metadata": updated}
        run["status"] = "complete"
    except ClaudeCliError as exc:
        run["error"] = _friendly_error_message(str(exc))
        run["status"] = "error"
    except Exception as exc:
        run["error"] = _friendly_error_message(str(exc))
        run["status"] = "error"


@router.post("/api/library/items/{item_id}/narrative")
async def library_apply_narrative(item_id: str, narrative: str = Form(...)):
    """Applies a hand-edited narrative to this video_creator item's
    storyboard JSON via one targeted LLM call -- not the full directing
    critique loop, so meaningfully faster. Polled the same way as a fresh
    library_create_item job (GET .../runs/{run_id}/status)."""
    item_dir = _item_dir(item_id)
    item_info = json.loads((item_dir / "item.json").read_text(encoding="utf-8"))
    if item_info.get("agent") != "video_creator":
        raise HTTPException(400, "The narrative view is only available for Video Creator items.")

    run_id = uuid.uuid4().hex[:12]
    LIBRARY_ITEM_RUNS[run_id] = {"status": "running", "log": [], "result": None, "error": None}
    threading.Thread(target=_run_apply_narrative_job, args=(run_id, item_id, narrative), daemon=True).start()
    return JSONResponse({"run_id": run_id})


def _reanswer_pdf_item(item_dir: Path, question: str | None) -> dict:
    """Re-runs pdf_parser's own question-answering pass against an
    ALREADY-attached item's original file, overwriting its metadata.json.
    Shared by the manual /question endpoint below AND the Workflow module's
    runner (see Workflow/workflow_server.py's _execute_workflow_run, which
    imports this function) -- a workflow run always re-asks whatever
    question is currently on the node before using that reader's output, so
    Run alone is authoritative and never depends on a separate manual "Ask"
    click having already been made (or being stale/out of sync with a since
    -edited question box)."""
    original = next((f for f in item_dir.glob("original.*")), None)
    if not original:
        raise HTTPException(404, "This item's original file is missing.")
    scan = scan_pdf(original, 4000)
    q = (question or "").strip()
    prompt = (f"Here is the per-page extraction of a PDF:\n\n{json.dumps(scan, indent=2)}\n\n"
              + (f"Question: {q}" if q else "No specific question -- just produce the outline."))
    result = run_claude(prompt, system_prompt=PDF_BATCH_PROMPT, allowed_tools=[])
    metadata = extract_json(result["result"])
    (item_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


@router.post("/api/library/items/{item_id}/question")
async def library_reanswer_item(item_id: str, question: str | None = Form(None)):
    """Manual "Ask" trigger -- lets a user preview/verify an answer before
    committing to a full workflow run. Exists because "pick existing"
    (reusing a library item added before it ever had a question, or added
    without one) has no other way to get a real, specific answer into that
    item's metadata outside of a run -- the alternative would be
    re-uploading the same file from scratch just to ask a follow-up
    question."""
    item_dir = _item_dir(item_id)
    item_info = json.loads((item_dir / "item.json").read_text(encoding="utf-8"))
    if item_info["agent"] != "pdf_parser":
        raise HTTPException(400, "Only PDF Parser items support asking a question today.")
    metadata = _reanswer_pdf_item(item_dir, question)
    # Keep the item's recorded input in sync with what was actually last
    # asked -- otherwise a re-ask would silently leave history showing the
    # ORIGINAL (possibly blank) question while the metadata reflects the new one.
    if (question or "").strip():
        item_info.setdefault("input", {})["question"] = question.strip()
    else:
        item_info.get("input", {}).pop("question", None)
    (item_dir / "item.json").write_text(json.dumps(item_info, indent=2), encoding="utf-8")
    return JSONResponse({**item_info, "metadata": metadata})


@router.delete("/api/library/items/{item_id}")
async def library_delete_item(item_id: str):
    shutil.rmtree(_item_dir(item_id), ignore_errors=True)
    return JSONResponse({"ok": True})


@router.post("/api/library/items/{item_id}/chat")
async def library_chat_start(item_id: str):
    item_dir = _item_dir(item_id)
    item_info = json.loads((item_dir / "item.json").read_text(encoding="utf-8"))
    metadata = json.loads((item_dir / "metadata.json").read_text(encoding="utf-8"))
    agent = item_info["agent"]

    prompt_parts = [f"CURATED METADATA (may have been edited by the user -- trust this over guessing):\n"
                     f"{json.dumps(metadata, indent=2)}"]
    if agent == "image_parser":
        image_file = next((f.name for f in item_dir.glob("resized.*")), None) \
            or next((f.name for f in item_dir.glob("original.*")), None)
        if image_file:
            prompt_parts.append(f"\nThe image file is saved as ./{image_file} in your working directory.")
    prompt_parts.append("\nGive me a brief (2-3 sentence) overview using this metadata, mention that you can dig "
                         "into the underlying data directly for anything beyond it, then wait for my questions.")

    return JSONResponse(_start_chat(agent, "\n".join(prompt_parts), LIBRARY_CHAT_TOOLS[agent], item_dir, timeout=900,
                                     system_prompt=CHAT_LIBRARY_SYSTEM_PROMPTS[agent], persistent=True))


def _save_upload(upload: UploadFile | None, dest_dir: Path = UPLOADS_DIR) -> Path | None:
    if upload is None or not upload.filename:
        return None
    dest = dest_dir / f"{uuid.uuid4().hex[:8]}_{upload.filename}"
    dest.write_bytes(upload.file.read())
    return dest


def _run_script(script: str, args: list[str], timeout: int = 600) -> dict:
    script_path = CONTENT_AGENTS_DIR / script
    cmd = [sys.executable, str(script_path), *args]
    try:
        proc = subprocess.run(
            cmd, cwd=str(script_path.parent), capture_output=True, text=True,
            encoding="utf-8", timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": f"Timed out after {timeout}s", "outputs": {}}

    outputs = {}
    for match in _OUTPUT_LINE_RE.finditer(proc.stdout):
        path = Path(match.group(1).strip())
        if path.exists() and path.suffix in (".json", ".md", ".txt"):
            outputs[path.name] = path.read_text(encoding="utf-8", errors="replace")[:20000]
        elif path.exists():
            outputs[path.name] = f"[binary file: {path}]"

    return {
        "ok": proc.returncode == 0, "stdout": proc.stdout, "stderr": proc.stderr,
        "outputs": outputs,
    }


# --- Global model picker (mirrors TurboAppGenerator's header picker) ---

class SelectModelRequest(BaseModel):
    model: str


@router.get("/api/models")
async def api_list_models():
    return {"choices": MODEL_CHOICES, "current": get_selected_model()}


@router.post("/api/models/select")
async def api_select_model(req: SelectModelRequest):
    try:
        set_selected_model(req.model)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True}


@router.post("/api/run/excel_parser")
async def run_excel_parser(file: UploadFile):
    path = _save_upload(file)
    return JSONResponse(_run_script("excel_parser/run.py", [str(path)]))


@router.post("/api/run/pdf_parser")
async def run_pdf_parser(file: UploadFile, question: str = Form("")):
    path = _save_upload(file)
    args = [str(path)]
    if question.strip():
        args += ["--question", question.strip()]
    return JSONResponse(_run_script("pdf_parser/run.py", args))


@router.post("/api/run/ppt_creator")
async def run_ppt_creator(brief: str = Form(...), slides: str = Form(""),
                           template: UploadFile | None = None):
    args = ["--brief", brief]
    if slides.strip():
        args += ["--slides", slides.strip()]
    template_path = _save_upload(template)
    if template_path:
        args += ["--template", str(template_path)]
    out_path = UPLOADS_DIR / f"{uuid.uuid4().hex[:8]}_deck.pptx"
    args += ["--out", str(out_path)]
    result = _run_script("ppt_creator/run.py", args)
    if out_path.exists():
        result["download"] = f"/api/download/{out_path.name}"
    return JSONResponse(result)


@router.post("/api/run/image_parser")
async def run_image_parser(file: UploadFile, instruction: str = Form("")):
    path = _save_upload(file)
    args = [str(path)]
    if instruction.strip():
        args += ["--instruction", instruction.strip()]
    return JSONResponse(_run_script("image_parser/run.py", args))


@router.post("/api/run/media_parser")
async def run_media_parser(file: UploadFile, question: str = Form("")):
    if not shutil.which("ffmpeg"):
        return JSONResponse({"ok": False, "stdout": "", "outputs": {},
                              "stderr": "ffmpeg not found on the server's PATH. Install ffmpeg to use this agent."})
    path = _save_upload(file)
    args = [str(path)]
    if question.strip():
        args += ["--question", question.strip()]
    return JSONResponse(_run_script("media_parser/run.py", args, timeout=1800))


@router.post("/api/run/site_crawler")
async def run_site_crawler(url: str = Form(...), question: str = Form(""),
                            max_pages: str = Form("20")):
    args = [url, "--max-pages", max_pages.strip() or "20"]
    if question.strip():
        args += ["--question", question.strip()]
    return JSONResponse(_run_script("site_crawler/run.py", args, timeout=900))


@router.get("/api/download/{filename}")
def download(filename: str):
    path = UPLOADS_DIR / filename
    return FileResponse(path, filename=filename)


if __name__ == "__main__":
    # Standalone dev entrypoint only -- when embedded in TurboAppGenerator,
    # only `router` above is imported and this block never runs. This copy
    # has no frontend of its own anymore (superseded by TurboAppGenerator's
    # native "Workflow"/"Utility Agents" tabs) -- this is API-only, for
    # exercising endpoints directly (e.g. via /docs) during development.
    import uvicorn
    from fastapi import FastAPI

    app = FastAPI(title="ContentAgents API (dev-only, API-only)")
    app.include_router(router)
    uvicorn.run(app, host="127.0.0.1", port=8420)
