"""Pauses/resumes systemd --user services that compete with TriAPI's Tier 4
(local Ollama) for CPU/RAM/GPU, so a dispatch run gets full priority on this
machine's shared resources. Service list is config/resource_guard.yaml, not
hardcoded here -- machine-specific, edited independently of code.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.tri_logging import get_logger

log = get_logger("resource_guard")


def _is_active(service: str) -> bool:
    result = subprocess.run(
        ["systemctl", "--user", "is-active", service],
        capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )
    return result.stdout.strip() == "active"


def pause_services(services: list[str]) -> list[str]:
    """Stops each currently-active service in `services`. Returns exactly
    the subset that was actually running -- a service already stopped for
    an unrelated reason is left alone in both directions, so this never
    resurrects something the user (or another process) deliberately turned
    off before the dispatch run started."""
    paused = []
    for service in services:
        if _is_active(service):
            log.info("Pausing %s for the duration of this dispatch run", service)
            subprocess.run(["systemctl", "--user", "stop", service], stdin=subprocess.DEVNULL)
            paused.append(service)
        else:
            log.info("%s already inactive, leaving as-is", service)
    return paused


def resume_services(paused: list[str]) -> None:
    for service in paused:
        log.info("Resuming %s", service)
        subprocess.run(["systemctl", "--user", "start", service], stdin=subprocess.DEVNULL)
