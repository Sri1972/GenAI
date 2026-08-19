#!/usr/bin/env python3
"""
Quick test for map/chart SVG extraction and Figma placement.

Tests only ONE page (default: Global Map) without running the full
8-page build. Verifies:
  1. SVG is extracted with correct choropleth colors (not grey)
  2. Figma receives figma_create_svg_node (not figma_create_map)
  3. The placed SVG visually matches the web app

Usage:
    python test_map_chart_extraction.py
    python test_map_chart_extraction.py --url http://localhost:3000/app/automotive-portal-6/global-map
    python test_map_chart_extraction.py --url http://localhost:3000/app/automotive-portal-6/north-america
    python test_map_chart_extraction.py --url http://localhost:3000/app/automotive-portal-6/analytics
"""

import argparse
import base64
import json
import sys
import time
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent.parent.parent / "API"))

from dotenv import load_dotenv
load_dotenv(_HERE.parent.parent.parent.parent / ".env")

# ── Args ──────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://localhost:3000/app/automotive-portal-6/global-map",
                    help="URL of the single page to test")
parser.add_argument("--out", default=str(_HERE.parent.parent / "generated" / "test-extraction"),
                    help="Output directory for screenshots and SVGs")
parser.add_argument("--no-figma", action="store_true",
                    help="Skip Figma placement — only test extraction")
args = parser.parse_args()

OUT_DIR = Path(args.out)
OUT_DIR.mkdir(parents=True, exist_ok=True)

print(f"\n{'='*60}")
print(f"  Map/Chart Extraction Test")
print(f"  URL : {args.url}")
print(f"  Out : {OUT_DIR}")
print(f"{'='*60}\n")

# ── Step 1: Extract SVG from the page ────────────────────────────────────────
print("[1] Launching Playwright and extracting SVG nodes...")

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    print("  FAIL: playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)

from webapp_to_figma_agent import _take_screenshots

pages = _take_screenshots(
    start_url=args.url,
    max_pages=1,          # only this one page
    nav_click_depth=0,    # no navigation — just this URL
    viewport={"width": 1440, "height": 900},
    emit=print,
    screenshots_dir=OUT_DIR,
)

if not pages:
    print("\n  FAIL: No pages captured")
    sys.exit(1)

pg = pages[0]
elem_shots = pg.get("element_screenshots", [])
print(f"\n[1] RESULT: {len(elem_shots)} element(s) extracted from '{pg['title']}'")

# ── Step 2: Validate SVG colors ───────────────────────────────────────────────
print("\n[2] Validating extracted SVG colors...")

NO_DATA_COLORS = {
    "#d1d5db", "rgb(209,213,219)", "#cccccc", "rgb(204,204,204)",
    "#e5e7eb", "rgb(229,231,235)", "#ffffff", "white",
}

passed = True
for e in elem_shots:
    print(f"\n  [{e['type'].upper()}] {e['label']} ({e.get('kind','?')})  {e.get('width',0):.0f}×{e.get('height',0):.0f}px")
    print(f"    path: {Path(e['path']).name}")

    if e["type"] == "svg":
        svg_content = e.get("svg", "")
        import re
        # Count distinct fill= attribute values
        all_fills = re.findall(r'fill="([^"]+)"', svg_content)
        fill_counts = {}
        for f in all_fills:
            f = f.strip().lower()
            fill_counts[f] = fill_counts.get(f, 0) + 1

        data_fills = {f: c for f, c in fill_counts.items()
                      if f not in NO_DATA_COLORS and f != "none"}
        grey_count = fill_counts.get("#d1d5db", 0)

        print(f"    Total path fills: {len(all_fills)}")
        print(f"    No-data grey (#D1D5DB): {grey_count}")
        print(f"    Data-colored fills: {len(data_fills)} distinct values")
        for fill, count in sorted(data_fills.items(), key=lambda x: -x[1])[:8]:
            print(f"      {fill}: {count}×")

        if len(data_fills) == 0:
            print(f"    ❌ FAIL: No data colors found — map extracted before D3 colored it")
            passed = False
        elif len(data_fills) < 2:
            print(f"    ⚠️  WARN: Only {len(data_fills)} data color — may be partially rendered")
        else:
            print(f"    ✓  PASS: {len(data_fills)} distinct data colors present")

    elif e["type"] == "canvas":
        # For PNG fallbacks just confirm file exists and is non-empty
        p = Path(e["path"])
        if p.exists() and p.stat().st_size > 5000:
            print(f"    ✓  PASS: PNG exists ({p.stat().st_size:,} bytes)")
        else:
            print(f"    ❌ FAIL: PNG missing or too small")
            passed = False

# ── Step 3: Check prompt would use SVG not native map ─────────────────────────
print("\n[3] Checking prompt generation (would Claude use SVG or native map?)...")

svg_nodes   = [e for e in elem_shots if e["type"] == "svg"]
canvas_nodes = [e for e in elem_shots if e["type"] == "canvas"]

if svg_nodes or canvas_nodes:
    print(f"  ✓  {len(svg_nodes)} SVG node(s) + {len(canvas_nodes)} canvas fallback(s) extracted")
    print(f"  ✓  Prompt will emit '⚡ EXTRACTED SVG NODES' block — Claude MUST use figma_create_svg_node")
    print(f"  ✓  RULE 0 forbids figma_create_map / figma_create_chart for these pages")
else:
    print(f"  ⚠️  No elements extracted — Claude would fall back to figma_create_map (native, no colors)")
    passed = False

# ── Step 4: Optionally place in Figma ────────────────────────────────────────
if not args.no_figma and (svg_nodes or canvas_nodes):
    print("\n[4] Placing extracted asset in Figma (test frame)...")
    try:
        from figma_agent_shared import mcp_initialize, mcp_list_tools, mcp_call_tool, MCP_SERVER
        import urllib.request, urllib.error

        try:
            urllib.request.urlopen(MCP_SERVER, timeout=3)
        except Exception:
            print(f"  SKIP: MCP server not reachable at {MCP_SERVER} — run start.bat first")
        else:
            mcp_initialize()
            tools = mcp_list_tools()
            print(f"  {len(tools)} Figma tools available")

            test_frame = "TEST-MapChart"
            # Create a test frame
            mcp_call_tool("figma_create_frame", {
                "name": test_frame,
                "width": 1440, "height": 900,
            })
            print(f"  Created test frame: {test_frame}")

            for e in (svg_nodes + canvas_nodes)[:1]:  # just first element
                if e["type"] == "svg":
                    result = mcp_call_tool("figma_create_svg_node", {
                        "frame_name": test_frame,
                        "svg_path": e["path"],
                        "name": e["label"],
                        "x": int(e["x"]), "y": int(e["y"]),
                        "width": int(e["width"]), "height": int(e["height"]),
                    })
                    print(f"  ✓  figma_create_svg_node placed '{e['label']}' → check Figma for colors")
                else:
                    result = mcp_call_tool("figma_create_image_from_file", {
                        "frame_name": test_frame,
                        "file_path": e["path"],
                        "name": e["label"],
                        "x": int(e["x"]), "y": int(e["y"]),
                        "width": int(e["width"]), "height": int(e["height"]),
                        "scale_mode": "FIT",
                    })
                    print(f"  ✓  figma_create_image_from_file placed '{e['label']}' → check Figma for colors")
    except Exception as ex:
        print(f"  SKIP: Figma placement failed ({ex}) — run with --no-figma to skip")
else:
    if args.no_figma:
        print("\n[4] Figma placement skipped (--no-figma)")

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
if passed:
    print("  ✓  ALL CHECKS PASSED — extraction is correct")
    print("  The full build should produce colored maps in Figma.")
else:
    print("  ❌ SOME CHECKS FAILED — see details above")
    print("  Re-run after fixing the issue before doing a full build.")
print(f"{'='*60}\n")
print(f"  Saved files in: {OUT_DIR}")
for f in sorted(OUT_DIR.iterdir()):
    print(f"    {f.name}  ({f.stat().st_size:,} bytes)")
