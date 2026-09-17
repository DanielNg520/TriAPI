#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="$HOME/.local/share/applications"

mkdir -p "$TARGET_DIR"
cp "$SCRIPT_DIR/triapi.desktop" "$TARGET_DIR/triapi.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$TARGET_DIR"
fi

echo "Installed triapi.desktop to $TARGET_DIR/triapi.desktop"
