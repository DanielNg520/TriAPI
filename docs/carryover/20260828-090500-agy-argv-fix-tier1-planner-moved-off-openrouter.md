# 2026-08-28 09:05 UTC — ACTIVE: agy argv crash fixed, tier_1_planner moved off free OpenRouter models onto agy/Gemini 3.1 Pro; two bugs found+fixed along the way; nothing mid-flight

**Working tree is clean, no paused run, no pending approval.** `git log -1`
should show `3cbdeba` (or later) as `HEAD`. Safe to start fresh work
immediately.

## What happened this session

Started on queue item 1 (`agy` `Argument list too long` crash) via
`triapi plan`. The plan session itself exposed that `tier_1_planner`'s
current model, `dots-studio/dots-3-note-preview:free`, **also**
hallucinates -- confirmed live, reproducibly, emitting fake
`<dots_function_call>`/`<invoke name="read_file">` tool-call markup even
though `tier_1_planner`'s non-`'cli'` path has no tools wired in at all
(this is the second free OpenRouter model in a row to do this; see
[[project_tier1_planner_nemotron_hallucination]]). A second, harder-to-spot
bug also surfaced live: giving the model corrective feedback on turn 2
produced a response that couldn't see the original goal at all -- traced to
`triapi.py`'s planning loop (`message = reply` each turn) combined with
`planner.py`'s non-`'cli'` path only ever sending `context_blob + message`
(never prior turns), so **every OpenRouter-backed planning turn after the
first is stateless and blind to the original goal**. This is a real,
previously-undocumented bug in its own right, not yet fixed (see Next up).

Given the pipeline's own planner was actively broken in two ways at once,
the user explicitly authorized hand-fixing TriAPI directly this session
(the standing "never do TriAPI's job" exception, invoked and confirmed by
the user rather than assumed). Also had the user directly resolve the
tier-reassignment ambiguity via AskUserQuestion before touching config.

## Landed and committed (`3cbdeba`)

1. **`agy` `Argument list too long` crash — RESOLVED.** Added
   `_AGY_MAX_PROMPT_CHARS = 100_000` guard in `_call_agy_cli()`
   (`scripts/llm_client.py`): an oversized prompt now raises the same
   controlled `subprocess.CalledProcessError` family agy's other failure
   modes use, before `subprocess.run()` is ever called, instead of an
   uncaught OS-level `OSError` (E2BIG) that bypassed the per-tier fallback
   chain entirely. New `tests/test_llm_client_agy_argv_guard.py` (3 tests):
   oversized prompt alone, oversized combined prompt+system_prompt, and
   normal-sized prompt still working.
2. **`tier_1_planner` reassigned off free OpenRouter models entirely.**
   Per user's explicit direction: `tier_1_planner` now uses
   `provider: agy`, `model: gemini-3.1-pro`, `effort: high` -- the same
   real, tool-using, already-reliable path `tier_3_debugger` uses (reused,
   not moved -- `tier_3_debugger` keeps its own identical config).
   `dots-studio/dots-3-note-preview:free` demoted into `tier_3_debugger`
   as a `models.secondary` entry, documented as **currently inert**:
   `tier3_escalate.py` only ever reads `models[default_model]` and has no
   per-tier model-fallback wiring (unlike `tier_5_librarian`'s
   `fallback_local`/`fallback_agy`/`fallback_openrouter` chain). Live-
   verified: `probe_models()` succeeds; a direct `planner.plan_turn()` call
   produces a coherent, correctly-grounded, non-hallucinated plan.
3. **Bug found+fixed: `planner.py`'s non-`'cli'` `execute_llm()` call never
   forwarded `tier1.get("effort")`.** Harmless while `tier_1_planner` used
   free OpenRouter models with no `effort` key at all; broke immediately
   once moved to `agy`'s `gemini-3.1-pro`, which *requires* `--effort` --
   every real planning call errored with `"--model gemini-3.1-pro requires
   --effort"` and silently fell back to `tier_1_manager`'s Claude CLI
   (confirmed live: the fallback response literally said "I'm actually
   Claude, not Gemini"). Fixed by adding `effort=tier1.get("effort")` to
   the `execute_llm()` call (`scripts/planner.py`). New
   `tests/test_planner_effort_forwarding.py` (2 tests): effort forwarded
   when configured, and `None` forwarded (not an error) when absent, for
   providers like the old free-OpenRouter setup that never had one.
4. **Bug found+fixed: `librarian_escalate.py`'s `fallback_openrouter` leg
   broke as a direct consequence of item 2.** It read
   `config.get("tier_1_planner", {}).get("endpoint")` as a shared "the
   OpenRouter endpoint" source -- valid only because `tier_1_planner`
   itself always used to be OpenRouter. Once `tier_1_planner` moved to
   `agy` and dropped its `endpoint`/`api_key_secret` fields, this silently
   resolved to `None`, which would have crashed `tier_5_librarian`'s 4th
   fallback leg (`"None/chat/completions"`) the next time it was actually
   exercised -- same failure shape as the `ollama_host`-endpoint-None bug
   from 2026-08-24. Fixed by adding a new top-level `openrouter_defaults`
   block to `config/tiers.yaml` (`endpoint` + `api_key_secret`, same
   pattern as `gemini_fallback`/`deepseek_reference_pricing`) and pointing
   `librarian_escalate.py` at that instead. `tests/test_tier5_librarian.py`'s
   config fixture and one assertion's stale comment updated to match.

Full suite: **219 tests, OK** (post all four changes above).

## New bugs found this session, not yet fixed (queued)

- **`triapi plan`'s multi-turn conversation loses the original goal after
  turn 1, for every OpenRouter-backed (non-`'cli'`) provider.**
  `triapi.py`'s loop sets `message = reply` each turn (line ~137);
  `planner.py`'s `_plan_turn_llm()` non-`'cli'` branch only ever sends
  `context_blob + message` (line ~269) -- never the original goal, never
  prior turns. Confirmed live: feedback on turn 2 got a response saying
  the goal wasn't visible at all. This is now moot for `tier_1_planner`
  itself (moved to the `'cli'`-adjacent `agy` path... no, wait: `agy` is
  still a *non*-`'cli'` provider per `planner.py`'s dispatch, so this bug
  **still applies to `tier_1_planner`'s multi-turn conversations today**
  -- turn 1 is now reliable, but turn 2+ feedback will still lose the
  original goal until this is fixed. Only `provider == "cli"` (Claude CLI,
  via `--resume`) has real cross-turn memory. Worth fixing properly: either
  give non-`'cli'` providers a real conversation history (accumulate
  turns, not just the latest `message`), or make this limitation loud to
  the user instead of silently degrading. High priority -- affects every
  planning session with feedback, not just this one.
- Everything else queued as of the previous file (still open, unchanged):
  the `py_compile`-insufficient verify-command gap, the bare-`skipped`-
  substring false-positive pattern, Tier 3's out-of-scope-edit pattern
  (2 confirmed incidents), no sanity check on `triapi plan`'s own raw
  output before it's treated as approvable (this session's statelessness
  bug is a *specific instance* of exactly this gap -- worth fixing
  together).

## Standing rules (accumulated, still in effect)

- All rules from the previous file still apply unchanged (never do
  TriAPI's job except the pipeline-can't-function exception -- confirmed
  and explicitly invoked by the user this session; use
  `scripts/librarian_escalate.py` for doc edits except carryover rotation
  itself; always read a plan turn's text before approving; DeepSeek
  peak-hours windows; `tier_5_librarian`'s primary is `agy`/Gemini 3.7
  Flash).
- **`tier_1_planner`'s config as of this session:** `provider: agy`,
  `model: gemini-3.1-pro`, `effort: high` -- reused from
  `tier_3_debugger`, not a new/separate model instance. If planning output
  looks wrong again, check both tiers together since they share a model.
- **New `openrouter_defaults` top-level config block** now exists in
  `config/tiers.yaml` specifically so OpenRouter connection details don't
  implicitly depend on whichever tier happens to be OpenRouter-backed this
  week -- any future OpenRouter-routed fallback leg should read from here,
  not borrow another tier's fields.
- **`tier_3_debugger`'s `models.secondary` field (`dots-3-note-preview:free`)
  is documentation-only, not live fallback** -- don't assume it's actually
  used until `tier3_escalate.py` gets real per-tier model-fallback wiring.

## Next up (priority order)

1. **Fix the multi-turn statelessness bug for non-`'cli'` planner
   providers** (queued above) -- directly affects `tier_1_planner`'s
   day-to-day usability right now.
2. Consider folding in the "no sanity check on `triapi plan`'s own output"
   item together with #1, since they're closely related.
3. Fix the `py_compile`-insufficient verify-command gap.
4. Fix the bare-`skipped`-substring false-positive pattern.
5. Investigate/fix Tier 3's out-of-scope-edit pattern.
6. Resume `20260827-132236-806da1` (one remaining cosmetic `AGENTS.md`
   note) or let it lapse.
7. Older carried-forward items (unchanged): `cost_log.jsonl` size split
   (~858KB), `git_ops.push()`'s unconditional `git add -A` scoping gap,
   OpenRouter `[PHONE]` filter root-cause, Groq provider addition,
   architecture items (backend registry, complexity router, per-tier
   fallback toggles).

**Separately, on hold for the user (unchanged across sessions):**
- **Virtual Codebase Plan** (`VIRTUAL_CODEBASE_PLAN.md`).
- Consolidate target-repo-specific content out of TriAPI's own docs --
  goes through TriAPI itself, not hand-drafted.
- `docs/TUI_plan.md` -- still untracked/unplanned.

*(Full session narrative, including the exact live reproduction steps for
each bug above, is in this file -- no further prior-file detail needed to
resume; read `20260828-082044-queue-cleared-tier1-planner-swapped.md` only
for the queue history predating this session.)*
