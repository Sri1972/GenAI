"""
Solutions Architect Agent — Standalone module.

Usage:
    from agents.architect.agent import ArchitectAgent
    arch = ArchitectAgent()
    response = arch.respond(context, instruction, stage="design")
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))

from base import BaseAgent


class ArchitectAgent(BaseAgent):
    AGENT_ID = "architect"

    def validate_output(self, output: str) -> tuple[bool, str]:
        valid, reason = super().validate_output(output)
        if not valid:
            return valid, reason
        if "design" in output.lower() or "architecture" in output.lower():
            checks = ["security", "scalab", "monitor", "deploy"]
            missing = [c for c in checks if c not in output.lower()]
            if len(missing) > 2:
                return False, f"Design missing critical sections: {missing}"
        return True, "OK"


if __name__ == "__main__":
    agent = ArchitectAgent()
    print(f"Agent: {agent.get_info()['name']}")
    print(f"Skills: {', '.join(agent.get_info()['skills'])}")
    print(f"Stages: {', '.join(agent.get_info()['stages'])}")
