"""
UI Developer Agent — Standalone module.

Usage:
    from agents.ui_developer.agent import UIDeveloperAgent
    ui = UIDeveloperAgent()
    response = ui.respond(context, instruction, stage="design")
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))

from base import BaseAgent


class UIDeveloperAgent(BaseAgent):
    AGENT_ID = "ui_developer"

    def validate_output(self, output: str) -> tuple[bool, str]:
        valid, reason = super().validate_output(output)
        if not valid:
            return valid, reason
        if "component" in output.lower():
            if "accessibility" not in output.lower() and "a11y" not in output.lower() and "aria" not in output.lower():
                return False, "UI design missing accessibility considerations — guardrail violation"
        return True, "OK"


if __name__ == "__main__":
    agent = UIDeveloperAgent()
    print(f"Agent: {agent.get_info()['name']}")
    print(f"Skills: {', '.join(agent.get_info()['skills'])}")
    print(f"Stages: {', '.join(agent.get_info()['stages'])}")
