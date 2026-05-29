@echo off
REM ============================================================
REM  Vision Pipeline launcher - Mouse Cursor application (RETIRED / parked)
REM  This is the ORIGINAL server-client system. It now lives in _not_used\ and
REM  is self-contained: it builds its own LOCAL .venv here (in MouseCursorApp\)
REM  and the server is the sibling folder _not_used\Python_Server_MediaPipe_vision_pipeline.
REM  PythonApp_Main.py spawns the launcher, which starts the vision server +
REM  cursor-control client (all in this venv). Press 'q' in the camera window to stop.
REM ============================================================

REM Work from this .bat's own folder (MouseCursorApp).
cd /d "%~dp0"

REM Create the local virtual environment on first run (deps from requirements.txt).
if not exist ".venv\Scripts\python.exe" (
    echo [launch] Creating local virtual environment (.venv)...
    python -m venv .venv
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

echo [launch] Starting Vision Pipeline (Mouse Cursor app)...
".venv\Scripts\python.exe" PythonApp_Main.py

echo.
echo [launch] Vision Pipeline exited.
pause
