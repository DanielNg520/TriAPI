# 2026-08-28 10:00 UTC — ACTIVE: full queue drained (5 items), dispatcher.py split to relieve file-size ceiling, docs caught up; nothing mid-flight

**Working tree is clean, no paused run, no pending approval.** `git log -1`
should show `ae566e6` (or later) as `HEAD`. Safe to start fresh work
immediately.

## What happened this session

User asked to "continue to drain the queue" against the 5 items left open
by `20260828-090500-agy-argv-fix-tier1-planner-moved-off-openrouter.md`.
All 5 are now resolved and committed, plus one file-size proactive fix and
a docs catch-up, hand-fixed directly per the standing pipeline-broken
exception already established this week (not re-litigated this session).

## Landed and committed

1. **Multi-turn planner statelessness — RESOLVED** (`f28af99`). Root cause:
   `triapi.py`'s loop only ever sent the caller's latest reply, and
   `planner.py`'s non-`'cli'` path (no server-side session) had no memory
   of earlier turns. `triapi.py` now accumulates a `history` list of
   `{user, assistant}` pairs; `planner.py` renders it into the prompt.
   Live-verified: a real two-turn sequence ("add hello print" → "make it
   goodbye instead") correctly revised the plan instead of losing the
   goal. `tests/test_planner_multiturn_history.py`.
2. **Sanity check on `triapi plan`'s own output — RESOLVED** (`8b2ff71`).
   `planner.detect_degenerate_plan()`: fast, no-LLM-call heuristic
   flagging fabricated tool-call markup, truncated/short output, and
   degenerate repeating content. `triapi.py`'s `cmd_plan()` now requires
   an explicit second `'approve'` when a turn is flagged — a blind piped
   single `'approve'` hits `EOFError` on the re-confirmation and aborts
   instead of silently approving garbage. `tests/test_planner_degenerate_plan_guard.py`,
   `tests/test_triapi_flagged_approval_gate.py`.
3. **`py_compile`-insufficient default verify command — RESOLVED**
   (`0b6cc30`). `_default_build_cmd()` for a `tests/test_*.py` target now
   runs the module via `unittest` instead of syntax-only `py_compile`.
   Live-verified against a real fabricated test file (importing a
   nonexistent module): `py_compile` passed it cleanly, the new default
   failed loudly. `tests/test_dispatcher_default_build_cmd.py`.
4. **Bare `grep -i 'skipped'` false-positive — RESOLVED (prompt-level)**
   (`cf325ad`). Added a THIRD SPECIAL CASE to
   `BREAKDOWN_SYSTEM_INSTRUCTION` (now in `scripts/breakdown_prompts.py`,
   see item 6) steering the breakdown model toward unittest's real
   anchored skip syntax instead of an unanchored substring match. This is
   prompt guidance, not enforced code — cannot be unit-tested for
   compliance, only that the guidance text exists
   (`tests/test_breakdown_prompt_skip_guidance.py`).
5. **Tier 3 out-of-scope-edit pattern — RESOLVED (advisory)** (`b57579e`).
   New `scripts/scope_guard.py`: `find_out_of_scope_functions()` compares
   the function/class names git's own diff driver tags each hunk with
   against what the item's description names, flagging (never blocking)
   an edit that touches a function the description didn't mention.
   Wired into `dispatcher.py`'s `dispatch()` loop after every successful
   regular item, attaching `scope_concerns` to the result entry — same
   non-blocking pattern `mock_patch_lint`'s test-file findings already
   use. `tests/test_scope_guard.py`, `tests/test_dispatcher_scope_guard_wiring.py`.
6. **`dispatcher.py` file-size proactive split — RESOLVED** (`78c194d`).
   Item 5's own commit pushed `dispatcher.py` to 72906/73728 chars
   (~99% of this repo's ceiling). Extracted the ~9.6KB
   `BREAKDOWN_SYSTEM_INSTRUCTION` prompt constant (pure text, zero logic)
   into a new `scripts/breakdown_prompts.py`, re-exported unchanged via
   `from scripts.breakdown_prompts import BREAKDOWN_SYSTEM_INSTRUCTION` so
   `dispatcher.BREAKDOWN_SYSTEM_INSTRUCTION` keeps working for existing
   callers. `dispatcher.py`: 72906 → 63659 chars.
7. **Docs caught up** (`ae566e6`), via `scripts/librarian_escalate.py`
   per convention. `docs/agents/20260825-100000-scripts-directory-reference.md`'s
   `dispatcher.py` bullet now documents all of items 3, 5, and 6 above
   (item 4 is prompt-only, already self-documenting in the constant
   itself). This same edit also closed out the one remaining item from
   stalled run `20260827-234324-b88ea5` (`stopped_on_failure`, 7/13 —
   its actual code changes, `_resolve_dynamic_target` + tests, were
   already completed and committed in a later session per
   `20260828-082044-...md`; only this doc note was ever outstanding).
   That run is now safe to ignore/let lapse — nothing left to resume.

Full suite after every commit: 243 tests, OK (final count; grew from 219
at session start as each fix added its own regression tests).

## Standing rules (accumulated, still in effect)

All rules from prior files still apply unchanged. Nothing new this
session beyond what's already documented — this was pure queue-draining,
no new incidents or process changes.

## Next up (priority order)

Everything from the previous file's "Next up" list is now done except:

1. Older carried-forward items (unchanged, still open): `cost_log.jsonl`
   size split (~858KB), `git_ops.push()`'s unconditional `git add -A`
   scoping gap, OpenRouter `[PHONE]` filter root-cause, Groq provider
   addition, architecture items (backend registry, complexity router,
   per-tier fallback toggles).
2. No new bugs surfaced this session to add to the queue.

**Separately, on hold for the user (unchanged across sessions):**
- **Virtual Codebase Plan** (`VIRTUAL_CODEBASE_PLAN.md`).
- Consolidate target-repo-specific content out of TriAPI's own docs --
  goes through TriAPI itself, not hand-drafted.
- `docs/TUI_plan.md` -- still untracked/unplanned.

*(No further prior-file detail needed to resume — this file is
self-contained for "what's the current state.")*
