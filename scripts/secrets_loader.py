"""Loads secrets from the sops/age-encrypted config/secrets.enc.yaml.

Requires the `sops` binary on PATH and a usable age key (SOPS_AGE_KEY_FILE
or the default ~/.config/sops/age/keys.txt) able to decrypt the recipient
in .sops.yaml. Never prints or logs decrypted values.
"""

import json
import subprocess
from pathlib import Path

SECRETS_PATH = Path(__file__).resolve().parent.parent / "config" / "secrets.enc.yaml"


def load_secrets() -> dict:
    if not SECRETS_PATH.exists():
        raise FileNotFoundError(
            f"{SECRETS_PATH} not found. Copy config/secrets.example.yaml, fill it in, "
            f"then run: sops -e -i <path> (or `sops config/secrets.enc.yaml` to edit in place)."
        )
    try:
        result = subprocess.run(
            ["sops", "-d", "--output-type", "json", str(SECRETS_PATH)],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as e:
        raise RuntimeError("`sops` binary not found on PATH.") from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"sops failed to decrypt {SECRETS_PATH}: {e.stderr.strip()}") from e

    secrets = json.loads(result.stdout)
    required = ["deepseek_api_key", "ollama_host", "google_ai_studio_api_key"]
    missing = [k for k in required if k not in secrets]
    if missing:
        raise ValueError(f"{SECRETS_PATH} is missing required keys: {missing}")
    return secrets
