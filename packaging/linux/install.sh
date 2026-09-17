#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
TARGET_DIR="$HOME/.local/share/applications"

source "$SCRIPT_DIR/../ensure_venv.sh"

LAUNCH_CMD="/bin/bash -c \"cd '$REPO_DIR/rebuild' && exec '$PYTHON' -m scripts.task_queue tui\""
LAUNCH_CMD_ESCAPED="$(printf '%s' "$LAUNCH_CMD" | sed -e 's/[&\\]/\\&/g')"

mkdir -p "$TARGET_DIR"
sed "s|__TRIAPI_LAUNCH_CMD__|$LAUNCH_CMD_ESCAPED|" "$SCRIPT_DIR/triapi.desktop" > "$TARGET_DIR/triapi.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$TARGET_DIR"
fi

echo "Installed triapi.desktop to $TARGET_DIR/triapi.desktop"
