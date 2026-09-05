#!/usr/bin/env python3
"""CLI: send a code-writing task to DeepSeek, print the raw response.

Usage:
    python3 call_deepseek.py --prompt-file task.md --system-file system.md
    echo "..." | python3 call_deepseek.py --system-file system.md

Intended caller: a human/agent supervisor who writes a strict, detailed
prompt per function/section/task, reviews this script's stdout before
applying anything -- this script never touches the target repo itself.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import llm_client, secrets_loader


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prompt-file", type=Path, help="Task prompt file; reads stdin if omitted")
    ap.add_argument(
        "--system-file",
        type=Path,
        required=True,
        help="System prompt file (the strict instructions/constraints for this task)",
    )
    args = ap.parse_args()

    prompt = args.prompt_file.read_text() if args.prompt_file else sys.stdin.read()
    system_prompt = args.system_file.read_text()

    if llm_client.is_deepseek_peak_hours():
        print("[WARN] DeepSeek peak billing window (01:00-04:00 UTC) -- costs elevated", file=sys.stderr)

    secrets = secrets_loader.load_secrets()
    response, in_tok, out_tok = llm_client.execute_deepseek(
        prompt, system_prompt, secrets["deepseek_api_key"]
    )
    print(response)
    print(f"[tokens] in={in_tok} out={out_tok}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
