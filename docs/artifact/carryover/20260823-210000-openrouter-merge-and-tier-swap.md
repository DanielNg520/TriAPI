# 2026-08-23 21:00 — OpenRouter branch merge, Tier 3/4 swap, early bug fixes

- **`openrouter` branch merged into `main` (2026-08-23), commit `47cddb4`,
  NOT pushed to any remote.** All 4 tiers are config-driven/hot-swappable
  through `config/tiers.yaml` + `llm_client.py`'s single `execute_llm()`
  dispatch point, with a working `probe_models()` pre-flight gate and
  consistent fail-fast across all 4 tiers — confirmed by design and by a
  real live swap the same session (below): any tier slot can hold any
  provider (API, local model, or CLI), not just its original assignment.
  **Current tier assignments (updated 2026-08-24):** Tier 1 repair = Claude
  CLI (`claude-sonnet-5`, effort `high`, `tier_1_manager`); Tier 1 planning
  = OpenRouter `stealth/ox-alpha` (`tier_1_planner`), falling back to Tier
  1's own CLI config on any failure; Tier 2 = Nemotron 3 via OpenRouter;
  **Tier 3 = real DeepSeek API directly** (`api.deepseek.com`, model
  `deepseek-chat` → resolves to `deepseek-v4-flash`), swapped from
  OpenRouter's dots-3-note-preview; **Tier 4 = notes3 (dots-3-note-preview)
  via OpenRouter**, swapped from local Ollama qwen2.5-coder — this also
  sidesteps Phase 25's genuine local-Ollama Tier 4 timeout issue, since
  dispatch no longer depends on local Ollama being responsive at all. Both
  swaps live-probed OK and full suite 141/141 passing post-swap. Full
  bug-by-bug detail on the original merge (8 real bugs found and fixed
  pre-merge, including one that had fully bricked `triapi plan`) is in
  `PLAN.md`'s "Phase 21" entry.
- The `openrouter` branch itself still exists locally, now fully merged —
  safe to delete (`git branch -d openrouter`) once confirmed not needed for
  anything else; not done yet, not urgent.
- **Queue items #1-#6 from the 2026-08-19 carryover, and the 2026-08-20
  queue drain**, are done — see `PLAN.md` for that history if ever needed;
  nothing outstanding from either.
- **Four real bugs found/fixed 2026-08-23/24** — see `PLAN.md` Phases
  23/24/25/26: swallowed error reason on Tier 1/2 failure; a dispatcher
  mechanism gotcha where mid-run item insertion can collide `task_id`s with
  stale state (workaround documented, not yet a code fix); a genuine Tier 4
  timeout never falling through to Tier 3/2/1 (workaround: `skip_tier4` on
  the stuck item); OpenRouter's content-filter fix (Phase 21) generalized
  from the planner to every OpenRouter-routed tier.
- **Stale, superseded self-fix drafts: `20260823-204035-0c929e` and
  `20260823-204847-f50c6c`** (auto-captured `RuntimeError`s from
  `cmd_dispatch` crashing) — both are transient OpenRouter flakiness
  (content-filter 403, then a rate-limit 429), not real code bugs; the
  403 one is the exact thing Phase 26 already fixed by hand, the 429 one
  is just rate-limit pressure from resuming this run too many times too
  quickly in one evening. Do not approve/dispatch either. Safe to leave
  queued or clean up next time `triapi self-fix list`'s backlog gets
  reviewed.
- **Pacing lesson:** resumed the email-routing run 5+ times in under an
  hour tonight, each doing a fresh `probe_models()` pre-flight OpenRouter
  call — eventually tripped a real `429`. Next resume attempt should wait
  a few minutes rather than retry immediately.
- **Architecture change queued, 2026-08-24: a named backend registry so
  tier↔model reassignment never touches each tier's own config block.**
  Today's Tier 3/4 swap (below) worked, but required rewriting each tier's
  whole `provider`/`endpoint`/`api_key_secret`/`models` block by hand in
  `tiers.yaml` — exactly the "hardcoded to the tier" pattern the user wants
  gone. Target design: a `backends:` section defining each reusable model
  config once (name → provider/endpoint/model/api_key_secret/pricing), and
  every `tier_N_*` block reduced to a single reference (e.g. `backend:
  deepseek_flash`) plus tier-specific fields that stay per-tier (role,
  automatable, peak_hours_utc, build_commands). Reassigning a tier becomes
  a one-line pointer change, never a block rewrite. Touches
  `config/tiers.yaml`'s schema, `config_loader.py`'s validation, and every
  `tier*_escalate.py`/`tier4_worker.py`/`llm_client.probe_models()` call
  site that currently reads a tier's fields directly. **This is TriAPI
  self-feature work — draft via `triapi plan --project-dir` against this
  repo and dispatch it, don't hand-build it.**
- **Second architecture feature queued, 2026-08-24 (user's own framing):
  a complexity-aware router/orchestrator ahead of the tier ladder.**
  Currently every dispatched item walks the same escalation path
  regardless of shape. Wanted: something that reads the dispatch
  prompt/plan upfront and decides how much machinery a given task actually
  needs — a large multi-phase plan gets the full Tier 4→3→2→1 ladder as
  today, but something shaped like "just reconcile/update these docs"
  routes straight to Tier 5 (the librarian, once built) without walking
  the code-repair tiers at all. User's own words: "so TriAPI will work in
  the most efficient way." Depends on Tier 5 existing first (see the
  librarian entry below) and probably the backend-registry change above
  too (a router needs a clean way to address "which tier/backend" as a
  first-class concept). **Also TriAPI self-feature work — plan and
  dispatch it through the pipeline once Tier 5 lands, don't hand-build.**
- **Found, NOT fixed (per the new "let TriAPI fix itself" rule — queue it,
  don't hand-patch), 2026-08-24: a stale duplicate of the DeepSeek
  peak-hours check.** New policy: Sat/Sun Beijing time is off-peak all day.
  `budget_guard.check_tier3_peak_hours_ok()` implements this correctly
  (converts to `Asia/Shanghai`, checks `weekday() in (5, 6)` before the
  hourly windows) and is the one that actually gates Tier 3 dispatch — that
  part is right. But `dispatcher._is_deepseek_peak_hours()` is a separate,
  older duplicate (advisory-only, just logs a "may be expensive" warning in
  `handle_fix_forward`) that only checks a single hardcoded `06:00-10:00
  UTC` window, doesn't read `tiers.yaml`'s actual two-window list, and has
  no weekend exception at all — so it'll wrongly warn about peak pricing on
  a weekend. Route the fix through `triapi self-fix` or a normal plan
  against this repo: `dispatcher.py` should probably just call
  `budget_guard.check_tier3_peak_hours_ok()` instead of maintaining its own
  separate/stale copy. **RESOLVED 2026-08-25**, see the
  `20260825-000000-*` carryover file — fixed via run `20260824-164451-2b7635`.
- **Self-fix `20260823-213048-a51c20` approved and dispatched 2026-08-25** —
  `edit_blocks.apply_edit_blocks()` crash on `response_text is None` (see
  prior entry, now historical). Phase 2's core guard landed clean (Tier 4,
  `scripts/edit_blocks.py`). Phase 3's first item (`tier3_escalate.py`) hit
  a **new, confirmed-live systemic bug while dispatching** — queued below.
  Workaround applied to unblock this run: dropped `logs/triapi.log` and
  `logs/cost_log.jsonl` from that item's `context_files` (they weren't load-
  bearing for the edit) and set `skip_tier4: true`. If this run is still
  mid-flight next session, `triapi dispatch 20260823-213048-a51c20` resumes
  it; if it finished, check `PLAN.md` for the outcome instead of resuming.
- **New systemic bug found 2026-08-25, NOT fixed (queue it, don't hand-
  patch — same rule as the peak-hours duplicate above): OpenRouter's content
  filter false-positives on `[PHONE]` for TriAPI's own log files, and this
  can wedge an item's entire escalation ladder, not just Tier 4.** Repro'd
  live: feeding `logs/triapi.log` + `logs/cost_log.jsonl` as Tier 4 context
  for a real dispatch item got a `403 Client Error: Forbidden`; direct curl
  isolated the cause to `{"error":{"message":"Request blocked by content
  filter: [PHONE]", ...}}` — a false positive, almost certainly one of the
  many digit-heavy `run_id`/`task_id`/timestamp strings in those logs
  (e.g. `20260810-092820-8cbeaf`) pattern-matching as a phone number, not
  an actual phone number. Phase 26's sanitizer (`llm_client.
  _sanitize_for_openrouter_content_filter()`) only strips email-shaped
  tokens — it has no phone-number case, so it didn't catch this. **Worse
  than Phase 26's finding**: because `context_blob` is folded into the same
  `prompt` string sent to every OpenRouter-routed tier, this item's Tier 4
  failure fell through (via `skip_tier4`) straight into Tier 3 → Tier 2,
  and Tier 2 (Nemotron, OpenRouter) hit the *same* `[PHONE]` block on every
  candidate in its `fallback_chain` too, so the whole ladder failed and
  crashed the run (`RuntimeError: Tier 2 failed: ...403...`) rather than
  landing in `human_handoff` with a clear reason. Route the fix through
  `triapi self-fix`/a normal plan against this repo: extend
  `_sanitize_for_openrouter_content_filter()` with a phone-number-shaped
  regex case (careful not to also mangle legitimate digit-heavy content
  like hex hashes or line numbers), and consider whether `logs/*.log`/
  `logs/*.jsonl` should even be eligible as raw LLM context at all — they
  are internal operational logs, not source/docs, and stuffing them
  unsanitized into a prompt is the root cause both here and in Phase 26.
  **RESOLVED 2026-08-25**, see the `20260825-000000-*` carryover file.
