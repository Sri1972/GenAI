@echo off
title AutoAudience Agent (port 8005)

echo Killing existing AutoAudience on port 8005...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8005" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo Starting AutoAudience Agent...
cd /d "%~dp0\autoaudience\backend"
python app.py
