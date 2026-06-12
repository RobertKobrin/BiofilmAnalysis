@echo off
setlocal
cd /d "%~dp0"
echo Setting up BiofilmAnalysis for Windows...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows_launcher.ps1" -Setup -InstallShortcut
if errorlevel 1 (
    echo.
    echo Setup failed. Read the message above, then press any key to close.
    pause >nul
    exit /b 1
)
echo.
echo Setup complete. A BiofilmAnalysis shortcut should now be on your Desktop.
echo Press any key to close this window.
pause >nul
