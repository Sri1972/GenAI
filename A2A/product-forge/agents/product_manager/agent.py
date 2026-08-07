"""
Product Manager Agent — Standalone module.

Usage:
    from agents.product_manager.agent import ProductManagerAgent
    pm = ProductManagerAgent()
    response = pm.respond(context, instruction, stage="prd")
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))

from base import BaseAgent


class ProductManagerAgent(BaseAgent):
    AGENT_ID = "product_manager"

    def validate_output(self, output: str) -> tuple[bool, str]:
        valid, reason = super().validate_output(output)
        if not valid:
            return valid, reason
        # PRD-specific validations
        if "prd" in output.lower() or "## " in output:
            if "success metric" not in output.lower() and "kpi" not in output.lower():
                return False, "PRD missing success metrics — guardrail violation"
        return True, "OK"


if __name__ == "__main__":
    agent = ProductManagerAgent()
    print(f"Agent: {agent.get_info()['name']}")
    print(f"Skills: {', '.join(agent.get_info()['skills'])}")
    print(f"Stages: {', '.join(agent.get_info()['stages'])}")
    print(f"\nSystem Prompt Preview:\n{agent.system_prompt[:500]}...")
