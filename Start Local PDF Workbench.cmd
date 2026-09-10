@echo off
setlocal
set "PROJECT_ROOT=%~dp0"
set "PORTABLE_DIR=%PROJECT_ROOT%release\LocalPDFWorkbench"
if exist "%PROJECT_ROOT%.local\portable_output_dir.txt" set /p PORTABLE_DIR=<"%PROJECT_ROOT%.local\portable_output_dir.txt"
set "PORTABLE=%PORTABLE_DIR%\LocalPDFWorkbench.exe"
set "PYTHON=%PROJECT_ROOT%.venv\Scripts\python.exe"
set "PYTHONW=%PROJECT_ROOT%.venv\Scripts\pythonw.exe"

if exist "%PYTHON%" if exist "%PYTHONW%" (
  "%PYTHON%" -I -c "import desktop, uvicorn; desktop._browser_executable()" >nul 2>&1
  if not errorlevel 1 (
    start "Local PDF Workbench" /d "%PROJECT_ROOT%" "%PYTHONW%" -I -m desktop
    exit /b 0
  )
)

if exist "%PORTABLE%" (
  start "Local PDF Workbench" /d "%PORTABLE_DIR%" "%PORTABLE%"
  exit /b 0
)

powershell.exe -NoProfile -Command "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('Tidak ditemukan source environment atau portable app yang bisa dijalankan. Jalankan scripts\\setup_windows.ps1 atau build ulang portable app.','Local PDF Workbench')" >nul 2>&1
exit /b 1
