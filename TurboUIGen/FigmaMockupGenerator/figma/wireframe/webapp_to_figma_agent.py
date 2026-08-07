#!/usr/bin/env python3
"""
Web App → Figma Wireframe Agent
================================
Takes a live web app URL, screenshots every discoverable page with Playwright,
analyses the UI with Claude Vision, then builds a complete interactive Figma
prototype matching the app's structure and wiring.

Architecture:
    Web App URL
        ↓
    Playwright  (headless Chrome — screenshot every page)
        ↓
    Claude Vision  (analyse layout, components, navigation per page)
        ↓
    prompt_to_figma_agent logic  (same MCP tool-use loop)
        ↓  AWS Bedrock / Claude (tool_use)
        ↓  POST http://MCP_SERVER/mcp
    server.py  (Figma MCP)
        ↓  WebSocket relay
    relay.py → figma-console-mcp → Figma Desktop

Usage:
    python webapp_to_figma_agent.py "http://localhost:5174/app/automotive-portal-3/"
    python webapp_to_figma_agent.py --url "http://localhost:5174/app/automotive-portal-3/" --nav-clicks 5

Prerequisites:
    1. pip install playwright && playwright install chromium
    2. figma/mcp/start.bat running  (MCP server + relay)
    3. Figma Desktop open with Desktop Bridge plugin showing "Local Ready"
    4. Target web app running and accessible at the given URL
"""

import argparse
import base64
import json
import logging
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Callable, Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("webapp-to-figma")

# ── Shared infrastructure ──────────────────────────────────────────────────────
from figma_agent_shared import (
    MCP_SERVER, MODEL_ID, MAX_TOKENS,
    mcp_initialize, mcp_list_tools, mcp_call_tool,
    get_openai_client, tools_to_openai,
    _fetch_figma_url,
    SYSTEM_PROMPT,
    run_validation_pass,
    record_token_usage, _get_figma_run_id,
)

MAX_TURNS = 80  # web apps can have many pages; allow more turns


# ── Playwright screenshotter ────────────────────────────────────────────────────

def _auto_login(page, username: str, password: str, emit: Callable[[str], None]) -> bool:
    """
    Try to fill and submit a login form on the current page.
    Returns True if a login form was found and submitted.
    Uses JavaScript to fill fields so React controlled-component onChange fires.
    """
    try:
        # Check for a password input — that's the reliable login-page signal
        pwd_count = page.locator("input[type='password']").count()
        if pwd_count == 0:
            return False

        emit("  Login form detected — filling credentials via JS …")

        # Use JavaScript to set values and fire React's synthetic input event.
        # Plain page.fill() can silently time-out on React controlled inputs
        # that have no name/id attributes.
        filled = page.evaluate("""([user, pass]) => {
            const nativeSetter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value'
            ).set;

            // Find password field
            const pwdField = document.querySelector("input[type='password']");
            if (!pwdField) return {ok: false, reason: 'no password field'};

            // Find username field: prefer email, then text inputs before the password field
            let userField = document.querySelector("input[type='email']");
            if (!userField) {
                const all = Array.from(document.querySelectorAll("input[type='text'], input:not([type])"));
                userField = all[0] || null;
            }

            if (userField) {
                nativeSetter.call(userField, user);
                userField.dispatchEvent(new Event('input',  {bubbles: true}));
                userField.dispatchEvent(new Event('change', {bubbles: true}));
            }

            nativeSetter.call(pwdField, pass);
            pwdField.dispatchEvent(new Event('input',  {bubbles: true}));
            pwdField.dispatchEvent(new Event('change', {bubbles: true}));

            return {ok: true, hadUserField: !!userField};
        }""", [username, password])

        if not filled.get("ok"):
            emit(f"  ⚠ JS fill failed: {filled.get('reason')}")
            return False

        if filled.get("hadUserField"):
            emit("  Filled username + password via JS")
        else:
            emit("  ⚠ No username field found — filled password only")

        # Click the submit button (try several common patterns)
        submitted = False
        for sel in [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Sign In')",
            "button:has-text('Login')",
            "button:has-text('Log in')",
            "button:has-text('Sign in')",
            "button:has-text('Submit')",
            "button:has-text('Continue')",
        ]:
            locs = page.locator(sel)
            if locs.count() > 0:
                try:
                    locs.first.click(timeout=2_000)
                    submitted = True
                    emit(f"  Clicked submit button")
                    break
                except Exception:
                    continue

        if not submitted:
            # Fall back to pressing Enter on the password field
            page.locator("input[type='password']").first.press("Enter")
            emit("  Pressed Enter on password field")

        page.wait_for_load_state("networkidle", timeout=10_000)
        emit(f"  ✓ Login submitted → {page.url}")
        return True
    except Exception as exc:
        log.warning(f"Auto-login attempt failed: {exc}")
        return False


def _take_screenshots(
    start_url: str,
    max_pages: int = 12,
    nav_click_depth: int = 2,
    viewport: dict | None = None,
    emit: Callable[[str], None] = print,
    screenshots_dir: Optional[Path] = None,
    login_username: str = "",
    login_password: str = "",
    pages_cache: "list[dict] | None" = None,
) -> list[dict]:
    """
    Launch Playwright, navigate the app, click nav/tab links up to
    nav_click_depth levels deep, and return a list of:
        {"url": str, "title": str, "screenshot_b64": str, "nav_label": str,
         "screenshot_path": str | None}
    If screenshots_dir is provided, each PNG is also saved there as
    {index:02d}_{slug}.png.

    If pages_cache is provided (a list of page dicts from a prior discover run),
    BFS discovery and screenshotting are SKIPPED entirely. Only SVG re-extraction
    and interaction probing run, so fresh choropleth colors are captured without
    losing tab sub-pages or probe data from the discover session.
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        raise RuntimeError(
            "Playwright not installed. Run: pip install playwright && playwright install chromium"
        )

    if screenshots_dir is not None:
        screenshots_dir.mkdir(parents=True, exist_ok=True)

    vp = viewport or {"width": 1440, "height": 900}
    visited_urls: set[str] = set()
    pages_data: list[dict] = []

    def _normalise(url: str) -> str:
        return url.split("#")[0].rstrip("/")

    def _safe_slug(text: str) -> str:
        import re
        return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "page"

    # JS run inside the browser to inline computed styles and extract SVG nodes.
    # Returns a list of {label, svg, x, y, width, height, kind, is_canvas} objects.
    _SVG_EXTRACT_JS = r"""
() => {
  const SVG_SIZE_LIMIT = 400000; // 400 KB — skip overly complex SVGs

  const STYLE_PROPS = [
    'fill','stroke','stroke-width','stroke-dasharray','stroke-linecap','stroke-linejoin',
    'opacity','color','font-size','font-family','font-weight','font-style',
    'text-anchor','dominant-baseline','shape-rendering','vector-effect',
    'visibility','display','transform'
  ];

  function inlineStyles(svgEl) {
    // Walk every descendant and copy computed styles as inline attributes
    const all = svgEl.querySelectorAll('*');
    all.forEach(el => {
      const cs = window.getComputedStyle(el);
      let styleStr = '';
      STYLE_PROPS.forEach(p => {
        const v = cs.getPropertyValue(p);
        if (v && v !== 'none' && v !== 'normal' && v !== 'auto' && v !== '') {
          styleStr += p + ':' + v + ';';
        }
      });
      if (styleStr) el.setAttribute('style', styleStr);
    });
    // Stamp explicit pixel width/height on the root SVG so Figma renders it
    // at the correct size. Without this, 'width: 100%' causes Figma to stretch
    // the SVG to fill the entire frame, covering everything below it.
    //
    // IMPORTANT: Do NOT use getBoundingClientRect() here — it is unreliable when
    // overflow containers have been temporarily expanded for full-page screenshots.
    // Instead read dimensions from the SVG's own attributes/style, then fall back
    // to getBoundingClientRect() only as a last resort.
    function parsePx(v) {
      if (!v) return null;
      const n = parseFloat(v);
      return isNaN(n) ? null : n;
    }
    // 1. Prefer explicit width/height attributes (e.g. width="900" height="460")
    let pxW = parsePx(svgEl.getAttribute('width'));
    let pxH = parsePx(svgEl.getAttribute('height'));
    // 2. Fall back to inline style (e.g. style="width:100%;height:460px")
    if (!pxW || !pxH) {
      const st = svgEl.getAttribute('style') || '';
      const sw = st.match(/width\s*:\s*([\d.]+)px/i);
      const sh = st.match(/height\s*:\s*([\d.]+)px/i);
      if (!pxW && sw) pxW = parseFloat(sw[1]);
      if (!pxH && sh) pxH = parseFloat(sh[1]);
    }
    // 3. Fall back to viewBox (third/fourth values are intrinsic size)
    if (!pxW || !pxH) {
      const vb = (svgEl.getAttribute('viewBox') || '').trim().split(/[\s,]+/);
      if (vb.length === 4) {
        if (!pxW) pxW = parseFloat(vb[2]);
        if (!pxH) pxH = parseFloat(vb[3]);
      }
    }
    // 4. Last resort: live layout (only safe when overflow is in its normal state)
    if (!pxW || !pxH) {
      const bb = svgEl.getBoundingClientRect();
      if (!pxW) pxW = Math.round(bb.width);
      if (!pxH) pxH = Math.round(bb.height);
    }
    svgEl.setAttribute('width', Math.round(pxW));
    svgEl.setAttribute('height', Math.round(pxH));
    // Strip width/height from the style attribute so they don't override the
    // explicit attributes above (e.g. remove 'width:100%' that would re-stretch).
    const rootStyle = svgEl.getAttribute('style') || '';
    const cleanedStyle = rootStyle
      .replace(/width\s*:\s*[^;]+;?/gi, '')
      .replace(/height\s*:\s*[^;]+;?/gi, '')
      .trim().replace(/;+$/, '');
    if (cleanedStyle) {
      svgEl.setAttribute('style', cleanedStyle);
    } else {
      svgEl.removeAttribute('style');
    }
    return svgEl.outerHTML;
  }

  function labelFromEl(el) {
    // Try to derive a meaningful name from the element and its parents.
    // Ignore generic React root IDs ('root', 'app', 'main') — they would make
    // every SVG look the same and cause Claude to ignore the extracted content.
    const IGNORE_IDS = new Set(['root', 'app', 'main', 'content', 'wrapper', 'container']);
    for (let e = el; e && e !== document.body; e = e.parentElement) {
      const id = e.id;
      const cls = (e.className && typeof e.className === 'string') ? e.className : '';
      const idOk = id && !IGNORE_IDS.has(id.toLowerCase());
      const candidate = (idOk ? id : null) || cls.split(' ').find(c =>
        /chart|graph|map|plot|viz|visual|recharts|highcharts/i.test(c)
      );
      if (candidate) return candidate.replace(/[^a-z0-9-_]/gi, '-').slice(0, 40).toLowerCase();
    }
    return null;
  }

  function guessKind(svgEl) {
    // Identify whether this SVG is a chart, map, or other visual
    const parent = svgEl.parentElement;
    const ctx = ((parent && parent.id) || (parent && parent.className) || '').toLowerCase();
    if (/map|geo|globe|world/.test(ctx)) return 'map';
    const paths = svgEl.querySelectorAll('path');
    // Geographic paths have very long d attributes
    for (const p of paths) {
      if ((p.getAttribute('d') || '').length > 500) return 'map';
    }
    const rects = svgEl.querySelectorAll('rect');
    const circles = svgEl.querySelectorAll('circle');
    if (rects.length > 3) return 'chart-bar';
    if (circles.length > 3) return 'chart-scatter';
    if (paths.length > 0) return 'chart-line';
    return 'chart';
  }

  const results = [];
  const seen = new Set();

  document.querySelectorAll('svg').forEach((svg, idx) => {
    // Skip tiny decorative SVGs (icons etc.)
    const bb = svg.getBoundingClientRect();
    if (bb.width < 80 || bb.height < 80) return;
    // Skip if it's an icon inside a button/nav
    let p = svg.parentElement;
    while (p && p !== document.body) {
      if (['BUTTON','A','LI','NAV'].includes(p.tagName)) return;
      p = p.parentElement;
    }
    const key = Math.round(bb.left) + '_' + Math.round(bb.top) + '_' + Math.round(bb.width);
    if (seen.has(key)) return;
    seen.add(key);

    const inlined = inlineStyles(svg);
    const x = bb.left + window.scrollX;
    const y = bb.top + window.scrollY;
    const kind = guessKind(svg);
    const label = labelFromEl(svg) || (kind + '-' + idx);

    if (inlined.length > SVG_SIZE_LIMIT) {
      // SVG too large to inline (e.g. world/US map with thousands of paths).
      // Fall back to canvas-style element screenshot so the map still appears in Figma.
      results.push({ label, svg: null, x, y, width: bb.width, height: bb.height, kind, is_canvas: true, is_svg_fallback: true });
    } else {
      results.push({ label, svg: inlined, x, y, width: bb.width, height: bb.height, kind, is_canvas: false });
    }
  });

  // Canvas fallback — capture position info (screenshot taken Python-side)
  document.querySelectorAll('canvas').forEach((cv, idx) => {
    const bb = cv.getBoundingClientRect();
    if (bb.width < 80 || bb.height < 80) return;
    const key = 'canvas_' + Math.round(bb.left) + '_' + Math.round(bb.top);
    if (seen.has(key)) return;
    seen.add(key);
    const label = labelFromEl(cv) || ('canvas-' + idx);
    results.push({ label, svg: null, x: bb.left + window.scrollX, y: bb.top + window.scrollY,
                   width: bb.width, height: bb.height, kind: 'chart-canvas', is_canvas: true });
  });

  return results;
}
"""

    # JS that waits until map/chart SVGs have their data colors applied.
    #
    # The old check (any 2 colored fills on the page) fired immediately because
    # sidebar icon SVGs already have 2+ colored fills — it never waited for
    # D3 map country paths to be colored.
    #
    # D3 world maps also fetch GeoJSON via useEffect AFTER networkidle fires,
    # so networkidle alone doesn't guarantee the map has rendered.
    #
    # This version targets LARGE SVGs only and distinguishes:
    #   - Maps (>40 paths): requires 3+ distinct data-colored fills (choropleth)
    #   - Charts: requires 2+ distinct data-colored fills
    #   - Keeps polling if a large SVG with many paths has no data colors yet
    _WAIT_FOR_COLORS_JS = """
async () => {
  const MAX_WAIT = 12000;
  const POLL = 300;

  const NO_DATA = new Set([
    '#d1d5db','rgb(209,213,219)',
    '#cccccc','rgb(204,204,204)',
    '#c8c8c8','rgb(200,200,200)',
    '#e5e7eb','rgb(229,231,235)',
    '#e3eaf2','rgb(227,234,242)',
    '#ffffff','white','rgb(255,255,255)',
    'none','transparent',''
  ]);

  const isData = (f) => {
    if (!f) return false;
    return !NO_DATA.has(f.toLowerCase().replace(/\\s+/g,''));
  };

  const start = Date.now();
  while (Date.now() - start < MAX_WAIT) {
    const largeSvgs = Array.from(document.querySelectorAll('svg')).filter(s => {
      const b = s.getBoundingClientRect();
      return b.width > 200 && b.height > 150;
    });

    // If no large SVG found yet, keep waiting up to 3s then give up
    if (largeSvgs.length === 0) {
      if (Date.now() - start > 3000) return false;
      await new Promise(r => setTimeout(r, POLL));
      continue;
    }

    let anyMapStillLoading = false;
    for (const svg of largeSvgs) {
      const paths = svg.querySelectorAll('path');
      if (paths.length >= 40) {
        // Likely a D3 map — need 3+ distinct data fills among country paths
        const fills = new Set();
        for (const p of paths) {
          if (isData(p.getAttribute('fill') || '')) fills.add(p.getAttribute('fill'));
          if (fills.size >= 3) return true;  // choropleth colors applied
        }
        // Map SVG exists but no data colors yet — still loading
        anyMapStillLoading = true;
        continue;
      }
      // Smaller SVG (chart) — need 2+ distinct data fills
      const fills = new Set();
      for (const el of svg.querySelectorAll('path,rect,circle')) {
        const f = el.getAttribute('fill') || window.getComputedStyle(el).fill || '';
        if (isData(f)) fills.add(f);
        if (fills.size >= 2) return true;
      }
    }

    // If only charts with no colors (no maps), give up after 3s
    if (!anyMapStillLoading && Date.now() - start > 3000) return false;

    await new Promise(r => setTimeout(r, POLL));
  }
  return false;
}
"""

    def _extract_svg_nodes(page, label: str, index: int) -> list[dict]:
        """
        Extract SVG chart/map nodes from the live page via CSS inlining.
        Returns a list of dicts ready to pass to figma_create_svg_node or figma_create_image_from_file.
        """
        extracted = []
        if screenshots_dir is None:
            return extracted
        # Wait for Highcharts/D3 to finish applying color scales before extracting SVG
        try:
            colored = page.evaluate(_WAIT_FOR_COLORS_JS)
            if not colored:
                emit(f"    [SVG] color wait timed out — extracting anyway")
        except Exception:
            pass
        try:
            nodes = page.evaluate(_SVG_EXTRACT_JS)
        except Exception as e:
            emit(f"    [SVG] extract failed: {e}")
            return extracted

        for i, node in enumerate(nodes or []):
            kind  = node.get("kind", "chart")
            lbl   = node.get("label", f"{kind}-{i}")
            x, y  = node.get("x", 0), node.get("y", 0)
            w, h  = node.get("width", 0), node.get("height", 0)

            if node.get("is_canvas"):
                is_svg_fallback = node.get("is_svg_fallback", False)
                if is_svg_fallback:
                    # SVG was too large to inline — screenshot the SVG element directly by position
                    try:
                        svg_els = page.query_selector_all("svg")
                        for sv in svg_els:
                            bb = sv.bounding_box()
                            if bb and abs(bb["x"] - x) < 5 and abs(bb["y"] - y) < 5:
                                png = sv.screenshot()
                                fname = f"{index:02d}_{_safe_slug(label)}_{lbl}_map.png"
                                dest = screenshots_dir / fname
                                dest.write_bytes(png)
                                b64 = base64.b64encode(png).decode()
                                extracted.append({
                                    "type": "canvas", "kind": kind, "label": lbl,
                                    "path": str(dest), "b64": b64,
                                    "x": x, "y": y, "width": int(w), "height": int(h),
                                })
                                emit(f"    [MAP-IMG] {lbl} → {dest.name} ({int(w)}×{int(h)}px)")
                                break
                    except Exception as e:
                        emit(f"    [MAP-IMG] element screenshot failed for {lbl}: {e}")
                else:
                    # Canvas fallback — take element screenshot
                    try:
                        canvas_els = page.query_selector_all("canvas")
                        for cv in canvas_els:
                            bb = cv.bounding_box()
                            if bb and abs(bb["x"] - x) < 5 and abs(bb["y"] - y) < 5:
                                png = cv.screenshot()
                                fname = f"{index:02d}_{_safe_slug(label)}_{lbl}_canvas.png"
                                dest = screenshots_dir / fname
                                dest.write_bytes(png)
                                b64 = base64.b64encode(png).decode()
                                extracted.append({
                                    "type": "canvas", "kind": kind, "label": lbl,
                                    "path": str(dest), "b64": b64,
                                    "x": x, "y": y, "width": int(w), "height": int(h),
                                })
                                emit(f"    [CANVAS] {lbl} → {dest.name} ({int(w)}×{int(h)}px)")
                                break
                    except Exception:
                        pass
            else:
                # SVG node — save to file and store inline SVG string
                svg_str = node.get("svg", "")
                if not svg_str:
                    continue
                fname = f"{index:02d}_{_safe_slug(label)}_{lbl}.svg"
                dest = screenshots_dir / fname
                dest.write_text(svg_str, encoding="utf-8")
                extracted.append({
                    "type": "svg", "kind": kind, "label": lbl,
                    "svg": svg_str, "path": str(dest),
                    "x": x, "y": y, "width": int(w), "height": int(h),
                })
                emit(f"    [SVG] {lbl} ({kind}) → {dest.name} ({int(w)}×{int(h)}px, {len(svg_str):,} chars)")

        return extracted

    def _wait_for_loaded(page):
        """Wait for network to settle, then wait for loading indicators to disappear."""
        # First networkidle — catches initial bundle + data fetches
        try:
            page.wait_for_load_state("networkidle", timeout=8_000)
        except Exception:
            pass
        # Wait for any loading indicators triggered by data fetches
        LOADING_SELECTORS = [
            "text=Loading...",
            "text=Loading",
            "text=Loading map",
            "[class*='loading']:visible",
            "[class*='spinner']:visible",
            "[class*='skeleton']:visible",
        ]
        for sel in LOADING_SELECTORS:
            try:
                page.wait_for_selector(sel, state="hidden", timeout=8_000)
            except Exception:
                pass
        # Second networkidle — D3 maps fetch GeoJSON in a useEffect that fires AFTER
        # the first networkidle (React renders, then effect runs, then fetch starts).
        # Waiting again catches that secondary network request.
        try:
            page.wait_for_load_state("networkidle", timeout=10_000)
        except Exception:
            pass
        # Extra pause for D3 projection + color scale application after data arrives
        time.sleep(2.0)

    # JS that expands all overflow-auto/hidden/scroll containers to their full
    # scroll height before a full_page screenshot, then restores them.
    # Needed because the app uses a fixed-height <main overflow-auto> sidebar layout —
    # the browser document never grows beyond the viewport, so full_page=True alone
    # only captures 900px. This makes ALL content visible to Playwright.
    _EXPAND_OVERFLOW_JS = """
() => {
  const els = document.querySelectorAll('*');
  const saved = [];
  for (const el of els) {
    const cs = window.getComputedStyle(el);
    const ov = cs.overflow + '|' + cs.overflowY;
    if (/auto|scroll|hidden/.test(ov)) {
      saved.push([el, el.style.overflow, el.style.overflowY,
                  el.style.height, el.style.maxHeight]);
      el.style.overflow  = 'visible';
      el.style.overflowY = 'visible';
      el.style.height    = 'auto';
      el.style.maxHeight = 'none';
    }
  }
  return saved.length;
}
"""
    _RESTORE_OVERFLOW_JS = """
(saved) => {
  // saved is not passed back — just undo all inline overrides we set
  const els = document.querySelectorAll('*');
  for (const el of els) {
    if (el.style.overflowY === 'visible') {
      el.style.removeProperty('overflow');
      el.style.removeProperty('overflow-y');
      el.style.removeProperty('height');
      el.style.removeProperty('max-height');
    }
  }
}
"""

    def _screenshot_b64(page, label: str, index: int) -> tuple[str, Optional[str], int, int]:
        _wait_for_loaded(page)
        # Expand overflow-auto/scroll containers so full_page=True captures
        # content that lives in inner-scrolling divs (e.g. data table below map).
        try:
            n = page.evaluate(_EXPAND_OVERFLOW_JS)
            emit(f"    [EXPAND] unlocked {n} overflow container(s) for full-page capture")
        except Exception:
            pass
        png_bytes = page.screenshot(full_page=True)
        # Restore overflow so subsequent SVG extraction uses correct element positions
        try:
            page.evaluate(_RESTORE_OVERFLOW_JS)
        except Exception:
            pass
        b64 = base64.b64encode(png_bytes).decode()
        # Decode PNG header to get actual pixel dimensions (bytes 16-24 of IHDR chunk)
        import struct
        png_w = struct.unpack(">I", png_bytes[16:20])[0]
        png_h = struct.unpack(">I", png_bytes[20:24])[0]
        saved_path = None
        if screenshots_dir is not None:
            filename = f"{index:02d}_{_safe_slug(label)}.png"
            dest = screenshots_dir / filename
            dest.write_bytes(png_bytes)
            saved_path = str(dest)
            emit(f"    Saved screenshot → {dest.name}  ({png_w}×{png_h}px)")
        return b64, saved_path, png_w, png_h

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(viewport=vp)
        page = ctx.new_page()

        emit(f"[BROWSER] Opening {start_url}")
        try:
            page.goto(start_url, wait_until="networkidle", timeout=30_000)
        except PWTimeout:
            page.goto(start_url, wait_until="domcontentloaded", timeout=30_000)
        time.sleep(3.0)  # allow chart/map libraries to finish their render cycle

        # Auto-login if credentials provided
        if login_username or login_password:
            emit(f"[LOGIN] Signing in as '{login_username}'…")
            if _auto_login(page, login_username, login_password, emit):
                time.sleep(1.5)
            else:
                emit("[LOGIN] No login form found — continuing without login")

        # Use the post-login URL as the "home" to return to between nav clicks
        landing_url = page.url
        landing_origin = landing_url.split("/")[0] + "//" + landing_url.split("/")[2]

        base_norm = _normalise(landing_url)
        visited_urls.add(base_norm)

        # seen_labels is shared between in-page tab discovery and nav BFS
        seen_labels: set[str] = set()

        def _capture_in_page_tabs(pg, page_label: str, page_index_base: int) -> list[dict]:
            """
            Find and screenshot every in-page tab panel.
            Detects two patterns:
              1. [role=tab] elements (proper ARIA tabs)
              2. Buttons in a flex container with a bottom border (custom tab bar, e.g. D3 chart pages)
            Returns list of page dicts. Restores the first tab before returning.
            """
            tab_pages = []
            try:
                # Use JS to detect both ARIA tabs and custom button-group tab bars.
                # Returns [{text, x, y}] — coordinates for mouse.click().
                clickable_tabs = pg.evaluate(r"""
() => {
  // Strategy 1: proper ARIA [role=tab] elements
  const ariaEls = Array.from(document.querySelectorAll('[role="tab"]')).filter(el => {
    const href = el.getAttribute('href') || '';
    const text = (el.innerText || el.textContent || '').trim();
    return text && !href.startsWith('http');
  });
  if (ariaEls.length > 1) {
    return ariaEls.map(el => {
      const bb = el.getBoundingClientRect();
      return { text: (el.innerText || '').trim(), x: bb.x + bb.width / 2, y: bb.y + bb.height / 2 };
    });
  }

  // Strategy 2: buttons in a flex container with a bottom border (custom tab bar)
  const allBtns = Array.from(document.querySelectorAll('button'));
  const parentMap = new Map();
  for (const btn of allBtns) {
    const text = (btn.innerText || '').trim();
    if (!text || text.length > 100) continue;
    const par = btn.parentElement;
    if (!par) continue;
    const ps = window.getComputedStyle(par);
    if (ps.display === 'flex' || ps.display === 'inline-flex') {
      if (!parentMap.has(par)) parentMap.set(par, []);
      parentMap.get(par).push(btn);
    }
  }
  for (const [par, btns] of parentMap) {
    if (btns.length < 2) continue;
    const ps = window.getComputedStyle(par);
    const parHasBorder = ps.borderBottomStyle !== 'none' && ps.borderBottomWidth !== '0px';
    const btnHasBorder = btns.some(b => {
      const bs = window.getComputedStyle(b);
      return bs.borderBottomStyle !== 'none' && bs.borderBottomWidth !== '0px';
    });
    if (parHasBorder || btnHasBorder) {
      return btns.map(btn => {
        const bb = btn.getBoundingClientRect();
        return { text: (btn.innerText || '').trim(), x: bb.x + bb.width / 2, y: bb.y + bb.height / 2 };
      }).filter(t => t.text);
    }
  }
  return [];
}
""")

                if not clickable_tabs or len(clickable_tabs) <= 1:
                    return tab_pages

                emit(f"[TABS] Found {len(clickable_tabs)} in-page tabs on '{page_label}'")

                for ti, tab_info in enumerate(clickable_tabs[1:], start=1):
                    tab_text = tab_info["text"]
                    tab_label = f"{page_label} — {tab_text}"
                    if tab_label in seen_labels:
                        continue
                    seen_labels.add(tab_label)
                    try:
                        pg.mouse.click(tab_info["x"], tab_info["y"])
                        try:
                            pg.wait_for_load_state("networkidle", timeout=5_000)
                        except Exception:
                            pass
                        time.sleep(1.5)  # allow chart/map libraries to finish their render cycle
                        idx = page_index_base + ti
                        emit(f"[TAB] [{idx}] {tab_label}")
                        elem_shots = _extract_svg_nodes(pg, tab_label, idx)
                        b64, saved, png_w, png_h = _screenshot_b64(pg, tab_label, idx)
                        tab_pages.append({
                            "url": pg.url,
                            "title": tab_label,
                            "screenshot_b64": b64,
                            "screenshot_path": saved,
                            "screenshot_width": png_w,
                            "screenshot_height": png_h,
                            "element_screenshots": elem_shots,
                            "nav_label": tab_label,
                            "is_tab_panel": True,
                        })
                    except Exception as e:
                        emit(f"    [TAB] click failed for '{tab_text}': {e}")

                # Restore first tab
                try:
                    first = clickable_tabs[0]
                    pg.mouse.click(first["x"], first["y"])
                    time.sleep(0.5)
                except Exception:
                    pass

            except Exception as e:
                emit(f"    [TABS] discovery failed: {e}")
            return tab_pages

        def _capture_button_responses(pg, page_label: str, page_index_base: int) -> list[dict]:
            """
            Detect flex-col button groups and capture every response-generating combination.

            Algorithm:
            1. Collect all flex-col containers that have 2+ direct <button> children.
            2. Classify each group by clicking its first button and measuring DOM growth:
               - DOM grew >= 100 chars → prompt group (generates a response)
               - DOM didn't grow → selector group (switches state, e.g. personas)
            3. Build the full matrix: for each selector × each prompt, reload, activate
               selector, click prompt, wait for response, screenshot.
            """
            response_pages = []
            base_url = pg.url

            def _dom_text_length(p):
                try:
                    return p.evaluate("() => document.body.innerText.length")
                except Exception:
                    return 0

            def _find_btn_coords_local(p, text):
                return p.evaluate(f"""
() => {{
  const text = {repr(text)};
  for (const btn of document.querySelectorAll('button')) {{
    if ((btn.innerText || '').trim() === text) {{
      const bb = btn.getBoundingClientRect();
      if (bb.width > 0 && bb.height > 0) return {{ x: bb.x + bb.width/2, y: bb.y + bb.height/2 }};
    }}
  }}
  return null;
}}
""")

            try:
                # Collect all flex-col direct-child button groups
                btn_groups = pg.evaluate(r"""
() => {
  const groups = [];
  const seenPar = new Set();
  for (const btn of document.querySelectorAll('button')) {
    const par = btn.parentElement;
    if (!par || seenPar.has(par)) continue;
    const ps = window.getComputedStyle(par);
    if ((ps.display === 'flex' || ps.display === 'inline-flex') && ps.flexDirection === 'column') {
      seenPar.add(par);
      const btns = Array.from(par.querySelectorAll(':scope > button')).map(b => {
        const t = (b.innerText || '').trim();
        const bb = b.getBoundingClientRect();
        return (t && bb.width > 0 && bb.height > 0) ? { text: t, x: bb.x + bb.width/2, y: bb.y + bb.height/2 } : null;
      }).filter(Boolean);
      if (btns.length >= 2) groups.push(btns);
    }
  }
  return groups;
}
""")
                if not btn_groups:
                    return response_pages

                # ----- NEW: per-selector × per-prompt matrix -----
                # Classify each group: prompt groups grow DOM, selector groups don't.
                # We already tested the first button of each group; use the results.
                # Re-test properly: reload, click first btn in group, measure DOM delta.
                prompt_groups = []
                selector_groups = []

                for grp in btn_groups:
                    pg.goto(base_url, wait_until="networkidle", timeout=15_000)
                    _wait_for_loaded(pg)
                    before = _dom_text_length(pg)
                    coords = _find_btn_coords_local(pg, grp[0]["text"])
                    if not coords:
                        continue
                    pg.mouse.click(coords["x"], coords["y"])
                    time.sleep(1.5)
                    after = _dom_text_length(pg)
                    if after - before >= 100:
                        prompt_groups.append(grp)
                    else:
                        selector_groups.append(grp)

                # Restore page
                pg.goto(base_url, wait_until="networkidle", timeout=15_000)
                _wait_for_loaded(pg)

                if not prompt_groups:
                    return response_pages

                emit(f"[PROMPTS] {page_label}: {len(selector_groups)} selector group(s), "
                     f"{sum(len(g) for g in prompt_groups)} prompt(s) across {len(prompt_groups)} group(s)")

                # One stacked frame per selector state:
                # activate selector → click ALL prompts sequentially → screenshot once.
                # This produces e.g. 3 frames (one per persona) each showing the full
                # conversation history, rather than 15 individual frames.
                selectors = selector_groups[0] if selector_groups else [None]
                idx_offset = 0

                for sel in selectors:
                    pg.goto(base_url, wait_until="networkidle", timeout=15_000)
                    _wait_for_loaded(pg)
                    selector_label = ""
                    if sel:
                        coords = _find_btn_coords_local(pg, sel["text"])
                        if coords:
                            pg.mouse.click(coords["x"], coords["y"])
                            time.sleep(0.8)
                            selector_label = sel["text"]
                            emit(f"  [SELECTOR] '{selector_label}'")

                    # Build the stacked frame label
                    full_label = f"{page_label} — {selector_label}" if selector_label else f"{page_label} — Responses"
                    if full_label in seen_labels:
                        continue
                    seen_labels.add(full_label)

                    # Collect all prompt texts across all prompt groups
                    all_prompt_texts = [p["text"] for grp in prompt_groups for p in grp]

                    try:
                        # Click every prompt in sequence — responses stack in chat panel
                        clicked = []
                        for prompt_text in all_prompt_texts:
                            coords = _find_btn_coords_local(pg, prompt_text)
                            if not coords:
                                emit(f"    [PROMPT] '{prompt_text}' not found, skipping")
                                continue
                            pg.mouse.click(coords["x"], coords["y"])
                            time.sleep(2.5)  # wait for response + chart to render
                            clicked.append(prompt_text)
                            emit(f"    [PROMPT] clicked '{prompt_text}'")

                        if not clicked:
                            continue

                        idx_offset += 1
                        idx = page_index_base + idx_offset
                        emit(f"  [PROMPT-STACK] [{idx}] {full_label} ({len(clicked)} responses)")
                        elem_shots = _extract_svg_nodes(pg, full_label, idx)
                        b64, saved, png_w, png_h = _screenshot_b64(pg, full_label, idx)
                        response_pages.append({
                            "url": base_url,
                            "title": full_label,
                            "screenshot_b64": b64,
                            "screenshot_path": saved,
                            "screenshot_width": png_w,
                            "screenshot_height": png_h,
                            "element_screenshots": elem_shots,
                            "nav_label": full_label,
                            "is_prompt_response": True,
                            "all_prompts": clicked,       # all prompts that trigger this frame
                            "selector_label": selector_label,
                            "parent_page_title": page_label,  # for back-button wiring
                        })
                    except Exception as e:
                        emit(f"    [PROMPT-STACK] failed '{full_label}': {e}")

                # Restore clean state
                try:
                    pg.goto(base_url, wait_until="networkidle", timeout=15_000)
                    _wait_for_loaded(pg)
                except Exception:
                    pass

            except Exception as e:
                emit(f"    [PROMPTS] discovery failed: {e}")
            return response_pages

        if not pages_cache:
            title = page.title() or "Home"
            emit(f"[SCREENSHOT] [{len(pages_data)+1}] {title} — {page.url}")
            elem_shots = _extract_svg_nodes(page, title, 0)
            b64, saved, png_w, png_h = _screenshot_b64(page, title, 0)
            pages_data.append({
                "url": page.url,
                "title": title,
                "screenshot_b64": b64,
                "screenshot_path": saved,
                "screenshot_width": png_w,
                "screenshot_height": png_h,
                "element_screenshots": elem_shots,
                "nav_label": "Home",
                "interactions": [],  # filled after all pages discovered (needs full pages_data)
            })
            # Capture any in-page tab panels (tabs that switch content without changing URL).
            # Use "Home" as the parent label since the landing page nav_label is "Home".
            tab_pages = _capture_in_page_tabs(page, "Home", len(pages_data))
            pages_data.extend(tab_pages)

        # ── Interaction probing ────────────────────────────────────────────────
        def _probe_interactions(pg, page_title: str) -> list[dict]:
            """
            Exhaustively probe every interactive control on the page:
              - Nav/sidebar links   → NAVIGATE (resolved via href)
              - In-page tabs        → NAVIGATE to sub-frame (click each, record panel title/content)
              - <select> dropdowns  → OVERLAY (record all options without clicking)
              - Custom dropdowns    → OVERLAY (click, capture options, Escape)
              - Buttons             → NAVIGATE if URL changes, OVERLAY if modal appears
            Returns list of { label, type, result_type, result_target, options?, tab_frames? }
            """
            interactions = []

            # ── 1. In-page tabs ─────────────────────────────────────────────────
            # Detect both ARIA [role=tab] and custom button-group tab bars.
            # Uses the same JS strategy as _capture_in_page_tabs.
            try:
                clickable_tabs = pg.evaluate(r"""
() => {
  const ariaEls = Array.from(document.querySelectorAll('[role="tab"]')).filter(el => {
    const href = el.getAttribute('href') || '';
    const text = (el.innerText || el.textContent || '').trim();
    return text && !href.startsWith('http');
  });
  if (ariaEls.length > 1) {
    return ariaEls.map(el => {
      const bb = el.getBoundingClientRect();
      return { text: (el.innerText || '').trim(), x: bb.x + bb.width / 2, y: bb.y + bb.height / 2 };
    });
  }
  const allBtns = Array.from(document.querySelectorAll('button'));
  const parentMap = new Map();
  for (const btn of allBtns) {
    const text = (btn.innerText || '').trim();
    if (!text || text.length > 100) continue;
    const par = btn.parentElement;
    if (!par) continue;
    const ps = window.getComputedStyle(par);
    if (ps.display === 'flex' || ps.display === 'inline-flex') {
      if (!parentMap.has(par)) parentMap.set(par, []);
      parentMap.get(par).push(btn);
    }
  }
  for (const [par, btns] of parentMap) {
    if (btns.length < 2) continue;
    const ps = window.getComputedStyle(par);
    const parHasBorder = ps.borderBottomStyle !== 'none' && ps.borderBottomWidth !== '0px';
    const btnHasBorder = btns.some(b => {
      const bs = window.getComputedStyle(b);
      return bs.borderBottomStyle !== 'none' && bs.borderBottomWidth !== '0px';
    });
    if (parHasBorder || btnHasBorder) {
      return btns.map(btn => {
        const bb = btn.getBoundingClientRect();
        return { text: (btn.innerText || '').trim(), x: bb.x + bb.width / 2, y: bb.y + bb.height / 2 };
      }).filter(t => t.text);
    }
  }
  return [];
}
""")

                if clickable_tabs and len(clickable_tabs) > 1:
                    emit(f"    [PROBE-TABS] {len(clickable_tabs)} tab(s) on '{page_title}'")
                    tab_frames = []
                    for tab_info in clickable_tabs:
                        tab_text = tab_info["text"]
                        try:
                            pg.mouse.click(tab_info["x"], tab_info["y"])
                            time.sleep(0.8)
                            # Read active panel heading or first chart title
                            panel_title = pg.evaluate(r"""
() => {
  const panel = document.querySelector('[role="tabpanel"]');
  if (panel) {
    const h = panel.querySelector('h1,h2,h3,[class*="title"],[class*="heading"]');
    if (h) return h.innerText.trim().slice(0, 60);
  }
  const main = document.querySelector('main, [class*="content"], [class*="panel"]');
  if (main) {
    const h = main.querySelector('h1,h2,h3');
    if (h) return h.innerText.trim().slice(0, 60);
  }
  return null;
}
""")
                            sub_frame = f"{page_title} — {tab_text}"
                            tab_frames.append({
                                "tab_label": tab_text,
                                "frame_name": sub_frame,
                                "panel_title": panel_title or tab_text,
                            })
                        except Exception as e:
                            emit(f"      [PROBE-TABS] click failed for tab '{tab_text}': {e}")

                    # Restore first tab
                    try:
                        first = clickable_tabs[0]
                        pg.mouse.click(first["x"], first["y"])
                        time.sleep(0.5)
                    except Exception:
                        pass

                    if tab_frames:
                        interactions.append({
                            "label": f"Tab bar on {page_title}",
                            "type": "tab-bar",
                            "result_type": "TAB_SET",
                            "result_target": "",
                            "tab_frames": tab_frames,
                        })
            except Exception as e:
                emit(f"    [PROBE-TABS] failed: {e}")

            # ── 2. Scan all other interactive elements via JS ────────────────────
            # Comprehensive scan: catches buttons, <a> links anywhere on the page,
            # onclick/tabindex/data-action elements, and anything with cursor:pointer
            # that has no pointer-cursor children (leaf-level clickables only).
            _INTERACTIVE_SCAN_JS = r"""
() => {
  const SKIP_TEXT = new Set([
    'sign out','logout','log out','delete','remove','cancel account',
    'close','x','×','dismiss','skip',
  ]);
  const results = [];
  const seen = new Set();

  function label(el) {
    return (el.getAttribute('aria-label') || el.innerText || el.textContent || el.getAttribute('title') || '').trim().slice(0, 80);
  }
  function visible(el) {
    const bb = el.getBoundingClientRect();
    if (bb.width === 0 || bb.height === 0) return false;
    if (bb.y < -200 || bb.y > window.innerHeight + 800) return false;
    const cs = window.getComputedStyle(el);
    return cs.display !== 'none' && cs.visibility !== 'hidden' && cs.opacity !== '0';
  }
  function add(el, type, extra) {
    const txt = label(el);
    if (!txt || txt.length < 2 || SKIP_TEXT.has(txt.toLowerCase())) return;
    const key = type + ':' + txt;
    if (seen.has(key)) return;
    seen.add(key);
    if (!visible(el)) return;
    const bb = el.getBoundingClientRect();
    results.push(Object.assign({ label: txt, type, x: bb.x + bb.width/2, y: bb.y + bb.height/2 }, extra || {}));
  }

  const inNav = el => !!el.closest('nav, aside, [class*="sidebar"], [class*="nav-item"]');
  const isTab = el => el.getAttribute('role') === 'tab' || !!el.closest('[role="tablist"]');

  // 1. Nav/sidebar links (resolved separately — no click needed)
  document.querySelectorAll(
    'nav a, aside a, [class*="sidebar"] a, [class*="nav-item"] a, [role="menuitem"]'
  ).forEach(el => {
    const txt = label(el);
    if (!txt || SKIP_TEXT.has(txt.toLowerCase())) return;
    const key = 'nav:' + txt;
    if (seen.has(key)) return;
    seen.add(key);
    if (!visible(el)) return;
    const bb = el.getBoundingClientRect();
    results.push({ label: txt, type: 'nav-link', href: el.href || null, x: bb.x + bb.width/2, y: bb.y + bb.height/2 });
  });

  // 2. Native <select> — record options without clicking
  document.querySelectorAll('select').forEach(el => {
    if (!visible(el)) return;
    const lbl = (el.getAttribute('aria-label') || el.id ||
                 el.closest('label')?.textContent || 'filter').trim().slice(0, 40);
    const key = 'sel:' + lbl;
    if (seen.has(key)) return;
    seen.add(key);
    const bb = el.getBoundingClientRect();
    const options = Array.from(el.options).map(o => o.text.trim()).filter(Boolean).slice(0, 10);
    results.push({ label: lbl, type: 'select', options, x: bb.x + bb.width/2, y: bb.y + bb.height/2 });
  });

  // 3. Buttons (explicit <button> + role=button + class*=btn)
  document.querySelectorAll('button, [role="button"], [class*="btn"]').forEach(el => {
    if (inNav(el) || isTab(el)) return;
    if (['INPUT','SELECT','TEXTAREA'].includes(el.tagName)) return;
    const cls = (el.className || '').toLowerCase();
    const txt = label(el);
    const type = /dropdown|select|filter|sort|picker/.test(cls + ' ' + txt.toLowerCase()) ? 'dropdown' : 'button';
    add(el, type, { href: el.tagName === 'A' ? (el.href || null) : null });
  });

  // 4. All <a href> tags outside nav — text/image links in content area
  // These are the "hidden hyperlinks" — may look like bold text with no underline
  document.querySelectorAll('a[href]').forEach(el => {
    if (inNav(el)) return; // already captured above
    if (isTab(el)) return;
    const href = el.href || '';
    if (!href || href.startsWith('javascript:') || href === '#') return;
    add(el, 'link', { href });
  });

  // 5. Elements with onclick / data-action / data-href (custom clickables)
  document.querySelectorAll('[onclick], [data-action], [data-href], [data-url]').forEach(el => {
    if (inNav(el) || isTab(el)) return;
    if (['SCRIPT','STYLE','HTML','BODY'].includes(el.tagName)) return;
    const href = el.getAttribute('data-href') || el.getAttribute('data-url') || null;
    add(el, 'button', { href });
  });

  // 6. tabindex="0" elements (keyboard-focusable custom widgets)
  document.querySelectorAll('[tabindex="0"]').forEach(el => {
    if (inNav(el) || isTab(el)) return;
    if (['INPUT','SELECT','TEXTAREA','BUTTON','A'].includes(el.tagName)) return;
    add(el, 'button', {});
  });

  // 7. cursor:pointer leaf nodes — catch anything visual that acts clickable
  // Only walk elements that could plausibly be interactive (skip huge containers)
  const SKIP_TAGS = new Set(['SCRIPT','STYLE','SVG','PATH','G','CIRCLE','RECT','POLYGON',
                              'LINE','POLYLINE','DEFS','CLIPPATH','HTML','BODY','HEAD',
                              'HEADER','MAIN','ARTICLE','SECTION','FOOTER','DIV','SPAN',
                              'UL','OL','LI','TABLE','TR','TD','TH','THEAD','TBODY']);
  document.querySelectorAll('p, strong, b, em, h1, h2, h3, h4, h5, h6, td, th, li, label, [class*="link"], [class*="chip"], [class*="badge"], [class*="tag"], [class*="card"]').forEach(el => {
    if (inNav(el) || isTab(el)) return;
    const cs = window.getComputedStyle(el);
    if (cs.cursor !== 'pointer') return;
    // Skip if a child also has cursor:pointer (we want leaf-level only)
    const hasPointerChild = Array.from(el.querySelectorAll('*')).some(c => window.getComputedStyle(c).cursor === 'pointer');
    if (hasPointerChild) return;
    add(el, 'link', { href: null });
  });

  return results;
}
"""
            try:
                controls = pg.evaluate(_INTERACTIVE_SCAN_JS)
            except Exception as e:
                emit(f"    [PROBE] scan failed: {e}")
                return interactions

            before_url = pg.url

            # Build a lookup: prompt button text → stacked frame title.
            # Each stacked frame has all_prompts = [...] listing every prompt that leads to it.
            # Any of those prompt button labels navigates to that frame.
            _cur_norm = _normalise(pg.url)
            prompt_response_map: dict[str, str] = {}
            for pd in pages_data:
                if pd.get("is_prompt_response") and _normalise(pd["url"]) == _cur_norm:
                    for pt in pd.get("all_prompts", []):
                        prompt_response_map[pt] = pd["title"]

            for ctrl in (controls or []):
                label = ctrl.get("label", "").strip()
                ctrl_type = ctrl.get("type", "button")
                href = ctrl.get("href")
                cx, cy = ctrl.get("x", 0), ctrl.get("y", 0)
                if not label:
                    continue

                # Prompt-response button — wire directly to the captured sub-frame
                if label in prompt_response_map:
                    interactions.append({
                        "label": label, "type": "button",
                        "result_type": "NAVIGATE",
                        "result_target": prompt_response_map[label],
                    })
                    continue

                # Native <select> — record options as dropdown overlay
                if ctrl_type == "select":
                    options = ctrl.get("options", [])
                    if options:
                        safe = label.replace(' ', '-').lower()
                        interactions.append({
                            "label": label, "type": "dropdown",
                            "result_type": "OVERLAY",
                            "result_target": f"{page_title}-{safe}-dropdown-modal",
                            "options": options,
                        })
                    continue

                # Nav links with href — resolve to known page without clicking
                if ctrl_type == "nav-link" and href:
                    norm_href = _normalise(href)
                    matched = next((pd for pd in pages_data if _normalise(pd["url"]) == norm_href), None)
                    if matched:
                        interactions.append({
                            "label": label, "type": "nav-link",
                            "result_type": "NAVIGATE",
                            "result_target": matched["title"],
                        })
                    continue

                # Everything else — click and observe
                try:
                    before_nodes = pg.evaluate(
                        "() => document.querySelectorAll("
                        "'[role=\"dialog\"],[role=\"menu\"],"
                        "[class*=\"modal\"],[class*=\"dropdown-menu\"],"
                        "[class*=\"popover\"],[class*=\"overlay\"],"
                        "[class*=\"dropdown-content\"],[class*=\"select-menu\"]'"
                        ").length"
                    )
                    pg.mouse.click(cx + 4, cy + 4)
                    time.sleep(0.7)

                    after_url = pg.url
                    after_nodes = pg.evaluate(
                        "() => document.querySelectorAll("
                        "'[role=\"dialog\"],[role=\"menu\"],"
                        "[class*=\"modal\"],[class*=\"dropdown-menu\"],"
                        "[class*=\"popover\"],[class*=\"overlay\"],"
                        "[class*=\"dropdown-content\"],[class*=\"select-menu\"]'"
                        ").length"
                    )

                    if _normalise(after_url) != _normalise(before_url):
                        matched = next((pd for pd in pages_data if _normalise(pd["url"]) == _normalise(after_url)), None)
                        target = matched["title"] if matched else (pg.title() or after_url)
                        interactions.append({
                            "label": label, "type": ctrl_type,
                            "result_type": "NAVIGATE",
                            "result_target": target,
                        })
                        pg.go_back(wait_until="networkidle", timeout=8_000)
                        time.sleep(0.5)
                        before_url = pg.url

                    elif after_nodes > before_nodes:
                        # Overlay/dropdown appeared — capture its options/content
                        overlay_info = pg.evaluate(r"""
() => {
  const sel = '[role="dialog"],[role="menu"],[class*="modal"],[class*="dropdown-menu"],[class*="popover"],[class*="dropdown-content"],[class*="select-menu"]';
  const el = document.querySelector(sel);
  if (!el) return { title: null, options: [] };
  const h = el.querySelector('h1,h2,h3,[class*="title"]');
  const title = h ? h.innerText.trim().slice(0, 50) : null;
  const opts = Array.from(el.querySelectorAll('li, [role="option"], [class*="item"], [class*="option"]'))
    .map(o => o.innerText.trim()).filter(Boolean).slice(0, 10);
  return { title, options: opts };
}
""")
                        safe = label.replace(' ', '-').lower()
                        overlay_name = f"{page_title}-{safe}-modal"
                        interactions.append({
                            "label": label, "type": ctrl_type,
                            "result_type": "OVERLAY",
                            "result_target": overlay_name,
                            "options": overlay_info.get("options", []),
                            "overlay_content": overlay_info.get("title") or "",
                        })
                        try:
                            pg.keyboard.press("Escape")
                            time.sleep(0.3)
                        except Exception:
                            pass
                    # NONE result — omit from interactions (not useful for wiring)

                except Exception as e:
                    emit(f"    [PROBE] click failed for '{label}': {e}")
                    try:
                        if _normalise(pg.url) != _normalise(before_url):
                            pg.go_back(wait_until="domcontentloaded", timeout=6_000)
                    except Exception:
                        pass

            navigates = [i for i in interactions if i["result_type"] == "NAVIGATE"]
            overlays  = [i for i in interactions if i["result_type"] == "OVERLAY"]
            tab_sets  = [i for i in interactions if i["result_type"] == "TAB_SET"]
            n_tabs    = sum(len(t.get("tab_frames", [])) for t in tab_sets)
            emit(f"    [PROBE] {len(interactions)} interactions: {len(navigates)} navigate, {len(overlays)} overlay, {n_tabs} tab(s)")
            return interactions

        # Discover nav / sidebar / tab links
        def _collect_nav_links(pg) -> list[dict]:
            """Return {text, href, tag, is_tab} for navigation and tab elements."""
            links = pg.eval_on_selector_all(
                "a, button, [role='tab'], [role='menuitem'], nav *[class*='nav'], "
                "nav *[class*='tab'], aside *[class*='item'], *[class*='sidebar'] a, "
                "*[class*='menu'] a",
                """els => els.map(el => ({
                    text:   (el.innerText || el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 60),
                    href:   el.href || null,
                    tag:    el.tagName.toLowerCase(),
                    is_tab: el.getAttribute('role') === 'tab' || el.closest('[role=\"tablist\"]') !== null,
                })).filter(e => e.text.length > 0)"""
            )
            return links

        if not pages_cache and nav_click_depth > 0:
            # BFS queue: each entry is (url_to_visit, label, current_depth)
            # Seed from the landing page's nav links
            queue: list[tuple[str, str, int]] = []

            nav_links_found = _collect_nav_links(page)
            emit(f"[DISCOVER] Found {len(nav_links_found)} navigation elements on landing page")
            for lk in nav_links_found:
                label = lk.get("text", "").strip()
                href  = lk.get("href") or ""
                if not label or label in seen_labels:
                    continue
                if href and "://" in href and not href.startswith(landing_origin):
                    continue
                seen_labels.add(label)
                queue.append((href, label, 1))

            while queue and len(pages_data) < max_pages:
                href, label, depth = queue.pop(0)

                norm = _normalise(href) if href else None
                if norm and norm in visited_urls:
                    continue

                try:
                    emit(f"[NAV] Navigating to: {label}")
                    if href and href.startswith("http"):
                        page.goto(href, wait_until="networkidle", timeout=20_000)
                    else:
                        # button/tab with no href — click by text from landing page
                        page.goto(landing_url, wait_until="networkidle", timeout=15_000)
                        locator = page.get_by_text(label, exact=True).first
                        if not locator.is_visible():
                            continue
                        locator.click()
                        page.wait_for_load_state("networkidle", timeout=10_000)

                    time.sleep(3.0)  # allow chart/map libraries to finish their render cycle
                    new_url  = page.url
                    new_norm = _normalise(new_url)

                    if new_norm in visited_urls:
                        continue
                    visited_urls.add(new_norm)

                    pg_title = page.title() or label
                    emit(f"[SCREENSHOT] [{len(pages_data)+1}] {pg_title} — {new_url}")
                    elem_shots = _extract_svg_nodes(page, label, len(pages_data))
                    b64, saved, png_w, png_h = _screenshot_b64(page, label, len(pages_data))
                    pages_data.append({
                        "url": new_url,
                        "title": pg_title,
                        "screenshot_b64": b64,
                        "screenshot_path": saved,
                        "screenshot_width": png_w,
                        "screenshot_height": png_h,
                        "element_screenshots": elem_shots,
                        "nav_label": label,
                        "depth": depth,
                        "interactions": [],  # filled in probe pass below
                    })
                    # Capture in-page tab panels on this nav page.
                    # Use the nav label (e.g. "Analytics") not pg_title (browser title
                    # is the same for all pages in an SPA — e.g. "AutoPulse Global").
                    if len(pages_data) < max_pages:
                        tab_pgs = _capture_in_page_tabs(page, label, len(pages_data))
                        pages_data.extend(tab_pgs[:max(0, max_pages - len(pages_data))])

                    # Capture button-response sub-pages (e.g. AI Concierge prompt buttons
                    # that append chat messages + inline charts to the DOM).
                    if len(pages_data) < max_pages:
                        resp_pgs = _capture_button_responses(page, label, len(pages_data))
                        pages_data.extend(resp_pgs[:max(0, max_pages - len(pages_data))])

                    # If we haven't hit max depth, enqueue links found on this page
                    if depth < nav_click_depth and len(pages_data) < max_pages:
                        for lk in _collect_nav_links(page):
                            sub_label = lk.get("text", "").strip()
                            sub_href  = lk.get("href") or ""
                            if not sub_label or sub_label in seen_labels:
                                continue
                            if sub_href and "://" in sub_href and not sub_href.startswith(landing_origin):
                                continue
                            sub_norm = _normalise(sub_href) if sub_href else None
                            if sub_norm and sub_norm in visited_urls:
                                continue
                            seen_labels.add(sub_label)
                            queue.append((sub_href, sub_label, depth + 1))

                    # Return to landing page for next item
                    page.goto(landing_url, wait_until="networkidle", timeout=20_000)
                    time.sleep(0.8)

                except Exception as exc:
                    log.warning(f"  Nav {label!r} failed: {exc}")
                    try:
                        page.goto(landing_url, wait_until="networkidle", timeout=15_000)
                    except Exception:
                        pass

        if pages_cache:
            # ── Cache-restore mode: skip BFS, re-extract SVGs + probe only ────────
            # pages_data is still empty here (BFS block was skipped because
            # pages_cache is truthy — see guard at BFS entry above). Restore it now.
            pages_data = [
                {k: v for k, v in p.items() if k != "element_screenshots"}
                for p in pages_cache
            ]
            emit(f"[CACHE] Restored {len(pages_data)} page(s) from discover cache")

            # Navigate to each page, click any required tab, re-extract SVG nodes.
            # Tab sub-pages have is_tab_panel=True and title like "Analytics — Volume"
            # where "Analytics" is the parent page title and "Volume" is the tab label.
            for idx, pd_entry in enumerate(pages_data):
                pg_url = pd_entry["url"]
                pg_title = pd_entry["title"]
                is_tab = pd_entry.get("is_tab_panel", False)
                try:
                    emit(f"  [SVG-REFRESH] [{idx+1}] {pg_title}")
                    page.goto(pg_url, wait_until="networkidle", timeout=20_000)
                    _wait_for_loaded(page)
                    if pd_entry.get("is_prompt_response"):
                        # Click the selector then ALL prompts in sequence (stacked response frame)
                        sel_label = pd_entry.get("selector_label", "")
                        all_prompts = pd_entry.get("all_prompts", [])
                        # Activate selector if needed
                        if sel_label:
                            try:
                                coords = page.evaluate(f"""
() => {{
  const text = {repr(sel_label)};
  for (const el of document.querySelectorAll('button')) {{
    if ((el.innerText || '').trim() === text) {{
      const bb = el.getBoundingClientRect();
      return {{ x: bb.x + bb.width / 2, y: bb.y + bb.height / 2 }};
    }}
  }}
  return null;
}}
""")
                                if coords:
                                    page.mouse.click(coords["x"], coords["y"])
                                    time.sleep(0.8)
                                    emit(f"    [SELECTOR] activated '{sel_label}'")
                            except Exception as se:
                                emit(f"    [SELECTOR] click failed for '{sel_label}': {se}")
                        # Click every prompt in sequence so all responses stack
                        for btn_text in all_prompts:
                            try:
                                coords = page.evaluate(f"""
() => {{
  const text = {repr(btn_text)};
  for (const el of document.querySelectorAll('button')) {{
    if ((el.innerText || '').trim() === text) {{
      const bb = el.getBoundingClientRect();
      return {{ x: bb.x + bb.width / 2, y: bb.y + bb.height / 2 }};
    }}
  }}
  return null;
}}
""")
                                if coords:
                                    page.mouse.click(coords["x"], coords["y"])
                                    time.sleep(2.0)
                                    emit(f"    [PROMPT] clicked '{btn_text}'")
                            except Exception as pe:
                                emit(f"    [PROMPT] click failed for '{btn_text}': {pe}")
                    elif is_tab:
                        # Title format: "ParentTitle — TabLabel"  e.g. "Analytics — Volume — ..."
                        # Split on first " — " to get the tab button text
                        tab_label = pg_title.split(" — ", 1)[-1] if " — " in pg_title else ""
                        if tab_label:
                            try:
                                # Use JS to find the tab button by text (works for both
                                # [role=tab] and custom button-group tab bars)
                                coords = page.evaluate(f"""
() => {{
  const text = {repr(tab_label)};
  // ARIA tabs
  for (const el of document.querySelectorAll('[role="tab"]')) {{
    if ((el.innerText || '').trim() === text) {{
      const bb = el.getBoundingClientRect();
      return {{ x: bb.x + bb.width / 2, y: bb.y + bb.height / 2 }};
    }}
  }}
  // Plain buttons
  for (const el of document.querySelectorAll('button')) {{
    if ((el.innerText || '').trim() === text) {{
      const bb = el.getBoundingClientRect();
      return {{ x: bb.x + bb.width / 2, y: bb.y + bb.height / 2 }};
    }}
  }}
  return null;
}}
""")
                                if coords:
                                    page.mouse.click(coords["x"], coords["y"])
                                    time.sleep(1.5)
                                    emit(f"    [TAB] clicked tab '{tab_label}'")
                                else:
                                    emit(f"    [TAB] tab button '{tab_label}' not found in DOM")
                            except Exception as te:
                                emit(f"    [TAB] could not click tab '{tab_label}': {te}")
                    pd_entry["element_screenshots"] = _extract_svg_nodes(page, pg_title, idx)
                except Exception as e:
                    emit(f"    [SVG-REFRESH] failed for '{pg_title}': {e}")
                    pd_entry["element_screenshots"] = []

            # Re-run interaction probe for every page (tab sub-pages share parent URL;
            # probe navigates there and the parent page handles interaction wiring).
            # Skip tab sub-pages in the probe pass — their interactions are already
            # captured under the parent page entry.
            emit(f"[PROBE] Probing interactions on {len(pages_data)} page(s)…")
            probed_urls: set[str] = set()
            for pd_entry in pages_data:
                if pd_entry.get("is_tab_panel") or pd_entry.get("is_prompt_response"):
                    continue  # covered by parent page probe
                pg_url = pd_entry["url"]
                pg_title = pd_entry["title"]
                norm_url = _normalise(pg_url)
                if norm_url in probed_urls:
                    continue
                probed_urls.add(norm_url)
                try:
                    emit(f"  [PROBE] {pg_title}")
                    page.goto(pg_url, wait_until="networkidle", timeout=20_000)
                    _wait_for_loaded(page)
                    pd_entry["interactions"] = _probe_interactions(page, pg_title)
                except Exception as e:
                    emit(f"    [PROBE] failed for '{pg_title}': {e}")
                    pd_entry["interactions"] = []

        else:
            # ── Normal mode: interaction probe pass after BFS discovery ───────────
            emit(f"[PROBE] Probing interactions on {len(pages_data)} page(s)…")
            for pd_entry in pages_data:
                if pd_entry.get("is_tab_panel") or pd_entry.get("is_prompt_response"):
                    continue  # covered by parent page probe
                try:
                    pg_url = pd_entry["url"]
                    pg_title = pd_entry["title"]
                    emit(f"  [PROBE] {pg_title}")
                    page.goto(pg_url, wait_until="networkidle", timeout=20_000)
                    _wait_for_loaded(page)
                    pd_entry["interactions"] = _probe_interactions(page, pg_title)
                except Exception as e:
                    emit(f"    [PROBE] failed for '{pd_entry['title']}': {e}")
                    pd_entry["interactions"] = []

        browser.close()

    emit(f"[SCREENSHOTS_DONE] Captured {len(pages_data)} page(s)")
    return pages_data


# ── Vision analysis ─────────────────────────────────────────────────────────────

_VISION_SYSTEM = """\
You are a senior UX analyst. Your job is to analyse a screenshot of a running web app
and describe its UI structure precisely so a Figma designer can recreate it.

Return a JSON object with exactly these fields:
{
  "page_title":      "short page name suitable as a Figma frame name (e.g. 'Dashboard')",
  "layout_type":     "sidebar-nav | top-nav | tabs | full-page | modal | other",
  "nav_items":       ["Label1", "Label2", ...],   // sidebar or top nav item labels visible
  "active_nav_item": "Label of currently-active nav item or null",
  "header_title":    "text in the page header / breadcrumb or null",
  "sections":        [
    {
      "type": "kpi-row | chart | map | data-table | table | card-grid | form | tab-bar | action-bar | hero | list | other",
      "title": "section heading text or null",
      "item_count": 3,
      "description": "one sentence describing this section's content",
      "columns": ["Col1", "Col2"],  // for data-table: list visible column headers; omit for other types
      "chart_type": "bar | horizontal_bar | line | area | scatter | pie | donut | gauge | sparkline | null",
      "bbox_pct": {"left": 0.0, "top": 0.0, "right": 1.0, "bottom": 1.0}
      // bbox_pct: bounding box of this section as fractions of the full screenshot (0.0–1.0).
      // REQUIRED for ALL section types — estimate carefully from visual position.
      // The screenshot may be taller than a single viewport (full-page scroll capture).
      // Example: a data table in the lower third of the page →
      //   {"left": 0.0, "top": 0.65, "right": 1.0, "bottom": 0.95}
    }
  ],
  "interactive_elements": [
    // List EVERY clickable/typeable control visible: dropdowns, search bars, text inputs, tabs, date pickers, toggles
    {
      "type": "dropdown | search-input | text-input | tab-bar | date-picker | toggle | button-group",
      "label": "visible label or placeholder text, e.g. 'Filter: All', 'Search customers...'",
      "options": ["Option1", "Option2"],   // for dropdown: likely options based on context; [] if unknown
      "location": "brief description of where this appears, e.g. 'top-right above data table', 'sidebar header'"
    }
  ],
  "primary_cta":     "label of the main action button or null",
  "color_scheme":    "dark | light | mixed",
  "primary_color":   "#hex of the dominant brand/accent colour",
  "has_sidebar":     true | false,
  "sidebar_width_approx": 240,
  "has_top_header":  true | false,
  "header_height_approx": 64,
  "modal_visible":   false,
  "notes":           "anything else a Figma designer needs to know"
}

Be precise. Infer types from visual appearance. For interactive_elements, be exhaustive — list every
dropdown, search bar, text input, and tab switcher you can see. Only return valid JSON, no markdown."""


def _analyse_pages(
    pages: list[dict],
    emit: Callable[[str], None] = print,
) -> list[dict]:
    """Run Claude Vision on each screenshot and return enriched page dicts."""
    client = get_openai_client()
    enriched = []

    for i, pg in enumerate(pages):
        emit(f"[VISION] [{i+1}/{len(pages)}] Analysing: {pg['title']}")

        content = [
            {"type": "text", "text": (
                f"This is a FULL-PAGE screenshot of the '{pg['title']}' page (URL: {pg['url']}).\n"
                "The screenshot captures the entire scrollable content, not just the visible viewport.\n"
                "Make sure to identify ALL sections including any data tables, charts, or content below the fold.\n"
                "Analyse the UI and return the JSON description."
            )},
            {"type": "image_url", "image_url": {
                "url": f"data:image/png;base64,{pg['screenshot_b64']}",
            }},
        ]

        try:
            resp = client.chat.completions.create(
                model=MODEL_ID,
                max_tokens=2000,
                messages=[
                    {"role": "system", "content": _VISION_SYSTEM},
                    {"role": "user", "content": content},
                ],
            )
            if hasattr(resp, "usage") and resp.usage:
                record_token_usage(
                    _get_figma_run_id(),
                    resp.usage.prompt_tokens or 0,
                    resp.usage.completion_tokens or 0,
                )
            text = (resp.choices[0].message.content or "").strip()
            # Strip markdown fences if present
            if text.startswith("```"):
                lines = text.splitlines()
                text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            analysis = json.loads(text)
            pg["analysis"] = analysis
            sections = analysis.get('sections', [])
            section_types = ", ".join(s.get('type','?') for s in sections) if sections else "none"
            interactive = analysis.get('interactive_elements', [])
            interactive_str = ""
            if interactive:
                interactive_types = ", ".join(f"{el.get('type','?')} '{el.get('label','')}'" for el in interactive[:4])
                if len(interactive) > 4:
                    interactive_types += f" +{len(interactive)-4} more"
                interactive_str = f", {len(interactive)} interactive: {interactive_types}"
            emit(f"[VISION_DONE] {pg['title']}: {analysis.get('layout_type','?')} layout, {len(sections)} section(s) — {section_types}{interactive_str}")
        except Exception as exc:
            log.warning(f"  Vision analysis failed for {pg['title']}: {exc}")
            pg["analysis"] = {}

        enriched.append(pg)

    return enriched


# ── Prompt builder ──────────────────────────────────────────────────────────────

def _build_figma_prompt(
    pages: list[dict],
    source_url: str,
    extra_instructions: str = "",
) -> str:
    """Convert page analyses into a detailed Figma build prompt."""

    lines = [
        f"Recreate the following web app as an interactive Figma prototype.",
        f"Source URL: {source_url}",
        f"Total pages to recreate: {len(pages)}",
        "",
        "## CHART AND MAP RULES — NON-NEGOTIABLE, read before doing anything else",
        "",
        "### RULE 0 — MANDATORY: Never override extracted assets",
        "  If a page lists '⚡ EXTRACTED SVG NODES' or '⚡ CANVAS FALLBACKS', you MUST use",
        "  figma_create_svg_node or figma_create_image_from_file for those items.",
        "  YOU ARE FORBIDDEN from calling figma_create_map or figma_create_chart for any",
        "  chart/map that already has an extracted file listed — regardless of your assessment",
        "  of the SVG quality, size, or content. The extracted asset IS the correct output.",
        "  No exceptions. No substitutions. No 'native charts give cleaner results'.",
        "",
        "### Charts and Maps — THREE strategies in strict priority order",
        "",
        "STRATEGY 1 — SVG extracted (listed as '⚡ EXTRACTED SVG NODES') — ALWAYS USE THIS FIRST:",
        "  The browser-rendered SVG has all CSS styles inlined including choropleth fill colors.",
        "  This is the pixel-perfect output. Use figma_create_svg_node with the svg_path listed:",
        "    figma_create_svg_node(frame_name='Global Map', svg_path='/abs/path/to/map.svg',",
        "      name='world-heatmap', x=140, y=280, width=900, height=460)",
        "  The x/y are scroll-adjusted coordinates — use them exactly as listed.",
        "",
        "STRATEGY 2 — Image fallback (listed as '⚡ CANVAS FALLBACKS') — USE WHEN NO SVG:",
        "  Use figma_create_image_from_file with the path and coordinates listed.",
        "",
        "STRATEGY 3 — Native draw (NO ⚡ lines at all for this page) — LAST RESORT ONLY:",
        "  Only call figma_create_chart or figma_create_map if and only if there are zero",
        "  extracted nodes listed for that page. If even one ⚡ line exists, use it.",
        "",
    ]

    # Gather global properties from first analysed page
    first_analysis = next((p["analysis"] for p in pages if p.get("analysis")), {})
    color_scheme   = first_analysis.get("color_scheme", "dark")
    primary_color  = first_analysis.get("primary_color", "#6366f1")
    has_sidebar    = first_analysis.get("has_sidebar", True)
    sidebar_w      = first_analysis.get("sidebar_width_approx", 240)
    header_h       = first_analysis.get("header_height_approx", 64)

    lines += [
        f"## Global layout",
        f"  Color scheme: {color_scheme}",
        f"  Primary/accent color: {primary_color}",
        f"  Has sidebar: {has_sidebar}  (width ≈ {sidebar_w}px)",
        f"  Has top header: {first_analysis.get('has_top_header', True)}  (height ≈ {header_h}px)",
        "",
        "## Frame height rule",
        "  Screenshots are FULL-PAGE (entire scrollable content, not just 900px viewport).",
        "  Each page below lists '*** FRAME SIZE: width=Xpx, height=Ypx ***'.",
        "  You MUST create the Figma frame with EXACTLY those pixel dimensions.",
        "  Content sections also list [y=TOP–BOTpx] absolute pixel positions within the frame.",
        "  Use those y coordinates when calling figma_create_table, figma_create_text, etc.",
        "  NEVER cut off content — if a section is listed in the page description, it must appear.",
        "",
    ]

    # Global nav from first page
    nav_items = first_analysis.get("nav_items", [p["title"] for p in pages])
    if nav_items:
        lines += [
            "## Navigation items (appear on every screen)",
            "  " + ", ".join(nav_items),
            "",
        ]

    lines += ["## Pages to build (in order)", ""]

    for i, pg in enumerate(pages):
        a = pg.get("analysis", {})
        # For tab sub-pages, always use the crawl label (e.g. "Analytics — Volume ...").
        # Vision sees the same app header on every tab and names them all the same thing.
        pg_title = pg["title"] if (pg.get("is_tab_panel") or pg.get("is_prompt_response")) else a.get("page_title", pg["title"])
        pg_safe = pg_title.replace(" ", "-")
        # Full-page screenshot pixel height — used to convert bbox_pct → absolute y coords
        scr_h = pg.get("screenshot_height") or 900
        scr_w = pg.get("screenshot_width") or 1440
        lines.append(f"### Page {i+1}: {pg_title}")
        if a.get("layout_type"):
            lines.append(f"  Layout: {a['layout_type']}")
        if a.get("header_title"):
            lines.append(f"  Header title: {a['header_title']}")
        if a.get("active_nav_item"):
            lines.append(f"  Active nav item: {a['active_nav_item']}")
        if a.get("primary_cta"):
            lines.append(f"  Primary CTA button: {a['primary_cta']}")
        # Explicit frame size derived from actual full-page screenshot dimensions
        lines.append(f"  *** FRAME SIZE: width={scr_w}px, height={scr_h}px ***")
        lines.append(f"  *** Create this Figma frame with EXACTLY these dimensions. ***")

        # Prompt-response stacked frame: instruct LLM to add a back/clear button
        if pg.get("is_prompt_response"):
            parent_title = pg.get("parent_page_title", "")
            sel_label = pg.get("selector_label", "")
            all_prompts = pg.get("all_prompts", [])
            lines.append(f"  ⚡ PROMPT RESPONSE FRAME — this shows the chat panel after ALL prompts were clicked in sequence.")
            if sel_label:
                lines.append(f"    Persona/selector active: '{sel_label}'")
            if all_prompts:
                lines.append(f"    Prompts shown (stacked top-to-bottom): {all_prompts}")
            lines.append(f"  ✦ BACK BUTTON — add a '← New conversation' button at the top-right of the chat panel.")
            lines.append(f"    Name it: 'btn-new-conversation-on-{pg_safe}'")
            lines.append(f"    Wire it: NAVIGATE → '{parent_title or pg_title.split(' — ')[0]}'")
            if parent_title:
                lines.append(f"    Include this in the wiring table below with target_frame='{parent_title}'.")

        sections = a.get("sections", [])
        elem_shots = pg.get("element_screenshots", [])

        if sections:
            lines.append("  Content sections (y_px = absolute pixel position within the frame):")
            for s in sections:
                count_str = f" ({s['item_count']} items)" if s.get("item_count") else ""
                title_str = f" '{s['title']}'" if s.get("title") else ""
                col_str = ""
                if s.get("columns"):
                    col_str = f" [columns: {', '.join(s['columns'])}]"
                chart_type_str = f" [chart_type: {s['chart_type']}]" if s.get("chart_type") else ""
                # Compute absolute y from bbox_pct if available
                bbox = s.get("bbox_pct", {})
                y_px_str = ""
                if bbox:
                    y_top = int(bbox.get("top", 0) * scr_h)
                    y_bot = int(bbox.get("bottom", 1) * scr_h)
                    x_left = int(bbox.get("left", 0) * scr_w)
                    x_right = int(bbox.get("right", 1) * scr_w)
                    y_px_str = f" [y={y_top}–{y_bot}px, x={x_left}–{x_right}px]"
                lines.append(f"    - {s['type']}{title_str}{count_str}{col_str}{chart_type_str}{y_px_str}: {s.get('description', '')}")

        # Emit SVG node and canvas fallback instructions
        svg_nodes   = [e for e in elem_shots if e.get("type") == "svg"]
        canvas_nodes = [e for e in elem_shots if e.get("type") == "canvas"]

        if svg_nodes:
            lines.append("  ⚡ EXTRACTED SVG NODES — use figma_create_svg_node (fully editable vectors, preserves all colors):")
            # Check if there are other sections below the SVG (e.g. data table under a map).
            # If so, compute a scaled-down size so everything fits in the frame height.
            has_sections_below = any(
                s.get("bbox_pct", {}).get("top", 0) > (
                    max((sn["y"] + sn["height"]) for sn in svg_nodes) / scr_h
                )
                for s in sections
            ) if sections else False
            for sn in svg_nodes:
                sw, sh = sn["width"], sn["height"]
                sx, sy = sn["x"], sn["y"]
                # If there are sections below this SVG, scale it proportionally to
                # match its fraction of the full-page screenshot height, so content
                # below is not pushed off-frame.
                if has_sections_below and scr_h > 900:
                    scale = scr_w / max(scr_w, sw)  # keep width within frame
                    sw_fit = int(sw * scale)
                    sh_fit = int(sh * scale)
                    lines.append(f"    [{sn['kind']}] label='{sn['label']}'  path={sn['path']}")
                    lines.append(f"      place at x={sx:.0f}, y={sy:.0f}, width={sw_fit}, height={sh_fit}")
                    lines.append(f"      (scaled from {sn['width']}×{sn['height']} to fit frame — preserve aspect ratio)")
                else:
                    lines.append(f"    [{sn['kind']}] label='{sn['label']}'  path={sn['path']}")
                    lines.append(f"      place at x={sx:.0f}, y={sy:.0f}, width={sw}, height={sh}")
            lines.append("  *** MANDATORY: call figma_create_svg_node for EVERY node listed above. ***")
            lines.append("  *** Do NOT call figma_create_map or figma_create_chart for any of these. ***")
            lines.append("  *** The SVG already contains correct choropleth colors and chart data.  ***")
            lines.append("  *** Using native map/chart tools instead is WRONG and will produce a    ***")
            lines.append("  *** blank grey placeholder instead of the real colored visualization.   ***")
            lines.append("  Use the x/y coordinates listed — they are scroll-adjusted full-page positions.")
            lines.append("  CRITICAL SIZING RULE: ALL sections listed for this page MUST be visible in the frame.")
            lines.append("  If the SVG + sections below would exceed the frame height, scale the SVG down")
            lines.append("  (maintaining aspect ratio) until everything fits. NEVER let the SVG overlap or")
            lines.append("  push a data-table or other section outside the frame bounds.")
        if canvas_nodes:
            lines.append("  ⚡ CANVAS FALLBACKS — use figma_create_image_from_file (canvas cannot be vectorised):")
            for cn in canvas_nodes:
                lines.append(f"    [{cn['kind']}] label='{cn['label']}'  path={cn['path']}")
                lines.append(f"      place at x={cn['x']:.0f}, y={cn['y']:.0f}, width={cn['width']}, height={cn['height']}")
            lines.append("  Call figma_create_image_from_file with the path and coordinates above.")
            lines.append("  CRITICAL SIZING RULE: ALL sections listed for this page MUST be visible in the frame.")
            lines.append("  Scale images down if needed so every section fits — never clip or overlap content.")

        # ── Mandatory completion checklist for pages that mix SVG/maps with other sections ──
        # Sections that are NOT covered by an extracted SVG/canvas node must still be built.
        non_visual_section_types = {"data-table", "table", "kpi-row", "action-bar",
                                     "card-grid", "list", "form", "hero", "other"}
        non_visual_sections = [
            s for s in sections
            if s.get("type") in non_visual_section_types
        ]
        if (svg_nodes or canvas_nodes) and non_visual_sections:
            lines.append("  ─────────────────────────────────────────────────────────────")
            lines.append("  ⚠️  THIS PAGE HAS BOTH A MAP/CHART AND OTHER SECTIONS.")
            lines.append("  After placing the map/chart SVG, you MUST ALSO build ALL of the following:")
            for s in non_visual_sections:
                bbox = s.get("bbox_pct", {})
                if bbox:
                    y_top = int(bbox.get("top", 0) * scr_h)
                    y_bot = int(bbox.get("bottom", 1) * scr_h)
                    pos = f" at approx y={y_top}–{y_bot}px"
                else:
                    pos = ""
                col_str = f" [columns: {', '.join(s['columns'])}]" if s.get("columns") else ""
                title_str = f" '{s['title']}'" if s.get("title") else ""
                lines.append(f"    ✦ {s['type']}{title_str}{col_str}{pos} — {s.get('description', '')}")
            lines.append("  DO NOT skip these sections. The map/chart is one part of the page.")
            lines.append("  A page with a map and a data table MUST show BOTH in Figma.")
            lines.append("  Use figma_create_table for every data-table/table section listed above.")
            lines.append("  Use the y-coordinates above to position each section below the map.")
            lines.append("  ─────────────────────────────────────────────────────────────")

        # Playwright-probed interactions take priority over Vision guesses
        probed = pg.get("interactions", [])
        vision_interactive = a.get("interactive_elements", [])

        if probed or pg.get("is_prompt_response"):
            lines.append("  ⚡ PLAYWRIGHT-VERIFIED INTERACTIONS — Playwright clicked every element; use these EXACTLY for wiring.")
            lines.append("  Rendering rules per type:")
            lines.append("    • button/dropdown → figma_create_button (filled/outlined rectangle with label text)")
            lines.append("    • link → figma_create_text with underline style and pointer cursor (looks like a hyperlink)")
            lines.append("    • nav-link → sidebar nav button (already built as part of the sidebar)")
            lines.append("    • tab-bar → tab strip with one button per tab; active tab highlighted")
            wire_entries = []   # accumulated for the wiring table at end

            # Prompt-response frames always get a back button wired to their parent
            if pg.get("is_prompt_response"):
                parent_title = pg.get("parent_page_title", "") or pg_title.split(" — ")[0]
                back_node = f"btn-new-conversation-on-{pg_safe}"
                wire_entries.append({"source_node": back_node, "target_frame": parent_title, "link_type": "NAVIGATE"})

            for ix in probed:
                lbl = ix["label"]
                ix_type = ix["type"]
                rtype = ix.get("result_type", "NONE")
                rtarget = ix.get("result_target", "")
                opts = ix.get("options", [])
                lbl_safe = lbl.replace(" ", "-").replace("'", "").lower()[:30]

                if rtype == "NAVIGATE":
                    node_name = f"btn-{lbl_safe}-on-{pg_safe}" if ix_type != "link" else f"link-{lbl_safe}-on-{pg_safe}"
                    render = "figma_create_text (underline)" if ix_type == "link" else "figma_create_button"
                    lines.append(f"    → '{lbl}' [{ix_type}]: NAVIGATE → '{rtarget}'")
                    lines.append(f"      Render as: {render}  name='{node_name}'")
                    wire_entries.append({"source_node": node_name, "target_frame": rtarget, "link_type": "NAVIGATE"})

                elif rtype == "OVERLAY":
                    node_name = f"btn-{lbl_safe}-on-{pg_safe}"
                    opts_str = f" → options: {opts}" if opts else ""
                    lines.append(f"    → '{lbl}' [{ix_type}]: OVERLAY → '{rtarget}'{opts_str}")
                    lines.append(f"      Render as: figma_create_button  name='{node_name}'")
                    lines.append(f"      Create overlay frame '{rtarget}' — list the options above as text rows.")
                    wire_entries.append({"source_node": node_name, "target_frame": rtarget, "link_type": "OVERLAY"})

                elif rtype == "TAB_SET":
                    tab_frames = ix.get("tab_frames", [])
                    lines.append(f"    → Tab bar: {len(tab_frames)} tabs — each switches content in-place")
                    for tf in tab_frames:
                        sub = tf["frame_name"]
                        tab_safe = tf["tab_label"].replace(" ", "-").replace("'", "").lower()[:30]
                        node_name = f"tab-{tab_safe}-on-{pg_safe}"
                        lines.append(f"      • '{tf['tab_label']}' → sub-frame '{sub}'  name='{node_name}'")
                        wire_entries.append({"source_node": node_name, "target_frame": sub, "link_type": "NAVIGATE"})
                    lines.append(f"      Each sub-frame has the full tab bar (active tab highlighted) + that tab's content.")

            # Emit a compact wiring table the LLM copies verbatim into figma_wire_all
            if wire_entries:
                lines.append(f"  ── WIRING TABLE for '{pg_title}' ── copy into figma_wire_all(frame_name='{pg_title}', links=[...])")
                for we in wire_entries:
                    lines.append(f"    {{source_node: '{we['source_node']}', target_frame: '{we['target_frame']}', link_type: '{we['link_type']}'}}")

            # Supplement with Vision-detected items not covered by probing
            probed_labels = {ix["label"].lower() for ix in probed}
            extra = [el for el in vision_interactive if el.get("label", "").lower() not in probed_labels]
            if extra:
                lines.append("  Additional interactive elements (Vision-only — wire if you can identify the node):")
                for el in extra:
                    opts_str = f"  options: {el['options']}" if el.get("options") else ""
                    lines.append(f"    - {el['type']} '{el.get('label', '')}' @ {el.get('location', '')}{opts_str}")
        elif vision_interactive:
            lines.append("  Interactive elements (MUST be prototyped — no Playwright data available):")
            for el in vision_interactive:
                opts_str = f"  options: {el['options']}" if el.get("options") else ""
                lines.append(f"    - {el['type']} '{el.get('label', '')}' @ {el.get('location', '')}{opts_str}")

        if a.get("modal_visible"):
            lines.append("  Has visible modal/overlay")
        if a.get("notes"):
            lines.append(f"  Notes: {a['notes']}")
        lines.append("")

    # Collect all interactive elements across all pages for the instructions block
    all_interactive: list[dict] = []
    for pg in pages:
        a = pg.get("analysis", {})
        page_title = pg["title"] if (pg.get("is_tab_panel") or pg.get("is_prompt_response")) else a.get("page_title", pg["title"])
        for el in a.get("interactive_elements", []):
            all_interactive.append({**el, "_page": page_title})

    if all_interactive:
        lines += [
            "## Interactive element instructions — READ CAREFULLY",
            "",
            "CRITICAL: Use figma_create_button for EVERY element that a user would click.",
            "All interactive elements must be named so they can be wired with figma_wire_all.",
            "Do NOT use figma_create_rectangle for anything clickable.",
            "",
            "### Dropdowns",
            "For EVERY dropdown (type='dropdown') detected above:",
            "  1. Create the trigger with figma_create_button:",
            "     - Name: 'dropdown-<label>-on-<ScreenName>'  (e.g. 'dropdown-Filter-on-Dashboard')",
            "     - Width ≈ 160px, height ≈ 36px, label text + '▼' suffix, rounded corners.",
            "  2. Create a SEPARATE overlay frame named '<ScreenName>-<label>-dropdown-modal':",
            "     - Width = trigger width, height = (number of options × 36px) + 8px.",
            "     - Each option as a text row (36px tall, 12px left padding).",
            "     - Add this to the figma_wire_all links array as type='OVERLAY'.",
            "",
            "### Search bars and text inputs",
            "For EVERY search-input or text-input detected above:",
            "  1. Create with figma_create_button:",
            "     - Name: 'search-btn-<ScreenName>'  (e.g. 'search-btn-Customers')",
            "     - Height ≈ 40px, rounded corners, card background fill, '🔍 Search…' label.",
            "  2. Create a search results overlay frame named '<ScreenName>-search-results-modal':",
            "     - Width ≈ 600px, height ≈ 400px.",
            "     - Header: 'Showing results for…', then 4-6 result rows with realistic sample data.",
            "     - A Close button at the top right.",
            "  3. Add to figma_wire_all links as type='OVERLAY' pointing to the results modal.",
            "  NOTE: Real typing is not possible in Figma — the overlay simulates the search result state.",
            "",
            "### Tab bars",
            "For EVERY tab-bar detected above:",
            "  1. Create each tab with figma_create_button:",
            "     - Name: 'tab-<TabName>-on-<ScreenName>'",
            "     - Active tab: accent color fill, white text. Inactive: transparent, muted text.",
            "  2. Wire inactive tabs to their respective screens using figma_wire_all (type='NAVIGATE').",
            "     The active tab is the current screen — do NOT wire it to itself.",
            "",
            "### Data tables and data grids",
            "For EVERY data-table, data-grid, or tabular section detected above:",
            "  ALWAYS use figma_create_table — never manually draw rectangles and text for tables.",
            "  figma_create_table(",
            "    frame_name='ScreenName',",
            "    name='inventory-table',",
            "    x=264, y=200, width=1000,",
            "    columns=[{'label':'ID','width':80}, {'label':'Name','width':260}, {'label':'Status','width':120}, {'label':'Value','width':120}],",
            "    rows=[['001','Alpha Widget','Active','$1,200'], ['002','Beta Gadget','Pending','$840']],",
            "    row_height=40, header_height=44,",
            "    header_bg='#1E293B', header_text='#F1F5F9',",
            "    row_bg='#0F172A', row_alt_bg='#1E293B', row_text='#CBD5E1'",
            "  )",
            "  Use the detected column headers. Fill 6-8 rows with realistic placeholder data.",
            "  After creating the table, wire the first data row with figma_create_button (name: 'row1-btn-<ScreenName>') to a detail overlay.",
            "",
            "### Text hyperlinks",
            "For every interaction with type 'link':",
            "  1. Render as figma_create_text with underline=True and color='#0064D2'.",
            "     The text looks like an inline hyperlink, not a button.",
            "  2. Add to figma_wire_all as NAVIGATE or OVERLAY just like a button.",
            "",
            "### All wiring — use figma_wire_all",
            "Each page section above ends with a '── WIRING TABLE ──' block.",
            "COPY that table verbatim into figma_wire_all(frame_name='<screen>', links=[...]).",
            "ALSO add sidebar nav links: for each nav item, wire its button on THIS screen to the target frame.",
            "Combine sidebar nav wires + WIRING TABLE entries into ONE figma_wire_all call per screen.",
            "BEFORE calling figma_wire_all, call figma_list_frame_nodes(frame_name=<screen>, filter='btn-')",
            "to confirm node names exist — use the exact names returned, not assumed names.",
            "Do NOT call figma_add_overlay_link or figma_set_prototype_link individually.",
            "",
        ]

    # Wiring instructions — connect nav items to their target pages
    page_titles = [
        pg["title"] if (pg.get("is_tab_panel") or pg.get("is_prompt_response")) else (pg.get("analysis") or {}).get("page_title", pg["title"])
        for pg in pages
    ]
    lines += [
        "## Wiring / prototype links",
        "Wire every navigation item on every screen to its target screen.",
        "STEP 1: For each screen, call figma_list_frame_nodes(frame_name=<screen>, filter='tab-') to get exact node names.",
        "STEP 2: Wire every nav item using the exact name returned by figma_list_frame_nodes.",
        "Nav items and their targets:",
    ]
    for title in page_titles:
        lines.append(f"  - nav button for '{title}' on every OTHER screen → navigate to frame '{title}'")
    lines += [
        "Use figma_wire_all in ONE call per screen with ALL links for that screen.",
        "Set the first page as the prototype start frame.",
        "",
    ]

    if extra_instructions:
        lines += ["## Additional instructions", extra_instructions, ""]

    lines += [
        "## Build instructions",
        "1. Build ALL screens listed above. Do NOT skip any screen even if a frame with that name already exists — delete it first with figma_delete_frame and recreate it.",
        "2. Build all screens at 1440×900 (desktop), matching the source app's layout exactly.",
        f"3. Apply the {color_scheme} color palette matching primary color {primary_color}.",
        "4. On each screen: create the sidebar nav first, then the top header, then content sections.",
        "5. Mark the correct active nav item per screen.",
        "6. Build ALL interactive elements (dropdowns, search bars, tab bars, data tables) as described above.",
        "7. Draw bar/column charts with figma_create_rectangle bars at proportional heights.",
        "8. Use figma_create_chart for ALL charts (bar/line/area/scatter/pie/donut/gauge/sparkline). Use figma_create_map for all maps.",
        "9. For each screen: call figma_list_frame_nodes(filter='tab-') to get exact node names, then wire ALL links (nav + overlays + row actions) in ONE figma_wire_all call.",
        "10. Run a QA pass: call figma_inspect_reactions on each screen to verify all nav buttons are wired.",
    ]

    return "\n".join(lines)


# ── Main entry point ────────────────────────────────────────────────────────────

def run_agent(
    url: str,
    stream_callback: Optional[Callable[[str], None]] = None,
    max_pages: int = 12,
    nav_click_depth: int = 2,
    extra_instructions: str = "",
    viewport_width: int = 1440,
    viewport_height: int = 900,
    project_name: str = "",
    login_username: str = "",
    login_password: str = "",
) -> str | dict:
    """
    Crawl a web app URL, screenshot its pages, analyse them with Claude Vision,
    then build a matching Figma prototype.

    Args:
        url:                Web app URL to crawl (e.g. "http://localhost:5174/app/my-app/")
        stream_callback:    Optional fn(text) for progress updates
        max_pages:          Maximum number of pages to screenshot (default 12)
        nav_click_depth:    How many nav links to follow (default 2)
        extra_instructions: Additional natural-language instructions for the Figma build
        viewport_width:     Browser viewport width (default 1440)
        viewport_height:    Browser viewport height (default 900)
        project_name:       If set, screenshots are saved to
                            FigmaMockupGenerator/generated/figma-mockups/<project_name>/screenshots/

    Returns:
        {"result": "...", "figma_url": "..."} on success
        "ERROR:..." string on failure
    """
    emit = stream_callback or print

    # Resolve screenshots directory
    screenshots_dir: Optional[Path] = None
    if project_name:
        _fmc_root = Path(__file__).resolve().parent.parent.parent
        screenshots_dir = _fmc_root / "generated" / "figma-mockups" / project_name / "screenshots"

    # ── 1. Check MCP server ────────────────────────────────────────────────────
    emit("Connecting to Figma MCP server…")
    try:
        mcp_initialize()
        mcp_tools = mcp_list_tools()
    except ConnectionError as exc:
        return "ERROR:NO_MCP_SERVER"

    if not mcp_tools:
        return "ERROR:NO_TOOLS"

    emit(f"  {len(mcp_tools)} Figma tools available")

    # ── 2. Check Figma Desktop ─────────────────────────────────────────────────
    emit("Checking Figma Desktop connection…")
    try:
        state_raw = mcp_call_tool("figma_get_status", {})
        state = json.loads(state_raw) if isinstance(state_raw, str) else state_raw
    except Exception as exc:
        return f"ERROR:MCP_CALL_FAILED:{exc}"

    # If the relay isn't connected to the plugin, figma_get_status returns
    # {"error": "Relay not connected..."} with no "page" or "ready" keys.
    relay_error = state.get("error", "")
    if relay_error and "relay" in relay_error.lower():
        return "ERROR:RELAY_NOT_CONNECTED"

    connected = (
        state.get("ready") is True
        or state.get("relay_connected") is True
        or state.get("anyClientConnected") is True
        or (isinstance(state.get("clients"), list) and len(state["clients"]) > 0)
    )
    if not connected:
        if not state.get("page"):
            return "ERROR:NO_FIGMA_FILE"
        return "ERROR:BRIDGE_NOT_CONNECTED"

    page_name = state.get("page", "")
    emit(f"  Figma connected — page: '{page_name}'")

    # ── 3. Screenshot the web app (or load from discover cache) ───────────────
    pages = None
    pages_cache_data = None
    cache_file = screenshots_dir / ".discover_cache.json" if screenshots_dir else None

    if cache_file and cache_file.exists():
        try:
            import json as _json_mod
            cached = _json_mod.loads(cache_file.read_text(encoding="utf-8"))
            # Validate: same URL and cache is fresh (under 30 minutes old)
            from datetime import datetime, timezone
            cached_url = cached.get("url", "")
            cached_at_str = cached.get("cached_at", "")
            age_ok = False
            if cached_at_str:
                try:
                    cached_at = datetime.fromisoformat(cached_at_str.replace("Z", "+00:00"))
                    age_seconds = (datetime.now(timezone.utc) - cached_at).total_seconds()
                    age_ok = age_seconds < 1800  # 30 minutes
                except Exception:
                    pass
            if cached_url == url and age_ok and cached.get("pages"):
                n = len(cached["pages"])
                emit(f"[PHASE] Discover cache found ({n} page(s)) — re-extracting SVGs only (preserving tab sub-pages)")
                pages_cache_data = cached["pages"]
            else:
                reason = "URL mismatch" if cached_url != url else ("stale" if not age_ok else "empty")
                emit(f"[PHASE] Discover cache unusable ({reason}) — running full discovery")
        except Exception as e:
            emit(f"[PHASE] Could not load discover cache ({e}) — running full discovery")

    if pages is None:
        if pages_cache_data:
            emit(f"[PHASE] Re-extracting SVGs on {len(pages_cache_data)} cached page(s): {url}")
        else:
            emit(f"[PHASE] Screenshotting web app: {url}")
        if screenshots_dir:
            emit(f"  Screenshots will be saved to: {screenshots_dir}")
        try:
            pages = _take_screenshots(
                url,
                max_pages=max_pages,
                nav_click_depth=nav_click_depth,
                viewport={"width": viewport_width, "height": viewport_height},
                emit=emit,
                screenshots_dir=screenshots_dir,
                login_username=login_username,
                login_password=login_password,
                pages_cache=pages_cache_data,
            )
        except RuntimeError as exc:
            return f"ERROR:PLAYWRIGHT:{exc}"
        except Exception as exc:
            log.exception("Screenshot failed")
            return f"ERROR:SCREENSHOT_FAILED:{exc}"

    if not pages:
        return "ERROR:NO_PAGES_CAPTURED"

    # ── 4. Analyse screenshots with Claude Vision ──────────────────────────────
    emit(f"[PHASE] Analysing {len(pages)} page(s) with Claude Vision…")
    pages = _analyse_pages(pages, emit=emit)

    # ── 5. Build Figma prompt ──────────────────────────────────────────────────
    emit("\nBuilding Figma wireframe prompt…")
    figma_prompt = _build_figma_prompt(pages, url, extra_instructions)
    emit(f"  Prompt length: {len(figma_prompt)} chars, {len(pages)} screens")

    # ── 6. Run Figma agent loop ────────────────────────────────────────────────
    emit("[PHASE] Launching Figma build agent…")
    oai_tools = tools_to_openai(mcp_tools)
    client = get_openai_client()

    # Track which screens are expected so we can detect early stops
    expected_screens = [
        pg["title"] if (pg.get("is_tab_panel") or pg.get("is_prompt_response")) else ((pg.get("analysis") or {}).get("page_title") or pg["title"])
        for pg in pages
    ]
    emit(f"  Expecting {len(expected_screens)} screens: {', '.join(expected_screens)}")

    # Pre-delete any frames with the same names so Claude doesn't skip them
    emit("  Clearing any existing frames with matching names…")
    try:
        frames_raw = mcp_call_tool("figma_list_frames", {})
        frames_data = json.loads(frames_raw) if isinstance(frames_raw, str) else frames_raw
        existing = frames_data if isinstance(frames_data, list) else frames_data.get("frames", [])
        names_to_delete = {f.get("name", "") for f in existing} & set(expected_screens)
        for name in names_to_delete:
            try:
                mcp_call_tool("figma_delete_frame", {"name": name})
                emit(f"    Deleted existing frame: {name}")
            except Exception:
                pass
    except Exception:
        pass

    # Track frames created this run by watching figma_create_frame tool calls
    frames_built_this_run: set[str] = set()

    messages = [{"role": "user", "content": figma_prompt}]
    turn = 0
    consecutive_end_turns = 0

    while turn < MAX_TURNS:
        turn += 1
        log.info(f"Turn {turn} — calling Claude…")
        emit(f"\n[Turn {turn}] Thinking…")

        response = client.chat.completions.create(
            model=MODEL_ID,
            max_tokens=MAX_TOKENS,
            tools=oai_tools,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        )

        if hasattr(response, "usage") and response.usage:
            record_token_usage(
                _get_figma_run_id(),
                response.usage.prompt_tokens or 0,
                response.usage.completion_tokens or 0,
            )

        choice        = response.choices[0]
        msg           = choice.message
        finish_reason = choice.finish_reason

        # Add assistant message to history
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

        if msg.content and msg.content.strip():
            txt = msg.content.strip()
            emit(f"[Claude] {txt[:300]}{'…' if len(txt) > 300 else ''}")

        if finish_reason == "stop":
            consecutive_end_turns += 1

            # Use frames we watched being created this run — not the full canvas list
            missing = [s for s in expected_screens if s not in frames_built_this_run]

            if missing and consecutive_end_turns < 3:
                emit(f"\n⚠ Claude stopped early — {len(missing)} screen(s) not yet built: {', '.join(missing)}")
                emit("  Resuming build…")
                resume_prompt = (
                    f"You stopped before building all screens. "
                    f"The following screens are MISSING from the Figma canvas: {', '.join(missing)}. "
                    f"Please build them now using the same layout, colour scheme, and nav structure as the screens already created. "
                    f"Remember: use figma_create_chart for ALL chart types and figma_create_map for all maps. Never draw charts manually or use placeholder rectangles for charts/maps."
                )
                messages.append({"role": "user", "content": resume_prompt})
                continue

            # All screens present (or max retries reached) — run QA and return
            if missing:
                emit(f"\n⚠ Could not build all screens after retries. Missing: {', '.join(missing)}")
            else:
                emit(f"\n✓ All {len(expected_screens)} screens built — running QA pass…")

            qa_result = run_validation_pass(oai_tools, client, emit, messages)
            main_result = msg.content or "Done."
            figma_url = _fetch_figma_url(emit)
            return {
                "result": f"{main_result}\n\n--- QA ---\n{qa_result}",
                "figma_url": figma_url,
            }

        if finish_reason == "tool_calls":
            consecutive_end_turns = 0
            for tc in msg.tool_calls:
                tool_name   = tc.function.name
                tool_input  = json.loads(tc.function.arguments)
                tool_use_id = tc.id

                # Emit human-readable progress labels per tool
                if tool_name == "figma_create_frame":
                    frame_name = tool_input.get("name", "?")
                    frames_built_this_run.add(frame_name)
                    emit(f"\n🖼️  Creating screen: {frame_name} ({len(frames_built_this_run)}/{len(expected_screens)})")
                elif tool_name == "figma_create_auto_layout_frame":
                    frame_name = tool_input.get("name", "?")
                    emit(f"  📐 Layout frame: {frame_name}")
                elif tool_name == "figma_create_text":
                    txt = str(tool_input.get("characters", ""))[:50]
                    emit(f"  ✏️  Text: {txt}")
                elif tool_name == "figma_create_rectangle":
                    name = tool_input.get("name", "")
                    emit(f"  ▭  Rectangle: {name}" if name else "  ▭  Rectangle")
                elif tool_name == "figma_create_button":
                    emit(f"  🔘 Button: {tool_input.get('label', '?')}")
                elif tool_name == "figma_wire_all":
                    emit(f"  🔗 Wiring prototype links…")
                elif tool_name == "figma_set_prototype_start":
                    emit(f"  ▶️  Setting prototype start screen")
                elif tool_name == "figma_set_prototype_link":
                    src = tool_input.get("source_frame", "?")
                    dst = tool_input.get("target_frame", "?")
                    emit(f"  ↗  Link: {src} → {dst}")
                elif tool_name == "figma_audit_frame":
                    emit(f"  🔍 Auditing: {tool_input.get('frame_name', '?')}")
                elif tool_name == "figma_create_sidebar_nav":
                    emit(f"  📋 Sidebar nav for: {tool_input.get('frame_name', '?')}")
                elif tool_name == "figma_execute_js":
                    emit(f"  ⚙️  Running Figma JS…")
                else:
                    args_preview = ", ".join(
                        f"{k}={repr(v)[:30]}" for k, v in list(tool_input.items())[:2]
                    )
                    emit(f"  → {tool_name}({args_preview})")

                try:
                    result_text = mcp_call_tool(tool_name, tool_input)
                    try:
                        parsed = json.loads(result_text)
                        if isinstance(parsed, dict):
                            if "error" in parsed:
                                emit(f"    ✗ {parsed['error']}")
                            elif tool_name == "figma_wire_all":
                                wired   = parsed.get('wired', 0)
                                skipped = parsed.get('skipped', 0)
                                errors  = parsed.get('errors', [])
                                emit(f"    ✓ Wired {wired} links, skipped {skipped}" + (f", {len(errors)} failed" if errors else ""))
                                for err in errors[:5]:
                                    emit(f"      ✗ {err.get('from','?')} → {err.get('to','?')}: {err.get('error','unknown')}")
                            elif tool_name == "figma_audit_frame":
                                issues = parsed.get("issues", [])
                                if issues:
                                    emit(f"    ⚠ Issues: {', '.join(issues)}")
                                else:
                                    emit(f"    ✓ {parsed.get('frame', '?')} — clean")
                    except Exception:
                        pass
                except Exception as exc:
                    result_text = json.dumps({"error": str(exc)})
                    emit(f"    ✗ MCP error: {exc}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_use_id,
                    "content": result_text,
                })

    emit(f"\n⚠ Reached {MAX_TURNS} turns — running final QA pass…")
    qa_result = run_validation_pass(oai_tools, client, emit, messages)
    return {"result": f"Reached {MAX_TURNS} turns.\n\n--- QA ---\n{qa_result}", "figma_url": _fetch_figma_url(emit)}


# ── CLI entry ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Web App → Figma Wireframe Agent")
    parser.add_argument("url", nargs="?", help="Web app URL to screenshot and convert")
    parser.add_argument("--url", dest="url_flag", help="Web app URL (alternative to positional)")
    parser.add_argument("--max-pages", type=int, default=12, help="Max pages to capture (default 12)")
    parser.add_argument("--nav-clicks", type=int, default=2, help="Nav link click depth (default 2)")
    parser.add_argument("--instructions", default="", help="Extra instructions for the Figma build")
    parser.add_argument("--width",  type=int, default=1440, help="Viewport width (default 1440)")
    parser.add_argument("--height", type=int, default=900,  help="Viewport height (default 900)")
    args = parser.parse_args()

    target_url = args.url or args.url_flag
    if not target_url:
        parser.error("Provide a URL as positional arg or --url")

    result = run_agent(
        url=target_url,
        max_pages=args.max_pages,
        nav_click_depth=args.nav_clicks,
        extra_instructions=args.instructions,
        viewport_width=args.width,
        viewport_height=args.height,
    )

    if isinstance(result, dict):
        print(f"\n✓ Done. Figma URL: {result.get('figma_url', 'N/A')}")
        print(result.get("result", ""))
    else:
        print(f"\n✗ {result}", file=sys.stderr)
        sys.exit(1)
