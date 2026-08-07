"""
AutoRegistry Data Agent — Vehicle & Owner Data Provider

This agent represents a data services company that maintains comprehensive
vehicle registration, ownership, financial, and loyalty records.
It runs on port 8004 and responds to queries from authorized partners.

Data available:
- Vehicle specs, history, title status
- Owner identity, address, driving record summary
- Lease/finance information
- Service loyalty scores and maintenance history
- Registration and inspection status
"""

import json
import re
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from rich.console import Console
from rich.panel import Panel

from a2a_protocol import AgentCard, A2AMessage, ConversationState
from llm_client import chat_completion

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "config"))
from loader import load_agent_config, build_system_prompt

load_dotenv()
console = Console()

# Load configuration from external files
AGENT_CONFIG = load_agent_config("autoregistry")
AGENT_ID = AGENT_CONFIG["agent_id"]
ORGANIZATION = AGENT_CONFIG["organization"]
PORT = AGENT_CONFIG["port"]

VEHICLE_DATABASE = {
    "1HGCM82633A004352": {
        "vin": "1HGCM82633A004352",
        "year": 2022,
        "make": "Honda",
        "model": "Accord",
        "trim": "EX-L",
        "color": "Lunar Silver Metallic",
        "engine": "1.5L Turbo I4",
        "mileage": 34500,
        "title_status": "clean",
        "salvage_history": False,
        "accident_count": 0,
        "recall_status": "none_open",
        "license_plate": "CA-7KBR231",
        "registration_state": "CA",
        "registration_expiry": "2027-03-15",
        "inspection_status": "passed",
        "last_inspection": "2026-03-10",
        "owner": {
            "name": "Sarah Chen",
            "address": "4521 Willow Creek Dr, San Jose, CA 95129",
            "dob": "1988-04-12",
            "license_number": "D4521887",
            "license_state": "CA",
            "driving_record": {
                "years_licensed": 16,
                "violations_3yr": 0,
                "accidents_5yr": 0,
                "dui_history": False,
                "suspended_ever": False,
            },
        },
        "financial": {
            "ownership_type": "financed",
            "lienholder": "Honda Financial Services",
            "loan_start": "2022-06-15",
            "loan_term_months": 60,
            "monthly_payment": 485,
            "remaining_balance": 12400,
            "payment_history": "perfect",
            "late_payments_count": 0,
        },
        "loyalty": {
            "customer_since": "2018",
            "vehicles_owned_total": 3,
            "brand_loyalty_score": 92,
            "service_at_dealer_pct": 85,
            "maintenance_adherence": "excellent",
            "total_service_spend": 4200,
            "referrals_made": 2,
        },
    },
    "5YJSA1E26MF123456": {
        "vin": "5YJSA1E26MF123456",
        "year": 2021,
        "make": "Tesla",
        "model": "Model 3",
        "trim": "Long Range",
        "color": "Pearl White Multi-Coat",
        "engine": "Dual Motor Electric",
        "mileage": 42000,
        "title_status": "clean",
        "salvage_history": False,
        "accident_count": 1,
        "recall_status": "one_open",
        "license_plate": "TX-MKP4492",
        "registration_state": "TX",
        "registration_expiry": "2026-11-30",
        "inspection_status": "passed",
        "last_inspection": "2026-01-22",
        "owner": {
            "name": "Marcus Johnson",
            "address": "8901 Preston Hollow Ln, Dallas, TX 75225",
            "dob": "1975-09-28",
            "license_number": "TX28456712",
            "license_state": "TX",
            "driving_record": {
                "years_licensed": 28,
                "violations_3yr": 1,
                "accidents_5yr": 1,
                "dui_history": False,
                "suspended_ever": False,
            },
        },
        "financial": {
            "ownership_type": "leased",
            "lienholder": "Tesla Leasing",
            "lease_start": "2021-08-01",
            "lease_term_months": 36,
            "monthly_payment": 620,
            "residual_value": 28000,
            "lease_status": "buy_out_pending",
            "mileage_overage": True,
            "overage_miles": 6000,
        },
        "loyalty": {
            "customer_since": "2021",
            "vehicles_owned_total": 1,
            "brand_loyalty_score": 68,
            "service_at_dealer_pct": 100,
            "maintenance_adherence": "good",
            "total_service_spend": 1800,
            "referrals_made": 0,
        },
    },
    "1FTFW1ET5DFC10987": {
        "vin": "1FTFW1ET5DFC10987",
        "year": 2020,
        "make": "Ford",
        "model": "F-150",
        "trim": "XLT SuperCrew",
        "color": "Oxford White",
        "engine": "3.5L EcoBoost V6",
        "mileage": 68000,
        "title_status": "clean",
        "salvage_history": False,
        "accident_count": 2,
        "recall_status": "none_open",
        "license_plate": "FL-JHTK88",
        "registration_state": "FL",
        "registration_expiry": "2027-01-20",
        "inspection_status": "passed",
        "last_inspection": "2026-06-05",
        "owner": {
            "name": "Robert Williams",
            "address": "2234 Cypress Point Blvd, Tampa, FL 33611",
            "dob": "1965-11-03",
            "license_number": "W445-332-65-113-0",
            "license_state": "FL",
            "driving_record": {
                "years_licensed": 38,
                "violations_3yr": 2,
                "accidents_5yr": 2,
                "dui_history": False,
                "suspended_ever": False,
            },
        },
        "financial": {
            "ownership_type": "owned_outright",
            "lienholder": None,
            "paid_off_date": "2025-01-15",
            "original_loan_amount": 52000,
            "payment_history": "good",
            "late_payments_count": 3,
        },
        "loyalty": {
            "customer_since": "2012",
            "vehicles_owned_total": 5,
            "brand_loyalty_score": 88,
            "service_at_dealer_pct": 40,
            "maintenance_adherence": "fair",
            "total_service_spend": 8900,
            "referrals_made": 4,
        },
    },
    "WBAPH5C55BA271190": {
        "vin": "WBAPH5C55BA271190",
        "year": 2023,
        "make": "BMW",
        "model": "330i",
        "trim": "M Sport",
        "color": "Alpine White",
        "engine": "2.0L Turbo I4",
        "mileage": 18000,
        "title_status": "clean",
        "salvage_history": False,
        "accident_count": 0,
        "recall_status": "none_open",
        "license_plate": "NY-HGT5567",
        "registration_state": "NY",
        "registration_expiry": "2027-05-01",
        "inspection_status": "passed",
        "last_inspection": "2026-05-01",
        "owner": {
            "name": "Jennifer Martinez",
            "address": "156 E 72nd St, Apt 14B, New York, NY 10021",
            "dob": "1992-01-15",
            "license_number": "NY-M15924680",
            "license_state": "NY",
            "driving_record": {
                "years_licensed": 12,
                "violations_3yr": 1,
                "accidents_5yr": 0,
                "dui_history": False,
                "suspended_ever": False,
            },
        },
        "financial": {
            "ownership_type": "leased",
            "lienholder": "BMW Financial Services",
            "lease_start": "2023-05-01",
            "lease_term_months": 36,
            "monthly_payment": 545,
            "residual_value": 32000,
            "lease_status": "active",
            "mileage_overage": False,
            "overage_miles": 0,
        },
        "loyalty": {
            "customer_since": "2020",
            "vehicles_owned_total": 2,
            "brand_loyalty_score": 78,
            "service_at_dealer_pct": 95,
            "maintenance_adherence": "excellent",
            "total_service_spend": 3200,
            "referrals_made": 1,
        },
    },
    "2T1BURHE0JC987654": {
        "vin": "2T1BURHE0JC987654",
        "year": 2019,
        "make": "Toyota",
        "model": "Corolla",
        "trim": "LE",
        "color": "Barcelona Red Metallic",
        "engine": "1.8L I4",
        "mileage": 89000,
        "title_status": "rebuilt",
        "salvage_history": True,
        "accident_count": 3,
        "recall_status": "two_open",
        "license_plate": "IL-AB4421X",
        "registration_state": "IL",
        "registration_expiry": "2026-09-30",
        "inspection_status": "expired",
        "last_inspection": "2025-09-28",
        "owner": {
            "name": "David Kowalski",
            "address": "7743 W Belmont Ave, Chicago, IL 60634",
            "dob": "1995-06-20",
            "license_number": "K552-4419-5672",
            "license_state": "IL",
            "driving_record": {
                "years_licensed": 9,
                "violations_3yr": 4,
                "accidents_5yr": 3,
                "dui_history": True,
                "suspended_ever": True,
            },
        },
        "financial": {
            "ownership_type": "financed",
            "lienholder": "Capital One Auto",
            "loan_start": "2023-03-01",
            "loan_term_months": 72,
            "monthly_payment": 310,
            "remaining_balance": 9800,
            "payment_history": "poor",
            "late_payments_count": 8,
        },
        "loyalty": {
            "customer_since": "2023",
            "vehicles_owned_total": 1,
            "brand_loyalty_score": 25,
            "service_at_dealer_pct": 10,
            "maintenance_adherence": "poor",
            "total_service_spend": 450,
            "referrals_made": 0,
        },
    },
}

PLATE_INDEX = {v["license_plate"]: vin for vin, v in VEHICLE_DATABASE.items()}
NAME_INDEX = {v["owner"]["name"].lower(): vin for vin, v in VEHICLE_DATABASE.items()}


def lookup_vehicle(criteria: dict) -> dict | None:
    """Look up a vehicle by VIN, license plate, or name+address."""
    if vin := criteria.get("vin"):
        return VEHICLE_DATABASE.get(vin)

    if plate := criteria.get("license_plate"):
        plate_upper = plate.upper()
        for key, vin in PLATE_INDEX.items():
            if plate_upper in key.upper():
                return VEHICLE_DATABASE.get(vin)

    if name := criteria.get("name"):
        name_lower = name.lower()
        for key, vin in NAME_INDEX.items():
            if name_lower in key:
                return VEHICLE_DATABASE.get(vin)

    return None


conversations: dict[str, ConversationState] = {}

# Build system prompt from config files (skills + guardrails + guidelines)
SYSTEM_PROMPT = build_system_prompt(
    agent_name="autoregistry",
    skill_name="vehicle_data_analyst",
    guardrail_name="autoregistry_guardrails",
    guideline_names=["communication_style", "a2a_protocol_rules"],
)


def extract_body_from_text(text: str) -> str:
    """Extract the 'body' field value from potentially malformed/truncated JSON text."""
    # Look for "body": "..." pattern — handles escaped quotes within the value
    match = re.search(r'"body"\s*:\s*"((?:[^"\\]|\\.)*)(?:"|$)', text, re.DOTALL)
    if match:
        body = match.group(1)
        # Unescape JSON string escapes
        body = body.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"').replace('\\\\', '\\')
        return body
    return text


def get_agent_response(conversation_history: list[dict]) -> dict:
    """Get a response from the LLM via LiteLLM proxy."""
    text = chat_completion(
        system_prompt=SYSTEM_PROMPT,
        messages=conversation_history,
        max_tokens=4096,
    )

    # Strip code fences if present
    cleaned = text
    if "```json" in cleaned:
        cleaned = cleaned.split("```json", 1)[1]
        if "```" in cleaned:
            cleaned = cleaned.split("```", 1)[0]
    elif "```" in cleaned:
        cleaned = cleaned.split("```", 1)[1]
        if "```" in cleaned:
            cleaned = cleaned.split("```", 1)[0]

    # Try full JSON parse
    try:
        result = json.loads(cleaned.strip())
        # If LLM wrapped in A2A envelope, extract the core fields
        if "body" in result and "conversation_id" in result:
            return {
                "message_type": result.get("message_type", "data_response"),
                "body": result["body"],
                "data": result.get("data", {}),
                "risk_flags": result.get("risk_flags", []),
                "data_confidence": result.get("data_confidence", 0),
            }
        return result
    except json.JSONDecodeError:
        pass

    # JSON was truncated — extract the body field with regex
    body = extract_body_from_text(cleaned)

    # Try to extract risk_flags
    risk_flags = []
    flags_match = re.search(r'"risk_flags"\s*:\s*\[(.*?)\]', cleaned, re.DOTALL)
    if flags_match:
        risk_flags = [s.strip().strip('"') for s in flags_match.group(1).split(',') if s.strip().strip('"')]

    # Try to extract data_confidence
    confidence = 0
    conf_match = re.search(r'"data_confidence"\s*:\s*(\d+)', cleaned)
    if conf_match:
        confidence = int(conf_match.group(1))

    return {
        "message_type": "data_response",
        "body": body,
        "data": {},
        "risk_flags": risk_flags,
        "data_confidence": confidence,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    console.print(
        Panel(
            f"[bold green]{ORGANIZATION}[/bold green]\n"
            f"Agent ID: {AGENT_ID}\n"
            f"Port: {PORT}\n"
            f"Records available: {len(VEHICLE_DATABASE)} vehicles",
            title="AutoRegistry Agent Online",
            border_style="green",
        )
    )
    yield


app = FastAPI(title="AutoRegistry Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@app.get("/a2a/agent-card")
async def get_agent_card() -> AgentCard:
    return AgentCard(
        agent_id=AGENT_ID,
        organization=ORGANIZATION,
        name="AutoRegistry Data Agent",
        description="Provides comprehensive vehicle, owner, financial, and loyalty data for authorized partners.",
        capabilities=[
            "vin_lookup",
            "plate_lookup",
            "owner_lookup",
            "financial_data",
            "loyalty_scoring",
            "title_history",
            "driving_record",
        ],
        endpoint=f"http://localhost:{PORT}",
    )


@app.post("/a2a/message")
async def receive_message(message: A2AMessage) -> A2AMessage:
    """Receive and process data requests from partner agents."""

    console.print(
        Panel(
            f"[bold]From:[/bold] {message.sender_agent_id}\n"
            f"[bold]Type:[/bold] {message.message_type}\n"
            f"[bold]Subject:[/bold] {message.subject}\n\n"
            f"{message.body}",
            title="Incoming Data Request",
            border_style="yellow",
        )
    )

    conv_id = message.conversation_id
    if conv_id not in conversations:
        conversations[conv_id] = ConversationState(conversation_id=conv_id)

    conversation = conversations[conv_id]
    conversation.messages.append(message)

    lookup_criteria = message.metadata.get("lookup_criteria", {})
    vehicle_data = lookup_vehicle(lookup_criteria)

    if vehicle_data:
        context_msg = (
            f"[Data request from {message.sender_agent_id}]\n"
            f"Request: {message.body}\n\n"
            f"VEHICLE DATA FOUND:\n{json.dumps(vehicle_data, indent=2)}\n\n"
            f"Please format a professional response with this data, highlighting "
            f"any risk indicators relevant to insurance underwriting."
        )
    else:
        context_msg = (
            f"[Data request from {message.sender_agent_id}]\n"
            f"Request: {message.body}\n"
            f"Lookup criteria: {json.dumps(lookup_criteria)}\n\n"
            f"NO MATCHING RECORD FOUND. Respond professionally indicating the "
            f"record was not found and suggest alternative lookup criteria."
        )

    llm_response = get_agent_response([{"role": "user", "content": context_msg}])

    response_message = A2AMessage(
        conversation_id=conv_id,
        sender_agent_id=AGENT_ID,
        receiver_agent_id=message.sender_agent_id,
        message_type=llm_response.get("message_type", "data_response"),
        subject=f"Re: {message.subject}",
        body=llm_response.get("body", ""),
        metadata={
            "data": llm_response.get("data", {}),
            "risk_flags": llm_response.get("risk_flags", []),
            "data_confidence": llm_response.get("data_confidence", 0),
        },
        in_reply_to=message.message_id,
    )

    conversation.messages.append(response_message)

    console.print(
        Panel(
            f"[bold]Type:[/bold] {response_message.message_type}\n"
            f"[bold]Risk Flags:[/bold] {llm_response.get('risk_flags', [])}\n"
            f"[bold]Confidence:[/bold] {llm_response.get('data_confidence', 'N/A')}%\n\n"
            f"{response_message.body[:300]}...",
            title="Outgoing Response",
            border_style="green",
        )
    )

    return response_message


@app.get("/api/records")
async def list_records():
    """List all vehicle records (for UI display)."""
    records = []
    for vin, data in VEHICLE_DATABASE.items():
        records.append({
            "vin": vin,
            "plate": data["license_plate"],
            "owner_name": data["owner"]["name"],
            "vehicle": f"{data['year']} {data['make']} {data['model']} {data['trim']}",
            "title_status": data["title_status"],
            "mileage": data["mileage"],
        })
    return records


@app.get("/api/activity")
async def get_activity():
    """Get recent request activity (for UI dashboard)."""
    activity = []
    for conv_id, conv in conversations.items():
        for msg in conv.messages:
            activity.append({
                "conversation_id": conv_id,
                "timestamp": msg.timestamp,
                "sender": msg.sender_agent_id,
                "type": msg.message_type,
                "subject": msg.subject,
                "body": msg.body,
                "lookup_criteria": msg.metadata.get("lookup_criteria", {}),
            })
    return sorted(activity, key=lambda x: x["timestamp"])[-20:]


if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    @app.get("/")
    async def serve_ui():
        return FileResponse(FRONTEND_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
