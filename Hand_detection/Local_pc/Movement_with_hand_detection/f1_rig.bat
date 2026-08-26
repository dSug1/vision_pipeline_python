@echo off
REM ============================================================
REM  F1's THREE-WINDOW RIG -- one camera, three configurations.
REM
REM    panel 1  STEP 0   palm anchor, no fingertip trim   [SHIPPED / CONTROL]
REM    panel 2  STEP 2   fingertip BARYCENTRE drives snap + translation
REM    panel 3  STEP 4   step 2 PLUS the fingertip ROTATION trim
REM
REM  Each panel differs from the one before it by EXACTLY ONE step, so a
REM  difference between two panels has one cause. One camera, one detection,
REM  one identity resolution and ONE shared fingertip filter feed all three.
REM
REM  WHAT TO JUDGE, panel by panel:
REM    2 vs 1  does grabbing and dragging by the FINGERTIPS feel better than by
REM            the palm? Watch for the object WANDERING while your hand is still
REM            and you only shift your grip -- measured at 1 cm typical, 6 cm at
REM            p95, and only you can say whether that reads as natural or wrong.
REM    3 vs 2  does the fingertip TRIM earn its place? Turn a held object with
REM            your fingers, wrist still. This is the assembly-alignment case
REM            F1 exists for.
REM
REM  !! The bar is VISIBLY better, not measurably better. T6d had the best
REM     numbers of any correction attempted and was correctly rejected, because
REM     4.83 deg is below what an eye resolves on a 40-80 px cube.
REM
REM  Recording is ON: the take lands on E: as *_f1_rig. The drive is woken and
REM  retried automatically now (queue N4), so a sleeping E: no longer costs the
REM  take.
REM
REM  Press 'q' or close a window to stop; 'r' resets the counters.
REM ============================================================

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [f1_rig] No local .venv found ^-- run launch.bat first to set it up.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" "LiveSnapDebug.py" --f1-rig --record --tag f1_rig ^
    --note "F1 three-window rig: panel1 STEP0 palm control, panel2 STEP2 fingertip barycentre, panel3 STEP4 barycentre + rotation trim." %*

echo.
echo [f1_rig] Session finished. The take is on E: under sessions\*_f1_rig.
pause
