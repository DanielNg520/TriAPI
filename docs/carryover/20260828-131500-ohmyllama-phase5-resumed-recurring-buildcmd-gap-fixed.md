# 2026-08-28 13:15 — oh-my-llama Phase 5 resumed, recurring build_cmd gap hand-patched

**Status: RESOLVED.** Supervised a straightforward resume-and-finish: no
new TriAPI code changes this session, but one real observation worth
carrying forward.

## What happened

Restarted the paused oh-my-llama dispatch (`triapi.py dispatch
20260823-154515-149c00`) once `budget_guard.check_tier3_peak_hours_ok()`
confirmed the weekend DeepSeek off-peak window was active. Dispatch hit a
`human_handoff` on the last item (`p4-i2`, registering mail workers in
`src/semai/adapters/cli.py`) after all 4 tiers failed it.

**Root cause was not that item's own code** — `cli.py`'s registration was
already correct from the tiers. The real cause was an earlier item in the
*same plan*, `p4-i0` (adding the `add_email_rule` intent kind to
`src/semai/core/intents.py`), whose `build_cmd` was only `python -m
py_compile src/semai/core/intents.py` — it compiled clean and was marked
`success` by `tier_3`, but never ran the actual test suite, so it never
caught the two regressions it silently introduced:

- `tests/fixtures/intents.jsonl`'s golden-set coverage check failed
  (`add_email_rule` had 0 labeled examples; the test requires >=5 per
  declared kind).
- `test_semai_intents.py`'s hardcoded declared-kind-count assertion went
  stale (22 -> 23).

Every subsequent item's `build_cmd` in this plan happened to be `bash
run_tests.sh` (the full suite), so the pre-existing regression surfaced
on the very next item and burned all 4 tiers there instead of at its
actual source.

**This is the identical failure shape** to an earlier item in this same
plan (`p2-i2`, which fixed a hardcoded `20 -> 22` kind-count assertion
after Phase 2 added 2 new kinds) — two occurrences of "a plan item that
adds a new intent kind gets a weak/partial `build_cmd` that can't see the
kind-count and golden-fixture-coverage tests it's about to break."

## What I did

Diagnosed it as a genuine implementation gap (not a false-success
`build_cmd`/silent-skip pattern already known and fixed), verified fully
before touching state: added 5 synthetic golden examples for
`add_email_rule` to `tests/fixtures/intents.jsonl`, bumped
`test_semai_intents.py`'s count 22->23, confirmed `bash run_tests.sh`
went fail->pass by hand (172 passed, 3 pre-existing/unrelated skips, exit
0) before marking `p4-i2` `success`/`resolved_by: manual` with a refreshed
`content_hash` (`scripts.regression_guard.hash_file()`), per the
supervisor playbook in oh-my-llama's own `AGENT_GUIDE.md` §10. Confirmed
no dispatch process was alive both before the hand-patch and before
resuming. Resumed dispatch; it finished `completed`, pushed commit
`aa8a90e` to oh-my-llama, and the advisory Jules run also came back clean.

Updated oh-my-llama's own `docs/Agent/CARRYOVER.md` (via
`scripts/librarian_escalate.py`, not hand-edited) to close out the
Phase 5 item and record this gap in its own history.

## Not fixed — flagging as a real (if small) planning-quality gap

This is not a dispatcher/orchestrator bug — `p4-i0`'s `build_cmd` was
exactly what `triapi plan` generated for that step, and a bare
`py_compile` is legitimately the right level of check for most
single-file items. The gap is specific to items that add a **new intent
kind**: `INTENT_KINDS`/`INTENT_MODELS` changes have a project-wide
blast radius (golden-fixture coverage, kind-count assertions elsewhere in
the suite) that `py_compile` structurally cannot see. Two occurrences in
one plan is enough to call it a pattern rather than noise.

- [ ] Possible angle, not designed yet: teach `triapi plan`'s breakdown
  step (or a post-hoc heuristic in `dispatcher.py`) to force
  `build_cmd = "bash run_tests.sh"` (never a narrower check) whenever an
  item's `target` is `src/semai/core/intents.py` or its description
  mentions `INTENT_KINDS`/adding an intent — a small, targeted rule
  rather than a general "always run the full suite" change (which would
  slow down every simple item for no reason). Not urgent: it has now
  self-corrected twice via the existing Tier1/manual escalation path
  with no lasting damage, so it's a nice-to-have, not queued as a live
  bug.

## Session state

Working tree clean here in TriAPI. oh-my-llama's mail-routing plan
(Phases 1-5) is fully done, verified, and pushed. Nothing mid-flight.
