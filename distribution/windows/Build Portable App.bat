@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_portable.ps1"
if errorlevel 1 (
  echo.
  echo Build did not complete. Read the message above.
  pause
)
endlocal
