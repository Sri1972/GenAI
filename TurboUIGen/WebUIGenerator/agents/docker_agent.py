"""
Docker image builder and container manager for generated React apps.
  build_image              — vite build → dist/ → Dockerfile → docker build
  save_image               — docker save → .tar for download
  run/stop/start/delete_container — container lifecycle
  get_status               — image + container state dict
"""

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import socket

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import WEB_APPS_DIR

# Docker build output lives inside each project: web-apps/{name}/docker/
# (no separate top-level docker-builds folder)

# Host port range for containers (separate from Vite dev ports 5173+)
_CONTAINER_PORT_START = 7000
_CONTAINER_PORTS_FILE = WEB_APPS_DIR.parent / ".container_ports.json"

# Cache docker availability so slow "docker info" only runs once per 10s
_docker_avail_cache: tuple[float, bool] | None = None


def _port_is_free(port: int) -> bool:
    """Return True if nothing is bound to this port on localhost right now."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


# ── Port assignment ────────────────────────────────────────────────────────────

def _load_container_ports() -> dict:
    if _CONTAINER_PORTS_FILE.exists():
        try:
            return json.loads(_CONTAINER_PORTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_container_ports(ports: dict):
    _CONTAINER_PORTS_FILE.write_text(
        json.dumps(ports, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _docker_used_ports() -> set:
    """Get all host ports currently mapped by Docker containers."""
    ok, out = _docker(["ps", "--format", "{{.Ports}}"], timeout=10)
    if not ok:
        return set()
    import re
    return set(int(m) for m in re.findall(r"0\.0\.0\.0:(\d+)->", out))


def _assign_container_port(project_name: str) -> int:
    ports = _load_container_ports()
    docker_ports = _docker_used_ports()
    if project_name in ports:
        p = ports[project_name]
        if _port_is_free(p) and p not in docker_ports:
            return p
    # Find the lowest free port starting from _CONTAINER_PORT_START
    used = set(ports.values()) | docker_ports
    port = _CONTAINER_PORT_START
    while not _port_is_free(port) or port in used:
        port += 1
    ports[project_name] = port
    _save_container_ports(ports)
    return port


# ── Naming ─────────────────────────────────────────────────────────────────────

def image_tag(project_name: str) -> str:
    return f"turboui-{project_name}:latest"

def container_name(project_name: str) -> str:
    return f"turboui-{project_name}"

def _build_dir(project_name: str) -> Path:
    """Docker build context lives inside the project folder: web-apps/{name}/docker/"""
    return WEB_APPS_DIR / project_name / "docker"

def _status_file(project_name: str) -> Path:
    return WEB_APPS_DIR / project_name / ".docker.json"


# ── Persistence ────────────────────────────────────────────────────────────────

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
        r = subprocess.run(
            ["docker"] + args,
            capture_output=True, timeout=timeout, cwd=cwd,
        )
        stdout = r.stdout.decode("utf-8", errors="replace") if r.stdout else ""
        stderr = r.stderr.decode("utf-8", errors="replace") if r.stderr else ""
        return r.returncode == 0, (stdout + stderr).strip()
    except FileNotFoundError:
        return False, "Docker not found. Is Docker Desktop installed and running?"
    except subprocess.TimeoutExpired:
        return False, f"Docker command timed out after {timeout}s"
    except Exception as e:
        return False, str(e)


# ── Availability + status ──────────────────────────────────────────────────────

def is_docker_available() -> bool:
    global _docker_avail_cache
    now = time.time()
    if _docker_avail_cache and (now - _docker_avail_cache[0]) < 10:
        return _docker_avail_cache[1]
    # Use a longer timeout for Windows Docker Desktop — the named-pipe handshake
    # can take several seconds even when Docker is fully running.
    # Fall back to a simple `docker ps` ping which is faster than `docker info`.
    ok, _ = _docker(["ps", "--format", "{{.ID}}"], timeout=15)
    _docker_avail_cache = (now, ok)
    return ok


def get_status(project_name: str) -> dict:
    tag   = image_tag(project_name)
    cname = container_name(project_name)
    stored    = _read_status(project_name)
    host_port = _load_container_ports().get(project_name)

    if not is_docker_available():
        return {
            "dockerAvailable": False,
            "imageExists":     False,
            "imageTag":        None,
            "containerStatus": "none",
            "containerName":   None,
            "hostPort":        host_port,
            "builtAt":         stored.get("builtAt"),
            "containerUrl":    None,
        }

    ok_img, img_out = _docker(["image", "inspect", tag, "--format", "{{.Id}}"], timeout=8)
    image_exists = ok_img and bool(img_out.strip())

    ok_con, con_out = _docker(["inspect", cname, "--format", "{{.State.Status}}"], timeout=8)
    container_status = con_out.strip() if ok_con else "none"

    return {
        "dockerAvailable": True,
        "imageExists":     image_exists,
        "imageTag":        tag if image_exists else None,
        "containerStatus": container_status,
        "containerName":   cname if container_status != "none" else None,
        "hostPort":        host_port,
        "builtAt":         stored.get("builtAt"),
        "containerUrl":    (
            f"http://localhost:{host_port}"
            if container_status == "running" and host_port else None
        ),
    }


# ── Build ──────────────────────────────────────────────────────────────────────

def build_image(project_name: str, project_dir: Path, progress=None) -> tuple[bool, str]:
    """
    1. Write vite.config.docker.ts  (base: '/', abs outDir)
    2. vite build  →  dist/ in docker build context
    3. Write Dockerfile + nginx.conf
    4. docker build  →  image tagged turboui-{name}:latest
    """
    from agents.uigen_agent import NODE_PATH, _DS_CLEAN_JUNCTION, _SHARED_NM_JUNCTION

    def _p(msg: str):
        if progress:
            progress(f"docker_build:{msg}")

    bdir = _build_dir(project_name)
    bdir.mkdir(parents=True, exist_ok=True)
    dist_dir = bdir / "dist"

    # 1. Temporary vite config for production build
    _p("Writing Docker vite config…")
    ds_index = _DS_CLEAN_JUNCTION + "/src/index.ts"
    docker_cfg = (
        "import { defineConfig } from 'vite'\n"
        "import react from '@vitejs/plugin-react'\n"
        "export default defineConfig({\n"
        "  plugins: [react()],\n"
        "  resolve: {\n"
        "    alias: { 'mobility-global-ds': '" + ds_index + "' },\n"
        "    dedupe: ['react', 'react-dom'],\n"
        "    preserveSymlinks: true,\n"
        "  },\n"
        "  base: '/',\n"
        "  build: {\n"
        "    outDir: '" + dist_dir.as_posix() + "',\n"
        "    emptyOutDir: true,\n"
        "  },\n"
        "})\n"
    )
    cfg_path = project_dir / "vite.config.docker.ts"
    cfg_path.write_text(docker_cfg, encoding="utf-8")

    # 2. Patch main.tsx — remove basename so React Router works at root path in nginx
    main_tsx = project_dir / "src" / "main.tsx"
    main_tsx_original: str | None = None
    if main_tsx.exists():
        import re as _re
        original = main_tsx.read_text(encoding="utf-8")
        patched  = _re.sub(r'\s*basename="[^"]*"', '', original)
        if patched != original:
            main_tsx_original = original
            main_tsx.write_text(patched, encoding="utf-8")
            _p("Patched main.tsx: removed basename for root-path serving")

    # 3. vite build
    _p("Running vite build (this takes ~30s)…")
    node_exe = Path(NODE_PATH) / "node.exe"
    vite_js  = Path(_SHARED_NM_JUNCTION) / "vite" / "bin" / "vite.js"
    if not vite_js.exists():
        vite_js = project_dir / "node_modules" / "vite" / "bin" / "vite.js"

    env = os.environ.copy()
    env["PATH"] = NODE_PATH + os.pathsep + env.get("PATH", "")

    r = subprocess.run(
        [str(node_exe), str(vite_js), "build", "--config", str(cfg_path)],
        cwd=str(project_dir), env=env,
        capture_output=True, text=True, timeout=180,
    )
    # Restore main.tsx to its original state (with basename) for Vite dev server
    try:
        cfg_path.unlink(missing_ok=True)
    except Exception:
        pass
    if main_tsx_original is not None:
        main_tsx.write_text(main_tsx_original, encoding="utf-8")

    if r.returncode != 0:
        return False, f"vite build failed:\n{r.stdout[-800:]}\n{r.stderr[-800:]}"
    if not (dist_dir / "index.html").exists():
        return False, "vite build succeeded but index.html missing from dist/"

    n_files = len(list(dist_dir.rglob("*")))
    _p(f"vite build complete — {n_files} output files")

    # 3. Dockerfile — choose between static (nginx) and API-backed (Python + FastAPI)
    api_dir = project_dir / "api"
    has_api_server = (api_dir / "app_server.py").exists() or (project_dir / "app_server.py").exists()
    _p("Writing Dockerfile…")

    if has_api_server:
        # Copy API server files into build context
        import shutil
        copied_files = []
        # Check api/ subfolder first, then legacy root-level
        api_source = api_dir if (api_dir / "app_server.py").exists() else project_dir
        for fname in ("app_server.py", "schema.sql", "seed.sql", ".env", "requirements.txt"):
            src = api_source / fname
            if src.exists():
                shutil.copy2(str(src), str(bdir / fname))
                copied_files.append(fname)

        # Ensure python-multipart is in requirements (FastAPI needs it for form data)
        req_file = bdir / "requirements.txt"
        if req_file.exists():
            req_text = req_file.read_text(encoding="utf-8")
            if "python-multipart" not in req_text:
                req_file.write_text(req_text.rstrip() + "\npython-multipart\n", encoding="utf-8")

        # Build COPY lines for all files that exist
        copy_lines = "COPY requirements.txt .\n"
        copy_lines += "RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -r requirements.txt\n"
        copy_lines += "COPY dist/ /app/dist/\n"
        for fname in copied_files:
            if fname != "requirements.txt":
                copy_lines += f"COPY {fname} .\n"

        (bdir / "Dockerfile").write_text(
            "FROM python:3.11-slim\n"
            "WORKDIR /app\n"
            + copy_lines +
            "ENV API_PORT=80\n"
            "EXPOSE 80\n"
            'CMD ["python", "app_server.py"]\n',
            encoding="utf-8",
        )
    else:
        (bdir / "nginx.conf").write_text(
            "server {\n"
            "    listen 80;\n"
            "    server_name _;\n"
            "    root /usr/share/nginx/html;\n"
            "    index index.html;\n"
            "    location / {\n"
            "        try_files $uri $uri/ /index.html;\n"
            "    }\n"
            "    location ~* \\.(js|css|png|jpg|jpeg|gif|svg|ico|woff|woff2|ttf)$ {\n"
            "        expires 1y;\n"
            '        add_header Cache-Control "public, immutable";\n'
            "    }\n"
            "}\n",
            encoding="utf-8",
        )
        (bdir / "Dockerfile").write_text(
            "FROM nginx:alpine\n"
            "COPY dist/ /usr/share/nginx/html/\n"
            "COPY nginx.conf /etc/nginx/conf.d/default.conf\n"
            "EXPOSE 80\n"
            'CMD ["nginx", "-g", "daemon off;"]\n',
            encoding="utf-8",
        )

    # 4. docker build
    tag = image_tag(project_name)
    _p(f"Building Docker image {tag} (first run downloads nginx:alpine ~10MB)…")
    ok, out = _docker(["build", "-t", tag, "."], timeout=300, cwd=str(bdir))
    if not ok:
        return False, f"docker build failed:\n{out[-1500:]}"

    _write_status(project_name, {
        "builtAt":  datetime.now(timezone.utc).isoformat(),
        "imageTag": tag,
    })
    _p(f"Image {tag} ready")
    return True, out


# ── Image export ───────────────────────────────────────────────────────────────

def save_image(project_name: str) -> tuple[bool, Path, str]:
    """docker save → .tar file. Returns (ok, tar_path, error_msg)."""
    tag      = image_tag(project_name)
    tar_path = _build_dir(project_name) / f"{project_name}.tar"
    ok, out  = _docker(["save", "-o", str(tar_path), tag], timeout=120)
    return ok, tar_path, out


# ── Container lifecycle ────────────────────────────────────────────────────────

def run_container(project_name: str) -> tuple[bool, str]:
    cname     = container_name(project_name)
    tag       = image_tag(project_name)
    host_port = _assign_container_port(project_name)
    _docker(["rm", "-f", cname], timeout=15)   # remove any stale container
    return _docker([
        "run", "-d",
        "--name", cname,
        "-p", f"{host_port}:80",
        "--restart", "unless-stopped",
        tag,
    ], timeout=30)


def stop_container(project_name: str) -> tuple[bool, str]:
    return _docker(["stop", container_name(project_name)], timeout=30)


def start_container(project_name: str) -> tuple[bool, str]:
    return _docker(["start", container_name(project_name)], timeout=30)


def delete_container(project_name: str) -> tuple[bool, str]:
    return _docker(["rm", "-f", container_name(project_name)], timeout=30)
