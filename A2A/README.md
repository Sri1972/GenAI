# A2A (Agent-to-Agent) Protocol Prototypes

## What is A2A?

A2A is a protocol pattern where autonomous AI agents from **separate organizations** communicate via structured JSON-over-HTTP messages to negotiate, collaborate, and transact — without human intervention in the loop.

Each agent has:
- Its own identity and organization
- Private constraints and objectives
- An LLM "brain" for reasoning and decision-making
- A public agent card for discovery

## Use Cases

This repository contains three automotive industry A2A demos, each showing a different collaboration pattern:

| # | Use Case | Pattern | Ports | Folder |
|---|----------|---------|-------|--------|
| 1 | Fleet + Service Negotiation | Adversarial negotiation | 8001, 8002 | [`fleet-service-negotiation/`](fleet-service-negotiation/DOCUMENTATION.md) |
| 2 | Insurance + Vehicle Data | Data lookup + underwriting | 8003, 8004 | [`insurance-vehicle-lookup/`](insurance-vehicle-lookup/DOCUMENTATION.md) |
| 3 | Audience + Incentive Optimization | Multi-turn strategy collaboration | 8005, 8006 | [`audience-incentive-platform/`](audience-incentive-platform/DOCUMENTATION.md) |

### Use Case 1: Fleet Service Negotiation
Two agents with **opposing interests** negotiate vehicle maintenance scheduling.
SmartFleet wants minimal cost/downtime; AutoServ wants maximum revenue/utilization.
They exchange proposals, counter-proposals, and reach agreement — or escalate.

### Use Case 2: Insurance Vehicle Lookup
An insurance underwriter agent queries a vehicle data provider for history, ownership,
and risk signals. Multi-turn: the underwriter asks follow-up questions before rendering
an underwriting decision (approve/decline/refer with conditions).

### Use Case 3: Audience Incentive Platform
An audience intelligence agent collaborates with an incentive optimization engine to find
the best incentive packages for customer segments. Supports conquest, volume, and
retention campaign strategies with real automotive incentive programs.

## Architecture

```
                        ┌─────────────────────────────┐
                        │         A2A Protocol          │
                        │    JSON-over-HTTP Messages     │
                        │  ┌─────────┐  ┌──────────┐   │
                        │  │Agent Card│  │ Messages │   │
                        │  └─────────┘  └──────────┘   │
                        └──────────┬──────────┬────────┘
                                   │          │
              ┌────────────────────┴──┐  ┌────┴────────────────────┐
              │     Agent A            │  │     Agent B              │
              │  ┌────────────────┐    │  │  ┌────────────────┐     │
              │  │  LLM (Claude)  │    │  │  │  LLM (Claude)  │     │
              │  └───────┬────────┘    │  │  └───────┬────────┘     │
              │  ┌───────┴────────┐    │  │  ┌───────┴────────┐     │
              │  │ Skills/Config   │    │  │  │ Skills/Config   │     │
              │  │ Guardrails      │    │  │  │ Guardrails      │     │
              │  │ Guidelines      │    │  │  │ Guidelines      │     │
              │  └────────────────┘    │  │  └────────────────┘     │
              │  ┌────────────────┐    │  │  ┌────────────────┐     │
              │  │ FastAPI Backend │    │  │  │ FastAPI Backend │     │
              │  │ React Frontend  │    │  │  │ React Frontend  │     │
              │  └────────────────┘    │  │  └────────────────┘     │
              └────────────────────────┘  └─────────────────────────┘
```

## Tech Stack

- **Backend:** Python, FastAPI, Pydantic
- **Frontend:** React (CDN), Tailwind CSS (CDN), marked.js, DOMPurify
- **LLM:** Claude via LiteLLM proxy (OpenAI-compatible API)
- **Config:** Externalized YAML (skills, guardrails, guidelines)
- **Protocol:** Custom A2A JSON-over-HTTP (agent cards + typed messages)

## Quick Start

### Prerequisites
- Python 3.11+
- LiteLLM proxy credentials (see `.env` setup)

### Install
```bash
pip install -r fleet-service-negotiation/requirements.txt
pip install -r insurance-vehicle-lookup/requirements.txt
pip install -r audience-incentive-platform/requirements.txt
```

### Environment
Create a `.env` file in this directory:
```
LITELLM_API_BASE=https://your-litellm-proxy-url
LITELLM_API_KEY=your-api-key
LITELLM_MODEL=your-model-name
```

### Run Any Use Case

Each use case has two agents. Start both agents in separate terminals, then either
open the web UI or use the CLI runner.

**Example — Use Case 3 (Audience + Incentive):**
```bash
# Terminal 1
cd audience-incentive-platform/incentiveiq/backend
python app.py

# Terminal 2
cd audience-incentive-platform/autoaudience/backend
python app.py

# Terminal 3 (CLI) or open http://localhost:8005 in browser
cd audience-incentive-platform
python run_campaign.py
```

## Port Map

| Port | Agent | Use Case |
|------|-------|----------|
| 8001 | SmartFleet (Fleet Manager) | Fleet Negotiation |
| 8002 | AutoServ (Service Provider) | Fleet Negotiation |
| 8003 | SecureAuto (Insurance) | Insurance Lookup |
| 8004 | AutoRegistry (Vehicle Data) | Insurance Lookup |
| 8005 | AutoAudience (Audience Intelligence) | Incentive Platform |
| 8006 | IncentiveIQ (Incentive Optimizer) | Incentive Platform |

## Key Design Patterns

1. **Config-Driven Behavior** — Agent personalities, constraints, and communication styles are defined in YAML files, not hardcoded. Swap a guardrail file to change agent behavior without touching code.

2. **Multi-Turn Conversation** — Agents don't make snap decisions. They ask follow-up questions, gather context, then decide. This mimics real B2B workflows.

3. **Robust LLM Response Handling** — JSON parsing with regex fallback for truncated responses, code-fence stripping, A2A envelope detection. LLMs are unpredictable; the parsing is defensive.

4. **Separate Frontends per Agent** — Each agent has its own themed UI so you can run all 6 agents simultaneously without tab confusion. Color coding: blue (insurance), green/dark (data), amber (audience), purple (incentive).

5. **CLI + UI** — Every use case works headless (CLI with rich terminal output) or via browser (React SPA with progressive message display).
