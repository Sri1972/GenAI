"""
Database Engineer Agent — Standalone module.

Usage:
    from AgentPlatform.catalog.db_engineer.agent import DBEngineerAgent
    db = DBEngineerAgent()
    response = db.respond(context, instruction, stage="design")
"""

from AgentPlatform.core.base_agent import BaseAgent


class DBEngineerAgent(BaseAgent):
    AGENT_ID = "db_engineer"

    def validate_output(self, output: str) -> tuple[bool, str]:
        valid, reason = super().validate_output(output)
        if not valid:
            return valid, reason
        if "table" in output.lower() or "schema" in output.lower():
            if "index" not in output.lower():
                return False, "Schema design missing indexing strategy — guardrail violation"
        return True, "OK"


if __name__ == "__main__":
    agent = DBEngineerAgent()
    print(f"Agent: {agent.get_info()['name']}")
    print(f"Skills: {', '.join(agent.get_info()['skills'])}")
    print(f"Stages: {', '.join(agent.get_info()['stages'])}")
