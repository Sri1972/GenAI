"""
Backend API Engineer Agent — Standalone module.

Usage:
    from agents.backend_engineer.agent import BackendEngineerAgent
    be = BackendEngineerAgent()
    response = be.respond(context, instruction, stage="design")
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))

from base import BaseAgent


class BackendEngineerAgent(BaseAgent):
    AGENT_ID = "backend_engineer"

    def validate_output(self, output: str) -> tuple[bool, str]:
        valid, reason = super().validate_output(output)
        if not valid:
            return valid, reason
        if "endpoint" in output.lower() or "api" in output.lower():
            if "error" not in output.lower() and "status" not in output.lower():
                return False, "API design missing error handling/status codes — guardrail violation"
        return True, "OK"


if __name__ == "__main__":
    agent = BackendEngineerAgent()
    print(f"Agent: {agent.get_info()['name']}")
    print(f"Skills: {', '.join(agent.get_info()['skills'])}")
    print(f"Stages: {', '.join(agent.get_info()['stages'])}")
