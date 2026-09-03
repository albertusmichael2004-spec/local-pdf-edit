$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Launcher = Join-Path $ProjectRoot "Start Local PDF Workbench.cmd"
$Icon = Join-Path $ProjectRoot "frontend\assets\images\app.ico"
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "Local PDF Workbench.lnk"

foreach ($Required in @($Launcher, $Icon)) {
    if (-not (Test-Path $Required)) {
        throw "Required file not found: $Required"
    }
}

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = Join-Path $env:SystemRoot "System32\cmd.exe"
$Shortcut.Arguments = "/d /c `"`"$Launcher`"`""
$Shortcut.WorkingDirectory = $ProjectRoot
$Shortcut.WindowStyle = 7
$Shortcut.IconLocation = "$Icon,0"
$Shortcut.Description = "Local PDF Workbench"
$Shortcut.Save()

Write-Host "Desktop shortcut created/refreshed:"
Write-Host "  $ShortcutPath"
Write-Host ""
Write-Host "The shortcut uses the source environment when healthy and falls back to the portable release."
