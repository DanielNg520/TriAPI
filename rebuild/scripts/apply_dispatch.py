from __future__ import annotations

import argparse
import difflib
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts._root_edit_blocks import apply_edit_blocks
from scripts.dispatch import dispatch_task, load_stored_response
from scripts.llm_client import extract_code_block


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--response", required=True, type=Path)
    parser.add_argument("--new", action="store_true")
    parser.add_argument("--language", default="python")
    parser.add_argument("--test")
    parser.add_argument("--cwd", type=Path)
    return parser.parse_args(argv)


def prepare_edit(target: Path, response_text: str) -> tuple[str, str]:
    old_content = target.read_text()
    new_content, error = apply_edit_blocks(old_content, response_text)
    if new_content is None:
        raise ValueError(error)
    return old_content, new_content


def prepare_new(target: Path, response_text: str, language: str) -> tuple[str, str]:
    if target.exists():
        raise ValueError("target already exists")
    content = extract_code_block(response_text, language)
    if not content.endswith("\n"):
        content += "\n"
    return "", content


def run_dispatch(
    target: Path,
    old_content: str,
    new_content: str,
    args: argparse.Namespace,
) -> dict:
    test_cmd = shlex.split(args.test) if args.test else None
    return dispatch_task(
        target,
        new_content=new_content,
        test_cmd=test_cmd,
        cwd=args.cwd,
    )


def diffstat(old_content: str, new_content: str) -> tuple[int, int]:
    added = removed = 0
    for line in difflib.unified_diff(
        old_content.splitlines(), new_content.splitlines(), lineterm=""
    ):
        if line.startswith(("+++", "---")):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    return added, removed


def print_summary(
    target: Path,
    old_content: str,
    new_content: str,
    result: dict,
) -> int:
    added, removed = diffstat(old_content, new_content)
    status = "PASSED" if result["passed"] else "FAILED (rolled back)"
    print(f"{status}: {result['summary']} +{added} -{removed}")
    return 0 if result["passed"] else 1


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        response_text = load_stored_response(args.response)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2

    try:
        if args.new:
            old_content, new_content = prepare_new(args.target, response_text, args.language)
        else:
            old_content, new_content = prepare_edit(args.target, response_text)
    except (ValueError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 1

    if args.new:
        args.target.parent.mkdir(parents=True, exist_ok=True)
        args.target.touch()

    result = run_dispatch(args.target, old_content, new_content, args)

    if args.new and not result["passed"]:
        args.target.unlink(missing_ok=True)

    return print_summary(args.target, old_content, new_content, result)


if __name__ == "__main__":
    raise SystemExit(main())
