# 2026-08-28 10:50 UTC — ACTIVE: full-week audit complete (no regressions), live-caught + fixed a Tier 4 scope-creep bug during a supervised doc-fix dispatch, scope_guard blind spot fixed; nothing mid-flight

**Working tree is clean, no paused run, no pending approval.** `git log -1`
should show `5b40110` (or later) as `HEAD`. Safe to start fresh work
immediately.

## What happened this session

Two parts, both user-initiated.

### Part 1: Full-week audit (no code changes)

User asked to audit every fix made this week (2026-08-23 through
2026-08-28, ~55 commits, 14 carryover sessions). Ran 4 parallel fork
audits by date range, each verifying claimed fixes against actual diffs
and real (non-skip) test assertions, not carryover prose. **Result: no
functional regressions, no fake-skip tests, no silently-reverted-but-
still-claimed fixes anywhere in the whole week.** 5 minor cosmetic/doc-
accuracy issues were found (stale docstring timezone claim, a stale
"not yet confirmed" test note, one carryover timeline slip, one wording
nuance, one harmless redundant except-clause) — see the two items fixed
in Part 2 below; the other three (timeline slip, wording nuance,
redundant except-clause) are cosmetic-only and not queued for action.

### Part 2: Supervised `triapi plan`/`dispatch` doc fix — caught a real bug live

User asked to fix two of the audit's findings (stale docstring, stale
carryover note) through `triapi plan`/`dispatch` with active supervision,
not hand-edited. Plan text was read and approved (clean, no
hallucination, correctly scoped to exactly the two items asked).

**Dispatch of item 2 (carryover doc note) was clean** — verified diff is
a correct, minimal, appended-only note via `scripts/librarian_escalate.py`.

**Dispatch of item 1 (dispatcher.py docstring fix) was NOT clean.** The
item's own description explicitly said "Do not change any implementation
logic" for a docstring-only text correction
(`_is_deepseek_peak_hours()`'s docstring: America/Los_Angeles ->
Beijing). Tier 4 instead **deleted `_is_deepseek_peak_hours()` entirely**
and inlined its logic directly into `handle_fix_forward()`, changing the
log message format too — a textbook out-of-scope edit, auto-committed by
the pipeline (`db5fe8b`) because the item's own `verify_command`
(`python3 -m py_compile scripts/dispatcher.py`) only checks syntax, not
that other files' tests still pass.

Caught by supervision (`git diff`/`git show` review before trusting the
"success" status, per this repo's standing "verify, don't trust status"
rule) — NOT caught by `scope_guard.py` (added earlier today, meant for
exactly this failure class), which reported zero concerns. Confirmed
live the breakage: 4 test errors across `tests/test_dispatcher_peak_hours.py`
and `tests/test_tier_reassignment_prep.py`
(`AttributeError: module 'scripts.dispatcher' has no attribute
'_is_deepseek_peak_hours'`).

**Root-caused why `scope_guard.py` missed it, and fixed it** (`5b40110`):
git's diff hunk header anchors to whichever function *precedes* a
deletion in the pre-image context, not the deleted function's own name —
its `def` line is inside the hunk body, not before it. So a fully
deleted function's name never appears as any hunk's header context, and
the guard's "was the touched function named in the description" check
had nothing to match against `_is_deepseek_peak_hours` at all (it only
saw `_run_design_judge` and `handle_fix_forward` as touched). Fixed by
adding a second regex (`_BODY_DEF_RE`) that scans each hunk's own
added/removed body lines directly for `def`/`class` names, unioned with
the existing hunk-header extraction. Verified against the real diff from
`db5fe8b`: now correctly flags `_run_design_judge` and
`handle_fix_forward` while correctly NOT flagging
`_is_deepseek_peak_hours` itself (which *was* named in scope). New
regression test (`test_whole_function_deletion_is_flagged_via_body_scan`)
uses the real incident's diff shape verbatim.

**Corrected the actual regression** (`7c21561`): reverted Tier 4's
deletion/inlining back to the original working form, keeping only the
genuinely-requested docstring text change (Beijing, not
America/Los_Angeles). Done as a direct hand-fix, not re-dispatched — per
the user's explicit "you supervise" framing, this is a supervisory
correction of an already-landed bad pipeline commit, not new work that
should go through the pipeline again (which risks repeating the exact
same scope-creep).

Full suite after both fixes: **244 tests, OK.**

## Standing rules (accumulated, still in effect)

All rules from prior files still apply unchanged. One addition:

- **`scope_guard.py`'s hunk-header-only heuristic has a known-fixed blind
  spot on whole-function deletions** — now also scans hunk bodies
  directly (`_BODY_DEF_RE`), but it's still advisory/non-blocking, still
  heuristic, and still only as good as its regex coverage. Don't treat
  `scope_concerns: null`/absent on a dispatch item as proof an edit was
  in scope — it's a helpful signal, not a guarantee. Read the diff
  yourself before trusting a "success" status, same as always.

## Next up (priority order)

Nothing urgent queued from this session — both audit findings acted on
are resolved, the live-caught regression is reverted and verified, and
the gap that let it slip through (`scope_guard.py`) is fixed with its own
regression test.

Older carried-forward items (unchanged, still open): `cost_log.jsonl`
size split (~858KB), `git_ops.push()`'s unconditional `git add -A`
scoping gap, OpenRouter `[PHONE]` filter root-cause, Groq provider
addition, architecture items (backend registry, complexity router,
per-tier fallback toggles).

**Separately, on hold for the user (unchanged across sessions):**
- **Virtual Codebase Plan** (`VIRTUAL_CODEBASE_PLAN.md`).
- Consolidate target-repo-specific content out of TriAPI's own docs --
  goes through TriAPI itself, not hand-drafted.
- `docs/TUI_plan.md` -- still untracked/unplanned.

*(No further prior-file detail needed to resume — this file is
self-contained for "what's the current state.")*
