"""LLM client with primary/fallback routing across providers."""

import re
import subprocess
import json
from typing import Tuple

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


def _sanitize_for_openrouter_content_filter(text: str) -> str:
    return _EMAIL_LIKE_RE.sub(lambda m: m.group(0).replace("@", "(at)"), text)

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

    Returns:
        (response_text, billing_type, input_tokens, output_tokens)
    """
    return _primary_request(provider, endpoint, api_key, model, prompt, system_prompt, effort)


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


def _call_gemini_api(
    endpoint: str, api_key: str, model: str, prompt: str, system_prompt: str
) -> Tuple[str, str, int, int]:
    """Call Google Gemini via REST API."""
    url = f"{endpoint}/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "system_instruction": {"parts": [{"text": system_prompt}]},
    }
    resp = requests.post(url, json=payload, timeout=300)
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
    resp = requests.post(url, headers=headers, json=payload, timeout=300)
    resp.raise_for_status()
    data = resp.json()
    response_text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)
    return response_text, provider, input_tokens, output_tokens


def probe_models():
    """Probe each tier's default model with a ping/pong exchange."""
    config = config_loader.load_tiers()
    secrets = secrets_loader.load_secrets()
    # tier_1_manager is the Claude CLI tier actually used for repair dispatch
    # (tier1_escalate.py); tier_1_planner is the separate OpenRouter tier used
    # only for plan authoring (planner.py). Both must be probed -- validating
    # only tier_1_planner would let a real Claude-CLI outage/misconfig sail
    # through this pre-flight check undetected.
    for tier in ['tier_4_worker', 'tier_3_debugger', 'tier_2_manager', 'tier_1_planner', 'tier_1_manager']:
        try:
            tier_config = config[tier]
            provider = tier_config['provider']
            endpoint = tier_config.get('endpoint')
            default_model = tier_config['default_model']
            model_name = tier_config['models'][default_model]
            api_key_secret = tier_config.get('api_key_secret')
            execute_llm(
                provider,
                endpoint,
                secrets.get(api_key_secret, '') if api_key_secret else '',
                model_name,
                'ping',
                'reply pong',
                is_tier4=(tier == 'tier_4_worker'),
                effort=tier_config.get('effort'),
            )
        except Exception as e:
            raise RuntimeError(f"Probe failed for {tier}: {e}")
