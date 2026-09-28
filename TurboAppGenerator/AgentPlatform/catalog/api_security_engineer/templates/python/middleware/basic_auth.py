"""
Deterministic HTTP Basic Auth middleware. Only wired in when auth_type == "basic"
(see security_bootstrap.py). Not LLM-generated — auth must be correct every
generation, so credential comparison always uses constant-time hmac.compare_digest.
"""

import base64
import hmac
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_EXEMPT_PATHS = {"/health"}


class BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        username = os.environ.get("API_BASIC_AUTH_USERNAME", "admin")
        password = os.environ.get("API_BASIC_AUTH_PASSWORD", "changeme")

        auth = request.headers.get("authorization", "")
        authorized = False
        if auth.lower().startswith("basic "):
            # try/except deliberately covers ONLY decoding/parsing the header
            # (the one place malformed input can legitimately throw) — NOT
            # call_next(request). Reproduced directly: an unrelated bug deep
            # in a route/repository (a missing `await` on an async DB call)
            # raised an AttributeError from inside call_next(), and because
            # this try/except used to wrap that call too, the exception was
            # silently swallowed here and reported back as a plain 401
            # "Unauthorized" — completely masking a real application bug
            # behind what looked like a credentials problem, with correct
            # credentials, no less. Letting call_next()'s own exceptions
            # propagate normally means a downstream bug now surfaces as an
            # actual 500 with a real traceback, not a misleading 401.
            try:
                decoded = base64.b64decode(auth[6:]).decode("utf-8")
                given_user, _, given_pass = decoded.partition(":")
                authorized = (
                    hmac.compare_digest(given_user, username)
                    and hmac.compare_digest(given_pass, password)
                )
            except Exception:
                authorized = False

        if authorized:
            return await call_next(request)

        return Response(
            status_code=401,
            headers={"WWW-Authenticate": "Basic"},
            content='{"detail":"Unauthorized"}',
            media_type="application/json",
        )
