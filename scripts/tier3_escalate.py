"""Tier 3: DeepSeek escalation client.

Called after Tier 4 (Ollama) hits the consecutive-failure threshold. Sends
a byte-stable prefix (system prompt + full current file contents) first and
the small variable part (the new build stderr) last, so DeepSeek's automatic
disk-based prefix caching can hit on the stable part across repeated calls
against the same file. Logs raw cache-hit/cache-miss token counts (not just
computed dollars) to logs/cost_log.jsonl so cost can be recomputed later if
tiers.yaml's pricing block goes stale.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.config_loader import load_tiers
from scripts.secrets_loader import load_secrets
from scripts.state import read_state
from scripts.tier4_worker import extract_code
from scripts.tri_logging import get_logger

log = get_logger("tier3")

COST_LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "cost_log.jsonl"


def build_stable_context(target_path: Path) -> str:
    """Deterministic, byte-stable across calls for the same file contents.
    No timestamps or run-specific data allowed here -- that's what kills
    the prefix-cache hit rate.
    """
    return (
        f"You are a coding/writing assistant working on {target_path.name}. You will "
        "be given the full contents of a file that fails to build/verify, followed by "
        "the error. Respond with ONLY the complete, corrected file contents inside a "
        "single fenced code block, using the language tag appropriate for this file "
        "(or no tag for plain text/markdown) -- no explanation, no partial diffs.\n\n"
        f"Current contents of {target_path.name}:\n```\n{target_path.read_text()}\n```"
    )


def build_user_message(stderr: str) -> str:
    return f"Build/verification error:\n```\n{stderr}\n```\n\nFix the file."


def compute_cost(model_pricing: dict, cache_hit_tokens: int, cache_miss_tokens: int, output_tokens: int):
    hit_price = model_pricing.get("cache_hit_per_mtok_usd")
    miss_price = model_pricing.get("cache_miss_per_mtok_usd")
    output_price = model_pricing.get("output_per_mtok_usd")

    cost = 0.0
    partial = False
    if hit_price is not None:
        cost += cache_hit_tokens / 1_000_000 * hit_price
    else:
        partial = True
    if miss_price is not None:
        cost += cache_miss_tokens / 1_000_000 * miss_price
    else:
        partial = True
    if output_price is not None:
        cost += output_tokens / 1_000_000 * output_price
    else:
        partial = True

    return round(cost, 8), partial


def log_cost(entry: dict) -> None:
    COST_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(COST_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def escalate(task_id: str, target: str, model: str | None = None) -> dict:
    config = load_tiers()
    tier3 = config["tier_3_debugger"]
    secrets = load_secrets()

    model_key = model or tier3["default_model"]
    model_name = tier3["models"][model_key]
    model_pricing = tier3["pricing"][model_key]

    target_path = Path(target)
    state = read_state(task_id)
    stderr = state.get("last_stderr", "")

    log.info("[%s] Tier 3 (DeepSeek/%s) escalating for %s", task_id, model_name, target_path)

    stable_context = build_stable_context(target_path)
    user_message = build_user_message(stderr)

    resp = requests.post(
        f"{tier3['endpoint']}/chat/completions",
        headers={
            "Authorization": f"Bearer {secrets['deepseek_api_key']}",
            "Content-Type": "application/json",
        },
        json={
            "model": model_name,
            "messages": [
                {"role": "system", "content": stable_context},
                {"role": "user", "content": user_message},
            ],
            "stream": False,
        },
        timeout=180,
    )
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        log.error("[%s] Tier 3 request failed: %s %s", task_id, resp.status_code, resp.text[:500])
        raise
    data = resp.json()

    usage = data.get("usage", {})
    cache_hit_tokens = usage.get("prompt_cache_hit_tokens", 0)
    cache_miss_tokens = usage.get("prompt_cache_miss_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)

    cost_usd, partial = compute_cost(model_pricing, cache_hit_tokens, cache_miss_tokens, output_tokens)
    log.info(
        "[%s] Tier 3 response: cache_hit=%d cache_miss=%d output=%d cost=$%.6f%s",
        task_id, cache_hit_tokens, cache_miss_tokens, output_tokens, cost_usd,
        " (partial pricing)" if partial else "",
    )

    log_cost(
        {
            "timestamp": time.time(),
            "tier": "tier_3",
            "model": model_name,
            "task_id": task_id,
            "cache_hit_tokens": cache_hit_tokens,
            "cache_miss_tokens": cache_miss_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
            "cost_partial": partial,
        }
    )

    response_text = data["choices"][0]["message"]["content"]
    fixed_code = extract_code(response_text)
    target_path.write_text(fixed_code)

    return {
        "status": "fix_applied",
        "model": model_name,
        "cache_hit_tokens": cache_hit_tokens,
        "cache_miss_tokens": cache_miss_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd,
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
