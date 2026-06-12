$Port = if ($env:PORT) { [int]$env:PORT } else { 8501 }
& "$PSScriptRoot\windows_launcher.ps1" -Launch -Port $Port
