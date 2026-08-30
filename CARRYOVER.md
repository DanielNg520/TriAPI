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
| [`docs/carryover/20260830-005500-mappingmd-split-complete-agy-direct-write-bug-found.md`](docs/carryover/20260830-005500-mappingmd-split-complete-agy-direct-write-bug-found.md) | **ACTIVE** — oh-my-llama `MAPPING.md` split (375,554 → 3,971 chars) complete and pushed via `docs/mapping/`; found+root-caused (not yet fixed) a serious `agy --dangerously-skip-permissions` direct-file-write bug, same class as the already-fixed Claude CLI hole; `AGENTS.md` plan-block-folding item now unblocked, still queued |

The ACTIVE file is the only one required reading for "what do I do next."
Everything below is historical — read a row only if your task needs that
specific history (debugging a regression in the area it covers, or
understanding why a past decision was made).

## History index

| File | Date | Status | Topic |
|---|---|---|---|
| [`20260830-001500-agentsmd-cleanup-blocked-on-oversized-mappingmd.md`](docs/carryover/20260830-001500-agentsmd-cleanup-blocked-on-oversized-mappingmd.md) | 2026-08-30 | RESOLVED | oh-my-llama `AGENTS.md` cleanup attempted, blocked on discovering `MAPPING.md` (375,554 chars) needed its own overflow split first; nothing changed, resolved in the next file |
| [`20260829-235200-three-mailwatcher-telegram-bugs-fixed-live.md`](docs/carryover/20260829-235200-three-mailwatcher-telegram-bugs-fixed-live.md) | 2026-08-29 | RESOLVED | Three real oh-my-llama runtime bugs found+fixed live (WorkingDirectory= missing, MailWatcher init_db() never called, Telegram env-var-name mismatch); one dispatch regression caught (misleading same-file comment led a tier to revert the correct ExecStart back to a stale form) and reverted by hand; AGENTS.md over-ceiling item deliberately deferred to a fresh session |
| [`20260829-233950-daemon-orchestrator-port-complete-two-real-triapi-bugs-fixed.md`](docs/carryover/20260829-233950-daemon-orchestrator-port-complete-two-real-triapi-bugs-fixed.md) | 2026-08-29 | RESOLVED | daemon.py orchestrator port for oh-my-llama completed (Phase 5G's daemon-shim blocker resolved, commits `31a43cf`/`967236b`); `tier3_escalate.py` `CalledProcessError` crash-vs-soft-escalate (`a8638ee`) and Tier 1 claude-CLI `--tools ""` direct-mutation-hole fixes (`3dbbbc7`); queued the librarian FRESH-false-negative recurrence and oh-my-llama `AGENTS.md` over-ceiling items, both carried into the next file (the first resolved there, the second still open) |
| [`20260829-210000-phase5g7-web-cut-plus-three-triapi-bugs-fixed.md`](docs/carryover/20260829-210000-phase5g7-web-cut-plus-three-triapi-bugs-fixed.md) | 2026-08-29 | RESOLVED | Phase 5G/7 web-frontend cut executed via triapi plan/dispatch, three real TriAPI pipeline bugs fixed (librarian FRESH-verify_cmd trust gap, doc-target ceiling wording, dispatch-summary KeyError) |
| [`20260829-000000-fact-proposal-port-plus-severe-daemon-blocker-found.md`](docs/carryover/20260829-000000-fact-proposal-port-plus-severe-daemon-blocker-found.md) | 2026-08-29 | RESOLVED | Resumed oh-my-llama's Phase 5G; fact-proposal port completed and verified; surfaced daemon orchestrator blocker; TriAPI whole-file-deletion bypass fixed (`99df062`) |
| [`20260828-131500-ohmyllama-phase5-resumed-recurring-buildcmd-gap-fixed.md`](docs/carryover/20260828-131500-ohmyllama-phase5-resumed-recurring-buildcmd-gap-fixed.md) | 2026-08-28 | RESOLVED | Resumed oh-my-llama's paused mail-routing dispatch once DeepSeek off-peak window opened; Phase 5 completed and pushed (`aa8a90e`), plan 10/10 done. Hand-patched a gap after all 4 tiers failed the last item: weak `py_compile`-only `build_cmd` let 2 test regressions slip through; flagged as a `triapi plan`-quality nice-to-have |
| [`20260828-053500-oh-my-llama-supervision-session-two-more-bugs-fixed.md`](docs/carryover/20260828-053500-oh-my-llama-supervision-session-two-more-bugs-fixed.md) | 2026-08-28 | RESOLVED | Never left ACTIVE when superseded by later same-day sessions (082044/090500/100000/105000/131500) — backfilled here for index consistency. Supervised full `triapi plan`/`dispatch` cycles against oh-my-llama end to end; found+fixed design-judge fix-forward discarding already-passing work, `tier_5_librarian` never running its item's verify command, plus a `--project-dir` footgun guard; oh-my-llama mail-routing plan Phases 1-4 verified+committed+pushed there |
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
| [`20260828-100000-queue-drained-5-items-plus-file-split.md`](docs/carryover/20260828-100000-queue-drained-5-items-plus-file-split.md) | 2026-08-28 | RESOLVED | Full 5-item queue drained (multi-turn statelessness, plan sanity check, `py_compile` fix, skip-grep guidance, `scope_guard`); `dispatcher.py` split to relieve file-size ceiling; docs caught up — see next file |
| [`20260828-105000-week-audit-plus-live-scope-guard-catch.md`](docs/carryover/20260828-105000-week-audit-plus-live-scope-guard-catch.md) | 2026-08-28 | RESOLVED | Full-week audit (2026-08-23–28, ~55 commits) found zero functional regressions, only 5 minor doc-accuracy issues; fixing 2 via supervised dispatch caught Tier 4 deleting `_is_deepseek_peak_hours()` out-of-scope, reverted; root-caused+fixed the `scope_guard.py` blind spot that missed it — see next file |
| [`20260828-171500-ohmyllama-full-repo-audit-4-of-6-items-false-success.md`](docs/carryover/20260828-171500-ohmyllama-full-repo-audit-4-of-6-items-false-success.md) | 2026-08-28 | RESOLVED | Full-repo audit of oh-my-llama found+fixed 5 real bugs, most severe: `agent_enabled=True` silently swallowed every approval confirm/reject. 4 of 6 dispatched items initially came back tier-`success` but were actually broken on manual verification. Commit `fa76279`, pushed clean — see next file |

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
