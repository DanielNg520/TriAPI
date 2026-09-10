"""Slicer helpers for the Virtual Codebase Plan."""

import re
import subprocess


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


def parse_symbols_only_output(output: str) -> list[tuple[str, str, int]]:
    parsed: list[tuple[str, str, int]] = []
    in_symbols = False
    bullet_re = re.compile(
        r'^\s*-\s+`([^`]+)`\s+\([^)]*\)\s*(.*?)\s*—\s*:\s*(\d+)\s*$'
    )

    for line in output.splitlines():
        stripped = line.strip()

        if stripped == '**Symbols**':
            in_symbols = True
            continue

        if stripped.startswith('**') and stripped != '**Symbols**':
            in_symbols = False
            continue

        if not in_symbols:
            continue

        match = bullet_re.match(line)
        if match:
            symbol_name = match.group(1)
            signature = match.group(2).strip()
            start_line = int(match.group(3))
            parsed.append((symbol_name, signature, start_line))

    return parsed


def run_symbols_only(repo_path: str, file_path: str) -> list[tuple[str, str, int]]:
    result = subprocess.run(
        ["codegraph", "node", file_path, "--symbols-only", "-p", repo_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"codegraph node failed with return code {result.returncode}: {result.stderr}"
        )
    return parse_symbols_only_output(result.stdout)
