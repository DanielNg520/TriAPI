# 2026-08-26 06:30 UTC — ACTIVE: `agy` fallback leg + HTTP-timeout fix complete, committed; session closed for the day

**This is the primary file to read to resume work — everything else in
`docs/carryover/` is historical/completed context only.**

## Current state

Session closed out cleanly. All of this session's changes (see "What
happened" below) are **committed** — check `git log -1` / `git status` on
resume to confirm the tree is clean; if it isn't, something changed
between sessions and this file's "current state" is stale, trust `git`
over this paragraph. Full 199-test suite was green at commit time.

Run `20260825-194415-b54313` (agy fallback leg + shared `_HTTP_TIMEOUT`)
finished: all 9 plan items done, 7 by the pipeline itself, 2 resolved
manually (see below). `AGENTS.md`'s checkboxes for this run's own plan
block were flipped via `agents_md_gate.mark_plan_complete()` (not a
hand-edit) before committing.

**Nothing is queued mid-flight** — there is no paused dispatch, no
uncommitted diff, no open human_handoff to pick back up. Next session can
start fresh from the "Next up" queue below, or from whatever the user asks
for first.

## What happened this session

**1. Resumed dispatch off-peak** (confirmed via `budget_guard.check_tier3_peak_hours_ok()`,
`ok=True` at 04:11 UTC) per the prior session's pause. Phase 1 (shared
`_HTTP_TIMEOUT` constant + new test file) and the first two Phase 2 items
(config/tiers.yaml `fallback_agy` key + chain; `librarian_escalate.py`'s
new leg) all resolved automatically (tier_4/tier_3).

**2. Real pipeline bug found and fixed directly (not through the pipeline
— this was blocking the pipeline itself): `scripts/librarian_escalate.py`'s
new `fallback_agy` leg called `llm_client.execute_agy(...)`, a function
that never existed** — every tier that touched this file (and the sibling
test file, which mocks the same nonexistent symbol) hallucinated the name
instead of reusing `llm_client.execute_llm(provider="agy", ...)` the way
`tier3_escalate.py` actually does. This stalled item `p2-i2`
(`tests/test_tier5_librarian.py`) through a full `human_handoff` after
Tier 4→3→2→1 all failed on the same `AttributeError`. **Fix:** added a
thin `execute_agy(model, prompt, system_prompt=None, effort=None)` wrapper
to `scripts/llm_client.py` that delegates to the existing `_call_agy_cli()`
— no duplicated subprocess logic, and it matches what both the production
code and the test file already (correctly, as it turned out) expected.
Full 199-test suite confirmed green after this fix.

**3. Manually resolved two stuck dispatch items per `AGENT_GUIDE.md`'s
documented human_handoff workflow** (verify real state, hand-patch,
`results[]` → `status: success`/`resolved_by: manual`, refresh
`content_hash` via `regression_guard.hash_file()`, resume) rather than
letting the pipeline keep re-attempting and churning:
   - `tests/test_tier5_librarian.py` (item `p2-i2`) — once `execute_agy`
     existed, the file already on disk (written by an earlier Tier 3/1
     attempt) passed all 22 `test_tier5_librarian` tests and the full
     suite; just needed its `results[]` entry flipped, no further edit.
   - `ARCHITECTURE.md` (item `p3-i0`) — the librarian's own staleness
     precheck returned a false "FRESH" (not-stale) verdict for a doc that
     in fact had zero mentions of `fallback_agy`/`_HTTP_TIMEOUT`
     (confirmed via `grep`), so no leg ever produced real content; the
     doc-level Tier 3 (agy) fix-forward attempt then produced an edit
     whose SEARCH block didn't match and got reverted, landing at
     `build_failed`/`resolved_by: None` with no escalation file written
     (this doc-target failure path doesn't call
     `orchestrator.human_handoff()` the way item-level handoffs do — a
     minor inconsistency, not fixed, low value). Added a new "## Tier 5 —
     doc librarian fallback chain and CLI/HTTP timeouts" section by hand
     (`ARCHITECTURE.md` had no Tier 5 section at all — it still describes
     itself as "four tiers" throughout, a separate/larger staleness gap
     out of scope for this item, see queue below).

**4. Remaining Phase 3 items (`AGENTS.md`, the scripts-directory reference
doc, this carryover-index update) done directly rather than through the
pipeline**, given (a) they're small, mechanical, well-specified index
updates to TriAPI's own docs — squarely "fix TriAPI's own docs directly"
territory per standing guidance — and (b) the local Ollama primary leg was
observed timing out at the full 600s per doc-shaped item this session
(see queue item 2 below), making a third or fourth pipeline round-trip
for trivial edits a poor use of the DeepSeek peak-hours-constrained
window. Both `AGENTS.md` (now 54,700 chars) and the scripts reference doc
(34,544 chars) stayed well under the 73,728-char ceiling.

## Worth queuing (not urgent, found this session)

- **`ARCHITECTURE.md` is broadly stale**, independent of the fix above —
  it still describes "four tiers" throughout (Tier 2 = Nemotron, Tier 3 =
  DeepSeek) even though the real Phase 33 tier flip (DeepSeek→Tier 2,
  agy→Tier 3, Ollama→Tier 4) and the Tier 5 librarian addition both
  predate this session. The new Tier 5 section added this session is
  accurate but sits awkwardly next to an outdated tier table/escalation
  diagram above it. Plan/dispatch a proper refresh rather than hand-fixing
  further — this is real feature-shaped doc work, not a one-line edit.
- **Doc-target `build_failed` (no escalation file) vs. item-level
  `human_handoff` (writes one) is an inconsistent failure surface** —
  `dispatcher.py`'s doc-routing path stops the run without calling
  `orchestrator.human_handoff()`, unlike the item-level path. Not fixed
  (rare, low-value, workaround is reading `logs/runs/<id>.log`'s tail
  instead of a `logs/escalation_*.md` file). Mention only so the pattern
  is recognized quickly if it recurs.
- **Local Ollama (`mistral-small:latest`, the Tier 5 primary leg) is
  running slow enough to hit the full 600s `_HTTP_TIMEOUT` on ordinary doc
  edits** (observed live this session on the `ARCHITECTURE.md` item,
  10 minutes to time out before falling through to `fallback_local`).
  Worth a closer look at what's contending for the iGPU/RAM outside
  `resource_guard.yaml`'s paused-service list — not investigated this
  session.

## Standing rules (accumulated, unchanged this session)

- Allowed models, no Gemini except `agy`/Jules.
- Everything configurable, no hardcoded provider/tier paths.
- OpenRouter shared rate limit (20 RPM/1000 RPD pool-wide).
- DeepSeek peak-hours windows: `01:00-04:00` and `06:00-10:00 UTC`,
  weekdays, live on `tier_2_manager`.
- Doc architecture: `AGENTS.md`/`CARRYOVER.md` are permanent index files,
  never pruned; real content in `docs/carryover/`/`docs/agents/`.

## Next up (priority order, carried forward from the prior session's queue)

**1. DONE (this file).** `agy` `tier_5_librarian` fallback leg +
`_HTTP_TIMEOUT` root fix — complete and committed, see above.

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
`tiers.yaml`); complexity-aware router ahead of the tier ladder;
`ARCHITECTURE.md` refresh (new item, see "Worth queuing" above).

**Separately, on hold for the user (not part of the ordering above):**
- **Virtual Codebase Plan** (`VIRTUAL_CODEBASE_PLAN.md`) — user wants to
  work on this one together, personally.
- Consolidate target-repo-specific content out of TriAPI's own docs —
  goes through TriAPI itself, not hand-drafted.
- `docs/TUI_plan.md` — untracked draft, not yet planned/dispatched,
  blocked by the one-plan-per-repo gate like everything else.
