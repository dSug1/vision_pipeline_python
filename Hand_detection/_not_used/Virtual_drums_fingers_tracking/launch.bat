@echo off
setlocal
REM ============================================================
REM  Virtual Drums - Finger Tracking launcher (self-contained)
REM  Builds/uses a LOCAL .venv inside THIS folder, then runs the app.
REM  The folder can be copied anywhere with no external dependencies.
REM  Press 'q' or close the camera window to stop.
REM ============================================================
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" goto run

echo [launch] First run: creating local virtual environment (.venv)...
python -m venv .venv
if errorlevel 1 goto nopython
echo [launch] Installing dependencies (first time only, may take a few minutes)...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto pipfail

:run
echo [launch] Starting Virtual Drums...
".venv\Scripts\python.exe" main.py
goto end

:nopython
echo.
echo [launch] ERROR: 'python' was not found on PATH.
echo [launch] Install Python 3.11+ (check "Add to PATH" in the installer) and re-run.
goto end

:pipfail
echo.
echo [launch] ERROR: dependency installation failed. See the messages above.
goto end

:end
echo.
pause
