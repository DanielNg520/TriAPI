"""Tier 4: local Ollama drafting + build loop.

Asks a local Ollama model to draft/fix code for a task, writes it to the
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
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.config_loader import load_tiers
from scripts.state import clear_state, read_state, record_failure
from scripts.tri_logging import get_logger

log = get_logger("tier4")

CODE_FENCE_RE = re.compile(r"```(?:[a-zA-Z0-9_+-]*)\n(.*?)```", re.DOTALL)


def extract_code(response_text: str) -> str:
    blocks = CODE_FENCE_RE.findall(response_text)
    if blocks:
        return max(blocks, key=len).strip() + "\n"
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
    parts = [
        f"You are a coding/writing assistant working on {target_path.name}. Output "
        "ONLY the complete, corrected file contents inside a single fenced code "
        "block, using the language tag appropriate for this file (or no tag for "
        "plain text/markdown) -- no explanation.",
        f"Task: {description}",
    ]
    if context_blob:
        parts.append(context_blob)
    if target_path.exists():
        parts.append(f"Current contents of {target_path.name}:\n```\n{target_path.read_text()}\n```")
    if last_stderr:
        parts.append(f"Previous build/verification error:\n```\n{last_stderr}\n```")
    return "\n\n".join(parts)


def call_ollama(host: str, model: str, prompt: str) -> str:
    resp = requests.post(
        f"{host}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=300,
    )
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        log.error("Ollama request failed (model=%s): %s %s", model, resp.status_code, resp.text[:500])
        raise
    return resp.json()["response"]


def run_build(build_cmd: str, workdir: str, timeout: int = 120) -> tuple[bool, str]:
    result = subprocess.run(
        build_cmd, shell=True, cwd=workdir, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL
    )
    ok = result.returncode == 0
    output = (result.stdout or "") + (result.stderr or "")
    return ok, output


def run(task_id: str, description: str, target: str, workdir: str = ".", build_cmd: str | None = None, model: str | None = None, context_blob: str = "") -> dict:
    config = load_tiers()
    tier4 = config["tier_4_worker"]
    threshold = config["escalation_rules"]["tier4_to_tier3"]["threshold"]

    model = model or tier4["models"][tier4["default_model"]]
    build_cmd = build_cmd or " && ".join(tier4["build_commands"])

    target_arg = Path(target)
    target_path = target_arg if target_arg.is_absolute() else Path(workdir) / target_arg

    state = read_state(task_id)
    prompt = build_prompt(description, target_path, state.get("last_stderr", ""), context_blob)

    log.info("[%s] Tier 4 (Ollama/%s) drafting %s", task_id, model, target_path)

    response_text = call_ollama(tier4["endpoint"], model, prompt)
    code = extract_code(response_text)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(code)

    ok, build_output = run_build(build_cmd, workdir)

    if ok:
        log.info("[%s] Tier 4 build succeeded", task_id)
        clear_state(task_id)
        return {"status": "success", "consecutive_failures": 0, "stderr": ""}

    state = record_failure(task_id, build_output)
    status = "escalate" if state["consecutive_failures"] >= threshold else "build_failed"
    log.info("[%s] Tier 4 build failed (consecutive_failures=%d, threshold=%d)", task_id, state["consecutive_failures"], threshold)
    return {
        "status": status,
        "consecutive_failures": state["consecutive_failures"],
        "stderr": build_output,
    }


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
