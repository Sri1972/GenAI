"""
Backend for the "Try it" tab's chat tester — connects to a running generated
MCP server as a real client, lets an LLM decide which of its tools to call to
answer a plain-language question, and returns the final reply plus a log of
what was actually called.

Adapted from the exact same proven pattern already shipped in
AgentPlatform/catalog/webui_integration_engineer/templates/datachat_api_server.py
(_get_chat_tools/_execute_chat_tool/_run_litellm_chat_stream) — that file is a
GENERATED APP's own DataChat backend for a different purpose (chat grounded in
ingested files or a generated app's own DB); this is the platform-side
equivalent for testing an arbitrary MCP server, so it lives here instead of
being copied from a template meant for generated projects.
"""

import asyncio
import json

from fastmcp import Client

from agents.llm import chat_with_tools

_SYSTEM_PROMPT = (
    "You are a helpful assistant with access to tools that query a live MCP "
    "server's real data. ALWAYS call a tool to fetch real data before "
    "answering a question about that data — never guess or fabricate values. "
    "For questions unrelated to the available tools (e.g. general knowledge "
    "or simple arithmetic), just answer directly without calling a tool."
)


async def run_chat_turn(mcp_url: str, messages: list[dict], max_tool_rounds: int = 5) -> dict:
    """
    messages: the full conversation so far, each {"role": "user"|"assistant", "content": str}.
    Returns {"reply": str, "toolCalls": [{"name": str, "args": dict, "result": str}, ...]}.
    """
    async with Client(mcp_url) as client:
        mcp_tools = await client.list_tools()
        tools_openai = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description or "",
                    "parameters": t.inputSchema,
                },
            }
            for t in mcp_tools
        ]

        conversation: list[dict] = list(messages)
        tool_call_log: list[dict] = []

        for _round in range(max_tool_rounds):
            result = await asyncio.to_thread(chat_with_tools, conversation, tools_openai, _SYSTEM_PROMPT)
            tool_calls = result.get("tool_calls") or []
            if not tool_calls:
                return {"reply": result.get("content") or "", "toolCalls": tool_call_log}

            conversation.append({
                "role": "assistant",
                "content": result.get("content"),
                "tool_calls": [
                    {"id": tc["id"], "type": "function",
                     "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"], default=str)}}
                    for tc in tool_calls
                ],
            })
            for tc in tool_calls:
                try:
                    tool_result = await client.call_tool(tc["name"], tc["arguments"])
                    data = tool_result.data if hasattr(tool_result, "data") else tool_result
                    result_str = data if isinstance(data, str) else json.dumps(data, default=str)
                except Exception as e:
                    result_str = json.dumps({"error": f"Tool execution failed: {e}"})
                tool_call_log.append({"name": tc["name"], "args": tc["arguments"], "result": result_str})
                conversation.append({"role": "tool", "tool_call_id": tc["id"], "content": result_str})

        return {
            "reply": "I wasn't able to answer within the allowed number of tool-call rounds.",
            "toolCalls": tool_call_log,
        }
