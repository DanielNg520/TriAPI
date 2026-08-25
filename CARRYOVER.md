# Carryover — 2026-08-25 (session end)

**Standing rule for this file: stay brief.** Only what's needed to resume
the *next* session goes here. Finished-work narrative, per-round findings,
and "what happened" writeups belong in `PLAN.md` (this repo's permanent
build-history/decisions record), never here. Fold an item out of this file
into `PLAN.md` the moment it's resolved, in the same edit — don't leave it
lingering here in past tense. Full history lives in `PLAN.md`'s phase
entries (through **Phase 32** as of this writing) and the "Historical
notes"/addenda sections further down this file.

**Read this first in a new session.** Then `AGENTS.md` for the file/dir
index, `AGENT_GUIDE.md` for the operating manual (what's safe to hand-edit
vs. must route through `triapi plan`/`dispatch`).

## Current state, 2026-08-25 (session end) — everything queued tonight is
DONE and on `main`. Working tree clean, full suite green (118 tests:
`PYTHONPATH=. python3 -m unittest tests.test_branch_features
tests.test_tier5_librarian tests.test_llm_client_sanitize
tests.test_dispatcher_peak_hours tests.test_tier_reassignment_prep
tests.test_run_build_pipefail tests.test_orchestrator_tier3_peak_skip -v`).
Three stale `triapi/TriAPI-*` review branches from earlier sessions (all
already fully merged into `main`) were cleaned up and deleted this
session — `main` is now the single source of truth, nothing stranded on
an unmerged branch.

**Completed this session** (full detail in `PLAN.md` Phases 30-32):
- OpenRouter fixes (phone/IP content-filter sanitizer, dispatcher
  peak-hours dedup, librarian endpoint audit) — run `20260824-164451-2b7635`.
- Tier-reassignment prep: new `agy` (Antigravity CLI) provider in
  `llm_client.py`, generic (non-hardcoded) provider routing in
  `dispatcher._breakdown_phase_attempt()`, position-independent DeepSeek
  peak-hours gate (`budget_guard.resolve_deepseek_tier()`) — run
  `20260824-221726-3df72d`.
- Critical fix: `run_build()` no longer silently masks a failing
  `build_cmd` behind a truncating pipe (`| tail`, etc.) — was giving false
  "verified green" results. Plus a stale test fixture regression found
  alongside it. — run `20260825-000610-4c040a`.
- `git_ops.push()`'s auto-branch-creation safety rail **removed at the
  user's explicit request** — it now always pushes to whatever branch is
  checked out (including `main`/`master` directly), no more auto-created
  `triapi/<dirname>-<timestamp>` review branches. See `AGENTS.md`'s
  `git_ops.py` bullet.

## Standing rules (accumulated this session, still in effect)

- **Allowed models, no Gemini except `agy`/Jules.** Every tier's model
  must be an explicitly-approved free OpenRouter model
  (`stealth/ox-alpha`, `nvidia/nemotron-3-ultra-550b-a55b:free`,
  `dots-studio/dots-3-note-preview:free`), DeepSeek, or Claude Code CLI.
  No Gemini via raw API/OpenRouter. Two scoped exceptions: Jules
  (`jules_tester`, separate daily-capped quota) and `agy`/Antigravity CLI
  (separate subscription auth from the exhausted Google AI Studio budget,
  but has its own usage cap — needs graceful quota-exhaustion handling,
  not assumed unlimited). See `feedback_no_gemini_allowed_models` memory.
- **Everything configurable, no hardcoded provider/tier paths.** A
  function that only handles one provider/tier by name instead of
  reading config and dispatching generically is a bug to fix. See
  `feedback_everything_configurable_no_hardcoding` memory.
- **OpenRouter shared rate limit**: all models on this account (free and
  paid) share ONE pool — 20 RPM / 1000 RPD, not per-model. Explains
  cascading 429s across unrelated tiers. See
  `project_openrouter_shared_rate_limit` memory.
- **DeepSeek peak-hours windows**: 01:00-04:00 and 06:00-10:00 UTC,
  weekdays only (weekend fully off-peak, Beijing-time weekday check).

## Next up

**1. The actual tier reassignment (config/tiers.yaml) — both prep plans
are done, this is now unblocked.** Final agreed layout ("FINAL, v2" design
from earlier tonight — search this file's history if the summary below
isn't enough):
- Tier 1 = `stealth/ox-alpha` (unchanged)
- Tier 2 = DeepSeek **v4 pro** (real API) — **exact model string not yet
  verified against DeepSeek's real API**, don't guess, check before wiring
- Tier 3 = Gemini 3.1 pro via `agy` CLI, effort high,
  `--dangerously-skip-permissions` (now has a real, tested provider branch
  to use — see Phase 31)
- Tier 4 = local qwen (`qwen2.5-coder:14b-instruct-q6_K`, unchanged)
This is a config-only change now that the code prerequisites exist, but
still real behavior change — go through `triapi plan`/`dispatch` per the
user's own stated preference for this change, not a silent hand-edit.

**2. Two follow-ons queued, not yet started:**
- Add `agy` as a `tier_5_librarian` fallback leg (its ~1M context solves
  the recurring PLAN.md doc-update failures hit three times tonight —
  Phases 30, 31, 32 all had to write PLAN.md's own phase entry by hand
  because the librarian's local+OpenRouter legs couldn't handle it).
- Make every tier's fallback mechanism individually on/off configurable,
  matching the "everything configurable" principle — natural extension of
  the backend-registry architecture item below.

**Open root-cause question, never actually resolved, flagged by the user
2026-08-25 morning:** Phases 30/31/32 each hit the OpenRouter `[PHONE]`
content-filter 403 on `PLAN.md` **even after** the phone/IP sanitizer fix
(`_PHONE_LIKE_RE`/`_IP_LIKE_RE` in `llm_client.py`) landed and was
confirmed working elsewhere. That fix only matches specific *shapes*
(3-3-4 phone grouping, IPv4 dotted-quad) — it was never actually verified
whether OpenRouter's real trigger is shape-specific at all, or whether it
flags **any sufficiently long unbroken digit run** (which `PLAN.md`'s
dense timestamp/hash content would trip regardless of grouping, and which
`_PHONE_LIKE_RE`/`_IP_LIKE_RE` would NOT catch, since both require
separators). **Attempted a direct live test 2026-08-25 morning** (an
18-digit separator-free string through a real `execute_llm(provider=
"openrouter", ...)` call) — inconclusive, hit the OpenRouter shared-pool
429 before getting a real answer either way (see
`project_openrouter_shared_rate_limit` memory). Retry when convenient,
away from other OpenRouter activity so a 429 doesn't mask the result
again. Worth resolving before assuming the sanitizer is complete, though
the queued `agy`-as-librarian-fallback item above sidesteps the whole
question for the specific PLAN.md case (agy doesn't go through
OpenRouter's filter at all).

**3. Groq provider addition** (`qwen/qwen3.6-27b`, `groq_api_key` already
in `secrets.enc.yaml`, unwired) — for a lightweight/router role, not a
tier replacement. Rate limits given: RPM 30, RPD 1,000, TPM 8,000, and a
"200K" figure whose unit needs verifying against Groq's real docs before
wiring a hard gate on it.

**4. Architecture items** (self-feature work — plan/dispatch, don't
hand-build):
- Named backend registry (`backends:` section in `tiers.yaml`) so
  tier↔model reassignment is a one-line pointer change.
- Complexity-aware router ahead of the tier ladder (large plan → full
  ladder, pure doc-reconcile → straight to Tier 5). Also would subsume
  `probe_models()` unconditionally gating on all 6 tiers even when a
  run's breakdown doesn't need them all (found earlier tonight, not yet
  fixed).

**Separately, on hold for the user (not part of the ordering above):**
- **Virtual Codebase Plan** — `VIRTUAL_CODEBASE_PLAN.md` at repo root.
  User wants to work on this one together, personally — hold off solo.
- **Consolidate target-repo-specific content out of TriAPI's own docs**
  (~700 lines of `PLAN.md` history, plus a few `AGENTS.md`/`README.md`
  mentions) — both planning and execution go through TriAPI itself
  (`triapi plan`, Tier 5 doing the rewriting), not a hand-drafted plan or
  a one-off script.


## Historical archive (2026-08-24 sessions, superseded by the summary above, kept for deep context only)

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

## Current state (addendum, 2026-08-24 continued)

- **Librarian improvements run `20260824-132910-a7b69b` is `stopped_on_failure`
  after Phase 1 (both items landed clean, Tier 4) and Phase 2's single item
  (`scripts/doc_staleness.py`) hit `human_handoff` after exhausting Tier 4 →
  3 → 2 → 1 — all four independently produced the same bug.** Root cause
  (confirmed by reading the generated file, not hand-fixed): the epoch-
  collision handling in `should_skip_model_call()`'s scan loop treats "a
  commit landed at the same UNIX-epoch second as the doc's last commit" as
  "this commit touched the doc" and discards it (`if current_epoch ==
  doc_commit_epoch: continue`). Git's commit timestamp has 1-second
  granularity, so two *different* commits made in quick succession — the
  test harness's own `git commit` calls, and realistically TriAPI's own
  automated commits too — can share an epoch even though only one touched
  the doc. That silently drops a genuine non-doc commit from the scan,
  leaving `found_non_doc_commit = False` and forcing permanent fail-open
  (never skips the model call) in exactly the fast-commit scenario the
  pre-check exists to handle. Fail-open itself is safe (matches spec:
  "ANY ... unexpected ... -> fail open"), so this isn't unsafe, just makes
  the whole feature inert whenever commits are fast/batched. Fix should
  distinguish "commit touched the doc" (check the file list, not the
  epoch) from "commit epoch ties the doc's epoch" — the same-epoch guard
  needs to check membership of `relpath_str` in that commit's file list,
  not epoch equality. Route via `triapi plan`/self-fix against
  `scripts/doc_staleness.py`, don't hand-patch. Once fixed, resume/retry
  run `20260824-132910-a7b69b`'s Phase 2 item (still awaiting Phases 3-9:
  wiring, tests, PLAN.md/AGENTS.md updates).

## Current state (addendum 2, 2026-08-24 continued)

- **Run `20260824-132910-a7b69b` resumed past the Phase 2 `doc_staleness.py`
  bug on retry (a fresh Tier 1/Claude attempt got it right this time,
  6/9 steps done) and hit a NEW `human_handoff` at Phase 4** (regression
  tests in `tests/test_tier5_librarian.py`). Root cause here is a plan-
  breakdown gap, not a code bug: **two pre-existing tests —
  `test_advisory_no_change_verdict_returns_changed_false_without_writing`
  and `test_success_path_lands_via_edit_block_with_local_billing` — still
  mock the OLD JSON-envelope response format (`'{"stale": false}'`) that
  Phase 1 deliberately eliminated.** Against the new single-call plain-
  text `run()`, that mocked JSON string correctly fails to parse as either
  `FRESH` or a SEARCH/REPLACE block, so `run()` (correctly, per the new
  design) escalates through the full chain and the test's
  `execute_llm.assert_called_once()` fails (actually called 3x). Phase
  4's item description only said to *add* new single-call-flow tests, not
  to update/remove these two now-incompatible old ones — that's the gap.
  4 escalation attempts (Tier 4→3→2→1) apparently thrashed on this,
  producing one genuinely broken syntax (`SyntaxError: unterminated
  string literal` at old line 358) that a later attempt already
  overwrote — current file parses clean (`ast.parse` succeeds), so no
  cleanup needed there. Resumed dispatch again after documenting this;
  if it's still stuck next session, the fix is either (a) let a tier
  finally rewrite those two tests for the new format on its own, or (b)
  if it keeps thrashing, a small follow-up `triapi plan` item explicitly
  naming those two tests for update would remove the ambiguity — draft
  via the pipeline, don't hand-edit the test file directly.

## Current state (addendum 3, 2026-08-24 continued)

- **New systemic bug found 2026-08-24, NOT fixed (queue it, don't hand-
  patch): `orchestrator.run_task()`'s Tier 4→3→2→1 escalation can declare
  `human_handoff` even when the FINAL tier attempt's write genuinely
  satisfies the item's own `build_cmd`.** Confirmed live on run
  `20260824-132910-a7b69b`'s Phase 4 item (`tests/test_tier5_librarian.py`
  regression tests): after sharpening the item's description (see prior
  addendum) and resuming, the run again reported `human_handoff` with a
  "Tier 4 -> Tier 3 -> Tier 2 -> Tier 1" exhaustion reason — but the file
  actually left on disk was completely correct: re-running the exact
  recorded `build_cmd` (`PYTHONPATH=. python3 -m unittest
  tests.test_tier5_librarian -v`) by hand passed clean, 14/14 tests green,
  including both previously-stale tests now correctly updated. So the
  last tier's write did succeed against its own acceptance check, but
  `run_task`'s own bookkeeping still escalated to human_handoff instead of
  returning success — most likely a consecutive-failure-threshold check
  firing on a stale counter without re-validating the final attempt's
  actual build result, similar in spirit to the epoch-collision bug found
  earlier this session but in a different module (root cause not yet
  isolated to a specific line — needs a read through `tier1_escalate.py`'s
  retry loop, or wherever the final tier's success/failure gets folded
  into the human_handoff decision). **Workaround applied this session
  (with explicit user sign-off, since it required overriding the run's
  own recorded verdict): manually corrected `logs/runs/
  20260824-132910-a7b69b.json`'s last result entry from `human_handoff` to
  `success` (resolved_by: tier_1, content_hash recomputed via
  `regression_guard.hash_file()`), since the target file was independently
  re-verified against its own build_cmd first.** Route the actual fix
  through `triapi plan`/self-fix against `scripts/orchestrator.py` (and
  whichever `tierN_escalate.py` turns out to hold the stale-counter logic)
  once this run completes — don't hand-patch.

## Current state (addendum 4, 2026-08-24 continued)

- **Run `20260824-132910-a7b69b` reached 8/9 (Phases 1-4 fully done and
  verified — full regression gate green) and stalled on Phase 5's PLAN.md
  update.** All three of `tier_5_librarian`'s escalation legs failed:
  local legs (`mistral-small`/Ollama fallback) can't fit `PLAN.md` at
  188,334 chars (well over Tier 4's 73,728-char ceiling — same standing
  ceiling problem as [[feedback_no_files_at_tier4_ceiling]]), and the
  OpenRouter fallback leg hit the already-queued `403 Forbidden` content-
  filter false-positive (see priority #2 in "Next up" below) — this is a
  second, independent live confirmation of that bug against a different
  digit-heavy file (`PLAN.md`'s many `run_id`/timestamp strings), not a
  new bug. This item is genuinely blocked on two already-queued fixes
  (the OpenRouter phone-regex sanitizer, and PLAN.md's own oversize —
  which is also the subject of the already-queued "consolidate historical
  PLAN.md content out to target-repo docs" follow-on). Not resolved this
  session; run left at `stopped_on_failure` on this item pending user
  direction on how to proceed (skip Phase 5 for now vs. wait for the
  OpenRouter/PLAN.md-size fixes to land first).

## Current state (addendum 5, 2026-08-24 continued)

- **Priority #2 (OpenRouter fixes), first attempt (`20260824-162206-4ae0a0`)
  hit a genuine chicken-and-egg failure: its own breakdown call (Tier 2/
  Gemini, routed through OpenRouter) got `403 Forbidden` because the
  approved plan text itself contained literal phone-number-shaped example
  strings (e.g. a fake pager number as a test fixture) — a fourth live
  confirmation of the exact bug being fixed, this time tripped by the fix's
  own plan. That run is abandoned/stuck (`stopped_on_failure`, 0 phases,
  still sitting in `AGENTS.md`'s plan-gate block — harmless to leave, next
  plan used `--refactor` to supersede it). Redrafted as
  `20260824-164451-2b7635`** with an explicit constraint in the prompt
  telling the planner not to emit literal phone-shaped digit strings
  anywhere in the plan/test text (describe the format structurally
  instead) — this one's breakdown succeeded and it's now dispatching.
- **Priority #2 now dispatching: run `20260824-164451-2b7635`**, plan
  approved and running in background.
  Bundles all three queued OpenRouter/dispatch bugs into one 4-phase plan:
  (1) phone-number content-filter false-positive fix in
  `llm_client._sanitize_for_openrouter_content_filter()` (new
  `_PHONE_LIKE_RE`/`_redact_phone_like()`, scoped to not mangle
  run_id/task_id-shaped strings, hex hashes, or line numbers); (2)
  `dispatcher._is_deepseek_peak_hours()` now delegates to
  `budget_guard.check_tier3_peak_hours_ok()` instead of its stale
  hardcoded 06:00-10:00-UTC-only duplicate; (3) audit of
  `librarian_escalate.py`'s `fallback_openrouter` endpoint resolution
  (plan's own read concluded it's already correct via
  `tier_1_planner`'s config block, not the buggy pattern
  `probe_models()` had — a regression test asserting the resolved URL
  either way is still item 3's deliverable). Phase 4 does the full
  regression gate + PLAN.md/AGENTS.md doc updates. Check
  `triapi status 20260824-162206-4ae0a0` for progress if resuming.

## Next up

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
     probably more efficient than a standalone fix. Third self-fix
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

## Historical notes (already resolved, kept for context)

- **Self-fix `20260824-011749-b8ba34` (the `llm_client.py` `KeyError:
  'choices'` fix) is fully resolved (2026-08-24).** Phases 1-2 (the
  `_call_openai_api()` guard + regression tests) landed via the pipeline;
  Phase 3 (the one-sentence `AGENTS.md` addition) hit `human_handoff` three
  times in a row on real local Ollama inference timing out (300s+ per
  attempt across all 3 escalation legs) — applied by hand instead, since
  the underlying code fix was already done/tested and this was a trivial,
  fully-specified one-line doc edit. `AGENTS.md` confirmed at 73,380 chars
  (still under the 73,728 ceiling, but tight — worth trimming further
  before the next addition). Full suite green (83 tests).
- **`llm_client.probe_models()` gained retry tolerance, 2026-08-24.** It
  had zero tolerance for a single transient blip on *any* tier — one
  OpenRouter 429 or a free model's temporary 502 aborted the entire
  pre-flight gate and thus the whole dispatch, even for tiers the run
  doesn't use. `_probe_with_retry()` now retries 3x, 5s apart, before
  failing the gate; still fails hard on a genuinely broken/misconfigured
  tier.
- **Found, not fixed: `tests.test_ollama_service_lifecycle.
  CmdDispatchOllamaLifecycleTests.test_cmd_dispatch_restores_ollama_state_
  on_exception` hangs on a real unmocked network call** (confirmed live
  2026-08-24 — it doesn't fail fast, it blocks for minutes). Pre-existing,
  unrelated to tonight's Tier 5 work (an earlier Jules advisory pass had
  already flagged this test module's mocking as incomplete). Needs a
  proper mock at the HTTP boundary, not just a shorter timeout. Run
  `tests.test_branch_features`/`tests.test_tier5_librarian` directly
  instead of bare `unittest discover tests` until this is fixed.
