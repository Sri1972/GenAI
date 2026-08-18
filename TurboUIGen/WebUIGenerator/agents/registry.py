"""
Agent registry — discovers and provides access to all agents.

Each agent lives in its own directory:
    agents/<agent_id>/
        config.yaml  — role, skills, guidelines, guardrails, stage_roles
        agent.py     — Python class extending BaseAgent
        templates/   — (optional) skill templates owned by this agent

To use a single agent independently:
    from agents.react_ui.agent import ReactUIAgent
    agent = ReactUIAgent()
    result = agent.generate("Build a dashboard page", stage="pages", json_mode=True)

To use the full registry:
    from agents.registry import get_agent, list_agents
    agent = get_agent("react_ui")
"""

from .base_agent import BaseAgent
from .ux_architect.agent import UXArchitectAgent
from .react_ui.agent import ReactUIAgent
from .data_architect.agent import DataArchitectAgent
from .services_engineer.agent import ServicesEngineerAgent
from .visual_design.agent import VisualDesignAgent
from .ai_genai.agent import AIGenAIAgent


AGENT_REGISTRY: dict[str, type[BaseAgent]] = {
    "ux_architect": UXArchitectAgent,
    "react_ui": ReactUIAgent,
    "data_architect": DataArchitectAgent,
    "services_engineer": ServicesEngineerAgent,
    "visual_design": VisualDesignAgent,
    "ai_genai": AIGenAIAgent,
}


def get_agent(agent_id: str) -> BaseAgent:
    """Instantiate and return an agent by ID."""
    cls = AGENT_REGISTRY.get(agent_id)
    if not cls:
        raise ValueError(f"Unknown agent: {agent_id}. Available: {list(AGENT_REGISTRY.keys())}")
    return cls()


def list_agents() -> list[str]:
    """Return all registered agent IDs."""
    return list(AGENT_REGISTRY.keys())
