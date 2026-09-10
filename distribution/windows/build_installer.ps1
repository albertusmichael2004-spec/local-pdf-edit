param(
    [switch]$SkipTests,
    [switch]$SkipAppBuild,
    [string]$OutputDirectory,
    [string]$CertificateThumbprint = $env:PDF_WORKBENCH_CERT_THUMBPRINT,
    [string]$TimestampUrl = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Spec = Join-Path $PSScriptRoot "LocalPDFWorkbench.spec"
$InstallerScript = Join-Path $PSScriptRoot "LocalPDFWorkbench.iss"
$VersionFile = Join-Path $ProjectRoot "VERSION"
$UpdateConfigFile = Join-Path $ProjectRoot "update-config.json"
$PayloadDirectory = Join-Path $ProjectRoot "dist\LocalPDFWorkbench"
$BuildRoot = Join-Path $ProjectRoot "build"
$DistRoot = Join-Path $ProjectRoot "dist"
$LocalBuildDirectory = Join-Path $ProjectRoot ".local\installer"
$TestTempDirectory = Join-Path $LocalBuildDirectory ("pytest-" + [Guid]::NewGuid().ToString("N"))

if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $ProjectRoot "release\installer"
}
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)

function Assert-PathInsideProject([string]$Path, [string]$Description) {
    $resolved = [IO.Path]::GetFullPath($Path)
    $rootPrefix = $ProjectRoot.TrimEnd('\') + '\'
    if (-not $resolved.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "$Description must stay inside the project workspace: $resolved"
    }
}

function Find-InnoCompiler {
    $command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $candidates = @(
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }
    throw "Inno Setup 6 was not found. Install it once, then rerun this script."
}

function Find-SignTool {
    $command = Get-Command "signtool.exe" -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $kitsRoot = Join-Path ${env:ProgramFiles(x86)} "Windows Kits\10\bin"
    if (Test-Path -LiteralPath $kitsRoot) {
        $candidate = Get-ChildItem -LiteralPath $kitsRoot -Filter "signtool.exe" -File -Recurse |
            Where-Object { $_.FullName -match '\\x64\\signtool\.exe$' } |
            Sort-Object FullName -Descending |
            Select-Object -First 1
        if ($candidate) {
            return $candidate.FullName
        }
    }
    throw "signtool.exe was not found. Install the Windows SDK signing tools or omit CertificateThumbprint."
}

function Invoke-CodeSigning([string]$FilePath, [string]$Thumbprint) {
    if (-not $Thumbprint) {
        return
    }
    $signTool = Find-SignTool
    & $signTool sign /sha1 $Thumbprint /fd SHA256 /tr $TimestampUrl /td SHA256 /v $FilePath
    if ($LASTEXITCODE -ne 0) {
        throw "Code signing failed for: $FilePath"
    }
}

function Escape-InnoQuotedValue([string]$Value) {
    return $Value.Replace('"', '""')
}

function Escape-PascalString([string]$Value) {
    return $Value.Replace("'", "''")
}

foreach ($required in @($Python, $Spec, $InstallerScript, $VersionFile)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required build input was not found: $required"
    }
}

$version = (Get-Content -Raw -LiteralPath $VersionFile).Trim()
if ($version -notmatch '^\d+\.\d+\.\d+$') {
    throw "VERSION must use numeric semantic versioning (for example 4.2.0): $version"
}

$projectVersion = & $Python -c "import pathlib,tomllib; print(tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8'))['project']['version'])"
if ($LASTEXITCODE -ne 0 -or $projectVersion.Trim() -ne $version) {
    throw "VERSION and pyproject.toml must contain the same version."
}

Assert-PathInsideProject $BuildRoot "PyInstaller build directory"
Assert-PathInsideProject $DistRoot "PyInstaller dist directory"
Assert-PathInsideProject $LocalBuildDirectory "Installer staging directory"

if (-not $SkipTests) {
    Write-Host "Running release tests..." -ForegroundColor Cyan
    # Use a per-run directory inside the workspace. A fixed basetemp or the
    # user's global %TEMP% can be left owned by an elevated process on Windows,
    # which makes pytest fail before tests start with WinError 5.
    New-Item -ItemType Directory -Force -Path $LocalBuildDirectory | Out-Null
    $testExitCode = 1
    try {
        & $Python -m pytest --basetemp $TestTempDirectory
        $testExitCode = $LASTEXITCODE
    }
    finally {
        if (Test-Path -LiteralPath $TestTempDirectory) {
            Remove-Item -Recurse -Force -LiteralPath $TestTempDirectory -ErrorAction SilentlyContinue
        }
    }
    if ($testExitCode -ne 0) {
        throw "Release tests failed."
    }
}

if (-not $SkipAppBuild) {
    foreach ($generated in @($BuildRoot, $DistRoot)) {
        if (Test-Path -LiteralPath $generated) {
            Remove-Item -Recurse -Force -LiteralPath $generated
        }
    }
    Write-Host "Building the folder-based Windows application..." -ForegroundColor Cyan
    & $Python -m PyInstaller --clean --noconfirm $Spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed."
    }
}

$applicationExe = Join-Path $PayloadDirectory "LocalPDFWorkbench.exe"
if (-not (Test-Path -LiteralPath $applicationExe)) {
    throw "Packaged application was not found: $applicationExe"
}

Invoke-CodeSigning $applicationExe $CertificateThumbprint

New-Item -ItemType Directory -Force -Path $LocalBuildDirectory | Out-Null
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText(
    (Join-Path $PayloadDirectory "VERSION"),
    $version + [Environment]::NewLine,
    (New-Object System.Text.UTF8Encoding($false)))

$updateConfig = @{}
if (Test-Path -LiteralPath $UpdateConfigFile) {
    try {
        $loadedUpdateConfig = Get-Content -Raw -LiteralPath $UpdateConfigFile | ConvertFrom-Json
        if ($loadedUpdateConfig) {
            foreach ($property in $loadedUpdateConfig.PSObject.Properties) {
                # Preserve nested language maps and arrays when serializing the
                # configuration into the frozen application payload.
                $updateConfig[$property.Name] = $property.Value
            }
        }
    }
    catch {
        throw "Could not read update configuration: $UpdateConfigFile"
    }
}
foreach ($override in @(
    @{ Name = "manifest_url"; Environment = "PDF_WORKBENCH_UPDATE_MANIFEST_URL" },
    @{ Name = "installer_url"; Environment = "PDF_WORKBENCH_PUBLIC_INSTALLER_URL" },
    @{ Name = "release_notes"; Environment = "PDF_WORKBENCH_RELEASE_NOTES" }
)) {
    $value = [Environment]::GetEnvironmentVariable($override.Environment)
    if ($value) {
        $updateConfig[$override.Name] = $value.Trim()
    }
}
[IO.File]::WriteAllText(
    (Join-Path $PayloadDirectory "update-config.json"),
    ($updateConfig | ConvertTo-Json -Depth 4),
    $utf8NoBom)

$manifestPath = Join-Path $LocalBuildDirectory "payload-manifest.txt"
$fileListPath = Join-Path $LocalBuildDirectory "payload-files.iss"
$payloadFiles = Get-ChildItem -LiteralPath $PayloadDirectory -File -Recurse |
    Where-Object { $_.Name -ne "payload-manifest.txt" } |
    Sort-Object FullName

$manifestLines = New-Object System.Collections.Generic.List[string]
$fileListLines = New-Object System.Collections.Generic.List[string]
$payloadRootPrefix = $PayloadDirectory.TrimEnd('\') + '\'
foreach ($file in $payloadFiles) {
    # GetRelativePath is unavailable in Windows PowerShell 5.1. Both paths
    # are absolute and the payload files are descendants of this root, so a
    # prefix removal is sufficient and works on the supported PowerShell
    # versions.
    $relativePath = $file.FullName.Substring($payloadRootPrefix.Length).Replace('/', '\')
    $relativeDirectory = [IO.Path]::GetDirectoryName($relativePath)
    $destination = if ($relativeDirectory) { "{app}\$relativeDirectory" } else { "{app}" }
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash.ToLowerInvariant()
    $sourceValue = Escape-InnoQuotedValue $file.FullName
    $destinationValue = Escape-InnoQuotedValue $destination
    $nameValue = Escape-InnoQuotedValue $file.Name
    $relativeValue = Escape-PascalString $relativePath
    $manifestLines.Add($relativePath)
    $fileListLines.Add(
        "Source: `"$sourceValue`"; DestDir: `"$destinationValue`"; DestName: `"$nameValue`"; Flags: ignoreversion; Check: PayloadFileNeedsUpdate('$relativeValue', '$hash')")
}

[IO.File]::WriteAllLines($manifestPath, $manifestLines, $utf8NoBom)
[IO.File]::WriteAllLines($fileListPath, $fileListLines, $utf8NoBom)

$innoCompiler = Find-InnoCompiler
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$compilerArguments = @(
    "/Qp",
    "/DMyAppVersion=$version",
    "/DPayloadFileList=$fileListPath",
    "/DPayloadManifest=$manifestPath",
    "/DInstallerOutputDir=$OutputDirectory",
    $InstallerScript
)

Write-Host "Compiling the Windows installer..." -ForegroundColor Cyan
& $innoCompiler @compilerArguments
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup compilation failed."
}

$installer = Join-Path $OutputDirectory "LocalPDFWorkbench-Setup-x64-v$version.exe"
if (-not (Test-Path -LiteralPath $installer)) {
    throw "Installer compiler completed without producing: $installer"
}

Invoke-CodeSigning $installer $CertificateThumbprint
$checksumFile = Join-Path $OutputDirectory "LocalPDFWorkbench-$version-SHA256.txt"
$installerHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $installer).Hash.ToLowerInvariant()
[IO.File]::WriteAllText(
    $checksumFile,
    "$installerHash  $([IO.Path]::GetFileName($installer))$([Environment]::NewLine)",
    $utf8NoBom)

Write-Host ""
Write-Host "Installer ready:" -ForegroundColor Green
Write-Host "  $installer"
Write-Host "SHA-256:" -ForegroundColor Green
Write-Host "  $checksumFile"
if (-not $CertificateThumbprint) {
    Write-Host ""
    Write-Host "This build is unsigned. Set PDF_WORKBENCH_CERT_THUMBPRINT to a trusted code-signing certificate thumbprint before a public release." -ForegroundColor Yellow
}
