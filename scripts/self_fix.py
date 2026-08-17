#!/usr/bin/env python3
"""Capture TriAPI crashes and prepare human-approved self-fix runs."""

import datetime
import json
import os
import re
import tempfile
import traceback
from pathlib import Path

from scripts import dispatcher, planner
from scripts.tri_logging import get_logger

TRIAPI_ROOT = Path(__file__).resolve().parent.parent
BUGS_DIR = TRIAPI_ROOT / "logs" / "triapi_bugs"
log = get_logger("self_fix")


def _source_files_from_report(bug_report: dict) -> list[str]:
    """Return unique TriAPI source files named by a captured traceback."""
    candidates = list(bug_report.get("source_files") or [])
    if not candidates:
        candidates = re.findall(r'File "([^"]+)"', bug_report.get("traceback", ""))

    source_files: list[str] = []
    root = TRIAPI_ROOT.resolve()
    for candidate in candidates:
        try:
            raw = Path(candidate).expanduser()
            path = raw.resolve() if raw.is_absolute() else (root / raw).resolve()
            if path.is_relative_to(root):
                relative = str(path.relative_to(root))
                if relative not in source_files:
                    source_files.append(relative)
        except (OSError, ValueError):
            continue
    return source_files


def draft_self_fix_plan(bug_report: dict) -> dict:
    """
    Given a captured crash/bug report, ask the planner (Tier 1) to draft a
    self-fix plan for it, scoped to the TriAPI project itself.
    """
    tb = bug_report.get("traceback", "")
    source_files = _source_files_from_report(bug_report)
    source_block = "\n".join(f"- {path}" for path in source_files) or "- (none identified)"
    message = (
        "This is a TriAPI-internal bug fix. Only modify the TriAPI repository.\n"
        f"TriAPI crashed with {bug_report.get('exception_type')}: "
        f"{bug_report.get('exception_message')}\n"
        f"Context: {bug_report.get('context')}\n"
        f"TriAPI source files present in the traceback:\n{source_block}\n"
        f"Traceback:\n{tb}\n"
        "Draft a focused, verifiable plan to fix this bug in the TriAPI codebase. "
        "Do not dispatch or edit another project."
    )
    try:
        return planner.plan_turn(message, str(TRIAPI_ROOT), None)
    except Exception as e:
        return {"status": "draft_failed", "reason": f"Planner unavailable: {e}"}


def capture_crash(
    exc: BaseException,
    *,
    run_id: str | None,
    context: str,
) -> Path | None:
    """Write a structured crash report without ever masking ``exc``."""
    try:
        tb = exc.__traceback__
        source_files = []
        if tb is not None:
            root = TRIAPI_ROOT.resolve()
            for frame in traceback.extract_tb(tb):
                path = Path(frame.filename).expanduser().resolve()
                if path.is_relative_to(root):
                    relative = str(path.relative_to(root))
                    if relative not in source_files:
                        source_files.append(relative)

        now = datetime.datetime.now(datetime.timezone.utc)
        crash_info = {
            "timestamp": now.isoformat().replace("+00:00", "Z"),
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "traceback": "".join(traceback.format_exception(type(exc), exc, tb)),
            "run_id": run_id,
            "context": context,
            "source_files": source_files,
        }

        BUGS_DIR.mkdir(parents=True, exist_ok=True)
        safe_run_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", run_id or "unknown")
        prefix = f"{now.strftime('%Y%m%d-%H%M%S-%f')}-{safe_run_id}-"
        fd, raw_path = tempfile.mkstemp(dir=BUGS_DIR, prefix=prefix, suffix=".json")
        path = Path(raw_path)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(crash_info, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        log.error(
            "[%s] Captured %s in %s: %s (report: %s)",
            run_id or "unknown",
            type(exc).__name__,
            context,
            exc,
            path,
        )
        return path
    except Exception as capture_error:
        log.error(
            "[%s] Failed to write crash report for %s: %s",
            run_id or "unknown",
            type(exc).__name__,
            capture_error,
        )
        return None


def queue_self_fix(bug_report_path: Path) -> dict:
    """Read a bug report JSON, draft a plan, queue a run as self_fix_drafted.

    Never auto-dispatches. project_dir is always TRIAPI_ROOT — never taken
    from the bug report or the crashing run's state.
    """
    bug_report_path = Path(bug_report_path).expanduser().resolve()
    if not bug_report_path.is_relative_to(BUGS_DIR.resolve()):
        return {"status": "draft_failed", "reason": "Bug report must be under logs/triapi_bugs"}
    with open(bug_report_path, encoding="utf-8") as f:
        bug_report = json.load(f)

    draft = draft_self_fix_plan(bug_report)
    if draft.get("status") != "ok" or not draft.get("text"):
        return {"status": "draft_failed", "reason": draft.get("reason", draft.get("status"))}

    prompt = (
        f"[self-fix] {bug_report.get('exception_type')}: "
        f"{bug_report.get('exception_message')}"
    )
    # Deliberate: always TRIAPI_ROOT, never a project_dir from the bug report.
    state = dispatcher.new_run(prompt=prompt, project_dir=str(TRIAPI_ROOT.resolve()))
    if Path(state.get("project_dir", "")).resolve() != TRIAPI_ROOT.resolve():
        return {"status": "draft_failed", "reason": "Refusing self-fix run outside TriAPI root"}
    state["plan_text"] = draft["text"]
    state["status"] = "self_fix_drafted"
    state["self_fix_bug_report"] = str(bug_report_path)
    dispatcher.save_run(state)
    return {"status": "queued", "run_id": state["run_id"]}
