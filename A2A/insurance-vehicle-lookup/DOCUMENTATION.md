# Insurance Vehicle Lookup — A2A Demo

---

## Product Overview

### What Is This?

A working prototype demonstrating how an **insurance company's AI agent** queries a **vehicle data provider's AI agent** in real-time to support underwriting decisions — quotes, claims, and renewals — without human data-entry or manual lookups.

This represents how insurance workflows will operate in the near future: automated, cross-organizational data exchange between AI agents, with intelligent risk assessment built in.

### The Business Scenario

When a customer contacts **SecureAuto Insurance** for a quote, claim, or renewal, the insurance agent needs vehicle and owner data to make underwriting decisions. Instead of a human manually querying databases, the insurance AI agent programmatically queries **AutoRegistry** (a vehicle data provider) and gets back structured data including:

- Vehicle specs and history
- Owner driving record
- Financial/lease information
- Loyalty and maintenance scores
- Title status and registration

The insurance agent then applies underwriting rules to make a decision.

### Key Actors

| Actor | Role | Organization Type |
|-------|------|-------------------|
| **SecureAuto Agent** | Insurance underwriter | Insurance company |
| **AutoRegistry Agent** | Vehicle/owner data provider | Data services company |

### Data Available from AutoRegistry

| Category | Data Points |
|----------|-------------|
| **Vehicle** | Year, make, model, trim, mileage, color, engine |
| **Title & History** | Title status (clean/rebuilt/salvage), accident count, recall status |
| **Registration** | State, expiry date, inspection status |
| **Owner Identity** | Name, address, DOB, license number |
| **Driving Record** | Years licensed, violations, accidents, DUI history, suspensions |
| **Financial** | Ownership type (owned/financed/leased), payment history, balance, late payments |
| **Loyalty** | Customer tenure, vehicles owned, brand loyalty score, maintenance adherence, service spend |

### Lookup Methods

The data provider accepts queries via three criteria:

1. **VIN** — Most precise, returns exact vehicle match
2. **License Plate** — State + plate number lookup
3. **Name** — Owner name search (partial match supported)

### Insurance Workflows Supported

| Workflow | What Happens |
|----------|-------------|
| **New Quote** | Customer wants insurance → agent pulls data → calculates risk/premium → approve/decline |
| **Claim** | Customer reports incident → agent verifies vehicle/policy → assess validity → approve/investigate |
| **Renewal** | Policy expiring → agent checks updated data → recalculate risk → adjust premium |

### Underwriting Rules

The insurance agent applies these risk multipliers to a base premium of $1,200/year:

| Factor | Multiplier | Effect |
|--------|-----------|--------|
| Clean driving record | 0.85x | -15% discount |
| 1 violation | 1.0x | No change |
| 2 violations | 1.25x | +25% |
| 3+ violations | 1.6x | +60% |
| Accident history | 1.15x | +15% |
| DUI history | 2.5x | +150% |
| Salvage title | 1.8x | +80% |
| Young driver (<25) | 1.35x | +35% |
| Luxury vehicle | 1.3x | +30% |
| High mileage (>60k) | 1.1x | +10% |
| Poor payment history | 1.2x | +20% |
| Excellent loyalty | 0.9x | -10% |
| Good maintenance | 0.95x | -5% |

**Auto-decline triggers:**
- DUI within 3 years
- Currently suspended license
- Salvage title + high mileage combination
- More than 4 violations in 3 years

### Demo Scenarios (10 total)

| # | Scenario | Risk Profile | Expected Outcome |
|---|----------|-------------|-----------------|
| 1 | Clean record Honda owner | Low risk | Approve with favorable rate |
| 2 | High-risk driver (DUI, violations) | Very high risk | Decline or very high premium |
| 3 | Tesla fender bender claim | Moderate risk | Approve claim |
| 4 | F-150 renewal with new violations | Elevated risk | Approve with premium increase |
| 5 | BMW lease — NYC professional | Low-moderate risk | Approve standard rate |
| 6 | Salvage vehicle theft claim | Fraud indicators | Investigate/refer |
| 7 | Loyal Honda customer renewal | Very low risk | Approve with loyalty discount |
| 8 | Tesla lease buyout new policy | Moderate risk | Approve moderate rate |
| 9 | F-150 hail damage comprehensive | Standard | Approve comprehensive claim |
| 10 | High-mileage rebuilt title | Very high risk | Decline |

### Vehicle Profiles in Database

| Owner | Vehicle | Risk Level | Key Factors |
|-------|---------|-----------|-------------|
| Sarah Chen | 2022 Honda Accord | Low | Clean record, 0 accidents, perfect payments, high loyalty |
| Marcus Johnson | 2021 Tesla Model 3 | Moderate | 1 accident, 1 violation, lease buyout pending, mileage overage |
| Robert Williams | 2020 Ford F-150 | Elevated | 2 accidents, 2 violations, fair maintenance, paid off |
| Jennifer Martinez | 2023 BMW 330i | Low-Moderate | 1 violation, 0 accidents, active lease, excellent maintenance |
| David Kowalski | 2019 Toyota Corolla | Very High | 3 accidents, 4 violations, DUI, salvage title, poor payments, suspended |

### Business Value Demonstrated

1. **Instant data retrieval** — No manual database queries or phone calls
2. **Risk-aware intelligence** — Data provider proactively flags concerns
3. **Consistent underwriting** — Same rules applied every time, no human bias
4. **Audit compliance** — Complete trail of data requests and decisions
5. **Cross-org security** — Data shared only with validated business purpose
6. **Scalability** — Process hundreds of quotes/claims simultaneously

---

## Technical Documentation

### Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         A2A Protocol Layer (HTTP/JSON)                         │
├───────────────────────────────────────┬──────────────────────────────────────┤
│       SecureAuto Insurance Agent      │      AutoRegistry Data Agent          │
│       (Port 8003)                     │      (Port 8004)                      │
│                                       │                                       │
│  ┌─────────────────────────────┐      │   ┌─────────────────────────────┐    │
│  │   FastAPI Server             │      │   │   FastAPI Server             │    │
│  │                              │      │   │                              │    │
│  │  /a2a/agent-card       GET   │      │   │  /a2a/agent-card       GET   │    │
│  │  /insurance/process    POST  │──────┼──►│  /a2a/message          POST  │    │
│  └──────────┬───────────────────┘      │   └──────────┬───────────────────┘    │
│             │                          │              │                        │
│  ┌──────────▼───────────────────┐      │   ┌──────────▼───────────────────┐    │
│  │  LLM: Risk Assessment        │      │   │  LLM: Data Formatting         │    │
│  │  + Underwriting Decision      │      │   │  + Risk Flag Identification   │    │
│  │  (Claude Sonnet 4.5)         │      │   │  (Claude Sonnet 4.5)          │    │
│  └──────────────────────────────┘      │   └──────────────────────────────┘    │
│                                        │              │                        │
│                                        │   ┌──────────▼───────────────────┐    │
│                                        │   │  Vehicle Database (in-memory)  │    │
│                                        │   │  5 vehicles, indexed by:       │    │
│                                        │   │  • VIN  • Plate  • Name        │    │
│                                        │   └──────────────────────────────┘    │
└───────────────────────────────────────┴──────────────────────────────────────┘
```

### File Structure

```
insurance-vehicle-lookup/
├── a2a_protocol.py            # Message format and conversation state
├── autoregistry_agent.py      # Data provider agent (port 8004)
├── secureauto_agent.py        # Insurance agent (port 8003)
├── llm_client.py              # LiteLLM proxy client
├── run_scenario.py            # 10 scenarios with session tracking
├── requirements.txt           # Python dependencies
└── DOCUMENTATION.md           # This file
```

### Workflow Sequence

```
Customer Request
       │
       ▼
┌─────────────────┐     data_request      ┌──────────────────┐
│  SecureAuto      │─────────────────────►│  AutoRegistry      │
│  (Port 8003)     │                       │  (Port 8004)       │
│                  │◄─────────────────────│                    │
│                  │     data_response     │  • VIN lookup       │
│                  │     + risk_flags      │  • Plate lookup     │
│  • Apply rules   │                       │  • Name lookup      │
│  • Calc premium  │                       └──────────────────┘
│  • Make decision │
└────────┬─────────┘
         │
         ▼
  Underwriting Decision
  (approve/decline/refer)
```

### A2A Protocol

#### Message Types (Insurance-specific)

| Type | Direction | Purpose |
|------|-----------|---------|
| `data_request` | Insurance → Registry | Request vehicle/owner data |
| `data_response` | Registry → Insurance | Return structured data + risk flags |
| `verification_request` | Registry → Insurance | Ask for additional authorization |
| `verification_response` | Insurance → Registry | Provide authorization proof |
| `risk_assessment` | Internal | Document risk analysis |
| `quote_decision` | Internal | Final quote/premium decision |
| `claim_decision` | Internal | Claim approval/denial |
| `error` | Either direction | Data not found or invalid request |

#### Data Request Metadata

```json
{
  "lookup_criteria": {
    "vin": "1HGCM82633A004352"
  },
  "purpose": "new_quote"
}
```

Or by plate:
```json
{
  "lookup_criteria": {
    "license_plate": "TX-MKP4492"
  },
  "purpose": "claim"
}
```

Or by name:
```json
{
  "lookup_criteria": {
    "name": "Sarah Chen"
  },
  "purpose": "renewal"
}
```

#### Data Response Metadata

```json
{
  "data": { /* full vehicle/owner record */ },
  "risk_flags": ["salvage_title", "dui_history", "poor_payment_history"],
  "data_confidence": 95
}
```

### Database Schema

The in-memory vehicle database stores records with this structure:

```python
{
    "vin": str,
    "year": int,
    "make": str,
    "model": str,
    "trim": str,
    "color": str,
    "engine": str,
    "mileage": int,
    "title_status": "clean" | "rebuilt" | "salvage",
    "salvage_history": bool,
    "accident_count": int,
    "recall_status": str,
    "license_plate": str,
    "registration_state": str,
    "registration_expiry": str,  # ISO date
    "inspection_status": "passed" | "expired",
    "owner": {
        "name": str,
        "address": str,
        "dob": str,
        "license_number": str,
        "driving_record": {
            "years_licensed": int,
            "violations_3yr": int,
            "accidents_5yr": int,
            "dui_history": bool,
            "suspended_ever": bool,
        }
    },
    "financial": {
        "ownership_type": "owned_outright" | "financed" | "leased",
        "lienholder": str | None,
        "payment_history": "perfect" | "good" | "poor",
        "late_payments_count": int,
        # ... additional fields vary by ownership type
    },
    "loyalty": {
        "customer_since": str,
        "vehicles_owned_total": int,
        "brand_loyalty_score": int,  # 0-100
        "service_at_dealer_pct": int,
        "maintenance_adherence": "excellent" | "good" | "fair" | "poor",
        "total_service_spend": int,
        "referrals_made": int,
    }
}
```

### Lookup Indexes

Three indexes support the lookup methods:

```python
# Primary: VIN → full record
VEHICLE_DATABASE = {"1HGCM82633A004352": {...}, ...}

# Secondary: License plate → VIN
PLATE_INDEX = {"CA-7KBR231": "1HGCM82633A004352", ...}

# Secondary: Owner name (lowercase) → VIN
NAME_INDEX = {"sarah chen": "1HGCM82633A004352", ...}
```

Plate and name lookups support partial matching.

### LLM Usage

**AutoRegistry Agent** uses the LLM to:
- Format raw data into professional, readable summaries
- Proactively identify and flag risk indicators
- Provide data confidence scores
- Add contextual commentary relevant to insurance use cases

**SecureAuto Agent** uses the LLM to:
- Parse customer requests and identify lookup criteria
- Analyze returned data against underwriting rules
- Calculate premiums with applicable multipliers and discounts
- Generate human-readable decision explanations
- Determine edge cases that require human underwriter review

### Running the Demo

```bash
# Prerequisites
pip install -r requirements.txt
# Ensure ../.env has LiteLLM credentials

# Start agents (separate terminals)
python autoregistry_agent.py   # Terminal 1 → port 8004
python secureauto_agent.py     # Terminal 2 → port 8003

# Run scenarios
python run_scenario.py              # Random (non-repeating)
python run_scenario.py 2            # Specific scenario (#1-10)
python run_scenario.py --list       # Show session status
python run_scenario.py --all        # All 10 sequentially
python run_scenario.py --reset      # Reset session
```

### API Endpoints

#### SecureAuto Insurance Agent (Port 8003)

| Method | Path | Parameters | Description |
|--------|------|-----------|-------------|
| GET | `/a2a/agent-card` | — | Agent discovery |
| POST | `/insurance/process-request` | `workflow_type`, `lookup_by`, `lookup_value`, `customer_context` | Full underwriting workflow |

**Query Parameters for `/insurance/process-request`:**
- `workflow_type`: `new_quote` | `claim` | `renewal`
- `lookup_by`: `vin` | `plate` | `name`
- `lookup_value`: The VIN, plate number, or owner name
- `customer_context`: Free-text description of the customer's situation

#### AutoRegistry Data Agent (Port 8004)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/a2a/agent-card` | Agent discovery |
| POST | `/a2a/message` | Receive data requests, return vehicle/owner data |

### Response Format

The `/insurance/process-request` endpoint returns:

```json
{
  "conversation_id": "uuid",
  "workflow_type": "new_quote",
  "status": "complete",
  "data_provider_response": {
    "body": "Data summary from AutoRegistry...",
    "risk_flags": ["high_mileage", "multiple_violations"],
    "data_confidence": 92
  },
  "underwriting_decision": {
    "decision": "approve",
    "annual_premium": 1560,
    "multipliers_applied": ["two_violations: 1.25x", "high_mileage: 1.1x"],
    "discounts_applied": ["good_maintenance: 0.95x"]
  },
  "explanation": "Human-readable decision explanation...",
  "transcript": [
    {"step": "data_request", "to": "AutoRegistry", "criteria": {...}},
    {"step": "data_received", "from": "AutoRegistry", "risk_flags": [...]},
    {"step": "decision", "result": {...}}
  ]
}
```

### Session Tracking

Temp file: `%TEMP%/a2a_insurance_session.json`

Stores a list of scenario IDs (1–10) that have been run. Scenarios won't repeat until all 10 are exhausted or `--reset` is called.

### Dependencies

| Package | Purpose |
|---------|---------|
| `fastapi` | HTTP server framework |
| `uvicorn` | ASGI server |
| `httpx` | HTTP client for inter-agent communication |
| `openai` | OpenAI-compatible client (for LiteLLM proxy) |
| `python-dotenv` | Environment variable management |
| `pydantic` | Data validation and serialization |
| `rich` | Terminal output formatting |

### Extending the Demo

**Add a new vehicle record:**
1. Add entry to `VEHICLE_DATABASE` in `autoregistry_agent.py`
2. It auto-indexes by plate and owner name

**Add a new scenario:**
1. Add entry to `SCENARIOS` list in `run_scenario.py`
2. Ensure the lookup criteria matches a record in the database

**Add new data fields:**
1. Add to vehicle record schema in `autoregistry_agent.py`
2. Update the system prompt to describe new fields
3. Update underwriting rules if applicable

**Connect a real database:**
1. Replace `VEHICLE_DATABASE` dict with database queries
2. Update `lookup_vehicle()` function to query the DB
3. Add connection pooling and error handling

---

## Glossary

### Insurance Workflows

| Term | Definition |
|------|-----------|
| **New Quote** | Customer requesting insurance pricing for a vehicle they own or are about to purchase. Requires vehicle history lookup to assess risk. |
| **Claim** | Customer reporting an incident (accident, theft, damage) and requesting coverage payout. Requires vehicle data to verify ownership and assess legitimacy. |
| **Renewal** | Existing policy approaching expiration. Agent re-evaluates risk based on updated vehicle data (new accidents, mileage changes, modifications). |
| **Underwriting** | The process of evaluating risk and deciding whether to insure (and at what price). The core decision: approve, decline, or refer with conditions. |
| **Premium** | The price the customer pays for insurance coverage, typically expressed as annual cost. Higher risk = higher premium. |

### Underwriting Decisions

| Term | Definition |
|------|-----------|
| **Approve** | Accept the risk. Issue the policy at the quoted premium. |
| **Approve with Conditions** | Accept but with requirements (e.g., "install dashcam", "provide inspection within 30 days", "exclude modifications from coverage"). |
| **Decline** | Reject the application. Too risky. Common reasons: salvage title, excessive claims history, high-risk modifications. |
| **Refer** | Escalate to a human underwriter for manual review. Used for edge cases the AI agent isn't confident about. |

### Vehicle Data

| Term | Definition |
|------|-----------|
| **VIN** | Vehicle Identification Number — a unique 17-character code identifying every vehicle manufactured. Decodes to make, model, year, engine, assembly plant. |
| **License Plate** | State-issued registration identifier. Can be used to look up VIN and owner information. |
| **Title Status** | Legal ownership classification: Clean (normal), Salvage (declared total loss), Rebuilt (salvage that's been repaired), Lemon (manufacturer buyback due to defects). |
| **Accident History** | Record of reported collisions, including severity, repair cost, and whether airbags deployed. Major factor in risk assessment. |
| **Odometer Reading** | Current mileage. High mileage = more wear = higher mechanical failure risk. Also used to detect rollback fraud. |
| **Lien** | A financial claim on the vehicle (e.g., an auto loan). Lienholder is typically listed as loss payee on the insurance policy. |

### Risk Assessment

| Term | Definition |
|------|-----------|
| **Risk Flags** | Indicators of elevated risk discovered during vehicle data lookup. Examples: prior total loss, frame damage, flood damage, odometer discrepancy. |
| **Data Confidence** | Percentage score indicating how complete/reliable the vehicle data is. Low confidence (< 60%) triggers additional verification requirements. |
| **Loss History** | Record of prior insurance claims on a vehicle or by an owner. Frequent claims = higher risk. |
| **Modification** | Aftermarket changes to a vehicle (lift kits, engine tunes, custom exhaust). Some modifications void coverage or increase premiums. |
| **Salvage Title** | Legal designation that a vehicle was declared a total loss by an insurance company. Even if rebuilt, it carries permanent risk stigma. |
| **Risk Multiplier** | A factor applied to the base premium to reflect specific risk indicators. For example, DUI history = 2.5x multiplier (+150% premium increase). |

### Lookup Methods

| Term | Definition |
|------|-----------|
| **VIN Lookup** | Querying vehicle records by the 17-digit VIN. Most reliable method — returns exact vehicle match. |
| **Plate Lookup** | Querying by license plate number + state. Resolves to VIN, then proceeds as VIN lookup. Less reliable (plates can be transferred). |
| **Owner Lookup** | Querying by owner name. Least specific — may return multiple vehicles. Used when VIN/plate unavailable. |

### A2A Protocol

| Term | Definition |
|------|-----------|
| **Agent Card** | JSON document describing an agent's identity, capabilities, and endpoint. Used for discovery between SecureAuto and AutoRegistry. |
| **Data Request** | SecureAuto asking AutoRegistry for vehicle/owner information. Includes lookup type and query value. |
| **Info Request** | Follow-up question from SecureAuto asking for additional details (e.g., "What was the repair cost for the 2021 accident?"). |
| **Multi-Turn** | The conversation pattern where SecureAuto asks follow-ups before rendering a decision, rather than deciding on first response alone. |
| **Conversation** | A full exchange from initial lookup through decision. Typically 2-4 rounds. Tracked by conversation ID. |
