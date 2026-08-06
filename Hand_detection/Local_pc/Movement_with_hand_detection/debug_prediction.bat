@echo off
REM ============================================================
REM  Side-by-side A/B of the B7 confirmation gate, with the hand drawn as
REM  the SIX BLOCKS (Hand_detection/Claude/GESTURE_PIPELINE_SPEC.md
REM  section 16) instead of the 21-point landmark skeleton.
REM
REM  FOUR windows in a 2x2 grid - ANCHOR (rows) x GATE (columns):
REM      1 top-left      14.1 anchor, 9 landmarks   no gate   <- production today
REM      2 top-right     14.1 anchor                + B7 gate
REM      3 bottom-left   PALM anchor (B4)           no gate
REM      4 bottom-right  PALM anchor                + B7 gate
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
