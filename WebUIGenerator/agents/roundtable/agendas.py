"""
Agenda templates for the roundtable.

A meeting can carry an *agenda* — a set of named sections ("buckets"). The Chair organizes the
meeting's outcomes into these buckets at recap time (PM-style minutes) instead of a flat list.
Each template also proposes sensible default people + duration. The user can edit the buckets
before starting, so a template is a starting point, not a cage.

`buckets` are ordered; `people` are persona ids from personas.PERSONAS.
"""

from __future__ import annotations

AGENDA_TEMPLATES = [
    {
        "id": "feature-brainstorm",
        "name": "New feature brainstorming",
        "buckets": ["Problem & why now", "Who it's for", "Ideas on the table",
                    "Trade-offs & risks", "What we'll pursue", "Open questions"],
        "people": ["product", "engineering", "design", "data"],
        "duration": 12,
    },
    {
        "id": "mvp-design",
        "name": "Product MVP design",
        "buckets": ["Core problem", "MVP must-haves", "Explicitly cut (not now)",
                    "Key decisions", "Assumptions to validate", "Open risks"],
        "people": ["product", "design", "engineering", "data"],
        "duration": 12,
    },
    {
        "id": "sprint-planning",
        "name": "Sprint planning",
        "buckets": ["Sprint goal", "Committed work", "Capacity & constraints",
                    "Risks & dependencies", "Deferred / out"],
        "people": ["product", "engineering", "delivery", "quality"],
        "duration": 12,
    },
    {
        "id": "scope-finalization",
        "name": "Scope finalization",
        "buckets": ["In scope", "Out of scope", "Contested (to decide)",
                    "Constraints", "Sign-off decisions", "Follow-ups"],
        "people": ["product", "engineering", "architecture", "delivery"],
        "duration": 12,
    },
    {
        "id": "brainstorm",
        "name": "General brainstorming",
        "buckets": ["The question", "Perspectives raised", "Promising directions",
                    "Concerns", "Agreed", "Still open"],
        "people": ["product", "engineering", "design"],
        "duration": 12,
    },
    {
        "id": "design-review",
        "name": "Architecture / design review",
        "buckets": ["Problem & requirements", "Proposed approach", "Alternatives considered",
                    "Trade-offs", "Decisions", "Risks & unknowns"],
        "people": ["architecture", "engineering", "security", "data"],
        "duration": 12,
    },
    {
        "id": "prioritization",
        "name": "Roadmap / prioritization",
        "buckets": ["Candidates", "Impact vs effort", "Priorities (ranked)",
                    "Cut / deferred", "Dependencies"],
        "people": ["product", "engineering", "delivery", "data"],
        "duration": 12,
    },
    {
        "id": "retro",
        "name": "Retrospective",
        "buckets": ["Went well", "Didn't go well", "Root causes", "Action items", "Owners"],
        "people": ["delivery", "quality", "engineering", "product"],
        "duration": 10,
    },
    {
        "id": "incident-triage",
        "name": "Incident / bug triage",
        "buckets": ["What happened", "Impact", "Root cause",
                    "Immediate fixes", "Preventive actions", "Owners"],
        "people": ["engineering", "quality", "security", "delivery"],
        "duration": 10,
    },
    {
        "id": "go-no-go",
        "name": "Launch go / no-go",
        "buckets": ["Readiness", "Blockers", "Risks", "Decision", "Conditions", "Owners"],
        "people": ["product", "engineering", "quality", "delivery"],
        "duration": 10,
    },
]

_BY_ID = {t["id"]: t for t in AGENDA_TEMPLATES}
# The fallback buckets when a meeting has no agenda set.
DEFAULT_BUCKETS = _BY_ID["brainstorm"]["buckets"]


def templates() -> list[dict]:
    return AGENDA_TEMPLATES


def get(template_id: str) -> dict | None:
    return _BY_ID.get(template_id)
