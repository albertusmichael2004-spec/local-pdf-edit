param(
    [switch]$InstallDependencies
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$CreatedVenv = $false
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "No usable .venv found. Creating one..."
    python -m venv .venv
    $CreatedVenv = $true
}

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if ($CreatedVenv -or $InstallDependencies) {
    Write-Host "Installing/updating runtime dependencies from requirements.txt..."
    & $Python -m pip install --upgrade pip setuptools wheel
    & $Python -m pip install -r requirements.txt
} else {
    Write-Host "Existing .venv found. Reusing it without reinstalling packages."
    Write-Host "Use -InstallDependencies only when requirements.txt changes."
}

Write-Host ""
& $Python scripts\check_system.py
Write-Host ""
Write-Host "Source-mode desktop app:"
Write-Host "  & `"$ProjectRoot\.venv\Scripts\pythonw.exe`" `"$ProjectRoot\desktop.py`""
Write-Host ""
Write-Host "Create/refresh Desktop shortcut:"
Write-Host "  .\scripts\create_desktop_shortcut.ps1"
