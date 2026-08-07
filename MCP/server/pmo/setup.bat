@echo off
echo ========================================
echo PMO MCP Server - Setup Script
echo ========================================
echo.

echo Step 1: Copying metadata files...
if not exist metadata mkdir metadata
xcopy /E /I /Y "..\metadata\*" "metadata\"
echo Metadata files copied!
echo.

echo Step 2: Creating .env file from example...
if not exist .env (
    copy "config\.env.example" ".env"
    echo .env file created! Please edit it with your settings.
) else (
    echo .env file already exists, skipping...
)
echo.

echo Step 3: Installing Python dependencies...
pip install -r requirements.txt
echo.

echo ========================================
echo Setup complete!
echo ========================================
echo.
echo Next steps:
echo 1. Edit .env file with your API configuration
echo 2. Edit config\config.yaml for advanced settings (optional)
echo 3. Edit config\prompts.yaml to customize prompts (optional)
echo 4. Run: python server.py
echo.
pause
