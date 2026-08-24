# Carryover — 2026-08-23 (end of session)

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

- **`openrouter` branch merged into `main` (2026-08-23), commit `47cddb4`,
  NOT pushed to any remote.** All 4 tiers are now config-driven/hot-swappable
  through `config/tiers.yaml` + `llm_client.py`'s single `execute_llm()`
  dispatch point, with a working `probe_models()` pre-flight gate and
  consistent fail-fast across all 4 tiers. Current tier assignments: Tier 1
  repair = Claude CLI (`claude-sonnet-5`, effort `high`, `tier_1_manager`);
  Tier 1 planning = OpenRouter `stealth/ox-alpha` (`tier_1_planner`),
  falling back to Tier 1's own CLI config on any failure; Tier 2 = Nemotron 3
  via OpenRouter; Tier 3 = dots-note via OpenRouter; Tier 4 = local Qwen via
  Ollama. Full bug-by-bug detail (8 real bugs found and fixed pre-merge,
  including one that had fully bricked `triapi plan`) is in `PLAN.md`'s
  "Phase 21" entry. **Test suite: 141/141 passing on `main` post-merge.**
- The `openrouter` branch itself still exists locally, now fully merged —
  safe to delete (`git branch -d openrouter`) once confirmed not needed for
  anything else; not done yet, not urgent.
- **Queue items #1-#6 from the 2026-08-19 carryover, and the 2026-08-20
  queue drain**, are done — see `PLAN.md` for that history if ever needed;
  nothing outstanding from either.
- **oh-my-llama Consolidation Phase 5:** still only 5G left, blocked on
  the 7-day production soak of `src/semai/`'s daemon runtime. Not
  started; nothing to do until the soak completes or the user says to
  track it.

## Next up

- **Virtual Codebase Plan (Tiered Planner-Materializer architecture) is
  still queued.** `VIRTUAL_CODEBASE_PLAN.md` at this repo's root (restored
  2026-08-23 — had been deleted in commit `8998db5`, before this session;
  the user asked for it back). **User wants to work on this one together,
  personally** — hold off starting it solo; wait for the user.
- Otherwise: oh-my-llama's 5G once the soak clears.
