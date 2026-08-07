"""
QA Engineer Agent — Standalone module.

Usage:
    from agents.qa_engineer.agent import QAEngineerAgent
    qa = QAEngineerAgent()
    response = qa.respond(context, instruction, stage="test_cases")
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))

from base import BaseAgent


class QAEngineerAgent(BaseAgent):
    AGENT_ID = "qa_engineer"

    def validate_output(self, output: str) -> tuple[bool, str]:
        valid, reason = super().validate_output(output)
        if not valid:
            return valid, reason
        if "test case" in output.lower() or "tc-" in output.lower():
            if "negative" not in output.lower() and "error" not in output.lower() and "invalid" not in output.lower():
                return False, "Test cases missing negative/error tests — guardrail violation"
        return True, "OK"


if __name__ == "__main__":
    agent = QAEngineerAgent()
    print(f"Agent: {agent.get_info()['name']}")
    print(f"Skills: {', '.join(agent.get_info()['skills'])}")
    print(f"Stages: {', '.join(agent.get_info()['stages'])}")
