@echo off
cd /d "%~dp0..\.."

echo.
echo  Figma MCP - Starting server and relay
echo  ======================================
echo  MCP Server : http://localhost:7771
echo  Relay      : connects to Figma Desktop Bridge
echo.
echo  ACTION REQUIRED after both windows open:
echo    1. Open Figma Desktop
echo    2. Plugins ^> Development ^> Figma Desktop Bridge ^> Run
echo    3. Wait for "Local Ready" in the plugin panel
echo.

start "Figma MCP Server" cmd /k "uvicorn figma.mcp.server:app --host 0.0.0.0 --port 7771"
timeout /t 5 /nobreak >nul
start "Figma Relay" cmd /k "python figma\mcp\relay.py"

echo  Both started in separate windows.
echo  Press any key to close this window.
pause >nul
