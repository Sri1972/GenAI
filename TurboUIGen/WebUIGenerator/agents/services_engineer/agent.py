"""
Services Engineer Agent — designs REST APIs, configures FastAPI backends,
and ensures frontend-backend data integration is correct.

Usage (standalone):
    from agents.services_engineer.agent import ServicesEngineerAgent
    agent = ServicesEngineerAgent()
    result = agent.generate("Verify all useApi calls match schema tables", stage="integration")
"""

from agents.base_agent import BaseAgent


class ServicesEngineerAgent(BaseAgent):
    AGENT_ID = "services_engineer"

    def validate_output(self, output: str) -> tuple[bool, str]:
        valid, reason = super().validate_output(output)
        if not valid:
            return valid, reason
        return True, "OK"
