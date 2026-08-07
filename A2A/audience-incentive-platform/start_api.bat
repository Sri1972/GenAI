@echo off
title Data API (port 8007)

echo Killing existing Data API on port 8007...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8007" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo Starting Data API...
cd /d "%~dp0"
python api/server.py
