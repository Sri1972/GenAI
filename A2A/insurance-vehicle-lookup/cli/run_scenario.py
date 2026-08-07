"""
Scenario Runner — Triggers insurance workflows between SecureAuto and AutoRegistry.

Usage:
    python run_scenario.py              # Random scenario (no repeats in session)
    python run_scenario.py --list       # See available scenarios
    python run_scenario.py --reset      # Clear session history
    python run_scenario.py --all        # Run all 10 scenarios
    python run_scenario.py 3            # Run scenario #3 specifically
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

SCENARIOS = [
    {
        "id": 1,
        "title": "New Quote — Clean Record Honda Owner",
        "workflow_type": "new_quote",
        "lookup_by": "vin",
        "lookup_value": "1HGCM82633A004352",
        "customer_context": "Customer wants a new full coverage policy. Has been with another insurer for 5 years, shopping for better rates.",
        "expected_outcome": "approve_favorable",
    },
    {
        "id": 2,
        "title": "New Quote — High-Risk Driver (DUI History)",
        "workflow_type": "new_quote",
        "lookup_by": "name",
        "lookup_value": "David Kowalski",
        "customer_context": "Walk-in customer requesting minimum liability coverage. Says previous insurer dropped them.",
        "expected_outcome": "decline_or_high_premium",
    },
    {
        "id": 3,
        "title": "Claim — Tesla Fender Bender",
        "workflow_type": "claim",
        "lookup_by": "plate",
        "lookup_value": "TX-MKP4492",
        "customer_context": "Customer reports minor rear-end collision in parking lot. Damage to rear bumper and trunk. No injuries. Other party at fault.",
        "expected_outcome": "approve_claim",
    },
    {
        "id": 4,
        "title": "Policy Renewal — Ford F-150 with Violations",
        "workflow_type": "renewal",
        "lookup_by": "vin",
        "lookup_value": "1FTFW1ET5DFC10987",
        "customer_context": "Annual renewal. Customer had 2 speeding tickets and a minor at-fault accident since last renewal. Wants to keep same coverage.",
        "expected_outcome": "approve_with_increase",
    },
    {
        "id": 5,
        "title": "New Quote — BMW Lease (Plate Lookup)",
        "workflow_type": "new_quote",
        "lookup_by": "plate",
        "lookup_value": "NY-HGT5567",
        "customer_context": "Leasing company requires full coverage with $500 deductible. Customer is a young professional in NYC.",
        "expected_outcome": "approve_standard",
    },
    {
        "id": 6,
        "title": "Claim — Salvage Title Vehicle Theft",
        "workflow_type": "claim",
        "lookup_by": "name",
        "lookup_value": "David Kowalski",
        "customer_context": "Customer reports vehicle stolen from street parking overnight. No witnesses. Vehicle has rebuilt title.",
        "expected_outcome": "investigate_fraud_risk",
    },
    {
        "id": 7,
        "title": "Policy Renewal — Loyal Honda Customer",
        "workflow_type": "renewal",
        "lookup_by": "name",
        "lookup_value": "Sarah Chen",
        "customer_context": "3-year customer requesting renewal. No claims filed, perfect payment history. Asking about loyalty discount.",
        "expected_outcome": "approve_with_discount",
    },
    {
        "id": 8,
        "title": "New Quote — Tesla Lease Buyout",
        "workflow_type": "new_quote",
        "lookup_by": "vin",
        "lookup_value": "5YJSA1E26MF123456",
        "customer_context": "Customer buying out lease and needs new personal policy. Previously covered under fleet insurance. Has one prior accident.",
        "expected_outcome": "approve_moderate",
    },
    {
        "id": 9,
        "title": "Claim — F-150 Hail Damage (Comprehensive)",
        "workflow_type": "claim",
        "lookup_by": "plate",
        "lookup_value": "FL-JHTK88",
        "customer_context": "Customer reports extensive hail damage during Florida storm. Hood, roof, and all panels affected. Requesting comprehensive claim for repair estimate of $8,500.",
        "expected_outcome": "approve_comprehensive",
    },
    {
        "id": 10,
        "title": "New Quote — High Mileage Corolla (Address Lookup)",
        "workflow_type": "new_quote",
        "lookup_by": "name",
        "lookup_value": "David Kowalski",
        "customer_context": "Customer shopping for cheapest possible insurance. Only wants state minimum. Vehicle has 89k miles and rebuilt title. Previous policy was non-renewed.",
        "expected_outcome": "decline_high_risk",
    },
]

SESSION_FILE = Path(tempfile.gettempdir()) / "a2a_insurance_session.json"


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
    console.print("[bold green]Session reset.[/bold green] All 10 scenarios available again.")


def pick_random_scenario() -> dict | None:
    used = load_session()
    available = [s for s in SCENARIOS if s["id"] not in used]

    if not available:
        console.print(
            "[bold yellow]All 10 scenarios have been run this session![/bold yellow]\n"
            "Run with --reset to start over."
        )
        return None

    scenario = random.choice(available)
    used.append(scenario["id"])
    save_session(used)
    return scenario


def show_scenario_list():
    used = load_session()
    table = Table(title="Insurance Scenarios", show_lines=True)
    table.add_column("#", width=3)
    table.add_column("Title", width=40)
    table.add_column("Workflow", width=12)
    table.add_column("Lookup", width=10)
    table.add_column("Status", width=10)

    for s in SCENARIOS:
        status = "[dim]done[/dim]" if s["id"] in used else "[green]available[/green]"
        table.add_row(str(s["id"]), s["title"], s["workflow_type"], s["lookup_by"], status)

    console.print(table)
    console.print(f"\n[dim]{len(used)}/10 scenarios completed this session[/dim]")


def run_scenario(scenario: dict):
    console.print()
    console.print(
        Panel(
            "[bold]A2A Protocol Demo: Insurance ↔ Vehicle Data Provider[/bold]\n\n"
            f"[blue]SecureAuto Insurance[/blue] ← → [green]AutoRegistry Data Services[/green]\n\n"
            f"Scenario: [bold]{scenario['title']}[/bold]\n"
            f"Workflow: {scenario['workflow_type']}\n"
            f"Lookup: {scenario['lookup_by']} = {scenario['lookup_value']}\n\n"
            f"[dim]{scenario['customer_context']}[/dim]",
            title="Agent-to-Agent Insurance Workflow",
            border_style="magenta",
        )
    )
    console.print()

    console.print("[bold]Step 1:[/bold] Discovering AutoRegistry agent...", style="dim")
    try:
        with httpx.Client(timeout=10.0) as client:
            card = client.get("http://localhost:8004/a2a/agent-card").json()
            console.print(f"  ✓ Found: {card['name']} @ {card['organization']}")
            console.print(f"  ✓ Capabilities: {', '.join(card['capabilities'])}")
    except httpx.ConnectError:
        console.print("[bold red]ERROR:[/bold red] AutoRegistry agent not reachable at port 8004.")
        console.print("Start it first: python autoregistry_agent.py")
        return
    except Exception as e:
        console.print(f"[bold red]ERROR:[/bold red] {e}")
        return

    console.print()
    console.print("[bold]Step 2:[/bold] Discovering SecureAuto agent...", style="dim")
    try:
        with httpx.Client(timeout=10.0) as client:
            card = client.get("http://localhost:8003/a2a/agent-card").json()
            console.print(f"  ✓ Found: {card['name']} @ {card['organization']}")
            console.print(f"  ✓ Capabilities: {', '.join(card['capabilities'])}")
    except httpx.ConnectError:
        console.print("[bold red]ERROR:[/bold red] SecureAuto agent not reachable at port 8003.")
        console.print("Start it first: python secureauto_agent.py")
        return
    except Exception as e:
        console.print(f"[bold red]ERROR:[/bold red] {e}")
        return

    console.print()
    console.print(
        "[bold]Step 3:[/bold] Processing insurance request (this may take 30-60 seconds)...",
        style="dim",
    )
    console.print()

    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                "http://localhost:8003/insurance/process-request",
                params={
                    "workflow_type": scenario["workflow_type"],
                    "lookup_by": scenario["lookup_by"],
                    "lookup_value": scenario["lookup_value"],
                    "customer_context": scenario["customer_context"],
                },
            )
            response.raise_for_status()
            result = response.json()
    except httpx.ConnectError:
        console.print("[bold red]ERROR:[/bold red] SecureAuto agent not reachable.")
        return
    except httpx.ReadTimeout:
        console.print("[bold yellow]TIMEOUT:[/bold yellow] Processing took too long. Check agent logs.")
        return
    except Exception as e:
        console.print(f"[bold red]ERROR:[/bold red] {e}")
        return

    # Display conversation transcript as a table
    console.print()
    table = Table(title=f"Agent Conversation ({result.get('rounds', '?')} rounds)", show_lines=True)
    table.add_column("Agent", style="bold", width=14)
    table.add_column("Step", width=18)
    table.add_column("Message", width=80)

    for step in result.get("transcript", []):
        agent = step.get("agent", "System")
        step_type = step.get("step", "")
        message = step.get("message", "")

        agent_style = "blue" if agent == "SecureAuto" else "green"
        table.add_row(
            f"[{agent_style}]{agent}[/{agent_style}]",
            step_type.replace("_", " "),
            message[:300] if len(message) > 300 else message,
        )

    console.print(table)

    # Final decision
    console.print()
    decision = result.get("underwriting_decision", {})
    console.print(
        Panel(
            f"[bold]Decision:[/bold] {json.dumps(decision, indent=2)}\n\n"
            f"[bold]Explanation:[/bold]\n{result.get('explanation', 'N/A')}",
            title="Final Underwriting Decision",
            border_style="magenta",
        )
    )


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--reset":
            reset_session()
        elif arg == "--list":
            show_scenario_list()
        elif arg == "--all":
            for s in SCENARIOS:
                run_scenario(s)
                console.print("\n" + "=" * 80 + "\n")
        elif arg.isdigit():
            idx = int(arg)
            scenario = next((s for s in SCENARIOS if s["id"] == idx), None)
            if scenario:
                run_scenario(scenario)
            else:
                console.print(f"[bold red]Scenario #{idx} not found.[/bold red] Use 1-10.")
        else:
            console.print(f"[bold red]Unknown argument:[/bold red] {arg}")
            console.print("Usage: python run_scenario.py [1-10 | --all | --list | --reset]")
    else:
        scenario = pick_random_scenario()
        if scenario:
            run_scenario(scenario)
