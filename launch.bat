@echo off
REM ============================================================
REM  Vision Pipeline launcher
REM  - Uses the project's virtual environment (.venv)
REM  - Starts PythonApp_Main.py, which spawns the vision server
REM    and the client (cursor control).
REM  Press 'q' in the camera preview window to stop.
REM ============================================================

REM Move to the directory this .bat lives in (the project root)
cd /d "%~dp0"

REM Make sure the virtual environment exists
if not exist ".venv\Scripts\python.exe" (
    echo [launch] Virtual environment not found at .venv
    echo [launch] Create it with:  python -m venv .venv ^&^& .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

echo [launch] Starting Vision Pipeline...
".venv\Scripts\python.exe" PythonApp_Main.py

echo.
echo [launch] Vision Pipeline exited.
pause
