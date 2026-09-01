"""Tier 2: Escalation client (Nemotron via OpenRouter).

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
import subprocess
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import content_guard, edit_blocks, llm_client
from scripts import budget_guard
from scripts.config_loader import load_tiers
from scripts.secrets_loader import load_secrets
from scripts.state import read_state
from scripts.tier4_worker import extract_code
from scripts.tri_logging import get_logger
from scripts import lessons

log = get_logger("tier2")


def check_tier2_ok():
    return budget_guard.check_tier2_ok()


def resolve_peak_conditional(config):
    return budget_guard.resolve_peak_conditional(config)


COST_LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "cost_log.jsonl"

def build_user_content(
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
    # target_path may not exist yet (a new file, e.g. a new ADR) -- see
    # tier1_escalate.py's build_prompt for the same fix and why.
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
    model: str | None = None,
    context_blob: str = "",
    revision_note: str = "",
    description: str = "",
) -> dict:
    try:
        guard = check_tier2_ok()
    except requests.RequestException as e:
        log.warning("[%s] Tier 2 budget guard check failed: %s", task_id, e)
        return {"status": "skipped", "reason": f"Tier 2 budget guard check failed: {e}"}
    if not guard["ok"]:
        log.warning("[%s] Tier 2 skipped: %s", task_id, guard["reason"])
        return {"status": "skipped", "reason": guard["reason"]}

    config = load_tiers()
    tier2 = resolve_peak_conditional(config["tier_2_manager"])
    secrets = load_secrets()

    default_model = tier2["models"][tier2["default_model"]]
    # Fail fast on any request error instead of hopping through a
    # fallback_chain: a fallback list previously masked real failures
    # (auth, 5xx, network) behind a synthetic "all candidates failed"
    # result and silently swapped models on transient 429/403s.
    model_name = model or default_model

    target_path = Path(target)
    current_contents = target_path.read_text() if target_path.exists() else None
    editing = current_contents is not None
    state = read_state(task_id)
    stderr = state.get("last_stderr", "")
    user_content = build_user_content(
        target_path,
        stderr,
        context_blob,
        revision_note,
        current_contents=current_contents,
        description=description,
    )
    system_instruction = (
        edit_blocks.build_edit_prompt_header(
            target_path.name,
            lessons_block=lessons.format_lessons_for_prompt(
                lessons.select_relevant(target_path.name, description)
            ),
        ) if editing else
        f"You are a coding/writing assistant working on {target_path.name}. Output "
        "ONLY the complete, corrected file contents inside a single fenced code "
        "block, using the language tag appropriate for this file (or no tag for "
        "plain text/markdown) -- no explanation."
    )

    log.info("[%s] Tier 2 (%s) escalating for %s", task_id, model_name, target_path)
    try:
        response_text, billing_type, prompt_tokens, output_tokens = llm_client.execute_llm(
            provider=tier2.get("provider", "openrouter"),
            endpoint=tier2.get("endpoint"),
            api_key=secrets.get(tier2.get("api_key_secret", "open_router_api_key")),
            model=model_name,
            prompt=user_content,
            system_prompt=system_instruction,
            is_tier4=False,
        )
    except Exception as e:
        # agy's argv-size guard (llm_client._call_agy_cli) raises a
        # synthetic CalledProcessError(0, ...) for a too-large prompt --
        # not a real request failure, and orchestrator.run_task treats
        # any Tier 2 "error" status as fatal (raises RuntimeError,
        # crashing the whole dispatch). Found for real 2026-09-01: an
        # item editing a large file escalated Tier4->Tier3->Tier2 (agy,
        # during peak hours) and its prompt (system prompt + full file
        # contents) exceeded agy's 100k-char argv limit, crashing an
        # otherwise-recoverable dispatch instead of gracefully falling
        # through to Tier 1 (Claude, stdin-based, no argv limit). Return
        # "skipped" instead of "error" for this specific case so
        # orchestrator.py's Tier 2 block just falls through.
        if (
            isinstance(e, subprocess.CalledProcessError)
            and e.returncode == 0
            and "prompt too large for argv" in (e.stderr or "")
        ):
            log.warning("[%s] Tier 2 (%s) prompt too large for agy's argv limit, skipping to Tier 1: %s", task_id, model_name, e)
            return {"status": "skipped", "reason": str(e)}
        log.error("[%s] Tier 2 request failed on %s: %s", task_id, model_name, e, exc_info=True)
        return {"status": "error", "reason": f"Tier 2 request failed on {model_name}: {e}"}

    cached_tokens = 0

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
            "billing": billing_type,
        }
    )
    if editing:
        new_content, err = edit_blocks.apply_edit_blocks(current_contents, response_text)
        if new_content is None:
            # Not all models reliably return SEARCH/REPLACE blocks even when
            # prompted to; fall back to treating the response as a full-file
            # replacement (same extraction used for new files) before
            # giving up outright.
            fallback_code = extract_code(response_text)
            if fallback_code is None:
                log.warning("[%s] Tier 2 edit-block apply failed: %s", task_id, err)
                return {
                    "status": "fix_rejected",
                    "reason": f"Could not apply proposed edit: {err}",
                    "model": model_name,
                    "prompt_tokens": prompt_tokens,
                    "cached_tokens": cached_tokens,
                    "output_tokens": output_tokens,
                }
            log.info(
                "[%s] Tier 2 edit-block apply failed (%s); falling back to full-file replacement",
                task_id, err,
            )
            new_content = fallback_code
        fixed_code = new_content
    else:
        fixed_code = extract_code(response_text)
        if fixed_code is None:
            return {
                "status": "fix_rejected",
                "reason": "Tier 2 response truncated mid-generation (unterminated code fence); refusing to write incomplete file.",
                "model": model_name,
                "prompt_tokens": prompt_tokens,
                "cached_tokens": cached_tokens,
                "output_tokens": output_tokens,
            }

    guard = content_guard.check_write(task_id, target_path, fixed_code)
    if not guard["ok"]:
        return {
            "status": "fix_rejected",
            "reason": guard["reason"],
            "model": model_name,
            "prompt_tokens": prompt_tokens,
            "cached_tokens": cached_tokens,
            "output_tokens": output_tokens,
        }

    target_path.parent.mkdir(parents=True, exist_ok=True)
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
