@echo off
cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in system PATH.
    echo Please install Python and ensure it is added to your PATH environment variable.
    pause
    exit /b 1
)

python launcher.py %*
if errorlevel 1 (
    echo.
    echo [ERROR] Application exited with error code %errorlevel%.
    pause
)
