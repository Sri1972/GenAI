"""
Full Stack Developer Agent — Standalone module.

Usage:
    from AgentPlatform.catalog.fullstack_dev.agent import FullStackDevAgent
    dev = FullStackDevAgent()
    response = dev.respond(context, instruction, stage="tasks")
"""

from AgentPlatform.core.base_agent import BaseAgent


class FullStackDevAgent(BaseAgent):
    AGENT_ID = "fullstack_dev"

    def validate_output(self, output: str) -> tuple[bool, str]:
        valid, reason = super().validate_output(output)
        if not valid:
            return valid, reason
        return True, "OK"


if __name__ == "__main__":
    agent = FullStackDevAgent()
    print(f"Agent: {agent.get_info()['name']}")
    print(f"Skills: {', '.join(agent.get_info()['skills'])}")
    print(f"Stages: {', '.join(agent.get_info()['stages'])}")
