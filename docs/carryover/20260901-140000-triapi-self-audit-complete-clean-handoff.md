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
- **oh-my-llama `AGENTS.md` over ceiling / `tier_5_librarian` prompt-size-guard bug** (found live 2026-09-01) —
  oh-my-llama's own `AGENTS.md` is now 93,852 chars, over this repo's 73,728-char
  per-file ceiling convention (which oh-my-llama's docs also follow); a
  `librarian_escalate.py` call against it (adding a plan-correction note to
  a specific `triapi:plan` block) failed at the primary `agy` attempt with a
  prompt-size-guard `CalledProcessError`, and since `tier_5_librarian`'s
  fallback chain was retired in yesterday's (2026-09-01) tier-simplification
  work, there was no fallback leg to catch it -- straight to `human_handoff`.
  Worked around by hand-editing the specific block directly this one time
  (documented exception). Two real follow-ups this surfaces:
  (1) oh-my-llama's `AGENTS.md` needs the same `docs/agents/`-style overflow
  split TriAPI's own `AGENTS.md` already got, to get back under the ceiling;
  (2) reconsider whether `tier_5_librarian` having zero fallback
  (post-simplification) is an acceptable tradeoff, or whether at least one
  fallback leg (e.g. `fallback_local`) should be restored specifically for
  oversized-file cases, since Tier 5's whole-file-context design means it will
  keep hard-failing this way on any doc that's over the ceiling, in ANY
  target repo, not just this one instance.
- **`dispatcher.breakdown_phase()` silent detail drop on dense plan steps** (found live 2026-09-01, same oh-my-llama Phase 7 prep session) —
  `dispatcher.breakdown_phase()` (the Tier 2/Gemini call that compresses
  one markdown plan phase into per-item JSON task descriptions) silently
  dropped most of the technical detail from one unusually long, dense
  plan step (`task_store.py`'s method list, ~2000+ chars in a single
  checklist bullet after a hand-correction added `facts`/`put_fact`/`forget_fact`
  requirements) despite `breakdown_prompts.py`'s `BREAKDOWN_SYSTEM_INSTRUCTION`
  already explicitly warning against this ('Carry forward every concrete
  technical requirement... verbatim... Summarizing away a specific
  requirement... is a failure'). The resulting per-item description was
  missing most of the required method list (`facts`/`put_fact`/`forget_fact`,
  `fail`, `enqueue`, `telegram_set_topic`, `set_awaiting_approval`, `close`,
  correct `claim_next`/`requeue_stale` signatures), and Tier 4 built exactly
  what it was told, producing a materially incomplete file that still
  reported `status:success` since its narrow `build_cmd` only checked
  `py_compile` + 3 basic methods. Worked around this one time by
  hand-correcting the file directly after independently verifying the real
  requirement against `ohmyllama/state.py` and the real caller
  (`src/semai/adapters/daemon.py`) -- see that repo's own commit for detail.
  Real follow-up this surfaces: `breakdown_phase()` has no length-based
  safeguard for an unusually dense single bullet -- worth considering either
  (a) a length-based warning/split heuristic in `_split_plan_by_phase` or
  `breakdown_phase()` when a single checklist item is unusually long relative
  to the rest of its phase, or (b) a stronger `verify_cmd` convention
  encouraged by the planning prompt itself (e.g. asserting specific required
  method/symbol names exist, not just that the file compiles) so a lossy
  breakdown gets caught by its own `build_cmd` instead of silently reporting
  success.

## Session state

Nothing mid-flight. No active `triapi dispatch` process, no live
monitors. Next session should read this file, then decide with the user
whether to work the Virtual Codebase Plan together, resolve the TUI
plan's open questions, or start something new.
