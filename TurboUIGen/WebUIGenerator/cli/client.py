#!/usr/bin/env python3
"""
TurboUIGen CLI — generate and manage React apps from the command line.

Usage:
  python -m cli.client generate "IPL dashboard with team scores and charts"
  python -m cli.client list
  python -m cli.client start ipl-dashboard
  python -m cli.client stop  ipl-dashboard
  python -m cli.client delete ipl-dashboard
  python -m cli.client open  ipl-dashboard
"""

import argparse
import subprocess
import sys
import webbrowser
from pathlib import Path

# Allow running from the TurboUIGen root
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.uigen_agent import (
    delete_project,
    generate_project,
    list_projects,
    start_project,
    stop_project,
)

# ── ANSI colours ──────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
BLUE   = "\033[94m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

STEPS = {
    "llm":     ("🤖", "Calling LLM to generate project files…"),
    "crew":    ("🤖", "Multi-agent crew building your app…"),
    "write":   ("📝", "Writing files to disk…"),
    "install": ("📦", "Running npm install…"),
    "start":   ("🚀", "Starting Vite dev server…"),
    "ready":   ("✅", "App is ready!"),
}


def _banner():
    print(f"\n{BOLD}{CYAN}┌────────────────────────────────────────┐")
    print(f"│  ⚡ TurboUIGen — AI App Generator       │")
    print(f"└────────────────────────────────────────┘{RESET}\n")


def _progress(step: str):
    # Handle prefixed progress messages (crew:..., skill:..., llm_codegen:...)
    if ":" in step and step.split(":")[0] in ("crew", "skill", "llm_codegen", "tsc_heal"):
        prefix, msg = step.split(":", 1)
        icons = {"crew": "🤖", "skill": "⚡", "llm_codegen": "🔧", "tsc_heal": "🩹"}
        print(f"  {icons.get(prefix, '…')}  {msg}")
        return
    icon, label = STEPS.get(step, ("…", step))
    print(f"  {icon}  {label}")


def cmd_generate(args):
    _banner()

    # ── Figma URL path ─────────────────────────────────────────────────────────
    if args.figma:
        from agents.figma_to_web_using_api_agent import run as figma_run
        from agents.figma_to_web_using_playwright_agent import start_figma_project

        print(f"{BOLD}Figma URL:{RESET} {args.figma}")
        if args.prompt:
            print(f"{BOLD}Prompt:{RESET} {args.prompt}\n")
        else:
            print()
        try:
            raw = figma_run(figma_url=args.figma, prompt=args.prompt or "")
            result = start_figma_project(raw["project_name"])
        except Exception as e:
            print(f"\n{RED}✗ Error: {e}{RESET}")
            sys.exit(1)

        print(f"\n{GREEN}{BOLD}✓ Generated: {raw.get('title', raw['project_name'])}{RESET}")
        print(f"  {DIM}Project : {raw['project_name']}{RESET}")
        print(f"  {DIM}Files   : {', '.join(raw.get('files', []))}{RESET}")
        print(f"\n  {BLUE}{BOLD}🌐 {result['url']}{RESET}\n")
        if not args.no_open:
            webbrowser.open(result["url"])
        return

    # ── Text prompt path ───────────────────────────────────────────────────────
    print(f"{BOLD}Prompt:{RESET} {args.prompt}\n")
    try:
        result = generate_project(args.prompt, progress=_progress)
    except Exception as e:
        print(f"\n{RED}✗ Error: {e}{RESET}")
        sys.exit(1)

    print(f"\n{GREEN}{BOLD}✓ Generated: {result['title']}{RESET}")
    print(f"  {DIM}Project : {result['projectName']}{RESET}")
    print(f"  {DIM}Files   : {len(result['files'])}{RESET}")
    print(f"\n  {BLUE}{BOLD}🌐 {result['url']}{RESET}\n")

    if not args.no_open:
        webbrowser.open(result["url"])


def cmd_list(args):
    projects = list_projects()
    if not projects:
        print(f"{YELLOW}No projects found.{RESET}")
        return

    _banner()
    print(f"{BOLD}{'NAME':<35} {'PORT':<8} {'STATUS':<10} {'FILES'}{RESET}")
    print("─" * 65)
    for p in projects:
        status  = f"{GREEN}running{RESET}" if p["running"] else f"{DIM}stopped{RESET}"
        port    = str(p["port"]) if p["port"] else "—"
        print(f"{p['name']:<35} {port:<8} {status:<20} {p['files']}")
    print()


def cmd_start(args):
    print(f"  🚀  Starting {BOLD}{args.name}{RESET}…")
    try:
        result = start_project(args.name)
    except Exception as e:
        print(f"{RED}✗ {e}{RESET}")
        sys.exit(1)
    print(f"  {GREEN}✓ Running at {BOLD}{result['url']}{RESET}")
    if not args.no_open:
        webbrowser.open(result["url"])


def cmd_stop(args):
    print(f"  ⏹  Stopping {BOLD}{args.name}{RESET}…")
    stop_project(args.name)
    print(f"  {GREEN}✓ Stopped.{RESET}")


def cmd_delete(args):
    confirm = input(f"  {RED}Delete '{args.name}' and all its files? [y/N] {RESET}").strip().lower()
    if confirm != "y":
        print("  Cancelled.")
        return
    print(f"  🗑  Deleting {BOLD}{args.name}{RESET}…")
    delete_project(args.name)
    print(f"  {GREEN}✓ Deleted.{RESET}")


def cmd_open(args):
    projects = {p["name"]: p for p in list_projects()}
    p = projects.get(args.name)
    if not p:
        print(f"{RED}Project '{args.name}' not found.{RESET}")
        sys.exit(1)
    if not p["running"]:
        print(f"  Project is stopped. Starting first…")
        result = start_project(args.name)
        url = result["url"]
    else:
        url = p["url"]
    print(f"  {BLUE}Opening {url}{RESET}")
    webbrowser.open(url)


def main():
    parser = argparse.ArgumentParser(
        prog="turboui",
        description="TurboUIGen — AI-powered React app generator",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # generate
    p_gen = sub.add_parser("generate", aliases=["gen", "g"], help="Generate a new app from a prompt or Figma URL")
    p_gen.add_argument("prompt", nargs="?", default="", help="Natural-language description of the app")
    p_gen.add_argument("--figma", "-f", default="", help="Figma file URL — exports via REST API + generates app")
    p_gen.add_argument("--no-open", action="store_true", help="Don't open browser after generation")
    p_gen.set_defaults(func=cmd_generate)

    # list
    p_list = sub.add_parser("list", aliases=["ls"], help="List all generated projects")
    p_list.set_defaults(func=cmd_list)

    # start
    p_start = sub.add_parser("start", help="Start a project's dev server")
    p_start.add_argument("name", help="Project name (kebab-case)")
    p_start.add_argument("--no-open", action="store_true", help="Don't open browser")
    p_start.set_defaults(func=cmd_start)

    # stop
    p_stop = sub.add_parser("stop", help="Stop a project's dev server")
    p_stop.add_argument("name", help="Project name")
    p_stop.set_defaults(func=cmd_stop)

    # delete
    p_del = sub.add_parser("delete", aliases=["del", "rm"], help="Delete a project and its files")
    p_del.add_argument("name", help="Project name")
    p_del.set_defaults(func=cmd_delete)

    # open
    p_open = sub.add_parser("open", help="Open a project in the browser (starts it if stopped)")
    p_open.add_argument("name", help="Project name")
    p_open.set_defaults(func=cmd_open)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
