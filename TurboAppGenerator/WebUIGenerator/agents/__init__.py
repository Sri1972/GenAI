"""
TurboUIGen Agents — multi-agent architecture for web app generation.

The persona agents themselves (config.yaml + agent.py + templates/) now live
in the shared AgentPlatform/catalog/, not here — see AgentPlatform/core/registry.py.
This package keeps the pipeline infra: llm.py, orchestrator.py, sdk_client.py,
skills/, etc.

Usage:
    from agents.orchestrator import CrewOrchestrator
    from AgentPlatform.core.registry import get_agent, list_agents
"""

from .orchestrator import CrewOrchestrator
from AgentPlatform.core.registry import get_agent, list_agents

__all__ = ["CrewOrchestrator", "get_agent", "list_agents"]
