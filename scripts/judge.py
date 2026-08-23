import fcntl
import json
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.budget_guard import check_tier3_peak_hours_ok
from scripts.config_loader import load_tiers
from scripts.secrets_loader import load_secrets
from scripts.tier3_escalate import compute_cost, log_cost
from scripts.tri_logging import get_logger

log = get_logger("judge")


def clean_response(text: str) -> str:
    """Strip leading and trailing markdown code fences to extract raw JSON."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:\w+)?\s*\n", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _build_prompt(diff_text: str, task_goal: str) -> str:
    return (
        "You are a design judge reviewing a proposed code diff against a task goal. "
        "Respond with ONLY a JSON object of the form "
        '{"approved": true|false, "reason": "<short explanation>"} and nothing else.\n\n'
        f"Task goal:\n{task_goal}\n\n"
        f"Diff:\n```\n{diff_text}\n```"
    )


def _call_tier3_with_retries(
    prompt: str,
    system_prompt: str,
    task_id: str,
    validator_fn,
) -> tuple[any, float, str | None]:
    """Helper to call Tier 3 (DeepSeek) with a 2-attempt retry loop.

    Each attempt's API token usage is computed and logged to the cost log separately.
    Calls validator_fn on the response text. If validator_fn runs without raising an exception,
    returns (validated_value, cumulative_cost, None).
    If both attempts fail or fail validation, returns (None, cumulative_cost, last_error_message).
    """
    config = load_tiers()
    tier3 = config["tier_3_debugger"]
    secrets = load_secrets()

    model_key = tier3["default_model"]
    model_name = tier3["models"][model_key]
    model_pricing = tier3["pricing"][model_key]

    cost_usd = 0.0
    last_error = None

    for attempt in range(2):
        try:
            resp = requests.post(
                f"{tier3['endpoint']}/chat/completions",
                headers={
                    "Authorization": f"Bearer {secrets[tier3['api_key_secret']]}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                },
                timeout=180,
            )
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as e:
            last_error = f"API request/parse failed: {e}"
            log.warning("[%s] Attempt %d failed: %s", task_id, attempt + 1, last_error)
            continue

        usage = data.get("usage", {})
        cache_hit_tokens = usage.get("prompt_cache_hit_tokens", 0)
        cache_miss_tokens = usage.get("prompt_cache_miss_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        attempt_cost, partial = compute_cost(model_pricing, cache_hit_tokens, cache_miss_tokens, output_tokens)
        cost_usd += attempt_cost
        log_cost(
            {
                "timestamp": time.time(),
                "tier": "tier_3",
                "model": model_name,
                "task_id": task_id,
                "call_type": task_id,
                "cache_hit_tokens": cache_hit_tokens,
                "cache_miss_tokens": cache_miss_tokens,
                "output_tokens": output_tokens,
                "cost_usd": attempt_cost,
                "cost_partial": partial,
            }
        )

        try:
            response_text = data["choices"][0]["message"]["content"]
            validated = validator_fn(response_text)
            return validated, cost_usd, None
        except Exception as e:
            last_error = f"Validation failed: {e}"
            log.warning("[%s] Validation failed on attempt %d: %s", task_id, attempt + 1, last_error)
            continue

    return None, cost_usd, last_error


def evaluate_design(diff_text: str, task_goal: str) -> dict:
    """Ask Tier 3 (DeepSeek) to judge whether a diff satisfies a task goal.

    Fails closed (approved=False) on any peak-hours refusal, request
    failure, or unparseable response after one retry -- an unattended
    dispatch run must never silently treat a judge failure as approval.
    """
    peak_check = check_tier3_peak_hours_ok()
    if not peak_check["ok"]:
        log.info("Judge skipped: %s", peak_check["reason"])
        return {
            "status": "skipped",
            "approved": False,
            "reason": peak_check["reason"],
            "cost_usd": 0.0,
        }

    prompt = _build_prompt(diff_text, task_goal)

    def validate_json(response_text: str):
        cleaned = clean_response(response_text)
        return json.loads(cleaned)

    parsed, cost_usd, last_error = _call_tier3_with_retries(
        prompt,
        system_prompt="You are a strict design judge.",
        task_id="judge",
        validator_fn=validate_json,
    )

    if parsed is None:
        return {
            "status": "error",
            "approved": False,
            "reason": f"Could not parse judge response after retry: {last_error}",
            "cost_usd": cost_usd,
        }

    return {
        "status": "ok",
        "approved": bool(parsed.get("approved", False)),
        "reason": parsed.get("reason", ""),
        "cost_usd": cost_usd,
    }


def extract_pattern(full_file_text: str, diff_text: str) -> None:
    """Ask Tier 3 (DeepSeek) to extract a pattern from the file/diff and save it to hivemind.md."""
    peak_check = check_tier3_peak_hours_ok()
    if not peak_check["ok"]:
        log.info("Extract pattern skipped: %s", peak_check["reason"])
        return

    prompt = (
        "You are an expert software engineer analyzing a code change to extract general engineering patterns, lessons, or guidelines "
        "for future reference. Review the full file contents and the diff, then extract a reusable pattern, lesson, rule, or best practice.\n\n"
        "Your response MUST contain a single XML-wrapped <triapi_snippet> block containing the extracted lesson or pattern, "
        "formatted in clean Markdown. For example:\n"
        "<triapi_snippet>\n"
        "### [Pattern Title]\n"
        "...\n"
        "</triapi_snippet>\n\n"
        f"Full file text:\n```\n{full_file_text}\n```\n\n"
        f"Diff text:\n```\n{diff_text}\n```"
    )

    def validate_xml(response_text: str):
        match = re.search(r"<triapi_snippet>(.*?)</triapi_snippet>", response_text, re.DOTALL)
        if match:
            return match.group(1).strip()
        raise ValueError("Missing <triapi_snippet> tags in response")

    snippet, cost_usd, last_error = _call_tier3_with_retries(
        prompt,
        system_prompt="You are a helpful software engineering assistant.",
        task_id="judge_extract_pattern",
        validator_fn=validate_xml,
    )

    if snippet is None:
        log.error("Could not extract pattern after 2 attempts. Last error: %s", last_error)
        return

    hivemind_path = Path("knowledge/hivemind.md")
    hivemind_path.parent.mkdir(parents=True, exist_ok=True)

    with open(hivemind_path, "a+", encoding="utf-8") as f:
        locked = False
        try:
            # Advisory locking helps prevent concurrent-write corruption under real contention.
            # Fall back to proceeding without lock on failure if the platform does not fully support it.
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except (IOError, OSError) as e:
            log.warning("Could not acquire exclusive lock on %s: %s. Proceeding without lock.", hivemind_path, e)

        try:
            f.seek(0)
            content = f.read()
            if not content.strip():
                f.seek(0)
                f.truncate()
                f.write("# Hivemind\n\nCollective intelligence, lessons, and engineering patterns.\n\n")

            f.seek(0, 2)
            f.write(f"\n{snippet}\n")
        finally:
            if locked:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                except (IOError, OSError):
                    pass
