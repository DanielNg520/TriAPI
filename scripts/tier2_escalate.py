"""Tier 2: Gemini (Google AI Studio API) escalation client.

Called after Tier 1 (Claude Code CLI) fails to resolve the build -- the
final automated tier before human handoff. Mirrors tier3_escalate.py's
structure: stable system-instruction prefix + file contents, volatile
stderr as the user content, extract fix from response, log usage.

Must only be called after budget_guard.check_tier2_ok() passes -- Google
AI Studio's free tier is rate-limited, not unlimited, and this must never
silently run into paid overage.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.budget_guard import check_tier2_ok, record_gemini_call
from scripts.config_loader import load_tiers
from scripts.secrets_loader import load_secrets
from scripts.state import read_state
from scripts.tier4_worker import extract_code
from scripts.tri_logging import get_logger

log = get_logger("tier2")

COST_LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "cost_log.jsonl"

SYSTEM_INSTRUCTION = (
    "You are a coding/writing assistant. Given a file's contents and a "
    "build/verification error, respond with ONLY the complete, corrected file "
    "contents inside a single fenced code block, using the language tag "
    "appropriate for the file (or no tag for plain text/markdown) -- no "
    "explanation, no partial diffs."
)


def build_user_content(target_path: Path, stderr: str) -> str:
    return (
        f"Current contents of {target_path.name}:\n```\n{target_path.read_text()}\n```\n\n"
        f"Build/verification error:\n```\n{stderr}\n```\n\nFix the file."
    )


def log_cost(entry: dict) -> None:
    COST_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(COST_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def escalate(task_id: str, target: str, model: str | None = None) -> dict:
    guard = check_tier2_ok()
    if not guard["ok"]:
        log.warning("[%s] Tier 2 skipped: %s", task_id, guard["reason"])
        return {"status": "skipped", "reason": guard["reason"]}

    config = load_tiers()
    tier2 = config["tier_2_manager"]
    secrets = load_secrets()

    model_key = model or tier2["default_model"]
    model_name = tier2["models"][model_key]

    target_path = Path(target)
    state = read_state(task_id)
    stderr = state.get("last_stderr", "")
    user_content = build_user_content(target_path, stderr)

    log.info("[%s] Tier 2 (Gemini/%s) escalating for %s", task_id, model_name, target_path)

    resp = requests.post(
        f"{tier2['endpoint']}/v1beta/models/{model_name}:generateContent",
        params={"key": secrets["google_ai_studio_api_key"]},
        json={
            "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
            "contents": [{"role": "user", "parts": [{"text": user_content}]}],
        },
        timeout=180,
    )
    record_gemini_call()
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        log.error("[%s] Tier 2 request failed: %s %s", task_id, resp.status_code, resp.text[:500])
        raise
    data = resp.json()

    usage = data.get("usageMetadata", {})
    prompt_tokens = usage.get("promptTokenCount", 0)
    cached_tokens = usage.get("cachedContentTokenCount", 0)
    output_tokens = usage.get("candidatesTokenCount", 0)

    log.info(
        "[%s] Tier 2 response: prompt=%d cached=%d output=%d",
        task_id, prompt_tokens, cached_tokens, output_tokens,
    )

    log_cost(
        {
            "timestamp": time.time(),
            "tier": "tier_2",
            "model": model_name,
            "task_id": task_id,
            "prompt_tokens": prompt_tokens,
            "cached_tokens": cached_tokens,
            "output_tokens": output_tokens,
            "cost_usd": 0.0,
            "billing": "free_tier",
        }
    )

    response_text = data["candidates"][0]["content"]["parts"][0]["text"]
    fixed_code = extract_code(response_text)
    target_path.write_text(fixed_code)

    return {
        "status": "fix_applied",
        "model": model_name,
        "prompt_tokens": prompt_tokens,
        "cached_tokens": cached_tokens,
        "output_tokens": output_tokens,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--target", required=True, help="path to the file to fix")
    parser.add_argument("--model", default=None, help="flash or pro; overrides config default")
    args = parser.parse_args()

    result = escalate(args.task_id, args.target, args.model)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
