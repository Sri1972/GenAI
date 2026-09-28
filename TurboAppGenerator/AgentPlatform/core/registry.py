"""
Agent registry — discovers and provides access to every persona agent in the
shared catalog (AgentPlatform/catalog/), regardless of which pipeline
(WebUIGenerator, ProductForge, or an external caller) is asking for one.

To use a single agent independently:
    from AgentPlatform.catalog.react_ui.agent import ReactUIAgent
    agent = ReactUIAgent()
    result = agent.generate("Build a dashboard page", stage="pages", json_mode=True)

To use the full registry:
    from AgentPlatform.core.registry import get_agent, list_agents
    agent = get_agent("react_ui")
"""

from .base_agent import BaseAgent

# WebUIGenerator's 6
from AgentPlatform.catalog.ux_architect.agent import UXArchitectAgent
from AgentPlatform.catalog.react_ui.agent import ReactUIAgent
from AgentPlatform.catalog.data_architect.agent import DataArchitectAgent
from AgentPlatform.catalog.webui_integration_engineer.agent import WebUIIntegrationEngineerAgent
from AgentPlatform.catalog.visual_design.agent import VisualDesignAgent
from AgentPlatform.catalog.ai_genai.agent import AIGenAIAgent

# ProductForge's 10
from AgentPlatform.catalog.product_manager.agent import ProductManagerAgent
from AgentPlatform.catalog.product_owner.agent import ProductOwnerAgent
from AgentPlatform.catalog.business_analyst.agent import BusinessAnalystAgent
from AgentPlatform.catalog.architect.agent import ArchitectAgent
from AgentPlatform.catalog.fullstack_dev.agent import FullStackDevAgent
from AgentPlatform.catalog.ui_developer.agent import UIDeveloperAgent
from AgentPlatform.catalog.backend_engineer.agent import BackendEngineerAgent
from AgentPlatform.catalog.db_engineer.agent import DBEngineerAgent
from AgentPlatform.catalog.qa_engineer.agent import QAEngineerAgent
from AgentPlatform.catalog.devops_engineer.agent import DevOpsEngineerAgent

# WebAPIGenerator's 4
from AgentPlatform.catalog.api_services_engineer.agent import ApiServicesEngineerAgent
from AgentPlatform.catalog.api_security_engineer.agent import ApiSecurityEngineerAgent
from AgentPlatform.catalog.api_architect.agent import ApiArchitectAgent
from AgentPlatform.catalog.api_data_architect.agent import ApiDataArchitectAgent


AGENT_REGISTRY: dict[str, type[BaseAgent]] = {
    "ux_architect": UXArchitectAgent,
    "react_ui": ReactUIAgent,
    "data_architect": DataArchitectAgent,
    "webui_integration_engineer": WebUIIntegrationEngineerAgent,
    "visual_design": VisualDesignAgent,
    "ai_genai": AIGenAIAgent,
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
    "api_services_engineer": ApiServicesEngineerAgent,
    "api_security_engineer": ApiSecurityEngineerAgent,
    "api_architect": ApiArchitectAgent,
    "api_data_architect": ApiDataArchitectAgent,
}


def get_agent(agent_id: str) -> BaseAgent:
    """Instantiate and return an agent by ID."""
    cls = AGENT_REGISTRY.get(agent_id)
    if not cls:
        raise ValueError(f"Unknown agent: {agent_id}. Available: {list(AGENT_REGISTRY.keys())}")
    return cls()


def list_agents() -> list[dict]:
    """List all available agents with metadata."""
    return [cls().get_info() for cls in AGENT_REGISTRY.values()]
