param(
    [switch]$Setup,
    [switch]$InstallShortcut,
    [switch]$Launch,
    [switch]$NoBrowser,
    [int]$Port = 8501
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
$VenvDir = Join-Path $RootDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$DesktopLauncher = Join-Path $VenvDir "Scripts\biofilm-analysis-desktop.exe"
$LaunchBat = Join-Path $RootDir "BiofilmAnalysis-Launch-Windows.bat"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Find-Python {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return [pscustomobject]@{ Executable = "py"; Arguments = @("-3") }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return [pscustomobject]@{ Executable = "python"; Arguments = @() }
    }
    throw "Python was not found. Install Python 3 from https://www.python.org/downloads/windows/ and check 'Add python.exe to PATH'."
}

function Invoke-Python {
    param([string[]]$Arguments)
    $PythonCommand = Find-Python
    & $PythonCommand.Executable @($PythonCommand.Arguments) @Arguments
}

function Ensure-Environment {
    Set-Location $RootDir

    if (-not (Test-Path $VenvPython)) {
        Write-Step "Creating Python virtual environment"
        Invoke-Python @("-m", "venv", ".venv")
    }

    Write-Step "Installing or updating BiofilmAnalysis dependencies"
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -e ".[dev]"

    if (-not (Test-Path $DesktopLauncher)) {
        throw "Desktop launcher was not installed into .venv. Check the pip output above for errors."
    }
}

function Install-DesktopShortcut {
    if (-not (Test-Path $DesktopLauncher)) {
        Ensure-Environment
    }
    if (-not (Test-Path $LaunchBat)) {
        throw "Could not find $LaunchBat. The repository may be incomplete."
    }

    Write-Step "Creating Windows desktop shortcut"
    $Desktop = [Environment]::GetFolderPath("Desktop")
    $ShortcutPath = Join-Path $Desktop "BiofilmAnalysis.lnk"
    $WScriptShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WScriptShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $LaunchBat
    $Shortcut.WorkingDirectory = $RootDir
    $Shortcut.Description = "Segment, visualize, and quantify 3D AO/PI biofilm stacks"
    $Shortcut.IconLocation = "$DesktopLauncher,0"
    $Shortcut.Save()
    Write-Host "Desktop shortcut installed at: $ShortcutPath" -ForegroundColor Green
}

function Start-BiofilmAnalysis {
    if (-not (Test-Path $DesktopLauncher)) {
        Ensure-Environment
    }

    Write-Step "Starting BiofilmAnalysis"
    $Arguments = @("--port", "$Port")
    if ($NoBrowser) {
        $Arguments += "--no-browser"
    }
    & $DesktopLauncher @Arguments
}

if (-not $Setup -and -not $InstallShortcut -and -not $Launch) {
    $Launch = $true
}

try {
    if ($Setup) {
        Ensure-Environment
    }
    if ($InstallShortcut) {
        Install-DesktopShortcut
    }
    if ($Launch) {
        Start-BiofilmAnalysis
    }

    Write-Host ""
    Write-Host "Done." -ForegroundColor Green
} catch {
    Write-Host ""
    Write-Host "BiofilmAnalysis launcher failed:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "If Python is missing, install it from https://www.python.org/downloads/windows/ and check 'Add python.exe to PATH'."
    exit 1
}
