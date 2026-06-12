#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ "$(uname -s)" != "Linux" ]]; then
    echo "This desktop shortcut installer currently supports Linux .desktop launchers."
    echo "You can still run the app with: scripts/run_app.sh"
    exit 1
fi

if [[ ! -x ".venv/bin/biofilm-analysis-desktop" ]]; then
    echo "Project environment is not ready; running scripts/setup_environment.sh first."
    scripts/setup_environment.sh
fi

APP_DIR="$HOME/.local/share/applications"
DESKTOP_ENTRY="$APP_DIR/biofilm-analysis.desktop"
DESKTOP_COPY="$HOME/Desktop/biofilm-analysis.desktop"
ICON_PATH="$ROOT_DIR/assets/biofilm-analysis.svg"
EXEC_PATH="$ROOT_DIR/.venv/bin/biofilm-analysis-desktop"

mkdir -p "$APP_DIR"

cat > "$DESKTOP_ENTRY" <<EOF
[Desktop Entry]
Type=Application
Name=BiofilmAnalysis
Comment=Segment, visualize, and quantify 3D AO/PI biofilm stacks
Exec=$EXEC_PATH
Icon=$ICON_PATH
Terminal=false
Categories=Science;Education;
StartupNotify=true
EOF

chmod +x "$DESKTOP_ENTRY"

if [[ -d "$HOME/Desktop" ]]; then
    cp "$DESKTOP_ENTRY" "$DESKTOP_COPY"
    chmod +x "$DESKTOP_COPY"
    echo "Desktop launcher installed at: $DESKTOP_COPY"
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
fi

echo "Application launcher installed at: $DESKTOP_ENTRY"
echo "Open BiofilmAnalysis from your application menu or desktop icon."
