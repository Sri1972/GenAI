@echo off
echo === Installing TurboUI Dashboard dependencies ===
cd /d "%~dp0"
npm install
echo.
echo Done! Run "npm run dev" to start the dashboard.
pause
