"""Cheap regression detection for dispatcher.py.

Cost rationale: hashing every earlier successfully-completed item's target
file is O(n) milliseconds-cheap per dispatch() call -- sha256 over a small
source file, no subprocess, no build_cmd execution. Only a file whose hash
has actually drifted since it last succeeded gets its (possibly expensive,
e.g. a full ./run_tests.sh) build_cmd re-run. A future reader must not
"fix" this into an unconditional full-rebuild sweep after every item --
that reintroduces the O(n^2)/full-test-suite-every-time cost this design
was built specifically to avoid.
"""

import hashlib
from pathlib import Path


def hash_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


def check_regressions(state: dict, project_dir: str) -> list[dict]:
    """Pure detection only -- never runs build_cmd itself, that is the
    caller's job so the caller can decide whether the cost of re-running
    is warranted. Returns entries whose on-disk hash no longer matches
    the hash recorded when they last succeeded."""
    drifted = []
    for idx, entry in enumerate(state.get("results", [])):
        if entry.get("status") != "success":
            continue
        target = entry.get("target")
        content_hash = entry.get("content_hash")
        if not target or not content_hash:
            continue
        current_hash = hash_file(Path(project_dir) / target)
        if current_hash != content_hash:
            drifted.append({"index": idx, "entry": entry, "current_hash": current_hash})
    return drifted
