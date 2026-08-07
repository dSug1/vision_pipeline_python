@echo off
REM ============================================================
REM  Side-by-side A/B of the B7 confirmation gate, with the hand drawn as
REM  the SIX BLOCKS (Hand_detection/Claude/GESTURE_PIPELINE_SPEC.md
REM  section 16) instead of the 21-point landmark skeleton.
REM
REM  SIX windows, 3 rows x 2 columns. Each ROW changes exactly ONE thing:
REM      1  14.1 anchor, shipped rotation     2  + B7 gate  <- production today
REM      3  ARM B anchor, shipped rotation    4  + B7 gate  <- anchor changed
REM      5  ARM B + HORN rotation             6  + B7 gate  <- rotation changed
REM
REM  Verified one-variable: the anchor moves ONLY cube position, the rotation
REM  estimator moves ONLY cube orientation. Nothing leaks between rows.
REM  HORN cuts the cube's worst orientation step 39.9 -> 9.6 deg on pitch and
REM  58.9 -> 8.4 deg at back-of-hand (section 16.15).
REM  Use --arms 4 for two rows, --arms 2 for one. Scale auto-fits the rows.
REM
REM  ARM B is the measured winner (section 16.14): it kills the systematic
REM  SINK on every axis (yaw 0.000, pitch -0.000, depth -0.001, back 0.000)
REM  where 14.1 scores -0.656 / -0.807 / -0.589 / -0.083, at a cost of roughly
REM  30-70 percent more jitter in p95. Pitch or yaw the hand while holding a
REM  cube and watch whether the cube slides away from the palm.
REM  Read DOWN a column for what the gate changes, ACROSS a row for what the
REM  anchor changes. Use --arms 2 for the original pair, --scale 0.7 if the
REM  four windows do not fit your screen.
REM
REM  ONE PROCESS, TWO WINDOWS, and deliberately so: two processes cannot
REM  share one webcam on Windows, and two cameras would mean the windows
REM  were watching different hand motions. Here the camera, MediaPipe,
REM  DR-1 identity and DR-2 palm-facing all run ONCE and the stream then
REM  forks, so every difference between the windows is caused by the gate.
REM
REM  The blocks: filled palm quad + centroid dot (position) + knuckle bar
REM  (scale) + 3-axis gizmo (rotation); each finger as MCP/TIP vertices
REM  joined by a circular arc whose bow comes from the arc-extension
REM  scalar alone; the thumb dashed and labelled RAW because it is
REM  deliberately unmodelled. Amber = the gate is withholding judgement on
REM  that channel, red = its frames were just discarded.
REM
REM  Reuses this folder's .venv (run launch.bat once first to create it).
REM  Usage: debug_prediction.bat [camera_index] [extra args...]
REM     e.g. debug_prediction.bat 1
REM          debug_prediction.bat 0 --scale 0.75      (if they do not fit)
REM          debug_prediction.bat 0 --lag 4           (sweep the hold length)
REM          debug_prediction.bat 0 --landmarks       (old skeleton on the left)
REM  Press 'q' in either window to stop.
REM
REM  WHAT NOT TO EXPECT: section 16.7 measured this gate and it FAILS 2 of
REM  its 4 acceptance criteria; it is NOT in production. Back-of-hand and
REM  edge-on poses are identical in both windows by construction. What is
REM  visible is the trade: fewer transient cube spikes against ~83 ms of
REM  hold at every flag.
REM ============================================================

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [debug_prediction] No local .venv found ^-- run launch.bat first to set it up.
    pause
    exit /b 1
)

REM First argument is the camera index UNLESS it already starts with '-', so
REM `debug_prediction.bat --scale 0.75` works without naming a camera.
REM With no arguments the session RECORDS (landmarks + both cube states) to
REM E:\Python\Recordings for vision_pipeline\Recordings_prediction_gate, so the
REM A/B you just watched can be re-measured offline under any gate config.
REM Pass explicit arguments to opt out.
set "FIRSTARG=%~1"
if "%FIRSTARG%"=="" (
    ".venv\Scripts\python.exe" "LiveBlockPredictionDebug.py" --record
) else if "%FIRSTARG:~0,1%"=="-" (
    ".venv\Scripts\python.exe" "LiveBlockPredictionDebug.py" %*
) else (
    ".venv\Scripts\python.exe" "LiveBlockPredictionDebug.py" --camera-index %*
)

echo.
echo [debug_prediction] Live A/B session finished.
pause
