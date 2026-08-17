#!/usr/bin/env python3
import sys
import time
from pathlib import Path

import yaml
import requests

# Import the function that unloads all other Ollama models except one.
# This module is expected to be part of the repository under the name
# `resource_guard.py`. Adjust the import path if necessary.
try:
    from resource_guard import unload_other_ollama_models
except Exception as e:  # pragma: no cover
    print(f"FAILED: could not import unload_other_ollama_models ({e})")
    sys.exit(1)


def load_config() -> dict:
    """Load the YAML configuration file used by the system."""
    cfg_path = Path(__file__).resolve().parent.parent / "config" / "tiers.yaml"
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:  # pragma: no cover
        print(f"FAILED: could not read config file {cfg_path} ({e})")
        sys.exit(1)


def get_endpoint(config: dict) -> str:
    """Return the Ollama endpoint for tier_4_worker."""
    try:
        return config["tier_4_worker"]["endpoint"]
    except KeyError as e:  # pragma: no cover
        print(f"FAILED: missing key in config {e}")
        sys.exit(1)


def main() -> None:
    cfg = load_config()
    endpoint = get_endpoint(cfg)

    # Step 1: Unload all other models, keeping the fallback.
    try:
        unload_other_ollama_models(ollama_host=endpoint, keep_model="gpt-oss:20b")
    except Exception as e:  # pragma: no cover
        print(f"FAILED: error unloading models ({e})")
        sys.exit(1)

    # Step 2: Make the generate request to the draft model.
    url = f"{endpoint.rstrip('/')}/api/generate"
    payload = {
        "model": "qwen3-coder:30b-cc",
        "prompt": "Hello world",  # minimal prompt
        "stream": False,
    }

    start = time.perf_counter()
    try:
        resp = requests.post(url, json=payload, timeout=300)
        elapsed = time.perf_counter() - start
    except Exception as e:  # pragma: no cover
        print(f"FAILED: request error ({e})")
        sys.exit(1)

    if not resp.ok:
        reason = f"HTTP {resp.status_code}"
        try:
            reason += f": {resp.text.strip()[:120]}"
        except Exception:
            pass
        print(f"FAILED: {reason}")
        sys.exit(1)

    # Optionally inspect response content for errors.
    body = resp.json()
    if "error" in body:
        print(f"FAILED: API error ({body['error']})")
        sys.exit(1)

    # Success
    print(f"SUCCESS in {elapsed:.2f}s")


if __name__ == "__main__":
    main()
