"""
React UI Engineer Agent — builds production-quality React/TypeScript/Tailwind
page components using the mobility-global-ds design system.

Usage (standalone):
    from agents.react_ui.agent import ReactUIAgent
    agent = ReactUIAgent()
    result = agent.generate("Generate a Dashboard page with KPI cards", stage="pages", json_mode=True)
"""

from agents.base_agent import BaseAgent


class ReactUIAgent(BaseAgent):
    AGENT_ID = "react_ui"

    def validate_output(self, output: str) -> tuple[bool, str]:
        valid, reason = super().validate_output(output)
        if not valid:
            return valid, reason
        if "import" not in output and "export" not in output:
            return False, "React UI output should contain import/export statements"
        return True, "OK"
