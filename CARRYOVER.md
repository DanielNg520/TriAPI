# Carryover — 2026-08-24 (end of session)

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

**Standing rule (2026-08-24): TriAPI's own docs never mention a specific
target repo by name**, whichever repo it dispatches against. A TriAPI-internal bug found via a
target-repo run still gets documented here (generically), but the
target-repo's own status/context goes into that repo's own docs instead —
see `feedback_target_repo_docs_stay_in_target_repo` memory.

## Current state

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
  separate/stale copy.
- **Real self-fix draft awaiting review: `20260823-213048-a51c20`** —
  `edit_blocks.apply_edit_blocks()` crashes (`AttributeError: 'NoneType'
  object has no attribute 'strip'`) when a Tier 3 response comes back with
  `response_text is None` (observed once, right after a Tier 3 call that
  hit the 65536-output-token ceiling — plausibly related, not confirmed).
  This one is a genuine bug, unlike the two stale drafts above — review
  and approve/dispatch it next session rather than re-diagnosing from
  scratch.

## Next up

- **Virtual Codebase Plan (Tiered Planner-Materializer architecture) is
  still queued.** `VIRTUAL_CODEBASE_PLAN.md` at this repo's root (restored
  2026-08-23 — had been deleted in commit `8998db5`, before this session;
  the user asked for it back). **User wants to work on this one together,
  personally** — hold off starting it solo; wait for the user.
- **Tier 5: local librarian (reader/writer split), queued 2026-08-23/24.**
  A real tier in the pipeline, like tiers 1-4, dispatched specifically for
  doc-update work — so the supervising Claude agent never hand-writes docs
  itself, same "never do TriAPI's job" discipline already applied to code.
  User-approved model picks:
  - **Writer** (`tier_5_librarian`): Ollama, model `mistral-small:latest` —
    drafts/edits prose, does the actual doc updates.
  - **Reader**: Ollama, model `jina-reranker-v2` — cheap triage/relevance
    pass (what's stale, what needs the writer's attention) before the
    writer is invoked. **Also does bookkeeping (2026-08-24): a quick grep
    for `@` across a target/context file before any OpenRouter-routed tier
    proceeds on it**, flagging likely email-like content upfront — a cheap
    pre-check complementing (not replacing) the runtime sanitization added
    in Phase 26 (`llm_client._sanitize_for_openrouter_content_filter()`),
    catching the same class of content-filter-403 risk earlier/visibly
    instead of only defending against it silently at request time.
  - Scope once drafted: new tier config block(s) in `config/tiers.yaml`, a
    `librarian_escalate.py`/reader+writer pair mirroring the existing tier
    scripts, and routing for doc-shaped targets (`*.md`, `docs/**`). Draft
    via `triapi plan --project-dir` against this repo (TriAPI self-feature
    work, same as any other TriAPI capability) and dispatch it through the
    pipeline, don't hand-write it. Whatever it reads/writes still follows
    the target-repo-docs-stay-in-target-repo rule above.
  - **Not yet started.** The in-flight target-repo dispatch run it was
    waiting on has now finished (`human_handoff` on its last item — see
    that repo's own `CARRYOVER.md`, not here). Clear to start Tier 5 next
    session. **User's explicit plan: stop here, start TriAPI feature work
    (this, the backend registry, and the router/orchestrator above) in a
    fresh session.**
  - **Follow-on task queued for once Tier 5 exists: consolidate all
    target-repo-specific content out of TriAPI's own docs.** A supervisor
    survey (2026-08-24) found ~700 lines of `PLAN.md`'s historical record
    (17 sections spanning many phases, heavily interleaved with genuinely
    generic TriAPI bug fixes) plus a few illustrative mentions in
    `AGENTS.md`/`README.md` that name a target repo and should relocate to
    that repo's own docs per the rule above. **Both the planning and the
    execution go through TriAPI itself** (`triapi plan` against this repo,
    then `triapi dispatch`, Tier 5 doing the actual doc rewriting) — do not
    hand-draft the plan and do not write a one-off script that calls the
    librarian model directly; that defeats the point of building Tier 5.
