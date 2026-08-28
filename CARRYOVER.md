# CARRYOVER — INDEX ONLY

This file is an **index**, not content. It is never pruned or trimmed for
size — it only ever grows by one row per session/task. Real carryover
content lives in dated files under `docs/carryover/`. **Read only the
row(s) below relevant to your current task — do not read every file.**

**Machine-readable index: [`docs/carryover/index.json`](docs/carryover/index.json)
is the authoritative source** (this table is a human-readable mirror of
it, kept in sync by hand). Fastest way to resume: `jq -r '.active'
docs/carryover/index.json`, then read only that file — no need to parse
this markdown table at all.

## Read first, always

| File | Status |
|---|---|
| [`docs/carryover/20260828-100000-queue-drained-5-items-plus-file-split.md`](docs/carryover/20260828-100000-queue-drained-5-items-plus-file-split.md) | **ACTIVE** — full 5-item queue drained: multi-turn planner statelessness fixed (`f28af99`), plan-output sanity check added (`8b2ff71`), `py_compile`-insufficient verify command fixed (`0b6cc30`), bare-`skipped`-grep prompt guidance added (`cf325ad`), Tier 3 out-of-scope-edit advisory flag added (`b57579e`); `dispatcher.py` proactively split (72906→63659 chars) to relieve file-size ceiling (`78c194d`); docs caught up (`ae566e6`); full suite 243 tests OK; working tree clean, nothing mid-flight, no open items besides old carried-forward architecture work |

The ACTIVE file is the only one required reading for "what do I do next."
Everything below is historical — read a row only if your task needs that
specific history (debugging a regression in the area it covers, or
understanding why a past decision was made).

## History index

| File | Date | Status | Topic |
|---|---|---|---|
| [`20260826-063000-agy-fallback-http-timeout-complete-queue-updated.md`](docs/carryover/20260826-063000-agy-fallback-http-timeout-complete-queue-updated.md) | 2026-08-26 | RESOLVED | `agy` fallback leg + `_HTTP_TIMEOUT` fix complete and committed (run `20260825-194415-b54313`); a missing `llm_client.execute_agy()` bug found+fixed; session closed cleanly, nothing mid-flight |
| [`20260823-210000-openrouter-merge-and-tier-swap.md`](docs/carryover/20260823-210000-openrouter-merge-and-tier-swap.md) | 2026-08-23 | RESOLVED | OpenRouter branch merge into `main`; Tier 3/4 provider swap; 4 early bug fixes; backend-registry and complexity-router architecture items first queued |
| [`20260824-030000-librarian-tier5-redesign-debugging.md`](docs/carryover/20260824-030000-librarian-tier5-redesign-debugging.md) | 2026-08-24 | RESOLVED | Tier 5 librarian build: 5 debugging addenda (epoch-collision staleness bug, stale test mocks, human_handoff bookkeeping bug, PLAN.md-too-large stall, OpenRouter phone-filter fix drafted) |
| [`20260824-190000-queue-snapshot-openrouter-obstacles.md`](docs/carryover/20260824-190000-queue-snapshot-openrouter-obstacles.md) | 2026-08-24 | SUPERSEDED | Old queue snapshot mid-fix — OpenRouter dispatch obstacles (403s, 429s, `probe_models()` over-gating found) |
| [`20260824-235900-misc-resolved-fixes.md`](docs/carryover/20260824-235900-misc-resolved-fixes.md) | 2026-08-24 | RESOLVED | `KeyError: 'choices'` fix; `probe_models()` retry tolerance; Ollama lifecycle test hang (found, not fixed) |
| [`20260825-000000-openrouter-fixes-tier-prep-pipefail-complete.md`](docs/carryover/20260825-000000-openrouter-fixes-tier-prep-pipefail-complete.md) | 2026-08-25 | RESOLVED | OpenRouter phone/IP sanitizer + peak-hours dedup (Phase 30); `agy` provider + generic routing + position-independent peak gate (Phase 31); `run_build()` pipefail fix (Phase 32); `git_ops` auto-branch removed |
| [`20260825-092344-active-tier-flip-plan-and-queue.md`](docs/carryover/20260825-092344-active-tier-flip-plan-and-queue.md) | 2026-08-25 | RESOLVED | Tier reassignment plan drafted+approved+dispatched+committed (`762ff81`); 3 hardcoded-Tier-3 bugs fixed; a recurring false-success pipeline bug first discovered here |
| [`20260825-173000-tier-flip-complete-false-success-bug-fixed.md`](docs/carryover/20260825-173000-tier-flip-complete-false-success-bug-fixed.md) | 2026-08-25 | RESOLVED | False-success `dispatcher.py` bug fixed+committed (`5a6ae01`): `_run_design_judge`/`handle_fix_forward` outcome propagation; two 300s timeout root causes fixed; incidental `agy` `system_prompt` bug fixed; updated queue |
| [`20260826-025500-paused-for-deepseek-offpeak-agy-fallback-queued.md`](docs/carryover/20260826-025500-paused-for-deepseek-offpeak-agy-fallback-queued.md) | 2026-08-26 | RESOLVED | Session paused mid-dispatch for DeepSeek peak hours (run `20260825-194415-b54313`); resumed and completed in the next file |
| [`20260826-193000-tier3-timeout-softescalate-architecture-refresh-agentsmd-routing-bug.md`](docs/carryover/20260826-193000-tier3-timeout-softescalate-architecture-refresh-agentsmd-routing-bug.md) | 2026-08-26 | RESOLVED | Run `fa6eea` completed+committed (`60cd085`): Tier 3 CLI-timeout soft-escalation + `ARCHITECTURE.md` refresh; the doc-target routing-inconsistency theory queued here was a misdiagnosis, corrected in the next file; `git_ops.push()` `git add -A` scoping gap found, still unfixed |
| [`20260828-012100-tier5-agy-swap-paused-4-new-bugs-queued.md`](docs/carryover/20260828-012100-tier5-agy-swap-paused-4-new-bugs-queued.md) | 2026-08-28 | RESOLVED | `_run_design_judge`/`critique.applies_to_tiers` bug fixed+committed (`96e005e`); `tier_5_librarian` primary swapped to `agy`/Gemini-3.7-Flash; 4 new bugs queued (AGENTS.md bloat, `agy` argv-too-long, `staleness_precheck` false-negative, dynamic-target-bypass); continuation resolved 3 of 4, reopened the 4th with a corrected diagnosis — see next file |
| [`20260828-082044-queue-cleared-tier1-planner-swapped.md`](docs/carryover/20260828-082044-queue-cleared-tier1-planner-swapped.md) | 2026-08-28 | RESOLVED | 3 of 4 previously-queued bugs resolved+committed (AGENTS.md bloat, `staleness_precheck` false-negative, dynamic-shell-expression-target bug); `agy` argument-length bug reopened with a corrected diagnosis (stdin approach disproven live, reverted cleanly); `tier_1_planner` swapped off a repeatedly-hallucinating free Nemotron model to `dots-3-note-preview:free`, live-verified; 4 new gaps queued — see next file |
| [`20260828-090500-agy-argv-fix-tier1-planner-moved-off-openrouter.md`](docs/carryover/20260828-090500-agy-argv-fix-tier1-planner-moved-off-openrouter.md) | 2026-08-28 | RESOLVED | `agy` argv-length crash fixed+committed (`3cbdeba`); `tier_1_planner` moved off two hallucinating free OpenRouter models onto `agy`/Gemini 3.1 Pro; effort-forwarding bug and librarian `fallback_openrouter` endpoint bug found+fixed; multi-turn planner-statelessness bug newly discovered, queued — resolved in next file |

## Convention for adding a new entry (read once, then follow every session)

1. **Filename**: `docs/carryover/YYYYMMDD-HHMMSS-brief-kebab-title.md` —
   timestamp of when the entry was written, title is 3-6 words.
2. **Update BOTH `index.json` and this markdown table together, every
   time** — `index.json` is authoritative for tooling/queries, this table
   is for a human skimming the file directly. Never let them drift.
3. **Exactly one entry is ever tagged/marked `ACTIVE`** (`index.json`'s
   top-level `"active"` key, and this table's "Read first, always" row) —
   the current-state file a new session reads first. When that file's
   work is fully done: move it into `index.json`'s `history` array with
   status `RESOLVED`/`SUPERSEDED`, update this table's History index the
   same way, create a new dated file, and point `"active"`/the "Read
   first" row at it. Never leave two active at once; never leave zero.
4. **Never delete or prune** a `docs/carryover/` file or its index entry.
   If content becomes wrong, add a short correction note at its use site
   (or in the ACTIVE file) rather than editing history away.
5. **Keep each dated file under 73,728 characters** (this repo's
   file-size ceiling). Split further by topic/timestamp if a session
   would otherwise overflow one file — see the multiple entries from
   2026-08-24 for the pattern (one file per distinct sub-topic/session
   segment, not one giant file per day).
6. **Index entries stay one line/one topic clause** — file, date,
   status, topic only, same shape in both `index.json` and this table.
   Full detail belongs in the dated file itself.
7. This is the same convention `AGENTS.md`'s own top-of-file index and
   `docs/agents/index.json` follow for file/dir documentation overflow —
   see `AGENTS.md`'s index section.
