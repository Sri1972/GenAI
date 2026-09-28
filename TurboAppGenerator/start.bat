@echo off
cd /d "%~dp0"

:: TurboAppGenerator runs on port 3100 (TurboUIGen uses 3000)
set TURBOUI_PORT=3100

:: Kill any process already listening on port 3100
echo Checking for processes on port 3100...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":3100 "') do (
    echo Killing PID %%a on port 3100
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

python run.py
pause
