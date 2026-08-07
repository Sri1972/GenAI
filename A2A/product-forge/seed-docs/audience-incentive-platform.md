# Product Brief: Automotive Campaign Incentive Optimizer

## What We're Building

An AI-powered platform where two specialized agents collaborate in real-time to find the optimal incentive package for automotive marketing campaigns. One agent understands customer segments (demographics, buying behavior, motivations). The other agent knows all available incentive programs (rebates, financing deals, loyalty bonuses) and their eligibility/stacking rules. They negotiate across multiple rounds — just like a real marketing strategist working with an incentive analyst — and deliver a final recommendation with projected ROI.

## The Problem

Today, when a dealer or OEM marketing team wants to launch a campaign targeting a specific customer segment (e.g., "truck loyalists in the Southeast" or "EV-curious millennials on the West Coast"), it takes days of back-and-forth between marketing strategists and incentive analysts to figure out which offers to combine, what's eligible, what stacks, and whether it fits the budget. This is slow, inconsistent, and doesn't scale.

## Target Users

- OEM regional marketing managers planning quarterly campaigns
- Dealer group marketing teams running local promotions
- Incentive planning analysts who manage program budgets

## Core Capabilities

1. **Audience Segmentation & Profiling** — Pre-built customer segments (truck loyalists, EV-curious millennials, budget first-time buyers, luxury downsizers, lease churners) with demographics, credit profiles, motivations, and purchase cycles.

2. **Incentive Program Matching** — A database of active programs (OEM rebates, dealer cash, special APR financing, loyalty/conquest bonuses, lease specials, government EV credits) with eligibility criteria and stacking rules.

3. **Multi-Turn Agent Negotiation** — The audience agent sends a segment profile + campaign goal to the incentive agent. The incentive agent responds with available programs. The audience agent asks follow-up questions (expiry dates, regional restrictions, credit requirements). After 2-4 rounds, the audience agent synthesizes a final recommendation.

4. **Campaign Goals** — Support three campaign types:
   - Conquest: steal customers from competitors ($3,000-$5,000/unit budget)
   - Volume: move maximum units regardless of source ($1,500-$5,000/unit)
   - Retention: keep existing customers from defecting ($2,000-$3,000/unit)

5. **Guardrails & Compliance** — Never recommend expired programs, never exceed budget per unit, never stack incompatible programs, maintain minimum dealer margin (3%).

6. **ROI Projection** — Every recommendation includes projected conversion rate, cost per unit, and return on investment ratio.

## Key Technical Requirements

- Two independent AI agents communicating via a standardized agent-to-agent protocol (JSON over HTTP)
- Each agent has its own UI showing real-time conversation flow
- LLM-powered reasoning for both agents (strategy generation + incentive matching)
- Agent discovery via "agent cards" (identity, capabilities, endpoints)
- Config-driven agent behavior (skills, guardrails, guidelines in external YAML files)
- In-memory data store for segments, programs, and campaign scenarios
- Full conversation transcript for audit trail
- Support 10 pre-built campaign scenarios for demo purposes
- CLI runner for automated scenario execution

## Example Scenario

Campaign: "Steal Truck Buyers from Competition"
- Segment: Truck Loyalists (male 35-55, rural/suburban, income $75K, credit 710)
- Goal: Conquest
- Region: Southeast
- Budget: $3,500/unit

Expected output: A recommended incentive stack (e.g., Q3 Conquest Bonus + Dealer Cash = $4,500 combined), eligibility confirmation, stacking validation, and projected 12:1 ROI.

## Non-Functional Requirements

- Response time: Full multi-turn conversation completes in under 30 seconds
- Both agent UIs update in real-time via streaming
- System should work behind a corporate proxy (LiteLLM-based LLM access)
- All agent behavior configurable without code changes (YAML configs)
- Session tracking to avoid repeating demo scenarios
