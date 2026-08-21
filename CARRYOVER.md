# Carryover — 2026-08-20

**Standing rule for this file: stay brief.** Only what's needed to resume
the *next* session goes here. Finished-work narrative, per-round findings,
and "what happened" writeups belong in `PLAN.md` (this repo's permanent
build-history/decisions record), never here. Fold an item out of this file
into `PLAN.md` the moment it's resolved, in the same edit — don't leave it
lingering here in past tense. Full history through 2026-08-19 lives in
`PLAN.md`'s "Session Carryover Log" section.

**Read this first in a new session.** Then `AGENTS.md` for the file/dir
index, `AGENT_GUIDE.md` for the operating manual (what's safe to hand-edit
vs. must route through `triapi plan`/`dispatch`).

## Current state

- **Queue items #1-#6 from the 2026-08-19 carryover, plus the embedding
  warm-up bug, are ALL DONE** as of tonight (2026-08-20): #1-#3 (TriAPI's
  own repo), #4a (already fixed 2026-08-19), #4b/#5 (oh-my-llama webui.py +
  AGENTS.md deep-clean), #4c (`ohmyllama/state.py` package split, done
  correctly this time), and run `20260820-111151-1d83d6` (`Ollama.warm()`
  routing embedding models to `/api/embeddings` instead of `/api/generate`)
  — that run's own status is `stopped_on_failure` because its live-log
  verification phase escalated to `human_handoff`, but the fix and its
  test were confirmed live afterward (400 error gone from `journalctl`,
  `run_tests.sh` green) and oh-my-llama's `AGENTS.md` has been pruned of
  both resolved plan blocks (224KB peak → 47.8KB). Full bug-by-bug detail
  — including four real TriAPI pipeline bugs found and fixed live along
  the way — is in `PLAN.md`'s "2026-08-20 — Queue drain" entry.
  `queued_plans/` (both plans in it were superseded by fresh regenerated
  plans this session, not resumed as originally written) has been deleted.
- **TriAPI's own repo has uncommitted changes from tonight's emergency
  mid-dispatch fixes**, not yet committed (I don't commit without being
  asked): `scripts/tier4_worker.py` (timeout default), `scripts/
  content_guard.py` (oversized-write shrink-allow fix), `scripts/
  dispatcher.py` (`_PHASE_HEADER_RE` bold-markdown fix,
  `_item_deletes_target_file` false-positive fix), `tests/
  test_content_guard.py` (new), `tests/test_file_size_ceiling_and_
  oversize_escalation.py`, `tests/test_plan_phase_split_and_completion_
  guard.py`. Full suite green (139/139) as of the last check. Ask the
  user before committing, or route through a `triapi plan` self-hosted
  run if that's preferred over a direct commit.
- **oh-my-llama Consolidation Phase 5:** still only 5G left, blocked on
  the 7-day production soak of `src/semai/`'s daemon runtime. Not
  started; nothing to do until the soak completes or the user says to
  track it.
- **`openclaw_plan.md`'s Gemini branch was audited, fixed, and its two
  genuinely non-duplicate ideas folded into `main`, committed
  (`33b4112`), not pushed.** The `Gemini` branch (separate, still has its
  full 11-plugin implementation, untouched) was reviewed against
  `openclaw_plan.md`'s requirements — 6 real security/correctness bugs
  found (`openclaw_audit.md`, since fixed on that branch with
  `TRIAPI_NO_TIER1=1`). Of the 11 plugins, 9 duplicated existing oh-my-llama
  capabilities (search, Gmail/Calendar, memory/RAG, file writes,
  Telegram/Gotify) and were deliberately not folded in; `computation-core`
  and `headless-browser`'s form-fill/PDF-export were genuinely new and
  ported into `main`'s real `src/semai/` architecture instead of the JS
  files (`src/semai/tooling/computation.py`, `src/semai/workers/
  browser_action.py` + a new `browser_action` intent kind, new
  `fill_form()`/`export_pdf()` on the existing `BrowserCapability`). Took
  8 dispatch rounds to land clean — Tier escalations repeatedly introduced
  real defects (a worker silently gutted to dead stubs, a fabricated test
  leaked from pipeline log content, a later round's test that asserted a
  bug as correct behavior, a dropped function argument, a too-narrow
  error-string check, two stale hardcoded test assertions masked by
  `run_tests.sh` aborting on first failure) — all caught by direct
  post-hoc verification against the actual files, never by trusting a
  reported "success". Also folded oh-my-llama's `main`-branch `AGENTS.md`
  (209KB, 21 fully-resolved plan blocks going back to 2026-08-16 that
  never got the doc-hygiene pass the `Gemini` branch already had) down to
  ~46KB. A pre-existing, unrelated `tests/test_watcher_worker.py`
  test-pollution flake was found and confirmed (via `git stash`) to
  already exist on stock `main` — not touched, out of scope, flagging
  here in case it resurfaces.
- **Real TriAPI pipeline bug found during the above, not yet fixed:**
  `"Critique error: Failed to parse Claude result JSON"` in
  `logs/triapi.log`, seen at least twice (runs `20260820-155059-ff015c`
  item p1-i1, and again on a later item) — Tier 1's critique step
  sometimes returns something that isn't valid JSON, and the failure is
  swallowed/logged rather than surfaced; the item still proceeds with
  `resolved_by=tier_2`/similar rather than retrying or escalating the
  critique itself. Worth a look at whatever parses the critique response
  in `scripts/orchestrator.py`.

## Next up

- **#6 — Virtual Codebase Plan (Tiered Planner-Materializer
  architecture):** see `VIRTUAL_CODEBASE_PLAN.md` at this repo's root.
  **User wants to work on this one together, personally** — hold off
  starting it solo; wait for the user.
- Fix the critique-JSON-parse-failure pipeline bug above.
- Otherwise: oh-my-llama's 5G once the soak clears.
