#!/usr/bin/env python3
"""One-off backlog-grooming script: discard self-fix entries that are either
test-development debris (see self_fix.BUGS_DIR isolation in tests/test_branch_features.py's
SelfFixTests -- the current suite writes zero real files there, confirming the
bare-tempfile-named entries predate that isolation and are dead debris, not a
live leak) or match an exception signature already root-caused and fixed by a
landed commit. Never guesses on an unfamiliar signature -- flags and skips it
instead of discarding.

Run manually: `python3 scripts/clear_stale_self_fixes.py`. Re-run is safe
(idempotent): a discarded entry simply won't be listed again.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

TRIAPI_ROOT = Path(__file__).resolve().parent.parent
BUGS_DIR = TRIAPI_ROOT / "logs" / "triapi_bugs"
RUNS_DIR = TRIAPI_ROOT / "logs" / "runs"

# Bare tempfile.mkstemp()-style stems (no timestamp prefix) predate the
# BUGS_DIR test-isolation fixture and are 2026-08-15 test-development debris.
_TMP_DEBRIS_RE = re.compile(r"^tmp[A-Za-z0-9_]+$")

# Substrings of exception_type/exception_message (bug reports) or prompt
# (drafted runs) that identify an error signature already root-caused and
# fixed by a landed commit -- see docs/carryover/ for each fix's history.
_KNOWN_FIXED_SNIPPETS = [
    "429 Client Error",
    "404 Client Error",
    "403 Client Error",
    "gemini-2.5-flash-lite",
    "nvidia/nemotron",
    "'choices'",
    "KeyError: 'pricing'",
    "KeyError: 'phases'",
    "KeyError: 'item'",
    "KeyError: 'default'",
    "KeyError: 'pass'",
    "gemini-3.7-flash",
    "gemini-3.1-pro",
    "returned choices with null message content",
    "IsADirectoryError",
    "ohmyllama",
]


def _list_output() -> str:
    result = subprocess.run(
        [sys.executable, "scripts/triapi.py", "self-fix", "list"],
        cwd=TRIAPI_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _parse_list(output: str) -> tuple[list[str], list[str]]:
    bug_ids: list[str] = []
    run_ids: list[str] = []
    section = None
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("Unqueued bug reports:"):
            section = "bugs"
            continue
        if stripped.startswith("Drafted self-fix runs"):
            section = "runs"
            continue
        if not stripped or stripped == "(none)":
            continue
        if section == "bugs":
            bug_ids.append(stripped)
        elif section == "runs":
            run_ids.append(stripped.split()[0])
    return bug_ids, run_ids


def _bug_report_text(bug_id: str) -> str | None:
    path = BUGS_DIR / f"{bug_id}.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return f"{data.get('exception_type', '')}: {data.get('exception_message', '')}"


def _run_prompt_text(run_id: str) -> str | None:
    path = RUNS_DIR / f"{run_id}.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("prompt", "")


def _is_stale(bug_id: str, text: str | None) -> bool:
    if _TMP_DEBRIS_RE.match(bug_id):
        return True
    if text is None:
        return False
    return any(snippet in text for snippet in _KNOWN_FIXED_SNIPPETS)


def _discard(bug_id: str) -> None:
    subprocess.run(
        [sys.executable, "scripts/triapi.py", "self-fix", "discard", bug_id],
        cwd=TRIAPI_ROOT,
        check=True,
    )


def main() -> None:
    bug_ids, run_ids = _parse_list(_list_output())

    discarded = []
    flagged = []

    for bug_id in bug_ids:
        text = _bug_report_text(bug_id)
        if _is_stale(bug_id, text):
            _discard(bug_id)
            discarded.append(bug_id)
        else:
            flagged.append((bug_id, text))

    for run_id in run_ids:
        text = _run_prompt_text(run_id)
        if _is_stale(run_id, text):
            _discard(run_id)
            discarded.append(run_id)
        else:
            flagged.append((run_id, text))

    print(f"Discarded {len(discarded)} stale entr{'y' if len(discarded) == 1 else 'ies'}.")
    if flagged:
        print(f"\n{len(flagged)} entr{'y' if len(flagged) == 1 else 'ies'} did NOT match a known-stale "
              f"signature -- left untouched, review manually:")
        for entry_id, text in flagged:
            print(f"  {entry_id}: {text}")

    print()
    print(_list_output())


if __name__ == "__main__":
    main()
