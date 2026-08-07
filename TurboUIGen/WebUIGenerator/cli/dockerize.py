#!/usr/bin/env python3
"""
TurboUIGen Dockerizer
---------------------
Packages any project from generated/ as a self-contained Docker image
served by nginx. Run it, click the URL.

Works with both React/Vite builds and HTML/CSS/JS projects generated
by the Figma export pipeline.

Usage:
    python cli/dockerize.py                     # interactive
    python cli/dockerize.py <project-slug>      # direct
    python cli/dockerize.py --list              # show all projects
    python cli/dockerize.py --status            # show running containers
    python cli/dockerize.py --stop <name>       # stop a container
    python cli/dockerize.py --stop-all          # stop all containers
"""

import sys
import json
import subprocess
import socket
import re
from pathlib import Path

BASE_DIR   = Path(__file__).parent.parent          # TurboUIGen root
OUTPUT_DIR = BASE_DIR / "generated"
REGISTRY   = OUTPUT_DIR / "projects.json"
DOCKER_REG = OUTPUT_DIR / "docker_registry.json"   # tracks slug → docker port

# ── Terminal colours ───────────────────────────────────────────────────────────
def c(text, code): return f"\033[{code}m{text}\033[0m"
BOLD    = lambda t: c(t, "1")
DIM     = lambda t: c(t, "2")
GREEN   = lambda t: c(t, "32")
CYAN    = lambda t: c(t, "36")
YELLOW  = lambda t: c(t, "33")
RED     = lambda t: c(t, "31")
MAGENTA = lambda t: c(t, "35")

SEP = DIM("  " + "-" * 54)

# ── Registry helpers ───────────────────────────────────────────────────────────
def load_registry() -> dict:
    if REGISTRY.exists():
        try:
            return json.loads(REGISTRY.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def load_docker_reg() -> dict:
    """{ slug: { port, container_name } }"""
    if DOCKER_REG.exists():
        try:
            return json.loads(DOCKER_REG.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_docker_reg(reg: dict) -> None:
    DOCKER_REG.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")


def next_docker_port() -> int:
    """Return 8080 or one above the highest port already recorded."""
    reg = load_docker_reg()
    if not reg:
        return 8080
    highest = max(v["port"] for v in reg.values())
    return highest + 1


def alloc_docker_port(slug: str) -> int:
    """
    Return a port for this slug that is genuinely available:
    - If slug has a stored port AND that port isn't used by a different
      running container, reuse it.
    - Otherwise allocate a new port above the highest recorded one.
    """
    reg = load_docker_reg()

    # Ports currently claimed by OTHER running containers
    occupied = {
        ct["port"]
        for ct in get_running_containers()
        if ct["port"] and ct["name"] != slug
    }

    if slug in reg:
        stored = reg[slug]["port"]
        if stored not in occupied and port_free(stored):
            return stored
        # Stored port is taken — fall through to allocate a new one

    port = next_docker_port()
    while port in occupied or not port_free(port):
        port += 1

    reg[slug] = {"port": port, "container_name": slug}
    save_docker_reg(reg)
    return port


def record_docker_port(slug: str, port: int) -> None:
    reg = load_docker_reg()
    reg[slug] = {"port": port, "container_name": slug}
    save_docker_reg(reg)


# ── Docker helpers ─────────────────────────────────────────────────────────────
def docker_available() -> bool:
    try:
        r = subprocess.run(["docker", "info"], capture_output=True, timeout=10)
        return r.returncode == 0
    except Exception:
        return False


def image_name(slug: str) -> str:
    return "turboui-" + re.sub(r"[^a-z0-9-]", "-", slug.lower()).strip("-")


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("", port))
            return True
        except OSError:
            return False


def get_running_containers() -> list[dict]:
    """
    Return list of dicts for every running TurboUIGen container.
    Matches both container names (slug) and image names (turboui-*).
    """
    try:
        # Get all running containers, filter client-side by image prefix
        out = subprocess.check_output(
            ["docker", "ps",
             "--format", "{{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}"],
            text=True, timeout=10,
        ).strip()
    except Exception:
        return []

    containers = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        cid, name, image, ports, status = parts[0], parts[1], parts[2], parts[3], parts[4]
        # Only include TurboUIGen containers (matched by image name prefix)
        if not image.startswith("turboui-"):
            continue
        m = re.search(r":(\d+)->", ports)
        host_port = int(m.group(1)) if m else None
        containers.append({
            "id":     cid[:12],
            "name":   name,
            "image":  image,
            "port":   host_port,
            "status": status,
        })
    return containers


def stop_container(name: str) -> bool:
    r = subprocess.run(["docker", "stop", name], capture_output=True)
    return r.returncode == 0


def remove_container(name: str) -> bool:
    subprocess.run(["docker", "stop", name], capture_output=True)
    r = subprocess.run(["docker", "rm", name], capture_output=True)
    return r.returncode == 0


# ── Running containers menu ────────────────────────────────────────────────────
def show_running_menu() -> None:
    """
    Show running TurboUIGen containers and let user stop/remove any before continuing.
    Returns when user is done (presses Enter or types 'done').
    """
    containers = get_running_containers()
    if not containers:
        return

    while True:
        containers = get_running_containers()
        if not containers:
            print(GREEN("  No TurboUIGen containers running."))
            print()
            return

        print()
        print(BOLD("  Running TurboUIGen containers:"))
        print(SEP)
        for i, ct in enumerate(containers, 1):
            url = f"http://localhost:{ct['port']}" if ct["port"] else "unknown port"
            print(f"  {CYAN(str(i))}.  {BOLD(ct['name'])}")
            print(f"      {DIM('URL')}    {CYAN(url)}")
            print(f"      {DIM('Image')}  {ct['image']}  |  {ct['status']}")
        print(SEP)
        print()
        print(DIM("  Enter number(s) to stop/remove, or press Enter to continue."))
        print(DIM("  Examples:  2        stop #2"))
        print(DIM("             1 3      stop #1 and #3"))
        print(DIM("             all      stop all"))
        print(DIM("             done     continue without stopping any"))
        print()

        try:
            raw = input(BOLD(MAGENTA("manage")) + " > ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            sys.exit(0)

        if not raw or raw in ("done", "continue", "skip", ""):
            print()
            return

        if raw == "all":
            targets = containers
        else:
            targets = []
            for token in raw.split():
                if token.isdigit():
                    idx = int(token) - 1
                    if 0 <= idx < len(containers):
                        targets.append(containers[idx])
                    else:
                        print(YELLOW(f"  No container #{token}."))

        if not targets:
            continue

        print()
        for ct in targets:
            print(DIM(f"  Stopping and removing {ct['name']}…"), end=" ", flush=True)
            if remove_container(ct["name"]):
                print(GREEN("done"))
                # Free up the port in docker registry
                reg = load_docker_reg()
                for slug, info in list(reg.items()):
                    if info.get("container_name") == ct["name"]:
                        del reg[slug]
                        save_docker_reg(reg)
                        break
            else:
                print(RED("failed"))
        print()


# ── Project helpers ────────────────────────────────────────────────────────────
def list_projects() -> list[dict]:
    reg = load_registry()
    projects = []
    for d in sorted(OUTPUT_DIR.iterdir()):
        if d.is_dir() and (d / "index.html").exists():
            entry = reg.get(d.name, {})
            projects.append({
                "slug":  d.name,
                "title": entry.get("title", d.name),
                "port":  entry.get("port"),
                "path":  d,
            })
    return projects


def pick_project() -> dict:
    projects = list_projects()
    if not projects:
        print(RED("  No projects found in generated/. Generate one from the UI or CLI first."))
        sys.exit(1)

    docker_reg = load_docker_reg()
    running    = {ct["name"] for ct in get_running_containers()}

    print(BOLD("  Available projects:"))
    print(SEP)
    for i, p in enumerate(projects, 1):
        is_running = p["slug"] in running
        dr_entry   = docker_reg.get(p["slug"])
        docker_port = dr_entry["port"] if dr_entry else None
        status = GREEN(" [running]") if is_running else ""
        port_note = f"  docker port {docker_port}" if docker_port else ""
        print(f"  {CYAN(str(i))}.  {BOLD(p['title'])}{status}")
        print(DIM(f"      {p['slug']}{port_note}"))
    print(SEP)
    print()

    while True:
        try:
            raw = input(BOLD(MAGENTA("pick")) + " > ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            sys.exit(0)
        if raw.isdigit() and 1 <= int(raw) <= len(projects):
            return projects[int(raw) - 1]
        for p in projects:
            if raw == p["slug"] or raw.lower() == p["title"].lower():
                return p
        print(YELLOW(f"  Enter a number (1–{len(projects)}) or the project slug."))


# ── Docker file templates ──────────────────────────────────────────────────────
DOCKERFILE = """\
# syntax=docker/dockerfile:1
FROM nginx:alpine

COPY . /usr/share/nginx/html/

RUN printf 'server {\\n\
    listen 80;\\n\
    root /usr/share/nginx/html;\\n\
    index index.html;\\n\
    location / {\\n\
        try_files $uri $uri/ /index.html;\\n\
    }\\n\
    location /data/ {\\n\
        add_header Access-Control-Allow-Origin *;\\n\
    }\\n\
    gzip on;\\n\
    gzip_types text/html text/css application/javascript application/json;\\n\
}\\n' > /etc/nginx/conf.d/default.conf

EXPOSE 80
"""


def make_compose(slug: str, host_port: int) -> str:
    img = image_name(slug)
    return f"""\
services:
  {slug}:
    image: {img}
    build: .
    ports:
      - "{host_port}:80"
    restart: unless-stopped
"""


def make_readme(title: str, slug: str, host_port: int) -> str:
    img = image_name(slug)
    return f"""\
# {title}

Generated by TurboUIGen. Served by nginx inside Docker.

## Quick start

```bash
docker build -t {img} .
docker run -d -p {host_port}:80 --name {slug} {img}
# Open http://localhost:{host_port}
```

## Docker Compose

```bash
docker compose up -d
```

Open: http://localhost:{host_port}

## Stop / remove

```bash
docker stop {slug} && docker rm {slug}
# or
docker compose down
```
"""


# ── CLI commands ──────────────────────────────────────────────────────────────
def cmd_status() -> None:
    """--status  Show all running TurboUIGen containers in a clean table."""
    containers = get_running_containers()
    dr = load_docker_reg()

    print()
    print(BOLD("  TurboUIGen — Docker Status"))
    print(SEP)

    if not containers:
        print(DIM("  No TurboUIGen containers are currently running."))
        print()

        # Show any that were previously built but are stopped
        stopped = [(slug, info) for slug, info in dr.items()
                   if slug not in {ct["name"] for ct in containers}]
        if stopped:
            print(DIM("  Previously built (stopped):"))
            for slug, info in stopped:
                print(DIM(f"    {slug}  port {info['port']}"))
            print()
        return

    # Column widths
    name_w   = max(len(ct["name"])   for ct in containers)
    status_w = max(len(ct["status"]) for ct in containers)
    name_w   = max(name_w, 12)

    header = (
        f"  {'#':<4}"
        f"{'Container':<{name_w + 2}}"
        f"{'Port':<10}"
        f"{'URL':<32}"
        f"{'Status'}"
    )
    print(DIM(header))
    print(DIM("  " + "-" * (name_w + 58)))

    for i, ct in enumerate(containers, 1):
        url = f"http://localhost:{ct['port']}" if ct["port"] else "unknown"
        print(
            f"  {CYAN(str(i)):<13}"          # #  (with colour codes)
            f"{BOLD(ct['name']):<{name_w + 11}}"  # name (with colour codes)
            f"{str(ct['port']):<10}"
            f"{CYAN(url):<41}"
            f"{GREEN(ct['status'])}"
        )

    print()
    print(DIM(f"  {len(containers)} container(s) running."))
    print()
    print(DIM("  To stop one:    python dockerize.py --stop <name>"))
    print(DIM("  To remove one:  python dockerize.py --remove <name>"))
    print(DIM("  To stop all:    python dockerize.py --stop-all"))
    print()


def cmd_stop(name: str, remove: bool = False) -> None:
    """--stop / --remove  Stop (and optionally remove) a named container."""
    containers = get_running_containers()
    names = [ct["name"] for ct in containers]

    if name not in names:
        print(RED(f"  Container '{name}' is not running."))
        running_names = ", ".join(names) if names else "none"
        print(DIM(f"  Running: {running_names}"))
        return

    action = "Stopping and removing" if remove else "Stopping"
    print(DIM(f"  {action} {name}…"), end=" ", flush=True)
    ok = remove_container(name) if remove else stop_container(name)
    print(GREEN("done") if ok else RED("failed"))

    if ok and remove:
        reg = load_docker_reg()
        for slug, info in list(reg.items()):
            if info.get("container_name") == name:
                del reg[slug]
                save_docker_reg(reg)
                break
    print()


def cmd_stop_all() -> None:
    """--stop-all  Stop and remove every running TurboUIGen container."""
    containers = get_running_containers()
    if not containers:
        print(DIM("  No TurboUIGen containers running."))
        return
    for ct in containers:
        print(DIM(f"  Stopping {ct['name']}…"), end=" ", flush=True)
        ok = remove_container(ct["name"])
        print(GREEN("done") if ok else RED("failed"))
    reg = load_docker_reg()
    running_names = {ct["name"] for ct in containers}
    for slug in list(reg.keys()):
        if reg[slug].get("container_name") in running_names:
            del reg[slug]
    save_docker_reg(reg)
    print()


def cmd_list_projects() -> None:
    """--list  Show all built projects (not docker status)."""
    reg = load_registry()
    dr  = load_docker_reg()
    running = {ct["name"] for ct in get_running_containers()} if docker_available() else set()

    print()
    print(BOLD("  TurboUIGen — Built Projects"))
    print(SEP)

    projects = list_projects()
    if not projects:
        print(DIM("  No projects yet. Run prompt_to_figma_agent.py to build one."))
        print()
        return

    for i, p in enumerate(projects, 1):
        docker_info = dr.get(p["slug"])
        is_running  = p["slug"] in running
        status      = GREEN("  running") if is_running else DIM("  stopped")
        port_str    = f"  port {docker_info['port']}" if docker_info else ""
        print(f"  {CYAN(str(i))}.  {BOLD(p['title'])}{status}")
        print(DIM(f"      slug: {p['slug']}{port_str}"))
    print()


def print_help() -> None:
    print()
    print(BOLD("  TurboUIGen Dockerizer — Commands"))
    print(SEP)
    print(f"  {CYAN('python dockerize.py')}")
    print(DIM("      Interactive: manage running containers, then pick a project to build"))
    print()
    print(f"  {CYAN('python dockerize.py <slug>')}")
    print(DIM("      Directly build & run a specific project"))
    print()
    print(f"  {CYAN('python dockerize.py --status')}")
    print(DIM("      Show all running TurboUIGen containers with name, port, URL, status"))
    print()
    print(f"  {CYAN('python dockerize.py --list')}")
    print(DIM("      List all built projects in generated/"))
    print()
    print(f"  {CYAN('python dockerize.py --stop <name>')}")
    print(DIM("      Stop a running container by name"))
    print()
    print(f"  {CYAN('python dockerize.py --remove <name>')}")
    print(DIM("      Stop and remove a container by name"))
    print()
    print(f"  {CYAN('python dockerize.py --stop-all')}")
    print(DIM("      Stop and remove all running TurboUIGen containers"))
    print()


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    print()
    print(BOLD("  TurboUIGen Dockerizer"))
    print(SEP)

    args = sys.argv[1:]

    if not args or "--help" in args or "-h" in args:
        if not args:
            pass  # fall through to interactive mode
        else:
            print_help()
            return

    if "--status" in args:
        cmd_status()
        return

    if "--list" in args:
        cmd_list_projects()
        return

    if "--stop-all" in args:
        cmd_stop_all()
        return

    if "--stop" in args:
        idx = args.index("--stop")
        name = args[idx + 1] if idx + 1 < len(args) else ""
        if not name:
            print(RED("  Usage: python dockerize.py --stop <container-name>"))
            return
        cmd_stop(name, remove=False)
        return

    if "--remove" in args:
        idx = args.index("--remove")
        name = args[idx + 1] if idx + 1 < len(args) else ""
        if not name:
            print(RED("  Usage: python dockerize.py --remove <container-name>"))
            return
        cmd_stop(name, remove=True)
        return

    if not docker_available():
        print(YELLOW("  Docker is not running or not installed."))
        print(DIM("  Start Docker Desktop and try again."))
        print()
        # Still write the files so user can run manually
        if args and not args[0].startswith("-"):
            projects = list_projects()
            matches  = [p for p in projects if p["slug"] == args[0]]
            project  = matches[0] if matches else pick_project()
        else:
            project = pick_project()
        slug      = project["slug"]
        title     = project["title"]
        proj_dir  = project["path"]
        img       = image_name(slug)
        port      = alloc_docker_port(slug)
        (proj_dir / "Dockerfile").write_text(DOCKERFILE, encoding="utf-8")
        (proj_dir / "docker-compose.yml").write_text(make_compose(slug, port), encoding="utf-8")
        (proj_dir / "README.docker.md").write_text(make_readme(title, slug, port), encoding="utf-8")
        print(GREEN("  Files written. Once Docker is running:"))
        print()
        print(f'    cd "{proj_dir}"')
        print(f"    docker build -t {img} .")
        print(f"    docker run -d -p {port}:80 --name {slug} {img}")
        print(f"\n  URL: {CYAN(f'http://localhost:{port}')}")
        print()
        return

    # ── Step 1: show running containers, offer to stop/remove ─────────────────
    show_running_menu()

    # ── Step 2: pick project ───────────────────────────────────────────────────
    if args and not args[0].startswith("-"):
        slug_arg = args[0]
        projects = list_projects()
        matches  = [p for p in projects if p["slug"] == slug_arg]
        if not matches:
            print(RED(f"  Project '{slug_arg}' not found."))
            print(DIM("  Run: python cli/dockerize.py --list to see available projects."))
            sys.exit(1)
        project = matches[0]
    else:
        project = pick_project()

    slug      = project["slug"]
    title     = project["title"]
    proj_dir  = project["path"]
    img       = image_name(slug)

    # ── Step 3: allocate port ──────────────────────────────────────────────────
    host_port = alloc_docker_port(slug)

    print()
    print(f"  Project : {BOLD(title)}")
    print(f"  Folder  : {DIM(str(proj_dir))}")
    print(f"  Image   : {CYAN(img)}")
    print(f"  Port    : {host_port}  ->  {CYAN(f'http://localhost:{host_port}')}")
    print()

    # ── Step 4: write docker files ─────────────────────────────────────────────
    (proj_dir / "Dockerfile").write_text(DOCKERFILE, encoding="utf-8")
    (proj_dir / "docker-compose.yml").write_text(make_compose(slug, host_port), encoding="utf-8")
    (proj_dir / "README.docker.md").write_text(make_readme(title, slug, host_port), encoding="utf-8")
    print(GREEN("  Dockerfile + docker-compose.yml written."))

    # ── Step 5: force-remove any existing container with this name ────────────
    print(DIM(f"  Removing any existing container named '{slug}'…"))
    subprocess.run(["docker", "rm", "-f", slug], capture_output=True)

    # ── Step 6: build image ────────────────────────────────────────────────────
    print(DIM("  Building Docker image (this may take a moment)…"))
    build = subprocess.run(
        ["docker", "build", "-t", img, "."],
        cwd=str(proj_dir),
        capture_output=True,
        text=True,
    )
    if build.returncode != 0:
        print(RED("  docker build failed:"))
        print(build.stderr[-2000:])
        sys.exit(1)
    print(GREEN(f"  Image built: {img}"))

    # ── Step 7: run container ──────────────────────────────────────────────────
    print(DIM("  Starting container…"))
    run = subprocess.run(
        ["docker", "run", "-d", "-p", f"{host_port}:80", "--name", slug, img],
        capture_output=True,
        text=True,
    )
    if run.returncode != 0:
        print(RED("  docker run failed:"))
        print(run.stderr)
        sys.exit(1)

    container_id = run.stdout.strip()[:12]
    url = f"http://localhost:{host_port}"

    print()
    print(f"  {BOLD(GREEN('Running!'))}  {BOLD(title)}")
    print()
    print(f"  {BOLD('URL')}        {CYAN(url)}")
    print(f"  {DIM('Container')}  {container_id}")
    print(f"  {DIM('Image')}      {img}")
    print()
    print(DIM(f"  Stop:    docker stop {slug}"))
    print(DIM(f"  Remove:  docker rm {slug}"))
    print()

    import webbrowser
    webbrowser.open(url)


if __name__ == "__main__":
    main()
