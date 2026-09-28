"""
API Security Engineer Agent — generates jwt/api_key authentication and
rate-limiting middleware for WebAPIGenerator's generated REST APIs. The
`none`/`basic` auth types never reach this agent — those are deterministic
template copies with no LLM call, handled directly by the orchestrator.

Usage:
    from AgentPlatform.catalog.api_security_engineer.agent import ApiSecurityEngineerAgent
    agent = ApiSecurityEngineerAgent()
    result = agent.generate(user_prompt, max_tokens=32000, json_mode=True)
"""

from AgentPlatform.core.base_agent import BaseAgent


class ApiSecurityEngineerAgent(BaseAgent):
    AGENT_ID = "api_security_engineer"
