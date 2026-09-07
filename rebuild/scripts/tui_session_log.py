"""Per-session carryover log for `triapi tui` (see rebuild/tasks/triapi_tui_plan.md,
"Per-session carryover logging"). One file per TUI session, one appended
section per prompt/response round-trip.
"""

from datetime import datetime, timezone
from pathlib import Path

SESSIONS_DIR = Path(__file__).resolve().parent.parent / "tasks" / "tui_sessions"


def new_session_log_path() -> Path:
    """Return a fresh path for this TUI session's carryover log, under
    SESSIONS_DIR, named "<UTC timestamp, YYYYMMDD-HHMMSS>.md". Create
    SESSIONS_DIR itself if it doesn't exist (mkdir(parents=True,
    exist_ok=True)) -- do NOT create the log file yet, only the
    directory and the path; the file is created lazily by the first
    append_session_log() call. If a path for the current second is
    somehow already taken (SESSIONS_DIR / "<ts>.md" exists), append
    "-2", "-3", etc. before ".md" until an unused path is found.
    """
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    base = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    candidate = SESSIONS_DIR / f"{base}.md"
    suffix = 2
    while candidate.exists():
        candidate = SESSIONS_DIR / f"{base}-{suffix}.md"
        suffix += 1
    return candidate


def format_log_entry(prompt: str, response: str, ts: str) -> str:
    """Return one markdown carryover-log section as a single string,
    with this exact structure (ts is already a formatted string,
    caller's responsibility, not a datetime object):

        ## {ts}

        **Prompt:** {prompt}

        **Response:**

        {response}

    Two trailing newlines after the response, so consecutive entries
    appended to the same file are visually separated by a blank line.
    """
    return f"## {ts}\n\n**Prompt:** {prompt}\n\n**Response:**\n\n{response}\n\n"


def append_session_log(log_path: Path, entry: str) -> None:
    """Append `entry` (already formatted by format_log_entry) to the
    file at `log_path`, in UTF-8 text mode. Create the file (and any
    missing parent directories) if it doesn't exist yet. Never
    overwrite or truncate existing content -- append only.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(entry)
