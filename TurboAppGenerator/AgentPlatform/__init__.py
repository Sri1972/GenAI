"""
AgentPlatform — the shared persona-agent catalog for the whole TurboAppGenerator
platform. Every agent used by WebUIGenerator (react_ui, visual_design, ...) and
ProductForge (architect, backend_engineer, ...) lives here, under one base
class and one registry, instead of being duplicated per-pipeline.

    from AgentPlatform.core.registry import get_agent, list_agents
"""
