"""
SecureAuto Insurance Agent — Insurance Company

This agent represents an auto insurance company. It processes
new policy quotes, claims, and renewals by querying external data
providers for vehicle and owner information.

Runs on port 8003 and communicates with AutoRegistry (port 8004)
to retrieve vehicle data for underwriting decisions.
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
AGENT_CONFIG = load_agent_config("secureauto")
AGENT_ID = AGENT_CONFIG["agent_id"]
ORGANIZATION = AGENT_CONFIG["organization"]
PORT = AGENT_CONFIG["port"]
AUTOREGISTRY_ENDPOINT = AGENT_CONFIG["partner_agents"]["autoregistry"]["endpoint"]
MAX_ROUNDS = AGENT_CONFIG["conversation"]["max_rounds"]

# Build system prompt from config files (skills + guardrails + guidelines)
SYSTEM_PROMPT = build_system_prompt(
    agent_name="secureauto",
    skill_name="insurance_underwriter",
    guardrail_name="secureauto_guardrails",
    guideline_names=["communication_style", "a2a_protocol_rules"],
)

conversations: dict[str, ConversationState] = {}


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


async def send_to_autoregistry(message: A2AMessage) -> A2AMessage:
    """Send any message to the AutoRegistry agent."""
    console.print(
        Panel(
            f"[bold]To:[/bold] AutoRegistry\n"
            f"[bold]Type:[/bold] {message.message_type}\n\n"
            f"{message.body[:200]}",
            title="→ Sending to AutoRegistry",
            border_style="cyan",
        )
    )

    async with httpx.AsyncClient(timeout=60.0) as http_client:
        response = await http_client.post(
            f"{AUTOREGISTRY_ENDPOINT}/a2a/message",
            json=message.model_dump(),
        )
        response.raise_for_status()
        return A2AMessage(**response.json())


async def query_autoregistry(conv_id: str, lookup_criteria: dict, purpose: str) -> A2AMessage:
    """Send initial data request to AutoRegistry agent."""
    request_message = A2AMessage(
        conversation_id=conv_id,
        sender_agent_id=AGENT_ID,
        receiver_agent_id="autoregistry-agent-001",
        message_type="data_request",
        subject=f"Vehicle/Owner Data Request — {purpose}",
        body=f"Requesting vehicle and owner data for insurance {purpose}. "
             f"Lookup criteria: {json.dumps(lookup_criteria)}. "
             f"Please provide full vehicle specs, owner driving record, "
             f"financial/lease information, and loyalty data.",
        metadata={"lookup_criteria": lookup_criteria, "purpose": purpose},
    )
    return await send_to_autoregistry(request_message)


async def ask_followup(conv_id: str, question: str, subject: str, lookup_criteria: dict = None) -> A2AMessage:
    """Send a follow-up question to AutoRegistry."""
    # Include lookup criteria in body so AutoRegistry can always identify the record
    criteria = lookup_criteria or {}
    criteria_text = ", ".join(f"{k}={v}" for k, v in criteria.items()) if criteria else "unknown"
    body_with_context = (
        f"Regarding the record with {criteria_text}:\n\n{question}"
    )
    followup_message = A2AMessage(
        conversation_id=conv_id,
        sender_agent_id=AGENT_ID,
        receiver_agent_id="autoregistry-agent-001",
        message_type="info_request",
        subject=f"Follow-up: {subject}",
        body=body_with_context,
        metadata={"lookup_criteria": criteria, "purpose": "clarification"},
    )
    return await send_to_autoregistry(followup_message)


@asynccontextmanager
async def lifespan(app: FastAPI):
    console.print(
        Panel(
            f"[bold blue]{ORGANIZATION}[/bold blue]\n"
            f"Agent ID: {AGENT_ID}\n"
            f"Port: {PORT}\n"
            f"Connected to: AutoRegistry (port 8004)",
            title="SecureAuto Insurance Agent Online",
            border_style="blue",
        )
    )
    yield


app = FastAPI(title="SecureAuto Insurance Agent", lifespan=lifespan)

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
        name="SecureAuto Underwriting Agent",
        description="Processes auto insurance quotes, claims, and renewals using external vehicle data.",
        capabilities=[
            "new_policy_quotes",
            "claims_processing",
            "policy_renewals",
            "risk_assessment",
            "premium_calculation",
        ],
        endpoint=f"http://localhost:{PORT}",
    )


@app.post("/insurance/process-request")
async def process_insurance_request(
    workflow_type: str = "new_quote",
    lookup_by: str = "vin",
    lookup_value: str = "1HGCM82633A004352",
    customer_context: str = "",
):
    """Process an insurance request with multi-turn agent conversation."""

    conv_id = str(uuid.uuid4())
    conversation = ConversationState(conversation_id=conv_id, workflow_type=workflow_type)
    conversations[conv_id] = conversation

    console.print(
        Panel(
            f"[bold]Workflow:[/bold] {workflow_type}\n"
            f"[bold]Lookup:[/bold] {lookup_by} = {lookup_value}\n"
            f"[bold]Context:[/bold] {customer_context or 'Standard request'}",
            title="New Insurance Request",
            border_style="blue",
        )
    )

    lookup_criteria = {}
    if lookup_by == "vin":
        lookup_criteria = {"vin": lookup_value}
    elif lookup_by == "plate":
        lookup_criteria = {"license_plate": lookup_value}
    elif lookup_by == "name":
        lookup_criteria = {"name": lookup_value}

    # Step 1: Initial data request
    data_response = await query_autoregistry(conv_id, lookup_criteria, workflow_type)
    conversation.messages.append(data_response)

    transcript = [
        {
            "step": "data_request",
            "agent": "SecureAuto",
            "to": "AutoRegistry",
            "message": f"Requesting vehicle/owner data via {lookup_by}: {lookup_value}",
            "criteria": lookup_criteria,
        },
        {
            "step": "data_received",
            "agent": "AutoRegistry",
            "message": data_response.body,
            "risk_flags": data_response.metadata.get("risk_flags", []),
            "data_confidence": data_response.metadata.get("data_confidence", 0),
        },
    ]

    console.print(
        Panel(
            f"[bold]Data received from AutoRegistry[/bold]\n\n"
            f"Risk flags: {data_response.metadata.get('risk_flags', [])}\n"
            f"Confidence: {data_response.metadata.get('data_confidence', 'N/A')}%",
            title="Data Provider Response (Round 1)",
            border_style="green",
        )
    )

    # Step 2: Multi-turn conversation — ask follow-ups before deciding
    llm_history = [
        {
            "role": "user",
            "content": (
                f"WORKFLOW: {workflow_type}\n"
                f"CUSTOMER CONTEXT: {customer_context or 'Standard request'}\n\n"
                f"INITIAL DATA FROM AUTOREGISTRY:\n{data_response.body}\n\n"
                f"Raw data: {json.dumps(data_response.metadata.get('data', {}), indent=2)}\n"
                f"Risk flags: {data_response.metadata.get('risk_flags', [])}\n\n"
                f"Review this data. Before making a final decision, identify what's unclear or "
                f"needs verification. Ask 1-2 follow-up questions to AutoRegistry to clarify "
                f"key risk factors. Only make your decision after getting answers."
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
                title=f"SecureAuto Thinking (Round {round_num})",
                border_style="blue",
            )
        )

        if action == "ask_followup":
            followup_q = agent_response.get("followup_question", body)

            transcript.append({
                "step": "followup_question",
                "agent": "SecureAuto",
                "round": round_num,
                "message": followup_q,
            })

            # Send follow-up to AutoRegistry
            followup_response = await ask_followup(
                conv_id, followup_q, f"Re: {workflow_type} — {lookup_value}",
                lookup_criteria=lookup_criteria,
            )
            conversation.messages.append(followup_response)

            # Extract clean body text from AutoRegistry response
            followup_body = followup_response.body
            if followup_body and followup_body.strip().startswith("{"):
                try:
                    parsed_body = json.loads(followup_body)
                    followup_body = parsed_body.get("body", followup_body)
                except json.JSONDecodeError:
                    pass

            transcript.append({
                "step": "followup_answer",
                "agent": "AutoRegistry",
                "round": round_num,
                "message": followup_body,
            })

            console.print(
                Panel(
                    f"{followup_response.body[:300]}",
                    title=f"AutoRegistry Answer (Round {round_num})",
                    border_style="green",
                )
            )

            # Feed answer back into LLM conversation
            llm_history.append({"role": "assistant", "content": json.dumps(agent_response)})
            llm_history.append({
                "role": "user",
                "content": (
                    f"AUTOREGISTRY RESPONSE TO YOUR FOLLOW-UP:\n{followup_response.body}\n\n"
                    f"Based on all information gathered so far, either ask another follow-up "
                    f"question if something critical is still unclear, or make your final decision."
                ),
            })

        else:
            # Final decision
            final_decision = agent_response.get("decision", {})
            transcript.append({
                "step": "final_decision",
                "agent": "SecureAuto",
                "round": round_num,
                "message": body,
                "decision": final_decision,
            })

            console.print(
                Panel(
                    f"[bold]Decision:[/bold] {json.dumps(final_decision, indent=2)}\n\n"
                    f"{body}",
                    title="Final Underwriting Decision",
                    border_style="magenta",
                )
            )
            break

    # If we exhausted rounds without a decision, force one
    if final_decision is None:
        llm_history.append({"role": "assistant", "content": json.dumps(agent_response)})
        llm_history.append({
            "role": "user",
            "content": "You've gathered enough information. Make your final decision NOW with action='make_decision'.",
        })
        final_response = get_agent_response(llm_history)
        final_decision = final_response.get("decision", {})
        body = final_response.get("body", "")
        transcript.append({
            "step": "final_decision",
            "agent": "SecureAuto",
            "round": round_num + 1,
            "message": body,
            "decision": final_decision,
        })

    conversation.status = "complete"

    return {
        "conversation_id": conv_id,
        "workflow_type": workflow_type,
        "status": "complete",
        "rounds": round_num,
        "data_provider_response": {
            "body": data_response.body,
            "risk_flags": data_response.metadata.get("risk_flags", []),
            "data_confidence": data_response.metadata.get("data_confidence"),
        },
        "underwriting_decision": final_decision,
        "explanation": body,
        "transcript": transcript,
    }


@app.get("/api/scenarios")
async def list_scenarios():
    """List available scenarios for the UI."""
    return [
        {"id": 1, "title": "New Quote — Clean Record Honda Owner", "workflow_type": "new_quote", "lookup_by": "vin", "lookup_value": "1HGCM82633A004352", "customer_context": "Customer wants a new full coverage policy. Has been with another insurer for 5 years, shopping for better rates."},
        {"id": 2, "title": "New Quote — High-Risk Driver (DUI History)", "workflow_type": "new_quote", "lookup_by": "name", "lookup_value": "David Kowalski", "customer_context": "Walk-in customer requesting minimum liability coverage. Says previous insurer dropped them."},
        {"id": 3, "title": "Claim — Tesla Fender Bender", "workflow_type": "claim", "lookup_by": "plate", "lookup_value": "TX-MKP4492", "customer_context": "Customer reports minor rear-end collision in parking lot. Damage to rear bumper and trunk. No injuries. Other party at fault."},
        {"id": 4, "title": "Policy Renewal — Ford F-150 with Violations", "workflow_type": "renewal", "lookup_by": "vin", "lookup_value": "1FTFW1ET5DFC10987", "customer_context": "Annual renewal. Customer had 2 speeding tickets and a minor at-fault accident since last renewal."},
        {"id": 5, "title": "New Quote — BMW Lease (Plate Lookup)", "workflow_type": "new_quote", "lookup_by": "plate", "lookup_value": "NY-HGT5567", "customer_context": "Leasing company requires full coverage with $500 deductible. Customer is a young professional in NYC."},
        {"id": 6, "title": "Claim — Salvage Title Vehicle Theft", "workflow_type": "claim", "lookup_by": "name", "lookup_value": "David Kowalski", "customer_context": "Customer reports vehicle stolen from street parking overnight. No witnesses. Vehicle has rebuilt title."},
        {"id": 7, "title": "Policy Renewal — Loyal Honda Customer", "workflow_type": "renewal", "lookup_by": "name", "lookup_value": "Sarah Chen", "customer_context": "3-year customer requesting renewal. No claims filed, perfect payment history. Asking about loyalty discount."},
        {"id": 8, "title": "New Quote — Tesla Lease Buyout", "workflow_type": "new_quote", "lookup_by": "vin", "lookup_value": "5YJSA1E26MF123456", "customer_context": "Customer buying out lease and needs new personal policy. Previously covered under fleet insurance. Has one prior accident."},
        {"id": 9, "title": "Claim — F-150 Hail Damage", "workflow_type": "claim", "lookup_by": "plate", "lookup_value": "FL-JHTK88", "customer_context": "Customer reports extensive hail damage during Florida storm. Hood, roof, and all panels affected. Repair estimate $8,500."},
        {"id": 10, "title": "New Quote — High Mileage Rebuilt Title", "workflow_type": "new_quote", "lookup_by": "name", "lookup_value": "David Kowalski", "customer_context": "Customer shopping for cheapest possible insurance. Only wants state minimum. Vehicle has 89k miles and rebuilt title."},
    ]


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
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    @app.get("/")
    async def serve_ui():
        return FileResponse(FRONTEND_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
