# 2026-08-28 05:35 (LA) / 12:35 UTC — ACTIVE: supervised oh-my-llama dispatch end to end, found+fixed 3 more real TriAPI bugs, oh-my-llama's mail-routing plan Phases 1-4 done+committed+pushed (Phase 5 still open there)

**Working tree is clean, no paused run, no pending approval.** `git log -1`
should show `0b7a77f` (or later) as `HEAD`. Full suite: 246 tests, OK.
Safe to start fresh work immediately.

## What happened this session

User asked to switch focus to the target repo `oh-my-llama`
(`/home/dyne/Documents/Coding/oh-my-llama`) and act as supervisor for
TriAPI's dispatch work there, per [[project_triapi_ohmyllama_dispatch]].
This was explicitly framed as a real-world stress test of TriAPI's
pipeline — a genuinely messy repo (5 days of uncommitted work sitting in
the working tree) was the deliberate "battlefield," not an accident to
clean up first.

## Landed and committed (TriAPI side)

1. **Design-judge fix-forward discarding working code — RESOLVED**
   (`9c25d82`). `handle_fix_forward()`'s revert path (taken when Tier 3's
   own remedy attempt fails to apply, or applies but the rebuild fails)
   correctly restores the file to its pre-fix-forward snapshot — which is
   ALWAYS a demonstrably-passing state, since `_run_design_judge()` only
   ever runs after `run_task()` already confirmed `status: "success"`.
   But the function still reported `fixed: False` unconditionally on that
   path, so `_run_design_judge()` downgraded the whole item to
   `build_failed` anyway — discarding genuinely-passing Tier 4/5 output
   over an unrelated, disconnected failure in the judge's own suggested
   remedy. **Confirmed live three times in one dispatch run** against
   oh-my-llama (`762d8d`, see below). Fixed: `handle_fix_forward()` now
   returns `reverted: True` alongside `fixed: False` on both its revert
   paths; `_run_design_judge()` treats `reverted` the same as `fixed`
   (keep the item's original success), while `tech_debt.log_tech_debt()`
   still records the judge's concern for later review. Two regression
   tests added/updated in `tests/test_design_judge_fix_forward_status.py`
   (one for each revert path).
2. **`tier_5_librarian` never actually running the item's verify command
   — RESOLVED** (`d171a8b`). `dispatch()`'s doc-target routing called
   `librarian_escalate.run()` without `verify_cmd=`, so
   `verify_cmd_resolved` inside that function fell through to
   `tier_5_librarian.verify_command` (`null` in config) then the literal
   no-op `"true"` — meaning the item's real, content-asserting build_cmd
   was **never executed for any tier_5-routed item, in any repo**.
   "Verification succeeded" logged and `success` reported unconditionally
   regardless of what actually happened on disk. **Confirmed live**: a
   `MAPPING.md` doc-update item reported success twice in a row while
   writing to an entirely wrong resolved path (see item 3 below) — the
   item's own build_cmd (`git -C <repo> diff -- MAPPING.md`) would have
   caught this immediately, had it run. Fixed: `dispatch()` now passes
   `verify_cmd=build_cmd` (already computed earlier in the same loop
   iteration) through to `librarian_escalate.run()`. New regression test
   in `tests/test_dispatcher_dynamic_target_resolution.py` asserts the
   real build_cmd is what gets passed, not silently dropped.
3. **A supervisor mistake, root-caused and guarded against** (`a54163e`
   cleanup, `9c25d82`'s `cmd_plan()` change is the actual guard). A
   `triapi plan` call for the oh-my-llama test-fix work was launched
   without `--project-dir`, which silently defaults to `"."` — the
   invoking cwd, which was TriAPI's own root. Dispatch still correctly
   targeted oh-my-llama's real files for code/test edits (the plan text
   used absolute paths in build_cmds), but two things landed in TriAPI's
   own repo by mistake: the plan's own text got appended to TriAPI's own
   `AGENTS.md` (cleaned up), and `librarian_escalate.run()`'s relative
   `MAPPING.md` target resolved against the wrong `workdir`, writing to
   `/home/dyne/Documents/Coding/TriAPI/MAPPING.md` (a file that shouldn't
   exist there at all — deleted) instead of oh-my-llama's real one. This
   is what item 2 above's false-success bug was masking — once verify_cmd
   was wired through for real, the SAME wrong-path write started failing
   the way it always should have. Fixed the run's own `state["project_dir"]`
   by hand to unblock it, then `cmd_plan()` now prints the resolved
   absolute `project_dir` right after the Run ID, before any turn is
   shown or approved, so this class of mistake is visible immediately
   instead of silently propagating for hours.
4. **`scope_guard.py`'s whole-function-deletion blind spot** — already
   covered in the prior carryover file (`5b40110`), not repeated here.

Full suite after all fixes: **246 tests, OK.**

## oh-my-llama side (target repo, its own docs already updated+pushed there)

Two `triapi plan`/`dispatch` runs, both supervised end to end per
oh-my-llama's own `docs/Agent/CARRYOVER.md`/`AGENT_GUIDE.md` playbook
(Tier 1 on, hand-edit only as genuine last resort after all 4 tiers
failed that exact item, verify for real before marking anything resolved
manually):

- **Mail-routing plan** (`20260823-154515-149c00`, dispatched 2026-08-23,
  picked back up this session): Phases 1–4 (7/10 items) verified correct
  and complete — `mail_watcher.py`, `intents.py`'s `MarkMailRead`/
  `GetMailFull`, `mail.py`'s two workers, `daemon.py`'s `MailWatcher`
  wiring, `telegram.py`'s 5-button inline keyboard — all independently
  confirmed present in the real files, not just trusted from a stale
  "9/10 steps" carryover claim that turned out to be wrong (the run's
  own JSON showed 6/10 at the actual start of this session). **Phase 5
  (3 items: `AddEmailRule` intent, `AddEmailRuleWorker`, `cli.py`
  registration) was never attempted at all** — caught by direct grep
  verification before checking boxes that would have falsely claimed it
  done. `AGENTS.md` and the run's own JSON now accurately reflect 7/10;
  the one-plan-per-repo gate stays closed until Phase 5 is dispatched.
- **Test-fix plan** (`20260828-035846-762d8d`, this session): fixed 3
  real, pre-existing, unrelated `bash run_tests.sh` failures — two
  `test_watcher_worker.py` cooldown-suppression cases baking
  `datetime.now()` into `@pytest.mark.parametrize` decorator arguments
  (evaluated once at collection time, not execution time), and a stale
  `test_semai_daemon.py` assertion checking positional args on a call
  that legitimately uses a keyword arg. Also found+fixed a third stale
  test while investigating full-suite verification:
  `test_non_ghostwriter_task_still_reaches_orchestrator_process` mocked
  the OLD `daemon._orchestrator._process()` shim call, which `daemon.py`
  deliberately moved off of (confirmed via `git log -p`) in favor of the
  native `self._dispatcher.dispatch()` — renamed and fixed. `bash
  run_tests.sh`: 172 passed, 3 skipped (pre-existing, expected), fully
  green.

**oh-my-llama commits this session** (all pushed to `origin/migration-clean-up`):
`9e22caa` (test fixes, auto-pushed by TriAPI's completed-run hook —
**this swept the entire 5-day-old pending working tree into one commit**,
a known `git_ops.push()` `git add -A` scoping gap, not new tonight —
see oh-my-llama's own `CARRYOVER.md` for the full list of what rode
along, including some files that look like scratch/debug artifacts
flagged there for review, not removed unilaterally), `945198f`
(`AGENTS.md` checkbox correction), `a29f2f2` (`CARRYOVER.md` rewrite).

**Full detail, next-up items, and the Phase 5 pickup point all live in
oh-my-llama's own `docs/Agent/CARRYOVER.md` and `MAPPING.md` — per
[[feedback_target_repo_docs_stay_in_target_repo]], not reproduced here
beyond this summary.**

## Standing rules (accumulated, still in effect)

All rules from prior files still apply unchanged. Nothing new to add —
tonight's findings were all either (a) real TriAPI bugs, now fixed with
tests, or (b) a supervisor process mistake, now guarded against with a
visible confirmation line. No new standing rule needed beyond what
already exists.

## Next up (priority order)

1. Nothing urgent on TriAPI's own side — all findings from tonight are
   fixed, tested, and documented.
2. On oh-my-llama's side (separate repo, its own carryover has full
   detail): resume `triapi dispatch 20260823-154515-149c00` for mail-
   routing Phase 5, and review the scratch/debug files that rode along
   in `9e22caa`'s auto-push.
3. Older carried-forward TriAPI items (unchanged, still open):
   `cost_log.jsonl` size split (~858KB), OpenRouter `[PHONE]` filter
   root-cause, Groq provider addition, architecture items (backend
   registry, complexity router, per-tier fallback toggles). The
   `git_ops.push()` `git add -A` scoping gap (confirmed causing real
   collateral tonight) is now a stronger candidate to actually fix, not
   just carry forward — worth prioritizing next.

**Separately, on hold for the user (unchanged across sessions):**
- **Virtual Codebase Plan** (`VIRTUAL_CODEBASE_PLAN.md`).
- `docs/TUI_plan.md` — still untracked/unplanned.

*(No further prior-file detail needed to resume — this file is
self-contained for "what's the current state.")*
