"""
TurboUIGen — central configuration
===================================
All service URLs and ports read from environment / .env.
Import this module instead of repeating os.environ.get() everywhere.

Local development (.env defaults):
  TURBOUI_HOST       = localhost
  TURBOUI_PORT       = 8080
  TURBOUI_MCP_HOST   = localhost
  TURBOUI_MCP_PORT   = 7771

AWS deployment — only change these two in .env:
  TURBOUI_HOST       = your-ec2-ip-or-domain.com
  TURBOUI_MCP_HOST   = your-ec2-ip-or-domain.com  (same host usually)

Generated folder structure:
  generated/
    web-apps/        ← React/Vite and HTML apps generated from prompts or Figma URLs
    figma-mockups/   ← Screenshots and exports from Figma wireframe builds
    _figma_projects/ ← Figma mockup project metadata (JSON records)
    _figma_specs/    ← Figma spec files
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# ── Host / ports ───────────────────────────────────────────────────────────────

# The public hostname used to construct project preview URLs.
# On AWS set to: ec2-1-2-3-4.compute.amazonaws.com  or  your-domain.com
TURBOUI_HOST = os.environ.get("TURBOUI_HOST", "localhost")
TURBOUI_PORT = int(os.environ.get("TURBOUI_PORT", "8080"))

# Figma MCP server
MCP_HOST = os.environ.get("TURBOUI_MCP_HOST", "localhost")
MCP_PORT = int(os.environ.get("TURBOUI_MCP_PORT", "7771"))

# Base ports for generated projects
HTML_PORT_START  = int(os.environ.get("TURBOUI_HTML_PORT_START",  "6100"))
REACT_PORT_START = int(os.environ.get("TURBOUI_REACT_PORT_START", "5173"))
API_PORT_START   = int(os.environ.get("TURBOUI_API_PORT_START",   "8100"))

# ── Derived URLs ───────────────────────────────────────────────────────────────

# TurboUIGen API base URL
API_URL = f"http://{TURBOUI_HOST}:{TURBOUI_PORT}"

# Figma MCP server URLs
MCP_URL      = f"http://{MCP_HOST}:{MCP_PORT}"
MCP_ENDPOINT = f"{MCP_URL}/mcp"
RELAY_URL    = os.environ.get("TURBOUI_RELAY_URL", f"ws://{MCP_HOST}:{MCP_PORT}/relay")

# ── Generated folder structure ────────────────────────────────────────────────

GENERATED_ROOT   = Path(__file__).parent / "generated"
WEB_APPS_DIR     = GENERATED_ROOT / "web-apps"      # React/Vite + HTML projects
FIGMA_MOCKUPS_DIR = GENERATED_ROOT / "figma-mockups" # Figma wireframe screenshots/exports

# Only create the directory this sub-project actually uses
WEB_APPS_DIR.mkdir(parents=True, exist_ok=True)

# Registry files live in the generated root (not in sub-folders)
REGISTRY_FILE   = GENERATED_ROOT / "projects-web-apps.json"
PORTS_FILE      = GENERATED_ROOT / ".ports.json"
HTML_PORTS_FILE = GENERATED_ROOT / ".html_ports.json"  # Legacy — no longer used

# ── Helpers ────────────────────────────────────────────────────────────────────

def project_url(project_name: str, port: int, proj_type: str = "react") -> str:
    """Return the browser URL for a generated project."""
    host = TURBOUI_HOST
    if proj_type == "html":
        return f"http://{host}:{port}/{project_name}/"
    return f"http://{host}:{port}"

def health_url(port: int, proj_type: str = "html") -> str:
    """Return the health check URL for a running project server."""
    if proj_type == "html":
        return f"http://localhost:{port}/_health"
    return f"http://localhost:{port}/"
