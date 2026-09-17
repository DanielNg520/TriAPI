#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [ ! -x "$REPO_DIR/.venv/bin/python" ] && ! command -v python3 >/dev/null 2>&1; then
    echo "No venv found at $REPO_DIR/.venv -- run the repo setup first (see README.md)." >&2
    exit 1
fi

mkdir -p "$HOME/Applications"
sed "s|__TRIAPI_REPO_DIR__|$REPO_DIR|" "$SCRIPT_DIR/TriAPI.command" > "$HOME/Applications/TriAPI.command"
chmod +x "$HOME/Applications/TriAPI.command"

echo "Installed TriAPI.command to ~/Applications. You can double-click it or add it to the Dock."
