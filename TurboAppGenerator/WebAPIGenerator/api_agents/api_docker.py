"""
Docker image builder and container manager for generated standalone APIs.

Much simpler than WebUIGenerator's agents/docker_agent.py: there's no React
frontend to vite-build and no nginx SPA/proxy layer to stitch together — a
generated API's own Dockerfile (see api_orchestrator._generate_packaging) is
already a complete, single-service image. Docker is opt-in here: generation
itself no longer produces a Dockerfile by default (the runner starts APIs
directly, uvicorn / mvn spring-boot:run, same as a web app's dev server), so
build_image() generates one on demand the first time it's needed.
"""

import json
import re
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from api_config import WEB_API_DIR

# Separate port range from WebUIGenerator's docker containers (7000+) and this
# project's own live dev-server pool (8400+, see api_config.PORT_START).
_CONTAINER_PORT_START = 7100
_CONTAINER_PORTS_FILE = WEB_API_DIR.parent / ".container_ports.json"

_docker_avail_cache: tuple[float, bool] | None = None


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _load_container_ports() -> dict:
    if _CONTAINER_PORTS_FILE.exists():
        try:
            return json.loads(_CONTAINER_PORTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_container_ports(ports: dict):
    _CONTAINER_PORTS_FILE.write_text(json.dumps(ports, indent=2, ensure_ascii=False), encoding="utf-8")


def _docker_used_ports() -> set:
    ok, out = _docker(["ps", "--format", "{{.Ports}}"], timeout=10)
    if not ok:
        return set()
    return set(int(m) for m in re.findall(r"0\.0\.0\.0:(\d+)->", out))


def _assign_container_port(project_name: str) -> int:
    ports = _load_container_ports()
    docker_ports = _docker_used_ports()
    if project_name in ports:
        p = ports[project_name]
        if _port_is_free(p) and p not in docker_ports:
            return p
    used = set(ports.values()) | docker_ports
    port = _CONTAINER_PORT_START
    while not _port_is_free(port) or port in used:
        port += 1
    ports[project_name] = port
    _save_container_ports(ports)
    return port


# ── Naming ─────────────────────────────────────────────────────────────────────

def release_container_port(project_name: str):
    """Drop a deleted project's container port assignment — same leak, same
    fix as api_runner.release_port for the live dev-server port pool."""
    ports = _load_container_ports()
    if ports.pop(project_name, None) is not None:
        _save_container_ports(ports)


def rename_docker(old_name: str, new_name: str):
    """
    Best-effort carry-over of any existing image/container to the new name.
    Most projects never had one built, and Docker itself may not even be
    running — either way this must never block a rename.
    """
    ports = _load_container_ports()
    if old_name in ports:
        ports[new_name] = ports.pop(old_name)
        _save_container_ports(ports)

    if not is_docker_available():
        return

    old_tag, new_tag = image_tag(old_name), image_tag(new_name)
    ok, _ = _docker(["image", "inspect", old_tag, "--format", "{{.Id}}"], timeout=8)
    if ok:
        _docker(["tag", old_tag, new_tag], timeout=15)
        _docker(["rmi", "-f", old_tag], timeout=15)

    old_cname, new_cname = container_name(old_name), container_name(new_name)
    ok, _ = _docker(["inspect", old_cname, "--format", "{{.Id}}"], timeout=8)
    if ok:
        _docker(["rename", old_cname, new_cname], timeout=15)


def image_tag(project_name: str) -> str:
    return f"turboapi-{project_name}:latest"


def container_name(project_name: str) -> str:
    return f"turboapi-{project_name}"


def _status_file(project_name: str) -> Path:
    return WEB_API_DIR / project_name / ".docker.json"


def _read_status(project_name: str) -> dict:
    f = _status_file(project_name)
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _write_status(project_name: str, data: dict):
    f = _status_file(project_name)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Docker CLI wrapper ─────────────────────────────────────────────────────────

def _docker(args: list, timeout: int = 60, cwd: str | None = None) -> tuple[bool, str]:
    try:
        r = subprocess.run(["docker"] + args, capture_output=True, timeout=timeout, cwd=cwd)
        stdout = r.stdout.decode("utf-8", errors="replace") if r.stdout else ""
        stderr = r.stderr.decode("utf-8", errors="replace") if r.stderr else ""
        return r.returncode == 0, (stdout + stderr).strip()
    except FileNotFoundError:
        return False, "Docker not found. Is Docker Desktop installed and running?"
    except subprocess.TimeoutExpired:
        return False, f"Docker command timed out after {timeout}s"
    except Exception as e:
        return False, str(e)


def is_docker_available() -> bool:
    global _docker_avail_cache
    now = time.time()
    if _docker_avail_cache and (now - _docker_avail_cache[0]) < 10:
        return _docker_avail_cache[1]
    ok, _ = _docker(["info", "--format", "{{.ServerVersion}}"], timeout=15)
    _docker_avail_cache = (now, ok)
    return ok


def get_status(project_name: str) -> dict:
    tag = image_tag(project_name)
    cname = container_name(project_name)
    stored = _read_status(project_name)
    host_port = _load_container_ports().get(project_name)

    if not is_docker_available():
        return {
            "dockerAvailable": False, "imageExists": False, "imageTag": None,
            "containerStatus": "none", "containerName": None, "hostPort": host_port,
            "builtAt": stored.get("builtAt"), "containerUrl": None,
        }

    ok_img, img_out = _docker(["image", "inspect", tag, "--format", "{{.Id}}"], timeout=8)
    image_exists = ok_img and bool(img_out.strip())

    ok_con, con_out = _docker(["inspect", cname, "--format", "{{.State.Status}}"], timeout=8)
    container_status = con_out.strip() if ok_con else "none"

    return {
        "dockerAvailable": True,
        "imageExists": image_exists,
        "imageTag": tag if image_exists else None,
        "containerStatus": container_status,
        "containerName": cname if container_status != "none" else None,
        "hostPort": host_port,
        "builtAt": stored.get("builtAt"),
        "containerUrl": f"http://localhost:{host_port}" if container_status == "running" and host_port else None,
    }


# ── Build ──────────────────────────────────────────────────────────────────────

def build_image(project_name: str, project_dir: Path, language: str, architecture: dict,
                 database: str = "sqlite", progress=None) -> tuple[bool, str]:
    def _p(msg: str):
        if progress:
            progress(f"docker_build:{msg}")

    _p("Checking Docker availability…")
    if not is_docker_available():
        return False, (
            "Docker Desktop is not running or not fully ready. "
            "Please start Docker Desktop, wait for it to be ready "
            "(whale icon in the system tray), and try again."
        )

    # Dockerfile isn't generated by default anymore (see api_orchestrator's
    # include_docker flag) — write it now, on demand, the first time an image
    # is actually requested. Reuses the exact same deterministic templates
    # generation would have used, so this stays in sync automatically.
    dockerfile = project_dir / "Dockerfile"
    if not dockerfile.exists():
        _p("Generating Dockerfile (first build for this project)…")
        from api_agents.api_orchestrator import ApiCrewOrchestrator
        orchestrator = ApiCrewOrchestrator()
        packaging_files = orchestrator._generate_packaging(architecture or {}, language, database)
        for fname, content in packaging_files.items():
            out = project_dir / fname
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(content, encoding="utf-8", newline="\n")

    tag = image_tag(project_name)
    build_timeout = 600 if language == "java" else 300
    if language == "java":
        _p(f"Building Docker image {tag} (Maven build — first run downloads dependencies, may take 3-5 min)…")
    else:
        _p(f"Building Docker image {tag}…")
    ok, out = _docker(["build", "-t", tag, "."], timeout=build_timeout, cwd=str(project_dir))
    if not ok:
        return False, f"docker build failed:\n{out[-1500:]}"

    _write_status(project_name, {"builtAt": datetime.now(timezone.utc).isoformat(), "imageTag": tag})
    _p(f"Image {tag} ready")
    return True, out


def save_image(project_name: str) -> tuple[bool, Path, str]:
    """docker save → .tar file. Returns (ok, tar_path, error_msg)."""
    tag = image_tag(project_name)
    tar_path = WEB_API_DIR / project_name / f"{project_name}.tar"
    ok, out = _docker(["save", "-o", str(tar_path), tag], timeout=120)
    return ok, tar_path, out


# ── Container lifecycle ────────────────────────────────────────────────────────

def run_container(project_name: str, language: str) -> tuple[bool, str]:
    cname = container_name(project_name)
    tag = image_tag(project_name)
    container_port = 8080 if language == "java" else 8000
    host_port = _assign_container_port(project_name)
    _docker(["rm", "-f", cname], timeout=15)   # remove any stale container
    return _docker([
        "run", "-d",
        "--name", cname,
        "-p", f"{host_port}:{container_port}",
        "--restart", "unless-stopped",
        tag,
    ], timeout=30)


def stop_container(project_name: str) -> tuple[bool, str]:
    return _docker(["stop", container_name(project_name)], timeout=30)


def start_container(project_name: str) -> tuple[bool, str]:
    return _docker(["start", container_name(project_name)], timeout=30)


def delete_container(project_name: str) -> tuple[bool, str]:
    return _docker(["rm", "-f", container_name(project_name)], timeout=30)


def delete_image(project_name: str) -> tuple[bool, str]:
    return _docker(["rmi", "-f", image_tag(project_name)], timeout=30)
