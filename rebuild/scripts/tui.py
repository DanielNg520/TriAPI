"""Interactive TUI driver for TriAPI (see AGENTS.md, "triapi tui", and
rebuild/tasks/triapi_tui_plan.md for the full design).

Each submitted prompt triggers a fresh, independent `claude -p` call --
no session continuity. Continuity instead comes from a per-session
carryover log file under rebuild/tasks/tui_sessions/.

This module holds only the Textual App wiring (Claude-authored, infra --
see rebuild/tasks/triapi_tui_plan.md, "Architecture"). The per-call logic
lives in its own small module per concern, each filled in by a separate
DeepSeek call per rebuild/tasks/tui/mini_task_{1..6}_*.md:
  - scripts.tui_session_log: new_session_log_path, format_log_entry, append_session_log
  - scripts.tui_framing: build_framed_prompt
  - scripts.tui_dispatch_status: is_dispatch_running
  - scripts.tui_stream: stream_claude_output
"""

from __future__ import annotations

from datetime import datetime, timezone

from textual import work
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog

from scripts.tui_dispatch_status import is_dispatch_running
from scripts.tui_framing import build_framed_prompt
from scripts.tui_session_log import append_session_log, format_log_entry, new_session_log_path
from scripts.tui_stream import stream_claude_output


class TriapiTUI(App):
    """Textual app: a scrolling output log plus a single-line input box.
    Glue code wiring the four helper modules above together -- infra,
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
