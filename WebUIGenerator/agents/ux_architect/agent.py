"""
UX Architect Agent — designs information architecture, page layouts,
navigation patterns, and user flows for web applications.

Usage (standalone):
    from agents.ux_architect.agent import UXArchitectAgent
    agent = UXArchitectAgent()
    result = agent.generate("Design a sales dashboard app", stage="architecture")
"""

from agents.base_agent import BaseAgent


class UXArchitectAgent(BaseAgent):
    AGENT_ID = "ux_architect"

    def validate_output(self, output: str) -> tuple[bool, str]:
        valid, reason = super().validate_output(output)
        if not valid:
            return valid, reason
        if "pages" not in output.lower() and "page" not in output.lower():
            return False, "UX output should define page structure"
        return True, "OK"
