# Carryover — 2026-09-02 (late evening) — tech-debt backlog cleared, self-fix backlog groomed (72->12 entries), 3 more TriAPI bugs fixed

**Status: RESOLVED.** Nothing pending; clean session-end record.

## What this session covered (continuing from 20260902-191415)

User asked to 'call triapi to act on the tech debt and the backlog first.' Per feedback_supervisor_fully_dispatch_only, every fix went through triapi plan/dispatch, not hand-written -- except one narrow, user-approved hand-fix (see below) and reverting an already-broken uncommitted automated edit before it could be committed.

### 1. knowledge/TECH_DEBT.md's 9-entry backlog processed via `triapi tech-debt --project-dir .`

Dispatch run ac1f245d resolved all 4 fresh (non-stale-hash) TriAPI entries: config_loader.py (missing encoding="utf-8" on 3 open() calls, tier_3), test_run_build_pipefail.py (assertIs->assertTrue/assertFalse, tier_4), orchestrator.py (added a missing log line for Tier 3's "skipped" status, tier_2 after a critique-flagged first attempt correctly caught and reverted a regression that would have silently dropped a budget guard), and test_llm_client_sanitize.py -- this last one was NOT accepted: Tier 2's fix changed the import to a nonexistent `llm_client_sanitize` module and reported "success" only because cmd_tech_debt's hardcoded verify command never actually ran that specific test file. Caught by hand (ModuleNotFoundError on direct re-run), reverted before committing (git commit d5f666f covers only the 4 genuinely-good fixes). The 5 oh-my-llama-path entries and 2 stale TriAPI entries were correctly skipped by tech_debt.py's existing hash-based staleness filter.

### 2. Four real TriAPI bugs found+fixed via two further triapi plan/dispatch rounds (commits 125d7a4, 5e798f8)

- `cmd_status()` crashed with `KeyError: 'prompt'` on any run created by `cmd_tech_debt()`, whose synthetic run state never set that key -- fixed by adding it.
- `scripts/dispatcher.py` was already over the 73728-char Tier 4 ceiling (77549 chars); the critique gate correctly rejected a lazy comment-stripping first attempt (score 2/10) that didn't actually reduce size and deleted real incident-postmortem comments, then accepted a proper revision that split doc-target/context-file helpers into a new scripts/breakdown_guards.py module.
- Added `triapi self-fix discard <bug_id>` (scripts/triapi.py) to delete a stale captured bug report and/or its drafted-but-unapproved run -- the self-fix backlog had no cleanup mechanism at all, unlike TECH_DEBT.md's hash-based staleness check.
- `tech_debt.remove_resolved_entries()` now prunes TECH_DEBT.md once cmd_tech_debt resolves an entry, instead of leaving it forever; also manually trimmed two ~30-75KB garbage entries (raw multi-KB stdout/traceback dumps captured by log_tech_debt during transient mid-fix-loop failures on files that ultimately succeeded) out of TECH_DEBT.md by hand, since they were pipeline-generated log noise, not authored doc content.
- **One user-approved hand-fix** (per feedback_supervisor_fully_dispatch_only's approval requirement): cmd_tech_debt's first-pass build_cmd fix checked `entry['filepath'].startswith('tests/test_')`, but every real TECH_DEBT.md entry uses an absolute path, so the check could never fire in practice -- test-file targets silently fell back to the generic suite instead of getting their own targeted unittest run, the exact gap that let the test_llm_client_sanitize.py false-success slip through in the first place. Extracted a small `_tech_debt_build_cmd()` helper matching on the basename instead, user approved this one-line diagnosis+fix directly rather than a 4th dispatch round.
- New regression coverage went into a new file, tests/test_self_fix_discard.py, per this repo's established "split out, don't extend test_branch_features.py" convention (that file is already at the 73728-char ceiling, confirmed by a human_handoff when a dispatch item tried to append tests there directly).
- Also replaced a non-hermetic generated test (accidentally read real project TECH_DEBT.md state via cmd_tech_debt's hardcoded path instead of an isolated fixture, and passed for the wrong reason) with 3 direct unit tests of the pure `_tech_debt_build_cmd()` function.

### 3. Self-fix backlog groomed 72 -> 12 entries (commit 6d371bb)

New scripts/clear_stale_self_fixes.py classifies every `triapi self-fix list` entry as stale (bare tempfile-named 2026-08-15 test-development debris -- confirmed dead, not a live leak, by re-running the SelfFixTests suite and observing zero new files appear under logs/triapi_bugs/) or a real entry matching an exception signature already root-caused and fixed by a landed commit (429/404 tier_1_planner probes, gemini-2.5-flash-lite 403s, nvidia/nemotron KeyErrors, several other KeyErrors, the exact gemini-3.7-flash/gemini-3.1-pro crash-vs-soft-escalate bug fixed the same day in commit 85755cd, the ohmyllama IsADirectoryError resolved by the completed Phase 7 rename). Discarded 83 entries total across two idempotent passes (the first pass's discards surfaced previously-hidden linked bug reports, handled by re-running). 12 entries remain, genuinely unrecognized by the script's known-signature list (old secrets/config errors, early pipeline bugs predating several since-landed fixes, and a few obviously-synthetic test names using a different naming convention than the tmp* pattern) -- deliberately left untouched rather than guessed at; flagged for a future manual review pass, not urgent.

### 4. Plan-gate bookkeeping (commit 7f38a8f)

Run d0c31a's plan block had 4 unchecked boxes even though every item finished (2 dispatched successfully, 2 hit human_handoff and were resolved by hand) -- dispatch halts on the first unresolved item so its own final-loop mark_plan_complete() call never ran. Called it directly so find_incomplete_plan() returns None again.

## Final verified state

TriAPI: 5 commits this session (d5f666f, 125d7a4, 5e798f8, 6d371bb, 7f38a8f), full local suite green (108 tests, OK, zero SKIPPED), working tree clean. No oh-my-llama work this session.

**Next up:** the 12 flagged self-fix backlog entries above are worth a manual read-through eventually (not urgent, all pre-date multiple architecture changes and are very likely also stale, just not confidently classified by the script's current signature list). No deadline given.
