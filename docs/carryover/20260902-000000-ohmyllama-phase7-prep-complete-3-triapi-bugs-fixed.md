# Carryover — 2026-09-02 (early) — oh-my-llama Phase 7 prep complete, 3 real TriAPI bugs fixed

**Status: RESOLVED at write time.** Session paused for a new session to
continue — see `20260901-140000-triapi-self-audit-complete-clean-handoff.md`
(now history) for the prior day's narrative if needed.

## What this session covered (all pushed to `origin/main`, working tree clean)

Supervised oh-my-llama's "1st parked item" (openclaw update) and Phase 7
prep (retiring the last live legacy `ohmyllama/` imports from `src/semai/`)
end to end. Full detail lives in oh-my-llama's own
`docs/Agent/CARRYOVER.md`/commit history — this file only covers what
changed in TriAPI itself.

1. `openclaw` updated 2026.6.33 -> 2026.7.1 in oh-my-llama's environment
   (unrelated to TriAPI's own code, no TriAPI change).
2. **`llm_client.py`**: `_call_openai_api` now raises a clear error when an
   OpenRouter response has a non-empty `choices` array but
   `message.content: null` -- previously this silently returned `None` as
   `response_text` and crashed the whole dispatch process uncaught, deep in
   `tier4_worker.extract_code()`, instead of failing just the one item.
3. **`dispatcher.py`**: `_split_plan_by_phase()` now drops a leading
   single-`#` (H1) title/rationale block that precedes a real "Phase"-named
   section -- a plan's own "# Execution Plan -- ..." title followed by
   prose "Key decisions" bullets was matching the loose checklist filter
   and getting dispatched as a bogus duplicate phase before the real
   phases even started (wasted a full duplicate build pass on a real
   dispatch before being caught).
4. **`content_guard.py`**: `check_write()` now rejects any write containing
   literal, unprocessed edit-block markers (the fenced SEARCH/REPLACE
   delimiters `edit_blocks.py` uses) -- a fenceless malformed edit response
   can leak through a full-file-replacement fallback with no guard at all,
   previously landing verbatim on disk as a file's real content (found
   live: a trivial new empty `__init__.py` ended up containing the raw
   markup after Tier 4->3->2->1 all failed to apply a proper edit against
   it). **Known false-positive, hit for real within this same session**:
   the guard also fires on a legitimate doc that quotes those marker
   strings as prose (like this very paragraph almost did) -- narrow and
   accepted for now, documented exception is a direct hand-write.
5. Reconciled a stale run-tracking gap from a prior session (run
   `20260831-231437-6479a2`, Sub-Phase 5H): the real work was done and
   committed but the run's tracked state and `AGENTS.md` checkboxes were
   never synced after a stuck `human_handoff` was resolved by hand.

All three code fixes have regression tests, full suite green throughout
(106+ unittest tests, all passing, zero skipped).

## Still queued (unchanged, carry this section forward every session)

- **`VIRTUAL_CODEBASE_PLAN.md`** (repo root) -- Tiered Planner-Materializer
  design for large-file Tier 4 edits. **On hold for the user
  specifically -- do not start solo.** See
  [[project_triapi_virtual_codebase_plan]] (memory) / `AGENTS.md`'s Root
  index for detail.
- **`docs/TUI_plan.md`** -- confirmed `triapi tui` subcommand spec,
  unblocked, not yet dispatched. Has open design questions (see the file)
  that need the user's input before a `triapi plan` session. See
  [[project_triapi_tui_plan]] (memory) / `AGENTS.md`'s Root index.
- **Gemini free API key placement** -- lands with the new month (2026-09);
  user will specify where it goes. Don't assume its slot.
- **oh-my-llama `AGENTS.md` over ceiling / `tier_5_librarian` prompt-size-guard bug** --
  oh-my-llama's own `AGENTS.md` is still ~94KB, over this repo's
  73,728-char per-file ceiling convention; `tier_5_librarian` calls against
  it keep needing a hand-edit workaround since its fallback chain was
  retired and it has no way to degrade gracefully on an oversized target.
  Two follow-ups still open: (1) split oh-my-llama's `AGENTS.md`
  `docs/agents/`-style; (2) reconsider restoring at least one Tier 5
  fallback leg for oversized-file cases.
- **`dispatcher.breakdown_phase()` silent detail drop on dense plan steps** --
  FIXED: a dominant checklist bullet is now split off into its own recursive
  breakdown_phase() call instead of being compressed alongside the rest of the
  phase, regression-tested in tests/test_breakdown_dense_bullet_split.py.
- **`content_guard.py`'s new edit-block-marker guard has a narrow
  false-positive** -- FIXED: the guard now requires a marker to occupy its own
  line rather than matching as a bare substring, so prose quoting the marker
  strings inline no longer trips it, regression-tested in
  tests/test_content_guard.py.

## Session state

oh-my-llama's Phase 7 prep (retiring live `ohmyllama/` imports from
`src/semai/`) is fully complete and pushed there (see its own
`docs/Agent/CARRYOVER.md`) -- zero real `ohmyllama` imports remain in
`src/semai/`, full test suite green. **Next step for oh-my-llama is the
actual Phase 7 rename** (`pyproject.toml`'s `name = "ohmyllama"` ->
`"semai"`), not yet started, paused here at the user's request to continue
in a new session. Nothing mid-flight in TriAPI itself -- no active
`triapi dispatch` process, no live monitors.
