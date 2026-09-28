@echo off
cd /d "%~dp0"
set PATH=C:\Program Files\nodejs;%PATH%
echo.
echo  ⚡ TurboUIGen CLI
echo  Requires API to be running (start-api.bat)
echo.
echo  Commands:
echo    generate "your app description"
echo    list
echo    start   ^<project-name^>
echo    stop    ^<project-name^>
echo    delete  ^<project-name^>
echo    open    ^<project-name^>
echo.
if "%~1"=="" (
    echo  Usage: start-cli.bat ^<command^> [args]
    echo  Example: start-cli.bat generate "IPL dashboard"
    pause
    exit /b
)
python -m cli.client %*
pause
