"""Pauses/resumes systemd --user services that compete with TriAPI's Tier 4
(local Ollama) for CPU/RAM/GPU, so a dispatch run gets full priority on this
machine's shared resources. Service list is config/resource_guard.yaml, not
hardcoded here -- machine-specific, edited independently of code.

Self-healing by design, not just a try/finally in the caller: a plain
try/finally does NOT run on SIGTERM (only on exceptions and SIGINT), so a
`kill <pid>` on a stuck dispatch -- which has actually happened once
already in this project's real usage -- would otherwise leave services
paused forever. Two layers of defense on top of the caller's own
try/finally:
  1. A signal/atexit safety net installed the moment anything gets paused,
     so SIGTERM/SIGINT/normal-exit all resume services from *this*
     process, whichever happens first.
  2. A lock file (logs/resource_guard_lock.json) recording what got paused
     and by which pid. If that pid is hard-killed (SIGKILL, OOM, power
     loss) before even the signal handler runs, the lock survives; the
     very next call to pause_services() (i.e. the next `triapi dispatch`)
     notices the owning pid is dead and resumes the orphaned services
     before doing anything else. No separate watchdog process needed.
"""

import atexit
import json
import os
import signal
import subprocess
import sys
import time
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.tri_logging import get_logger

log = get_logger("resource_guard")

LOCK_PATH = Path(__file__).resolve().parent.parent / "logs" / "resource_guard_lock.json"

_state = {"resumed": False}


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, just not ours to signal -- treat as alive
    except (TypeError, ValueError):
        return False
    return True


def _reap_stale_lock() -> None:
    if not LOCK_PATH.exists():
        return
    try:
        lock = json.loads(LOCK_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        LOCK_PATH.unlink(missing_ok=True)
        return
    if _pid_alive(lock.get("pid", -1)):
        return  # a dispatch is still legitimately holding the guard
    log.warning(
        "Found orphaned resource-guard lock from dead pid %s -- resuming %s and clearing it",
        lock.get("pid"), lock.get("paused"),
    )
    _do_resume(lock.get("paused") or [])
    LOCK_PATH.unlink(missing_ok=True)


def _do_resume(paused: list[str]) -> None:
    for service in paused:
        log.info("Resuming %s", service)
        subprocess.run(["systemctl", "--user", "start", service], stdin=subprocess.DEVNULL)


def _install_safety_net(paused: list[str]) -> None:
    def _handler(signum=None, frame=None):
        resume_services(paused)
        if signum is not None:
            sys.exit(128 + signum)

    atexit.register(_handler)
    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)


def snapshot_ollama_state(ollama_host: str, service: str = "ollama.service") -> dict:
    """
    Snapshot the Ollama service state once per dispatch run, before Tier 4
    work, so the service can be restored to exactly this state on exit.

    Parameters
    ----------
    ollama_host : str
        Base URL of the Ollama server (e.g., "http://localhost:11434").
    service : str, optional
        The systemd service name to check and control. Defaults to "ollama.service".

    Returns
    -------
    dict
        A dictionary containing:
        - 'was_active': bool indicating if the Ollama service was active at snapshot.
        - 'resident_models': list of names of currently resident/warm models.
        - 'service': str, the name of the service checked and possibly started.
    """
    active_result = subprocess.run(
        ["systemctl", "--user", "is-active", "--quiet", service],
        stdin=subprocess.DEVNULL,
    )
    was_active = active_result.returncode == 0
    resident_models = []

    if was_active:
        try:
            resp = requests.get(f"{ollama_host}/api/ps")
            resp.raise_for_status()
            data = resp.json()
            resident_models = [model["name"] for model in data.get("models", [])]
        except requests.RequestException as exc:
            log.warning("Could not retrieve Ollama model list: %s", exc)

    else:
        result = subprocess.run(["systemctl", "--user", "start", service], stdin=subprocess.DEVNULL)
        if result.returncode != 0:
            log.warning(
                "Could not start %s before dispatch (exit %s); continuing with no resident models",
                service,
                result.returncode,
            )

    return {"was_active": was_active, "resident_models": resident_models, "service": service}


def restore_ollama_state(snapshot: dict, ollama_host: str) -> None:
    """
    Restore the Ollama service to its pre-dispatch snapshot state.

    Parameters
    ----------
    snapshot : dict
        Snapshot taken by snapshot_ollama_state(). May be None, in which
        case this function is a no-op.
    ollama_host : str
        Base URL of the Ollama server (e.g., "http://localhost:11434").

    Returns
    -------
    None
    """
    if snapshot is None:
        log.debug("No Ollama snapshot to restore; skipping")
        return

    for name in snapshot.get("resident_models") or []:
        try:
            log.info("Reloading %s to restore warm Ollama state", name)
            post_resp = requests.post(
                f"{ollama_host}/api/generate",
                json={"model": name},
            )
            post_resp.raise_for_status()
        except requests.RequestException as exc:
            log.warning("Failed to reload model %s: %s", name, exc)

    if not snapshot.get("was_active"):
        service = snapshot.get("service") or "ollama.service"
        log.info("Stopping %s back to its pre-dispatch state", service)
        try:
            subprocess.run(
                ["systemctl", "--user", "stop", service],
                stdin=subprocess.DEVNULL,
            )
        except OSError as exc:
            log.warning("Failed to stop %s: %s", service, exc)


def pause_services(services: list[str]) -> list[str]:
    """Stops each currently-active service in `services`. Returns exactly
    the subset that was actually running -- a service already stopped for
    an unrelated reason is left alone in both directions, so this never
    resurrects something the user (or another process) deliberately turned
    off before the dispatch run started."""
    _reap_stale_lock()

    paused = []
    for service in services:
        active_result = subprocess.run(
            ["systemctl", "--user", "is-active", "--quiet", service],
            stdin=subprocess.DEVNULL,
        )
        if active_result.returncode == 0:
            log.info("Pausing %s for the duration of this dispatch run", service)
            subprocess.run(["systemctl", "--user", "stop", service], stdin=subprocess.DEVNULL)
            paused.append(service)
        else:
            log.info("%s already inactive, leaving as-is", service)

    if paused:
        _state["resumed"] = False
        LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOCK_PATH.write_text(json.dumps({"pid": os.getpid(), "paused": paused, "started_at": time.time()}))
        _install_safety_net(paused)

    return paused


def resume_services(paused: list[str]) -> None:
    """Idempotent -- safe to call from the caller's own try/finally AND
    from the signal/atexit safety net without double-starting anything."""
    if _state["resumed"]:
        return
    _do_resume(paused)
    _state["resumed"] = True
    LOCK_PATH.unlink(missing_ok=True)

def unload_other_ollama_models(keep_model: str, ollama_host: str) -> list[str]:
    """
    Unload all Ollama models except keep_model from the given host.

    Parameters
    ----------
    keep_model : str
        The model name to retain; all others will be unloaded.
    ollama_host : str
        Base URL of the Ollama server (e.g., "http://localhost:11434").

    Returns
    -------
    list[str]
        List of names of models successfully unloaded.
    """
    unloaded = []
    try:
        resp = requests.get(f"{ollama_host}/api/ps")
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        log.warning("Could not retrieve Ollama model list: %s", exc)
        return []

    for entry in data.get("models", []):
        name = entry.get("name")
        if not name or name == keep_model:
            continue
        try:
            log.info("Unloading %s to free resources for TriAPI dispatch", name)
            post_resp = requests.post(
                f"{ollama_host}/api/generate",
                json={"model": name, "keep_alive": 0},
            )
            post_resp.raise_for_status()
            unloaded.append(name)
        except requests.RequestException as exc:
            log.warning("Failed to unload model %s: %s", name, exc)

    return unloaded
