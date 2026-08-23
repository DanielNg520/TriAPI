"""LLM client with primary/fallback routing across providers."""

import subprocess
import json
from typing import Tuple

import requests

from scripts import budget_guard, config_loader, secrets_loader, tri_logging


def execute_llm(
    provider: str,
    endpoint: str,
    api_key: str,
    model: str,
    prompt: str,
    system_prompt: str,
    is_tier4: bool = False,
) -> Tuple[str, str, int, int]:
    """Execute an LLM call with automatic fallback on failure.

    Returns:
        (response_text, billing_type, input_tokens, output_tokens)
    """
    try:
        return _primary_request(provider, endpoint, api_key, model, prompt, system_prompt)
    except Exception as exc:
        tri_logging.warning(
            f"Primary provider '{provider}' failed: {exc}. Falling back..."
        )
        return _fallback_request(provider, prompt, system_prompt, is_tier4)


def _primary_request(
    provider: str,
    endpoint: str,
    api_key: str,
    model: str,
    prompt: str,
    system_prompt: str,
) -> Tuple[str, str, int, int]:
    """Dispatch to the appropriate primary backend."""
    if provider == "cli":
        return _call_claude_cli(prompt, system_prompt)
    if provider == "google":
        return _call_gemini_api(endpoint, api_key, model, prompt, system_prompt)
    # openrouter, deepseek, and any other OpenAI-compatible endpoint
    return _call_openai_api(endpoint, api_key, model, prompt, system_prompt, provider)


def _call_claude_cli(prompt: str, system_prompt: str) -> Tuple[str, str, int, int]:
    """Run the local `claude` CLI."""
    cmd = ["claude", "-p", prompt, "--system", system_prompt]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
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
    resp = requests.post(url, json=payload, timeout=120)
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
    url = f"{endpoint}/chat/completions"
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
    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    response_text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)
    return response_text, provider, input_tokens, output_tokens


def _fallback_request(
    provider: str, prompt: str, system_prompt: str, is_tier4: bool
) -> Tuple[str, str, int, int]:
    """Route to the appropriate fallback chain."""
    if is_tier4:
        return _fallback_ollama(prompt, system_prompt)
    return _fallback_deepseek_then_gemini(prompt, system_prompt)


def _fallback_ollama(prompt: str, system_prompt: str) -> Tuple[str, str, int, int]:
    """Call local Ollama API (tier-4 fallback)."""
    config = config_loader.load_config()
    tier4_cfg = config.get("tier_4_worker", {})
    model_name = tier4_cfg.get("models", {}).get(
        "default", "dots-studio/dots-3-note-preview:free"
    )
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model_name,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
    }
    resp = requests.post(url, json=payload, timeout=300)
    resp.raise_for_status()
    data = resp.json()
    response_text = data.get("response", "")
    input_tokens = data.get("prompt_eval_count", 0)
    output_tokens = data.get("eval_count", 0)
    return response_text, "ollama_fallback", input_tokens, output_tokens


def _fallback_deepseek_then_gemini(
    prompt: str, system_prompt: str
) -> Tuple[str, str, int, int]:
    """Try DeepSeek (if allowed), then fall back to Gemini."""
    if budget_guard.check_tier3_peak_hours_ok():
        try:
            return _call_deepseek_fallback(prompt, system_prompt)
        except Exception as exc:
            tri_logging.warning(
                f"DeepSeek fallback failed: {exc}. Trying Gemini fallback..."
            )
    else:
        tri_logging.warning(
            "Tier-3 peak hours active; skipping DeepSeek, going straight to Gemini."
        )
    return _call_gemini_fallback(prompt, system_prompt)


def _call_deepseek_fallback(
    prompt: str, system_prompt: str
) -> Tuple[str, str, int, int]:
    """Call DeepSeek API using tier_3_debugger config."""
    config = config_loader.load_config()
    tier3_cfg = config.get("tier_3_debugger", {})
    endpoint = tier3_cfg.get("endpoint", "https://api.deepseek.com")
    # Resolve model: default_model is a key (e.g. 'flash') -> models.flash
    default_key = tier3_cfg.get("default_model", "flash")
    model = tier3_cfg.get("models", {}).get(default_key, "deepseek-v4-flash")
    api_key = secrets_loader.get_secret("deepseek_api_key")

    return _call_openai_api(
        endpoint, api_key, model, prompt, system_prompt, "deepseek"
    )


def _call_gemini_fallback(
    prompt: str, system_prompt: str
) -> Tuple[str, str, int, int]:
    """Call Gemini API using tier_2_manager config."""
    config = config_loader.load_config()
    tier2_cfg = config.get("tier_2_manager", {})
    endpoint = tier2_cfg.get("endpoint", "https://generativelanguage.googleapis.com")
    # Fallback model is the flash model from config
    model = tier2_cfg.get("models", {}).get(
        "flash", "gemini-3.5-flash"
    )
    api_key = secrets_loader.get_secret("google_ai_studio_api_key")

    return _call_gemini_api(endpoint, api_key, model, prompt, system_prompt)
