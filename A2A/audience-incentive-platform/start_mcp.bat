@echo off
title MCP Server (port 8008)

echo Killing existing MCP Server on port 8008...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8008" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo Starting MCP Server...
cd /d "%~dp0"
python mcp/server.py
