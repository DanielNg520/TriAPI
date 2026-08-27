# 2026-08-26 19:30 UTC — ACTIVE: Tier 3 timeout soft-escalation + ARCHITECTURE.md refresh complete, committed; tier_5-fed-into-_run_design_judge bug RESOLVED (gated dispatcher on critique.applies_to_tiers, regression tests added)

**This is the primary file to read to resume work — everything else in
`docs/carryover/` is historical/completed context only.**

## Current state

Session closed out cleanly. All of this session's changes are
**committed and pushed** (`60cd085`, TriAPI's own `git_ops.push()` at
run-completion time) — check `git log -1` / `git status` on resume to
confirm the tree is clean; if not, trust `git` over this paragraph. Full
regression suite (97 tests) was green at commit time.

Run `20260826-121026-fa6eea` finished: all 9 plan items done, 7 by the
pipeline itself, 1 resolved manually (Phase 3 item 1, see below), 1
`verify` item. `AGENTS.md`'s checkboxes for this run's own plan block
were flipped via `agents_md_gate.mark_plan_complete()` automatically at
completion (not a hand-edit).

**Nothing is queued mid-flight** — no paused dispatch, no uncommitted
diff, no open `human_handoff`. Next session can start fresh from "Next
up" below.

## What happened this session

**1. Pre-flight blocker, fixed before any dispatch could start:**
`stealth/ox-alpha` (then `tier_1_planner`'s primary OpenRouter model) had
been pulled from OpenRouter's catalog (confirmed live via `GET
/api/v1/models` — 404 on probe), which hard-crashed `probe_models()` and
blocked the entire pipeline before Phase 1 could even begin. User
confirmed the pull and gave explicit direction: standardize on
`nvidia/nemotron-3-ultra-550b-a55b:free` (not
`dots-studio/dots-3-note-preview:free`, which OpenRouter is separately
retiring 2026-09-30) and clean up all references to `ox-alpha`. Fixed:
`tier_1_planner.models.default` and `tier_5_librarian.models.fallback_openrouter`
in `config/tiers.yaml` both swapped to `nemotron-3-ultra-550b-a55b:free`
(config-only edit, financial-safety carve-out,
[[feedback_supervisor_never_do_triapi_job]]); stale comments in
`scripts/planner.py` naming `ox-alpha` corrected. **`stealth/ox-alpha`
removed from the allowed-models memory entirely** — see
`feedback_no_gemini_allowed_models.md`, updated this session.

**2. Phase 1 — Tier 3 CLI-timeout soft-escalation, via the pipeline,
clean:** confirmed a real gap (an `agy` CLI `subprocess.TimeoutExpired`
was indistinguishable from any other Tier 3 failure and propagated as an
uncaught `RuntimeError` out of `orchestrator.run_task()`, crashing the
whole item instead of falling through to Tier 2). Fixed:
`tier3_escalate.py` now catches `subprocess.TimeoutExpired` specifically
and returns `status: "timeout"`; `orchestrator.py`'s Tier 3 block treats
that status as a no-op log-and-fall-through (mirroring the existing
peak-hour-skip style) rather than raising. New
`tests/test_orchestrator_tier3_timeout_skip.py` proves a simulated
timeout lands on Tier 2, not a crash and not `human_handoff`. All 4 items
resolved automatically (tier_3/tier_4/tier_1/verify), full suite green.

**3. Phase 2 — `ARCHITECTURE.md` refresh via `tier_5_librarian`, needed
two manual retries, both because the model's first pass was
under-scoped, not because of a false-success bug:** the librarian's
first attempt (local `mistral-small`) reported `success` and *did* make a
real 2-line edit — but skipped the actual core ask (the stale "four
tiers" opening paragraph, the tier table's Tier 2/3 rows, the escalation
diagram labels). The pipeline's own verify step correctly caught this
(grep for `"four tiers|Nemotron"` still matched) and escalated to
`human_handoff` — **the false-success bug from prior sessions is
confirmed fixed; this was a genuine partial-completion gap, correctly
surfaced.** Resolved by retrying `librarian_escalate.py` directly (not
through a full pipeline round-trip) twice, each time with a narrower,
itemized description than the original broad one — mistral-small
handled a tightly-scoped 3-point instruction correctly on both retries.
Each retry's result was verified against the actual file diff before
trusting it, not just the reported JSON status (per
[[feedback_verify_dont_trust_status]]). `ARCHITECTURE.md` now correctly
describes the 5-tier state end-to-end.

**4. Phase 3 — `AGENTS.md` index update, a real dispatcher bug found and
worked around by hand:** item `p2-i0` ("invoke `librarian_escalate.py`
against `AGENTS.md`") reported `build_failed`, and initial investigation
found `AGENTS.md` had been mutated with 56 lines of raw plan-checklist
text pasted verbatim — which looked exactly like a hallucinated edit from
a repair tier that couldn't actually invoke a subprocess. **That
diagnosis was wrong and was caught before compounding it**: the pasted
block was `agents_md_gate.append_plan()`'s own legitimate output (written
automatically at `triapi plan` *approval* time, unrelated to this
specific dispatch item) — reverting it via `git checkout -- AGENTS.md`
would have destroyed real plan-tracking state needed later by
`mark_plan_complete()`. Caught by checking `scripts/agents_md_gate.py`
directly rather than trusting the first hypothesis, and fixed by
reconstructing the exact same state via `agents_md_gate.append_plan()`
called directly (using the run's own `plan_text` from
`logs/runs/<run_id>.json`) before re-applying the librarian's (separately
verified, correct) prose edits on top. The dispatcher's `results[]` entry
for that item was hand-patched to `status: "success",
resolved_by: "manual"` with a freshly recomputed `content_hash`
(`regression_guard.hash_file()`), per `AGENT_GUIDE.md`'s documented
`human_handoff`-equivalent manual-resolution workflow — then the run was
resumed and finished the last verify item cleanly. **The real root cause
of the original `build_failed` was confirmed and FIXED in a follow-up
dispatch** — `scripts/dispatcher.py`'s `_run_design_judge()` call is now
gated on `result['resolved_by']` being in `config/tiers.yaml`'s
`critique.applies_to_tiers` (which now includes `tier_4`, still excludes
`tier_5`), mirroring `scripts/orchestrator.py:82`'s existing pattern.
Regression tests added in `tests/test_design_judge_fix_forward_status.py`
and `tests/test_branch_features.py`.

## Worth queuing (not urgent except where noted)

1. **RESOLVED: `dispatcher.py`'s `_run_design_judge()` was ignoring `critique.applies_to_tiers`, triggering bogus fix-forward on tier_5 successes.** Root cause confirmed via `logs/triapi.log` lines ~54443-54446 and ~55006-55013 of the `20260826-121026-fa6eea` run. **FIXED:** `scripts/dispatcher.py`'s call to `_run_design_judge()` (around `dispatcher.py:1301-1302`) is now gated on `result['resolved_by']` being in `config/tiers.yaml`'s `critique.applies_to_tiers` list (which now includes `tier_4`, still excludes `tier_5`), mirroring `scripts/orchestrator.py:82`'s existing pattern. Regression tests added in `tests/test_design_judge_fix_forward_status.py` and `tests/test_branch_features.py`. A secondary, separate finding worth its own queue line: `scripts/librarian_escalate.py`'s 'FRESH' escape hatch (`librarian_escalate.py:277-280`) returned FRESH for both files on their second attempt (qwen2.5-coder fallback) even though both files demonstrably needed real edits — a possible false-negative freshness judgment that deserves its own investigation, separate from the design-judge gating bug.
2. **`logs/cost_log.jsonl` is ~858KB, ~11.6x this repo's 73,728-char
   Tier 4 ceiling.** Already surfaced by this run's own Phase 2 verify
   item (which passed anyway, since it only greps the tail). Needs
   splitting into smaller cohesive files, not mechanical truncation — see
   the item's own note in `logs/runs/20260826-121026-fa6eea.json` for the
   exact framing already drafted.
3. **`git_ops.push()` runs `git add -A` unconditionally** (`git_ops.py:141`),
   so any unrelated untracked file sitting in the working tree at
   run-completion time gets swept into that run's auto-commit and pushed
   to `origin/main` under a machine-generated message. Confirmed live
   this session: the user's own untracked `docs/TUI_plan.md` (explicitly
   on hold, not part of this or any plan) got bundled into commit
   `60cd085`. Not a data-loss risk (content unmodified) but a real
   commit-hygiene/scoping gap — worth a proper fix (scope the add to
   only the run's own touched files) rather than a blanket `-A`.
4. Unresolved OpenRouter `[PHONE]` filter root-cause question (shape-
   specific vs. any long digit run) — carried forward, still not
   retried.
5. Groq provider addition (`qwen/qwen3.6-27b`) — rate limits still need
   re-verifying against Groq's real docs first.
6. Architecture items (self-feature work — plan/dispatch, don't
   hand-build): named backend registry (`backends:` section in
   `tiers.yaml`); complexity-aware router ahead of the tier ladder;
   making every tier's fallback mechanism individually on/off
   configurable (carried forward from the prior session's queue).
7. Design question carried forward but now resolved in code this
   session: whether a Tier 3 CLI timeout should soft-escalate to Tier 2 —
   **yes, done, see Phase 1 above.** Removed from the queue.

## Standing rules (accumulated, updated this session)

- Allowed models: `nvidia/nemotron-3-ultra-550b-a55b:free` (primary,
  going forward), `dots-studio/dots-3-note-preview:free` (still allowed
  but sunsetting 2026-09-30, don't newly assign it), DeepSeek direct API,
  Claude Code CLI. `stealth/ox-alpha` **removed** — pulled from
  OpenRouter's catalog 2026-08-26. No Gemini except `agy`/Jules.
- Everything configurable, no hardcoded provider/tier paths.
- OpenRouter shared rate limit (20 RPM/1000 RPD pool-wide).
- DeepSeek peak-hours windows: `01:00-04:00` and `06:00-10:00 UTC`,
  weekdays, live on `tier_2_manager`.
- Doc architecture: `AGENTS.md`/`CARRYOVER.md` are permanent index files,
  never pruned; real content in `docs/carryover/`/`docs/agents/`.
- Doc edits to `AGENTS.md`/`CARRYOVER.md`/`ARCHITECTURE.md`-class files
  route through `scripts/librarian_escalate.py`, never hand-`Edit`/`Write`
  — **except** the narrow, documented `human_handoff`-equivalent
  recovery case (verify real state, hand-patch, refresh `content_hash`,
  resume) used this session for the `AGENTS.md` routing bug above.

## Next up (priority order)

1. `logs/cost_log.jsonl` size split (queue item 2).
2. `git_ops.push()` `git add -A` scoping fix (queue item 3).
3. OpenRouter `[PHONE]` filter root-cause (queue item 4).
4. Groq provider addition (queue item 5).
5. Architecture items: backend registry, complexity router, per-tier
   fallback toggles (queue item 6).
6. **Investigate `librarian_escalate.py`'s 'FRESH' false-negative** (from
   resolved queue item 1's secondary finding): qwen2.5-coder fallback
   returned FRESH for both `AGENTS.md` and `ARCHITECTURE.md` on second
   attempt even though both files needed real edits.

**Separately, on hold for the user (not part of the ordering above):**
- **Virtual Codebase Plan** (`VIRTUAL_CODEBASE_PLAN.md`) — user wants to
  work on this one together, personally.
- Consolidate target-repo-specific content out of TriAPI's own docs —
  goes through TriAPI itself, not hand-drafted.
- `docs/TUI_plan.md` — untracked draft as of last session, but got
  swept into commit `60cd085` this session by `git_ops.push()`'s `git
  add -A` (see queue item 3) — still not planned/dispatched, still
  blocked by the one-plan-per-repo gate like everything else, just now
  tracked in git earlier than the user may have intended. Flag this to
  the user; don't silently rewrite history to un-commit it.
