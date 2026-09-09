#!/usr/bin/env python3
"""CLI: send a planning task to the standing Planner role (nemotron via
OpenRouter), print the raw response.

Usage:
    python3 call_planner.py --prompt-file planning_task.md --system-file planner_system.md
    echo "..." | python3 call_planner.py --system-file planner_system.md

Intended caller: a human/agent supervisor who writes a strict, detailed
prompt per planning request, reviews this script's stdout before applying
anything -- this script never touches the target repo itself.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import llm_client, secrets_loader
from scripts._root_resource_guard import pause_services, resume_services, load_resource_guard_services


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prompt-file", type=Path, help="Planning prompt file; reads stdin if omitted")
    ap.add_argument(
        "--system-file",
        type=Path,
        required=True,
        help="Planner system prompt file",
    )
    ap.add_argument("--task-id", default=None, help="Task id for this call (default: prompt filename or 'stdin')")
    args = ap.parse_args()

    prompt = args.prompt_file.read_text() if args.prompt_file else sys.stdin.read()
    system_prompt = llm_client.load_rules() + "\n\n" + args.system_file.read_text()

    task_id = args.task_id or (args.prompt_file.stem if args.prompt_file else "stdin")

    secrets = secrets_loader.load_secrets()
    paused = pause_services(load_resource_guard_services())
    try:
        response, in_tok, out_tok = llm_client.execute_planner(
            prompt, system_prompt, secrets["open_router_api_key"]
        )
    finally:
        resume_services(paused)

    print(response)
    print(f"[tokens] in={in_tok} out={out_tok}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
