"""Interactive TUI driver for TriAPI (see AGENTS.md, "triapi tui", and
rebuild/tasks/triapi_tui_plan.md for the full design).

Each submitted prompt triggers a fresh, independent `claude -p` call --
no session continuity. Continuity instead comes from a per-session
carryover log file under rebuild/tasks/tui_sessions/.

Skeleton written by Claude (top-level constructor): the App class and
every helper function's signature/contract are fixed here. Each helper
body below is filled in by a separate DeepSeek call (lower-level
builder), one function per call, per rebuild/tasks/tui/mini_task_{1..6}_*.md.
"""

from __future__ import annotations

import subprocess
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from textual import work
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog

from scripts.task_queue import DB_PATH, init_conn

SESSIONS_DIR = Path(__file__).resolve().parent.parent / "tasks" / "tui_sessions"

FRAMING_PREFIX = (
    "You are operating as TriAPI's supervisor for this repository. "
    "Follow AGENTS.md (hub-and-spoke: DeepSeek/agy write, you audit every "
    "response before the next step) and rebuild/RULES.md. Task:\n\n"
)


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


def build_framed_prompt(raw_prompt: str) -> str:
    """Return FRAMING_PREFIX + raw_prompt, unchanged otherwise -- do not
    alter raw_prompt's own content, only prepend the fixed prefix
    already defined above as the module-level constant FRAMING_PREFIX.
    """
    return FRAMING_PREFIX + raw_prompt


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
    raise NotImplementedError


def append_session_log(log_path: Path, entry: str) -> None:
    """Append `entry` (already formatted by format_log_entry) to the
    file at `log_path`, in UTF-8 text mode. Create the file (and any
    missing parent directories) if it doesn't exist yet. Never
    overwrite or truncate existing content -- append only.
    """
    raise NotImplementedError


def is_dispatch_running() -> bool:
    """Return True if the queue database (scripts.task_queue.DB_PATH)
    exists AND contains at least one row in `tasks` with
    status = 'in_progress' -- meaning a `triapi claim` is active.
    Return False if no such row exists, or if DB_PATH doesn't exist yet
    (don't create it -- a missing database means nothing is running).
    Open and close your own connection via sqlite3.connect(DB_PATH) and
    scripts.task_queue.init_conn(conn); don't assume one is passed in.
    """
    raise NotImplementedError


def stream_claude_output(prompt: str) -> Iterator[str]:
    """Run `claude -p <prompt>` as a subprocess via
    subprocess.Popen(["claude", "-p", prompt], stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT, text=True), and yield its combined
    stdout+stderr one line at a time as it's produced (not buffered
    until the process exits) -- iterate `proc.stdout` directly. Strip
    only the trailing newline from each yielded line (str.rstrip("\\n")).
    Stop yielding once the process's stdout closes (EOF); then wait()
    on the process to reap it. Do not raise if the process exits
    non-zero -- just stop yielding, the caller doesn't need the exit code.
    """
    raise NotImplementedError


class TriapiTUI(App):
    """Textual app: a scrolling output log plus a single-line input box.
    Glue code wiring the six helper functions above together -- infra,
    not dispatched (see rebuild/tasks/triapi_tui_plan.md, "Architecture")."""

    CSS = """
    RichLog { border: solid $accent; height: 1fr; }
    Input { dock: bottom; }
    """
    BINDINGS = [("ctrl+c", "quit", "Quit")]

    def __init__(self) -> None:
        super().__init__()
        self.session_log_path = new_session_log_path()

    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(id="output", wrap=True, markup=True)
        yield Input(placeholder="Type a prompt for TriAPI...", id="prompt_input")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#output", RichLog)
        if is_dispatch_running():
            log.write("[yellow]Warning: a triapi dispatch is already in progress.[/yellow]")
        log.write(f"[dim]Session log: {self.session_log_path}[/dim]")
        self.query_one("#prompt_input", Input).focus()

    def on_input_submitted(self, message: Input.Submitted) -> None:
        raw_prompt = message.value
        self.query_one("#prompt_input", Input).value = ""
        if raw_prompt.strip():
            self._handle_prompt(raw_prompt)

    @work(thread=True)
    def _handle_prompt(self, raw_prompt: str) -> None:
        log = self.query_one("#output", RichLog)
        self.call_from_thread(log.write, f"[bold cyan]> {raw_prompt}[/bold cyan]")

        framed = build_framed_prompt(raw_prompt)
        response_lines: list[str] = []
        for line in stream_claude_output(framed):
            response_lines.append(line)
            self.call_from_thread(log.write, line)

        response = "\n".join(response_lines)
        ts = datetime.now(timezone.utc).isoformat()
        entry = format_log_entry(raw_prompt, response, ts)
        append_session_log(self.session_log_path, entry)


def main(argv: list[str] | None = None) -> int:
    TriapiTUI().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
