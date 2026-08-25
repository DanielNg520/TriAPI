# 2026-08-25 09:23 — ACTIVE: tier-flip plan ready to dispatch, standing rules, full queue

**This is the primary file to read to resume work — everything else in
`docs/carryover/` is historical/completed context only.**

## 2026-08-25 ~11:40 session stop (usage-limited, stopped gracefully mid-task)

**Tier-flip dispatch (`20260825-092344-5ff4a7`) is 9/15 items done, NOT
finished.** Phase 1 (all 4 config-reassignment items) and Phase 2 (live
pre-flight probe) both completed successfully. Phase 3 item 1 (rename
`TIER_3_DEBUGGER_CONFIG`→`TIER_2_MANAGER_CONFIG` fixture in
`tests/test_orchestrator_tier3_peak_skip.py`) landed **incompletely** —
bigger leftover than first recorded here. Checked the actual file
2026-08-25 ~12:05: only the fixture's *definition* was renamed/rewritten
(new `TIER_2_MANAGER_CONFIG` dict at the top, correct new shape). Every
*usage* site still references the old name, and worse,
`test_config_matches_tiers_yaml` (lines 31-57) still asserts the entire OLD
`tier_3_debugger` shape verbatim (nested `flash`/`pro`/`default` pricing
sub-keys, `models: {"flash": "deepseek-chat"}`, old role text) — none of it
matches the new `TIER_2_MANAGER_CONFIG` dict sitting right above it.
`test_peak_hours_skip_tier3`/`test_off_peak_allows_tier3` (lines 65, 73)
also still pass `{"tier_3_debugger": TIER_3_DEBUGGER_CONFIG}` to the mocked
loader instead of `{"tier_2_manager": TIER_2_MANAGER_CONFIG}`. Full suite
run (Phase 3 item 3) failed hard on this:
`NameError: name 'TIER_3_DEBUGGER_CONFIG' is not defined`. See
`logs/escalation_20260825-092344-5ff4a7-p2-i2.md`. Run status:
`stopped_on_failure`, human_handoff logged. **Next session: rewrite
`test_config_matches_tiers_yaml`'s body (lines 32-57) to assert
`TIER_2_MANAGER_CONFIG`'s actual flat-pricing shape instead of the old
nested one, and fix the two mock `load_tiers` calls (lines 65, 73) to key
on `tier_2_manager` — the exact target shape is already fully specified in
AGENTS.md's own embedded Phase 3 checklist item (see the
`<!-- triapi:plan run_id=20260825-092344-5ff4a7 -->` block, Phase 3 first
bullet) — then rerun the suite, then
`triapi dispatch 20260825-092344-5ff4a7` to resume through Phase 3 item
3's rerun + all of Phase 4 (AGENTS.md/PLAN.md updates) if nothing else
surfaces.**

Three real root-cause bugs were found and fixed this session while
supervising this run (all committed to the working tree, uncommitted at
session end — verify `git status` before assuming these landed):
`scripts/judge.py` and `scripts/tier3_escalate.py` both hardcoded Tier 3 to
a raw DeepSeek-shaped HTTP call and `tier3["pricing"][model_key]` direct
indexing instead of the generic `llm_client.execute_llm()` dispatcher —
broke the instant Tier 3 became `agy` (a CLI provider with no
endpoint/pricing block). Fixed both call sites to route generically and use
`.get()` fallbacks; updated `tests/test_judge.py`'s mocks to match (16/16
pass). Also found the dispatch's own regression-check catch a real bug:
applying the Tier 3 edit had silently stripped `peak_hours_utc`/`pricing`
that a prior item had just added to `tier_2_manager` — restored by hand.
And `scripts/cost_report.py`'s `deepseek_flash_cost()` had the same
hardcoded-pricing-under-tier_3_debugger pattern (third occurrence) — fixed
by moving that reference pricing into a new standalone
`deepseek_reference_pricing` top-level block in `config/tiers.yaml`,
decoupled from any tier slot. Full 191-test suite was green after all
three fixes, before this last Phase-3-fixture issue surfaced.

**Also found, not yet fixed:** `scripts/librarian_escalate.py` silently
no-op'd (`"changed": false`) on a legitimate, straightforward append to a
small (7.8KB) file — not the known large-doc gap. Worked around by hand
once; still needs investigation as its own bug.

**New feature queued, NOT yet planned/dispatched (do not hand-build —
route through `triapi plan`/`triapi dispatch` once the tier-flip run above
is fully drained; blocked right now by the one-plan-per-repo gate anyway):**
add a `triapi tui` subcommand. Spec, confirmed with the user 2026-08-25:
- New CLI flag/subcommand `triapi tui` (not a change to bare `triapi`'s
  existing behavior) launches an interactive terminal UI.
- Each prompt typed into the TUI triggers a **fresh, independent**
  `claude -p "<prompt>"` call — explicitly NOT session-continued
  (`--continue`/`--resume`) — no conversation memory is carried
  CLI-side between turns.
- Instead, continuity comes from logging: each call's progress/state/
  activity, plus TriAPI's own errors and responses, gets a **meaningful,
  brief** entry logged and indexed into `CARRYOVER.md` (presumably a new
  dated `docs/carryover/` file per session, per the existing index
  convention) so the *next* session/TUI launch has context of what came
  before — this is the mechanism that replaces conversational memory here.
- Output streams live into the TUI as `claude -p` generates it (not
  buffered until completion).
- The example prompt shape the user gave: a prompt like "Read carryover.md
  and carryon with the queue." is exactly the kind of thing this TUI is
  for — i.e. the TUI is meant to be the normal day-to-day driver of
  TriAPI-adjacent work going forward, not a one-off tool.

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

**Standing interim rule, user directive 2026-08-25 (during the tier-flip
dispatch):** until the queued `agy`-as-`tier_5_librarian`-fallback-leg
feature above is fully built, deployed, and confirmed working, manually
invoke the `agy` CLI (Antigravity/Gemini 3.1 Pro, separate auth from
OpenRouter, does not go through OpenRouter's content filter at all) to
check/process any content suspected of tripping the OpenRouter `[PHONE]`
false-positive filter (e.g. `PLAN.md`'s dense digit runs), instead of
relying on the automated OpenRouter path or waiting on the unresolved
shape-vs-digit-run root-cause test above. This is a manual workflow
stopgap, not a code change — mark it superseded once the librarian
fallback leg ships and is verified working.

**Bug found while recording the note above:** `scripts/librarian_escalate.py`
silently no-op'd on this exact file (`{"status": "success", "resolved_by":
"tier_5", "changed": false, "via": "model_fresh"}`) when asked to append
this same paragraph — a straightforward append to a 7,836-char file, well
under the 73,728-char ceiling and not the known large-doc (`PLAN.md`) gap
already tracked in `project_triapi_librarian` memory. The model apparently
judged the file "fresh" (no change needed) despite the requested content
genuinely being absent. Worked around by hand-editing this file directly
this one time. Queued as a new, distinct librarian bug to investigate: why
does Tier 5's model_fresh path decide "no change needed" for a real,
missing addition on a small file? Reproduce with a similarly-sized
target/description pair before assuming it's a fluke.

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
