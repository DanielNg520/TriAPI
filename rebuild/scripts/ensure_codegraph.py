import shutil
import subprocess
import sys
from pathlib import Path

CODEGRAPH_NPM_PACKAGE = '@colbymchenry/codegraph'
CODEGRAPH_REPO_URL = 'https://github.com/colbymchenry/codegraph'


def ensure_codegraph_installed() -> bool:
    if shutil.which('codegraph'):
        return True
    if shutil.which('npm'):
        result = subprocess.run(['npm', 'install', '-g', CODEGRAPH_NPM_PACKAGE])
        return result.returncode == 0 and shutil.which('codegraph') is not None
    print(
        f'codegraph is not installed. Please install it manually: {CODEGRAPH_REPO_URL}',
        file=sys.stderr,
    )
    return False


def ensure_codegraph_index(repo_path: str) -> bool:
    if (Path(repo_path) / '.codegraph').exists():
        return True
    if not ensure_codegraph_installed():
        return False
    result = subprocess.run(
        ['codegraph', 'init', repo_path],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True
    print(result.stderr, file=sys.stderr)
    return False


if __name__ == '__main__':
    success = True
    if not ensure_codegraph_installed():
        success = False
    if len(sys.argv) > 1:
        if not ensure_codegraph_index(sys.argv[1]):
            success = False
    sys.exit(0 if success else 1)
