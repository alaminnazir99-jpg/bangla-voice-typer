@echo off
REM ============================================================
REM  Hotkey diagnostic test
REM  Press Ctrl+Shift+B within 15 seconds and watch the result
REM ============================================================
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python hotkey_test.py
) else (
    echo Virtual environment not found.
    pause
)
pause
