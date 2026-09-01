# Carryover — 2026-09-01 14:00 PDT — Session closed clean, self-audit complete

**Status: RESOLVED at write time.** This file exists to give a fresh
session a short, current-state brief instead of a long day's blow-by-blow
— see `20260901-100100-triapi-tier-simplification-self-dispatch-two-bugs-fixed.md`
(now history) for the full narrative if a task specifically needs it.

## What today covered (all pushed to `origin/main`, working tree clean)

1. Tier reassignment simplified into one shared peak/off-peak promotion
   chain across Tiers 2/3/4; Tier 5's fallback chain and the Gemini
   per-model quota-fallback mechanism retired.
2. `tier2_escalate.py`'s synthetic-error handling broadened to cover all
   three `CalledProcessError(0, ...)` shapes `_call_agy_cli` can raise,
   not just the argv-too-large one (a same-day incomplete fix, caught and
   closed).
3. `triapi tech-debt`'s `cmd_tech_debt()` fixed (missing import causing a
   real `NameError`, a placeholder no-op `build_cmd`, a dropped failure
   reason) — `knowledge/TECH_DEBT.md` hash-verified and pruned to its 4
   genuinely-open entries.
4. `PLAN.md` split from ~205,040 chars into a short index plus
   `docs/plan/` (mirrors the existing `docs/agents/`/`docs/carryover/`
   convention) — was 2.7x this repo's 73,728-char ceiling.
5. Two real, substantive queued items recovered from silently falling out
   of tracking (see "Still queued" below) and added to `AGENTS.md`'s Root
   index so this can't happen again unnoticed; a process-lesson memory
   (`feedback_recarry_on_hold_items`) saved outside this repo.
6. Self-audit dispatched through `triapi plan` (twice — both aborted at
   the approval prompt for lack of a TTY under this environment, a known
   limitation; findings independently verified against the real code
   before acting, which caught one of three findings as fabricated).
   Fixed: `dispatcher.breakdown_phase()` now resolves `tier_2_manager`'s
   `peak_alt` block like every other real Tier 2 call site (was always
   using the off-peak DeepSeek config even during peak hours);
   `librarian_escalate.py`'s `--model` CLI override was dead code, now
   honored.

Full test suite green throughout every step (104 unittest tests + 7
pytest tests, zero skipped).

## Still queued (unchanged, carry this section forward every session)

- **`VIRTUAL_CODEBASE_PLAN.md`** (repo root) — Tiered Planner-Materializer
  design for large-file Tier 4 edits. **On hold for the user
  specifically — do not start solo.** See
  [[project_triapi_virtual_codebase_plan]] (memory) / `AGENTS.md`'s Root
  index for detail.
- **`docs/TUI_plan.md`** — confirmed `triapi tui` subcommand spec,
  unblocked, not yet dispatched. Has open design questions (see the file)
  that need the user's input before a `triapi plan` session. See
  [[project_triapi_tui_plan]] (memory) / `AGENTS.md`'s Root index.
- **Gemini free API key placement** — lands with the new month (2026-09);
  user will specify where it goes. Don't assume its slot.

## Session state

Nothing mid-flight. No active `triapi dispatch` process, no live
monitors. Next session should read this file, then decide with the user
whether to work the Virtual Codebase Plan together, resolve the TUI
plan's open questions, or start something new.
