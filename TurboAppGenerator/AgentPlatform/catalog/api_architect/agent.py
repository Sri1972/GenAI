"""
API Architect Agent — designs the RESTful API architecture (entities,
endpoints, auth, pagination) for a from-scratch WebAPIGenerator project, and
merges a requested change into an existing architecture during refine (via
stage="refine").

Usage:
    from AgentPlatform.catalog.api_architect.agent import ApiArchitectAgent
    agent = ApiArchitectAgent()
    result = agent.generate(user_prompt, max_tokens=16000, json_mode=True)
    result = agent.generate(merge_prompt, stage="refine", max_tokens=16000, json_mode=True)
"""

from AgentPlatform.core.base_agent import BaseAgent


class ApiArchitectAgent(BaseAgent):
    AGENT_ID = "api_architect"
