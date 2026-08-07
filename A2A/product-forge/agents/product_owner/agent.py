"""
Product Owner Agent — Standalone module.

Usage:
    from agents.product_owner.agent import ProductOwnerAgent
    po = ProductOwnerAgent()
    response = po.respond(context, instruction, stage="stories")
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))

from base import BaseAgent


class ProductOwnerAgent(BaseAgent):
    AGENT_ID = "product_owner"

    def validate_output(self, output: str) -> tuple[bool, str]:
        valid, reason = super().validate_output(output)
        if not valid:
            return valid, reason
        if "as a" in output.lower() and "acceptance criteria" not in output.lower():
            return False, "User stories missing acceptance criteria — guardrail violation"
        return True, "OK"


if __name__ == "__main__":
    agent = ProductOwnerAgent()
    print(f"Agent: {agent.get_info()['name']}")
    print(f"Skills: {', '.join(agent.get_info()['skills'])}")
    print(f"Stages: {', '.join(agent.get_info()['stages'])}")
