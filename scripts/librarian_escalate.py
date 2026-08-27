"""Librarian: escalates stale library detection and update.

Asks an Ollama model to determine if a library file is stale based on a
task description, writes the updated file if stale, runs a verification
command, and falls back through local Ollama, OpenRouter, and human
handoff if verification fails. Designed to be invoked once per attempt.

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

    # Escalation chain per config/tiers.yaml: primary (config-driven provider)
    # -> fallback_local (Ollama, ollama_fallback's model) -> fallback_agy
    # (agy CLI) -> fallback_openrouter (OpenRouter, tier_1_planner's free model).
    # DeepSeek/Claude/Gemini are strictly forbidden anywhere in this chain.
    models_cfg = lib_config.get("models", {})
    fallback_local_block = config.get(models_cfg.get("fallback_local", "ollama_fallback"), {})
    providers = [
        {
            "name": lib_config.get("provider", "ollama"),
            "model": model_override or models_cfg.get("primary", "mistral-small:latest"),
            "effort": lib_config.get("effort"),
        },
        {"name": "ollama", "model": model_override or fallback_local_block.get("models", {}).get("default")},
        {"name": "agy", "model": models_cfg.get("fallback_agy")},
        {"name": "openrouter", "model": model_override or models_cfg.get("fallback_openrouter")},
    ]

    secrets = load_secrets()
    last_stderr = ""
    state = {"consecutive_failures": 0}
    for attempt_idx, provider_info in enumerate(providers):
        provider = provider_info["name"]
        model = provider_info["model"]

        # Enforce zero DeepSeek/Claude/Gemini calls
        if provider in ("deepseek", "claude", "gemini") or not model:
            log.warning("Skipping disallowed/unresolved provider: %s/%s", provider, model)
            continue

        prompt = build_prompt(description, target_path, current_contents, last_stderr)

        if provider == "openrouter":
            endpoint = config.get("tier_1_planner", {}).get("endpoint")
            api_key = secrets.get(lib_config.get("api_key_secret", "open_router_api_key"))
        elif provider == "agy":
            endpoint = None
            api_key = None
        else:
            endpoint = secrets.get("ollama_host")
            api_key = None

        log.info("[%s] Librarian attempt %d via %s/%s", task_id, attempt_idx + 1, provider, model)

        try:
            if provider == "agy":
                response_text, billing_type, input_tokens, output_tokens = llm_client.execute_agy(
                    model=model,
                    prompt=prompt,
                    system_prompt="",
                    effort=provider_info.get("effort"),
                )
            else:
                response_text, billing_type, input_tokens, output_tokens = llm_client.execute_llm(
                    provider=provider,
                    endpoint=endpoint,
                    api_key=api_key,
                    model=model,
                    prompt=prompt,
                    system_prompt="",
                    is_tier4=False,
                )
        except Exception as e:
            log.error("[%s] Librarian %s request failed: %s", task_id, provider, e, exc_info=True)
            last_stderr = f"LLM request failed: {e}"
            continue

        # Both "ollama"-provider slots (primary + fallback_local) run on local
        # hardware at zero cost; tag them "local" for cost_report.py. The agy
        # leg is a subscription CLI, so tag it "subscription" ($0 marginal).
        # The openrouter fallback remains distinguishable via billing_type.
        if provider == "ollama":
            billing_label = "local"
        elif provider == "agy":
            billing_label = "subscription"
        else:
            billing_label = billing_type
        log_cost(
            {
                "timestamp": time.time(),
                "tier": "librarian",
                "model": model,
                "task_id": task_id,
                "prompt_eval_count": input_tokens,
                "eval_count": output_tokens,
                "cost_usd": 0.0,
                "billing": billing_label,
            }
        )

        # Strip the response and guard against None/empty.
        if not isinstance(response_text, str) or not response_text.strip():
            log.warning("[%s] Model returned no usable text (None or empty)", task_id)
            last_stderr = "Model returned no usable text (None or empty)"
            continue
        stripped_response = response_text.strip()

        # FRESH escape hatch: the model reports the document is already
        # accurate for the described change, so there is nothing to write.
        if stripped_response == "FRESH":
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
                continue
            code = new_content
        else:
            code = extract_code(stripped_response)
            if code is None:
                log.warning("[%s] Response truncated mid-generation", task_id)
                last_stderr = "Response truncated mid-generation (unterminated code fence); refusing to write incomplete file."
                continue

        guard = content_guard.check_write(task_id, target_path, code)
        if not guard["ok"]:
            log.warning("[%s] Content guard rejected: %s", task_id, guard["reason"])
            last_stderr = guard["reason"]
            continue

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

    # All providers exhausted
    log.error("[%s] All librarian attempts failed, escalating to human handoff", task_id)
    _escalate_to_human(
        task_id, target_path,
        "tier_5_librarian exhausted primary -> fallback_local -> fallback_agy -> fallback_openrouter",
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
