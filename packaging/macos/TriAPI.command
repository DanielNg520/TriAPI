#!/usr/bin/env bash
set -e

REPO_DIR="__TRIAPI_REPO_DIR__"
if [ -x "$REPO_DIR/.venv/bin/python" ]; then
    PYTHON="$REPO_DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON="python3"
else
    echo "No venv found at $REPO_DIR/.venv -- run the repo setup first (see README.md)." >&2
    exit 1
fi

cd "$REPO_DIR/rebuild"
exec "$PYTHON" -m scripts.task_queue tui
