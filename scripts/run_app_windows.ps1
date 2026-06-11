$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

$Port = if ($env:PORT) { $env:PORT } else { "8501" }

if (Test-Path ".\.venv\Scripts\streamlit.exe") {
    .\.venv\Scripts\streamlit.exe run src\biofilm_analyzer\app.py --server.address=127.0.0.1 --server.port=$Port
} else {
    python -m streamlit run src\biofilm_analyzer\app.py --server.address=127.0.0.1 --server.port=$Port
}
