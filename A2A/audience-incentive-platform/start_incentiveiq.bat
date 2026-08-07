@echo off
title IncentiveIQ Agent (port 8006)

echo Killing existing IncentiveIQ on port 8006...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8006" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo Starting IncentiveIQ Agent...
cd /d "%~dp0\incentiveiq\backend"
python app.py
