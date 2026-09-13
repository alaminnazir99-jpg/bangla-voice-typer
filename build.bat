@echo off
REM ============================================================
REM  Bangla VoiceTyper - Windows Build Script
REM  Build a standalone .exe using PyInstaller
REM ============================================================
setlocal

echo.
echo ============================================
echo   Bangla VoiceTyper - Build Script
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Install Python 3.10+ from python.org
    pause
    exit /b 1
)

echo [1/4] Creating virtual environment...
if not exist ".venv" python -m venv .venv
call .venv\Scripts\activate.bat

echo.
echo [2/4] Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt

echo.
echo [3/4] Installing build tools...
pip install pyinstaller

echo.
echo [4/4] Building executable...
if not exist "build" mkdir build
if not exist "dist" mkdir dist

pyinstaller --noconfirm ^
    --name "BanglaVoiceTyper" ^
    --windowed ^
    --onefile ^
    --add-data "config;config" ^
    --hidden-import pyaudio ^
    --hidden-import whisper ^
    --hidden-import vosk ^
    --hidden-import keyboard ^
    --hidden-import pynput ^
    --hidden-import PyQt6 ^
    main.py

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Build successful!
echo   Executable: dist\BanglaVoiceTyper.exe
echo ============================================
pause
