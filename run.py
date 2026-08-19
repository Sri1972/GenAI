#!/usr/bin/env python3
"""
TurboUIGen launcher
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
ROOT = Path(__file__).resolve().parent  # TurboUIGen/

# WebUIGenerator MUST come before FigmaMockupGenerator — both have an agents/
# package and WebUIGenerator/agents/ has uigen_agent.py which FigmaMockupGenerator/agents/ doesn't.
# sys.path.insert(0,...) reverses order so add FigmaGenerator first (ends up second).
for _p in [str(ROOT / "FigmaMockupGenerator"), str(ROOT / "WebUIGenerator")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
# Result: sys.path[0]=WebUIGenerator, sys.path[1]=FigmaMockupGenerator

# Load .env
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

port = int(os.environ.get("TURBOUI_PORT", 3000))
print(f"\n  TurboUIGen  —  http://localhost:{port}")
print(f"  UI + API served together\n")

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
