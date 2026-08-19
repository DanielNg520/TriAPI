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
  guard, the plan-completion integrity fix, Ollama lifecycle management,
  and the file-size ceiling + oversize-escalation guard all landed
  2026-08-19 (6 of 6 original queue items done, full suite 117/117 clean).
  Full bug-by-bug detail in `PLAN.md`'s carryover log; one new systemic
  gap found along the way is queued below.
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

Full incident detail for the item below is in `PLAN.md`'s carryover log
(`### 2026-08-19 — File-Size Ceiling Guard...` entry's "found post-landing"
section) — kept out of here per this file's own "stay brief" rule above.

- **#1 IN QUEUE: AGENTS.md itself is 143,773 chars — over Tier 4's own new
  size ceiling (73,728 chars) — and the just-landed
  `_enforce_file_size_ceiling()` guard re-runs on every `breakdown_plan()`
  call, including resuming an already-broken-down run, so it can
  retroactively block a resume the moment ANY item's target (not just the
  one currently dispatching) exceeds the ceiling.** Two independent fixes
  needed: (a) shrink `AGENTS.md` — it has grown well past this repo's own
  doc-hygiene rule (see `feedback_doc_hygiene_all_docs` memory) through
  accumulated `triapi:plan` blocks and verbose file/dir index entries; (b)
  make `breakdown_plan()`'s post-breakdown guards (file-size ceiling,
  import-order, test-context) run once after initial breakdown, not on
  every resume of an already-broken-down state — a resume should trust
  the prior successful validation pass, not re-litigate it against
  unrelated items' current disk state. Route through `triapi plan`/`dispatch`.

Otherwise: oh-my-llama's 5G once the soak clears.

