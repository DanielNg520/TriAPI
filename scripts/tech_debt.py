"""Tech-debt backlog for fixes that `handle_fix_forward` gave up on.

Tier 3 is in DeepSeek peak billing hours 01:00-04:00 UTC (LA local 2026-08-18T20:59:37.361917-07:00, UTC 2026-08-19T03:59:37.361917+00:00).

Each entry records the file, a hash of its bytes at the moment it was
logged, and why. See knowledge/TECH_DEBT.md for the canonical backlog file.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

TECH_DEBT_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "TECH_DEBT.md"

_ENTRY_RE = re.compile(
    r"^- \[ \] FILE: (?P<filepath>.*?) \| HASH: (?P<hash>[0-9a-f]{64}|n/a.*?) \| REASON: (?P<reason>.*)$"
)


def log_tech_debt(filepath: str, reason: str) -> None:
    """Append a tech-debt entry for filepath, hashing its current bytes.

    Uses the file's on-disk SHA-256 at call time (not a git hash) -- TriAPI
    edits files before committing, so a git hash would track the wrong
    state.
    """
    content_hash = hashlib.sha256(Path(filepath).read_bytes()).hexdigest()

    TECH_DEBT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not TECH_DEBT_PATH.exists():
        TECH_DEBT_PATH.write_text(
            "# Tech Debt\n\n"
            "Fixes `handle_fix_forward` gave up on after a single Tier 3 "
            "attempt failed to rebuild. Tier 3 is in DeepSeek peak billing "
            "hours 01:00-04:00 UTC (LA local 2026-08-18T20:59:37.361917-07:00, "
            "UTC 2026-08-19T03:59:37.361917+00:00). Each entry's HASH is the file's "
            "SHA-256 at the moment it was logged; if the file has since "
            "changed, treat the entry as STALE.\n\n",
            encoding="utf-8",
        )

    with open(TECH_DEBT_PATH, "a", encoding="utf-8") as f:
        f.write(f"- [ ] FILE: {filepath} | HASH: {content_hash} | REASON: {reason}\n")


def read_tech_debt_entries() -> list[dict]:
    """Parse all logged entries from knowledge/TECH_DEBT.md."""
    if not TECH_DEBT_PATH.exists():
        return []

    entries = []
    for line in TECH_DEBT_PATH.read_text(encoding="utf-8").splitlines():
        match = _ENTRY_RE.match(line.strip())
        if match:
            entries.append(match.groupdict())
    return entries


def check_staleness(entry: dict) -> bool:
    """True if entry's file is missing or has changed since it was logged."""
    if entry["hash"].startswith("n/a"):
        return False
    path = Path(entry["filepath"])
    if not path.exists():
        return True
    return hashlib.sha256(path.read_bytes()).hexdigest() != entry["hash"]


def verify_tech_debt() -> bool:
    """Verify all logged tech-debt entries for staleness.

    Returns:
        True if all entries are valid/fresh, False if any entries are stale.
    """
    entries = read_tech_debt_entries()
    if not entries:
        return True

    all_fresh = True
    for entry in entries:
        if check_staleness(entry):
            all_fresh = False
            print(f"STALE: {entry['filepath']} (hash mismatch or missing)")
        else:
            print(f"OK: {entry['filepath']}")
    return all_fresh


def remove_resolved_entries(resolved_targets: set[str]) -> None:
    """Remove tech-debt entries whose filepath is in resolved_targets.

    Reads knowledge/TECH_DEBT.md, filters out any entry lines whose parsed
    filepath is in resolved_targets, and overwrites the file with the remaining
    lines, preserving the header intact.
    """
    if not TECH_DEBT_PATH.exists():
        return

    lines = TECH_DEBT_PATH.read_text(encoding="utf-8").splitlines()
    kept_lines = []

    for line in lines:
        match = _ENTRY_RE.match(line.strip())
        if match:
            filepath = match.group("filepath")
            if filepath not in resolved_targets:
                kept_lines.append(line)
        else:
            # Non-entry lines (header, description) are always kept
            kept_lines.append(line)

    TECH_DEBT_PATH.write_text("\n".join(kept_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    import sys
    sys.exit(0 if verify_tech_debt() else 1)
