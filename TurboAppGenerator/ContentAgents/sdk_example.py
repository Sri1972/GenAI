"""
Minimal example: call one of the ContentAgents subagents via the Claude
Agent SDK (pip install claude-agent-sdk) instead of the `claude` CLI.

This is the starting point for a custom client — a bot, a service, whatever
you're building — that wants to invoke "excel-parser" or any of the other
five subagents programmatically without shelling out to a CLI binary at all.

Usage:
    python sdk_example.py excel-parser "Parse Q3.xlsx and tell me the primary key column"
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common.claude_agent_client import run_agent


async def main():
    if len(sys.argv) < 3:
        sys.exit('Usage: python sdk_example.py <agent-name> "<prompt>"')

    agent_name, prompt = sys.argv[1], sys.argv[2]
    result = await run_agent(agent_name, prompt)
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
