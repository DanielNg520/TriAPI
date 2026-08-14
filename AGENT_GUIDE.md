# Agent guide: operating TriAPI with Tier 1 off

For an agent (human-directed AI, not necessarily this same assistant)
running `triapi dispatch --no-tier1` or with `config/tiers.yaml`'s
`tier_1_manager.enabled: false`. Read this before dispatching in that mode.

## What actually changes

Only the **repair role** (`scripts/tier1_escalate.py`, called from
`orchestrator.run_task()`'s escalation chain) is disabled. The chain becomes:

```
Tier 4 (Ollama, local)  →  Tier 3 (DeepSeek)  →  [Tier 1 skipped]  →  Tier 2 (Gemini)  →  human_handoff
```

`triapi plan`'s interactive planning step (`scripts/planner.py`) is a
**separate code path and a separate config block** (`tier_1_planner`, not
`tier_1_manager`) — it still uses Claude Code CLI regardless of this switch.
Planning is unaffected; only automated repair loses its strongest tier.

## Why this changes your job

Tier 1 (Claude Code CLI) was the strongest automated repair tier — closest
in capability to a careful human edit, and the one most likely to correctly
diagnose a subtle bug or an ambiguous plan-item description rather than
pattern-matching a shallow fix. With it off, more items than usual will
exhaust Tier 4 → Tier 3 → Tier 2 and land in `human_handoff` — not because
the plan was worse, but because there's one less capable safety net between
"a cheap/local model's best guess" and "give up and ask a human."

**Practically: you (the agent running triapi in this mode) are now the
de facto Tier 1.** You take on three roles a fully-tiered run would have
partly automated:

1. **Planner** — still literally true regardless of the switch (`triapi
   plan` is always interactive and human/agent-reviewed before dispatch).
   Nothing new here, but worth restating: a vague or under-specified plan
   item that Tier 1 might have quietly disambiguated correctly will now more
   often surface as a stuck item instead — so scope plan items a little more
   precisely than you might with Tier 1 available.
2. **Supervisor** — expect to personally diagnose a higher fraction of
   `human_handoff`s. Two failure classes to distinguish immediately (same
   discipline this project has used throughout, see `PLAN.md`/`CARRYOVER.md`
   for many real examples):
   - **The build_cmd itself is broken/too weak** (a check that's
     environment-fragile, tautological, or doesn't actually assert the
     described change happened) — fix the check, not the code.
   - **A genuine gap** — the described change really didn't happen, or
     happened incorrectly/incompletely — fix the target file (by hand if
     needed) or let a corrected build_cmd give Tier 3/Tier 2 another real
     shot.
3. **Monitor** — watch dispatch output / `logs/triapi.log` actively rather
   than firing a long run and checking back at the end. A `stopped_on_failure`
   run does not resume itself; expect to intervene mid-run more often than
   with Tier 1 on.

## Concrete workflow when a human_handoff hits

1. Read `logs/escalation_<task_id>.md` — the actual last build error, not
   just the summary line. An empty or uninformative error body is itself a
   signal the build_cmd is weak (e.g. a bare `grep`/pipe failure with no
   real assertion), not that the fix attempts were all equally bad.
2. Read the actual target file's current diff (`git diff <target>`) —
   never trust a tier's reported `success`/`fix_rejected` status. Check
   whether the real described change landed, landed partially, or was
   replaced by unrelated scope-creep (a tier "fixing" something adjacent
   instead of the actual ask — has happened for real in this project).
3. If the build_cmd is at fault: patch it in **all copies** it can appear
   in — `state["breakdown"]["phases"][i]["items"][j]["build_cmd"]` (live
   definition), `state["results"][k]["build_cmd"]` (historical record,
   re-checked by `dispatcher._recheck_regression_flags()` before resume),
   and any `state["regression_flags"]` entry's own frozen snapshot. Missing
   one of these can cause a stale/wrong check to keep firing after you
   think you've fixed it.
4. Verify your fix manually before resuming: run the corrected build_cmd
   by hand against both the pre-fix and post-fix file state if possible,
   confirming it fails/passes as expected — a build_cmd that always passes
   (tautological) is worse than no check at all, since it hides the gap
   permanently instead of surfacing it once.
5. If you hand-patch the target file directly (rather than letting a tier
   redo it): mark that item's `results[]` entry `"status": "success"`,
   `"resolved_by": "manual"`, and refresh `"content_hash"` via
   `scripts.regression_guard.hash_file()` — otherwise the item stays
   `human_handoff` and blocks the run indefinitely, or a resume re-attempts
   Tier 4 from scratch and overwrites your fix.
6. Resume: `triapi dispatch <run_id>` (add `--background` for a long run
   over an unreliable connection). Confirm no dispatch process is already
   alive first (`pgrep -af "triapi dispatch"`) before hand-patching state —
   editing a run's JSON while a live process holds it risks a lost write.

## What's still safe to trust automatically

- Phase-by-phase `verify_only` items (pure checks, no draft step) — these
  never touch a file, so a `success` here is lower-risk to trust than a
  file-editing item's `success`.
- Tier 4/Tier 3/Tier 2 successfully resolving a *simple, well-scoped* item
  end-to-end — spot-check occasionally, but this project's real failures
  have concentrated in large/ambiguous items and weak build_cmds, not
  small precise ones.

## What never changes, switch or no switch

- **Never hand-edit a target repo directly.** Fix TriAPI's own scripts/
  config/build_cmds so the pipeline handles it correctly, or hand-patch a
  run's own state JSON per the workflow above — the actual file-content
  work for a *target* repo item still goes through a tier whenever
  possible. Hand-writing a target file's content should be a last resort
  when a tier has genuinely and repeatedly failed on that exact item, not
  a shortcut to avoid supervising.
- **Documentation in TriAPI's own repo** (this file, `README.md`,
  `PLAN.md`, `mapping.md`, `CARRYOVER.md`) is always fine to edit directly
  — it's not target-repo work and doesn't need to go through dispatch.
- **Verify, don't trust status.** The single most repeated lesson across
  this project: read the real file diff, the real escalation log, the real
  test output — never take a `success`/`completed` string at face value.
