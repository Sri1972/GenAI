"""
Data API -- Serves audience, incentive, and campaign data from JSON files.

Lightweight FastAPI service that provides a clean REST interface to the
data layer. Both agents and the MCP server consume this API.

Runs on port 8007.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s [DATA-API] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("data-api")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

app = FastAPI(title="Audience-Incentive Data API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"{request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"  -> {response.status_code}")
    return response


def load_json(filename: str) -> dict | list:
    path = DATA_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Data file not found: {filename}")
    return json.loads(path.read_text(encoding="utf-8"))


# ─── Segments ─────────────────────────────────────────────────────────────────


@app.get("/api/segments")
def list_segments():
    """List all audience segments."""
    segments = load_json("audience_segments.json")
    return {"segments": list(segments.values()), "count": len(segments)}


@app.get("/api/segments/{segment_id}")
def get_segment(segment_id: str):
    """Get a specific audience segment by ID."""
    segments = load_json("audience_segments.json")
    if segment_id not in segments:
        raise HTTPException(status_code=404, detail=f"Segment not found: {segment_id}")
    return segments[segment_id]


# ─── Incentive Programs ───────────────────────────────────────────────────────


@app.get("/api/programs")
def list_programs(
    program_type: str = Query(None, description="Filter by type: cash_back, apr, lease, rebate, conquest"),
    stackable_only: bool = Query(False, description="Only return stackable programs"),
    active_only: bool = Query(True, description="Exclude expired programs"),
):
    """List incentive programs with optional filters."""
    programs = load_json("incentive_programs.json")
    results = list(programs.values())

    today = datetime.now().strftime("%Y-%m-%d")

    if active_only:
        results = [p for p in results if not p["expiry"] or p["expiry"] >= today]

    if program_type:
        results = [p for p in results if p["type"] == program_type]

    if stackable_only:
        results = [p for p in results if p["stackable"]]

    return {"programs": results, "count": len(results)}


@app.get("/api/programs/{program_id}")
def get_program(program_id: str):
    """Get a specific incentive program by ID."""
    programs = load_json("incentive_programs.json")
    if program_id not in programs:
        raise HTTPException(status_code=404, detail=f"Program not found: {program_id}")
    return programs[program_id]


@app.post("/api/programs/match")
def match_programs(criteria: dict):
    """Match incentive programs to audience criteria.

    Accepts criteria like:
    {
        "segment_id": "truck_loyalists",
        "campaign_goal": "conquest",
        "credit_score": 710,
        "has_trade_in": true,
        "region": "Southeast"
    }
    """
    programs = load_json("incentive_programs.json")
    segments = load_json("audience_segments.json")

    segment_id = criteria.get("segment_id", "")
    campaign_goal = criteria.get("campaign_goal", "")
    credit_score = criteria.get("credit_score")
    age = criteria.get("age")
    has_trade_in = criteria.get("has_trade_in", False)
    returning_lessee = criteria.get("returning_lessee", False)
    region = criteria.get("region", "").upper()

    # Derive additional context from segment profile
    segment = segments.get(segment_id, {})
    if not credit_score and segment:
        credit_score = segment.get("avg_credit_score")
    if has_trade_in is None and segment:
        has_trade_in = segment.get("trade_in_likely", False)

    today = datetime.now().strftime("%Y-%m-%d")
    matched = []

    for prog in programs.values():
        # Check expiry
        if prog["expiry"] and prog["expiry"] < today:
            continue

        # Check segment alignment
        segment_match = False
        eligible_segs = prog["eligible_segments"]
        search_terms = [segment_id, campaign_goal]
        for term in search_terms:
            if term:
                for eligible in eligible_segs:
                    if term in eligible or eligible in term:
                        segment_match = True
                        break
            if segment_match:
                break
        if not search_terms[0] and not search_terms[1]:
            segment_match = True

        if not segment_match:
            continue

        # Check credit score
        min_credit = prog["conditions"].get("min_credit_score")
        if min_credit and credit_score and credit_score < min_credit:
            continue

        # Check age
        max_age = prog["conditions"].get("max_age")
        if max_age and age and age > max_age:
            continue

        # Check returning lessee requirement
        if prog["conditions"].get("returning_lessee") and not returning_lessee:
            continue

        # Check trade-in requirement
        if prog["conditions"].get("requires_trade_in") and not has_trade_in:
            continue

        # Check region
        if region and prog["region"] != "nationwide":
            prog_regions = [r.strip().upper() for r in prog["region"].split(",")]
            if region not in prog_regions:
                continue

        matched.append(prog)

    # Calculate stacking
    stackable = [p for p in matched if p["stackable"]]
    non_stackable = [p for p in matched if not p["stackable"]]
    total_value = sum(p["amount"] for p in stackable if p["amount"])
    total_margin_impact = sum(p["margin_impact_pct"] for p in stackable)

    return {
        "matched_programs": matched,
        "count": len(matched),
        "stacking_analysis": {
            "stackable_count": len(stackable),
            "non_stackable_count": len(non_stackable),
            "total_stackable_value": total_value,
            "total_margin_impact_pct": round(total_margin_impact, 1),
        },
    }


# ─── Campaign Cases ───────────────────────────────────────────────────────────


@app.get("/api/campaigns")
def list_campaigns(
    goal: str = Query(None, description="Filter by goal: conquest, volume, retention"),
    segment_id: str = Query(None, description="Filter by segment ID"),
):
    """List campaign cases with optional filters."""
    campaigns = load_json("campaign_cases.json")

    if goal:
        campaigns = [c for c in campaigns if c["campaign_goal"] == goal]

    if segment_id:
        campaigns = [c for c in campaigns if c["segment_id"] == segment_id]

    return {"campaigns": campaigns, "count": len(campaigns)}


@app.get("/api/campaigns/{campaign_id}")
def get_campaign(campaign_id: int):
    """Get a specific campaign case by ID."""
    campaigns = load_json("campaign_cases.json")
    campaign = next((c for c in campaigns if c["id"] == campaign_id), None)
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign not found: {campaign_id}")
    return campaign


# ─── Health ───────────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "audience-incentive-data-api",
        "port": 8007,
        "data_files": [f.name for f in DATA_DIR.glob("*.json")],
    }


if __name__ == "__main__":
    import uvicorn
    print("Starting Data API on port 8007...")
    uvicorn.run(app, host="0.0.0.0", port=8007)
