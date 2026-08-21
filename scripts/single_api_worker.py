"""Single-API worker: draft-apply-build loop using one configured backend.

This worker is the non-local counterpart to tier4_worker.py. Instead of
asking a local Ollama model, it uses one of the configured hosted backends
(Gemini via gemini_fallback, Claude via the `claude` CLI, or DeepSeek via
its HTTP API). It retries the draft/apply/build cycle up to max_retries,
then escalates to orchestrator.human_handoff.

Usage:
    python3 scripts/single_api_worker.py --task-id t1 \\
        --description "Fix the compile error" \\
        --target samples/broken_build/main.cpp \\
        --workdir samples/broken_build \\
        --build-cmd "cmake -S . -B build && cmake --build build" \\
        --backend gemini
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import content_guard, edit_blocks, gemini_fallback, hivemind_util, lessons, orchestrator
from scripts.config_loader import load_tiers
from scripts.tri_logging import get_logger

log = get_logger("single_api")

CODE_FENCE_RE = re.compile(r"```(?:[a-zA-Z0-9_+-]*)\n(.*?)```", re.DOTALL)


def extract_code(response_text: str) -> str | None:
    """Extracts the longest fenced code block from response_text.

    If a code fence is opened but never closed, returns None.
    If no code fence is found, returns response_text.
    """
    blocks = CODE_FENCE_RE.findall(response_text)
    if blocks:
        return max(blocks, key=len).strip() + "\n"
    if "```" in response_text:
        return None
    return response_text.strip() + "\n"


def build_context_blob(paths: list[str], workdir: str, max_chars_per_file: int = 20000) -> str:
    """Reads other repo files referenced by a task description for grounding.

    Missing files are skipped, and files exceeding max_chars_per_file are truncated.
    """
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
    """Builds a structured prompt for editing or creating a target file.

    Incorporates lessons relevant to the task and target file, context files,
    current contents (if editing), and the last build/verification error.
    """
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
    """Runs the project's build command with a timeout.

    Returns a tuple of (success, output). Captures stdout and stderr defensively on timeout.
    """
    try:
        result = subprocess.run(
            build_cmd, shell=True, cwd=workdir, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL
        )
    except subprocess.TimeoutExpired as e:
        partial_out = e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        partial_err = e.stderr.decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        log.error("Build command timed out after %ds: %s", timeout, build_cmd)
        return False, f"Command timed out after {timeout}s: {build_cmd}\n{partial_out}{partial_err}"
    ok = result.returncode == 0
    output = (result.stdout or "") + (result.stderr or "")
    return ok, output


def _draft_with_gemini(prompt: str, config: dict) -> str:
    """Drafts content using the Gemini backend."""
    gemini_key = os.environ.get("GEMINI_API_KEY") or config.get("gemini", {}).get("api_key")
    gemini_model = config.get("gemini", {}).get("model") or "gemini-1.5-pro"
    
    res = gemini_fallback.post_generate_content(prompt, config=config, api_key=gemini_key, model=gemini_model)
    if isinstance(res, str):
        return res
    if hasattr(res, "text"):
        return res.text
    if isinstance(res, dict):
        try:
            return res["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            return str(res)
    return str(res)


def _draft_with_claude(prompt: str, timeout: int = 120) -> str:
    """Drafts content using the Claude CLI backend with a timeout."""
    res = subprocess.run(["claude"], input=prompt, capture_output=True, text=True, timeout=timeout)
    if res.returncode != 0:
        res2 = subprocess.run(["claude", prompt], capture_output=True, text=True, timeout=timeout)
        if res2.returncode != 0:
            raise RuntimeError(f"Claude CLI execution failed: {res.stderr}\n{res2.stderr}")
        return res2.stdout
    return res.stdout


def _draft_with_deepseek(prompt: str, config: dict) -> str:
    """Drafts content using the DeepSeek HTTP API."""
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY") or config.get("deepseek", {}).get("api_key")
    deepseek_url = config.get("deepseek", {}).get("endpoint") or "https://api.deepseek.com/chat/completions"
    deepseek_model = config.get("deepseek", {}).get("model") or "deepseek-coder"
    
    headers = {
        "Authorization": f"Bearer {deepseek_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": deepseek_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0
    }
    resp = requests.post(deepseek_url, json=payload, headers=headers, timeout=120)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def run(task_id: str, description: str, target: str, workdir: str = ".", build_cmd: str | None = None, context_blob: str = "", config: dict | None = None, backend: str = "gemini") -> dict:
    """Runs a draft-apply-build loop using the specified backend.

    Retries drafting, applying edits/code, and running build commands up to
    max_retries. If all attempts fail, escalates to orchestrator.human_handoff.
    """
    if config is None:
        config = load_tiers()

    max_retries = config.get("single_api_worker", {}).get("max_retries") or config.get("max_retries", 3)

    if not build_cmd:
        build_commands = config.get("single_api_worker", {}).get("build_commands") or config.get("build_commands", ["make"])
        if isinstance(build_commands, list):
            build_cmd = " && ".join(build_commands)
        else:
            build_cmd = str(build_commands)

    target_path = Path(target) if Path(target).is_absolute() else Path(workdir) / Path(target)
    editing = target_path.exists()

    last_stderr = ""
    for attempt in range(1, max_retries + 1):
        log.info("[%s] Attempt %d/%d drafting with %s", task_id, attempt, max_retries, backend)
        prompt = build_prompt(description, target_path, last_stderr, context_blob)

        hivemind_code = hivemind_util.search_hivemind(description, target_path.suffix)
        if hivemind_code is not None:
            prompt += (
                "\n\n[HIVEMIND REFERENCE PATTERN]\n"
                "Adapt this structure for your solution:\n"
                f"{hivemind_code}"
            )

        try:
            if backend == "gemini":
                response_text = _draft_with_gemini(prompt, config)
            elif backend == "claude":
                response_text = _draft_with_claude(prompt)
            elif backend == "deepseek":
                response_text = _draft_with_deepseek(prompt, config)
            else:
                raise ValueError(f"Unknown backend: {backend}")
        except Exception as e:
            log.error("[%s] Attempt %d failed due to API/CLI error: %s", task_id, attempt, e)
            last_stderr = f"API/CLI call failed: {e}"
            continue

        if editing:
            new_content, err = edit_blocks.apply_edit_blocks(target_path.read_text(), response_text)
            if new_content is None:
                log.warning("[%s] Attempt %d edit block apply failed: %s", task_id, attempt, err)
                last_stderr = f"Could not apply proposed edit: {err}"
                continue
            code = new_content
        else:
            code = extract_code(response_text)
            if code is None:
                log.warning("[%s] Attempt %d response truncated", task_id, attempt)
                last_stderr = "Response truncated mid-generation (unterminated code fence); refusing to write incomplete file."
                continue

        guard = content_guard.check_write(task_id, target_path, code)
        if not guard["ok"]:
            log.warning("[%s] Attempt %d content guard rejected: %s", task_id, attempt, guard["reason"])
            last_stderr = guard["reason"]
            continue

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(code)

        ok, build_output = run_build(build_cmd, workdir)
        if ok:
            log.info("[%s] Build succeeded on attempt %d!", task_id, attempt)
            return {"status": "success", "resolved_by": backend}
        else:
            log.warning("[%s] Build failed on attempt %d", task_id, attempt)
            last_stderr = build_output

    log.warning("[%s] Hit max_retries (%d) for backend %s. Escalating to human handoff.", task_id, max_retries, backend)
    try:
        return orchestrator.human_handoff(
            task_id=task_id,
            description=description,
            target=target,
            workdir=workdir,
            build_cmd=build_cmd,
        )
    except Exception as e:
        log.error("[%s] Failed to call orchestrator.human_handoff: %s", task_id, e)
        return {"status": "human_handoff", "reason": "Max retries reached and orchestrator.human_handoff call failed"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--workdir", default=".")
    parser.add_argument("--build-cmd", default=None)
    parser.add_argument("--backend", default="gemini")
    parser.add_argument("--context-file", action="append", default=[])
    args = parser.parse_args()

    config = load_tiers()
    context_blob = build_context_blob(args.context_file, args.workdir)
    result = run(
        task_id=args.task_id,
        description=args.description,
        target=args.target,
        workdir=args.workdir,
        build_cmd=args.build_cmd,
        context_blob=context_blob,
        config=config,
        backend=args.backend
    )
    print(json.dumps(result))
    return result


if __name__ == "__main__":
    main()