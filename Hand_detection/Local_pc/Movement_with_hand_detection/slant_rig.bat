@echo off
REM ============================================================
REM  T6's LEAN RIG -- two windows, one camera, ONE variable.
REM
REM    panel 1   shipped Horn                       [CONTROL, bit-exact]
REM    panel 2   Horn with its rotation AXIS steered by the palm's own
REM              foreshortening                     [SLANT slider drives this]
REM
REM  WHAT THIS IS FOR: the LEAN. Turning a held cube tips it up to ~27 deg,
REM  which you called a show-stopper. t5f measured WHY -- the cube turns about
REM  as FAR as the hand (that part is fine), it turns about the WRONG AXIS.
REM
REM  WHAT TO DO:
REM    Grab a cube with your palm toward the camera and TURN IT -- doorknob
REM    left/right for yaw, tip the fingers toward and away for pitch. Watch the
REM    two panels for the cube LEANING when it should only be turning.
REM    Then sweep the SLANT slider (panel 2 only) and find where it looks right.
REM
REM  !! 0%% IS BIT-EXACT SHIPPED HORN. Panel 1 is pinned there, so the left
REM     window is today's production behaviour and not an approximation of it.
REM     The rig starts panel 2 at 75%%.
REM
REM  MEASURED on the clean sweeps, median lean vs the instructed axis:
REM      yaw    22.0 -> 16.2 (50%%) -> 13.6 (75%%) -> 13.5 (100%%)
REM      pitch  14.8 -> 12.4 (75%%) -> 10.0 (100%%)
REM    and per-frame axis WANDER does not get worse: yaw 19.8 -> 19.6 p95,
REM    pitch 45.0 -> 22.1 p95 (it improves).
REM
REM  !! KNOWN LIMIT, and you will be able to see it: the correction switches
REM     itself OFF when the BACK of your hand faces the camera, and near
REM     edge-on. Past that fold the signal inverts, so panel 2 falls back to
REM     panel 1 rather than correcting backwards.
REM
REM  !! The bar is VISIBLY better, not measurably better. T6d had good numbers
REM     and was correctly rejected for feeling wrong.
REM
REM  Recording is ON: the take lands on E: as *_slant_rig.
REM  Press 'q' or close a window to stop; 'r' resets the counters.
REM ============================================================

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [slant_rig] No local .venv found ^-- run launch.bat first to set it up.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" "LiveSnapDebug.py" --slant-rig --record --tag slant_rig ^
    --note "T6 lean rig: panel1 shipped Horn control, panel2 Horn with the rotation axis steered by palm foreshortening; SLANT slider drives panel2." %*

echo.
echo [slant_rig] Session finished. The take is on E: under sessions\*_slant_rig.
pause
