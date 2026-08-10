"""Per-task escalation state, persisted to logs/state/<task_id>.json.

File-backed (not in-memory) because Tier 4 is expected to run as discrete
process invocations across separate attempts, and the consecutive-failure
count must survive between them.
"""

import json
import time
from pathlib import Path

STATE_DIR = Path(__file__).resolve().parent.parent / "logs" / "state"


def _state_path(task_id: str) -> Path:
    return STATE_DIR / f"{task_id}.json"


def read_state(task_id: str) -> dict:
    path = _state_path(task_id)
    if not path.exists():
        return {"task_id": task_id, "consecutive_failures": 0, "last_stderr": "", "last_attempt_ts": None}
    with open(path) as f:
        return json.load(f)


def write_state(task_id: str, data: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    data["last_attempt_ts"] = time.time()
    with open(_state_path(task_id), "w") as f:
        json.dump(data, f, indent=2)


def record_failure(task_id: str, stderr: str) -> dict:
    state = read_state(task_id)
    state["consecutive_failures"] += 1
    state["last_stderr"] = stderr
    write_state(task_id, state)
    return state


def clear_state(task_id: str) -> None:
    path = _state_path(task_id)
    if path.exists():
        path.unlink()
