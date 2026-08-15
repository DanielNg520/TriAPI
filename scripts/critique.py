"""Tier 1: Claude Code CLI critique client.

This script evaluates a diff using Claude and returns a strict JSON review
containing a score, verdict, and list of issues. It mirrors the pattern
of tier1_escalate.escalate but focuses on code quality assessment rather
than file editing.

The output format is enforced by CRITIQUE_SYSTEM_PROMPT which demands
only the following JSON structure:

{
  "score": integer between 1 and 10,
  "verdict": "pass" | "revise",
  "issues": [string, ...]
}

A score below the configured threshold triggers a “revise” verdict;
otherwise the verdict is “pass”.

The script logs each invocation to LOGS/cost_log.jsonl with a mock
cost of 0.0 (subscription tier, no metered billing).
"""

import argparse
import json
import subprocess
import time
from pathlib import Path

from scripts.edit_blocks import _FENCE_RE

COST_LOG_PATH = (
    Path(__file__).resolve().parent.parent / "logs" / "cost_log.jsonl"
)

CRITIQUE_SYSTEM_PROMPT = """You are a code review assistant. Return ONLY a JSON object in this strict format:
{{
  "score": integer between 1 and 10,
  "verdict": "pass" | "revise",
  "issues": [string, ...]
}}
The verdict must be "revise" exactly when score is below {score_threshold}.
No explanation, no additional text, no markdown fences."""

# --------------------------------------------------------------------------- #
# Helper functions
# --------------------------------------------------------------------------- #

def log_cost(entry: dict) -> None:
    """Append a JSON line to the cost log file."""
    COST_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(COST_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

def strip_fenced_json(raw: str) -> str:
    """Remove a surrounding code fence using the shared edit-block parser."""
    text = raw.strip()
    match = _FENCE_RE.match(text)
    return match.group(1).strip() if match else text

def build_critique_prompt(target_name: str, description: str,
                          diff_text: str, tier_name: str) -> str:
    """
    Construct a prompt for Claude that asks it to evaluate the provided
    diff. The prompt includes context about the target file, an optional
    description of its purpose, the diff itself, and the tier name (used
    only for potential internal logic). The system prompt ensures that the
    response is a JSON object with the strict schema defined in
    CRITIQUE_SYSTEM_PROMPT.
    """
    return (
        f"Target file: {target_name}\n"
        f"Description: {description}\n\n"
        f"Diff to evaluate:\n{diff_text}\n\n"
        f"You are a code review assistant for tier '{tier_name}'. "
        f"Please score the diff on complexity, abstraction, dead code, and style.\n"
    )

def critique_diff(
    task_id: str,
    target_path: str | Path,
    description: str,
    diff_text: str,
    tier_name: str = "tier_1",
    score_threshold: int = 7,
) -> dict:
    """
    Evaluate a diff using Claude. Mirrors tier1_escalate.escalate in
    structure but returns a JSON review rather than editing code.

    Returns a dictionary with keys:
      - status: "ok", "skipped", or "error"
      - if ok: score, verdict, issues (and optionally notional_cost_usd)
      - if skipped: reason
      - if error: reason

    The function logs each call to COST_LOG_PATH.
    """
    # Guard against running outside budget limits
    usage: dict = {}
    call_data: dict = {}

    def finish(status: str, **fields) -> dict:
        entry = {
            "timestamp": time.time(),
            "tier": "critique",
            "model": call_data.get("model", ""),
            "task_id": task_id,
            "source_tier": tier_name,
            "status": status,
            "input_tokens": usage.get("input_tokens", 0),
            "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", 0),
            "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "cost_usd": 0.0,
            "notional_cost_usd": call_data.get("total_cost_usd", 0.0),
            "billing": "subscription",
        }
        if fields.get("reason"):
            entry["reason"] = fields["reason"]
        try:
            log_cost(entry)
        except OSError:
            pass
        return {"status": status, **fields}

    try:
        from scripts.budget_guard import check_tier1_ok  # type: ignore
    except Exception as e:
        return finish("error", reason=f"Budget guard import failed: {e}")

    guard = check_tier1_ok()
    if not guard.get("ok", False):
        return finish("skipped", reason=guard.get("reason", "Unknown"))

    # Build the prompt
    target_path = target_path if isinstance(target_path, Path) else Path(target_path)
    target_name = target_path.name
    prompt_body = build_critique_prompt(
        target_name,
        description=description,
        diff_text=diff_text,
        tier_name=tier_name
    )
    system_prompt = CRITIQUE_SYSTEM_PROMPT.format(score_threshold=score_threshold)

    # Call claude
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
            input=prompt_body,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return finish("error", reason=f"Claude subprocess failed: {e}")

    if result.returncode != 0:
        return finish("error", reason=result.stderr.strip())

    # Parse Claude's JSON response
    try:
        call_data = json.loads(result.stdout)
    except Exception as e:
        return finish("error", reason=f"Failed to parse CLI output: {e}")

    if not isinstance(call_data, dict):
        return finish("error", reason="Claude CLI output must be a JSON object")
    usage = call_data.get("usage", {})
    if not isinstance(usage, dict):
        usage = {}
    notional_cost_usd = call_data.get("total_cost_usd", 0.0)

    # Extract the result string and clean fences
    raw_result = call_data.get("result", "")
    cleaned = strip_fenced_json(raw_result)
    try:
        critique = json.loads(cleaned)
    except Exception as e:
        return finish("error", reason=f"Failed to parse Claude result JSON: {e}")

    if not isinstance(critique, dict):
        return finish("error", reason="Critique result must be a JSON object")
    try:
        score = int(critique["score"])
    except (KeyError, TypeError, ValueError):
        return finish("error", reason="Critique score must be an integer from 1 to 10")
    if not 1 <= score <= 10:
        return finish("error", reason="Critique score must be between 1 and 10")
    raw_issues = critique.get("issues", [])
    if isinstance(raw_issues, str):
        issues = [raw_issues] if raw_issues.strip() else []
    elif isinstance(raw_issues, list) and all(isinstance(item, str) for item in raw_issues):
        issues = raw_issues
    else:
        return finish("error", reason="Critique issues must be a list of strings")

    # Enforce threshold rule
    verdict = "revise" if score < score_threshold else "pass"
    return finish(
        "ok",
        score=score,
        verdict=verdict,
        issues=issues,
        notional_cost_usd=notional_cost_usd,
    )

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--target", required=True, help="path to the target file")
    parser.add_argument("--description", default="")
    parser.add_argument("--tier-name", default="tier_1")
    parser.add_argument("--score-threshold", type=int, default=7)
    parser.add_argument(
        "--diff",
        required=True,
        help="Diff text (in unified format) to critique"
    )
    args = parser.parse_args()

    result = critique_diff(
        args.task_id,
        args.target,
        args.description,
        args.diff,
        args.tier_name,
        args.score_threshold,
    )
    print(json.dumps(result))

if __name__ == "__main__":
    main()
