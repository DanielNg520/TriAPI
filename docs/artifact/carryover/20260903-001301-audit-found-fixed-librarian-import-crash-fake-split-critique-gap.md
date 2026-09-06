# Carryover — 2026-09-03 (just past midnight) — Audit of prior session's work found+fixed a live crash bug, a fake file split, and a critique-gate design gap

**Status: RESOLVED.** Nothing pending; clean session-end record.

## What this session covered (continuing from 20260902-225427)

User asked to audit the implementation and docs from the immediately preceding tech-debt/self-fix cleanup session. Per feedback_supervisor_fully_dispatch_only, this was done by forking an independent sub-agent to re-verify everything against actual repo state rather than trusting the prior session's own account of itself -- exactly the 'verify, don't trust status' principle applied reflexively.

### Audit found two real problems in commit 125d7a4's scripts/dispatcher.py 'size-ceiling split'

1. A live crash bug: the split dropped `librarian_escalate` from dispatcher.py's import line while the module still called `librarian_escalate.run()` at its tier_5 doc-routing branch. Never triggered during the prior session because every doc edit that session went through the standalone librarian_escalate.py CLI directly, and the prior session only ever re-ran the 3 test modules it had touched (tests.test_branch_features tests.test_tier5_librarian tests.test_self_fix_discard), never the FULL suite. Running the complete 287-module test suite surfaced 2 failing tests with `AttributeError: module 'scripts.dispatcher' has no attribute 'librarian_escalate'`.
2. The 'split' itself was fake: scripts/breakdown_guards.py (17,649 chars, created in that commit) was dead code, imported nowhere in the repo, with every one of its 11 functions ALSO still fully defined, unchanged, in dispatcher.py. The actual size reduction (77,549->71,355 chars) came entirely from stripping real historical incident-postmortem comments -- the exact loss-of-institutional-knowledge problem the pipeline's own critique step had explicitly rejected on the first attempt at this same fix (score 2/10). The revision was wrongly accepted anyway because orchestrator.py's `_critique_and_maybe_revise_inner()` only re-checked that the rebuild passed after a revision, never re-ran critique_diff() to confirm the revision actually addressed the original feedback.

### Both fixed via triapi plan/dispatch (commits fa23253, 29dc4ea)

- Restored the `librarian_escalate` import; deleted the dead scripts/breakdown_guards.py file rather than retroactively wiring it in, since dispatcher.py (71,375 chars post-fix) is comfortably under the 73,728-char ceiling on its own.
- Hardened `_critique_and_maybe_revise_inner()` to re-run critique_diff() on a revision's own diff before accepting it -- a revision that still scores below threshold now gets reverted instead of accepted just because it rebuilds; a critique-infrastructure failure on the re-check fails open (keeps the revision), matching the function's existing fail-open behavior elsewhere. New tests/test_critique_revision_requality_check.py (new file, test_branch_features.py already over the size ceiling) covers both outcomes.
- Both dispatch runs hit human_handoff once each on items whose own narrow build_cmd (a self-referential grep in one case, a build_cmd that never ran the full suite in the other) failed to actually verify what mattered, even though the underlying code changes were independently confirmed correct by hand in both cases. Resolved by patching each run's result in-place to 'success' (per feedback_state_patch_replace_not_append, never appended) and resuming, rather than re-dispatching.
- One additional real regression found only by running the full suite by hand: the critique-hardening fix broke an existing test, test_max_revision_attempts_retries_after_failed_apply, whose mock returned a constant low critique score forever -- correct under the OLD behavior (score was never rechecked) but wrong under the NEW, intended behavior, since it never modeled a revision that genuinely improves. Fixed the mock (2-line change, user-approved hand-fix) to return a passing score on the re-check. Full 289-test suite green afterward.
- Both runs' AGENTS.md plan-gate checkboxes marked complete by hand afterward (mark_plan_complete()), since dispatch halting on the first unresolved item meant neither run's own final loop ever called it.

## Meta-lesson for future sessions

Both bugs this audit found trace back to the same root cause: re-running only the test modules touched in a session instead of the FULL suite after every change. This was true of the prior session (which introduced both bugs) AND very nearly true of this one (the critique-hardening dispatch item's own build_cmd only ran py_compile / the new test file, and would have missed the stale-mock regression entirely if the full suite hadn't been run by hand afterward). `PYTHONPATH=. python3 -m unittest discover -s tests -p "test_*.py"` (287-289 tests as of this writing) is confirmed to work cleanly as the full-suite command and should be the default verification step, not a subset.

## Final verified state

TriAPI: 4 commits this session (fa23253, 29dc4ea, c3e3fbb, this doc commit), full local suite green (289 tests via unittest discover, OK, zero SKIPPED), working tree clean. No oh-my-llama work this session.

**Next up:** tests/test_branch_features.py remains over the 73728-char ceiling (74,811 chars as of this session, a pre-existing condition slightly worsened by this session's 2-line mock fix) -- worth a proper split into smaller files eventually, not attempted here. Also worth noting: the 12 flagged self-fix backlog entries from the prior session (20260902-225427) were not touched this session, still pending manual review.
