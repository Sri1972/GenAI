"""
WebUI Integration Engineer Agent — verifies/wires an already-designed,
fixed-shape auto-generated API (GET /api/data/{table}, /api/metadata, ...)
against a WebUIGenerator React frontend's useApi hook. Distinct from
AgentPlatform/catalog/api_services_engineer/, which generates a real
Controller/Service/Repository backend from scratch for WebAPIGenerator —
a meaningfully different, much larger scope. Named "webui_integration_engineer"
(not "services_engineer") specifically to avoid that confusion.

Usage (standalone):
    from AgentPlatform.catalog.webui_integration_engineer.agent import WebUIIntegrationEngineerAgent
    agent = WebUIIntegrationEngineerAgent()
    result = agent.generate("Verify all useApi calls match schema tables", stage="integration")
"""

from AgentPlatform.core.base_agent import BaseAgent


class WebUIIntegrationEngineerAgent(BaseAgent):
    AGENT_ID = "webui_integration_engineer"

    def validate_output(self, output: str) -> tuple[bool, str]:
        valid, reason = super().validate_output(output)
        if not valid:
            return valid, reason
        return True, "OK"
