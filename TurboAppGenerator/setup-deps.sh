#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
#  TurboUIGen — Full Setup (run once on a fresh machine)
#  Prerequisites: Python 3.11+, Node.js 18+, npm
#  Usage: bash setup-deps.sh
# ═══════════════════════════════════════════════════════════════════════════════
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║       TurboUIGen — Environment Setup         ║"
echo "  ╚══════════════════════════════════════════════╝"
echo ""

# ── Step 0: Verify prerequisites ─────────────────────────────────────────────
echo "[0/5] Checking prerequisites..."
command -v python3 >/dev/null 2>&1 || { echo "ERROR: Python 3 not found. Install Python 3.11+"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "ERROR: Node.js not found. Install Node.js 18+"; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "ERROR: npm not found."; exit 1; }
echo "      Python, Node.js, npm found."
echo ""

# ── Step 1: .env file ────────────────────────────────────────────────────────
echo "[1/5] Checking .env configuration..."
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    if [ -f "$SCRIPT_DIR/.env.example" ]; then
        cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
        echo "      Created .env from .env.example — EDIT IT with your API keys!"
        echo "      Required: LITELLM_API_BASE, LITELLM_API_KEY"
        echo "      Optional: FIGMA_ACCESS_TOKEN (for Figma-to-web)"
        echo ""
        echo "      Edit .env, then re-run this script."
        exit 0
    else
        echo "WARNING: No .env file found."
    fi
else
    echo "      .env exists."
fi
echo ""

# ── Load TURBOUI_JUNCTION_DIR from .env ───────────────────────────────────────
if [ -z "$TURBOUI_JUNCTION_DIR" ]; then
    TURBOUI_JUNCTION_DIR=$(grep -E "^TURBOUI_JUNCTION_DIR=" "$SCRIPT_DIR/.env" 2>/dev/null | cut -d'=' -f2- | tr -d '\r')
fi
if [ -z "$TURBOUI_JUNCTION_DIR" ]; then
    TURBOUI_JUNCTION_DIR="$HOME/.turboui-junctions"
fi
export TURBOUI_JUNCTION_DIR

# ── Step 2: Python packages ──────────────────────────────────────────────────
echo "[2/5] Installing Python packages..."
pip3 install -r "$SCRIPT_DIR/requirements.txt" --quiet
echo "      Done."
echo ""

# ── Step 3: Playwright browsers ──────────────────────────────────────────────
echo "[3/5] Installing Playwright browser (chromium)..."
python3 -m playwright install chromium 2>/dev/null || {
    echo "WARNING: Playwright browser install failed — Figma screenshots won't work."
    echo "         Run manually: python3 -m playwright install chromium"
}
echo "      Done."
echo ""

# ── Step 4: Junction directory + shared npm modules ──────────────────────────
echo "[4/5] Setting up shared npm modules in $TURBOUI_JUNCTION_DIR/shared-nm ..."
mkdir -p "$TURBOUI_JUNCTION_DIR/shared-nm"

# Copy the version-controlled package.json to the junction dir
cp "$SCRIPT_DIR/WebUIGenerator/agents/shared-nm-package.json" "$TURBOUI_JUNCTION_DIR/shared-nm/package.json"

cd "$TURBOUI_JUNCTION_DIR/shared-nm"
npm install --quiet
echo "      Done. ($TURBOUI_JUNCTION_DIR/shared-nm/node_modules)"
echo ""

# ── Step 5: Design system ────────────────────────────────────────────────────
cd "$SCRIPT_DIR"
echo "[5/5] Checking design system..."
if [ -f "$TURBOUI_JUNCTION_DIR/mgds/package.json" ]; then
    echo "      Design system found at $TURBOUI_JUNCTION_DIR/mgds"
elif [ -f "$SCRIPT_DIR/UIDesignSystem/package.json" ]; then
    echo "      Copying design system to junction dir..."
    mkdir -p "$TURBOUI_JUNCTION_DIR/mgds"
    cp -r "$SCRIPT_DIR/UIDesignSystem/"* "$TURBOUI_JUNCTION_DIR/mgds/"
    echo "      Done."
else
    echo "      No design system found — generated apps will use default styling."
fi
echo ""

# ── Done ──────────────────────────────────────────────────────────────────────
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║         Setup Complete!                      ║"
echo "  ╠══════════════════════════════════════════════╣"
echo "  ║  To start TurboUIGen:                        ║"
echo "  ║    python3 run.py                            ║"
echo "  ║                                              ║"
echo "  ║  Opens at: http://localhost:3000             ║"
echo "  ╚══════════════════════════════════════════════╝"
echo ""
