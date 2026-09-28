"""
Deterministic usage-metering middleware — logs every request to a local SQLite
usage.db and exposes GET /usage with aggregate counts.

Not LLM-generated: metering must be present and correct on every generation, not
occasionally forgotten by a freehand LLM security stage (see WebAPIGenerator's
api_orchestrator.py security stage).
"""

import os
import sqlite3
import time
from pathlib import Path

from fastapi import APIRouter
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .client_id import extract_client_id

# src/middleware/usage_tracking.py -> project root
DB_PATH = Path(__file__).resolve().parent.parent.parent / "usage.db"

# Shared with rate_limit.py so the two can never drift: what counts toward
# being BLOCKED must be the exact same thing counted in the "used" total
# reported below. An allowlist, not a blocklist — this platform's own
# architect prompt mandates business endpoints be URL-versioned under
# /api/v1/ (api_architect's "API versioning via URL path"), so
# anything else — favicon, health, docs, usage, the root path, or any other
# infra/browser noise nobody thought to list — is excluded by construction,
# not by trying to enumerate every possible non-business path one at a time.
RATE_LIMIT_PATH_PREFIX = "/api/"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    # WAL mode lets readers (the rate limiter now queries this table on every
    # request — see rate_limit.py) proceed without blocking on the writer
    # this middleware itself is about to become, and vice versa.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS api_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            client_id TEXT,
            method TEXT,
            path TEXT,
            status_code INTEGER,
            duration_ms REAL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_api_usage_client_ts ON api_usage(client_id, ts)")
    return conn


class UsageTrackingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000
        try:
            conn = _connect()
            conn.execute(
                "INSERT INTO api_usage (ts, client_id, method, path, status_code, duration_ms) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    time.time(),
                    extract_client_id(request),
                    request.method,
                    request.url.path,
                    response.status_code,
                    duration_ms,
                ),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass  # usage logging must never break the actual request
        return response


def rate_limit_status(client_id: str, window_seconds: int = 60) -> dict:
    """Shared by RateLimitMiddleware (to decide allow/block) and GET /usage
    below (to report the calling client's own quota) — one query against the
    same table both already read/write, instead of a second, separate
    counter that could drift from what /usage shows."""
    limit = int(os.environ.get("RATE_LIMIT_RPM", "100"))
    if limit <= 0:
        return {"limit": 0, "windowSeconds": window_seconds, "used": 0, "remaining": None}
    cutoff = time.time() - window_seconds
    conn = _connect()
    try:
        used = conn.execute(
            "SELECT COUNT(*) FROM api_usage WHERE client_id = ? AND ts > ? AND path LIKE ?",
            (client_id, cutoff, f"{RATE_LIMIT_PATH_PREFIX}%"),
        ).fetchone()[0]
    finally:
        conn.close()
    return {
        "limit": limit,
        "windowSeconds": window_seconds,
        "used": used,
        "remaining": max(0, limit - used),
    }


usage_router = APIRouter()


@usage_router.get("/usage")
def get_usage(request: Request):
    conn = _connect()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM api_usage")
    total = cur.fetchone()[0]

    cur.execute("SELECT path, COUNT(*) FROM api_usage GROUP BY path ORDER BY COUNT(*) DESC LIMIT 20")
    by_endpoint = {row[0]: row[1] for row in cur.fetchall()}

    cur.execute("SELECT client_id, COUNT(*) FROM api_usage GROUP BY client_id ORDER BY COUNT(*) DESC LIMIT 20")
    by_client = {row[0]: row[1] for row in cur.fetchall()}

    cutoff = time.time() - 86400
    cur.execute("SELECT COUNT(*) FROM api_usage WHERE ts >= ?", (cutoff,))
    last_24h = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM api_usage WHERE status_code >= 400")
    errors = cur.fetchone()[0]

    # Recent activity — method/path/status/timing only, never request/response
    # bodies (those aren't captured at all; see UsageTrackingMiddleware above).
    cur.execute(
        "SELECT ts, client_id, method, path, status_code, duration_ms "
        "FROM api_usage ORDER BY id DESC LIMIT 20"
    )
    recent = [
        {
            "ts": row[0], "client_id": row[1], "method": row[2],
            "path": row[3], "status_code": row[4], "duration_ms": round(row[5], 1),
        }
        for row in cur.fetchall()
    ]

    conn.close()
    return {
        "total_requests": total,
        "requests_last_24h": last_24h,
        "error_count": errors,
        "error_rate": round(errors / total, 4) if total else 0.0,
        "by_endpoint": by_endpoint,
        "by_client": by_client,
        "recent": recent,
        # The CALLING client's own current quota — piggybacks on this
        # already-happening request/response instead of a dedicated endpoint.
        "rate_limit": rate_limit_status(extract_client_id(request)),
    }


@usage_router.post("/usage/reset")
def reset_usage():
    """
    Wipes the usage log entirely — both the rate-limit counter and the
    Total Requests/Recent Activity history, since they're now backed by the
    same table on purpose (see rate_limit_status). A dev/test convenience,
    not a production audit feature: a real system would never want to lose
    this history, but restarting used to give an easy "start clean" reset
    before the rate limiter moved off in-memory state, and this is that same
    convenience back. Not itself rate-limited (path doesn't start with
    /api/) — still requires valid Basic Auth if auth_type=basic, same as
    every other non-business route.
    """
    conn = _connect()
    conn.execute("DELETE FROM api_usage")
    conn.commit()
    conn.close()
    return {"reset": True}
