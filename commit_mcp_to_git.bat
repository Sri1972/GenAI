@echo off
cd /d "D:\SourceCode\GenAI"

echo Marking directory as safe for Git...
git config --global --add safe.directory D:/SourceCode/GenAI

echo --------------------------------------------
echo Initializing new Git repo and cleaning up
echo --------------------------------------------
if exist .git (
    echo Removing existing Git data...
    rmdir /s /q .git
)

git init

echo --------------------------------------------
echo Creating .gitignore file
echo --------------------------------------------
(
    echo # --- Environment files ---
    echo MCP\client\pmo\.env
    echo MCP\client\nlp_to_structured_data\.env

    echo # --- Backup folders ---
    echo Backups\

    echo # --- Python cache ---
    echo __pycache__\
    echo MCP\server\pmo\__pycache__\
    echo MCP\server\nlp_to_structured_data\__pycache__\
    echo MCP\server\charts\mcp-d3-stdio-custom\__pycache__\
    echo MCP\client\pmo\__pycache__\
    echo MCP/client/ppt/LLM_PROVIDERS.md

    echo # --- Common virtual environments ---
    echo venv\
    echo .env\
    echo *.env

    echo # --- Logs and temporary files ---
    echo *.log
    echo *.tmp

    echo # --- IDE / Editor files ---
    echo .vscode\
    echo .idea\
    echo *.iml

    echo # --- Node / npm artifacts ---
    echo node_modules\
    echo npm-debug.log*

    echo # --- OS junk ---
    echo .DS_Store
    echo Thumbs.db
) > .gitignore

echo --------------------------------------------
echo Connecting to remote GitHub repo
echo --------------------------------------------
git remote add origin https://github.com/Sri1972/GenAI.git

echo --------------------------------------------
echo Adding files and committing
echo --------------------------------------------
git add .
git commit -m "Clean workspace push"

echo --------------------------------------------
echo Forcing push to GitHub main branch
echo --------------------------------------------
git branch -M main
git push -u origin main --force

echo Done! Repo synced with GitHub.
pause