"""
UIGen Agent — core logic for generating, running, stopping and deleting projects.
Used by both the FastAPI server (main.py) and the CLI client.
"""

import json
import os
import re
import shutil
import socket
import subprocess
import time
from pathlib import Path

from dotenv import load_dotenv

from .llm import chat, model_id as _llm_model_id
from .prompts import DS_ROOT
from .qa_agent import run_qa

load_dotenv(Path(__file__).parent.parent.parent / ".env")  # TurboUIGen/.env

import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    project_url as _project_url, health_url as _health_url,
    HTML_PORT_START, REACT_PORT_START, API_PORT_START,
    WEB_APPS_DIR, REGISTRY_FILE as _REG_FILE, PORTS_FILE as _PRT_FILE,
    GENERATED_ROOT,
)

NODE_PATH = r"C:\Program Files\nodejs"
DEPLOYMENT = _llm_model_id()  # for compatibility — shows model in health endpoint

# Web apps (React/Vite + HTML) go into generated/web-apps/
GENERATED_DIR  = WEB_APPS_DIR
_PORTS_FILE    = _PRT_FILE
_REGISTRY_FILE = _REG_FILE

# In-memory state (shared within the process)
_dev_servers: dict[str, subprocess.Popen] = {}
_api_servers: dict[str, subprocess.Popen] = {}
_dev_ports:   dict[str, int]              = {}
_api_ports:   dict[str, int]              = {}


# ── Project registry (fast JSON index, no directory scanning) ──────────────────

def _load_registry() -> dict:
    if _REGISTRY_FILE.exists():
        try:
            data = json.loads(_REGISTRY_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def _save_registry(reg: dict):
    _REGISTRY_FILE.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")


def registry_upsert(name: str, **kwargs):
    """Add or update a project entry in the registry."""
    reg = _load_registry()
    entry = reg.get(name, {"name": name})
    entry.update(kwargs)
    reg[name] = entry
    _save_registry(reg)


def registry_set_port(name: str, port: int, proj_type: str = "react"):
    """Persist port assignment so it survives API restarts."""
    registry_upsert(name, port=port, type=proj_type)


def registry_remove(name: str):
    reg = _load_registry()
    reg.pop(name, None)
    _save_registry(reg)


# ── Port persistence ───────────────────────────────────────────────────────────

def _load_ports() -> tuple[dict, dict]:
    """Load ports from disk. Returns (vite_ports, api_ports).
    Supports both old format { "name": port } and new { "name": { "vite": N, "api": N } }.
    """
    vite = {}
    api = {}
    if _PORTS_FILE.exists():
        try:
            raw = json.loads(_PORTS_FILE.read_text())
            for name, val in raw.items():
                if isinstance(val, dict):
                    if val.get("vite"):
                        vite[name] = val["vite"]
                    if val.get("api"):
                        api[name] = val["api"]
                elif isinstance(val, int):
                    vite[name] = val
        except Exception:
            pass
    return vite, api


def _save_ports():
    """Save unified ports file with both vite and api ports per project."""
    data = {}
    all_names = set(_dev_ports.keys()) | set(_api_ports.keys())
    for name in sorted(all_names):
        entry = {}
        if name in _dev_ports:
            entry["vite"] = _dev_ports[name]
        if name in _api_ports:
            entry["api"] = _api_ports[name]
        data[name] = entry
    _PORTS_FILE.write_text(json.dumps(data, indent=2))


_vite_loaded, _api_loaded = _load_ports()
_dev_ports.update(_vite_loaded)
_api_ports.update(_api_loaded)


def _port_is_free(port: int) -> bool:
    """Return True if nothing is bound to this port on localhost right now."""
    import socket as _sock
    with _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM) as s:
        s.setsockopt(_sock.SOL_SOCKET, _sock.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _next_port() -> int:
    """Return the lowest port >= REACT_PORT_START that is both free on the OS
    and not currently assigned to another project."""
    assigned = set(_dev_ports.values())
    port = REACT_PORT_START
    while port in assigned or not _port_is_free(port):
        port += 1
    return port


def _next_api_port() -> int:
    """Return the lowest port >= API_PORT_START that is both free on the OS
    and not currently assigned to another project's API server."""
    assigned = set(_api_ports.values())
    port = API_PORT_START
    while port in assigned or not _port_is_free(port):
        port += 1
    return port


# ── Helpers ────────────────────────────────────────────────────────────────────

def wait_for_port(port: int, timeout: int = 60) -> bool:
    """Wait until Vite is actually serving HTTP (not just TCP-open from a dying process)."""
    import urllib.request as _ur
    import urllib.error as _ue
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            _ur.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
            return True
        except _ue.HTTPError:
            return True   # got an HTTP error — server IS running
        except Exception:
            time.sleep(1)
    return False


def _wait_for_api(port: int, timeout: int = 15) -> bool:
    """Wait until the Python API server responds to /health."""
    import urllib.request as _ur
    import urllib.error as _ue
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            _ur.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
            return True
        except _ue.HTTPError:
            return True
        except Exception:
            time.sleep(0.5)
    print(f"[_wait_for_api] WARNING: API server on port {port} not ready after {timeout}s", flush=True)
    return False


_NPM_STRIP_FROM_PKG = {"mobility-global-ds", "@mobility-global/ds"}


def _npm_install(project_dir: Path) -> tuple[bool, str]:
    # Strip packages that are resolved via vite alias (not on npm)
    pj = project_dir / "package.json"
    if pj.exists():
        import re as _re
        txt = pj.read_text(encoding="utf-8")
        for pkg in _NPM_STRIP_FROM_PKG:
            txt = _re.sub(r',?\s*"' + _re.escape(pkg) + r'"\s*:\s*"[^"]*"', '', txt)
        pj.write_text(txt, encoding="utf-8")

    env = os.environ.copy()
    env["PATH"] = NODE_PATH + ";" + env.get("PATH", "")
    node_exe = Path(NODE_PATH) / "node.exe"
    npm_js   = Path(NODE_PATH) / "node_modules" / "npm" / "bin" / "npm-cli.js"
    result = subprocess.run(
        [str(node_exe), str(npm_js), "install"],
        cwd=str(project_dir),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    return result.returncode == 0, result.stdout + result.stderr


# ── Shared node_modules ────────────────────────────────────────────────────────
# All generated React apps share the same base packages. We install them once
# into SHARED_NM_DIR and junction each project's node_modules there, skipping
# the ~60s per-project npm install entirely.

_LEGACY_SHARED_NM_DIR = GENERATED_DIR.parent / "shared-node-modules"


def _needs_clean_paths() -> bool:
    """Return True if any project path contains characters that break Vite @fs/ URLs.
    On a clean Linux/AWS deployment the paths have no & or spaces, so junctions are
    unnecessary.  On Windows with OneDrive paths like 'S&P Global' they are required.
    """
    bad_chars = set("&")
    probe_paths = [str(_LEGACY_SHARED_NM_DIR), str(DS_ROOT)]
    return any(c in p for p in probe_paths for c in bad_chars)


def _clean_junction_base() -> Path:
    """Return the base directory for clean-path junctions.
    Respects TURBOUI_JUNCTION_DIR env var so it can be overridden in any environment.
    Falls back to <home>/.turboui-junctions which is writable without admin rights.
    """
    override = os.environ.get("TURBOUI_JUNCTION_DIR", "").strip()
    if override:
        return Path(override)
    return Path.home() / ".turboui-junctions"


_NEEDS_JUNCTIONS = _needs_clean_paths()
_JUNCTION_BASE   = _clean_junction_base() if _NEEDS_JUNCTIONS else None

# When paths contain & (OneDrive 'S&P Global'), store shared-node-modules at a clean path.
# Vite calls fs.realpathSync() to generate @fs/ URLs, which follows all junction chains to
# the final real directory. If that directory is at a clean path, @fs/ URLs contain no &.
SHARED_NM_DIR = (_JUNCTION_BASE / "shared-nm") if _NEEDS_JUNCTIONS else _LEGACY_SHARED_NM_DIR

# Forward-slash paths for use inside vite.config.ts — Vite requires forward slashes.
# SHARED_NM_DIR is already at a clean path, so _SHARED_NM_JUNCTION needs no extra junction.
_DS_CLEAN_JUNCTION  = (_JUNCTION_BASE / "mgds").as_posix() if _NEEDS_JUNCTIONS else Path(DS_ROOT).as_posix()
_SHARED_NM_JUNCTION = (SHARED_NM_DIR / "node_modules").as_posix()

# Canonical set of packages all generated apps use
_SHARED_PACKAGE_JSON = {
    "name": "turboui-shared-deps",
    "version": "1.0.0",
    "private": True,
    "dependencies": {
        "react": "^18.2.0",
        "react-dom": "^18.2.0",
        "react-router-dom": "^6.22.3",
        "recharts": "^2.12.2",
        "lucide-react": "^0.378.0",
        "d3": "^7.9.0",
        "d3-sankey": "^0.12.3",
        "topojson-client": "^3.1.0",
        "us-atlas": "^3.0.1",
        "world-atlas": "^2.0.2",
        "leaflet": "^1.9.4",
        "react-leaflet": "^4.2.1",
    },
    "devDependencies": {
        "typescript": "^5.4.5",
        "@types/react": "^18.2.79",
        "@types/react-dom": "^18.2.25",
        "@types/d3": "^7.4.3",
        "@types/d3-sankey": "^0.12.5",
        "@types/topojson-client": "^3.1.5",
        "@types/leaflet": "^1.9.14",
        "vite": "^5.2.8",
        "@vitejs/plugin-react": "^4.2.1",
        "tailwindcss": "^3.4.3",
        "postcss": "^8.4.38",
        "autoprefixer": "^10.4.19",
    },
}

# Packages the LLM commonly adds — pre-installed so they're always available
_EXTRA_PACKAGES = [
    "date-fns", "axios", "clsx", "classnames",
    "react-hook-form", "zod", "framer-motion",
    "@tanstack/react-table", "react-select",
    # Skill dependencies — always available so skill templates just work
    "pptxgenjs",        # PptxExport.skill.tsx
    "xlsx",             # ExcelExport.skill.tsx (SheetJS)
    "jspdf",            # PdfExport.skill.tsx
    "jspdf-autotable",  # PdfExport.skill.tsx — table rendering plugin
]


def _ensure_shared_nm() -> tuple[bool, str]:
    """Create and populate the shared node_modules folder if it doesn't exist."""
    SHARED_NM_DIR.mkdir(parents=True, exist_ok=True)
    nm = SHARED_NM_DIR / "node_modules"
    pj = SHARED_NM_DIR / "package.json"

    # Write package.json only if it doesn't exist or is outdated
    import json as _json
    current_pj = _json.dumps(_SHARED_PACKAGE_JSON, indent=2, sort_keys=True)
    if not pj.exists() or pj.read_text(encoding="utf-8").strip() != current_pj.strip():
        pj.write_text(current_pj, encoding="utf-8")

    env = os.environ.copy()
    env["PATH"] = NODE_PATH + ";" + env.get("PATH", "")
    node_exe = Path(NODE_PATH) / "node.exe"
    npm_js   = Path(NODE_PATH) / "node_modules" / "npm" / "bin" / "npm-cli.js"

    # Run npm install only if base packages are missing
    if not nm.exists() or not (nm / "vite").exists() or not (nm / "react").exists():
        r = subprocess.run(
            [str(node_exe), str(npm_js), "install"],
            cwd=str(SHARED_NM_DIR), env=env, capture_output=True, text=True, timeout=300,
        )
        if r.returncode != 0:
            return False, r.stdout + r.stderr

    # Install any extra packages not yet present (picked up whenever list changes)
    def _pkg_dir(p: str) -> Path:
        # scoped packages like @tanstack/react-table live under node_modules/@tanstack/react-table
        parts = p.split("/")
        return nm.joinpath(*parts) if p.startswith("@") else nm / p
    extra = [p for p in _EXTRA_PACKAGES if not _pkg_dir(p).exists()]
    if extra:
        subprocess.run(
            [str(node_exe), str(npm_js), "install", "--save-optional"] + extra,
            cwd=str(SHARED_NM_DIR), env=env, capture_output=True, text=True, timeout=120,
        )

    return True, "shared node_modules ready"


def _link_shared_nm(
    project_dir: Path,
    project_deps: dict,
    progress=None,
) -> tuple[bool, str]:
    """
    Link project_dir/node_modules to the shared node_modules store.
    On Windows paths containing & (e.g. OneDrive S&P Global), uses a clean-path
    junction so Vite never generates @fs/ URLs with & in them.
    On Linux/AWS with clean paths, uses a plain symlink directly to the real dir.
    Any packages the project needs that aren't in the shared store are installed
    there first — making them available to all future projects too.
    """
    nm_target = SHARED_NM_DIR / "node_modules"   # real path — where npm installs
    nm_link   = project_dir / "node_modules"

    # Install any missing packages into the shared store FIRST (before touching the link)
    # Packages that don't exist on npm — the LLM hallucinates these
    _BLOCKED_PACKAGES = {
        "@types/us-atlas", "@types/world-atlas", "@types/topojson",
        "@types/topojson-specification", "@types/geojson-vt",
        "mobility-global-ds", "@mobility-global/ds",
    }

    def _nm_exists(pkg: str) -> bool:
        parts = pkg.split("/")
        return nm_target.joinpath(*parts).exists() if pkg.startswith("@") else (nm_target / pkg).exists()
    missing = [p for p in project_deps if not _nm_exists(p) and p not in _BLOCKED_PACKAGES]

    if missing:
        if progress:
            progress(f"Installing new packages into shared store: {', '.join(missing)}")
        env = os.environ.copy()
        env["PATH"] = NODE_PATH + os.pathsep + env.get("PATH", "")
        node_exe = Path(NODE_PATH) / "node.exe"
        npm_js   = Path(NODE_PATH) / "node_modules" / "npm" / "bin" / "npm-cli.js"
        r = subprocess.run(
            [str(node_exe), str(npm_js), "install"] + missing,
            cwd=str(SHARED_NM_DIR), env=env, capture_output=True, text=True, timeout=120,
        )
        if r.returncode != 0:
            return False, f"Failed to install {missing}:\n{r.stdout + r.stderr}"
        if progress:
            progress(f"Added to shared store (available to all projects): {', '.join(missing)}")

    # If the link already points at the right target, nothing to do
    if _is_junction(nm_link) or nm_link.is_symlink():
        try:
            resolved = Path(os.readlink(str(nm_link)) if nm_link.is_symlink()
                            else str(nm_link))
            if resolved.resolve() == nm_target.resolve():
                return True, "junction already correct"
        except Exception:
            pass
        nm_link.unlink(missing_ok=True)
    elif nm_link.exists():
        # Real directory (e.g. legacy per-project install) — remove it.
        # Use cmd /c rmdir on Windows: handles locked files better than shutil.rmtree.
        if os.name == "nt":
            subprocess.run(
                ["cmd", "/c", "rmdir", "/s", "/q", str(nm_link)],
                capture_output=True, timeout=60,
            )
        else:
            shutil.rmtree(str(nm_link), ignore_errors=True)
        if nm_link.exists():
            return False, f"Could not remove existing node_modules at {nm_link}"

    # Create the junction / symlink to shared-nm
    if os.name == "nt":
        r = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(nm_link), str(nm_target)],
            capture_output=True, text=True,
        )
        return r.returncode == 0, r.stdout + r.stderr
    else:
        nm_link.symlink_to(nm_target)
        return True, "symlinked to shared node_modules"


def _is_junction(path: Path) -> bool:
    """Check if a path is a Windows directory junction."""
    try:
        return path.stat().st_reparse_tag == 0xA0000003  # IO_REPARSE_TAG_MOUNT_POINT
    except Exception:
        import os as _os
        try:
            return bool(_os.stat(str(path)).st_file_attributes & 0x400)
        except Exception:
            return False


def _get_project_deps(project_dir: Path) -> dict:
    """Read dependency names from the project's package.json."""
    import json as _json
    pj = project_dir / "package.json"
    if not pj.exists():
        return {}
    try:
        d = _json.loads(pj.read_text(encoding="utf-8"))
        return {**d.get("dependencies", {}), **d.get("devDependencies", {})}
    except Exception:
        return {}


def _scan_imports_from_files(project_dir: Path) -> set[str]:
    """
    Scan all .ts/.tsx source files for actual import statements (static and dynamic)
    and return the set of third-party package names referenced.

    This catches packages the LLM uses in code but forgot to add to package.json —
    a common failure mode that causes runtime 'module not found' errors.
    """
    # Matches: import X from 'pkg', import { X } from 'pkg', import 'pkg'
    _static_import = re.compile(r"""(?:import|export)\s+.*?from\s+['"]([^./][^'"]*?)['"]""")
    # Matches: await import('pkg'), import('pkg')
    _dynamic_import = re.compile(r"""import\s*\(\s*['"]([^./][^'"]*?)['"]""")
    # Matches: require('pkg')
    _require = re.compile(r"""require\s*\(\s*['"]([^./][^'"]*?)['"]""")

    packages: set[str] = set()

    # Built-in/virtual modules to skip
    _BUILTINS = {"react", "react-dom", "react-dom/client", "react-router-dom",
                 "vite", "@vitejs/plugin-react", "typescript",
                 "mobility-global-ds", "tailwindcss", "postcss", "autoprefixer"}

    for fpath in project_dir.rglob("*"):
        if fpath.suffix not in (".ts", ".tsx", ".js", ".jsx"):
            continue
        if "node_modules" in fpath.parts:
            continue
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for pat in (_static_import, _dynamic_import, _require):
            for m in pat.finditer(content):
                raw = m.group(1)
                # Extract package name: 'd3-sankey' from 'd3-sankey/src/foo'
                # Scoped: '@tanstack/react-table' from '@tanstack/react-table/core'
                if raw.startswith("@"):
                    parts = raw.split("/")
                    pkg = "/".join(parts[:2]) if len(parts) >= 2 else raw
                else:
                    pkg = raw.split("/")[0]
                packages.add(pkg)

    # Remove builtins and packages already known to be handled by aliases
    packages -= _BUILTINS
    return packages


# Ensure shared deps are installed at import time (runs once in background on first use)
_shared_nm_ready: bool = False


def _ensure_shared_nm_once() -> tuple[bool, str]:
    global _shared_nm_ready
    if _shared_nm_ready:
        # Even if ready, verify extra packages exist (catches partial installs)
        nm = SHARED_NM_DIR / "node_modules"
        def _pkg_dir(p: str) -> Path:
            parts = p.split("/")
            return nm.joinpath(*parts) if p.startswith("@") else nm / p
        missing = [p for p in _EXTRA_PACKAGES if not _pkg_dir(p).exists()]
        if missing:
            print(f"[_ensure_shared_nm_once] Missing packages detected: {missing}", flush=True)
            _shared_nm_ready = False
        else:
            return True, "ready"
    ok, log = _ensure_shared_nm()
    if ok:
        _shared_nm_ready = True
    return ok, log


def _start_vite(project_dir: Path, port: int) -> subprocess.Popen:
    # Clear Vite's dep cache so pre-bundling runs fresh every time.
    # Stale .vite/deps causes "Failed to fetch dynamically imported module" errors.
    import shutil
    _vite_cache = project_dir / "node_modules" / ".vite"
    if _vite_cache.exists():
        shutil.rmtree(_vite_cache, ignore_errors=True)

    node_exe = Path(NODE_PATH) / "node.exe"
    vite_js = Path(_SHARED_NM_JUNCTION) / "vite" / "bin" / "vite.js"
    if not vite_js.exists():
        vite_js = project_dir / "node_modules" / "vite" / "bin" / "vite.js"
    env = os.environ.copy()
    env["PATH"] = NODE_PATH + os.pathsep + env.get("PATH", "")
    # --preserve-symlinks stops Node from calling realpathSync on module paths,
    # so @fs/ URLs stay at the clean junction path instead of resolving to OneDrive.
    if _NEEDS_JUNCTIONS:
        existing = env.get("NODE_OPTIONS", "")
        if "--preserve-symlinks" not in existing:
            env["NODE_OPTIONS"] = (existing + " --preserve-symlinks").strip()
    # Redirect output to a log file so the pipe buffer never fills and blocks the process.
    log_file = open(str(project_dir / "vite.log"), "w", encoding="utf-8", errors="replace")
    kwargs: dict = {"cwd": str(project_dir), "env": env, "stdout": log_file, "stderr": log_file}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen([str(node_exe), str(vite_js), "--port", str(port), "--host", "0.0.0.0"], **kwargs)


def _start_api_server(project_dir: Path, api_port: int = 8080) -> subprocess.Popen | None:
    """Start the Python API server for generated apps (api/app_server.py)."""
    api_dir = project_dir / "api"
    server_file = api_dir / "app_server.py"

    # Legacy fallback: check root-level files from older generations
    if not server_file.exists():
        server_file = project_dir / "app_server.py"
    if not server_file.exists():
        server_file = project_dir / "api_server.py"
    if not server_file.exists():
        # Auto-bundle if schema.sql exists but server was never bundled
        schema_found = (api_dir / "schema.sql").exists() or (project_dir / "schema.sql").exists()
        if schema_found:
            tmpl = _SKILLS_DIR / "app_server_template.py"
            if tmpl.exists():
                api_dir.mkdir(exist_ok=True)
                server_file = api_dir / "app_server.py"
                server_file.write_text(tmpl.read_text(encoding="utf-8"), encoding="utf-8")
                # Move schema/seed into api/ if they're at root level
                for f in ("schema.sql", "seed.sql"):
                    root_f = project_dir / f
                    if root_f.exists() and not (api_dir / f).exists():
                        root_f.rename(api_dir / f)
                print(f"[api_server] Auto-bundled api/app_server.py (schema.sql present)", flush=True)
            else:
                return None
        else:
            return None

    # Use the server file's parent as cwd so relative paths (schema.sql, .env) resolve
    cwd = str(server_file.parent)
    env = os.environ.copy()
    env["API_PORT"] = str(api_port)
    log_file = open(str(project_dir / "api_server.log"), "w", encoding="utf-8", errors="replace")
    kwargs: dict = {"cwd": cwd, "env": env, "stdout": log_file, "stderr": log_file}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(["python", str(server_file)], **kwargs)
    print(f"[api_server] Started Python API server on port {api_port} (PID {proc.pid}, cwd={cwd})", flush=True)
    return proc


def _stop_api_server(project_name: str):
    """Stop the API server process for a project."""
    proc = _api_servers.pop(project_name, None)
    if proc:
        try:
            proc.terminate()
            proc.wait(timeout=8)
        except Exception:
            try:
                proc.kill()
                proc.wait(timeout=5)
            except Exception:
                pass
    # Kill any python process on this project's API port
    api_port = _api_ports.get(project_name)
    if api_port:
        try:
            subprocess.run(
                f'for /f "tokens=5" %a in (\'netstat -ano ^| findstr "LISTENING" ^| findstr ":{api_port} "\') do taskkill /PID %a /F',
                shell=True, capture_output=True, timeout=5,
            )
        except Exception:
            pass


def _make_junction(link: Path, target: Path):
    """Create a Windows directory junction link → target."""
    link.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
    )


def _ensure_ds_junction():
    """Create a clean-path junction for UIDesignSystem if the project path contains
    characters (like &) that break Vite @fs/ URLs.  No-op on clean deployments."""
    if not _NEEDS_JUNCTIONS:
        return
    junc = Path(_DS_CLEAN_JUNCTION)
    if not junc.exists():
        _make_junction(junc, DS_ROOT)


def _ensure_nm_junction():
    """No-op — SHARED_NM_DIR is now stored at a clean path, no junction needed."""
    pass


# Create junctions at import time (only when the path contains & or spaces)
_ensure_ds_junction()
_ensure_nm_junction()


def _link_ds_into_project(project_dir: Path):
    """No-op — DS is resolved via C:/TurboUI/mgds junction in vite.config.ts."""
    pass


# ── Post-processors (extracted to postprocessors.py) ──────────────────────────
from agents.postprocessors import (
    _patch_vite_for_ds, _fix_chart_container, _fix_self_wrapping_charts,
    _fix_badge_variants, _fix_prop_contracts, _patch_map_components,
    _patch_dynamic_imports, _patch_index_html, _patch_highcharts_more,
    _ensure_tsconfig_vite_types, run_all_postprocessors,
)


# ── Boilerplate safety net ────────────────────────────────────────────────────

def _ensure_boilerplate(files: dict, project_name: str) -> dict:
    """Ensure essential boilerplate files exist. Generates from templates if missing."""
    if "index.html" not in files:
        title = project_name.replace("-", " ").title()
        files["index.html"] = (
            '<!DOCTYPE html>\n<html lang="en">\n  <head>\n'
            '    <meta charset="UTF-8" />\n'
            '    <link rel="icon" type="image/svg+xml" href="./vite.svg" />\n'
            '    <meta name="viewport" content="width=device-width, initial-scale=1.0" />\n'
            f'    <title>{title}</title>\n'
            '    <link rel="preconnect" href="https://fonts.googleapis.com" />\n'
            '    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />\n'
            '    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />\n'
            '  </head>\n  <body>\n    <div id="root"></div>\n'
            '    <script type="module" src="/src/main.tsx"></script>\n'
            '  </body>\n</html>\n'
        )
        print(f"[boilerplate] Generated missing index.html", flush=True)

    if "package.json" not in files:
        files["package.json"] = (
            '{\n  "name": "' + project_name + '",\n'
            '  "private": true,\n  "version": "0.1.0",\n  "type": "module",\n'
            '  "scripts": {\n    "dev": "vite",\n    "build": "tsc && vite build",\n    "preview": "vite preview"\n  },\n'
            '  "dependencies": {\n'
            '    "react": "^18.2.0",\n    "react-dom": "^18.2.0",\n'
            '    "react-router-dom": "^6.22.0",\n    "lucide-react": "^0.344.0",\n'
            '    "d3": "^7.9.0"\n  },\n'
            '  "devDependencies": {\n'
            '    "typescript": "^5.3.3",\n    "@types/react": "^18.2.56",\n'
            '    "@types/react-dom": "^18.2.19",\n    "@types/d3": "^7.4.3",\n'
            '    "vite": "^5.1.4",\n    "@vitejs/plugin-react": "^4.2.1",\n'
            '    "tailwindcss": "^3.4.1",\n    "postcss": "^8.4.35",\n'
            '    "autoprefixer": "^10.4.18"\n  }\n}\n'
        )
        print(f"[boilerplate] Generated missing package.json", flush=True)

    if "tsconfig.json" not in files:
        files["tsconfig.json"] = (
            '{\n  "compilerOptions": {\n    "target": "ES2020",\n    "useDefineForClassFields": true,\n'
            '    "lib": ["ES2020", "DOM", "DOM.Iterable"],\n    "module": "ESNext",\n'
            '    "skipLibCheck": true,\n    "moduleResolution": "bundler",\n'
            '    "allowImportingTsExtensions": true,\n    "resolveJsonModule": true,\n'
            '    "isolatedModules": true,\n    "noEmit": true,\n    "jsx": "react-jsx",\n'
            '    "strict": true,\n    "noUnusedLocals": false,\n    "noUnusedParameters": false,\n'
            '    "noFallthroughCasesInSwitch": true,\n    "types": ["vite/client"]\n'
            '  },\n  "include": ["src"]\n}\n'
        )
        print(f"[boilerplate] Generated missing tsconfig.json", flush=True)

    if "postcss.config.js" not in files:
        files["postcss.config.js"] = "export default {\n  plugins: {\n    tailwindcss: {},\n    autoprefixer: {}\n  }\n}\n"
        print(f"[boilerplate] Generated missing postcss.config.js", flush=True)

    if "tailwind.config.js" not in files:
        files["tailwind.config.js"] = (
            "/** @type {import('tailwindcss').Config} */\nexport default {\n"
            "  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],\n"
            "  theme: { extend: { fontFamily: { sans: ['Inter', 'sans-serif'] } } },\n"
            "  plugins: []\n}\n"
        )
        print(f"[boilerplate] Generated missing tailwind.config.js", flush=True)

    if "src/main.tsx" not in files:
        files["src/main.tsx"] = (
            "import React from 'react'\n"
            "import ReactDOM from 'react-dom/client'\n"
            "import { BrowserRouter } from 'react-router-dom'\n"
            "import App from './App'\n"
            "import './index.css'\n\n"
            "const BASE = import.meta.env.BASE_URL.replace(/\\/$/, '') || ''\n\n"
            "ReactDOM.createRoot(document.getElementById('root')!).render(\n"
            "  <React.StrictMode>\n"
            "    <BrowserRouter basename={BASE} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>\n"
            "      <App />\n"
            "    </BrowserRouter>\n"
            "  </React.StrictMode>\n)\n"
        )
        print(f"[boilerplate] Generated missing src/main.tsx", flush=True)

    if "src/index.css" not in files:
        files["src/index.css"] = (
            "@tailwind base;\n@tailwind components;\n@tailwind utilities;\n\n"
            "* { box-sizing: border-box; }\n\n"
            "body {\n  margin: 0;\n  padding: 0;\n"
            "  font-family: 'Inter', sans-serif;\n"
            "  background-color: #F1F5F9;\n  color: #1E293B;\n}\n"
        )
        print(f"[boilerplate] Generated missing src/index.css", flush=True)

    return files


# ── API Server bundling ───────────────────────────────────────────────────────
_SKILLS_DIR = Path(__file__).parent / "services_engineer" / "templates"

def _bundle_api_server(files: dict) -> dict:
    """If schema.sql is present, bundle API server into api/ subfolder + useApi hook."""
    if "schema.sql" not in files:
        return files

    # Move schema.sql and seed.sql into api/ subfolder
    files["api/schema.sql"] = files.pop("schema.sql")
    if "seed.sql" in files:
        seed_content = files.pop("seed.sql")
        # Fix LLM-generated backslash escapes: \' → '' (SQL standard)
        seed_content = seed_content.replace("\\'", "''")
        files["api/seed.sql"] = seed_content

    # 1. Bundle app_server.py template into api/
    server_template = _SKILLS_DIR / "app_server_template.py"
    if server_template.exists():
        files["api/app_server.py"] = server_template.read_text(encoding="utf-8")
    else:
        print("[_bundle_api_server] WARNING: app_server_template.py not found", flush=True)
        return files

    # 2. Bundle useApi hook
    hook_template = _SKILLS_DIR / "useApi.hook.ts"
    if hook_template.exists():
        files["src/hooks/useApi.ts"] = hook_template.read_text(encoding="utf-8")

    # 3. Bundle ExportToolbar shared component
    export_toolbar = _SKILLS_DIR / "ExportToolbar.component.tsx"
    if export_toolbar.exists():
        files["src/components/ExportToolbar.tsx"] = export_toolbar.read_text(encoding="utf-8")

    # 3. Fill and bundle .env into api/
    env_template = _SKILLS_DIR / "app_server_env_template.txt"
    if env_template.exists():
        from dotenv import dotenv_values
        parent_env = dotenv_values(Path(__file__).parent.parent.parent / ".env")
        env_content = env_template.read_text(encoding="utf-8")
        env_content = env_content.replace("{{LITELLM_API_BASE}}", parent_env.get("LITELLM_API_BASE", ""))
        env_content = env_content.replace("{{LITELLM_API_KEY}}", parent_env.get("LITELLM_API_KEY", ""))
        env_content = env_content.replace("{{LITELLM_SSL_CERT}}", parent_env.get("LITELLM_SSL_CERT", ""))
        env_content = env_content.replace("{{LITELLM_MODEL}}", parent_env.get("LITELLM_SONNET_46_MODEL", "claude-sonnet-4-6"))
        files["api/.env"] = env_content

    # 4. Bundle requirements.txt into api/
    files["api/requirements.txt"] = "fastapi\nuvicorn\npython-dotenv\nopenai\nhttpx\nopenpyxl\nPyMuPDF\n"

    print(f"[_bundle_api_server] Bundled into api/: app_server.py + schema.sql + .env + requirements.txt", flush=True)
    return files


def _ensure_schema_sql(files: dict, force: bool = False) -> dict:
    """
    Safety net: if the LLM generated API-first signals (useApi imports, tableName in configs)
    but forgot to include schema.sql, auto-generate it from src/types.ts.
    When force=True, skip signal detection — always generate if schema.sql is missing.
    """
    if "schema.sql" in files or "api/schema.sql" in files:
        return files

    if not force:
        # Detect API-first signals
        has_use_api = any("useApi" in (v if isinstance(v, str) else "") for v in files.values())
        has_table_name = any("tableName" in (v if isinstance(v, str) else "") for k, v in files.items() if k.endswith(".config.ts"))
        if not has_use_api and not has_table_name:
            return files

    types_content = files.get("src/types.ts", "")
    if not types_content or not isinstance(types_content, str):
        print("[_ensure_schema_sql] WARNING: src/types.ts is missing or empty — cannot generate schema", flush=True)
        return files

    print("[_ensure_schema_sql] schema.sql missing — generating from types.ts", flush=True)

    import re
    interfaces = re.findall(
        r"export\s+interface\s+(\w+)\s*\{([^}]+)\}",
        types_content, re.DOTALL
    )
    if not interfaces:
        print("[_ensure_schema_sql] WARNING: no interfaces found in types.ts", flush=True)
        return files

    def _to_snake(name: str) -> str:
        s = re.sub(r"([A-Z])", r"_\1", name).lstrip("_").lower()
        return s

    def _ts_to_sqlite(ts_type: str) -> str:
        ts_type = ts_type.strip().rstrip(";").strip()
        if "number" in ts_type:
            if "[]" in ts_type:
                return "TEXT"
            if "null" in ts_type:
                return "REAL"
            return "REAL"
        return "TEXT"

    schema_lines = []
    table_names = []
    for iface_name, body in interfaces:
        # Skip helper/aggregation interfaces — only process primary data types
        fields = re.findall(r"(\w+)\s*[?]?\s*:\s*([^\n;]+)", body)
        if not fields or len(fields) < 3:
            continue
        # Only process interfaces that have an 'id' field — those are DB tables
        field_names = [f[0] for f in fields]
        if "id" not in field_names:
            continue

        # Convert interface name to table name (e.g. GlobalSale -> global_sales)
        table = _to_snake(iface_name)
        if not table.endswith("s"):
            table += "s"

        cols = []
        for fname, ftype in fields:
            if fname == "id":
                cols.append("  id INTEGER PRIMARY KEY AUTOINCREMENT")
            else:
                sqlite_type = _ts_to_sqlite(ftype)
                # Improve type detection from field name
                if any(x in fname for x in ["revenue", "growth", "share", "pct", "bound"]):
                    sqlite_type = "REAL"
                elif any(x in fname for x in ["units", "_count", "dealer_count"]) or fname.endswith("_id"):
                    sqlite_type = "INTEGER"
                nullable = "null" in ftype.lower()
                null_str = "" if nullable else " NOT NULL"
                cols.append(f"  {fname} {sqlite_type}{null_str}")

        if cols:
            schema_lines.append(
                f"CREATE TABLE IF NOT EXISTS {table} (\n"
                + ",\n".join(cols)
                + "\n);"
            )
            table_names.append(table)

    if schema_lines:
        files["schema.sql"] = "\n\n".join(schema_lines)
        print(f"[_ensure_schema_sql] Generated schema.sql with tables: {table_names}", flush=True)

        # Generate seed data via LLM call
        schema_text = files["schema.sql"]
        seed_prompt = (
            "Generate realistic seed.sql INSERT statements for the following SQLite schema.\n"
            "Rules:\n"
            "- At least 40-60 rows per main data table, fewer for small lookup tables\n"
            "- Use realistic values — real country names, real car brands, plausible numbers\n"
            "- Return ONLY valid SQL INSERT statements, no comments or explanations\n"
            "- Use single quotes for strings, NULL (not 'null') for nulls\n\n"
            f"Schema:\n{schema_text}"
        )
        try:
            from agents.llm import chat as _chat_llm
            seed_content = _chat_llm(
                [{"role": "user", "content": seed_prompt}],
                system="You are a SQL data generator. Return ONLY valid SQLite INSERT statements.",
                max_tokens=16000,
            )
            if seed_content and "INSERT" in seed_content.upper():
                # Strip markdown fences if present
                if seed_content.strip().startswith("```"):
                    lines = seed_content.strip().splitlines()
                    seed_content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
                files["seed.sql"] = seed_content
                print(f"[_ensure_schema_sql] Generated seed.sql via LLM ({len(seed_content)} chars)", flush=True)
            else:
                files["seed.sql"] = f"-- Placeholder: seed data generation failed\n"
                print(f"[_ensure_schema_sql] LLM seed generation returned no INSERT statements", flush=True)
        except Exception as e:
            files["seed.sql"] = f"-- Placeholder: seed data generation failed ({e})\n"
            print(f"[_ensure_schema_sql] Seed LLM call failed: {e}", flush=True)

    return files








def _repair_json(content: str, rel_path: str) -> str:
    """Validate JSON content and attempt common repairs if invalid."""
    import json, re
    content = content.strip()
    # Strip markdown fences if LLM wrapped the JSON
    if content.startswith("```"):
        lines = content.splitlines()
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:]).strip()
    try:
        json.loads(content)
        return content
    except json.JSONDecodeError:
        pass
    # Common fix 1: trailing commas before ] or }
    fixed = re.sub(r",\s*([}\]])", r"\1", content)
    try:
        json.loads(fixed)
        print(f"[_repair_json] Fixed trailing commas in {rel_path}", flush=True)
        return fixed
    except json.JSONDecodeError:
        pass
    # Common fix 2: single quotes → double quotes
    fixed2 = fixed.replace("'", '"')
    try:
        json.loads(fixed2)
        print(f"[_repair_json] Fixed quotes in {rel_path}", flush=True)
        return fixed2
    except json.JSONDecodeError:
        pass
    # Common fix 3: truncated JSON — attempt to close open brackets/braces
    depth_bracket = fixed.count("[") - fixed.count("]")
    depth_brace = fixed.count("{") - fixed.count("}")
    if depth_bracket > 0 or depth_brace > 0:
        # Remove trailing comma if present
        closed = re.sub(r",\s*$", "", fixed)
        closed += "]" * depth_bracket + "}" * depth_brace
        try:
            json.loads(closed)
            print(f"[_repair_json] Closed truncated JSON in {rel_path}", flush=True)
            return closed
        except json.JSONDecodeError:
            pass
    # Common fix 4: JS-style comments
    no_comments = re.sub(r"//.*?$", "", fixed, flags=re.MULTILINE)
    no_comments = re.sub(r"/\*.*?\*/", "", no_comments, flags=re.DOTALL)
    try:
        json.loads(no_comments)
        print(f"[_repair_json] Stripped comments in {rel_path}", flush=True)
        return no_comments
    except json.JSONDecodeError:
        pass
    print(f"[_repair_json] WARNING: Could not repair {rel_path} — writing as-is", flush=True)
    return content


_PRESERVE_FILES = {".history.json", ".buildlog.json", ".meta.json", ".docker.json", "screenshots", "docker", "app.db"}

def _write_files(project_dir: Path, files: dict):
    project_dir.mkdir(parents=True, exist_ok=True)
    for child in project_dir.iterdir():
        if child.name in ("node_modules",) or child.name in _PRESERVE_FILES:
            continue
        try:
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
        except Exception:
            pass
    from agents.sanitize_js import sanitize
    for rel_path, content in files.items():
        fp = project_dir / rel_path
        fp.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, list):
            content = "\n".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            )
        # Skip empty content entirely — never write blank files
        if not content or not content.strip():
            print(f"[_write_files] Skipping empty content for {rel_path}", flush=True)
            continue
        if rel_path.endswith(".json"):
            content = _repair_json(content, rel_path)
        content = sanitize(content, rel_path)
        fp.write_text(content, encoding="utf-8")
    # Junction must be created after node_modules exists (npm install runs after _write_files)
    # So we call _link_ds_into_project separately after npm install.


_REQUIRED_COMPONENT_SOURCES: dict[str, str] = {
    "FilterDropdown": """\
import { useMemo } from 'react'

type Option = string | { value: string; label: string }

interface Props {
  value: string
  options: Option[]
  onChange: (value: string) => void
  label?: string
  className?: string
}

export default function FilterDropdown({ value, options, onChange, label, className = '' }: Props) {
  const normalized = useMemo(() =>
    options.map((o) => typeof o === 'string' ? { value: o, label: o } : o),
    [options]
  )
  return (
    <div className={`flex flex-col gap-[4px] ${className}`}>
      {label && <span className="text-[11px] font-medium text-[#9CA3AF] uppercase tracking-wide">{label}</span>}
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="h-[40px] min-w-[140px] appearance-none pl-[12px] pr-[32px] rounded-[8px] border border-[#E5E7EB] bg-white text-[14px] text-[#132445] outline-none focus:border-[#0064D2] cursor-pointer"
        >
          {normalized.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <svg className="w-4 h-4 absolute right-[10px] top-1/2 -translate-y-1/2 text-[#9CA3AF] pointer-events-none" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 9l6 6 6-6" />
        </svg>
      </div>
    </div>
  )
}
export { FilterDropdown }
""",
    "Pagination": """\
interface Props {
  page: number
  pageCount: number
  onChange: (page: number) => void
}

export default function Pagination({ page, pageCount, onChange }: Props) {
  if (pageCount <= 1) return null
  const pages: (number | '...')[] = []
  if (pageCount <= 7) {
    for (let i = 1; i <= pageCount; i++) pages.push(i)
  } else {
    pages.push(1)
    if (page > 3) pages.push('...')
    for (let i = Math.max(2, page - 1); i <= Math.min(pageCount - 1, page + 1); i++) pages.push(i)
    if (page < pageCount - 2) pages.push('...')
    pages.push(pageCount)
  }
  const btn = (label: string | number, target: number, disabled: boolean) => (
    <button
      key={String(label)}
      disabled={disabled}
      onClick={() => !disabled && onChange(target)}
      className="h-[32px] min-w-[32px] px-[8px] rounded-[6px] text-[13px] font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
      style={{
        backgroundColor: target === page ? '#0064D2' : 'transparent',
        color: target === page ? '#FFFFFF' : '#374151',
        border: target === page ? 'none' : '1px solid #E5E7EB',
      }}
    >
      {label}
    </button>
  )
  return (
    <div className="flex items-center gap-[4px]">
      {btn('\\u2039', page - 1, page <= 1)}
      {pages.map((p, i) =>
        p === '...'
          ? <span key={`e${i}`} className="px-[4px] text-[#9CA3AF] text-[13px]">\\u2026</span>
          : btn(p, p as number, (p as number) === page)
      )}
      {btn('\\u203a', page + 1, page >= pageCount)}
    </div>
  )
}
export { Pagination }
""",
    "PersonaCard": """\
interface Persona {
  id?: string | number
  name: string
  role?: string
  description?: string
  accent?: string
  color?: string
  avatar?: string
  [key: string]: any
}

interface Props {
  persona: Persona
  active: boolean
  onClick: () => void
}

export default function PersonaCard({ persona, active, onClick }: Props) {
  const accent = persona.accent ?? persona.color ?? '#0064D2'
  const initials = persona.name.split(' ').map((w: string) => w[0]).join('').slice(0, 2).toUpperCase()
  return (
    <button
      onClick={onClick}
      className="w-full text-left p-[12px] rounded-[10px] border transition-all"
      style={{
        borderColor: active ? accent : '#E5E7EB',
        backgroundColor: active ? `${accent}12` : '#FFFFFF',
        boxShadow: active ? `0 0 0 2px ${accent}40` : 'none',
      }}
    >
      <div className="flex items-center gap-[10px]">
        {persona.avatar ? (
          <img src={persona.avatar} alt={persona.name} className="w-[36px] h-[36px] rounded-full object-cover flex-shrink-0" />
        ) : (
          <div
            className="w-[36px] h-[36px] rounded-full flex items-center justify-center text-white text-[13px] font-bold flex-shrink-0"
            style={{ backgroundColor: accent }}
          >
            {initials}
          </div>
        )}
        <div className="min-w-0">
          <div className="text-[13px] font-semibold truncate" style={{ color: '#132445' }}>{persona.name}</div>
          {persona.role && <div className="text-[11px] truncate" style={{ color: '#9CA3AF' }}>{persona.role}</div>}
        </div>
      </div>
    </button>
  )
}
export { PersonaCard }
""",
}


def _build_usa_map_wrapper(wrapped_name: str) -> str:
    """Build a UsaSalesMap.tsx that wraps whatever USA map variant was generated."""
    return f"""\
import {wrapped_name} from './{wrapped_name}'

const ABBR_TO_STATE: Record<string, string> = {{
  AL: 'Alabama', AK: 'Alaska', AZ: 'Arizona', AR: 'Arkansas', CA: 'California',
  CO: 'Colorado', CT: 'Connecticut', DE: 'Delaware', FL: 'Florida', GA: 'Georgia',
  HI: 'Hawaii', ID: 'Idaho', IL: 'Illinois', IN: 'Indiana', IA: 'Iowa',
  KS: 'Kansas', KY: 'Kentucky', LA: 'Louisiana', ME: 'Maine', MD: 'Maryland',
  MA: 'Massachusetts', MI: 'Michigan', MN: 'Minnesota', MS: 'Mississippi', MO: 'Missouri',
  MT: 'Montana', NE: 'Nebraska', NV: 'Nevada', NH: 'New Hampshire', NJ: 'New Jersey',
  NM: 'New Mexico', NY: 'New York', NC: 'North Carolina', ND: 'North Dakota', OH: 'Ohio',
  OK: 'Oklahoma', OR: 'Oregon', PA: 'Pennsylvania', RI: 'Rhode Island', SC: 'South Carolina',
  SD: 'South Dakota', TN: 'Tennessee', TX: 'Texas', UT: 'Utah', VT: 'Vermont',
  VA: 'Virginia', WA: 'Washington', WV: 'West Virginia', WI: 'Wisconsin', WY: 'Wyoming',
  DC: 'District of Columbia',
}}

const STATE_TO_ABBR: Record<string, string> = Object.fromEntries(
  Object.entries(ABBR_TO_STATE).map(([k, v]) => [v, k])
) as Record<string, string>

export interface StateSaleRow {{
  state: string
  make: string
  units: number
  abbr?: string
}}

interface Props {{
  stateSales: StateSaleRow[]
  makeFilter?: string
  height?: number
  selectedState?: string
  onStateClick?: (stateName: string) => void
}}

export default function UsaSalesMap({{ stateSales, makeFilter, height, selectedState: _selectedState, onStateClick }}: Props) {{
  const rows = stateSales.map((r) => ({{
    ...r,
    abbr: r.abbr ?? STATE_TO_ABBR[r.state] ?? r.state,
  }}))
  return (
    <{wrapped_name}
      stateSales={{{{rows}}}}
      makeFilter={{{{makeFilter ?? 'All'}}}}
      height={{{{height}}}}
      onStateClick={{{{onStateClick ? (abbr: string) => {{{{
        const name = ABBR_TO_STATE[abbr] ?? abbr
        onStateClick(name)
      }}}} : undefined}}}}
    />
  )
}}
export {{ UsaSalesMap }}
"""


def _ensure_required_components(files: dict) -> dict:
    """
    Guarantee FilterDropdown, Pagination, and PersonaCard always exist.
    Also creates UsaSalesMap.tsx if pages need it but only a variant was generated.
    """
    # Inject missing required components
    for name, source in _REQUIRED_COMPONENT_SOURCES.items():
        comp_path = f"src/components/{name}.tsx"
        if comp_path not in files:
            files[comp_path] = source
            print(f"[_ensure_required_components] injected {comp_path}", flush=True)

    # If pages import UsaSalesMap but the component doesn't exist, create a wrapper
    pages_want_usa = any(
        "UsaSalesMap" in content
        for path, content in files.items()
        if path.startswith("src/pages/")
    )
    usa_exists = "src/components/UsaSalesMap.tsx" in files
    if pages_want_usa and not usa_exists:
        _USA_VARIANTS = ("USStateMap", "USSalesMap", "UsStateMap", "UsStateSalesMap")
        actual = None
        for fp in files:
            fname = fp.split("/")[-1].replace(".tsx", "")
            if fname in _USA_VARIANTS or any(v in fname for v in _USA_VARIANTS):
                if "World" not in fname:
                    actual = fname
                    break
        if actual:
            files["src/components/UsaSalesMap.tsx"] = _build_usa_map_wrapper(actual)
            print(f"[_ensure_required_components] created UsaSalesMap.tsx wrapping {actual}", flush=True)

    return files


def _tsc_heal(project_dir: Path, files: dict, progress=None) -> dict:
    """
    Write files, run tsc --noEmit, feed errors back to LLM for targeted fixes.
    Loops up to 3 rounds. Returns the (possibly fixed) files dict.
    """
    import re as _re
    import subprocess as _sp
    from agents.component_contracts import build_component_api_section
    from agents.llm import chat

    contracts_section = build_component_api_section()

    TSC_SYSTEM = (
        "You are a TypeScript expert fixing compilation errors in a React/TypeScript app. "
        "Fix ONLY the reported errors. Do not rewrite unrelated code. "
        "Return ONLY the corrected file content — no markdown fences, no explanation."
    )

    for round_n in range(3):
        # Write current state to disk so tsc can read it
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
            fp.write_text(content, encoding="utf-8")

        # Run tsc — on Windows use .cmd wrapper
        import platform as _platform
        if _platform.system() == "Windows":
            tsc_bin = project_dir / "node_modules" / ".bin" / "tsc.cmd"
        else:
            tsc_bin = project_dir / "node_modules" / ".bin" / "tsc"
        if not tsc_bin.exists():
            print("[tsc_heal] tsc not found — skipping", flush=True)
            return files

        result = _sp.run(
            [str(tsc_bin), "--noEmit", "--pretty", "false"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=60,
            shell=(_platform.system() == "Windows"),
        )
        if result.returncode == 0:
            print(f"[tsc_heal] Clean after round {round_n}", flush=True)
            return files

        # Parse errors grouped by file
        errors_by_file: dict[str, list[str]] = {}
        for line in (result.stdout + result.stderr).splitlines():
            m = _re.match(r"^(src/[^(]+)\((\d+),\d+\):\s*error\s*(TS\d+):\s*(.+)$", line)
            if m:
                fpath, lineno, code, msg = m.groups()
                errors_by_file.setdefault(fpath, []).append(f"  Line {lineno} [{code}]: {msg}")

        if not errors_by_file:
            print(f"[tsc_heal] Round {round_n+1}: tsc failed but no parseable errors — stopping", flush=True)
            break

        total_errors = sum(len(v) for v in errors_by_file.values())
        print(f"[tsc_heal] Round {round_n+1}: {total_errors} errors in {len(errors_by_file)} files", flush=True)
        if progress:
            progress(f"tsc_heal:Fixing {total_errors} TypeScript errors (round {round_n+1}/3)…")

        # Fix each erroring file via LLM
        any_fixed = False
        for file_path, error_lines in errors_by_file.items():
            if file_path not in files:
                continue
            error_text = "\n".join(error_lines)
            prompt = (
                f"Fix these TypeScript compilation errors. Change ONLY what is needed.\n\n"
                f"{contracts_section}\n\n"
                f"File: {file_path}\n"
                f"Errors:\n{error_text}\n\n"
                f"Current file content:\n{files[file_path]}"
            )
            try:
                fixed = chat(
                    [{"role": "user", "content": prompt}],
                    system=TSC_SYSTEM,
                    max_tokens=8000,
                ).strip()
                # Strip markdown fences if the LLM added them
                if fixed.startswith("```"):
                    fixed = _re.sub(r"^```[^\n]*\n", "", fixed)
                    fixed = _re.sub(r"\n```$", "", fixed.rstrip())
                if fixed and fixed != files[file_path]:
                    files[file_path] = fixed
                    any_fixed = True
                    print(f"[tsc_heal] Fixed {file_path}", flush=True)
            except Exception as ex:
                print(f"[tsc_heal] LLM fix failed for {file_path}: {ex}", flush=True)

        if not any_fixed:
            print("[tsc_heal] No files changed — stopping early", flush=True)
            break

    return files


def _qa_heal(project_dir: Path, project_name: str, port: int,
             qa_report, files: dict, progress=None, max_rounds: int = 2):
    """
    Feed QA errors back to LLM for targeted fixes. Re-runs QA after each round.
    Returns (final_qa_report, fixed_files).
    """
    import re as _re

    QA_HEAL_SYSTEM = (
        "You are fixing runtime errors in a React/TypeScript page. "
        "The errors were detected by automated QA (browser console errors, missing imports, NaN values). "
        "Fix ONLY the specific errors listed. Do not rewrite unrelated code.\n\n"
        "OUTPUT FORMAT: Your response must be ONLY the complete .tsx file content starting with 'import'. "
        "Do NOT include any explanation, analysis, commentary, or prose. "
        "Do NOT start with 'Looking at', 'The issue is', 'Here is', 'I need to', or similar. "
        "The FIRST character of your response MUST be the letter 'i' in 'import'.\n\n"
        "CRITICAL RULES:\n"
        "- useApi syntax: useApi<any[]>('table_name') — pass ONLY the SQL table name\n"
        "- API returns SNAKE_CASE fields matching SQL: row.doc_type NOT row.docType\n"
        "- DO NOT import from '../components/...' unless it's ExportToolbar\n"
        "- D3 charts: useRef MUST be on a container <div> (NOT the <svg>). Container div MUST have minHeight.\n"
        "- D3 ResizeObserver: ALWAYS call measure()/render() immediately BEFORE ro.observe(). Never rely on RO alone.\n"
        "- NEVER use ref.current?.parentElement — ref the container div directly.\n"
        "- Null-guard all numeric values: Number(x) || 0\n"
    )

    for round_n in range(max_rounds):
        # Group errors by page file
        errors_by_page: dict[str, list[str]] = {}
        for finding in qa_report.findings:
            if finding.severity != "error":
                continue
            # Map route to page file
            route = finding.file  # e.g. "/timesheets" or "src/pages/Capacity.tsx"
            if route.startswith("/"):
                # Convert route like "/timesheets" to page file
                page_name = route.strip("/").replace("-", "").title()
                # Try to find matching page file
                for fpath in files:
                    if fpath.startswith("src/pages/") and fpath.endswith(".tsx"):
                        fname = fpath.replace("src/pages/", "").replace(".tsx", "")
                        if fname.lower() == page_name.lower() or fname.lower() == route.strip("/").lower():
                            page_name = fname
                            break
                page_file = f"src/pages/{page_name}.tsx"
            elif route.startswith("src/"):
                # Strip line number suffix from tsc output (e.g. "src/pages/Foo.tsx:42")
                page_file = route.split(":")[0]
            else:
                continue

            if page_file in files:
                errors_by_page.setdefault(page_file, []).append(
                    f"  [{finding.category}] {finding.message}"
                )

        if not errors_by_page:
            print(f"[qa_heal] No fixable page errors found — done", flush=True)
            break

        total_errors = sum(len(v) for v in errors_by_page.values())
        print(f"[qa_heal] Round {round_n+1}/{max_rounds}: {total_errors} errors in {len(errors_by_page)} pages", flush=True)
        if progress:
            progress(f"crew:QA auto-fix round {round_n+1} — fixing {total_errors} errors in {len(errors_by_page)} pages…")

        any_fixed = False
        for page_file, error_lines in errors_by_page.items():
            error_text = "\n".join(error_lines)
            current_code = files.get(page_file, "")
            if not current_code:
                continue

            # Read the schema for context
            schema = ""
            schema_path = project_dir / "api" / "schema.sql"
            if not schema_path.exists():
                schema_path = project_dir / "schema.sql"
            if schema_path.exists():
                try:
                    schema = schema_path.read_text(encoding="utf-8")[:3000]
                except Exception:
                    pass

            prompt = (
                f"Fix these runtime/build errors in {page_file}.\n\n"
                f"Errors found by QA:\n{error_text}\n\n"
                f"Database schema (use these exact table/column names):\n{schema}\n\n"
                f"Current file content:\n```tsx\n{current_code}\n```"
            )
            try:
                fixed = chat(
                    [{"role": "user", "content": prompt}],
                    system=QA_HEAL_SYSTEM,
                    max_tokens=16000,
                ).strip()
                # Strip markdown fences
                if fixed.startswith("```"):
                    fixed = _re.sub(r"^```[^\n]*\n", "", fixed)
                    fixed = _re.sub(r"\n```\s*$", "", fixed.rstrip())
                # Strip leading prose before actual code (LLM sometimes explains before writing code)
                if fixed and not fixed.startswith("import") and not fixed.startswith("//") and not fixed.startswith("'use"):
                    import_match = _re.search(r'^(import |// |/\*)', fixed, _re.MULTILINE)
                    if import_match and import_match.start() > 0:
                        leading = fixed[:import_match.start()]
                        if not any(kw in leading for kw in ['from ', 'export ', 'const ', 'function ', 'interface ']):
                            fixed = fixed[import_match.start():]
                            print(f"[qa_heal] Stripped {import_match.start()} chars of leading prose from {page_file}", flush=True)
                if fixed and fixed != files[page_file] and len(fixed) > 50:
                    files[page_file] = fixed
                    any_fixed = True
                    print(f"[qa_heal] Fixed {page_file}", flush=True)
            except Exception as ex:
                print(f"[qa_heal] LLM fix failed for {page_file}: {ex}", flush=True)

        if not any_fixed:
            print("[qa_heal] No files changed — stopping early", flush=True)
            break

        # Write fixed files (Vite HMR will pick them up)
        for rel_path, content in files.items():
            if not content or not content.strip():
                continue
            fp = project_dir / rel_path
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content, encoding="utf-8")

        # Give Vite a moment to recompile via HMR
        import time
        time.sleep(3)

        # Re-run QA
        if progress:
            progress(f"crew:Re-running QA after fix round {round_n+1}…")
        qa_report = run_qa(project_name, port, project_dir)

        if qa_report.passed:
            print(f"[qa_heal] QA passed after round {round_n+1}!", flush=True)
            if progress:
                progress(f"crew:QA passed after auto-fix! Score: {qa_report.score}/100")
            break
        else:
            remaining = sum(1 for f in qa_report.findings if f.severity == "error")
            print(f"[qa_heal] Still {remaining} errors after round {round_n+1}", flush=True)

    return qa_report, files


# ── Public API ─────────────────────────────────────────────────────────────────

def kill_server(project_name: str, forget_port: bool = False):
    """Stop both Vite and API server processes and wait for them to fully exit."""
    _stop_api_server(project_name)
    proc = _dev_servers.pop(project_name, None)
    if proc:
        try:
            proc.terminate()
            proc.wait(timeout=8)
        except Exception:
            try:
                proc.kill()
                proc.wait(timeout=5)
            except Exception:
                pass
    # Also kill any node processes still holding the port (Windows orphan processes).
    # Use "LISTENING" filter so we only kill the process bound to the port,
    # not uvicorn's ESTABLISHED proxy connections to Vite (which would kill the API server).
    port = _dev_ports.get(project_name)
    if port:
        try:
            import subprocess
            subprocess.run(
                f'for /f "tokens=5" %a in (\'netstat -ano ^| findstr "LISTENING" ^| findstr ":{port} "\') do taskkill /PID %a /F',
                shell=True, capture_output=True, timeout=5,
            )
        except Exception:
            pass
    if forget_port:
        _dev_ports.pop(project_name, None)
        _save_ports()


def _augment_prompt(prompt: str) -> str:
    """Append mandatory system constraints to every generation prompt."""
    notes = [
        "TECH STACK (MANDATORY — override any spec/TRD): "
        "This platform generates React 18 + TypeScript + Tailwind CSS + Vite frontend apps "
        "with a SQLite database + Python FastAPI backend. "
        "If the instructions/specs mention other technologies (PostgreSQL, Redis, Express, "
        "Node.js backend, MongoDB, AWS services, Docker, Kubernetes, etc.), IGNORE those "
        "technology choices and use the TurboUIGen stack instead. "
        "Extract the BUSINESS LOGIC, DATA MODELS, UI REQUIREMENTS, and USER FLOWS from "
        "the specs — but implement them using our stack. "
        "Do NOT generate backend code, Docker files, CI/CD pipelines, or infrastructure.",
        "DATA ARCHITECTURE (MANDATORY): ALL app data MUST live in a SQLite database. "
        "A schema.sql, seed.sql, and API server are ALWAYS created. "
        "The frontend NEVER contains hardcoded data — it fetches everything via REST API "
        "(useApi hook → GET /api/data/{tableName}). This applies to EVERY app regardless "
        "of what the user prompt says.",
        "CHART REMINDER: Use D3.js (useEffect + useRef + SVG) for any charts built from scratch. "
        "Do NOT use Highcharts — it breaks in Vite ESM mode. "
        "D3 pattern: useRef on container DIV (not SVG), container has minHeight, "
        "call render() immediately then pass render to ResizeObserver. Never use parentElement.",
        "MAP DATA — static imports only (dynamic import/fetch = blank maps): "
        "CORRECT: import usaTopo from 'us-atlas/states-10m.json' "
        "FORBIDDEN: fetch() or d3.json() for TopoJSON.",
    ]
    return prompt + "\n\n[SYSTEM NOTES — follow these exactly]\n" + "\n".join(notes)


def generate_project(prompt: str, progress=None, project_name_override: str | None = None,
                     architecture: dict | None = None,
                     reference_images: list[dict] | None = None) -> dict:
    """
    Generate a React/TS/Tailwind project from a prompt.
    progress(step: str) is called at each stage for CLI/UI feedback.
    architecture: pre-approved architecture from /api/draft (skips Stage 1 if provided).
    reference_images: list of Figma screenshots [{name, base64_data}] for visual fidelity.
    Returns project info dict.
    """
    if not os.environ.get("LITELLM_API_BASE") and not os.environ.get("LITELLM_API_KEY"):
        raise RuntimeError("LiteLLM credentials not configured in .env (LITELLM_API_BASE, LITELLM_API_KEY)")

    def _p(s):
        if progress:
            progress(s)

    _p("llm")

    # ── Detect refinement: if project already exists, read existing state ──────
    existing_schema = ""
    existing_seed = ""
    existing_files: dict[str, str] = {}
    _existing_dir = None
    if project_name_override:
        _existing_dir = GENERATED_DIR / re.sub(r"[^a-z0-9-]", "-", project_name_override.lower()).strip("-")
        if _existing_dir.exists():
            # Read schema context
            _schema_f = _existing_dir / "api" / "schema.sql"
            _seed_f = _existing_dir / "api" / "seed.sql"
            if not _schema_f.exists():
                _schema_f = _existing_dir / "schema.sql"
                _seed_f = _existing_dir / "seed.sql"
            if _schema_f.exists():
                existing_schema = _schema_f.read_text(encoding="utf-8")
            if _seed_f.exists():
                existing_seed = _seed_f.read_text(encoding="utf-8")

            # Read all existing source files for selective regeneration
            for fp in _existing_dir.rglob("*"):
                if fp.is_file() and fp.suffix in (".tsx", ".ts", ".css", ".sql", ".py", ".html", ".json", ".js", ".txt"):
                    rel = fp.relative_to(_existing_dir).as_posix()
                    if rel.startswith("node_modules/") or rel.startswith("."):
                        continue
                    try:
                        existing_files[rel] = fp.read_text(encoding="utf-8")
                    except Exception:
                        pass
            if existing_files:
                _p(f"crew:Detected existing project ({len(existing_files)} files) — selective regeneration mode")

    from agents.orchestrator import CrewOrchestrator
    _p("crew:Initializing multi-agent pipeline…")
    orchestrator = CrewOrchestrator(progress=_p)
    if existing_schema:
        orchestrator.existing_context = {
            "schema": existing_schema,
            "seed_preview": existing_seed[:5000],
        }
    if existing_files:
        orchestrator.existing_files = existing_files
    if architecture:
        orchestrator.approved_architecture = architecture
    if reference_images:
        orchestrator.reference_images = reference_images
    data = orchestrator.generate(_augment_prompt(prompt))

    if project_name_override:
        project_name = re.sub(r"[^a-z0-9-]", "-", project_name_override.lower()).strip("-") or "app"
    else:
        project_name = re.sub(r"[^a-z0-9-]", "-", data.get("projectName", "app").lower()).strip("-") or "app"
    files = data.get("files", {})
    if not files:
        raise RuntimeError("LLM returned no files")

    # Assign or reuse port — also persist to registry so it survives restarts
    port = _dev_ports.get(project_name) or _next_port()
    _dev_ports[project_name] = port
    _save_ports()
    registry_upsert(project_name, port=port, type="react")

    project_dir = GENERATED_DIR / project_name

    # ── Ensure essential boilerplate (safety net for partial/refinement builds) ──
    files = _ensure_boilerplate(files, project_name)
    # ── ALL apps use SQLite + API — ensure schema.sql always exists ─────────
    files = _ensure_schema_sql(files, force=True)
    # ── Bundle API server + useApi hook (always — every app has an API) ────
    files = _bundle_api_server(files)

    # Assign API port if this project has an API server
    has_api_files = (
        "api/app_server.py" in files or "app_server.py" in files
        or "api_server.py" in files
        or "api/schema.sql" in files or "schema.sql" in files
    )
    api_port = _api_ports.get(project_name)
    if has_api_files and not api_port:
        api_port = _next_api_port()
        _api_ports[project_name] = api_port
        _save_ports()

    # Patch .env with the correct dynamic API port
    if api_port and "api/.env" in files:
        import re as _re_env
        files["api/.env"] = _re_env.sub(r"API_PORT=\d+", f"API_PORT={api_port}", files["api/.env"])

    # Wire the design system alias and run all post-processors
    # Pass project_name + port + api_port so _inject_api_proxy builds the full server block
    # (port, host, proxy with base-path rewrite) — no separate port injection needed.
    files = run_all_postprocessors(files, project_dir=project_dir, project_name=project_name, port=port, api_port=api_port or 0)
    files = _ensure_required_components(files)

    # Ensure port is set even for non-API projects (where _inject_api_proxy is a no-op)
    vite = files.get("vite.config.ts", "")
    if vite and f"port: {port}" not in vite:
        vite = vite.replace(
            "defineConfig({\n",
            f"defineConfig({{\n  server: {{ port: {port}, host: '0.0.0.0' }},\n",
        )
        if f"port: {port}" not in vite:
            vite = vite.replace(
                "defineConfig({",
                f"defineConfig({{ server: {{ port: {port}, host: '0.0.0.0' }},",
            )
        files["vite.config.ts"] = vite

    _p("write")
    kill_server(project_name)
    _write_files(project_dir, files)

    _p("install")
    # Ensure shared node_modules exist, then junction the project to them
    ok, log = _ensure_shared_nm_once()
    if not ok:
        raise RuntimeError(f"Shared npm install failed:\n{log[-2000:]}")
    project_deps = _get_project_deps(project_dir)
    # Scan actual source imports — catches packages the LLM uses but didn't add to package.json
    scanned_imports = _scan_imports_from_files(project_dir)
    for pkg in scanned_imports:
        if pkg not in project_deps:
            project_deps[pkg] = "latest"
    ok2, log2 = _link_shared_nm(project_dir, project_deps, progress=_p)
    if not ok2:
        # Fall back to per-project install if junction fails
        ok3, log3 = _npm_install(project_dir)
        if not ok3:
            raise RuntimeError(f"npm install failed:\n{log3[-2000:]}")
    _link_ds_into_project(project_dir)

    # Verify all imported modules exist in node_modules — install any missing ones NOW
    nm_dir = project_dir / "node_modules"
    if nm_dir.exists():
        _final_imports = _scan_imports_from_files(project_dir)
        _missing_final = []
        for pkg in _final_imports:
            parts = pkg.split("/")
            pkg_path = nm_dir.joinpath(*parts) if pkg.startswith("@") else nm_dir / pkg
            if not pkg_path.exists():
                _missing_final.append(pkg)
        if _missing_final:
            _p(f"install:Installing missing modules: {', '.join(_missing_final)}")
            print(f"[generate] Missing modules detected after link: {_missing_final}", flush=True)
            env = os.environ.copy()
            env["PATH"] = NODE_PATH + os.pathsep + env.get("PATH", "")
            node_exe = Path(NODE_PATH) / "node.exe"
            npm_js = Path(NODE_PATH) / "node_modules" / "npm" / "bin" / "npm-cli.js"
            subprocess.run(
                [str(node_exe), str(npm_js), "install"] + _missing_final,
                cwd=str(SHARED_NM_DIR), env=env, capture_output=True, text=True, timeout=120,
            )
            print(f"[generate] Installed missing modules: {_missing_final}", flush=True)

    # Run tsc self-heal AFTER node_modules is present so tsc resolves types
    files = _tsc_heal(project_dir, files, progress=_p)
    # Re-write any files that were healed
    _write_files(project_dir, files)

    _p("start")
    # Start API server first (if app_server.py exists), then Vite
    has_api = (
        (project_dir / "api" / "app_server.py").exists()
        or (project_dir / "app_server.py").exists()
        or (project_dir / "api" / "schema.sql").exists()
    )
    api_port = _api_ports.get(project_name)
    if has_api:
        if not api_port:
            api_port = _next_api_port()
            _api_ports[project_name] = api_port
            _save_ports()
        api_proc = _start_api_server(project_dir, api_port=api_port)
    else:
        api_proc = None
    if api_proc:
        _api_servers[project_name] = api_proc
        _wait_for_api(api_port, timeout=15)
    proc = _start_vite(project_dir, port)
    _dev_servers[project_name] = proc

    if not wait_for_port(port, timeout=60):
        raise RuntimeError("Vite dev server did not start in time")

    # Wait for Vite dependency pre-bundling to complete before QA.
    # Vite writes _metadata.json once all deps are optimized — without this,
    # lazy-loaded pages fail with "Failed to fetch dynamically imported module".
    _deps_dir = project_dir / "node_modules" / ".vite" / "deps"
    _prebundle_deadline = time.time() + 30
    while time.time() < _prebundle_deadline:
        if (_deps_dir / "_metadata.json").exists():
            print("[generate] Vite dep pre-bundling complete", flush=True)
            break
        time.sleep(1)
    else:
        print("[generate] WARNING: Vite _metadata.json not found after 30s — proceeding anyway", flush=True)

    _p("qa")
    qa_report = run_qa(project_name, port, project_dir)

    # ── QA-Heal loop: if QA found fixable errors, feed them to LLM and retry ──
    if not qa_report.passed and qa_report.pages_fail:
        _p("crew:QA found errors — attempting auto-fix…")
        qa_report, files = _qa_heal(
            project_dir, project_name, port, qa_report, files, progress=_p
        )

    _p("ready")
    return {
        "projectName": project_name,
        "title":       data.get("title", project_name),
        "description": data.get("description", ""),
        "port":        port,
        "url":         "/app/" + project_name + "/",
        "files":       list(files.keys()),
        "qa":          qa_report.to_dict(),
    }


def start_project(project_name: str) -> dict:
    project_dir = GENERATED_DIR / project_name
    if not project_dir.exists():
        raise RuntimeError(f"Project '{project_name}' not found")
    if project_name in _dev_servers:
        port = _dev_ports[project_name]
        return {"projectName": project_name, "port": port, "url": "/app/" + project_name + "/"}
    port = _dev_ports.get(project_name)
    if not port:
        port = _next_port()
        _dev_ports[project_name] = port
        _save_ports()
    # Rewrite vite config with clean DS alias + proxy server/base/port block
    vite_cfg = project_dir / "vite.config.ts"
    base = "/app/" + project_name + "/"
    patched = _patch_vite_for_ds({})["vite.config.ts"]
    # Inject base + server block before the closing })
    # Add /api proxy if project has a Python API server (or schema.sql that will trigger auto-bundle)
    proxy_section = ""
    has_api = (
        (project_dir / "api" / "app_server.py").exists()
        or (project_dir / "app_server.py").exists()
        or (project_dir / "api_server.py").exists()
        or (project_dir / "api" / "schema.sql").exists()
        or (project_dir / "schema.sql").exists()
    )
    # Assign or reuse API port for this project
    api_port = _api_ports.get(project_name)
    if has_api and not api_port:
        api_port = _next_api_port()
        _api_ports[project_name] = api_port
        _save_ports()

    if has_api and api_port:
        proxy_section = (
            "    proxy: {\n"
            f"      '/api': {{ target: 'http://localhost:{api_port}', changeOrigin: true }},\n"
            f"      '/app/{project_name}/api': {{ target: 'http://localhost:{api_port}', changeOrigin: true, rewrite: (path) => path.replace(/^\\/app\\/{project_name}/, '') }},\n"
            "    },\n"
        )

    server_block = (
        "  base: '" + base + "',\n"
        "  server: {\n"
        "    port: " + str(port) + ",\n"
        "    host: '0.0.0.0',\n"
        "    hmr: false,\n"
        "    allowedHosts: ['localhost'],\n"
        + proxy_section +
        "    fs: { allow: ['..', '" + _DS_CLEAN_JUNCTION + "', '" + _SHARED_NM_JUNCTION + "'] },\n"
        "  },\n"
    )
    patched = patched.replace("})\n", server_block + "})\n", 1)
    vite_cfg.write_text(patched, encoding="utf-8")
    # Ensure shared node_modules exist (installs any missing packages like xlsx, jspdf)
    _ensure_shared_nm_once()
    # Ensure node_modules are linked (junction to shared, or fall back to real install)
    nm = project_dir / "node_modules"
    if not nm.exists():
        ok_s = True
        deps = _get_project_deps(project_dir)
        for pkg in _scan_imports_from_files(project_dir):
            if pkg not in deps:
                deps[pkg] = "latest"
        _link_shared_nm(project_dir, deps)
    _link_ds_into_project(project_dir)
    # Start API server if app_server.py exists
    if has_api:
        if not api_port:
            api_port = _next_api_port()
            _api_ports[project_name] = api_port
            _save_ports()
        # Patch .env on disk so it matches the assigned port
        env_file = project_dir / "api" / ".env"
        if env_file.exists():
            import re as _re_env
            env_text = env_file.read_text(encoding="utf-8")
            patched_env = _re_env.sub(r"API_PORT=\d+", f"API_PORT={api_port}", env_text)
            if patched_env != env_text:
                env_file.write_text(patched_env, encoding="utf-8")
        api_proc = _start_api_server(project_dir, api_port=api_port)
        if api_proc:
            _api_servers[project_name] = api_proc
            _wait_for_api(api_port, timeout=15)
    proc = _start_vite(project_dir, port)
    _dev_servers[project_name] = proc
    wait_for_port(port, timeout=60)
    reg = _load_registry().get(project_name, {})
    return {"projectName": project_name, "port": port, "apiPort": api_port, "url": "/app/" + project_name + "/",
            "title": reg.get("title", project_name), "architecture": reg.get("architecture", {})}


def stop_project(project_name: str):
    kill_server(project_name, forget_port=False)


def delete_project(project_name: str):
    kill_server(project_name, forget_port=True)
    # Wait for file handles to release (Vite watchers, OneDrive sync)
    time.sleep(2)
    project_dir = GENERATED_DIR / project_name
    if not project_dir.exists():
        return
    import subprocess as _sp

    # Remove .vite cache (Vite holds locks on these)
    vite_cache = project_dir / ".vite"
    if vite_cache.exists():
        shutil.rmtree(vite_cache, ignore_errors=True)

    # Remove node_modules — if it's a junction to shared-node-modules, just unlink it
    node_modules = project_dir / "node_modules"
    if node_modules.exists():
        try:
            result = _sp.run(
                ["cmd", "/c", "fsutil", "reparsepoint", "query", str(node_modules)],
                capture_output=True, timeout=5,
            )
            if result.returncode == 0:
                _sp.run(["cmd", "/c", "rmdir", str(node_modules)], capture_output=True, timeout=10)
            else:
                _sp.run(
                    ["cmd", "/c", "rd", "/s", "/q", str(node_modules)],
                    capture_output=True, timeout=30,
                )
        except Exception:
            shutil.rmtree(node_modules, ignore_errors=True)
        time.sleep(0.5)

    # Retry deletion up to 3 times — OneDrive and Windows can hold file locks briefly
    for attempt in range(3):
        shutil.rmtree(project_dir, ignore_errors=True)
        if not project_dir.exists():
            break
        # Fallback: force with rd /s /q
        try:
            _sp.run(
                ["cmd", "/c", "rd", "/s", "/q", str(project_dir)],
                capture_output=True, timeout=30,
            )
        except Exception:
            pass
        if not project_dir.exists():
            break
        # Wait progressively longer for locks to release
        time.sleep(2 * (attempt + 1))

    if project_dir.exists():
        print(f"[delete_project] WARNING: could not fully delete {project_dir} — files may be locked by OneDrive or another process", flush=True)


def _migrate_existing_projects():
    """One-time migration: scan disk and populate registry for pre-existing projects."""
    if _REGISTRY_FILE.exists():
        return  # already migrated
    reg = {}
    if not GENERATED_DIR.exists():
        return
    for d in sorted(GENERATED_DIR.iterdir()):
        if not d.is_dir() or not (d / "package.json").exists():
            continue
        try:
            pkg = json.loads((d / "package.json").read_text())
        except Exception:
            pkg = {}
        try:
            meta = json.loads((d / ".meta.json").read_text()) if (d / ".meta.json").exists() else {}
        except Exception:
            meta = {}
        reg[d.name] = {
            "name":        d.name,
            "title":       pkg.get("description", d.name),
            "hasApp":      (d / "src").exists(),
            "type":        "react",
            "source":      meta.get("source", "prompt"),
            "sourceLabel": meta.get("label", "Instructions"),
            "figmaUrl":    meta.get("figma_url", ""),
            "prompt":      meta.get("prompt", ""),
        }
    _save_registry(reg)


_migrate_existing_projects()


def _health_check(port: int, proj_type: str = "react", name: str = "") -> bool:
    """
    Check if a project server is alive and serving content.
    - HTML projects (figma): GET http://localhost:{port}/_health → {"status":"ok"}
    - React/Vite projects:   GET http://localhost:{port}/         → any 200/304 response
    Both checks timeout in 200ms.
    """
    if not port:
        return False
    import urllib.request
    import urllib.error
    try:
        if proj_type == "html":
            url = _health_url(port, "html")
        else:
            # Vite dev server — just check the root responds
            url = _health_url(port, "react")
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=0.2) as resp:
            return resp.status < 500
    except Exception:
        return False


def _check_health_parallel(checks: list[tuple[int, str, str]]) -> dict[int, bool]:
    """
    Run health checks for all projects concurrently.
    checks = list of (port, proj_type, name)
    Returns {port: is_healthy}
    """
    if not checks:
        return {}
    from concurrent.futures import ThreadPoolExecutor, as_completed
    results: dict[int, bool] = {}
    unique = {p: (pt, n) for p, pt, n in checks if p}
    with ThreadPoolExecutor(max_workers=min(len(unique), 20)) as ex:
        future_map = {
            ex.submit(_health_check, p, pt, n): p
            for p, (pt, n) in unique.items()
        }
        for fut in as_completed(future_map):
            p = future_map[fut]
            try:
                results[p] = fut.result()
            except Exception:
                results[p] = False
    return results


def list_projects() -> list[dict]:
    """
    Fast project list from registry JSON.
    Port checks run in parallel so 20 projects take the same time as 1.
    """
    from agents.figma_to_web_using_playwright_agent import _html_servers, _html_ports
    reg = _load_registry()
    if not reg:
        return []

    # Re-sync in-memory ports from disk (may have changed via another process)
    _vite_disk, _api_disk = _load_ports()
    _dev_ports.update(_vite_disk)
    _api_ports.update(_api_disk)

    # Collect all ports first
    port_map: dict[str, int | None] = {}
    type_map: dict[str, str] = {}
    for name, entry in reg.items():
        proj_type = entry.get("type", "react")
        type_map[name] = proj_type
        if proj_type == "html":
            port_map[name] = _html_ports.get(name) or entry.get("port")
        else:
            port_map[name] = _dev_ports.get(name) or entry.get("port")

    # Parallel health checks — skip projects whose process we own (already know they're running)
    checks_needed = [
        (port_map[name], type_map[name], name)
        for name in reg
        if port_map.get(name)
        and name not in _dev_servers
        and name not in _html_servers
    ]
    health = _check_health_parallel(checks_needed)

    projects = []
    for name, entry in sorted(reg.items()):
        proj_type = entry.get("type", "react")
        port = port_map.get(name)

        # Process-based check is instant; port check uses parallel results
        if proj_type == "html":
            running = (name in _html_servers) or bool(health.get(port))
            url = ("/figma-app/" + name + "/") if (running and port) else None
        else:
            running = (name in _dev_servers) or bool(health.get(port))
            url = ("/app/" + name + "/") if (running and port) else None

        projects.append({
            "name":        name,
            "title":       entry.get("title", name),
            "port":        port,
            "apiPort":     _api_ports.get(name),
            "url":         url,
            "running":     running,
            "hasApp":      entry.get("hasApp", False),
            "type":        proj_type,
            "source":      entry.get("source", "prompt"),
            "sourceLabel": entry.get("sourceLabel", "Instructions"),
            "figmaUrl":    entry.get("figmaUrl", ""),
            "prompt":      entry.get("prompt", ""),
        })
    return projects
