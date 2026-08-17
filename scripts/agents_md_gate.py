"""Enforces the "plan once per repo" rule: `triapi plan`'s Tier 1 planner
should run once per target repo, its approved plan appended to that repo's
own AGENTS.md, and not be invoked again until every phase/step checkbox in
that appended plan is checked off -- unless the new goal is an explicit
refactor/pivot (`triapi plan --refactor`).

Each appended plan lives inside an HTML-comment-delimited block keyed by
run_id, so multiple runs' plans can coexist in one AGENTS.md and each is
tracked independently:

    <!-- triapi:plan run_id=<id> start -->
    ## TriAPI Plan (run <id>, appended 2026-08-16)
    <plan markdown, with `- [ ]`/`- [x]` checklist items>
    <!-- triapi:plan run_id=<id> end -->

Only the most recent block's completion state gates a new plan -- an older
finished (or abandoned-via-refactor) block is not re-checked.
"""

import re
from pathlib import Path

AGENTS_MD_NAME = "AGENTS.md"

_BLOCK_RE = re.compile(
    r"<!-- triapi:plan run_id=(?P<run_id>\S+) start -->\n(?P<body>.*?)<!-- triapi:plan run_id=(?P=run_id) end -->\n?",
    re.DOTALL,
)
_UNCHECKED_RE = re.compile(r"^\s*(?:[-*]|\d+\.)\s+\[ \]", re.MULTILINE)


def _agents_md_path(project_dir: str) -> Path:
    return Path(project_dir) / AGENTS_MD_NAME


def find_incomplete_plan(project_dir: str) -> dict | None:
    """Return details of the most recently appended `triapi:plan` block in
    this repo's AGENTS.md if it still has unchecked steps, else None.

    A block with zero `- [ ]`/`- [x]` checkboxes at all (the planner didn't
    use checkbox syntax) is treated as complete rather than blocking forever
    -- fails open on that specific ambiguity, since there's nothing for the
    user to check off.
    """
    path = _agents_md_path(project_dir)
    if not path.exists():
        return None
    blocks = list(_BLOCK_RE.finditer(path.read_text()))
    if not blocks:
        return None
    last = blocks[-1]
    unchecked = _UNCHECKED_RE.findall(last.group("body"))
    if not unchecked:
        return None
    return {"run_id": last.group("run_id"), "unchecked_count": len(unchecked)}


def append_plan(project_dir: str, run_id: str, plan_text: str, appended_date: str) -> None:
    """Append the approved plan as a new `triapi:plan` block to this repo's
    AGENTS.md, creating the file (with a minimal header) if it doesn't exist.
    """
    path = _agents_md_path(project_dir)
    block = (
        f"<!-- triapi:plan run_id={run_id} start -->\n"
        f"## TriAPI Plan (run {run_id}, appended {appended_date})\n\n"
        f"{plan_text.strip()}\n"
        f"<!-- triapi:plan run_id={run_id} end -->\n"
    )
    if not path.exists():
        path.write_text(
            "# AGENTS.md\n\n"
            "Repo-root reference for coding agents. Sections below tagged "
            "`triapi:plan` are execution plans appended by TriAPI's Tier 1 "
            "planner -- see the run's own checklist for progress.\n\n"
            + block
        )
        return
    existing = path.read_text()
    if not existing.endswith("\n"):
        existing += "\n"
    path.write_text(existing + "\n" + block)


def mark_plan_complete(project_dir: str, run_id: str) -> bool:
    """Flip every `- [ ]` to `- [x]` inside the named run's block only.

    Returns False (no-op) if AGENTS.md or that run's block isn't found --
    e.g. the plan was appended to a project_dir that no longer exists, or
    AGENTS.md was hand-edited since. Never raises for that case.
    """
    path = _agents_md_path(project_dir)
    if not path.exists():
        return False
    text = path.read_text()
    found = False

    def _replace(match: re.Match) -> str:
        nonlocal found
        if match.group("run_id") != run_id:
            return match.group(0)
        found = True
        checked_body = re.sub(r"\[ \]", "[x]", match.group("body"))
        return (
            f"<!-- triapi:plan run_id={run_id} start -->\n{checked_body}"
            f"<!-- triapi:plan run_id={run_id} end -->\n"
        )

    new_text = _BLOCK_RE.sub(_replace, text)
    if not found:
        return False
    path.write_text(new_text)
    return True
