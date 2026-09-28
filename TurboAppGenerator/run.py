#!/usr/bin/env python3
"""
TurboAppGenerator launcher
Usage: python run.py  (or double-click start.bat)
"""
import sys
import os
from pathlib import Path

# Force UTF-8 stdout/stderr on Windows (avoids cp1252 UnicodeEncodeError for arrows, emoji etc.)
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Configure sys.path FIRST — before any other imports ──────────────────────
ROOT = Path(__file__).resolve().parent  # TurboAppGenerator/

# WebUIGenerator MUST come before FigmaMockupGenerator — both have an agents/
# package and WebUIGenerator/agents/ has uigen_agent.py which FigmaMockupGenerator/agents/ doesn't.
# sys.path.insert(0,...) reverses order so add FigmaGenerator first (ends up second).
# WebAPIGenerator and MCPGenerator use distinctly-named modules (api_agents/
# api_config.py, mcp_agents/mcp_config.py respectively), so neither can collide
# with the other or with WebUIGenerator/FigmaMockupGenerator — their position in
# this list doesn't matter.
for _p in [str(ROOT / "FigmaMockupGenerator"), str(ROOT / "WebUIGenerator"),
           str(ROOT / "WebAPIGenerator"), str(ROOT / "MCPGenerator")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
# Result: sys.path[0]=MCPGenerator, sys.path[1]=WebAPIGenerator, sys.path[2]=WebUIGenerator, sys.path[3]=FigmaMockupGenerator

# The TurboAppGenerator root itself — so AgentPlatform.core.*/AgentPlatform.catalog.*
# (the shared persona-agent framework used by both WebUIGenerator and ProductForge)
# resolve as absolute imports from anywhere. "AgentPlatform" is a uniquely-named
# top-level package, so unlike "agents"/"config" above it has no collision to
# dodge — this can just be a plain, permanent sys.path entry.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load .env
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

port = int(os.environ.get("TURBOUI_PORT", 3000))
print(f"\n  TurboAppGenerator  —  http://localhost:{port}")
print(f"  Generate Web Apps or APIs from requirements\n")

# Now import server — sys.path is ready so agents.* and config resolve correctly
from agents.uigen_agent import list_projects  # warm up the agents package first
from API.server import app                    # then import server which uses it

import logging
import uvicorn

# Tee all output to a rolling log file so crashes are inspectable after the window closes
_log_file = ROOT / "server.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(_log_file), encoding="utf-8"),
    ],
)
print(f"  Logging to: {_log_file}\n")

uvicorn.run(app, host="0.0.0.0", port=port, reload=False, log_config=None)
