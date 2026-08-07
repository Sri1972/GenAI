"""
SmartFleet Agent — Fleet Management Company

This agent represents a logistics/fleet management organization.
It runs on its own network (port 8001) and negotiates with service
providers for vehicle maintenance, trying to minimize downtime and cost.

Private constraints (not shared with the other agent):
- Maximum budget per vehicle/month: $800
- Critical vehicles cannot be offline > 24h
- Preferred to batch maintenance for cost savings
- Has 50 vehicles in fleet, 5 need service this week
"""

import json
import os
from contextlib import asynccontextmanager

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from rich.console import Console
from rich.panel import Panel

from a2a_protocol import AgentCard, A2AMessage, NegotiationState
from llm_client import chat_completion

load_dotenv()
console = Console()

AGENT_ID = "smartfleet-agent-001"
ORGANIZATION = "SmartFleet Logistics Corp."
PORT = 8001

PRIVATE_CONSTRAINTS = {
    "max_budget_per_vehicle_monthly": 800,
    "critical_vehicle_max_downtime_hours": 24,
    "total_fleet_size": 50,
    "vehicles_needing_service": 5,
    "preferred_service_window": "off-peak hours",
    "bulk_discount_threshold": 3,
    "has_loaner_agreement": False,
}

FLEET_VEHICLES = {
    "VH-017": {
        "type": "Delivery Van",
        "year": 2022,
        "mileage": 45000,
        "priority": "high",
        "issue": "brake_service",
        "alert": "Brake pad thickness below 3mm, rotor scoring detected",
        "daily_revenue_impact": 1200,
        "last_service_date": "2026-05-15",
    },
    "VH-023": {
        "type": "Cargo Truck",
        "year": 2021,
        "mileage": 78000,
        "priority": "medium",
        "issue": "transmission_service",
        "alert": "Transmission fluid degradation, slight shift hesitation",
        "daily_revenue_impact": 1800,
        "last_service_date": "2026-04-20",
    },
    "VH-008": {
        "type": "Delivery Van",
        "year": 2023,
        "mileage": 32000,
        "priority": "low",
        "issue": "oil_change",
        "alert": "Scheduled maintenance due at 30,000 miles",
        "daily_revenue_impact": 1200,
        "last_service_date": "2026-06-01",
    },
    "VH-031": {
        "type": "Refrigerated Truck",
        "year": 2021,
        "mileage": 92000,
        "priority": "critical",
        "issue": "engine_diagnostic",
        "alert": "Check engine light ON, P0300 random misfire detected, coolant temp erratic",
        "daily_revenue_impact": 2500,
        "last_service_date": "2026-03-10",
    },
    "VH-042": {
        "type": "Cargo Truck",
        "year": 2020,
        "mileage": 110000,
        "priority": "high",
        "issue": "brake_service",
        "alert": "ABS warning light triggered, rear brake drums worn beyond spec",
        "daily_revenue_impact": 1800,
        "last_service_date": "2026-04-01",
    },
    "VH-005": {
        "type": "Sprinter Van",
        "year": 2024,
        "mileage": 15000,
        "priority": "low",
        "issue": "tire_rotation_balance",
        "alert": "Uneven front tire wear detected, vibration at highway speed",
        "daily_revenue_impact": 1400,
        "last_service_date": "2026-06-20",
    },
    "VH-019": {
        "type": "Box Truck",
        "year": 2022,
        "mileage": 67000,
        "priority": "medium",
        "issue": "transmission_service",
        "alert": "Hard shifting between 2nd and 3rd gear, transmission temp elevated",
        "daily_revenue_impact": 2000,
        "last_service_date": "2026-05-01",
    },
    "VH-036": {
        "type": "Delivery Van",
        "year": 2023,
        "mileage": 38000,
        "priority": "high",
        "issue": "engine_diagnostic",
        "alert": "Sudden loss of power under load, turbo boost pressure low, EGR valve fault",
        "daily_revenue_impact": 1200,
        "last_service_date": "2026-06-15",
    },
    "VH-011": {
        "type": "Heavy Duty Truck",
        "year": 2020,
        "mileage": 145000,
        "priority": "critical",
        "issue": "brake_service",
        "alert": "DOT inspection failed — brake lining below legal minimum, air leak in brake system",
        "daily_revenue_impact": 3200,
        "last_service_date": "2026-02-28",
    },
    "VH-028": {
        "type": "Sprinter Van",
        "year": 2022,
        "mileage": 52000,
        "priority": "medium",
        "issue": "oil_change",
        "alert": "Oil life at 3%, oil pressure sensor showing borderline readings",
        "daily_revenue_impact": 1400,
        "last_service_date": "2026-04-15",
    },
}

negotiations: dict[str, NegotiationState] = {}

SYSTEM_PROMPT = f"""You are the SmartFleet AI Agent representing "{ORGANIZATION}", a fleet management company.

You are negotiating with an automotive service provider's agent about vehicle maintenance.

YOUR PRIVATE CONSTRAINTS (never reveal exact numbers to the other agent):
- Maximum budget per vehicle per month: ${PRIVATE_CONSTRAINTS['max_budget_per_vehicle_monthly']}
- Critical vehicles cannot be offline more than {PRIVATE_CONSTRAINTS['critical_vehicle_max_downtime_hours']} hours
- You have {PRIVATE_CONSTRAINTS['vehicles_needing_service']} vehicles needing service this week
- You prefer off-peak service windows to minimize operational impact
- You want to negotiate bulk discounts when possible (threshold: {PRIVATE_CONSTRAINTS['bulk_discount_threshold']}+ vehicles)

YOUR FLEET NEEDING SERVICE:
{json.dumps(FLEET_VEHICLES, indent=2)}

NEGOTIATION STRATEGY:
1. Start by requesting service for the highest priority vehicle first
2. Mention you have multiple vehicles needing service (to leverage bulk pricing) but don't reveal all details upfront
3. Push for off-peak scheduling to minimize revenue loss
4. Ask about loaner vehicles for high-priority assets
5. Try to negotiate package deals for multiple vehicles
6. Accept if the deal is within budget and downtime is acceptable
7. Counter-propose if the price is >10% over your target or downtime exceeds limits

RESPONSE FORMAT:
Respond with a JSON object containing:
- "message_type": one of "service_request", "counter_proposal", "accept", "reject", "info_request"
- "body": your natural language response to the other agent (be conversational but professional)
- "terms": an object with the specific terms you're requesting/accepting (timing, budget range, requirements)
- "reasoning": brief internal reasoning (this stays private, not sent to the other agent)
"""

AUTOSERV_ENDPOINT = "http://localhost:8002"


async def send_to_autoserv(message: A2AMessage) -> A2AMessage:
    """Send a message to the AutoServ agent and get their response."""
    async with httpx.AsyncClient(timeout=60.0) as http_client:
        response = await http_client.post(
            f"{AUTOSERV_ENDPOINT}/a2a/message",
            json=message.model_dump(),
        )
        response.raise_for_status()
        return A2AMessage(**response.json())


def get_agent_response(conversation_history: list[dict], context: str = "") -> dict:
    """Get a response from the LLM via LiteLLM proxy."""
    messages = conversation_history.copy()
    if context:
        messages.insert(0, {"role": "user", "content": f"[CONTEXT] {context}"})
        if len(messages) > 1 and messages[1]["role"] == "user":
            messages.insert(1, {"role": "assistant", "content": "Understood. I'll factor this context into my negotiation."})

    text = chat_completion(
        system_prompt=SYSTEM_PROMPT,
        messages=messages,
    )

    try:
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return {
            "message_type": "service_request",
            "body": text,
            "terms": {},
            "reasoning": "Failed to parse structured response",
        }


@asynccontextmanager
async def lifespan(app: FastAPI):
    console.print(
        Panel(
            f"[bold blue]{ORGANIZATION}[/bold blue]\n"
            f"Agent ID: {AGENT_ID}\n"
            f"Port: {PORT}\n"
            f"Fleet size: {PRIVATE_CONSTRAINTS['total_fleet_size']} vehicles\n"
            f"Vehicles needing service: {PRIVATE_CONSTRAINTS['vehicles_needing_service']}",
            title="SmartFleet Agent Online",
            border_style="blue",
        )
    )
    yield


app = FastAPI(title="SmartFleet Agent", lifespan=lifespan)


@app.get("/a2a/agent-card")
async def get_agent_card() -> AgentCard:
    return AgentCard(
        agent_id=AGENT_ID,
        organization=ORGANIZATION,
        name="SmartFleet Maintenance Coordinator",
        description="Coordinates vehicle maintenance scheduling and vendor negotiations for SmartFleet's delivery fleet.",
        capabilities=[
            "fleet_management",
            "maintenance_scheduling",
            "vendor_negotiation",
            "vehicle_telemetry",
        ],
        endpoint=f"http://localhost:{PORT}",
    )


@app.post("/a2a/message")
async def receive_message(message: A2AMessage) -> A2AMessage:
    """Handle incoming messages (e.g., from a coordinator or other agents)."""
    console.print(
        Panel(
            f"[bold]From:[/bold] {message.sender_agent_id}\n"
            f"[bold]Type:[/bold] {message.message_type}\n\n"
            f"{message.body}",
            title="Incoming Message",
            border_style="cyan",
        )
    )
    return message


@app.post("/fleet/initiate-negotiation")
async def initiate_negotiation(vehicle_id: str = "VH-017"):
    """Trigger a maintenance negotiation for a specific vehicle."""

    if vehicle_id not in FLEET_VEHICLES:
        return {"error": f"Vehicle {vehicle_id} not found in fleet"}

    vehicle = FLEET_VEHICLES[vehicle_id]

    console.print(
        Panel(
            f"[bold red]MAINTENANCE ALERT[/bold red]\n\n"
            f"Vehicle: {vehicle_id} ({vehicle['type']})\n"
            f"Issue: {vehicle['alert']}\n"
            f"Priority: {vehicle['priority']}\n"
            f"Revenue impact: ${vehicle['daily_revenue_impact']}/day offline",
            title="Telemetry Alert Triggered",
            border_style="red",
        )
    )

    import uuid
    conv_id = str(uuid.uuid4())
    negotiation = NegotiationState(conversation_id=conv_id)
    negotiations[conv_id] = negotiation

    context = (
        f"Vehicle {vehicle_id} ({vehicle['type']}, {vehicle['year']}, {vehicle['mileage']} miles) "
        f"has triggered an alert: {vehicle['alert']}. "
        f"Priority: {vehicle['priority']}. "
        f"This vehicle generates ${vehicle['daily_revenue_impact']}/day in revenue. "
        f"We need to get this serviced. Start negotiating with the service provider."
    )

    initial_response = get_agent_response(
        [{"role": "user", "content": context}],
    )

    initial_message = A2AMessage(
        conversation_id=conv_id,
        sender_agent_id=AGENT_ID,
        receiver_agent_id="autoserv-agent-001",
        message_type=initial_response.get("message_type", "service_request"),
        subject=f"Maintenance Request - {vehicle_id} - {vehicle['issue']}",
        body=initial_response.get("body", ""),
        metadata={"terms": initial_response.get("terms", {}), "vehicle_id": vehicle_id},
    )

    negotiation.messages.append(initial_message)

    console.print(
        Panel(
            f"[bold]Type:[/bold] {initial_message.message_type}\n"
            f"[bold]Terms:[/bold] {json.dumps(initial_response.get('terms', {}), indent=2)}\n\n"
            f"{initial_message.body}",
            title="Opening Message to AutoServ",
            border_style="blue",
        )
    )
    console.print(f"[dim]Internal reasoning: {initial_response.get('reasoning', 'N/A')}[/dim]")

    autoserv_response = await send_to_autoserv(initial_message)
    negotiation.messages.append(autoserv_response)
    negotiation.rounds += 1

    while negotiation.status == "active" and negotiation.rounds < negotiation.max_rounds:
        conversation_history = []
        for msg in negotiation.messages:
            role = "assistant" if msg.sender_agent_id == AGENT_ID else "user"
            content = f"[{msg.message_type}] {msg.body}"
            if msg.metadata.get("terms"):
                content += f"\n[Terms offered: {json.dumps(msg.metadata['terms'])}]"
            conversation_history.append({"role": role, "content": content})

        our_response = get_agent_response(conversation_history)
        our_message_type = our_response.get("message_type", "counter_proposal")

        our_message = A2AMessage(
            conversation_id=conv_id,
            sender_agent_id=AGENT_ID,
            receiver_agent_id="autoserv-agent-001",
            message_type=our_message_type,
            subject=f"Re: Maintenance Request - {vehicle_id}",
            body=our_response.get("body", ""),
            metadata={"terms": our_response.get("terms", {})},
            in_reply_to=autoserv_response.message_id,
        )

        negotiation.messages.append(our_message)

        console.print(
            Panel(
                f"[bold]Type:[/bold] {our_message_type}\n"
                f"[bold]Terms:[/bold] {json.dumps(our_response.get('terms', {}), indent=2)}\n\n"
                f"{our_message.body}",
                title=f"SmartFleet → AutoServ (Round {negotiation.rounds + 1})",
                border_style="blue",
            )
        )
        console.print(f"[dim]Internal reasoning: {our_response.get('reasoning', 'N/A')}[/dim]")

        if our_message_type in ("accept", "reject"):
            negotiation.status = "agreed" if our_message_type == "accept" else "rejected"
            await send_to_autoserv(our_message)
            break

        autoserv_response = await send_to_autoserv(our_message)
        negotiation.messages.append(autoserv_response)
        negotiation.rounds += 1

        console.print(
            Panel(
                f"[bold]Type:[/bold] {autoserv_response.message_type}\n\n"
                f"{autoserv_response.body}",
                title=f"AutoServ → SmartFleet (Round {negotiation.rounds})",
                border_style="green",
            )
        )

        if autoserv_response.message_type in ("accept", "reject", "escalate"):
            negotiation.status = (
                "agreed" if autoserv_response.message_type == "accept"
                else "escalated" if autoserv_response.message_type == "escalate"
                else "rejected"
            )
            break

    console.print(
        Panel(
            f"[bold]Status:[/bold] {negotiation.status}\n"
            f"[bold]Rounds:[/bold] {negotiation.rounds}\n"
            f"[bold]Messages exchanged:[/bold] {len(negotiation.messages)}",
            title="Negotiation Complete",
            border_style="magenta",
        )
    )

    return {
        "conversation_id": conv_id,
        "status": negotiation.status,
        "rounds": negotiation.rounds,
        "total_messages": len(negotiation.messages),
        "transcript": [
            {
                "sender": msg.sender_agent_id,
                "type": msg.message_type,
                "body": msg.body,
                "terms": msg.metadata.get("terms", {}),
            }
            for msg in negotiation.messages
        ],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
