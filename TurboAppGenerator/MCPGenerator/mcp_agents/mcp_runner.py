"""
Starts/stops live dev servers for standalone generated MCP servers.

Owns its own port pool and process table, entirely separate from WebUIGenerator's
and WebAPIGenerator's pools. Reuses WebUIGenerator's free-port check instead of
duplicating it, since WebUIGenerator stays on sys.path and owns the `agents`
package name — same reuse trick as WebAPIGenerator/api_agents/api_runner.py.

Always Python — every generated MCP server uses FastMCP (see mcp_orchestrator.py),
so unlike api_runner.py there's no Java branch here at all.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from agents.uigen_agent import _port_is_free

from mcp_config import PORTS_FILE, PORT_START

_procs: dict[str, subprocess.Popen] = {}
_ports: dict[str, int] = {}


def _load_ports() -> dict:
    if PORTS_FILE.exists():
        try:
            return json.loads(PORTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_ports():
    PORTS_FILE.write_text(json.dumps(_ports, indent=2), encoding="utf-8")


_ports.update(_load_ports())


def _next_port() -> int:
    assigned = set(_ports.values())
    port = PORT_START
    while port in assigned or not _port_is_free(port):
        port += 1
    return port


def _kill_port(port: int):
    """Best-effort: kill whatever is still bound to `port` on Windows."""
    if os.name != "nt" or not port:
        return
    try:
        out = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=10
        ).stdout
        for line in out.splitlines():
            if f":{port} " in line and "LISTENING" in line:
                pid = line.split()[-1]
                subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, timeout=10)
    except Exception:
        pass


def start_mcp_project(name: str, project_dir: Path) -> int:
    """
    Start the generated MCP server's dev server (installing deps on first run) and
    return the assigned port. Idempotent — restarts cleanly if already running.
    The generated src/main.py exposes a plain ASGI `app` (FastMCP's Streamable HTTP
    app plus a /health route mounted alongside it), spawned exactly like
    WebAPIGenerator's Python projects: `uvicorn src.main:app --port <port>`.
    """
    stop_mcp_project(name)

    port = _ports.get(name)
    if not port or not _port_is_free(port):
        port = _next_port()
    _ports[name] = port
    _save_ports()

    log_path = project_dir / "mcp_server.log"
    log_file = open(str(log_path), "w", encoding="utf-8", errors="replace")

    # Install deps once per project (marker file avoids re-running pip install on
    # every restart) — same convention as api_runner.py's Python branch.
    marker = project_dir / ".deps_installed"
    if not marker.exists():
        req = project_dir / "requirements.txt"
        if req.exists():
            install = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "-r", str(req)],
                cwd=str(project_dir), timeout=300, capture_output=True, text=True,
            )
            if install.returncode == 0:
                marker.write_text("ok", encoding="utf-8")
            else:
                log_file.write(f"pip install failed (exit {install.returncode}):\n{install.stderr}\n")
                log_file.flush()
        else:
            marker.write_text("ok", encoding="utf-8")

    env = os.environ.copy()
    env["PORT"] = str(port)
    cmd = [sys.executable, "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", str(port)]
    kwargs: dict = {"cwd": str(project_dir), "env": env, "stdout": log_file, "stderr": log_file}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    proc = subprocess.Popen(cmd, **kwargs)

    _procs[name] = proc
    print(f"[mcp-runner] Started {name} on port {port} (PID {proc.pid})", flush=True)
    return port


def stop_mcp_project(name: str):
    proc = _procs.pop(name, None)
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
    _kill_port(_ports.get(name))


def release_port(name: str):
    """Drop a deleted project's port assignment — see api_runner.py's
    release_port for why this is needed (otherwise .ports.json accumulates
    entries for projects that no longer exist on disk)."""
    if _ports.pop(name, None) is not None:
        _save_ports()


def rename_port(old_name: str, new_name: str):
    """Carry a project's assigned port over to its new name."""
    port = _ports.pop(old_name, None)
    if port is not None:
        _ports[new_name] = port
        _save_ports()


def get_port(name: str) -> int | None:
    return _ports.get(name)


def is_running(name: str) -> bool:
    port = _ports.get(name)
    return bool(port and not _port_is_free(port))


def wait_for_mcp(name: str, port: int, timeout: int = 30) -> bool:
    """Poll /health until it responds, OR bail out as soon as the process itself
    has already exited — same reasoning as api_runner.py's wait_for_api."""
    import urllib.request as _ur
    import urllib.error as _ue

    deadline = time.time() + timeout
    while time.time() < deadline:
        proc = _procs.get(name)
        if proc is not None and proc.poll() is not None:
            return False
        try:
            _ur.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
            return True
        except _ue.HTTPError:
            return True
        except Exception:
            time.sleep(0.5)
    return False
