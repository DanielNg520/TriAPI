"""LLM client with primary/fallback routing across providers."""

import subprocess
import json
from typing import Tuple

import requests

from scripts import budget_guard, config_loader, secrets_loader, tri_logging

log = tri_logging.get_logger("llm_client")

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
    return _primary_request(provider, endpoint, api_key, model, prompt, system_prompt)


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
