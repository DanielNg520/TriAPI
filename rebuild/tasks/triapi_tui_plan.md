# `triapi tui` — detailed plan

Status: planned, not dispatched. Skeleton + mini-task specs written 2026-09-06.
Resolved design decisions (user, 2026-09-06) are in AGENTS.md's "Future plans" section — this
file is the implementation-level detail underneath that entry, not a replacement for it.

## Re-scoping note

The original 2026-08-25 spec described `triapi tui` as a subcommand "alongside the existing
plan/dispatch/status/list/self-fix/tech-debt" ones — that CLI (the old tier1-5 dispatcher) is
now deprecated-in-place. The live `triapi` command is `rebuild/scripts/task_queue.py`'s argparse
CLI (`add`/`list`/`approve`/`claim`/`complete`). This plan adds `tui` as a sixth subcommand on
*that* CLI, not the old one. "Warn if a dispatch is already running" is re-scoped accordingly:
the old pipeline had a literal dispatch process to check for; the current queue has no such
process, only task status — so the check becomes "warn if any task's status is `in_progress`"
(a `triapi claim` in flight), queried directly from `queue.sqlite3`.

## Architecture

New module `rebuild/scripts/tui.py`, imported by `task_queue.py`'s new `tui` subparser (one-line
addition to `build_parser`/`main`, done directly — trivial CLI wiring, not dispatched).

Textual (`textual==8.2.8`, already present in the environment; added to `requirements.txt`) for
the UI: a `RichLog` output pane plus a single-line `Input`. One `App` subclass, `TriapiTUI`,
holds the whole interaction loop — this is UI wiring against a specific library's async/threading
API, not a clean isolated contract, so it's Claude-authored directly rather than dispatched
(same reasoning `task_queue.py`'s argparse/schema/`main` got: infra where a wrong signature or a
hallucinated Textual API call would cost more to review than to just write).

Five standalone helper functions carry the actual per-call logic. Each has a precise
input/output contract with no Textual dependency, so each is unit-testable in isolation and
dispatched to DeepSeek exactly like `task_queue.py`'s five `cmd_*` bodies were:

1. `new_session_log_path() -> Path` — one fresh per-session log path, `rebuild/tasks/tui_sessions/<UTC timestamp>.md`.
2. `build_framed_prompt(raw_prompt: str) -> str` — prefixes the user's raw prompt with a fixed reminder of TriAPI's supervisor role, per the "inject minimal framing" decision.
3. `format_log_entry(prompt: str, response: str, ts: str) -> str` — renders one markdown carryover-log section.
4. `append_session_log(log_path: Path, entry: str) -> None` — appends that section to the session's log file, creating it on first write.
5. `is_dispatch_running() -> bool` — queries `queue.sqlite3` for any `in_progress` task.

`stream_claude_output(prompt: str) -> Iterator[str]` (subprocess wrapper around `claude -p`,
streaming stdout line by line) is a sixth function with the same isolated-contract shape — also
dispatched, listed last since it is the one most worth a careful manual read before trusting
(subprocess handling is exactly the kind of thing DeepSeek has fabricated signatures for before,
per `RULES.md`'s incident log).

## Per-session carryover logging (resolved: one file per session, not per call)

`TriapiTUI.__init__` calls `new_session_log_path()` once and holds it for the app's lifetime.
Every prompt/response round-trip appends one `## <timestamp>` section to that same file via
`format_log_entry` + `append_session_log`. Next `triapi tui` launch gets its own fresh file —
there's no cross-session carryover-file continuity beyond what the user reads back manually
(consistent with the "fresh `claude -p` call, no session memory" design — the log is a record
for the human, not an input to the next call).

## Verification plan

- `rebuild/tests/test_tui.py`: real tests for all six helper functions, written now (will fail
  with `NotImplementedError` until each mini-task lands — this is intentional, same shape as
  `test_task_queue.py`'s tests before `task_queue.py`'s five bodies were filled).
- `stream_claude_output` is tested against a fake `subprocess.Popen` (monkeypatched), not a real
  `claude` invocation — no live API calls from the test suite.
- Manual end-to-end check once all six land: launch `triapi tui`, type one prompt, confirm the
  output streams, confirm one dated file appears under `rebuild/tasks/tui_sessions/` with one
  logged entry, confirm a second launch gets a second, separate file.
- Textual App wiring itself (`compose`/`on_mount`/`on_input_submitted`/`_handle_prompt`) is
  smoke-tested via Textual's own `App.run_test()` harness, not unit-tested function-by-function —
  it's glue, covered by the manual end-to-end check above being reproducible in CI as a scripted
  Textual pilot test once the six helpers are real.

## Dispatch order

Mini-tasks 1-4 have no interdependency and can be dispatched/verified in any order. Mini-task 5
(`is_dispatch_running`) depends only on `scripts.task_queue`'s existing `DB_PATH`/schema, already
stable. Mini-task 6 (`stream_claude_output`) is independent of the other five but is the
highest-risk one to review carefully (subprocess + generator semantics) — do it last, once the
simpler four have confirmed the dispatch pattern is behaving.
