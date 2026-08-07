"""
LLM agentic loop: Azure OpenAI drives tool selection; MCP executes tools.

The MCP subprocess is opened LAZILY — only when the LLM actually calls a tool.
If the LLM can answer from session history, no subprocess is spawned at all.
"""

import json
import os
import re
from pathlib import Path
from typing import Any

from openai import AsyncAzureOpenAI

from mcp_client import LazyMCPCaller, get_tools_multi

MAX_TURNS = 10
CHARTS_SERVER_KEY = "d3-charts"
CHARTS_OUTPUT_DIR = str(Path(__file__).resolve().parent / "html-charts")

SYSTEM_PROMPT = f"""You are AskMobility, an expert automotive data assistant.
Answer the user's question by calling the available tools as needed.
Think step-by-step: first identify which tool(s) to call, call them, interpret
the results, and then provide a clear, concise final answer to the user.
Always base your final answer on the tool results — do not guess.
If the answer is already present in the conversation history, answer directly
without calling any tools.

Format your final answer in Markdown: use tables for tabular data, bullet lists
for enumerations, bold for key figures, and headers to separate sections when
the response is long.

Only call chart tools (render_chart_from_dataset, create_bar_chart, etc.) when the
user explicitly asks for a chart, graph, or visualisation. Do NOT call chart tools
for plain data questions. When you do call a chart tool, ALWAYS pass
output_dir="{CHARTS_OUTPUT_DIR}" and include the returned file path verbatim in
your final answer."""


def _extract_chart_path(messages: list[dict[str, Any]]) -> str | None:
    """Return the first chart HTML file path found in tool result messages."""
    for msg in reversed(messages):
        if msg.get("role") == "tool":
            content = msg.get("content", "")
            # Chart tools return a path ending in .html
            match = re.search(r'([A-Za-z]:[^\n"\']+\.html|/[^\n"\']+\.html)', content)
            if match:
                return match.group(1)
    return None


def _get_client() -> AsyncAzureOpenAI:
    return AsyncAzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
    )


def _build_initial_messages(nlq: str) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": nlq},
    ]


async def run_agent(
    nlq: str,
    mcp_server_key: str,
    history: list[dict[str, Any]] | None = None,
) -> tuple[str, str | None, list[dict[str, Any]]]:
    """
    Run the agentic loop. Returns (answer, chart_path, updated_messages).

    - Tools from both the data server and the d3-charts server are available.
    - Subprocesses are opened lazily on first tool call per server.
    - chart_path is the HTML file written by the chart tool, or None.
    """
    print(f"[Agent] Starting | mcp={mcp_server_key} | nlq={nlq[:80]}")

    client = _get_client()
    deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]
    print(f"[Agent] Deployment: {deployment}")

    if history:
        messages: list[dict[str, Any]] = history + [{"role": "user", "content": nlq}]
        print(f"[Agent] Continuing session — {len(history)} prior messages")
    else:
        messages = _build_initial_messages(nlq)
        print("[Agent] Fresh session")

    # Fetch tool schemas from both data server and charts server
    tools, tool_server_map = await get_tools_multi([mcp_server_key, CHARTS_SERVER_KEY])

    # Lazy MCP caller: routes each tool to the correct server subprocess
    async with LazyMCPCaller(mcp_server_key, tool_server_map) as caller:
        for turn in range(1, MAX_TURNS + 1):
            print(f"[Agent] LLM turn {turn}/{MAX_TURNS} ...")
            response = await client.chat.completions.create(
                model=deployment,
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )

            message = response.choices[0].message
            finish_reason = response.choices[0].finish_reason
            print(f"[Agent] finish_reason: {finish_reason}")

            # LLM answered without tools — done
            if not message.tool_calls:
                answer = (message.content or "").replace("\\n", "\n").replace("\\t", "\t")
                print(f"[Agent] Answer ready ({len(answer)} chars)")
                messages.append({"role": "assistant", "content": answer})
                chart_path = _extract_chart_path(messages)
                return answer, chart_path, messages

            # LLM wants tools — dispatch to the appropriate server
            tool_names = [tc.function.name for tc in message.tool_calls]
            print(f"[Agent] Tool calls: {tool_names}")
            messages.append(message.model_dump(exclude_unset=True))

            tool_error = False
            for tc in message.tool_calls:
                args = json.loads(tc.function.arguments)
                tool_result = await caller.call_tool(tc.function.name, args)
                result_str = str(tool_result)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_str,
                    }
                )
                if "failed" in result_str.lower() or "error" in result_str.lower() or "missing" in result_str.lower():
                    tool_error = True
                    print(f"[Agent] Tool error detected in result for {tc.function.name} — will inject retry instruction")

            if tool_error:
                messages.append({
                    "role": "system",
                    "content": (
                        "One or more tool calls above failed or returned an error. "
                        "Do NOT give up, do NOT ask the user to resend their question. "
                        "Carefully read the error, correct the tool arguments, and retry the call with valid parameters now."
                    ),
                })

    final = "Maximum reasoning turns reached without a final answer."
    print(f"[Agent] WARNING: {final}")
    messages.append({"role": "assistant", "content": final})
    chart_path = _extract_chart_path(messages)
    return final, chart_path, messages
