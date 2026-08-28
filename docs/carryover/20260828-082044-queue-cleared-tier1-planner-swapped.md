# 2026-08-28 08:20 UTC — ACTIVE: 3 of 4 queued bugs resolved, tier_1_planner swapped off a hallucinating model; nothing mid-flight

**Working tree is clean, no paused run, no pending approval.** `git log -1`
should show `c9f92c3` (or later) as `HEAD`. Safe to start fresh work
immediately — this file is a resume briefing, not a stuck-state report.

## Current state

Everything below landed and is committed on `main`:

1. **`AGENTS.md` bloat (was ~2x the 73,728-char ceiling) — RESOLVED**
   (`d98de74`). A ~71.6KB fully-hallucinated `triapi:plan` block was
   deleted outright; 5 legitimate completed plan blocks were archived to
   `docs/agents/20260828-044229-agents-md-historical-plan-blocks-archive.md`.
   File is now ~64KB, comfortably under ceiling.
2. **`agy` CLI `Argument list too long` crash — STILL OPEN, reopened with
   corrected understanding** (`a318610`). A stdin-based fix was tried and
   reverted: **confirmed live that `agy`'s `-p` flag does not accept a
   value via stdin** (it's a Go-style flag requiring an explicit argv
   value; omitting it and piping stdin makes `agy` exit status 2 — this
   crashed `triapi`'s own `probe_models()` pre-flight check). `_call_agy_cli()`
   and `_call_claude_cli()` in `scripts/llm_client.py` are both back to
   their original, working, argv-based forms — do not attempt the stdin
   approach again. The real fix still needs designing: most likely a
   prompt-size guard inside `_call_agy_cli()` that fails fast (or falls
   through to `fallback_local`) before attempting a doomed argv-based
   subprocess call, rather than letting the OS kill it.
3. **`doc_staleness.py`'s `should_skip_model_call()` false-negative FRESH
   bug — RESOLVED** (`55fe3dd`). Was skipping the real model call (fast
   git-epoch check) for *any* Tier 5 task, including plain appends/index
   updates that have nothing to do with code-sync freshness, silently
   reporting false "success" with zero real edit. Fixed per user-chosen
   direction: a new `_STALENESS_QUESTION_PHRASES` leading gate now
   requires the description to contain a genuine staleness phrase (e.g.
   "stale", "out of date") before the fast-path git check runs at all;
   any other description always forces a real model call. Regression
   tests in `tests/test_tier5_librarian.py` (96 tests, OK).
4. **Dynamic shell-expression target bug in `dispatcher.py`'s `tier_5`
   routing — RESOLVED** (`c9f92c3`). A breakdown item's `target` like
   `docs/carryover/$(jq -r '.active' docs/carryover/index.json)` was
   used literally as a Python path (never shell-expanded), silently
   producing false "success" against a nonexistent file. Fixed via a new
   `_resolve_dynamic_target()` helper wired into `dispatch()`'s per-item
   loop; covered by `tests/test_dispatcher_dynamic_target_resolution.py`
   (4 tests). Full suite: 100 tests, OK.
5. **`tier_1_planner`'s model swapped off a hallucinating free model**
   (`c9f92c3`). `nvidia/nemotron-3-ultra-550b-a55b:free` was repeatedly
   fabricating entire fake tool-call transcripts (a nonexistent
   `Dispatcher` class, a fictional carryover file with invented queue
   items), truncating mid-sentence, and producing degenerate
   self-repeating non-plans — roughly half of ~10 `triapi plan` calls in
   one session were unusable garbage, confirmed live multiple times
   including *while trying to plan the fix for this very problem*.
   Swapped to `dots-studio/dots-3-note-preview:free` (already-approved,
   previously `tier_4_worker`'s pre-Phase-33 model — not new/unvetted).
   Live-verified post-swap: `probe_models()` succeeds, a direct
   `planner.plan_turn()` call returns a clean coherent response, full
   suite green. See [[project_tier1_planner_nemotron_hallucination]]
   memory for the full incident writeup.

## New bugs/gaps found this session, not yet fixed (queued below)

- **`py_compile`-only verify commands can't catch hallucinated test
  files.** A dispatched item whose `verify_command` is just
  `python3 -m py_compile <new_test_file>` reports success even when the
  file imports a nonexistent symbol or calls a nonexistent function —
  `py_compile` only checks syntax, not that names resolve. Confirmed live
  twice this session (once with a fully fabricated Docker-based test
  file, once with a 3-bug fixture file). `dispatcher.py`'s default
  verify-command logic for new test files should include an actual
  `unittest` import/collection check.
- **Bare `grep -i 'skipped'` in a verify command false-triggers on test
  *method names*** containing that substring (e.g.
  `test_jules_test_skipped_when_budget_check_refuses`), not real skipped
  tests — caused one confirmed false `human_handoff` this session. Any
  future verify command checking for real test skips should anchor to
  unittest's actual per-test/summary syntax (e.g. `\.\.\. skipped$` or
  `^OK \(skipped=`), never a bare substring match.
- **Tier 3 (`agy`) made two unauthorized out-of-scope edits** during this
  session's dispatch attempts, both explicitly outside the item's stated
  diff scope: rewrote `_call_claude_cli()` when only `_call_agy_cli()` was
  in scope, and separately rewrote `handle_fix_forward()`'s peak-hours
  logic when only item-target wiring was in scope. Both caught via
  `git diff` review before commit and reverted by hand. Not yet
  root-caused or fixed at the pipeline level — worth a scope-guard or
  diff-review check that flags an edit touching a function outside the
  item's named target/description.
- **`triapi plan`'s planning turn has no sanity check on its own output**
  — a truncated, hallucinated, or degenerate (self-repeating,
  zero-content) response gets appended to `AGENTS.md` and can be
  auto-approved by a blind piped `approve`. `breakdown_phase()` already
  has a "0 phases produced" guard for its own failure mode; the planning
  turn itself has no equivalent. Worth a minimum-content/sanity check
  before a plan is treated as approvable (this is separate from, and in
  addition to, the tier_1_planner model swap above — a bad model can
  still occasionally misfire even on a better model).

## Standing rules (accumulated, still in effect)

- **Never do TriAPI's job** — fix TriAPI's own code/docs directly is fine
  for docs; route code/config changes through `triapi plan`/`dispatch`
  against TriAPI's own repo. The one confirmed, narrow exception this
  session: when the pipeline itself cannot function until a specific
  change lands (AGENTS.md bloat blocking edits to AGENTS.md; the planner
  model being the very thing broken while trying to fix the planner) —
  ask first, don't assume the exception applies silently.
- **Use `scripts/librarian_escalate.py`'s CLI for doc edits**
  (`AGENTS.md`/`CARRYOVER.md`/`PLAN.md`/`docs/carryover/*.md`), not hand
  `Edit`/`Write` — except session-end carryover-file rotation itself
  (creating a new dated file + updating `index.json`/`CARRYOVER.md`),
  which has consistently been done by direct edit across sessions as
  established index-architecture mechanics, not routine content.
- **Always read a `triapi plan` turn's actual text before approving.** A
  blind piped `approve` can auto-approve fabricated/truncated/degenerate
  content — confirmed multiple times this session even after switching
  models. Read the printed plan before responding.
- When invoking `scripts/librarian_escalate.py` directly, **always
  literally name the target file by basename in `--description`** — a
  generic description can still trip a staleness/context ambiguity even
  after this session's fix.
- DeepSeek peak-hours windows unchanged: `01:00-04:00` and
  `06:00-10:00 UTC`, weekdays. Position-independent lookup via
  `budget_guard.resolve_deepseek_tier()` — verify which tier is really
  DeepSeek by checking `config/tiers.yaml` directly, not from memory.
- `tier_5_librarian`'s primary provider is `agy`/Gemini 3.7 Flash
  (`effort: low`); fallback chain unchanged
  (`fallback_local` → `fallback_agy` → `fallback_openrouter` →
  `log_and_notify`). `fallback_agy` is a *different* purpose/model
  (Gemini 3.1 Pro, `effort: high`) — don't confuse the two.
- `tier_1_planner`'s model is now `dots-studio/dots-3-note-preview:free`
  (was Nemotron — see above). If planning output looks fabricated,
  truncated, or degenerate again, don't assume it's a one-off; check
  whether this model also needs to be swapped.

## Next up (priority order)

1. **Design and fix the real `agy` argument-length bug (queue item 2)** —
   a prompt-size guard in `_call_agy_cli()`, not a stdin conversion (that
   premise is disproven, see above). Route through `triapi plan`/`dispatch`.
2. **Fix the `py_compile`-insufficient verify-command gap** — new test
   files' default verify command should actually import/collect the
   tests, not just syntax-check.
3. **Fix the bare-`skipped`-substring false-positive pattern** in verify
   commands.
4. **Investigate/fix Tier 3's out-of-scope-edit pattern** (two confirmed
   incidents this session) — needs root-causing, possibly a diff-scope
   guard.
5. Consider a minimum-content/sanity check on `triapi plan`'s own output
   before it's treated as approvable (separate from the model swap).
6. Resume `20260827-132236-806da1` to pick up its one remaining cosmetic
   `AGENTS.md` note, or let it lapse — the substance is already done.
7. Older carried-forward items (unchanged, still open): `cost_log.jsonl`
   size split (~858KB), `git_ops.push()`'s unconditional `git add -A`
   scoping gap, OpenRouter `[PHONE]` filter root-cause, Groq provider
   addition, architecture items (backend registry, complexity router,
   per-tier fallback toggles).

**Separately, on hold for the user (unchanged across sessions):**
- **Virtual Codebase Plan** (`VIRTUAL_CODEBASE_PLAN.md`) — user wants to
  work on this one together, personally.
- Consolidate target-repo-specific content out of TriAPI's own docs —
  goes through TriAPI itself, not hand-drafted.
- `docs/TUI_plan.md` — still untracked/unplanned, still blocked by the
  one-plan-per-repo gate like everything else.

*(Full session narrative, including the exact sequence of failed
`triapi plan` attempts and root-cause diagnosis for each item above,
lives in the prior file,
`20260828-012100-tier5-agy-swap-paused-4-new-bugs-queued.md` — read it
only if you need that level of detail; this file's summary is enough to
resume.)*
