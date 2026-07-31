@echo off
REM ============================================================
REM  Stage 4 live debug tool (Hand_detection/Claude/GESTURE_PIPELINE_SPEC.md
REM  §3 Stage 4): webcam + MediaPipe + trained pinch classifier + event
REM  layer, all live. Reuses this folder's .venv (run launch.bat at least
REM  once first to create it). No recording, no cube window.
REM  Usage: debug.bat [camera_index]   e.g. debug.bat 1
REM  Press 'q' or close the window to stop.
REM ============================================================

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [debug] No local .venv found ^-- run launch.bat first to set it up.
    pause
    exit /b 1
)

if "%~1"=="" (
    ".venv\Scripts\python.exe" "LiveGestureDebug.py"
) else (
    ".venv\Scripts\python.exe" "LiveGestureDebug.py" --camera-index %1
)

echo.
echo [debug] Live debug session finished.
pause
