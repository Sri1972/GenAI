"""
MCPGenerator — central configuration.

Deliberately named mcp_config.py (not config.py) and paired with the mcp_agents/
package (not agents/) so this project's modules never collide with WebUIGenerator's
or FigmaMockupGenerator's same-named modules on sys.path — same reasoning as
WebAPIGenerator/api_config.py's own docstring.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT.parent / ".env")

TURBOUI_HOST = os.environ.get("TURBOUI_HOST", "localhost")

# Mirrors WebAPIGenerator/api_config.py's generated/ layout exactly.
GENERATED_ROOT = ROOT / "generated"
MCP_DIR        = GENERATED_ROOT / "mcp-servers"
MCP_DIR.mkdir(parents=True, exist_ok=True)

REGISTRY_FILE = GENERATED_ROOT / "projects-mcp.json"
PORTS_FILE    = GENERATED_ROOT / ".ports.json"

# Fresh port range, clear of WebUIGenerator's 8200+ and WebAPIGenerator's 8400+ pools.
PORT_START = int(os.environ.get("TURBOUI_MCP_PORT_START", "8500"))


def project_url(port: int) -> str:
    return f"http://{TURBOUI_HOST}:{port}"


def protected_env_file(project_name: str) -> Path:
    """
    A copy of the project's .env kept OUTSIDE its own directory — same rationale as
    WebAPIGenerator/api_config.py's protected_env_file: an external API's Basic Auth
    credentials (for the "API" source type) must survive even if something inside
    the generated project's own directory rewrites its .env.
    """
    return GENERATED_ROOT / f".env.{project_name}"
