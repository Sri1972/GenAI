"""
AI/GenAI Engineer Agent — integrates LLM-powered features: chat interfaces,
natural language queries, AI recommendations, and conversational data exploration.

Usage (standalone):
    from agents.ai_genai.agent import AIGenAIAgent
    agent = AIGenAIAgent()
    result = agent.generate("Generate an AI chat page with persona selector", stage="pages", json_mode=True)
"""

from agents.base_agent import BaseAgent


class AIGenAIAgent(BaseAgent):
    AGENT_ID = "ai_genai"

    def validate_output(self, output: str) -> tuple[bool, str]:
        valid, reason = super().validate_output(output)
        if not valid:
            return valid, reason
        return True, "OK"
