#!/usr/bin/env python3
"""
figma_to_webapp.py
==================
Exports every frame from a Figma file via the Figma REST API,
saves them as clean descriptive PNG screenshots, then feeds them
to TurboUIGen's LLM to generate a fully interactive React/HTML web app.

Screenshot filenames follow the pattern:
    <project-slug>__<screen-index>__<frame-name-slug>.png
  e.g.
    sports-app__01__dashboard.png
    sports-app__02__players.png
    sports-app__03__match-detail.png

Usage:
    python figma_to_webapp.py "https://www.figma.com/design/ABC123/My-Sports-App"
    python figma_to_webapp.py <url> --prompt "Dark theme, mobile-first"
    python figma_to_webapp.py <url> --screenshots-only   # just export PNGs, don't generate app
    python figma_to_webapp.py <url> --scale 2            # 2x resolution (default 1)
"""

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from config import project_url as _project_url, WEB_APPS_DIR, FIGMA_MOCKUPS_DIR

# ── Brand tokens for CSS variable injection ────────────────────────────────────
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
try:
    from config_ds import DS_TOKENS_FILE as _DS_TOKENS_FILE
    import json as _json
    _TOKENS: dict = _json.loads(_DS_TOKENS_FILE.read_text(encoding="utf-8")) if _DS_TOKENS_FILE.exists() else {}
except Exception:
    _TOKENS = {}

def _brand_css_section() -> str:
    """Return a CSS variable + style guide section derived from brand_tokens.json."""
    if not _TOKENS:
        return ""
    u  = _TOKENS.get("usage", {})
    c  = _TOKENS.get("colors", {})
    sp = _TOKENS.get("spacing", {})
    r  = _TOKENS.get("radius", {})
    co = _TOKENS.get("components", {})
    ty = _TOKENS.get("typography", {})
    sem = c.get("semantic", {})
    brand = _TOKENS.get("brand", "Mobility Global")

    return f"""

## Mobility Global Brand Tokens — apply to css/styles.css
This is the {brand} design system. Apply these tokens so the generated app
matches the brand. Add the following :root block at the TOP of css/styles.css:

```css
:root {{
  /* Page */
  --bg:           {u.get('page_background','#EFEFE5')};
  --header-bg:    {u.get('header_background','#FFFFFF')};
  --sidebar-bg:   {u.get('sidebar_background','#FFFFFF')};
  --card-bg:      {u.get('card_background','#FFFFFF')};
  /* Text */
  --text:         {u.get('primary_text','#132445')};
  --text-2:       {u.get('secondary_text','#374151')};
  --text-muted:   {u.get('muted_text','#9CA3AF')};
  /* Brand */
  --blue:         {u.get('primary_button','#0064D2')};
  --blue-mist:    {u.get('hover_bg','#B8EAF5')};
  --nav-active-bg:{u.get('active_nav_bg','#EBF3FF')};
  --brand-dark:   {u.get('brand_dark','#132445')};
  /* Borders */
  --border:       {u.get('border','#E5E7EB')};
  /* Semantic */
  --success:      {sem.get('success','#059669')};
  --success-bg:   {sem.get('success_bg','#D1FAE5')};
  --warning:      {sem.get('warning','#D97706')};
  --warning-bg:   {sem.get('warning_bg','#FDEBB3')};
  --error:        {sem.get('error','#DC2626')};
  --error-bg:     {sem.get('error_bg','#FEE2E2')};
  /* Sizes */
  --header-h:     {co.get('header_height',64)}px;
  --sidebar-w:    {co.get('sidebar_width',240)}px;
  --radius-sm:    {r.get('sm',4)}px;
  --radius-md:    {r.get('md',8)}px;
  --radius-lg:    {r.get('lg',12)}px;
}}

body {{
  font-family: '{ty.get('heading_font','Inter')}', sans-serif;
  background: var(--bg);
  color: var(--text);
  margin: 0;
}}
```

Use these CSS variables throughout css/styles.css and inline styles.
For example:
  - Page/body background:  background: var(--bg)
  - Cards:                 background: var(--card-bg); border: 1px solid var(--border); border-radius: var(--radius-lg)
  - Sidebar:               background: var(--sidebar-bg); width: var(--sidebar-w)
  - Header:                background: var(--header-bg); height: var(--header-h)
  - Primary buttons:       background: var(--blue); color: #fff; border-radius: var(--radius-md)
  - Active nav items:      background: var(--nav-active-bg); color: var(--blue)
  - Status badges (green): background: var(--success-bg); color: var(--success)
  - Status badges (amber): background: var(--warning-bg); color: var(--warning)
  - Status badges (red):   background: var(--error-bg);   color: var(--error)

Typography sizes (use in CSS font-size):
  H1: {ty.get('sizes',{}).get('h1',32)}px  H2: {ty.get('sizes',{}).get('h2',24)}px  H3: {ty.get('sizes',{}).get('h3',20)}px
  Body: {ty.get('sizes',{}).get('body',14)}px  Caption: {ty.get('sizes',{}).get('caption',11)}px
"""

FIGMA_TOKEN = os.environ.get("FIGMA_ACCESS_TOKEN", "")
MODEL_ID    = os.environ.get("LITELLM_SONNET_46_MODEL", "claude-sonnet-4-6")

# Screenshots land inside the web-app project folder: web-apps/<project>/screenshots/
# SCREENSHOTS_DIR is the base; actual per-project dir is set in run() as project_screenshots_dir
SCREENSHOTS_DIR = WEB_APPS_DIR   # base — individual project subdirs created per-run
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# Generated web apps → generated/web-apps/
GENERATED_DIR = WEB_APPS_DIR


# ── Figma REST API helpers ─────────────────────────────────────────────────────

def _figma_get(path: str) -> dict:
    """Make an authenticated GET request to the Figma REST API."""
    if not FIGMA_TOKEN:
        raise RuntimeError("FIGMA_ACCESS_TOKEN not set in .env")
    url = f"https://api.figma.com/v1{path}"
    req = urllib.request.Request(url, headers={"X-Figma-Token": FIGMA_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"Figma API {e.code} on {path}: {body[:200]}")


def parse_figma_url(url: str) -> tuple[str, str]:
    """
    Extract (file_key, node_id) from any Figma URL.
    node_id may be '' if not specified.
    """
    m = re.search(
        r"figma\.com/(?:file|design|proto|make)/([A-Za-z0-9_-]+)",
        url, re.IGNORECASE,
    )
    if not m:
        raise ValueError(f"Cannot parse Figma file key from URL: {url}")
    file_key = m.group(1)
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    node_id = qs.get("node-id", [""])[0].replace("-", ":")
    return file_key, node_id


def slug(text: str) -> str:
    """Convert any string to a safe lowercase kebab-case slug."""
    text = re.sub(r"[^a-zA-Z0-9\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text.strip())
    return text.lower()[:50]


# ── Step 1: Discover frames ────────────────────────────────────────────────────

def get_top_frames(file_key: str) -> list[dict]:
    """
    Return all top-level FRAME nodes on all pages, with id, name, page.
    These are the 'screens' of the design.
    """
    print("  Fetching file structure from Figma API…")
    data = _figma_get(f"/files/{file_key}?depth=2")

    file_name = data.get("name", "Figma Design")
    frames = []

    for page in data.get("document", {}).get("children", []):
        page_name = page.get("name", "Page")
        for node in page.get("children", []):
            if node.get("type") == "FRAME":
                bbox = node.get("absoluteBoundingBox") or {}
                frames.append({
                    "id":        node["id"],
                    "name":      node["name"],
                    "page":      page_name,
                    "file_name": file_name,
                    "width":     bbox.get("width", 0),
                    "height":    bbox.get("height", 0),
                })

    print(f"  Found {len(frames)} frames across {len(data.get('document',{}).get('children',[]))} page(s)")
    return frames, file_name


# ── Step 2: Export frame screenshots via Figma REST API ───────────────────────

def export_frame_screenshots(
    file_key: str,
    frames: list[dict],
    project_slug_name: str,
    scale: float = 1,
    fmt: str = "jpg",
    screenshots_dir: Path = None,    # if None, falls back to global SCREENSHOTS_DIR
) -> list[dict]:
    """
    Export each frame as JPEG via the Figma /images endpoint.
    Saves files as: <screenshots_dir>/<project>__<nn>__<frame-name>.jpg

    Returns list of dicts with: frame info + local_path + base64_data
    """
    if not frames:
        return []

    out_dir = screenshots_dir or SCREENSHOTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build comma-separated node IDs for batch export
    node_ids = ",".join(f["id"] for f in frames)
    encoded_ids = urllib.parse.quote(node_ids, safe="")

    print(f"  Requesting export URLs from Figma for {len(frames)} frames…")
    export_data = _figma_get(
        f"/images/{file_key}?ids={encoded_ids}&scale={scale}&format={fmt}"
    )

    images_map = export_data.get("images", {})
    if not images_map:
        raise RuntimeError("Figma returned no image URLs. Check file key and token.")

    results = []
    for idx, frame in enumerate(frames, start=1):
        node_id  = frame["id"]
        img_url  = images_map.get(node_id)
        if not img_url:
            print(f"  ⚠ No image URL for frame '{frame['name']}' — skipping")
            continue

        # Descriptive filename: project__01__dashboard.png
        frame_slug = slug(frame["name"])
        filename   = f"{project_slug_name}__{idx:02d}__{frame_slug}.{fmt}"
        local_path = out_dir / filename

        print(f"  Downloading {filename}…")
        try:
            req = urllib.request.Request(img_url)
            with urllib.request.urlopen(req, timeout=60) as resp:
                img_bytes = resp.read()
            local_path.write_bytes(img_bytes)
            b64 = base64.b64encode(img_bytes).decode()
            results.append({
                **frame,
                "local_path":  str(local_path),
                "filename":    filename,
                "base64_data": b64,
                "index":       idx,
            })
            print(f"  ✓ Saved: {filename}")
        except Exception as e:
            print(f"  ✗ Failed to download {filename}: {e}")

    return results


# ── Step 3: Extract REAL prototype wiring from Figma file tree ────────────────

def extract_prototype_links(file_key: str, frames: list[dict]) -> dict:
    """
    Fetch the full Figma file tree and extract every prototype reaction
    (ON_CLICK, ON_HOVER, etc.) from every node, resolving destination IDs
    to human-readable frame names.

    Returns a structured wiring map:
    {
        "Dashboard": [
            {
                "node_name":   "tab-Players-on-Dashboard",
                "node_type":   "FRAME",
                "trigger":     "ON_CLICK",
                "action":      "NAVIGATE",
                "destination": "Players"
            },
            ...
        ],
        "Players": [ ... ],
    }

    Also returns a flat list of all links for easy reference.
    """
    print("  Fetching full file tree for prototype link extraction…")

    # depth=5 reaches: page → frame → section → nav-bar → button → text
    # That covers all typical nav tab / button nesting depths
    data = _figma_get(f"/files/{file_key}?depth=5")

    # ── Build lookup tables ───────────────────────────────────────────────────
    # node_id → node_name
    id_to_name: dict[str, str] = {}
    # node_id → top-level frame name (which screen contains this node)
    id_to_frame: dict[str, str] = {}

    def index_nodes(node: dict, current_frame: str):
        nid  = node.get("id", "")
        name = node.get("name", "")
        if nid:
            id_to_name[nid]  = name
            id_to_frame[nid] = current_frame

        # If this IS a top-level frame, it becomes the current_frame for children
        is_top_frame = node.get("type") == "FRAME" and current_frame == ""
        child_frame  = name if is_top_frame else current_frame

        for child in node.get("children", []):
            index_nodes(child, child_frame)

    for page in data.get("document", {}).get("children", []):
        for child in page.get("children", []):
            index_nodes(child, "")

    # ── Walk tree and collect reactions ──────────────────────────────────────
    wiring: dict[str, list[dict]] = {f["name"]: [] for f in frames}
    all_links: list[dict] = []

    def collect_reactions(node: dict, parent_frame: str):
        nid        = node.get("id", "")
        node_name  = node.get("name", "")
        node_type  = node.get("type", "")
        frame_name = id_to_frame.get(nid, parent_frame)

        for reaction in node.get("reactions", []):
            trigger = reaction.get("trigger", {})
            # Handle both old (action) and new (actions array) Figma formats
            actions = reaction.get("actions", [])
            if not actions and reaction.get("action"):
                actions = [reaction["action"]]

            for action in actions:
                dest_id   = action.get("destinationId") or action.get("destination", {}).get("id", "")
                nav_type  = action.get("navigation", action.get("type", "NAVIGATE"))
                dest_name = id_to_name.get(dest_id, dest_id)

                # Only include links where destination is a known top-level frame
                known_frames = {f["name"] for f in frames}
                if dest_name not in known_frames:
                    continue

                link = {
                    "node_name":   node_name,
                    "node_type":   node_type,
                    "node_id":     nid,
                    "trigger":     trigger.get("type", "ON_CLICK"),
                    "action":      nav_type,
                    "destination": dest_name,
                    "source_frame": frame_name,
                }
                if frame_name in wiring:
                    # Avoid duplicates
                    if not any(
                        x["node_name"] == node_name and x["destination"] == dest_name
                        for x in wiring[frame_name]
                    ):
                        wiring[frame_name].append(link)
                all_links.append(link)

        for child in node.get("children", []):
            child_frame = frame_name if frame_name else parent_frame
            collect_reactions(child, child_frame)

    for page in data.get("document", {}).get("children", []):
        for child in page.get("children", []):
            collect_reactions(child, "")

    # ── Summary ───────────────────────────────────────────────────────────────
    total = sum(len(v) for v in wiring.values())
    print(f"  Found {total} prototype reaction(s) in Figma file")

    # ── Fallback: infer wiring from node naming conventions ──────────────────
    # Even if setReactionsAsync was never called / not synced, the node names
    # we baked in encode the navigation:
    #   tab-{Target}-on-{Source}  →  NAVIGATE to Target
    #   {action}-btn-{Source}     →  NAVIGATE to best-matching screen
    #   {name}-modal / -drawer    →  OVERLAY target
    if total == 0:
        print("  No reactions in file — inferring wiring from node naming convention…")
        known_frames = {f["name"] for f in frames}

        # Build slug → real name map for fuzzy matching
        # e.g. "MatchDetail" → "Match Detail", "Players" → "Players"
        def name_to_slug(n): return re.sub(r"[\s_-]+", "", n).lower()
        slug_to_frame = {name_to_slug(f): f for f in known_frames}

        def resolve_target(raw_target: str) -> str:
            """Match a raw target string to a known frame name."""
            # Exact match first
            if raw_target in known_frames:
                return raw_target
            # Slug match (removes spaces/dashes)
            s = name_to_slug(raw_target)
            if s in slug_to_frame:
                return slug_to_frame[s]
            # Partial match
            for fname in known_frames:
                if s in name_to_slug(fname) or name_to_slug(fname) in s:
                    return fname
            return ""

        def infer_from_nodes(node: dict, source_frame: str):
            node_name = node.get("name", "")
            node_type = node.get("type", "")

            # Pattern 1: tab-{Target}-on-{Source}
            m = re.match(r"tab-(.+?)-on-(.+)", node_name, re.IGNORECASE)
            if m:
                raw_target = m.group(1)
                dest = resolve_target(raw_target)
                if dest and dest != source_frame:
                    link = {
                        "node_name":    node_name,
                        "node_type":    node_type,
                        "node_id":      node.get("id", ""),
                        "trigger":      "ON_CLICK",
                        "action":       "NAVIGATE",
                        "destination":  dest,
                        "source_frame": source_frame,
                        "inferred":     True,
                    }
                    if source_frame in wiring:
                        if not any(x["node_name"] == node_name for x in wiring[source_frame]):
                            wiring[source_frame].append(link)
                    all_links.append(link)

            # Pattern 2: {action}-btn-{Source} — find best destination
            m2 = re.match(r"(.+?)-btn-(.+)", node_name, re.IGNORECASE)
            if m2:
                action_part = m2.group(1).lower()
                # Look for destination clue in action part
                dest = ""
                for fname in known_frames:
                    if name_to_slug(fname) in action_part:
                        dest = fname
                        break
                # "view-match", "match-detail", "view-details" → Match Detail
                if not dest and any(k in action_part for k in ("match", "detail", "view")):
                    for fname in known_frames:
                        if any(k in name_to_slug(fname) for k in ("match", "detail")):
                            dest = fname
                            break
                # "back", "home" → first screen (Dashboard)
                if not dest and any(k in action_part for k in ("back", "home", "dash")):
                    dest = frames[0]["name"] if frames else ""

                if dest and dest != source_frame:
                    link = {
                        "node_name":    node_name,
                        "node_type":    node_type,
                        "node_id":      node.get("id", ""),
                        "trigger":      "ON_CLICK",
                        "action":       "NAVIGATE",
                        "destination":  dest,
                        "source_frame": source_frame,
                        "inferred":     True,
                    }
                    if source_frame in wiring:
                        if not any(x["node_name"] == node_name for x in wiring[source_frame]):
                            wiring[source_frame].append(link)
                    all_links.append(link)

            # Pattern 3: {name}-modal or {name}-drawer → OVERLAY
            if node_name.endswith(("-modal", "-drawer", "-popup", "-sheet")):
                # This is a target overlay frame, not a trigger — skip
                pass

            for child in node.get("children", []):
                infer_from_nodes(child, source_frame)

        # Walk the full tree
        data_full = _figma_get(f"/files/{file_key}?depth=8")
        for page in data_full.get("document", {}).get("children", []):
            for top_node in page.get("children", []):
                if top_node.get("type") == "FRAME":
                    frame_name = top_node.get("name", "")
                    infer_from_nodes(top_node, frame_name)

        inferred_total = sum(len(v) for v in wiring.values())
        print(f"  Inferred {inferred_total} link(s) from node naming convention")

    for frame_name, links in wiring.items():
        if links:
            for lnk in links:
                tag = " [inferred]" if lnk.get("inferred") else " [reaction]"
                nav = "overlay" if lnk["action"] == "OVERLAY" else "→"
                print(f"    [{frame_name}] {lnk['node_name']}  {nav}  {lnk['destination']}{tag}")

    return wiring, all_links


def format_wiring_for_prompt(wiring: dict, all_links: list[dict]) -> str:
    """
    Convert the wiring map into a clear, structured text block for the LLM prompt.
    This is the key information that turns guessed navigation into exact navigation.
    """
    if not any(wiring.values()):
        return "(No prototype links found — infer navigation from screen names and layout)"

    # Build screen id map: "Match Detail" → "match-detail"
    def to_id(name: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

    lines = ["EXACT PROTOTYPE WIRING — implement these interactions precisely:\n"]

    # Screen ID reference table
    all_screens = list(wiring.keys())
    if all_screens:
        lines.append("SCREEN IDs (use these exact strings in showPage() calls):")
        for s in all_screens:
            lines.append(f"  '{s}'  →  id='{to_id(s)}'  →  showPage('{to_id(s)}')")
        lines.append("")

    for frame_name, links in wiring.items():
        if not links:
            continue
        lines.append(f"Screen: {frame_name}  (id='{to_id(frame_name)}')")
        for lnk in links:
            trigger  = lnk["trigger"].replace("_", " ").title()
            action   = lnk["action"]
            dest     = lnk["destination"]
            node     = lnk["node_name"]
            node_type = lnk["node_type"]

            if action == "NAVIGATE":
                lines.append(f"  • {node} ({node_type})  —[{trigger}]→  showPage('{to_id(dest)}')")
            elif action == "OVERLAY":
                lines.append(f"  • {node} ({node_type})  —[{trigger}]→  open overlay '{to_id(dest)}'")
            elif action == "SWAP":
                lines.append(f"  • {node} ({node_type})  —[{trigger}]→  swap with '{dest}'")
            elif action == "SCROLL_TO":
                lines.append(f"  • {node} ({node_type})  —[{trigger}]→  scroll to '{dest}'")
            else:
                lines.append(f"  • {node} ({node_type})  —[{trigger} / {action}]→  '{dest}'")
        lines.append("")

    lines.append("IMPLEMENTATION RULES:")
    lines.append("- Every NAVIGATE link → add onclick=\"showPage('<id>')\" using the id from the table above")
    lines.append("- Every OVERLAY link  → toggle display of <div id='overlay-<id}'> absolutely positioned")
    lines.append("- Screen sections MUST have class='screen' and the correct id")
    lines.append("- router.js MUST call showPage('<first-screen-id>') on DOMContentLoaded AND call window._onPageShow(id) inside showPage()")
    lines.append("- D3 charts MUST be rendered inside window._onPageShow in app.js, NOT inside DOMContentLoaded (hidden sections have clientWidth===0)")
    lines.append("- Do NOT use Tailwind 'hidden' class to toggle screens — only showPage()")

    return "\n".join(lines)


# ── Playwright fallback (make / proto URLs, or REST API 403) ──────────────────

def take_screenshots_playwright(url: str, print_fn=print, output_dir: Path | None = None) -> tuple[list[dict], str]:
    """
    Use Playwright + Edge session to screenshot a Figma make/proto URL.
    Returns (screenshots_list, file_name).
    Each screenshot dict has: index, name, base64_data, filename, local_path.
    Mirrors the structure that export_frame_screenshots() returns so the
    rest of the pipeline is identical.
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        raise RuntimeError(
            "playwright not installed. Run: pip install playwright && playwright install chromium"
        )
    import shutil as _shutil, tempfile, base64 as _b64

    url_clean = re.sub(r"[?&](fullscreen|code-node-id)=[^&]*", "", url)
    shots_b64: list[str] = []

    edge_exe = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if not os.path.exists(edge_exe):
        edge_exe = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    edge_profile = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data")

    print_fn("  Launching browser for Playwright screenshot…")

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
                print_fn("  Using Edge session (logged-in Figma)")
                ctx = pw.chromium.launch_persistent_context(
                    user_data_dir=tmp, executable_path=edge_exe, headless=True,
                    args=["--no-sandbox","--disable-dev-shm-usage"],
                    viewport={"width": 1440, "height": 900},
                )
            except Exception:
                _shutil.rmtree(tmp, ignore_errors=True)
                print_fn("  Edge failed, using headless Chromium")
                browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
                ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        else:
            print_fn("  Using headless Chromium")
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
            ctx = browser.new_context(viewport={"width": 1440, "height": 900})

        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        print_fn(f"  Loading {url_clean[:70]}")

        try:
            page.goto(url_clean, wait_until="networkidle", timeout=45000)
        except PWTimeout:
            try:
                page.goto(url_clean, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(8000)
            except Exception:
                page.wait_for_timeout(5000)

        # Dismiss sign-in overlays
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

        page.wait_for_timeout(4000)
        shots_b64.append(_b64.b64encode(
            page.screenshot(full_page=False, type="jpeg", quality=85, timeout=60000)
        ).decode())
        print_fn("  Screenshot 1 captured")

        import hashlib as _hl
        def _hash(b: str) -> str:
            return _hl.md5(b[:3000].encode()).hexdigest()

        seen = {_hash(shots_b64[0])}

        def _snap(label: str) -> bool:
            try:
                buf = _b64.b64encode(
                    page.screenshot(full_page=False, type="jpeg", quality=85, timeout=60000)
                ).decode()
                h = _hash(buf)
                if h in seen:
                    return False
                seen.add(h)
                shots_b64.append(buf)
                print_fn(f"  Screenshot {len(shots_b64)} captured ({label})")
                return True
            except Exception:
                return False

        # ── Strategy 1: Figma prototype player — click the canvas to focus,
        #    then use Right Arrow to advance through screens (standard Figma nav)
        try:
            page.click("body", timeout=2000)
            page.wait_for_timeout(500)
        except Exception:
            pass

        for i in range(1, 20):  # up to 20 more screens
            if len(shots_b64) >= 15:
                break
            try:
                page.keyboard.press("ArrowRight")
                page.wait_for_timeout(1800)
                added = _snap(f"ArrowRight-{i}")
                if not added:
                    # Two consecutive identical frames → end of prototype
                    page.keyboard.press("ArrowRight")
                    page.wait_for_timeout(1800)
                    if not _snap(f"ArrowRight-{i}b"):
                        break
            except Exception:
                break

        # ── Strategy 2: click clickable elements inside the Figma canvas ────────
        if len(shots_b64) == 1:
            try:
                # Figma prototype renders inside an iframe or canvas — click hotspots
                for sel in ["[class*='hotspot']", "[class*='click']", "a[href]",
                            "canvas", "[role='button']", "button"]:
                    items = page.locator(sel).all()
                    for item in items[:8]:
                        if len(shots_b64) >= 15:
                            break
                        try:
                            item.click(timeout=2000, force=True)
                            page.wait_for_timeout(1500)
                            _snap(f"click-{sel[:20]}")
                        except Exception:
                            pass
            except Exception:
                pass

        # ── Strategy 3: nav selectors (HTML nav when prototype is full HTML) ────
        if len(shots_b64) == 1:
            clicked: set[str] = set()
            for selector in [
                "nav a","nav button",
                "[role='navigation'] a","[role='navigation'] button",
                "[class*='sidebar'] a","[class*='sidebar'] button",
                "[class*='nav'] a","[class*='nav'] button",
            ]:
                items = page.locator(selector).all()
                if len(items) < 2:
                    continue
                for item in items[:10]:
                    if len(shots_b64) >= 15:
                        break
                    try:
                        href = item.get_attribute("href") or ""
                        if href.startswith("http") and "figma.com" not in href:
                            continue
                        label = (item.text_content(timeout=1000) or "").strip()[:40]
                        if not label or label in clicked:
                            continue
                        clicked.add(label)
                        item.click(timeout=3000)
                        page.wait_for_timeout(2000)
                        _snap(label)
                    except Exception:
                        pass
                break

        # ── Strategy 4: scroll for single-page apps ──────────────────────────────
        if len(shots_b64) == 1:
            page.evaluate("window.scrollTo(0, 900)")
            page.wait_for_timeout(1200)
            _snap("scrolled-900px")

        ctx.close()

    # Infer file name from URL
    m = re.search(r"figma\.com/(?:make|file|design|proto)/[^/]+/([^/?&#]+)", url)
    raw_name = m.group(1) if m else "figma-design"
    file_name = re.sub(r"[-_]+", " ", raw_name)
    file_name = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", file_name).strip() or "Figma Design"
    proj_slug_name = slug(file_name)

    # Save to output_dir (project screenshots folder) or fallback to SCREENSHOTS_DIR
    save_dir = output_dir if output_dir else (SCREENSHOTS_DIR / proj_slug_name / "screenshots")
    save_dir.mkdir(parents=True, exist_ok=True)

    screenshots = []
    for idx, b64 in enumerate(shots_b64, start=1):
        screen_name = f"Screen {idx}"
        frame_slug_name = f"screen-{idx:02d}"
        filename = f"{proj_slug_name}__playwright__{idx:02d}__{frame_slug_name}.png"
        local_path = save_dir / filename
        local_path.write_bytes(_b64.b64decode(b64))
        screenshots.append({
            "index":       idx,
            "name":        screen_name,
            "id":          f"playwright-{idx}",
            "page":        "Page 1",
            "file_name":   file_name,
            "local_path":  str(local_path),
            "filename":    filename,
            "base64_data": b64,
        })
        print_fn(f"  Saved: {filename}")

    return screenshots, file_name


# ── Step 4: Generate web app via Claude ───────────────────────────────────────

WEBAPP_SYSTEM_PROMPT = """You are an expert frontend developer. You are given:
  1. Screenshots of EVERY SCREEN from a Figma wireframe (mobile OR desktop)
  2. The EXACT prototype wiring — which element navigates where
  3. The screen dimensions are provided in the prompt — use them to determine layout

╔══════════════════════════════════════════════════════════════════╗
║  HARD RULES — non-negotiable, enforced by post-processor         ║
╠══════════════════════════════════════════════════════════════════╣
║  DATA  : NEVER create data/app.json.                             ║
║          Create ONE file per entity: data/inventory.json,        ║
║          data/oems.json, data/sales.json, data/forecast.json …   ║
║          Each file is a JSON ARRAY of records (8-15 rows).       ║
║                                                                  ║
║  API   : ALL data access through js/api.js (IIFE module).        ║
║          app.js NEVER calls fetch() directly.                    ║
║          One function per entity, supports q/filter params.      ║
║                                                                  ║
║  CHARTS: D3.js v7 ONLY. ZERO Chart.js. ZERO <canvas> elements.  ║
║          All chart code in js/charts.js.                         ║
║          Load order: D3 CDN → charts.js → api.js → app.js       ║
║                                                                  ║
║  JS    : NEVER put <script> or </script> inside .js files.       ║
╚══════════════════════════════════════════════════════════════════╝

Your job: build a complete, fully interactive web app served as a single HTML file
with separate CSS/JS. It must work correctly when opened in a browser via HTTP server.

## Output format — STRICT multi-file
Output files separated by === path === markers:

TITLE: <app title>
PROJECT: <kebab-case-name>
---
=== index.html ===
=== css/styles.css ===
=== js/router.js ===
=== js/api.js ===
=== js/charts.js ===
=== js/app.js ===
=== data/<entity1>.json ===
=== data/<entity2>.json ===

## Data rules — SEPARATE FILES PER ENTITY
NEVER put all data in a single app.json. Create one JSON file per entity:
- data/inventory.json   → array of vehicle/product/item records
- data/oems.json        → array of manufacturer/OEM records
- data/sales.json       → array of monthly/quarterly sales records
- data/forecast.json    → array of forecast/projection records
Each file contains a JSON ARRAY (not an object) of records. Use 8-15 rows of realistic data.

## API stub rules — js/api.js
Create an IIFE module with one function per data entity:
```javascript
const AppNameAPI = (function () {
  const _store = {};
  function _load(file) {
    const key = file.replace('data/','').replace('.json','');
    if (_store[key]) return Promise.resolve(_store[key]);
    return fetch(file).then(r=>r.json()).then(d=>{ _store[key]=d; return d; });
  }
  function _delay(v,ms){ return new Promise(r=>setTimeout(()=>r(v),ms||100)); }
  function getInventory(params) {
    return _load('data/inventory.json').then(rows=>{
      let r=rows.slice();
      const q=((params||{}).q||'').trim().toLowerCase();
      if(q) r=r.filter(v=>JSON.stringify(v).toLowerCase().includes(q));
      return _delay(r);
    });
  }
  return { getInventory };
})();
```
Replace names and add one function per entity. Never call fetch() in app.js directly.

## Chart rules — D3.js ONLY
ALL charts in js/charts.js using D3.js v7. Chart containers are <div> not <canvas>.
Load D3 before charts.js: <script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
CRITICAL: Charts MUST be rendered via the _onPageShow hook (see router.js pattern below),
NOT inside DOMContentLoaded. Hidden sections have clientWidth===0, charts will be invisible.

### MANDATORY — every chart MUST have hover tooltips
Add a shared tooltip div at the top of charts.js and reuse it across all charts:
```javascript
var _tip = (function(){
  var el = document.createElement('div');
  el.style.cssText = 'position:fixed;background:rgba(15,20,40,0.92);color:#fff;padding:7px 13px;'
    + 'border-radius:6px;font-size:13px;pointer-events:none;opacity:0;transition:opacity .15s;z-index:9999;';
  document.body.appendChild(el);
  return {
    show: function(html, event){ el.innerHTML=html; el.style.opacity=1; _tip.move(event); },
    move: function(event){ el.style.left=(event.clientX+14)+'px'; el.style.top=(event.clientY-36)+'px'; },
    hide: function(){ el.style.opacity=0; }
  };
})();
```
Every bar, line dot, pie/donut slice MUST call _tip.show(...), _tip.move(...), _tip.hide():
```javascript
  .on('mouseover', function(event, d){ _tip.show('<b>'+d.month+'</b><br>'+d.units+' units', event); })
  .on('mousemove', function(event){ _tip.move(event); })
  .on('mouseout',  function(){ _tip.hide(); })
```

In app.js, register a page-show handler and render charts only when that page becomes visible:
```javascript
window._onPageShow = function(pageId) {
  if (pageId === 'sales-overview') {
    AppNameAPI.getSales().then(function(d){ renderBarChart('sales-chart', d, {xKey:'month',yKey:'units'}); });
  }
  if (pageId === 'forecast') {
    AppNameAPI.getForecast().then(function(d){ renderLineChart('forecast-chart', d, {xKey:'month',yKey:'value'}); });
  }
};
```
Container: <div id="chart-id" style="position:relative;width:100%;height:220px;"></div>
Tables and non-chart data (no width dependency) can still load at DOMContentLoaded.

## CRITICAL — router.js MUST be exactly this pattern:
```javascript
function showPage(id) {
  document.querySelectorAll('.screen').forEach(function(s){ s.style.display = 'none'; });
  var el = document.getElementById(id);
  if (el) el.style.display = 'flex';
  if (window._onPageShow) window._onPageShow(id);
}
document.addEventListener('DOMContentLoaded', function() {
  showPage('<first-screen-id>');
});
```

## CRITICAL — css/styles.css MUST hide all screens by default:
```css
.screen { display: none; flex-direction: column; }
```
NEVER use Tailwind's `hidden` class for screen visibility — only use inline style via showPage().

## CRITICAL — index.html screen structure:
- EVERY screen section must have BOTH class="screen" AND the id:
  <section id="dashboard" class="screen"> ... </section>
- DO NOT add any other display/visibility classes to screen sections
- Script tags at bottom of body, in order: router.js THEN charts.js THEN api.js THEN app.js

## Layout — detect from frame dimensions provided in the prompt:

### DESKTOP layout (frame width >= 1000px):
- Full-width responsive layout filling the browser window
- No phone shell wrapper
- Use the full viewport width
- CSS: body { margin: 0; } .screen { display: none; flex-direction: column; min-height: 100vh; }

### MOBILE layout (frame width < 1000px, e.g. 390px):
- Wrap in a phone shell centered on desktop:
```css
body { background:#0a0f14; display:flex; justify-content:center; padding:24px 0; min-height:100vh; }
.phone-shell { width:390px; min-height:844px; background:<app-bg-color>; border-radius:40px;
               box-shadow:0 0 0 10px #1a1a2e,0 30px 80px rgba(0,0,0,0.8); overflow:hidden; position:relative; }
.screen { display:none; flex-direction:column; min-height:844px; }
```

## Navigation rules — CRITICAL
- Screen IDs must be kebab-case of Figma frame name: "Match Detail" → "match-detail"
- showPage() call uses the screen id: showPage('match-detail')
- Wire EVERY link in the prototype wiring — add onclick="showPage('...')" to the element
- For nav tabs: the currently active screen's tab gets a highlighted style
- For OVERLAY links: create a hidden div with position:absolute, toggle display on click

## Technical rules
- Tailwind CSS via CDN for utility classes (https://cdn.tailwindcss.com)
- D3.js v7 via CDN (https://cdn.jsdelivr.net/npm/d3@7) — NO Chart.js, NO <canvas>
- ALL JS in js/ files — NO inline <script> in HTML
- ALL custom CSS in css/styles.css — NO inline <style> in HTML
- ALL data in data/*.json — NO hardcoded arrays in JS files
- Bottom nav: use position:absolute bottom:0 left:0 right:0 inside .phone-shell

## Visual fidelity rules
- Extract EXACT hex colors from screenshots — declare as CSS custom properties
- Match nav bar layout, tab labels, active/inactive states exactly
- Match card layouts, list items, header heights, spacing from screenshots
- Implement every interactive element shown: search, filters, dropdowns, buttons
- Use realistic domain-appropriate dummy data in data/*.json
- NEVER output prose — only the === file === blocks""" + _brand_css_section()



def generate_webapp(
    screenshots: list[dict],
    file_name: str,
    prompt: str = "",
    wiring: dict = None,
    all_links: list = None,
) -> dict:
    """
    Send screenshots + exact prototype wiring to Claude via LiteLLM.
    Returns {title, project_name, files: {path: content}}.
    """
    from agents.llm import _get_client

    client = _get_client()

    # ── Detect layout type from frame dimensions ──────────────────────────────
    # width=0 means the Figma API didn't return dimensions (e.g. Playwright path) — default desktop
    frame_width = screenshots[0].get("width", 0) if screenshots else 0
    is_desktop = (frame_width == 0) or (frame_width >= 1000)
    layout_hint = (
        f"LAYOUT: {'DESKTOP' if is_desktop else 'MOBILE'} "
        f"(Figma frame width={frame_width}px{' — unknown, defaulting to desktop' if frame_width == 0 else ''}). "
        + ("Use full-width desktop layout — NO phone shell wrapper." if is_desktop
           else "Use mobile phone shell (390px centered).")
    )

    print(f"  Layout: {'DESKTOP' if is_desktop else 'MOBILE'} (frame width={frame_width}px)")

    # ── Build user message ────────────────────────────────────────────────────
    screen_list = "\n".join(f"  {s['index']}. {s['name']}" for s in screenshots)
    wiring_text = format_wiring_for_prompt(wiring or {}, all_links or [])

    intro = (
        f'Figma design: "{file_name}"\n'
        f"{layout_hint}\n\n"
        f"{len(screenshots)} screens to implement:\n{screen_list}\n\n"
        f"{wiring_text}\n"
    )
    if prompt.strip():
        intro += f"\nAdditional instructions: {prompt}\n"
    intro += (
        "\nThe screenshots follow — one per screen in order. "
        "Match the visual design exactly and implement all wiring above."
    )

    content: list[dict] = [{"type": "text", "text": intro}]
    for s in screenshots:
        content.append({"type": "text", "text": f"\n--- Screen {s['index']}: {s['name']} ---"})
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{s['base64_data']}"},
        })

    print(f"\n  Sending {len(screenshots)} screenshots + wiring map to Claude…")
    total_links = sum(len(v) for v in (wiring or {}).values())
    print(f"  Wiring: {total_links} prototype link(s) extracted from Figma")

    # Use streaming to avoid gateway timeout — keeps connection alive
    from agents.llm import _get_current_run_id, _record_usage
    stream = client.chat.completions.create(
        model=MODEL_ID,
        max_tokens=64000,
        timeout=600,
        stream=True,
        stream_options={"include_usage": True},
        messages=[
            {"role": "system", "content": WEBAPP_SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
    )
    chunks = []
    usage_data = None
    for chunk in stream:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta and delta.content:
            chunks.append(delta.content)
        if hasattr(chunk, "usage") and chunk.usage:
            usage_data = chunk.usage

    # Record token usage
    if usage_data:
        _record_usage(
            _get_current_run_id(),
            getattr(usage_data, "prompt_tokens", 0),
            getattr(usage_data, "completion_tokens", 0),
        )
    else:
        est_output = sum(len(c) for c in chunks) // 4
        _record_usage(_get_current_run_id(), 0, est_output)

    text = "".join(chunks)

    title, proj_slug, files = _parse_multifile(text)
    return {"title": title, "project_name": proj_slug, "files": files, "raw": text}


def _parse_multifile(response: str) -> tuple[str, str, dict[str, str]]:
    text  = response.strip()
    title = "App"
    slug_name = ""

    header_m = re.match(
        r"TITLE:\s*(.+?)\n(?:PROJECT:\s*(.+?)\n)?-{3,}\n(.*)",
        text, re.DOTALL | re.IGNORECASE,
    )
    if header_m:
        title     = header_m.group(1).strip()
        slug_name = header_m.group(2).strip() if header_m.group(2) else ""
        text      = header_m.group(3).strip()

    FILE_RE = re.compile(r"={3}\s*([\w][\w\-./]*\.\w+)\s*={3}")
    matches = list(FILE_RE.finditer(text))
    files: dict[str, str] = {}
    for idx, m in enumerate(matches):
        path    = m.group(1).strip().lstrip("/")
        start   = m.end()
        end     = matches[idx+1].start() if idx+1 < len(matches) else len(text)
        content = text[start:end].strip()
        content = re.sub(r"^```[a-zA-Z]*\n?", "", content)
        content = re.sub(r"\n?```$",          "", content)
        files[path] = content.strip()

    if not slug_name:
        slug_name = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "app"
    files = _enforce_rules(files)
    return title, slug_name, files


def _enforce_rules(files: dict) -> dict:
    """
    Post-process LLM output to enforce the three mandatory rules regardless of
    what the model produced:
      1. Split data/app.json into per-entity files
      2. Ensure js/api.js exists and references the entity files
      3. Ensure js/charts.js exists with D3 patterns; replace Chart.js in index.html
    """
    import json as _json

    # ── 1. Split data/app.json into entity files ──────────────────────────────
    if "data/app.json" in files:
        try:
            app_data = _json.loads(files["data/app.json"])
        except Exception:
            app_data = {}

        if isinstance(app_data, dict):
            entity_map = {
                "inventory": "data/inventory.json", "vehicles": "data/inventory.json",
                "items": "data/items.json", "products": "data/products.json",
                "oems": "data/oems.json", "topOems": "data/oems.json",
                "manufacturers": "data/manufacturers.json", "segments": "data/segments.json",
                "forecast": "data/forecast.json", "forecastData": "data/forecast.json",
                "sales": "data/sales.json", "salesData": "data/sales.json",
                "monthly": "data/sales.json", "users": "data/users.json",
                "players": "data/players.json", "teams": "data/teams.json",
                "matches": "data/matches.json", "projects": "data/projects.json",
                "tasks": "data/tasks.json", "members": "data/members.json",
            }
            dest_data: dict = {}
            dest_obj:  dict = {}
            placed = set()
            for key, value in app_data.items():
                dest = entity_map.get(key)
                if dest:
                    placed.add(key)
                    if isinstance(value, list):
                        dest_data.setdefault(dest, []).extend(value)
                    elif isinstance(value, dict):
                        dest_obj.setdefault(dest, {})[key] = value
            for key, value in app_data.items():
                if key in placed:
                    continue
                if isinstance(value, list):
                    dest_data[f"data/{key}.json"] = value
                elif isinstance(value, dict):
                    dest_data[f"data/{key}.json"] = [value]
            for dest, rows in dest_data.items():
                if dest not in files:
                    files[dest] = _json.dumps(rows, indent=2)
            for dest, obj in dest_obj.items():
                if dest not in files and dest not in dest_data:
                    files[dest] = _json.dumps(obj, indent=2)
            del files["data/app.json"]
            print("  [enforce] Split data/app.json -> " + ", ".join(sorted(set(dest_data) | set(dest_obj))))
        elif isinstance(app_data, list):
            files["data/items.json"] = files.pop("data/app.json")

    # ── 2. Ensure js/api.js exists ────────────────────────────────────────────
    data_files = sorted(k for k in files if k.startswith("data/") and k.endswith(".json"))

    if "js/api.js" not in files or len(files.get("js/api.js", "")) < 80:
        if data_files:
            entity_name = re.sub(r"[^a-zA-Z0-9]", "", data_files[0].split("/")[-1].split(".")[0].title())
            api_name = f"{entity_name}API" if entity_name else "AppAPI"
            load_lines = []
            exports = []
            for df in data_files:
                key = df.split("/")[-1].replace(".json", "")
                fn  = "get" + key[0].upper() + key[1:]
                load_lines.append(
                    f"  function {fn}(params) {{\n"
                    f"    return _load('{df}').then(rows => {{\n"
                    f"      let r = rows.slice ? rows.slice() : rows;\n"
                    f"      const q = ((params || {{}}).q || '').trim().toLowerCase();\n"
                    f"      if (q) r = Array.isArray(r) ? r.filter(v => JSON.stringify(v).toLowerCase().includes(q)) : r;\n"
                    f"      return _delay(r);\n"
                    f"    }});\n"
                    f"  }}"
                )
                exports.append(fn)
            api_js = (
                f"const {api_name} = (function () {{\n"
                f"  const _store = {{}};\n"
                f"  function _load(file) {{\n"
                f"    const key = file.replace('data/', '').replace('.json', '');\n"
                f"    if (_store[key]) return Promise.resolve(_store[key]);\n"
                f"    return fetch(file).then(r => r.json()).then(d => {{ _store[key] = d; return d; }});\n"
                f"  }}\n"
                f"  function _delay(v, ms) {{ return new Promise(r => setTimeout(() => r(v), ms || 100)); }}\n"
                + "\n".join(load_lines) + "\n"
                f"  return {{ {', '.join(exports)} }};\n"
                f"}})();"
            )
            files["js/api.js"] = api_js
            print(f"  [enforce] Generated js/api.js with {len(exports)} endpoint(s)")

    # ── 3. Ensure js/charts.js with D3 patterns ──────────────────────────────
    if "js/charts.js" not in files or len(files.get("js/charts.js", "")) < 80:
        files["js/charts.js"] = """// D3.js v7 chart helpers — shared tooltip + bar/line/donut
var _tip = (function(){
  var el = document.createElement('div');
  el.style.cssText = 'position:fixed;background:rgba(15,20,40,0.92);color:#fff;padding:7px 13px;'
    + 'border-radius:6px;font-size:13px;pointer-events:none;opacity:0;transition:opacity .15s;z-index:9999;'
    + 'box-shadow:0 4px 16px rgba(0,0,0,.4);line-height:1.5;';
  document.body.appendChild(el);
  return {
    show: function(html, event){ el.innerHTML=html; el.style.opacity=1; _tip.move(event); },
    move: function(event){ el.style.left=(event.clientX+14)+'px'; el.style.top=(event.clientY-40)+'px'; },
    hide: function(){ el.style.opacity=0; }
  };
})();

function renderBarChart(containerId, data, opts) {
  opts = opts || {};
  var xKey = opts.xKey || Object.keys(data[0]||{})[0] || 'label';
  var yKey = opts.yKey || Object.keys(data[0]||{})[1] || 'value';
  var color = opts.color || '#3b82f6';
  var el = document.getElementById(containerId);
  if (!el || !data || !data.length) return;
  el.innerHTML = '';
  var W = el.clientWidth || 400, H = 220;
  var m = {top:20,right:16,bottom:44,left:50};
  var w = W-m.left-m.right, h = H-m.top-m.bottom;
  var svg = d3.select(el).append('svg').attr('width',W).attr('height',H);
  var g = svg.append('g').attr('transform','translate('+m.left+','+m.top+')');
  var x = d3.scaleBand().domain(data.map(function(d){return d[xKey];})).range([0,w]).padding(0.28);
  var y = d3.scaleLinear().domain([0,d3.max(data,function(d){return +d[yKey];})*1.12]).range([h,0]);
  g.append('g').attr('transform','translate(0,'+h+')').call(d3.axisBottom(x))
   .selectAll('text').attr('transform','rotate(-30)').style('text-anchor','end').style('font-size','11px');
  g.append('g').call(d3.axisLeft(y).ticks(5).tickFormat(d3.format('.2s')));
  g.selectAll('rect').data(data).join('rect')
    .attr('x',function(d){return x(d[xKey]);}).attr('y',function(d){return y(+d[yKey]);})
    .attr('width',x.bandwidth()).attr('height',function(d){return h-y(+d[yKey]);})
    .attr('fill',color).attr('rx',3).style('cursor','pointer')
    .on('mouseover',function(event,d){
      d3.select(this).attr('opacity',0.8);
      _tip.show('<b>'+d[xKey]+'</b><br>'+d3.format(',')(+d[yKey]), event);
    })
    .on('mousemove',function(event){ _tip.move(event); })
    .on('mouseout',function(){ d3.select(this).attr('opacity',1); _tip.hide(); });
}
function renderLineChart(containerId, data, opts) {
  opts = opts || {};
  var xKey = opts.xKey || Object.keys(data[0]||{})[0] || 'label';
  var yKey = opts.yKey || Object.keys(data[0]||{})[1] || 'value';
  var color = opts.color || '#3b82f6';
  var el = document.getElementById(containerId);
  if (!el || !data || !data.length) return;
  el.innerHTML = '';
  var W = el.clientWidth || 500, H = 230;
  var m = {top:20,right:20,bottom:40,left:52};
  var w = W-m.left-m.right, h = H-m.top-m.bottom;
  var svg = d3.select(el).append('svg').attr('width',W).attr('height',H);
  var g = svg.append('g').attr('transform','translate('+m.left+','+m.top+')');
  var x = d3.scalePoint().domain(data.map(function(d){return d[xKey];})).range([0,w]);
  var y = d3.scaleLinear().domain([0,d3.max(data,function(d){return +d[yKey];})*1.12]).range([h,0]);
  g.append('g').attr('transform','translate(0,'+h+')').call(d3.axisBottom(x)).selectAll('text').style('font-size','11px');
  g.append('g').call(d3.axisLeft(y).ticks(5).tickFormat(d3.format('.2s')));
  g.append('path').datum(data).attr('fill','none').attr('stroke',color).attr('stroke-width',2.5)
   .attr('d',d3.line().x(function(d){return x(d[xKey]);}).y(function(d){return y(+d[yKey]);}).curve(d3.curveMonotoneX));
  g.selectAll('circle').data(data).join('circle')
    .attr('cx',function(d){return x(d[xKey]);}).attr('cy',function(d){return y(+d[yKey]);})
    .attr('r',5).attr('fill',color).style('cursor','pointer')
    .on('mouseover',function(event,d){
      d3.select(this).attr('r',7);
      _tip.show('<b>'+d[xKey]+'</b><br>'+d3.format(',')(+d[yKey]), event);
    })
    .on('mousemove',function(event){ _tip.move(event); })
    .on('mouseout',function(){ d3.select(this).attr('r',5); _tip.hide(); });
}
function renderDonutChart(containerId, data, opts) {
  opts = opts || {};
  var labelKey = opts.labelKey || Object.keys(data[0]||{})[0] || 'label';
  var valueKey = opts.valueKey || Object.keys(data[0]||{})[1] || 'value';
  var el = document.getElementById(containerId);
  if (!el || !data || !data.length) return;
  el.innerHTML = '';
  var size = Math.min(el.clientWidth || 220, 220);
  var radius = size/2, inner = radius*0.55;
  var palette = d3.schemeTableau10;
  var svg = d3.select(el).append('svg').attr('width',size).attr('height',size);
  var g = svg.append('g').attr('transform','translate('+radius+','+radius+')');
  var pie = d3.pie().value(function(d){return +d[valueKey];}).sort(null);
  var arc = d3.arc().innerRadius(inner).outerRadius(radius-4);
  var arcHover = d3.arc().innerRadius(inner).outerRadius(radius+4);
  g.selectAll('path').data(pie(data)).join('path')
    .attr('d',arc).attr('fill',function(d,i){return palette[i%palette.length];})
    .attr('stroke','#fff').attr('stroke-width',1.5).style('cursor','pointer')
    .on('mouseover',function(event,d){
      d3.select(this).attr('d',arcHover);
      _tip.show('<b>'+d.data[labelKey]+'</b><br>'+d3.format(',')(+d.data[valueKey]), event);
    })
    .on('mousemove',function(event){ _tip.move(event); })
    .on('mouseout',function(event){ d3.select(this).attr('d',arc); _tip.hide(); });
}"""
        print("  [enforce] Injected js/charts.js with D3 bar/line/donut + fixed tooltips")

    # ── 4. Fix index.html: D3 CDN, canvas→div, script order ─────────────────
    if "index.html" in files:
        html = files["index.html"]
        html = re.sub(r'<script[^>]+chart\.js[^>]*>\s*</script>',
                      '<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>',
                      html, flags=re.IGNORECASE)
        html = re.sub(r'<canvas\s+id="([^"]+)"[^>]*></canvas>',
                      lambda m: f'<div id="{m.group(1)}" style="position:relative;width:100%;height:220px;"></div>',
                      html, flags=re.IGNORECASE)
        if 'cdn.jsdelivr.net/npm/d3' not in html:
            html = html.replace('<script src="js/charts.js">',
                                '<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>\n  <script src="js/charts.js">')
        if 'js/charts.js' not in html and 'js/api.js' in html:
            html = html.replace('<script src="js/app.js">',
                                '<script src="js/charts.js"></script>\n  <script src="js/app.js">')
        files["index.html"] = html

    # ── 5. Remove residual Chart.js calls from app.js ────────────────────────
    if "js/app.js" in files and "data/app.json" not in files:
        app_js = files["js/app.js"]
        app_js = re.sub(r"""fetch\s*\(\s*['"]data/app\.json['"]\s*\)""",
                        "fetch('data/" + (data_files[0].split("/")[-1] if data_files else "items.json") + "')",
                        app_js)
        app_js = re.sub(r'new Chart\s*\([^;]+;', '/* Chart rendered by js/charts.js */', app_js, flags=re.DOTALL)
        files["js/app.js"] = app_js

    # ── 6. Ensure router.js fires _onPageShow hook ────────────────────────────
    # D3 charts need the container visible (clientWidth > 0) before rendering.
    # Any router.js that doesn't call window._onPageShow(id) will produce blank charts.
    if "js/router.js" in files:
        rjs = files["js/router.js"]
        if "_onPageShow" not in rjs:
            # Inject the hook call inside showPage(), just after the display=flex line
            rjs = re.sub(
                r"(el\.style\.display\s*=\s*['\"]flex['\"];?)",
                r"\1\n  if (window._onPageShow) window._onPageShow(id);",
                rjs,
                count=1,
            )
            if "_onPageShow" not in rjs:
                # Fallback: append hook to the end of showPage body via closing brace pattern
                rjs = re.sub(
                    r"(function\s+showPage\s*\([^)]*\)\s*\{[^}]*)\}",
                    r"\1  if (window._onPageShow) window._onPageShow(id);\n}",
                    rjs,
                    count=1,
                    flags=re.DOTALL,
                )
            files["js/router.js"] = rjs
            print("  [enforce] Patched router.js to fire window._onPageShow(id)")

    return files


# ── Step 5: Write files ────────────────────────────────────────────────────────

def write_project(project_name: str, files: dict[str, str]) -> Path:
    """Write generated files to TurboUIGen/generated/."""
    output_base = GENERATED_DIR
    output_base.mkdir(parents=True, exist_ok=True)

    safe_name  = re.sub(r"[^a-z0-9-]", "-", project_name.lower()).strip("-") or "app"
    project_dir = output_base / safe_name
    project_dir.mkdir(parents=True, exist_ok=True)

    from agents.uigen_agent import _repair_json
    from agents.sanitize_js import sanitize
    for rel_path, content in files.items():
        fp = project_dir / rel_path
        fp.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, list):
            content = "\n".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            )
        if not content or not content.strip():
            continue
        if rel_path.endswith(".json"):
            content = _repair_json(content, rel_path)
        content = sanitize(content, rel_path)
        fp.write_text(content, encoding="utf-8")
        print(f"  Wrote: {safe_name}/{rel_path}")

    return project_dir


# ── Main pipeline ──────────────────────────────────────────────────────────────

def run(
    figma_url:             str,
    prompt:                str   = "",
    scale:                 float = 1.5,
    screenshots_only:      bool  = False,
    force_playwright:      bool  = False,
    project_name_override: str   = "",   # user's project name — always wins over LLM slug
    progress_callback      = None,       # callable(str) for live streaming progress to UI
) -> dict:
    """
    Full pipeline with smart URL routing:

    URL pattern decides the primary path immediately — no waiting:
      design / file  → REST API  (frames + exact wiring)
      make / proto   → Playwright (browser render, wiring inferred)

    REST API path also falls back to Playwright if it gets a 403
    (e.g. token lacks editor access), but that 403 returns instantly
    so there is no meaningful delay.

    Pass force_playwright=True to skip REST API regardless of URL type.
    """
    def _emit(msg: str):
        print(msg)
        if progress_callback:
            progress_callback(msg)

    _emit(f"\n{'='*60}")
    _emit(f"  Figma → Web App")
    _emit(f"  URL: {figma_url[:70]}")
    _emit(f"{'='*60}\n")

    # 1. URL pattern routing — decide primary path immediately, no round-trip needed
    url_type_m = re.search(r"figma\.com/(file|design|proto|make)/", figma_url, re.IGNORECASE)
    url_type = url_type_m.group(1).lower() if url_type_m else "design"

    # make/proto → Playwright by default (browser-rendered prototype links)
    # design/file → REST API by default (structured frame data + wiring)
    use_rest_api = (url_type in ("design", "file")) and not force_playwright

    screenshots: list[dict] = []
    file_name    = "Figma Design"
    wiring:      dict = {}
    # project-specific screenshots dir — resolved once we know the project name
    project_screenshots_dir: Path | None = None
    all_links:   list = []
    project_slug_name = ""
    used_playwright   = False
    file_key  = None
    frames    = []

    _emit(f"  URL type: {url_type}  →  "
          f"{'REST API' if use_rest_api else 'Playwright'} (primary path)")

    # ── REST API path (design / file URLs) ────────────────────────────────────
    if use_rest_api:
        try:
            file_key, _ = parse_figma_url(figma_url)
            _emit(f"  File key: {file_key}")
            frames, file_name = get_top_frames(file_key)

            if not frames:
                raise RuntimeError("No FRAME nodes found in this Figma file.")

            _emit(f"\n  Screens found:")
            for f in frames:
                _emit(f"    [{f['page']}] {f['name']}")

            project_slug_name = slug(project_name_override) if project_name_override else slug(file_name)
            # Screenshots go into figma-mockups/<project-name>/screenshots/
            project_screenshots_dir = SCREENSHOTS_DIR / project_slug_name / "screenshots"
            project_screenshots_dir.mkdir(parents=True, exist_ok=True)
            _emit(f"\n  Exporting screenshots → {project_screenshots_dir}")
            screenshots = export_frame_screenshots(
                file_key, frames, project_slug_name, scale=scale,
                screenshots_dir=project_screenshots_dir
            )
            if not screenshots:
                raise RuntimeError("REST API returned no screenshot URLs")

            _emit(f"\n  Screenshots saved:")
            for s in screenshots:
                _emit(f"    {s['filename']}")

        except RuntimeError as e:
            # 403 returns instantly — no delay before this fallback
            err_msg = str(e)
            _emit(f"\n  REST API failed ({err_msg[:80]})")
            _emit(f"  Falling back to Playwright screenshots…\n")
            use_rest_api = False   # drop through to Playwright below

    # ── Playwright path (make / proto URLs, or REST API 403 fallback) ─────────
    if not use_rest_api:
        if url_type in ("make", "proto"):
            _emit(f"  Using Playwright — '{url_type}' URLs render as browser prototypes")
        else:
            _emit(f"  Using Playwright — REST API fallback")
        _emit(f"  Wiring will be inferred by Claude from the screenshots.\n")
        try:
            # Compute project dir before calling so screenshots land in the right place
            _slug_hint = slug(project_name_override) if project_name_override else ""
            _hint_dir  = (SCREENSHOTS_DIR / _slug_hint / "screenshots") if _slug_hint else None
            if _hint_dir:
                _hint_dir.mkdir(parents=True, exist_ok=True)
            screenshots, file_name = take_screenshots_playwright(figma_url, output_dir=_hint_dir)
            project_slug_name = _slug_hint or slug(file_name)
            project_screenshots_dir = SCREENSHOTS_DIR / project_slug_name / "screenshots"
            project_screenshots_dir.mkdir(parents=True, exist_ok=True)
            used_playwright = True
        except Exception as pw_err:
            raise RuntimeError(
                f"Screenshot capture failed for {url_type} URL.\n"
                f"  Error: {pw_err}\n"
                f"  Tip: Make sure Playwright is installed: "
                f"pip install playwright && playwright install chromium"
            )

    if not screenshots:
        raise RuntimeError("No screenshots could be captured.")

    if screenshots_only:
        _emit(f"\n  --screenshots-only: stopping here.")
        return {"screenshots": [s["local_path"] for s in screenshots]}

    # ── Wiring extraction (REST API path only) ────────────────────────────────
    if use_rest_api and file_key and frames:
        _emit(f"\n  Extracting prototype links…")
        wiring, all_links = extract_prototype_links(file_key, frames)
        # Save wiring JSON next to screenshots inside the project folder
        wiring_dir = project_screenshots_dir if project_screenshots_dir else SCREENSHOTS_DIR
        wiring_path = wiring_dir / "wiring.json"
        wiring_path.write_text(
            json.dumps({"wiring": wiring, "all_links": all_links}, indent=2),
            encoding="utf-8",
        )
        _emit(f"  Wiring map saved: {wiring_path.name}")
    else:
        _emit(f"  Wiring: inferred by Claude from screenshots")

    # ── Generate web app ──────────────────────────────────────────────────────
    _emit(f"\n  Sending design to Claude for web app generation…")
    result = generate_webapp(screenshots, file_name, prompt, wiring, all_links)

    if not result["files"].get("index.html"):
        raise RuntimeError(
            f"Claude did not return a valid index.html. "
            f"Response started: {result['raw'][:300]}"
        )

    _emit(f"\n  Generated {len(result['files'])} files for '{result['title']}'")

    # 6. Write files — user's project name always wins over LLM-generated slug
    final_name = (
        re.sub(r"[^a-z0-9-]", "-", project_name_override.lower()).strip("-")
        if project_name_override
        else result["project_name"]
    )
    project_dir = write_project(final_name, result["files"])
    # Always create screenshots folder inside project dir
    (project_dir / "screenshots").mkdir(exist_ok=True)
    _emit(f"\n  Project written to: {project_dir}")

    _emit(f"\n{'='*60}")
    _emit(f"  Done!")
    _emit(f"  Project:     {final_name}")
    _emit(f"  Files:       {', '.join(result['files'].keys())}")
    _emit(f"  Screenshots: {SCREENSHOTS_DIR}")
    _emit(f"{'='*60}\n")

    return {
        "project_name": final_name,
        "title":        result["title"],
        "project_dir":  str(project_dir),
        "files":        list(result["files"].keys()),
        "screenshots":  [s["local_path"] for s in screenshots],
    }


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Export Figma frames → screenshots → generate interactive web app",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python figma_to_webapp.py "https://www.figma.com/design/ABC123/Sports-App"
  python figma_to_webapp.py <url> --prompt "Make it mobile-first with dark theme"
  python figma_to_webapp.py <url> --screenshots-only
  python figma_to_webapp.py <url> --scale 2

Screenshot filenames:
  <project>__<nn>__<screen-name>.jpg
  e.g. sports-app__01__dashboard.jpg
       sports-app__02__players.jpg
        """,
    )
    parser.add_argument("url",   help="Figma file or design URL")
    parser.add_argument("--prompt", "-p", default="", help="Extra instructions for the LLM")
    parser.add_argument("--scale",  "-s", type=float, default=1,
                        help="Export scale factor (default 1 — native resolution, JPEG compressed)")
    parser.add_argument("--screenshots-only", action="store_true",
                        help="Only export screenshots, skip web app generation")
    parser.add_argument("--playwright", action="store_true",
                        help="Force Playwright browser screenshots even for design/file URLs")
    args = parser.parse_args()

    try:
        result = run(
            figma_url=args.url,
            prompt=args.prompt,
            scale=args.scale,
            screenshots_only=args.screenshots_only,
            force_playwright=args.playwright,
        )
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
