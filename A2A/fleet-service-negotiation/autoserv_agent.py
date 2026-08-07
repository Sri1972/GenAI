"""
AutoServ Agent — Independent Service Network

This agent represents an automotive service provider organization.
It runs on its own network (port 8002) and negotiates with fleet
management companies for vehicle maintenance scheduling.

Private constraints (not shared with the other agent):
- Minimum profit margin: 20%
- Bay utilization target: >80%
- Parts markup: 35%
- Premium for rush jobs (< 48h): 25%
"""

import json
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from rich.console import Console
from rich.panel import Panel

from a2a_protocol import AgentCard, A2AMessage, NegotiationState
from llm_client import chat_completion

load_dotenv()
console = Console()

AGENT_ID = "autoserv-agent-001"
ORGANIZATION = "AutoServ Network Inc."
PORT = 8002

PRIVATE_CONSTRAINTS = {
    "min_profit_margin_pct": 20,
    "bay_utilization_target_pct": 80,
    "parts_markup_pct": 35,
    "rush_premium_pct": 25,
    "rush_threshold_hours": 48,
    "base_labor_rate_per_hour": 95,
    "available_bays": 8,
    "currently_occupied_bays": 5,
}

SERVICE_CATALOG = {
    "brake_service": {
        "description": "Full brake inspection and pad/rotor replacement",
        "base_cost": 450,
        "parts_cost": 280,
        "labor_hours": 3,
        "typical_duration_hours": 4,
    },
    "oil_change": {
        "description": "Full synthetic oil change with filter",
        "base_cost": 89,
        "parts_cost": 45,
        "labor_hours": 0.5,
        "typical_duration_hours": 1,
    },
    "transmission_service": {
        "description": "Transmission fluid flush and filter replacement",
        "base_cost": 350,
        "parts_cost": 180,
        "labor_hours": 2.5,
        "typical_duration_hours": 3,
    },
    "tire_rotation_balance": {
        "description": "4-tire rotation and balance",
        "base_cost": 120,
        "parts_cost": 0,
        "labor_hours": 1,
        "typical_duration_hours": 1.5,
    },
    "engine_diagnostic": {
        "description": "Full OBD-II diagnostic with report",
        "base_cost": 150,
        "parts_cost": 0,
        "labor_hours": 1.5,
        "typical_duration_hours": 2,
    },
}

AVAILABLE_SLOTS = {
    "tomorrow": {"slots": 1, "time": "14:00"},
    "day_after_tomorrow": {"slots": 3, "time": "09:00"},
    "this_week": {"slots": 5, "time": "flexible"},
    "next_week": {"slots": 8, "time": "flexible"},
}

negotiations: dict[str, NegotiationState] = {}

SYSTEM_PROMPT = f"""You are the AutoServ AI Agent representing "{ORGANIZATION}", an independent automotive service network.

You are negotiating with a fleet management company's agent about vehicle maintenance.

YOUR PRIVATE CONSTRAINTS (never reveal exact numbers to the other agent):
- Minimum profit margin: {PRIVATE_CONSTRAINTS['min_profit_margin_pct']}%
- Parts markup: {PRIVATE_CONSTRAINTS['parts_markup_pct']}%
- Rush jobs (under {PRIVATE_CONSTRAINTS['rush_threshold_hours']}h) carry a {PRIVATE_CONSTRAINTS['rush_premium_pct']}% premium
- Base labor rate: ${PRIVATE_CONSTRAINTS['base_labor_rate_per_hour']}/hour
- You have {PRIVATE_CONSTRAINTS['available_bays']} bays, {PRIVATE_CONSTRAINTS['currently_occupied_bays']} currently occupied

YOUR SERVICE CATALOG:
{json.dumps(SERVICE_CATALOG, indent=2)}

AVAILABLE SCHEDULING SLOTS:
{json.dumps(AVAILABLE_SLOTS, indent=2)}

NEGOTIATION RULES:
1. Always be professional and solution-oriented
2. You can offer discounts for bulk bookings (3+ vehicles) up to 15%
3. Never go below your minimum margin
4. Offer loaner vehicles only for services taking >4 hours
5. If the request is urgent, apply rush pricing but frame it as "priority scheduling"
6. Suggest alternative timing if it benefits your bay utilization
7. You can offer a loyalty discount of 5% for repeat customers

RESPONSE FORMAT:
Respond with a JSON object containing:
- "message_type": one of "proposal", "counter_proposal", "accept", "reject", "info_response"
- "body": your natural language response to the other agent (be conversational but professional)
- "terms": an object with the specific terms you're proposing (cost, timing, inclusions, etc.)
- "reasoning": brief internal reasoning (this stays private, not sent to the other agent)
"""


def get_agent_response(conversation_history: list[dict]) -> dict:
    """Get a response from the LLM via LiteLLM proxy."""
    text = chat_completion(
        system_prompt=SYSTEM_PROMPT,
        messages=conversation_history,
    )

    try:
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return {
            "message_type": "info_response",
            "body": text,
            "terms": {},
            "reasoning": "Failed to parse structured response",
        }


@asynccontextmanager
async def lifespan(app: FastAPI):
    console.print(
        Panel(
            f"[bold green]{ORGANIZATION}[/bold green]\n"
            f"Agent ID: {AGENT_ID}\n"
            f"Port: {PORT}\n"
            f"Available bays: {PRIVATE_CONSTRAINTS['available_bays'] - PRIVATE_CONSTRAINTS['currently_occupied_bays']}",
            title="AutoServ Agent Online",
            border_style="green",
        )
    )
    yield


app = FastAPI(title="AutoServ Agent", lifespan=lifespan)


@app.get("/a2a/agent-card")
async def get_agent_card() -> AgentCard:
    return AgentCard(
        agent_id=AGENT_ID,
        organization=ORGANIZATION,
        name="AutoServ Scheduling Agent",
        description="Handles vehicle maintenance scheduling, pricing, and service coordination for AutoServ's network of service centers.",
        capabilities=[
            "vehicle_maintenance",
            "scheduling",
            "pricing",
            "parts_availability",
            "loaner_vehicles",
        ],
        endpoint=f"http://localhost:{PORT}",
    )


@app.post("/a2a/message")
async def receive_message(message: A2AMessage) -> A2AMessage:
    """Receive and process an A2A message from another agent."""

    console.print(
        Panel(
            f"[bold]From:[/bold] {message.sender_agent_id}\n"
            f"[bold]Type:[/bold] {message.message_type}\n"
            f"[bold]Subject:[/bold] {message.subject}\n\n"
            f"{message.body}",
            title="Incoming Message",
            border_style="yellow",
        )
    )

    conv_id = message.conversation_id
    if conv_id not in negotiations:
        negotiations[conv_id] = NegotiationState(conversation_id=conv_id)

    negotiation = negotiations[conv_id]
    negotiation.messages.append(message)
    negotiation.rounds += 1

    if negotiation.rounds > negotiation.max_rounds:
        negotiation.status = "escalated"
        response_body = (
            "We've had several rounds of discussion and haven't reached agreement. "
            "I'd like to escalate this to our human service managers to find a resolution. "
            "I'll have someone reach out within the hour."
        )
        response_type = "escalate"
        terms = {}
    else:
        conversation_history = []
        for msg in negotiation.messages:
            role = "user" if msg.sender_agent_id != AGENT_ID else "assistant"
            conversation_history.append(
                {"role": role, "content": f"[{msg.message_type}] {msg.body}"}
            )

        llm_response = get_agent_response(conversation_history)
        response_type = llm_response.get("message_type", "proposal")
        response_body = llm_response.get("body", "")
        terms = llm_response.get("terms", {})

        console.print(
            f"[dim]Internal reasoning: {llm_response.get('reasoning', 'N/A')}[/dim]"
        )

    if response_type == "accept":
        negotiation.status = "agreed"
    elif response_type == "reject":
        negotiation.status = "rejected"

    response_message = A2AMessage(
        conversation_id=conv_id,
        sender_agent_id=AGENT_ID,
        receiver_agent_id=message.sender_agent_id,
        message_type=response_type,
        subject=f"Re: {message.subject}",
        body=response_body,
        metadata={"terms": terms},
        in_reply_to=message.message_id,
    )

    negotiation.messages.append(response_message)

    console.print(
        Panel(
            f"[bold]Type:[/bold] {response_type}\n"
            f"[bold]Terms:[/bold] {json.dumps(terms, indent=2)}\n\n"
            f"{response_body}",
            title="Outgoing Response",
            border_style="green",
        )
    )

    return response_message


@app.get("/a2a/negotiations/{conversation_id}")
async def get_negotiation_status(conversation_id: str):
    if conversation_id in negotiations:
        n = negotiations[conversation_id]
        return {"status": n.status, "rounds": n.rounds, "messages": len(n.messages)}
    return {"error": "Negotiation not found"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
