#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$SCRIPT_DIR/../ensure_venv.sh"

mkdir -p "$HOME/Applications"
sed "s|__TRIAPI_REPO_DIR__|$REPO_DIR|" "$SCRIPT_DIR/TriAPI.command" > "$HOME/Applications/TriAPI.command"
chmod +x "$HOME/Applications/TriAPI.command"

echo "Installed TriAPI.command to ~/Applications. You can double-click it or add it to the Dock."
