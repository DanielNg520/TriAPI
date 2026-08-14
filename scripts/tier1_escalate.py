"""Tier 1: Claude Code CLI escalation client.

Called after Tier 3 (DeepSeek) fails to resolve the build. Shells out to
`claude -p` with a minimal --system-prompt override (avoids Claude Code's
default system prompt + CLAUDE.md auto-discovery, which otherwise adds
~60K tokens of overhead per call -- irrelevant here since the task is a
one-shot text fix, not a coding session) and --tools "" (no tool access
needed; the file contents are inlined in the prompt and the fix is
extracted from the text response, same pattern as Tier 3).

Must only be called after budget_guard.check_tier1_ok() passes. Uses the
Claude Pro/Max subscription (no ANTHROPIC_API_KEY), never metered billing.

DO NOT pass --bare: it forces ANTHROPIC_API_KEY/apiKeyHelper auth and
never reads the OAuth/keychain subscription login, which would silently
switch this tier to metered billing -- the opposite of what budget_guard
is protecting against.
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import content_guard, edit_blocks
from scripts.budget_guard import check_tier1_ok
from scripts.state import read_state
from scripts.tier4_worker import extract_code

COST_LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "cost_log.jsonl"

def build_prompt(target_path: Path, stderr: str, context_blob: str = "") -> str:
    parts = []
    if context_blob:
        parts.append(context_blob)
    # target_path may not exist yet -- an item can be creating a new file
    # (e.g. a new ADR), not editing one. Found for real 2026-08-14: an
    # unconditional read_text() raised FileNotFoundError and crashed the
    # whole (potentially hours-long, unattended) dispatch run. Mirrors
    # tier4_worker.build_prompt's own editing/new-file split -- SEARCH/
    # REPLACE blocks (edit_blocks.py) only make sense against existing
    # content, so a new file must ask for the full contents instead.
    if target_path.exists():
        current = f"Current contents of {target_path.name}:\n```\n{target_path.read_text()}\n```\n\n"
    else:
        current = (f"{target_path.name} does not exist yet -- output ONLY the complete "
                   "new file contents inside a single fenced code block, no explanation.\n\n")
    parts.append(
        f"{current}"
        f"Build/verification error:\n```\n{stderr}\n```\n\nFix the file."
    )
    return "\n\n".join(parts)


def log_cost(entry: dict) -> None:
    COST_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(COST_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def escalate(task_id: str, target: str, context_blob: str = "") -> dict:
    guard = check_tier1_ok()
    if not guard["ok"]:
        return {"status": "skipped", "reason": guard["reason"]}

    target_path = Path(target)
    editing = target_path.exists()
    state = read_state(task_id)
    stderr = state.get("last_stderr", "")
    prompt = build_prompt(target_path, stderr, context_blob)
    system_prompt = (
        edit_blocks.build_edit_prompt_header(target_path.name) if editing else
        f"You are a coding/writing assistant working on {target_path.name}. Output "
        "ONLY the complete, corrected file contents inside a single fenced code "
        "block, using the language tag appropriate for this file (or no tag for "
        "plain text/markdown) -- no explanation."
    )

    # `prompt` (target file contents + context_blob, up to 20K chars/file --
    # tier4_worker.build_context_blob()'s own cap -- times however many
    # context files an item names) is piped via stdin, NOT passed as a CLI
    # argv token. Found for real 2026-08-12: passing it as `-p prompt`
    # hit the kernel's execve() argument-list size limit
    # (`OSError: [Errno 7] Argument list too long`) on an item with several
    # sizeable context files, an UNCAUGHT crash that took down the entire
    # unattended dispatch process -- the same failure shape as the
    # subprocess.TimeoutExpired crash tier4_worker.run_build() was already
    # fixed for. `claude`'s own `[prompt]` CLI arg is documented optional
    # (`claude -p --help`: "Arguments: prompt  Your prompt"), reading from
    # stdin when omitted -- exactly what's needed here, and with no
    # practical size limit the way argv has.
    try:
        result = subprocess.run(
            [
                "claude",
                "-p",
                "--output-format",
                "json",
                "--tools",
                "",
                "--system-prompt",
                system_prompt,
            ],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"status": "error", "reason": f"Tier 1 subprocess failed to run: {e}"}
    if result.returncode != 0:
        return {"status": "error", "reason": result.stderr.strip()}

    data = json.loads(result.stdout)
    usage = data.get("usage", {})

    log_cost(
        {
            "timestamp": time.time(),
            "tier": "tier_1",
            "model": "claude-sonnet-5",
            "task_id": task_id,
            "input_tokens": usage.get("input_tokens", 0),
            "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", 0),
            "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "cost_usd": 0.0,
            "notional_cost_usd": data.get("total_cost_usd", 0.0),
            "billing": "subscription",
        }
    )

    if editing:
        new_content, err = edit_blocks.apply_edit_blocks(target_path.read_text(), data["result"])
        if new_content is None:
            return {
                "status": "fix_rejected",
                "reason": f"Could not apply proposed edit: {err}",
                "notional_cost_usd": data.get("total_cost_usd", 0.0),
            }
        fixed_code = new_content
    else:
        fixed_code = extract_code(data["result"])

    guard = content_guard.check_write(task_id, target_path, fixed_code)
    if not guard["ok"]:
        return {
            "status": "fix_rejected",
            "reason": guard["reason"],
            "notional_cost_usd": data.get("total_cost_usd", 0.0),
        }

    target_path.write_text(fixed_code)

    return {
        "status": "fix_applied",
        "notional_cost_usd": data.get("total_cost_usd", 0.0),
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
