@echo off
REM ============================================================
REM  RB5 STEP 1 -- the window + gain calibration takes.
REM  Design of record: Claude/10_HAND_TRACKING/spec/SPEC_FRAME_AND_REBUILD.md
REM  section 8sexies.
REM
REM  Usage: record_rb5_calibration.bat [camera_index]
REM
REM  Records the three bracketed, declared-ANGLE takes RB5 needs:
REM      rb5_pitch_window   28 s   PITCH  +15..+50, bracketed by 0 and +60
REM      rb5_yaw_window     28 s   YAW      0..+60, bracketed by +75
REM      rb5_roll_window    33 s   ROLL   -45..+45, bracketed by -60 and +60
REM
REM  !! THIS SCRIPT EXISTS FOR ONE REASON: --no-mirror --mount facing_user.
REM  record_perception_sequence.bat cannot pass those flags, and a MIRRORED take
REM  cannot calibrate 1.7.42 -- it detects on the un-mirrored frame, and post-hoc
REM  un-mirroring is a REJECTED operation (MediaPipe is not mirror-equivariant:
REM  7.7-10 mm, 12-20 deg). Every hold_0..hold_90 take in the corpus is mirrored,
REM  which is exactly why these have to be re-recorded.
REM
REM  Each step waits for SPACE, so read the prompt, get into the pose, THEN press.
REM  Nothing is recorded while you are reading.
REM
REM  GRIP as if holding a small cube -- do not open the hand. The open-hand takes
REM  measured 2-4x noisier and that difference has decided two builds.
REM
REM  BRIGHT ROOM. The frame rate here is camera-bound, not compute-bound: every
REM  take on 2026-08-29 ran 8.5-20 fps, under the 20 fps floor. Angles survive
REM  that; RATES do not, and RB5 also owes a drift measurement.
REM
REM  Then:  .venv\Scripts\python.exe analysis\rb5_window_calibration.py ^
REM             "E:\...\sessions\<take1>" "<take2>" "<take3>"
REM ============================================================

cd /d "%~dp0" & cd ..

if not exist ".venv\Scripts\python.exe" (
    echo [rb5] No local .venv found ^-- run launch.bat first to set it up.
    pause
    exit /b 1
)

REM The argument is quoted so a stray token cannot become another switch.
set CAM=
if not "%~1"=="" set CAM=--camera-index "%~1"

echo.
echo [rb5] Waking the capture drive (E:) -- its first access after an idle gap fails.
".venv\Scripts\python.exe" "tools\wake_e_drive.py"
if errorlevel 1 (
    echo [rb5] Could not wake E: ^-- fix that before recording, do NOT use --local.
    pause
    exit /b 1
)

for %%S in (rb5_pitch_window rb5_yaw_window rb5_roll_window) do (
    echo.
    echo ============================================================
    echo [rb5] NEXT TAKE: %%S
    echo ============================================================
    pause
    ".venv\Scripts\python.exe" "tools\RecordPerceptionSequence.py" ^
        --sequence %%S --no-mirror --mount facing_user %CAM%
)

echo.
echo [rb5] All three takes done. Now run:
echo   .venv\Scripts\python.exe analysis\rb5_window_calibration.py "<take dirs>"
echo.
pause
