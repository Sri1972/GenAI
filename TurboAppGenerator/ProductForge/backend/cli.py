"""
Product Forge CLI — Run multi-agent product development from the command line.

Usage:
    python cli.py "Build a real-time collaborative whiteboard for remote teams"
    python cli.py --stage ideation "My product idea"
    python cli.py --interactive "My product idea"
"""

import argparse
import sys
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.live import Live
from rich.table import Table

from orchestrator import ForgeSession

console = Console()


def print_message(entry: dict):
    """Print a conversation message to the terminal."""
    if entry["type"] == "stage_start":
        console.print()
        console.print(Panel(
            f"[bold]{entry['stage_name']}[/bold]\n{entry['description']}\n\n"
            f"Participants: {', '.join(entry['participants'])}",
            title=f"Stage: {entry['stage_name']}",
            border_style="cyan",
        ))
    elif entry["type"] == "round_start":
        console.print(f"\n  [dim]--- Round {entry['round']} ---[/dim]\n")
    elif entry["type"] == "message":
        color = entry.get("agent_color", "white").lstrip("#")
        name = entry["agent_name"]
        short = entry["agent_short"]
        content = entry["content"]
        if len(content) > 2000:
            display = content[:2000] + "\n\n[dim]... (truncated in CLI, full content in artifact)[/dim]"
        else:
            display = content
        console.print(Panel(
            Markdown(display),
            title=f"[bold][#{color}]{short}[/#{color}][/bold] {name}",
            border_style=f"#{color}",
            padding=(0, 1),
        ))
    elif entry["type"] == "artifact_created":
        console.print(Panel(
            f"[green]Saved:[/green] {entry['path']}",
            title=f"Artifact: {entry['artifact_name']}",
            border_style="green",
        ))
    elif entry["type"] == "stage_complete":
        console.print(f"\n  [green]Stage '{entry['stage_name']}' complete.[/green]\n")
    elif entry["type"] == "forge_complete":
        console.print(Panel(
            f"[bold green]All stages complete![/bold green]\n\n"
            f"Artifacts produced:\n" +
            "\n".join(f"  - {a}" for a in entry["artifacts"]) +
            f"\n\nOutput directory: {entry['output_dir']}",
            title="Forge Complete",
            border_style="green",
        ))


def run_interactive(session: ForgeSession):
    """Run in interactive mode — pause between stages."""
    session.on_message = print_message
    console.print(Panel(
        f"[bold]Product Idea:[/bold] {session.product_idea}\n"
        f"[bold]Session ID:[/bold] {session.session_id}\n"
        f"[bold]Stages:[/bold] {len(session.stages)}",
        title="Product Forge — Interactive Mode",
        border_style="magenta",
    ))

    for i in range(len(session.stages)):
        stage = session.stages[i]
        console.print(f"\n[bold cyan]Next: {stage['name']}[/bold cyan] — {stage['description']}")
        response = input("  Press Enter to continue, 's' to skip, 'q' to quit: ").strip().lower()
        if response == 'q':
            console.print("[yellow]Forge paused. Artifacts saved so far.[/yellow]")
            break
        if response == 's':
            console.print(f"  [dim]Skipping {stage['name']}[/dim]")
            session.current_stage_idx += 1
            continue
        session.run_stage(i)


def run_full(session: ForgeSession):
    """Run all stages without stopping."""
    session.on_message = print_message
    console.print(Panel(
        f"[bold]Product Idea:[/bold] {session.product_idea}\n"
        f"[bold]Session ID:[/bold] {session.session_id}\n"
        f"[bold]Stages:[/bold] {len(session.stages)}\n\n"
        f"[dim]Running all stages automatically...[/dim]",
        title="Product Forge",
        border_style="magenta",
    ))
    session.run_all()


def main():
    parser = argparse.ArgumentParser(description="Product Forge — Multi-Agent Product Builder")
    parser.add_argument("idea", help="The product idea to build")
    parser.add_argument("--interactive", "-i", action="store_true", help="Pause between stages")
    parser.add_argument("--stage", "-s", help="Run only a specific stage (by id)")
    parser.add_argument("--session-id", help="Custom session ID")
    args = parser.parse_args()

    session = ForgeSession(args.idea, session_id=args.session_id)

    if args.stage:
        stage_ids = [s["id"] for s in session.stages]
        if args.stage not in stage_ids:
            console.print(f"[red]Unknown stage: {args.stage}. Available: {', '.join(stage_ids)}[/red]")
            sys.exit(1)
        session.on_message = print_message
        session.run_stage(stage_ids.index(args.stage))
    elif args.interactive:
        run_interactive(session)
    else:
        run_full(session)


if __name__ == "__main__":
    main()
