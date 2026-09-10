"""Slicer helpers for the Virtual Codebase Plan."""

def extract_import_block(file_path: str) -> str:
    with open(file_path, 'r', newline='') as f:
        lines = f.read().splitlines(keepends=True)

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == '' or stripped.startswith('#'):
            continue
        if stripped.startswith(('import ', 'from ')):
            continue
        return ''.join(lines[:index])

    return ''.join(lines)
