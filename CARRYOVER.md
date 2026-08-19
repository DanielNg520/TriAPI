# Carryover — 2026-08-18

**Standing rule for this file: stay brief.** Only what's needed to resume
the *next* session goes here. Finished-work narrative, per-round findings,
and "what happened" writeups belong in `PLAN.md` (this repo's permanent
build-history/decisions record), never here. Fold an item out of this file
into `PLAN.md` the moment it's resolved, in the same edit — don't leave it
lingering here in past tense. Full history through 2026-08-18 lives in
`PLAN.md`'s "Session Carryover Log" section.

**Read this first in a new session.** Then `AGENTS.md` for the file/dir
index, `AGENT_GUIDE.md` for the operating manual (what's safe to hand-edit
vs. must route through `triapi plan`/`dispatch`).

## Current state

- **oh-my-llama Consolidation Phase 5:** Sub-Phases 5A–5F all dispatched and
  verified (each needed at least one real post-hoc fix after its own run
  reported `completed` — see `PLAN.md`'s carryover log for the bug-by-bug
  detail). **Only 5G is left, blocked on a 7-day production soak** of
  oh-my-llama's new `src/semai/` daemon runtime — not started yet. Nothing
  to dispatch there until the soak completes or the user says to
  start/track it.
- **TriAPI's own repo:** Tier 4 task-type routing landed 2026-08-18. Self-
  Improvement feature (`hivemind_util.py`, `judge.py`, dispatcher hook +
  fix-forward, `tech_debt.py`, docs) landed 2026-08-19 — 17/17 items,
  64/64 tests, independently confirmed by a real Jules advisory pass
  (repo-wide `py_compile` clean too). Mock-patch-target lint check,
  context_files grounding guard, and plan phase-ordering/import-dependency
  guard, the plan-completion integrity fix, and Ollama lifecycle
  management all landed 2026-08-19 (5 of 6 total queue items fully done,
  full suite 111/111 clean). Full bug-by-bug detail in `PLAN.md`'s
  carryover log; systemic gaps found along the way are queued below.
  `config/tiers.yaml` also got two more corrections this session:
  `tier_4_worker` default model switched `q8_0` → `q6_K` with
  `num_ctx=24576` (dramatic speedup on small calls, mixed on very large
  files — see `PLAN.md`), and `jules_tester`/`tier_2_manager` rate limits
  corrected to reflect the account's actual Google AI Pro + billing-enabled
  status (was previously assuming free tier for both).
- **All four `AGENT_GUIDE.md` worked test cases are done:** ghostwriter,
  TriAPI self-fix, TriAPI learning (lessons + critique), Amazon HTML
  ingestion. (The old standalone `GHOSTWRITER_PLAN.md` said "queued" — that
  was stale; it's folded into `PLAN.md` now, marked completed.)

## Next up


Full incident detail for the item below is in `PLAN.md`'s carryover
log (`### 2026-08-19 — Queued, not yet implemented` entry) — kept out of
here per this file's own "stay brief" rule above.

- **#1 IN QUEUE (LAST, user reprioritization 2026-08-19): monolithic-file
  chunking + Tier-4-timeout-threshold guard.** Two patches: (1) hard
  file-length ceiling at Tier 4's context window (`num_ctx=24576`) as a
  plan-approval rule — reject/require-split for any file whose existing +
  planned content would exceed it; (2) escalate to Tier 3 after just 1
  Tier 4 failure, not 2, specifically when that failure is an
  oversize/timeout case (a normal `build_failed` still gets its full
  2-attempt budget). Route through `triapi plan`/`dispatch`.

Otherwise: oh-my-llama's 5G once the soak clears.

