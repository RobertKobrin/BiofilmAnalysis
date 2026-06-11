$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

if (Get-Command py -ErrorAction SilentlyContinue) {
    py -3 -m venv .venv
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    python -m venv .venv
} else {
    throw "Python was not found. Install Python 3 from https://www.python.org/downloads/ and check 'Add python.exe to PATH'."
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

Write-Host ""
Write-Host "Environment ready."
Write-Host "Run the app with: powershell -ExecutionPolicy Bypass -File scripts\run_app_windows.ps1"
Write-Host "Install a desktop shortcut with: powershell -ExecutionPolicy Bypass -File scripts\install_windows_shortcut.ps1"
