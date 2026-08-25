# 2026-08-25 09:23 — ACTIVE: tier-flip plan ready to dispatch, standing rules, full queue

**This is the primary file to read to resume work — everything else in
`docs/carryover/` is historical/completed context only.**

## Current state

System was rebooted after the 2026-08-24/25 overnight session, then a
short follow-up session ran during the day: fixed a stale memory file,
recorded an unresolved OpenRouter root-cause question (see below), and
drafted+approved the tier-reassignment plan (`20260825-092344-5ff4a7`)
but **deliberately did not dispatch it** — stopped at the user's request
so the next session can pick it up cleanly. Working tree clean, everything
committed to `main`, nothing running. Full suite green as of the
overnight session's end (118 tests:
`PYTHONPATH=. python3 -m unittest tests.test_branch_features
tests.test_tier5_librarian tests.test_llm_client_sanitize
tests.test_dispatcher_peak_hours tests.test_tier_reassignment_prep
tests.test_run_build_pipefail tests.test_orchestrator_tier3_peak_skip -v`)
— not rerun the short follow-up session since nothing code-facing changed
there.

## Standing rules (accumulated 2026-08-24/25, still in effect)

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
- **Doc architecture (2026-08-25, this session): `AGENTS.md` and
  `CARRYOVER.md` are now pure index files — never pruned/trimmed for size
  again.** Real content lives in dated, titled files under
  `docs/carryover/` (session/task history and queue state) and
  `docs/agents/` (overflow file/dir documentation once `AGENTS.md`'s own
  index grows too large to hold inline). Each dated file stays under the
  73,728-char ceiling. `CARRYOVER.md`'s job is to tell the agent which
  dated file(s) are relevant to the current task so it reads only what it
  needs, not the whole history. See `feedback_docs_are_index_files`
  memory.

## Next up

**1. The tier reassignment plan is drafted, approved, and READY TO
DISPATCH — resume with `triapi dispatch 20260825-092344-5ff4a7`.**
$0 planning cost, 4 phases: (1) edit `config/tiers.yaml` — Tier 2 →
DeepSeek `deepseek-v4-pro` (real API, confirmed live via
`GET https://api.deepseek.com/models` this session — this is the exact,
verified model id, not a guess; peak-hours gating moves here too), Tier 3
→ `agy` CLI running `gemini-3.1-pro` effort high (no config field needed
for `--dangerously-skip-permissions`, `_call_agy_cli()` already always
sets it), Tier 4 → back to local Ollama `qwen2.5-coder:14b-instruct-q6_K`
(it was actually still on OpenRouter's `dots-3-note-preview` from an
earlier swap, not already-local as an earlier draft of this note assumed
— caught before the plan was drafted); Tier 1 unchanged. (2) live
`probe_models()` pre-flight check against the real edited config —
inherently makes real calls to the new DeepSeek/agy tiers, that's the
point. (3) fix the one stale test fixture
(`tests/test_orchestrator_tier3_peak_skip.py`'s `TIER_3_DEBUGGER_CONFIG`
→ `TIER_2_MANAGER_CONFIG`, since DeepSeek moves tiers). (4) `AGENTS.md`/
`PLAN.md` updates (Phase 33 entry). **Not yet dispatched — next session
should just run the dispatch and supervise it through, same pattern as
the last several runs** (resolve any human_handoff by
retargeting/diagnosing precisely, not blind-approving; correct the run's
own bookkeeping by hand only when independently re-verified).

**2. Two follow-ons queued, not yet started (do after #1 lands):**
- Add `agy` as a `tier_5_librarian` fallback leg (its ~1M context solves
  the recurring PLAN.md doc-update failures hit three times — Phases 30,
  31, 32 all had to write PLAN.md's own phase entry by hand because the
  librarian's local+OpenRouter legs couldn't handle it).
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
  run's breakdown doesn't need them all (found 2026-08-24, not yet
  fixed).

**Separately, on hold for the user (not part of the ordering above):**
- **Virtual Codebase Plan** — `VIRTUAL_CODEBASE_PLAN.md` at repo root.
  User wants to work on this one together, personally — hold off solo.
- **Consolidate target-repo-specific content out of TriAPI's own docs**
  (~700 lines of `PLAN.md` history, plus a few `AGENTS.md`/`README.md`
  mentions) — both planning and execution go through TriAPI itself
  (`triapi plan`, Tier 5 doing the rewriting), not a hand-drafted plan or
  a one-off script.
