# TUI feature request (temporary staging doc)

**Status: NOT planned/dispatched yet. Temporary holding doc only** — this
is not a `docs/carryover/`-indexed file and not a `triapi`-managed plan.
Once the currently-active tier-flip dispatch (`20260825-092344-5ff4a7`,
see `CARRYOVER.md` → `docs/carryover/20260825-092344-active-tier-flip-plan-and-queue.md`)
is fully drained, run this through `triapi plan "<prompt built from the
spec below>"` (the one-plan-per-repo gate blocks a new plan until then),
review/approve the generated plan, then `triapi dispatch`. Delete this
file once that plan is drafted — the spec should live in the real plan
text and `PLAN.md`'s phase history from that point on, not here.

## Feature: `triapi tui`

New CLI subcommand `triapi tui` (does not change bare `triapi`'s existing
behavior) launches an interactive terminal UI as an alternative entry
point to the pipeline.

### Confirmed spec (user, 2026-08-25)

- **Invocation**: `triapi tui` — a new subcommand alongside the existing
  `plan`/`dispatch`/`status`/`list`/`self-fix`/`tech-debt` ones (see
  `/home/dyne/.local/bin/triapi`'s `argparse` subparsers).
- **Per-prompt behavior**: each prompt typed into the TUI triggers a
  **fresh, independent** `claude -p "<prompt>"` call. Explicitly **not**
  session-continued — no `--continue`/`--resume`, no CLI-side
  conversation memory carried between turns.
- **Continuity mechanism**: instead of conversational memory, each call's
  progress/state/activity — plus TriAPI's own errors and responses — gets
  a **meaningful, brief** entry logged and indexed into `CARRYOVER.md`
  (presumably a new dated `docs/carryover/` file per TUI session, following
  the existing index convention: one-line index row + full detail in the
  dated file). This is what gives the *next* TUI launch/session context of
  what came before, replacing conversational memory.
- **Output**: streams live into the TUI as `claude -p` generates it (not
  buffered until the full response is ready).
- **User interaction loop**: after TriAPI/`claude -p` prints its response
  in the TUI, the user can type a follow-up reacting to what they saw —
  that follow-up is itself just the next fresh prompt (per the "no
  session continuity" rule above), relying on the CARRYOVER.md logging to
  carry context forward rather than the CLI call itself.
- **Example prompt shape** the user gave, illustrating intended everyday
  use (not a literal fixed template): *"Read carryover.md and carryon
  with the queue."* — i.e. this TUI is meant to become the normal
  day-to-day driver of TriAPI-adjacent work, not a one-off/rarely-used
  tool.

### Open design questions for the eventual `triapi plan` prompt

Not yet asked/answered — worth resolving (or explicitly deferring to the
plan-drafting model's judgment) before dispatch:

- TUI implementation approach: raw `curses`, or a library (e.g. Python's
  `textual`/`rich`)? No dependency choice has been made yet.
- Exact `CARRYOVER.md`/dated-file write mechanics: does each individual
  `claude -p` call get its own dated file, or does a TUI *session*
  (potentially many prompts) get one dated file appended to across the
  session? The existing convention favors one file per session/task, not
  per single call — needs a decision matching that existing granularity.
  See `feedback_docs_are_index_files` memory and `CARRYOVER.md`'s own
  "Convention for adding a new entry" section for the pattern to follow.
- How does the TUI distinguish "just show me the last carryover context"
  vs. "actually dispatch/act on the queue" — should it always call
  `claude -p` with the raw user prompt verbatim, or does it inject any
  fixed system framing (e.g. reminding `claude -p` of TriAPI's role) around
  it?
- Should `triapi tui` refuse to launch (or warn) if a `triapi dispatch` run
  is already active in the background, to avoid confusing concurrent
  state, or is that out of scope / not a real conflict since the TUI
  doesn't dispatch anything itself, just runs `claude -p` calls?
