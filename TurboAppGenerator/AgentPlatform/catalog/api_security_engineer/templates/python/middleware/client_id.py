"""Shared client-identification used by rate_limit.py and usage_tracking.py so both
middlewares bucket the same request under the same identity."""

import base64


def extract_client_id(request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("basic "):
        try:
            decoded = base64.b64decode(auth[6:]).decode("utf-8", errors="replace")
            username = decoded.split(":", 1)[0]
            return f"user:{username}"
        except Exception:
            pass
    if request.client and request.client.host:
        return f"ip:{request.client.host}"
    return "unknown"
