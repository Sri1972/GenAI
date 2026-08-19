@echo off
echo === Installing Mobility Global Design System dependencies ===
cd /d "%~dp0"
npm install
echo.
echo Done! Run "npm run storybook" to start Storybook.
pause
