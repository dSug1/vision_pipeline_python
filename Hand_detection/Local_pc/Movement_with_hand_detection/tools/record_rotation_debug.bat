@echo off
REM ============================================================
REM  Ad hoc diagnostic recorder for rotation-while-snapped
REM  (Hand_detection/Claude/HANDOFF_SNAP_ROTATE_RELEASE.md §2): records
REM  landmarks + computed orientation + glitch flag + cube orientation for
REM  an 8s session (default), saved as JSON under
REM  rotation_debug_recordings\ for offline analysis. Reuses this folder's
REM  .venv (run launch.bat at least once first to create it).
REM  Usage: record_rotation_debug.bat [duration_seconds] [camera_index]
REM    e.g. record_rotation_debug.bat 8
REM         record_rotation_debug.bat 10 1
REM ============================================================

cd /d "%~dp0" & cd ..

if not exist ".venv\Scripts\python.exe" (
    echo [record_rotation_debug] No local .venv found ^-- run launch.bat first to set it up.
    pause
    exit /b 1
)

set DURATION=%1
if "%DURATION%"=="" set DURATION=8

set CAMERA=%2
if "%CAMERA%"=="" set CAMERA=0

".venv\Scripts\python.exe" "tools\RecordRotationDebug.py" --duration %DURATION% --camera-index %CAMERA%

echo.
echo [record_rotation_debug] Recording session finished.
pause
