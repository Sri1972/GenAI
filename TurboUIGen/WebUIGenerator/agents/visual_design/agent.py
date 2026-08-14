"""
Visual Design Engineer Agent — builds D3.js charts, geographic maps,
dashboards, and interactive data visualizations.

Usage (standalone):
    from agents.visual_design.agent import VisualDesignAgent
    agent = VisualDesignAgent()
    result = agent.generate("Generate a D3 bar chart component", stage="components", json_mode=True)
"""

from agents.base_agent import BaseAgent


class VisualDesignAgent(BaseAgent):
    AGENT_ID = "visual_design"

    def validate_output(self, output: str) -> tuple[bool, str]:
        valid, reason = super().validate_output(output)
        if not valid:
            return valid, reason
        if "d3" not in output.lower() and "chart" not in output.lower() and "map" not in output.lower():
            return False, "Visual Design output should reference D3, charts, or maps"
        return True, "OK"
