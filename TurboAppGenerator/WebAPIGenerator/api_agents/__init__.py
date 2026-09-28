"""
WebAPIGenerator agents — standalone REST API generation pipeline.

Reuses WebUIGenerator's shared agents.llm / agents.uigen_agent helpers directly
(WebUIGenerator stays on sys.path and owns the `agents` package name); this package
is named api_agents specifically so it never collides with that name.
"""
