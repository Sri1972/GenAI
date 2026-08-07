"""
MCP client with two behaviours:

1. get_tools(server_key)
   Returns OpenAI tool schemas for the given server. Caches them in memory
   for the lifetime of the process so we only pay the subprocess cost once.

2. LazyMCPCaller(server_key)
   Context manager that holds a slot for an MCP session but does NOT open the
   subprocess until the first call_tool() invocation.  If the LLM answers
   entirely from context no subprocess is ever spawned.
"""

import json
from contextlib import asynccontextmanager, AsyncExitStack
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

MCP_JSON_PATH = Path(__file__).parent.parent / ".mcp.json"

# In-process cache: tool schemas don't change between requests
_tool_schema_cache: dict[str, list[dict]] = {}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_mcp_config(server_key: str) -> StdioServerParameters:
    print(f"[MCP] Loading config: {server_key}")
    with open(MCP_JSON_PATH) as f:
        config = json.load(f)
    servers = config.get("mcpServers", {})
    if server_key not in servers:
        raise ValueError(f"MCP server '{server_key}' not found in .mcp.json")
    srv = servers[server_key]
    print(f"[MCP] Command: {srv['command']}")
    return StdioServerParameters(
        command=srv["command"],
        args=srv.get("args", []),
        env=srv.get("env"),
    )


@asynccontextmanager
async def _open_session(server_key: str):
    params = _load_mcp_config(server_key)
    print(f"[MCP] Spawning subprocess: {server_key} ...")
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print(f"[MCP] Session ready: {server_key}")
            yield session
    print(f"[MCP] Session closed: {server_key}")


def _to_openai_tool(mcp_tool) -> dict:
    return {
        "type": "function",
        "function": {
            "name": mcp_tool.name,
            "description": mcp_tool.description or "",
            "parameters": mcp_tool.inputSchema or {"type": "object", "properties": {}},
        },
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_tools(server_key: str) -> list[dict]:
    """
    Return OpenAI-compatible tool schemas, fetching from MCP once then caching.
    Subsequent calls for the same server_key are instant (no subprocess).
    """
    if server_key not in _tool_schema_cache:
        print(f"[MCP] Tool schema cache miss for {server_key} — fetching ...")
        async with _open_session(server_key) as session:
            result = await session.list_tools()
            _tool_schema_cache[server_key] = [_to_openai_tool(t) for t in result.tools]
        names = [t["function"]["name"] for t in _tool_schema_cache[server_key]]
        print(f"[MCP] Cached {len(names)} tools for {server_key}: {names}")
    else:
        names = [t["function"]["name"] for t in _tool_schema_cache[server_key]]
        print(f"[MCP] Tool schema cache HIT for {server_key}: {names}")
    return _tool_schema_cache[server_key]


async def get_tools_multi(server_keys: list[str]) -> tuple[list[dict], dict[str, str]]:
    """
    Fetch tools from multiple servers and return them merged with a name→server_key routing map.
    Returns (all_tools, tool_server_map).
    """
    all_tools: list[dict] = []
    tool_server_map: dict[str, str] = {}
    for key in server_keys:
        tools = await get_tools(key)
        for t in tools:
            name = t["function"]["name"]
            tool_server_map[name] = key
        all_tools.extend(tools)
    return all_tools, tool_server_map


class LazyMCPCaller:
    """
    Holds lazy MCP sessions keyed by server_key.
    Subprocesses are only started on the first call_tool() for each server.
    Supports routing tool calls across multiple servers via tool_server_map.
    """

    def __init__(self, default_server_key: str, tool_server_map: dict[str, str] | None = None):
        self._default_key = default_server_key
        self._tool_server_map: dict[str, str] = tool_server_map or {}
        self._sessions: dict[str, ClientSession] = {}
        self._stack = AsyncExitStack()

    async def __aenter__(self):
        await self._stack.__aenter__()
        return self

    async def __aexit__(self, *args):
        if self._sessions:
            print(f"[MCP] Closing lazy sessions: {list(self._sessions.keys())}")
        await self._stack.__aexit__(*args)

    async def _get_session(self, server_key: str) -> ClientSession:
        if server_key not in self._sessions:
            print(f"[MCP] First tool call — opening subprocess: {server_key}")
            self._sessions[server_key] = await self._stack.enter_async_context(
                _open_session(server_key)
            )
        return self._sessions[server_key]

    async def call_tool(self, tool_name: str, arguments: dict) -> Any:
        server_key = self._tool_server_map.get(tool_name, self._default_key)
        session = await self._get_session(server_key)

        print(f"[MCP] call_tool: {tool_name} via {server_key} | args: {json.dumps(arguments)[:300]}")
        result = await session.call_tool(tool_name, arguments)
        parts = [c.text for c in result.content if hasattr(c, "text")]
        combined = "\n".join(parts)
        print(f"[MCP] Tool result: {len(combined)} chars")
        return combined
