@echo off
title Mobility Global Storybook
cd /d "%~dp0"

echo ================================================
echo  Mobility Global Design System -- Storybook
echo ================================================
echo.

if not exist node_modules (
  echo [Installing dependencies...]
  call npm install
  if errorlevel 1 (
    echo ERROR: npm install failed.
    pause
    exit /b 1
  )
)

if not exist node_modules\.bin\storybook.cmd (
  echo ERROR: storybook.cmd not found in node_modules\.bin\
  echo Try running: npm install
  pause
  exit /b 1
)

echo Checking for processes on port 6006...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":6006 "') do (
    echo Killing PID %%a on port 6006
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo Starting Storybook at http://localhost:6006
echo Press Ctrl+C to stop.
echo.

node node_modules\storybook\bin\index.cjs dev --port 6006 --no-open

echo.
echo Storybook exited with code %ERRORLEVEL%
echo.
pause
