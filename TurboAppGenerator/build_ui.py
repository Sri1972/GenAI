#!/usr/bin/env python3
"""Build the TurboUIGen React UI. Run from anywhere: python build_ui.py"""
import subprocess, sys
from pathlib import Path

UI_DIR = Path(__file__).resolve().parent / "UI"
result = subprocess.run(
    ["node", "node_modules/vite/bin/vite.js", "build"],
    cwd=str(UI_DIR),
)
sys.exit(result.returncode)
