#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PORT="${PORT:-8501}"

if [[ -x ".venv/bin/streamlit" ]]; then
    exec .venv/bin/streamlit run src/biofilm_analyzer/app.py \
        --server.address=0.0.0.0 \
        --server.port="$PORT"
fi

exec python3 -m streamlit run src/biofilm_analyzer/app.py \
    --server.address=0.0.0.0 \
    --server.port="$PORT"
