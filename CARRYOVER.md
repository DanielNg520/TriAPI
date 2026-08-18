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
- **TriAPI's own repo:** no known bugs as of the last session. Last
  self-dispatched feature (`unload_other_ollama_models()` +
  `tier_4_worker.default_model` re-evaluation) landed clean, confirmed live.
  `tier_4_worker.default_model` stays `fallback` (`gpt-oss:20b`) —
  `qwen3-coder:30b-cc` empirically confirmed too much for this machine's
  iGPU memory bandwidth, don't re-attempt the flip without new hardware
  info.
- **All four `AGENT_GUIDE.md` worked test cases are done:** ghostwriter,
  TriAPI self-fix, TriAPI learning (lessons + critique), Amazon HTML
  ingestion. (The old standalone `GHOSTWRITER_PLAN.md` said "queued" — that
  was stale; it's folded into `PLAN.md` now, marked completed.)

## Next up

Nothing queued. Whatever the user asks for next, or: oh-my-llama's 5G once
the soak clears.
