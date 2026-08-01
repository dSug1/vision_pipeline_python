@echo off
REM ============================================================
REM  Ad hoc diagnostic recorder for the translation-pivot fix
REM  (Claude/GESTURE_PIPELINE_SPEC.md §14.1): records landmarks + REAL
REM  cube ownership/position (via LiveSnapDebug.py's actual live
REM  snap/translate logic) for a 12s session (default), saved as JSON
REM  under "E:\Python\Recordings for vision_pipeline\Position_during_rotation"
REM  for offline analysis via AnalyzeTranslationPivot.py. Reuses this
REM  folder's .venv (run launch.bat at least once first to create it).
REM  Usage: record_translation_pivot_debug.bat [duration_seconds] [camera_index] [label]
REM    e.g. record_translation_pivot_debug.bat 12 0 large_pos1
REM         record_translation_pivot_debug.bat 12 0 small_pos2
REM ============================================================

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [record_translation_pivot_debug] No local .venv found ^-- run launch.bat first to set it up.
    pause
    exit /b 1
)

set DURATION=%1
if "%DURATION%"=="" set DURATION=12

set CAMERA=%2
if "%CAMERA%"=="" set CAMERA=0

set LABEL=%3
if "%LABEL%"=="" set LABEL=session

".venv\Scripts\python.exe" "RecordTranslationPivotDebug.py" --duration %DURATION% --camera-index %CAMERA% --label %LABEL%

echo.
echo [record_translation_pivot_debug] Recording session finished.
pause
