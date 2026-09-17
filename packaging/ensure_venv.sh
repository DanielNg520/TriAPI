#!/usr/bin/env bash
# Sourced by packaging/*/install.sh -- expects $REPO_DIR already set, sets $PYTHON.
# Guarantees a real venv with requirements.txt installed, via uv, instead of
# trusting an ambient system python3 to already have the right deps.
set -e

if [ ! -x "$REPO_DIR/.venv/bin/python" ]; then
    if ! command -v uv >/dev/null 2>&1; then
        echo "No .venv at $REPO_DIR/.venv and uv not found -- install uv (https://docs.astral.sh/uv/) then re-run this installer." >&2
        exit 1
    fi
    uv venv "$REPO_DIR/.venv" >&2
    uv pip install --python "$REPO_DIR/.venv/bin/python" -r "$REPO_DIR/requirements.txt" >&2
fi

PYTHON="$REPO_DIR/.venv/bin/python"
