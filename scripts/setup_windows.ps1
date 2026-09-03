param(
    [switch]$InstallDependencies
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$CreatedVenv = $false
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "No usable .venv found. Creating one..."
    $StandalonePython = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
    if (Test-Path -LiteralPath $StandalonePython) {
        & $StandalonePython -m venv .venv
    } else {
        python -m venv .venv
    }
    $CreatedVenv = $true
}

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
& $Python -I -c "import sys; raise SystemExit(0 if sys.prefix else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "The existing .venv is broken. Move it aside, then run this setup script again."
}
$BasePrefix = & $Python -c "import sys; print(sys.base_prefix)"
if ($BasePrefix -match "\\.cache\\codex-runtimes\\") {
    Write-Warning "This development .venv uses the bundled Codex Python runtime. The portable app remains standalone."
}

if ($CreatedVenv -or $InstallDependencies) {
    Write-Host "Synchronizing runtime dependencies from requirements.txt..."
    & $Python -m pip install --upgrade pip setuptools wheel
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "Keeping installed runtime dependencies. Use -InstallDependencies to refresh them."
    & $Python -m pip check
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "Installing the LocalPDFWorkbench desktop launcher..."
& $Python -m pip install --no-build-isolation --no-deps --editable .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
& $Python scripts\check_system.py
Write-Host ""
Write-Host "Source-mode desktop app:"
Write-Host "  Start-Process `"$ProjectRoot\.venv\Scripts\pythonw.exe`" -ArgumentList '-I','-m','desktop' -WorkingDirectory `"$ProjectRoot`""
Write-Host ""
Write-Host "Create/refresh Desktop shortcut:"
Write-Host "  .\scripts\create_desktop_shortcut.ps1"
