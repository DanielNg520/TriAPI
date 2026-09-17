#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
TARGET_DIR="$HOME/.local/bin"
TARGET="$TARGET_DIR/triapi"

if [ -x "$REPO_DIR/.venv/bin/python" ]; then
    PYTHON="$REPO_DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON="python3"
else
    echo "No venv found at $REPO_DIR/.venv -- run the repo setup first (see README.md)." >&2
    exit 1
fi

mkdir -p "$TARGET_DIR"
cat > "$TARGET" <<EOF
#!/usr/bin/env bash
cd '$REPO_DIR/rebuild' && exec '$PYTHON' -m scripts.task_queue "\$@"
EOF
chmod +x "$TARGET"

echo "Installed triapi to $TARGET"
case ":$PATH:" in
    *":$TARGET_DIR:"*) ;;
    *) echo "Note: $TARGET_DIR is not on PATH -- add it (e.g. in ~/.bashrc/~/.zshrc) to run 'triapi' from any directory." ;;
esac
