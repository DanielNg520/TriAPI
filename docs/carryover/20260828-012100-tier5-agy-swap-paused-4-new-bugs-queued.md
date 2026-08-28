# 2026-08-28 01:21 UTC — ACTIVE: tier_5_librarian primary swapped to agy/Gemini-3.7-Flash (verified, committed); one run paused for DeepSeek peak hours with 4 new bugs queued, not yet fixed

**This is the primary file to read to resume work — everything else in
`docs/carryover/` is historical/completed context only.**

## Current state

**Two separate pieces of work landed and are committed/pushed** (`96e005e`,
`929c2ab` — check `git log -3` / `git status` on resume to confirm the tree
is still clean; trust `git` over this paragraph if they disagree):

1. Run `20260827-100542-afee9f` (the `_run_design_judge`/`critique.applies_to_tiers`
   fix queued at the end of the prior carryover file) completed and
   auto-pushed as `96e005e`.
2. A follow-up user-directed fix — `tier_5_librarian`'s primary model
   swapped from slow local `ollama/mistral-small` to `agy`/Gemini 3.7
   Flash (`effort: low`) — was implemented, live-verified, and (along with
   a hand-restored regression that `96e005e`'s own commit accidentally
   clobbered) is folded into that same `96e005e` commit. A follow-up
   carryover-queue update landed as `929c2ab`.

**One dispatch run is paused, not broken:** `20260827-132236-806da1`
(`triapi status 20260827-132236-806da1`) is `stopped_on_failure` on its
very last item — a cosmetic `AGENTS.md` index note about the agy swap.
That item cannot currently be completed by any tier because `AGENTS.md`
itself is bloated to ~2x this repo's size ceiling (queue item 1 below) —
fixing that is a prerequisite. **Nothing else about this run needs
resuming** — every other item (the actual code fix, config change,
regression tests, the stuck-run resume, the carryover update) already
succeeded. Either fix queue item 1 first and then `triapi dispatch
20260827-132236-806da1` to pick up that last cosmetic note, or just let
it sit — the substance is not blocked on it.

**Explicitly paused for the user, this session:** DeepSeek's peak-billing
window (`01:00-04:00 UTC`, currently active as of this file's timestamp)
— the user asked to pick further work back up after it passes. No other
mid-flight state exists beyond the one paused run above.

## What happened this session

**1. Root-caused a prior session's misdiagnosis.** The previous carryover
file's queue item 1 ("doc-target routing is inconsistent") was wrong —
`is_doc_target()` routing worked identically and correctly for both
`ARCHITECTURE.md` and `AGENTS.md`. The real bug: `scripts/dispatcher.py`'s
`_run_design_judge()` (called unconditionally on every "regular item"
success) ignored `config/tiers.yaml`'s `critique.applies_to_tiers`
(`["tier_3","tier_1","tier_2"]`, deliberately excluding `tier_4`/`tier_5`)
— unlike `scripts/orchestrator.py:82`'s own critique step, which already
checks it. So a `tier_5_librarian` doc-edit success got wrongly fed into
the design judge, which on rejection invoked Tier 3 to "refactor rewrite"
a Markdown file. Fixed via `triapi plan`/`dispatch` (run `20260827-100542-afee9f`):
`_run_design_judge`'s caller now gates on `result['resolved_by']` being in
`critique.applies_to_tiers` (`tier_4` added to that list to preserve its
existing behavior explicitly; `tier_5` deliberately still excluded).
Regression tests in `tests/test_design_judge_fix_forward_status.py` and
`tests/test_branch_features.py`.

**2. Diagnosed *why* the misdiagnosis happened in the first place:**
`tier_5_librarian`'s primary model, `ollama/mistral-small:latest`, runs at
only ~10-11 tok/s on this machine's AMD integrated GPU (no discrete GPU —
confirmed via `lspci`). `scripts/llm_client.py`'s HTTP timeout is 600s, so
any real doc edit (especially large files) routinely timed out on the
primary attempt before falling through to the faster `qwen2.5-coder`
fallback — a systematic 10-minute tax on every `tier_5` task, confirmed
across 5+ separate timeouts this session. User's fix: swap the primary to
`agy` (Antigravity CLI) / Gemini 3.7 Flash at `effort: low` (model
confirmed live via `agy models`). This required more than a config
change — `scripts/librarian_escalate.py`'s primary provider slot was
hardcoded to `"ollama"` and never read `tier_5_librarian.provider`/
`effort` at all; `run()`'s `providers` list is now config-driven and
`execute_agy()` is called with the configured `effort`. Live-verified
end-to-end against a throwaway scratch file: **4 seconds**, vs. the
previous 600s timeouts every time. Regression test added in
`tests/test_tier5_librarian.py`
(`test_primary_provider_swaps_to_agy_with_effort_when_configured`).

**3. Two planning attempts failed before a good plan was produced —
worth remembering for next time a `triapi plan` looks approved but is
garbage:** attempt 1 (run `20260827-130627-e41ad6`) got a truncated
one-sentence response from an overloaded free Nemotron model and
auto-approved it; attempt 2 (run `20260827-130810-27dd58`) got a
**fully hallucinated** response — Nemotron fabricated an entire fake
`<tool_call>` transcript with invented `config/tiers.yaml` content
(`gemini-1.5-pro`, `claude-3.7-sonnet` — none of which exist in this
repo) instead of actually reading the file. Neither was dispatched
(caught by reading the plan text before approving, not blind-piping
`approve`), but **both got appended to `AGENTS.md` at plan-approval time
regardless** — see queue item 1, this is why `AGENTS.md` is now bloated.
**Lesson applied and worth keeping**: after `triapi plan`, always read
the actual plan text before approving — a `plan_turn()` that returns
"ok" is not proof the content is real or complete.

**4. A design-judge regression got silently introduced and was caught by
its own regression test, then hand-restored.** While dispatching the agy
swap, an unrelated Tier 3 fix-forward rewrite of `config/tiers.yaml`
(for the tier_5 provider swap) clobbered the `tier_4` entry this same
session had just added to `critique.applies_to_tiers` — reverting item
2's fix. `test_tier4_success_still_runs_design_judge` caught it
immediately (`evaluate_design` called 0 times, expected once). Restored
by hand (a one-token config edit, not a hand-write of new content), with
explicit user permission given the item that would have needed to fix it
was a `verify_only` step with no target file of its own to edit.

**5. Several hand-patches to `logs/runs/*.json` bookkeeping, each only
after verifying the real file state matched, per the established
`human_handoff`-equivalent recovery pattern — not fabricated successes:**
a carryover-file item that had genuinely landed correctly but got killed
by an outer 600s timeout race; a new test file that had a syntax error at
one polling snapshot but was later fixed by a subsequent escalation
attempt before the item's own re-check happened; the `config/tiers.yaml`
regression fix in point 4; and the wrapper item for resuming a separate
stuck run (`20260827-100542-afee9f`, which itself completed and pushed
cleanly — the wrapper's own outer 600s timeout just couldn't see that).
**Every one of these was verified against real file content, a live test
run, or `git log`/`git status` before patching — never patched on trust
alone**, per [[feedback_verify_dont_trust_status]].

**6. Four new, real, confirmed bugs surfaced along the way — none fixed
yet, all queued below with root causes already identified** (this is the
valuable output of tonight's friction — see queue items 1-4).

## Worth queuing (in priority order — see the file's own numbered list
for full detail on each; this is a condensed pointer, not a duplicate)

1. **`AGENTS.md` is ~2x over the size ceiling** due to a ~1,294-line
   hallucinated block from the abandoned plan run `20260827-130810-27dd58`
   (see point 3 above). Needs the exact
   `<!-- triapi:plan run_id=20260827-130810-27dd58 start/end -->` block
   removed. **Do this first** — it's now blocking `AGENTS.md` edits
   entirely (see item 2) and was explicitly deferred by the user earlier
   this session ("leave it, focus on the real fix first") — that real fix
   is now done, so this is next.
2. **`AGENTS.md`'s bloat just crashed the `agy` CLI live**:
   `OSError: [Errno 7] Argument list too long` from `_call_agy_cli()`
   passing a huge prompt (including full `AGENTS.md` as context) via a
   command-line argument. Needs `agy` invocations to pass large prompts
   via stdin instead of argv, or a context-size cap before building the
   CLI command — will recur for any large doc target until fixed, not
   just `AGENTS.md`.
3. **RESOLVED (2026-08-28)** — `scripts/librarian_escalate.py`'s
   `staleness_precheck` false-negative FRESH bug. Fixed in
   `scripts/doc_staleness.py` via a new `_STALENESS_QUESTION_PHRASES`
   leading gate in `should_skip_model_call()`: the fast git-epoch skip
   path now only runs when the task description contains a
   code-sync-staleness phrase; any other description (e.g. a plain
   append/index-update task) always forces a real model call. Covered by
   new regression tests in `tests/test_tier5_librarian.py` (96 tests, full
   suite OK). Note: dispatch run `20260827-222943-2c134b` recorded a false
   human_handoff because its `verify_cmd` used a case-insensitive grep
   for 'skipped' across `unittest -v`, matching test method names rather
   than real skip markers; suite passed cleanly (re-verified). Follow-up
   queued: future plans should grep for anchored/word-bounded SKIP patterns.
4. **Dynamic shell-expression targets bypass shell expansion in
   `dispatcher.py`'s `tier_5_librarian` routing.** A breakdown-generated
   item `target` like `docs/carryover/$(jq -r '.active' docs/carryover/index.json)`
   resolves correctly only inside a real `build_cmd` shell command —
   `dispatcher.py`'s dedicated Python-call routing path
   (`dispatcher.py:1264-1272`) passes `item['target']` straight to
   `librarian_escalate.run()` with no shell expansion, so it silently
   operates against a literal nonexistent path (confirmed live, run
   `20260827-132236-806da1` Phase 4 item 0). This combined with bug 3
   above to produce a false "success" with zero real edit.
5. **RESOLVED, this session** — see point 1 above (`_run_design_judge`/
   `critique.applies_to_tiers`).
6. `logs/cost_log.jsonl` size split (still ~858KB, carried forward,
   unchanged this session).
7. `git_ops.push()`'s unconditional `git add -A` scoping gap (carried
   forward, unchanged this session).
8. OpenRouter `[PHONE]` filter root-cause (carried forward).
9. Groq provider addition (carried forward).
10. Architecture items: backend registry, complexity router, per-tier
    fallback toggles (carried forward).

*(Full text of every item, including the ones marked RESOLVED for
historical reference, lives in the prior file,
`20260826-193000-tier3-timeout-softescalate-architecture-refresh-agentsmd-routing-bug.md`
— read it only if you need that level of detail; this file's condensed
list above is enough to resume.)*

## Standing rules (accumulated; only what changed or is newly load-bearing
this session — see the prior file for the full accumulated list)

- `tier_5_librarian`'s primary provider is now `agy` / Gemini 3.7 Flash
  (`effort: low`), not `ollama`/`mistral-small`. The fallback chain
  (`fallback_local` → `fallback_agy` → `fallback_openrouter` →
  `log_and_notify`) is unchanged; `fallback_agy` still separately points
  at `agy`/Gemini 3.1 Pro (`effort: high`) for a stronger, slower purpose
  — do not confuse the two.
- **Always read a `triapi plan` turn's actual text before approving it.**
  A "turn ok" status does not mean the content is real, complete, or
  non-hallucinated — see point 3 above. Piping a blind `approve` is not
  safe.
- `critique.applies_to_tiers` in `config/tiers.yaml` is now
  `["tier_3", "tier_1", "tier_2", "tier_4"]` — verify this hasn't
  regressed again before trusting it (see point 4 above; it silently
  reverted once already this session from an unrelated Tier 3 rewrite).
- `scripts/doc_staleness.py` `should_skip_model_call()` now gates fast git-epoch skips on `_STALENESS_QUESTION_PHRASES`; generic append/update descriptions always force a real model call.
- In test verify commands, grep for real skip markers (e.g. word-bounded `'SKIPPED'` or `'... skipped$'`) rather than bare substring `'skipped'` to avoid matching test method names.
- DeepSeek peak-hours windows unchanged: `01:00-04:00` and
  `06:00-10:00 UTC`, weekdays.

## Next up (priority order)

1. **RESOLVED** — `AGENTS.md` bloat resolved (committed `d98de74`).
2. Fix the `agy` CLI argument-length crash (queue item 2) — reopened with corrected understanding (prompt-size guard / fail-fast / fallback, not stdin).
3. Fix `dispatcher.py` verify_command insufficiency for new test files (`py_compile` alone permits broken runtime/import references; require unittest import/collection verification).
4. **RESOLVED** — `librarian_escalate.py`'s `staleness_precheck` false-negative (queue item 3).
5. Fix the dynamic-shell-expression-target bug in `dispatcher.py`'s `tier_5` routing (queue item 4).
6. Fix test verification pattern: avoid bare `'skipped'` grep in verify commands that false-triggers on method names.
6. Once above items are clear, resume `20260827-132236-806da1` to pick up its one remaining cosmetic `AGENTS.md` note (or just let it lapse — the substance is already done).
7. Then the older carried-forward items: `cost_log.jsonl` split, `git_ops.push()` `git add -A` scoping, OpenRouter `[PHONE]` filter, Groq provider, architecture items (backend registry / complexity router / per-tier fallback toggles).

## 2026-08-28 Progress Update (Session continuation)

### 1. Queue item 1 (`AGENTS.md` bloat) — RESOLVED (`d98de74`)
- Hand-edited directly per explicit user approval since `AGENTS.md`'s own size bloat was blocking the pipeline from editing `AGENTS.md` at all (the exact chicken-and-egg situation).
- The fabricated ~71.6KB plan block from abandoned run `20260827-130810-27dd58` was deleted outright.
- 5 completed historical plan blocks archived to `docs/agents/20260828-044229-agents-md-historical-plan-blocks-archive.md`.
- `AGENTS.md` dropped from 161,878 to ~41,000 characters.

### 2. Queue item 2 (`agy` CLI Argument list too long) — ATTEMPTED & REVERTED (OPEN)
- Attempted via `triapi plan`/`dispatch` and failed, then correctly reverted.
- **Critical finding**: `agy`'s `-p` flag does **not** support stdin input (unlike `claude -p`). It is a Go-style flag requiring an explicit argv value; omitting it while piping via stdin causes `agy` to exit with status 2 (confirmed live via `triapi`'s `probe_models()` crashing).
- The stdin attempt regressed all `agy` calls across the board and was fully reverted: `scripts/llm_client.py`'s `_call_agy_cli()` and `_call_claude_cli()` are back to their byte-identical original forms; `tests.test_branch_features` and `tests.test_tier5_librarian` pass (93 tests OK).
- Deleted hallucinated test file `tests/test_llm_client_agy_stdin.py` generated during the attempt (which referenced a nonexistent nvidia-docker-based `_run_llm` function).
- Updated `AGENTS.md`'s `tier_5_librarian` bullet's 'Known open bug' note via librarian CLI to record this finding to prevent future stdin-based fix attempts.
- Real fix needs to be designed (e.g. prompt-size guard in `_call_agy_cli` failing fast / falling through before hitting OS argv limit). Requeued for future session.

### 3. New Systemic Gap Discovered & Queued
- Dispatched items using only `python3 -m py_compile <new_test_file>` as `verify_command` can report false success on test files with hallucinated imports or nonexistent function calls, since `py_compile` only validates syntax, not name/import resolution.
- `scripts/dispatcher.py` default verify-command logic for test files must include unittest import/collection checks. Queued as a priority item.

### 4. Queue item 3 (`staleness_precheck` false-negative FRESH) — RESOLVED
- Fixed in `scripts/doc_staleness.py` via `_STALENESS_QUESTION_PHRASES` leading gate in `should_skip_model_call()`: fast git-epoch skip only runs when description has code-sync-staleness phrases; all other tasks force a real model call.
- Regression tests added in `tests/test_tier5_librarian.py` (96 tests pass).
- Note: run `20260827-222943-2c134b` had a false human_handoff due to `verify_cmd` case-insensitive grep for `'skipped'` matching method names. Follow-up queued for anchored SKIP pattern grepping.

### 5. Queue item 4 — UNTOUCHED (OPEN)
- Item 4 (dynamic-shell-expression-target routing bypass) remains open.

**Separately, on hold for the user (unchanged from the prior file):**
- **Virtual Codebase Plan** (`VIRTUAL_CODEBASE_PLAN.md`) — user wants to
  work on this one together, personally.
- Consolidate target-repo-specific content out of TriAPI's own docs —
  goes through TriAPI itself, not hand-drafted.
- `docs/TUI_plan.md` — still untracked/unplanned, still blocked by the
  one-plan-per-repo gate like everything else.
