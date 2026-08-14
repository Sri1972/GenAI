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

    # Hardcoded data in component (not in data/)
    ("data-location","warning", r"const\s+\w+\s*=\s*\[\s*\{[^}]{80,}",
     "Large inline data array in component — move to src/data/*.json"),

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
]


def _static_check_file(path: str, content: str) -> list[QAFinding]:
    findings: list[QAFinding] = []
    for category, severity, pattern, message in _STATIC_CHECKS:
        if re.search(pattern, content, re.IGNORECASE | re.DOTALL):
            findings.append(QAFinding(severity, category, path, message))
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


# ── TypeScript compilation check ───────────────────────────────────────────────

def _tsc_check(project_dir: Path) -> list[QAFinding]:
    """Run tsc --noEmit and return TypeScript errors as QAFindings (max 20)."""
    import subprocess
    try:
        result = subprocess.run(
            "npx tsc --noEmit --pretty false",
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=90,
            shell=True,
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

    # Data source: either src/data/index.ts (inline data) or api/ (API-based)
    has_data_file = (project_dir / "src" / "data" / "index.ts").exists()
    has_api_server = (project_dir / "api" / "app_server.py").exists() or \
                     (project_dir / "api" / "schema.sql").exists()
    if not has_data_file and not has_api_server:
        findings.append(QAFinding("error", "completeness", "src/data/index.ts",
                                  "No data source found: need src/data/index.ts or api/schema.sql"))

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

    # ── 4. TypeScript compilation ─────────────────────────────────────────────
    print("[QA] Running tsc --noEmit…", flush=True)
    tsc_findings = _tsc_check(project_dir)
    findings.extend(tsc_findings)
    tsc_errors = sum(1 for f in tsc_findings if f.severity == "error")
    print(f"[QA] tsc: {tsc_errors} error(s)", flush=True)

    # ── 5. Runtime checks — Playwright → HTTP fallback ────────────────────────
    base_url = f"http://localhost:{port}/app/{project_name}"
    routes   = _get_page_routes(app_content) if app_content else ["/"]

    # Give Vite a moment to settle
    time.sleep(2)

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
        f"QA {'✅ PASSED' if passed else '❌ FAILED'} — {project_name}  "
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
            icon = "🔴" if f.severity == "error" else ("🟡" if f.severity == "warning" else "ℹ️")
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
