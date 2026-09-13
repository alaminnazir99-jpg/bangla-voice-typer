@echo off
REM ============================================================
REM  Bangla VoiceTyper - Install & Run Script
REM  Creates a venv, installs dependencies, and runs the app
REM ============================================================
setlocal
cd /d "%~dp0"

echo.
echo ============================================
echo   Bangla VoiceTyper - Installer
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    echo.
    echo Please install Python 3.10+ from https://python.org
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [1/3] Creating virtual environment...
if not exist ".venv" python -m venv .venv
call .venv\Scripts\activate.bat

echo.
echo [2/3] Installing dependencies (this may take a few minutes)...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip!
    pause
    exit /b 1
)
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies!
    echo.
    echo Please check your internet connection and try again.
    pause
    exit /b 1
)

echo.
echo [3/3] Setup complete!
echo.
echo To run the app:
echo     .venv\Scripts\python main.py
echo.
echo Or use: run.bat
echo.

pause
