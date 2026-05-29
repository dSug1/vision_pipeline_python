@echo off
REM ============================================================
REM  Virtual Drums - Finger Tracking launcher (self-contained)
REM  Creates/uses a LOCAL .venv inside THIS folder, so the folder
REM  can be copied anywhere with no external dependencies or links.
REM  Launching the app launches the vision pipeline (one process).
REM  Press 'q' or close the window to stop.
REM ============================================================

REM Work from this .bat's own folder (the self-contained app root).
cd /d "%~dp0"

REM Create the local virtual environment on first run.
if not exist ".venv\Scripts\python.exe" (
    echo [launch] Creating local virtual environment (.venv)...
    python -m venv .venv
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

echo [launch] Starting Virtual Drums...
".venv\Scripts\python.exe" main.py

echo.
echo [launch] Virtual Drums exited.
pause
