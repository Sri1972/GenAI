@echo off
cd /d "%~dp0"

:: ContentAgents test UI runs on port 8420
set CONTENTAGENTS_UI_PORT=8420

:: Kill any process already listening on port 8420
echo Checking for processes on port 8420...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8420 "') do (
    echo Killing PID %%a on port 8420
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo.
echo If this is your first run, install dependencies first:
echo     pip install -r ..\requirements.txt
echo.

:: Plain "python" can resolve to the Windows Store app-execution-alias stub,
:: which silently does nothing instead of running the real interpreter.
:: Use the known-good interpreter explicitly to avoid that.
set PYEXE=C:\Users\srikanth.c4\AppData\Local\Python\pythoncore-3.14-64\python.exe
if not exist "%PYEXE%" set PYEXE=python

"%PYEXE%" server.py
pause
