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
from scripts import content_guard, edit_blocks, gemini_fallback
from scripts.budget_guard import check_tier2_ok
from scripts.config_loader import load_tiers
from scripts.secrets_loader import load_secrets
from scripts.state import read_state
from scripts.tier4_worker import extract_code
from scripts.tri_logging import get_logger
from scripts import lessons

log = get_logger("tier2")

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
    tier2 = config["tier_2_manager"]
    secrets = load_secrets()

    default_model = tier2["models"][tier2["default_model"]]
    models = [tier2["models"][model]] if model else (tier2.get("fallback_chain") or [default_model])

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

    log.info("[%s] Tier 2 (Gemini/%s) escalating for %s", task_id, models[0], target_path)

    try:
        resp, model_name = gemini_fallback.post_generate_content(
            requests.post,
            tier2["endpoint"],
            secrets["google_ai_studio_api_key"],
            {
                "systemInstruction": {"parts": [{"text": system_instruction}]},
                "contents": [{"role": "user", "parts": [{"text": user_content}]}],
            },
            models,
            timeout=180,
        )
    except requests.RequestException as e:
        # A raw connection/timeout failure from post_generate_content's own
        # requests.post() call -- previously uncaught here, crashing the
        # whole unattended dispatch process. Same fix as the raise_for_status
        # case below: treat it as an ordinary escalation failure.
        log.error("[%s] Tier 2 request failed: %s", task_id, e)
        return {"status": "error", "reason": f"Gemini request failed: {e}"}
    if model_name != models[0]:
        log.info("[%s] Tier 2 used fallback model %s (default %s exhausted for today)", task_id, model_name, models[0])
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        # Previously re-raised after logging -- propagated uncaught through
        # orchestrator.run_task()/dispatcher.dispatch(), crashing the whole
        # unattended dispatch process on a transient Gemini-side error (a
        # real 503 killed a run 2026-08-13). Tier 1/Tier 4 already treat
        # their own request failures as an ordinary escalation failure
        # instead of a crash; Tier 2 didn't. Now consistent: return a
        # normal error result so orchestrator falls through to human_handoff
        # like any other failed tier, instead of taking the process down.
        log.error("[%s] Tier 2 request failed: %s %s", task_id, resp.status_code, resp.text[:500])
        return {"status": "error", "reason": f"Gemini request failed: {e}"}
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
    if editing:
        new_content, err = edit_blocks.apply_edit_blocks(current_contents, response_text)
        if new_content is None:
            log.warning("[%s] Tier 2 edit-block apply failed: %s", task_id, err)
            return {
                "status": "fix_rejected",
                "reason": f"Could not apply proposed edit: {err}",
                "model": model_name,
                "prompt_tokens": prompt_tokens,
                "cached_tokens": cached_tokens,
                "output_tokens": output_tokens,
            }
        fixed_code = new_content
    else:
        fixed_code = extract_code(response_text)

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
