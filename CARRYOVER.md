# Carryover — 2026-08-18

**Standing rule for this file: stay brief.** Only what's needed to resume
the *next* session goes here. Finished-work narrative, per-round findings,
and "what happened" writeups belong in `PLAN.md` (this repo's permanent
build-history/decisions record), never here. Fold an item out of this file
into `PLAN.md` the moment it's resolved, in the same edit — don't leave it
lingering here in past tense. Full history through 2026-08-18 lives in
`PLAN.md`'s "Session Carryover Log" section.

**Read this first in a new session.** Then `AGENTS.md` for the file/dir
index, `AGENT_GUIDE.md` for the operating manual (what's safe to hand-edit
vs. must route through `triapi plan`/`dispatch`).

## Current state

- **oh-my-llama Consolidation Phase 5:** Sub-Phases 5A–5F all dispatched and
  verified (each needed at least one real post-hoc fix after its own run
  reported `completed` — see `PLAN.md`'s carryover log for the bug-by-bug
  detail). **Only 5G is left, blocked on a 7-day production soak** of
  oh-my-llama's new `src/semai/` daemon runtime — not started yet. Nothing
  to dispatch there until the soak completes or the user says to
  start/track it.
- **TriAPI's own repo:** Tier 4 task-type routing landed 2026-08-18.
- **All four `AGENT_GUIDE.md` worked test cases are done:** ghostwriter,
  TriAPI self-fix, TriAPI learning (lessons + critique), Amazon HTML
  ingestion. (The old standalone `GHOSTWRITER_PLAN.md` said "queued" — that
  was stale; it's folded into `PLAN.md` now, marked completed.)

## Next up


- **Self-Improvement feature is dispatching** (run `20260818-152401-a589da`,
  17 items across 5 phases: `hivemind_util.py` retrieval, `judge.py`
  design-review + pattern extraction, dispatcher hook + fix-forward,
  tech-debt logging, docs). In progress as of 2026-08-18 — resume with
  `triapi dispatch 20260818-152401-a589da --background` if it's not
  already running. Two real bugs hit and fixed mid-run (detail in
  `PLAN.md`'s carryover log once landed): a truncated-response guard gap
  in `extract_code()` (`tier3_escalate.py`/`tier4_worker.py`, shared by
  Tier 1/2), and a plan item missing `scripts/hivemind_util.py` from its
  own `context_files` (patched directly in the run's state JSON).

- **TOP OF QUEUE (user priority 2026-08-19, supersedes the previous top item
  below): monolithic-file chunking + Tier-4-timeout-threshold guard.** User
  observation, confirmed against real data from this run: the plan chunks
  *tasks* into small units but not *files* — Phase 3/4's items repeatedly
  targeted the same, ever-growing `tests/test_branch_features.py` (kept
  saying "extend tests/test_branch_features.py" instead of creating a new
  file per feature), so Tier 4 had to ingest 1400+ and growing lines of
  existing content as context regardless of how small the new task was.
  By contrast, items targeting brand-new standalone files
  (`test_hivemind_util.py`, `test_judge.py`) never hit the 300s Tier 4
  timeout pattern (they had other bugs, but not this one) — the prompt
  size is dominated by the pre-existing file's total size, not the diff.
  Second, related finding: the escalation rule requires 2 consecutive
  Tier 4 failures before escalating to Tier 3 — on a file already too
  large for one 300s window, that guarantees ~10 minutes of dead waiting
  (2×300s, zero output) before Tier 3 (which resolved most of these in
  15-30s once reached) gets a chance. Free in dollars (local Ollama), not
  free in wall-clock time.

  **User-refined spec (2026-08-19), two patches, both top priority:**
  1. **Hard file-length ceiling, source code generally, not just tests**:
     no file TriAPI generates or extends should exceed Tier 4's context
     window (currently `num_ctx=24576`, see `tier_4_worker` in
     `config/tiers.yaml` / `call_ollama()` in `scripts/tier4_worker.py`).
     User's framing: a 1400+-LOC file is unproductive and unprofessional
     regardless of whether it's a test file — no legitimate design
     pattern or idiom justifies a single file that size; more LOC is
     exposed surface, not more value. This should be a hard plan-approval
     rule (reject/split at planning time), not just a soft preference —
     natural extension of the context_files grounding guard below, likely
     the same validation pass in `dispatcher.py`'s breakdown validation:
     estimate the target file's token count (existing content + planned
     addition) against the ceiling and reject/require-split if it would
     exceed it.
  2. **One Tier 4 failure, not two, when the failure is itself the
     oversize/timeout case**: if Tier 4's attempt fails specifically
     because it couldn't fit/finish within its context/time budget
     (distinguish from an ordinary `build_failed` on a normal-sized file,
     which should still get its full 2-attempt budget), escalate to Tier
     3 immediately on the first such failure — a second attempt against
     a file already shown to be oversized is a guaranteed-repeat 300s
     timeout, not a real second chance.

  New TriAPI feature work — route through `triapi plan`/`dispatch`, do
  not hand-implement.

- **#2 IN QUEUE (was TOP OF QUEUE 2026-08-18; superseded by the two file-size/
  timeout patches above per user priority 2026-08-19): mock-patch target
  lint check.** Immediate instance already
  fixed directly (`tests/test_branch_features.py`'s
  `DispatcherHookAndFixForwardTests`, 3 methods): each
  `@mock.patch("scripts.orchestrator.run_task")` was patching the wrong
  module — `scripts/dispatcher.py` imports via
  `from scripts.orchestrator import ... run_task ...` (name-binding import,
  copies the reference into `dispatcher`'s own namespace), so patching
  `scripts.orchestrator.run_task` never touched what `dispatcher.py`
  actually calls. Every one of these "unit" tests was firing the REAL
  `run_task` — real Tier 4/Ollama attempts (5+ min timeouts each),
  potentially cascading into real, billed Tier 2/3/1 API calls — on every
  single test-suite run. Confirmed live: a verification run hung 7+
  minutes with an ESTABLISHED TCP connection to `127.0.0.1:11434`. Fixed
  by correcting the 3 patch targets to `scripts.dispatcher.run_task`
  (2026-08-18) — no more real network calls, suite now runs in ~0.006s.
  **CONFIRMED RECURRING — same wrong-patch-target bug hit 2 more times in
  this same test class, one via the pipeline's own escalation attempts**:
  (1) `run_task` mocked with `{"status": "fixed", ...}` instead of the real
  `"success"` string (3 methods) — fixed directly; (2) the peak-hours-skip
  test's own assertions were inverted relative to its (correctly updated)
  mock, a leftover from the pre-correction spec — fixed directly; (3) **a
  4th wrong-patch-target instance**: `test_handle_fix_forward_failed_rebuild`/
  `_successful_rebuild` patched `scripts.tier4_worker.run_build` instead of
  `scripts.dispatcher.run_build` (same name-binding-import mistake) — this
  one was reintroduced by a *pipeline tier* while "fixing" an already-passing
  file (dispatch retried item [2-4] against content that already passed
  59/59; a tier rewrote it anyway and reintroduced this exact bug), fixed
  directly again 2026-08-19. Net: 5 known failures + 1 pipeline-caused
  regression, all fixed by hand across 3 rounds; suite is 59/59 clean as of
  2026-08-19. **New confirmed risk from round 3**: dispatch retrying an item
  whose file is already correct can cause a tier to regress it while
  "fixing" something that wasn't broken — worth folding into the systemic
  fix's scope (e.g., skip/short-circuit an item if its build_cmd already
  passes before invoking a drafting tier). Durable systemic fix still
  needed: a lint/plan-validation check flagging any `@mock.patch` target
  that patches a `from X import Y`-imported name at its *original* module
  instead of the *importing* module (the standard "patch where it's used,
  not where it's defined" mistake) — catch this class of bug before
  landing, not via a live hang or a pipeline regression. New TriAPI feature
  work — route through `triapi plan`/`dispatch`.

- **New gap found 2026-08-18, queued after Self-Improvement completes:
  context_files grounding guard.** CONFIRMED RECURRING — hit twice in the
  same run, two different symptoms, same root cause: a Tier 1-drafted plan
  item for a new test file doesn't ground the drafting tiers in either (a)
  the module it's testing, or (b) this repo's actual test-writing
  conventions, so every tier guesses blindly. Instance 1:
  `tests/test_hivemind_util.py`'s item never listed
  `scripts/hivemind_util.py` in `context_files` → wrong parameter name,
  wrong data format. Instance 2: `tests/test_judge.py`'s item had
  `scripts/judge.py` in context but no example *test* file and no
  "unittest, not pytest" instruction → every tier defaulted to `import
  pytest`, which isn't an installed dependency, and 4 escalation attempts
  (Tier4→3→2→1) all failed the same `ModuleNotFoundError` before human
  handoff. Both patched directly in the run's state JSON as a stopgap; the
  durable fix needs to be systemic. Spec: add a deterministic check (likely
  in `dispatcher.py`'s breakdown validation) for any item whose `target`
  matches a test-file naming convention (`tests/test_<name>.py` or
  similar): (1) if a same-stem source file exists in the repo
  (`scripts/<name>.py` etc.) and isn't already in `context_files`, auto-add
  it; (2) always include at least one existing test file from the same
  test directory as a style/convention anchor (this repo's is
  `tests/test_branch_features.py`) so the drafting tiers copy the real
  test framework/style instead of guessing; reject the plan at approval
  time with a clear reason if no existing test file can be found to anchor
  to. New TriAPI feature work — route through `triapi plan`/`dispatch`, do
  not hand-implement.

- **New gap found 2026-08-18, queued after Self-Improvement completes:
  plan phase-ordering / import-dependency guard.** A Tier 1-drafted plan
  sequenced Phase 3 (edits `scripts/dispatcher.py` to add
  `from scripts import ... tech_debt` at module load time) before Phase 4
  (creates `scripts/tech_debt.py`). Once Phase 3's item landed, `triapi`'s
  own CLI could no longer boot at all — `triapi` imports `dispatcher`,
  which now imports the nonexistent `tech_debt` module — a genuine
  bootstrap deadlock, since the pipeline needed to run to create the file
  it required just to start running. Unblocked by moving the two
  `scripts/tech_debt.py`-creation items from Phase 4 into Phase 3 (state
  JSON patch, user instruction 2026-08-18) — but the run was still stuck
  until `scripts/tech_debt.py` was hand-written directly (user-authorized
  in the moment), since even the *reordered* dispatch couldn't run without
  it. Spec for the durable fix: when a Tier 1 plan is approved, validate
  that no earlier phase/item introduces a module-load-time import
  (`from scripts import X` / `import scripts.X`) of a file first created
  by a *later* phase/item — either reject the plan with a clear ordering
  error, or auto-reorder so the creating item runs first. New TriAPI
  feature work — route through `triapi plan`/`dispatch`, do not
  hand-implement.

- **New gap found 2026-08-18, queued to dispatch immediately after the
  Self-Improvement feature run completes (user instruction 2026-08-18):
  Ollama lifecycle management for dispatch.** Currently `resource_guard.unload_other_ollama_models()`
  only unloads *other* resident models via Ollama's own API — it requires
  `ollama.service` to already be running, and nothing auto-starts it (found
  live: the service was down mid-session, `triapi dispatch` would have
  failed Tier 4 outright rather than bringing it up). User's spec for the
  fix (2026-08-18): once a `triapi dispatch` run starts, it has **full
  authority** over the shared Ollama service for that run's duration —
  start `ollama.service` if it's not active, unload other resident models
  as today. But it must be a **good citizen of a shared service**: on
  dispatch exit (success, failure, or interruption), restore Ollama to
  exactly the state it found it in before the run — if the service was
  off before, stop it again after; if it was on, leave it on; and if some
  other model was warm/resident before the unload, reload that same model
  back onto the GPU so it's warm again for whatever else uses this shared
  Ollama instance. Needs a "snapshot state before, restore after" wrapper
  around the existing pause/unload logic in `scripts/triapi.py`'s
  `cmd_dispatch` (same place `pause_services`/`unload_other_ollama_models`
  are already called) — new TriAPI feature work, route through `triapi
  plan`/`dispatch` per standing rule, do not hand-implement.

Otherwise: oh-my-llama's 5G once the soak clears.

