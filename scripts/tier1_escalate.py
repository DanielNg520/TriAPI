"""Tier 1: LLM escalation client.

Called after Tier 3 (DeepSeek) fails to resolve the build. Dispatches the
repair prompt through llm_client.execute_llm using the tier_1_planner
config (provider/endpoint/model). Must only be called after
budget_guard.check_tier1_ok() passes.
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import content_guard, edit_blocks, lessons
from scripts import llm_client
from scripts.config_loader import load_tiers
from scripts.secrets_loader import load_secrets
from scripts.budget_guard import check_tier1_ok
from scripts.state import read_state
from scripts.tier4_worker import extract_code

COST_LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "cost_log.jsonl"

def build_prompt(
    target_path: Path,
    stderr: str,
    context_blob: str = "",
    revision_note: str = "",
    current_contents: str | None = None,
    description: str = "",
) -> str:
    parts = []
    if description:
        parts.append(f"Task:\n{description}")
    if context_blob:
        parts.append(context_blob)
    # target_path may not exist yet -- an item can be creating a new file
    # (e.g. a new ADR), not editing one. Found for real 2026-08-14: an
    # unconditional read_text() raised FileNotFoundError and crashed the
    # whole (potentially hours-long, unattended) dispatch run. Mirrors
    # tier4_worker.build_prompt's own editing/new-file split -- SEARCH/
    # REPLACE blocks (edit_blocks.py) only make sense against existing
    # content, so a new file must ask for the full contents instead.
    if current_contents is None and target_path.exists():
        current_contents = target_path.read_text()
    if current_contents is not None:
        current = f"Current contents of {target_path.name}:\n```\n{current_contents}\n```\n\n"
    else:
        current = (f"{target_path.name} does not exist yet -- output ONLY the complete "
                   "new file contents inside a single fenced code block, no explanation.\n\n")
    if revision_note:
        instruction = (
            "The current file already passes its build/verification. Improve only the "
            f"following quality issues without regressing behavior: {revision_note}"
        )
    else:
        instruction = f"Build/verification error:\n```\n{stderr}\n```\n\nFix the file."
    parts.append(f"{current}{instruction}")
    return "\n\n".join(parts)


def log_cost(entry: dict) -> None:
    COST_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(COST_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def escalate(
    task_id: str,
    target: str,
    context_blob: str = "",
    revision_note: str = "",
    description: str = "",
) -> dict:
    guard = check_tier1_ok()
    if not guard["ok"]:
        return {"status": "skipped", "reason": guard["reason"]}

    target_path = Path(target)
    current_contents = target_path.read_text() if target_path.exists() else None
    editing = current_contents is not None
    state = read_state(task_id)
    stderr = state.get("last_stderr", "")
    prompt = build_prompt(
        target_path,
        stderr,
        context_blob,
        revision_note,
        current_contents=current_contents,
        description=description,
    )
    if editing:
        selected = lessons.select_relevant(target_path.name, description)
        lessons_block = lessons.format_lessons_for_prompt(selected)
        system_prompt = edit_blocks.build_edit_prompt_header(target_path.name, lessons_block=lessons_block)
    else:
        system_prompt = f"You are a coding/writing assistant working on {target_path.name}. Output " \
            "ONLY the complete, corrected file contents inside a single fenced code " \
            "block, using the language tag appropriate for this file (or no tag for " \
            "plain text/markdown) -- no explanation."

    secrets = load_secrets()
    config = load_tiers()
    tier1 = config.get("tier_1_manager", {})
    provider = tier1.get("provider", "cli")
    model_name = tier1.get("models", {}).get(tier1.get("default_model", "default"), "claude-code")

    try:
        raw_result, billing_type, input_tokens, output_tokens = llm_client.execute_llm(
            provider=provider,
            endpoint=tier1.get('endpoint'),
            api_key=secrets.get(tier1.get('api_key_secret', 'open_router_api_key')),
            model=model_name,
            prompt=prompt,
            system_prompt=system_prompt,
            is_tier4=False,
            effort=tier1.get('effort'),
        )
    except Exception:
        return {"status": "error"}

    log_cost(
        {
            "timestamp": time.time(),
            "tier": "tier_1",
            "model": model_name,
            "task_id": task_id,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": 0.0,
            "notional_cost_usd": 0.0,
            "billing": billing_type,
        }
    )

    if editing:
        new_content, err = edit_blocks.apply_edit_blocks(current_contents, raw_result)
        if new_content is None:
            return {
                "status": "fix_rejected",
                "reason": f"Could not apply proposed edit: {err}",
                "notional_cost_usd": 0.0,
            }
        fixed_code = new_content
    else:
        fixed_code = extract_code(raw_result)
        if fixed_code is None:
            return {
                "status": "fix_rejected",
                "reason": "Tier 1 response truncated mid-generation (unterminated code fence); refusing to write incomplete file.",
                "notional_cost_usd": 0.0,
            }

    guard = content_guard.check_write(task_id, target_path, fixed_code)
    if not guard["ok"]:
        return {
            "status": "fix_rejected",
            "reason": guard["reason"],
            "notional_cost_usd": 0.0,
        }

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(fixed_code)

    return {
        "status": "fix_applied",
        "notional_cost_usd": 0.0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--target", required=True, help="path to the file to fix")
    args = parser.parse_args()

    result = escalate(args.task_id, args.target)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
