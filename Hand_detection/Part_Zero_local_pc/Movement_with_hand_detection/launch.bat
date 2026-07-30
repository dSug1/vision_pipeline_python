@echo off
REM ============================================================
REM  Vision Pipeline launcher — active Part Zero pipeline (see
REM  Claude/PART_ZERO.md). This is the server-client system: this folder is
REM  self-contained, builds its own LOCAL .venv here, and the server is the
REM  sibling folder ../Python_Server_MediaPipe_vision_pipeline (both now live
REM  under Part_Zero_local_pc/, see Claude/PART_ZERO_BIS.md).
REM  PythonApp_Main.py spawns the launcher, which starts the vision server +
REM  the client (moves a cube in a local window, not the OS cursor anymore —
REM  see Claude/PART_ZERO.md). Press 'q' in the camera window to stop.
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
