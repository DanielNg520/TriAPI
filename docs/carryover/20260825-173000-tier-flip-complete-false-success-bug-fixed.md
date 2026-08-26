# 2026-08-25 17:30 — ACTIVE: tier-flip landed, false-success pipeline bug found+fixed, updated queue

**This is the primary file to read to resume work — everything else in
`docs/carryover/` is historical/completed context only.**

## Current state

Working tree clean, both commits landed on `main`, full 194-test suite green
(191 baseline + 3 new). Nothing running, nothing uncommitted, nothing blocked.

## What happened this session (2026-08-25 daytime session, continuing from the previous one)

**1. Tier-flip dispatch (`20260825-092344-5ff4a7`) finished and committed
(`762ff81`).** Resumed the run left ready-to-dispatch by the prior session.
Final assignment: Tier 2 → real DeepSeek API (`deepseek-v4-pro`, peak-hours
gating moved here from Tier 3), Tier 3 → `agy` CLI running `gemini-3.1-pro`
(Antigravity, effort high), Tier 4 → local Ollama
`qwen2.5-coder:14b-instruct-q6_K`. Tier 1 (planner + manager) untouched.
Three real hardcoded-Tier-3 bugs found and fixed while supervising:
`scripts/judge.py` and `scripts/tier3_escalate.py` both bypassed the generic
`llm_client.execute_llm()` dispatcher with a raw DeepSeek HTTP call and
direct `tier3["pricing"][model_key]` indexing — broke instantly once Tier 3
stopped being DeepSeek. `scripts/cost_report.py`'s `deepseek_flash_cost()`
had the same pattern; its reference pricing moved to a new standalone
`deepseek_reference_pricing` config block, decoupled from any tier slot.

**2. Found, while resolving the tier-flip run's own doc-update step: a
recurring "false success" bug in `dispatcher.py`'s design-judge/fix-forward
interaction.** The Phase 4 item to fix `AGENTS.md`'s stale tier-assignment
text reported `status: success, resolved_by: tier_5` — but `git diff`
proved the file was byte-for-byte unchanged. Root-caused precisely (see
`docs/agents/20260825-100000-scripts-directory-reference.md`'s updated
`dispatcher.py` entry for the exact mechanism):
`dispatcher._run_design_judge()`'s rejection branch called
`handle_fix_forward()` but discarded its outcome entirely, always returning
the original pre-judge `"success"` result even when the fix-forward repair
itself failed. Hand-fixed `AGENTS.md`'s content directly (same "hand-edit
when the automated path demonstrably fails" precedent as Phases 30-32's
PLAN.md workaround), then dispatched a proper `triapi plan`/`dispatch` fix
for the underlying pipeline bug itself (`20260825-154633-8927c3`, now
committed as `5a6ae01`) — this was TriAPI's own pipeline code, not a
one-off doc fix, so it went through the normal plan/dispatch process per
standing practice, with me supervising and hand-fixing only where the
automated tiers demonstrably failed (with each hand-fix independently
verified before accepting it, per `feedback_verify_dont_trust_status`).

**3. The false-success fix dispatch (`20260825-154633-8927c3`) hit three
real obstacles along the way, all found and fixed at the root, none
papered over:**
- `orchestrator.verify_task()`'s `run_build(..., timeout=300)` — this
  repo's own full test suite legitimately takes 166–330s, leaving no
  headroom at exactly 300s. A baseline-verification step hit this wall and
  reported a false `human_handoff`; independently reconfirmed the suite
  passing seconds later. Raised to 600s (comment updated to explain why,
  distinct from `run_build()`'s own unaffected 300s default, which
  protects retrying draft-loop tiers rather than a one-shot check).
- `llm_client._CLI_TIMEOUT` (300s, shared by `claude`/`agy` CLI
  subprocesses) — a real `agy -p ... --effort high` call hit this wall and
  crashed the *entire* dispatch process with an uncaught `RuntimeError`
  (`orchestrator.run_task()` treats any Tier 3 "error" status, timeouts
  included, as a hard crash rather than a soft escalate-to-Tier-2 — a
  separate, bigger design question, not addressed this session, queued
  below). Raised to 600s.
- **Incidental find, likely explains a chunk of today's repeated Tier 3
  SEARCH/REPLACE parse failures**: `llm_client._call_agy_cli()` never
  accepted a `system_prompt` parameter at all, so
  `tier3_escalate.py`'s `system_prompt=stable_context` argument was
  silently dropped on every single `agy` call since Tier 3 became `agy` —
  Tier 3 was missing its own anchoring context on every attempt. Fixed
  (`_call_agy_cli()` now prepends `system_prompt` to the prompt when
  given, mirroring `_call_claude_cli()`'s handling).

**4. The new regression test (`tests/test_design_judge_fix_forward_status.py`)
itself took 4 automated-tier attempts to author and all 4 failed** — not
because the fix logic was wrong, but because of three real test-authoring
mistakes: missing `autospec=True` on the `tier3_escalate.escalate` mock
(`handle_fix_forward` runtime-checks the real function's signature via
`inspect.signature()`, and a plain `mock.patch` doesn't preserve it — a
subtle, easy-to-miss `unittest.mock` gotcha); the `run_build` mock
returning a bare `True` instead of the real `(ok, output)` tuple; and the
test never capturing `_run_design_judge()`'s return value (the fix
correctly returns a *new* dict on the downgrade path rather than mutating
in place, so a discarded return value silently means the "downgrade
worked" assertion is checking stale data). Hand-fixed all three, re-ran
the file in isolation to confirm all 3 tests pass and case (c) genuinely
proves the downgrade fires, then manually resolved the run's own
bookkeeping (`manual_test_supervisor`/`manual_docs_supervisor`-style
entries, same precedent as previous hand-fixes this session) rather than
continuing to spend real tier-escalation cycles on an already-correct
file — this was an explicit user decision after the item had cycled for
over an hour across two separate 300s-timeout crashes.

**5. Cleanup**: 8 stray debugging scratch files (`test_empty.py`,
`test_regex*.py`, `test_parse.py`, `test_prompt.py`) left at repo root by
one of the AI tiers while investigating SEARCH/REPLACE parsing during this
session's many retry cycles — deleted, never committed. One legitimate
side-effect auto-commit (`ef9abff`, TriAPI's own `git_ops`) landed on `main`
during the dispatch cycles: a stale test mock fix
(`test_escalate_with_null_content_returns_failure_and_preserves_file` now
mocks `load_tiers` since Tier 3's real config shape changed) — harmless,
already covered by the green suite.

**Both fixes are committed to `main`:**
- `762ff81` — tier reassignment (config/tiers.yaml, judge.py,
  tier3_escalate.py, cost_report.py, test fixture, AGENTS.md, PLAN.md)
- `ef9abff` — auto-committed stale test mock fix (git_ops, incidental)
- `5a6ae01` — false-success bugfix (dispatcher.py, orchestrator.py,
  llm_client.py, new test file, test_ollama_service_lifecycle.py mock fix,
  AGENTS.md, docs/agents reference doc)

## Standing rules (accumulated, still in effect — see prior active file for full detail, unchanged this session)

- Allowed models, no Gemini except `agy`/Jules.
- Everything configurable, no hardcoded provider/tier paths.
- OpenRouter shared rate limit (20 RPM/1000 RPD pool-wide).
- DeepSeek peak-hours windows: 01:00-04:00 and 06:00-10:00 UTC, weekdays,
  now live on `tier_2_manager` (moved from `tier_3_debugger` this session).
- Doc architecture: `AGENTS.md`/`CARRYOVER.md` are permanent index files,
  never pruned; real content in `docs/carryover/`/`docs/agents/`.
- **New this session**: verify-step `build_cmd`s that only check file size
  (`wc -c`) cannot catch a no-op edit reporting false success — this is
  exactly the shape of bug that was just found and fixed once, but the
  general pattern (a shallow verify masking a real failure) is worth
  watching for elsewhere.

## Next up (priority order)

**1. Add `agy` as a `tier_5_librarian` fallback leg** — still the single
highest-value fix queued. Solves the recurring PLAN.md-too-large librarian
gap (Phases 30/31/32 all hit it) AND would have prevented needing a manual
hand-fix for this session's own `AGENTS.md` false-success incident, since
`agy`'s ~1M context has no OpenRouter content-filter exposure and doesn't
share librarian's local-model context ceiling.

**2. New design question, queued from this session's timeout-crash
investigation**: should `orchestrator.run_task()` treat a Tier 3 CLI
*timeout* (a `subprocess.TimeoutExpired`-shaped failure) as a soft
escalate-to-Tier-2 rather than the current hard crash-the-whole-dispatch
behavior it gives every Tier 3 "error" status? A slow-but-working call is
currently indistinguishable from a genuine misconfiguration/crash, and the
former should probably just fall through instead of aborting the entire
run. Not attempted this session — bumping `_CLI_TIMEOUT` to 600s was the
minimal fix that unblocked the immediate crash; this is the bigger,
separate architectural question underneath it. Plan/dispatch this properly
rather than hand-patching `orchestrator.py`'s escalation semantics.

**3. Make every tier's fallback mechanism individually on/off
configurable** — natural extension of the backend-registry architecture
item below, matching "everything configurable, no hardcoding."

**4. Unresolved OpenRouter `[PHONE]` filter root-cause question** (from the
prior session, never actually resolved): is the real trigger shape-specific
(what `_PHONE_LIKE_RE`/`_IP_LIKE_RE` cover) or does it fire on any long
unbroken digit run? A live test attempt was inconclusive (hit the shared
OpenRouter rate-limit pool before getting a real answer). Retry when
convenient, away from other OpenRouter activity. The queued `agy`-librarian-
fallback item (above) sidesteps this specific question for PLAN.md, but the
general question is still open for any other doc that might trip it.

**5. Groq provider addition** (`qwen/qwen3.6-27b`, `groq_api_key` already in
`secrets.enc.yaml`, unwired) — lightweight/router role, not a tier
replacement. Rate limits given (RPM 30, RPD 1,000, TPM 8,000, "200K" figure
of unverified unit) need re-verifying against Groq's real docs before wiring
a hard gate.

**6. Architecture items** (self-feature work — plan/dispatch, don't
hand-build):
- Named backend registry (`backends:` section in `tiers.yaml`) so
  tier↔model reassignment is a one-line pointer change.
- Complexity-aware router ahead of the tier ladder (large plan → full
  ladder, pure doc-reconcile → straight to Tier 5). Also would subsume
  `probe_models()` unconditionally gating on all 6 tiers even when a run's
  breakdown doesn't need them all.

**Separately, on hold for the user (not part of the ordering above):**
- **Virtual Codebase Plan** — `VIRTUAL_CODEBASE_PLAN.md` at repo root. User
  wants to work on this one together, personally — hold off solo.
- **Consolidate target-repo-specific content out of TriAPI's own docs**
  (~700 lines of `PLAN.md` history, plus a few `AGENTS.md`/`README.md`
  mentions) — both planning and execution go through TriAPI itself
  (`triapi plan`, Tier 5 doing the rewriting), not a hand-drafted plan or a
  one-off script.
- **`docs/TUI_plan.md`** — untracked draft at repo root from an earlier
  session (the `triapi tui` subcommand spec: fresh `claude -p` calls per
  prompt, no session continuity, carryover-log-mediated continuity instead,
  live-streamed output). Not yet planned/dispatched, blocked by the
  one-plan-per-repo gate like everything else — pick up whenever ready.
