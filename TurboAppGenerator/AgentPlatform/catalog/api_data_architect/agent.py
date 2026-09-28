"""
API Data Architect Agent — generates the database schema and ORM layer (JPA
entities or SQLAlchemy models) for WebAPIGenerator's from-scratch and refine
data-modeling stages, one batch of entities at a time.

Usage:
    from AgentPlatform.catalog.api_data_architect.agent import ApiDataArchitectAgent
    agent = ApiDataArchitectAgent()
    result = agent.generate(batch_prompt, max_tokens=8000, json_mode=True)
"""

from AgentPlatform.core.base_agent import BaseAgent


class ApiDataArchitectAgent(BaseAgent):
    AGENT_ID = "api_data_architect"
