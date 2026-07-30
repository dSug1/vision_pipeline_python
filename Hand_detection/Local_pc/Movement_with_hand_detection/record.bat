@echo off
REM ============================================================
REM  Records a labeled hand-landmark session for gesture classifier
REM  design work (Hand_detection/Claude/PART_ONE.md). Standalone --
REM  no socket, no cube window, just webcam + MediaPipe + JSON output
REM  to ../Python_Server_MediaPipe_vision_pipeline/recordings/. Reuses
REM  this folder's .venv (run launch.bat at least once first to create it).
REM  Usage: record.bat <label> [duration_seconds]   e.g. record.bat pinch_x3 4
REM  Recording starts after a short countdown and stops automatically --
REM  no keypress needed once it starts, since your hands are busy
REM  performing the gesture, not at the keyboard.
REM ============================================================

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [record] No local .venv found ^-- run launch.bat first to set it up.
    pause
    exit /b 1
)

if "%~1"=="" (
    echo Usage: record.bat ^<label^> [duration_seconds]   e.g. record.bat pinch_x3 4
    pause
    exit /b 1
)

if "%~2"=="" (
    ".venv\Scripts\python.exe" "..\Python_Server_MediaPipe_vision_pipeline\RecordSession.py" --label %1
) else (
    ".venv\Scripts\python.exe" "..\Python_Server_MediaPipe_vision_pipeline\RecordSession.py" --label %1 --duration %2
)

echo.
echo [record] Recording session finished.
pause
