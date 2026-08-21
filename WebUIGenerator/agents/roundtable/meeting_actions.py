"""The `meeting` in-process MCP server — structured meeting actions as TOOLS.

This is the heart of the debate engine's "leverage the SDK's natural behavior" bet.
The classic engine forces every turn through a JSON output schema, which is what makes
turns feel form-filled. Here the persona instead speaks in free-form prose and *calls
these tools* as it naturally would — so the structure the UI needs (decisions, citations,
questions) is a BYPRODUCT of the agent acting, not a cage around its language.

Each PersonaAgent gets its own server + buffer; the meeting reads and clears the buffer
after every turn to assemble the structured side of the Turn.

Same mechanism as dataset_mcp / turboui_mcp: create_sdk_mcp_server + @tool, no subprocess.
"""

from __future__ import annotations

from typing import Any

from claude_agent_sdk import tool, create_sdk_mcp_server, ToolAnnotations

MEETING_ACTION_TOOLS = [
    "mcp__meeting__propose",
    "mcp__meeting__cite",
    "mcp__meeting__ask_user",
    "mcp__meeting__defer_to",
    "mcp__meeting__concede",
]

# What `propose` kinds map to a hard "agreed" chip vs. a softer note for the recap.
_AGREED_KINDS = {"decision", "constraint", "commitment"}
_SOFT_KINDS = {"risk", "assumption", "open_question"}


def _ok(msg: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": msg}]}


def build_actions_server() -> tuple[Any, list[dict]]:
    """Return (server, buffer). The persona calls the tools; each call appends a record to
    `buffer`. The meeting drains `buffer` after the turn to build the Turn's structured fields
    and to emit `agreed` / `question` events. Not read-only — these mutate meeting state — but
    they touch nothing on disk."""
    buffer: list[dict] = []

    @tool("propose",
          "Put a concrete outcome on the table: a decision, a constraint the team must respect, "
          "a commitment (who does what), a risk, an assumption to validate, or an open question. "
          "Call this whenever you land something worth recording — it's how the meeting captures "
          "what was actually settled. Say it in one crisp line.",
          {"type": "object", "properties": {
              "kind": {"type": "string", "enum": ["decision", "constraint", "commitment", "risk", "assumption", "open_question"]},
              "text": {"type": "string"}},
           "required": ["kind", "text"]})
    async def propose(args: dict[str, Any]) -> dict[str, Any]:
        kind = (args.get("kind") or "").strip().lower()
        text = (args.get("text") or "").strip()
        if text:
            buffer.append({"action": "propose", "kind": kind, "text": text})
        return _ok(f"Recorded ({kind}).")

    @tool("cite",
          "Back a claim with a specific piece of evidence you actually looked at — a number you "
          "pulled from the data, a detail from a reference file. Use it so your point is grounded "
          "rather than asserted.",
          {"type": "object", "properties": {
              "claim": {"type": "string"}, "source": {"type": "string"}},
           "required": ["claim", "source"]})
    async def cite(args: dict[str, Any]) -> dict[str, Any]:
        source = (args.get("source") or "").strip()
        claim = (args.get("claim") or "").strip()
        if source:
            buffer.append({"action": "cite", "claim": claim, "source": source})
        return _ok("Citation noted.")

    @tool("ask_user",
          "Ask the human in the room a direct question when you genuinely need their call to go "
          "further — a priority, a constraint only they know, a go/no-go. Use sparingly; don't ask "
          "what the team can reason out itself.",
          {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]})
    async def ask_user(args: dict[str, Any]) -> dict[str, Any]:
        q = (args.get("question") or "").strip()
        if q:
            buffer.append({"action": "ask_user", "question": q})
        return _ok("Asked — the human may answer between turns.")

    @tool("defer_to",
          "Name the colleague who should respond next and why — hand them the floor because the "
          "point is theirs to answer. This is how the room self-organizes instead of waiting on a "
          "chair.",
          {"type": "object", "properties": {
              "who": {"type": "string", "description": "persona id, e.g. 'engineering'"},
              "why": {"type": "string"}},
           "required": ["who"]})
    async def defer_to(args: dict[str, Any]) -> dict[str, Any]:
        who = (args.get("who") or "").strip().lower()
        if who:
            buffer.append({"action": "defer_to", "who": who, "why": (args.get("why") or "").strip()})
        return _ok(f"Handed to {who}.")

    @tool("concede",
          "Say plainly when someone else's point has changed your mind — name what you're giving "
          "up. Real concessions are what make a debate worth having; don't dig in for its own sake.",
          {"type": "object", "properties": {"point": {"type": "string"}}, "required": ["point"]})
    async def concede(args: dict[str, Any]) -> dict[str, Any]:
        point = (args.get("point") or "").strip()
        if point:
            buffer.append({"action": "concede", "point": point})
        return _ok("Concession noted.")

    server = create_sdk_mcp_server(
        name="meeting", version="1.0.0",
        tools=[propose, cite, ask_user, defer_to, concede],
    )
    return server, buffer
