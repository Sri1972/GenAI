"""
Workflow backend: a DAG of agents built on a canvas, spanning ContentAgents'
own reader/creator agents plus the cross-app pipeline nodes (Product Forge,
Web UI Generator, Web API Generator, MCP Generator) that only exist inside
TurboAppGenerator. Extracted out of ContentAgents/ui/server.py into its own
top-level module (a sibling of WebUIGenerator/, WebAPIGenerator/,
MCPGenerator/, ProductForge/, ContentAgents/) because it orchestrates all of
those, not just ContentAgents.

Two dependencies on ContentAgents, both read-only reuse:
  1. Its agent packages directly (excel_creator, pdf_creator, ppt_creator,
     visualization_agent, video_creator, common.claude_cli) -- the same
     reusable layer ContentAgents/ui/server.py itself imports for its own
     Utility Agents endpoint.
  2. Its library glue (LIBRARY_DIR / _item_dir / _reanswer_pdf_item /
     READER_AGENTS) -- so a reader node can load an item parsed via the
     standalone Utility Agents tab, without promoting the library store out
     of ContentAgents.

webui_generator / webapi_generator / mcp_generator / product_forge nodes
need no import coupling at all -- they're called over HTTP loopback against
this same TurboAppGenerator process (see API/server.py), exactly as before.

Usage: only meaningful mounted inside TurboAppGenerator's API/server.py
(where Forge and the generators are mounted too) -- there is no standalone
entrypoint for this module.
"""

import json
import re
import shutil
import sys
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

CONTENT_AGENTS_DIR = Path(__file__).resolve().parent.parent / "ContentAgents"
WORKFLOWS_DIR = Path(__file__).resolve().parent / "workflows"
WORKFLOWS_DIR.mkdir(exist_ok=True)

# ContentAgents' own agent packages -- the reusable layer behind the creator
# node branch below (same imports ContentAgents/ui/server.py keeps for its
# own standalone Utility Agents endpoint; two independent callers of the
# same shared code, not duplicated logic).
sys.path.insert(0, str(CONTENT_AGENTS_DIR))
from common.claude_cli import ClaudeCliError, extract_json, run_claude  # noqa: E402
from excel_creator.run import SYSTEM_PROMPT as EXCEL_CREATOR_PROMPT  # noqa: E402
from excel_creator.run import build_xlsx  # noqa: E402
from pdf_creator.run import SYSTEM_PROMPT as PDF_CREATOR_PROMPT  # noqa: E402
from pdf_creator.run import build_pdf  # noqa: E402
from ppt_creator.run import generate as ppt_generate  # noqa: E402
from visualization_agent.run import generate as viz_generate  # noqa: E402
from video_creator.run import VOICES as VIDEO_VOICES  # noqa: E402
from video_creator.run import generate as video_generate  # noqa: E402
from video_creator.run import generate_series as video_generate_series  # noqa: E402

# ContentAgents' library glue -- reused, not duplicated (Option A: Workflow
# depends on ContentAgents for this rather than promoting the library store).
# Both this module and API/server.py's own ContentAgents mount block import
# this same bare-named `server` module; Python caches it once, so whichever
# mounts first is fine -- both get the same shared LIBRARY_DIR.
sys.path.insert(0, str(CONTENT_AGENTS_DIR / "ui"))
from server import LIBRARY_DIR, READER_AGENTS, _friendly_error_message, _item_dir, _reanswer_pdf_item  # noqa: E402

router = APIRouter()


# --- Workflows: a DAG of agents built on the canvas. Any node can have
# multiple incoming edges (e.g. several readers feeding one creator) and/or
# multiple outgoing edges, as long as there's no cycle. A creator node
# combines every connected predecessor's output into its own prompt, each
# clearly labeled by source, so multi-source runs stay traceable.
# A reader node always references an existing library item (parse it once in
# Utility Agents, reuse it here) rather than re-uploading inline; a creator
# node's own "prompt" plus the upstream reader's metadata (serialized as
# text) becomes that creator's brief + reference content.

class WorkflowNode(BaseModel):
    id: str
    agent: str
    label: str = ""
    position: dict = {}
    libraryItemId: str | None = None
    url: str | None = None
    question: str | None = None  # reader-node-only: last question asked of pdf_parser (see /question endpoint)
    prompt: str | None = None
    # product_forge node config
    productIdea: str | None = None
    draftMode: bool | None = None
    artifactStages: list[str] | None = None  # None/empty = every stage (Forge's own default)
    # webui_generator / webapi_generator / mcp_generator node config
    projectName: str | None = None
    # webapi_generator-only config
    apiLanguage: str | None = None  # "python" | "java"
    apiAuthType: str | None = None  # "none" | "basic"
    # mcp_generator-only config -- typed directly on the node since a
    # connected Forge node's PRD/TRD/Specs never contains concrete source
    # details (a DB path or API URL isn't "product requirements")
    mcpInstructions: str | None = None
    # video_creator-only config -- must be one of video_creator.run.VOICES,
    # validated at run time (see _execute_workflow_run's video_creator branch)
    videoVoice: str | None = None
    # video_creator-only config -- produce several ~5-minute parts instead
    # of one long video (see video_creator.run.generate_series)
    videoSplit: bool | None = None


class WorkflowEdge(BaseModel):
    id: str
    source: str
    target: str


class WorkflowIn(BaseModel):
    workflow_id: str | None = None
    name: str
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]


class RunWorkflowRequest(BaseModel):
    auto_mode: bool = True


# --- Product Forge / generator bridge -- self-HTTP calls into the SAME
# TurboAppGenerator process (Forge and the generators are mounted at
# /forge and / respectively, in the same server -- see API/server.py).

CROSS_APP_AGENTS = ("product_forge", "webui_generator")

# The 7 artifact-producing Forge stages (mirrors ProductForge/config/agents.json's
# pipeline order/names -- "ideation" is the only non-artifact stage and always
# runs regardless of selection, so it isn't offered as a checkbox on the node).
FORGE_ARTIFACT_STAGES = [
    {"id": "prd", "name": "PRD — Product Requirements"},
    {"id": "trd", "name": "TRD — Technical Requirements"},
    {"id": "design", "name": "Solution Design"},
    {"id": "stories", "name": "Epics & User Stories"},
    {"id": "tasks", "name": "Implementation Tasks"},
    {"id": "specs", "name": "Technical Specs"},
    {"id": "test_cases", "name": "QA Test Cases"},
    {"id": "review", "name": "Final Review"},
]

# Same slot mapping UI/src/components/InstructionsModal.tsx's ARTIFACT_SLOT_MAP
# uses for its human-curated import -- but unlike that modal (which offers an
# "Additional Notes" catch-all for whatever else the user picks), this
# automated bridge has no human to judge relevance, so anything Forge produced
# that isn't PRD/TRD/Specs (Epics, Tasks, Test Cases, Review) is intentionally
# dropped rather than guessed at -- the Web UI Generator's `instructions` only
# ever contains what its own prompt design expects.
#
# NOTE: keys here have the ".md" suffix because that's the actual key shape
# GET /forge/api/export/project/{id} returns (confirmed directly against a
# real session: {"artifacts": {"PRD.md": "...", "TRD.md": "...", ...}}) --
# InstructionsModal.tsx's own ARTIFACT_SLOT_MAP uses bare names ('PRD' etc.)
# and appears to have the same mismatch, so its human-curated import likely
# always falls through to its "Additional Notes" catch-all today too; not
# fixed here since that's a different, pre-existing file this task didn't
# touch.
_FORGE_ARTIFACT_SLOT_MAP = {
    "PRD.md": "prd", "TRD.md": "trd", "SPECS.md": "specs", "SOLUTION_DESIGN.md": "specs",
}
_FORGE_SLOT_MARKERS = {
    "prd": "## PRD — Product Requirements",
    "trd": "## TRD — Technical Requirements",
    "specs": "## Specs — Technical Specifications",
}


def _combine_forge_artifacts(artifacts: dict[str, str]) -> str:
    docs = {"prd": "", "trd": "", "specs": ""}
    for name, content in artifacts.items():
        if not content:
            continue
        slot = _FORGE_ARTIFACT_SLOT_MAP.get(name)
        if slot:
            docs[slot] = content

    parts = [f"{_FORGE_SLOT_MARKERS[slot]}\n\n{text.strip()}" for slot, text in docs.items() if text.strip()]
    return "\n\n---\n\n".join(parts)


def _workflow_dir(workflow_id: str) -> Path:
    d = WORKFLOWS_DIR / workflow_id
    if not (d / "definition.json").exists():
        raise HTTPException(404, "Unknown workflow")
    return d


def _slugify_workflow_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    return slug or "workflow"


def _unique_workflow_slug(name: str) -> str:
    """Disk directory name assigned to a brand-new workflow -- the
    workflow's own name, slugified, so a run's intermediate artifacts land
    under a name a user can actually find on disk instead of an opaque hash.
    Stable once assigned: renaming the workflow later doesn't move its
    directory, since that would cascade into active runs, in-flight
    frontend state, and download URLs that all key off this id today."""
    base = _slugify_workflow_name(name)
    slug, n = base, 2
    while (WORKFLOWS_DIR / slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


def _migrate_legacy_workflow_dirs():
    """One-time upgrade for workflows saved before workflow_id became a
    name-slug (on disk under an opaque hex id) -- renames each such
    directory to match its own name in place (dragging its runs/
    subdirectory along for free), so old workflows adopt the new scheme
    without the user having to resave them."""
    for d in list(WORKFLOWS_DIR.iterdir()):
        if not d.is_dir():
            continue
        def_path = d / "definition.json"
        if not def_path.exists():
            continue
        try:
            definition = json.loads(def_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if d.name == _slugify_workflow_name(definition.get("name") or d.name):
            continue
        target_name = _unique_workflow_slug(definition.get("name") or d.name)
        definition["workflow_id"] = target_name
        def_path.write_text(json.dumps(definition, indent=2), encoding="utf-8")
        d.rename(WORKFLOWS_DIR / target_name)


_migrate_legacy_workflow_dirs()


def _topological_order(nodes: list[dict], edges: list[dict]) -> list[dict]:
    """General DAG order (Kahn's algorithm) -- any node can have multiple
    incoming and/or outgoing edges (e.g. several readers feeding one
    creator), as long as there's no cycle."""
    if not nodes:
        return []
    by_id = {n["id"]: n for n in nodes}
    node_ids = set(by_id)
    # Ignore edges left dangling by a deleted node rather than erroring on them.
    edges = [e for e in edges if e["source"] in node_ids and e["target"] in node_ids]

    incoming = {nid: 0 for nid in node_ids}
    outgoing: dict[str, list[str]] = {nid: [] for nid in node_ids}
    for e in edges:
        incoming[e["target"]] += 1
        outgoing[e["source"]].append(e["target"])

    remaining = dict(incoming)
    queue = deque(nid for nid, count in incoming.items() if count == 0)
    order = []
    while queue:
        nid = queue.popleft()
        order.append(by_id[nid])
        for nxt in outgoing[nid]:
            remaining[nxt] -= 1
            if remaining[nxt] == 0:
                queue.append(nxt)

    if len(order) != len(nodes):
        raise HTTPException(400, "Workflow contains a cycle -- every step must eventually reach an end, no loops.")
    return order


def _run_creator_node(agent: str, prompt: str, context: str | None, out_dir: Path,
                       on_progress: Callable[[str], None] | None = None, voice: str | None = None,
                       split: bool = False) -> Path | list[Path]:
    prompt_text = f"BRIEF: {prompt}" + (f"\n\nREFERENCE CONTENT:\n{context}" if context else "")
    out_dir.mkdir(parents=True, exist_ok=True)
    # Intermediate artifacts, kept alongside the final output file so a run's
    # directory is self-contained -- what was actually sent (request.json)
    # and the structured plan/spec the LLM produced before rendering
    # (result.json), not just the rendered file itself.
    (out_dir / "request.json").write_text(
        json.dumps({"prompt": prompt, "context": context}, indent=2), encoding="utf-8")

    if agent == "excel_creator":
        if on_progress:
            on_progress("Drafting the workbook with Claude...")
        result = run_claude(prompt_text, system_prompt=EXCEL_CREATOR_PROMPT, allowed_tools=[])
        plan = extract_json(result["result"])
        if on_progress:
            on_progress("Building the spreadsheet...")
        out_path = out_dir / "output.xlsx"
        build_xlsx(plan, out_path)
    elif agent == "pdf_creator":
        if on_progress:
            on_progress("Drafting the document with Claude...")
        result = run_claude(prompt_text, system_prompt=PDF_CREATOR_PROMPT, allowed_tools=[])
        plan = extract_json(result["result"])
        if on_progress:
            on_progress("Building the PDF...")
        out_path = out_dir / "output.pdf"
        build_pdf(plan, out_path)
    elif agent == "ppt_creator":
        # Routed through the shared generate() (same as visualization_agent
        # below) instead of a manual run_claude+build_pptx dance -- picks up
        # the real AVAILABLE LAYOUTS context and the default MobilityGlobal
        # template/native-chart-table-chevron-gantt support for free, and
        # keeps this in sync with the Utility Agents path going forward.
        if on_progress:
            on_progress("Drafting the deck with Claude...")
        out_path = out_dir / "output.pptx"
        plan = ppt_generate(prompt, out_path, images_dir=out_dir / "template_images", context=context)
    elif agent == "visualization_agent":
        # context here is upstream metadata prose, not a clean table, so
        # generate() has the planning call extract its own data rows (see
        # run.py's SYSTEM_PROMPT "data" field). viz_generate has no
        # on_progress hook of its own (unlike video_creator's), so this is
        # the only checkpoint available for this node.
        if on_progress:
            on_progress("Building the chart with Claude...")
        out_path = out_dir / "output.html"
        plan = viz_generate(prompt, out_path, raw_context=context)
    else:  # video_creator -- the only creator whose render step takes long
        # enough (real per-frame headless-browser rendering + ffmpeg, not a
        # quick template fill) that a bare spinner would leave the run
        # looking stuck; on_progress streams its real render-subprocess
        # output into this node's live-polled log/summary instead.
        if split:
            parts = video_generate_series(prompt, out_dir, context=context, on_progress=on_progress, voice=voice)
            out_paths = []
            for i, (spec, part_path) in enumerate(parts, start=1):
                renamed = out_dir / f"output_part{i}.mp4"
                part_path.rename(renamed)
                out_paths.append(renamed)
            (out_dir / "result.json").write_text(
                json.dumps([spec for spec, _ in parts], indent=2), encoding="utf-8")
            return out_paths
        out_path = out_dir / "output.mp4"
        plan = video_generate(prompt, out_path, context=context, on_progress=on_progress, voice=voice)
        (out_dir / "result.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
        return out_path

    (out_dir / "result.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return out_path


@router.post("/api/workflows")
async def save_workflow(wf: WorkflowIn):
    workflow_id = wf.workflow_id or _unique_workflow_slug(wf.name)
    wf_dir = WORKFLOWS_DIR / workflow_id
    wf_dir.mkdir(parents=True, exist_ok=True)
    definition = {
        "workflow_id": workflow_id, "name": wf.name,
        "nodes": [n.model_dump() for n in wf.nodes], "edges": [e.model_dump() for e in wf.edges],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    (wf_dir / "definition.json").write_text(json.dumps(definition, indent=2), encoding="utf-8")
    return JSONResponse(definition)


@router.get("/api/workflows")
async def list_workflows():
    workflows = []
    for d in WORKFLOWS_DIR.iterdir():
        p = d / "definition.json"
        if p.exists():
            workflows.append(json.loads(p.read_text(encoding="utf-8")))
    workflows.sort(key=lambda w: w.get("updated_at", ""), reverse=True)
    return JSONResponse({"workflows": workflows})


@router.get("/api/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    return JSONResponse(json.loads((_workflow_dir(workflow_id) / "definition.json").read_text(encoding="utf-8")))


@router.delete("/api/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str):
    shutil.rmtree(WORKFLOWS_DIR / workflow_id, ignore_errors=True)
    return JSONResponse({"ok": True})


# --- Async workflow runner. Forge and the generator run for minutes, not
# seconds, so this can no longer be one blocking POST that returns every
# result at once (the old behavior, still fine for pure reader/creator
# workflows). /run now returns a run_id immediately; the frontend polls
# /status and, when a node is paused for review (HITL / Auto Mode off),
# calls /continue to advance it. Run state is in-memory only (ephemeral,
# single-server).

WORKFLOW_RUNS: dict[str, dict] = {}
# workflow_id -> its most recently started run_id -- lets the frontend
# reattach to an in-progress run after any remount (switching to a different
# tab and back, re-selecting the same workflow from the sidebar, a page
# reload), instead of only being able to see it from the exact browser tab
# that originally clicked Run.
WORKFLOW_LATEST_RUN: dict[str, str] = {}


def _forge_poll_stage_done(base_url: str, session_id: str, timeout_s: float = 1800) -> dict:
    """Poll until the single stage just kicked off (via /run-stage) finishes --
    i.e. status is no longer "running". Safe here because nothing else is
    concurrently driving this session (we call /run-stage exactly once per
    call to this)."""
    deadline = time.monotonic() + timeout_s
    while True:
        time.sleep(2)
        st = httpx.get(f"{base_url}forge/api/state/{session_id}", timeout=30).json()
        if st.get("status") != "running":
            return st
        if time.monotonic() > deadline:
            raise RuntimeError("Product Forge stage timed out.")


def _append_log(run_state: dict, node_id: str, line: str) -> None:
    """Appends one line to a node's progress log and mirrors it as the
    node's current one-line summary -- polled by the frontend so the
    Workflow canvas can show what's actually happening, not just a spinner."""
    node = run_state["nodes"][node_id]
    node.setdefault("log", []).append(line)
    node["summary"] = line


def _forge_poll_all_done(base_url: str, session_id: str, run_state: dict, node_id: str,
                          timeout_s: float = 3600) -> dict:
    """Poll until the whole session (kicked off via /run-all or
    /run-selected) reaches "complete" -- ignores transient "paused" blips
    between stages, since that background loop advances through them on its
    own. Logs a line each time the current stage changes, so Auto Mode runs
    -- which otherwise have no natural pause point to report progress at --
    still show live movement on the canvas."""
    deadline = time.monotonic() + timeout_s
    last_stage_idx = -1
    while True:
        time.sleep(2)
        st = httpx.get(f"{base_url}forge/api/state/{session_id}", timeout=30).json()
        status = st.get("status")
        stages = st.get("stages") or []
        stage_idx = st.get("current_stage", 0)
        if stage_idx != last_stage_idx and stage_idx < len(stages):
            last_stage_idx = stage_idx
            stage = stages[stage_idx]
            verb = "Skipping" if stage.get("status") == "skipped" else "Running"
            _append_log(run_state, node_id,
                        f"{verb} stage {stage_idx + 1}/{st.get('total_stages', '?')}: {stage['name']}")
        if status == "complete":
            _append_log(run_state, node_id, "All selected stages complete.")
            return st
        if status == "cancelled":
            raise RuntimeError("Product Forge session was cancelled.")
        if time.monotonic() > deadline:
            raise RuntimeError("Product Forge session timed out.")


def _run_forge_node(node: dict, run_state: dict) -> dict:
    node_id = node["id"]
    idea = (node.get("productIdea") or "").strip()
    if not idea:
        raise ValueError("This Product Forge node has no product idea typed in yet.")
    project_name = (node.get("projectName") or "").strip()
    if not project_name:
        raise ValueError("This Product Forge node needs a project name before it can run.")
    base_url = run_state["base_url"]
    auto_mode = run_state["auto_mode"]
    # None/empty = every stage (Forge's own default -- also true for older
    # saved nodes from before this field existed).
    stage_ids = node.get("artifactStages") or None

    _append_log(run_state, node_id, f"Starting Product Forge session “{project_name}”...")
    resp = httpx.post(f"{base_url}forge/api/start",
                       json={"idea": idea, "name": project_name, "draft_mode": bool(node.get("draftMode"))},
                       timeout=30)
    resp.raise_for_status()
    session_id = resp.json()["session_id"]

    if auto_mode:
        # /run-selected requires an explicit stage_ids list (no "None" over
        # the wire) -- /run-all is the "everything" equivalent.
        if stage_ids:
            httpx.post(f"{base_url}forge/api/run-selected",
                       json={"session_id": session_id, "stage_ids": stage_ids}, timeout=30).raise_for_status()
        else:
            httpx.post(f"{base_url}forge/api/run-all", json={"session_id": session_id}, timeout=30).raise_for_status()
        _forge_poll_all_done(base_url, session_id, run_state, node_id)
    else:
        # Forge's stepwise /run-stage has no skip concept -- every stage
        # still runs (and costs) regardless of selection, since there's no
        # way to advance past one for free outside of /run-selected's own
        # all-the-way-through loop. What the selection DOES control here is
        # which stage's completion actually interrupts the human -- anything
        # not selected (and the non-artifact "ideation" stage) just advances
        # straight through with no pause.
        while True:
            pre = httpx.get(f"{base_url}forge/api/state/{session_id}", timeout=30).json()
            about_to_run = (pre.get("stages") or [None])[pre.get("current_stage", 0)] \
                if pre.get("current_stage", 0) < len(pre.get("stages") or []) else None
            _append_log(run_state, node_id,
                        f"Running stage: {about_to_run['name']}" if about_to_run else "Running Forge...")

            httpx.post(f"{base_url}forge/api/run-stage", json={"session_id": session_id}, timeout=30).raise_for_status()
            st = _forge_poll_stage_done(base_url, session_id)
            status = st.get("status")
            if status == "complete":
                _append_log(run_state, node_id, "All stages complete.")
                break
            if status != "paused":
                raise RuntimeError(f"Product Forge session ended with status '{status}'.")

            has_artifact = bool(about_to_run and about_to_run.get("artifact"))
            is_selected = not stage_ids or (about_to_run and about_to_run["id"] in stage_ids)
            if not (has_artifact and is_selected):
                continue  # advance straight through, no pause

            done, total = st.get("current_stage", 0), st.get("total_stages", "?")
            _append_log(run_state, node_id, f"Stage {done}/{total} complete — review artifacts, then Continue.")
            run_state["nodes"][node_id]["status"] = "awaiting_review"
            run_state["run_status"] = "paused"
            run_state["awaiting_node_id"] = node_id
            run_state["pause_event"].wait()
            run_state["pause_event"].clear()
            run_state["run_status"] = "running"
            run_state["nodes"][node_id]["status"] = "running"

    export = httpx.get(f"{base_url}forge/api/export/project/{session_id}", timeout=30).json()
    combined = _combine_forge_artifacts(export.get("artifacts") or {})
    if not combined.strip():
        raise RuntimeError("Product Forge session finished with no artifacts to hand off.")
    return {
        "label": f"Product Forge – {project_name}",
        "content": combined,
        "forge_session_id": session_id,
        "forge_product_idea": export.get("product_idea") or idea,
    }


def _run_prompt_generator_node(node: dict, run_state: dict, predecessors: dict, outputs: dict, *,
                                mode: str, api_options: dict | None, label: str) -> dict:
    """Shared by webui_generator and webapi_generator -- both are the same
    /api/generate + /api/jobs + /api/generate/progress dance, differing only
    in `mode`/`api_options` and the node's own display label."""
    node_id = node["id"]
    project_name = (node.get("projectName") or "").strip()
    if not project_name:
        raise ValueError(f"This {label} node needs a project name before it can run.")
    base_url = run_state["base_url"]
    pred_ids = predecessors.get(node_id, [])
    forge_output = next((outputs[pid] for pid in pred_ids if "forge_session_id" in outputs.get(pid, {})), None)
    if not forge_output:
        raise ValueError(f"Connect a Product Forge node to this {label} node first.")

    idea = forge_output.get("forge_product_idea") or ""
    prompt = f"Build the {label.lower()} for: {idea[:200]}" if idea else f"Build the {label.lower()} for {project_name}."
    _append_log(run_state, node_id, f"Starting generation for “{project_name}”...")
    body = {"prompt": prompt, "project_name": project_name, "instructions": forge_output["content"], "mode": mode}
    if api_options is not None:
        body["api_options"] = api_options
    resp = httpx.post(f"{base_url}api/generate", json=body, timeout=30)
    resp.raise_for_status()
    request_id = resp.json()["requestId"]

    seen_log_len = 0
    deadline = time.monotonic() + 1800
    while True:
        time.sleep(3)
        # Best-effort -- the progress log is a nice-to-have live tail, never
        # worth failing the whole node over if this particular poll hiccups.
        try:
            prog = httpx.get(f"{base_url}api/generate/progress/{request_id}", timeout=10).json()
            new_lines = (prog.get("log") or [])[seen_log_len:]
            for line in new_lines:
                _append_log(run_state, node_id, line)
            seen_log_len += len(new_lines)
        except Exception:
            pass

        job = httpx.get(f"{base_url}api/jobs/{request_id}", timeout=30).json()
        status = job.get("status")
        if status == "completed":
            result = job.get("result") or {}
            url = result.get("url")
            _append_log(run_state, node_id, f"Generated at {url}." if url else "Generation complete.")
            return {
                "label": f"{label} – {project_name}",
                "content": f"Generated at {url}." if url else "Generation complete.",
                "preview_url": url,
            }
        if status == "failed":
            raise RuntimeError(job.get("error") or f"{label} failed.")
        if time.monotonic() > deadline:
            raise RuntimeError(f"{label} timed out after 30 minutes.")


def _run_webui_generator_node(node: dict, run_state: dict, predecessors: dict, outputs: dict) -> dict:
    return _run_prompt_generator_node(node, run_state, predecessors, outputs,
                                       mode="webapp", api_options=None, label="Web UI Generator")


def _run_webapi_generator_node(node: dict, run_state: dict, predecessors: dict, outputs: dict) -> dict:
    api_options = {
        "language": node.get("apiLanguage") or "python",
        "auth_type": node.get("apiAuthType") or "none",
        "rate_limit": 100, "endpoints": [], "include_docker": False, "include_tests": True,
    }
    return _run_prompt_generator_node(node, run_state, predecessors, outputs,
                                       mode="api", api_options=api_options, label="Web API Generator")


def _run_mcp_generator_node(node: dict, run_state: dict, predecessors: dict, outputs: dict) -> dict:
    """Unlike webui_generator/webapi_generator, a connected Product Forge
    node is optional here, not required -- Forge's PRD/TRD/Specs is business
    context, never a concrete database path or API URL, so it can enrich the
    instructions but can never satisfy them on its own. The node's own
    mcpInstructions field is where the actual source (and, per the user's
    own design, the ONLY place) has to state that concretely -- see
    _run_mcp_generate_from_instructions in API/server.py for the
    extract-then-really-introspect logic that enforces this."""
    node_id = node["id"]
    project_name = (node.get("projectName") or "").strip()
    if not project_name:
        raise ValueError("This MCP Generator node needs a project name before it can run.")

    own_instructions = (node.get("mcpInstructions") or "").strip()
    pred_ids = predecessors.get(node_id, [])
    sources = [outputs[pid] for pid in pred_ids if pid in outputs]
    parts = [f"--- Source: {s['label']} ---\n{s['content']}" for s in sources]
    if own_instructions:
        parts.append(own_instructions)
    instructions = "\n\n---\n\n".join(parts).strip()
    if not instructions:
        raise ValueError(
            "This MCP Generator node has no instructions -- type the exact database file path "
            "and/or API base URL (with credentials if it needs auth) directly on the node."
        )

    base_url = run_state["base_url"]
    _append_log(run_state, node_id, f"Starting MCP generation for “{project_name}”...")
    resp = httpx.post(f"{base_url}api/mcp/generate-from-instructions",
                       json={"projectName": project_name, "instructions": instructions}, timeout=30)
    resp.raise_for_status()
    request_id = resp.json()["requestId"]

    seen_log_len = 0
    deadline = time.monotonic() + 1800
    while True:
        time.sleep(3)
        try:
            prog = httpx.get(f"{base_url}api/generate/progress/{request_id}", timeout=10).json()
            new_lines = (prog.get("log") or [])[seen_log_len:]
            for line in new_lines:
                _append_log(run_state, node_id, line)
            seen_log_len += len(new_lines)
        except Exception:
            pass

        job = httpx.get(f"{base_url}api/jobs/{request_id}", timeout=30).json()
        status = job.get("status")
        if status == "completed":
            result = job.get("result") or {}
            url = result.get("url")
            tool_count = len(result.get("tools") or [])
            summary = f"MCP server running at {url} ({tool_count} tool(s))." if url else "MCP server generated."
            _append_log(run_state, node_id, summary)
            return {"label": f"MCP Generator – {project_name}", "content": summary, "preview_url": url}
        if status == "failed":
            raise RuntimeError(job.get("error") or "MCP generation failed.")
        if time.monotonic() > deadline:
            raise RuntimeError("MCP generation timed out after 30 minutes.")


def _execute_workflow_run(run_id: str):
    run_state = WORKFLOW_RUNS[run_id]
    order, predecessors, outputs = run_state["order"], run_state["predecessors"], run_state["outputs"]
    workflow_id, run_dir = run_state["workflow_id"], run_state["run_dir"]
    auto_mode = run_state["auto_mode"]

    for node in order:
        node_id, agent = node["id"], node["agent"]
        run_state["current_node_id"] = node_id
        run_state["nodes"][node_id]["status"] = "running"
        # Every node gets at least this one line the instant it starts --
        # without it, a node sits as a bare spinner with no summary text at
        # all until its first real progress update (or completion), which
        # for a reader node with no interim logging at all previously meant
        # NO feedback whatsoever while it ran.
        _append_log(run_state, node_id, f"Starting {agent}...")
        try:
            if agent in READER_AGENTS:
                item_id = node.get("libraryItemId")
                if not item_id:
                    raise ValueError("No library item selected for this node -- add/parse it in Utility Agents first.")
                item_dir = _item_dir(item_id)
                item_info = json.loads((item_dir / "item.json").read_text(encoding="utf-8"))
                if agent == "pdf_parser":
                    # Always re-asks whatever question is currently on the
                    # node -- so Run alone reflects the box's current
                    # contents, with no separate "Ask" click required first
                    # and no risk of running against a stale answer.
                    _append_log(run_state, node_id, "Re-answering with Claude based on the current question...")
                    metadata = _reanswer_pdf_item(item_dir, node.get("question"))
                else:
                    _append_log(run_state, node_id, "Loading stored metadata...")
                    metadata = json.loads((item_dir / "metadata.json").read_text(encoding="utf-8"))
                content = json.dumps(metadata, indent=2)
                outputs[node_id] = {"label": f"{agent} – {item_info.get('filename', item_id)}", "content": content}
                # Copied into the run's own directory (alongside creator
                # nodes' request/result.json) so the whole run is
                # self-contained on disk, not just referencing the library
                # item's storage elsewhere.
                node_dir = run_dir / node_id
                node_dir.mkdir(parents=True, exist_ok=True)
                (node_dir / "input.json").write_text(content, encoding="utf-8")
                summary = f"Loaded metadata from library item {item_id} ({len(content)} chars)."
                run_state["nodes"][node_id].update(status="ok", summary=summary, extra={})
            elif agent == "product_forge":
                result = _run_forge_node(node, run_state)
                outputs[node_id] = result
                run_state["nodes"][node_id].update(
                    status="ok", summary="Requirements gathered from Product Forge.",
                    extra={"forge_session_id": result["forge_session_id"]},
                )
            elif agent == "webui_generator":
                result = _run_webui_generator_node(node, run_state, predecessors, outputs)
                outputs[node_id] = result
                run_state["nodes"][node_id].update(
                    status="ok", summary=result["content"],
                    extra={"preview_url": result.get("preview_url")},
                )
            elif agent == "webapi_generator":
                result = _run_webapi_generator_node(node, run_state, predecessors, outputs)
                outputs[node_id] = result
                run_state["nodes"][node_id].update(
                    status="ok", summary=result["content"],
                    extra={"preview_url": result.get("preview_url")},
                )
            elif agent == "mcp_generator":
                result = _run_mcp_generator_node(node, run_state, predecessors, outputs)
                outputs[node_id] = result
                run_state["nodes"][node_id].update(
                    status="ok", summary=result["content"],
                    extra={"preview_url": result.get("preview_url")},
                )
            else:  # excel_creator / pdf_creator / ppt_creator
                prompt = node.get("prompt") or "Create the file based on the provided content."
                sources = [outputs[pid] for pid in predecessors.get(node_id, []) if pid in outputs]
                combined_context = "\n\n".join(
                    f"--- Source: {s['label']} ---\n{s['content']}" for s in sources
                ) if sources else None
                node_voice = node.get("videoVoice")
                node_split = agent == "video_creator" and bool(node.get("videoSplit"))
                result = _run_creator_node(
                    agent, prompt, combined_context, run_dir / node_id,
                    on_progress=lambda line: _append_log(run_state, node_id, line),
                    voice=node_voice if node_voice in VIDEO_VOICES else None,
                    split=node_split,
                )
                if isinstance(result, list):
                    summary = f"Created {len(result)} part(s)" + (f" from {len(sources)} source(s)." if sources else ".")
                    outputs[node_id] = {"label": f"{agent} output ({len(result)} parts)", "content": summary}
                    downloads = [
                        {"label": f"Part {i}",
                         "url": f"/api/workflows/{workflow_id}/runs/{run_state['run_id']}/download/{node_id}?part={i}"}
                        for i in range(1, len(result) + 1)
                    ]
                    run_state["nodes"][node_id].update(status="ok", summary=summary, extra={"downloads": downloads})
                else:
                    out_path = result
                    summary = f"Created {out_path.name}" + (f" from {len(sources)} source(s)." if sources else ".")
                    outputs[node_id] = {"label": f"{agent} output ({out_path.name})", "content": summary}
                    run_state["nodes"][node_id].update(
                        status="ok", summary=summary,
                        extra={"download": f"/api/workflows/{workflow_id}/runs/{run_state['run_id']}/download/{node_id}"},
                    )
        except ClaudeCliError as exc:
            run_state["nodes"][node_id].update(status="error", summary=_friendly_error_message(str(exc)))
            run_state["run_status"] = "error"
            return
        except Exception as exc:
            run_state["nodes"][node_id].update(status="error", summary=str(exc))
            run_state["run_status"] = "error"
            return

        # Uniform HITL pause: with Auto Mode off, every node -- including the
        # last one -- pauses for an explicit Continue before the run is
        # considered done, so there's always a final review step.
        if not auto_mode:
            run_state["run_status"] = "paused"
            run_state["awaiting_node_id"] = node_id
            run_state["pause_event"].wait()
            run_state["pause_event"].clear()

    run_state["run_status"] = "complete"
    run_state["current_node_id"] = None
    run_state["awaiting_node_id"] = None


@router.post("/api/workflows/{workflow_id}/run")
async def run_workflow(workflow_id: str, req: RunWorkflowRequest, request: Request):
    wf_dir = _workflow_dir(workflow_id)
    definition = json.loads((wf_dir / "definition.json").read_text(encoding="utf-8"))
    nodes, edges = definition["nodes"], definition["edges"]
    order = _topological_order(nodes, edges)

    predecessors: dict[str, list[str]] = {n["id"]: [] for n in nodes}
    for e in edges:
        if e["target"] in predecessors and e["source"] in predecessors:
            predecessors[e["target"]].append(e["source"])

    run_id = uuid.uuid4().hex[:12]
    run_state = {
        "workflow_id": workflow_id, "run_id": run_id, "auto_mode": req.auto_mode,
        "run_status": "running", "order": order, "predecessors": predecessors, "outputs": {},
        "run_dir": wf_dir / "runs" / run_id, "base_url": str(request.base_url),
        "current_node_id": None, "awaiting_node_id": None, "pause_event": threading.Event(),
        "nodes": {n["id"]: {"status": "pending", "summary": None, "extra": {}} for n in nodes},
    }
    WORKFLOW_RUNS[run_id] = run_state
    WORKFLOW_LATEST_RUN[workflow_id] = run_id

    threading.Thread(target=_execute_workflow_run, args=(run_id,), daemon=True).start()
    return JSONResponse({"run_id": run_id})


def _run_status_payload(run_state: dict) -> dict:
    return {
        "run_id": run_state["run_id"],
        "run_status": run_state["run_status"],
        "awaiting_node_id": run_state["awaiting_node_id"],
        "current_node_id": run_state["current_node_id"],
        "nodes": [{"node_id": nid, **info} for nid, info in run_state["nodes"].items()],
    }


@router.get("/api/workflows/{workflow_id}/runs/{run_id}/status")
async def get_workflow_run_status(workflow_id: str, run_id: str):
    run_state = WORKFLOW_RUNS.get(run_id)
    if not run_state:
        raise HTTPException(404, "Unknown run -- the server may have restarted since this run started.")
    return JSONResponse(_run_status_payload(run_state))


@router.get("/api/workflows/{workflow_id}/runs/latest")
async def get_latest_workflow_run(workflow_id: str):
    """Lets a freshly (re)mounted canvas reattach to whatever run is already
    in progress for this workflow, instead of only the browser tab/component
    instance that originally clicked Run ever being able to see it."""
    run_id = WORKFLOW_LATEST_RUN.get(workflow_id)
    run_state = WORKFLOW_RUNS.get(run_id) if run_id else None
    if not run_state:
        return JSONResponse({"run_id": None})
    return JSONResponse(_run_status_payload(run_state))


@router.post("/api/workflows/{workflow_id}/runs/{run_id}/continue/{node_id}")
async def continue_workflow_run(workflow_id: str, run_id: str, node_id: str):
    run_state = WORKFLOW_RUNS.get(run_id)
    if not run_state:
        raise HTTPException(404, "Unknown run")
    if run_state["run_status"] != "paused" or run_state["awaiting_node_id"] != node_id:
        raise HTTPException(409, "This node isn't currently awaiting Continue.")
    run_state["pause_event"].set()
    return JSONResponse({"ok": True})


@router.get("/api/workflows/{workflow_id}/runs/{run_id}/download/{node_id}")
async def download_workflow_output(workflow_id: str, run_id: str, node_id: str, part: int | None = None):
    node_dir = WORKFLOWS_DIR / workflow_id / "runs" / run_id / node_id
    # `part` selects one of a split video_creator node's several
    # output_part{N}.mp4 files (see _run_creator_node) instead of the usual
    # single output.* file every other node produces.
    pattern = f"output_part{part}.*" if part else "output.*"
    output = next((f for f in node_dir.glob(pattern)), None) if node_dir.exists() else None
    if not output:
        raise HTTPException(404, "No output file for this node.")
    if output.suffix == ".html":
        return FileResponse(output, media_type="text/html")  # viewable inline -- see library_download_item
    if output.suffix == ".mp4":
        return FileResponse(output, media_type="video/mp4")  # viewable inline -- see library_download_item
    return FileResponse(output, filename=output.name)
