$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

$Launcher = Join-Path $RootDir ".venv\Scripts\biofilm-analysis-desktop.exe"
if (-not (Test-Path $Launcher)) {
    Write-Host "Project environment is not ready; running scripts\setup_windows.ps1 first."
    & "$PSScriptRoot\setup_windows.ps1"
}

if (-not (Test-Path $Launcher)) {
    throw "Desktop launcher was not installed. Try rerunning scripts\setup_windows.ps1."
}

$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "BiofilmAnalysis.lnk"
$WScriptShell = New-Object -ComObject WScript.Shell
$Shortcut = $WScriptShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Launcher
$Shortcut.WorkingDirectory = $RootDir
$Shortcut.Description = "Segment, visualize, and quantify 3D AO/PI biofilm stacks"
$Shortcut.IconLocation = "$Launcher,0"
$Shortcut.Save()

Write-Host "Desktop shortcut installed at: $ShortcutPath"
Write-Host "Double-click BiofilmAnalysis to start the app and open it in your browser."
