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
from scripts.budget_guard import check_tier1_ok
from scripts.state import read_state
from scripts.tier4_worker import extract_code

COST_LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "cost_log.jsonl"

SYSTEM_PROMPT = (
    "You are a coding/writing assistant. Given a file's contents and a "
    "build/verification error, respond with ONLY the complete, corrected file "
    "contents inside a single fenced code block, using the language tag "
    "appropriate for the file (or no tag for plain text/markdown) -- no "
    "explanation, no partial diffs."
)


def build_prompt(target_path: Path, stderr: str) -> str:
    return (
        f"Current contents of {target_path.name}:\n```\n{target_path.read_text()}\n```\n\n"
        f"Build/verification error:\n```\n{stderr}\n```\n\nFix the file."
    )


def log_cost(entry: dict) -> None:
    COST_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(COST_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def escalate(task_id: str, target: str) -> dict:
    guard = check_tier1_ok()
    if not guard["ok"]:
        return {"status": "skipped", "reason": guard["reason"]}

    target_path = Path(target)
    state = read_state(task_id)
    stderr = state.get("last_stderr", "")
    prompt = build_prompt(target_path, stderr)

    result = subprocess.run(
        [
            "claude",
            "-p",
            prompt,
            "--output-format",
            "json",
            "--tools",
            "",
            "--system-prompt",
            SYSTEM_PROMPT,
        ],
        capture_output=True,
        text=True,
        timeout=180,
        stdin=subprocess.DEVNULL,
    )
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

    fixed_code = extract_code(data["result"])
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
