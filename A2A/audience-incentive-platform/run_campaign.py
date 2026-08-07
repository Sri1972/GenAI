"""
Campaign Runner — Triggers A2A incentive optimization between AutoAudience and IncentiveIQ.

Picks a random campaign case that hasn't been used this session.
Run this AFTER both agents are online (ports 8005 and 8006).

Usage:
    python run_campaign.py              # Random campaign (no repeats in session)
    python run_campaign.py 3            # Specific campaign by ID
    python run_campaign.py --all        # Run all 10 campaigns sequentially
    python run_campaign.py --list       # Show available campaigns
    python run_campaign.py --reset      # Clear session history and pick random
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

CAMPAIGNS = [
    {"id": 1, "title": "Conquest Campaign — Steal Truck Buyers", "segment_id": "truck_loyalists", "campaign_goal": "conquest", "dealer_region": "Southeast", "budget_constraint": "$3,500 per unit"},
    {"id": 2, "title": "EV Push — Convert Sedan Owners to Electric", "segment_id": "ev_curious_millennials", "campaign_goal": "volume", "dealer_region": "West Coast", "budget_constraint": "$4,000 per unit"},
    {"id": 3, "title": "First-Time Buyer Drive — Student Grad Special", "segment_id": "budget_first_time", "campaign_goal": "volume", "dealer_region": "Nationwide", "budget_constraint": "$2,000 per unit"},
    {"id": 4, "title": "Loyalty Reward — Keep Downsizers in the Family", "segment_id": "luxury_downsizers", "campaign_goal": "retention", "dealer_region": "Northeast", "budget_constraint": "$2,500 per unit"},
    {"id": 5, "title": "Lease Renewal Blitz — Prevent Brand Defection", "segment_id": "lease_churners", "campaign_goal": "retention", "dealer_region": "Tri-State", "budget_constraint": "$3,000 per unit"},
    {"id": 6, "title": "Holiday Truck Clearance — Year-End Volume Push", "segment_id": "truck_loyalists", "campaign_goal": "volume", "dealer_region": "Midwest", "budget_constraint": "$5,000 per unit"},
    {"id": 7, "title": "Green Fleet Incentive — Corporate EV Adoption", "segment_id": "ev_curious_millennials", "campaign_goal": "conquest", "dealer_region": "Pacific Northwest", "budget_constraint": "$4,500 per unit"},
    {"id": 8, "title": "Subprime Assist — Affordable Entry Point", "segment_id": "budget_first_time", "campaign_goal": "volume", "dealer_region": "Southwest", "budget_constraint": "$1,500 per unit"},
    {"id": 9, "title": "Premium Retention — Luxury-to-Midrange Bridge", "segment_id": "luxury_downsizers", "campaign_goal": "retention", "dealer_region": "Southeast", "budget_constraint": "$3,000 per unit"},
    {"id": 10, "title": "Lease-to-Own Conversion — Build Equity Campaign", "segment_id": "lease_churners", "campaign_goal": "retention", "dealer_region": "Nationwide", "budget_constraint": "$2,500 per unit"},
]

SESSION_FILE = Path(tempfile.gettempdir()) / "a2a_audience_session.json"


def load_session() -> list[int]:
    if SESSION_FILE.exists():
        try:
            return json.loads(SESSION_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return []
    return []


def save_session(used: list[int]):
    SESSION_FILE.write_text(json.dumps(used))


def reset_session():
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()
    console.print("[bold green]Session reset.[/bold green] All 10 campaigns available again.")


def pick_random_campaign() -> dict | None:
    used = load_session()
    available = [c for c in CAMPAIGNS if c["id"] not in used]

    if not available:
        console.print(
            "[bold yellow]All 10 campaigns have been run this session![/bold yellow]\n"
            "Run with --reset to start over."
        )
        return None

    campaign = random.choice(available)
    used.append(campaign["id"])
    save_session(used)
    return campaign


def show_campaign_list():
    used = load_session()
    table = Table(title="Campaign Cases", show_lines=True)
    table.add_column("ID", width=4)
    table.add_column("Title", width=40)
    table.add_column("Segment", width=22)
    table.add_column("Goal", width=10)
    table.add_column("Region", width=16)
    table.add_column("Budget", width=14)
    table.add_column("Status", width=10)

    for c in CAMPAIGNS:
        status = "[dim]done[/dim]" if c["id"] in used else "[green]available[/green]"
        table.add_row(
            str(c["id"]),
            c["title"],
            c["segment_id"].replace("_", " ").title(),
            c["campaign_goal"],
            c["dealer_region"],
            c["budget_constraint"],
            status,
        )

    console.print(table)
    console.print(f"\n[dim]{len(used)}/10 campaigns completed this session[/dim]")


def run_campaign(campaign: dict):
    console.print()
    console.print(
        Panel(
            "[bold]A2A Protocol Demo: Audience-Incentive Ecosystem[/bold]\n\n"
            "Two AI agents from separate organizations will now collaborate\n"
            "to find optimal incentive packages for a customer segment.\n\n"
            "[yellow]AutoAudience[/yellow] (Audience Intelligence) <-> [magenta]IncentiveIQ[/magenta] (Incentive Optimizer)\n\n"
            f"Campaign: [bold]{campaign['title']}[/bold]\n"
            f"Segment: {campaign['segment_id'].replace('_', ' ').title()}\n"
            f"Goal: [bold]{campaign['campaign_goal'].upper()}[/bold]\n"
            f"Region: {campaign['dealer_region']}\n"
            f"Budget: {campaign['budget_constraint']}",
            title="Campaign Incentive Optimization",
            border_style="yellow",
        )
    )
    console.print()

    # Step 1: Discover IncentiveIQ
    console.print("[bold]Step 1:[/bold] Discovering IncentiveIQ agent...", style="dim")
    try:
        with httpx.Client(timeout=10.0) as client:
            card_response = client.get("http://localhost:8006/a2a/agent-card")
            card_response.raise_for_status()
            agent_card = card_response.json()
            console.print(f"  Found: {agent_card['name']} @ {agent_card['organization']}")
            console.print(f"  Capabilities: {', '.join(agent_card['capabilities'])}")
    except httpx.ConnectError:
        console.print("[bold red]ERROR:[/bold red] IncentiveIQ agent not reachable at port 8006.")
        console.print("Start it first: cd incentiveiq/backend && python app.py")
        return
    except Exception as e:
        console.print(f"[bold red]ERROR:[/bold red] {e}")
        return

    console.print()

    # Step 2: Discover AutoAudience
    console.print("[bold]Step 2:[/bold] Discovering AutoAudience agent...", style="dim")
    try:
        with httpx.Client(timeout=10.0) as client:
            card_response = client.get("http://localhost:8005/a2a/agent-card")
            card_response.raise_for_status()
            agent_card = card_response.json()
            console.print(f"  Found: {agent_card['name']} @ {agent_card['organization']}")
            console.print(f"  Capabilities: {', '.join(agent_card['capabilities'])}")
    except httpx.ConnectError:
        console.print("[bold red]ERROR:[/bold red] AutoAudience agent not reachable at port 8005.")
        console.print("Start it first: cd autoaudience/backend && python app.py")
        return
    except Exception as e:
        console.print(f"[bold red]ERROR:[/bold red] {e}")
        return

    console.print()

    # Step 3: Run the campaign
    console.print(
        "[bold]Step 3:[/bold] Running campaign optimization (this may take 30-60 seconds)...",
        style="dim",
    )
    console.print()

    try:
        params = {
            "segment_id": campaign["segment_id"],
            "campaign_goal": campaign["campaign_goal"],
            "dealer_region": campaign["dealer_region"],
            "budget_constraint": campaign["budget_constraint"],
        }
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                "http://localhost:8005/audience/find-incentives",
                params=params,
            )
            response.raise_for_status()
            result = response.json()
    except httpx.ConnectError:
        console.print("[bold red]ERROR:[/bold red] AutoAudience agent not reachable.")
        return
    except httpx.ReadTimeout:
        console.print("[bold yellow]TIMEOUT:[/bold yellow] Campaign took too long. Check agent logs.")
        return
    except Exception as e:
        console.print(f"[bold red]ERROR:[/bold red] {e}")
        return

    if result.get("error"):
        console.print(f"[bold red]ERROR:[/bold red] {result['error']}")
        return

    # Show result summary
    console.print()
    console.print(
        Panel(
            f"[bold]Campaign:[/bold] {result.get('campaign_goal', 'N/A').upper()}\n"
            f"[bold]Segment:[/bold] {result.get('segment', 'N/A')}\n"
            f"[bold]Status:[/bold] {result.get('status', 'N/A')}\n"
            f"[bold]Rounds:[/bold] {result.get('rounds', 0)}",
            title="Campaign Result",
            border_style="yellow",
        )
    )

    # Show transcript
    console.print()
    table = Table(title="Conversation Transcript", show_lines=True)
    table.add_column("Agent", style="bold", width=14)
    table.add_column("Step", width=18)
    table.add_column("Message", width=70)

    for step in result.get("transcript", []):
        agent_name = step.get("agent", "Unknown")
        style = "yellow" if agent_name == "AutoAudience" else "magenta"
        msg = step.get("message", "")
        if len(msg) > 250:
            msg = msg[:250] + "..."
        table.add_row(f"[{style}]{agent_name}[/{style}]", step.get("step", ""), msg)

    console.print(table)

    # Show recommendation
    recommendation = result.get("recommendation")
    if recommendation:
        console.print()
        console.print(
            Panel(
                json.dumps(recommendation, indent=2),
                title="Final Recommendation",
                border_style="green",
            )
        )

    # Show explanation
    explanation = result.get("explanation")
    if explanation:
        console.print()
        console.print(
            Panel(
                explanation[:500] + ("..." if len(explanation) > 500 else ""),
                title="Recommendation Explanation",
                border_style="cyan",
            )
        )


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--reset":
            reset_session()
        elif arg == "--list":
            show_campaign_list()
        elif arg == "--all":
            for c in CAMPAIGNS:
                run_campaign(c)
                console.print("\n" + "=" * 80 + "\n")
        elif arg.isdigit():
            campaign_id = int(arg)
            campaign = next((c for c in CAMPAIGNS if c["id"] == campaign_id), None)
            if campaign:
                run_campaign(campaign)
            else:
                console.print(f"[bold red]Unknown campaign ID:[/bold red] {campaign_id}")
                console.print(f"Valid IDs: 1-{len(CAMPAIGNS)}")
        else:
            console.print(f"[bold red]Unknown argument:[/bold red] {arg}")
            console.print("Usage: python run_campaign.py [ID | --all | --list | --reset]")
    else:
        campaign = pick_random_campaign()
        if campaign:
            run_campaign(campaign)
