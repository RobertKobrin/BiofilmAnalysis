@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows_launcher.ps1" -Launch
if errorlevel 1 (
    echo.
    echo BiofilmAnalysis failed to start. Read the message above, then press any key to close.
    pause >nul
    exit /b 1
)
