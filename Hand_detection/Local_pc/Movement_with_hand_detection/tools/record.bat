@echo off
REM ============================================================
REM  Records a labeled hand-landmark session for gesture classifier
REM  design work (Hand_detection/Claude/GESTURE_PIPELINE_SPEC.md). Standalone
REM  -- no socket, no cube window, just webcam + MediaPipe + JSON output to
REM  E:\Python\Recordings for vision_pipeline\Pencil_style_grip\. Reuses this
REM  folder's .venv (run launch.bat at least once first to create it).
REM  Usage: record.bat <label> <protocol> [duration_seconds]
REM    e.g. record.bat pinch_front held_state
REM         record.bat pinch_cycles_front cyclic
REM  <protocol> is REQUIRED: "held_state" (one continuous hold, every frame
REM  is the labeled class -- pinch_*/open_hand_*/fist_*/rotating_no_pinch*)
REM  or "cyclic" (3 grip/release reps -- pinch_cycles_*/pinch_rotate_release).
REM  See RecordSession.py's header comment for why this is required and not
REM  inferred from the label.
REM  Recording starts after a short countdown and stops automatically --
REM  no keypress needed once it starts, since your hands are busy
REM  performing the gesture, not at the keyboard.
REM ============================================================

cd /d "%~dp0" & cd ..

if not exist ".venv\Scripts\python.exe" (
    echo [record] No local .venv found ^-- run launch.bat first to set it up.
    pause
    exit /b 1
)

if "%~2"=="" (
    echo Usage: record.bat ^<label^> ^<held_state^|cyclic^> [duration_seconds]
    echo   e.g. record.bat pinch_front held_state
    echo        record.bat pinch_cycles_front cyclic
    pause
    exit /b 1
)

if "%~3"=="" (
    ".venv\Scripts\python.exe" "..\Python_Server_MediaPipe_vision_pipeline\RecordSession.py" --label %1 --protocol %2
) else (
    ".venv\Scripts\python.exe" "..\Python_Server_MediaPipe_vision_pipeline\RecordSession.py" --label %1 --protocol %2 --duration %3
)

echo.
echo [record] Recording session finished.
pause
