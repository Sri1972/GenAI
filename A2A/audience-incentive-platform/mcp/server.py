"""
MCP Server -- Audience & Incentive Intelligence

Model Context Protocol server that exposes:
- Resources: audience segments, incentive programs, campaign cases
- Tools: match incentives, check eligibility, calculate stacking, detect intent
- Prompts: campaign strategy templates for different goals

Runs on port 8008 (SSE transport).
Consumes data from the Data API (port 8007).
"""

import json
import logging
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    Prompt,
    PromptArgument,
    PromptMessage,
    GetPromptResult,
)
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.requests import Request
from starlette.responses import JSONResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [MCP] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("mcp-server")

DATA_API_BASE = "http://localhost:8007"

server = Server("audience-incentive-mcp")


# --- Helper -------------------------------------------------------------------


async def api_get(path: str, params: dict = None) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{DATA_API_BASE}{path}", params=params)
        resp.raise_for_status()
        return resp.json()


async def api_post(path: str, body: dict) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(f"{DATA_API_BASE}{path}", json=body)
        resp.raise_for_status()
        return resp.json()


# ===============================================================================
# RESOURCES -- Expose data as readable context for LLMs
# ===============================================================================


@server.list_resources()
async def list_resources() -> list[Resource]:
    return [
        Resource(
            uri="audience://segments",
            name="Audience Segments",
            description="All customer audience segments with demographics, motivators, and purchase behavior",
            mimeType="application/json",
        ),
        Resource(
            uri="incentive://programs",
            name="Incentive Programs",
            description="All available incentive programs with eligibility, stacking rules, and expiry dates",
            mimeType="application/json",
        ),
        Resource(
            uri="campaign://cases",
            name="Campaign Cases",
            description="Pre-built campaign scenarios with segment, goal, region, and budget",
            mimeType="application/json",
        ),
    ]


@server.read_resource()
async def read_resource(uri: str) -> str:
    logger.info(f"Resource read: {uri}")

    if uri == "audience://segments":
        data = await api_get("/api/segments")
        return json.dumps(data, indent=2)
    elif uri == "incentive://programs":
        data = await api_get("/api/programs")
        return json.dumps(data, indent=2)
    elif uri == "campaign://cases":
        data = await api_get("/api/campaigns")
        return json.dumps(data, indent=2)
    elif uri.startswith("audience://segments/"):
        segment_id = uri.split("/")[-1]
        data = await api_get(f"/api/segments/{segment_id}")
        return json.dumps(data, indent=2)
    elif uri.startswith("incentive://programs/"):
        program_id = uri.split("/")[-1]
        data = await api_get(f"/api/programs/{program_id}")
        return json.dumps(data, indent=2)
    else:
        raise ValueError(f"Unknown resource URI: {uri}")


# ===============================================================================
# TOOLS -- Executable functions for incentive intelligence
# ===============================================================================


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="detect_intent",
            description="Classify a user request into a campaign intent (conquest, volume, retention) with confidence score. Use this as the first step to understand what the user is trying to accomplish.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_message": {
                        "type": "string",
                        "description": "The user's natural language request or campaign brief",
                    }
                },
                "required": ["user_message"],
            },
        ),
        Tool(
            name="match_incentives",
            description="Find all incentive programs that match a given audience segment and campaign goal. Returns matched programs with stacking analysis.",
            inputSchema={
                "type": "object",
                "properties": {
                    "segment_id": {
                        "type": "string",
                        "description": "Audience segment ID (e.g., truck_loyalists, ev_curious_millennials)",
                    },
                    "campaign_goal": {
                        "type": "string",
                        "enum": ["conquest", "volume", "retention"],
                        "description": "Campaign objective",
                    },
                    "region": {
                        "type": "string",
                        "description": "Dealer region (e.g., Southeast, West Coast, Nationwide)",
                    },
                    "credit_score": {
                        "type": "integer",
                        "description": "Target audience average credit score",
                    },
                    "has_trade_in": {
                        "type": "boolean",
                        "description": "Whether the segment is likely to have a trade-in",
                    },
                },
                "required": ["segment_id", "campaign_goal"],
            },
        ),
        Tool(
            name="check_eligibility",
            description="Check whether a specific incentive program is eligible for a given customer profile.",
            inputSchema={
                "type": "object",
                "properties": {
                    "program_id": {
                        "type": "string",
                        "description": "Incentive program ID (e.g., PROG-001)",
                    },
                    "credit_score": {
                        "type": "integer",
                        "description": "Customer credit score",
                    },
                    "age": {
                        "type": "integer",
                        "description": "Customer age",
                    },
                    "has_trade_in": {
                        "type": "boolean",
                        "description": "Whether customer has a trade-in vehicle",
                    },
                    "returning_lessee": {
                        "type": "boolean",
                        "description": "Whether customer is a returning lessee",
                    },
                    "region": {
                        "type": "string",
                        "description": "Customer region/state",
                    },
                },
                "required": ["program_id"],
            },
        ),
        Tool(
            name="calculate_stacking",
            description="Calculate the total incentive value when combining multiple programs. Validates stacking rules and reports margin impact.",
            inputSchema={
                "type": "object",
                "properties": {
                    "program_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of program IDs to stack (e.g., ['PROG-001', 'PROG-006'])",
                    }
                },
                "required": ["program_ids"],
            },
        ),
        Tool(
            name="get_segment_profile",
            description="Get the full demographic and behavioral profile of an audience segment.",
            inputSchema={
                "type": "object",
                "properties": {
                    "segment_id": {
                        "type": "string",
                        "description": "Segment ID (e.g., truck_loyalists)",
                    }
                },
                "required": ["segment_id"],
            },
        ),
        Tool(
            name="recommend_campaign",
            description="Given a segment and goal, return a complete campaign recommendation including matched incentives, stacking strategy, budget fit, and projected ROI.",
            inputSchema={
                "type": "object",
                "properties": {
                    "segment_id": {
                        "type": "string",
                        "description": "Target audience segment ID",
                    },
                    "campaign_goal": {
                        "type": "string",
                        "enum": ["conquest", "volume", "retention"],
                    },
                    "budget_per_unit": {
                        "type": "number",
                        "description": "Maximum budget per unit in dollars",
                    },
                    "region": {
                        "type": "string",
                        "description": "Target dealer region",
                    },
                },
                "required": ["segment_id", "campaign_goal", "budget_per_unit"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    logger.info(f"Tool invoked: {name} | args: {json.dumps(arguments, default=str)[:200]}")

    if name == "detect_intent":
        result = _detect_intent(arguments["user_message"])
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "match_incentives":
        criteria = {
            "segment_id": arguments["segment_id"],
            "campaign_goal": arguments["campaign_goal"],
            "credit_score": arguments.get("credit_score"),
            "has_trade_in": arguments.get("has_trade_in"),
            "region": arguments.get("region", ""),
        }
        result = await api_post("/api/programs/match", criteria)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "check_eligibility":
        program_id = arguments["program_id"]
        program = await api_get(f"/api/programs/{program_id}")

        eligible = True
        reasons = []

        conditions = program.get("conditions", {})

        # Credit score check
        min_credit = conditions.get("min_credit_score")
        credit = arguments.get("credit_score")
        if min_credit and credit:
            if credit < min_credit:
                eligible = False
                reasons.append(f"Credit score {credit} below minimum {min_credit}")
            else:
                reasons.append(f"Credit score {credit} meets minimum {min_credit}")

        # Age check
        max_age = conditions.get("max_age")
        age = arguments.get("age")
        if max_age and age:
            if age > max_age:
                eligible = False
                reasons.append(f"Age {age} exceeds maximum {max_age}")
            else:
                reasons.append(f"Age {age} within limit {max_age}")

        # Trade-in check
        if conditions.get("requires_trade_in"):
            if not arguments.get("has_trade_in"):
                eligible = False
                reasons.append("Program requires trade-in vehicle")
            else:
                reasons.append("Trade-in requirement met")

        # Returning lessee check
        if conditions.get("returning_lessee"):
            if not arguments.get("returning_lessee"):
                eligible = False
                reasons.append("Program requires returning lessee status")
            else:
                reasons.append("Returning lessee requirement met")

        # Region check
        region = arguments.get("region", "").upper()
        if region and program["region"] != "nationwide":
            prog_regions = [r.strip().upper() for r in program["region"].split(",")]
            if region not in prog_regions:
                eligible = False
                reasons.append(f"Region {region} not in eligible regions: {program['region']}")
            else:
                reasons.append(f"Region {region} eligible")

        # Expiry check
        from datetime import datetime
        if program.get("expiry"):
            today = datetime.now().strftime("%Y-%m-%d")
            if program["expiry"] < today:
                eligible = False
                reasons.append(f"Program expired on {program['expiry']}")

        result = {
            "program_id": program_id,
            "program_name": program["name"],
            "eligible": eligible,
            "checks": reasons,
            "program_value": program.get("amount") or f"{program.get('rate')}% APR",
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "calculate_stacking":
        program_ids = arguments["program_ids"]
        programs_data = await api_get("/api/programs", {"active_only": "false"})
        all_programs = {p["id"]: p for p in programs_data["programs"]}

        requested = []
        not_found = []
        for pid in program_ids:
            if pid in all_programs:
                requested.append(all_programs[pid])
            else:
                not_found.append(pid)

        stackable = [p for p in requested if p["stackable"]]
        non_stackable = [p for p in requested if not p["stackable"]]

        total_value = sum(p["amount"] for p in stackable if p["amount"])
        total_margin = sum(p["margin_impact_pct"] for p in stackable)

        result = {
            "requested_programs": [p["name"] for p in requested],
            "stackable": [{"id": p["id"], "name": p["name"], "value": p["amount"]} for p in stackable],
            "non_stackable": [{"id": p["id"], "name": p["name"], "reason": "Cannot be combined with other programs"} for p in non_stackable],
            "not_found": not_found,
            "total_stackable_value": total_value,
            "total_margin_impact_pct": round(total_margin, 1),
            "recommendation": "Use stackable programs together" if len(stackable) > 1 else "Single program - no stacking needed",
            "warning": f"Margin impact: {round(total_margin, 1)}% -- " + ("within acceptable range" if total_margin > -10 else "HIGH -- review with finance"),
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_segment_profile":
        segment_id = arguments["segment_id"]
        segment = await api_get(f"/api/segments/{segment_id}")
        return [TextContent(type="text", text=json.dumps(segment, indent=2))]

    elif name == "recommend_campaign":
        segment_id = arguments["segment_id"]
        campaign_goal = arguments["campaign_goal"]
        budget = arguments["budget_per_unit"]
        region = arguments.get("region", "Nationwide")

        # Get segment profile
        segment = await api_get(f"/api/segments/{segment_id}")

        # Match programs
        criteria = {
            "segment_id": segment_id,
            "campaign_goal": campaign_goal,
            "credit_score": segment.get("avg_credit_score"),
            "has_trade_in": segment.get("trade_in_likely", False),
            "region": region,
        }
        match_result = await api_post("/api/programs/match", criteria)

        # Filter to budget
        matched = match_result["matched_programs"]
        stackable = [p for p in matched if p["stackable"]]
        total_value = sum(p["amount"] for p in stackable if p["amount"])

        within_budget = total_value <= budget
        recommended_programs = stackable if within_budget else [p for p in stackable if (p["amount"] or 0) <= budget]

        result = {
            "segment": segment["name"],
            "campaign_goal": campaign_goal,
            "region": region,
            "budget_per_unit": budget,
            "matched_programs": [{"id": p["id"], "name": p["name"], "value": p["amount"], "type": p["type"]} for p in matched],
            "recommended_stack": [{"id": p["id"], "name": p["name"], "value": p["amount"]} for p in recommended_programs],
            "total_incentive_value": sum(p["amount"] for p in recommended_programs if p["amount"]),
            "within_budget": within_budget,
            "budget_remaining": budget - sum(p["amount"] for p in recommended_programs if p["amount"]),
            "margin_impact_pct": round(sum(p["margin_impact_pct"] for p in recommended_programs), 1),
            "segment_profile_summary": {
                "age_range": segment.get("age_range"),
                "credit_score": segment.get("avg_credit_score"),
                "location": segment.get("location"),
                "key_motivators": segment.get("key_motivators", []),
            },
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


# --- Intent Detection (rule-based + keyword) ---------------------------------


INTENT_KEYWORDS = {
    "conquest": ["steal", "switch", "compete", "competitor", "poach", "win over", "conquest", "from another brand", "brand switch"],
    "volume": ["clear", "clearance", "move", "volume", "push", "sell", "units", "inventory", "mass market", "year-end", "first-time"],
    "retention": ["keep", "retain", "loyalty", "renew", "lease end", "prevent defection", "re-lease", "stay", "churn", "coming back"],
}


def _detect_intent(message: str) -> dict:
    message_lower = message.lower()
    scores = {"conquest": 0, "volume": 0, "retention": 0}

    for intent, keywords in INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in message_lower:
                scores[intent] += 1

    total = sum(scores.values())
    if total == 0:
        return {
            "detected_intent": "unknown",
            "confidence": 0.0,
            "scores": scores,
            "suggestion": "Could not determine campaign intent. Please specify: conquest (steal from competitors), volume (maximize sales), or retention (keep existing customers).",
        }

    best_intent = max(scores, key=scores.get)
    confidence = round(scores[best_intent] / max(total, 1), 2)

    return {
        "detected_intent": best_intent,
        "confidence": confidence,
        "scores": scores,
        "suggestion": f"Detected '{best_intent}' campaign intent with {confidence:.0%} confidence.",
    }


# ===============================================================================
# PROMPTS -- Reusable prompt templates for campaign strategies
# ===============================================================================


@server.list_prompts()
async def list_prompts() -> list[Prompt]:
    return [
        Prompt(
            name="campaign_strategy",
            description="Generate a campaign strategy for a given segment and goal. Returns a structured brief with incentive recommendations.",
            arguments=[
                PromptArgument(name="segment_id", description="Target audience segment", required=True),
                PromptArgument(name="campaign_goal", description="conquest, volume, or retention", required=True),
                PromptArgument(name="budget", description="Budget per unit (e.g., $3,500)", required=False),
                PromptArgument(name="region", description="Target region", required=False),
            ],
        ),
        Prompt(
            name="incentive_analysis",
            description="Analyze a set of incentive programs for a specific customer profile. Identifies eligible programs, stacking opportunities, and total value.",
            arguments=[
                PromptArgument(name="customer_profile", description="Description of the target customer (age, credit, vehicle, behavior)", required=True),
            ],
        ),
        Prompt(
            name="roi_projection",
            description="Project the ROI for a campaign given incentive spend and expected conversion rate.",
            arguments=[
                PromptArgument(name="incentive_total", description="Total incentive cost per unit", required=True),
                PromptArgument(name="target_volume", description="Number of units targeted", required=True),
                PromptArgument(name="avg_vehicle_margin", description="Average gross margin per vehicle", required=False),
            ],
        ),
    ]


@server.get_prompt()
async def get_prompt(name: str, arguments: dict[str, str] | None = None) -> GetPromptResult:
    args = arguments or {}

    if name == "campaign_strategy":
        segment_id = args.get("segment_id", "truck_loyalists")
        goal = args.get("campaign_goal", "conquest")
        budget = args.get("budget", "$3,500")
        region = args.get("region", "Nationwide")

        return GetPromptResult(
            description=f"Campaign strategy for {segment_id} ({goal})",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=(
                            f"Create a {goal} campaign strategy for the '{segment_id}' audience segment.\n\n"
                            f"Budget: {budget} per unit\n"
                            f"Region: {region}\n\n"
                            f"Please:\n"
                            f"1. Use the `get_segment_profile` tool to understand the audience\n"
                            f"2. Use `match_incentives` to find applicable programs\n"
                            f"3. Use `calculate_stacking` to optimize the incentive package\n"
                            f"4. Provide a recommendation with:\n"
                            f"   - Recommended incentive stack\n"
                            f"   - Total incentive value vs. budget\n"
                            f"   - Key messaging angles based on segment motivators\n"
                            f"   - Projected conversion rate and ROI\n"
                            f"   - Risks and contingencies"
                        ),
                    ),
                )
            ],
        )

    elif name == "incentive_analysis":
        profile = args.get("customer_profile", "35-year-old truck owner, credit 710, has trade-in")

        return GetPromptResult(
            description=f"Incentive analysis for: {profile[:50]}",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=(
                            f"Analyze available incentives for this customer profile:\n\n"
                            f"{profile}\n\n"
                            f"Please:\n"
                            f"1. Identify which programs this customer qualifies for using `check_eligibility`\n"
                            f"2. Calculate the maximum stackable value using `calculate_stacking`\n"
                            f"3. Note any programs they're close to qualifying for (could they be nudged?)\n"
                            f"4. Recommend the optimal combination that maximizes customer value while protecting dealer margin"
                        ),
                    ),
                )
            ],
        )

    elif name == "roi_projection":
        incentive = args.get("incentive_total", "$4,000")
        volume = args.get("target_volume", "200")
        margin = args.get("avg_vehicle_margin", "$5,500")

        return GetPromptResult(
            description=f"ROI projection: {incentive}/unit x {volume} units",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=(
                            f"Project the ROI for this campaign:\n\n"
                            f"- Incentive cost per unit: {incentive}\n"
                            f"- Target volume: {volume} units\n"
                            f"- Average vehicle gross margin: {margin}\n\n"
                            f"Calculate:\n"
                            f"1. Total campaign cost (incentive x volume)\n"
                            f"2. Gross revenue at target volume\n"
                            f"3. Net margin after incentives\n"
                            f"4. Break-even conversion rate\n"
                            f"5. ROI ratio at various conversion scenarios (50%, 75%, 100% of target)\n"
                            f"6. Payback period assuming 12-month campaign window"
                        ),
                    ),
                )
            ],
        )

    raise ValueError(f"Unknown prompt: {name}")


# ===============================================================================
# SSE Transport -- Serve MCP over HTTP/SSE
# ===============================================================================


sse = SseServerTransport("/messages/")


async def handle_sse(request: Request):
    async with sse.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await server.run(
            streams[0], streams[1], server.create_initialization_options()
        )


async def handle_messages(request: Request):
    await sse.handle_post_message(request.scope, request.receive, request._send)


# ===============================================================================
# REST Endpoints -- Allow agents to call MCP tools/resources via simple HTTP
# ===============================================================================


async def handle_tool_call(request: Request):
    """POST /tools/call - Invoke an MCP tool by name with arguments.

    Body: {"name": "match_incentives", "arguments": {"segment_id": "...", ...}}
    Returns: {"result": <tool output as parsed JSON or text>}
    """
    body = await request.json()
    tool_name = body.get("name", "")
    arguments = body.get("arguments", {})

    logger.info(f"TOOL CALL: {tool_name}({json.dumps(arguments, default=str)[:200]})")

    try:
        contents = await call_tool(tool_name, arguments)
        text = contents[0].text if contents else ""
        try:
            result = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            result = text
        logger.info(f"TOOL RESULT: {tool_name} -> {str(result)[:150]}")
        return JSONResponse({"result": result})
    except Exception as e:
        logger.error(f"TOOL ERROR: {tool_name} -> {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


async def handle_resource_read(request: Request):
    """GET /resources/read?uri=audience://segments - Read an MCP resource.

    Returns: {"result": <resource content as parsed JSON or text>}
    """
    uri = request.query_params.get("uri", "")
    logger.info(f"RESOURCE READ: {uri}")

    try:
        text = await read_resource(uri)
        try:
            result = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            result = text
        logger.info(f"RESOURCE RESULT: {uri} -> {len(str(result))} chars")
        return JSONResponse({"result": result})
    except Exception as e:
        logger.error(f"RESOURCE ERROR: {uri} -> {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


async def handle_tools_list(request: Request):
    """GET /tools/list - List all available MCP tools."""
    logger.info("TOOLS LIST requested")
    tools = await list_tools()
    return JSONResponse({"tools": [{"name": t.name, "description": t.description} for t in tools]})


async def health(request: Request):
    return JSONResponse({
        "status": "ok",
        "service": "audience-incentive-mcp",
        "port": 8008,
        "capabilities": {
            "resources": 3,
            "tools": 6,
            "prompts": 3,
        },
        "rest_endpoints": [
            "POST /tools/call",
            "GET /tools/list",
            "GET /resources/read?uri=...",
        ],
    })


starlette_app = Starlette(
    routes=[
        Route("/health", health),
        Route("/sse", handle_sse),
        Route("/tools/call", handle_tool_call, methods=["POST"]),
        Route("/tools/list", handle_tools_list),
        Route("/resources/read", handle_resource_read),
        Mount("/messages/", routes=[Route("/", handle_messages, methods=["POST"])]),
    ],
)


if __name__ == "__main__":
    import uvicorn
    print("Starting MCP Server on port 8008 (SSE transport)...")
    print("Connect via: http://localhost:8008/sse")
    uvicorn.run(starlette_app, host="0.0.0.0", port=8008)
