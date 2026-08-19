#!/usr/bin/env python3
"""
Figma Wireframe Agent
=====================
LLM-powered agent that takes a plain-English wireframe prompt and builds
a complete interactive Figma prototype by calling the Figma MCP server.

Architecture:
    User prompt
        ↓
    prompt_to_figma_agent.py  (this file)
        ↓  AWS Bedrock / Claude (tool_use loop)
        ↓  POST http://MCP_SERVER/mcp
    server.py  (Figma MCP)
        ↓  WebSocket relay
    relay.py → figma-console-mcp → Figma Desktop

Usage:
    python prompt_to_figma_agent.py "Create a 3-screen sports app with Dashboard, Players and Match Detail"
    python prompt_to_figma_agent.py --prompt "E-commerce checkout flow: Cart, Shipping, Payment, Confirmation"
    python prompt_to_figma_agent.py --interactive          # REPL mode — switch modes on the fly
    python prompt_to_figma_agent.py --server               # run as FastAPI server (POST /generate)

Modes (--mode):
    new      (default) Start fresh — deletes all existing frames and builds everything from
                       scratch. Warns if existing frames are found (confirmation flow).
                       Tracks expected screens and resumes if the LLM stops early.

    edit               Edit existing — inspects what's already on the canvas and either makes
                       surgical edits to existing frames OR adds new frames to the right.
                       Never deletes existing frames. Use for enhancements, tweaks, or
                       adding screens to an existing prototype.

    replace            Rebuild specific — pre-deletes only the frames whose names match what
                       you're about to build, then rebuilds them fresh. Existing frames with
                       different names are untouched. Tracks and resumes like 'new'.

Examples:
    # Build a new wireframe from scratch
    python prompt_to_figma_agent.py "Automotive dashboard: Sales Overview, Inventory, Forecast"

    # Edit existing screens or add new ones alongside them
    python prompt_to_figma_agent.py "Add a filter panel to the Inventory screen" --mode edit

    # Add a new Settings screen without touching existing screens
    python prompt_to_figma_agent.py "Add a Settings screen with profile and notifications" --mode edit

    # Rebuild specific screens from scratch (others untouched)
    python prompt_to_figma_agent.py "Redesign Sales Overview with a full-width chart" --mode replace

    # Interactive REPL — switch modes without restarting
    python prompt_to_figma_agent.py --interactive
    # Then at the prompt type: mode replace
    # Then: Redesign the Dashboard with KPI cards

Prerequisites:
    1. figma/mcp/start.bat running  (MCP server + relay)
    2. Figma Desktop open with Desktop Bridge plugin showing "Local Ready"
"""

import argparse
import json
import logging
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Generator

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("prompt-to-figma-agent")

# ── Shared infrastructure ──────────────────────────────────────────────────────
from figma_agent_shared import (
    MCP_SERVER, MODEL_ID, MAX_TOKENS,
    mcp_call, mcp_initialize, mcp_list_tools, mcp_call_tool,
    get_openai_client, tools_to_openai,
    _fetch_figma_url,
    SYSTEM_PROMPT, VALIDATION_PROMPT,
    run_validation_pass,
    reset_token_usage, record_token_usage, get_token_usage,
    format_token_usage, set_figma_run_id, _get_figma_run_id,
)

MAX_TURNS = 120  # detailed 3-4 screen + modals + brand logos uses 60-80 turns; allow headroom for continuations

# ── Load design system brand tokens ───────────────────────────────────────────
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).parent.parent.parent))
from config_ds import DS_TOKENS_FILE as _DS_TOKENS_FILE

_BRAND_TOKENS: dict = {}
if _DS_TOKENS_FILE.exists():
    try:
        _BRAND_TOKENS = json.loads(_DS_TOKENS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass

# Mode context injected into the user prompt — 3 user-facing modes
MODE_CONTEXT = {
    "new": (
        "IMPORTANT — CANVAS MODE: new wireframe\n"
        "The canvas has been cleared for you. Build ALL screens from scratch.\n"
        "Do NOT call figma_list_frames or check for existing frames — start building immediately.\n"
        "Create every screen described in the user request. Do not skip any.\n"
        "\n"
        "You MUST complete ALL 4 phases before stopping:\n"
        "  Phase 1: Build every screen completely (sidebar + header + ALL content)\n"
        "  Phase 2: Create ALL overlay/modal frames described in the prompt\n"
        "  Phase 3: Wire EVERYTHING with figma_wire_all (nav, buttons, overlays)\n"
        "  Phase 4: Set prototype start + verify\n"
        "Do NOT stop after Phase 1. A wireframe without modals and wiring is broken.\n"
    ),
    "edit": (
        "IMPORTANT — CANVAS MODE: edit wireframe\n"
        "You are working on an EXISTING prototype. The canvas already has frames.\n"
        "\n"
        "DECIDE based on the user's request:\n"
        "  A) MODIFY existing screens — make surgical edits without deleting frames:\n"
        "     1. Call figma_list_frames to identify relevant frame(s).\n"
        "     2. Call figma_inspect_frame on each relevant frame to read the node tree.\n"
        "     3. Use figma_update_node to change specific nodes.\n"
        "     4. Use normal create tools to ADD new elements inside existing frames.\n"
        "     5. Never delete frames unless the user explicitly asks.\n"
        "\n"
        "  B) ADD new screens — place new frames to the right of existing ones:\n"
        "     1. Call figma_list_frames to find the rightmost existing frame.\n"
        "     2. Place ALL new frames to the RIGHT with 100px gap.\n"
        "     3. Never overlap or replace existing frames.\n"
        "     4. Wire new screens into existing sidebar navigation.\n"
        "\n"
        "You can do BOTH in one run — edit some frames AND add new ones.\n"
        "SCOPE: Only touch what the user asked to change or add.\n"
    ),
    "replace": (
        "IMPORTANT — CANVAS MODE: replace wireframe\n"
        "Specific frames have been pre-deleted for you. Build them fresh.\n"
        "Do NOT call figma_delete_frame — deletions are already handled.\n"
        "Create every screen described in the user request from scratch.\n"
        "Existing frames with different names are untouched — do not modify them.\n"
        "If the prompt references existing screens for navigation wiring, call\n"
        "figma_list_frames to discover their names.\n"
        "\n"
        "You MUST complete ALL phases: build screens → create modals → wire everything.\n"
        "Do NOT stop after building screens. Call figma_wire_all before finishing.\n"
    ),
}

# Backward compat: map old mode names to new ones
_MODE_ALIASES = {
    "create": "new",
    "append": "edit",
}



# ── Agentic loop ───────────────────────────────────────────────────────────────

BRAND_KEYWORDS = {
    "corporate", "mobility global", "company", "enterprise",
    "professional", "business", "workplace", "organization", "org",
    "internal tool", "intranet", "employee", "dashboard", "crm", "erp",
}

def _build_brand_context() -> str:
    """Build BRAND_CONTEXT from UIDesignSystem/brand_tokens.json if available."""
    if not _BRAND_TOKENS:
        # Fallback to hardcoded values if tokens file is missing
        return """
BRANDING OVERRIDE — MOBILITY GLOBAL BRAND REQUIRED:
Use the MOBILITY GLOBAL BRAND palette exclusively for all colors in this wireframe:
  Page background:  #EFEFE5   (Quiet Light)
  Sidebar:          #FFFFFF   (White — light sidebar theme)
  Sidebar border:   #E5E7EB   (right-edge separator)
  Header:           #FFFFFF   (White — logo sits on white background)
  Cards:            #FFFFFF
  Border:           #E5E7EB
  Primary text:     #132445
  Secondary text:   #374151
  Muted text:       #9CA3AF
  Primary button:   #0064D2   (Forward Blue)
  Active nav item:  bg=#EBF3FF text=#0064D2 left-accent-bar=#0064D2 (3px)
  Inactive nav:     text=#374151 transparent background
  Hover background: #B8EAF5   (Morning Mist)
  Success:          #059669
  Warning:          #D97706
  Danger/Error:     #DC2626
  Accent (sparse):  #420E71   (Steady Lilac — for tags/premium only)
  Yellow (sparse):  #FFE783   (Vital Spark — for warnings/notifications only)

SIDEBAR — always call figma_create_sidebar_nav with these exact params:
  sidebar_bg="#FFFFFF" border_color="#E5E7EB" text_color="#374151"
  active_text="#0064D2" active_bg="#EBF3FF" active_color="#0064D2"

LOGO (MANDATORY when branding is active):
  STEP 1: Call figma_create_sidebar_nav first — it creates the 'sidebar-<ScreenName>' sub-frame.
  STEP 2: Call figma_create_logo(frame_name='sidebar-<ScreenName>', x=16, y=12, width=160, height=48) on EVERY screen.
  Use 'sidebar-<ScreenName>' as frame_name (e.g. frame_name='sidebar-Dashboard') — NOT the bare screen name.
  Placing the logo inside the sidebar sub-frame ensures it sits on top of the sidebar background fill.
  This embeds the real Mobility Global PNG logo — NEVER draw a circle, ellipse, rectangle, or text as a substitute.
  NEVER call figma_create_logo before figma_create_sidebar_nav — the sidebar sub-frame must already exist.
"""
    u = _BRAND_TOKENS.get("usage", {})
    c = _BRAND_TOKENS.get("colors", {})
    sp = _BRAND_TOKENS.get("spacing", {})
    r  = _BRAND_TOKENS.get("radius", {})
    comp = _BRAND_TOKENS.get("components", {})
    brand = _BRAND_TOKENS.get("brand", "Mobility Global")
    return f"""
BRANDING OVERRIDE — {brand.upper()} BRAND REQUIRED (from UIDesignSystem/brand_tokens.json):
Use this palette exclusively for all colors in this wireframe:
  Page background:  {u.get('page_background','#EFEFE5')}   (Quiet Light)
  Sidebar:          #FFFFFF   (White — light sidebar theme)
  Sidebar border:   {u.get('border','#E5E7EB')}   (right-edge separator)
  Header:           {u.get('header_background','#FFFFFF')}   (White — logo sits on white background)
  Cards:            {u.get('card_background','#FFFFFF')}
  Border:           {u.get('border','#E5E7EB')}
  Primary text:     {u.get('primary_text','#132445')}
  Secondary text:   {u.get('secondary_text','#374151')}
  Muted text:       {u.get('muted_text','#9CA3AF')}
  Primary button:   {u.get('primary_button','#0064D2')}   (Forward Blue)
  Active nav item:  bg=#EBF3FF  text={u.get('active_nav','#0064D2')}  left-accent-bar={u.get('active_nav','#0064D2')} (3px)
  Inactive nav:     text={u.get('secondary_text','#374151')}  transparent background
  Hover background: {u.get('hover_bg','#B8EAF5')}   (Morning Mist)
  Success:          {c.get('semantic',{}).get('success','#059669')}
  Warning:          {c.get('semantic',{}).get('warning','#D97706')}
  Danger/Error:     {c.get('semantic',{}).get('error','#DC2626')}
  Accent (sparse):  {c.get('accent',{}).get('steady_lilac','#420E71')}   (Steady Lilac — for tags/premium only)
  Yellow (sparse):  {c.get('accent',{}).get('vital_spark','#FFE783')}   (Vital Spark — for warnings/notifications only)

SIDEBAR — always call figma_create_sidebar_nav with these exact params:
  sidebar_bg="#FFFFFF"  border_color="{u.get('border','#E5E7EB')}"  text_color="{u.get('secondary_text','#374151')}"
  active_text="{u.get('active_nav','#0064D2')}"  active_bg="#EBF3FF"  active_color="{u.get('active_nav','#0064D2')}"

SPACING (from design tokens):
  xs={sp.get('xs',4)}px  sm={sp.get('sm',8)}px  md={sp.get('md',12)}px  lg={sp.get('lg',16)}px
  xl={sp.get('xl',24)}px  2xl={sp.get('2xl',32)}px  3xl={sp.get('3xl',48)}px

CORNER RADIUS (from design tokens):
  Cards/containers: {r.get('lg',12)}–{r.get('xl',16)}px   Buttons: {r.get('md',8)}–{r.get('lg',12)}px
  Inputs: {r.get('md',8)}px   Badges: {r.get('full',999)}px

COMPONENT DIMENSIONS (from design tokens):
  Header height: {comp.get('header_height',64)}px   Sidebar width: {comp.get('sidebar_width',240)}px
  Button heights: SM={comp.get('button_height_sm',32)}px MD={comp.get('button_height_md',40)}px LG={comp.get('button_height_lg',48)}px
  Input height: {comp.get('input_height',40)}px   Card padding: {comp.get('card_padding',24)}px

TYPOGRAPHY ({_BRAND_TOKENS.get('typography',{}).get('heading_font','Inter')} font):
  H1={_BRAND_TOKENS.get('typography',{}).get('sizes',{}).get('h1',32)}px Bold
  H2={_BRAND_TOKENS.get('typography',{}).get('sizes',{}).get('h2',24)}px SemiBold
  H3={_BRAND_TOKENS.get('typography',{}).get('sizes',{}).get('h3',20)}px SemiBold
  Body={_BRAND_TOKENS.get('typography',{}).get('sizes',{}).get('body',14)}px Regular
  Caption={_BRAND_TOKENS.get('typography',{}).get('sizes',{}).get('caption',11)}px

LOGO (MANDATORY when branding is active):
  STEP 1: Call figma_create_sidebar_nav first — it creates the 'sidebar-<ScreenName>' sub-frame.
  STEP 2: Call figma_create_logo(frame_name='sidebar-<ScreenName>', x=16, y=12, width=160, height=48) on EVERY screen.
  Use 'sidebar-<ScreenName>' as frame_name (e.g. frame_name='sidebar-Dashboard') — NOT the bare screen name.
  Placing the logo inside the sidebar sub-frame ensures it sits on top of the sidebar background fill.
  This embeds the real {brand} PNG logo — NEVER draw a circle, ellipse, rectangle, or text as a substitute.
  NEVER call figma_create_logo before figma_create_sidebar_nav — the sidebar sub-frame must already exist.
"""

BRAND_CONTEXT = _build_brand_context()


def _extract_expected_screens(prompt: str) -> list[str]:
    """
    Heuristically extract expected MAIN SCREEN frame names from a prompt.
    Only matches explicit 'Screen N: Name' headings — not modals, not generic headings.
    """
    import re
    screens = []

    # Only match explicit "## Screen N: Name" pattern — not bare ## headings
    for m in re.finditer(r"^##\s+Screen\s*\d+\s*[:：]\s*(.+)", prompt, re.MULTILINE):
        name = m.group(1).strip().rstrip(" —-")
        screens.append(name)

    if not screens:
        # Fallback: "Build a N-screen app ... : Screen1, Screen2, Screen3"
        m = re.search(r"(\d+)-screen.*?[:：]\s*(.+?)(?:\.|$)", prompt, re.IGNORECASE)
        if m:
            parts = re.split(r"[,\s]+and\s+|,\s*", m.group(2))
            screens = [p.strip() for p in parts if p.strip()]

    return screens


def _track_component(components: dict, screen_name: str, component_type: str):
    """Increment the component count for the current screen."""
    if not screen_name:
        return
    if screen_name not in components:
        components[screen_name] = {}
    components[screen_name][component_type] = components[screen_name].get(component_type, 0) + 1


def _emit_screen_summary(emit, screen_name: str, components: dict):
    """Emit a one-line summary of what was built for a screen."""
    if not components:
        return
    parts = []
    for comp_type in ["Sidebar nav", "Logo", "Table", "Chart", "Map", "Button", "Text", "Shape", "Effect"]:
        count = components.get(comp_type, 0)
        if count > 0:
            if count == 1:
                parts.append(comp_type.lower())
            else:
                parts.append(f"{count} {comp_type.lower()}s")
    if parts:
        emit(f"  ✓ {screen_name} complete: {', '.join(parts)}")


def _delete_all_frames(emit) -> int:
    """Delete all frames on the current page. Returns count deleted."""
    try:
        frames_raw = mcp_call_tool("figma_list_frames", {})
        frames_data = json.loads(frames_raw) if isinstance(frames_raw, str) else frames_raw
        existing = frames_data if isinstance(frames_data, list) else frames_data.get("frames", [])
        count = 0
        for f in existing:
            name = f.get("name", "")
            if name:
                try:
                    mcp_call_tool("figma_delete_frame", {"name": name})
                    count += 1
                except Exception:
                    pass
        if count:
            emit(f"  Cleared {count} existing frame(s)")
        return count
    except Exception:
        return 0


def _delete_matching_frames(names_to_delete: set[str], emit) -> int:
    """Delete frames whose names match the given set. Returns count deleted."""
    try:
        frames_raw = mcp_call_tool("figma_list_frames", {})
        frames_data = json.loads(frames_raw) if isinstance(frames_raw, str) else frames_raw
        existing = frames_data if isinstance(frames_data, list) else frames_data.get("frames", [])
        existing_names = {f.get("name", "") for f in existing}
        to_delete = existing_names & names_to_delete
        count = 0
        for name in to_delete:
            try:
                mcp_call_tool("figma_delete_frame", {"name": name})
                emit(f"    Deleted: {name}")
                count += 1
            except Exception:
                pass
        return count
    except Exception:
        return 0


def run_agent(prompt: str, stream_callback=None, mode: str = "new",
              apply_brand: bool = False, confirmed: bool = False) -> str | dict:
    """
    Run the wireframe agent loop.

    Args:
        prompt:          user's wireframe description
        stream_callback: optional fn(text) called with each progress update
        mode:            'new' | 'edit' | 'replace'
        apply_brand:     True = force Mobility Global brand regardless of prompt
        confirmed:       True = user already confirmed overwrite (skip CONFIRM check)

    Returns:
        On success: dict with keys 'result' (summary text) and 'figma_url' (shareable link or '')
        On error/confirm: plain string (ERROR:... or CONFIRM:...)
    """
    # Resolve mode aliases (backward compat)
    mode = _MODE_ALIASES.get(mode, mode)

    def emit(text: str):
        if stream_callback:
            stream_callback(text)
        else:
            print(text, flush=True)

    # Auto-detect brand from prompt keywords if not explicitly forced
    prompt_lower = prompt.lower()
    use_brand = apply_brand or any(kw in prompt_lower for kw in BRAND_KEYWORDS)

    mode_label = {"new": "new wireframe", "replace": "replace screens", "edit": "edit wireframe"}.get(mode, mode)
    brand_label = " [Mobility Global Brand]" if use_brand else ""
    emit(f"\n{'='*60}")
    emit(f"  Figma Wireframe Agent  [{mode_label}]{brand_label}")
    emit(f"  Prompt: {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
    emit(f"{'='*60}\n")

    # Build full prompt: mode context + user request + brand override (last = highest priority)
    mode_ctx   = MODE_CONTEXT.get(mode, MODE_CONTEXT["new"])
    brand_ctx  = (
        BRAND_CONTEXT +
        "\n⚠️  BRAND OVERRIDE IS ACTIVE — IGNORE any colors, themes, or hex codes "
        "mentioned in the user request above. Use ONLY the palette defined in the "
        "BRANDING OVERRIDE block. The user request is a layout/content spec only.\n"
    ) if use_brand else ""
    full_prompt = f"{mode_ctx}\nUser request: {prompt}\n{brand_ctx}"

    # Check MCP server
    emit("Connecting to Figma MCP server…")
    if not mcp_initialize():
        return "ERROR:NO_MCP_SERVER"

    # Load tools
    mcp_tools = mcp_list_tools()
    if not mcp_tools:
        return "ERROR:NO_TOOLS"
    emit(f"Loaded {len(mcp_tools)} Figma tools\n")

    # ── Verify Figma Desktop state ────────────────────────────────────────────
    emit("Checking Figma Desktop state…")
    figma_state = mcp_call_tool("figma_get_status", {})
    try:
        state = json.loads(figma_state) if isinstance(figma_state, str) else figma_state
    except Exception:
        state = {}

    relay_ok = state.get("relay_connected", False) or state.get("ready", False)
    any_connected = state.get("anyClientConnected", False)
    connected = relay_ok or any_connected

    if not connected:
        has_page = bool(state.get("page"))
        if not has_page:
            return "ERROR:NO_FIGMA_FILE"
        return "ERROR:BRIDGE_NOT_CONNECTED"

    # ── Mode-specific canvas preparation ──────────────────────────────────────
    page_name   = state.get("page", "")
    frame_names = state.get("frame_names", [])
    frame_count = state.get("frame_count", 0)

    if mode == "new":
        if frame_count > 0 and not confirmed:
            # Return signal so the UI can prompt for confirmation
            frames_str = ", ".join(frame_names[:5])
            if len(frame_names) > 5:
                frames_str += f" + {len(frame_names) - 5} more"
            return (
                f"CONFIRM:EXISTING_FRAMES:{frame_count}:{frames_str}"
            )
        if frame_count > 0 and confirmed:
            # User confirmed — clear the canvas before building
            emit(f"Figma connected — page: '{page_name}', clearing {frame_count} existing frame(s)…")
            _delete_all_frames(emit)
        else:
            emit(f"Figma connected — page: '{page_name}', blank canvas")

    elif mode == "replace":
        # Pre-delete frames that match what we're about to build
        expected_screens = _extract_expected_screens(prompt)
        if expected_screens:
            emit(f"Figma connected — page: '{page_name}', {frame_count} existing frame(s)")
            emit(f"  Replacing screens: {', '.join(expected_screens)}")
            deleted = _delete_matching_frames(set(expected_screens), emit)
            if deleted:
                emit(f"  Pre-deleted {deleted} matching frame(s)")
        else:
            emit(f"Figma connected — page: '{page_name}', {frame_count} existing frame(s)")

    elif mode == "edit":
        emit(f"Figma connected — page: '{page_name}'"
             + (f", {frame_count} existing frame(s)" if frame_count else ", blank canvas"))

    emit("")

    # ── Track frame creation for progress display ──────────────────────────────
    frames_built_this_run: set = set()
    wiring_done = False  # tracks if figma_wire_all was called
    completeness_nudges = 0  # prevent infinite completeness-gate loops
    expected_screen_count = len(_extract_expected_screens(prompt)) or "?"
    current_screen_name = ""  # tracks which screen is being built
    current_screen_components: dict = {}  # {screen_name: {type: count}}
    current_phase = "screens"  # screens | overlays | wiring | verify

    oai_tools = tools_to_openai(mcp_tools)
    client = get_openai_client()

    messages = [{"role": "user", "content": full_prompt}]
    turn = 0

    while turn < MAX_TURNS:
        turn += 1
        log.info(f"Turn {turn} — calling Claude…")

        response = client.chat.completions.create(
            model=MODEL_ID,
            max_tokens=MAX_TOKENS,
            tools=oai_tools,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        )

        # Track token usage
        if hasattr(response, "usage") and response.usage:
            record_token_usage(
                _get_figma_run_id(),
                response.usage.prompt_tokens or 0,
                response.usage.completion_tokens or 0,
            )

        choice        = response.choices[0]
        msg           = choice.message
        finish_reason = choice.finish_reason

        # Add assistant response to history
        if msg.tool_calls:
            messages.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            })
        else:
            messages.append({"role": "assistant", "content": msg.content or ""})

        # Print any text Claude outputs
        if msg.content and msg.content.strip():
            txt = msg.content.strip()
            emit(f"\n[Claude] {txt[:300]}{'…' if len(txt) > 300 else ''}")

        # ── Claude hit output token limit — nudge to continue ──────────────
        if finish_reason == "length":
            emit(f"\n⚠️  Output limit reached — continuing build…")
            messages.append({
                "role": "user",
                "content": (
                    "You were cut off mid-build due to output length. "
                    "Continue EXACTLY where you left off — do NOT start over or re-create "
                    "frames that already exist. Pick up from the next incomplete element."
                ),
            })
            continue

        # ── Claude finished — completeness gate before QA ─────────────────────
        if finish_reason == "stop":
            nudge_reason = None

            if completeness_nudges < 2 and mode in ("new", "replace"):
                # Check 1: Did wiring happen? If prompt describes modals/wiring and
                # figma_wire_all was never called, builder stopped before Phase 3
                if not wiring_done and len(frames_built_this_run) >= 2:
                    nudge_reason = (
                        "STOP — you skipped Phase 2 (overlays) and Phase 3 (wiring)!\n\n"
                        "You built the screen frames but did NOT:\n"
                        "  - Create the overlay/modal frames described in the prompt\n"
                        "  - Wire navigation, buttons, and overlays with figma_wire_all\n\n"
                        "A prototype without wiring is BROKEN — buttons do nothing.\n"
                        "Continue NOW:\n"
                        "  1. Create ALL modal/overlay frames from the prompt (export-modal, etc.)\n"
                        "  2. Call figma_list_frame_nodes with filter='tab-' on each screen\n"
                        "  3. Call figma_wire_all with ALL links (nav, buttons, overlays)\n"
                        "  4. Set prototype start screen\n"
                        "Do NOT stop until wiring is complete."
                    )

                # Check 2: Any screen truly empty?
                if not nudge_reason:
                    expected_screens = _extract_expected_screens(prompt)
                    if not expected_screens and frames_built_this_run:
                        expected_screens = [f for f in frames_built_this_run if not f.endswith("-modal") and not f.endswith("-drawer")]
                    incomplete_screens = []
                    if expected_screens:
                        try:
                            for screen_name in expected_screens:
                                try:
                                    nodes_raw = mcp_call_tool("figma_list_frame_nodes", {"frame_name": screen_name})
                                    nodes_data = json.loads(nodes_raw) if isinstance(nodes_raw, str) else nodes_raw
                                    node_count = nodes_data.get("total", 0) if isinstance(nodes_data, dict) else 0
                                    if node_count < 10:
                                        incomplete_screens.append((screen_name, node_count))
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    if incomplete_screens:
                        screens_desc = ", ".join(f"{name} ({count} nodes)" for name, count in incomplete_screens)
                        nudge_reason = (
                            f"STOP — the following screens are EMPTY (no content built):\n"
                            f"  {screens_desc}\n\n"
                            f"Build ALL content for these screens now."
                        )

            if nudge_reason:
                completeness_nudges += 1
                emit(f"\n⚠️  Completeness check failed (attempt {completeness_nudges}/2)")
                emit(f"  Nudging builder to continue…\n")
                messages.append({"role": "user", "content": nudge_reason})
                continue

            # Emit final screen summary if we ended mid-screen
            if current_screen_name and current_screen_components.get(current_screen_name):
                _emit_screen_summary(emit, current_screen_name, current_screen_components[current_screen_name])

            screen_count = len([f for f in frames_built_this_run if not f.endswith("-modal") and not f.endswith("-drawer")])
            modal_count = len([f for f in frames_built_this_run if f.endswith("-modal") or f.endswith("-drawer")])
            summary_parts = [f"{screen_count} screen(s)"]
            if modal_count:
                summary_parts.append(f"{modal_count} modal(s)")
            if wiring_done:
                summary_parts.append("wiring done")
            emit(f"\n{'═'*40}")
            emit(f"✅ Build complete: {', '.join(summary_parts)}")
            emit(f"{'═'*40}")
            emit(f"  Running QA pass…")

            qa_result = run_validation_pass(oai_tools, client, emit, messages, user_prompt=prompt)
            main_result = msg.content or "Done."
            figma_url = _fetch_figma_url(emit)
            return {"result": f"{main_result}\n\n--- QA ---\n{qa_result}", "figma_url": figma_url}

        # ── Handle tool calls ─────────────────────────────────────────────────
        if finish_reason == "tool_calls":
            for tc in msg.tool_calls:
                tool_name   = tc.function.name
                tool_input  = json.loads(tc.function.arguments)
                tool_use_id = tc.id

                # ── Progress display — grouped by phase and screen ────────────
                if tool_name == "figma_create_frame":
                    frame_name = tool_input.get("name", "?")
                    is_modal = frame_name.endswith("-modal") or frame_name.endswith("-drawer")

                    if is_modal:
                        # Phase 2: overlays
                        if current_phase == "screens":
                            # Emit summary of last screen before switching phase
                            if current_screen_name and current_screen_components.get(current_screen_name):
                                _emit_screen_summary(emit, current_screen_name, current_screen_components[current_screen_name])
                            current_phase = "overlays"
                            emit(f"\n{'─'*40}")
                            emit(f"📦 Phase 2: Building overlays & modals")
                            emit(f"{'─'*40}")
                        emit(f"  📋 Modal: {frame_name}")
                    else:
                        # Phase 1: screens
                        # Emit summary for previous screen
                        if current_screen_name and current_screen_components.get(current_screen_name):
                            _emit_screen_summary(emit, current_screen_name, current_screen_components[current_screen_name])

                        frames_built_this_run.add(frame_name)
                        current_screen_name = frame_name
                        current_screen_components[frame_name] = {}
                        screen_num = len([f for f in frames_built_this_run if not f.endswith("-modal") and not f.endswith("-drawer")])
                        emit(f"\n{'─'*40}")
                        emit(f"🖼️  Screen {screen_num}/{expected_screen_count}: {frame_name}")
                        emit(f"{'─'*40}")

                elif tool_name == "figma_create_sidebar_nav":
                    _track_component(current_screen_components, current_screen_name, "Sidebar nav")
                    emit(f"  📋 Sidebar nav")
                elif tool_name == "figma_create_table":
                    tname = tool_input.get("name", tool_input.get("frame_name", "?"))
                    _track_component(current_screen_components, current_screen_name, "Table")
                    emit(f"  📊 Table: {tname}")
                elif tool_name == "figma_create_chart":
                    chart_desc = tool_input.get("title", tool_input.get("chart_type", "chart"))
                    _track_component(current_screen_components, current_screen_name, "Chart")
                    emit(f"  📈 Chart: {chart_desc}")
                elif tool_name == "figma_create_map":
                    _track_component(current_screen_components, current_screen_name, "Map")
                    emit(f"  🗺️  Map: {tool_input.get('name', '?')}")
                elif tool_name == "figma_create_button":
                    _track_component(current_screen_components, current_screen_name, "Button")
                    label = tool_input.get("label", "")
                    name = tool_input.get("name", "")
                    if label and ("btn" in name or "search" in name.lower() or "export" in label.lower() or "add" in label.lower()):
                        emit(f"  🔘 Interactive: {label}")
                elif tool_name == "figma_create_text":
                    _track_component(current_screen_components, current_screen_name, "Text")
                elif tool_name == "figma_create_rectangle":
                    _track_component(current_screen_components, current_screen_name, "Shape")
                elif tool_name == "figma_create_logo":
                    _track_component(current_screen_components, current_screen_name, "Logo")
                    emit(f"  🏷️  Logo")
                elif tool_name == "figma_wire_all":
                    # Phase 3: wiring
                    if current_phase != "wiring":
                        if current_screen_name and current_screen_components.get(current_screen_name):
                            _emit_screen_summary(emit, current_screen_name, current_screen_components[current_screen_name])
                        current_phase = "wiring"
                        emit(f"\n{'─'*40}")
                        emit(f"🔗 Phase 3: Wiring prototype interactions")
                        emit(f"{'─'*40}")
                    wiring_done = True
                    links = tool_input.get("links", [])
                    emit(f"  🔗 Wiring {len(links)} links…")
                elif tool_name == "figma_set_prototype_start":
                    if current_phase != "verify":
                        current_phase = "verify"
                        emit(f"\n{'─'*40}")
                        emit(f"✅ Phase 4: Final setup")
                        emit(f"{'─'*40}")
                    emit(f"  ▶️  Prototype start: {tool_input.get('frame_name', '?')}")
                elif tool_name == "figma_set_scrollable":
                    emit(f"  📜 Scrollable: {tool_input.get('frame_name', '?')}")
                elif tool_name == "figma_inspect_reactions":
                    emit(f"  🔍 Verifying: {tool_input.get('frame_name', '?')}")
                elif tool_name == "figma_audit_frame":
                    emit(f"  🔍 Auditing: {tool_input.get('frame_name', '?')}")
                elif tool_name == "figma_set_active_tab_style":
                    pass  # minor detail, no need to log
                elif tool_name == "figma_execute_js":
                    _track_component(current_screen_components, current_screen_name, "Effect")
                elif tool_name == "figma_list_frame_nodes":
                    pass  # internal lookup, no need to log
                elif tool_name == "figma_list_frames":
                    pass
                else:
                    emit(f"  → {tool_name}")

                # Execute via MCP
                try:
                    result_text = mcp_call_tool(tool_name, tool_input)
                    try:
                        parsed = json.loads(result_text)
                        if isinstance(parsed, dict):
                            if "error" in parsed:
                                emit(f"    ✗ {parsed['error']}")
                            elif tool_name == "figma_wire_all":
                                wired   = parsed.get("wired", 0)
                                skipped = parsed.get("skipped", 0)
                                failed  = parsed.get("failed", 0)
                                errors  = parsed.get("errors", [])
                                # Count link types from the input
                                nav_links = sum(1 for l in tool_input.get("links", []) if l.get("type") == "NAVIGATE")
                                overlay_links = sum(1 for l in tool_input.get("links", []) if l.get("type") == "OVERLAY")
                                emit(f"    ✓ Wired {wired} links ({nav_links} nav, {overlay_links} overlay), skipped {skipped}")
                                if failed or errors:
                                    for err in errors[:3]:
                                        emit(f"    ✗ Failed: {err.get('from','?')} → {err.get('to','?')}")
                            elif tool_name == "figma_inspect_reactions":
                                wired_count   = parsed.get("wired_count", 0)
                                unwired_count = parsed.get("unwired_interactive", 0)
                                frame         = parsed.get("frame", "?")
                                # Filter out self-tabs (tab-X-on-X) — they can't be wired
                                unwired_nodes = parsed.get("unwired", [])
                                real_unwired = [
                                    u for u in unwired_nodes
                                    if not (u.get("name", "").startswith("tab-") and
                                            u.get("name", "").endswith(f"-on-{frame}"))
                                ]
                                if real_unwired:
                                    emit(f"    ⚠ {frame}: {len(real_unwired)} unwired node(s)")
                                    for u in real_unwired:
                                        emit(f"      → {u.get('name','?')}")
                                else:
                                    emit(f"    ✓ {frame}: all interactive nodes wired")
                            elif parsed.get("created") or parsed.get("linked") or parsed.get("updated") or parsed.get("set"):
                                pass
                    except Exception:
                        pass
                except Exception as e:
                    result_text = json.dumps({"error": str(e)})
                    emit(f"    ✗ Exception: {e}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_use_id,
                    "content": result_text,
                })
            continue

        # Unexpected finish reason — treat as length cutoff
        log.warning(f"Unexpected finish_reason: {finish_reason} — treating as continuation")
        emit(f"\n⚠️  Unexpected stop ({finish_reason}) — nudging to continue…")
        messages.append({
            "role": "user",
            "content": (
                "You were cut off. Continue building where you left off. "
                "Do NOT re-create existing frames. Check what's missing and build it."
            ),
        })
        continue

    figma_url = _fetch_figma_url(emit)
    return {"result": f"Agent completed after {turn} turns.", "figma_url": figma_url}


# ── FastAPI server mode ────────────────────────────────────────────────────────

def create_app():
    """Create a FastAPI app that exposes the agent as an HTTP API."""
    try:
        from fastapi import FastAPI
        from fastapi.responses import StreamingResponse, JSONResponse
        from fastapi.middleware.cors import CORSMiddleware
        from pydantic import BaseModel
        import asyncio
    except ImportError:
        raise ImportError("Run: pip install fastapi uvicorn")

    app = FastAPI(title="Figma Wireframe Agent API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
    )

    class PromptRequest(BaseModel):
        prompt: str
        mode: str = "new"   # 'new' | 'edit' | 'replace'

    @app.get("/")
    def health():
        return {
            "service": "Figma Wireframe Agent",
            "mcp_server": MCP_SERVER,
            "modes": {
                "new": "build from scratch (clears canvas)",
                "edit": "edit existing or add new screens",
                "replace": "rebuild specific screens",
            },
        }

    @app.post("/generate")
    def generate(req: PromptRequest):
        """Run agent and return full result as JSON."""
        result = run_agent(req.prompt, mode=req.mode)
        return JSONResponse({"result": result, "mode": req.mode})

    @app.post("/generate/stream")
    def generate_stream(req: PromptRequest):
        """Run agent and stream progress as SSE."""
        import queue, threading

        def event_stream():
            q = queue.Queue()
            result_holder = []

            def run():
                r = run_agent(req.prompt, stream_callback=q.put, mode=req.mode)
                result_holder.append(r)
                q.put(None)

            threading.Thread(target=run, daemon=True).start()

            while True:
                item = q.get()
                if item is None:
                    break
                yield f"data: {json.dumps({'text': item})}\n\n"

            yield f"data: {json.dumps({'done': True, 'mode': req.mode, 'result': result_holder[0] if result_holder else ''})}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    return app


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Figma Wireframe Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  new     (default) — build from scratch on a clean canvas (warns if frames exist)
  edit              — edit existing screens or add new ones alongside them
  replace           — pre-delete matching screens and rebuild them fresh

Examples:
  python prompt_to_figma_agent.py "Sports app with Dashboard, Players, Match Detail"
  python prompt_to_figma_agent.py "Add a filter popup to the Players screen" --mode edit
  python prompt_to_figma_agent.py "Redesign the Dashboard with stats cards" --mode replace
  python prompt_to_figma_agent.py "Add a new Settings screen" --mode edit
        """,
    )
    parser.add_argument("prompt", nargs="?", help="Wireframe prompt")
    parser.add_argument("--prompt", "-p", dest="prompt_flag", help="Wireframe prompt (alternative)")
    parser.add_argument("--mode", "-m", default="new",
                        choices=["new", "edit", "replace", "create", "append"],
                        help="new=fresh build (default), edit=modify/add, replace=rebuild specific screens")
    parser.add_argument("--brand", "-b", action="store_true",
                        help="Apply Mobility Global brand colors (auto-detected from prompt keywords too)")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive REPL mode")
    parser.add_argument("--server", "-s", action="store_true", help="Run as FastAPI server")
    parser.add_argument("--port", type=int, default=7772, help="Server port (default 7772)")
    parser.add_argument("--mcp", default=MCP_SERVER, help=f"MCP server URL (default {MCP_SERVER})")
    args = parser.parse_args()

    MCP_SERVER = args.mcp

    if args.server:
        import uvicorn
        app = create_app()
        print(f"\n  Wireframe Agent API on http://0.0.0.0:{args.port}")
        print(f"  POST /generate        — JSON response")
        print(f"  POST /generate/stream — SSE streaming")
        print(f"  mode field: 'new' | 'edit' | 'replace'\n")
        uvicorn.run(app, host="0.0.0.0", port=args.port)

    elif args.interactive:
        print("Figma Wireframe Agent — Interactive mode (Ctrl+C to exit)")
        print("Commands: 'mode new|edit|replace'  or  'brand on|off'\n")
        current_mode  = "new"
        current_brand = args.brand
        while True:
            try:
                brand_indicator = " [brand]" if current_brand else ""
                prompt = input(f"[{current_mode}{brand_indicator}] Describe your wireframe: ").strip()
                if not prompt:
                    continue
                if prompt.startswith("mode "):
                    m = prompt.split(" ", 1)[1].strip()
                    # Accept old names too
                    m = _MODE_ALIASES.get(m, m)
                    if m in ("new", "edit", "replace"):
                        current_mode = m
                        print(f"Mode set to: {current_mode}")
                    else:
                        print("Unknown mode. Use: new, edit, replace")
                    continue
                if prompt.startswith("brand "):
                    v = prompt.split(" ", 1)[1].strip()
                    current_brand = v in ("on", "true", "yes", "1")
                    print(f"Brand: {'ON (Mobility Global)' if current_brand else 'OFF (auto-detect)'}")
                    continue
                run_agent(prompt, mode=current_mode, apply_brand=current_brand)
            except KeyboardInterrupt:
                print("\nBye!")
                break

    else:
        prompt = args.prompt or args.prompt_flag
        if not prompt:
            parser.print_help()
            sys.exit(1)
        result = run_agent(prompt, mode=args.mode, apply_brand=args.brand)
        print(f"\n{'='*60}")
        print(f"  Done: {result[:200] if isinstance(result, str) else str(result)[:200]}")
        print(f"{'='*60}")
