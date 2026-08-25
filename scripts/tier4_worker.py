"""Tier 4: OpenRouter drafting + build loop.

Asks an OpenRouter model to draft/fix code for a task, writes it to the
target file, runs the project's build command, and tracks consecutive
build failures in logs/state/<task_id>.json. Designed to be invoked once
per attempt (e.g. by an orchestrator or Antigravity via MCP), not as a
long-running loop -- the failure count persists across invocations.

Usage:
    python3 scripts/tier4_worker.py --task-id t1 \\
        --description "Fix the compile error" \\
        --target samples/broken_build/main.cpp \\
        --workdir samples/broken_build \\
        --build-cmd "cmake -S . -B build && cmake --build build"
"""

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import content_guard, edit_blocks, hivemind_util, lessons, llm_client
from scripts.config_loader import load_tiers
from scripts.secrets_loader import load_secrets
from scripts.state import clear_state, read_state, record_failure
from scripts.tri_logging import get_logger

log = get_logger("tier4")

COST_LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "cost_log.jsonl"


def log_cost(entry: dict) -> None:
    """Tier 4 runs on local hardware (no per-token API bill), but the raw
    token counts still matter -- they're the only record of how much work
    the local model actually did, which is what scripts/cost_report.py
    needs to compare against what the same work would have cost on a paid
    tier. Mirrors the log_cost() shape used by tiers 1-3 (same file,
    same fields where applicable) so the report script can aggregate all
    four tiers with one code path."""
    COST_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(COST_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")

CODE_FENCE_RE = re.compile(r"```(?:[a-zA-Z0-9_+-]*)\n(.*?)```", re.DOTALL)


def extract_code(response_text: str) -> str | None:
    """Returns None if a code fence was opened but never closed -- the
    response was cut off mid-generation. Callers must treat None as a
    failed attempt, never fall back to writing the raw, truncated fragment
    (found for real 2026-08-18: a truncated new-file response left an
    unterminated triple-quoted string; content_guard.check_write() has
    nothing to compare a brand-new file against, so it passed straight
    through and only surfaced as a build-time SyntaxError)."""
    blocks = CODE_FENCE_RE.findall(response_text)
    if blocks:
        return max(blocks, key=len).strip() + "\n"
    if "```" in response_text:
        return None
    return response_text.strip() + "\n"


def build_context_blob(paths: list[str], workdir: str, max_chars_per_file: int = 20000) -> str:
    """Reads other repo files a task description references (e.g. "seeded
    from X", "following Y's pattern") into a labeled, read-only block so
    drafting has real grounding instead of guessing at their content.
    Missing paths are skipped (logged), not fatal -- a plan step can
    reference a file that turns out not to exist, that's the drafter's
    problem to notice, not this helper's. Each file is capped so one huge
    reference file can't blow out the prompt."""
    if not paths:
        return ""
    parts = []
    for p in paths:
        path_obj = Path(p)
        resolved = path_obj if path_obj.is_absolute() else Path(workdir) / path_obj
        if not resolved.is_file():
            log.warning("Context file not found, skipping: %s", resolved)
            continue
        content = resolved.read_text(errors="replace")
        if len(content) > max_chars_per_file:
            content = content[:max_chars_per_file] + "\n... (truncated)"
        parts.append(f"Reference file `{p}` (read-only, for grounding only -- do not modify):\n```\n{content}\n```")
    return "\n\n".join(parts)


def build_prompt(description: str, target_path: Path, last_stderr: str, context_blob: str = "") -> str:
    editing = target_path.exists()
    if editing:
        lessons_text = lessons.format_lessons_for_prompt(
            lessons.select_relevant(target_path.name, description)
        )
        header = edit_blocks.build_edit_prompt_header(
            target_path.name, lessons_block=lessons_text
        )
    else:
        header = (
            f"You are a coding/writing assistant working on {target_path.name}. Output "
            "ONLY the complete, corrected file contents inside a single fenced code "
            "block, using the language tag appropriate for this file (or no tag for "
            "plain text/markdown) -- no explanation."
        )
    parts = [header, f"Task: {description}"]
    if context_blob:
        parts.append(context_blob)
    if editing:
        parts.append(f"Current contents of {target_path.name}:\n```\n{target_path.read_text()}\n```")
    if last_stderr:
        parts.append(f"Previous build/verification error:\n```\n{last_stderr}\n```")
    return "\n\n".join(parts)


def run_build(build_cmd: str, workdir: str, timeout: int = 300) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["bash", "-o", "pipefail", "-c", build_cmd], cwd=workdir, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL
        )
    except subprocess.TimeoutExpired as e:
        # A slow build_cmd (e.g. a test suite that cold-loads a large local
        # model) must fail like any other build failure, not crash the
        # whole unattended dispatch process -- found for real 2026-08-11:
        # `./run_tests.sh` alone exceeded the then-120s default and took down
        # the entire dispatch run with an uncaught traceback, no escalation
        # recorded, mid-run. Default raised to 300s 2026-08-20 after a
        # different repo's growing full suite (script + pytest, 86 files)
        # started tripping the same 120s wall on every tier identically --
        # since Tier 3/2/1 only patch-and-rebuild (never re-draft), a slow
        # test command fails the same way regardless of which tier is
        # trying, so the whole escalation chain hit human_handoff on a
        # passing build. Partial output captured before the timeout is
        # preserved (e.g. e.stdout is bytes when text=True isn't honored on
        # a timeout -- decode defensively) so the human_handoff/escalation
        # path still shows what ran before it hung.
        partial_out = e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        partial_err = e.stderr.decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        log.error("Build command timed out after %ds: %s", timeout, build_cmd)
        return False, f"Command timed out after {timeout}s: {build_cmd}\n{partial_out}{partial_err}"
    ok = result.returncode == 0
    output = (result.stdout or "") + (result.stderr or "")
    return ok, output


def _tier4_fail(task_id: str, threshold: int, reason: str, is_oversize_failure: bool = False) -> dict:
    effective_threshold = 1 if is_oversize_failure else threshold
    state = record_failure(task_id, reason)
    status = "escalate" if state["consecutive_failures"] >= effective_threshold else "build_failed"
    return {"status": status, "consecutive_failures": state["consecutive_failures"], "stderr": reason}


def run(task_id: str, description: str, target: str, workdir: str = ".", build_cmd: str | None = None, model: str | None = None, context_blob: str = "") -> dict:
    config = load_tiers()
    tier4 = config["tier_4_worker"]
    threshold = config["escalation_rules"]["tier4_to_tier3"]["threshold"]

    model = model or tier4["models"][tier4["default_model"]]
    build_cmd = build_cmd or " && ".join(tier4["build_commands"])

    target_arg = Path(target)
    target_path = target_arg if target_arg.is_absolute() else Path(workdir) / target_arg
    editing = target_path.exists()

    state = read_state(task_id)
    prompt = build_prompt(description, target_path, state.get("last_stderr", ""), context_blob)

    hivemind_code = hivemind_util.search_hivemind(description, target_path.suffix)
    if hivemind_code is not None:
        prompt += (
            "\n\n[HIVEMIND REFERENCE PATTERN]\n"
            "Adapt this structure for your solution:\n"
            f"{hivemind_code}"
        )

    log.info("[%s] Tier 4 (%s/%s) drafting %s", task_id, tier4.get('provider', 'ollama'), model, target_path)

    secrets = load_secrets()
    # A systemic/connectivity error here (Ollama down, timeout, HTTP error)
    # must NOT be downgraded to an ordinary build_failed/escalate result --
    # orchestrator.run_task()'s caller wraps this function specifically to
    # crash the pipeline (raise) on any exception, matching how tiers 1-3
    # fail hard on the same class of error. Do not add a try/except here.
    response_text, billing_type, input_tokens, output_tokens = llm_client.execute_llm(
        provider=tier4.get('provider', 'ollama'),
        endpoint=tier4.get('endpoint'),
        api_key=secrets.get(tier4.get('api_key_secret', 'open_router_api_key')),
        model=model,
        prompt=prompt,
        system_prompt='',
        is_tier4=True
    )

    log_cost({
        "timestamp": time.time(),
        "tier": "tier_4",
        "model": model,
        "task_id": task_id,
        "prompt_eval_count": input_tokens,
        "eval_count": output_tokens,
        "cost_usd": 0.0,
    })

    if editing:
        # Existing file: apply a targeted patch, never a full-file overwrite
        # (see edit_blocks.py -- asking for the whole file back is what
        # caused real, large, silent content loss on 2026-08-10).
        new_content, err = edit_blocks.apply_edit_blocks(target_path.read_text(), response_text)
        if new_content is None:
            log.warning("[%s] Tier 4 edit-block apply failed: %s", task_id, err)
            return _tier4_fail(task_id, threshold, f"Could not apply proposed edit: {err}")
        code = new_content
    else:
        code = extract_code(response_text)
        if code is None:
            return _tier4_fail(task_id, threshold, "Tier 4 response truncated mid-generation (unterminated code fence); refusing to write incomplete file.", is_oversize_failure=True)

    guard = content_guard.check_write(task_id, target_path, code)
    if not guard["ok"]:
        return _tier4_fail(task_id, threshold, guard["reason"])

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(code)

    ok, build_output = run_build(build_cmd, workdir)

    if ok:
        log.info("[%s] Tier 4 build succeeded", task_id)
        clear_state(task_id)
        return {"status": "success", "consecutive_failures": 0, "stderr": ""}

    is_oversize = build_output.startswith("Command timed out after")
    return _tier4_fail(task_id, threshold, build_output, is_oversize_failure=is_oversize)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--target", required=True, help="path to the file to draft/fix")
    parser.add_argument("--workdir", default=".", help="directory to run the build command in")
    parser.add_argument("--build-cmd", default=None, help="overrides config build_commands")
    parser.add_argument("--model", default=None, help="overrides config default draft model")
    parser.add_argument("--context-file", action="append", default=[], help="other repo file(s) to read for grounding, relative to --workdir; repeatable")
    args = parser.parse_args()

    context_blob = build_context_blob(args.context_file, args.workdir)
    result = run(args.task_id, args.description, args.target, args.workdir, args.build_cmd, args.model, context_blob)
    print(json.dumps(result))
    return result


if __name__ == "__main__":
    main()
