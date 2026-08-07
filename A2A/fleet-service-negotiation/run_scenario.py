"""
Scenario Runner — Triggers A2A negotiations between SmartFleet and AutoServ.

Picks a random vehicle from the fleet that hasn't been used this session.
Run this AFTER both agents are online (ports 8001 and 8002).

Usage:
    python run_scenario.py              # Random vehicle (no repeats in session)
    python run_scenario.py VH-017       # Specific vehicle
    python run_scenario.py --all        # Run all 10 scenarios sequentially
    python run_scenario.py --reset      # Clear session history and pick random
"""

import json
import random
import sys
import tempfile
from pathlib import Path

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

ALL_VEHICLES = [
    "VH-017", "VH-023", "VH-008", "VH-031", "VH-042",
    "VH-005", "VH-019", "VH-036", "VH-011", "VH-028",
]

VEHICLE_INFO = {
    "VH-017": ("Delivery Van", "Brake service", "high"),
    "VH-023": ("Cargo Truck", "Transmission service", "medium"),
    "VH-008": ("Delivery Van", "Oil change", "low"),
    "VH-031": ("Refrigerated Truck", "Engine diagnostic — misfire", "critical"),
    "VH-042": ("Cargo Truck", "Brake service — ABS", "high"),
    "VH-005": ("Sprinter Van", "Tire rotation & balance", "low"),
    "VH-019": ("Box Truck", "Transmission — hard shifting", "medium"),
    "VH-036": ("Delivery Van", "Engine diagnostic — turbo/EGR", "high"),
    "VH-011": ("Heavy Duty Truck", "Brake service — DOT failed", "critical"),
    "VH-028": ("Sprinter Van", "Oil change — low pressure", "medium"),
}

SESSION_FILE = Path(tempfile.gettempdir()) / "a2a_fleet_session.json"


def load_session() -> list[str]:
    """Load list of vehicles already used in this session."""
    if SESSION_FILE.exists():
        try:
            return json.loads(SESSION_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return []
    return []


def save_session(used: list[str]):
    SESSION_FILE.write_text(json.dumps(used))


def reset_session():
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()
    console.print("[bold green]Session reset.[/bold green] All 10 vehicles available again.")


def pick_random_vehicle() -> str | None:
    """Pick a random vehicle that hasn't been used this session."""
    used = load_session()
    available = [v for v in ALL_VEHICLES if v not in used]

    if not available:
        console.print(
            "[bold yellow]All 10 scenarios have been run this session![/bold yellow]\n"
            "Run with --reset to start over."
        )
        return None

    vehicle = random.choice(available)
    used.append(vehicle)
    save_session(used)
    return vehicle


def show_vehicle_list():
    """Show all vehicles and their session status."""
    used = load_session()
    table = Table(title="Fleet Scenarios", show_lines=True)
    table.add_column("Vehicle", width=8)
    table.add_column("Type", width=18)
    table.add_column("Issue", width=30)
    table.add_column("Priority", width=10)
    table.add_column("Status", width=10)

    for vid in ALL_VEHICLES:
        vtype, issue, priority = VEHICLE_INFO[vid]
        status = "[dim]done[/dim]" if vid in used else "[green]available[/green]"
        table.add_row(vid, vtype, issue, priority, status)

    console.print(table)
    console.print(f"\n[dim]{len(used)}/10 scenarios completed this session[/dim]")


def run_scenario(vehicle_id: str):
    vtype, issue, priority = VEHICLE_INFO.get(vehicle_id, ("Unknown", "Unknown", "unknown"))

    console.print()
    console.print(
        Panel(
            "[bold]A2A Protocol Demo: Automotive Ecosystem[/bold]\n\n"
            "Two AI agents from separate organizations will now negotiate\n"
            "vehicle maintenance scheduling in real-time.\n\n"
            "[blue]SmartFleet Agent[/blue] (Fleet Manager) ← → [green]AutoServ Agent[/green] (Service Provider)\n\n"
            f"Vehicle: [bold]{vehicle_id}[/bold] ({vtype})\n"
            f"Issue: {issue}\n"
            f"Priority: [bold]{priority.upper()}[/bold]",
            title="Agent-to-Agent Negotiation",
            border_style="magenta",
        )
    )
    console.print()

    console.print("[bold]Step 1:[/bold] Discovering AutoServ agent...", style="dim")
    try:
        with httpx.Client(timeout=10.0) as client:
            card_response = client.get("http://localhost:8002/a2a/agent-card")
            card_response.raise_for_status()
            agent_card = card_response.json()
            console.print(f"  ✓ Found: {agent_card['name']} @ {agent_card['organization']}")
            console.print(f"  ✓ Capabilities: {', '.join(agent_card['capabilities'])}")
    except httpx.ConnectError:
        console.print("[bold red]ERROR:[/bold red] AutoServ agent not reachable at port 8002.")
        console.print("Start it first: python autoserv_agent.py")
        return
    except Exception as e:
        console.print(f"[bold red]ERROR:[/bold red] {e}")
        return

    console.print()
    console.print("[bold]Step 2:[/bold] Discovering SmartFleet agent...", style="dim")
    try:
        with httpx.Client(timeout=10.0) as client:
            card_response = client.get("http://localhost:8001/a2a/agent-card")
            card_response.raise_for_status()
            agent_card = card_response.json()
            console.print(f"  ✓ Found: {agent_card['name']} @ {agent_card['organization']}")
            console.print(f"  ✓ Capabilities: {', '.join(agent_card['capabilities'])}")
    except httpx.ConnectError:
        console.print("[bold red]ERROR:[/bold red] SmartFleet agent not reachable at port 8001.")
        console.print("Start it first: python smartfleet_agent.py")
        return
    except Exception as e:
        console.print(f"[bold red]ERROR:[/bold red] {e}")
        return

    console.print()
    console.print(
        "[bold]Step 3:[/bold] Initiating negotiation (this may take 30-60 seconds)...",
        style="dim",
    )
    console.print()

    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"http://localhost:8001/fleet/initiate-negotiation?vehicle_id={vehicle_id}"
            )
            response.raise_for_status()
            result = response.json()
    except httpx.ConnectError:
        console.print("[bold red]ERROR:[/bold red] SmartFleet agent not reachable.")
        return
    except httpx.ReadTimeout:
        console.print("[bold yellow]TIMEOUT:[/bold yellow] Negotiation took too long. Check agent logs.")
        return
    except Exception as e:
        console.print(f"[bold red]ERROR:[/bold red] {e}")
        return

    console.print()
    console.print(
        Panel(
            f"[bold]Outcome:[/bold] {result['status'].upper()}\n"
            f"[bold]Rounds:[/bold] {result['rounds']}\n"
            f"[bold]Messages exchanged:[/bold] {result['total_messages']}",
            title="Negotiation Result",
            border_style="magenta",
        )
    )

    console.print()
    table = Table(title="Conversation Transcript", show_lines=True)
    table.add_column("Agent", style="bold", width=12)
    table.add_column("Type", width=16)
    table.add_column("Message", width=70)

    for msg in result.get("transcript", []):
        agent_name = "SmartFleet" if "smartfleet" in msg["sender"] else "AutoServ"
        style = "blue" if agent_name == "SmartFleet" else "green"
        body = msg["body"][:200] + "..." if len(msg["body"]) > 200 else msg["body"]
        table.add_row(f"[{style}]{agent_name}[/{style}]", msg["type"], body)

    console.print(table)

    if result.get("transcript"):
        final_msg = result["transcript"][-1]
        if final_msg.get("terms"):
            console.print()
            console.print(
                Panel(
                    f"```json\n{json.dumps(final_msg['terms'], indent=2)}\n```",
                    title="Final Agreed Terms",
                    border_style="green",
                )
            )


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--reset":
            reset_session()
        elif arg == "--list":
            show_vehicle_list()
        elif arg == "--all":
            for vid in ALL_VEHICLES:
                run_scenario(vid)
                console.print("\n" + "=" * 80 + "\n")
        elif arg.startswith("VH-"):
            run_scenario(arg)
        else:
            console.print(f"[bold red]Unknown argument:[/bold red] {arg}")
            console.print("Usage: python run_scenario.py [VH-xxx | --all | --list | --reset]")
    else:
        vehicle = pick_random_vehicle()
        if vehicle:
            run_scenario(vehicle)
