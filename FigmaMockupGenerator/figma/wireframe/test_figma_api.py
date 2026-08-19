#!/usr/bin/env python3
"""Quick tests for figma_to_web_using_api_agent.py — run before the full pipeline."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agents"))

from figma_to_web_using_api_agent import (
    parse_figma_url, get_top_frames, _figma_get,
    export_frame_screenshots, extract_prototype_links,
    format_wiring_for_prompt, slug, SCREENSHOTS_DIR,
)

FIGMA_URL = "https://www.figma.com/design/NXsuDdnpf31XBrXubDTm0T/SportsHub?node-id=0-1&t=NC8zjwgbKM2VqXvs-1"

file_key  = None
frames    = []
file_name = ""

# ── Test 1: Token ──────────────────────────────────────────────────────────────
print("\n[1] Testing Figma token...")
try:
    me = _figma_get("/me")
    print(f"    OK — logged in as: {me.get('email', me.get('handle', '?'))}")
except Exception as e:
    print(f"    FAIL: {e}")

# ── Test 2: Frame discovery ────────────────────────────────────────────────────
print("\n[2] Discovering frames...")
try:
    file_key, _ = parse_figma_url(FIGMA_URL)
    print(f"    File key: {file_key}")
    frames, file_name = get_top_frames(file_key)
    print(f"    File name: {file_name}")
    print(f"    Frames ({len(frames)}):")
    for f in frames:
        print(f"      [{f['page']}] {f['name']}  (id={f['id']})")
except Exception as e:
    print(f"    FAIL: {e}")

# ── Test 3: Prototype wiring extraction ───────────────────────────────────────
print("\n[3] Extracting prototype links (wiring)...")
wiring, all_links = {}, []
try:
    if file_key and frames:
        wiring, all_links = extract_prototype_links(file_key, frames)
        total = sum(len(v) for v in wiring.values())
        print(f"\n    Total links found: {total}")

        if total == 0:
            print("    NOTE: No prototype links found.")
            print("    This means either:")
            print("      a) The Figma frames have no ON_CLICK reactions wired yet")
            print("      b) The reactions are deeper than depth=5 in the node tree")
            print("      c) The reactions use a format not yet handled")
            print("    The app will still be generated — Claude will infer nav from screenshots.")
        else:
            print("\n    Wiring prompt text that Claude will receive:")
            print("    " + "-"*50)
            for line in format_wiring_for_prompt(wiring, all_links).splitlines():
                print(f"    {line}")
            print("    " + "-"*50)

        # Save wiring JSON for inspection
        import json as _json
        from figma_to_web_using_api_agent import SCREENSHOTS_DIR, slug
        wiring_path = SCREENSHOTS_DIR / f"{slug(file_name)}__wiring.json"
        wiring_path.write_text(
            _json.dumps({"wiring": wiring, "all_links": all_links}, indent=2),
            encoding="utf-8",
        )
        print(f"\n    Saved: {wiring_path}")
    else:
        print("    SKIP — frames not loaded (test 2 failed)")
except Exception as e:
    import traceback
    print(f"    FAIL: {e}")
    traceback.print_exc()

# ── Test 4: Screenshots ────────────────────────────────────────────────────────
print("\n[4] Exporting screenshots (REST API, no browser needed)...")
print(f"    Output folder: {SCREENSHOTS_DIR}")
try:
    if file_key and frames:
        project_slug = slug(file_name)
        screenshots = export_frame_screenshots(file_key, frames, project_slug, scale=1.5)
        print(f"\n    Saved {len(screenshots)} screenshot(s):")
        for s in screenshots:
            print(f"      {s['filename']}")
    else:
        print("    SKIP — frames not loaded")
except Exception as e:
    print(f"    FAIL: {e}")

print("\nAll tests done.\n")
