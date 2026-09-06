# Carryover — 2026-09-03 (afternoon, continued) — Relocation-guard hard-fail shipped; caught+fixed a P0 crash it exposed in its own dispatch run; tier_3_debugger peak_alt swapped to minimax-m3

**Status: RESOLVED.** Nothing pending in TriAPI. RAG/memory design plan requested by the user is queued next (was blocked by this run's own AGENTS.md plan-gate until it completed).

## What this session covered (continuing from 20260903-142631)

After the self-fix backlog clear and Jules-split bug fix (see 20260903-142631), the user pushed back hard on two things and both changed how this session proceeded:

1. **"Bookkeeping should never be your concern with a pipeline like triapi"** — caught routing an already-fully-authored carryover file through `librarian_escalate` just to have a tier retype it verbatim, pure LLM-round-trip overhead. Narrowed `feedback_use_librarian_for_doc_edits`: write directly when the supervisor already composed the exact final text; reserve the librarian for content a tier should actually draft. This file, and this session's other doc writes, were written directly per that narrowed rule.
2. **"We have to address this issue... TriAPI is there to assist you not you babysit them"** — the systemic gap flagged in the previous carryover (a move/split item's build_cmd only proves the resulting suite passes, never that content/test-count survived; scope_guard's flag is advisory-only) was escalated from "queued for someday" to "fix it now through triapi itself."

### Relocation-guard hard-fail plan drafted, approved, and dispatched (run `20260903-074835-818725`)

Plan: `scope_guard.py` gets `extract_named_symbols()`/`detect_relocation_intent()`/`symbol_exists_in_project()`; `dispatcher.py`'s dispatch loop hard-fails (not just advisory) when an item's own description names a symbol as being moved/split/extracted and that symbol is missing from the entire project after the edit. Phases 1-2 (4 steps) landed clean. Phase 3 (`tests/test_relocation_guard.py`) hit `human_handoff` after Tier 4→3→2→1 all failed the same way: the test-writing tier invented its own guessed API (`dispatcher.check_relocation_guard(source=, destination=, description=)`) instead of checking the real Phase 2 code — none of the 4 tiers looked at the actual implementation before writing the test.

### P0 found while investigating the human_handoff: TriAPI's dispatch pipeline was completely broken for every future run

`git diff` on `scripts/scope_guard.py` after Phase 1/2 both reported `success` (both `resolved_by=tier_3`) showed only a 4-line cosmetic dedup refactor — **`detect_relocation_intent()` and `symbol_exists_in_project()` were never actually written to disk**, despite two separate tier_3 steps claiming success for adding them. Root cause: their `build_cmd` was only `python3 -m py_compile scripts/scope_guard.py` — a syntax check that passes identically whether the function was added or the file was left untouched. Meanwhile Phase 2 Step 2 (`tier_4`, correctly implemented) wired `dispatcher.py` to call both functions **unconditionally on every dispatch item**. Confirmed via direct repro: `PYTHONPATH=. python3 -m unittest tests.test_branch_features.DispatcherHookAndFixForwardTests.test_successful_item_passing_judge_calls_extract_pattern` crashed with `AttributeError: module 'scripts.scope_guard' has no attribute 'detect_relocation_intent'`. This would have crashed the very first item of the next fresh `triapi dispatch` invocation on ANY run -- it only hadn't crashed yet because the still-running dispatch process had the pre-edit `dispatcher.py` loaded in memory before Phase 2 wrote its change to disk.

This is the third occurrence this week of the same shape: a tier reports `success` on a too-narrow (`py_compile`-only, or move/split-blind) `build_cmd` without actually doing the described work (see also: the fake `breakdown_guards.py` split and the Jules-class silent deletion, both in this session's own recent history).

### User-approved hand-fix (commit `637d0d1`)

- Added both missing functions to `scope_guard.py`. `extract_named_symbols()` uses an identifier-shape heuristic (PascalCase or underscore-containing tokens) rather than reusing `find_out_of_scope_functions()`'s git-diff-only regexes — a since-reverted earlier tier attempt at this exact function had tried that reuse and it silently breaks on plain-English descriptions (confirmed by a lesson the run's own design judge had already extracted into `knowledge/hivemind.md` from that failed attempt, kept as-is: it's an accurate, useful lesson despite coming from a diff that got hard-failed downstream).
- Rewrote `tests/test_relocation_guard.py` against the real API: two unit tests for `detect_relocation_intent()`, two for `symbol_exists_in_project()`, two integration tests exercising the real `dispatcher.dispatch()` call site (mirroring `tests/test_branch_features.py`'s `DispatcherHookAndFixForwardTests` mocking conventions). Note: `reason` is logged (`log.warning`) but never persisted into `state["results"]` entries anywhere in this codebase's existing convention (confirmed by grep across `dispatcher.py`/`orchestrator.py`) — the test asserts against the log via `assertLogs`, not a nonexistent `entry["reason"]` field; this is pre-existing, consistent behavior, not something this fix needed to change.
- Also noted, not fixed (separate, lower-severity, out of this fix's approved scope): the design judge's `extract_pattern()` call fires *before* the relocation hard-fail check in `dispatcher.py`'s item-processing order, so a relocation-violating diff's pattern can still get written to `hivemind.md` before the same item gets hard-failed a few lines later. Worth a future look, not urgent.
- Full suite: 295/295 green (was 289 baseline, +6 new relocation-guard tests), zero skipped, confirmed both before AND after this hand-fix.
- `knowledge/TECH_DEBT.md` picked up one new entry (a Tier 3 `agy` CLI failure during Phase 3's escalation attempts) as ordinary pipeline fallout — hash-staleness convention applies as usual, no action needed.

### Config: tier_3_debugger peak_alt swapped to minimax/minimax-m3:free (commit `55d4443`)

User request, prompted by a stale comment claiming `dots-3-note-preview:free` still occupied this slot. Verified live: `dots-3-note-preview` is not configured anywhere in `config/tiers.yaml` anymore — it was tier_1_planner's model on 2026-08-28 (moved off the same day for hallucinating fake tool-call syntax), demoted to `tier_3_debugger`'s `peak_alt` secondary, then swapped again by a later untracked commit to `nvidia/nemotron-3.5-lightning:free` without updating the explanatory comment. Now `minimax/minimax-m3:free`; both the stale comment and the actual value are corrected. Full suite reconfirmed green after this change.

## Plan-run bookkeeping for `20260903-074835-818725`

Phase 3's `human_handoff` item and all 4 of Phase 4's items were independently hand-verified (not tier-dispatched) as described above and in the docs updated by this same commit sequence, per user-approved hand-fix. `docs/carryover/index.json` and `CARRYOVER.md`'s ACTIVE row were updated to point to this file in the same edit that created it (see "Convention for adding a new entry" in `CARRYOVER.md`) rather than through a separate dispatched doc-drafting step, per the narrowed librarian-routing rule above. Run state and `AGENTS.md`'s plan-gate checkboxes for this run_id are being reconciled to reflect this completion so the plan-gate (`agents_md_gate.find_incomplete_plan`) no longer blocks a new `triapi plan`.

## Final verified state

TriAPI: 3 commits this half of the session (`637d0d1` P0 fix, `55d4443` config swap, this doc commit), full local suite green (295 tests via `unittest discover`, OK, zero SKIPPED), working tree clean after this commit. No oh-my-llama work this session.

**Next up:** the user asked for a RAG/memory design plan (to sit alongside `hivemind_util.py`/`lessons.py`, addressing multi-tier token-cost risk) to be drafted via `triapi plan` and reviewed before any dispatch — this was blocked by the relocation-guard run above and is being drafted immediately after this file is committed. Also still open, non-urgent: the design-judge-fires-before-hard-fail ordering note above.
