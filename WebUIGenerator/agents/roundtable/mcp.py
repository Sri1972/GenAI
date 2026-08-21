"""MCP servers, wired per persona.

This is the axis the README calls the one that matters. Personas differ by
prompt, by tools, and by what they can actually look at — and the third is
what decides whether a disagreement is real or merely plausible. A Design
voice that can read the actual Figma file is arguing from evidence; one that
cannot is arguing from a stance we wrote for it.

Servers are passed **explicitly** into each persona's session. ``PersonaAgent``
sets ``strict_mcp_config=True``, so nothing ambient on the host leaks in: a
persona gets exactly the servers this meeting granted it, and a meeting is
reproducible on another machine.

Tokens are read from the environment at the moment a meeting starts and go
nowhere else. They are not part of ``MeetingConfig``, not written into
``transcript.json``, and not seeded into any workspace — a meeting records
*which* servers a persona had, never the credential.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable

# Known servers. Each entry says how to reach it and how it takes a token, so
# adding one is a dict rather than a code change.
SERVERS: dict[str, dict[str, str]] = {
    "figma": {
        "type": "http",
        "url": "https://mcp.figma.com/mcp",
        # Tested: a personal access token does **not** work here, however
        # well scoped. The endpoint's own challenge is
        # `www-authenticate: Bearer ... scope="mcp:connect"`, and a PAT
        # cannot carry that scope — a token with every read scope Figma
        # offers still returns 401. It wants an OAuth access token, sent as
        # a bearer. (`vary: X-Figma-Token` in the same response is about
        # cache correctness, not an accepted auth path. It cost a probe to
        # find out.)
        "auth": "bearer",
        "token_env": "FIGMA_OAUTH_TOKEN",
        "token_header": "Authorization",
        "get_token": "https://developers.figma.com/docs/figma-mcp-server/",
        "note": "OAuth access token — a personal access token is rejected.",
    },
    "figma-local": {
        "type": "http",
        # The Dev Mode server inside the Figma desktop app. No token: it
        # borrows the session of whoever is logged into the app. Costs you
        # having the app open, and it answers about the current file.
        "url": "http://127.0.0.1:3845/mcp",
        "auth": "none",
        "get_token": "https://help.figma.com/hc/en-us/articles/32132100833559",
        "note": "Needs the Figma desktop app open with the Dev Mode MCP "
        "server enabled in preferences. No token.",
    },
}


def resolve(
    names: list[str], getenv: Callable[[str], str | None] = os.environ.get
) -> dict[str, Any]:
    """Server configs for ``ClaudeAgentOptions.mcp_servers``.

    A server with no token still gets configured — it will fail at call time
    with the server's own error, which is more useful than us guessing here.
    """
    out: dict[str, Any] = {}
    for name in names:
        spec = SERVERS.get(name)
        if not spec:
            continue
        config: dict[str, Any] = {"type": spec["type"], "url": spec["url"]}
        token = getenv(spec["token_env"])
        if token:
            config["headers"] = {spec["token_header"]: token}
        out[name] = config
    return out


def tool_grants(names: list[str]) -> list[str]:
    """Tool-allowlist entries for those servers.

    Without these the server connects and its tools are silently unusable —
    ``allowed_tools`` is an allowlist, and MCP tools arrive as
    ``mcp__<server>__<tool>``. ``mcp__<server>`` grants all of them; list
    individual tools (``mcp__figma__get_design_context``) to be narrower.
    """
    return [f"mcp__{n}" for n in names if n in SERVERS]


_INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "roundtable-check", "version": "0"},
    },
}


def probe(name: str, getenv: Callable[[str], str | None] = os.environ.get) -> tuple[bool, str]:
    """Ask the server directly whether this token works. Never prints it.

    Worth doing before a meeting rather than during one: an unauthenticated
    server connects, its tools are granted, and the persona simply never gets
    an answer — which reads as an unhelpful model rather than a bad
    credential.
    """
    spec = SERVERS.get(name)
    if not spec:
        return False, f"unknown server {name!r}"

    config = resolve([name], getenv).get(name, {})
    if not config.get("headers"):
        return False, f"no token — set {spec['token_env']} or paste one above"

    request = urllib.request.Request(
        config["url"],
        data=json.dumps(_INITIALIZE).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **config["headers"],
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return True, f"authenticated (HTTP {response.status})"
    except urllib.error.HTTPError as exc:
        body = exc.read(200).decode("utf-8", "replace").strip()
        if exc.code in (401, 403):
            return False, f"rejected (HTTP {exc.code} {body[:60]}) — wrong token or scope"
        return False, f"HTTP {exc.code} {body[:80]}"
    except OSError as exc:
        return False, f"unreachable — {exc}"


def missing_tokens(names: list[str], getenv=os.environ.get) -> list[str]:
    """Servers granted but with no token in the environment."""
    return [
        n
        for n in names
        if n in SERVERS and not getenv(SERVERS[n]["token_env"])
    ]
