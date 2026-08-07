"""
Design System configuration — single source of truth.

Set DESIGN_SYSTEM_PATH in your .env (or leave blank to use the bundled UIDesignSystem).

  # .env
  DESIGN_SYSTEM_PATH=C:/path/to/your/AnotherDesignSystem

Rules:
  - If DESIGN_SYSTEM_PATH is set and exists, use it.
  - Otherwise fall back to TurboUIGen/UIDesignSystem (the default Mobility Global DS).

The folder pointed to must contain:
  brand_tokens.json          — design tokens (colors, spacing, radius, typography, components)
  src/index.ts               — barrel export of all components (used by WebUIGenerator Vite alias)
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

_TURBOUI_ROOT  = Path(__file__).parent                         # TurboUIGen/
_DEFAULT_DS    = _TURBOUI_ROOT / "UIDesignSystem"              # bundled DS

_env_path = os.environ.get("DESIGN_SYSTEM_PATH", "").strip()

if _env_path:
    _candidate = Path(_env_path)
    if _candidate.exists():
        DS_ROOT = _candidate
    else:
        import warnings
        warnings.warn(
            f"DESIGN_SYSTEM_PATH='{_env_path}' does not exist — "
            f"falling back to bundled UIDesignSystem.",
            stacklevel=2,
        )
        DS_ROOT = _DEFAULT_DS
else:
    DS_ROOT = _DEFAULT_DS

# Derived paths — import these instead of re-computing in each module
DS_TOKENS_FILE  = DS_ROOT / "brand_tokens.json"
DS_SRC_INDEX    = DS_ROOT / "src" / "index.ts"
DS_STORYBOOK    = DS_ROOT / ".storybook"

# Storybook URL — configurable via STORYBOOK_URL in .env
STORYBOOK_URL: str = os.environ.get("STORYBOOK_URL", "").strip() or "http://localhost:6006"
