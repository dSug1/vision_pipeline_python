@echo off
REM ============================================================
REM  Perception-layer scripted-sequence recorder
REM  (Claude/PERCEPTION_LAYER_SPEC.md §7.2, merged queue items 0.1/0.2b).
REM  Records RAW MediaPipe output only -- no gesture logic, no cube -- to
REM  "E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\
REM   sessions\<timestamp>_<sequence>\".
REM  Reuses this folder's .venv (run launch.bat once first to create it).
REM
REM  Usage: record_perception_sequence.bat <sequence> [duration_s] [camera_index]
REM    e.g. record_perception_sequence.bat static_hold
REM         record_perception_sequence.bat non_crossing 30
REM         record_perception_sequence.bat pitch_sweep_slow 30 0
REM
REM  Sequences: static_hold, non_crossing, pitch_sweep_slow, pitch_sweep_fast,
REM             palm_back, occlusion, two_hand_overlap, two_hand_near_miss,
REM             depth_sweep,
REM             known_right_palm, known_right_back, known_left_palm,
REM             known_left_back
REM ============================================================

cd /d "%~dp0" & cd ..

if not exist ".venv\Scripts\python.exe" (
    echo [perception] No local .venv found ^-- run launch.bat first to set it up.
    pause
    exit /b 1
)

if "%1"=="" (
    echo [perception] No sequence given.
    echo   Usage: record_perception_sequence.bat ^<sequence^> [duration_s] [camera_index]
    pause
    exit /b 1
)

set SEQ=%1
set EXTRA=

if not "%2"=="" set EXTRA=%EXTRA% --duration %2
if not "%3"=="" set EXTRA=%EXTRA% --camera-index %3
if /I "%4"=="local" set EXTRA=%EXTRA% --local

".venv\Scripts\python.exe" "tools\RecordPerceptionSequence.py" --sequence %SEQ%%EXTRA%

echo.
echo [perception] Sequence finished.
pause
