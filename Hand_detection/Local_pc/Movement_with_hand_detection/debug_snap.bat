@echo off
REM ============================================================
REM  Combined snap/translate debug view (Hand_detection/Claude/
REM  GESTURE_PIPELINE_SPEC.md §13): webcam + MediaPipe hand landmarks +
REM  semi-transparent cube overlay, all in ONE window -- temporary, to be
REM  removed once the new gesture set is built and verified (see
REM  LiveSnapDebug.py's header comment). Reuses this folder's .venv (run
REM  launch.bat at least once first to create it). No socket, no separate
REM  pygame window.
REM  Usage: debug_snap.bat [camera_index]   e.g. debug_snap.bat 1
REM  Press 'q' or close the window to stop.
REM ============================================================

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [debug_snap] No local .venv found ^-- run launch.bat first to set it up.
    pause
    exit /b 1
)

if "%~1"=="" (
    ".venv\Scripts\python.exe" "LiveSnapDebug.py"
) else (
    ".venv\Scripts\python.exe" "LiveSnapDebug.py" --camera-index %1
)

echo.
echo [debug_snap] Live debug session finished.
pause
