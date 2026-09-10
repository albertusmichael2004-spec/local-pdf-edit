$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Spec = Join-Path $PSScriptRoot "LocalPDFWorkbench.spec"
$ProjectReleaseApp = Join-Path $ProjectRoot "release\LocalPDFWorkbench"
$LocalConfigDir = Join-Path $ProjectRoot ".local"
$ConfigFile = Join-Path $LocalConfigDir "portable_build.json"
$OutputStateFile = Join-Path $LocalConfigDir "portable_output_dir.txt"

function Get-SavedOutputDirectory {
    if (-not (Test-Path -LiteralPath $ConfigFile)) {
        return $null
    }
    try {
        $config = Get-Content -Raw -LiteralPath $ConfigFile | ConvertFrom-Json
        if ($config.saved_output_dir) {
            return [IO.Path]::GetFullPath([Environment]::ExpandEnvironmentVariables([string]$config.saved_output_dir))
        }
    } catch {
        Write-Host "Saved build configuration could not be read; opening folder picker." -ForegroundColor Yellow
    }
    return $null
}

function Select-OutputFolder([string]$InitialPath) {
    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = "Select the folder that will contain the portable Local PDF Workbench output"
    $dialog.ShowNewFolderButton = $true
    if ($InitialPath -and (Test-Path -LiteralPath $InitialPath)) {
        $dialog.SelectedPath = $InitialPath
    }
    if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
        return [IO.Path]::GetFullPath($dialog.SelectedPath)
    }
    return $null
}

function Choose-OutputDirectory {
    Write-Host ""
    Write-Host "Build complete. Choose the portable app output location:" -ForegroundColor Green
    Write-Host "  [1] Folder outside this project"
    Write-Host "  [2] release\LocalPDFWorkbench under this project"
    do { $locationChoice = (Read-Host "Choose 1 or 2").Trim() } while ($locationChoice -notin @("1", "2"))

    if ($locationChoice -eq "2") {
        return $ProjectReleaseApp
    }

    $saved = Get-SavedOutputDirectory
    Write-Host ""
    if ($saved) {
        Write-Host "  [1] Use saved folder: $saved"
    } else {
        Write-Host "  [1] Use saved folder (not configured yet)"
    }
    Write-Host "  [2] Other folder (open Windows folder picker)"
    do { $externalChoice = (Read-Host "Choose 1 or 2").Trim() } while ($externalChoice -notin @("1", "2"))

    if ($externalChoice -eq "1" -and $saved -and (Test-Path -LiteralPath $saved)) {
        return $saved
    }

    if ($externalChoice -eq "1") {
        Write-Host "Saved folder is not available. Windows Explorer folder picker will open so you can create/select it." -ForegroundColor Yellow
    } else {
        Write-Host "Select the output folder in the Windows folder picker." -ForegroundColor Cyan
    }
    $initial = if ($saved) { Split-Path -Parent $saved } else { [Environment]::GetFolderPath("MyDocuments") }
    $selected = Select-OutputFolder $initial
    if (-not $selected) {
        throw "No output folder was selected. The build completed, but the portable folder was not copied."
    }
    return $selected
}

function Save-OutputState([string]$Destination) {
    New-Item -ItemType Directory -Force -Path $LocalConfigDir | Out-Null
    $config = @{ saved_output_dir = (Get-SavedOutputDirectory); last_output_dir = $Destination }
    $config | ConvertTo-Json | Set-Content -LiteralPath $ConfigFile -Encoding UTF8
    # The CMD launcher reads this file directly; avoid a UTF-8 BOM that would
    # otherwise become an invisible character at the start of the path.
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($OutputStateFile, $Destination, $utf8NoBom)
}

if (-not (Test-Path -LiteralPath $Python)) {
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

Write-Host "Building portable Windows folder..."
& $Python -m PyInstaller --clean --noconfirm $Spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

$Built = Join-Path $ProjectRoot "dist\LocalPDFWorkbench"
if (-not (Test-Path -LiteralPath (Join-Path $Built "LocalPDFWorkbench.exe"))) {
    throw "PyInstaller finished without producing LocalPDFWorkbench.exe."
}

# Keep the generated PyInstaller folders out of the checkout after the copy.
try {
    $Destination = Choose-OutputDirectory
    $Destination = [IO.Path]::GetFullPath($Destination)
    if ($Destination.Equals($ProjectRoot, [StringComparison]::OrdinalIgnoreCase) -or
        $Destination.Equals([IO.Path]::GetPathRoot($Destination), [StringComparison]::OrdinalIgnoreCase)) {
        throw "Select a dedicated application output folder, not the project or drive root."
    }
    if ($Destination.StartsWith($ProjectRoot.TrimEnd('\') + '\') -and
        -not $Destination.Equals($ProjectReleaseApp, [StringComparison]::OrdinalIgnoreCase)) {
        throw "An external selection must be outside the project checkout, or choose option 2."
    }

    if (Test-Path -LiteralPath $Destination) {
        Write-Host "Output folder already exists: $Destination" -ForegroundColor Yellow
        $replace = (Read-Host "Replace its contents? (y/n)").Trim().ToLowerInvariant()
        if ($replace -ne "y") {
            throw "Build completed, but the existing output folder was kept and no copy was made."
        }
        Remove-Item -Recurse -Force -LiteralPath $Destination
    }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null
    Copy-Item -Recurse -Force -LiteralPath $Built -Destination $Destination
    Save-OutputState $Destination
} finally {
    Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Portable application folder created:" -ForegroundColor Green
Write-Host "  $Destination"
Write-Host "The launcher will use this location for portable fallback."
Write-Host "Share the ENTIRE output folder, not only the .exe."
Write-Host "The destination PC does not need Python or VS Code."
Write-Host "Ghostscript is still required for PDF compression and Tesseract for OCR."
