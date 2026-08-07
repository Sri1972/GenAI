"""
Manages chat sessions persisted as <session_id>.json in the sessions/ folder.

Session file schema:
{
  "session_id": "...",
  "product_code": "CFI",
  "created_at": "2025-...",
  "updated_at": "2025-...",
  "messages": [...]        # full OpenAI message history including system prompt
}
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SESSIONS_DIR = Path(__file__).parent / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)


def _session_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{session_id}.json"


def new_session(product_code: str, messages: list[dict[str, Any]]) -> str:
    """Create a new session, persist it, and return the session_id."""
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    data = {
        "session_id": session_id,
        "product_code": product_code,
        "created_at": now,
        "updated_at": now,
        "messages": messages,
    }
    _session_path(session_id).write_text(json.dumps(data, indent=2))
    return session_id


def load_session(session_id: str) -> dict:
    """Load and return a session. Raises FileNotFoundError if it doesn't exist."""
    path = _session_path(session_id)
    if not path.exists():
        raise FileNotFoundError(session_id)
    return json.loads(path.read_text())


def save_session(session_id: str, messages: list[dict[str, Any]]) -> None:
    """Update the messages and updated_at timestamp for an existing session."""
    data = load_session(session_id)
    data["messages"] = messages
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    _session_path(session_id).write_text(json.dumps(data, indent=2))


def session_exists(session_id: str) -> bool:
    return _session_path(session_id).exists()
