# Carryover — 2026-09-04 — Tech debt corruption incident and false build_failed bug

**Status: RESOLVED.** Working tree clean, all commits pushed to `origin/main`. Full regression suite green (343/343, zero skipped) throughout. Nothing mid-flight.

## What happened

1. **Resolved `cmd_tech_debt()` silent no-op on stale entries**: The open `knowledge/TECH_DEBT.md` entry documenting that `cmd_tech_debt()` silently no-ops on stale-hashed entries was addressed via `triapi plan`/`dispatch` run `20260904-153223-7b117e` (commit `5316e79`). `_ENTRY_RE` and `check_staleness()` in `scripts/tech_debt.py` now treat `HASH: n/a` as always-fresh, and `cmd_tech_debt()` in `scripts/triapi.py` was updated to print visible notices for skipped stale entries.
2. **`knowledge/TECH_DEBT.md` corruption incident caught and repaired**: Run `20260904-153223-7b117e`'s own rebuild-failure path corrupted the real `knowledge/TECH_DEBT.md` by dumping ~90 lines of raw unbounded test/build output into it as a tech-debt `REASON` field (root cause: `scripts/dispatcher.py`'s `handle_fix_forward()` formatted an f-string `reason` with unbounded `build_output`). Caught via manual verification before pushing; got user approval and dispatched a second fix (run `20260904-154839-ccfa17`, commit `e8d68a2`) that truncates and single-lines `build_output` before logging, added a regression test in `tests/test_branch_features.py`, and cleaned the corrupted doc back to its one legitimate entry.
3. **Pipeline false-positive `build_failed` verification bug**: During run `20260904-154839-ccfa17`, the pipeline's own build verification for a step falsely reported `build_failed` three times in a row across tiers (`tier_4`, `tier_3`, `tier_2`), even though the on-disk file at that exact content hash independently compiled and passed the full test suite when run manually outside the pipeline. Had to state-patch the run's stored result in memory to success by hand after independent verification (commit `e8d68a2`, state-patch in-memory only). Rather than chasing the false-negative bug mid-session, queued it as new tech debt in `knowledge/TECH_DEBT.md` (commit `15056ff`).
4. **`triapi tech-debt` live run, auto-removal of design-gap entry, and size-ceiling block**: Per user direction ("work on it now"), ran `triapi tech-debt --project-dir .` (run `db9caae9-7211-41a3-8f5d-03b316a37b87`). This resolved and auto-removed the original `n/a`-hash design-gap entry by implementing the full `verify_cmd` re-check option in `cmd_tech_debt()` (a superset of the earlier print-only fix; stale entries now re-run their verification command before being discarded, and if passing, are treated as resolved and auto-removed) — committed as `6e56fdc`. The second item (investigating the false `build_failed` report in `scripts/dispatcher.py`) hit `human_handoff`: every tier's proposed fix would have pushed `scripts/dispatcher.py` over the 73,728-character Tier 4 ceiling (file is currently at 73,672 chars), so the content guard correctly refused the write and left the file untouched. That entry remains open in `knowledge/TECH_DEBT.md`, flagged as requiring a file-split-first approach before dispatching a fix.
5. **Operational caution on `triapi tech-debt`**: For future sessions, note that `triapi tech-debt --project-dir .` is NOT a read-only check — it is a live dispatcher that mutates real files and can re-trigger unsupervised fix cycles; don't invoke it casually as a verification step.

## Doc sizes at session end (all under the 73,728-char ceiling)

AGENTS.md 22,339 · CARRYOVER.md 23,175 · PLAN.md 19,147 · ARCHITECTURE.md 10,765 · README.md 16,512 · AGENT_GUIDE.md 43,436 · knowledge/TECH_DEBT.md 1,228.

*(Note: `scripts/dispatcher.py` is at 73,672 chars, leaving only 56 chars headroom below the 73,728 ceiling; it must be split before further additions).*

## Open / carried forward

- **`scripts/dispatcher.py` false `build_failed` bug** — open in `knowledge/TECH_DEBT.md` (commit `15056ff`). Needs a file-split-first approach on `scripts/dispatcher.py` to restore headroom below the 73,728-char ceiling before the root cause in `run_build()`/`verify_task()` can be safely patched.
- **Operational rule**: `triapi tech-debt --project-dir .` is an active dispatcher, not a passive status check.
- **SemAI Phase 8 (full agentic mode)** — remains queued in SemAI's own carryover.

## Next Steps

Next session should split `scripts/dispatcher.py` to create headroom, then investigate and fix the false-negative build verification issue in `scripts/dispatcher.py`. Alternatively, resume normal supervision or SemAI Phase 8.
