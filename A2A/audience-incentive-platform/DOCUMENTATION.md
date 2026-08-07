# Audience Incentive Platform — Documentation

---

## Product Overview

### What Is This?

A working prototype demonstrating how an **audience intelligence platform** collaborates with an **incentive optimization engine** via AI agents to find the best incentive packages for automotive customer segments — matching the right offers to the right buyers for conquest, volume, and retention campaigns.

This represents how OEMs and dealers will orchestrate marketing campaigns in the near future: automated, multi-turn agent collaboration that mimics the back-and-forth between marketing strategists and incentive analysts.

### The Business Scenario

A dealer or OEM marketing team wants to run a campaign targeting a specific customer segment (e.g., "truck loyalists in the Southeast"). Their AI agent (**AutoAudience**) profiles the segment, then consults an incentive optimizer (**IncentiveIQ**) to find which programs are available, stackable, and within budget. The agents negotiate in multiple rounds before AutoAudience delivers a final recommendation with projected ROI.

### Key Actors

| Actor | Role | Organization Type |
|-------|------|-------------------|
| **AutoAudience Agent** | Audience intelligence & campaign strategist | Marketing intelligence platform |
| **IncentiveIQ Agent** | Incentive program matching & optimization | Pricing/incentive data provider |

### Campaign Goals

| Goal | Strategy | Risk Profile | Typical Budget |
|------|----------|-------------|----------------|
| **Conquest** | Steal customers from competing brands | High cost per unit, uncertain conversion | $3,000–$5,000/unit |
| **Volume** | Move maximum units regardless of source | Thin margins, broad targeting | $1,500–$5,000/unit |
| **Retention** | Keep existing customers from leaving | Low cost but potential waste on loyal buyers | $2,000–$3,000/unit |

### Audience Segments

| Segment | Profile | Key Motivators |
|---------|---------|---------------|
| **Truck Loyalists** | Male 35-55, rural/suburban, income $75k, credit 710 | Towing capacity, reliability, brand heritage, dealer relationship |
| **EV Curious Millennials** | 28-40, urban, income $92k, credit 740 | Sustainability, tech features, total cost of ownership |
| **Budget First-Time Buyers** | 21-28, urban/suburban, income $42k, credit 640 | Monthly payment, reliability, fuel economy, insurance cost |
| **Luxury Downsizers** | 55-70, suburban, income $130k, credit 785 | Comfort, safety features, lower maintenance, simplicity |
| **Lease Churners** | 30-45, urban/suburban, income $85k, credit 720 | New features, low monthly payment, no maintenance worry |

### Incentive Programs Available

| Program Type | Funded By | Example | Stackable? |
|-------------|-----------|---------|-----------|
| OEM Rebate | Manufacturer | $2,500 Holiday Bonus Cash | Yes (with most) |
| Dealer Cash | OEM → Dealer | $1,000 behind-the-scene | Yes |
| Financing Special | Captive finance arm | 0.9% APR for 60 months | No (exclusive with rebate) |
| Loyalty Bonus | OEM | $1,000 returning customer cash | Yes |
| Conquest Bonus | OEM | $1,500 competitive switch bonus | Yes |
| Lease Special | OEM + Dealer | Reduced money factor + residual bump | Partial |
| Federal/State Credits | Government | $7,500 EV tax credit + state rebates | Yes (always) |

### Demo Scenarios (10 total)

| # | Campaign | Segment | Goal | Region | Budget |
|---|----------|---------|------|--------|--------|
| 1 | Steal Truck Buyers from Competition | Truck Loyalists | Conquest | Southeast | $3,500/unit |
| 2 | Convert Sedan Owners to Electric | EV Curious Millennials | Volume | West Coast | $4,000/unit |
| 3 | Student Grad Special | Budget First-Time | Volume | Nationwide | $2,000/unit |
| 4 | Keep Downsizers in the Family | Luxury Downsizers | Retention | Northeast | $2,500/unit |
| 5 | Prevent Lease Brand Defection | Lease Churners | Retention | Tri-State | $3,000/unit |
| 6 | Holiday Truck Clearance | Truck Loyalists | Volume | Midwest | $5,000/unit |
| 7 | Corporate EV Adoption | EV Curious Millennials | Conquest | Pacific NW | $4,500/unit |
| 8 | Affordable Entry Point | Budget First-Time | Volume | Southwest | $1,500/unit |
| 9 | Luxury-to-Midrange Bridge | Luxury Downsizers | Retention | Southeast | $3,000/unit |
| 10 | Lease-to-Own Conversion | Lease Churners | Retention | Nationwide | $2,500/unit |

### Multi-Turn Conversation Flow

Unlike a single-shot query, AutoAudience engages in multi-round dialogue:

1. **Initial Request** — AutoAudience sends segment profile + campaign goal to IncentiveIQ
2. **Data Response** — IncentiveIQ returns available programs, eligibility criteria, stacking rules
3. **Follow-up Questions** — AutoAudience asks about specifics (expiry dates, regional restrictions, credit requirements)
4. **Clarification** — IncentiveIQ provides detailed answers
5. **Final Recommendation** — AutoAudience synthesizes everything into an optimized package with projected ROI

This mirrors how real marketing teams work with incentive analysts — you don't just ask "what's available?" and take the first answer.

### Business Value Demonstrated

1. **Speed** — Campaign optimization in seconds vs. days of analyst back-and-forth
2. **Optimization** — Finds stackable combinations humans might miss
3. **Compliance** — Guardrails prevent recommending expired, ineligible, or over-budget programs
4. **Scale** — Run 10 segment analyses in parallel across regions
5. **Consistency** — Same methodology every time, no analyst judgment variance
6. **Audit trail** — Full conversation transcript for marketing compliance

---

## Technical Documentation

### Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         A2A Protocol Layer (HTTP/JSON)                         │
├───────────────────────────────────────┬──────────────────────────────────────┤
│       AutoAudience Agent              │      IncentiveIQ Agent                │
│       (Port 8005)                     │      (Port 8006)                      │
│                                       │                                       │
│  ┌─────────────────────────────┐      │   ┌─────────────────────────────┐    │
│  │   FastAPI Server             │      │   │   FastAPI Server             │    │
│  │                              │      │   │                              │    │
│  │  /a2a/agent-card       GET   │      │   │  /a2a/agent-card       GET   │    │
│  │  /audience/find-incentives   │──────┼──►│  /a2a/message          POST  │    │
│  │  /api/cases            GET   │      │   │  /api/programs         GET   │    │
│  │  /api/history          GET   │      │   │  /api/activity         GET   │    │
│  └──────────┬───────────────────┘      │   └──────────┬───────────────────┘    │
│             │                          │              │                        │
│  ┌──────────▼───────────────────┐      │   ┌──────────▼───────────────────┐    │
│  │  LLM: Campaign Strategy       │      │   │  LLM: Incentive Matching      │    │
│  │  + Follow-up Generation       │      │   │  + Eligibility Assessment     │    │
│  │  + ROI Projection             │      │   │  + Stacking Optimization      │    │
│  └──────────────────────────────┘      │   └──────────────────────────────┘    │
│                                        │              │                        │
│                                        │   ┌──────────▼───────────────────┐    │
│                                        │   │  Incentive Database (in-mem)   │    │
│                                        │   │  6 programs with stacking      │    │
│                                        │   │  rules & eligibility criteria  │    │
│                                        │   └──────────────────────────────┘    │
└───────────────────────────────────────┴──────────────────────────────────────┘
```

### File Structure

```
audience-incentive-platform/
├── data/                            # JSON data store (human-readable, single source of truth)
│   ├── audience_segments.json       # 5 audience segment profiles
│   ├── incentive_programs.json      # 6 incentive programs with eligibility/stacking
│   └── campaign_cases.json          # 10 pre-built campaign scenarios
│
├── api/                             # Data API service (port 8007)
│   └── server.py                    # REST endpoints — segments, programs, campaigns, matching
│
├── mcp/                             # MCP Server (port 8008, SSE transport)
│   └── server.py                    # Resources + Tools + Prompts + Intent Detection
│
├── autoaudience/                    # Audience Intelligence Agent (port 8005)
│   ├── backend/
│   │   ├── app.py                   # FastAPI server
│   │   ├── a2a_protocol.py          # Protocol definitions
│   │   └── llm_client.py            # LiteLLM connection
│   └── frontend/
│       └── index.html               # React + Tailwind UI (amber theme)
│
├── incentiveiq/                     # Incentive Optimization Agent (port 8006)
│   ├── backend/
│   │   ├── app.py                   # FastAPI server
│   │   ├── a2a_protocol.py          # Protocol definitions
│   │   └── llm_client.py            # LiteLLM connection
│   └── frontend/
│       └── index.html               # React + Tailwind UI (purple theme)
│
├── config/                          # Externalized agent behavior (YAML)
│   ├── loader.py                    # Config loading utility
│   ├── agents/                      # Agent identity & connection settings
│   │   ├── autoaudience.yaml
│   │   └── incentiveiq.yaml
│   ├── skills/                      # LLM behavioral instructions
│   │   ├── audience_strategist.yaml
│   │   └── incentive_optimizer.yaml
│   ├── guardrails/                  # Safety & compliance boundaries
│   │   ├── autoaudience_guardrails.yaml
│   │   └── incentiveiq_guardrails.yaml
│   └── guidelines/                  # Communication & protocol rules
│       ├── communication_style.yaml
│       └── a2a_protocol_rules.yaml
│
├── run_campaign.py                  # CLI scenario runner
├── requirements.txt                 # Python dependencies
└── DOCUMENTATION.md                 # This file
```

### Config-Driven Architecture

Unlike Use Cases 1 and 2 (which embed configuration in code), this use case externalizes all agent behavior into YAML files:

| Config Type | Purpose | Example |
|------------|---------|---------|
| **Agents** | Identity, ports, partner connections, conversation limits | `max_rounds: 4` |
| **Skills** | LLM system prompt instructions for the agent's role | "You are an audience strategist..." |
| **Guardrails** | Hard boundaries the agent must never cross | "Never recommend expired programs" |
| **Guidelines** | Tone, formatting, and protocol communication rules | "Use markdown formatting" |

The `config/loader.py` utility assembles these into a complete system prompt at startup.

### A2A Protocol

#### Message Types

| Type | Direction | Purpose |
|------|-----------|---------|
| `data_request` | AutoAudience → IncentiveIQ | Initial incentive data request for a segment |
| `data_response` | IncentiveIQ → AutoAudience | Available programs + eligibility + stacking rules |
| `info_request` | AutoAudience → IncentiveIQ | Follow-up clarification question |
| `info_response` | IncentiveIQ → AutoAudience | Detailed answer to follow-up |

#### Data Request Metadata

```json
{
  "lookup_criteria": {
    "segment_id": "truck_loyalists",
    "segment_name": "Truck Loyalists",
    "campaign_goal": "conquest",
    "dealer_region": "Southeast"
  },
  "segment_profile": { /* full segment data */ },
  "budget_constraint": "$3,500 per unit",
  "purpose": "conquest_campaign"
}
```

#### Data Response Metadata

```json
{
  "available_incentives": ["OEM Rebate", "Conquest Bonus", "Dealer Cash"],
  "data_confidence": 88,
  "match_criteria": { "segment": "truck_loyalists", "goal": "conquest" }
}
```

### LLM Integration

- **Provider:** LiteLLM proxy (OpenAI-compatible API)
- **Model:** Configurable via `.env`
- **SSL:** Verification disabled for internal corporate proxy
- **Max Tokens:** 4096 per response
- **Temperature:** 0.7

#### AutoAudience LLM Strategy
The agent LLM is prompted to:
1. Analyze segment profile against available incentives
2. Identify gaps or uncertainties requiring follow-up
3. Ask 1-2 follow-up questions before deciding
4. Return structured JSON with `action` (ask_followup/make_decision), `body`, `reasoning`

#### IncentiveIQ LLM Strategy
The agent LLM is prompted to:
1. Match segment criteria against program database
2. Check eligibility and stacking rules
3. Calculate combined incentive values
4. Provide clear, complete answers to follow-ups

### Running the Demo

#### Prerequisites

```bash
cd audience-incentive-platform
pip install -r requirements.txt
```

Ensure `../.env` exists in the parent `A2A/` directory with LiteLLM credentials:
```
LITELLM_API_BASE=https://your-litellm-proxy-url
LITELLM_API_KEY=your-api-key
LITELLM_MODEL=your-model-name
```

#### Data Flow Architecture

```
Agent (AutoAudience/IncentiveIQ)
    |
    | HTTP POST /tools/call  or  GET /resources/read
    v
MCP Server (port 8008) -- tools, resources, prompts, intent detection
    |
    | HTTP GET/POST to /api/...
    v
Data API (port 8007) -- REST endpoints
    |
    | reads from disk
    v
JSON Files (data/) -- audience_segments, incentive_programs, campaign_cases
```

Agents NEVER call the Data API directly. They always go through the MCP server.

#### Service Startup Order

Start services in this order (each in a separate terminal). The Data API must start first, then MCP, then agents.

**Terminal 1 -- Data API (port 8007)**
```bash
cd audience-incentive-platform
python api/server.py
```
Expected output:
```
Starting Data API on port 8007...
INFO:     Uvicorn running on http://0.0.0.0:8007
```
Verify: http://localhost:8007/health

**Terminal 2 -- MCP Server (port 8008)**
```bash
cd audience-incentive-platform
python mcp/server.py
```
Expected output:
```
Starting MCP Server on port 8008 (SSE transport)...
Connect via: http://localhost:8008/sse
INFO:     Uvicorn running on http://0.0.0.0:8008
```
Verify: http://localhost:8008/health

**Terminal 3 -- IncentiveIQ Agent (port 8006)**
```bash
cd audience-incentive-platform/incentiveiq/backend
python app.py
```
Expected output: Rich panel showing "IncentiveIQ Agent Online" on port 8006.

**Terminal 4 -- AutoAudience Agent (port 8005)**
```bash
cd audience-incentive-platform/autoaudience/backend
python app.py
```
Expected output: Rich panel showing "AutoAudience Agent Online" on port 8005.

#### Using the UI

Once Terminals 3 and 4 are running, open in your browser:
- **AutoAudience UI:** http://localhost:8005 (amber theme -- trigger campaigns here)
- **IncentiveIQ UI:** http://localhost:8006 (purple theme -- watch incentive requests arrive)

Click any campaign case on the AutoAudience UI and watch the multi-turn conversation unfold in real time.

#### Using the CLI

With Terminals 3 and 4 running:
```bash
cd audience-incentive-platform
python run_campaign.py              # Random campaign (no repeats in session)
python run_campaign.py 3            # Specific campaign by ID (1-10)
python run_campaign.py --all        # Run all 10 campaigns sequentially
python run_campaign.py --list       # Show available campaigns & session status
python run_campaign.py --reset      # Clear session history, start fresh
```

#### Using the Data API directly

With Terminal 1 running, you can query data without starting the agents:
```bash
# List all audience segments
curl http://localhost:8007/api/segments

# Get a specific segment
curl http://localhost:8007/api/segments/truck_loyalists

# List active incentive programs
curl http://localhost:8007/api/programs

# Filter programs by type
curl "http://localhost:8007/api/programs?program_type=cash_back&stackable_only=true"

# Match programs to a segment + goal
curl -X POST http://localhost:8007/api/programs/match \
  -H "Content-Type: application/json" \
  -d '{"segment_id": "truck_loyalists", "campaign_goal": "conquest", "has_trade_in": true}'

# List campaigns filtered by goal
curl "http://localhost:8007/api/campaigns?goal=retention"
```

#### Using the MCP Server

With Terminals 1 and 2 running, connect any MCP client to `http://localhost:8008/sse`.

**Claude Desktop** -- add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "audience-incentive": {
      "url": "http://localhost:8008/sse"
    }
  }
}
```

**VS Code (Claude Code)** -- add to `.claude/settings.json`:
```json
{
  "mcpServers": {
    "audience-incentive": {
      "url": "http://localhost:8008/sse"
    }
  }
}
```

Once connected, the MCP client can:
- Read resources (segments, programs, campaigns)
- Call tools (`detect_intent`, `match_incentives`, `check_eligibility`, `calculate_stacking`, `get_segment_profile`, `recommend_campaign`)
- Use prompt templates (`campaign_strategy`, `incentive_analysis`, `roi_projection`)

#### Port Summary

| Port | Service | Role |
|------|---------|------|
| 8005 | AutoAudience Agent | Audience intelligence + campaign UI |
| 8006 | IncentiveIQ Agent | Incentive optimization + partner UI |
| 8007 | Data API | REST access to JSON data files |
| 8008 | MCP Server | Resources, Tools, Prompts for LLM clients |

#### Minimal Start (just agents, no MCP)

If you only need the A2A demo without MCP:
```bash
# Terminal 1
cd incentiveiq/backend && python app.py

# Terminal 2
cd autoaudience/backend && python app.py

# Terminal 3 (or open http://localhost:8005)
cd audience-incentive-platform && python run_campaign.py
```

The agents have their own in-memory data and work independently of the Data API/MCP.

### API Endpoints

#### Data API (Port 8007)

| Method | Path | Parameters | Description |
|--------|------|-----------|-------------|
| GET | `/api/segments` | -- | List all audience segments |
| GET | `/api/segments/{id}` | -- | Get a specific segment |
| GET | `/api/programs` | `program_type`, `stackable_only`, `active_only` | List programs with filters |
| GET | `/api/programs/{id}` | -- | Get a specific program |
| POST | `/api/programs/match` | JSON body with criteria | Match programs to segment/goal |
| GET | `/api/campaigns` | `goal`, `segment_id` | List campaigns with filters |
| GET | `/api/campaigns/{id}` | -- | Get a specific campaign |
| GET | `/health` | -- | Health check |

#### MCP Server (Port 8008)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/tools/call` | POST | Invoke an MCP tool: `{"name": "...", "arguments": {...}}` |
| `/tools/list` | GET | List all available MCP tools |
| `/resources/read?uri=...` | GET | Read an MCP resource by URI |
| `/sse` | SSE | MCP SSE connection (for native MCP clients) |
| `/messages/` | POST | MCP message handling (for native MCP clients) |
| `/health` | GET | Health check with capability summary |

**MCP Resources:**
| URI | Description |
|-----|-------------|
| `audience://segments` | All audience segments |
| `incentive://programs` | All incentive programs |
| `campaign://cases` | All campaign cases |

**MCP Tools:**
| Tool | Description |
|------|-------------|
| `detect_intent` | Classify user request into conquest/volume/retention |
| `match_incentives` | Find programs matching a segment + goal |
| `check_eligibility` | Verify if a program is eligible for a customer |
| `calculate_stacking` | Calculate combined value of multiple programs |
| `get_segment_profile` | Get full demographic profile of a segment |
| `recommend_campaign` | Full recommendation with budget fit and ROI |

**MCP Prompts:**
| Prompt | Description |
|--------|-------------|
| `campaign_strategy` | Generate a complete campaign strategy |
| `incentive_analysis` | Analyze incentives for a customer profile |
| `roi_projection` | Project ROI at various conversion scenarios |

#### AutoAudience Agent (Port 8005)

| Method | Path | Parameters | Description |
|--------|------|-----------|-------------|
| GET | `/a2a/agent-card` | -- | Agent discovery card |
| POST | `/audience/find-incentives` | `segment_id`, `campaign_goal`, `dealer_region`, `budget_constraint` | Full campaign optimization workflow |
| GET | `/api/cases` | -- | List pre-built campaign cases for the UI |
| GET | `/api/history` | -- | Recent conversation history |

#### IncentiveIQ Agent (Port 8006)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/a2a/agent-card` | Agent discovery card |
| POST | `/a2a/message` | Receive incentive data requests and follow-ups |
| GET | `/api/programs` | List all available incentive programs |
| GET | `/api/activity` | Recent request/response activity feed |

### Response Format

The `/audience/find-incentives` endpoint returns:

```json
{
  "conversation_id": "uuid",
  "campaign_goal": "conquest",
  "segment": "Truck Loyalists",
  "status": "complete",
  "rounds": 3,
  "incentive_data": {
    "body": "Summary from IncentiveIQ...",
    "available_incentives": ["OEM Rebate", "Conquest Bonus"],
    "data_confidence": 88
  },
  "recommendation": {
    "programs": ["Q3 Conquest Bonus", "Dealer Cash"],
    "total_incentive": "$4,500",
    "projected_roi": "12:1",
    "verdict": "Recommended"
  },
  "explanation": "Human-readable recommendation rationale...",
  "transcript": [
    {"step": "data_request", "agent": "AutoAudience", ...},
    {"step": "data_received", "agent": "IncentiveIQ", ...},
    {"step": "followup_question", "agent": "AutoAudience", ...},
    {"step": "followup_answer", "agent": "IncentiveIQ", ...},
    {"step": "final_decision", "agent": "AutoAudience", ...}
  ]
}
```

### Session Tracking

Temp file: `%TEMP%/a2a_audience_session.json`

Stores a list of campaign IDs (1-10) already run. Campaigns won't repeat until all 10 are exhausted or `--reset` is called.

### Dependencies

| Package | Purpose |
|---------|---------|
| `fastapi` | HTTP server framework (agents + data API) |
| `uvicorn` | ASGI server |
| `httpx` | Async HTTP client for inter-agent and API communication |
| `openai` | OpenAI-compatible client (for LiteLLM proxy) |
| `python-dotenv` | Environment variable management |
| `pydantic` | Data validation and serialization |
| `pyyaml` | YAML config file parsing |
| `rich` | Terminal output formatting |
| `mcp` | Model Context Protocol SDK (server) |
| `starlette` | ASGI framework (used by MCP SSE transport) |
| `sse-starlette` | Server-Sent Events support for Starlette |

---

## Glossary

### Campaign Goals

| Term | Definition |
|------|-----------|
| **Conquest** | Acquiring customers who currently own/lease a competing brand. The most expensive strategy — requires aggressive incentives to overcome brand loyalty. |
| **Volume** | Driving maximum unit sales in a given period regardless of customer origin. Used for inventory clearance, new model launches, or market share pushes. |
| **Retention** | Keeping existing customers within your brand ecosystem. Triggered when leases end, warranties expire, or competitors make aggressive offers. |

### Incentive Types

| Term | Definition |
|------|-----------|
| **OEM Rebate** | Cash back from the manufacturer (OEM = Original Equipment Manufacturer) applied at point of sale. Funded by the manufacturer, not the dealer. |
| **Dealer Cash** | A hidden incentive paid by the OEM to the dealer. The dealer may or may not pass it to the customer — essentially extra margin for deal-sweetening. |
| **Subvented Rate / Special APR** | Below-market financing offered by the OEM's captive finance arm. The OEM "buys down" the rate — 0% APR costs the OEM money but moves metal. |
| **Loyalty Bonus** | Extra cash for returning customers. Prevents defection at low cost. |
| **Conquest Bonus** | Extra cash for brand-switchers. Expensive but grows market share. |
| **Lease Pull-Ahead** | Lets a customer end their current lease early without penalty, provided they lease/buy another vehicle from the same brand. |
| **Residual Bump** | Artificially inflating the projected residual value of a leased vehicle. Lowers monthly payment; OEM absorbs depreciation risk. |
| **Money Factor** | The lease equivalent of an interest rate. Expressed as a decimal (e.g., 0.00125 = ~3% APR). |
| **Stacking** | Combining multiple incentives on a single deal. Not all programs stack — some are mutually exclusive (e.g., special APR OR cash back, not both). |
| **Federal Tax Credit** | Government incentive for EV purchases (e.g., $7,500 under the IRA). Eligibility depends on assembly location, MSRP caps, and buyer income. |
| **State Rebate** | Additional EV incentive from state governments. Stacks with federal credits. |

### Audience & Segmentation

| Term | Definition |
|------|-----------|
| **Audience Segment** | A group of potential customers sharing demographic, behavioral, and psychographic traits. Used to tailor incentive selection. |
| **Purchase Cycle** | How often a customer buys/leases a new vehicle. Truck owners: 5-7 years. Lease churners: every 3 years. |
| **Credit Score** | FICO score determining financing eligibility. Prime (720+), Near-prime (660-719), Subprime (<660). |
| **Trade-In** | Customer's current vehicle offered as partial payment. High trade-in values are a powerful incentive tool. |
| **Thin File** | A credit profile with limited history (common for first-time buyers). Requires special financing programs. |
| **Brand Loyalty Score** | Metric measuring how likely a customer is to repurchase the same brand. |

### Dealer & OEM Terminology

| Term | Definition |
|------|-----------|
| **OEM** | Original Equipment Manufacturer — the car company (Ford, GM, Toyota). Sets incentive budgets and programs. |
| **Dealer** | Independent franchise retailer. Buys vehicles from OEM and sells to consumers. Has its own margin to protect. |
| **Dealer Margin** | Profit per vehicle after all costs. Guardrails prevent stacks that push margin below 3%. |
| **MSRP** | Manufacturer's Suggested Retail Price — the "sticker price." Incentives are often capped relative to MSRP. |
| **Invoice Price** | What the dealer pays the OEM. The gap between invoice and MSRP is gross profit before incentives. |
| **Floor Plan** | Interest the dealer pays to finance vehicles sitting on the lot. Motivates year-end clearance. |
| **Metal** | Industry slang for vehicles. "Move metal" = sell cars. |

### Financial Metrics

| Term | Definition |
|------|-----------|
| **ROI (Return on Investment)** | Projected revenue per dollar of incentive spent. A 15:1 ROI means each $3,500 incentive generates $52,500 in lifetime value. |
| **Cost Per Unit** | Total incentive cost / vehicles sold. The budget constraint caps this. |
| **Conversion Rate** | Percentage of targeted audience who actually purchase. Always "projected" — never guaranteed. |
| **Cannibalization** | When one internal campaign steals customers from another internal campaign rather than from competitors. |

### A2A Protocol

| Term | Definition |
|------|-----------|
| **Agent Card** | JSON document describing an agent's identity, capabilities, and endpoint. Used for discovery. |
| **Conversation** | A multi-message exchange between two agents with a shared conversation ID. |
| **Data Request** | Initial message from AutoAudience requesting incentive data for a segment. |
| **Info Request** | Follow-up question within an existing conversation for clarification. |
| **Multi-Turn** | Conversation pattern where agents exchange multiple rounds before concluding. |
| **Guardrails** | Safety boundaries constraining agent behavior (budget limits, compliance rules, margin protection). |
