# 2026-08-24 03:00 — Tier 5 librarian redesign: bugs found and fixed across five addenda

## Addendum 1

- **Librarian improvements run `20260824-132910-a7b69b` is `stopped_on_failure`
  after Phase 1 (both items landed clean, Tier 4) and Phase 2's single item
  (`scripts/doc_staleness.py`) hit `human_handoff` after exhausting Tier 4 →
  3 → 2 → 1 — all four independently produced the same bug.** Root cause
  (confirmed by reading the generated file, not hand-fixed): the epoch-
  collision handling in `should_skip_model_call()`'s scan loop treats "a
  commit landed at the same UNIX-epoch second as the doc's last commit" as
  "this commit touched the doc" and discards it (`if current_epoch ==
  doc_commit_epoch: continue`). Git's commit timestamp has 1-second
  granularity, so two *different* commits made in quick succession — the
  test harness's own `git commit` calls, and realistically TriAPI's own
  automated commits too — can share an epoch even though only one touched
  the doc. That silently drops a genuine non-doc commit from the scan,
  leaving `found_non_doc_commit = False` and forcing permanent fail-open
  (never skips the model call) in exactly the fast-commit scenario the
  pre-check exists to handle. Fail-open itself is safe (matches spec:
  "ANY ... unexpected ... -> fail open"), so this isn't unsafe, just makes
  the whole feature inert whenever commits are fast/batched. Fix should
  distinguish "commit touched the doc" (check the file list, not the
  epoch) from "commit epoch ties the doc's epoch" — the same-epoch guard
  needs to check membership of `relpath_str` in that commit's file list,
  not epoch equality. Route via `triapi plan`/self-fix against
  `scripts/doc_staleness.py`, don't hand-patch. Once fixed, resume/retry
  run `20260824-132910-a7b69b`'s Phase 2 item (still awaiting Phases 3-9:
  wiring, tests, PLAN.md/AGENTS.md updates).

## Addendum 2

- **Run `20260824-132910-a7b69b` resumed past the Phase 2 `doc_staleness.py`
  bug on retry (a fresh Tier 1/Claude attempt got it right this time,
  6/9 steps done) and hit a NEW `human_handoff` at Phase 4** (regression
  tests in `tests/test_tier5_librarian.py`). Root cause here is a plan-
  breakdown gap, not a code bug: **two pre-existing tests —
  `test_advisory_no_change_verdict_returns_changed_false_without_writing`
  and `test_success_path_lands_via_edit_block_with_local_billing` — still
  mock the OLD JSON-envelope response format (`'{"stale": false}'`) that
  Phase 1 deliberately eliminated.** Against the new single-call plain-
  text `run()`, that mocked JSON string correctly fails to parse as either
  `FRESH` or a SEARCH/REPLACE block, so `run()` (correctly, per the new
  design) escalates through the full chain and the test's
  `execute_llm.assert_called_once()` fails (actually called 3x). Phase
  4's item description only said to *add* new single-call-flow tests, not
  to update/remove these two now-incompatible old ones — that's the gap.
  4 escalation attempts (Tier 4→3→2→1) apparently thrashed on this,
  producing one genuinely broken syntax (`SyntaxError: unterminated
  string literal` at old line 358) that a later attempt already
  overwrote — current file parses clean (`ast.parse` succeeds), so no
  cleanup needed there. Resumed dispatch again after documenting this;
  if it's still stuck next session, the fix is either (a) let a tier
  finally rewrite those two tests for the new format on its own, or (b)
  if it keeps thrashing, a small follow-up `triapi plan` item explicitly
  naming those two tests for update would remove the ambiguity — draft
  via the pipeline, don't hand-edit the test file directly.

## Addendum 3

- **New systemic bug found 2026-08-24, NOT fixed (queue it, don't hand-
  patch): `orchestrator.run_task()`'s Tier 4→3→2→1 escalation can declare
  `human_handoff` even when the FINAL tier attempt's write genuinely
  satisfies the item's own `build_cmd`.** Confirmed live on run
  `20260824-132910-a7b69b`'s Phase 4 item (`tests/test_tier5_librarian.py`
  regression tests): after sharpening the item's description (see prior
  addendum) and resuming, the run again reported `human_handoff` with a
  "Tier 4 -> Tier 3 -> Tier 2 -> Tier 1" exhaustion reason — but the file
  actually left on disk was completely correct: re-running the exact
  recorded `build_cmd` (`PYTHONPATH=. python3 -m unittest
  tests.test_tier5_librarian -v`) by hand passed clean, 14/14 tests green,
  including both previously-stale tests now correctly updated. So the
  last tier's write did succeed against its own acceptance check, but
  `run_task`'s own bookkeeping still escalated to human_handoff instead of
  returning success — most likely a consecutive-failure-threshold check
  firing on a stale counter without re-validating the final attempt's
  actual build result, similar in spirit to the epoch-collision bug found
  earlier this session but in a different module (root cause not yet
  isolated to a specific line — needs a read through `tier1_escalate.py`'s
  retry loop, or wherever the final tier's success/failure gets folded
  into the human_handoff decision). **Workaround applied this session
  (with explicit user sign-off, since it required overriding the run's
  own recorded verdict): manually corrected `logs/runs/
  20260824-132910-a7b69b.json`'s last result entry from `human_handoff` to
  `success` (resolved_by: tier_1, content_hash recomputed via
  `regression_guard.hash_file()`), since the target file was independently
  re-verified against its own build_cmd first.** Route the actual fix
  through `triapi plan`/self-fix against `scripts/orchestrator.py` (and
  whichever `tierN_escalate.py` turns out to hold the stale-counter logic)
  once this run completes — don't hand-patch. **Not yet fixed as of the
  last full carryover review** — still an open, precisely-diagnosed bug.

## Addendum 4

- **Run `20260824-132910-a7b69b` reached 8/9 (Phases 1-4 fully done and
  verified — full regression gate green) and stalled on Phase 5's PLAN.md
  update.** All three of `tier_5_librarian`'s escalation legs failed:
  local legs (`mistral-small`/Ollama fallback) can't fit `PLAN.md` at
  188,334 chars (well over Tier 4's 73,728-char ceiling — same standing
  ceiling problem as the file-size-ceiling rule), and the
  OpenRouter fallback leg hit the already-queued `403 Forbidden` content-
  filter false-positive — this is a
  second, independent live confirmation of that bug against a different
  digit-heavy file (`PLAN.md`'s many `run_id`/timestamp strings), not a
  new bug. This item is genuinely blocked on two already-queued fixes
  (the OpenRouter phone-regex sanitizer, and PLAN.md's own oversize —
  which is also the subject of the already-queued "consolidate historical
  PLAN.md content out to target-repo docs" follow-on). Not resolved this
  session; run left at `stopped_on_failure` on this item pending user
  direction on how to proceed (skip Phase 5 for now vs. wait for the
  OpenRouter/PLAN.md-size fixes to land first). **Later resolved by hand
  once the sanitizer fix landed** — see the `20260825-000000-*` carryover
  file for the phase entries this became.

## Addendum 5

- **Priority #2 (OpenRouter fixes), first attempt (`20260824-162206-4ae0a0`)
  hit a genuine chicken-and-egg failure: its own breakdown call (Tier 2/
  Gemini, routed through OpenRouter) got `403 Forbidden` because the
  approved plan text itself contained literal phone-number-shaped example
  strings (e.g. a fake pager number as a test fixture) — a fourth live
  confirmation of the exact bug being fixed, this time tripped by the fix's
  own plan. That run is abandoned/stuck (`stopped_on_failure`, 0 phases,
  still sitting in `AGENTS.md`'s plan-gate block — harmless to leave, next
  plan used `--refactor` to supersede it). Redrafted as
  `20260824-164451-2b7635`** with an explicit constraint in the prompt
  telling the planner not to emit literal phone-shaped digit strings
  anywhere in the plan/test text (describe the format structurally
  instead) — this one's breakdown succeeded and it's now dispatching.
- **Priority #2 now dispatching: run `20260824-164451-2b7635`**, plan
  approved and running in background.
  Bundles all three queued OpenRouter/dispatch bugs into one 4-phase plan:
  (1) phone-number content-filter false-positive fix in
  `llm_client._sanitize_for_openrouter_content_filter()` (new
  `_PHONE_LIKE_RE`/`_redact_phone_like()`, scoped to not mangle
  run_id/task_id-shaped strings, hex hashes, or line numbers); (2)
  `dispatcher._is_deepseek_peak_hours()` now delegates to
  `budget_guard.check_tier3_peak_hours_ok()` instead of its stale
  hardcoded 06:00-10:00-UTC-only duplicate; (3) audit of
  `librarian_escalate.py`'s `fallback_openrouter` endpoint resolution
  (plan's own read concluded it's already correct via
  `tier_1_planner`'s config block, not the buggy pattern
  `probe_models()` had — a regression test asserting the resolved URL
  either way is still item 3's deliverable). Phase 4 does the full
  regression gate + PLAN.md/AGENTS.md doc updates. **This run completed
  successfully — see the `20260825-000000-*` carryover file.**
