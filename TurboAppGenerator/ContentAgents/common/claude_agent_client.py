"""
Claude Agent SDK-based alternative to common/claude_cli.py.

Instead of shelling out to the `claude` CLI as a subprocess (which on
Windows has to go through the claude.cmd shim and its argv re-tokenization —
see claude_cli.py's _resolve_claude_binary), this talks to the same Claude
Code engine through the Python SDK (`pip install claude-agent-sdk`), which
streams the prompt over stdio rather than as a CLI argument.

Loads a subagent's own Agents/.claude/agents/<name>.md definition
(frontmatter `tools:` + the body as the system prompt) and runs it as the
acting agent for a single, one-shot query — mirroring exactly what the
CLI-based run.py scripts do, just via the SDK instead of a subprocess.
"""

import asyncio
import re
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

AGENTS_DIR = Path(__file__).resolve().parent.parent.parent / ".claude" / "agents"

# Same rationale as claude_cli.ALL_TOOLS: always explicitly allow or disallow
# every standard tool, so the SDK never needs to raise an interactive
# permission question with no one able to answer it.
ALL_TOOLS = ["Bash", "Read", "Write", "Edit", "Glob", "Grep", "WebFetch", "WebSearch", "NotebookEdit", "Task"]

# Same Bedrock inference-profile ARNs as Agents/.claude/settings.json.
BEDROCK_ENV = {
    "CLAUDE_CODE_USE_BEDROCK": "1",
    "AWS_REGION": "us-east-1",
    "AWS_PROFILE": "default",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "arn:aws:bedrock:us-east-1:992382856886:application-inference-profile/oonx9pzz8l4h",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "arn:aws:bedrock:us-east-1:992382856886:application-inference-profile/ighsdreux5fs",
}

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
_TOOLS_RE = re.compile(r"^tools:\s*(.+)$", re.MULTILINE)


class AgentClientError(RuntimeError):
    pass


def _load_subagent(agent_name: str) -> tuple[str, list[str]]:
    """Parse Agents/.claude/agents/<agent_name>.md -> (system_prompt, tools)."""
    path = AGENTS_DIR / f"{agent_name}.md"
    if not path.exists():
        raise AgentClientError(f"No subagent definition at {path}")

    match = _FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
    if not match:
        raise AgentClientError(f"Malformed subagent file (no frontmatter): {path}")
    frontmatter, body = match.groups()

    tools_match = _TOOLS_RE.search(frontmatter)
    tools = [t.strip() for t in tools_match.group(1).split(",")] if tools_match else []
    return body.strip(), tools


async def run_agent(agent_name: str, prompt: str, cwd: str | None = None, timeout: int = 900) -> str:
    """Run a named subagent (Agents/.claude/agents/<agent_name>.md) via the
    SDK for one query, and return its final result text."""
    system_prompt, tools = _load_subagent(agent_name)

    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        allowed_tools=tools,
        disallowed_tools=[t for t in ALL_TOOLS if t not in tools],
        cwd=cwd or str(AGENTS_DIR.parent),
        env=BEDROCK_ENV,
        setting_sources=[],  # isolation mode: don't depend on interactive trust/settings state
    )

    result: ResultMessage | None = None
    async with asyncio.timeout(timeout):
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, ResultMessage):
                result = message

    if result is None:
        raise AgentClientError("No result message received from the SDK")
    if result.is_error:
        raise AgentClientError(f"Agent reported an error: {result.result}")
    return result.result or ""


def run_agent_sync(agent_name: str, prompt: str, cwd: str | None = None, timeout: int = 900) -> str:
    """Synchronous convenience wrapper around run_agent() for non-async callers."""
    return asyncio.run(run_agent(agent_name, prompt, cwd=cwd, timeout=timeout))
