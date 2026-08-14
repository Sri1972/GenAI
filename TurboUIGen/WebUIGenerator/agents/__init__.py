"""
TurboUIGen Agents — multi-agent architecture for web app generation.

Each agent is a self-contained directory:
    agents/<agent_id>/
        config.yaml   — role, skills, guidelines, guardrails, stage_roles
        agent.py      — Python class extending BaseAgent
        templates/    — (optional) skill templates owned by this agent

Usage:
    from agents.registry import get_agent, list_agents
    from agents.orchestrator import CrewOrchestrator
"""

from .orchestrator import CrewOrchestrator
from .registry import get_agent, list_agents

__all__ = ["CrewOrchestrator", "get_agent", "list_agents"]
