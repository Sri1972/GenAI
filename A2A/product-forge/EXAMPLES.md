# Product Forge — Example Ideas to Test

Copy any of these into the Product Forge UI or CLI to test the multi-agent pipeline.

---

## Simple / Small Scope

**1. Team Standup Bot**
```
A Slack bot that runs daily standups asynchronously — team members post updates via DM, the bot summarizes blockers and highlights to a channel at 9:30am, and flags anyone who hasn't posted by the deadline.
```

**2. Internal Expense Tracker**
```
A mobile-first web app for employees to photograph receipts, auto-extract amount/vendor/date via OCR, categorize expenses, and submit for manager approval with a one-tap workflow.
```

---

## Medium Complexity

**3. AI-Powered Code Review Assistant**
```
A GitHub App that automatically reviews pull requests — identifies potential bugs, security vulnerabilities, performance issues, and style violations. Provides inline suggestions with explanations and confidence scores. Learns from team's accept/reject patterns over time.
```

**4. Real-Time Collaborative Whiteboard**
```
A browser-based collaborative whiteboard for remote teams with infinite canvas, real-time cursors, sticky notes, drawing tools, shape recognition, and AI-powered diagramming that converts rough sketches into clean diagrams. Supports video presence bubbles and async comments.
```

**5. Customer Health Score Dashboard**
```
A B2B SaaS dashboard that aggregates product usage, support tickets, NPS scores, billing history, and engagement data to compute a real-time customer health score. Alerts CSMs when accounts show churn risk signals and suggests intervention playbooks.
```

---

## Complex / Enterprise

**6. Multi-Tenant API Gateway with Usage-Based Billing**
```
An API gateway platform where B2B customers can register, get API keys, access rate-limited endpoints, view usage analytics, and receive automated invoices based on consumption tiers. Includes admin portal for managing plans, monitoring abuse, and configuring rate limits per customer.
```

**7. Automotive Dealer Inventory Intelligence Platform**
```
A platform for automotive dealers that predicts optimal inventory mix based on local demand signals (search trends, competitor pricing, seasonal patterns, demographic data). Recommends which vehicles to order, price adjustments for aging inventory, and trade-in valuations. Integrates with DMS systems and OEM allocation feeds.
```

**8. Enterprise Document Workflow Engine**
```
A configurable document workflow system where business users can design approval chains, define routing rules based on document metadata (amount, department, type), set SLAs with escalation paths, and track documents through their lifecycle. Supports parallel approvals, conditional branching, delegation, and audit trails for compliance.
```

---

## Automotive / S&P Global Relevant

**9. Connected Vehicle Data Marketplace**
```
A B2B marketplace where OEMs publish anonymized connected vehicle telemetry data (fuel consumption, maintenance alerts, driving patterns by region) and insurance companies, fleet operators, and urban planners can subscribe to curated data products. Includes data quality scoring, usage licensing, and privacy compliance controls.
```

**10. VIN-Based Vehicle History & Valuation API**
```
A developer-facing API platform that provides comprehensive vehicle history (accidents, ownership, recalls, service records) and real-time market valuation based on VIN lookup. Supports batch processing for dealer inventory, webhook notifications for recall updates, and embeddable widgets for consumer-facing sites.
```

---

## CLI Usage

```bash
cd product-forge/backend

# Run interactively (pause between stages)
python cli.py -i "A Slack bot that runs daily standups asynchronously — team members post updates via DM, the bot summarizes blockers to a channel at 9:30am"

# Run a single stage
python cli.py -s ideation "An AI-powered code review assistant for GitHub"

# Run all stages automatically
python cli.py "A mobile expense tracker with receipt OCR and one-tap approval"
```

## Web UI Usage

```bash
# Start the server
start_forge.bat

# Open http://localhost:8010
# Paste any idea above and click "Start Forging"
# Use "Run Next Stage" to step through, or "Run All" for full pipeline
```
