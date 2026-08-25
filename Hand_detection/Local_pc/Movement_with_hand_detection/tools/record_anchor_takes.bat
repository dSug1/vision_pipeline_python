@echo off
REM ============================================================
REM  B4 ANCHOR + ROTATION study - the six purpose-built takes.
REM  (Hand_detection/Claude/GESTURE_PIPELINE_SPEC.md sections 16.12, 16.13)
REM
REM  WHY SIX SEPARATE TAKES AND NOT ONE LONG ONE: section 16.5's rule. The
REM  sink must be read PER TAKE and never pooled, because pitch-sink and
REM  yaw-sink have OPPOSITE SIGNS and cancel when mixed - that is exactly
REM  how 16.4 produced a confident, wrong, three-decimal answer that 16.5
REM  then had to overturn. Naming each take is what keeps them separable.
REM
REM  Raw landmarks are recorded, so EVERY candidate (14.1, tip-weighted
REM  14.1, palm-centroid translation, Kabsch rotation, and the combination)
REM  is replayed OFFLINE from these takes. The content is what matters -
REM  you do not need the candidates on screen while recording.
REM
REM  HOLD A CUBE THROUGHOUT EVERY TAKE. A take with no cube held measures
REM  nothing, since all of these metrics are about a HELD object.
REM
REM  Press 'q' in a window to end each take. Takes are ~45-60 s each,
REM  about 5 minutes in total. Recording is automatic.
REM ============================================================

cd /d "%~dp0" & cd ..

if not exist ".venv\Scripts\python.exe" (
    echo [record] No local .venv found ^-- run launch.bat first to set it up.
    pause
    exit /b 1
)

set PY=.venv\Scripts\python.exe
set TOOL=LiveBlockPredictionDebug.py
set COMMON=--arms 2

echo.
echo ============================================================
echo  SIX TAKES. Grab a cube at the start of each one and KEEP IT HELD.
echo  Press 'q' in a window to finish a take and move to the next.
echo ============================================================
echo.
pause

echo.
echo [1/6] finger_flex_hold - keep the PALM STILL, flex and extend the FINGERS
echo       Isolates the 16.10 defect: only the palm should move the cube.
pause
%PY% %TOOL% %COMMON% --sequence finger_flex_hold --prompt "PALM STILL - flex and extend the FINGERS" --note "isolates the fingertip contribution to the anchor"

echo.
echo [2/6] wrist_rotate_still_palm - ROTATE THE WRIST, keep the palm centroid put
echo       Isolates the rotation channel: Kabsch vs Gram-Schmidt.
pause
%PY% %TOOL% %COMMON% --sequence wrist_rotate_still_palm --prompt "ROTATE THE WRIST - keep the palm centre in one place" --note "isolates the rotation estimator"

echo.
echo [3/6] yaw_hold_cube - sustained YAW, 10+ slow cycles
echo       The SINK on the yaw axis. No existing take contains this.
pause
%PY% %TOOL% %COMMON% --sequence yaw_hold_cube --prompt "SLOW SUSTAINED YAW - turn the hand edge-on and back, 10+ cycles" --note "sink, yaw axis - read PER TAKE, never pooled"

echo.
echo [4/6] pitch_crossing_cube - PITCH across the horizontal, 10+ cycles
echo       The SINK on the pitch axis, plus N12.
pause
%PY% %TOOL% %COMMON% --sequence pitch_crossing_cube --prompt "PITCH ACROSS THE HORIZONTAL - fingers up then down, 10+ cycles" --note "sink, pitch axis - OPPOSITE SIGN to yaw, never pool the two"

echo.
echo [5/6] depth_sweep_cube - move the hand TOWARD and AWAY from the camera
echo       Is a scale term needed, and is a frozen scale safe?
pause
%PY% %TOOL% %COMMON% --sequence depth_sweep_cube --prompt "MOVE THE HAND TOWARD AND AWAY FROM THE CAMERA" --note "tests the metres-to-pixels scale term"

echo.
echo [6/6] back_of_hand_hold - turn the hand PALM-AWAY while holding
echo       The band where 0.18 says the palm reconstruction collapses.
pause
%PY% %TOOL% %COMMON% --sequence back_of_hand_hold --prompt "TURN THE HAND PALM-AWAY AND BACK, holding the cube" --note "orientation reliability at back-of-hand (0.18)"

echo.
echo ============================================================
echo  All six takes recorded to
echo  E:\Python\Recordings for vision_pipeline\Recordings_prediction_gate
echo ============================================================
pause
