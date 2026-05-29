@echo off
REM ============================================================
REM  Stops any running Vision Pipeline processes for this project
REM  (the vision server and the Mouse Cursor client).
REM  Use this if a run got stuck and won't close from the window.
REM ============================================================

powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process -Filter 'Name=''python.exe''' | Where-Object { $_.CommandLine -match 'VisionPipeline\.py' -or $_.CommandLine -match 'MouseCursorApp' }; if ($p) { $p | ForEach-Object { Write-Host ('Stopping PID ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force } } else { Write-Host 'No Vision Pipeline processes running.' }"

echo.
pause
