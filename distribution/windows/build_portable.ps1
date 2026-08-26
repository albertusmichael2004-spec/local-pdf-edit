$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Spec = Join-Path $PSScriptRoot "LocalPDFWorkbench.spec"
$ReleaseRoot = Join-Path $ProjectRoot "release"
$ReleaseApp = Join-Path $ReleaseRoot "LocalPDFWorkbench"

if (-not (Test-Path $Python)) {
    throw "Existing project .venv not found: $Python"
}

$HasPyInstaller = & $Python -c "import importlib.util; raise SystemExit(0 if importlib.util.find_spec('PyInstaller') else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Host "PyInstaller is not installed in the existing .venv." -ForegroundColor Yellow
    Write-Host "Install the optional build-only requirement once:" -ForegroundColor Yellow
    Write-Host "  & `"$Python`" -m pip install -r `"$PSScriptRoot\requirements-build.txt`"" -ForegroundColor Cyan
    exit 1
}

Set-Location $ProjectRoot
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force $ReleaseApp -ErrorAction SilentlyContinue

Write-Host "Building portable Windows folder..."
& $Python -m PyInstaller --clean --noconfirm $Spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

New-Item -ItemType Directory -Force -Path $ReleaseRoot | Out-Null
Copy-Item -Recurse -Force (Join-Path $ProjectRoot "dist\LocalPDFWorkbench") $ReleaseApp

# Keep development root clean after copying the deliverable.
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Portable application folder created:" -ForegroundColor Green
Write-Host "  $ReleaseApp"
Write-Host ""
Write-Host "Share the ENTIRE LocalPDFWorkbench folder, not only the .exe."
Write-Host "The destination PC does not need Python or VS Code."
Write-Host "Ghostscript is still required for PDF compression and Tesseract for OCR."
