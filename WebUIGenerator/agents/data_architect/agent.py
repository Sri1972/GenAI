"""
Data Architect Agent — designs SQLite schemas, generates realistic seed data,
and creates TypeScript interface definitions that mirror the database.

Usage (standalone):
    from agents.data_architect.agent import DataArchitectAgent
    agent = DataArchitectAgent()
    result = agent.generate("Design schema for a sales analytics app", stage="data_modeling", json_mode=True)
"""

from agents.base_agent import BaseAgent


class DataArchitectAgent(BaseAgent):
    AGENT_ID = "data_architect"

    def validate_output(self, output: str) -> tuple[bool, str]:
        valid, reason = super().validate_output(output)
        if not valid:
            return valid, reason
        has_schema = "CREATE TABLE" in output.upper() or "interface" in output.lower()
        if not has_schema:
            return False, "Data Architect output should contain schema or interface definitions"
        return True, "OK"
