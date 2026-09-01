# Carryover — 2026-09-01 10:01 PDT — Tier reassignment + doc sweep complete; two real TriAPI pipeline bugs found via self-dispatch

**Session summary:** Started by resuming oh-my-llama's Sub-Phase 5H (see
history below, fully done). User then directed a multi-round tier
reassignment for TriAPI itself, ending in a simplified "promotion chain"
shared across Tiers 2/3/4, plus retiring Tier 5's fallback chain and the
whole Gemini per-model-quota-fallback mechanism. Per the user's explicit
correction ("call triapi to improve itself"), the second half of this
work was dispatched through **TriAPI's own `triapi plan`/`dispatch`
against its own repo** rather than hand-edited — this surfaced two real,
previously-unknown pipeline bugs (see below), both fixed and committed.
Session ends here cleanly, nothing mid-flight, full test suite green.

## Current live tier assignment (config/tiers.yaml, as of commit `d62da19`)

Single shared "promotion chain" across Tiers 2/3/4
(`budget_guard.resolve_peak_conditional()`, each tier's `peak_alt` block):

- **Off-peak:** Tier 2 = DeepSeek v4 Pro → Tier 3 = `agy`/Gemini 3.1 Pro
  (effort high) → Tier 4 = OpenRouter `nvidia/nemotron-3.5-lightning:free`.
- **Peak** (DeepSeek's billing window): DeepSeek drops out, everything
  promotes up one rung — Tier 2 = `agy`/Gemini 3.1 Pro → Tier 3 =
  OpenRouter Nemotron → Tier 4 = local Ollama
  `qwen2.5-coder:14b-instruct-q6_K`.
- Tiers 2/3 no longer skip during peak hours (previous behavior) — they
  always run, just on a different backend.
- **Tier 1** unchanged: `agy`/Gemini 3.1 Pro primary, Claude Sonnet
  (`cli`) fallback on any failure — deliberate exception to
  "fallback chains go down" (Claude via CLI is subscription-covered, not
  metered, and Tier 1 is already the last automated attempt).
- **Tier 5**: single call, `agy`/Gemini 3.7 Flash, effort high. No
  fallback chain — fails fast to `human_handoff` on any failure.
- **Gemini per-model daily-quota fallback removed entirely**
  (`scripts/gemini_fallback.py` deleted, `tier_2_manager.fallback_chain`
  and `tier2_escalate.py`'s candidate-loop gone) — moot now the account
  is on a paid Gemini tier, not free-tier-quota-limited.

Full detail and rationale: memory `project_triapi_tier_assignment_20260901`
(auto-memory, not in this repo) is the authoritative record of *why*;
this file is the *what happened this session*.

## Two real TriAPI pipeline bugs found (both fixed+committed)

1. **No lock prevented two `triapi dispatch` processes for the same
   `run_id` running concurrently.** A `nohup triapi dispatch <id> &`
   that looked like it failed to launch (silently killed by shell/tool
   process-group cleanup, indistinguishable from a real launch failure)
   had in fact kept running; retrying with `--background` started a
   second, independent dispatch racing the first against the same git
   tree — this is what caused the oh-my-llama Sub-Phase 5H file
   corruption earlier this session (see history below). Fixed:
   `dispatcher.dispatch()` now takes a pidfile lock
   (`logs/runs/<run_id>.lock`), refuses a concurrent second dispatch with
   `RunAlreadyDispatchingError`. Commit `cf0d8f6`.
2. **`agy`'s argv-size guard crashed the whole dispatch instead of
   escalating gracefully.** `llm_client._call_agy_cli` raises a synthetic
   `CalledProcessError(0, ...)` when a prompt exceeds its 100k-char argv
   limit — `orchestrator.run_task`'s Tier 2 block treated ANY "error"
   status as fatal (`raise RuntimeError`, crashing the entire dispatch)
   instead of falling through to Tier 1. Found live self-dispatching an
   edit to a large file via Tier 2's agy/peak_alt leg. Fixed:
   `tier2_escalate.py` now recognizes this specific synthetic error and
   returns `"skipped"` instead of `"error"`. Commit `de00fe9`.

**Also found (not a pipeline bug, my own mistake):** manually patching a
run's `logs/runs/<run_id>.json` results list by *appending* a success
entry instead of *replacing* the existing (human_handoff) one desynced
the count-based resume logic by one slot, silently skipping a real
checklist item. Caught, fixed, recorded in memory
(`feedback_state_patch_replace_not_append`) — if you ever hand-patch a
run's state to mark an item done past a bug, always replace the existing
entry at that position, never append.

**Also found:** the self-dispatch itself transiently broke
`scripts/librarian_escalate.py` (unterminated f-strings, a dangling
~190-line dead-code tail from the old fallback loop, and a wrong-indent
bug that nested the entire write/verify path inside the FRESH-check
branch) — broke every `triapi` command (dispatcher.py imports it at load
time) until hand-fixed directly (commit `01f60b5`, since this is a live
bug fix, not new feature work — see
[[feedback_supervisor_never_do_triapi_job]]). Lesson: a plan targeting
TriAPI's own repo can transiently break the tool that's supposed to fix
it — always independently verify with `python3 -m py_compile` + the full
test suite, don't just trust a tier's reported "success".

## Doc sweep (commits `f6f3bb5`, `d62da19`)

README.md, ARCHITECTURE.md, and AGENTS.md's scripts-directory reference
were multiple generations stale on tier assignment (some inconsistencies
pre-dated this session entirely — e.g. README.md had two different,
mutually-contradictory escalation orders in different sections). Fixed
via `scripts/librarian_escalate.py` (dogfooding tonight's own Tier 5
simplification) plus a couple of direct one-line fixes for spots outside
the librarian instructions' scope. Historical/decision narrative
(ARCHITECTURE.md's "Design decisions that changed during the build",
README's Jules/MCP-server deferred-feature notes, AGENTS.md's dated
history bullets) deliberately left untouched — those are historical
record, not live-state claims, per this repo's own convention.

## Status at session end

TriAPI: working tree clean, full test suite green (262 passed, 13
subtests). **20 commits ahead of `origin/main`, not pushed** — nothing
asked me to push tonight; a fresh session should check with the user
before pushing, or just ask if they want it pushed now.

oh-my-llama: Sub-Phase 5H fully complete, committed (`c4c8722`) and
pushed; both services (`oh-my-llama.service`, `oh-my-llama-telegram.service`)
confirmed healthy directly, not just via a tier's report. Nothing pending
there — see its own `docs/Agent/CARRYOVER.md` for its next task (Phase 7,
package rename).

## Expected next-session item

User said: a refreshed Gemini free API key lands with the new month
(2026-09) and they'll specify where to place it later. Don't assume its
slot — wait for explicit instruction.

No other TriAPI work is queued or mid-flight.
