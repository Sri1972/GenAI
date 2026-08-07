"""
AutoAudience Agent -- Audience Intelligence Provider

This agent represents an audience intelligence platform. It processes
campaign requests by querying IncentiveIQ for the best incentive packages
tailored to specific customer segments.

Runs on port 8005 and communicates with IncentiveIQ (port 8006)
to find optimal incentive combinations for audience segments.
"""

import json
import re
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
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
AGENT_CONFIG = load_agent_config("autoaudience")
AGENT_ID = AGENT_CONFIG["agent_id"]
ORGANIZATION = AGENT_CONFIG["organization"]
PORT = AGENT_CONFIG["port"]
INCENTIVEIQ_ENDPOINT = AGENT_CONFIG["partner_agents"]["incentiveiq"]["endpoint"]
MAX_ROUNDS = AGENT_CONFIG["conversation"]["max_rounds"]

# Build system prompt from config files (skills + guardrails + guidelines)
SYSTEM_PROMPT = build_system_prompt(
    agent_name="autoaudience",
    skill_name="audience_strategist",
    guardrail_name="autoaudience_guardrails",
    guideline_names=["communication_style", "a2a_protocol_rules"],
)

conversations: dict[str, ConversationState] = {}

# --- MCP Integration (Agent -> MCP -> API -> JSON) ---------------------------

MCP_BASE = "http://localhost:8008"
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


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


async def get_segments() -> dict:
    """Fetch audience segments dynamically via MCP (always fresh)."""
    data = await _mcp_resource("audience://segments")
    if data and "segments" in data:
        return {s["id"]: s for s in data["segments"]}
    # Fallback: local JSON if MCP is down
    data_file = DATA_DIR / "audience_segments.json"
    if data_file.exists():
        segments = json.loads(data_file.read_text(encoding="utf-8"))
        console.print(f"[yellow]Segments from local fallback (MCP unavailable)[/yellow]")
        return segments
    return {}


async def get_campaign_cases() -> list:
    """Fetch campaign cases dynamically via MCP (always fresh)."""
    data = await _mcp_resource("campaign://cases")
    if data and "campaigns" in data:
        return data["campaigns"]
    # Fallback: local JSON if MCP is down
    data_file = DATA_DIR / "campaign_cases.json"
    if data_file.exists():
        campaigns = json.loads(data_file.read_text(encoding="utf-8"))
        console.print(f"[yellow]Campaigns from local fallback (MCP unavailable)[/yellow]")
        return campaigns
    return []





# --- Helper Functions ----------------------------------------------------------

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
        # If LLM wrapped in A2A envelope, extract core fields
        if "body" in result and "conversation_id" in result:
            return {
                "action": result.get("action", "make_decision"),
                "body": result["body"],
                "followup_question": result.get("followup_question", ""),
                "decision": result.get("decision", {}),
                "reasoning": result.get("reasoning", ""),
            }
        return result
    except json.JSONDecodeError:
        pass

    # JSON was truncated — extract fields with regex
    body = extract_body_from_text(cleaned)
    action = "make_decision"
    action_match = re.search(r'"action"\s*:\s*"([^"]+)"', cleaned)
    if action_match:
        action = action_match.group(1)

    followup = ""
    fq_match = re.search(r'"followup_question"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned, re.DOTALL)
    if fq_match:
        followup = fq_match.group(1).replace('\\n', '\n').replace('\\"', '"')

    return {
        "action": action,
        "body": body,
        "followup_question": followup,
        "decision": {},
        "reasoning": "",
    }


async def send_to_incentiveiq(message: A2AMessage) -> A2AMessage:
    """Send any message to the IncentiveIQ agent."""
    console.print(
        Panel(
            f"[bold]To:[/bold] IncentiveIQ\n"
            f"[bold]Type:[/bold] {message.message_type}\n\n"
            f"{message.body[:200]}",
            title="→ Sending to IncentiveIQ",
            border_style="cyan",
        )
    )

    async with httpx.AsyncClient(timeout=60.0) as http_client:
        try:
            response = await http_client.post(
                f"{INCENTIVEIQ_ENDPOINT}/a2a/message",
                json=message.model_dump(),
            )
            response.raise_for_status()
            return A2AMessage(**response.json())
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            console.print(f"[bold red]IncentiveIQ returned HTTP {status}[/bold red]")
            raise RuntimeError(f"IncentiveIQ is unavailable (HTTP {status}). The LLM service may be down.")
        except httpx.ConnectError:
            raise RuntimeError("Cannot connect to IncentiveIQ (port 8006). Is it running?")
        except httpx.TimeoutException:
            raise RuntimeError("IncentiveIQ request timed out. The LLM service may be slow or unavailable.")


async def query_incentiveiq(conv_id: str, segment_data: dict, campaign_goal: str, dealer_region: str, budget_constraint: str) -> A2AMessage:
    """Send initial data request to IncentiveIQ agent."""
    request_message = A2AMessage(
        conversation_id=conv_id,
        sender_agent_id=AGENT_ID,
        receiver_agent_id="incentiveiq-agent-001",
        message_type="data_request",
        subject=f"Incentive Package Request — {segment_data['name']} / {campaign_goal}",
        body=f"Requesting available incentive packages for audience segment: {segment_data['name']}. "
             f"Campaign goal: {campaign_goal}. Region: {dealer_region}. Budget: {budget_constraint}. "
             f"Segment profile: Age {segment_data['age_range']}, income {segment_data['avg_income']}, "
             f"credit score {segment_data['avg_credit_score']}, location {segment_data['location']}. "
             f"Current vehicles: {', '.join(segment_data.get('current_vehicles', ['none']))}. "
             f"Key motivators: {', '.join(segment_data.get('key_motivators', []))}. "
             f"Please provide all applicable incentives including OEM rebates, dealer cash, "
             f"financing specials, loyalty bonuses, and any stackable offers.",
        metadata={
            "lookup_criteria": {
                "segment_id": segment_data["id"],
                "segment_name": segment_data["name"],
                "campaign_goal": campaign_goal,
                "dealer_region": dealer_region,
            },
            "segment_profile": segment_data,
            "budget_constraint": budget_constraint,
            "purpose": f"{campaign_goal}_campaign",
        },
    )
    return await send_to_incentiveiq(request_message)


async def ask_followup(conv_id: str, question: str, subject: str, lookup_criteria: dict = None) -> A2AMessage:
    """Send a follow-up question to IncentiveIQ."""
    # Include lookup criteria in body so IncentiveIQ can always identify the context
    criteria = lookup_criteria or {}
    criteria_text = ", ".join(f"{k}={v}" for k, v in criteria.items()) if criteria else "unknown"
    body_with_context = (
        f"Regarding the incentive query for {criteria_text}:\n\n{question}"
    )
    followup_message = A2AMessage(
        conversation_id=conv_id,
        sender_agent_id=AGENT_ID,
        receiver_agent_id="incentiveiq-agent-001",
        message_type="info_request",
        subject=f"Follow-up: {subject}",
        body=body_with_context,
        metadata={"lookup_criteria": criteria, "purpose": "clarification"},
    )
    return await send_to_incentiveiq(followup_message)


@asynccontextmanager
async def lifespan(app: FastAPI):
    console.print(
        Panel(
            f"[bold yellow]{ORGANIZATION}[/bold yellow]\n"
            f"Agent ID: {AGENT_ID}\n"
            f"Port: {PORT}\n"
            f"Connected to: IncentiveIQ (port 8006)",
            title="AutoAudience Agent Online",
            border_style="yellow",
        )
    )
    yield


app = FastAPI(title="AutoAudience Intelligence Agent", lifespan=lifespan)

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
        name="AutoAudience Strategist Agent",
        description="Analyzes customer audience segments and finds optimal incentive packages for campaigns.",
        capabilities=[
            "audience_segmentation",
            "incentive_matching",
            "campaign_strategy",
            "roi_projection",
            "conquest_retention_analysis",
        ],
        endpoint=f"http://localhost:{PORT}",
    )



@app.post("/audience/find-incentives")
async def find_incentives(
    segment_id: str = "truck_loyalists",
    campaign_goal: str = "conquest",
    dealer_region: str = "Southeast",
    budget_constraint: str = "$3,500 per unit",
):
    """Find the best incentive package for an audience segment."""

    # Fetch segments dynamically via MCP (always fresh)
    segments = await get_segments()
    segment_data = segments.get(segment_id)
    if not segment_data:
        return {"error": f"Unknown segment: {segment_id}. Available: {list(segments.keys())}"}

    conv_id = str(uuid.uuid4())
    conversation = ConversationState(conversation_id=conv_id, workflow_type=f"{campaign_goal}_campaign")
    conversations[conv_id] = conversation

    console.print(
        Panel(
            f"[bold]Segment:[/bold] {segment_data['name']}\n"
            f"[bold]Goal:[/bold] {campaign_goal}\n"
            f"[bold]Region:[/bold] {dealer_region}\n"
            f"[bold]Budget:[/bold] {budget_constraint}",
            title="New Campaign Request",
            border_style="yellow",
        )
    )

    lookup_criteria = {
        "segment_id": segment_id,
        "segment_name": segment_data["name"],
        "campaign_goal": campaign_goal,
        "dealer_region": dealer_region,
    }

    # Step 1: Initial data request to IncentiveIQ
    try:
        data_response = await query_incentiveiq(conv_id, segment_data, campaign_goal, dealer_region, budget_constraint)
    except RuntimeError as e:
        return {"error": str(e), "conversation_id": conv_id, "status": "failed"}
    conversation.messages.append(data_response)

    transcript = [
        {
            "step": "data_request",
            "agent": "AutoAudience",
            "to": "IncentiveIQ",
            "message": f"Requesting incentives for {segment_data['name']} -- {campaign_goal} campaign in {dealer_region}",
            "criteria": lookup_criteria,
        },
        {
            "step": "data_received",
            "agent": "IncentiveIQ",
            "message": data_response.body,
            "available_incentives": data_response.metadata.get("available_incentives", []),
            "data_confidence": data_response.metadata.get("data_confidence", 0),
        },
    ]

    console.print(
        Panel(
            f"[bold]Data received from IncentiveIQ[/bold]\n\n"
            f"Available incentives: {data_response.metadata.get('available_incentives', [])}\n"
            f"Confidence: {data_response.metadata.get('data_confidence', 'N/A')}%",
            title="Incentive Data Response (Round 1)",
            border_style="green",
        )
    )

    # Step 2: Multi-turn conversation -- ask follow-ups before deciding
    llm_history = [
        {
            "role": "user",
            "content": (
                f"CAMPAIGN BRIEF:\n"
                f"- Segment: {segment_data['name']}\n"
                f"- Goal: {campaign_goal}\n"
                f"- Region: {dealer_region}\n"
                f"- Budget: {budget_constraint}\n\n"
                f"SEGMENT PROFILE:\n{json.dumps(segment_data, indent=2)}\n\n"
                f"INITIAL INCENTIVE DATA FROM INCENTIVEIQ:\n{data_response.body}\n\n"
                f"Raw data: {json.dumps(data_response.metadata.get('data', {}), indent=2)}\n"
                f"Available incentives: {data_response.metadata.get('available_incentives', [])}\n\n"
                f"Review this incentive data against our audience segment profile. Before making "
                f"a final recommendation, identify what's unclear or needs verification. Ask 1-2 "
                f"follow-up questions to IncentiveIQ about eligibility, stacking, or timing. "
                f"Only make your recommendation after getting answers."
            ),
        }
    ]

    max_rounds = MAX_ROUNDS
    round_num = 0
    final_decision = None

    while round_num < max_rounds:
        round_num += 1
        agent_response = get_agent_response(llm_history)

        action = agent_response.get("action", "make_decision")
        body = agent_response.get("body", "")
        reasoning = agent_response.get("reasoning", "")

        console.print(
            Panel(
                f"[bold]Action:[/bold] {action}\n"
                f"[bold]Round:[/bold] {round_num}\n"
                f"[dim]Reasoning: {reasoning}[/dim]\n\n"
                f"{body[:200]}",
                title=f"AutoAudience Thinking (Round {round_num})",
                border_style="yellow",
            )
        )

        if action == "ask_followup":
            followup_q = agent_response.get("followup_question", body)

            transcript.append({
                "step": "followup_question",
                "agent": "AutoAudience",
                "round": round_num,
                "message": followup_q,
            })

            # Send follow-up to IncentiveIQ
            try:
                followup_response = await ask_followup(
                    conv_id, followup_q, f"Re: {campaign_goal} -- {segment_data['name']}",
                    lookup_criteria=lookup_criteria,
                )
            except RuntimeError as e:
                transcript.append({"step": "error", "agent": "System", "round": round_num, "message": str(e)})
                break
            conversation.messages.append(followup_response)

            # Extract clean body text from IncentiveIQ response
            followup_body = followup_response.body
            if followup_body and followup_body.strip().startswith("{"):
                try:
                    parsed_body = json.loads(followup_body)
                    followup_body = parsed_body.get("body", followup_body)
                except json.JSONDecodeError:
                    pass

            transcript.append({
                "step": "followup_answer",
                "agent": "IncentiveIQ",
                "round": round_num,
                "message": followup_body,
            })

            console.print(
                Panel(
                    f"{followup_response.body[:300]}",
                    title=f"IncentiveIQ Answer (Round {round_num})",
                    border_style="green",
                )
            )

            # Feed answer back into LLM conversation
            llm_history.append({"role": "assistant", "content": json.dumps(agent_response)})
            llm_history.append({
                "role": "user",
                "content": (
                    f"INCENTIVEIQ RESPONSE TO YOUR FOLLOW-UP:\n{followup_response.body}\n\n"
                    f"Based on all information gathered so far, either ask another follow-up "
                    f"question if something critical is still unclear, or make your final "
                    f"recommendation with projected ROI."
                ),
            })

        else:
            # Final decision
            final_decision = agent_response.get("decision", {})
            transcript.append({
                "step": "final_decision",
                "agent": "AutoAudience",
                "round": round_num,
                "message": body,
                "decision": final_decision,
            })

            console.print(
                Panel(
                    f"[bold]Decision:[/bold] {json.dumps(final_decision, indent=2)}\n\n"
                    f"{body}",
                    title="Final Incentive Recommendation",
                    border_style="magenta",
                )
            )
            break

    # If we exhausted rounds without a decision, force one
    if final_decision is None:
        llm_history.append({"role": "assistant", "content": json.dumps(agent_response)})
        llm_history.append({
            "role": "user",
            "content": "You've gathered enough information. Make your final recommendation NOW with action='make_decision'.",
        })
        final_response = get_agent_response(llm_history)
        final_decision = final_response.get("decision", {})
        body = final_response.get("body", "")
        transcript.append({
            "step": "final_decision",
            "agent": "AutoAudience",
            "round": round_num + 1,
            "message": body,
            "decision": final_decision,
        })

    conversation.status = "complete"

    # Notify IncentiveIQ that this conversation is complete
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{INCENTIVEIQ_ENDPOINT}/a2a/complete",
                json={"conversation_id": conv_id},
            )
    except Exception:
        pass

    return {
        "conversation_id": conv_id,
        "campaign_goal": campaign_goal,
        "segment": segment_data["name"],
        "status": "complete",
        "rounds": round_num,
        "incentive_data": {
            "body": data_response.body,
            "available_incentives": data_response.metadata.get("available_incentives", []),
            "data_confidence": data_response.metadata.get("data_confidence"),
        },
        "recommendation": final_decision,
        "explanation": body,
        "transcript": transcript,
    }


@app.get("/api/cases")
async def list_cases():
    """List available campaign cases for the UI (fetched fresh via MCP)."""
    return await get_campaign_cases()


@app.get("/api/history")
async def get_history():
    """Get processing history for the UI."""
    history = []
    for conv_id, conv in conversations.items():
        history.append({
            "conversation_id": conv_id,
            "workflow_type": conv.workflow_type,
            "status": conv.status,
            "message_count": len(conv.messages),
        })
    return sorted(history, key=lambda x: x["conversation_id"], reverse=True)[:20]


if FRONTEND_DIR.exists():
    @app.get("/")
    async def serve_ui():
        return FileResponse(FRONTEND_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
