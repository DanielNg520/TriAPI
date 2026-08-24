# Carryover — 2026-08-23

**Standing rule for this file: stay brief.** Only what's needed to resume
the *next* session goes here. Finished-work narrative, per-round findings,
and "what happened" writeups belong in `PLAN.md` (this repo's permanent
build-history/decisions record), never here. Fold an item out of this file
into `PLAN.md` the moment it's resolved, in the same edit — don't leave it
lingering here in past tense. Full history through 2026-08-19 lives in
`PLAN.md`'s "Session Carryover Log" section.

**Read this first in a new session.** Then `AGENTS.md` for the file/dir
index, `AGENT_GUIDE.md` for the operating manual (what's safe to hand-edit
vs. must route through `triapi plan`/`dispatch`).

## Current state

- **Queue items #1-#6 from the 2026-08-19 carryover are ALL DONE** as of
  tonight (2026-08-20): #1-#3 (TriAPI's own repo), #4a (already fixed
  2026-08-19), #4b/#5 (oh-my-llama webui.py + AGENTS.md deep-clean), #4c
  (`ohmyllama/state.py` package split, done correctly this time). Full
  bug-by-bug detail — including four real TriAPI pipeline bugs found and
  fixed live along the way — is in `PLAN.md`'s "2026-08-20 — Queue drain"
  entry. `queued_plans/` is now stale (both plans in it were superseded by
  fresh regenerated plans this session, not resumed as originally
  written) — safe to delete next time it's in the way, not urgent.
- **Provider Decoupling Complete (2026-08-22)**: LLM client routing (`llm_client.py`), config loading (`config_loader.py`), and fallback behaviors (`_call_gemini_fallback` / `_fallback_ollama`) are fully decoupled and dynamic. TriAPI now routes correctly through OpenRouter, DeepSeek, and local fallbacks without hardcoded model strings. All changes are committed.
- **Openrouter-branch self-audit + hand-fix (2026-08-23), NOT YET COMMITTED**:
  7 bugs found and fixed (6 from a fork audit + 1 found live — a
  content-filter issue that had fully bricked `triapi plan`). Full detail in
  `PLAN.md`'s "Phase 21" entry. Test suite: `tests/test_branch_features.py`
  68/68 passing (was hanging before the fix); `tests/test_judge.py` has 10
  pre-existing, unrelated failures (confirmed via `git stash`), not touched.
  **Working tree has all fixes applied but nothing is committed yet** —
  review `git diff` and commit next session if not done by end of this one.
- **oh-my-llama Consolidation Phase 5:** still only 5G left, blocked on
  the 7-day production soak of `src/semai/`'s daemon runtime. Not
  started; nothing to do until the soak completes or the user says to
  track it.

## Next up

- **#6 — Virtual Codebase Plan (Tiered Planner-Materializer
  architecture):** see `VIRTUAL_CODEBASE_PLAN.md` at this repo's root.
  **User wants to work on this one together, personally** — hold off
  starting it solo; wait for the user.
- Otherwise: oh-my-llama's 5G once the soak clears.
