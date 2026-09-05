"""Minimal LLM client: DeepSeek (OpenAI-compatible HTTP API) + agy (local CLI).

Trimmed from the old pipeline's scripts/llm_client.py -- dropped Claude
CLI, Gemini, OpenRouter, Ollama, and the OpenRouter-specific content-filter
sanitizers (none apply to these two backends). Kept: the two working call
paths, agy's mandatory safety flags, and the argv-size guard (both were
real incidents in the old pipeline, see docstrings below).
"""

import json
import subprocess
from datetime import datetime, timezone
from typing import Tuple

import requests
import yaml
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "model_config.yaml"


def load_model_config() -> dict:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def is_deepseek_peak_hours(cfg: dict | None = None) -> bool:
    """DeepSeek peak billing window (UTC), configurable in model_config.yaml."""
    cfg = cfg or load_model_config()
    start, end = cfg["deepseek"]["peak_hours_utc"]
    hour = datetime.now(timezone.utc).hour
    return start <= hour < end


def execute_deepseek(prompt: str, system_prompt: str, api_key: str) -> Tuple[str, int, int]:
    """Call DeepSeek's OpenAI-compatible chat completions endpoint.

    Returns (response_text, input_tokens, output_tokens).
    """
    cfg = load_model_config()
    ds = cfg["deepseek"]
    url = f"{ds['endpoint']}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": ds["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
    }
    timeout = cfg["timeouts"]["http"]
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    choices = data.get("choices")
    if not choices:
        raise RuntimeError(f"DeepSeek API returned no choices: {json.dumps(data)[:500]}")
    response_text = choices[0]["message"]["content"]
    if response_text is None:
        raise RuntimeError(
            f"DeepSeek API returned null content (finish_reason="
            f"{choices[0].get('finish_reason')!r}): {json.dumps(data)[:500]}"
        )
    usage = data.get("usage", {})
    return response_text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)


# agy -p requires its prompt as an argv element, not stdin (confirmed live
# in the old pipeline: piping stdin makes agy exit status 2). A prompt too
# large for the OS argv limit crashes subprocess.run() with an uncaught
# OSError instead of a controlled error -- guard against it before calling.
_AGY_MAX_PROMPT_CHARS = 100_000


def execute_agy(prompt: str, system_prompt: str | None = None) -> str:
    """Run the local `agy` CLI with JSON output format.

    `--dangerously-skip-permissions --mode plan` are always set: without
    `--mode plan`, agy is a fully agentic CLI that can Read/Edit/Bash the
    live target repo directly instead of returning the edit as text for
    review -- a real incident in the old pipeline (two files written
    directly by agy mid-call, invisible to the caller). `--mode plan`
    suppresses the direct write while leaving the returned text unchanged,
    verified live in the old pipeline; it depends on the prompt itself
    explicitly instructing "reply with ... no other text" to override
    plan mode's default propose-and-ask framing -- keep that instruction
    in every prompt sent through this function.

    Returns the response text verbatim.
    """
    cfg = load_model_config()
    agy_cfg = cfg["agy"]
    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
    if len(full_prompt) > _AGY_MAX_PROMPT_CHARS:
        raise ValueError(
            f"agy prompt too large for argv: {len(full_prompt)} chars "
            f"(limit {_AGY_MAX_PROMPT_CHARS})"
        )
    cmd = ["agy", "-p", full_prompt]
    if agy_cfg.get("model"):
        cmd.extend(["--model", agy_cfg["model"]])
    if agy_cfg.get("effort"):
        cmd.extend(["--effort", agy_cfg["effort"]])
    cmd.extend(["--dangerously-skip-permissions", "--mode", "plan", "--output-format", "json"])
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=cfg["timeouts"]["agy_cli"]
    )
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"agy returned non-JSON stdout: {result.stdout[:500]!r}") from e
    if data.get("status") != "SUCCESS" or not isinstance(data.get("response"), str):
        raise RuntimeError(
            f"agy status={data.get('status')!r} stderr_tail={result.stderr[-200:]!r}"
        )
    return data["response"]
