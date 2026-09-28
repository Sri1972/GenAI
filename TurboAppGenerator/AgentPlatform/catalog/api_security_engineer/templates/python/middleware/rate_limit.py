"""
Deterministic rate-limiting middleware — backed by the same usage.db every
request is already logged to (see usage_tracking.py), not a separate
in-memory counter. One source of truth for "how many requests has this
client made" — the same data GET /usage reports — and the limit naturally
survives restarts instead of silently resetting (restarting no longer lets a
client dodge it, though see api_orchestrator.py's notes on why that's an
acceptable, even convenient, tradeoff for a dev/test tool if you'd rather
have the old in-memory behavior back).

Adds X-RateLimit-Limit / X-RateLimit-Remaining response headers on every
call (success or 429) — visible in Swagger UI's own response viewer and to
any real client, with no separate call needed to see it.

Not LLM-generated: throttling must behave identically every generation, so this is
a fixed template copied verbatim into every generated API rather than freehand LLM
output (see WebAPIGenerator's api_orchestrator.py security stage).
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .client_id import extract_client_id
from .usage_tracking import RATE_LIMIT_PATH_PREFIX, rate_limit_status


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = 100):
        super().__init__(app)
        self.limit = requests_per_minute
        self.window_seconds = 60

    async def dispatch(self, request: Request, call_next):
        if self.limit <= 0 or not request.url.path.startswith(RATE_LIMIT_PATH_PREFIX):
            return await call_next(request)

        client_id = extract_client_id(request)
        status = rate_limit_status(client_id, self.window_seconds)

        if status["used"] >= status["limit"]:
            return JSONResponse(
                {"detail": "Rate limit exceeded"},
                status_code=429,
                headers={
                    "Retry-After": str(self.window_seconds),
                    "X-RateLimit-Limit": str(status["limit"]),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        # This request isn't logged to api_usage until AFTER it completes (see
        # UsageTrackingMiddleware, the outermost middleware), so `status` above
        # reflects requests before this one — knock one more off for the
        # request currently in flight, once it succeeds.
        response.headers["X-RateLimit-Limit"] = str(status["limit"])
        response.headers["X-RateLimit-Remaining"] = str(max(0, status["remaining"] - 1))
        return response
