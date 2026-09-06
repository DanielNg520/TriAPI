# 2026-08-24 19:00 — Queue snapshot: OpenRouter fix obstacles, superseded

Everything in this file was live-in-progress on 2026-08-24 evening and is
now fully resolved (see the `20260825-000000-*` and `20260823-210000-*`
carryover files for outcomes). Kept verbatim for deep context on exactly
what obstacles were hit and how, not because any of it is still actionable.

**Priority order, per user directive 2026-08-24: finish the librarian
improvements first, then the OpenRouter fixes, then the architecture
items.** The Virtual Codebase Plan is separate — it's on hold for the user
specifically, not part of this sequence.

1. **Librarian improvements: DONE.** Run `20260824-132910-a7b69b`
   completed Phases 1-4 (single-call redesign, `doc_staleness.py`, wiring,
   full regression coverage — all verified green). Only Phase 5 (append a
   dated phase block to `PLAN.md`) is still stuck, blocked on the same
   OpenRouter content-filter bug item 2 below is fixing, applied to
   `PLAN.md` itself (188K chars, also over the Tier 4 context ceiling) —
   retry `triapi dispatch 20260824-132910-a7b69b` once item 2 ships.
   `AGENTS.md` bullet updates for this work are not yet done either
   (bundled with the same stuck Phase 5).
2. **OpenRouter fixes: IN PROGRESS, immediate next action for the new
   session.** Run `20260824-164451-2b7635` (plan approved, 4 phases, 9
   items) is dispatching the same 3 bugs listed below. Status as of
   end of last session: **Phase 1's first item just got unblocked and is
   ready to redispatch** — `triapi dispatch 20260824-164451-2b7635`. Two
   real obstacles hit and resolved so far, both live confirmations of bug
   (c) below:
   - The plan's *own* breakdown call 403'd because an earlier draft's
     generated text contained a literal phone-shaped test-fixture string
     — redrafted with an explicit "no literal phone-shaped strings in
     plan/test text" constraint (worked; this is run `2b7635`, superseding
     abandoned/stuck run `20260824-162206-4ae0a0` which can be ignored).
   - Phase 1's first item then crashed Tier 4 with the *same* 403, this
     time because Tier 2's breakdown mis-extracted `context_files` from
     the item's own prose (pulled `logs/cost_log.jsonl`, `PLAN.md`, and a
     bogus `file.py` that were only mentioned as *examples* in the
     description, not real context needed). Fixed by editing
     `logs/runs/20260824-164451-2b7635.json`'s Phase 1 item to
     `context_files: []` directly (established workaround pattern from
     earlier this session) — not yet redispatched after this edit.
   - The three bugs being fixed: (a) `librarian_escalate.py`'s
     `fallback_openrouter` endpoint resolution — plan's own read concluded
     it's already correct via `tier_1_planner`'s config block, a
     regression test is the only deliverable; (b) `dispatcher.py`'s stale
     duplicate DeepSeek peak-hours check — should delegate to
     `budget_guard.check_tier3_peak_hours_ok()` instead of its own
     hardcoded `06:00-10:00 UTC`-only copy; (c) OpenRouter's content
     filter false-positives on phone-shaped digit sequences — add
     `_PHONE_LIKE_RE`/redaction to `llm_client.
     _sanitize_for_openrouter_content_filter()`, careful not to mangle
     TriAPI's own run_id/task_id format or hex hashes.
   - **Also check the self-fix queue**: `20260824-165500-90f029` and
     `20260824-173338-8bf5ad` were both auto-captured from transient `429`
     rate-limit crashes on this same run (`cmd_dispatch:foreground` —
     `Probe failed for tier_1_planner: 429`) — same "transient OpenRouter
     flakiness, don't approve" noise pattern as the other stale drafts
     already flagged in this file; skip both rather than approving.
   - **2026-08-24/25 update: the `context_files: []` workaround (edited
     directly into `logs/runs/20260824-164451-2b7635.json`'s Phase 1 item
     0) DID hold on retry** — confirmed live: `run_task starting: ...
     context_files=[] skip_tier4=False` and Tier 4 began drafting with no
     403. The run is NOT yet resolved though: two back-to-back resumes
     since then both crashed mid-flight on `probe_models()`'s pre-flight
     gate hitting a genuine `429` (not the phone-content-filter bug) —
     each dispatch resume calls `probe_models()` fresh across ALL tiers
     before running anything, so repeated resumes in a short window
     compound OpenRouter rate-limit pressure even for tiers this run's
     Phase 1 item doesn't need. This is the same "Pacing lesson" already
     recorded above, now reconfirmed twice more. **Next session: wait
     several minutes since the last resume attempt before running `triapi
     dispatch 20260824-164451-2b7635` again** — don't retry immediately.
   - **Refined root cause, 2026-08-25: this isn't just "OpenRouter is
     rate-limited," it's `probe_models()` (`scripts/llm_client.py`)
     unconditionally hard-gating on ALL SIX tiers — including
     `tier_1_planner`, which `triapi dispatch` never actually calls (only
     `triapi plan` uses it) — before running a single item.** 20 separate
     `Probe failed for tier_1_planner: 429` captures across
     2026-08-23→08-25 in `logs/triapi.log`, spanning ~22h, but
     interspersed with successful planning calls in between (e.g. one
     succeeded at 17:33:38 the same evening) — so this is a bursty
     per-minute rate limit on the free `stealth/ox-alpha` model, not a
     hard daily quota. Every `triapi dispatch <run_id>` resume re-probes
     `tier_1_planner` regardless of whether the run's own breakdown
     touches it, so a repair-only run with zero planning calls left in it
     (like this one, already fully broken down) can still be blocked
     indefinitely by an unrelated tier's transient rate limit. **Not
     hand-patched** (per standing rule) — candidate fix for the queue:
     `probe_models()` should only probe tiers the run's breakdown actually
     references (or at minimum not hard-fail the whole gate on
     `tier_1_planner`/`tier_1_manager` specifically when dispatching an
     already-broken-down run, since planning is already done by that
     point). This is closely related to, and probably subsumed by, the
     already-queued "complexity-aware router" architecture item below —
     folding this into that item's scope (or the backend-registry item) is
     probably more efficient than a standalone fix. **Still open as of the
     current active queue** — see the current carryover index for the
     live version of this item. Third self-fix
     duplicate of the same 429 noise pattern: `20260824-173338-8bf5ad`.
3. **Architecture items** (both already flagged as TriAPI self-feature
   work — plan/dispatch through the pipeline, don't hand-build):
   - A named backend registry (`backends:` section in `tiers.yaml`
     defining each reusable model config once) so tier↔model reassignment
     is a one-line pointer change instead of rewriting a tier's whole
     `provider`/`endpoint`/`api_key_secret`/`models` block by hand.
   - A complexity-aware router ahead of the tier ladder that reads a
     dispatch prompt/plan upfront and decides how much machinery a task
     actually needs — a large multi-phase plan gets the full ladder, a
     pure doc-reconcile task routes straight to Tier 5. Depends on Tier 5
     (done) and probably the backend registry above.

**Separately, on hold for the user (not part of the ordering above):**
- **Virtual Codebase Plan (Tiered Planner-Materializer architecture).**
  `VIRTUAL_CODEBASE_PLAN.md` at this repo's root (restored 2026-08-23 —
  had been deleted in commit `8998db5`; the user asked for it back).
  **User wants to work on this one together, personally** — hold off
  starting it solo.
- **Follow-on task queued for once Tier 5 exists (it does now):
  consolidate all target-repo-specific content out of TriAPI's own docs.**
  A supervisor survey (2026-08-24) found ~700 lines of `PLAN.md`'s
  historical record (17 sections spanning many phases, heavily interleaved
  with genuinely generic TriAPI bug fixes) plus a few illustrative
  mentions in `AGENTS.md`/`README.md` that name a target repo and should
  relocate to that repo's own docs per the rule above. **Both the planning
  and the execution go through TriAPI itself** (`triapi plan` against this
  repo, then `triapi dispatch`, Tier 5 doing the actual doc rewriting) —
  do not hand-draft the plan and do not write a one-off script that calls
  the librarian model directly; that defeats the point of building Tier 5.
