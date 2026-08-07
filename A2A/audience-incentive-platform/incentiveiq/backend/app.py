"""
IncentiveIQ Agent — Incentive & Pricing Optimization Engine

This agent represents an incentive analytics company that maintains comprehensive
incentive program databases and provides optimization recommendations.
It runs on port 8006 and responds to queries from authorized partners (AutoAudience).

Data available:
- Incentive programs (cash back, APR, lease, rebate, conquest)
- Eligibility criteria and conditions
- Stacking rules and combined value calculations
- ROI/margin impact analysis
- Regional availability and expiration tracking
"""

import json
import re
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
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
AGENT_CONFIG = load_agent_config("incentiveiq")
AGENT_ID = AGENT_CONFIG["agent_id"]
ORGANIZATION = AGENT_CONFIG["organization"]
PORT = AGENT_CONFIG["port"]

# --- MCP Integration (Agent -> MCP -> API -> JSON) ---------------------------

MCP_BASE = "http://localhost:8008"
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


async def _mcp_tool(name: str, arguments: dict = None):
    """Call an MCP tool via the REST endpoint (async). Falls back to None."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{MCP_BASE}/tools/call",
                json={"name": name, "arguments": arguments or {}},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("result")
    except Exception as e:
        console.print(f"[dim yellow]MCP tool '{name}' unavailable ({e})[/dim yellow]")
        return None


async def _mcp_resource(uri: str):
    """Read an MCP resource via the REST endpoint (async). Falls back to None."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{MCP_BASE}/resources/read", params={"uri": uri})
            resp.raise_for_status()
            data = resp.json()
            return data.get("result")
    except Exception as e:
        console.print(f"[dim yellow]MCP resource '{uri}' unavailable ({e})[/dim yellow]")
        return None


async def get_incentive_programs() -> dict:
    """Fetch incentive programs dynamically via MCP (always fresh)."""
    data = await _mcp_resource("incentive://programs")
    if data and "programs" in data:
        return {p["id"]: p for p in data["programs"]}
    # Fallback: local JSON if MCP is down
    data_file = DATA_DIR / "incentive_programs.json"
    if data_file.exists():
        programs = json.loads(data_file.read_text(encoding="utf-8"))
        console.print(f"[yellow]Programs from local fallback (MCP unavailable)[/yellow]")
        return programs
    return {}


def match_programs(criteria: dict) -> list[dict]:
    """Match incentive programs locally (fallback when MCP is unavailable)."""
    data_file = DATA_DIR / "incentive_programs.json"
    if not data_file.exists():
        return []
    programs_db = json.loads(data_file.read_text(encoding="utf-8"))

    matched = []
    segment = criteria.get("segment", "").lower()
    vehicle = criteria.get("vehicle", "").lower()
    vehicle_class = criteria.get("vehicle_class", "").lower()
    credit_score = criteria.get("credit_score")
    age = criteria.get("age")
    is_returning_lessee = criteria.get("returning_lessee", False)
    has_trade_in = criteria.get("has_trade_in", False)
    region = criteria.get("region", "").upper()

    today = datetime.now().strftime("%Y-%m-%d")

    for prog_id, prog in programs_db.items():
        # Check expiry
        if prog["expiry"] and prog["expiry"] < today:
            continue

        # Check segment match
        segment_match = False
        if segment:
            for eligible_seg in prog["eligible_segments"]:
                if segment in eligible_seg.lower() or eligible_seg.lower() in segment:
                    segment_match = True
                    break
        else:
            segment_match = True  # No segment filter = match all

        # Check vehicle match
        vehicle_match = False
        if vehicle:
            for eligible_vehicle in prog["eligible_vehicles"]:
                if (vehicle in eligible_vehicle.lower() or
                    eligible_vehicle.lower() in vehicle or
                    eligible_vehicle.lower() == "any model" or
                    eligible_vehicle.lower() == "any ev model"):
                    vehicle_match = True
                    break
        elif vehicle_class:
            cond_class = prog["conditions"].get("vehicle_class", "any")
            if cond_class == "any" or cond_class == vehicle_class:
                vehicle_match = True
        else:
            vehicle_match = True  # No vehicle filter = match all

        # Check credit score
        min_credit = prog["conditions"].get("min_credit_score")
        if min_credit and credit_score and credit_score < min_credit:
            continue

        # Check age
        max_age = prog["conditions"].get("max_age")
        if max_age and age and age > max_age:
            continue

        # Check returning lessee requirement
        if prog["conditions"].get("returning_lessee") and not is_returning_lessee:
            continue

        # Check trade-in requirement
        if prog["conditions"].get("requires_trade_in") and not has_trade_in:
            continue

        # Check region
        if region and prog["region"] != "nationwide":
            prog_regions = [r.strip() for r in prog["region"].split(",")]
            if region not in prog_regions:
                continue

        if segment_match and vehicle_match:
            matched.append(prog)

    return matched


def calculate_stacking(programs: list[dict]) -> dict:
    """Calculate total incentive value for stackable programs."""
    stackable = [p for p in programs if p["stackable"]]
    non_stackable = [p for p in programs if not p["stackable"]]

    total_cash_value = sum(p["amount"] for p in stackable if p["amount"])
    total_margin_impact = sum(p["margin_impact_pct"] for p in stackable)

    # Best non-stackable (if any) as alternative
    best_non_stackable = None
    if non_stackable:
        best_non_stackable = max(non_stackable, key=lambda p: p["amount"] or 0)

    return {
        "stackable_programs": [p["id"] for p in stackable],
        "non_stackable_programs": [p["id"] for p in non_stackable],
        "total_stackable_value": total_cash_value,
        "total_margin_impact_pct": round(total_margin_impact, 1),
        "best_non_stackable": best_non_stackable["id"] if best_non_stackable else None,
        "best_non_stackable_value": best_non_stackable["amount"] if best_non_stackable else 0,
    }


# ─── Conversation & LLM ────────────────────────────────────────────────────────

conversations: dict[str, ConversationState] = {}

# Build system prompt from config files (skills + guardrails + guidelines)
SYSTEM_PROMPT = build_system_prompt(
    agent_name="incentiveiq",
    skill_name="incentive_optimizer",
    guardrail_name="incentiveiq_guardrails",
    guideline_names=["communication_style", "a2a_protocol_rules"],
)


def extract_body_from_text(text: str) -> str:
    """Extract the 'body' field value from potentially malformed/truncated JSON text."""
    match = re.search(r'"body"\s*:\s*"((?:[^"\\]|\\.)*)(?:"|$)', text, re.DOTALL)
    if match:
        body = match.group(1)
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
        if "body" in result and "conversation_id" in result:
            return {
                "message_type": result.get("message_type", "data_response"),
                "body": result["body"],
                "data": result.get("data", {}),
                "eligible_programs": result.get("eligible_programs", []),
                "total_incentive_value": result.get("total_incentive_value", 0),
                "margin_impact_pct": result.get("margin_impact_pct", 0),
            }
        return result
    except json.JSONDecodeError:
        pass

    # JSON was truncated — extract the body field with regex
    body = extract_body_from_text(cleaned)

    # Try to extract eligible_programs
    eligible = []
    prog_match = re.search(r'"eligible_programs"\s*:\s*\[(.*?)\]', cleaned, re.DOTALL)
    if prog_match:
        eligible = [s.strip().strip('"') for s in prog_match.group(1).split(',') if s.strip().strip('"')]

    # Try to extract total_incentive_value
    total_value = 0
    val_match = re.search(r'"total_incentive_value"\s*:\s*(\d+)', cleaned)
    if val_match:
        total_value = int(val_match.group(1))

    # Try to extract margin_impact_pct
    margin = 0
    margin_match = re.search(r'"margin_impact_pct"\s*:\s*(-?[\d.]+)', cleaned)
    if margin_match:
        margin = float(margin_match.group(1))

    return {
        "message_type": "data_response",
        "body": body,
        "data": {},
        "eligible_programs": eligible,
        "total_incentive_value": total_value,
        "margin_impact_pct": margin,
    }


# ─── FastAPI App ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    console.print(
        Panel(
            f"[bold magenta]{ORGANIZATION}[/bold magenta]\n"
            f"Agent ID: {AGENT_ID}\n"
            f"Port: {PORT}\n"
            f"Data: fetched dynamically via MCP (port 8008)",
            title="IncentiveIQ Agent Online",
            border_style="magenta",
        )
    )
    yield


app = FastAPI(title="IncentiveIQ Agent", lifespan=lifespan)

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
        name="IncentiveIQ Optimization Agent",
        description="Incentive and pricing optimization engine that matches audience segments to eligible programs and calculates combined incentive packages.",
        capabilities=[
            "segment_matching",
            "incentive_stacking",
            "roi_analysis",
            "margin_impact",
            "program_eligibility",
            "pricing_optimization",
            "conquest_analysis",
        ],
        endpoint=f"http://localhost:{PORT}",
    )


@app.post("/a2a/message")
async def receive_message(message: A2AMessage) -> A2AMessage:
    """Receive and process incentive requests from partner agents."""

    console.print(
        Panel(
            f"[bold]From:[/bold] {message.sender_agent_id}\n"
            f"[bold]Type:[/bold] {message.message_type}\n"
            f"[bold]Subject:[/bold] {message.subject}\n\n"
            f"{message.body}",
            title="Incoming Incentive Request",
            border_style="yellow",
        )
    )

    conv_id = message.conversation_id
    if conv_id not in conversations:
        conversations[conv_id] = ConversationState(conversation_id=conv_id)

    conversation = conversations[conv_id]
    conversation.messages.append(message)

    # Extract matching criteria from metadata (AutoAudience sends as "lookup_criteria")
    raw_criteria = message.metadata.get("lookup_criteria", message.metadata.get("match_criteria", {}))
    segment_profile = message.metadata.get("segment_profile", {})

    # Use MCP tool for matching (Agent -> MCP -> API -> JSON flow)
    mcp_match_args = {
        "segment_id": raw_criteria.get("segment_id", ""),
        "campaign_goal": raw_criteria.get("campaign_goal", "conquest"),
        "region": raw_criteria.get("dealer_region", raw_criteria.get("region", "")),
        "credit_score": segment_profile.get("avg_credit_score"),
        "has_trade_in": segment_profile.get("trade_in_likely", False),
    }

    match_criteria = {
        "segment_id": raw_criteria.get("segment_id", ""),
        "campaign_goal": raw_criteria.get("campaign_goal", "conquest"),
        "region": raw_criteria.get("dealer_region", raw_criteria.get("region", "")),
        "credit_score": segment_profile.get("avg_credit_score"),
        "has_trade_in": segment_profile.get("trade_in_likely", False),
    }

    mcp_result = await _mcp_tool("match_incentives", mcp_match_args)

    if mcp_result and "matched_programs" in mcp_result:
        console.print(f"[green]MCP match_incentives returned {mcp_result['count']} programs[/green]")
        matched_programs = mcp_result["matched_programs"]
        stacking_info = mcp_result.get("stacking_analysis", {})
    else:
        # Fallback to local matching if MCP unavailable
        local_criteria = {
            "segment": raw_criteria.get("campaign_goal", raw_criteria.get("segment", "")),
            "credit_score": segment_profile.get("avg_credit_score"),
            "has_trade_in": segment_profile.get("trade_in_likely", False),
            "region": raw_criteria.get("dealer_region", raw_criteria.get("region", "")),
        }
        matched_programs = match_programs(local_criteria)
        stacking_info = calculate_stacking(matched_programs) if matched_programs else {}

    if matched_programs:
        context_msg = (
            f"[Incentive request from {message.sender_agent_id}]\n"
            f"Request: {message.body}\n\n"
            f"MATCHING CRITERIA:\n{json.dumps(match_criteria, indent=2)}\n\n"
            f"MATCHED PROGRAMS ({len(matched_programs)} found):\n{json.dumps(matched_programs, indent=2)}\n\n"
            f"STACKING ANALYSIS:\n{json.dumps(stacking_info, indent=2)}\n\n"
            f"Please format a professional response with incentive recommendations, "
            f"highlighting the best package combination, total savings, eligibility requirements, "
            f"and any expiring programs that create urgency."
        )
    else:
        context_msg = (
            f"[Incentive request from {message.sender_agent_id}]\n"
            f"Request: {message.body}\n"
            f"Match criteria: {json.dumps(match_criteria)}\n\n"
            f"NO MATCHING PROGRAMS FOUND for the given criteria. Respond professionally "
            f"indicating no programs match and suggest alternative criteria or segments "
            f"that might qualify."
        )

    try:
        llm_response = get_agent_response([{"role": "user", "content": context_msg}])
    except Exception as e:
        error_body = f"Unable to generate response — the LLM service is unavailable. Error: {e}"
        console.print(f"[red]LLM ERROR: {e}[/red]")
        error_message = A2AMessage(
            conversation_id=conv_id,
            sender_agent_id=AGENT_ID,
            receiver_agent_id=message.sender_agent_id,
            message_type="error",
            subject=f"Re: {message.subject}",
            body=error_body,
            metadata={"error": str(e), "match_criteria": match_criteria},
            in_reply_to=message.message_id,
        )
        conversation.messages.append(error_message)
        conversation.status = "error"
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content={"error": error_body, "conversation_id": conv_id},
        )

    response_message = A2AMessage(
        conversation_id=conv_id,
        sender_agent_id=AGENT_ID,
        receiver_agent_id=message.sender_agent_id,
        message_type=llm_response.get("message_type", "data_response"),
        subject=f"Re: {message.subject}",
        body=llm_response.get("body", ""),
        metadata={
            "data": llm_response.get("data", {}),
            "available_incentives": [p["name"] for p in matched_programs],
            "data_confidence": min(95, 70 + len(matched_programs) * 5),
            "eligible_programs": llm_response.get("eligible_programs", [p["id"] for p in matched_programs]),
            "total_incentive_value": llm_response.get("total_incentive_value", stacking_info.get("total_stackable_value", 0)),
            "margin_impact_pct": llm_response.get("margin_impact_pct", stacking_info.get("total_margin_impact_pct", 0)),
            "stacking_info": stacking_info,
            "match_criteria": match_criteria,
        },
        in_reply_to=message.message_id,
    )

    conversation.messages.append(response_message)

    console.print(
        Panel(
            f"[bold]Type:[/bold] {response_message.message_type}\n"
            f"[bold]Programs Matched:[/bold] {len(matched_programs)}\n"
            f"[bold]Total Value:[/bold] ${stacking_info.get('total_stackable_value', 0):,}\n"
            f"[bold]Margin Impact:[/bold] {stacking_info.get('total_margin_impact_pct', 0)}%\n\n"
            f"{response_message.body[:300]}...",
            title="Outgoing Response",
            border_style="magenta",
        )
    )

    return response_message


@app.post("/a2a/complete")
async def mark_complete(request: Request):
    """Mark a conversation as complete (called by AutoAudience when done)."""
    body = await request.json()
    conv_id = body.get("conversation_id")
    if conv_id and conv_id in conversations:
        conversations[conv_id].status = "complete"
        console.print(f"[green]Conversation {conv_id} marked COMPLETE[/green]")
        return {"status": "ok"}
    return {"status": "not_found"}


@app.get("/api/programs")
async def list_programs():
    """List all incentive programs (fetched fresh via MCP)."""
    db = await get_incentive_programs()
    programs = []
    for prog_id, data in db.items():
        programs.append({
            "id": data["id"],
            "name": data["name"],
            "type": data["type"],
            "amount": data["amount"],
            "rate": data["rate"],
            "eligible_vehicles": data["eligible_vehicles"],
            "eligible_segments": data["eligible_segments"],
            "stackable": data["stackable"],
            "expiry": data["expiry"],
            "region": data["region"],
        })
    return programs


@app.get("/api/activity")
async def get_activity():
    """Get recent request activity (for UI dashboard)."""
    activity = []
    for conv_id, conv in conversations.items():
        for msg in conv.messages:
            criteria = msg.metadata.get("lookup_criteria", msg.metadata.get("match_criteria", {}))
            activity.append({
                "conversation_id": conv_id,
                "conversation_status": conv.status,
                "timestamp": msg.timestamp,
                "sender": msg.sender_agent_id,
                "type": msg.message_type,
                "subject": msg.subject,
                "body": msg.body,
                "match_criteria": criteria,
                "stacking_info": msg.metadata.get("stacking_info", {}),
                "total_incentive_value": msg.metadata.get("total_incentive_value", 0),
                "available_incentives": msg.metadata.get("available_incentives", []),
            })
    return sorted(activity, key=lambda x: x["timestamp"])


if FRONTEND_DIR.exists():
    @app.get("/")
    async def serve_ui():
        return FileResponse(FRONTEND_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
