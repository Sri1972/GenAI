"""
DevOps Engineer Agent — Standalone module.

Usage:
    from agents.devops_engineer.agent import DevOpsEngineerAgent
    ops = DevOpsEngineerAgent()
    response = ops.respond(context, instruction, stage="design")
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))

from base import BaseAgent


class DevOpsEngineerAgent(BaseAgent):
    AGENT_ID = "devops_engineer"

    def validate_output(self, output: str) -> tuple[bool, str]:
        valid, reason = super().validate_output(output)
        if not valid:
            return valid, reason
        if "deploy" in output.lower() or "pipeline" in output.lower():
            if "rollback" not in output.lower():
                return False, "Deployment plan missing rollback strategy — guardrail violation"
        return True, "OK"


if __name__ == "__main__":
    agent = DevOpsEngineerAgent()
    print(f"Agent: {agent.get_info()['name']}")
    print(f"Skills: {', '.join(agent.get_info()['skills'])}")
    print(f"Stages: {', '.join(agent.get_info()['stages'])}")
