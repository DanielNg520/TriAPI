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

from scripts import cost, llm_client, secrets_loader
from scripts._root_resource_guard import pause_services, resume_services, load_resource_guard_services


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prompt-file", type=Path, help="Task prompt file; reads stdin if omitted")
    ap.add_argument(
        "--system-file",
        type=Path,
        required=True,
        help="System prompt file (the strict instructions/constraints for this task)",
    )
    ap.add_argument("--task-id", default=None, help="Task id for cost log (default: prompt filename or 'stdin')")
    ap.add_argument("--no-fallback", action="store_true", help="Fail fast during DeepSeek peak hours instead of using the OpenRouter fallback")
    args = ap.parse_args()

    prompt = args.prompt_file.read_text() if args.prompt_file else sys.stdin.read()
    system_prompt = llm_client.load_rules() + "\n\n" + args.system_file.read_text()

    task_id = args.task_id or (args.prompt_file.stem if args.prompt_file else "stdin")

    if llm_client.is_deepseek_peak_hours():
        if args.no_fallback:
            print(
                "[BLOCKED] DeepSeek peak hours active and fallback disabled for this call",
                file=sys.stderr,
            )
            return 1
        print(
            "[FALLBACK] DeepSeek peak billing window active -- using OpenRouter "
            f"fallback model {llm_client.load_model_config()['openrouter']['fallback_model']}",
            file=sys.stderr,
        )
        secrets = secrets_loader.load_secrets()
        paused = pause_services(load_resource_guard_services())
        try:
            response, in_tok, out_tok = llm_client.execute_openrouter(
                prompt, system_prompt, secrets["open_router_api_key"]
            )
        finally:
            resume_services(paused)
        print(response)
        cost.log_cost(task_id, 0, 0)
        print(f"[tokens] in={in_tok} out={out_tok} cost_usd=0.000000 (openrouter free fallback)", file=sys.stderr)
        return 0

    limit = llm_client.load_model_config()["deepseek"]["spend_limit_usd"]
    budget = cost.check_budget(limit)
    if not budget["under_limit"]:
        print(
            f"[BLOCKED] Cumulative spend ${budget['total_cost_usd']:.4f} exceeds limit ${limit:.2f}",
            file=sys.stderr,
        )
        return 1

    secrets = secrets_loader.load_secrets()
    paused = pause_services(load_resource_guard_services())
    try:
        response, in_tok, out_tok = llm_client.execute_deepseek(
            prompt, system_prompt, secrets["deepseek_api_key"]
        )
    finally:
        resume_services(paused)
    print(response)
    cost.log_cost(task_id, in_tok, out_tok)
    print(f"[tokens] in={in_tok} out={out_tok} cost_usd={cost.calculate_cost(in_tok, out_tok):.6f}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
