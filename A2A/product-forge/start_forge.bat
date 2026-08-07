@echo off
title Product Forge (port 8010)

echo Killing existing Product Forge on port 8010...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8010" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo Starting Product Forge...
cd /d "%~dp0\backend"
python app.py
