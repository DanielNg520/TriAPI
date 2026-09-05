# Session-end clean handoff: dispatcher split + bug root-caused + doc audit complete

**Date:** 2026-09-04 **Status:** RESOLVED -- nothing in flight, safe to start fresh.

## Summary of this session

Three pieces of work, all committed and pushed to `main`, full suite
green (344/344, zero skipped) at every step:

1. **`scripts/dispatcher.py` split** (run `20260904-172545-dd6087`,
   commit `1bb3c7c`): was at 73,672/73,728 chars, blocking any edit to
   it. Split into `dispatcher_git.py`, `dispatcher_breakdown.py`,
   `dispatcher_verify.py`; `dispatcher.py` now ~61KB with real headroom.
   Needed three hand-fixes along the way (a file-corruption bug in
   `handle_fix_forward()`'s relocation-check interaction; a non-verbatim
   `breakdown_phase()` move that would have broken `breakdown_plan()`;
   4 test files left with stale post-split references) -- see the
   superseded 204800 file for the full blow-by-blow if debugging a
   regression in this area.

2. **The false-`build_failed` bug root-caused and fixed** (the actual
   motivation for the split -- it was queued in `knowledge/TECH_DEBT.md`
   and needed editing `dispatcher.py`, which was blocked at the
   ceiling). Root cause: `scripts/scope_guard.py`'s
   `detect_relocation_intent()` matched the bare word "split" inside
   unrelated `.split()` method calls in an item's own description text,
   misreading ordinary Python code as a relocation instruction and
   flagging local variables as "missing" targets. Two automated tier
   attempts misdiagnosed this first (one wrong theory, one fix that
   would have crashed every build check pipeline-wide) -- both caught
   and reverted before landing. Real fix: negative-lookbehind on the
   verb regex, plus 3 more variants of the same false-positive class
   found and fixed along the way (Verify-command/filename tokens,
   parenthetical asides, missing constant-assignment detection in
   `symbol_exists_in_project()`). Regression test in
   `tests/test_relocation_guard.py`. Both `TECH_DEBT.md` entries for
   this are now removed -- `TECH_DEBT.md` is back to just its header,
   **no open entries**.

3. **Doc audit** (run `20260904-211220-428acb`, commit `490a812`, user
   request): `AGENTS.md`'s stale scripts module list replaced with a
   durable pointer; `README.md`'s two dead `ollama pull` lines removed
   and its Tier-4-default wording corrected (default is now the
   `minimax` OpenRouter model, not local Ollama); `ARCHITECTURE.md`'s
   stale Tier-2/Google-free-tier budget-guard bullet removed. One item
   hit a self-referential verify-cmd false-negative (the plan's own
   appended text momentarily quoted the string its check searched for)
   -- verified correct by hand.

## Current state -- nothing in flight

- `knowledge/TECH_DEBT.md`: **empty**, no open entries.
- Self-fix backlog: **empty** (no unqueued bug reports, nothing
  drafted-awaiting-approval).
- Working tree: clean, `main` up to date with `origin/main`.
- Full suite: 344/344, zero skipped.

## On-hold items (re-carried -- do this every session or they vanish from tracking)

- `VIRTUAL_CODEBASE_PLAN.md` -- Tiered Planner-Materializer design for
  large-file Tier 4 edits. Status: queued design reference, not started.
  User wants to work on this together personally -- never start solo.
- `docs/TUI_plan.md` -- confirmed `triapi tui` subcommand spec. Status:
  not planned/dispatched yet; the blocker that originally deferred it
  (an in-flight tier-flip dispatch) cleared long ago. Open design
  questions still need the user before running this through `triapi
  plan`.

## Reference

`docs/agents/20260825-100000-scripts-directory-reference.md`'s
`scope_guard.py` and `dispatcher_verify.py` entries have the fuller
per-module detail on the split and the relocation-guard fixes.

Supersedes
`20260904-204800-dispatcher-split-plus-relocation-guard-root-cause-fixed.md`
(which itself superseded the 165751 file) now that the doc audit landed
too and there's nothing left mid-flight.
