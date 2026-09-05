#!/usr/bin/env python3
"""CLI: send a docs/trivial task to the local `agy` CLI, print the response.

Usage:
    python3 call_agy.py --prompt-file task.md --system-file system.md
    echo "..." | python3 call_agy.py --system-file system.md

Every prompt sent through this MUST end with an explicit instruction like
"reply with the complete file content only, no other text" -- agy's
--mode plan (always set by llm_client.execute_agy) relies on the prompt
itself to suppress its default propose-and-ask framing.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import llm_client


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prompt-file", type=Path, help="Task prompt file; reads stdin if omitted")
    ap.add_argument("--system-file", type=Path, help="Optional system prompt file")
    args = ap.parse_args()

    prompt = args.prompt_file.read_text() if args.prompt_file else sys.stdin.read()
    system_prompt = args.system_file.read_text() if args.system_file else None

    response = llm_client.execute_agy(prompt, system_prompt)
    print(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
