$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonW = Join-Path $ProjectRoot ".venv\Scripts\pythonw.exe"
$DesktopPy = Join-Path $ProjectRoot "desktop.py"
$Icon = Join-Path $ProjectRoot "frontend\assets\images\app.ico"
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "Local PDF Workbench.lnk"

foreach ($Required in @($PythonW, $DesktopPy, $Icon)) {
    if (-not (Test-Path $Required)) {
        throw "Required file not found: $Required"
    }
}

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $PythonW
$Shortcut.Arguments = "`"$DesktopPy`""
$Shortcut.WorkingDirectory = $ProjectRoot
$Shortcut.IconLocation = "$Icon,0"
$Shortcut.Description = "Local PDF Workbench - live source launcher"
$Shortcut.Save()

Write-Host "Desktop shortcut created/refreshed:"
Write-Host "  $ShortcutPath"
Write-Host ""
Write-Host "The shortcut points to this source folder, so saved code changes are used the next time the app starts."
