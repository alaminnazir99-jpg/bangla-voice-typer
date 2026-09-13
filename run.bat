@echo off
REM ============================================================
REM  Bangla VoiceTyper - Quick Run Script
REM ============================================================
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python main.py
) else (
    echo Virtual environment not found.
    echo Please run install.bat first.
    pause
)
