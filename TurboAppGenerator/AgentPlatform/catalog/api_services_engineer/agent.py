"""
API Services Engineer Agent — generates the Controller/Service/Repository
backend code layer for WebAPIGenerator's from-scratch multi-entity REST APIs
(Python/FastAPI or Java/Spring Boot). Distinct from the catalog's
`services_engineer` agent, which only wires/verifies an already-designed,
single-endpoint-shape backend for a WebUIGenerator React frontend — a
meaningfully different, narrower scope.

Usage:
    from AgentPlatform.catalog.api_services_engineer.agent import ApiServicesEngineerAgent
    agent = ApiServicesEngineerAgent()
    result = agent.generate(user_prompt, max_tokens=32000, json_mode=True)
"""

from AgentPlatform.core.base_agent import BaseAgent


class ApiServicesEngineerAgent(BaseAgent):
    AGENT_ID = "api_services_engineer"
