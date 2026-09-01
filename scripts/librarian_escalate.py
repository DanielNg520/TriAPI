"""Librarian: escalates stale library detection and update.

Asks agy/Gemini 3.7 Flash (config/tiers.yaml's tier_5_librarian) to
determine if a library file is stale based on a task description, writes
the updated file if stale, and runs a verification command. Fails fast to
human_handoff on any failure -- no multi-provider fallback chain (removed
2026-09-01: previously fell through local Ollama -> agy -> OpenRouter in
sequence). Designed to be invoked once per attempt; `consecutive_failures`
persists across external retries (dispatcher.py re-invoking run() for the
same item) so a verify-failure threshold is still enforced across calls.

Usage:
    python3 scripts/librarian_escalate.py --task-id t1 \
        --description "Update requests to v2.31.0" \
        --target samples/requirements.txt \
        --workdir samples/ \
        --verify-cmd "pip install -r requirements.txt"
"""

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import content_guard, edit_blocks, doc_staleness
from scripts import llm_client
from scripts.config_loader import load_tiers
from scripts.secrets_loader import load_secrets
from scripts.state import clear_state, read_state, record_failure
from scripts.tier4_worker import extract_code
from scripts.tri_logging import get_logger

log = get_logger("librarian")

COST_LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "cost_log.jsonl"


def log_cost(entry: dict) -> None:
    """Log token usage with zero USD cost -- librarian runs on local
    hardware, but the raw token counts are still recorded for
    scripts/cost_report.py to compare against paid tiers."""
    COST_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(COST_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def defensive_json_parse(text: str) -> dict | None:
    """Try to extract a JSON object from the model response, handling
    code fences and surrounding text. Returns None if no valid JSON."""
    text = text.strip()
    # Strip code fences if present
    fence_match = re.search(r"```(?:[a-zA-Z0-9_+-]*)\n(.*?)```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    # Try to find a JSON object in the text
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or start >= end:
        return None
    json_str = text[start:end+1]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def build_prompt(
    description: str,
    target_path: Path,
    current_contents: str | None = None,
    last_stderr: str = "",
) -> str:
    # No JSON envelope: the model replies either with the single-line FRESH
    # escape hatch (document already accurate) or with the raw edit blocks /
    # complete file contents directly. Asking for a JSON wrapper around
    # SEARCH/REPLACE blocks forced models to double-escape newlines and
    # routinely lost the "not stale" signal when the JSON failed to parse.
    fresh_prefix = (
        "If the document is already accurate for the described change, "
        "reply with exactly `FRESH` on a single line and nothing else; "
    )
    parts = []
    parts.append(
        "You are a librarian. Determine if the library file is stale based on the task description. "
        "If the file is stale, provide the updated file contents. If not, indicate it's not stale.\n\n"
        f"Task: {description}\n\n"
        f"File: {target_path.name}\n\n"
    )
    if current_contents is not None:
        # Existing file: a targeted SEARCH/REPLACE patch, never the whole file.
        parts.append(
            fresh_prefix
            + "otherwise reply with the SEARCH/REPLACE block(s) below.\n\n"
            + edit_blocks.build_edit_prompt_header(target_path.name)
        )
        parts.append(f"Current contents of {target_path.name}:\n```\n{current_contents}\n```")
    else:
        # Brand-new file: one fenced code block with the complete contents.
        parts.append(
            f"The file {target_path.name} does not exist yet. If the task requires it, "
            "create it with the appropriate contents.\n\n"
            + fresh_prefix
            + "otherwise reply with the complete new file contents in a single fenced code "
            "block (the format `tier4_worker.extract_code()` parses), with no other text."
        )
    if last_stderr:
        parts.append(
            f"Previous verification failed:\n```\n{last_stderr}\n```\n"
            "Please fix the file and provide updated contents."
        )
    return "\n\n".join(parts)


def _escalate_to_human(task_id: str, target_path: Path, reason: str, detail: str) -> None:
    """Writes logs/escalation_<task_id>.md via orchestrator.human_handoff().

    Deferred import: orchestrator imports this module at module load time
    (`from scripts import librarian_escalate`) to route doc targets here, so
    importing orchestrator back at module scope would be circular. Importing
    it lazily, inside the function body, resolves fine because by the time
    run() actually executes, both modules are already fully loaded."""
    from scripts import orchestrator
    orchestrator.human_handoff(task_id, reason, detail, component=str(target_path))


def run_command(cmd: str, workdir: str, timeout: int = 300) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=workdir, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL
        )
    except subprocess.TimeoutExpired as e:
        partial_out = e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        partial_err = e.stderr.decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        log.error("Command timed out after %ds: %s", timeout, cmd)
        return False, f"Command timed out after {timeout}s: {cmd}\n{partial_out}{partial_err}"
    ok = result.returncode == 0
    output = (result.stdout or "") + (result.stderr or "")
    return ok, output


def run(
    task_id: str,
    description: str,
    target: str,
    workdir: str = ".",
    verify_cmd: str | None = None,
    model_override: str | None = None,
) -> dict:
    config = load_tiers()
    lib_config = config.get("tier_5_librarian", {})
    threshold = config.get("escalation_rules", {}).get("tier5_to_fallbacks", {}).get("threshold", 2)

    # Resolve target path and enforce boundary check
    target_path = Path(target)
    if not target_path.is_absolute():
        target_path = Path(workdir) / target
    target_path = target_path.resolve()
    workdir_path = Path(workdir).resolve()
    try:
        target_path.relative_to(workdir_path)
    except ValueError:
        log.error("Target %s is outside workdir %s", target_path, workdir_path)
        return {"status": "error", "resolved_by": None, "reason": f"Target {target_path} is outside workdir {workdir_path}"}

    # Staleness pre-check: skip the model chain entirely when the doc is
    # already up-to-date for the described change. Zero LLM calls, zero
    # cost-log entries -- the caller (orchestrator/dispatcher) sees the
    # ordinary "success" shape and needs no changes.
    skip, reason = doc_staleness.should_skip_model_call(target_path, workdir, description)
    if skip:
        log.info("[%s] Staleness pre-check skipped model call: %s", task_id, reason)
        clear_state(task_id)
        return {
            "status": "success",
            "resolved_by": "tier_5",
            "consecutive_failures": 0,
            "stderr": "",
            "changed": False,
            "via": "staleness_precheck",
            "reason": reason,
        }

    editing = target_path.exists()
    current_contents = target_path.read_text() if editing else None

    # Single execution of the primary model using the `agy` provider
    models_cfg = lib_config.get("models", {})
    model = models_cfg.get("primary")
    last_stderr = ""
    prompt = build_prompt(description, target_path, current_contents, last_stderr)

    log.info("[%s] Librarian attempt via agy/%s", task_id, model)

    try:
        response_text, billing_type, input_tokens, output_tokens = llm_client.execute_agy(
            model=model,
            prompt=prompt,
            system_prompt="",
            effort=lib_config.get("effort"),
        )
    except Exception as e:
        log.error("[%s] Librarian agy request failed: %s", task_id, e, exc_info=True)
        last_stderr = f"LLM request failed: {e}"
        _escalate_to_human(
            task_id, target_path,
            "tier_5_librarian agy request failed",
            f"**LLM request failed:**\n```\n{e}\n```",
        )
        return {
            "status": "human_handoff",
            "resolved_by": None,
            "consecutive_failures": 1,
            "stderr": last_stderr,
        }

    # Strip the response and guard against None/empty.
    if not isinstance(response_text, str) or not response_text.strip():
        last_stderr = "Model returned no usable text (None or empty)"
        _escalate_to_human(
            task_id, target_path,
            "tier_5_librarian model returned no usable text",
            f"**Error:** Model returned no usable text",
        )
        return {
            "status": "human_handoff",
            "resolved_by": None,
            "consecutive_failures": 1,
            "stderr": last_stderr,
        }
    stripped_response = response_text.strip()

    # FRESH escape hatch: the model reports the document is already
    # accurate for the described change, so there is nothing to write.
    # Recurring bug (4+ confirmed instances, e.g. AGENTS.md/ARCHITECTURE.md
    # updates): the model claims FRESH even when the file demonstrably
    # still needs the described edit -- this used to be trusted
    # unconditionally, the exact "trust the status, not the diff"
    # mistake this repo's own convention warns against. When the caller
    # supplied a real verify_cmd (one that actually asserts something
    # about content, not the trivial existence-only default used for doc
    # targets with no explicit build_cmd), run it against the file as it
    # sits on disk before trusting the claim -- a verify_cmd written to
    # confirm a specific edit landed will fail if it didn't, contradicting
    # a false FRESH. No verify_cmd means nothing to check the claim
    # against, so it's trusted as before.
    if stripped_response == "FRESH":
        verify_cmd_resolved = verify_cmd or lib_config.get("verify_command")
        if verify_cmd_resolved:
            ok, verify_output = run_command(verify_cmd_resolved, workdir)
            if not ok:
                log.warning(
                    "[%s] Model claimed FRESH but verify_cmd contradicted it -- "
                    "rejecting the claim: %s", task_id, verify_output,
                )
                last_stderr = (
                    f"Model claimed the document was already FRESH, but verify_cmd "
                    f"contradicted that: {verify_output}"
                )
                _escalate_to_human(
                    task_id, target_path,
                    "tier_5_librarian FRESH claim contradicted by verify_cmd",
                    f"**Verification output:**\n```\n{verify_output}\n```",
                )
                return {
                    "status": "human_handoff",
                    "resolved_by": None,
                    "consecutive_failures": 1,
                    "stderr": verify_output,
                }
        log.info("[%s] Library is not stale (FRESH)", task_id)
        clear_state(task_id)
        return {
            "status": "success", "resolved_by": "tier_5", "consecutive_failures": 0,
            "stderr": "", "changed": False, "via": "model_fresh",
        }

    # Write path handling: edit_blocks for existing files, extract_code for new files.
    # The response is the raw edit blocks / complete file contents directly --
    # there is no JSON envelope to parse; the FRESH line above is the "not
    # stale" signal.
    if editing:
        new_content, err = edit_blocks.apply_edit_blocks(current_contents, stripped_response)
        if new_content is None:
            log.warning("[%s] Edit-block apply failed: %s", task_id, err)
            last_stderr = f"Could not apply proposed edit: {err}"
            _escalate_to_human(
                task_id, target_path,
                "tier_5_librarian edit block apply failed",
                f"**Edit error:**\n```\n{err}\n```",
            )
            return {
                "status": "human_handoff",
                "resolved_by": None,
                "consecutive_failures": 1,
                "stderr": err,
            }
        code = new_content
    else:
        code = extract_code(stripped_response)
        if code is None:
            log.warning("[%s] Response truncated mid-generation", task_id)
            last_stderr = "Response truncated mid-generation (unterminated code fence); refusing to write incomplete file."
            _escalate_to_human(
                task_id, target_path,
                "tier_5_librarian response truncated",
                f"**Error:** Response truncated mid-generation",
            )
            return {
                "status": "human_handoff",
                "resolved_by": None,
                "consecutive_failures": 1,
                "stderr": "Response truncated mid-generation",
            }

    guard = content_guard.check_write(task_id, target_path, code)
    if not guard["ok"]:
        log.warning("[%s] Content guard rejected: %s", task_id, guard["reason"])
        last_stderr = guard["reason"]
        _escalate_to_human(
            task_id, target_path,
            "tier_5_librarian content guard rejected",
            f"**Guard rejected:** {guard['reason']}",
        )
        return {
            "status": "human_handoff",
            "resolved_by": None,
            "consecutive_failures": 1,
            "stderr": guard["reason"],
        }

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(code)

    # Verification: built-in or custom verify_cmd
    verify_cmd_resolved = verify_cmd or lib_config.get("verify_command") or "true"
    ok, verify_output = run_command(verify_cmd_resolved, workdir)

    if ok:
        log.info("[%s] Verification succeeded", task_id)
        clear_state(task_id)
        return {
            "status": "success", "resolved_by": "tier_5", "consecutive_failures": 0,
            "stderr": "", "changed": True,
        }

    log.warning("[%s] Verification failed: %s", task_id, verify_output)
    last_stderr = verify_output
    state = record_failure(task_id, verify_output)
    if state["consecutive_failures"] >= threshold:
        log.error("[%s] Max failures reached, escalating to human handoff", task_id)
        _escalate_to_human(
            task_id, target_path,
            f"tier_5_librarian verification failed {state['consecutive_failures']}x (threshold {threshold})",
            f"**Verification output:**\n```\n{verify_output}\n```",
        )
        return {
            "status": "human_handoff",
            "resolved_by": None,
            "consecutive_failures": state["consecutive_failures"],
            "stderr": verify_output,
        }

    # No fallback chain anymore (2026-09-01): a verify failure below
    # threshold still returns human_handoff on THIS call, but the
    # `consecutive_failures` state is persisted across external retries
    # (dispatcher.py re-invoking run() for the same item on the next
    # attempt) via record_failure() above, so threshold is enforced across
    # calls, not via an internal per-call loop.
    log.error("[%s] Librarian attempt failed, escalating to human handoff", task_id)
    _escalate_to_human(
        task_id, target_path,
        "tier_5_librarian primary attempt failed",
        f"**Last error:**\n```\n{last_stderr}\n```",
    )
    return {
        "status": "human_handoff",
        "resolved_by": None,
        "consecutive_failures": state.get("consecutive_failures", 0),
        "stderr": last_stderr,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--target", required=True, help="path to the file to check/update")
    parser.add_argument("--workdir", default=".", help="directory to run verification command in")
    parser.add_argument("--verify-cmd", default=None, help="command to run to verify the update")
    parser.add_argument("--model", default=None, help="overrides config default model")
    args = parser.parse_args()

    result = run(args.task_id, args.description, args.target, args.workdir, args.verify_cmd, args.model)
    print(json.dumps(result))
    return result


if __name__ == "__main__":
    main()
