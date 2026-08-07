# Fleet Service Negotiation — Documentation

---

## Product Overview

### What Is This?

A working prototype demonstrating how two AI agents from **separate organizations** can autonomously negotiate vehicle maintenance scheduling — without human intervention.

This represents a near-future scenario where fleet management companies and service providers use AI agents to handle routine B2B interactions, reducing scheduling friction and optimizing outcomes for both parties.

### The Business Scenario

A logistics company (**SmartFleet**) operates a fleet of 50 delivery vehicles. When a vehicle's telemetry system detects a maintenance need, the company's AI agent automatically reaches out to an independent service provider (**AutoServ**) to negotiate scheduling, pricing, and logistics.

### Key Actors

| Actor | Role | Organization Type |
|-------|------|-------------------|
| **SmartFleet Agent** | Fleet maintenance coordinator | Logistics/delivery company |
| **AutoServ Agent** | Service scheduling & pricing | Independent service network |

### What Gets Negotiated

- **Timing** — When can the vehicle be serviced with minimal operational disruption?
- **Pricing** — What's the cost, and are bulk/loyalty discounts available?
- **Logistics** — Is a loaner vehicle available during service?
- **Priority** — Can critical vehicles be fast-tracked?

### Realistic Constraints

Each agent has **private constraints** that mirror real business operations:

**SmartFleet (Buyer) doesn't reveal:**
- Maximum maintenance budget per vehicle ($800/month)
- Revenue impact of vehicle downtime ($1,200–$3,200/day)
- Which vehicles are critical vs. deferrable

**AutoServ (Seller) doesn't reveal:**
- Minimum profit margins (20%)
- Actual bay availability and utilization targets
- Rush job premium rates (25%)

### Demo Scenarios (10 total)

| Priority | Vehicle | Issue | Negotiation Dynamics |
|----------|---------|-------|---------------------|
| Critical | VH-031 (Refrigerated Truck) | Engine misfire | Urgent — high revenue impact, rush pricing expected |
| Critical | VH-011 (Heavy Duty Truck) | DOT inspection failed | Legal compliance — must be fixed immediately |
| High | VH-017 (Delivery Van) | Brake service | Safety-critical, loaner needed |
| High | VH-042 (Cargo Truck) | ABS brake failure | Safety + revenue pressure |
| High | VH-036 (Delivery Van) | Turbo/EGR fault | Performance degradation |
| Medium | VH-023 (Cargo Truck) | Transmission service | Scheduling flexibility exists |
| Medium | VH-019 (Box Truck) | Hard shifting | Can be deferred 1–2 days |
| Medium | VH-028 (Sprinter Van) | Oil change — low pressure | Borderline urgent |
| Low | VH-008 (Delivery Van) | Scheduled oil change | Full flexibility on timing |
| Low | VH-005 (Sprinter Van) | Tire rotation | Non-urgent, batch-friendly |

### Possible Outcomes

- **Agreed** — Both agents reach mutually acceptable terms
- **Rejected** — Terms couldn't be reconciled (e.g., budget vs. margin conflict)
- **Escalated** — After 6 rounds, agents hand off to human managers

### Business Value Demonstrated

1. **Speed** — Negotiations complete in seconds vs. hours of phone/email
2. **Optimization** — Agents optimize for their org's constraints simultaneously
3. **Scale** — Can handle 50+ vehicle negotiations in parallel
4. **Consistency** — Every negotiation follows organizational policies perfectly
5. **Audit trail** — Full transcript of every exchange for compliance

---

## Technical Documentation

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        A2A Protocol Layer (HTTP/JSON)                     │
├─────────────────────────────────┬───────────────────────────────────────┤
│       SmartFleet Agent          │         AutoServ Agent                 │
│       (Port 8001)               │         (Port 8002)                    │
│                                 │                                        │
│  ┌───────────────────────┐      │   ┌───────────────────────┐           │
│  │   FastAPI Server       │      │   │   FastAPI Server       │           │
│  │                        │      │   │                        │           │
│  │  /a2a/agent-card  GET  │      │   │  /a2a/agent-card  GET  │           │
│  │  /a2a/message    POST  │      │   │  /a2a/message    POST  │           │
│  │  /fleet/initiate POST  │      │   │                        │           │
│  └──────────┬─────────────┘      │   └──────────┬─────────────┘           │
│             │                    │              │                         │
│  ┌──────────▼─────────────┐      │   ┌──────────▼─────────────┐           │
│  │  LLM (via LiteLLM)     │      │   │  LLM (via LiteLLM)     │           │
│  │  Claude Sonnet 4.5     │      │   │  Claude Sonnet 4.5     │           │
│  └────────────────────────┘      │   └────────────────────────┘           │
└─────────────────────────────────┴───────────────────────────────────────┘
```

### File Structure

```
fleet-service-negotiation/
├── a2a_protocol.py          # Shared protocol definitions (Pydantic models)
├── autoserv_agent.py        # Service provider agent (port 8002)
├── smartfleet_agent.py      # Fleet manager agent (port 8001)
├── llm_client.py            # LiteLLM proxy client (shared)
├── run_scenario.py          # Scenario runner with session tracking
├── requirements.txt         # Python dependencies
└── DOCUMENTATION.md         # This file
```

### A2A Protocol

#### Agent Card (Discovery)

Each agent exposes a `GET /a2a/agent-card` endpoint for capability discovery:

```json
{
  "agent_id": "smartfleet-agent-001",
  "organization": "SmartFleet Logistics Corp.",
  "name": "SmartFleet Maintenance Coordinator",
  "capabilities": ["fleet_management", "maintenance_scheduling", "vendor_negotiation"],
  "endpoint": "http://localhost:8001",
  "protocol_version": "1.0"
}
```

#### Message Format

All inter-agent communication uses the `A2AMessage` schema:

```json
{
  "message_id": "uuid",
  "conversation_id": "uuid",
  "timestamp": "ISO-8601",
  "sender_agent_id": "smartfleet-agent-001",
  "receiver_agent_id": "autoserv-agent-001",
  "message_type": "service_request | proposal | counter_proposal | accept | reject | escalate",
  "subject": "Maintenance Request - VH-017 - brake_service",
  "body": "Natural language message",
  "metadata": {"terms": {...}},
  "in_reply_to": "previous-message-uuid"
}
```

#### Negotiation State Machine

```
service_request → proposal → [counter_proposal ↔ counter_proposal]* → accept/reject/escalate
```

- Maximum 6 rounds before auto-escalation
- State tracked per `conversation_id`

### LLM Integration

- **Provider:** LiteLLM proxy (OpenAI-compatible API)
- **Model:** Configurable via `.env`
- **SSL:** Verification disabled for internal corporate proxy
- **Timeout:** 120 seconds per LLM call
- **Temperature:** 0.7 (for varied negotiation responses)

#### System Prompt Strategy

Each agent has a detailed system prompt containing:
1. Role and organization identity
2. Private constraints (budget, margins, etc.)
3. Negotiation rules and strategy
4. Required JSON response format

The LLM returns structured JSON with:
- `message_type` — protocol-level message classification
- `body` — natural language response (sent to other agent)
- `terms` — structured terms being proposed
- `reasoning` — private internal reasoning (never transmitted)

### Running the Demo

```bash
# Prerequisites
pip install -r requirements.txt
# Ensure ../.env has LiteLLM credentials

# Start agents (separate terminals)
python autoserv_agent.py     # Terminal 1 → port 8002
python smartfleet_agent.py   # Terminal 2 → port 8001

# Run scenarios
python run_scenario.py              # Random (non-repeating)
python run_scenario.py VH-031       # Specific vehicle
python run_scenario.py --list       # Show session status
python run_scenario.py --all        # All 10 back-to-back
python run_scenario.py --reset      # Reset session
```

### API Endpoints

#### SmartFleet Agent (Port 8001)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/a2a/agent-card` | Agent discovery card |
| POST | `/a2a/message` | Receive A2A messages |
| POST | `/fleet/initiate-negotiation?vehicle_id=VH-017` | Trigger negotiation |

#### AutoServ Agent (Port 8002)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/a2a/agent-card` | Agent discovery card |
| POST | `/a2a/message` | Receive and respond to A2A messages |
| GET | `/a2a/negotiations/{conversation_id}` | Check negotiation status |

### Session Tracking

The scenario runner uses a temp file (`%TEMP%/a2a_fleet_session.json`) to track which vehicles have been used. This ensures no scenario repeats until all 10 are exhausted or the session is reset.

### Dependencies

| Package | Purpose |
|---------|---------|
| `fastapi` | HTTP server framework |
| `uvicorn` | ASGI server |
| `httpx` | Async HTTP client for inter-agent communication |
| `openai` | OpenAI-compatible client (for LiteLLM proxy) |
| `python-dotenv` | Environment variable management |
| `pydantic` | Data validation and serialization |
| `rich` | Terminal output formatting |

---

## Glossary

### Fleet Management

| Term | Definition |
|------|-----------|
| **Fleet** | A collection of vehicles owned/managed by a single company for commercial use (delivery, logistics, field service). SmartFleet manages 50 vehicles. |
| **Telemetry** | Real-time data from vehicle sensors — mileage, engine codes, brake wear, tire pressure. Triggers proactive maintenance requests. |
| **Downtime** | Time a vehicle is out of service (being repaired). Fleet managers optimize to minimize this because idle vehicles = lost revenue. |
| **Utilization Rate** | Percentage of time a vehicle is actively in service vs. sitting idle or in maintenance. Fleet KPI. |
| **Preventive Maintenance (PM)** | Scheduled service based on mileage/time intervals (oil changes, brake inspections) before something breaks. Cheaper than reactive repair. |
| **Priority Level** | Urgency classification: Critical (safety/compliance), High (performance-impacting), Medium (degrading), Low (routine). |

### Service Provider

| Term | Definition |
|------|-----------|
| **Service Center** | A physical repair facility with bays, technicians, and parts inventory. AutoServ operates 3 centers. |
| **Bay** | A single vehicle repair slot in a service center. A center with 8 bays can work on 8 vehicles simultaneously. |
| **Parts Availability** | Whether required components are in stock. Backordered parts delay service and affect negotiation. |
| **Labor Rate** | Hourly charge for technician time. Varies by specialization (general mechanic vs. transmission specialist). |
| **Loaner Vehicle** | A temporary replacement vehicle provided to the fleet while theirs is being serviced. Reduces effective downtime. |

### Negotiation

| Term | Definition |
|------|-----------|
| **Proposal** | An initial offer from one agent to another (schedule, price, terms). |
| **Counter-Proposal** | A modified offer in response. Changes one or more terms (e.g., different date, lower price). |
| **Accept** | Agreement to the current terms. Ends the negotiation successfully. |
| **Reject** | Declining the proposal outright. May end negotiation or trigger escalation. |
| **Escalate** | Handing the negotiation to a human when agents can't reach agreement within their constraints. |
| **Constraints** | Private rules each agent optimizes for. SmartFleet: minimize cost + downtime. AutoServ: maximize margin + utilization. Neither reveals their constraints to the other. |

### Vehicle Service Types

| Term | Definition |
|------|-----------|
| **Brake Service** | Inspection/replacement of brake pads, rotors, calipers, or ABS components. |
| **Transmission Service** | Fluid change, filter replacement, or repair of gear-shifting mechanisms. |
| **Engine Diagnostic** | Computer-aided troubleshooting of engine issues (misfires, turbo/EGR faults, oil pressure). |
| **Oil Change** | Routine fluid replacement. Low priority unless accompanied by pressure warnings. |
| **DOT Inspection** | Department of Transportation safety inspection. Failure = vehicle legally prohibited from operating. Always critical. |

### A2A Protocol

| Term | Definition |
|------|-----------|
| **Agent Card** | JSON document describing an agent's identity, capabilities, and endpoint. Used for discovery. |
| **Message Type** | Classification of each A2A message: `request`, `proposal`, `counter`, `accept`, `reject`, `escalate`. |
| **Conversation** | A sequence of messages between two agents sharing a conversation ID. Tracks negotiation state. |
| **Round** | One complete exchange (message + response) in a negotiation. Most complete in 2-4 rounds. |
