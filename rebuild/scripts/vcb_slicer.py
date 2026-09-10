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


def parse_single_symbol_output(output: str) -> str:
    first_line = output.lstrip().split("\n", 1)[0]
    if first_line.startswith("**") and "definitions named" in first_line:
        raise ValueError("codegraph output is a multi-match listing, not a single symbol block")
    if "**Other definitions**" in output:
        raise ValueError("codegraph output is a multi-match listing, not a single symbol block")

    in_code = False
    symbol_headers = 0
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not line.startswith("**"):
            continue
        close = line.find("**", 2)
        if close == -1:
            continue
        after = line[close + 2:].strip()
        if after.startswith("(") and after.endswith(")"):
            symbol_headers += 1
            if symbol_headers > 1:
                raise ValueError("codegraph output is a multi-match listing, not a single symbol block")

    fence_start = output.find("```python")
    if fence_start == -1:
        raise ValueError("no python code block found in codegraph output")
    content_start = output.find("\n", fence_start) + 1
    fence_end = output.find("\n```", content_start)
    if fence_end == -1:
        raise ValueError("unterminated python code block in codegraph output")

    block = output[content_start:fence_end]
    result = []
    for line in block.splitlines():
        number, tab, rest = line.partition("\t")
        if tab and number.isdigit():
            result.append(rest)
        else:
            result.append(line)
    return "\n".join(result)


def run_single_symbol(repo_path: str, symbol_name: str) -> str:
    result = subprocess.run(
        ["codegraph", "node", symbol_name, "-p", repo_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"codegraph node failed with return code {result.returncode}: {result.stderr}"
        )
    return parse_single_symbol_output(result.stdout)


def build_skeleton(repo_path: str, file_path: str, target_symbol: str) -> str:
    import_block = extract_import_block(file_path)
    symbols = run_symbols_only(repo_path, file_path)

    target = None
    for symbol in symbols:
        if symbol[0] == target_symbol:
            target = symbol
            break

    if target is None:
        raise ValueError(f"Target symbol {target_symbol!r} not found in {file_path!r}")

    skeleton = import_block
    for symbol_name, signature, _ in symbols:
        if symbol_name != target_symbol:
            skeleton += f"{symbol_name}{signature}:\n    ...\n"

    skeleton += run_single_symbol(repo_path, target_symbol)
    return skeleton
