# Known recurring pipeline problems (session audit, 2026-09-05)

Synthesized from `docs/carryover/` history, `knowledge/TECH_DEBT.md`,
`knowledge/lessons.jsonl`, and `logs/rejected_writes/` (30+ sessions,
2026-08-12 through 2026-09-05). These are structural/recurring problems,
not one-off bugs — each has resurfaced in multiple sessions under
different symptoms. Logged per user request to track before starting the
fix work. **Not yet fixed as of this entry** — this is the backlog, see
`CARRYOVER.md`'s active file for fix-in-progress status once work starts.

## 1. False-success / false-failure reporting from the pipeline itself (highest priority)

Tiers/dispatcher repeatedly report `success` on work that's actually
broken or reverted, and separately report `build_failed` on work that's
actually fine. Examples: 4 of 6 dispatched items came back false-success
in one audit (`20260828-171500`); `_run_design_judge`/`handle_fix_forward`
outcome-propagation bugs (`20260825-173000`); a tautological verify-grep
that matched dormant/commented code instead of the live
`_CAPABILITY_FACTORIES` registry (`tautological-verify-grep` in
`lessons.jsonl`); the false `build_failed` bug root-caused to
`scope_guard.py`'s relocation-guard matching "split" inside `.split()`
calls (`20260904-204800`). Root cause is consistently **verify commands
that don't prove anything** — `py_compile`-only `build_cmd`, bare
substring grep, matching text instead of ground-truth state (a registry
dict, actual test pass/fail, actual file content post-write).

## 2. Doc/file-size ceiling churn

`AGENTS.md`, `MAPPING.md` (oh-my-llama), `dispatcher.py`,
`TECH_DEBT.md` keep ballooning past the repo's 73,728-char ceiling and
need emergency splits — `AGENTS.md` alone hit the ceiling twice
(`20260828-100000` file split, `20260904-215500` and again
`20260904-211220`/`20260904-213926` blocks) even after the 2026-08-25
"index files, never pruned" policy was adopted specifically to prevent
this. The policy reduces damage (nothing lost) but hasn't stopped the
churn — sections still have to be manually watched and split reactively.

## 3. Tier scope creep — edits outside what was asked

Tier 3/4 deleting functions out of scope
(`_is_deepseek_peak_hours()` deletion caught in `20260828-105000`),
silently deleting test classes despite reporting success
(`20260903-142631`), reverting correct code back to a stale form via a
misleading same-file comment (`20260829-235200`).
`scripts/scope_guard.py`'s relocation-guard has had multiple
false-positive *and* false-negative variants found and patched across at
least 4 separate sessions (`20260828-105000`, `20260903-162623`,
`20260904-204800` x3 more variants same session) — it reads as a
heuristic being patched reactively rather than a structurally sound
check.

## 4. Free-model instability driving constant tier reassignment

Repeated hallucinations on free OpenRouter models forced `tier_1_planner`
off Nemotron twice (`20260828-082044`, then off `dots-3-note-preview`
too per `project_tier1_planner_nemotron_hallucination` memory); the
shared 20 RPM / 1000 RPD OpenRouter pool (one pool for *all* models, not
per-model) causes cascading 429/502s across unrelated tiers
(`project_openrouter_shared_rate_limit` memory). Not fully fixable while
free tiers are in the mix, but the pipeline has no explicit
circuit-breaker for "this model is currently hallucinating" beyond
manual tier reassignment after the fact.

## 5. Bugs shipped by a dispatch, caught only by a later audit — not by the pipeline's own tests

A near-constant stream of "audit found+fixed N more bugs" carryover
entries: missing `librarian_escalate` import causing a live crash
(`20260903-001301`), null-content crash in `llm_client.py`
(`20260902-000000`), `breakdown_phase` endpoint `KeyError`
(`20260902-064500`), `agy` argv-too-long crash (`20260828-090500`), a
dead fake file split (`breakdown_guards.py`, `20260903-001301`). The
regression suite passes green on each of these before they ship — it
isn't catching what a manual audit later finds, meaning either the
suite's coverage has a systematic blind spot or (per problem #1) some of
these "green" runs weren't actually verifying what they claimed to.

## 6. State/bookkeeping bugs around resume and approval

Status-enum mismatches blocking resume (`stopped_on_failure` vs `failed`,
`breakdown-rpm-resumability` in `lessons.jsonl`); state-patch
append-instead-of-replace bug (`feedback_state_patch_replace_not_append`
memory — resume-by-count would skip the next real item); `triapi plan`
accepting `'approve'` on a bare clarifying-question turn with no
checklist, polluting a target repo's `AGENTS.md`
(`20260904-130000`). Individually small, but each has caused real
tracking/data loss when it hit.

## Assessment

#1 and #5 are the same root disease: **verification that doesn't
actually verify.** Nearly every other category here (scope creep going
undetected until a manual audit, false success/failure, doc corruption
slipping through) traces back to a verify step too weak to catch it.
Tightening `scripts/dispatcher_verify.py`'s `run_build`/`verify_task` to
require ground-truth checks (real test pass/fail, actual post-write file
content, structural checks instead of substring grep) is the
highest-leverage fix available — most of #2-#6 would either shrink or
become easier to catch quickly if #1 were solved first.
