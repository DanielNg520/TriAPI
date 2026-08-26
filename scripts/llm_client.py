"""LLM client with primary/fallback routing across providers."""

import os
import re
import subprocess
import json
import time
from typing import Tuple
from datetime import datetime, timezone

import requests

from scripts import budget_guard, config_loader, secrets_loader, tri_logging

log = tri_logging.get_logger("llm_client")

# OpenRouter's content filter can 403 a request whose prompt contains an
# email-like token, even a synthetic one in test fixture data (e.g.
# "attacker@evil.com") -- confirmed live 2026-08-24 blocking tier2_escalate.py
# on every candidate model in its fallback_chain, same root cause as the
# planner-specific fix in Phase 21 (2026-08-23). That fix only sanitized
# planner.py's own prompt; this generalizes it to every OpenRouter-routed
# call (tier_1_planner, tier_2_manager, tier_3_debugger all use provider
# "openrouter"), applied once here at the single dispatch point instead of
# per-tier.
_EMAIL_LIKE_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")

# Phone-like tokens (NANP-style) also trigger OpenRouter's content filter.
# Added 2026-08-25 after three live blocks: Tier 4 context from logs/cost_log.jsonl,
# tier_5_librarian's OpenRouter fallback leg routing PLAN.md, and this very plan's
# own breakdown call being blocked by an earlier draft's literal test fixture.
_PHONE_LIKE_RE = re.compile(
    r"\b(?:\+\d{1,3}\s*)?(?:\(\d{3}\)\s*|\d{3}[\s.\-])\d{3}[\s.\-]\d{4}\b"
)

# IPv4-shaped tokens (four dot-separated octets) also trigger the filter.
# Added 2026-08-25 per live OpenRouter dashboard evidence: 36 blocked requests
# today -- 18 PHONE, 12 EMAIL, 6 IP ADDRESS. Redacting the dotted-quad shape
# defeats the filter while keeping the transform visible in logs.
_IP_LIKE_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b"
)

# Timeout for CLI subprocesses (claude, agy) in seconds. Raised from 300 to
# 600 2026-08-25 after a real live crash: a `agy -p ... --effort high` call
# (gemini-3.1-pro via Antigravity CLI) hit exactly this wall mid-dispatch
# (run 20260825-154633-8927c3), and orchestrator.run_task() treats any Tier 3
# "error" status (this included) as a hard crash of the whole dispatch rather
# than a soft escalation to Tier 2 -- so a slow-but-working call was
# indistinguishable from a real failure. 600s gives high-effort calls real
# headroom without changing that error-vs-escalate design (a separate,
# bigger question, not addressed here).
_CLI_TIMEOUT = 600

# New constant for HTTP timeout, configurable via TRIAPI_HTTP_TIMEOUT
try:
    _HTTP_TIMEOUT = int(os.getenv('TRIAPI_HTTP_TIMEOUT', '600'))
except ValueError:
    _HTTP_TIMEOUT = 600


def _redact_phone_like(match: re.Match) -> str:
    """Replace separator characters in a phone-like match with a redaction marker."""
    s = match.group(0)
    return re.sub(r"[\s.\-()]", "-REDACTED-", s)


def _redact_ip_like(match: re.Match) -> str:
    """Replace dots in an IPv4-like match with a redaction marker."""
    s = match.group(0)
    return s.replace(".", "-REDACTED-")


def _sanitize_for_openrouter_content_filter(text: str) -> str:
    text = _EMAIL_LIKE_RE.sub(lambda m: m.group(0).replace("@", "(at)"), text)
    text = _PHONE_LIKE_RE.sub(_redact_phone_like, text)
    text = _IP_LIKE_RE.sub(_redact_ip_like, text)
    return text

# detect_email_like_content() is a flag-only scan: it identifies potential
# email-like tokens and mailto: occurrences so callers can log a [PRE-CHECK]
# warning and proceed. It does NOT transform or sanitize content. The actual
# enforcement transform on OpenRouter-bound content is
# _sanitize_for_openrouter_content_filter(), which remains the authoritative
# defense.
def detect_email_like_content(text: str) -> list[dict]:
    """Scan text for email-like tokens and mailto: occurrences.

    Returns a list of dicts, one per finding, with keys:
        line_no: 1-based line number where the match occurred.
        snippet: the matched text.
        pattern: the regex pattern that matched (email or mailto:).
    """
    email_pat = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
    mailto_pat = r"mailto:"
    findings = []
    for i, line in enumerate(text.splitlines(), start=1):
        for m in re.finditer(email_pat, line):
            findings.append({
                "line_no": i,
                "snippet": m.group(),
                "pattern": email_pat,
            })
        for m in re.finditer(mailto_pat, line):
            findings.append({
                "line_no": i,
                "snippet": m.group(),
                "pattern": mailto_pat,
            })
    return findings

def _is_deepseek_peak_hours() -> bool:
    """Check if current UTC time is within DeepSeek peak billing hours.

    DeepSeek peak billing is 01:00-04:00 UTC daily (LA local 2026-08-24T18:59:53.459255-07:00
    corresponds to UTC 2026-08-25T01:59:53.459255+00:00, which falls in this window).
    """
    now_utc = datetime.now(timezone.utc)
    hour = now_utc.hour
    return 1 <= hour < 4


def execute_llm(
    provider: str,
    endpoint: str,
    api_key: str,
    model: str,
    prompt: str,
    system_prompt: str,
    is_tier4: bool = False,
    effort: str | None = None,
) -> Tuple[str, str, int, int]:
    """Execute an LLM call with automatic fallback on failure.

    `effort` only applies to provider == "cli" (passed as `claude -p --effort
    <level>`); ignored otherwise.

    Note: Tier 3 (tier_3_debugger) uses DeepSeek; during peak billing hours
    (01:00-04:00 UTC) costs are elevated, so routing decisions may need to
    account for this window.

    Returns:
        (response_text, billing_type, input_tokens, output_tokens)
    """
    return _primary_request(provider, endpoint, api_key, model, prompt, system_prompt, effort)


def execute_agy(
    model: str | None,
    prompt: str,
    system_prompt: str | None = None,
    effort: str | None = None,
) -> Tuple[str, str, int, int]:
    """Public entry point for the `agy` CLI, for callers outside the
    provider-dispatch table in `_primary_request` (e.g. `librarian_escalate.py`'s
    `fallback_agy` leg). Thin wrapper around `_call_agy_cli` -- no duplicated
    subprocess logic.

    Returns:
        (response_text, billing_type, input_tokens, output_tokens)
    """
    return _call_agy_cli(prompt, model, effort, system_prompt)


def _primary_request(
    provider: str,
    endpoint: str,
    api_key: str,
    model: str,
    prompt: str,
    system_prompt: str,
    effort: str | None = None,
) -> Tuple[str, str, int, int]:
    """Dispatch to the appropriate primary backend."""
    if provider == "cli":
        return _call_claude_cli(prompt, system_prompt, model, effort)
    if provider == "agy":
        return _call_agy_cli(prompt, model, effort, system_prompt)
    if provider == "google":
        return _call_gemini_api(endpoint, api_key, model, prompt, system_prompt)
    # openrouter, deepseek, and any other OpenAI-compatible endpoint
    return _call_openai_api(endpoint, api_key, model, prompt, system_prompt, provider)


def _call_claude_cli(
    prompt: str, system_prompt: str, model: str | None = None, effort: str | None = None
) -> Tuple[str, str, int, int]:
    """Run the local `claude` CLI.

    `model` is passed as `--model` (accepts an alias like "sonnet" or a full
    model name like "claude-sonnet-5"); `effort` as `--effort` (low, medium,
    high, xhigh, max). Both are omitted from the invocation when falsy, in
    which case the CLI's own default applies.
    """
    cmd = ["claude", "-p", "--system-prompt", system_prompt]
    if model:
        cmd.extend(["--model", model])
    if effort:
        cmd.extend(["--effort", effort])
    result = subprocess.run(cmd, input=prompt, capture_output=True, text=True, check=True)
    response_text = result.stdout.strip()
    # CLI does not reliably report token counts; zero them out.
    return response_text, "cli", 0, 0


def _call_agy_cli(
    prompt: str, model: str | None, effort: str | None, system_prompt: str | None = None
) -> Tuple[str, str, int, int]:
    """Run the local `agy` CLI with JSON output format.

    `model` is passed as `--model`; `effort` as `--effort`. Both are omitted
    when falsy. The `--dangerously-skip-permissions` and
    `--output-format json` flags are always set.

    Success requires returncode 0, valid JSON stdout with
    `"status" == "SUCCESS"` and a string `"response"`; the response is
    returned verbatim (trailing newline preserved). Any other outcome
    raises subprocess.CalledProcessError (the same family
    `_call_claude_cli` raises) with a message embedding the status and
    stderr tail, so the existing per-tier fallthrough skips to the next
    tier gracefully.
    """
    if system_prompt:
        prompt = f"{system_prompt}\n\n{prompt}"
    cmd = ["agy", "-p", prompt]
    if model:
        cmd.extend(["--model", model])
    if effort:
        cmd.extend(["--effort", effort])
    cmd.extend(["--dangerously-skip-permissions", "--output-format", "json"])
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=_CLI_TIMEOUT
    )
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, cmd, result.stdout, result.stderr
        )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise subprocess.CalledProcessError(
            0, cmd, result.stdout, result.stderr
        ) from e
    if data.get("status") != "SUCCESS" or not isinstance(
        data.get("response"), str
    ):
        # Embed the status and stderr tail in the exception message so
        # the fallthrough handler can log them without crashing.
        detail = (
            f"agy status={data.get('status')!r} "
            f"stderr_tail={result.stderr[-200:]!r}"
        )
        raise subprocess.CalledProcessError(
            0, cmd, result.stdout, detail
        )
    return data["response"], "agy", 0, 0


def _call_gemini_api(
    endpoint: str, api_key: str, model: str, prompt: str, system_prompt: str
) -> Tuple[str, str, int, int]:
    """Call Google Gemini via REST API."""
    url = f"{endpoint}/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "system_instruction": {"parts": [{"text": system_prompt}]},
    }
    resp = requests.post(url, json=payload, timeout=_HTTP_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    response_text = data["candidates"][0]["content"]["parts"][0]["text"]
    usage = data.get("usageMetadata", {})
    input_tokens = usage.get("promptTokenCount", 0)
    output_tokens = usage.get("candidatesTokenCount", 0)
    return response_text, "google", input_tokens, output_tokens


def _call_openai_api(
    endpoint: str,
    api_key: str,
    model: str,
    prompt: str,
    system_prompt: str,
    provider: str,
) -> Tuple[str, str, int, int]:
    """Call any OpenAI-compatible chat completions endpoint."""
    if provider == "ollama":
        url = f"{endpoint}/v1/chat/completions"
    else:
        url = f"{endpoint}/chat/completions"
    if provider == "openrouter":
        prompt = _sanitize_for_openrouter_content_filter(prompt)
        system_prompt = _sanitize_for_openrouter_content_filter(system_prompt)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=_HTTP_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    # OpenRouter free models (e.g. `nvidia/nemotron-3-ultra-550b-a55b:free`) can return HTTP 200 with the error embedded in the body instead of a real error status, which previously crashed as a bare `KeyError: 'choices'` (real Tier 2 dispatch crash, 2026-08-24); attaching `.response.status_code` lets `tier2_escalate.py`'s existing `status in (429, 403)` fallback-chain check keep working for this case instead of aborting.
    choices = data.get("choices")
    if not choices:
        err_body = data.get("error")
        synthetic_resp = requests.Response()
        if isinstance(err_body, dict) and isinstance(err_body.get("code"), int):
            synthetic_resp.status_code = err_body["code"]
        else:
            synthetic_resp.status_code = resp.status_code
        synthetic_resp._content = resp.content
        if err_body is not None:
            message = f"{provider} API ({model}) returned no choices, embedded error: {err_body}"
        else:
            message = f"{provider} API ({model}) returned an unexpected response shape (no 'choices'): {json.dumps(data)[:500]}"
        raise requests.exceptions.HTTPError(message, response=synthetic_resp)
    response_text = choices[0]["message"]["content"]
    usage = data.get("usage", {})
    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)
    return response_text, provider, input_tokens, output_tokens


def _probe_with_retry(tier: str, call):
    """Retry a probe's ping/pong call up to 2 extra times (5s apart) before
    failing the whole pre-flight gate. Added 2026-08-24: a transient upstream
    blip (an OpenRouter 429, or a free model's own temporary 502/503) on a
    tier the current dispatch doesn't even use was aborting every dispatch
    outright with no tolerance at all -- this smooths over exactly that class
    of blip without weakening the gate for a genuinely broken/misconfigured
    tier (still fails hard after 3 total attempts)."""
    last_exc = None
    for attempt in range(3):
        try:
            call()
            return
        except Exception as e:
            last_exc = e
            if attempt < 2:
                log.warning("Probe for %s failed (attempt %d/3), retrying in 5s: %s", tier, attempt + 1, e)
                time.sleep(5)
    raise RuntimeError(f"Probe failed for {tier}: {last_exc}")


def probe_models():
    """Probe each tier's default model with a ping/pong exchange."""
    config = config_loader.load_tiers()
    secrets = secrets_loader.load_secrets()
    # tier_1_manager is the Claude CLI tier actually used for repair dispatch
    # (tier1_escalate.py); tier_1_planner is the separate OpenRouter tier used
    # only for plan authoring (planner.py). Both must be probed -- validating
    # only tier_1_planner would let a real Claude-CLI outage/misconfig sail
    # through this pre-flight check undetected.
    # Tier 3 (tier_3_debugger) uses DeepSeek; check peak-hours status for diagnostics.
    deepseek_peak = _is_deepseek_peak_hours()
    log.info("Tier 3 DeepSeek peak-hours status (01:00-04:00 UTC): %s", "ACTIVE" if deepseek_peak else "inactive")
    # Probe tier_5_librarian's primary model (same mechanism as tier_4_worker)
    tier = 'tier_5_librarian'
    tier_config = config[tier]
    provider = tier_config['provider']
    # tier_5_librarian has no static 'endpoint' key -- its Ollama endpoint
    # resolves from the ollama_host secret at runtime (2026-08-24 fix:
    # tier_config.get('endpoint') was always None here, producing
    # "Invalid URL 'None/v1/chat/completions'" and blocking every dispatch).
    endpoint = tier_config.get('endpoint') or (secrets.get('ollama_host') if provider == 'ollama' else None)
    model_name = tier_config['models']['primary']
    api_key_secret = tier_config.get('api_key_secret')
    _probe_with_retry(tier, lambda: execute_llm(
        provider,
        endpoint,
        secrets.get(api_key_secret, '') if api_key_secret else '',
        model_name,
        'ping',
        'reply pong',
        is_tier4=False,
        effort=tier_config.get('effort'),
    ))
    for tier in ['tier_4_worker', 'tier_3_debugger', 'tier_2_manager', 'tier_1_planner', 'tier_1_manager']:
        tier_config = config[tier]
        provider = tier_config['provider']
        endpoint = tier_config.get('endpoint')
        default_model = tier_config['default_model']
        model_name = tier_config['models'][default_model]
        api_key_secret = tier_config.get('api_key_secret')
        _probe_with_retry(tier, lambda tier_config=tier_config, provider=provider, endpoint=endpoint, model_name=model_name, api_key_secret=api_key_secret: execute_llm(
            provider,
            endpoint,
            secrets.get(api_key_secret, '') if api_key_secret else '',
            model_name,
            'ping',
            'reply pong',
            is_tier4=(tier == 'tier_4_worker'),
            effort=tier_config.get('effort'),
        ))
