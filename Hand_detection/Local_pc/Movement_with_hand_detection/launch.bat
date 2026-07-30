@echo off
REM ============================================================
REM  Vision Pipeline launcher — the PC pipeline. Started as Part Zero (see
REM  Hand_detection/Claude/PART_ZERO.md) and now also carries Part One's
REM  gesture work (Hand_detection/Claude/PART_ONE.md). This is the
REM  server-client system: this folder is self-contained, builds its own
REM  LOCAL .venv here, and the server is the sibling folder
REM  ../Python_Server_MediaPipe_vision_pipeline (both under
REM  Hand_detection/Local_pc/ — renamed from Part_Zero_local_pc once Part
REM  One started building on top of it, see PART_ONE.md §1).
REM  PythonApp_Main.py spawns the launcher, which starts the vision server +
REM  the client (moves cube(s) in a local window, driven by hand gestures —
REM  see PART_ZERO.md and PART_ONE.md). Press 'q' in the camera window
REM  to stop.
REM ============================================================

REM Work from this .bat's own folder (Movement_with_hand_detection).
cd /d "%~dp0"

REM Create the local virtual environment on first run (deps from requirements.txt).
if not exist ".venv\Scripts\python.exe" (
    echo [launch] Creating local virtual environment ^(.venv^)...
    python -m venv .venv
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

echo [launch] Starting Vision Pipeline...
".venv\Scripts\python.exe" PythonApp_Main.py

echo.
echo [launch] Vision Pipeline exited.
pause
