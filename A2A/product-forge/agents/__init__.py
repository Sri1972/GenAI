"""
Product Forge Agents — Each agent is a standalone package with its own
config (skills, guardrails, guidelines) and can be used independently.

Usage:
    from agents import get_agent, list_agents
    pm = get_agent("product_manager")
    response = pm.respond(context, instruction, stage="prd")
"""

from agents.product_manager.agent import ProductManagerAgent
from agents.product_owner.agent import ProductOwnerAgent
from agents.business_analyst.agent import BusinessAnalystAgent
from agents.architect.agent import ArchitectAgent
from agents.fullstack_dev.agent import FullStackDevAgent
from agents.ui_developer.agent import UIDeveloperAgent
from agents.backend_engineer.agent import BackendEngineerAgent
from agents.db_engineer.agent import DBEngineerAgent
from agents.qa_engineer.agent import QAEngineerAgent
from agents.devops_engineer.agent import DevOpsEngineerAgent

AGENT_REGISTRY = {
    "product_manager": ProductManagerAgent,
    "product_owner": ProductOwnerAgent,
    "business_analyst": BusinessAnalystAgent,
    "architect": ArchitectAgent,
    "fullstack_dev": FullStackDevAgent,
    "ui_developer": UIDeveloperAgent,
    "backend_engineer": BackendEngineerAgent,
    "db_engineer": DBEngineerAgent,
    "qa_engineer": QAEngineerAgent,
    "devops_engineer": DevOpsEngineerAgent,
}


def get_agent(agent_id: str):
    """Get an agent instance by ID."""
    cls = AGENT_REGISTRY.get(agent_id)
    if not cls:
        raise ValueError(f"Unknown agent: {agent_id}. Available: {list(AGENT_REGISTRY.keys())}")
    return cls()


def list_agents():
    """List all available agents with metadata."""
    return [cls().get_info() for cls in AGENT_REGISTRY.values()]
