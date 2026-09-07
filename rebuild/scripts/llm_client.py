"""Minimal LLM client: DeepSeek (OpenAI-compatible HTTP API) + agy (local CLI),
plus a narrow OpenRouter fallback for DeepSeek's peak-billing window.

Trimmed from the old pipeline's scripts/llm_client.py -- dropped Claude
CLI, Gemini, and Ollama. OpenRouter itself is back, but only as
call_deepseek.py's peak-hours fallback (see AGENTS.md) -- not a general
peer to DeepSeek/agy. Its content-filter sanitizer (still needed: see
scripts/openrouter_sanitizer.py) lives in its own module. Kept: the two
original working call paths, agy's mandatory safety flags, and the
argv-size guard (both were real incidents in the old pipeline, see
docstrings below).
"""

import json
import re
import subprocess
from datetime import datetime, timezone
from typing import Tuple
from zoneinfo import ZoneInfo

import requests
import yaml
from pathlib import Path

from scripts.openrouter_sanitizer import sanitize_for_openrouter_content_filter

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "model_config.yaml"
_RULES_PATH = Path(__file__).resolve().parent.parent / "RULES.md"
_BEIJING_TZ = ZoneInfo("Asia/Shanghai")


def load_model_config() -> dict:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_rules() -> str:
    """Hard rules shared by every DeepSeek/agy call -- see RULES.md."""
    return _RULES_PATH.read_text(encoding="utf-8")


def is_deepseek_peak_hours(cfg: dict | None = None) -> bool:
    """DeepSeek peak billing window (UTC), configurable in model_config.yaml; Beijing weekends are off-peak."""
    cfg = cfg or load_model_config()
    now = datetime.now(timezone.utc)
    if now.astimezone(_BEIJING_TZ).weekday() >= 5:
        return False
    start, end = cfg["deepseek"]["peak_hours_utc"]
    return start <= now.hour < end


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


def execute_openrouter(prompt: str, system_prompt: str, api_key: str) -> Tuple[str, int, int]:
    """Call OpenRouter's OpenAI-compatible chat completions endpoint with the
    configured fallback model (config/model_config.yaml: openrouter.fallback_model).

    Peak-hours fallback for execute_deepseek only -- see call_deepseek.py.
    Returns (response_text, input_tokens, output_tokens).
    """
    cfg = load_model_config()
    orc = cfg["openrouter"]
    url = f"{orc['endpoint']}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": orc["fallback_model"],
        "messages": [
            {"role": "system", "content": sanitize_for_openrouter_content_filter(system_prompt)},
            {"role": "user", "content": sanitize_for_openrouter_content_filter(prompt)},
        ],
    }
    timeout = cfg["timeouts"]["http"]
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    choices = data.get("choices")
    if not choices:
        raise RuntimeError(f"OpenRouter API returned no choices: {json.dumps(data)[:500]}")
    response_text = choices[0]["message"]["content"]
    if response_text is None:
        raise RuntimeError(
            f"OpenRouter API returned null content (finish_reason="
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


def extract_code_block(
    response: str,
    language: str = "python",
) -> str:
    language_pattern = rf"```{re.escape(language)}\n(.*?)\n```"
    match = re.search(language_pattern, response, re.DOTALL)
    if match:
        return match.group(1)

    bare_pattern = r"```\n(.*?)\n```"
    match = re.search(bare_pattern, response, re.DOTALL)
    if match:
        return match.group(1)

    raise ValueError("no fenced code block found")
