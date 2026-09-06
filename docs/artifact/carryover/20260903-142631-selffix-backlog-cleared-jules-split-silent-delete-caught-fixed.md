# Carryover — 2026-09-03 (afternoon) — Self-fix backlog cleared to zero; test-file split found a real silent-deletion bug in the dispatch pipeline itself, hand-fixed with approval

**Status: RESOLVED.** Nothing pending; clean session-end record. One new systemic gap queued below for a future `triapi plan` session.

## What this session covered (continuing from 20260903-001301)

User asked to resume TriAPI housekeeping: clear the 12 unclassified self-fix backlog entries flagged by the prior session, and split `tests/test_branch_features.py` (74,811 chars) under the 73,728-char ceiling. Mid-session the user explicitly reaffirmed full-dispatch-only supervisor mode.

### 1. Self-fix backlog manually reviewed and cleared 12 -> 0

Read every one of the 12 entries (5 unqueued bug reports + 7 drafted-but-unapproved self-fix runs) against *current* repo source, not just their dates, and confirmed each one's root cause is already fixed by a later commit:
- `remnants` sops decrypt failure -- `.sops.yaml` creation-rule mismatch, resolved same day (file re-encrypted, mtimes match).
- `fix-planner` list-indices TypeError -- stale resumed-run state schema; current `breakdown_plan()` always inits `state["breakdown"]["phases"]` as a list.
- `20260823-154515...` "Tier 1 failed: None" -- `tier1_escalate.escalate()` now has exactly one error-status return path and it always formats a real reason string; can no longer produce a None reason.
- `...spzo74sv` probe `Invalid URL 'None/v1/...'` -- was tier_5_librarian pointed at an OpenAI-shaped provider with a missing endpoint; tier_5_librarian is now `agy`, a different code path entirely.
- `...q67ds363` `librarian_escalate.run() got build_cmd` -- the dispatcher call site now passes `verify_cmd=build_cmd`, confirmed in current `dispatcher.py`.
- 4 drafted `unittest-*`/`tmp*` runs -- confirmed synthetic `SelfFixTests` suite fixtures (literal content `"ValueError: bad"` / `"X: x"`), not real crashes.
- `9f5b8e` missing `anthropic_api_key` -- current `secrets_loader.py`'s required-keys list no longer includes that key at all.
- `a25d29` probe timeout on `localhost:11434` -- tier_5_librarian no longer runs on local Ollama.
- `52402d` `extract_code()` NoneType crash -- `llm_client.py` already has an explicit null-content guard whose own comment cites this exact run ID as the reason it was added.

All 12 discarded via the existing `triapi self-fix discard <id>` command (routine backlog administration through the tool's own interface, not a code change; `logs/` is gitignored so nothing to commit for this part).

### 2. `tests/test_branch_features.py` split via `triapi plan`/`dispatch` (run `20260903-064926-265e55`, commit `c6a799e`) -- found a real silent-deletion bug

Plan: move the 8 Jules-related test classes into a new `tests/test_jules_client.py`, following this repo's established "split cohesive test groups into their own topic file" convention. Dispatched cleanly: step 1 (create new file) resolved by tier_4, step 2 (delete moved classes from the old file) resolved by tier_2, both reported `success`.

**Per `feedback_verify_dont_trust_status`, ran the full suite by hand instead of trusting the "success" status -- it caught a real bug the pipeline's own status missed:** 2 of the 8 classes (`CheckJulesOkTests`, `BreakdownDispatchJulesHookTests`, 5 test methods) were silently *deleted*, present in neither file. Full suite dropped from 289 to 284 tests, still fully green (deletion, not breakage, so nothing failed). Root cause: tier_2's own `build_cmd` for the delete step *did* run the full `unittest discover` suite, but a pure delete-with-nothing-broken always exits 0 -- the build_cmd checks "does the suite still pass," never "does the suite still have the same test count / do the removed symbols exist somewhere." The run's own `scope_concerns` field (from `scope_guard.py`) correctly flagged both classes' symbols as removed, but scope_concerns are advisory-only and did not block the item from being marked `success`.

User approved a hand-fix (not a redispatch) given the low risk: restored both classes verbatim from git history (`532ff28`) into `tests/test_jules_client.py` with the imports they actually need (`budget_guard`, `io`, `json`, `time`, `tempfile`, `Path`, `triapi`). Full suite back to 289/289 green, zero skipped. Both files now comfortably under the ceiling (`test_branch_features.py` 64,218 chars, `test_jules_client.py` 10,704 chars). Committed as `7b20572`.

## New systemic gap queued for a future `triapi plan` session (not fixed this session -- real code work, not doc/backlog housekeeping)

**File-split/move tasks have no verification that content actually moved rather than vanished.** Two independent gaps compound: (1) a "move N things from file A to file B" item's `build_cmd` only proves the *resulting* suite passes, never that the *same* test count survives or that each named symbol landed somewhere; (2) `scope_guard.py`'s `scope_concerns` are logged but advisory-only -- they never block a `success` verdict even when a concern names a symbol that turns out to have been deleted outright, not relocated. This is the same root-cause shape (weak/absent verify_cmd for a move/split, not a build/behavior change) as the fake `breakdown_guards.py` split caught in the 20260903-001301 session -- two sessions in a row have now found a real split task silently losing content that its own "success" status didn't catch. Worth a `triapi plan` item: either have split/move `build_cmd`s assert equal test count (or equal enumerated-symbol presence) before/after, or promote scope_concerns naming a symbol absent from every target file post-edit to a hard failure. No deadline given.

## Final verified state

TriAPI: 2 commits this session (`c6a799e` from the dispatch, `7b20572` the hand-fix restoration), full local suite green (289 tests via `unittest discover`, OK, zero SKIPPED), working tree clean. No oh-my-llama work this session -- its own open item (Phase 8, full agentic mode) was surfaced to the user at session start and explicitly deferred in favor of this TriAPI housekeeping.
