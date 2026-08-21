"""Reading structured output back from the SDK.

Non-obvious, and not spelled out in the SDK's own docstring for
``ClaudeAgentOptions.output_format`` ("the agent returns structured data
matching the schema"):

**The payload does not arrive as text.** Setting ``output_format`` gives the
session a synthetic ``StructuredOutput`` tool and the model *calls it*. The
object you want is ``ToolUseBlock.input`` on an ``AssistantMessage`` — the
text blocks are empty. Parsing ``TextBlock`` content yields nothing at all,
silently.

Both helpers below fall back to concatenated text so a session without
``output_format`` still works.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Callable

from claude_agent_sdk import AssistantMessage, Message, ResultMessage, TextBlock, ToolUseBlock

_TOOL = "StructuredOutput"


def usage_from_result(msg: ResultMessage) -> dict[str, Any]:
    """Pull a flat token/cost record out of a ResultMessage. Tolerant of the
    usage payload arriving as a dict or an object across SDK versions."""
    u = getattr(msg, "usage", None) or {}

    def g(*keys: str) -> int:
        for k in keys:
            v = u.get(k) if isinstance(u, dict) else getattr(u, k, None)
            if v:
                return int(v)
        return 0

    return {
        "input_tokens": g("input_tokens"),
        "output_tokens": g("output_tokens"),
        "cache_read_tokens": g("cache_read_input_tokens", "cache_read_tokens"),
        "cache_write_tokens": g("cache_creation_input_tokens", "cache_creation_tokens"),
        "cost_usd": float(getattr(msg, "total_cost_usd", 0.0) or 0.0),
    }


async def collect(
    messages: AsyncIterator[Message],
    *,
    on_activity: Callable[[str, dict], None] | None = None,
    on_result: Callable[[ResultMessage], None] | None = None,
) -> dict[str, Any] | None:
    """Drain a message stream and return the structured payload, if any.

    Optional hooks let a caller watch the work as it happens without changing
    the return contract: ``on_activity(tool_name, tool_input)`` fires for every
    real tool call (i.e. not the synthetic StructuredOutput), and
    ``on_result(msg)`` fires on each ResultMessage so usage/cost can be tallied.
    """
    payload: dict[str, Any] | None = None
    text: list[str] = []

    async for msg in messages:
        if isinstance(msg, ResultMessage):
            if on_result is not None:
                on_result(msg)
            continue
        if not isinstance(msg, AssistantMessage):
            continue
        for block in msg.content:
            if isinstance(block, TextBlock):
                text.append(block.text)
            elif isinstance(block, ToolUseBlock):
                if block.name == _TOOL:
                    value = block.input
                    if isinstance(value, dict):
                        payload = value
                elif on_activity is not None:
                    on_activity(block.name, block.input or {})

    if payload is not None:
        return payload
    return _from_text("".join(text).strip())


def _from_text(raw: str) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    if "```" in raw:
        inner = raw.split("```")[1]
        inner = inner[4:] if inner.startswith("json") else inner
        try:
            return json.loads(inner.strip())
        except json.JSONDecodeError:
            pass
    return {"_text": raw}
