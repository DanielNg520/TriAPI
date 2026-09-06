# Carryover — 2026-09-02 (evening) — Gemini 3.7→3.8 tier_5_librarian swap complete; supervisor mode tightened to fully-dispatch-only

**Status: RESOLVED.** Nothing pending; clean session-end record.

## What this session covered

### 1. User tightened the supervisor operating rule

User stated, verbatim in intent: TriAPI is mature enough now that Claude is fully a supervisor -- call TriAPI for mostly all tasks and only audit its activities; write-tool spend should mostly be assigning tasks via triapi plan/dispatch, not hand-writing changes; any genuine hand fix (even a minor one) now needs the user's approval first. This narrows the prior 2026-08-19 standing overnight-authority grant, which had allowed autonomous minor patch-or-queue decisions -- that grant still covers triage/sequencing judgment calls, not silent hand-patching. Saved to memory as feedback_supervisor_fully_dispatch_only (see the assistant's own persistent memory store, not a repo file).

### 2. Gemini 3.7 Flash → 3.8 Flash tier swap, assigned to TriAPI (not hand-edited)

User reported Google pulled Gemini 3.7 and rolled out 3.8, asking to update the agy CLI calls for affected tiers. Live-checked first (per feedback_verify_dont_trust_status): 'agy models' still listed gemini-3.7-flash-* variants and added gemini-3.8-flash-*; a direct smoke call confirmed the bare id 'gemini-3.8-flash' with a separate '--effort' flag works (same pattern as the existing 'gemini-3.1-pro' bare-id usage), so no id-suffix migration was needed. Per project_triapi_tier_assignment_20260901, tier_5_librarian was the ONLY tier on Gemini 3.7 Flash (effort high); tier_1_planner, tier_2_manager's peak_alt, and tier_3_debugger all use gemini-3.1-pro and were confirmed untouched.

Ran 'triapi plan --project-dir /home/dyne/Documents/Coding/TriAPI' with the swap goal plus the live-verification requirement; approved the resulting 3-phase plan as run 20260902-105125-fa54aa (also answered one in-plan clarifying question: yes, also fix a stale orchestrator.py comment that described Tier 2's peak-billing model as something other than gemini-3.1-pro, since it was a genuine drift bug found in the same file being touched). Dispatched it (nohup, backgrounded, single dispatch invocation) and supervised to completion via Monitor + triapi status polling rather than trusting the 'Dispatch completed' log line alone (per feedback_dispatch_completed_log_not_process_exit) -- confirmed the background process's actual exit state, then independently verified live file contents and ran the full regression suite myself.

Result: config/tiers.yaml's tier_5_librarian.models.primary is now gemini-3.8-flash (effort unchanged, high); ARCHITECTURE.md and AGENTS.md's own config/ section doc bullet updated to match; scripts/librarian_escalate.py's module docstring and scripts/orchestrator.py's inline comment (plus the unrelated stale Tier-2-model comment) updated; tests/test_tier5_librarian.py's fixture literals updated to gemini-3.8-flash. Committed as ca8085c. Full suite verified green independently afterward: 'PYTHONPATH=. python3 -m unittest tests.test_branch_features tests.test_tier5_librarian -v' -- 100 tests, OK, zero SKIPPED. AGENTS.md's own frozen historical '<!-- triapi:plan -->' transcripts still say gemini-3.7-flash where they quote what actually happened at the time -- correctly left untouched, per the standing 'never edit archived plan history' convention.

## Queue snapshot taken this session (not newly created, just surfaced -- see the assistant's chat reply for the full breakdown)

- Two on-hold design items, unstarted, still waiting on the user personally per their own instructions: the Virtual Codebase Plan (Tiered Planner-Materializer for oversized Tier-4 files) and the 'triapi tui' subcommand spec (design questions need the user before planning). Neither is newly stale this session; both were already tracked as on-hold going into it.
- knowledge/TECH_DEBT.md carries 9 unresolved entries (unapplied Tier-3 SEARCH/REPLACE edits, mostly against test files in both TriAPI and oh-my-llama, plus one orchestrator.py rebuild-failure entry from a Tier-3 refactor attempt earlier this same session that reverted cleanly and did not affect the final committed result).
- 'triapi self-fix list' shows a large accumulated backlog never groomed: 35 unqueued captured bug reports and 32 drafted-but-never-approved self-fix runs, spanning 2026-08-14 through 2026-09-02. Skimmed, not read in full this session -- the large majority read as transient/already-superseded noise (old free-tier 429 rate limits, since-retired model names like gemini-2.5-flash and gemini-3.7-flash error variants, connectivity blips already covered by since-shipped soft-escalation fixes), but the backlog itself has never been triaged/pruned and is worth a dedicated grooming pass rather than assuming every entry is moot without individually checking. Flagging as a queue item rather than resolving it in this session, since bulk-closing 67 entries without reading each one would risk silently discarding a still-real bug.

## Final verified state

TriAPI: 1 commit (ca8085c) this session's work, full local suite green (100 tests, OK), working tree clean immediately after the dispatch. No oh-my-llama work this session.

**Next up:** groom the self-fix/tech-debt backlog above (read each entry, close what's genuinely stale, re-queue or hand-review anything still live) -- not started, no deadline given.
