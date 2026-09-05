"""Loads secrets from the sops/age-encrypted config/secrets.enc.yaml.

Trimmed from the old pipeline's scripts/secrets_loader.py: only
`deepseek_api_key` is required now (agy is a local CLI, no key needed).
Points at the main TriAPI repo's existing secrets file rather than
duplicating one -- this folder is a trim of the same repo, not a
separate credential store.

Requires the `sops` binary on PATH and a usable age key (SOPS_AGE_KEY_FILE
or the default ~/.config/sops/age/keys.txt) able to decrypt the recipient
in .sops.yaml. Never prints or logs decrypted values.
"""

import json
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # rebuild/scripts -> rebuild -> TriAPI
SECRETS_PATH = _REPO_ROOT / "config" / "secrets.enc.yaml"
SOPS_CONFIG_PATH = _REPO_ROOT / ".sops.yaml"


def load_secrets() -> dict:
    if not SECRETS_PATH.exists():
        raise FileNotFoundError(
            f"{SECRETS_PATH} not found. Copy config/secrets.example.yaml, fill it in, "
            f"then run: sops -e -i <path> (or `sops config/secrets.enc.yaml` to edit in place)."
        )
    try:
        result = subprocess.run(
            ["sops", "--config", str(SOPS_CONFIG_PATH), "-d", "--output-type", "json", str(SECRETS_PATH)],
            capture_output=True,
            text=True,
            check=True,
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError as e:
        raise RuntimeError("`sops` binary not found on PATH.") from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"sops failed to decrypt {SECRETS_PATH}: {e.stderr.strip()}") from e

    secrets = json.loads(result.stdout)
    if "deepseek_api_key" not in secrets:
        raise ValueError(f"{SECRETS_PATH} is missing required key 'deepseek_api_key'")
    return secrets
