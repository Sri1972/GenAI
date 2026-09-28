"""
install_security(app) wires deterministic rate-limiting, usage-metering, and (if
configured) basic-auth middleware into the generated FastAPI app.

Appended to the end of src/main.py by the orchestrator (see api_orchestrator.py) —
not LLM-generated, because security/metering infra must work identically every
generation rather than being freehand LLM output.

Middleware added LAST is OUTERMOST in Starlette's stack (wraps everything added
before it), so UsageTrackingMiddleware is added last here — it must see every
response's final status code, including ones rejected by rate-limit or auth.
"""

import os

from dotenv import load_dotenv

from src.middleware.rate_limit import RateLimitMiddleware
from src.middleware.usage_tracking import UsageTrackingMiddleware, usage_router

# Load .env here rather than relying on the LLM-generated main.py to have done so —
# security config must have its values regardless of what main.py does.
load_dotenv()


def _health():
    return {"status": "ok"}


def install_security(app):
    # Registered here (not left to the LLM) so /health is guaranteed to exist —
    # both the rate-limit and basic-auth middleware exempt this exact path, and
    # the generated Dockerfile's HEALTHCHECK depends on it responding.
    app.add_api_route("/health", _health, methods=["GET"])
    app.include_router(usage_router)

    if os.environ.get("API_AUTH_TYPE", "none") == "basic":
        from src.middleware.basic_auth import BasicAuthMiddleware
        app.add_middleware(BasicAuthMiddleware)

    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=int(os.environ.get("RATE_LIMIT_RPM", "100")),
    )

    app.add_middleware(UsageTrackingMiddleware)
