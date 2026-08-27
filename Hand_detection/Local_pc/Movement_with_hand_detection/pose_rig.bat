@echo off
REM ============================================================
REM  YOUR STRATEGY, LIVE -- three windows, one camera.
REM
REM    panel 1   shipped Horn                  [CONTROL, bit-exact production]
REM    panel 2   HALF 1 + HALF 2, palm landmarks      [POSE slider drives this]
REM    panel 3   HALF 1 + HALF 2, finger landmarks    [POSE slider drives this]
REM
REM  HALF 1 = the sigma->angle regression fitted from your six takes.
REM  HALF 2 = everything measured against a canonical FROZEN AT THE GRAB.
REM  Panels 2 and 3 do NOT use Horn's axis or angle at all. All three degrees of
REM  freedom come from pixels: the angle from the regression, the axis from the
REM  direction the palm did not foreshorten, the roll from the knuckle row.
REM
REM  WHAT TO JUDGE:
REM    2 vs 1   does the LEAN go away? Grab a cube palm-to-camera and turn it,
REM             doorknob for yaw, fingers toward/away for pitch.
REM    3 vs 2   fingers or palm? The takes cannot answer this -- they are all
REM             OPEN hands and the game GRIPS.
REM
REM  MEASURED BEFOREHAND, so you know what to expect:
REM    yaw lean   27.2 -> 8.6 deg   (the best this row has produced)
REM    pitch lean 15.5 -> 15.7 deg  (no change)
REM    per-frame orientation jump: median 2.98 -> 2.41 (BETTER)
REM                                p95    12.6 -> 30.3 (2.4x WORSE)
REM
REM  !! SO EXPECT IT SMOOTHER MOST OF THE TIME AND JUMPIER OCCASIONALLY. The
REM     previous attempt was rejected for exactly that tail, at 1.8x. This is
REM     2.4x but fixes three times as much lean. Whether that trade is worth it
REM     is the question, and only your hand can answer it.
REM
REM  !! THE POSE SLIDER'S MIDDLE IS WORSE THAN EITHER END -- 53.7 deg of lean at
REM     50%%, against 27.2 at 0%% and 8.6 at 100%%. It opens at 100%%. Treat the
REM     slider as a switch, not a dial.
REM
REM  Recording is ON: the take lands on E: as *_pose_rig, and the blend is in
REM  the log this time.
REM  Press 'q' or close a window to stop; 'r' resets the counters.
REM ============================================================

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [pose_rig] No local .venv found ^-- run launch.bat first to set it up.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" "LiveSnapDebug.py" --pose-rig --record --tag pose_rig ^
    --note "Owner's strategy: panel1 shipped Horn control, panel2 halves 1+2 palm, panel3 halves 1+2 fingers; POSE slider drives panels 2-3." %*

echo.
echo [pose_rig] Session finished. The take is on E: under sessions\*_pose_rig.
pause
