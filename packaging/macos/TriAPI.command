#!/usr/bin/env bash
set -e

REPO_DIR="__TRIAPI_REPO_DIR__"
PYTHON="$REPO_DIR/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
    echo "No venv found at $REPO_DIR/.venv -- run the repo setup first (see README.md)." >&2
    exit 1
fi

cd "$REPO_DIR/rebuild"
exec "$PYTHON" -m scripts.task_queue tui
