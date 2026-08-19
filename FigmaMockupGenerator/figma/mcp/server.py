#!/usr/bin/env python3
"""
Figma MCP Server — HTTP Streamable
====================================
An MCP (Model Context Protocol) server that exposes Figma design operations
as tools callable by any LLM (Claude, GPT, etc.).

Architecture:
    LLM ──→ MCP Server (this file, port 7771)
                 ↓
            Relay Agent (relay.py, runs on user's laptop)
                 ↓ WebSocket localhost:9223
            Figma Desktop Bridge Plugin
                 ↓
            Figma Desktop

Usage:
    python server.py            # start the MCP server
    python server.py --port 7771

MCP Endpoint:
    POST http://localhost:7771/mcp   (JSON-RPC 2.0)
    GET  http://localhost:7771/mcp   (SSE stream — for streaming responses)
"""

import asyncio
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import JSONResponse, StreamingResponse

load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))  # TurboUIGen/
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))          # FigmaMockupGenerator/
from config import MCP_PORT as _DEFAULT_MCP_PORT
from config_ds import DS_TOKENS_FILE as _DS_TOKENS_FILE

# ── Design system tokens — loaded once at startup ─────────────────────────────
# All colour defaults below come from brand_tokens.json (via DESIGN_SYSTEM_PATH
# in .env).  Switching design systems requires only an .env change + server restart.
def _load_ds_tokens() -> dict:
    try:
        if _DS_TOKENS_FILE.exists():
            return json.loads(_DS_TOKENS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}

_DS   = _load_ds_tokens()
_U    = _DS.get("usage",      {})
_C    = _DS.get("colors",     {})
_PRI  = _C.get("primary",     {})
_SEM  = _C.get("semantic",    {})
_TYP  = _DS.get("typography", {})
_SP   = _DS.get("spacing",    {})
_RAD  = _DS.get("radius",     {})
_COMP = _DS.get("components", {})

# ── Colours — all from design system tokens ───────────────────────────────────
_T_PAGE_BG        = _U.get("page_background",    "#EFEFE5")
_T_SIDEBAR_BG     = _U.get("sidebar_background", "#FFFFFF")
_T_SIDEBAR_BORDER = _U.get("sidebar_border",     "#E5E7EB")
_T_HEADER_BG      = _U.get("header_background",  "#FFFFFF")
_T_CARD_BG        = _U.get("card_background",    "#FFFFFF")
_T_BORDER         = _U.get("border",             "#E5E7EB")
_T_TEXT           = _U.get("primary_text",       "#132445")
_T_TEXT2          = _U.get("secondary_text",     "#374151")
_T_MUTED          = _U.get("muted_text",         "#9CA3AF")
_T_ACCENT         = _U.get("primary_button",     "#0064D2")
_T_ACTIVE_NAV     = _U.get("active_nav",         "#0064D2")
_T_ACTIVE_BG      = _U.get("active_nav_bg",      "#EBF3FF")
_T_HOVER          = _U.get("hover_bg",           "#B8EAF5")
_T_BRAND_DARK     = _U.get("brand_dark",  _PRI.get("vital_blue",   "#132445"))
_T_BRAND_ACCENT   = _U.get("brand_accent",_PRI.get("forward_blue", "#0064D2"))
_T_BRAND_MIST     = _U.get("brand_mist",  _PRI.get("morning_mist", "#B8EAF5"))
_T_BRAND_BG       = _U.get("brand_bg",    _U.get("page_background","#EFEFE5"))
_T_SUCCESS        = _SEM.get("success",   "#059669")
_T_WARNING        = _SEM.get("warning",   "#D97706")
_T_DANGER         = _SEM.get("error",     "#DC2626")

# ── Typography — all from design system tokens ────────────────────────────────
_T_FONT_HEADING   = _TYP.get("heading_font", "Inter")
_T_FONT_BODY      = _TYP.get("body_font",    "Inter")
_T_W_REGULAR      = _TYP.get("weights", {}).get("regular",  "Regular")
_T_W_MEDIUM       = _TYP.get("weights", {}).get("medium",   "Medium")
_T_W_BOLD         = _TYP.get("weights", {}).get("bold",     "Bold")
_T_FS_BODY        = _TYP.get("sizes",   {}).get("body",     14)
_T_FS_LABEL       = _TYP.get("sizes",   {}).get("label",    12)
_T_FS_NAV         = _TYP.get("sizes",   {}).get("nav",      14)
_T_FS_H4          = _TYP.get("sizes",   {}).get("h4",       16)

# ── Component sizes — all from design system tokens ───────────────────────────
_T_SIDEBAR_W      = _COMP.get("sidebar_width",       240)
_T_SIDEBAR_H      = _COMP.get("sidebar_height",      900)
_T_NAV_ITEM_H     = _COMP.get("nav_item_height",     44)
_T_NAV_START_Y    = _COMP.get("nav_start_y",         100)
_T_NAV_PAD_LEFT   = _COMP.get("nav_padding_left",    20)
_T_NAV_ACCENT_W   = _COMP.get("nav_accent_bar_width",3)
_T_HEADER_H       = _COMP.get("header_height",       64)
_T_BTN_RADIUS     = _RAD.get("md",                   8)
_T_CARD_RADIUS    = _COMP.get("card_radius",         16)
_T_INPUT_RADIUS   = _COMP.get("input_radius",        8)
_T_LOGO_W         = _COMP.get("logo_width",          160)
_T_LOGO_H         = _COMP.get("logo_height",         48)
_T_LOGO_X         = _COMP.get("logo_x",              16)
_T_LOGO_Y         = _COMP.get("logo_y",              12)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("figma-mcp")

app = FastAPI(title="Figma MCP Server")

# ── Relay connection ──────────────────────────────────────────────────────────
# The relay.py process connects here via WebSocket and forwards commands to Figma
_relay_ws = None          # active relay WebSocket connection
_pending: dict[str, asyncio.Future] = {}   # request_id → Future for results


# ── Tool registry ─────────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "figma_create_sidebar_nav",
        "description": (
            "Create a perfectly aligned sidebar navigation in one call. "
            "All nav items get IDENTICAL width (full sidebar width), same x=0, "
            "sequential y positions with no gaps. This guarantees pixel-perfect alignment. "
            "Use this instead of calling figma_create_button multiple times for nav items."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "frame_name":    {"type": "string", "description": "Parent screen frame name"},
                "sidebar_width": {"type": "number", "description": "Sidebar width (default 240)"},
                "sidebar_height":{"type": "number", "description": "Sidebar height (default 900)"},
                "sidebar_bg":    {"type": "string", "description": f"Sidebar background hex (default {_T_SIDEBAR_BG})"},
                "items": {
                    "type": "array",
                    "description": "Nav items. Each: {label, name, active, target_frame}",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label":        {"type": "string"},
                            "name":         {"type": "string", "description": "Node name e.g. tab-Dashboard-on-Screen"},
                            "active":       {"type": "boolean"},
                            "target_frame": {"type": "string"},
                        },
                    },
                },
                "item_height":   {"type": "number", "description": "Height of each nav item (default 44)"},
                "start_y":       {"type": "number", "description": "Y position of first nav item (default 80)"},
                "active_color":  {"type": "string", "description": f"Left accent bar hex (default {_T_ACTIVE_NAV})"},
                "active_bg":     {"type": "string", "description": f"Active item background tint hex (default {_T_ACTIVE_BG})"},
                "active_text":   {"type": "string", "description": f"Active item text hex (default {_T_ACTIVE_NAV})"},
                "text_color":    {"type": "string", "description": f"Inactive item text hex (default {_T_TEXT2})"},
                "border_color":  {"type": "string", "description": f"Sidebar right-border hex (default {_T_BORDER})"},
            },
            "required": ["frame_name", "items"],
        },
    },
    {
        "name": "figma_apply_brand",
        "description": (
            "Apply Mobility Global brand colors to all frames on the current page. "
            "Walks every node and remaps generic colors to brand equivalents: "
            "dark backgrounds → Vital Blue #132445, bright accents → Forward Blue #0064D2, "
            "light backgrounds → Quiet Light #EFEFE5, cards/inputs → White #FFFFFF. "
            "Also sets headers to white and sidebars to Vital Blue. "
            "Call this AFTER building all frames to apply brand in one pass. "
            "Can also be called on existing wireframes to rebrand them."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "frames": {
                    "type": "array",
                    "description": "List of frame names to brand. Empty list = all frames on page.",
                    "items": {"type": "string"},
                },
                "header_bg":  {"type": "string", "description": f"Header background hex (default {_T_HEADER_BG})"},
                "sidebar_bg": {"type": "string", "description": f"Sidebar background hex (default {_T_SIDEBAR_BG})"},
                "card_bg":    {"type": "string", "description": f"Card/panel background hex (default {_T_CARD_BG})"},
                "page_bg":    {"type": "string", "description": f"Page background hex (default {_T_PAGE_BG})"},
                "accent":     {"type": "string", "description": f"Primary accent hex (default {_T_ACCENT})"},
            },
            "required": [],
        },
    },
    {
        "name": "figma_create_logo",
        "description": (
            "Place the Mobility Global logo image inside a frame. "
            "Creates a rectangle with the actual company logo as an image fill. "
            "Use this instead of a blue circle or text when the prompt mentions "
            "Mobility Global, the company logo, or corporate branding. "
            "Always place in the top-left of the sidebar or header."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "frame_name": {"type": "string", "description": "Parent frame name"},
                "name":       {"type": "string", "description": "Node name (default: logo-mobility-global)"},
                "x":          {"type": "number", "description": "X position"},
                "y":          {"type": "number", "description": "Y position"},
                "width":      {"type": "number", "description": "Width in px (default 160)"},
                "height":     {"type": "number", "description": "Height in px (default 48)"},
            },
            "required": ["frame_name", "x", "y"],
        },
    },
    {
        "name": "figma_wire_all",
        "description": (
            "Wire ALL prototype interactions in a single call. Far more reliable than calling "
            "figma_set_prototype_link and figma_add_overlay_link one at a time because it does "
            "everything in one JS execution — no round-trip failures, no partial wiring. "
            "Pass a list of links. Each link is: "
            "{source_frame, source_node, target_frame, type} where type is 'NAVIGATE' or 'OVERLAY'. "
            "ALWAYS use this instead of individual wiring calls. "
            "Call AFTER all frames and nodes have been created."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "links": {
                    "type": "array",
                    "description": "List of prototype links to wire",
                    "items": {
                        "type": "object",
                        "properties": {
                            "source_frame":  {"type": "string", "description": "Frame containing the clickable node"},
                            "source_node":   {"type": "string", "description": "Name of the clickable node"},
                            "target_frame":  {"type": "string", "description": "Frame to navigate to or show as overlay"},
                            "type":          {"type": "string", "description": "'NAVIGATE' (go to screen) or 'OVERLAY' (show on top). Default: NAVIGATE"},
                        },
                        "required": ["source_frame", "source_node", "target_frame"],
                    },
                },
                "start_frame": {"type": "string", "description": "Name of the prototype start/home screen (optional)"},
            },
            "required": ["links"],
        },
    },
    {
        "name": "figma_inspect_reactions",
        "description": (
            "Inspect all prototype reactions on every node in a frame. "
            "Use this after wiring to verify reactions were actually set, and to debug "
            "why clicks are not working. Returns every node with reactions showing "
            "navigation type, destination, and trigger."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "frame_name": {"type": "string", "description": "Name of the frame to inspect"},
            },
            "required": ["frame_name"],
        },
    },
    {
        "name": "figma_get_status",
        "description": "Check if Figma Desktop is connected and ready. Call this first before any other tool.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "figma_get_file_url",
        "description": (
            "Return the shareable Figma URL for the currently open file. "
            "Returns an object with 'url' (the full https://www.figma.com/design/... link), "
            "'file_key', and 'file_name'. Call this after building the wireframe to get the link to share."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "figma_list_frames",
        "description": "List all top-level frames on the current Figma page with their names, sizes and positions.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "figma_list_frame_nodes",
        "description": (
            "List ALL named nodes inside a frame — returns the full flat list of node names, types, and sizes. "
            "Call this BEFORE figma_wire_all to confirm the exact node names you need to pass as source_node. "
            "Node names from figma_create_sidebar_nav follow the pattern 'tab-{Label}-on-{FrameName}'. "
            "Use this to catch typos and name mismatches that cause wiring to silently fail."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "frame_name": {"type": "string", "description": "Name of the top-level frame to inspect"},
                "filter":     {"type": "string", "description": "Optional: only return nodes whose name contains this string (case-insensitive)"},
            },
            "required": ["frame_name"],
        },
    },
    {
        "name": "figma_create_frame",
        "description": "Create a new top-level frame (screen) on the current page.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name":   {"type": "string",  "description": "Frame name, e.g. 'Dashboard'"},
                "width":  {"type": "number",  "description": "Width in pixels (default 390 for mobile, 1440 for desktop)"},
                "height": {"type": "number",  "description": "Height in pixels (default 844 for mobile, 900 for desktop)"},
                "x":      {"type": "number",  "description": "X position on canvas (default 0)"},
                "y":      {"type": "number",  "description": "Y position on canvas (default 0)"},
                "fill":   {"type": "string",  "description": "Background hex color e.g. '#1a1a2e' (default white)"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "figma_create_rectangle",
        "description": "Create a rectangle inside a frame. Use for cards, headers, nav bars, image placeholders.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "frame_name": {"type": "string", "description": "Name of the parent frame"},
                "name":       {"type": "string", "description": "Name for this rectangle"},
                "x":          {"type": "number", "description": "X position inside frame"},
                "y":          {"type": "number", "description": "Y position inside frame"},
                "width":      {"type": "number", "description": "Width in pixels"},
                "height":     {"type": "number", "description": "Height in pixels"},
                "fill":       {"type": "string", "description": "Fill hex color e.g. '#3b82f6'"},
                "corner_radius": {"type": "number", "description": "Corner radius (default 0)"},
            },
            "required": ["frame_name", "name", "x", "y", "width", "height"],
        },
    },
    {
        "name": "figma_create_text",
        "description": "Create a text node inside a frame.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "frame_name": {"type": "string", "description": "Name of the parent frame"},
                "name":       {"type": "string", "description": "Name for this text node"},
                "content":    {"type": "string", "description": "The text to display"},
                "x":          {"type": "number", "description": "X position inside frame"},
                "y":          {"type": "number", "description": "Y position inside frame"},
                "font_size":  {"type": "number", "description": "Font size in pixels (default 14)"},
                "color":      {"type": "string", "description": "Text hex color (default '#ffffff')"},
                "bold":       {"type": "boolean","description": "Bold text (default false)"},
            },
            "required": ["frame_name", "name", "content", "x", "y"],
        },
    },
    {
        "name": "figma_set_prototype_link",
        "description": "Add a prototype ON_CLICK navigation link from a node to a target frame. Used to make buttons/tabs interactive.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_frame": {"type": "string", "description": "Name of the frame containing the clickable node"},
                "source_node":  {"type": "string", "description": "Name of the clickable node (button/tab)"},
                "target_frame": {"type": "string", "description": "Name of the frame to navigate to on click"},
            },
            "required": ["source_frame", "source_node", "target_frame"],
        },
    },
    {
        "name": "figma_execute_js",
        "description": "Execute arbitrary Figma Plugin API JavaScript. Use for complex operations not covered by other tools. The code has access to the figma global object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "JavaScript code to execute in Figma. Wrap in async IIFE if using await."},
            },
            "required": ["code"],
        },
    },
    {
        "name": "figma_audit_frame",
        "description": (
            "Inspect a frame deeply and return a structured report of what it contains: "
            "all child node names, types, whether a bottom nav exists, which tab buttons are present, "
            "which nodes have prototype reactions wired, and which do not. "
            "Use this after building each screen to verify nothing is missing before moving on."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "frame_name": {"type": "string", "description": "Name of the frame to audit"},
            },
            "required": ["frame_name"],
        },
    },
    {
        "name": "figma_delete_frame",
        "description": (
            "Delete a top-level frame from the canvas by name. "
            "Use in 'replace' mode before recreating a screen fresh. "
            "Safe — only deletes exact name matches at the top level."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "frame_name": {"type": "string", "description": "Exact name of the frame to delete"},
            },
            "required": ["frame_name"],
        },
    },
    {
        "name": "figma_set_prototype_start",
        "description": (
            "Set which frame is the START screen for prototype presentation mode. "
            "Always call this after all screens are built, passing the first/home screen name. "
            "Without this Figma picks a random start frame."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "frame_name": {"type": "string", "description": "Name of the frame to use as the prototype entry point (e.g. 'Dashboard')"},
            },
            "required": ["frame_name"],
        },
    },
    {
        "name": "figma_create_button",
        "description": (
            "Create a fully clickable button as an auto-layout FRAME (not a rectangle). "
            "The entire button area is interactive — no need to click a tiny hotspot. "
            "Use this for all buttons, nav tabs, list rows, cards that need prototype links."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "frame_name":    {"type": "string", "description": "Parent frame to place the button inside"},
                "name":          {"type": "string", "description": "Name for this button node"},
                "label":         {"type": "string", "description": "Text label shown on the button"},
                "x":             {"type": "number", "description": "X position inside parent frame"},
                "y":             {"type": "number", "description": "Y position inside parent frame"},
                "width":         {"type": "number", "description": "Button width in pixels"},
                "height":        {"type": "number", "description": "Button height in pixels"},
                "fill":          {"type": "string", "description": "Background hex color (default '#3b82f6')"},
                "text_color":    {"type": "string", "description": "Label hex color (default '#ffffff')"},
                "font_size":     {"type": "number", "description": "Label font size (default 14)"},
                "bold":          {"type": "boolean","description": "Bold label (default false)"},
                "corner_radius": {"type": "number", "description": "Corner radius (default 8)"},
            },
            "required": ["frame_name", "name", "label", "x", "y", "width", "height"],
        },
    },
    {
        "name": "figma_set_active_tab_style",
        "description": (
            "Visually highlight the active/selected nav tab on a screen by changing its fill and text color. "
            "Call once per screen after creating the nav bar to show which tab is selected on that screen."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "frame_name":    {"type": "string", "description": "Name of the parent frame"},
                "tab_node_name": {"type": "string", "description": "Name of the tab/button node to mark as active"},
                "active_fill":   {"type": "string", "description": "Active tab background hex color (default '#3b82f6')"},
                "active_text":   {"type": "string", "description": "Active tab text hex color (default '#ffffff')"},
                "inactive_fill": {"type": "string", "description": "Inactive tab background hex color (default 'transparent'/#1a1a2e)"},
            },
            "required": ["frame_name", "tab_node_name"],
        },
    },
    {
        "name": "figma_create_auto_layout_frame",
        "description": (
            "Create a frame with auto-layout enabled. Use this for nav bars, tab bars, button rows, card lists, "
            "and any container that arranges children automatically. Children are placed with itemSpacing gap "
            "and respect padding. direction='HORIZONTAL' for rows, 'VERTICAL' for columns."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "parent_frame": {"type": "string",  "description": "Name of the parent frame to place this inside (use '' to create as top-level frame)"},
                "name":         {"type": "string",  "description": "Name for this auto-layout frame"},
                "direction":    {"type": "string",  "description": "'HORIZONTAL' (row) or 'VERTICAL' (column). Default: HORIZONTAL"},
                "x":            {"type": "number",  "description": "X position inside parent"},
                "y":            {"type": "number",  "description": "Y position inside parent"},
                "width":        {"type": "number",  "description": "Width in pixels (0 = hug contents horizontally)"},
                "height":       {"type": "number",  "description": "Height in pixels (0 = hug contents vertically)"},
                "item_spacing": {"type": "number",  "description": "Gap between children in pixels (default 0)"},
                "padding_h":    {"type": "number",  "description": "Left & right padding in pixels (default 0)"},
                "padding_v":    {"type": "number",  "description": "Top & bottom padding in pixels (default 0)"},
                "align_main":   {"type": "string",  "description": "Main axis alignment: 'MIN' (start), 'CENTER', 'MAX' (end), 'SPACE_BETWEEN'. Default: MIN"},
                "align_cross":  {"type": "string",  "description": "Cross axis alignment: 'MIN', 'CENTER', 'MAX'. Default: CENTER"},
                "fill":         {"type": "string",  "description": "Background hex color (default transparent — no fill)"},
                "corner_radius":{"type": "number",  "description": "Corner radius (default 0)"},
            },
            "required": ["parent_frame", "name", "x", "y", "width", "height"],
        },
    },
    {
        "name": "figma_create_ellipse",
        "description": "Create a circle or ellipse inside a frame. Use for avatars, profile pictures, status dots, icons, and decorative circles.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "frame_name":{"type": "string", "description": "Name of the parent frame"},
                "name":      {"type": "string", "description": "Name for this ellipse"},
                "x":         {"type": "number", "description": "X position inside frame"},
                "y":         {"type": "number", "description": "Y position inside frame"},
                "width":     {"type": "number", "description": "Width in pixels (same as height for a circle)"},
                "height":    {"type": "number", "description": "Height in pixels (same as width for a circle)"},
                "fill":      {"type": "string", "description": "Fill hex color (default '#cccccc')"},
            },
            "required": ["frame_name", "name", "x", "y", "width", "height"],
        },
    },
    {
        "name": "figma_set_stroke",
        "description": (
            "Add or update a stroke (border/outline) on any existing node inside a frame. "
            "Use for input field borders, card outlines, divider lines, selected-tab underlines."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "frame_name":   {"type": "string", "description": "Name of the parent frame"},
                "node_name":    {"type": "string", "description": "Name of the node to stroke"},
                "color":        {"type": "string", "description": "Stroke hex color (default '#cccccc')"},
                "weight":       {"type": "number", "description": "Stroke width in pixels (default 1)"},
                "position":     {"type": "string", "description": "'INSIDE', 'OUTSIDE', or 'CENTER' (default CENTER)"},
            },
            "required": ["frame_name", "node_name"],
        },
    },
    {
        "name": "figma_add_overlay_link",
        "description": (
            "Add a prototype ON_CLICK link that opens a target frame as an OVERLAY (modal, bottom sheet, drawer) "
            "rather than navigating away. Use for popups, modals, side drawers, confirmation dialogs."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_frame":  {"type": "string", "description": "Frame containing the clickable node"},
                "source_node":   {"type": "string", "description": "Name of the clickable node"},
                "overlay_frame": {"type": "string", "description": "Frame to show as overlay"},
                "overlay_type":  {"type": "string", "description": "'OVERLAY' (modal), 'SWAP' (replace), 'SCROLL_ANIMATE'. Default: OVERLAY"},
                "position":      {"type": "string", "description": "Where to place the overlay: 'CENTER', 'TOP', 'BOTTOM', 'TOP_LEFT', 'TOP_RIGHT', 'BOTTOM_LEFT', 'BOTTOM_RIGHT', 'MANUAL'. Default: CENTER"},
            },
            "required": ["source_frame", "source_node", "overlay_frame"],
        },
    },
    {
        "name": "figma_set_scrollable",
        "description": (
            "Make a frame scrollable in prototype mode. Use when a screen's content is taller or wider than the "
            "frame viewport (e.g. a long list, an infinite feed). Set clip_content=true to hide overflow in the editor."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "frame_name":    {"type": "string", "description": "Name of the frame to make scrollable"},
                "direction":     {"type": "string", "description": "'VERTICAL', 'HORIZONTAL', or 'BOTH'. Default: VERTICAL"},
                "clip_content":  {"type": "boolean","description": "Whether to clip overflow content in editor (default true)"},
            },
            "required": ["frame_name"],
        },
    },
    {
        "name": "figma_inspect_frame",
        "description": (
            "Read the full node tree of an existing frame — returns every child node with its name, type, "
            "position (x/y), size (width/height), fill colour, text content, font size, and corner radius. "
            "Use this in 'edit' mode BEFORE making any changes so you know exactly what nodes exist and "
            "what their current values are. Essential for surgical edits without destroying existing content."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "frame_name": {"type": "string", "description": "Name of the frame to inspect"},
                "depth":      {"type": "number", "description": "How many levels deep to traverse (default 3). Use 1 for top-level only."},
            },
            "required": ["frame_name"],
        },
    },
    {
        "name": "figma_update_node",
        "description": (
            "Surgically update properties of a named node inside a frame WITHOUT touching anything else. "
            "Can change: fill colour, text content, x/y position, width/height, corner radius, opacity, font size. "
            "Only the properties you pass are changed — everything else stays exactly as it is. "
            "Use this in 'edit' mode instead of delete-and-recreate."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "frame_name":    {"type": "string", "description": "Parent frame name"},
                "node_name":     {"type": "string", "description": "Exact name of the node to update"},
                "fill":          {"type": "string", "description": "New fill hex colour (e.g. '#0064D2'). Omit to leave unchanged."},
                "text":          {"type": "string", "description": "New text content. Only valid for TEXT nodes. Omit to leave unchanged."},
                "x":             {"type": "number", "description": "New x position. Omit to leave unchanged."},
                "y":             {"type": "number", "description": "New y position. Omit to leave unchanged."},
                "width":         {"type": "number", "description": "New width. Omit to leave unchanged."},
                "height":        {"type": "number", "description": "New height. Omit to leave unchanged."},
                "corner_radius": {"type": "number", "description": "New corner radius. Omit to leave unchanged."},
                "opacity":       {"type": "number", "description": "New opacity 0–1. Omit to leave unchanged."},
                "font_size":     {"type": "number", "description": "New font size (TEXT nodes only). Omit to leave unchanged."},
            },
            "required": ["frame_name", "node_name"],
        },
    },
    {
        "name": "figma_create_chart",
        "description": (
            "Draw a chart inside a Figma frame. Supports bar, horizontal_bar, line, area, scatter, "
            "pie, donut, gauge, and sparkline chart types. All drawing is done with "
            "native Figma primitives (rectangles, ellipses, rotation) — no Bezier paths. "
            "Use instead of figma_create_rectangle when the content is a chart."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "frame_name":   {"type": "string",  "description": "Parent frame to place the chart in"},
                "chart_type":   {"type": "string",  "description": "'bar'|'horizontal_bar'|'line'|'area'|'scatter'|'pie'|'donut'|'gauge'|'sparkline'"},
                "title":        {"type": "string",  "description": "Chart title text shown above the chart"},
                "x":            {"type": "number",  "description": "X position of chart area"},
                "y":            {"type": "number",  "description": "Y position of chart area (top of title)"},
                "width":        {"type": "number",  "description": "Total width of the chart area"},
                "height":       {"type": "number",  "description": "Total height of the chart area (excluding title)"},
                "data_points":  {
                    "type": "array",
                    "description": "Array of {label, value} objects. For pie/donut each item is one slice.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "value": {"type": "number"},
                        },
                    },
                },
                "series":       {
                    "type": "array",
                    "description": "For multi-series charts (grouped bar, multi-line): array of {name, color, values:[]} ",
                    "items": {"type": "object"},
                },
                "color":        {"type": "string",  "description": "Primary color hex (default: brand accent #0064D2)"},
                "colors":       {"type": "array",   "description": "Array of hex colors for pie slices or multi-series", "items": {"type": "string"}},
                "show_labels":  {"type": "boolean", "description": "Show value labels on bars/slices (default true)"},
                "show_legend":  {"type": "boolean", "description": "Show legend (default true for pie/donut)"},
                "gauge_min":    {"type": "number",  "description": "Gauge minimum value (default 0)"},
                "gauge_max":    {"type": "number",  "description": "Gauge maximum value (default 100)"},
                "gauge_value":  {"type": "number",  "description": "Current gauge value"},
            },
            "required": ["frame_name", "chart_type", "x", "y", "width", "height"],
        },
    },
    {
        "name": "figma_create_svg_node",
        "description": (
            "Insert a browser-extracted SVG file into a Figma frame as a fully editable vector node. "
            "Use this for charts and maps captured from a live web app via Playwright — every bar, line, "
            "slice, and axis becomes an individual Figma vector element. "
            "Pass the absolute path to the .svg file saved during the Playwright extraction pass. "
            "ALWAYS prefer this over figma_create_chart when an SVG file is available."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "frame_name":  {"type": "string", "description": "Parent frame to place the SVG in"},
                "svg_path":    {"type": "string", "description": "Absolute path to the .svg file"},
                "name":        {"type": "string", "description": "Node name in Figma (default: svg-node)"},
                "x":           {"type": "number", "description": "X position in the frame"},
                "y":           {"type": "number", "description": "Y position in the frame"},
                "width":       {"type": "number", "description": "Width to resize the SVG node to (px)"},
                "height":      {"type": "number", "description": "Height to resize the SVG node to (px)"},
            },
            "required": ["frame_name", "svg_path", "x", "y", "width", "height"],
        },
    },
    {
        "name": "figma_create_table",
        "description": (
            "Draw a complete data table (grid) inside a Figma frame — header row plus data rows, "
            "with alternating row backgrounds, column dividers, and proper text labels. "
            "Use for any data grid, data table, inventory list, sales grid, or tabular report. "
            "ALWAYS use this tool instead of manually drawing rectangles and text for tables."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "frame_name":   {"type": "string", "description": "Parent frame to place the table in"},
                "name":         {"type": "string", "description": "Node name for the table group (default: data-table)"},
                "x":            {"type": "number", "description": "X position"},
                "y":            {"type": "number", "description": "Y position"},
                "width":        {"type": "number", "description": "Total table width in px"},
                "columns":      {
                    "type": "array",
                    "description": "Column definitions. Each item: {label: string, width?: number}. Widths are proportional if provided, otherwise equal.",
                    "items": {"type": "object"},
                },
                "rows":         {
                    "type": "array",
                    "description": "Data rows. Each row is an array of cell strings matching the column order.",
                    "items": {"type": "array", "items": {"type": "string"}},
                },
                "row_height":       {"type": "number", "description": "Height of each row in px (default 40)"},
                "header_height":    {"type": "number", "description": "Height of the header row in px (default 44)"},
                "header_bg":        {"type": "string", "description": "Header background hex (default #1E293B for dark, #F1F5F9 for light)"},
                "header_text":      {"type": "string", "description": "Header text hex (default #F1F5F9)"},
                "row_bg":           {"type": "string", "description": "Even row background hex (default #0F172A)"},
                "row_alt_bg":       {"type": "string", "description": "Odd row background hex (default #1E293B)"},
                "row_text":         {"type": "string", "description": "Row text hex (default #CBD5E1)"},
                "accent_col":       {"type": "number", "description": "Zero-based column index to render in accent colour (optional)"},
                "accent_color":     {"type": "string", "description": "Accent colour hex for the accent column (default #6366F1)"},
                "show_row_dividers":{"type": "boolean", "description": "Draw a 1px divider between rows (default true)"},
            },
            "required": ["frame_name", "x", "y", "width", "columns", "rows"],
        },
    },
    {
        "name": "figma_create_image_from_file",
        "description": (
            "Insert a local image file (PNG, JPG, WEBP) directly into a Figma frame as an image fill. "
            "Use for placing screenshots, logos, photos, or any existing image file into a mockup. "
            "The image is read server-side and injected via figma.createImage(bytes). "
            "Pass an absolute file path. The image is scaled to fit the given width×height with FILL mode."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "frame_name": {"type": "string", "description": "Parent frame to place the image in"},
                "file_path":  {"type": "string", "description": "Absolute path to the image file (PNG/JPG/WEBP)"},
                "name":       {"type": "string", "description": "Node name (default: image)"},
                "x":          {"type": "number", "description": "X position"},
                "y":          {"type": "number", "description": "Y position"},
                "width":      {"type": "number", "description": "Width in px"},
                "height":     {"type": "number", "description": "Height in px"},
                "scale_mode": {"type": "string", "description": "'FILL' (default), 'FIT', 'CROP', or 'TILE'"},
                "corner_radius": {"type": "number", "description": "Corner radius in px (default 0)"},
            },
            "required": ["frame_name", "file_path", "x", "y", "width", "height"],
        },
    },
    {
        "name": "figma_create_map",
        "description": (
            "Insert a real map image into a Figma frame by fetching an OpenStreetMap tile "
            "server-side and injecting it as an image fill. No API key required. "
            "Use for any map, world map, regional map, or location visual in a mockup."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "frame_name": {"type": "string",  "description": "Parent frame to place the map in"},
                "name":       {"type": "string",  "description": "Node name (default: map-image)"},
                "x":          {"type": "number",  "description": "X position"},
                "y":          {"type": "number",  "description": "Y position"},
                "width":      {"type": "number",  "description": "Width in px (default 600)"},
                "height":     {"type": "number",  "description": "Height in px (default 300)"},
                "lat":        {"type": "number",  "description": "Centre latitude (default 51.505 — London)"},
                "lon":        {"type": "number",  "description": "Centre longitude (default -0.09)"},
                "zoom":       {"type": "integer", "description": "Zoom level 1–18 (default 12). 1=world, 12=city, 16=street"},
                "style":      {"type": "string",  "description": "'osm' (default, OpenStreetMap standard) or 'topo' (OpenTopoMap)"},
            },
            "required": ["frame_name", "x", "y"],
        },
    },
]


# ── Tool implementations ───────────────────────────────────────────────────────

def _hex_to_rgb(hex_color: str) -> dict:
    h = hex_color.lstrip("#")
    if len(h) == 3: h = "".join(c*2 for c in h)
    return {
        "r": round(int(h[0:2], 16) / 255, 3),
        "g": round(int(h[2:4], 16) / 255, 3),
        "b": round(int(h[4:6], 16) / 255, 3),
    }


def _build_js(tool_name: str, args: dict) -> str:
    """Convert a tool call into Figma Plugin API JavaScript."""

    if tool_name == "figma_create_sidebar_nav":
        fname         = args["frame_name"].replace("'", "\\'")
        sw            = args.get("sidebar_width",  _T_SIDEBAR_W)
        sh            = args.get("sidebar_height", _T_SIDEBAR_H)
        sbg           = args.get("sidebar_bg",     _T_SIDEBAR_BG)
        items         = args.get("items", [])
        item_h        = args.get("item_height", _T_NAV_ITEM_H)
        start_y       = args.get("start_y",     _T_NAV_START_Y)
        active_color  = args.get("active_color", _T_ACTIVE_NAV)
        active_bg     = args.get("active_bg",    _T_ACTIVE_BG)
        text_color    = args.get("text_color",   _T_TEXT2)
        active_text   = args.get("active_text",  _T_ACTIVE_NAV)
        border_color  = args.get("border_color", _T_BORDER)
        items_json    = json.dumps(items)
        sbg_r, sbg_g, sbg_b   = _hex_to_rgb(sbg).values()
        ac_r,  ac_g,  ac_b    = _hex_to_rgb(active_color).values()
        abg_r, abg_g, abg_b   = _hex_to_rgb(active_bg).values()
        tc_r,  tc_g,  tc_b    = _hex_to_rgb(text_color).values()
        atc_r, atc_g, atc_b   = _hex_to_rgb(active_text).values()
        bc_r,  bc_g,  bc_b    = _hex_to_rgb(border_color).values()
        return f"""
(async () => {{
  await figma.loadFontAsync({{family:'{_T_FONT_BODY}',style:'{_T_W_MEDIUM}'}});
  await figma.loadFontAsync({{family:'{_T_FONT_BODY}',style:'{_T_W_REGULAR}'}});

  var screenFrame = null;
  for (var i=0;i<figma.currentPage.children.length;i++) {{
    if (figma.currentPage.children[i].name==='{fname}') {{ screenFrame=figma.currentPage.children[i]; break; }}
  }}
  if (!screenFrame) return JSON.stringify({{error:'Frame not found: {fname}'}});

  // White sidebar background with right border
  var sidebar = figma.createFrame();
  sidebar.name = 'sidebar-{fname}';
  sidebar.resize({sw}, {sh});
  sidebar.x = 0; sidebar.y = 0;
  sidebar.fills = [{{type:'SOLID',color:{{r:{sbg_r},g:{sbg_g},b:{sbg_b}}}}}];
  sidebar.strokes = [{{type:'SOLID',color:{{r:{bc_r},g:{bc_g},b:{bc_b}}}}}];
  sidebar.strokeWeight = 1;
  sidebar.strokeAlign = 'INSIDE';
  sidebar.strokeTopWeight = 0; sidebar.strokeLeftWeight = 0; sidebar.strokeBottomWeight = 0;
  sidebar.strokeRightWeight = 1;
  screenFrame.appendChild(sidebar);

  var items = {items_json};
  var itemH = {item_h};
  var created = [];

  for (var idx=0; idx<items.length; idx++) {{
    var item = items[idx];
    var itemY = {start_y} + idx * itemH;

    var btn = figma.createFrame();
    btn.name = item.name || ('tab-' + item.label + '-on-{fname}');
    btn.resize({sw}, itemH);
    btn.x = 0;
    btn.y = itemY;
    btn.layoutMode = 'HORIZONTAL';
    btn.primaryAxisAlignItems = 'MIN';
    btn.counterAxisAlignItems = 'CENTER';
    btn.primaryAxisSizingMode = 'FIXED';
    btn.counterAxisSizingMode = 'FIXED';
    btn.paddingLeft = {_T_NAV_PAD_LEFT};
    btn.itemSpacing = 10;
    btn.clipsContent = false;

    if (item.active) {{
      btn.fills = [{{type:'SOLID',color:{{r:{abg_r},g:{abg_g},b:{abg_b}}},opacity:1}}];

      var accent = figma.createRectangle();
      accent.name = 'active-accent';
      accent.resize({_T_NAV_ACCENT_W}, itemH);
      accent.x = 0; accent.y = 0;
      accent.fills = [{{type:'SOLID',color:{{r:{ac_r},g:{ac_g},b:{ac_b}}}}}];
      accent.cornerRadius = 0;
      btn.appendChild(accent);
    }} else {{
      btn.fills = [];
    }}

    var labelT = figma.createText();
    labelT.fontName = item.active ? {{family:'{_T_FONT_BODY}',style:'{_T_W_MEDIUM}'}} : {{family:'{_T_FONT_BODY}',style:'{_T_W_REGULAR}'}};
    labelT.characters = item.label;
    labelT.fontSize = {_T_FS_NAV};
    if (item.active) {{
      labelT.fills = [{{type:'SOLID',color:{{r:{atc_r},g:{atc_g},b:{atc_b}}}}}];
    }} else {{
      labelT.fills = [{{type:'SOLID',color:{{r:{tc_r},g:{tc_g},b:{tc_b}}}}}];
    }}
    btn.appendChild(labelT);

    sidebar.appendChild(btn);
    created.push({{name:btn.name, x:0, y:itemY, width:{sw}, height:itemH}});
  }}

  return JSON.stringify({{created:true, sidebar:'sidebar-{fname}', items:created}});
}})();
""".strip()

    if tool_name == "figma_apply_brand":
        frames_filter = json.dumps(args.get("frames", []))
        header_bg  = args.get("header_bg",  _T_HEADER_BG)
        sidebar_bg = args.get("sidebar_bg", _T_SIDEBAR_BG)
        card_bg    = args.get("card_bg",    _T_CARD_BG)
        page_bg    = args.get("page_bg",    _T_PAGE_BG)
        accent     = args.get("accent",     _T_ACCENT)

        # Pre-compute all brand RGB values
        h_r, h_g, h_b   = _hex_to_rgb(header_bg).values()
        s_r, s_g, s_b   = _hex_to_rgb(sidebar_bg).values()
        c_r, c_g, c_b   = _hex_to_rgb(card_bg).values()
        p_r, p_g, p_b   = _hex_to_rgb(page_bg).values()
        a_r, a_g, a_b   = _hex_to_rgb(accent).values()
        vb_r, vb_g, vb_b = _hex_to_rgb(_T_BRAND_DARK).values()    # brand dark (e.g. Vital Blue)
        fb_r, fb_g, fb_b = _hex_to_rgb(_T_BRAND_ACCENT).values()  # brand accent (e.g. Forward Blue)
        mm_r, mm_g, mm_b = _hex_to_rgb(_T_BRAND_MIST).values()    # brand mist (e.g. Morning Mist)
        ql_r, ql_g, ql_b = _hex_to_rgb(_T_BRAND_BG).values()      # brand bg (e.g. Quiet Light)

        return f"""
(async () => {{
  await figma.loadAllPagesAsync();

  var frameFilter = {frames_filter};
  var allFrames = figma.currentPage.children.filter(function(n) {{
    return n.type === 'FRAME' &&
           (frameFilter.length === 0 || frameFilter.indexOf(n.name) >= 0);
  }});

  var stats = {{recolored: 0, frames: []}};

  // Color mapping rules: [match_fn, new_color]
  // Dark backgrounds (likely page/sidebar bg) → brand equivalents
  function isDark(c) {{ return c.r < 0.2 && c.g < 0.2 && c.b < 0.2; }}
  function isVeryDark(c) {{ return c.r < 0.15 && c.g < 0.18 && c.b < 0.3; }}
  function isMidBlue(c) {{ return c.b > 0.5 && c.r < 0.3 && c.g < 0.5; }}
  function isLightGray(c) {{ return c.r > 0.9 && c.g > 0.9 && c.b > 0.9 && Math.abs(c.r-c.g) < 0.05; }}
  function isPurple(c) {{ return c.r > 0.3 && c.b > 0.5 && c.g < 0.3; }}
  function isYellow(c) {{ return c.r > 0.8 && c.g > 0.7 && c.b < 0.3; }}

  function remapColor(c) {{
    if (!c) return null;
    // Sidebar/header darks → Vital Blue
    if (isVeryDark(c)) return {{r:{vb_r},g:{vb_g},b:{vb_b}}};
    // Generic dark bg → sidebar brand
    if (isDark(c) && c.b > c.r) return {{r:{s_r},g:{s_g},b:{s_b}}};
    // Mid blues → Forward Blue
    if (isMidBlue(c)) return {{r:{fb_r},g:{fb_g},b:{fb_b}}};
    // Very light gray / near-white cards → card bg
    if (isLightGray(c) && c.r < 0.98) return {{r:{ql_r},g:{ql_g},b:{ql_b}}};
    // Pure white stays white (headers, cards)
    return null; // no remap
  }}

  function applyBrandToNode(node) {{
    try {{
      // Remap fills
      if (node.fills && node.fills.length > 0 && node.type !== 'TEXT') {{
        var newFills = node.fills.map(function(f) {{
          if (f.type === 'SOLID' && f.color) {{
            var newColor = remapColor(f.color);
            if (newColor) {{
              stats.recolored++;
              return {{type:'SOLID', color:newColor, opacity: f.opacity || 1}};
            }}
          }}
          return f;
        }});
        node.fills = newFills;
      }}

      // Remap strokes
      if (node.strokes && node.strokes.length > 0) {{
        var newStrokes = node.strokes.map(function(f) {{
          if (f.type === 'SOLID' && f.color) {{
            var newColor = remapColor(f.color);
            if (newColor) return {{type:'SOLID', color:newColor}};
          }}
          return f;
        }});
        node.strokes = newStrokes;
      }}

      // Recurse into children
      if (node.children) {{
        for (var i = 0; i < node.children.length; i++) {{
          applyBrandToNode(node.children[i]);
        }}
      }}
    }} catch(e) {{
      // Skip read-only nodes
    }}
  }}

  for (var f = 0; f < allFrames.length; f++) {{
    applyBrandToNode(allFrames[f]);
    // Set frame background to page bg
    try {{
      allFrames[f].fills = [{{type:'SOLID',color:{{r:{p_r},g:{p_g},b:{p_b}}}}}];
    }} catch(e) {{}}
    stats.frames.push(allFrames[f].name);
  }}

  figma.notify('Brand applied to ' + allFrames.length + ' frame(s) — ' + stats.recolored + ' colors updated', {{timeout:5000}});

  return JSON.stringify({{
    ok: true,
    frames_branded: stats.frames,
    colors_remapped: stats.recolored
  }});
}})();
""".strip()

    if tool_name == "figma_get_status":
        return r"""
(async () => {
  var frames = figma.currentPage.children.filter(function(n){ return n.type==='FRAME'; });
  return JSON.stringify({
    page: figma.currentPage.name,
    frame_count: frames.length,
    frame_names: frames.map(function(f){ return f.name; }),
    ready: true
  });
})();
""".strip()

    if tool_name == "figma_get_file_url":
        return r"""
(async () => {
  var fileKey = figma.fileKey || '';
  var fileName = figma.root ? figma.root.name : '';
  var url = fileKey ? ('https://www.figma.com/design/' + fileKey + '/' + encodeURIComponent(fileName)) : '';
  return JSON.stringify({
    url: url,
    file_key: fileKey,
    file_name: fileName,
    ok: fileKey !== ''
  });
})();
""".strip()

    if tool_name == "figma_create_logo":
        fname  = args["frame_name"].replace("'", "\'")
        name   = args.get("name", f"logo-{_DS.get('brand','ds')}").replace("'", "\\'")
        x, y   = args.get("x", _T_LOGO_X), args.get("y", _T_LOGO_Y)
        w      = args.get("width",  _T_LOGO_W)
        h      = args.get("height", _T_LOGO_H)
        # Base64-encoded Mobility Global logo PNG — embedded directly so no fetch needed
        LOGO_B64 = "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"
        return f"""
(async () => {{
  function findNode(root, name) {{
    if (root.name === name) return root;
    if (root.children) for (var k=0;k<root.children.length;k++) {{
      var f=findNode(root.children[k],name); if(f) return f;
    }}
    return null;
  }}
  var parent = null;
  for (var i=0;i<figma.currentPage.children.length;i++) {{
    var found = findNode(figma.currentPage.children[i], '{fname}');
    if (found) {{ parent = found; break; }}
  }}
  if (!parent) return JSON.stringify({{error:'Frame not found: {fname}'}});

  // Decode base64 to Uint8Array
  var b64 = '{LOGO_B64}';
  var binary = atob(b64);
  var bytes = new Uint8Array(binary.length);
  for (var i=0; i<binary.length; i++) bytes[i] = binary.charCodeAt(i);

  try {{
    var imageHash = figma.createImage(bytes).hash;
    var logo = figma.createRectangle();
    logo.name = '{name}';
    logo.resize({w}, {h});
    logo.x = {x}; logo.y = {y};
    logo.fills = [{{type:'IMAGE', imageHash:imageHash, scaleMode:'FIT'}}];
    logo.strokes = [];
    parent.appendChild(logo);
    return JSON.stringify({{created:true, name:'{name}', source:'embedded-png'}});
  }} catch(e) {{
    await figma.loadFontAsync({{family:'{_T_FONT_HEADING}',style:'{_T_W_BOLD}'}});
    var t = figma.createText();
    t.name = '{name}';
    t.fontName = {{family:'{_T_FONT_HEADING}',style:'{_T_W_BOLD}'}};
    t.characters = '{_DS.get("brand", "Brand")}';
    t.fontSize = {_T_FS_H4};
    t.fills = [{{type:'SOLID',color:{{r:{_hex_to_rgb(_T_BRAND_DARK)['r']},g:{_hex_to_rgb(_T_BRAND_DARK)['g']},b:{_hex_to_rgb(_T_BRAND_DARK)['b']}}}}}];
    t.x = {x}; t.y = {y + 10};
    parent.appendChild(t);
    return JSON.stringify({{created:true, fallback:true, error:e.message}});
  }}
}})();
""".strip()


    if tool_name == "figma_wire_all":
        links = args.get("links", [])
        start_frame = args.get("start_frame", "").replace("'", "\\'")
        links_json = json.dumps(links)
        return f"""
(async () => {{
  await figma.loadAllPagesAsync();

  // Build frame lookup
  var frameMap = {{}};
  for (var i = 0; i < figma.currentPage.children.length; i++) {{
    var f = figma.currentPage.children[i];
    frameMap[f.name] = f;
  }}

  // Deep node finder
  function findDeep(node, name) {{
    if (node.name === name) return node;
    if (node.children) {{
      for (var k = 0; k < node.children.length; k++) {{
        var found = findDeep(node.children[k], name);
        if (found) return found;
      }}
    }}
    return null;
  }}

  var links = {links_json};
  var results = [];

  for (var li = 0; li < links.length; li++) {{
    var link = links[li];
    var srcFrameName = link.source_frame;
    var srcNodeName  = link.source_node;
    var dstFrameName = link.target_frame;
    var linkType     = link.type || 'NAVIGATE';

    var srcFrame = frameMap[srcFrameName];
    var dstFrame = frameMap[dstFrameName];

    if (!srcFrame) {{ results.push({{error: 'Source frame not found: ' + srcFrameName, link: li}}); continue; }}
    if (!dstFrame) {{ results.push({{error: 'Target frame not found: ' + dstFrameName, link: li}}); continue; }}

    // Skip self-navigation (Figma does not allow it)
    if (srcFrameName === dstFrameName && linkType === 'NAVIGATE') {{
      results.push({{skipped: true, reason: 'self-navigation not allowed', from: srcNodeName, to: dstFrameName}});
      continue;
    }}

    var node = findDeep(srcFrame, srcNodeName);
    if (!node) {{ results.push({{error: 'Node not found: ' + srcNodeName + ' in ' + srcFrameName, link: li}}); continue; }}

    try {{
      var action = {{
        type: 'NODE',
        destinationId: dstFrame.id,
        navigation: linkType,
        transition: linkType === 'OVERLAY'
          ? {{type: 'DISSOLVE', easing: {{type: 'LINEAR'}}, duration: 0.2}}
          : null,
        preserveScrollPosition: false
      }};
      // For OVERLAY: position the modal centered on the source frame
      if (linkType === 'OVERLAY') {{
        var centerX = Math.round((srcFrame.width  - dstFrame.width)  / 2);
        var centerY = Math.round((srcFrame.height - dstFrame.height) / 2);
        action.overlayRelativePosition = {{
          x: centerX > 0 ? centerX : 0,
          y: centerY > 0 ? centerY : 0
        }};
      }}
      var reaction = {{
        trigger: {{type: 'ON_CLICK'}},
        actions: [action]
      }};
      await node.setReactionsAsync([reaction]);
      // Immediately verify reaction was stored
      var stored = node.reactions && node.reactions.length > 0;
      results.push({{
        wired: stored,
        verified: stored,
        from: srcNodeName,
        to: dstFrameName,
        type: linkType,
        error: stored ? null : 'setReactionsAsync ran but node.reactions is still empty'
      }});
    }} catch(e) {{
      results.push({{error: e.message || String(e), from: srcNodeName, to: dstFrameName}});
    }}
  }}

  // Set prototype start frame
  var startName = '{start_frame}';
  if (startName && frameMap[startName]) {{
    figma.currentPage.prototypeStartNode = frameMap[startName];
  }}

  var wired   = results.filter(function(r){{ return r.wired; }}).length;
  var skipped = results.filter(function(r){{ return r.skipped; }}).length;
  var failed  = results.filter(function(r){{ return r.error; }});

  // Show result in Figma Desktop so it's visible even if return value is discarded
  var msg = 'Wired ' + wired + '/' + links.length + ' links';
  if (failed.length > 0) msg += ' (' + failed.length + ' failed)';
  figma.notify(msg, {{timeout: 5000, error: failed.length > 0}});

  return JSON.stringify({{
    total: links.length,
    wired: wired,
    skipped: skipped,
    errors: failed,
    start_frame: startName || null,
    results: results
  }});
}})();
""".strip()

    if tool_name == "figma_inspect_reactions":
        fname = args["frame_name"].replace("'", "\\'")
        return f"""
(async () => {{
  var frame = null;
  for (var i = 0; i < figma.currentPage.children.length; i++) {{
    if (figma.currentPage.children[i].name === '{fname}') {{ frame = figma.currentPage.children[i]; break; }}
  }}
  if (!frame) return JSON.stringify({{error: 'Frame not found: {fname}'}});

  var nodesWithReactions = [];
  var nodesWithoutReactions = [];

  function walk(node) {{
    if (node.reactions && node.reactions.length > 0) {{
      var rxs = node.reactions.map(function(r) {{
        var action = (r.actions && r.actions[0]) || r.action || {{}};
        return {{
          trigger:     r.trigger ? r.trigger.type : 'unknown',
          navigation:  action.navigation || action.type || 'unknown',
          destination: action.destinationId || 'none',
          type:        action.type || 'unknown'
        }};
      }});
      nodesWithReactions.push({{ name: node.name, type: node.type, reactions: rxs }});
    }} else if (node.name && (node.name.includes('-btn-') || node.name.startsWith('tab-'))) {{
      nodesWithoutReactions.push({{ name: node.name, type: node.type }});
    }}
    if (node.children) {{
      for (var k = 0; k < node.children.length; k++) walk(node.children[k]);
    }}
  }}
  walk(frame);

  return JSON.stringify({{
    frame: '{fname}',
    wired_count: nodesWithReactions.length,
    unwired_interactive: nodesWithoutReactions.length,
    wired: nodesWithReactions,
    unwired: nodesWithoutReactions
  }});
}})();
""".strip()

    if tool_name == "figma_list_frame_nodes":
        fname  = args["frame_name"].replace("'", "\\'")
        filter_str = (args.get("filter") or "").replace("'", "\\'").lower()
        return f"""
(async () => {{
  var frame = null;
  for (var i = 0; i < figma.currentPage.children.length; i++) {{
    if (figma.currentPage.children[i].name === '{fname}') {{ frame = figma.currentPage.children[i]; break; }}
  }}
  if (!frame) return JSON.stringify({{error: 'Frame not found: {fname}'}});

  var results = [];
  function walk(node, depth) {{
    if (depth > 10) return;
    if (node.name) {{
      var nameLC = node.name.toLowerCase();
      var filter = '{filter_str}';
      if (!filter || nameLC.indexOf(filter) !== -1) {{
        results.push({{
          name: node.name,
          type: node.type,
          x: Math.round(node.x),
          y: Math.round(node.y),
          width:  Math.round(node.width  || 0),
          height: Math.round(node.height || 0),
          hasReactions: !!(node.reactions && node.reactions.length > 0)
        }});
      }}
    }}
    if (node.children) {{
      for (var k = 0; k < node.children.length; k++) walk(node.children[k], depth + 1);
    }}
  }}
  walk(frame, 0);
  return JSON.stringify({{frame: '{fname}', total: results.length, nodes: results}});
}})();
""".strip()

    if tool_name == "figma_list_frames":
        return r"""
(async () => {
  var frames = figma.currentPage.children.filter(function(n){ return n.type==='FRAME'; });
  return JSON.stringify(frames.map(function(f){
    return {id: f.id, name: f.name, width: f.width, height: f.height, x: f.x, y: f.y,
            children: f.children.length};
  }));
})();
""".strip()

    if tool_name == "figma_create_frame":
        name   = args["name"].replace("'", "\\'")
        w      = args.get("width", 390)
        h      = args.get("height", 844)
        x      = args.get("x", 0)
        y      = args.get("y", 0)
        fill   = args.get("fill", _T_PAGE_BG)
        rgb    = _hex_to_rgb(fill)
        return f"""
(async () => {{
  var f = figma.createFrame();
  f.name = '{name}';
  f.resize({w}, {h});
  f.x = {x}; f.y = {y};
  f.fills = [{{type:'SOLID', color:{{r:{rgb['r']},g:{rgb['g']},b:{rgb['b']}}}}}];
  figma.currentPage.appendChild(f);
  return JSON.stringify({{id: f.id, name: f.name, created: true}});
}})();
""".strip()

    if tool_name == "figma_create_rectangle":
        fname  = args["frame_name"].replace("'", "\\'")
        name   = args["name"].replace("'", "\\'")
        x, y   = args["x"], args["y"]
        w, h   = args["width"], args["height"]
        fill   = args.get("fill", _T_BORDER)
        radius = args.get("corner_radius", 0)
        rgb    = _hex_to_rgb(fill)
        return f"""
(async () => {{
  var frame = null;
  for (var i = 0; i < figma.currentPage.children.length; i++) {{
    if (figma.currentPage.children[i].name === '{fname}') {{ frame = figma.currentPage.children[i]; break; }}
  }}
  if (!frame) return JSON.stringify({{error: 'Frame not found: {fname}'}});
  var r = figma.createRectangle();
  r.name = '{name}';
  r.resize({w}, {h});
  r.x = {x}; r.y = {y};
  r.fills = [{{type:'SOLID', color:{{r:{rgb['r']},g:{rgb['g']},b:{rgb['b']}}}}}];
  r.cornerRadius = {radius};
  frame.appendChild(r);
  return JSON.stringify({{id: r.id, name: r.name, created: true}});
}})();
""".strip()

    if tool_name == "figma_create_text":
        fname    = args["frame_name"].replace("'", "\\'")
        name     = args["name"].replace("'", "\\'")
        content  = args["content"].replace("'", "\\'").replace("\n", "\\n")
        x, y     = args["x"], args["y"]
        size     = args.get("font_size", 14)
        color    = args.get("color", _T_TEXT)
        bold     = args.get("bold", False)
        style    = "Bold" if bold else "Regular"
        rgb      = _hex_to_rgb(color)
        return f"""
(async () => {{
  await figma.loadFontAsync({{family:'{_T_FONT_BODY}', style:'{style}'}});
  var frame = null;
  for (var i = 0; i < figma.currentPage.children.length; i++) {{
    if (figma.currentPage.children[i].name === '{fname}') {{ frame = figma.currentPage.children[i]; break; }}
  }}
  if (!frame) return JSON.stringify({{error: 'Frame not found: {fname}'}});
  var t = figma.createText();
  t.name = '{name}';
  t.fontName = {{family:'{_T_FONT_BODY}', style:'{style}'}};
  t.characters = '{content}';
  t.fontSize = {size};
  t.fills = [{{type:'SOLID', color:{{r:{rgb['r']},g:{rgb['g']},b:{rgb['b']}}}}}];
  t.x = {x}; t.y = {y};
  frame.appendChild(t);
  return JSON.stringify({{id: t.id, name: t.name, created: true}});
}})();
""".strip()

    if tool_name == "figma_set_prototype_link":
        src_frame = args["source_frame"].replace("'", "\\'")
        src_node  = args["source_node"].replace("'", "\\'")
        dst_frame = args["target_frame"].replace("'", "\\'")
        return f"""
(async () => {{
  await figma.loadAllPagesAsync();
  var frames = {{}};
  for (var i = 0; i < figma.currentPage.children.length; i++) {{
    frames[figma.currentPage.children[i].name] = figma.currentPage.children[i];
  }}
  var srcFrame = frames['{src_frame}'];
  var dstFrame = frames['{dst_frame}'];
  if (!srcFrame) return JSON.stringify({{error: 'Source frame not found: {src_frame}'}});
  if (!dstFrame) return JSON.stringify({{error: 'Target frame not found: {dst_frame}'}});
  function findDeep(node, name) {{
    if (node.name === name) return node;
    if (node.children) {{
      for (var k = 0; k < node.children.length; k++) {{
        var found = findDeep(node.children[k], name);
        if (found) return found;
      }}
    }}
    return null;
  }}
  var node = findDeep(srcFrame, '{src_node}');
  if (!node) return JSON.stringify({{error: 'Source node not found anywhere in {src_frame}: {src_node}'}});
  await node.setReactionsAsync([{{
    trigger: {{type:'ON_CLICK'}},
    actions: [{{type:'NODE', destinationId:dstFrame.id, navigation:'NAVIGATE',
               transition:null, preserveScrollPosition:false}}]
  }}]);
  return JSON.stringify({{linked: true, from: '{src_node}', to: '{dst_frame}'}});
}})();
""".strip()

    if tool_name == "figma_create_auto_layout_frame":
        parent  = args.get("parent_frame", "").replace("'", "\\'")
        name    = args["name"].replace("'", "\\'")
        direction = args.get("direction", "HORIZONTAL")
        x, y    = args.get("x", 0), args.get("y", 0)
        w       = args.get("width", 0)
        h       = args.get("height", 0)
        spacing = args.get("item_spacing", 0)
        pad_h   = args.get("padding_h", 0)
        pad_v   = args.get("padding_v", 0)
        align_m = args.get("align_main", "MIN")
        align_c = args.get("align_cross", "CENTER")
        fill    = args.get("fill", "")
        radius  = args.get("corner_radius", 0)
        fill_js = ""
        if fill:
            rgb = _hex_to_rgb(fill)
            fill_js = f"f.fills = [{{type:'SOLID', color:{{r:{rgb['r']},g:{rgb['g']},b:{rgb['b']}}}}}];"
        else:
            fill_js = "f.fills = [];"
        # sizing: 0 means hug, otherwise fixed
        h_sizing = "FIXED" if w > 0 else "HUG"
        v_sizing = "FIXED" if h > 0 else "HUG"
        resize_js = f"f.resize({w}, {h});" if w > 0 and h > 0 else ""
        return f"""
(async () => {{
  var parent = null;
  if ('{parent}') {{
    for (var i = 0; i < figma.currentPage.children.length; i++) {{
      if (figma.currentPage.children[i].name === '{parent}') {{ parent = figma.currentPage.children[i]; break; }}
    }}
    if (!parent) return JSON.stringify({{error: 'Parent frame not found: {parent}'}});
  }}
  var f = figma.createFrame();
  f.name = '{name}';
  f.layoutMode = '{direction}';
  f.itemSpacing = {spacing};
  f.paddingLeft = {pad_h}; f.paddingRight = {pad_h};
  f.paddingTop = {pad_v}; f.paddingBottom = {pad_v};
  f.primaryAxisAlignItems = '{align_m}';
  f.counterAxisAlignItems = '{align_c}';
  f.primaryAxisSizingMode = '{h_sizing if direction == "HORIZONTAL" else v_sizing}';
  f.counterAxisSizingMode = '{v_sizing if direction == "HORIZONTAL" else h_sizing}';
  {resize_js}
  f.cornerRadius = {radius};
  {fill_js}
  f.x = {x}; f.y = {y};
  if (parent) parent.appendChild(f); else figma.currentPage.appendChild(f);
  return JSON.stringify({{id: f.id, name: f.name, created: true, layout: '{direction}'}});
}})();
""".strip()

    if tool_name == "figma_create_ellipse":
        fname = args["frame_name"].replace("'", "\\'")
        name  = args["name"].replace("'", "\\'")
        x, y  = args["x"], args["y"]
        w, h  = args["width"], args["height"]
        fill  = args.get("fill", _T_MUTED)
        rgb   = _hex_to_rgb(fill)
        return f"""
(async () => {{
  var frame = null;
  for (var i = 0; i < figma.currentPage.children.length; i++) {{
    if (figma.currentPage.children[i].name === '{fname}') {{ frame = figma.currentPage.children[i]; break; }}
  }}
  if (!frame) return JSON.stringify({{error: 'Frame not found: {fname}'}});
  var e = figma.createEllipse();
  e.name = '{name}';
  e.resize({w}, {h});
  e.x = {x}; e.y = {y};
  e.fills = [{{type:'SOLID', color:{{r:{rgb['r']},g:{rgb['g']},b:{rgb['b']}}}}}];
  frame.appendChild(e);
  return JSON.stringify({{id: e.id, name: e.name, created: true}});
}})();
""".strip()

    if tool_name == "figma_set_stroke":
        fname    = args["frame_name"].replace("'", "\\'")
        nname    = args["node_name"].replace("'", "\\'")
        color    = args.get("color", _T_BORDER)
        weight   = args.get("weight", 1)
        position = args.get("position", "CENTER")
        rgb      = _hex_to_rgb(color)
        return f"""
(async () => {{
  var frame = null;
  for (var i = 0; i < figma.currentPage.children.length; i++) {{
    if (figma.currentPage.children[i].name === '{fname}') {{ frame = figma.currentPage.children[i]; break; }}
  }}
  if (!frame) return JSON.stringify({{error: 'Frame not found: {fname}'}});
  function findDeep(node, name) {{
    if (node.name === name) return node;
    if (node.children) for (var k=0;k<node.children.length;k++) {{
      var f=findDeep(node.children[k],name); if(f) return f;
    }}
    return null;
  }}
  var node = findDeep(frame, '{nname}');
  if (!node) return JSON.stringify({{error: 'Node not found: {nname}'}});
  node.strokes = [{{type:'SOLID', color:{{r:{rgb['r']},g:{rgb['g']},b:{rgb['b']}}}}}];
  node.strokeWeight = {weight};
  node.strokeAlign = '{position}';
  return JSON.stringify({{updated: true, node: '{nname}', strokeWeight: {weight}}});
}})();
""".strip()

    if tool_name == "figma_add_overlay_link":
        src_frame   = args["source_frame"].replace("'", "\\'")
        src_node    = args["source_node"].replace("'", "\\'")
        overlay_frm = args["overlay_frame"].replace("'", "\\'")
        nav_type    = args.get("overlay_type", "OVERLAY")
        position    = args.get("position", "CENTER")
        return f"""
(async () => {{
  await figma.loadAllPagesAsync();
  var frames = {{}};
  for (var i = 0; i < figma.currentPage.children.length; i++) {{
    frames[figma.currentPage.children[i].name] = figma.currentPage.children[i];
  }}
  var srcFrame = frames['{src_frame}'];
  var ovlFrame = frames['{overlay_frm}'];
  if (!srcFrame) return JSON.stringify({{error: 'Source frame not found: {src_frame}'}});
  if (!ovlFrame) return JSON.stringify({{error: 'Overlay frame not found: {overlay_frm}'}});
  function findDeep(node, name) {{
    if (node.name === name) return node;
    if (node.children) for (var k=0;k<node.children.length;k++) {{
      var f=findDeep(node.children[k],name); if(f) return f;
    }}
    return null;
  }}
  var node = findDeep(srcFrame, '{src_node}');
  if (!node) return JSON.stringify({{error: 'Source node not found: {src_node}'}});
  // Calculate centered position for the overlay
  var centerX = Math.round((srcFrame.width  - ovlFrame.width)  / 2);
  var centerY = Math.round((srcFrame.height - ovlFrame.height) / 2);
  await node.setReactionsAsync([{{
    trigger: {{type:'ON_CLICK'}},
    actions: [{{
      type: 'NODE',
      destinationId: ovlFrame.id,
      navigation: '{nav_type}',
      transition: {{type:'DISSOLVE', easing:{{type:'LINEAR'}}, duration:0.2}},
      preserveScrollPosition: false,
      overlayRelativePosition: {{
        x: centerX > 0 ? centerX : 0,
        y: centerY > 0 ? centerY : 0
      }}
    }}]
  }}]);
  return JSON.stringify({{linked: true, type: '{nav_type}', from: '{src_node}', overlay: '{overlay_frm}'}});
}})();
""".strip()

    if tool_name == "figma_set_scrollable":
        fname     = args["frame_name"].replace("'", "\\'")
        direction = args.get("direction", "VERTICAL")
        clip      = str(args.get("clip_content", True)).lower()
        overflow_map = {
            "VERTICAL":   "SCROLLS",
            "HORIZONTAL": "SCROLLS",
            "BOTH":       "SCROLLS",
        }
        # Figma uses overflowDirection + scrollDirection separately
        scroll_dir_map = {
            "VERTICAL":   "VERTICAL",
            "HORIZONTAL": "HORIZONTAL",
            "BOTH":       "BOTH",
        }
        return f"""
(async () => {{
  var frame = null;
  for (var i = 0; i < figma.currentPage.children.length; i++) {{
    if (figma.currentPage.children[i].name === '{fname}') {{ frame = figma.currentPage.children[i]; break; }}
  }}
  if (!frame) return JSON.stringify({{error: 'Frame not found: {fname}'}});
  frame.overflowDirection = '{scroll_dir_map.get(direction, "VERTICAL")}';
  frame.clipsContent = {clip};
  return JSON.stringify({{updated: true, frame: '{fname}', scrollDirection: '{direction}'}});
}})();
""".strip()

    if tool_name == "figma_audit_frame":
        fname = args["frame_name"].replace("'", "\\'")
        return f"""
(async () => {{
  var frame = null;
  for (var i = 0; i < figma.currentPage.children.length; i++) {{
    if (figma.currentPage.children[i].name === '{fname}') {{ frame = figma.currentPage.children[i]; break; }}
  }}
  if (!frame) return JSON.stringify({{error: 'Frame not found: {fname}'}});

  function collectNodes(node, depth) {{
    var info = {{
      name: node.name,
      type: node.type,
      depth: depth,
      hasReactions: node.reactions && node.reactions.length > 0,
      reactionCount: node.reactions ? node.reactions.length : 0,
      children: []
    }};
    if (node.children) {{
      for (var i = 0; i < node.children.length; i++) {{
        info.children.push(collectNodes(node.children[i], depth + 1));
      }}
    }}
    return info;
  }}

  var tree = collectNodes(frame, 0);

  function flatten(node, results) {{
    results.push({{
      name: node.name, type: node.type, depth: node.depth,
      hasReactions: node.hasReactions, reactionCount: node.reactionCount
    }});
    for (var i = 0; i < node.children.length; i++) flatten(node.children[i], results);
    return results;
  }}
  var allNodes = flatten(tree, []);

  var frameName = '{fname}';

  // Self-tabs: tab-X-on-X where X matches the parent frame name — Figma CANNOT
  // self-navigate so these must never be flagged as unwired issues.
  function isSelfTab(nodeName, parentFrameName) {{
    var m = nodeName.match(/^tab-(.+)-on-(.+)$/);
    if (!m) return false;
    var target = m[1].replace(/\s/g,'').toLowerCase();
    var parent = m[2].replace(/\s/g,'').toLowerCase();
    var frame  = parentFrameName.replace(/\s/g,'').toLowerCase();
    return target === parent || target === frame;
  }}

  var tabNodes    = allNodes.filter(function(n) {{ return n.name.startsWith('tab-'); }});
  var wiredTabs   = tabNodes.filter(function(n) {{ return n.hasReactions; }});
  // Only flag tabs that: (a) are not self-tabs AND (b) have no reactions
  var unwiredTabs = tabNodes.filter(function(n) {{
    return !n.hasReactions && !isSelfTab(n.name, frameName);
  }});

  var hasNav    = allNodes.some(function(n) {{ return n.name.toLowerCase().includes('nav') || n.name.startsWith('tab-'); }});
  var hasHeader = allNodes.some(function(n) {{ return n.name.toLowerCase().includes('header'); }});

  // Buttons: flag ones with no reactions that are NOT self-tabs
  var allButtons = allNodes.filter(function(n) {{ return n.name.includes('-btn-'); }});
  var unwiredButtons = allButtons.filter(function(n) {{ return !n.hasReactions; }});

  // Classify unwired buttons by type to help the agent decide how to wire them
  var searchBtns = unwiredButtons.filter(function(n) {{ return n.name.startsWith('search-btn-'); }});
  var filterBtns = unwiredButtons.filter(function(n) {{ return n.name.startsWith('filter-btn-'); }});
  var otherBtns  = unwiredButtons.filter(function(n) {{
    return !n.name.startsWith('search-btn-') && !n.name.startsWith('filter-btn-');
  }});

  var issues = [];
  if (!hasHeader) issues.push('Missing header');
  if (!hasNav)    issues.push('Missing nav bar');
  if (unwiredTabs.length > 0)
    issues.push('Unwired nav tabs (need figma_set_prototype_link): ' + unwiredTabs.map(function(n){{return n.name;}}).join(', '));
  if (searchBtns.length > 0)
    issues.push('Unwired search buttons (need figma_add_overlay_link to search-results-modal): ' + searchBtns.map(function(n){{return n.name;}}).join(', '));
  if (filterBtns.length > 0)
    issues.push('Unwired filter buttons (need figma_add_overlay_link to filter-modal): ' + filterBtns.map(function(n){{return n.name;}}).join(', '));
  if (otherBtns.length > 0)
    issues.push('Unwired action buttons (wire to detail screen or create overlay): ' + otherBtns.map(function(n){{return n.name;}}).join(', '));

  return JSON.stringify({{
    frame: '{fname}',
    total_nodes: allNodes.length,
    has_header: hasHeader,
    has_nav: hasNav,
    tab_nodes: tabNodes.map(function(n){{return n.name;}}),
    wired_tabs: wiredTabs.map(function(n){{return n.name;}}),
    unwired_tabs: unwiredTabs.map(function(n){{return n.name;}}),
    unwired_search_btns: searchBtns.map(function(n){{return n.name;}}),
    unwired_filter_btns: filterBtns.map(function(n){{return n.name;}}),
    unwired_other_btns: otherBtns.map(function(n){{return n.name;}}),
    issues: issues,
    ok: issues.length === 0,
    note: 'Self-tabs (tab-X-on-X) are intentionally excluded — Figma cannot self-navigate'
  }});
}})();
""".strip()

    if tool_name == "figma_delete_frame":
        fname = args["frame_name"].replace("'", "\\'")
        return f"""
(async () => {{
  var deleted = [];
  for (var i = figma.currentPage.children.length - 1; i >= 0; i--) {{
    if (figma.currentPage.children[i].name === '{fname}') {{
      figma.currentPage.children[i].remove();
      deleted.push('{fname}');
    }}
  }}
  if (deleted.length === 0) return JSON.stringify({{deleted: false, note: 'Frame not found: {fname}'}});
  return JSON.stringify({{deleted: true, frame: '{fname}', count: deleted.length}});
}})();
""".strip()

    if tool_name == "figma_set_prototype_start":
        fname = args["frame_name"].replace("'", "\\'")
        return f"""
(async () => {{
  await figma.loadAllPagesAsync();
  var frame = null;
  for (var i = 0; i < figma.currentPage.children.length; i++) {{
    if (figma.currentPage.children[i].name === '{fname}') {{ frame = figma.currentPage.children[i]; break; }}
  }}
  if (!frame) return JSON.stringify({{error: 'Frame not found: {fname}'}});
  figma.currentPage.prototypeStartNode = frame;
  return JSON.stringify({{set: true, start_frame: '{fname}'}});
}})();
""".strip()

    if tool_name == "figma_create_button":
        fname   = args["frame_name"].replace("'", "\\'")
        name    = args["name"].replace("'", "\\'")
        label   = args["label"].replace("'", "\\'")
        x, y    = args["x"], args["y"]
        w, h    = args["width"], args["height"]
        fill    = args.get("fill",         _T_ACCENT)
        tcol    = args.get("text_color",   "#ffffff")
        fsize   = args.get("font_size",    _T_FS_BODY)
        bold    = args.get("bold",         False)
        radius  = args.get("corner_radius",_T_BTN_RADIUS)
        style   = "Bold" if bold else "Regular"
        rgb     = _hex_to_rgb(fill)
        trgb    = _hex_to_rgb(tcol)
        return f"""
(async () => {{
  await figma.loadFontAsync({{family:'{_T_FONT_BODY}', style:'{style}'}});
  function findDeep(node, name) {{
    if (node.name === name) return node;
    if (node.children) for (var k=0;k<node.children.length;k++) {{
      var f=findDeep(node.children[k],name); if(f) return f;
    }}
    return null;
  }}
  var parent = null;
  for (var i = 0; i < figma.currentPage.children.length; i++) {{
    if (figma.currentPage.children[i].name === '{fname}') {{ parent = figma.currentPage.children[i]; break; }}
    var deep = findDeep(figma.currentPage.children[i], '{fname}');
    if (deep) {{ parent = deep; break; }}
  }}
  if (!parent) return JSON.stringify({{error: 'Frame not found: {fname}'}});
  var btn = figma.createFrame();
  btn.name = '{name}';
  btn.resize({w}, {h});
  btn.x = {x}; btn.y = {y};
  btn.cornerRadius = {radius};
  btn.fills = [{{type:'SOLID', color:{{r:{rgb['r']},g:{rgb['g']},b:{rgb['b']}}}}}];
  btn.layoutMode = 'HORIZONTAL';
  btn.primaryAxisAlignItems = 'CENTER';
  btn.counterAxisAlignItems = 'CENTER';
  btn.primaryAxisSizingMode = 'FIXED';
  btn.counterAxisSizingMode = 'FIXED';
  var txt = figma.createText();
  txt.fontName = {{family:'{_T_FONT_BODY}', style:'{style}'}};
  txt.characters = '{label}';
  txt.fontSize = {fsize};
  txt.fills = [{{type:'SOLID', color:{{r:{trgb['r']},g:{trgb['g']},b:{trgb['b']}}}}}];
  btn.appendChild(txt);
  parent.appendChild(btn);
  return JSON.stringify({{id: btn.id, name: btn.name, created: true, type: 'button-frame'}});
}})();
""".strip()

    if tool_name == "figma_set_active_tab_style":
        fname    = args["frame_name"].replace("'", "\\'")
        tabname  = args["tab_node_name"].replace("'", "\\'")
        afill    = args.get("active_fill", _T_ACCENT)
        atxt     = args.get("active_text", "#ffffff")
        ifill    = args.get("inactive_fill", _T_SIDEBAR_BG)
        argb     = _hex_to_rgb(afill)
        atrgb    = _hex_to_rgb(atxt)
        irgb     = _hex_to_rgb(ifill)
        return f"""
(async () => {{
  var frame = null;
  for (var i = 0; i < figma.currentPage.children.length; i++) {{
    if (figma.currentPage.children[i].name === '{fname}') {{ frame = figma.currentPage.children[i]; break; }}
  }}
  if (!frame) return JSON.stringify({{error: 'Frame not found: {fname}'}});
  var updated = [];
  function findAll(node) {{
    if (node.name === '{tabname}') {{
      node.fills = [{{type:'SOLID', color:{{r:{argb['r']},g:{argb['g']},b:{argb['b']}}}}}];
      for (var c = 0; c < node.children.length; c++) {{
        if (node.children[c].type === 'TEXT') {{
          node.children[c].fills = [{{type:'SOLID', color:{{r:{atrgb['r']},g:{atrgb['g']},b:{atrgb['b']}}}}}];
        }}
      }}
      updated.push(node.name);
    }}
    if (node.children) {{
      for (var j = 0; j < node.children.length; j++) findAll(node.children[j]);
    }}
  }}
  findAll(frame);
  return JSON.stringify({{updated: updated, active_tab: '{tabname}'}});
}})();
""".strip()

    if tool_name == "figma_inspect_frame":
        fname = args["frame_name"].replace("'", "\\'")
        depth = args.get("depth", 3)
        return f"""
(async () => {{
  var frame = null;
  for (var i = 0; i < figma.currentPage.children.length; i++) {{
    if (figma.currentPage.children[i].name === '{fname}') {{ frame = figma.currentPage.children[i]; break; }}
  }}
  if (!frame) return JSON.stringify({{error: 'Frame not found: {fname}'}});

  function nodeInfo(node, d) {{
    var info = {{
      name: node.name,
      type: node.type,
      x: Math.round(node.x),
      y: Math.round(node.y),
      width:  node.width  ? Math.round(node.width)  : undefined,
      height: node.height ? Math.round(node.height) : undefined,
    }};
    if (node.fills && node.fills.length > 0 && node.fills[0].type === 'SOLID') {{
      var c = node.fills[0].color;
      info.fill = '#' + [c.r,c.g,c.b].map(function(v){{
        return ('0'+Math.round(v*255).toString(16)).slice(-2);
      }}).join('');
      info.opacity = node.fills[0].opacity !== undefined ? node.fills[0].opacity : 1;
    }}
    if (node.type === 'TEXT') {{
      info.text      = node.characters;
      info.fontSize  = node.fontSize;
      info.fontName  = node.fontName;
    }}
    if (node.cornerRadius !== undefined) info.cornerRadius = node.cornerRadius;
    if (d > 0 && node.children && node.children.length > 0) {{
      info.children = node.children.map(function(ch) {{ return nodeInfo(ch, d-1); }});
    }} else if (node.children) {{
      info.childCount = node.children.length;
    }}
    return info;
  }}

  return JSON.stringify(nodeInfo(frame, {depth}));
}})();
""".strip()

    if tool_name == "figma_update_node":
        fname     = args["frame_name"].replace("'", "\\'")
        nname     = args["node_name"].replace("'", "\\'")
        new_fill  = args.get("fill")
        new_text  = args.get("text")
        new_x     = args.get("x")
        new_y     = args.get("y")
        new_w     = args.get("width")
        new_h     = args.get("height")
        new_rad   = args.get("corner_radius")
        new_op    = args.get("opacity")
        new_fs    = args.get("font_size")

        # Build JS update statements for only the properties that were passed
        updates = []
        if new_fill is not None:
            rgb = _hex_to_rgb(new_fill)
            updates.append(f"node.fills = [{{type:'SOLID',color:{{r:{rgb['r']},g:{rgb['g']},b:{rgb['b']}}}}}];")
        if new_text is not None:
            safe_text = new_text.replace("'", "\\'").replace("\n", "\\n")
            updates.append(f"if (node.type==='TEXT') {{ await figma.loadFontAsync(node.fontName); node.characters = '{safe_text}'; }}")
        if new_x is not None:
            updates.append(f"node.x = {new_x};")
        if new_y is not None:
            updates.append(f"node.y = {new_y};")
        if new_w is not None or new_h is not None:
            w_expr = str(new_w) if new_w is not None else "node.width"
            h_expr = str(new_h) if new_h is not None else "node.height"
            updates.append(f"node.resize({w_expr}, {h_expr});")
        if new_rad is not None:
            updates.append(f"node.cornerRadius = {new_rad};")
        if new_op is not None:
            updates.append(f"node.opacity = {new_op};")
        if new_fs is not None:
            updates.append(f"if (node.type==='TEXT') {{ await figma.loadFontAsync(node.fontName); node.fontSize = {new_fs}; }}")

        update_js = "\n    ".join(updates) if updates else "/* nothing to update */"

        return f"""
(async () => {{
  function findDeep(node, name) {{
    if (node.name === name) return node;
    if (node.children) for (var k=0;k<node.children.length;k++) {{
      var f = findDeep(node.children[k], name); if (f) return f;
    }}
    return null;
  }}
  var frame = null;
  for (var i=0;i<figma.currentPage.children.length;i++) {{
    if (figma.currentPage.children[i].name==='{fname}') {{ frame=figma.currentPage.children[i]; break; }}
  }}
  if (!frame) return JSON.stringify({{error:'Frame not found: {fname}'}});
  var node = findDeep(frame, '{nname}');
  if (!node) return JSON.stringify({{error:'Node not found: {nname}'}});
  {update_js}
  return JSON.stringify({{updated:true, node:'{nname}', type:node.type}});
}})();
""".strip()

    if tool_name == "figma_execute_js":
        # Sanitize user JS: strip any existing IIFE wrapper so we don't double-wrap
        code = args["code"].strip()
        # Remove outer (async () => { ... })(); wrapper if the LLM sent one
        if code.startswith("(async") and code.endswith("();"):
            import re as _re
            # Unwrap: (async () => { BODY })();  →  BODY
            m = _re.match(r'^\(async\s*\(\)\s*=>\s*\{(.*)\}\s*\)\s*\(\s*\)\s*;?\s*$', code, _re.DOTALL)
            if m:
                code = m.group(1).strip()
        # Replace arrow functions in findOne/findAll with function() for compatibility
        # e.g. n => n.name === 'x'  →  function(n){ return n.name === 'x'; }
        import re as _re
        code = _re.sub(
            r'(\w+)\s*=>\s*([^{][^\n;,)]*)',
            r'function(\1){ return \2; }',
            code,
        )
        return f"""
(async () => {{
  try {{
    var _result = await (async () => {{
      {code}
    }})();
    return _result !== undefined ? String(_result) : JSON.stringify({{ok: true}});
  }} catch(e) {{
    return JSON.stringify({{error: e.message || String(e), stack: e.stack || ''}});
  }}
}})();
""".strip()

    if tool_name == "figma_create_chart":
        fname      = args["frame_name"].replace("'", "\\'")
        ctype      = args.get("chart_type", "bar").lower()
        title      = args.get("title", "").replace("'", "\\'")
        cx         = args.get("x", 264)
        cy         = args.get("y", 100)
        cw         = args.get("width", 800)
        ch         = args.get("height", 200)
        color      = args.get("color", _T_ACCENT)
        show_labels= str(args.get("show_labels", True)).lower()
        show_legend= str(args.get("show_legend", True)).lower()
        # Build data_points JSON
        import json as _json
        data_pts   = args.get("data_points", [])
        if not data_pts:
            data_pts = [{"label": "A", "value": 80}, {"label": "B", "value": 60},
                        {"label": "C", "value": 90}, {"label": "D", "value": 50}]
        colors_arr = args.get("colors", [
            _T_ACCENT, _T_SUCCESS, _T_WARNING, _T_DANGER,
            "#7C3AED", "#0891B2", "#D97706", "#059669",
        ])
        series     = args.get("series", [])
        g_min      = args.get("gauge_min", 0)
        g_max      = args.get("gauge_max", 100)
        g_val      = args.get("gauge_value", data_pts[0]["value"] if data_pts else 75)

        data_json   = _json.dumps(data_pts)
        colors_json = _json.dumps(colors_arr)
        series_json = _json.dumps(series)
        rgb         = _hex_to_rgb(color)

        return f"""
(async () => {{
  try {{
    // Find parent frame
    var parent = figma.currentPage.findOne(n => n.name === '{fname}' && n.type === 'FRAME');
    if (!parent) return JSON.stringify({{error: 'Frame not found: {fname}'}});

    var chartType  = '{ctype}';
    var title      = '{title}';
    var cx         = {cx}, cy = {cy}, cw = {cw}, ch = {ch};
    var showLabels = {show_labels};
    var showLegend = {show_legend};
    var dataPoints = {data_json};
    var seriesData = {series_json};
    var colorArr   = {colors_json};
    var accentHex  = '{color}';
    var gMin = {g_min}, gMax = {g_max}, gVal = {g_val};
    var created = [];

    function hexToRgb(hex) {{
      hex = hex.replace('#','');
      if (hex.length===3) hex = hex.split('').map(c=>c+c).join('');
      return {{r:parseInt(hex.slice(0,2),16)/255, g:parseInt(hex.slice(2,4),16)/255, b:parseInt(hex.slice(4,6),16)/255}};
    }}
    function solid(hex, opacity) {{
      var rgb = hexToRgb(hex);
      var p = {{type:'SOLID', color:rgb}};
      if (opacity !== undefined) p.opacity = opacity;
      return [p];
    }}
    function addText(txt, x, y, w, h, size, bold, hex, parent) {{
      var t = figma.createText();
      figma.loadFontAsync({{family:'Inter', style: bold ? 'Bold':'Regular'}}).then(()=>{{
        try {{ t.fontName = {{family:'Inter', style: bold ? 'Bold':'Regular'}}; }} catch(e) {{}}
        t.characters = String(txt);
        t.fontSize = size;
        t.fills = solid(hex || '#374151');
        t.resize(w, h);
        t.textAlignHorizontal = 'CENTER';
      }});
      t.x = x; t.y = y;
      parent.appendChild(t);
      return t;
    }}
    function makeRect(x, y, w, h, hex, opacity, parent) {{
      var r = figma.createRectangle();
      r.x=x; r.y=y; r.resize(Math.max(w,1), Math.max(h,1));
      r.fills = solid(hex || accentHex, opacity);
      parent.appendChild(r);
      created.push(r.id);
      return r;
    }}
    function makeEllipse(x, y, w, h, hex, parent) {{
      var e = figma.createEllipse();
      e.x=x; e.y=y; e.resize(w,h);
      e.fills = solid(hex || accentHex);
      parent.appendChild(e);
      created.push(e.id);
      return e;
    }}

    // Chart title
    var titleH = title ? 28 : 0;
    if (title) addText(title, cx, cy, cw, titleH, 14, true, '#132445', parent);

    var plotY  = cy + titleH + 8;
    var plotH  = ch - titleH - 8;

    // ── BAR CHART ────────────────────────────────────────────────────────────
    if (chartType === 'bar' || chartType === 'column') {{
      var useData = (seriesData.length > 0) ? null : dataPoints;
      var n       = useData ? useData.length : (dataPoints.length);
      var maxVal  = useData ? Math.max(...useData.map(d=>d.value)) : Math.max(...dataPoints.map(d=>d.value));
      if (seriesData.length > 0) {{
        // grouped bar
        var sn = seriesData.length;
        var groupW = cw / dataPoints.length;
        var barW = Math.max(8, (groupW - 16) / sn - 4);
        for (var gi=0; gi<dataPoints.length; gi++) {{
          var gx = cx + gi * groupW + 8;
          for (var si=0; si<sn; si++) {{
            var sv = seriesData[si].values ? seriesData[si].values[gi] : 0;
            var bh = Math.max(2, (sv / Math.max(...seriesData.map(s=>Math.max(...(s.values||[1]))))) * (plotH - 30));
            var bx = gx + si*(barW+4);
            var by = plotY + plotH - 24 - bh;
            makeRect(bx, by, barW, bh, colorArr[si % colorArr.length], undefined, parent);
          }}
          addText(dataPoints[gi].label, cx + gi*groupW, plotY+plotH-20, groupW, 16, 10, false, '#9CA3AF', parent);
        }}
        // legend
        if (showLegend) {{
          for (var li=0; li<sn; li++) {{
            makeRect(cx + li*120, plotY, 12, 12, colorArr[li%colorArr.length], undefined, parent);
            addText(seriesData[li].name||'', cx+li*120+16, plotY, 100, 14, 11, false, '#374151', parent);
          }}
        }}
      }} else {{
        var barW2 = Math.max(8, (cw / n) * 0.55);
        var barGap = (cw - n*barW2) / (n+1);
        for (var i=0; i<n; i++) {{
          var bh2 = Math.max(2, (useData[i].value / maxVal) * (plotH - 30));
          var bx2 = cx + barGap + i*(barW2+barGap);
          var by2 = plotY + plotH - 24 - bh2;
          makeRect(bx2, by2, barW2, bh2, colorArr[i % colorArr.length], undefined, parent);
          if (showLabels) addText(useData[i].value, bx2, by2-18, barW2, 16, 10, false, '#374151', parent);
          addText(useData[i].label, bx2, plotY+plotH-20, barW2, 16, 10, false, '#9CA3AF', parent);
        }}
      }}
      // x-axis line
      makeRect(cx, plotY+plotH-24, cw, 1, '#E5E7EB', undefined, parent);
    }}

    // ── HORIZONTAL BAR CHART ─────────────────────────────────────────────────
    if (chartType==='horizontal_bar') {{
      var n_h = dataPoints.length;
      var maxV_h = Math.max(...dataPoints.map(d=>d.value));
      var rowH = Math.max(16, (plotH - (n_h+1)*8) / n_h);
      var labelW = 120;
      var barAreaW = cw - labelW - 16;
      for (var i=0; i<n_h; i++) {{
        var ry = plotY + i*(rowH+8);
        var bw_h = Math.max(2, (dataPoints[i].value / maxV_h) * barAreaW);
        addText(dataPoints[i].label, cx, ry + rowH/2 - 7, labelW, 14, 11, false, '#374151', parent);
        makeRect(cx+labelW, ry, bw_h, rowH, colorArr[i % colorArr.length], undefined, parent);
        if (showLabels) addText(dataPoints[i].value, cx+labelW+bw_h+4, ry+rowH/2-7, 50, 14, 10, false, '#374151', parent);
      }}
      makeRect(cx+labelW, plotY, 1, plotH, '#E5E7EB', undefined, parent);
    }}

    // ── LINE / AREA / SPARKLINE — using SVG vector paths (local coords) ────────
    if (chartType==='line' || chartType==='area' || chartType==='sparkline') {{
      var n2 = dataPoints.length;
      if (n2 < 2) n2 = 2;
      var maxV2 = Math.max(...dataPoints.map(d=>d.value));
      var minV2 = Math.min(...dataPoints.map(d=>d.value));
      var xStep = cw / (n2 - 1);
      var isSpark = chartType==='sparkline';
      var axisOffset = isSpark ? 0 : 24;
      var plotInnerH = plotH - axisOffset - 8;

      // pts in LOCAL coordinates: origin = (cx, plotY)
      var pts = dataPoints.map(function(d,i) {{
        return {{
          lx: i * xStep,
          ly: plotH - axisOffset - Math.max(2, ((d.value - minV2) / (maxV2 - minV2 || 1)) * plotInnerH),
        }};
      }});

      // area fill — rectangles in frame coords (makeRect handles frame placement)
      if (chartType==='area') {{
        for (var i=0; i<pts.length; i++) {{
          var bh3 = (plotH - axisOffset) - pts[i].ly;
          makeRect(cx + pts[i].lx - xStep/2, plotY + pts[i].ly, xStep, Math.max(bh3,1), accentHex, 0.2, parent);
        }}
      }}

      // SVG polyline — path data in LOCAL coords, node positioned via x/y
      var pathData = 'M ' + pts[0].lx + ' ' + pts[0].ly;
      for (var i=1; i<pts.length; i++) {{
        pathData += ' L ' + pts[i].lx + ' ' + pts[i].ly;
      }}
      var vec = figma.createVector();
      vec.vectorPaths = [{{ windingRule: 'NONE', data: pathData }}];
      vec.strokes = [{{ type:'SOLID', color: hexToRgb(accentHex) }}];
      vec.strokeWeight = 2.5;
      vec.fills = [];
      vec.name = 'line-path';
      vec.x = cx;
      vec.y = plotY;
      parent.appendChild(vec); created.push(vec.id);

      // dots at each data point (frame coords)
      if (!isSpark) {{
        pts.forEach(function(p) {{ makeEllipse(cx+p.lx-5, plotY+p.ly-5, 10, 10, accentHex, parent); }});
      }}

      // x-axis labels + baseline
      if (!isSpark) {{
        dataPoints.forEach(function(d,i) {{
          addText(d.label, cx+i*xStep-24, plotY+plotH-20, 48, 16, 10, false, '#9CA3AF', parent);
        }});
        makeRect(cx, plotY+plotH-axisOffset, cw, 1, '#E5E7EB', undefined, parent);
      }}

      // ── MULTI-SERIES LINE: if seriesData present, draw one line per series ──
      if (seriesData.length > 0) {{
        // Compute global max across all series for consistent y scale
        var allVals = seriesData.flatMap(function(s) {{ return s.values || []; }});
        var msMax = Math.max(...allVals) || 1;
        var msMin = Math.min(...allVals);
        var msN   = dataPoints.length;
        var msStep = cw / (msN - 1 || 1);
        seriesData.forEach(function(series, si) {{
          var vals = series.values || [];
          if (vals.length < 2) return;
          var sColor = colorArr[si % colorArr.length];
          // Build path in local coords, node positioned via x/y
          var pd = 'M 0 ' + (plotH - axisOffset - Math.max(2, ((vals[0]-msMin)/(msMax-msMin||1)) * plotInnerH));
          for (var vi=1; vi<vals.length; vi++) {{
            var lx2 = vi * msStep;
            var ly2 = plotH - axisOffset - Math.max(2, ((vals[vi]-msMin)/(msMax-msMin||1)) * plotInnerH);
            pd += ' L ' + lx2 + ' ' + ly2;
          }}
          var sv = figma.createVector();
          sv.vectorPaths = [{{ windingRule:'NONE', data: pd }}];
          sv.strokes = [{{ type:'SOLID', color: hexToRgb(sColor) }}];
          sv.strokeWeight = 2;
          sv.fills = [];
          sv.name = 'line-' + (series.name || si);
          sv.x = cx; sv.y = plotY;
          parent.appendChild(sv); created.push(sv.id);
          // dot at last point
          var lastLx = (vals.length-1) * msStep;
          var lastLy = plotH - axisOffset - Math.max(2, ((vals[vals.length-1]-msMin)/(msMax-msMin||1)) * plotInnerH);
          makeEllipse(cx+lastLx-4, plotY+lastLy-4, 8, 8, sColor, parent);
        }});
        // legend for multi-series
        if (showLegend) {{
          seriesData.forEach(function(series, si) {{
            makeRect(cx + si*110, plotY, 10, 10, colorArr[si%colorArr.length], undefined, parent);
            addText(series.name||'', cx+si*110+14, plotY-1, 90, 14, 10, false, '#374151', parent);
          }});
        }}
      }}
    }}

    // ── SCATTER ──────────────────────────────────────────────────────────────
    if (chartType==='scatter') {{
      var maxV3 = Math.max(...dataPoints.map(d=>d.value));
      dataPoints.forEach(function(d,i) {{
        var px3 = cx + (i / (dataPoints.length-1||1)) * cw;
        var py3 = plotY + plotH - 24 - (d.value/maxV3)*(plotH-30);
        makeEllipse(px3-6, py3-6, 12, 12, colorArr[i % colorArr.length], parent);
        if (showLabels) addText(d.label, px3-20, py3+8, 40, 14, 10, false, '#9CA3AF', parent);
      }});
      makeRect(cx, plotY+plotH-24, cw, 1, '#E5E7EB', undefined, parent);
    }}

    // ── PIE / DONUT ──────────────────────────────────────────────────────────
    if (chartType==='pie' || chartType==='donut') {{
      var total = dataPoints.reduce(function(s,d){{return s+d.value;}}, 0);
      // Reserve bottom space for legend (placed below the chart)
      var legendH = showLegend ? Math.min(dataPoints.length * 24 + 8, 80) : 0;
      var chartAreaH = plotH - legendH;
      var r_outer = Math.min(cw * 0.6, chartAreaH) / 2 * 0.85;
      var ccx = cx + cw/2, ccy = plotY + chartAreaH/2;
      var cumAngle = -Math.PI/2;
      var innerR = chartType==='donut' ? 0.5 : 0;
      dataPoints.forEach(function(d, i) {{
        var sweep = (d.value / total) * 2 * Math.PI;
        var sl = figma.createEllipse();
        sl.resize(r_outer*2, r_outer*2);
        sl.x = ccx - r_outer; sl.y = ccy - r_outer;
        sl.arcData = {{startingAngle: cumAngle, endingAngle: cumAngle+sweep, innerRadius: innerR}};
        sl.fills = solid(colorArr[i % colorArr.length]);
        sl.name = 'slice-' + i;
        parent.appendChild(sl); created.push(sl.id);
        cumAngle += sweep;
      }});
      // legend — placed BELOW the donut, horizontal layout
      if (showLegend) {{
        var legY = plotY + chartAreaH + 8;
        var legX = cx + 16;
        var colW = Math.min(160, Math.floor(cw / Math.min(dataPoints.length, 3)));
        dataPoints.forEach(function(d, i) {{
          var col = i % 3;
          var row = Math.floor(i / 3);
          var lx = legX + col * colW;
          var ly = legY + row * 24;
          makeEllipse(lx, ly + 2, 10, 10, colorArr[i % colorArr.length], parent);
          addText(d.label, lx + 14, ly - 1, colW - 50, 16, 11, false, '#374151', parent);
          addText(Math.round(d.value/total*100) + '%', lx + colW - 48, ly - 1, 44, 16, 11, true, '#132445', parent);
        }});
      }}
    }}

    // ── GAUGE ────────────────────────────────────────────────────────────────
    if (chartType==='gauge') {{
      var pct = Math.max(0, Math.min(1, (gVal - gMin) / (gMax - gMin || 1)));
      var r_g = Math.min(cw*0.45, plotH*0.85);
      var gcx = cx + cw/2, gcy = plotY + plotH * 0.7;
      // background arc
      var bg = figma.createEllipse();
      bg.resize(r_g*2, r_g*2); bg.x=gcx-r_g; bg.y=gcy-r_g;
      bg.arcData={{startingAngle:Math.PI, endingAngle:2*Math.PI, innerRadius:0.6}};
      bg.fills=solid('#E5E7EB'); parent.appendChild(bg); created.push(bg.id);
      // value arc
      var fg = figma.createEllipse();
      fg.resize(r_g*2, r_g*2); fg.x=gcx-r_g; fg.y=gcy-r_g;
      fg.arcData={{startingAngle:Math.PI, endingAngle:Math.PI+pct*Math.PI, innerRadius:0.6}};
      fg.fills=solid(accentHex); parent.appendChild(fg); created.push(fg.id);
      // centre text
      addText(String(gVal), gcx-40, gcy-18, 80, 32, 22, true, '#132445', parent);
      addText(String(gMax), gcx+r_g*0.5, gcy+4, 40, 14, 10, false, '#9CA3AF', parent);
      addText(String(gMin), gcx-r_g*0.5-40, gcy+4, 40, 14, 10, false, '#9CA3AF', parent);
    }}

    return JSON.stringify({{created: true, chart_type: chartType, nodes: created.length}});
  }} catch(e) {{
    return JSON.stringify({{error: e.message || String(e)}});
  }}
}})();
""".strip()

    if tool_name == "figma_create_svg_node":
        svg_path = args["svg_path"]
        fname    = args["frame_name"].replace("'", "\\'")
        name     = args.get("name", "svg-node").replace("'", "\\'")
        nx       = args.get("x", 0)
        ny       = args.get("y", 0)
        nw       = args.get("width", 400)
        nh       = args.get("height", 300)

        try:
            svg_content = Path(svg_path).read_text(encoding="utf-8")
        except Exception as read_err:
            return f"""
(async () => {{
  return JSON.stringify({{error: 'Could not read SVG file: {str(read_err)[:120]}'}});
}})();
""".strip()

        # Escape backticks and backslashes so the SVG string is safe inside a JS template literal
        svg_escaped = svg_content.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")

        # Cap size — Figma's createNodeFromSvg can handle large SVGs but we guard against extreme cases
        if len(svg_escaped) > 600_000:
            return f"""
(async () => {{
  return JSON.stringify({{error: 'SVG too large for createNodeFromSvg ({len(svg_content):,} chars). Use figma_create_image_from_file instead.'}});
}})();
""".strip()

        return f"""
(async () => {{
  try {{
    var parent = figma.currentPage.findOne(n => n.name === '{fname}' && n.type === 'FRAME');
    if (!parent) return JSON.stringify({{error: 'Frame not found: {fname}'}});

    var svgString = `{svg_escaped}`;
    var node = figma.createNodeFromSvg(svgString);
    node.name = '{name}';
    node.x = {nx};
    node.y = {ny};
    node.resize({nw}, {nh});
    parent.appendChild(node);

    return JSON.stringify({{created: true, name: '{name}', x: {nx}, y: {ny}, width: {nw}, height: {nh}}});
  }} catch(e) {{
    return JSON.stringify({{error: e.message || String(e)}});
  }}
}})();
""".strip()

    if tool_name == "figma_create_table":
        import json as _json
        fname       = args["frame_name"].replace("'", "\\'")
        name        = args.get("name", "data-table").replace("'", "\\'")
        tx          = args.get("x", 264)
        ty          = args.get("y", 100)
        tw          = args.get("width", 900)
        columns     = args.get("columns", [])
        rows        = args.get("rows", [])
        row_h       = args.get("row_height", 40)
        hdr_h       = args.get("header_height", 44)
        hdr_bg      = args.get("header_bg", "#1E293B")
        hdr_txt     = args.get("header_text", "#F1F5F9")
        row_bg      = args.get("row_bg", "#0F172A")
        row_alt_bg  = args.get("row_alt_bg", "#1E293B")
        row_txt     = args.get("row_text", "#CBD5E1")
        accent_col  = args.get("accent_col", -1)
        accent_clr  = args.get("accent_color", "#6366F1")
        show_div    = str(args.get("show_row_dividers", True)).lower()

        cols_json = _json.dumps(columns)
        rows_json = _json.dumps(rows)

        return f"""
(async () => {{
  try {{
    var parent = figma.currentPage.findOne(n => n.name === '{fname}' && n.type === 'FRAME');
    if (!parent) return JSON.stringify({{error: 'Frame not found: {fname}'}});

    var columns    = {cols_json};
    var rows       = {rows_json};
    var tx = {tx}, ty = {ty}, tw = {tw};
    var rowH = {row_h}, hdrH = {hdr_h};
    var hdrBg = '{hdr_bg}', hdrTxt = '{hdr_txt}';
    var rowBg = '{row_bg}', rowAltBg = '{row_alt_bg}', rowTxt = '{row_txt}';
    var accentCol = {accent_col}, accentClr = '{accent_clr}';
    var showDividers = {show_div};

    function hexToRgb(hex) {{
      hex = hex.replace('#','');
      if (hex.length===3) hex = hex.split('').map(c=>c+c).join('');
      return {{r:parseInt(hex.slice(0,2),16)/255, g:parseInt(hex.slice(2,4),16)/255, b:parseInt(hex.slice(4,6),16)/255}};
    }}
    function solid(hex) {{ return [{{type:'SOLID', color:hexToRgb(hex)}}]; }}
    function addText(txt, x, y, w, h, size, bold, hex) {{
      var t = figma.createText();
      figma.loadFontAsync({{family:'Inter', style: bold ? 'Bold':'Regular'}}).then(()=>{{
        try {{
          t.fontName = {{family:'Inter', style: bold ? 'Bold':'Regular'}};
          t.characters = String(txt);
        }} catch(e) {{}}
        t.fontSize = size;
        t.fills = solid(hex);
        t.resize(Math.max(w-16, 20), h);
        t.textAlignVertical = 'CENTER';
      }});
      t.x = x + 8; t.y = y;
      parent.appendChild(t);
      return t;
    }}

    // Calculate column widths
    var totalColW = columns.reduce(function(s,c){{return s+(c.width||0);}},0);
    var colWidths = columns.map(function(c) {{
      return totalColW > 0 ? (c.width / totalColW) * tw : tw / columns.length;
    }});

    var created = [];

    // Header row
    var hdrRect = figma.createRectangle();
    hdrRect.x = tx; hdrRect.y = ty;
    hdrRect.resize(tw, hdrH);
    hdrRect.fills = solid(hdrBg);
    hdrRect.name = '{name}-header-bg';
    parent.appendChild(hdrRect); created.push(hdrRect.id);

    var colX = tx;
    columns.forEach(function(col, ci) {{
      var cw = colWidths[ci];
      addText(col.label || col, colX, ty, cw, hdrH, 12, true, hdrTxt);
      // column divider (skip last)
      if (ci < columns.length - 1) {{
        var div = figma.createRectangle();
        div.x = colX + cw - 1; div.y = ty;
        div.resize(1, hdrH + rows.length * rowH);
        div.fills = [{{type:'SOLID', color:hexToRgb(hdrBg), opacity:0.5}}];
        parent.appendChild(div);
      }}
      colX += cw;
    }});

    // Data rows
    rows.forEach(function(row, ri) {{
      var ry = ty + hdrH + ri * rowH;
      var bg = (ri % 2 === 0) ? rowBg : rowAltBg;
      var rowRect = figma.createRectangle();
      rowRect.x = tx; rowRect.y = ry;
      rowRect.resize(tw, rowH);
      rowRect.fills = solid(bg);
      rowRect.name = '{name}-row-' + ri;
      parent.appendChild(rowRect); created.push(rowRect.id);

      // Row divider
      if (showDividers && ri < rows.length - 1) {{
        var rdiv = figma.createRectangle();
        rdiv.x = tx; rdiv.y = ry + rowH - 1;
        rdiv.resize(tw, 1);
        rdiv.fills = [{{type:'SOLID', color:hexToRgb('#334155')}}];
        parent.appendChild(rdiv);
      }}

      var cellX = tx;
      row.forEach(function(cell, ci) {{
        var cw = colWidths[ci];
        var txtColor = (ci === accentCol) ? accentClr : rowTxt;
        addText(String(cell), cellX, ry, cw, rowH, 12, false, txtColor);
        cellX += cw;
      }});
    }});

    // Outer border
    var border = figma.createRectangle();
    border.x = tx; border.y = ty;
    border.resize(tw, hdrH + rows.length * rowH);
    border.fills = [];
    border.strokes = solid('#334155');
    border.strokeWeight = 1;
    border.name = '{name}-border';
    parent.appendChild(border);

    return JSON.stringify({{created: true, name: '{name}', rows: rows.length, cols: columns.length}});
  }} catch(e) {{
    return JSON.stringify({{error: e.message || String(e)}});
  }}
}})();
""".strip()

    if tool_name == "figma_create_image_from_file":
        import base64 as _b64
        import io

        fname       = args["frame_name"].replace("'", "\\'")
        file_path   = args["file_path"]
        name        = args.get("name", "image").replace("'", "\\'")
        ix          = args.get("x", 0)
        iy          = args.get("y", 0)
        iw          = args.get("width", 400)
        ih          = args.get("height", 300)
        scale_mode  = args.get("scale_mode", "FILL").upper()
        corner_r    = args.get("corner_radius", 0)

        try:
            from PIL import Image as _PILImage
            with open(file_path, "rb") as fh:
                raw = fh.read()
            # Normalise to PNG so Figma accepts it reliably
            img_obj = _PILImage.open(io.BytesIO(raw)).convert("RGBA")
            buf = io.BytesIO()
            img_obj.save(buf, format="PNG")
            img_b64 = _b64.b64encode(buf.getvalue()).decode("ascii")
        except Exception as img_err:
            return f"""
(async () => {{
  var parent = figma.currentPage.findOne(n => n.name === '{fname}' && n.type === 'FRAME');
  if (!parent) return JSON.stringify({{error:'Frame not found:{fname}'}});
  var r = figma.createRectangle();
  r.x={ix}; r.y={iy}; r.resize({iw},{ih});
  r.fills=[{{type:'SOLID',color:{{r:0.8,g:0.8,b:0.8}}}}];
  r.name='{name}';
  parent.appendChild(r);
  return JSON.stringify({{created:true,fallback:true,error:{repr(str(img_err)[:120])}}});
}})();
""".strip()

        corner_js = f"rect.cornerRadius = {corner_r};" if corner_r else ""
        return f"""
(async () => {{
  try {{
    var parent = figma.currentPage.findOne(n => n.name === '{fname}' && n.type === 'FRAME');
    if (!parent) return JSON.stringify({{error:'Frame not found:{fname}'}});
    var b64 = '{img_b64}';
    var binary = atob(b64);
    var bytes = new Uint8Array(binary.length);
    for (var i=0; i<binary.length; i++) bytes[i] = binary.charCodeAt(i);
    var imageHash = figma.createImage(bytes).hash;
    var rect = figma.createRectangle();
    rect.x = {ix}; rect.y = {iy};
    rect.resize({iw}, {ih});
    rect.name = '{name}';
    {corner_js}
    rect.fills = [{{type:'IMAGE', imageHash:imageHash, scaleMode:'{scale_mode}'}}];
    parent.appendChild(rect);
    return JSON.stringify({{created:true, name:'{name}', width:{iw}, height:{ih}}});
  }} catch(e) {{
    return JSON.stringify({{error: e.message || String(e)}});
  }}
}})();
""".strip()

    if tool_name == "figma_create_map":
        import urllib.request as _ureq
        import base64 as _b64
        import math as _math
        import io

        fname  = args["frame_name"].replace("'", "\\'")
        name   = args.get("name",   "map-image").replace("'", "\\'")
        mx     = args.get("x",      264)
        my     = args.get("y",      100)
        mw     = args.get("width",  600)
        mh     = args.get("height", 300)
        lat    = args.get("lat",    51.505)
        lon    = args.get("lon",   -0.09)
        zoom   = int(args.get("zoom", 12))
        style  = args.get("style", "osm")

        # Convert lat/lon/zoom to fractional tile coordinates (float, not int)
        def _deg2tile_f(lat_deg, lon_deg, z):
            lat_r = _math.radians(lat_deg)
            n = 2 ** z
            xtile_f = (lon_deg + 180.0) / 360.0 * n
            ytile_f = (1.0 - _math.asinh(_math.tan(lat_r)) / _math.pi) / 2.0 * n
            return xtile_f, ytile_f

        try:
            from PIL import Image as _PILImage
            n_tiles = 2 ** zoom

            # Exact fractional tile position of the requested lat/lon
            xtf, ytf = _deg2tile_f(lat, lon, zoom)

            # How many tiles we need to cover the requested pixel dimensions
            # Add 2 extra tiles on each axis so the crop always has enough pixels
            tiles_x = int(_math.ceil(mw / 256)) + 2
            tiles_y = int(_math.ceil(mh / 256)) + 2

            # Start tile: centre the grid on the fractional tile position
            start_x = int(_math.floor(xtf)) - tiles_x // 2
            start_y = int(_math.floor(ytf)) - tiles_y // 2

            # Pixel position of the lat/lon centre within the stitched canvas
            canvas_cx = (xtf - start_x) * 256
            canvas_cy = (ytf - start_y) * 256

            canvas = _PILImage.new("RGB", (tiles_x * 256, tiles_y * 256))
            base_url = "https://tile.openstreetmap.org" if style != "topo" else "https://tile.opentopomap.org"
            for tx in range(tiles_x):
                for ty in range(tiles_y):
                    tile_x = (start_x + tx) % n_tiles
                    tile_y = (start_y + ty) % n_tiles
                    # Clamp y tiles — no wrapping vertically in OSM
                    if tile_y < 0 or tile_y >= n_tiles:
                        continue
                    url = f"{base_url}/{zoom}/{tile_x}/{tile_y}.png"
                    try:
                        req = _ureq.Request(url, headers={"User-Agent": "TurboUIGen/1.0 (figma-mockup-generator)"})
                        with _ureq.urlopen(req, timeout=8) as resp:
                            tile_img = _PILImage.open(io.BytesIO(resp.read())).convert("RGB")
                        canvas.paste(tile_img, (tx * 256, ty * 256))
                    except Exception:
                        pass  # leave blank tile rather than failing the whole map

            # Crop centred on the exact lat/lon pixel position
            left   = max(0, int(canvas_cx - mw / 2))
            top    = max(0, int(canvas_cy - mh / 2))
            right  = left + mw
            bottom = top  + mh
            # Clamp to canvas bounds
            if right > canvas.width:
                right = canvas.width
                left  = max(0, right - mw)
            if bottom > canvas.height:
                bottom = canvas.height
                top    = max(0, bottom - mh)
            canvas = canvas.crop((left, top, right, bottom))
            # Pad to exact size if canvas was too small (e.g. at zoom=1)
            if canvas.width < mw or canvas.height < mh:
                padded = _PILImage.new("RGB", (mw, mh), (200, 210, 220))
                padded.paste(canvas, (0, 0))
                canvas = padded

            buf = io.BytesIO()
            canvas.save(buf, format="PNG")
            img_b64 = _b64.b64encode(buf.getvalue()).decode("ascii")
        except Exception as fetch_err:
            # Fallback: plain placeholder rectangle if fetch/PIL fails
            rgb = _hex_to_rgb("#CBD5E1")
            return f"""
(async () => {{
  var parent = figma.currentPage.findOne(n => n.name === '{fname}' && n.type === 'FRAME');
  if (!parent) return JSON.stringify({{error:'Frame not found:{fname}'}});
  var r = figma.createRectangle();
  r.x={mx}; r.y={my}; r.resize({mw},{mh});
  r.fills=[{{type:'SOLID',color:{{r:{rgb['r']},g:{rgb['g']},b:{rgb['b']}}}}}];
  r.name='{name}';
  parent.appendChild(r);
  var t = figma.createText();
  t.x={mx}; t.y={my + mh//2 - 10}; t.resize({mw},20);
  t.characters='Map — {name} (image unavailable)';
  t.textAlignHorizontal='CENTER';
  parent.appendChild(t);
  return JSON.stringify({{created:true, fallback:true, error:'{str(fetch_err)[:80]}'}});
}})();
""".strip()

        return f"""
(async () => {{
  try {{
    var parent = figma.currentPage.findOne(n => n.name === '{fname}' && n.type === 'FRAME');
    if (!parent) return JSON.stringify({{error:'Frame not found:{fname}'}});
    var b64 = '{img_b64}';
    var binary = atob(b64);
    var bytes = new Uint8Array(binary.length);
    for (var i=0; i<binary.length; i++) bytes[i] = binary.charCodeAt(i);
    var imageHash = figma.createImage(bytes).hash;
    var rect = figma.createRectangle();
    rect.x = {mx}; rect.y = {my};
    rect.resize({mw}, {mh});
    rect.name = '{name}';
    rect.fills = [{{type:'IMAGE', imageHash:imageHash, scaleMode:'FILL'}}];
    parent.appendChild(rect);
    return JSON.stringify({{created:true, name:'{name}', width:{mw}, height:{mh}}});
  }} catch(e) {{
    return JSON.stringify({{error: e.message || String(e)}});
  }}
}})();
""".strip()

    return f'(async () => {{ return JSON.stringify({{error: "Unknown tool: {tool_name}"}}) }})();'


# ── Relay communication ───────────────────────────────────────────────────────

_error_log_path = Path(__file__).parent / "figma_errors.log"


def _append_error_log(tool: str, error: str):
    """Persist every Figma error to figma_errors.log so they're never lost."""
    try:
        from datetime import datetime
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {tool}: {error}\n"
        with open(_error_log_path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


async def execute_in_figma(js_code: str, tool_name: str = "") -> dict:
    """Send JS to the relay → Figma Desktop Bridge → return result."""
    if _relay_ws is None:
        return {"error": "Relay not connected. Start relay.py on your local machine."}
    req_id = uuid.uuid4().hex
    fut = asyncio.get_event_loop().create_future()
    _pending[req_id] = fut

    # The generated JS already starts with (async () => { ... })();
    # We do NOT double-wrap it — we just pass it through as-is.
    # The try/catch is baked into each generated snippet by _build_js.
    msg = json.dumps({"type": "execute", "id": req_id, "code": js_code})
    await _relay_ws.send_text(msg)
    try:
        result = await asyncio.wait_for(fut, timeout=90.0)
        # Log errors returned by Figma
        if isinstance(result, dict) and "result" in result:
            inner = result["result"]
            if isinstance(inner, str) and '"error"' in inner:
                try:
                    parsed = json.loads(inner)
                    if "error" in parsed:
                        _append_error_log(tool_name, parsed["error"])
                        log.warning(f"Figma error in {tool_name}: {parsed['error']}")
                except Exception:
                    pass
        return result
    except asyncio.TimeoutError:
        _pending.pop(req_id, None)
        return {"error": "Figma execution timed out after 90s"}


# ── WebSocket endpoint for relay ──────────────────────────────────────────────

@app.websocket("/relay")
async def relay_endpoint(websocket: WebSocket):
    """relay.py connects here to bridge commands to Figma Desktop."""
    global _relay_ws
    await websocket.accept()
    _relay_ws = websocket
    log.info("Relay connected — Figma Desktop Bridge is available")
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            req_id = msg.get("id")
            if req_id and req_id in _pending:
                fut = _pending.pop(req_id)
                if not fut.done():
                    fut.set_result(msg.get("result", {}))
    except Exception as e:
        log.warning(f"Relay disconnected: {e}")
    finally:
        _relay_ws = None
        log.info("Relay disconnected")


# ── MCP JSON-RPC 2.0 endpoint ──────────────────────────────────────────────────

@app.post("/mcp")
async def mcp_post(request: Request):
    body = await request.json()
    method  = body.get("method", "")
    params  = body.get("params", {})
    req_id  = body.get("id")

    async def respond(result=None, error=None):
        resp = {"jsonrpc": "2.0", "id": req_id}
        if error:
            resp["error"] = {"code": -32000, "message": error}
        else:
            resp["result"] = result
        return JSONResponse(resp)

    # ── MCP handshake ──────────────────────────────────────────────────────────
    if method == "initialize":
        return await respond({
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "figma-mcp", "version": "1.6.0"},
        })

    if method == "notifications/initialized":
        return await respond({})

    # ── Tool discovery ─────────────────────────────────────────────────────────
    if method == "tools/list":
        return await respond({"tools": TOOLS})

    # ── Tool execution ─────────────────────────────────────────────────────────
    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        log.info(f"Tool call: {tool_name}({list(tool_args.keys())})")

        js = _build_js(tool_name, tool_args)
        figma_result = await execute_in_figma(js, tool_name=tool_name)

        # Parse the JSON string that the JS returns
        if isinstance(figma_result, dict) and "result" in figma_result:
            raw = figma_result["result"]
            try:
                parsed = json.loads(raw) if isinstance(raw, str) else raw
            except Exception:
                parsed = raw
        else:
            parsed = figma_result

        text = json.dumps(parsed, indent=2) if not isinstance(parsed, str) else parsed
        return await respond({
            "content": [{"type": "text", "text": text}],
            "isError": "error" in str(parsed).lower(),
        })

    return await respond(error=f"Unknown method: {method}")


# ── SSE streaming endpoint (for streaming MCP clients) ────────────────────────

@app.get("/mcp")
async def mcp_sse(request: Request):
    """SSE endpoint for streaming MCP — sends events as they arrive."""
    async def event_stream():
        yield "data: {\"type\": \"connected\"}\n\n"
        await asyncio.sleep(30)  # keep alive

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── Serve brand assets (logo accessible to Figma plugin via fetch) ────────────

@app.get("/brand/logo.png")
async def serve_logo():
    """Serve Mobility Global logo so Figma plugin can fetch it as image data."""
    from fastapi.responses import FileResponse as _FR
    logo_path = Path(__file__).resolve().parent.parent.parent.parent / \
                "branding" / "Mobility_Global_Logo.png"
    if logo_path.exists():
        return _FR(str(logo_path), media_type="image/png")
    return {"error": "Logo not found", "path": str(logo_path)}


# ── Health check ───────────────────────────────────────────────────────────────

@app.get("/")
async def health():
    return {
        "service": "Figma MCP Server",
        "relay_connected": _relay_ws is not None,
        "tools": len(TOOLS),
        "mcp_endpoint": "POST /mcp",
    }


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Figma MCP Server")
    parser.add_argument("--port", type=int, default=_DEFAULT_MCP_PORT)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()
    print(f"\n  Figma MCP Server starting on http://{args.host}:{args.port}")
    print(f"  MCP endpoint: POST http://localhost:{args.port}/mcp")
    print(f"  Relay endpoint: ws://localhost:{args.port}/relay")
    print(f"  Start relay.py on your laptop to connect Figma Desktop\n")
    uvicorn.run("server:app", host=args.host, port=args.port, reload=False)
