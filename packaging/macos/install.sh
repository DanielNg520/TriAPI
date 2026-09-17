#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$HOME/Applications"
cp "$SCRIPT_DIR/TriAPI.command" "$HOME/Applications/TriAPI.command"
chmod +x "$HOME/Applications/TriAPI.command"

echo "Installed TriAPI.command to ~/Applications. You can double-click it or add it to the Dock."
