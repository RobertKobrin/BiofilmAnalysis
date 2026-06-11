#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"

"$PYTHON_BIN" -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -e ".[dev]"

echo "Environment ready."
echo "Activate it with: source $VENV_DIR/bin/activate"
echo "Run the app with: scripts/run_app.sh"
echo "Install a desktop icon with: scripts/install_desktop_launcher.sh"
