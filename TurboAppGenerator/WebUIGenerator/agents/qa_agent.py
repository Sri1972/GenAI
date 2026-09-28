"""
QA Agent — static + runtime checks for generated React/TS apps.

Runs after generate_project() and returns a structured sign-off report.
Call run_qa(project_name, port, project_dir) to get a QAReport dict.

Check pipeline:
  1. Static regex checks (banned libs, map bugs, hook bugs)
  2. Config checks (package.json, vite.config.ts, App.tsx)
  3. Completeness checks (required files, pages dir)
  4. TypeScript compilation  — tsc --noEmit (always)
  5. Browser runtime checks — Playwright headless if installed,
                              HTTP probes otherwise (fallback)
"""

from __future__ import annotations
import re
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from dataclasses import dataclass, field
from typing import Literal

# ── Types ─────────────────────────────────────────────────────────────────────

Severity = Literal["error", "warning", "info"]

@dataclass
class QAFinding:
    severity: Severity
    category: str
    file: str
    message: str

@dataclass
class QAReport:
    project_name: str
    passed: bool
    score: int          # 0–100
    findings: list[QAFinding] = field(default_factory=list)
    pages_ok: list[str] = field(default_factory=list)
    pages_fail: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "project":    self.project_name,
            "passed":     self.passed,
            "score":      self.score,
            "summary":    self.summary,
            "pages_ok":   self.pages_ok,
            "pages_fail": self.pages_fail,
            "findings": [
                {"severity": f.severity, "category": f.category,
                 "file": f.file, "message": f.message}
                for f in self.findings
            ],
        }


# ── Static checks ─────────────────────────────────────────────────────────────

_STATIC_CHECKS: list[tuple[str, Severity, str, str]] = [
    # Banned libraries
    ("banned-lib",   "error",   r"from\s+['\"]react-simple-maps['\"]",
     "react-simple-maps import — use D3+topojson instead"),
    ("banned-lib",   "error",   r"from\s+['\"]highcharts['\"]",
     "highcharts import — use D3 instead"),
    ("banned-lib",   "error",   r"from\s+['\"]recharts['\"]",
     "recharts import — use D3 instead"),
    ("banned-lib",   "error",   r"from\s+['\"]chart\.js['\"]",
     "chart.js import — use D3 instead"),

    # Map anti-patterns
    ("map-bug",      "error",   r"ADM0_A3",
     "ADM0_A3 property doesn't exist in world-atlas@2; use geo.id numeric lookup"),
    ("map-bug",      "error",   r"ISO2_TO_ISO3",
     "ISO2_TO_ISO3 reverse-lookup is fragile; use NUMERIC_TO_ISO2 forward table"),
    ("map-bug",      "warning", r"\.padStart\(2",
     "padStart(2) on geo.id — world-atlas numeric IDs need padStart(3,'0')"),
    ("map-bug",      "error",
     r"import\s*\(['\"](?:us-atlas|world-atlas)[^'\"]*['\"]",
     "Dynamic import() of atlas data causes blank maps — use static top-level import"),
    ("map-bug",      "error",
     r"d3\.json\s*\(['\"]https?://[^'\"]*(?:us-atlas|world-atlas|cdn\.jsdelivr)[^'\"]*['\"]",
     "d3.json() fetch of atlas data causes blank maps — use static top-level import"),
    ("map-bug",      "error",
     r"fetch\s*\(['\"]https?://[^'\"]*(?:us-atlas|world-atlas|cdn\.jsdelivr)[^'\"]*['\"]",
     "fetch() of atlas data causes blank maps — use static top-level import"),

    # React hook anti-patterns
    ("hook-bug",     "error",   r"useEffect\([^)]*\[[^\]]*\]\s*\)",
     "useEffect with non-memoised object/array in dep array — causes infinite re-renders"),

    # D3 + React double-render
    ("d3-bug",       "warning", r"svg\.selectAll\('\*'\)\.remove\(\).*useState",
     "D3 clears SVG on every render — ensure data is memoised so effect only fires on data change"),

    # Missing fallback data
    ("data-safety",  "warning", r"props\.\w+\.map\(",
     "Calling .map() directly on a prop without null-guard — may crash if prop is undefined"),

    # Calling .map() on a state object that wraps an array (common LLM bug)
    ("map-on-object","error",
     r"\{diff\s*\?\s*\([^)]*diff\.map\(",
     "diff.map() called on state object — should be diff.diff.map() to access the nested array"),

    # (data-location check removed — projects use SQLite + API, inline seed data is fine)

    # TODO / placeholders
    ("completeness", "warning", r"\/\/\s*TODO|\/\/\s*FIXME|\.\.\.placeholder|coming soon",
     "Placeholder/TODO left in generated code"),

    # Absolute favicon href
    ("asset-path",   "warning", r'href="/vite\.svg"',
     'Absolute favicon href "/vite.svg" will 404 when served under a sub-path — use "./vite.svg"'),

    # react-dom/client missing
    ("import-bug",   "error",   r"ReactDOM\.render\(",
     "ReactDOM.render() is React 17 API — use createRoot from react-dom/client"),

    # Missing component file (SalesMap → should be UsaSalesMap)
    ("import-bug",   "error",   r"from\s+['\"]\.\.?/components/SalesMap['\"]",
     "SalesMap does not exist — import UsaSalesMap instead"),

    # Props typed as required but often undefined
    ("prop-safety",  "warning", r"groupKeys\s*=\s*\{",
     "groupKeys is not a valid D3GroupedBar prop — use groupKey (string) + series instead"),

    # ResizeObserver + setDims infinite loop (setDims creates new object ref → re-render → resize → loop).
    # Bounded to ~300 chars — the call site's own DOTALL means an unbounded
    # ".*" here can span the ENTIRE file, matching "ResizeObserver" and
    # "setDims({" wherever each happens to appear, even in two unrelated
    # components. 300 chars comfortably covers a real ResizeObserver
    # callback body while not reaching into a different function below it.
    ("infinite-loop", "warning",
     r"ResizeObserver[\s\S]{0,300}?setDims\(\s*\{",
     "setDims({...}) inside ResizeObserver creates new object ref each call — "
     "use setDims(prev => prev.w === w && prev.h === h ? prev : {w, h}) to prevent infinite re-renders"),

    # Duplicate export default — esbuild/Vite will fail with "multiple default exports"
    ("syntax-error", "error",
     r"(?s)export default .+\nexport default ",
     "Multiple 'export default' statements — only one is allowed per module"),

    # Self-closing JSX tag missing closing > (e.g. <Component prop="val" / with no >)
    ("syntax-error", "error",
     r"<[A-Z]\w+[^>]*/\s*$",
     "Self-closing JSX tag missing closing > — will crash the bundler"),

    # @media queries in JSX inline style objects (React doesn't support them).
    # [^)]* stops at the FIRST ")" — a compound query like "(min-width: 768px)
    # and (max-width: 1024px)" has a second "(...)" before the closing quote,
    # so that real, common pattern slipped past this check entirely. Matching
    # up to the closing quote itself (not just one paren group) instead.
    ("inline-style-bug", "warning",
     r"""['"]@media\s*\([^'"]*\)['"]\s*:""",
     "@media query in inline style object — React ignores these; use Tailwind responsive classes instead"),
]


def _static_check_file(path: str, content: str) -> list[QAFinding]:
    findings: list[QAFinding] = []
    for category, severity, pattern, message in _STATIC_CHECKS:
        # MULTILINE matters for at least one pattern here (the self-closing
        # JSX tag check's trailing "$" — without it, "$" only anchors at the
        # true end of the whole file, not each line, so it silently missed
        # every occurrence except one on the file's very last line). None of
        # the other patterns in _STATIC_CHECKS use ^/$ anchors, so adding it
        # doesn't change their behavior.
        if re.search(pattern, content, re.IGNORECASE | re.DOTALL | re.MULTILINE):
            findings.append(QAFinding(severity, category, path, message))

    # Map components MUST have click-to-select interaction
    _is_map = any(kw in content for kw in [
        'topojson', 'world-atlas', 'us-atlas', 'geoPath', 'geoMercator',
        'geoAlbersUsa', 'geoNaturalEarth',
    ])
    _has_hover = ".on('mouseenter'" in content or '.on("mouseenter"' in content \
        or ".on('mouseover'" in content or '.on("mouseover"' in content
    _has_click = ".on('click'" in content or '.on("click"' in content
    if _is_map and _has_hover and not _has_click:
        findings.append(QAFinding(
            "error", "d3-bug", path,
            "Map component has hover interaction but no .on('click') handler — "
            "add click-to-select: set a selectedCountry/selectedState state on click, "
            "highlight the selected path with a distinct stroke, and show a selected badge in the filter toolbar"
        ))

    # Undeclared rect variable in measure/ResizeObserver context. A plain regex for
    # "const {...} = rect" (no scope awareness) false-positives on the extremely
    # common, perfectly valid pattern `const rect = el.getBoundingClientRect(); const
    # { width, height } = rect` — the declaration is just earlier in the same
    # function. Only flag destructuring sites where no `rect` declaration/param
    # exists anywhere earlier in the file.
    if re.search(r"(?:const|let)\s+\{[^}]*\}\s*=\s*rect\b(?!\.)", content):
        has_decl = bool(re.search(r"\b(?:const|let|var)\s+rect\s*=", content))
        has_param = bool(re.search(r"\(\s*(?:\[?\s*)?rect\b", content))
        if not has_decl and not has_param:
            findings.append(QAFinding(
                "error", "undefined-var", path,
                "Destructuring from 'rect' which is likely undeclared — add const rect = el.getBoundingClientRect()"
            ))

    return findings


def _check_package_json(content: str) -> list[QAFinding]:
    findings: list[QAFinding] = []
    try:
        pkg = json.loads(content)
    except Exception:
        findings.append(QAFinding("error", "config", "package.json", "Invalid JSON in package.json"))
        return findings

    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    required = ["react", "react-dom", "d3", "react-router-dom"]
    for r in required:
        if r not in deps:
            findings.append(QAFinding("warning", "deps", "package.json",
                                      f"Missing dependency: {r}"))

    banned = ["highcharts", "recharts", "chart.js", "react-simple-maps",
              "react-leaflet", "leaflet"]
    for b in banned:
        if b in deps:
            findings.append(QAFinding("error", "banned-lib", "package.json",
                                      f"Banned dependency in package.json: {b}"))
    return findings


def _check_vite_config(content: str) -> list[QAFinding]:
    findings: list[QAFinding] = []
    if "'react'" in content and "'react/jsx-dev-runtime'" in content:
        idx_bare = content.find("'react':")
        idx_dev  = content.find("'react/jsx-dev-runtime':")
        if idx_dev > idx_bare:
            findings.append(QAFinding(
                "error", "vite-config", "vite.config.ts",
                "'react' alias listed before 'react/jsx-dev-runtime' — sub-path aliases must come first"
            ))
    return findings


def _check_app_tsx(content: str, main_content: str = "") -> list[QAFinding]:
    findings: list[QAFinding] = []
    combined = content + main_content
    has_router = any(t in combined for t in ("BrowserRouter", "RouterProvider", "MemoryRouter"))
    if not has_router:
        if "<Routes" in content or "useNavigate" in content:
            findings.append(QAFinding("error", "routing", "src/App.tsx",
                                      "Uses React Router but BrowserRouter not found in App.tsx or main.tsx"))
    if "mobility-global-ds" not in content:
        findings.append(QAFinding("warning", "ds-usage", "src/App.tsx",
                                  "App.tsx does not import from mobility-global-ds — Header/Sidebar may be hand-rolled"))
    return findings


# ── Table name validation ─────────────────────────────────────────────────────

def _check_table_names(project_dir: Path) -> list[QAFinding]:
    """Validate useApi/apiAggregate table names against schema.sql."""
    findings: list[QAFinding] = []
    schema_path = project_dir / "api" / "schema.sql"
    if not schema_path.exists():
        schema_path = project_dir / "schema.sql"
    if not schema_path.exists():
        return findings

    schema_content = schema_path.read_text(encoding="utf-8", errors="ignore")
    table_names = set(
        t.lower() for t in re.findall(
            r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", schema_content, re.IGNORECASE
        )
    )
    if not table_names:
        return findings

    call_pattern = re.compile(r"""(?:useApi|apiAggregate)(?:<[^>]*>)?\s*\(\s*['"](\w+)['"]""")

    for fpath in project_dir.rglob("*.tsx"):
        if "node_modules" in fpath.parts:
            continue
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for m in call_pattern.finditer(content):
            table_arg = m.group(1)
            if table_arg.lower() not in table_names:
                rel = str(fpath.relative_to(project_dir)).replace("\\", "/")
                findings.append(QAFinding(
                    "error", "table-name", rel,
                    f"useApi/apiAggregate references table '{table_arg}' which does not exist in schema.sql. "
                    f"Available tables: {sorted(table_names)}"
                ))
    return findings


# ── Chart data-source validation ────────────────────────────────────────────────
# Guards against the class of bug where a chart config hardcodes canned numbers
# instead of fetching live from the API — prompt compliance ("LIVE DATA ONLY")
# was previously the only thing enforcing this, which is exactly how the radar
# chart empty-values regression slipped through.

def _extract_bracketed_items(text: str) -> list[str]:
    """Split an array literal's body into its top-level `{...}` object items via
    brace counting. Chart configs are plain data literals with no braces inside
    string values, so this simple approach is safe here."""
    items: list[str] = []
    depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start is not None:
                items.append(text[start:i + 1])
                start = None
    return items


def _check_chart_blocks(blocks_with_type_key: list[tuple[str, str]], rel: str) -> list[QAFinding]:
    findings: list[QAFinding] = []
    for block, type_key in blocks_with_type_key:
        type_m = re.search(rf"{type_key}:\s*'([^']+)'", block)
        chart_type = type_m.group(1) if type_m else None
        if not chart_type:
            continue

        if chart_type != "radar":
            has_live_table = bool(re.search(r"tableName:\s*'([^']+)'", block))
            data_has_content = bool(re.search(r"data:\s*\[\s*[^\]\s]", block))
            if not has_live_table and data_has_content:
                findings.append(QAFinding(
                    "error", "chart-data-source", rel,
                    f"'{chart_type}' chart has a hardcoded non-empty `data` array and no live "
                    f"`tableName` — it will always render the same canned numbers instead of "
                    f"fetching from the API. Charts must fetch live via `tableName`; `data` may "
                    f"only hold genuinely static UI content (e.g. a fixed legend), never metrics."
                ))
        else:
            # Radar has no live per-row fetch even when a (vestigial) tableName is
            # present, so check values emptiness unconditionally — this is a direct
            # regression guard for the exact bug that shipped with an empty `values: []`
            # on every series.
            series_values = re.findall(r"values:\s*\[([^\]]*)\]", block)
            empty_series = [v for v in series_values if not v.strip() or not re.search(r"\d", v)]
            if series_values and len(empty_series) == len(series_values):
                findings.append(QAFinding(
                    "error", "chart-data-source", rel,
                    "radar chart's series all have empty `values` arrays — the chart will render "
                    "nothing. Each series needs a static `values: number[]` (one per axis) grounded "
                    "in a real column, computed by the LLM at generation time."
                ))
            elif not series_values:
                findings.append(QAFinding(
                    "warning", "chart-data-source", rel,
                    "radar chart has no `series[].values` arrays — check the config was fully generated."
                ))
    return findings


def _check_chart_data_sources(project_dir: Path) -> list[QAFinding]:
    """Scan src/config/*.config.ts chart configs for hardcoded canned data or
    an empty radar series (see module comment above)."""
    findings: list[QAFinding] = []
    config_dir = project_dir / "src" / "config"
    if not config_dir.exists():
        return findings

    for fpath in config_dir.glob("*.config.ts"):
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if "chartType" not in content:
            continue
        rel = str(fpath.relative_to(project_dir)).replace("\\", "/")

        blocks: list[tuple[str, str]] = []
        if re.search(r"chartType:\s*'multi'", content):
            charts_m = re.search(r"charts:\s*\[", content)
            if charts_m:
                for item in _extract_bracketed_items(content[charts_m.end():]):
                    blocks.append((item, "type"))
        else:
            blocks.append((content, "chartType"))

        findings.extend(_check_chart_blocks(blocks, rel))

    return findings


# ── TypeScript compilation check ───────────────────────────────────────────────

def _tsc_check(project_dir: Path) -> list[QAFinding]:
    """Run tsc --noEmit and return TypeScript errors as QAFindings (max 20)."""
    import subprocess, os as _os
    # `npx tsc ...` via shell=True resolves to tsc.cmd, a batch-script wrapper —
    # cmd.exe treats '&' as a command separator, and this repo's path contains
    # "S&P Global", so cmd.exe splits the invocation mid-path and fails with
    # "'P' is not recognized as an internal or external command" (exactly the
    # fragment starting right after the '&'). Same root cause and same fix as the
    # WinError 193 issue in server.py's _typecheck_and_autofix: bypass the shell
    # and the .cmd wrapper entirely by invoking tsc's JS entry point via node.exe.
    tsc_js = project_dir / "node_modules" / "typescript" / "lib" / "tsc.js"
    if not tsc_js.exists():
        return [QAFinding("warning", "typescript", "", "tsc check skipped: typescript not installed")]
    try:
        from agents.uigen_agent import NODE_PATH
        node_exe = Path(NODE_PATH) / "node.exe"
        env = _os.environ.copy()
        env["PATH"] = NODE_PATH + _os.pathsep + env.get("PATH", "")
        result = subprocess.run(
            [str(node_exe), str(tsc_js), "--noEmit", "--pretty", "false"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=90,
            env=env,
        )
    except Exception as e:
        return [QAFinding("warning", "typescript", "", f"tsc check skipped: {e}")]

    if result.returncode == 0:
        return []

    findings: list[QAFinding] = []
    seen: set[tuple] = set()
    pat = re.compile(r'^(.+?)\((\d+),\d+\): error (TS\d+): (.+)$')

    for line in (result.stdout + "\n" + result.stderr).splitlines():
        m = pat.match(line.strip())
        if not m:
            continue
        fpath_raw, lineno, tscode, msg = m.groups()
        try:
            rel = str(Path(fpath_raw).relative_to(project_dir)).replace('\\', '/')
        except ValueError:
            rel = Path(fpath_raw).name
        key = (rel, tscode, msg[:60])
        if key in seen:
            continue
        seen.add(key)
        findings.append(QAFinding("error", "typescript", f"{rel}:{lineno}", f"{tscode}: {msg[:120]}"))
        if len(findings) >= 20:
            break

    if not findings and result.returncode != 0:
        out_snippet = (result.stdout + result.stderr)[:300].strip()
        findings.append(QAFinding("warning", "typescript", "tsconfig.json",
                                  f"tsc exited {result.returncode} (no parseable errors). Output: {out_snippet}"))

    return findings


# ── Playwright browser-runtime checks ─────────────────────────────────────────

# Console.error text that should be ignored (not real app errors)
_PW_IGNORE = frozenset([
    "Download the React DevTools",
    "React DevTools",
    "[vite]",
    "WebSocket connection",
    "vite:hmr",
    "Warning:",
    "Each child in a list should have a unique",
])

# Console.error patterns that definitely indicate a broken page
_PW_ERROR_PATTERNS = (
    "Error:",
    "Objects are not valid as a React child",
    "Cannot read properties of undefined",
    "is not a function",
    " is not defined",
    "Failed to fetch dynamically imported module",
    "Uncaught TypeError",
    "Uncaught ReferenceError",
    "ResizeObserver loop",
    "Maximum update depth exceeded",
    "Too many re-renders",
)


def _playwright_check(
    base_url: str,
    routes: list[str],
    timeout_ms: int = 15_000,
) -> tuple[list[str], list[str], list[QAFinding], bool]:
    """
    Load each route in a headless Chromium browser and capture JS errors.

    Returns (ok_routes, fail_routes, findings, playwright_ran).
    playwright_ran is False when playwright is not installed — caller should
    fall back to HTTP probes.
    """
    try:
        from playwright.sync_api import sync_playwright, Error as _PWErr  # type: ignore
    except ImportError:
        return [], [], [], False   # not installed

    ok_routes: list[str] = []
    fail_routes: list[str] = []
    findings: list[QAFinding] = []

    try:
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
            except Exception as e:
                # Browser binaries not installed — inform but don't crash
                findings.append(QAFinding(
                    "warning", "playwright", "",
                    f"Chromium launch failed (run 'playwright install chromium'): {e}"
                ))
                return [], [], findings, False

            ctx = browser.new_context(ignore_https_errors=True)

            _DYNAMIC_IMPORT_ERR = "dynamically imported module"

            for route in routes:
                page_errors: list[str] = []
                page = ctx.new_page()

                def _on_pageerror(err: Exception, _errs: list = page_errors) -> None:
                    _errs.append(f"Uncaught: {str(err)[:250]}")

                def _on_console(msg, _errs: list = page_errors) -> None:
                    if msg.type != "error":
                        return
                    txt = msg.text
                    if any(ig in txt for ig in _PW_IGNORE):
                        return
                    if any(pat in txt for pat in _PW_ERROR_PATTERNS):
                        _errs.append(txt[:250])

                page.on("pageerror", _on_pageerror)
                page.on("console",   _on_console)

                url = base_url.rstrip("/") + route
                try:
                    page.goto(url, wait_until="load", timeout=timeout_ms)
                    page.wait_for_timeout(2_500)   # let React finish rendering

                    # Check for Vite error overlay (only present when Vite itself errors)
                    try:
                        if page.locator("vite-error-overlay").count() > 0:
                            try:
                                overlay_txt = page.locator("vite-error-overlay").inner_text(timeout=2_000)
                                page_errors.append(f"Vite error overlay: {overlay_txt[:300]}")
                            except Exception:
                                page_errors.append("Vite error overlay detected")
                    except Exception:
                        pass

                    # Retry once if the error is specifically about dynamic imports
                    # (Vite pre-bundling was still running when we first hit the page)
                    if page_errors and any(_DYNAMIC_IMPORT_ERR in e for e in page_errors):
                        print(f"[QA] Vite pre-bundle not ready for {route} — retrying after 5s", flush=True)
                        page_errors.clear()
                        page.close()
                        time.sleep(5)
                        page = ctx.new_page()
                        page.on("pageerror", lambda err, _errs=page_errors: _errs.append(f"Uncaught: {str(err)[:250]}"))
                        page.on("console", lambda msg, _errs=page_errors: (
                            _errs.append(msg.text[:250])
                            if msg.type == "error"
                            and not any(ig in msg.text for ig in _PW_IGNORE)
                            and any(pat in msg.text for pat in _PW_ERROR_PATTERNS)
                            else None
                        ))
                        page.goto(url, wait_until="load", timeout=timeout_ms)
                        page.wait_for_timeout(3_000)
                        try:
                            if page.locator("vite-error-overlay").count() > 0:
                                try:
                                    overlay_txt = page.locator("vite-error-overlay").inner_text(timeout=2_000)
                                    page_errors.append(f"Vite error overlay: {overlay_txt[:300]}")
                                except Exception:
                                    page_errors.append("Vite error overlay detected")
                        except Exception:
                            pass

                    if page_errors:
                        fail_routes.append(route)
                        for err in page_errors[:4]:
                            findings.append(QAFinding("error", "browser-runtime", route, err))
                    else:
                        ok_routes.append(route)

                except _PWErr as e:
                    fail_routes.append(route)
                    findings.append(QAFinding("error", "browser-runtime", route,
                                              f"Navigation failed: {str(e)[:200]}"))
                except Exception as e:
                    fail_routes.append(route)
                    findings.append(QAFinding("error", "browser-runtime", route, str(e)[:200]))
                finally:
                    try:
                        page.close()
                    except Exception:
                        pass

            try:
                ctx.close()
                browser.close()
            except Exception:
                pass

    except Exception as e:
        findings.append(QAFinding("warning", "playwright", "",
                                  f"Playwright check error: {e}"))
        return ok_routes, fail_routes, findings, False

    return ok_routes, fail_routes, findings, True


# ── HTTP probe fallback ────────────────────────────────────────────────────────

def _get_page_routes(app_tsx: str) -> list[str]:
    """Extract static route paths from App.tsx <Route path="..." /> elements."""
    paths = re.findall(r'path=["\']([^"\']+)["\']', app_tsx)
    static = [p for p in paths if ":" not in p and "*" not in p]
    return list(dict.fromkeys(static)) or ["/"]


def _probe_http(base_url: str, path: str, timeout: int = 8) -> tuple[int, str]:
    """Return (status_code, error_message). status=0 means connection error."""
    url = base_url.rstrip("/") + path
    try:
        req = urllib.request.Request(url, headers={"Accept": "text/html,*/*"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, ""
    except urllib.error.HTTPError as e:
        return e.code, str(e)
    except Exception as e:
        return 0, str(e)


def _runtime_checks(base_url: str, routes: list[str]) -> tuple[list[str], list[str], list[QAFinding]]:
    """HTTP-only probe — only catches server errors (404/500), not browser JS crashes."""
    ok, fail, findings = [], [], []
    for route in routes:
        status, err = _probe_http(base_url, route)
        if status in (200, 304):
            ok.append(route)
        else:
            fail.append(route)
            findings.append(QAFinding(
                "error", "runtime", route,
                f"HTTP {status} for {base_url}{route}" + (f": {err}" if err else "")
            ))
    return ok, fail, findings


# ── API backend health checks ─────────────────────────────────────────────────

def _check_api_health(base_url: str, project_name: str, project_dir: Path | None = None) -> list[QAFinding]:
    """Probe API endpoints to verify the backend is working end-to-end."""
    findings: list[QAFinding] = []
    app_base = f"{base_url}/app/{project_name}"

    # 1. Check /api/metadata (basic data layer)
    status, err = _probe_http(app_base, "/api/metadata")
    if status not in (200, 304):
        findings.append(QAFinding("error", "api-health", "/api/metadata",
                                  f"API metadata endpoint returned HTTP {status}" + (f": {err}" if err else "")))
        return findings  # if metadata fails, backend is down — skip further checks

    # 2. Check /api/chat with a simple test message — but only for apps that
    # actually have an AI-chat/DataChat page. This used to probe unconditionally
    # for every app with a working backend, so a plain dashboard app with no chat
    # feature at all would "fail" a health check against a route it never had.
    has_chat_feature = False
    if project_dir is not None:
        src_dir = project_dir / "src"
        if src_dir.exists():
            for f in src_dir.rglob("*.tsx"):
                try:
                    if "/api/chat" in f.read_text(encoding="utf-8", errors="ignore"):
                        has_chat_feature = True
                        break
                except OSError:
                    continue
    if not has_chat_feature:
        return findings

    import json as _json
    chat_url = f"{app_base}/api/chat"
    try:
        body = _json.dumps({"messages": [{"role": "user", "content": "hello"}]}).encode()
        req = urllib.request.Request(
            chat_url,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = _json.loads(r.read().decode())
            if "error" in resp:
                findings.append(QAFinding("warning", "api-health", "/api/chat",
                                          f"Chat endpoint returned error: {str(resp['error'])[:200]}"))
    except urllib.error.HTTPError as e:
        body_text = ""
        try:
            body_text = e.read().decode()[:200]
        except Exception:
            pass
        if e.code == 503:
            findings.append(QAFinding("warning", "api-health", "/api/chat",
                                      f"LLM not configured: {body_text}"))
        elif e.code == 502:
            findings.append(QAFinding("warning", "api-health", "/api/chat",
                                      f"LLM connectivity issue (502): {body_text}. "
                                      "Check LITELLM_API_BASE is reachable and LITELLM_SSL_CERT is valid."))
        else:
            findings.append(QAFinding("warning", "api-health", "/api/chat",
                                      f"Chat endpoint returned HTTP {e.code}: {body_text}"))
    except Exception as e:
        findings.append(QAFinding("warning", "api-health", "/api/chat",
                                  f"Chat endpoint unreachable: {str(e)[:200]}"))

    return findings


# ── Main entry point ───────────────────────────────────────────────────────────

def run_qa(project_name: str, port: int, project_dir: Path) -> QAReport:
    """
    Run all QA checks on a generated project.
    Returns a QAReport with a pass/fail decision and scored findings.
    """
    findings: list[QAFinding] = []
    src_dir = project_dir / "src"

    # ── 1. Static analysis ────────────────────────────────────────────────────
    for fpath in project_dir.rglob("*.tsx"):
        if "node_modules" in fpath.parts:
            continue
        rel = str(fpath.relative_to(project_dir)).replace("\\", "/")
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        findings.extend(_static_check_file(rel, content))

    for fpath in project_dir.rglob("*.ts"):
        if "node_modules" in fpath.parts or fpath.name.endswith(".d.ts"):
            continue
        rel = str(fpath.relative_to(project_dir)).replace("\\", "/")
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        findings.extend(_static_check_file(rel, content))

    # ── 2. Config checks ──────────────────────────────────────────────────────
    pkg_path = project_dir / "package.json"
    if pkg_path.exists():
        findings.extend(_check_package_json(pkg_path.read_text(encoding="utf-8")))

    vite_path = project_dir / "vite.config.ts"
    if vite_path.exists():
        findings.extend(_check_vite_config(vite_path.read_text(encoding="utf-8")))

    app_path  = src_dir / "App.tsx"
    main_path = src_dir / "main.tsx"
    app_content  = app_path.read_text(encoding="utf-8")  if app_path.exists()  else ""
    main_content = main_path.read_text(encoding="utf-8") if main_path.exists() else ""
    if app_content:
        findings.extend(_check_app_tsx(app_content, main_content))

    # ── 3. Completeness checks ────────────────────────────────────────────────
    required_files = [
        "index.html", "package.json", "vite.config.ts",
        "src/main.tsx", "src/App.tsx", "src/types.ts",
    ]
    for rf in required_files:
        if not (project_dir / rf).exists():
            findings.append(QAFinding("error", "completeness", rf,
                                      f"Required file missing: {rf}"))

    # Data source: either src/data/index.ts (inline data), api/ (Python API-based),
    # or backend/ (Java Spring Boot API-based) — this check only recognized the
    # first two, so every Java-backend project was reported as having no data
    # source at all despite backend/schema.sql being real and working.
    has_data_file = (project_dir / "src" / "data" / "index.ts").exists()
    has_api_server = (project_dir / "api" / "app_server.py").exists() or \
                     (project_dir / "api" / "schema.sql").exists() or \
                     (project_dir / "backend" / "schema.sql").exists() or \
                     (project_dir / "backend" / "pom.xml").exists()
    if not has_data_file and not has_api_server:
        findings.append(QAFinding("error", "completeness", "src/data/index.ts",
                                  "No data source found: need src/data/index.ts, api/schema.sql, or backend/schema.sql"))

    pages_dir = src_dir / "pages"
    if pages_dir.exists():
        if not list(pages_dir.glob("*.tsx")):
            findings.append(QAFinding("warning", "completeness", "src/pages/",
                                      "No page files found in src/pages/"))
    else:
        findings.append(QAFinding("warning", "completeness", "src/pages/",
                                  "src/pages/ directory missing"))

    # ── 3b. Table name validation against schema.sql ────────────────────────
    table_findings = _check_table_names(project_dir)
    if table_findings:
        print(f"[QA] Table name mismatches: {len(table_findings)} error(s)", flush=True)
    findings.extend(table_findings)

    # ── 3c. Chart data-source validation (hardcoded data / empty radar values) ──
    chart_findings = _check_chart_data_sources(project_dir)
    if chart_findings:
        print(f"[QA] Chart data-source issues: {len(chart_findings)} finding(s)", flush=True)
    findings.extend(chart_findings)

    # ── 4. TypeScript compilation ─────────────────────────────────────────────
    print("[QA] Running tsc --noEmit…", flush=True)
    tsc_findings = _tsc_check(project_dir)
    findings.extend(tsc_findings)
    tsc_errors = sum(1 for f in tsc_findings if f.severity == "error")
    print(f"[QA] tsc: {tsc_errors} error(s)", flush=True)

    # ── 5. Runtime checks — Playwright → HTTP fallback ────────────────────────
    base_url = f"http://localhost:{port}/app/{project_name}"
    routes   = _get_page_routes(app_content) if app_content else ["/"]

    # Poll Vite dev server until it responds with 200 (pre-bundling complete).
    # Cold-start on a new project with d3/topojson can take 5-15s even with
    # optimizeDeps.include — warmup transforms fire after deps are ready.
    _poll_deadline = time.time() + 20
    _server_ready = False
    while time.time() < _poll_deadline:
        status, _ = _probe_http(f"http://localhost:{port}", f"/app/{project_name}/")
        if status in (200, 304):
            _server_ready = True
            break
        time.sleep(1)
    if _server_ready:
        time.sleep(2)  # extra buffer for module transforms after index.html is ready
        print(f"[QA] Vite server ready (took {20 - int(_poll_deadline - time.time())}s)", flush=True)
    else:
        print("[QA] WARNING: Vite server did not respond within 20s — proceeding anyway", flush=True)

    print("[QA] Attempting Playwright browser checks…", flush=True)
    pw_ok, pw_fail, pw_findings, pw_ran = _playwright_check(base_url, routes)

    if pw_ran:
        pages_ok   = pw_ok
        pages_fail = pw_fail
        findings.extend(pw_findings)
        runtime_mode = "playwright"
        print(f"[QA] Playwright: {len(pw_ok)} page(s) OK, {len(pw_fail)} page(s) with errors", flush=True)
        # Still probe root via HTTP as a quick sanity check
        root_status, _ = _probe_http(f"http://localhost:{port}", f"/app/{project_name}/")
        if root_status not in (200, 304):
            findings.append(QAFinding("error", "runtime", "/",
                                      f"Root URL returned HTTP {root_status}"))
            if "/" not in pages_fail:
                pages_fail.append("/")
        elif "/" not in pages_ok:
            pages_ok.append("/")
    else:
        # Playwright not available — fall back to HTTP probes
        runtime_mode = "http"
        print("[QA] Playwright not available — falling back to HTTP probes", flush=True)
        pages_ok, pages_fail, runtime_findings = _runtime_checks(base_url, routes)
        findings.extend(runtime_findings)
        root_status, _ = _probe_http(f"http://localhost:{port}", f"/app/{project_name}/")
        if root_status not in (200, 304):
            findings.append(QAFinding("error", "runtime", "/",
                                      f"Root URL returned HTTP {root_status}"))
            if "/" not in pages_fail:
                pages_fail.append("/")
        elif "/" not in pages_ok:
            pages_ok.append("/")
        # Add a one-time info finding so the build log shows playwright isn't active
        findings.append(QAFinding(
            "info", "playwright", "",
            "Playwright not installed — browser-runtime checks skipped. "
            "Run: pip install playwright && playwright install chromium"
        ))

    # ── 5c. API backend health check ────────────────────────────────────────────
    has_backend = (project_dir / "backend" / ".backend_type").exists() or \
                  (project_dir / "api" / "app_server.py").exists()
    if has_backend:
        print("[QA] Checking API backend health…", flush=True)
        api_findings = _check_api_health(f"http://localhost:{port}", project_name, project_dir)
        findings.extend(api_findings)
        if api_findings:
            print(f"[QA] API health: {len(api_findings)} issue(s) found", flush=True)
        else:
            print("[QA] API health: OK", flush=True)

    # ── 6. Score and sign-off ─────────────────────────────────────────────────
    error_count   = sum(1 for f in findings if f.severity == "error")
    warning_count = sum(1 for f in findings if f.severity == "warning")

    score = max(0, 100 - error_count * 15 - warning_count * 3)
    passed = error_count == 0 and score >= 70

    # De-duplicate findings by (category, file, message prefix)
    seen_keys: set[tuple] = set()
    deduped: list[QAFinding] = []
    for f in findings:
        key = (f.category, f.file, f.message[:60])
        if key not in seen_keys:
            seen_keys.add(key)
            deduped.append(f)
    findings = deduped

    runtime_label = "playwright" if runtime_mode == "playwright" else "http-probe"
    lines = [
        f"QA {'PASSED' if passed else 'FAILED'} — {project_name}  "
        f"(score {score}/100, runtime={runtime_label})",
        f"  Errors: {error_count}   Warnings: {warning_count}   "
        f"tsc errors: {tsc_errors}",
        f"  Pages OK: {len(pages_ok)}   Pages failed: {len(pages_fail)}",
    ]
    if pages_fail:
        lines.append(f"  Failed pages: {', '.join(pages_fail)}")
    if findings:
        lines.append("  Top findings:")
        priority = sorted(findings, key=lambda x: 0 if x.severity == "error" else
                                                   1 if x.severity == "warning" else 2)
        for f in priority[:10]:
            icon = "[ERROR]" if f.severity == "error" else ("[WARN]" if f.severity == "warning" else "[INFO]")
            lines.append(f"    {icon} [{f.category}] {f.file}: {f.message[:90]}")
    summary = "\n".join(lines)
    print("\n" + summary + "\n", flush=True)

    return QAReport(
        project_name=project_name,
        passed=passed,
        score=score,
        findings=findings,
        pages_ok=pages_ok,
        pages_fail=pages_fail,
        summary=summary,
    )
