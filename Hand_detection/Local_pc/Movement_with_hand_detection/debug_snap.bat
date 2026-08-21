@echo off
REM ============================================================
REM  Combined snap/translate debug view (Hand_detection/Claude/
REM  GESTURE_PIPELINE_SPEC.md §13): webcam + MediaPipe hand landmarks +
REM  semi-transparent cube overlay, all in ONE window -- temporary, to be
REM  removed once the new gesture set is built and verified (see
REM  LiveSnapDebug.py's header comment). Reuses this folder's .venv (run
REM  launch.bat at least once first to create it). No socket, no separate
REM  pygame window.
REM
REM  DEFAULT: ONE window, mirroring production exactly -- including queue
REM  D1/D2/D3's 150 ms tracking-loss coast and 3-frame resync blend, which the
REM  owner accepted live on 2026-08-21.
REM
REM  The D2/D3 COMPARISON RIG is still available with --arms 3: three windows
REM  side by side, one per arm --
REM    1 OFF   = production before D2 (releases the cube on the first missed frame)
REM    2 ON    = D2's 150 ms coast, no resync blend
REM    3 BLEND = D2 + D3's 3-frame resync -- what ships
REM  All three run off ONE camera, ONE detection and ONE identity resolution, so
REM  the only difference between panels is the bridging.
REM  ⚠ The rig tests nothing unless you PROVOKE dropouts: grab a cube, then move
REM    fast, or sweep your hand out past the frame edge and back. If the 'brid'
REM    counter stays at 0, nothing was exercised.
REM
REM  Usage: debug_snap.bat [args...]
REM    debug_snap.bat                        production behaviour, camera 0
REM    debug_snap.bat 1                      production behaviour, camera 1
REM    debug_snap.bat --arms 3               the three-arm comparison rig
REM    debug_snap.bat --bridge off           one window, pre-D2 behaviour
REM  Press 'q' or close a window to stop; 'r' resets the counters.
REM ============================================================

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [debug_snap] No local .venv found ^-- run launch.bat first to set it up.
    pause
    exit /b 1
)

REM Arguments are forwarded verbatim -- see LiveSnapDebug.py --help. A single
REM bare number still means the camera index, as it always did.
set "_first=%~1"
if "%_first%"=="" goto :run
if "%_first:~0,1%"=="-" goto :run
".venv\Scripts\python.exe" "LiveSnapDebug.py" --camera-index %*
goto :done

:run
".venv\Scripts\python.exe" "LiveSnapDebug.py" %*

:done

echo.
echo [debug_snap] Live debug session finished.
pause
