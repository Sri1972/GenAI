"""
Figma Prototype Agent
---------------------
Builds a website from a Figma URL using the same approach as WebBuilder:
  1. Screenshot the Figma design (design/file URLs) or infer from name (make/proto)
  2. Send screenshots + prompt directly to LLM in ONE call
  3. LLM outputs multi-file HTML/CSS/JS (Tailwind CDN + Chart.js CDN)
  4. Files written to generated/<project>/ and served by a Python HTTP server

No React, no TypeScript, no build step — identical to WebBuilder approach.
The LLM sees the actual screenshots while writing code, giving maximum visual fidelity.
"""

import base64
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

from .llm import chat, build_vision_message

load_dotenv(Path(__file__).parent.parent.parent / ".env")

import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    project_url as _project_url, health_url as _health_url,
    HTML_PORT_START, WEB_APPS_DIR, HTML_PORTS_FILE as _HTML_PRT_FILE,
)

FIGMA_TOKEN = os.environ.get("FIGMA_ACCESS_TOKEN", "")

# HTML/Figma apps go into generated/web-apps/
GENERATED_DIR    = WEB_APPS_DIR
HTML_SERVER      = Path(__file__).parent / "html_server.py"

# Running HTML servers: project_name -> (process, port)
_html_servers: dict[str, tuple[subprocess.Popen, int]] = {}
_html_ports:   dict[str, int] = {}
_HTML_PORTS_FILE = _HTML_PRT_FILE


# ── URL helpers ────────────────────────────────────────────────────────────────

FIGMA_URL_RE = re.compile(
    r"https?://(?:www\.)?figma\.com/(file|proto|design|make)/([A-Za-z0-9_-]+)",
    re.IGNORECASE,
)

def is_figma_url(text: str) -> bool:
    return bool(FIGMA_URL_RE.search(text))

def is_make_or_proto(url: str) -> bool:
    m = FIGMA_URL_RE.search(url)
    return bool(m and m.group(1).lower() in ("make", "proto"))

def parse_figma_file_key(url: str) -> tuple[str, str]:
    m = FIGMA_URL_RE.search(url)
    if not m:
        raise ValueError(f"Cannot parse Figma file key from: {url}")
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    return m.group(2), qs.get("node-id", [""])[0]

def slug_from_url(url: str) -> str:
    m = re.search(r"figma\.com/(?:make|file|design|proto)/[^/]+/([^/?&#]+)", url)
    if m:
        slug = re.sub(r"[-_]+", " ", m.group(1))
        return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", slug).strip()
    return "Figma Design"

def _clean_figma_url(url: str) -> str:
    """Strip editor-mode params that force code view instead of prototype view.
    Do NOT convert URL types — use the URL as-is so the correct Figma view loads."""
    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)
    # Remove params that open code/editor mode instead of the rendered prototype
    for drop in ("fullscreen", "code-node-id"):
        qs.pop(drop, None)
    clean_query = urllib.parse.urlencode({k: v[0] for k, v in qs.items()})
    return urllib.parse.urlunparse(parsed._replace(query=clean_query))


# ── Playwright screenshots ─────────────────────────────────────────────────────

def take_screenshots(url: str, progress=None, max_shots: int = 30) -> list[str]:
    """Screenshot every page of a Figma design. Identical approach to WebBuilder."""
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    import shutil as _shutil, tempfile

    def _p(msg: str):
        if progress:
            safe = msg.encode("ascii", errors="replace").decode("ascii")
            progress(f"screenshot:{safe}")

    # Do NOT convert the URL — use it exactly as-is so WebBuilder-style session works
    url = _clean_figma_url(url)
    shots: list[str] = []
    edge_exe = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if not os.path.exists(edge_exe):
        edge_exe = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    edge_profile = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data")

    _p("Launching browser")

    with sync_playwright() as pw:
        if os.path.exists(edge_exe) and os.path.exists(edge_profile):
            tmp = tempfile.mkdtemp(prefix="turboui_edge_")
            try:
                src = os.path.join(edge_profile, "Default")
                dst = os.path.join(tmp, "Default")
                if os.path.isdir(src):
                    _shutil.copytree(src, dst,
                        ignore=_shutil.ignore_patterns(
                            "*.lock","Lock","LOCK","lockfile","SingletonLock",
                            "GPUCache","Code Cache","Cache",
                            "Cookies","Cookies-journal",
                            "Sessions","Session_*","Tabs_*","Safe Browsing*",
                        ), ignore_dangling_symlinks=True,
                    )
                _p("Using Edge session (logged-in Figma)")
                ctx = pw.chromium.launch_persistent_context(
                    user_data_dir=tmp, executable_path=edge_exe, headless=True,
                    args=["--no-sandbox","--disable-dev-shm-usage"],
                    viewport={"width": 1440, "height": 900},
                )
            except Exception:
                _shutil.rmtree(tmp, ignore_errors=True)
                _p("Edge failed, using headless Chromium")
                browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
                ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        else:
            _p("Using headless Chromium")
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
            ctx = browser.new_context(viewport={"width": 1440, "height": 900})

        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        _p(f"Loading {url[:60]}")

        try:
            page.goto(url, wait_until="networkidle", timeout=45000)
        except PWTimeout:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(8000)
            except Exception:
                page.wait_for_timeout(5000)

        # Dismiss overlays — same selectors as WebBuilder
        for sel in [
            "button:has-text('Continue without signing in')",
            "button:has-text('Continue as guest')",
            "button:has-text('Skip')",
            "button:has-text('Not now')",
            "[data-testid='close-button']",
            "button[aria-label='Close']",
        ]:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=2000):
                    btn.click()
                    page.wait_for_timeout(800)
            except Exception:
                pass

        # Wait for full render
        page.wait_for_timeout(4000)

        # ── Shot 1: full-page screenshot (captures everything including bottom buttons) ──
        try:
            buf = base64.b64encode(
                page.screenshot(full_page=True, type="png", timeout=60000)
            ).decode()
        except Exception:
            # Some Figma prototype players block full_page — fall back to viewport
            buf = base64.b64encode(
                page.screenshot(full_page=False, type="png", timeout=60000)
            ).decode()
        shots.append(buf)
        _p("Screenshot 1 captured (full page)")

        # ── Shots 2-N: click nav items to capture each screen ─────────────────
        # Track seen hashes to deduplicate — skip visually identical screenshots
        import hashlib
        def _hash(b64: str) -> str:
            return hashlib.md5(b64[:2000].encode()).hexdigest()

        seen_hashes: set[str] = {_hash(shots[0])}

        def _capture() -> str | None:
            """Take a screenshot, return base64 or None if capture fails."""
            try:
                return base64.b64encode(
                    page.screenshot(full_page=True, type="png", timeout=60000)
                ).decode()
            except Exception:
                try:
                    return base64.b64encode(
                        page.screenshot(full_page=False, type="png", timeout=60000)
                    ).decode()
                except Exception:
                    return None

        def _add_shot(buf: str, label: str) -> bool:
            """Add screenshot if it's new. Returns True if added."""
            h = _hash(buf)
            if h in seen_hashes:
                return False
            seen_hashes.add(h)
            shots.append(buf)
            _p(f"Screenshot {len(shots)} captured ({label})")
            return True

        # ── Click every nav/tab/menu item to capture each screen ──────────────
        clicked: set[str] = set()
        for selector in [
            "nav a", "nav button",
            "[role='navigation'] a", "[role='navigation'] button",
            "[class*='sidebar'] a", "[class*='sidebar'] button",
            "[class*='nav'] a", "[class*='nav'] button",
            "[class*='tab'] button", "[class*='menu'] a",
        ]:
            items = page.locator(selector).all()
            if len(items) < 2:
                continue
            for item in items:
                if len(shots) >= max_shots:
                    _p(f"Reached max_shots limit ({max_shots}) — stopping")
                    break
                try:
                    href = item.get_attribute("href") or ""
                    if href.startswith("http") and "figma.com" not in href: continue
                    if any(x in href for x in ["developers", "help", "community", "careers"]): continue
                    label = (item.text_content(timeout=1000) or "").strip()[:40]
                    if not label or label in clicked: continue
                    clicked.add(label)
                    item.scroll_into_view_if_needed(timeout=2000)
                    item.click(timeout=3000)
                    page.wait_for_timeout(2000)
                    buf = _capture()
                    if buf:
                        _add_shot(buf, label)
                except Exception:
                    pass
            break

        # ── Scroll-based capture for pages with no nav (single long page) ─────
        if len(shots) == 1:
            try:
                total_height = page.evaluate(
                    "Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)"
                )
                viewport_h = 900
                scroll_pos = viewport_h
                while scroll_pos < total_height and len(shots) < max_shots:
                    page.evaluate(f"window.scrollTo(0, {scroll_pos})")
                    page.wait_for_timeout(1000)
                    buf = _capture()
                    if buf:
                        _add_shot(buf, f"scroll-{scroll_pos}px")
                    scroll_pos += viewport_h
            except Exception:
                pass

        ctx.close()
    return shots


# ── WebBuilder-style system prompt ────────────────────────────────────────────

_VISION_SYSTEM_PROMPT = """You are an expert frontend developer and UX designer.
You are given screenshots of DIFFERENT PAGES/SCREENS from a Figma design.
Each screenshot shows a separate page or view in the application.

╔══════════════════════════════════════════════════════════════════╗
║  HARD RULES — non-negotiable, enforced by post-processor         ║
╠══════════════════════════════════════════════════════════════════╣
║  DATA  : NEVER create data/app.json.                             ║
║          Create ONE file per entity: data/inventory.json,        ║
║          data/sales.json, data/forecast.json, data/teams.json …  ║
║          Each file is a JSON ARRAY of records (8-15 rows).       ║
║                                                                  ║
║  API   : ALL data access through js/api.js (IIFE module).        ║
║          app.js NEVER calls fetch() directly.                    ║
║          One function per entity, supports q/filter params.      ║
║                                                                  ║
║  CHARTS: D3.js v7 ONLY. ZERO Chart.js. ZERO <canvas> elements.  ║
║          All chart code in js/charts.js.                         ║
║          Load order: D3 CDN → charts.js → api.js → app.js       ║
║          EVERY chart MUST have hover tooltips using a shared     ║
║          _tip object (position:fixed, clientX/clientY). Bars,    ║
║          dots, and slices must show label+value on mouseover.    ║
║                                                                  ║
║  JS    : NEVER put <script> or </script> inside .js files.       ║
╚══════════════════════════════════════════════════════════════════╝

Your job: implement this as a fully working, multi-page HTML website that matches
the Figma design as closely as possible.

## Output format — STRICT multi-file
Output EXACTLY this structure. Files separated by === path === markers.

TITLE: <short page title>
PROJECT: <kebab-case-folder-name>
---
=== index.html ===
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>...</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
  <link rel="stylesheet" href="css/styles.css">
</head>
<body>
  ...
  <script src="js/router.js"></script>
  <script src="js/api.js"></script>
  <script src="js/charts.js"></script>
  <script src="js/app.js"></script>
</body>
</html>

=== css/styles.css ===
/* Custom styles only */

=== js/router.js ===
function showPage(id) {
  document.querySelectorAll('.screen').forEach(function(s){ s.style.display = 'none'; });
  var el = document.getElementById(id);
  if (el) el.style.display = 'flex';
  if (window._onPageShow) window._onPageShow(id);
}
document.addEventListener('DOMContentLoaded', function() {
  showPage('<first-screen-id>');
});

=== js/api.js ===
// IIFE data module — one function per entity, reads from data/*.json

=== js/charts.js ===
// D3.js v7 chart helpers — shared tooltip + renderBarChart, renderLineChart, renderDonutChart
// Shared tooltip (position:fixed so it works across SVG boundaries)
var _tip = (function(){
  var el = document.createElement('div');
  el.style.cssText = 'position:fixed;background:rgba(15,20,40,0.92);color:#fff;padding:7px 13px;'
    + 'border-radius:6px;font-size:13px;pointer-events:none;opacity:0;transition:opacity .15s;z-index:9999;';
  document.body.appendChild(el);
  return {
    show: function(html, event){ el.innerHTML=html; el.style.opacity=1; _tip.move(event); },
    move: function(event){ el.style.left=(event.clientX+14)+'px'; el.style.top=(event.clientY-40)+'px'; },
    hide: function(){ el.style.opacity=0; }
  };
})();
// Wire tooltips on every bar/dot/slice:
//   .on('mouseover', function(event,d){ _tip.show('<b>'+d.label+'</b><br>'+d.value, event); })
//   .on('mousemove', function(event){ _tip.move(event); })
//   .on('mouseout',  function(){ _tip.hide(); })

=== js/app.js ===
// Entry point — non-chart data loads at DOMContentLoaded; charts load via _onPageShow
document.addEventListener('DOMContentLoaded', function() {
  AppNameAPI.getTeams().then(function(teams) { renderTable('teams-table', teams); });
});
// D3 charts MUST be in _onPageShow — hidden sections have clientWidth===0 at DOMContentLoaded
window._onPageShow = function(pageId) {
  if (pageId === 'sales-overview') {
    AppNameAPI.getSales().then(function(data) { renderBarChart('sales-chart', data, {xKey:'month',yKey:'units'}); });
  }
};

=== data/teams.json ===
[ ... ]

## Rules — follow exactly
- ALWAYS emit: index.html, css/styles.css, js/router.js, js/api.js, js/charts.js, js/app.js
- ALL JavaScript in js/ files — NO inline <script> blocks in HTML
- ALL custom CSS in css/styles.css — NO inline <style> in HTML
- ALL data in data/*.json — NO arrays embedded in JS — each file is a JSON ARRAY
- Multi-page: js/router.js shows ONE section at a time, hides others via showPage()
- Each page = one <section id="page-name" class="screen"> in index.html
- Nav clicks call showPage('page-name') from router.js
- Default page shown on load = first nav item (called inside DOMContentLoaded)
- CRITICAL: D3 chart render calls MUST be inside window._onPageShow, NOT DOMContentLoaded
  Hidden sections have clientWidth===0; charts render blank if called before the section is visible
- Tables and non-chart data (no width dependency) can load at DOMContentLoaded
- All charts, dropdowns, tables, filters MUST work in JS
- NEVER output prose — only the === file === blocks

## Visual fidelity rules
- Match the EXACT color palette from the screenshots (use hex values in CSS variables)
- Match layout: sidebar width, header height, card grid columns, spacing
- Match typography: font sizes, weights
- Match every nav item label exactly as shown
- Implement charts with D3.js v7 matching the chart types shown (bar/line/pie/donut) — NO Chart.js
- Implement tables with exact column headers visible in screenshots
- Implement all dropdowns, filters, search inputs shown
- Use realistic data matching the domain (real team/player names etc.)
- NEVER stack all pages — only ONE visible at a time
"""

_INFERENCE_SYSTEM_PROMPT = """You are an expert frontend developer and UX designer.
Build a complete, professional website based on the Figma project name and description.

╔══════════════════════════════════════════════════════════════════╗
║  HARD RULES — DATA: one JSON array file per entity, never        ║
║  data/app.json.  API: js/api.js IIFE module, no fetch in app.js. ║
║  CHARTS: D3.js v7 only — zero Chart.js, zero <canvas>.           ║
╚══════════════════════════════════════════════════════════════════╝

## Output format — STRICT multi-file
Output EXACTLY this structure. Files separated by === path === markers.

TITLE: <short page title>
PROJECT: <kebab-case-folder-name>
---
=== index.html ===
=== css/styles.css ===
=== js/router.js ===
=== js/api.js ===
=== js/charts.js ===
=== js/app.js ===
=== data/<entity1>.json ===
=== data/<entity2>.json ===

## Rules
- ALL JavaScript in js/ files — NO inline <script> in HTML
- ALL custom CSS in css/styles.css
- ALL data in data/*.json — one JSON array per entity, 8-15 rows
- Multi-page: ONE section visible at a time, nav switches between them via showPage()
- router.js MUST call window._onPageShow(id) inside showPage() after making section visible
- CRITICAL: D3 chart render calls MUST be inside window._onPageShow in app.js, NOT DOMContentLoaded
  Hidden sections have clientWidth===0; charts render blank if called before the section is visible
- Tables, KPI cards, non-chart content can load at DOMContentLoaded
- Use Tailwind CDN + D3.js v7 CDN (https://cdn.jsdelivr.net/npm/d3@7) — NO Chart.js
- Realistic data, fully working interactions
- Professional design matching the project's domain
"""


# ── Multi-file parser (same as WebBuilder) ────────────────────────────────────

def _parse_multifile(response: str) -> tuple[str, str, dict[str, str]]:
    text  = response.strip()
    title = "Prototype"
    slug  = ""

    header_m = re.match(
        r"TITLE:\s*(.+?)\n(?:PROJECT:\s*(.+?)\n)?-{3,}\n(.*)",
        text, re.DOTALL | re.IGNORECASE,
    )
    if header_m:
        title = header_m.group(1).strip()
        slug  = header_m.group(2).strip() if header_m.group(2) else ""
        text  = header_m.group(3).strip()

    FILE_PATH_RE = re.compile(r"={3}\s*([\w][\w\-./]*\.\w+)\s*={3}")
    file_matches = list(FILE_PATH_RE.finditer(text))
    files: dict[str, str] = {}
    if file_matches:
        for idx, m in enumerate(file_matches):
            path    = m.group(1).strip().lstrip("/")
            start   = m.end()
            end     = file_matches[idx+1].start() if idx+1 < len(file_matches) else len(text)
            content = text[start:end].strip()
            content = re.sub(r"^```[a-zA-Z]*\n?", "", content)
            content = re.sub(r"\n?```$", "", content)
            files[path] = content.strip()
    else:
        fenced = re.search(r"```(?:html)?\n(.*?)```", text, re.DOTALL)
        files["index.html"] = fenced.group(1).strip() if fenced else text

    if not slug:
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "prototype"
    files = _enforce_rules(files)
    return title, slug, files


def _enforce_rules(files: dict) -> dict:
    # server.py calls agents.figma_to_web_using_api_agent._enforce_rules on the
    # merged files after _parse_multifile returns, so no need to duplicate it here.
    return files


# ── HTML server (Python HTTP, no npm/Vite) ────────────────────────────────────

def _load_html_ports() -> dict:
    if _HTML_PORTS_FILE.exists():
        try: return json.loads(_HTML_PORTS_FILE.read_text())
        except: pass
    return {}

def _save_html_ports():
    _HTML_PORTS_FILE.write_text(json.dumps(_html_ports, indent=2))

_html_ports.update(_load_html_ports())

def _next_html_port() -> int:
    used = set(_html_ports.values())
    port = HTML_PORT_START
    while port in used:
        port += 1
    return port

def _wait_for_port(port: int, timeout: int = 15) -> bool:
    """Wait for the HTML server's /_health endpoint to respond."""
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(_health_url(port, "html"), timeout=1) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False

def kill_figma_server(project_name: str, forget_port: bool = False):
    entry = _html_servers.pop(project_name, None)
    if entry:
        proc, port = entry
        try: proc.terminate(); proc.wait(timeout=5)
        except Exception:
            try: proc.kill()
            except: pass
    if forget_port:
        _html_ports.pop(project_name, None)
        _save_html_ports()

def start_figma_project(project_name: str) -> dict:
    project_dir = GENERATED_DIR / project_name
    if not project_dir.exists():
        raise RuntimeError(f"Project '{project_name}' not found")

    # If already running and port is listening, return immediately
    if project_name in _html_servers:
        _, port = _html_servers[project_name]
        if _wait_for_port(port, timeout=1):
            return {"projectName": project_name, "port": port,
                    "url": "/figma-app/" + project_name + "/"}

    # Get port from memory → html_ports file → registry → assign new
    port = _html_ports.get(project_name)
    if not port:
        try:
            # Read from the shared web-apps registry if it exists
            import json as _j
            from config import REGISTRY_FILE
            if REGISTRY_FILE.exists():
                reg = _j.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
                port = reg.get(project_name, {}).get("port")
        except Exception:
            pass
    if not port:
        port = _next_html_port()

    _html_ports[project_name] = port
    _save_html_ports()

    # Persist port to the shared registry
    try:
        import json as _j
        from config import REGISTRY_FILE
        reg = _j.loads(REGISTRY_FILE.read_text(encoding="utf-8")) if REGISTRY_FILE.exists() else {}
        entry = reg.get(project_name, {})
        entry.update({"port": port, "type": "html"})
        reg[project_name] = entry
        REGISTRY_FILE.write_text(_j.dumps(reg, indent=2), encoding="utf-8")
    except Exception:
        pass

    proc = subprocess.Popen(
        [sys.executable, str(HTML_SERVER), str(GENERATED_DIR), str(port)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    _html_servers[project_name] = (proc, port)
    _wait_for_port(port, timeout=15)
    return {"projectName": project_name, "port": port,
            "url": "/figma-app/" + project_name + "/"}

def is_figma_project(project_name: str) -> bool:
    """True if this project is an HTML project (from Figma agent), not React/Vite."""
    project_dir = GENERATED_DIR / project_name
    return (project_dir / "index.html").exists() and not (project_dir / "package.json").exists()


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_from_figma(
    figma_url: str,
    prompt: str = "",
    progress=None,
    project_name_override: str | None = None,
) -> dict:
    """
    Build a website from a Figma URL using the WebBuilder approach:
    screenshots (when available) + single LLM call → HTML/CSS/JS files → Python HTTP server.

    Modes:
      design/file URL  → screenshots + LLM → HTML output
      make/proto URL   → name inference + LLM → HTML output (screenshots blocked by Figma CDN)
      any URL + prompt → above + user instructions applied
    """
    def _p(msg: str):
        if progress:
            safe = msg.encode("ascii", errors="replace").decode("ascii")
            progress(safe)

    design_name = slug_from_url(figma_url)

    # ── Step 1: Screenshots ────────────────────────────────────────────────────
    shots: list[str] = []
    try:
        _p("screenshot_start")
        shots = take_screenshots(figma_url, progress=progress)
        _p(f"screenshot_done:{len(shots)}")
    except Exception as exc:
        _p(f"screenshot_warn:Screenshot failed ({exc.__class__.__name__}) - building from name+prompt")

    # ── Step 2: Single LLM call (Claude via LiteLLM) → HTML/CSS/JS ───────────
    _p("llm")
    _p("llm_codegen:Building website from Figma design")

    if shots:
        # Vision mode: build message with text + images for Claude
        intro = f'Figma design: "{design_name}"\n'
        if prompt.strip():
            intro += f"Additional instructions: {prompt}\n"
        intro += (
            f"\n{len(shots)} screenshot(s) follow. Each shows a DIFFERENT PAGE of the app. "
            "Implement ALL pages with working sidebar/nav routing. "
            "Match the visual design exactly — colors, layout, components."
        )
        # Add page labels between images
        text_parts = [intro]
        for i in range(len(shots)):
            text_parts.append(f"[Page {i+1} of {len(shots)}]")

        # Build Claude vision message: interleave text + images (OpenAI format)
        content: list[dict] = [{"type": "text", "text": intro}]
        for i, b64 in enumerate(shots):
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            })
            content.append({"type": "text", "text": f"[Page {i+1} of {len(shots)}]"})

        raw = chat(
            messages=[{"role": "user", "content": content}],
            system=_VISION_SYSTEM_PROMPT,
            max_tokens=32000,
            temperature=0.2,
        )
    else:
        # No screenshots — build from name + prompt
        user_text = f'Figma project: "{design_name}"\nURL: {figma_url}\n'
        if prompt.strip():
            user_text += f"\nUser description:\n{prompt}\n"
        else:
            user_text += (
                "\nNo screenshots available. Based on the project name, build a professional, "
                "fully working website. Infer appropriate pages, components, and data from the name."
            )

        raw = chat(
            messages=[{"role": "user", "content": user_text}],
            system=_INFERENCE_SYSTEM_PROMPT,
            max_tokens=32000,
            temperature=0.3,
        )
    title, slug, files = _parse_multifile(raw)

    if not files.get("index.html") or "<!DOCTYPE" not in files.get("index.html", ""):
        raise RuntimeError(
            f"LLM did not return valid HTML. Response started with: {raw[:200]}"
        )

    # ── Step 3: Resolve project name ──────────────────────────────────────────
    # project_name_override ALWAYS wins — it is what the user named the project.
    # The LLM-generated slug is only a fallback when no override is given.
    if project_name_override:
        project_name = re.sub(r"[^a-z0-9-]", "-", project_name_override.lower()).strip("-") or "prototype"
    else:
        project_name = re.sub(r"[^a-z0-9-]", "-", slug.lower()).strip("-") or "prototype"

    project_dir = GENERATED_DIR / project_name
    project_dir.mkdir(parents=True, exist_ok=True)

    # ── Save screenshots into project folder FIRST ────────────────────────────
    # Always create the screenshots dir, even if no shots (useful as an indicator)
    screenshots_dir = project_dir / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)
    if shots:
        try:
            import base64 as _b64
            safe_name = re.sub(r"[^a-z0-9-]", "-", design_name.lower())[:40]
            saved = []
            for i, shot in enumerate(shots, start=1):
                filename = f"{safe_name}__page{i:02d}.png"
                filepath = screenshots_dir / filename
                filepath.write_bytes(_b64.b64decode(shot))
                saved.append(filename)
            _p(f"screenshot:Saved {len(saved)} screenshot(s) to {project_name}/screenshots/")
            for fn in saved:
                _p(f"screenshot:  {fn}")
        except Exception as ss_exc:
            _p(f"screenshot:Could not save screenshots: {ss_exc.__class__.__name__}")
    else:
        _p(f"screenshot:No screenshots captured (make/proto URL or screenshot failed)")

    # ── Write generated HTML/CSS/JS/data files ────────────────────────────────
    from agents.uigen_agent import _repair_json
    from agents.sanitize_js import sanitize
    for rel_path, content_str in files.items():
        fp = project_dir / rel_path
        fp.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content_str, list):
            content_str = "\n".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content_str
            )
        if not content_str or not content_str.strip():
            continue
        if rel_path.endswith(".json"):
            content_str = _repair_json(content_str, rel_path)
        content_str = sanitize(content_str, rel_path)
        fp.write_text(content_str, encoding="utf-8")

    # ── Step 4: Start Python HTTP server ──────────────────────────────────────
    _p("start")
    kill_figma_server(project_name)
    port = _html_ports.get(project_name) or _next_html_port()
    _html_ports[project_name] = port
    _save_html_ports()

    proc = subprocess.Popen(
        [sys.executable, str(HTML_SERVER), str(GENERATED_DIR), str(port)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    _html_servers[project_name] = (proc, port)
    _wait_for_port(port, timeout=15)

    url = "/figma-app/" + project_name + "/"
    _p("ready")

    return {
        "projectName":     project_name,
        "title":           title,
        "description":     f"Figma prototype: {design_name}",
        "port":            port,
        "url":             url,
        "files":           list(files.keys()),
        "type":            "html",
        "screenshotsDir":  str(screenshots_dir),
        "screenshotCount": len(shots),
    }
