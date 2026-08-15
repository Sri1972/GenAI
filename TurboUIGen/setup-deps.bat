@echo off
REM ═══════════════════════════════════════════════════════════════════════════
REM  TurboUIGen — Full Setup (run once on a fresh machine)
REM  Prerequisites: Python 3.11+, Node.js 18+, npm
REM ═══════════════════════════════════════════════════════════════════════════
cd /d "%~dp0"

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║       TurboUIGen — Environment Setup         ║
echo  ╚══════════════════════════════════════════════╝
echo.

REM ── Step 0: Verify prerequisites ───────────────────────────────────────────
echo [0/5] Checking prerequisites...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python not found. Install Python 3.11+ from https://python.org
    exit /b 1
)
node --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Node.js not found. Install Node.js 18+ from https://nodejs.org
    exit /b 1
)
npm --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: npm not found. Comes with Node.js — reinstall Node.
    exit /b 1
)
echo       Python, Node.js, npm found.
echo.

REM ── Step 1: .env file ──────────────────────────────────────────────────────
echo [1/5] Checking .env configuration...
if not exist "%~dp0.env" (
    if exist "%~dp0.env.example" (
        copy "%~dp0.env.example" "%~dp0.env" >nul
        echo       Created .env from .env.example — EDIT IT with your API keys!
        echo       Required: LITELLM_API_BASE, LITELLM_API_KEY
        echo       Optional: FIGMA_ACCESS_TOKEN (for Figma-to-web)
        echo.
        echo       Open .env in your editor, fill in credentials, then re-run this script.
        pause
        exit /b 0
    ) else (
        echo WARNING: No .env file found. Copy .env.example or create one manually.
    )
) else (
    echo       .env exists.
)
echo.

REM ── Step 2: Python packages ────────────────────────────────────────────────
echo [2/5] Installing Python packages...
pip install -r "%~dp0requirements.txt" --quiet
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python package install failed. Check pip and network.
    exit /b 1
)
echo       Done.
echo.

REM ── Step 3: Playwright browsers ────────────────────────────────────────────
echo [3/5] Installing Playwright browser (chromium)...
playwright install chromium 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Playwright browser install failed — Figma screenshots won't work.
    echo          Run manually: playwright install chromium
)
echo       Done.
echo.

REM ── Step 4: Junction directory + shared npm modules ────────────────────────
REM Load TURBOUI_JUNCTION_DIR from .env if not already set
if "%TURBOUI_JUNCTION_DIR%"=="" (
    for /f "tokens=1,* delims==" %%a in ('findstr "TURBOUI_JUNCTION_DIR" "%~dp0.env" 2^>nul') do set JUNCTION_DIR=%%b
)
if "%JUNCTION_DIR%"=="" set JUNCTION_DIR=%TURBOUI_JUNCTION_DIR%
if "%JUNCTION_DIR%"=="" set JUNCTION_DIR=%USERPROFILE%\.turboui-junctions

echo [4/5] Setting up shared npm modules in %JUNCTION_DIR%\shared-nm ...
if not exist "%JUNCTION_DIR%" mkdir "%JUNCTION_DIR%"
if not exist "%JUNCTION_DIR%\shared-nm" mkdir "%JUNCTION_DIR%\shared-nm"

REM Copy the version-controlled package.json to the junction dir
copy /Y "%~dp0WebUIGenerator\agents\shared-nm-package.json" "%JUNCTION_DIR%\shared-nm\package.json" >nul 2>&1

cd /d "%JUNCTION_DIR%\shared-nm"
call npm install --quiet
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: npm install failed for shared modules.
    exit /b 1
)
echo       Done. (%JUNCTION_DIR%\shared-nm\node_modules)
echo.

REM ── Step 5: Design system (mgds) ──────────────────────────────────────────
cd /d "%~dp0"
echo [5/5] Checking design system...
if exist "%JUNCTION_DIR%\mgds\package.json" (
    echo       Design system found at %JUNCTION_DIR%\mgds
) else if exist "%~dp0UIDesignSystem\package.json" (
    echo       Copying design system to junction dir...
    if not exist "%JUNCTION_DIR%\mgds" mkdir "%JUNCTION_DIR%\mgds"
    xcopy /E /Y /Q "%~dp0UIDesignSystem\*" "%JUNCTION_DIR%\mgds\" >nul 2>&1
    echo       Done.
) else (
    echo       No design system found — generated apps will use default styling.
    echo       To add one later, place it at %JUNCTION_DIR%\mgds\
)
echo.

REM ── Done ────────────────────────────────────────────────────────────────────
echo  ╔══════════════════════════════════════════════╗
echo  ║         Setup Complete!                      ║
echo  ╠══════════════════════════════════════════════╣
echo  ║  To start TurboUIGen:                        ║
echo  ║    start.bat                                 ║
echo  ║    (or: python run.py)                       ║
echo  ║                                              ║
echo  ║  Opens at: http://localhost:3000             ║
echo  ╚══════════════════════════════════════════════╝
echo.
pause
