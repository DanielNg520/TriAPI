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
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import content_guard, edit_blocks
from scripts import lessons
from scripts import llm_client
from scripts.config_loader import load_tiers
from scripts.secrets_loader import load_secrets
from scripts.state import read_state
from scripts.tri_logging import get_logger

log = get_logger("tier3")

COST_LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "cost_log.jsonl"


def build_stable_context(
    target_path: Path,
    context_blob: str = "",
    current_contents: str | None = None,
    description: str = "",
) -> str:
    """Deterministic, byte-stable across calls for the same file contents.
    No timestamps or run-specific data allowed here -- that's what kills
    the prefix-cache hit rate. context_blob (other repo files a task
    description references, see tier4_worker.build_context_blob) is equally
    stable across retries for the same item, so it belongs in this cached
    prefix too, not the volatile per-call user message.

    target_path may not exist yet -- an item can be creating a new file
    (e.g. a new ADR), not editing one. Found for real 2026-08-14: an
    unconditional read_text() raised FileNotFoundError and crashed the
    whole (potentially hours-long, unattended) dispatch run. Mirrors
    tier1/tier2/tier4's own editing/new-file split.

    current_contents lets the caller pass the exact file snapshot that was
    shown to the model; if omitted, the file is read here. Callers should
    pass the same snapshot when later applying edit blocks so the SEARCH text
    the model saw is guaranteed to match the file being edited (avoids races
    where the file changes between prompt construction and response handling).
    """
    if current_contents is None:
        editing = target_path.exists()
    else:
        editing = True
    lessons_block = ""
    if editing:
        lessons_block = lessons.format_lessons_for_prompt(
            lessons.select_relevant(target_path.name, description)
        )
    header = (
        edit_blocks.build_edit_prompt_header(target_path.name, lessons_block=lessons_block) if editing else
        f"You are a coding/writing assistant working on {target_path.name}. Output "
        "ONLY the complete, corrected file contents inside a single fenced code "
        "block, using the language tag appropriate for this file (or no tag for "
        "plain text/markdown) -- no explanation."
    )
    parts = [header]
    if description:
        parts.append(f"Task description:\n{description}")
    if context_blob:
        parts.append(context_blob)
    if editing:
        current = current_contents if current_contents is not None else target_path.read_text()
        parts.append(f"Current contents of {target_path.name}:\n```\n{current}\n```")
    else:
        parts.append(f"{target_path.name} does not exist yet -- create it from scratch.")
    return "\n\n".join(parts)


def build_user_message(stderr: str, revision_note: str = "") -> str:
    if revision_note:
        return (
            "The current file already passes its build/verification. Improve only the "
            f"following quality issues without regressing behavior: {revision_note}"
        )
    return f"Build/verification error:\n```\n{stderr}\n```\n\nFix the file."


def extract_code(text: str) -> str | None:
    """Extract the fenced code block from a model response.

    The new-file prompt asks for exactly one fenced code block. This parser
    returns the first fenced block's contents, or the whole response trimmed
    if no fence is present. Defined locally (instead of importing from
    tier4_worker) so tier3 can rescue new-file creation even when Ollama --
    tier4_worker's backing service -- is down, which is exactly when tier3 is
    invoked. Importing tier4_worker at that point could try to reach Ollama's
    /api/generate endpoint and crash with a connection error.

    Returns None if a code fence was opened but never closed -- the response
    was cut off mid-generation (found for real 2026-08-18: a truncated
    DeepSeek response left an unterminated triple-quoted string in a new test
    file; content_guard.check_write() has nothing to compare a brand-new file
    against, so the broken content sailed straight through and only surfaced
    as a SyntaxError at build time, by which point Tier 2/Tier 1 couldn't
    SEARCH/REPLACE against the malformed content either). Callers must treat
    None as a failed attempt, not fall back to writing the raw fragment.
    """
    match = re.search(r"```(?:\w+)?\s*\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    if "```" in text:
        return None
    return text.strip()


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


def escalate(
    task_id: str,
    target: str,
    model: str | None = None,
    context_blob: str = "",
    revision_note: str = "",
    description: str = "",
) -> dict:
    config = load_tiers()
    tier3 = config["tier_3_debugger"]
    secrets = load_secrets()

    model_key = model or tier3["default_model"]
    model_name = tier3["models"][model_key]
    # .get(...) with an empty-dict fallback, not tier3["pricing"][model_key]:
    # a CLI-based provider in this slot (agy, cli) has no token pricing block
    # at all -- compute_cost() already treats missing price entries as
    # partial/$0. See the matching fix in judge.py._call_tier3_with_retries.
    model_pricing = tier3.get("pricing", {}).get(model_key, {})

    target_path = Path(target)
    state = read_state(task_id)
    stderr = state.get("last_stderr", "")

    log.info("[%s] Tier 3 (DeepSeek/%s) escalating for %s", task_id, model_name, target_path)

    # Snapshot the file once and reuse the same bytes for the prompt and the
    # later edit-block application. Re-checking existence or re-reading after
    # the API call would let a concurrent change desync the model's SEARCH
    # blocks from the file we apply them to.
    current_contents = target_path.read_text() if target_path.exists() else None
    stable_context = build_stable_context(
        target_path,
        context_blob,
        current_contents=current_contents,
        description=description,
    )
    user_message = build_user_message(stderr, revision_note)

    try:
        # .get(...) throughout, not direct indexing: tier_3_debugger is a
        # hot-swappable slot (per config/tiers.yaml's own design) and a
        # CLI-based provider here (agy, cli) has neither an `endpoint` nor
        # an `api_key_secret` field, and needs `effort` passed through where
        # a DeepSeek-shaped provider does not. Found 2026-08-25 alongside
        # the matching judge.py fix when this slot moved to agy.
        response_data, billing_type, input_tokens, output_tokens = llm_client.execute_llm(
            provider=tier3.get("provider", "deepseek"),
            endpoint=tier3.get("endpoint"),
            api_key=secrets.get(tier3.get("api_key_secret")),
            model=model_name,
            prompt=user_message,
            system_prompt=stable_context,
            is_tier4=False,
            effort=tier3.get("effort"),
        )
    except Exception as e:
        log.error("[%s] Tier 3 request failed: %s", task_id, e)
        return {
            "status": "error",
            "reason": f"Tier 3 request failed: {e}",
            "model": model_name,
            "cache_hit_tokens": 0,
            "cache_miss_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
        }

    # Extract message content and metadata from response
    if isinstance(response_data, dict):
        content = response_data.get("content")
        finish_reason = response_data.get("finish_reason")
        reasoning_content = response_data.get("reasoning_content")
    else:
        content = response_data
        finish_reason = None
        reasoning_content = None

    # Handle null/empty content branch
    if not content:
        has_reasoning = bool(reasoning_content)
        log.debug(
            "[%s] Tier 3 empty content: model=%s finish_reason=%s reasoning_content_populated=%s",
            task_id, model_name, finish_reason, has_reasoning
        )
        # Still log cost entry if usage data exists
        cache_hit_tokens = 0
        cache_miss_tokens = input_tokens
        cost_usd, partial = compute_cost(model_pricing, cache_hit_tokens, cache_miss_tokens, output_tokens)
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
        return {
            "status": "fix_rejected",
            "reason": f"Tier 3 returned empty content (finish_reason={finish_reason}, reasoning_content_populated={has_reasoning})",
            "model": model_name,
            "cache_hit_tokens": cache_hit_tokens,
            "cache_miss_tokens": cache_miss_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
        }

    response_text = content
    cache_hit_tokens = 0
    cache_miss_tokens = input_tokens
    
    cost_usd, partial = compute_cost(model_pricing, cache_hit_tokens, cache_miss_tokens, output_tokens)
    log.info(
        "[%s] Tier 3 response: input=%d output=%d cost=$%.6f%s",
        task_id, input_tokens, output_tokens, cost_usd,
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
    if current_contents is not None:
        new_content, err = edit_blocks.apply_edit_blocks(current_contents, response_text)
        if new_content is None:
            log.warning("[%s] Tier 3 edit-block apply failed: %s", task_id, err)
            return {
                "status": "fix_rejected",
                "reason": f"Could not apply proposed edit: {err}",
                "model": model_name,
                "cache_hit_tokens": cache_hit_tokens,
                "cache_miss_tokens": cache_miss_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost_usd,
            }
        fixed_code = new_content
    else:
        fixed_code = extract_code(response_text)
        if fixed_code is None:
            log.warning("[%s] Tier 3 new-file response truncated (unterminated code fence)", task_id)
            return {
                "status": "fix_rejected",
                "reason": "Tier 3 response truncated mid-generation (unterminated code fence); refusing to write incomplete file.",
                "model": model_name,
                "cache_hit_tokens": cache_hit_tokens,
                "cache_miss_tokens": cache_miss_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost_usd,
            }

    guard = content_guard.check_write(task_id, target_path, fixed_code)
    if not guard["ok"]:
        return {
            "status": "fix_rejected",
            "reason": guard["reason"],
            "model": model_name,
            "cache_hit_tokens": cache_hit_tokens,
            "cache_miss_tokens": cache_miss_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
        }

    target_path.parent.mkdir(parents=True, exist_ok=True)
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
