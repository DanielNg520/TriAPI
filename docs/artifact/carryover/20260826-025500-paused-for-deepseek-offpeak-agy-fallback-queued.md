# 2026-08-26 02:55 UTC — RESOLVED: session paused mid-dispatch for DeepSeek peak hours; resume with `triapi dispatch 20260825-194415-b54313`

**Resolution (2026-08-26 06:xx UTC):** Run `20260825-194415-b54313` resumed
off-peak and completed. `config/tiers.yaml`'s `tier_5_librarian.models`
gained `fallback_agy: default` and `escalation_rules.tier5_to_fallbacks.chain`
is now `[fallback_local, fallback_agy, fallback_openrouter, log_and_notify]`.
`scripts/llm_client.py` gained the `_HTTP_TIMEOUT` constant (600s default,
`TRIAPI_HTTP_TIMEOUT` override) used by `_call_openai_api()`/`_call_gemini_api()`,
plus the `execute_agy()` public wrapper `librarian_escalate.py`'s new leg
calls. New test file `tests/test_llm_client_http_timeout.py`. Full 199-test
suite green. Two items needed manual resolution mid-run (see the new active
file for details) rather than the pipeline resolving them unattended;
"Next up" item 1 below is done. See the new ACTIVE file for current state
and the rest of the queue.

**This is the primary file to read to resume work — everything else in
`docs/carryover/` is historical/completed context only.**

## Current state

Working tree: only `AGENTS.md` modified (see item 1 below), untracked
`docs/TUI_plan.md` (pre-existing, unrelated, still on hold per prior
session). Nothing else uncommitted. Full 194-test suite was last
confirmed green at the end of the prior session (`docs/carryover/20260825-173000-tier-flip-complete-false-success-bug-fixed.md`).

**A `triapi plan`/`dispatch` run is queued and ready, deliberately paused
before Phase 2's breakdown call could hit DeepSeek during a peak-hours
window — resume it once DeepSeek is off-peak (see "Why paused" below).**

## What happened this session

**1. Bookkeeping fix (not a code bug): `AGENTS.md`'s checkboxes for the
already-completed run `20260825-154633-8927c3` were still all unchecked**,
incorrectly making `triapi plan`'s one-plan-per-repo gate (`agents_md_gate.find_incomplete_plan()`,
which only inspects the *most recent* appended block) refuse a new plan.
Root cause: that run's Phase 3/4/5 items were closed out via manual state
bookkeeping (`manual_test_supervisor`, prior session) rather than the
normal `_breakdown_and_dispatch()` completion path in `scripts/triapi.py`
(line ~201-202), so `agents_md_gate.mark_plan_complete()` never ran for
it. The run genuinely is complete (10/10 breakdown items, all `success`,
committed as `5a6ae01`) — this was purely a stale index, not real
unfinished work. Fixed by calling the existing `agents_md_gate.mark_plan_complete()`
function directly (not a hand-edit of the markdown, not a code change):
```
PYTHONPATH=. python3 -c "
from scripts import agents_md_gate, dispatcher
state = dispatcher.load_run('20260825-154633-8927c3')
n = sum(len(p['items']) for p in state['breakdown']['phases'])
agents_md_gate.mark_plan_complete(state['project_dir'], state['run_id'], n)
"
```
Verified: that run's block now shows `unchecked=0, checked=10`. **This
change is still uncommitted** (`git diff AGENTS.md` — 10 lines flipped
`[ ]`→`[x]`, nothing else touched) — commit it whenever the next real
commit happens, no need for a standalone commit just for this.

**Worth queuing as a real fix later** (not urgent, low-value/rare): the
gap itself — manual-bookkeeping closeouts don't call `mark_plan_complete()`
— will recur if a future session hand-resolves a run's remaining items
again. Not fixing now since it's a rare path with a known one-line
workaround (the command above); mention only so the pattern is
recognized quickly if it resurfaces.

**2. Kicked off the top of the previous session's queue**: a `triapi plan`
covering both (a) adding `agy` (Antigravity CLI, `gemini-3.1-pro`) as a
`tier_5_librarian` fallback leg, and (b) the root-cause fix for a fresh
crash found this session — `scripts/llm_client.py`'s `_call_openai_api()`/
`_call_gemini_api()` both hardcode `requests.post(..., timeout=300)` with
no override, the same shallow-timeout bug class already fixed today for
the CLI subprocess path (`_CLI_TIMEOUT` 300→600, commit `5a6ae01`) but
missed for the HTTP path — confirmed as the live cause of run
`20260825-174353-a25d29`'s `self_fix_drafted` crash (`tier_5_librarian`
probe hit `Read timed out. (read timeout=300)` against local Ollama).

Plan was drafted, approved (single turn, no revisions needed — the
prompt was detailed enough), and appended to `AGENTS.md` as run
**`20260825-194415-b54313`** (3 phases: Tier-5 `agy` fallback leg +
shared `_HTTP_TIMEOUT` constant/env-override; test updates including
`tests/test_tier5_librarian.py` escalation-order chain
`primary → fallback_local → fallback_agy → fallback_openrouter → log_and_notify`
and a new `tests/test_llm_client_http_timeout.py`; docs/index upkeep in
`ARCHITECTURE.md`/`AGENTS.md`/`docs/agents/20260825-100000-scripts-directory-reference.md`
and this same active-carryover-file convention). Run status: `planned`,
0/0 items dispatched — breakdown never started.

## Why paused

Dispatch (`triapi dispatch 20260825-194415-b54313 --background`) was
started at 19:48 local (2026-08-26 02:48 UTC) and terminated cleanly by
`SIGTERM` a few minutes later, per explicit user instruction ("stop
gracefully when you can... continue in a new session when deepseek is in
offpeak"). At termination time it was 02:52 UTC — **inside DeepSeek's
`01:00-04:00 UTC` peak window** (`config/tiers.yaml`'s
`tier_2_manager.peak_hours_utc`, moved here from Tier 3 in the prior
session's tier-flip). Breakdown (Phase 2, uses Tier 2 = real DeepSeek
API) hadn't produced any output yet when killed — confirmed via
`logs/runs/20260825-194415-b54313.json`: `status: "planned"`,
`breakdown.phases[0].items: []`, `results: []`. **Nothing was mid-write
— safe to resume from scratch, no partial state to reconcile.**

**Off-peak windows** (from `config/tiers.yaml`, weekdays,
America/Los_Angeles wall-clock underlying UTC list — see
`check_tier3_peak_hours_ok()`'s docstring for the exact conversion if the
literal UTC windows below ever look off for a given date):
- Currently in peak: `01:00-04:00 UTC` (ends 2026-08-26 04:00 UTC / 21:00
  PDT 2026-08-25).
- Also peak: `06:00-10:00 UTC`.
- **Safe off-peak windows to resume in**: `04:00-06:00 UTC` or
  `10:00-01:00 UTC` (i.e. most of the day/evening Pacific time).

## Resume instructions (next session)

1. Confirm off-peak: `date -u`, check against the windows above (or just
   run `PYTHONPATH=. python3 -c "from scripts import budget_guard; print(budget_guard.check_tier3_peak_hours_ok())"` —
   despite the function's name it now resolves whichever tier is really
   DeepSeek, i.e. `tier_2_manager`, position-independently).
2. `triapi dispatch 20260825-194415-b54313` (foreground) or `--background`
   — no re-planning needed, the approved plan is already saved and
   appended to `AGENTS.md`.
3. Supervise per standing practice: verify each item's real diff, don't
   trust reported status alone (`feedback_verify_dont_trust_status`).
4. On completion, this file's own "Next up" section below still has the
   remaining queue items — update the active-carryover pointer per the
   convention in `CARRYOVER.md`.

## Standing rules (accumulated, unchanged this session)

- Allowed models, no Gemini except `agy`/Jules.
- Everything configurable, no hardcoded provider/tier paths.
- OpenRouter shared rate limit (20 RPM/1000 RPD pool-wide).
- DeepSeek peak-hours windows: `01:00-04:00` and `06:00-10:00 UTC`,
  weekdays, live on `tier_2_manager`.
- Doc architecture: `AGENTS.md`/`CARRYOVER.md` are permanent index files,
  never pruned; real content in `docs/carryover/`/`docs/agents/`.

## Next up (priority order, carried forward from the prior session's queue)

**1. (IN PROGRESS, this file)** `agy` `tier_5_librarian` fallback leg +
`_HTTP_TIMEOUT` root fix — plan approved as run `20260825-194415-b54313`,
paused before dispatch started. Resume per above.

**2.** New design question: should `orchestrator.run_task()` treat a
Tier 3 CLI *timeout* as a soft escalate-to-Tier-2 rather than a hard
crash? Not attempted yet — plan/dispatch this properly.

**3.** Make every tier's fallback mechanism individually on/off
configurable.

**4.** Unresolved OpenRouter `[PHONE]` filter root-cause question (shape-
specific vs. any long digit run) — retry when convenient.

**5.** Groq provider addition (`qwen/qwen3.6-27b`) — rate limits need
re-verifying against Groq's real docs first.

**6.** Architecture items (self-feature work — plan/dispatch, don't
hand-build): named backend registry (`backends:` section in
`tiers.yaml`); complexity-aware router ahead of the tier ladder.

**Separately, on hold for the user (not part of the ordering above):**
- **Virtual Codebase Plan** (`VIRTUAL_CODEBASE_PLAN.md`) — user wants to
  work on this one together, personally.
- Consolidate target-repo-specific content out of TriAPI's own docs —
  goes through TriAPI itself, not hand-drafted.
- `docs/TUI_plan.md` — untracked draft, not yet planned/dispatched,
  blocked by the one-plan-per-repo gate like everything else.
