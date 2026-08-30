# Carryover — 2026-08-30 07:20 — Sub-Phase 5G fully retired; caused (and recovered from) a live service outage

**Session summary:** User asked why Sub-Phase 5G wasn't just fixed;
dispatched a properly-rescoped plan through the pipeline (the original
2026-08-28 plan was both wrong-scoped and had false-success history — see
below). Completed it, found two more real gaps mid-flight (a dead-code
cleanup miss, a feature never ported), fixed both, but the multi-hour
patch-and-retry loop needed to get there left oh-my-llama's live
`oh-my-llama.service` crash-looped into `failed` for ~15 minutes before I
caught and fixed it. Recovered cleanly; no data loss, service back to
normal 20+ minutes before session end.

## Sub-Phase 5G: legacy `ohmyllama/` runtime fully retired

The original plan (run `20260828-182931-264248`, referenced from
`AGENTS.md`) was unreliable: 3 of its 4 capability-file deletions were
recorded `success` but **never actually happened** (confirmed via `git
log` showing no deletion commit ever existed) — a false-success case, not
caught until this session. It was also incompletely scoped: it never
identified that `ohmyllama/cli.py`/`tui.py`/`telegram.py` were themselves
dead (nothing in `pyproject.toml` or any `deploy/*.service` points at
them), or that ~9 legacy test files still directly tested the old
modules despite semai-native equivalents existing.

Verified the real current state from scratch (grep against the live
repo, not the stale plan or its history) and dispatched a properly-scoped
5-phase plan (run `20260830-042532-fec46a`) with `--refactor` to supersede
the stale one:
1. Delete 9 legacy test files (`test_agent.py`, `test_browser_errand.py`,
   `test_agent_escalation.py`, `test_agent_rules.py`,
   `test_agent_feedback.py`, `test_ghostwriter.py`,
   `test_router_observations.py`, `test_telegram_review_label.py`,
   `test_telegram_delivery.py`) — each superseded 1:1 by a semai-native
   test.
2. Delete the 3 dead entry points (`ohmyllama/cli.py`, `tui.py`,
   `telegram.py`).
3. Delete the 4 old runtime files (`orchestrator.py`, `agent.py`,
   `ghostwriter.py`, `watcher.py`).
4. Delete the 4 old capability files (`terminal.py`, `search_router.py`,
   `memory.py`, `ingestion.py`), leaving `browser.py`.
5. Update `docs/Agent/CARRYOVER.md`.

Result: `ohmyllama/` now holds only files still genuinely in use (not
part of this migration's scope); `ohmyllama/capabilities/` holds only
`base.py`, `browser.py`, `_path_guard.py`, `__init__.py`. Full
`bash run_tests.sh` green (109 passed) at every checkpoint. Committed
`7899ce1`, pushed.

## Two real gaps found mid-dispatch, both resolved

1. **`ohmyllama/capabilities/__init__.py`** still had dangling imports of
   the 4 just-deleted capability modules (`from .terminal import
   TerminalCapability`, etc.) — my own grep patterns checking for
   "zero remaining references" only matched fully-qualified
   `ohmyllama.capabilities.X` style imports, missing the package's own
   relative imports (`from .terminal import ...`). Caught by
   `bash run_tests.sh` itself (a real `ModuleNotFoundError`), not by any
   of my checks. Added a proper plan item; a tier (Tier 3) fixed it
   correctly, verified by reading the file directly afterward.
2. **A real feature gap, not a doc bug:** `tests/test_semantic_cache.py`
   turned out to be the last reference to the deleted
   `ohmyllama/orchestrator.py`, and it tests a real feature — an
   embedding-similarity answer cache for chat/triage — that was **never
   ported to `src/semai/`** and had no prior decision record. Paused and
   asked the user rather than silently deleting test coverage for an
   undocumented feature drop; user chose to drop it formally. Added
   `docs/decisions/0015-drop-semantic-answer-cache.md` (matching the
   existing ADR convention) and a `D15` row in `docs/semai-preflight.md`,
   which in turn required bumping `tests/test_adr_check_seam.py`'s
   hardcoded ADR count from 14 to 15 (same "hardcoded count in a seam
   test" pattern this repo has hit before, e.g.
   `test_semai_intents.py`'s `INTENT_KINDS` count per its own
   `AGENT_GUIDE.md`).

## Also fixed: a documentation mistake of my own, and a stale
Phase-block correction

- The docs-update plan two runs before this one deleted a plan block
  (`20260828-182931-264248`, Sub-Phase 5G itself!) that it was explicitly
  told to preserve, because I gave it a tautological `verify_cmd` — see
  the previous carryover file. Already fixed there; noted again here
  since Sub-Phase 5G is the same block this session finished for real.
- My own Phase-5G completion plan told the tier to mark oh-my-llama's
  "Phase 7 Package rename" as `done` in `CARRYOVER.md` — wrong: 5G
  finishing only *unblocks* 7, `pyproject.toml`'s package is still
  literally named `ohmyllama`. Caught by re-verifying my own prior
  instruction against live state (not trusting my own plan text either),
  dispatched a one-item correction (run `20260830-065753-beb2d2`) through
  the pipeline per the "use librarian for doc edits" convention, verified
  directly, committed `f84a59e`.

## The outage: `oh-my-llama.service` crash-looped into `failed` for ~15 min

Root cause: between deleting `ohmyllama/capabilities/terminal.py` and
landing the `__init__.py` fix above, the repo was in a transiently broken
state (import error). `resource_guard`'s pause/resume cycle — triggered
by the many dispatch stop/resume cycles this session's patch-and-retry
loop required — happened to resume the live service during exactly that
broken window. `semai-daemon` crashed on every restart
(`ModuleNotFoundError: No module named 'ohmyllama.capabilities.terminal'`),
and systemd's restart-rate-limit ("Start request repeated too quickly")
latched it into `failed` after 5 failures within ~16 seconds
(06:48:00–06:48:16). It sat `failed` — not auto-retrying, per systemd's
design — until I separately checked service health at 07:01 (unrelated
to the crash itself; a routine end-of-session check that happened to
catch it) and found both `oh-my-llama.service` and
`oh-my-llama-telegram.service` reporting `failed`.

**Recovery:** confirmed the code was already fixed by then (the
`__init__.py` fix had landed ~7 minutes earlier, verified via
`bash run_tests.sh` green), so this was purely a matter of clearing
systemd's latched failure state: `systemctl --user reset-failed
oh-my-llama.service oh-my-llama-telegram.service` then `systemctl --user
start` both. Confirmed stable (single invocation, no restart-counter
increment) for 20+ minutes before end of session.

**Contributing factor, not a TriAPI bug per se:** running two `triapi
dispatch` processes concurrently (this session's own `fec46a` and
`beb2d2` runs briefly overlapped, both doing their own post-completion
`resource_guard` resume + Jules advisory test cycles) is itself a known
risk — `AGENT_GUIDE.md` already says to check `pgrep -af "triapi dispatch"`
before hand-patching state. It happened here because a `--background`
dispatch's own post-completion Jules-advisory-test tail can run for many
minutes (up to ~15 min observed this session) after "Dispatch completed"
already logs, and I started a second unrelated dispatch without checking
for that lingering tail process first. No corruption resulted (both runs
touched disjoint parts of the repo), but the coincidence of one run's
mid-flight broken window lining up with a resume triggered by either
process is exactly the kind of race this pattern risks. **Lesson:** even
after "Dispatch completed" logs, `pgrep -af "triapi.py dispatch"` before
launching another dispatch against the same project — the process can
still be alive doing its own post-completion service pause/resume dance
for several more minutes.

## Status at session end

TriAPI: clean, no code changes this entry (all fixes were either
plan-prompt/run-state patches or oh-my-llama-side commits via the
pipeline). oh-my-llama: clean working tree (only the known pre-existing
tracked-sqlite binary diffs), `bash run_tests.sh` green (109 passed),
both `oh-my-llama.service`/`oh-my-llama-telegram.service` active and
stable, pushed to `migration-clean-up` (`f84a59e` latest). Queue is
empty — Sub-Phase 5G was the last open item from the prior file's
verified-real queue; Phase 7 (package rename) is the next one, correctly
marked "unblocked, not yet started" rather than done.
