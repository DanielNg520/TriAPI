# dispatcher.py split complete; original false-build_failed bug root-caused and fixed

**Date:** 2026-09-04 **Status:** RESOLVED

## What happened

TriAPI run `20260904-172545-dd6087` split `scripts/dispatcher.py` (73,672
chars, at the repo's 73,728-char file-size ceiling) into
`scripts/dispatcher_git.py`, `scripts/dispatcher_breakdown.py`, and
`scripts/dispatcher_verify.py`, leaving `dispatcher.py` at ~61KB with real
headroom. Full suite green (344/344, zero skipped) throughout. Committed
and pushed as `1bb3c7c`.

The split itself needed three hand-fixes along the way (approved live,
each verified with the full suite before continuing):

1. An empty/garbled Tier-3 fix-forward response could get applied to
   disk; when the relocation-guard then caught the resulting corruption
   it flipped the item to `build_failed` **without reverting the file**
   (unlike its sibling failure branch just above it, which does revert).
   Fixed in `scripts/dispatcher.py`'s `handle_fix_forward()` by threading
   a `snapshot_path` through so the relocation-check branch reverts too.
2. Tier 3's "move" of `breakdown_phase()` wasn't verbatim -- a simplified
   rewrite missing the dense-bullet-split recursion, RPD-vs-RPM retry
   handling, and model-fallback-chain logic, returning a different shape
   entirely. Hand-copied the real logic verbatim into
   `scripts/dispatcher_breakdown.py` (diffed byte-for-byte against the
   source), also relocating `_backstop_context_files`/`_FILE_REF_RE`
   there to avoid a circular import the plan hadn't accounted for.
3. The split broke 4 test files with stale `dispatcher.X` references for
   symbols that moved to `dispatcher_breakdown` -- the pipeline's own
   `build_cmd` checks only compile the touched file, not the full suite,
   so this slipped through until a manual full-suite run caught it.
   Fixed all 4 test files' `mock.patch`/import targets.

## The original bug, finally root-caused

The false-`build_failed` bug queued in `knowledge/TECH_DEBT.md`
(originally from run `20260904-154839-ccfa17`) was the actual motivation
for doing the split at all -- investigating it required editing
`dispatcher.py`, which was blocked at the ceiling.

Once the split freed up headroom, the plan's own Phase 6/7 (automated
investigation + fix) **misdiagnosed the bug entirely**: Tier 2 concluded
"wrong cwd" (false -- every real call site already passes the correct
`workdir`/`project_dir`), and Tier 4's "fix" was a wrapper assuming a
`run_build()` signature that doesn't exist (`cwd=`/`project_dir=`
keyword args), which would have crashed **every real build check across
the whole pipeline**. Caught before commit, reverted by hand, verified
working again (344/344 green).

Re-reading the *original* incident's own logs by hand found the real
root cause: `scripts/scope_guard.py`'s `detect_relocation_intent()`
matches the bare word "split" from its `_RELOCATION_VERBS` list *inside*
unrelated `.split()` method calls. The original item's description used
`" ".join(build_output.split())` -- the literal Python idiom, not a
relocation instruction -- which triggered the relocation-verb check, and
then `build_output` (a local variable, never a def/class) was extracted
as a "relocation target" and reported "missing," permanently failing
three genuinely successful tier attempts (tier_4, tier_3, tier_2) in a
row on the *original* run.

**Fixed** with a negative-lookbehind on the verb regex
(`(?<!\.)\b{verb}\b`) in `scripts/scope_guard.py`, with a real regression
test added to `tests/test_relocation_guard.py`
(`test_method_call_named_after_verb_is_not_relocation_intent`).

## Three more variants of the same false-positive class, found live during the split itself

All in `scripts/scope_guard.py`'s `detect_relocation_intent()` /
`symbol_exists_in_project()`:

- Shell `Verify: ...` commands (e.g. `py_compile`) and a destination
  module's own filename/import path (`dispatcher_git.py`,
  `scripts.dispatcher_git`) were being swept up as bogus relocation
  targets. Fixed: truncate at `Verify:`, exclude `f"{sym}.py"` and
  `f"scripts.{sym}"` matches.
- A parenthetical aside/caveat (an "out of scope"/"do NOT" note, an
  "e.g." example) and bare all-caps acronyms used as ordinary prose
  (`NOT`, `LLM`, `PLAN`) were also swept up. Fixed: strip parenthetical
  spans before extraction; require a PascalCase-shaped match to also
  contain a lowercase letter (not just internal uppercase).
- `symbol_exists_in_project()` only checked `def`/`class` patterns, never
  module-level constant assignments -- this separately false-flagged a
  correctly-reused constant (`BREAKDOWN_SYSTEM_INSTRUCTION`, which Tier 3
  correctly imported from its existing home in `breakdown_prompts.py`
  rather than duplicating). Fixed: also check `NAME = ` / `NAME: `
  assignment patterns.

## Tech debt

Both `knowledge/TECH_DEBT.md` entries for these bugs are removed --
genuinely resolved, not just worked around. `TECH_DEBT.md` is back to
just its header, no open entries. Self-fix backlog also empty (no
unqueued bug reports, no drafted-awaiting-approve runs).

## On-hold items (re-carried, not touched this session)

Per standing practice, explicitly re-carrying these so they don't
silently drop out of tracking:

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
per-module detail.

Superseded the
`20260904-165751-tech-debt-corruption-incident-and-false-buildfail-bug.md`
file once this session's work fully landed.
