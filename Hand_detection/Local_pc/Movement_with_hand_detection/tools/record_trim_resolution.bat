@echo off
REM ============================================================
REM  F1 SECTION 10.1 -- THE TRIM-RESOLUTION TAKE.
REM  (Hand_detection/Claude/10_HAND_TRACKING/spec/F1_FINGERTIP_TRANSFORM_SPEC.md
REM   section 10.1)
REM
REM  WHY THIS TAKE EXISTS. Every metric the project owns measures GROSS sweep
REM  fidelity -- yaw axis, lean, pitch, roll, jitter over big hand rotations.
REM  F1 exists to buy FINE alignment: nudging a held object into place with the
REM  fingers while the wrist stays put. So F1 can pass every existing number and
REM  still deliver nothing it was built for. This is the take that tells them
REM  apart, and it is the LAST outstanding acceptance gate.
REM
REM  WHAT YOU DO -- six states, three angles x two phases:
REM
REM    For each declared angle (10, 20, 40 degrees):
REM      1. REFERENCE  hold your hand as if gripping a cube, fingers NEUTRAL.
REM                    SPACE, then hold still for 30 frames.
REM      2. TARGET     rotate the imagined object with your FINGERS ONLY, by
REM                    that angle. YOUR WRIST MUST NOT TURN.
REM                    SPACE, then hold still for 30 frames.
REM
REM  The overlay is GREEN while the wrist-still gate is met and ORANGE when it
REM  is not, and shows your palm's actual rotation and drift against the limits.
REM  Only green frames count toward the 30 -- orange ones are still RECORDED and
REM  flagged, so a take that could not hold the wrist is visible rather than
REM  silently thinned.
REM
REM    SPACE = start / end a state     R = redo this state     ESC or Q = abort
REM
REM  !! BE HONEST ABOUT THE ANGLE. The declared number is the ground truth (rule
REM  B4: an anchor metric must not share an expression with the anchor). If 40
REM  degrees of finger-only rotation is not comfortable while gripping, do a
REM  smaller one and say what it really was -- a hittable angle beats a tidy one,
REM  exactly as the 30 degree grid beat 25.71 on the ratio takes.
REM
REM  The object's response is deliberately NOT recorded: only landmarks are, and
REM  analysis/f1_trim_resolution.py replays them through the SHIPPED pipeline.
REM  That way this take scores every FUTURE build too, instead of freezing
REM  today's answer into it.
REM
REM  Usage: record_trim_resolution.bat [hand] [angles...]
REM    e.g. record_trim_resolution.bat
REM         record_trim_resolution.bat right 10 20 40
REM         record_trim_resolution.bat left 5 15
REM ============================================================

cd /d "%~dp0" & cd ..

if not exist ".venv\Scripts\python.exe" (
    echo [trimres] No local .venv found ^-- run launch.bat first to set it up.
    pause
    exit /b 1
)

set "HAND=%~1"
if "%HAND%"=="" set "HAND=right"

REM Everything after the hand is the declared angle list; empty means the default.
set "ANGLES="
if not "%~2"=="" (
    shift
    :collect
    if "%~1"=="" goto done
    set "ANGLES=%ANGLES% %~1"
    shift
    goto collect
)
:done

if "%ANGLES%"=="" (
    ".venv\Scripts\python.exe" "tools\RecordTrimResolution.py" --hand %HAND% --tag f1_10_1
) else (
    ".venv\Scripts\python.exe" "tools\RecordTrimResolution.py" --hand %HAND% --tag f1_10_1 --angles%ANGLES%
)

echo.
echo [trimres] Session finished. The take is on E: under sessions\*_trim_resolution_*.
pause
