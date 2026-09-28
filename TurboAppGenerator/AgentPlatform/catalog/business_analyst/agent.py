"""
Business Analyst Agent — Standalone module.

Usage:
    from AgentPlatform.catalog.business_analyst.agent import BusinessAnalystAgent
    ba = BusinessAnalystAgent()
    response = ba.respond(context, instruction, stage="trd")
"""

from AgentPlatform.core.base_agent import BaseAgent


class BusinessAnalystAgent(BaseAgent):
    AGENT_ID = "business_analyst"

    def validate_output(self, output: str) -> tuple[bool, str]:
        valid, reason = super().validate_output(output)
        if not valid:
            return valid, reason
        if "trd" in output.lower() or "business rule" in output.lower():
            if "error" not in output.lower() and "exception" not in output.lower():
                return False, "TRD missing error/exception handling — guardrail violation"
        return True, "OK"


if __name__ == "__main__":
    agent = BusinessAnalystAgent()
    print(f"Agent: {agent.get_info()['name']}")
    print(f"Skills: {', '.join(agent.get_info()['skills'])}")
    print(f"Stages: {', '.join(agent.get_info()['stages'])}")
