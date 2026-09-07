"""Minimal LLM client: DeepSeek (OpenAI-compatible HTTP API) + agy (local CLI),
plus a narrow OpenRouter fallback for DeepSeek's peak-billing window.

Trimmed from the old pipeline's scripts/llm_client.py -- dropped Claude
CLI, Gemini, and Ollama. OpenRouter itself is back, but only as
call_deepseek.py's peak-hours fallback (see AGENTS.md) -- not a general
peer to DeepSeek/agy -- and its content-filter sanitizers came back with
it (still needed: OpenRouter's filter 403s on email/phone/IP-shaped
tokens, a real live problem in the old pipeline, see
_sanitize_for_openrouter_content_filter below). Kept: the two original
working call paths, agy's mandatory safety flags, and the argv-size
guard (both were real incidents in the old pipeline, see docstrings
below).
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

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "model_config.yaml"
_RULES_PATH = Path(__file__).resolve().parent.parent / "RULES.md"
_BEIJING_TZ = ZoneInfo("Asia/Shanghai")

# OpenRouter's content filter can 403 a request whose prompt contains an
# email/phone/IP-shaped token, even a synthetic one in test/task fixture
# data -- ported from the old pipeline's scripts/llm_client.py (real live
# blocks there, 2026-08-24/25: 36 blocked requests in one day -- 18 PHONE,
# 12 EMAIL, 6 IP ADDRESS). Applied to every execute_openrouter() call below,
# the fallback's single call site.
_EMAIL_LIKE_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")

# NANP-style phone shape (3-3-4 digit groups with separators). Anchored to
# that exact grouping so it does NOT match run-id timestamps ("20260824-
# 153000-a1b2c3"), hex hashes, or version strings ("1.2.3") -- see
# rebuild/tests/test_llm_client.py's false-positive cases, ported from the
# old pipeline's tests/test_llm_client_sanitize.py.
_PHONE_LIKE_RE = re.compile(
    r"\b(?:\+\d{1,3}\s*)?(?:\(\d{3}\)\s*|\d{3}[\s.\-])\d{3}[\s.\-]\d{4}\b"
)

# IPv4-shaped tokens (four dot-separated octets).
_IP_LIKE_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b"
)


def _redact_phone_like(match: re.Match) -> str:
    return re.sub(r"[\s.\-()]", "-REDACTED-", match.group(0))


def _redact_ip_like(match: re.Match) -> str:
    return match.group(0).replace(".", "-REDACTED-")


def _sanitize_for_openrouter_content_filter(text: str) -> str:
    text = _EMAIL_LIKE_RE.sub(lambda m: m.group(0).replace("@", "(at)"), text)
    text = _PHONE_LIKE_RE.sub(_redact_phone_like, text)
    text = _IP_LIKE_RE.sub(_redact_ip_like, text)
    return text


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
            {"role": "system", "content": _sanitize_for_openrouter_content_filter(system_prompt)},
            {"role": "user", "content": _sanitize_for_openrouter_content_filter(prompt)},
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
