@echo off
cd /d "%~dp0"

:: Kill any process already listening on port 3000
echo Checking for processes on port 3000...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":3000 "') do (
    echo Killing PID %%a on port 3000
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

python run.py
pause
