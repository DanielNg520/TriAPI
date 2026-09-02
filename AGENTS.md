# AGENTS.md

Repo-root reference for coding agents: codebase conventions, test commands, architecture, and guidelines, plus a living index of every file/dir in this repo. Read this before exploring — updated at the end of every phase. (Renamed from `mapping.md` 2026-08-17; conventions/test-commands/architecture content is being folded in incrementally as it's touched, not as a one-time rewrite — see `AGENT_GUIDE.md`/`ARCHITECTURE.md`/`README.md` for the fuller versions of each until then.)

**Standing rule, effective 2026-08-25 (supersedes the 2026-08-18/19 "prune
regularly" policy below): `AGENTS.md` and `CARRYOVER.md` are permanent
INDEX files, never pruned or trimmed for size again.** Real content —
session/task carryover, and (once this file's own index would otherwise
grow past the ceiling) file/dir documentation overflow — lives in dated,
titled files under `docs/carryover/` and `docs/agents/` respectively, each
kept under this repo's 73,728-char ceiling on its own. The goal is token
efficiency: an agent reads the relevant index row(s), then only the
specific dated file(s) that row points to — never the full history. See
the two index sections immediately below, and the "Convention for adding
a new entry" block in `CARRYOVER.md` (the same convention applies to both
folders). See `feedback_docs_are_index_files` memory.

<details>
<summary>Historical: 2026-08-18/19 "prune regularly" policy (superseded, kept for context only)</summary>

Docs stayed clean via periodic outright removal of stale content: session
narrative, per-run diagnostic play-by-play, and anything about a *target*
repo TriAPI dispatched against (e.g. oh-my-llama) never belonged in
TriAPI's docs at all. 2026-08-18: `agent_evalution.md`, `agent_testrun.md`,
`GHOSTWRITER_PLAN.md` removed outright (target-repo narrative);
`CARRYOVER.md` cut from ~2,400 lines to a short current-state brief, the
play-by-play discarded rather than relocated. 2026-08-19: same treatment
applied to `AGENTS.md` itself — 9 fully-checked-off `triapi:plan` history
blocks (~417 lines) removed, since their outcomes were already in
`PLAN.md`; file went from 146,117 to ~53,000 chars. This discard-based
policy is now replaced by the index/archive policy above — nothing gets
discarded going forward, it gets filed into `docs/carryover/`/`docs/agents/`
instead.
</details>

## Carryover index — session/task state (read this to resume work)

**Machine-readable: [`docs/carryover/index.json`](docs/carryover/index.json)**
(`jq -r '.active' docs/carryover/index.json` gets you the one required
file with zero markdown parsing). Human-readable mirror:

| File | Status |
|---|---|
| [`CARRYOVER.md`](CARRYOVER.md) | Full index of `docs/carryover/` — **read this first**, then only the row(s) it points you to |

`CARRYOVER.md`'s own top row (and `index.json`'s `"active"` key) always
name the current `ACTIVE` file — that is the one required read for "what
do I do next." Do not read `docs/carryover/`'s historical files unless
your task specifically needs that history.

## This file's own index

**Machine-readable: [`docs/agents/index.json`](docs/agents/index.json)**
lists every file/dir doc that has overflowed out of this file (currently
two: the full `scripts/` reference, and the archived historical
`triapi:plan` blocks — see the rows below).
Human-readable mirror:

| Section | What's there |
|---|---|
| [Conventions, test commands, architecture](#conventions-test-commands-architecture-quick-reference) | Quick pointers to `AGENT_GUIDE.md`/`ARCHITECTURE.md`, the standard test command |
| [Root](#root) | Top-level docs and config files |
| [config/](#config) | `tiers.yaml`, secrets |
| [knowledge/](#knowledge) | `lessons.jsonl`, `TECH_DEBT.md`, `hivemind.md` |
| [scripts/](#scripts) | Pointer only — full reference moved to [`docs/agents/20260825-100000-scripts-directory-reference.md`](docs/agents/20260825-100000-scripts-directory-reference.md) (2026-08-25, this file's largest section, moved to stay under the 73,728-char ceiling without pruning any content) |
| [tests/](#tests) | Test file map |
| [logs/](#logs) | Runtime log layout (gitignored) |
| [samples/](#samples) | Fixture projects for end-to-end verification |
| [Historical `triapi:plan` blocks](#historical-completed-triapiplan-blocks-2026-08-25-through-2026-08-27) | Pointer only — 5 completed plan runs moved to [`docs/agents/20260828-044229-agents-md-historical-plan-blocks-archive.md`](docs/agents/20260828-044229-agents-md-historical-plan-blocks-archive.md) (2026-08-28, kept this file under the 73,728-char ceiling) |

**Convention for moving a section to `docs/agents/` (same shape as
`docs/carryover/`'s convention in `CARRYOVER.md`):** filename
`docs/agents/YYYYMMDD-HHMMSS-brief-kebab-title.md`; add an entry to
`docs/agents/index.json` AND a row here pointing to it; never delete the
moved content, only relocate it; replace the inline section with a short
pointer paragraph, not a stub summary (the summary would drift from the
real content — the pointer is the single source of truth). Move a
section when this file's total size is within a few KB of the ceiling
and that section is the largest/lowest-churn one, not preemptively.

## Conventions, test commands, architecture (quick reference)
- **Conventions/guidelines:** full detail in `AGENT_GUIDE.md` (agent operating manual — what's safe to hand-edit vs. must route through the dispatch pipeline, phase discipline, verification requirements).
- **Test commands:** `PYTHONPATH=. python3 -m unittest tests.test_branch_features tests.test_tier5_librarian -v` (full regression suite); `python3 -m py_compile <file>` before any script change is considered done.
- **Architecture:** full detail in `ARCHITECTURE.md` (5-tier escalation state machine — Tier 5, the doc librarian, added 2026-08-24 — budget guard rationale, DeepSeek cache-hit economics).

## Root
- `PLAN.md` — phase-by-phase implementation plan with checklists and end-of-phase tests. The permanent record of TriAPI's own build — read here for *why*, not `CARRYOVER.md`. Split 2026-09-01 (was ~205,040 chars, ~2.7x this repo's 73,728-char ceiling): now a short index with pointers into `docs/plan/` (own `index.json`, same convention as `docs/agents/`) — see PLAN.md's own "This file's own index" section for the row-by-row map. Nothing after the 2026-08-25 tier reassignment should be appended here as new inline Phase blocks; use `CARRYOVER.md`/`docs/carryover/` for session work, and add a new `docs/plan/` entry only for durable build-rationale record.
- `AGENTS.md` — this file (formerly `mapping.md`).
- `ARCHITECTURE.md` — system design: the 4-tier escalation state machine, DeepSeek cache-hit economics, budget guard rationale, and what changed during the build (Tier 2 redesign, MCP server dropped, Jules deferred).
- `README.md` — step-by-step walkthrough (first-time run, reading output/cost report, human-handoff files, common gotchas) plus setup (Python deps, sops/age, Ollama systemd service, Claude Code subscription login) and command reference (standalone task, smoke test, cost report).
- `AGENT_GUIDE.md` (2026-08-14) — for an agent operating `triapi` with Tier 1 off (`--no-tier1` / `tier_1_manager.enabled: false`): what actually changes (repair chain only, `planner.py` untouched), why the agent effectively becomes planner+supervisor+monitor with one less automated repair tier, and the concrete human_handoff diagnosis/patch/resume workflow. Also documents `scripts/self_fix.py` (crash-triggered plan drafting, never auto-dispatched) and `knowledge/lessons.py` + `scripts/critique.py` (failure-pattern knowledge store + advisory diff-quality gate) — both TriAPI's own features, proven via worked dispatches against a target repo; target-repo specifics of those dispatches live in that repo's own docs, not here.
- `CARRYOVER.md` — brief current-state resume note only. Read this first when resuming work.
- `VIRTUAL_CODEBASE_PLAN.md` (2026-08-19, restored 2026-08-23 after a since-reverted deletion) — queued design reference, not started: a Tiered Planner-Materializer architecture (Slicer/Planner/Materializer/Patcher roles, Tree-sitter-based semantic extraction) so Tier 4 edits on oversized files stop being an all-or-nothing load/skip decision. **User wants to work on this one together, personally — do not start it solo**, per their explicit 2026-08-23 instruction; this note was dropped from `CARRYOVER.md`'s active chain after 2026-08-28 and had gone untracked in this index until 2026-09-01 (see `docs/carryover/`'s history for the original discussion).
- `docs/TUI_plan.md` (2026-08-25) — confirmed spec, not yet dispatched, for a new `triapi tui` subcommand (interactive terminal UI, each prompt a fresh independent `claude -p` call with no CLI session continuity, continuity instead carried via `CARRYOVER.md` dated-file logging — see the file for the full spec and its still-open design questions). Was blocked on the tier-flip dispatch draining at the time it was written; that dispatch completed long ago, so this is now unblocked and ready for a `triapi plan` session once the open design questions are resolved with the user. Also went untracked in this index until 2026-09-01.
- `.sops.yaml` — sops encryption rule: files matching `config/secrets.enc.yaml` are encrypted to the age recipient in `~/.config/sops/age/keys.txt`.
- `.gitignore` — excludes runtime logs/state, plaintext secrets, Python caches, venvs.
- `requirements.txt` — Python deps: `requests`, `PyYAML`, `mcp`.
- `LICENSE` — Apache-2.0.

## config/
- `tiers.yaml` — tier definitions: models, endpoints, roles, pricing (DeepSeek pricing needs periodic reverification, see `last_verified`), escalation thresholds. As of the Phase 33 reassignment (2026-08-25), `tier_2_manager` is the real DeepSeek API (`deepseek-v4-pro`; `peak_hours_utc` now lives here, moved from Tier 3), `tier_3_debugger` is `agy`/`gemini-3.1-pro` (Antigravity CLI, effort high, no peak-hours/pricing block), and `tier_4_worker` is local Ollama `qwen2.5-coder:14b-instruct-q6_K` at `http://localhost:11434` — check the file directly for the live assignment rather than trusting a snapshot here, since these get reassigned periodically (see `CARRYOVER.md`'s "Next up" for the most recent reassignment in flight). `tier_2_manager.peak_hours_utc` (or wherever `budget_guard.resolve_deepseek_tier()` currently finds the real DeepSeek API assignment — position-independent as of Phase 31, not hardcoded to a tier name) — UTC peak-window list checked by `budget_guard.check_tier3_peak_hours_ok()`, defaulting to the two DeepSeek V4 peak windows if absent; `tier_3_debugger.default_model` is `default` (`gemini-3.1-pro` via `agy`). `critique:` block (enabled, applies_to_tiers, critic, score_threshold, max_revision_attempts) gates the advisory diff-quality step in `orchestrator._critique_and_maybe_revise()`. `self_fix.enabled` controls crash-triggered plan drafting without disabling report capture. `tier_1_manager.enabled` (2026-08-14) — on/off switch for Tier 1's *repair* role in `orchestrator.run_task()`; distinct from `tier_1_planner` above, which configures `planner.py`'s interactive plan-authoring role and is untouched by this switch. Boolean, default `true` (both in the yaml and in `check_tier1_manager_ok()`'s own fallback). Overridable per-run via `triapi dispatch --no-tier1` / the `TRIAPI_NO_TIER1` env var without editing this file. `jules_tester:` block (2026-08-16/17, same documentation style as the DeepSeek peak-hour block above) — config for the advisory, never-blocking Jules post-dispatch verification tier: `enabled`; `source` (the confirmed-live REST source resource name from `GET /sources`, e.g. `sources/github/owner/repo` — NOT the bare `owner/repo` form); `daily_task_limit` (15, free tier, confirmed by the absence of a Pro/Ultra indicator on this account); `poll_timeout_s`/`poll_interval_s` (900s/15s, sized from real live discovery sessions that took several minutes including plan-approval delay). Also documents, inline as a comment, the corrected `sourceContext.githubRepoContext.startingBranch` field path vs. the public docs' wrong `sourceContext.githubBranch` — see `scripts/jules_client.py` above for the live-verification details. `requirePlanApproval: false` is sent by `jules_client.create_session()`'s default, but whether it actually skips the "Awaiting Plan Approval" delay is **NOT confirmed live** — both real sessions created during planning (one via the CLI, one a throwaway REST discovery call) went through an observed "Awaiting Plan Approval"/`planApproved` activity before proceeding regardless, and neither was created with this exact flag set and watched to completion. A post-implementation dispatch run initially documented this as "confirmed live" in this file, which was wrong (a fabricated confirmation, caught and corrected 2026-08-17) — treat the flag's actual effect as an open question until a manual smoke test observes it directly, and budget the ~30-60s plan-approval delay into `poll_timeout_s` regardless of whether the flag turns out to skip it. **We do not trigger a real live Jules session as part of automated tests** — `tests/test_branch_features.py` and the rest of the automated suite mock `jules_client`/`budget_guard` wherever Jules is touched and never make a real network call to `jules.googleapis.com`. `jules_client.run_jules_test()`/`main()`'s actual end-to-end session-create-and-poll path is reserved for a manual, human-supervised smoke test (run by hand, with the real `google_jules_apikey` secret and a real GitHub source) — not part of `PYTHONPATH=. python3 -m unittest tests.test_branch_features -v`. `ARCHITECTURE.md` was refreshed on 2026-08-26 to describe the current 5-tier state (Tier 2=DeepSeek, Tier 3=agy/gemini-3.1-pro, Tier 4=local Ollama, Tier 5=librarian) replacing its previous stale 4-tier description.
- `tiers.yaml`'s `tier_1_planner` model swap (2026-08-28) — `tier_1_planner`'s model was swapped from `nvidia/nemotron-3-ultra-550b-a55b:free` to `dots-studio/dots-3-note-preview:free` (an already-approved free OpenRouter model, previously `tier_4_worker`'s model pre-Phase-33) after the Nemotron model repeatedly produced hallucinated planning output in one session: fully fabricated tool-call transcripts inventing nonexistent code/files, truncated responses, and degenerate self-repeating non-plans. Live-verified after the swap: `probe_models()` succeeds, a real `planner.plan_turn()` call returns a clean, coherent, non-hallucinated response, and the full regression suite passes (96 tests, OK).
- `resource_guard.yaml` — machine-specific list of systemd `--user` services paused for the duration of every `triapi dispatch` run and resumed afterward (Phase 12), so Tier 4's local Ollama gets the shared iGPU/RAM without contention. Not portable to another deployment; empty/missing file just disables the guard. `unload_other_ollama_models: true` (2026-08-17) — complementary, separate mechanism layered on top of `pause_services`: force-unloads any other Ollama-resident model via the API (`GET /api/ps` then `POST /api/generate` with `keep_alive: 0`) immediately before every `triapi dispatch`, so Tier 4's configured model gets the full shared iGPU/RAM budget. Defaults to `true` (also when the file or key is absent — the loader defaults on); set it to `false` to disable model-unloading while keeping the systemd pause list active.
- `secrets.example.yaml` — plaintext template documenting required secret keys (`deepseek_api_key`, `ollama_host`, `google_ai_studio_api_key`, `google_jules_apikey`), no real values, safe to commit.
- `secrets.enc.yaml` — sops/age-encrypted real secrets. **As of 2026-08-17, local-only and gitignored, NOT committed** (a full `git filter-repo` history purge removed the previously-committed ciphertext from every past commit — see `ARCHITECTURE.md`). Edit with `sops config/secrets.enc.yaml`; the file must be created locally (from `secrets.example.yaml`'s template, then `sops -e -i`) on any new machine, since it no longer ships with `git clone`.

## knowledge/
- `lessons.jsonl` — committed failure-pattern knowledge store (deliberately *not* under `logs/`, which is gitignored wholesale). One JSON object per line with schema `{id, date, category ("bug_fix"|"unresolved_pattern"), component, bug_description, what_went_wrong, fix_description, tags[]}`. Seeded from real historical TriAPI bugs; appended at runtime by `scripts/lessons.add_lesson()` (including auto-capture from `orchestrator.human_handoff()`). Consumed cheaply/locally by `select_relevant()` keyword overlap — no LLM call — and folded into tier edit prompts as a "## Known past mistakes..." do/don't block.
- `hivemind.md` — central repository of reusable, stripped-down code snippets with XML-wrapped `<triapi_snippet>` blocks. Parsed at runtime to search for patterns matching the task description and file extension, and injected into Tier 4's prompt as reference.
- `TECH_DEBT.md` — record of accumulated technical debt from judge rejections where the fix-forward build loop failed to compile, storing the file path, file content hash, and reason.

- `tiers.yaml`'s `tier_5_librarian:` block (2026-08-24, `fallback_agy` leg added 2026-08-26, **primary swapped from `ollama`/`mistral-small` to `agy`/`gemini-3.8-flash` at `effort: low` on 2026-08-27**) — the doc-update tier: `provider: agy`, `effort: low`, `models: {primary: gemini-3.8-flash, fallback_local: ollama_fallback, fallback_agy: default, fallback_openrouter: stealth/ox-alpha}`, `target_globs: ["*.md", "docs/**"]` (matched by `dispatcher.is_doc_target()`), `verify_command`, `max_attempts`. The primary swap fixed a systematic 600s timeout on every real doc-edit task: local `mistral-small` on this machine's AMD iGPU ran at only ~10-11 tok/s, so any real-sized target routinely exceeded `_HTTP_TIMEOUT` before falling through to the fallback; the same edit via `agy`/Gemini 3.7 Flash completed in ~4s in live verification. `scripts/librarian_escalate.py`'s `providers` list is config-driven for the primary slot (reads `tier_5_librarian.provider`/`effort`, not hardcoded). `escalation_rules.tier5_to_fallbacks` (`threshold: 2`, `chain: [fallback_local, fallback_agy, fallback_openrouter, log_and_notify]`) is otherwise unchanged — `fallback_agy` (Antigravity CLI, `gemini-3.1-pro`, effort high) sits between the two Ollama legs and OpenRouter, subscription-billed at $0 marginal cost, same as the rest of this chain: all-local/free-or-subscription, zero paid/metered-API calls anywhere in it (do not confuse this fallback slot with the new primary — different model, different effort, different purpose). `llm_client.execute_agy()` is the thin public wrapper this leg calls (delegates to `_call_agy_cli`, the same subprocess helper Tier 3 uses). The argv-too-long crash was fixed in commit 3cbdeba via a `_AGY_MAX_PROMPT_CHARS=100000` guard in `_call_agy_cli()` (`scripts/llm_client.py`) that raises a controlled `CalledProcessError` instead of letting `subprocess.run()` crash with an uncaught `OSError`, so the bug is resolved, not open. `scripts/doc_staleness.py`'s `should_skip_model_call()` false-negative bug (git-epoch skip firing on non-staleness tasks like plain appends/index updates) fixed 2026-08-28: leading `_STALENESS_QUESTION_PHRASES` gate requires a code-sync-staleness phrase before git skip logic runs, otherwise forcing a model call (covered by `tests/test_tier5_librarian.py`). The FRESH escape hatch's false-negative bug (model claims a doc is already accurate when it demonstrably isn't) is fixed as of commit bdf58a9 — `librarian_escalate.py`'s `run()` now runs a real caller-supplied `verify_cmd` against the file before trusting a FRESH claim, rejecting and falling through to the next provider if it contradicts. See `scripts/librarian_escalate.py` below for the runtime logic.

## scripts/
Full reference moved to [`docs/agents/20260825-100000-scripts-directory-reference.md`](docs/agents/20260825-100000-scripts-directory-reference.md) (2026-08-25 — see `docs/agents/index.json`) to keep this file under the 73,728-char ceiling. Covers every pipeline module: `secrets_loader.py`, `config_loader.py`, `llm_client.py`, `state.py`, `content_guard.py`, `edit_blocks.py`, `lessons.py`, `hivemind_util.py`, `critique.py`, `judge.py`, `self_fix.py`, `tier4_context.py`, `tier4_worker.py`, `tier3_escalate.py`, `tier1_escalate.py`, `tier2_escalate.py`, `budget_guard.py`, `jules_client.py`, `cost_report.py`, `orchestrator.py`, `agents_md_gate.py`, `planner.py`, `dispatcher.py`, `regression_guard.py`, `mock_patch_lint.py`, `tech_debt.py`, `git_ops.py`, `triapi.py`, `resource_guard.py`, `tri_logging.py`, `librarian_escalate.py`. (`gemini_fallback.py` deleted 2026-09-01 — see the reference file's own note.)

## tests/
- `test_tier5_librarian.py` (2026-08-24, updated 2026-08-26 for the `fallback_agy` leg) — regression tests for `scripts/librarian_escalate.py`/`dispatcher.is_doc_target()`/`llm_client.detect_email_like_content()`: config schema, glob truth table, email-detection, the success write path (edit-block apply + cost-log `billing: "local"`), the primary→fallback_local→fallback_agy→fallback_openrouter→log_and_notify escalation order (with an `execute_agy` mock sentinel asserted invoked only after `fallback_local` exhausts its threshold) with paid-tier (DeepSeek/Claude/Gemini) call sentinels proving they're never touched, chain-exhaustion handoff, workdir-boundary refusal, and the advisory no-change verdict. Split out from `tests/test_branch_features.py` for the same size-ceiling reason as `test_mock_patch_lint.py` below.
- `test_llm_client_http_timeout.py` (2026-08-26) — regression coverage for `scripts/llm_client.py`'s `_HTTP_TIMEOUT` constant (fixture/mock style, zero network calls): default value 600, `TRIAPI_HTTP_TIMEOUT` env-override via `importlib.reload`, and both `_call_openai_api()`/`_call_gemini_api()` proven to actually pass `timeout=_HTTP_TIMEOUT` to `requests.post` (the original bug shape, a hardcoded 300, being the thing this guards against). Split out per the same size-ceiling convention as the other dedicated test files above.
- `test_orchestrator_tier3_timeout_skip.py` (2026-08-26) — regression coverage proving a `scripts/llm_client.py` `subprocess.TimeoutExpired` from the `agy` CLI (Tier 3) is returned by `scripts/tier3_escalate.py` as `status: 'timeout'` and soft-escalates to Tier 2 (DeepSeek) in `scripts/orchestrator.py`'s `run_task()`, rather than raising `RuntimeError` or falling through to `human_handoff`. Fixture/mock style, zero network calls. Also covers (2026-08-29) a new `Tier3EscalateCalledProcessErrorTests` class proving a `subprocess.CalledProcessError` from `_call_agy_cli` returns `status: "fix_rejected"` (not error), the regression test for the crash-vs-soft-escalate fix in `scripts/tier3_escalate.py`.
- `test_llm_client_claude_cli_no_tools.py` (2026-08-29) — regression coverage for `scripts/llm_client.py`'s `_call_claude_cli()`: asserts `--tools ""` is always present in the built argv (with and without model/effort passed), the fix for a real bug where Tier 1's claude CLI call had no tool restriction and could edit a target repo directly instead of returning parseable SEARCH/REPLACE text.
- `test_mock_patch_lint.py` — regression tests for `scripts/mock_patch_lint.py` (the mock-patch target/import-binding-mismatch linter above): covers wrong vs. correct patch targets and CLI exit codes, using temporary fixture repos rather than the repo's own files. Split out from `tests/test_branch_features.py`, which had grown well past the size ceiling for further extension.
- `test_dispatcher_test_context_guard.py` — regression tests for `scripts/dispatcher.py`'s test-file context grounding guard (`_find_anchor_test_file`/`_apply_test_context_guard`): covers companion-script and anchor-test-file auto-inclusion, missing-anchor rejection, and no-fabrication/no-duplication behavior, using temporary fixture repos rather than the repo's own files. Split out as a new file per the "split out, don't keep extending `test_branch_features.py`" convention already used for `test_mock_patch_lint.py`.
- `test_import_order_guard.py` — regression tests for `scripts/dispatcher.py`'s module import-order guard (`_enforce_module_import_order`/`_extract_imported_modules`/`_SCRIPTS_TARGET_RE`/`_IMPORT_RE`): covers both `from scripts import X` and `import scripts.X` extraction, the exact 2026-08-18 incident shape (importer before creator gets reordered), no-op when already ordered or the module pre-exists on disk, git items skipped, and unresolvable circular imports returning an error string, using temporary fixture repos rather than the repo's own files. Split out as a new file per the same convention as `test_mock_patch_lint.py`/`test_dispatcher_test_context_guard.py`.
- `test_plan_phase_split_and_completion_guard.py` — regression tests for the 2026-08-19 plan-completion integrity bug: covers `scripts/dispatcher.py`'s `_split_plan_by_phase` now recognizing numbered `N. Phase ...` top-level markers (not just ATX headers) and `scripts/agents_md_gate.py`'s `mark_plan_complete` now refusing to check off AGENTS.md boxes when the breakdown captured fewer items than the block declares (run `20260819-063339-9d23c7`), using temporary fixture repos rather than the repo's own files. Split out as a new file per the same convention as `test_mock_patch_lint.py`/`test_dispatcher_test_context_guard.py`/`test_import_order_guard.py`.
- `test_ollama_service_lifecycle.py` — regression coverage for the `cmd_dispatch` Ollama snapshot/restore wiring (mocking `scripts.triapi.resource_guard.snapshot_ollama_state`/`restore_ollama_state` at their use site).
- `test_file_size_ceiling_and_oversize_escalation.py` — regression coverage for `scripts/dispatcher.py`'s `_enforce_file_size_ceiling` (rejects a plan item targeting an existing over-ceiling file, ignores small/nonexistent targets) and `scripts/tier4_worker.py`'s `_tier4_fail(..., is_oversize_failure=...)` 1-attempt escalation shortcut for timeout and truncated-response failures vs. the normal 2-attempt threshold for ordinary build failures. Fixture-repo pattern, split out per the same convention as the other dedicated test files above.
- `test_llm_client_sanitize.py` (2026-08-25) — regression coverage for `llm_client._sanitize_for_openrouter_content_filter()`'s phone/IP cases: a phone-shaped and an IPv4-shaped input are each changed by the sanitizer, while a TriAPI `run_id`/timestamp-shaped input, a hex hash, and a 3-part version string are all left untouched. Split out per the same file-size convention as the other dedicated test files.
- `test_dispatcher_peak_hours.py` (2026-08-25) — regression test asserting `scripts/dispatcher._is_deepseek_peak_hours()` purely delegates to `budget_guard.check_tier3_peak_hours_ok()` rather than any hardcoded weekend/peak-window logic of its own: `ok=True` (e.g. weekend off-peak) yields `False`, `ok=False` (inside a peak window) yields `True`, and the mock is asserted called. Created as a new file rather than appended to `tests/test_branch_features.py`, which was at 73,571 chars against the 73,728-char Tier 4 ceiling with no headroom left — same "split out, don't keep extending" convention as the other dedicated test files above.
- `test_design_judge_fix_forward_status.py` (2026-08-25) — regression coverage for the false-success bugfix in `scripts/dispatcher.py`'s `_run_design_judge()`/`handle_fix_forward()` (found live in run `20260825-092344-5ff4a7`: an item was recorded `status: success` despite the target file being byte-for-byte unchanged, because a design-judge rejection whose fix-forward attempt also failed was silently discarded). Fixture-repo/tempdir pattern, zero real LLM/network calls, mocks `judge.evaluate_design`/`tier3_escalate.escalate`/`run_build`/`_git_diff_for` at their `scripts.dispatcher`-local use sites: (a) judge approves → status stays `success`, `handle_fix_forward` not called; (b) judge rejects but fix-forward succeeds (Tier 3 applies + rebuild passes) → status stays `success`; (c) judge rejects and fix-forward fails (Tier 3 returns non-`fix_applied`) → status is downgraded to `build_failed`/`resolved_by: None`, matching the pipeline's existing `mock_patch_lint`-override convention, and the file is confirmed reverted to its original bytes. Split out per the same file-size convention as the other dedicated test files above.

## logs/
- `state/` — per-task JSON state files (gitignored contents, dir kept via `.gitkeep`).
- `cost_log.jsonl` — per-call cost/usage log across all paid/metered tiers, one JSON line per call (gitignored).
- `gemini_usage.jsonl` — Tier 2 call timestamps, used by `budget_guard.check_tier2_ok()` to enforce free-tier RPM/RPD limits (gitignored).
- `escalations.jsonl`, `escalation_<task_id>.md` — final human-handoff records, written only when Tier 4→3→1→2 all fail to resolve a task (gitignored).
- `triapi.log` — centralized debug log from `tri_logging.py`, on by default; `tail -f` it live (gitignored).
- `runs/<run_id>.json` — persisted plan/dispatch state for `triapi`, updated after every item so a run survives SSH disconnects; `runs/<run_id>.log` is the raw output when dispatched with `--background` (gitignored).

## samples/
- `broken_build/` — fixture C++ project: `main.cpp` has a genuine compile error (copying a `std::vector<std::unique_ptr<Widget>>`, illegal since `unique_ptr` isn't copyable) plus `CMakeLists.txt`. Used for end-to-end pipeline verification (Phase 6) — a full production-config `orchestrator.py` run resolved it correctly at Tier 4 alone, $0 cost. `build/` (CMake output) is gitignored, regenerated by running the smoke test in `README.md`.


## Historical, completed `triapi:plan` blocks (2026-08-25 through 2026-08-27)

**Historical, completed `triapi:plan` blocks (2026-08-25 through 2026-08-27,
five real runs) were moved to
[`docs/agents/20260828-044229-agents-md-historical-plan-blocks-archive.md`](docs/agents/20260828-044229-agents-md-historical-plan-blocks-archive.md)
on 2026-08-28 to bring this file back under the repo's 73,728-char ceiling —
see `docs/agents/index.json`. A separate, unrelated ~71,600-char fully
hallucinated block (`run_id=20260827-130810-27dd58` — an overloaded/
malfunctioning model invented a nonexistent
`scripts.librarian_escalate.escalate_librarian()` function and fake
`config/tiers.yaml` values; never approved, never dispatched) was deleted
outright, not archived. Only the single most-recent `triapi:plan` block
below is still tracked inline — that's the one
`scripts/agents_md_gate.py`'s `find_incomplete_plan()` actually checks to
gate a new `triapi plan` call.**

<!-- triapi:plan run_id=20260827-132236-806da1 start -->
## TriAPI Plan (run 20260827-132236-806da1, appended 2026-08-27)

# TriAPI — Execution Plan: tier_5_librarian primary swap to agy, live verification, resume stuck run, doc updates

**Grounding notes from reading the live repo (not assumptions):**
- `scripts/librarian_escalate.py`'s `providers` list (lines 192–197) currently **hardcodes** `"name": "ollama"` for the primary slot and never reads `tier_5_librarian.provider` (that top-level config key exists today but is dead/unused code) and never passes `effort` to `execute_agy()` (which already accepts an `effort` kwarg, confirmed at `scripts/llm_client.py:148-162`). Editing `config/tiers.yaml` alone would **not** actually route the primary attempt through `agy` — a code change is required first. This corrects the assumption in the prior (2nd) planning attempt that "no code change" was needed.
- `git status` currently shows uncommitted edits to `AGENTS.md`, `config/tiers.yaml`, the active carryover file, `knowledge/hivemind.md`, `scripts/dispatcher.py`, and two test files. The `config/tiers.yaml` diff is unrelated to this task (a `critique.applies_to_tiers` fix already in progress) — leave it as-is, don't revert it.
- The stuck run is `20260827-100542-afee9f` (`status: stopped_on_failure`), a real, previously-approved dispatch. `triapi` is an installed binary (`~/.local/bin/triapi`), so `triapi status <id>` / `triapi dispatch <id>` are used directly, exactly as documented in `README.md`.
- The active carryover file is resolved dynamically via `docs/carryover/index.json`'s `.active` key (currently `20260826-193000-tier3-timeout-softescalate-architecture-refresh-agentsmd-routing-bug.md`) — resolved at execution time, not hardcoded, since it may change before this plan runs.
- `AGENTS.md` is currently 147,933 chars — already well past this repo's 73,728-char ceiling (a pre-existing condition, out of this plan's scope). Doc-edit steps below keep their `--description` maximally narrow (mirrors what worked last session) both for speed and to avoid growing this further than necessary.
- `librarian_escalate.py`'s only supported interface is its CLI (`argparse`-based `main()`, confirmed at line 358) — no plan step below invokes it as a Python function.

---

## Phase 1 — Make the primary provider configurable, then swap it to agy/gemini-3.7-flash (effort low)

- [x] **`scripts/librarian_escalate.py`** — Wire the primary slot's provider/effort to come from config instead of being hardcoded, without touching the `fallback_local`/`fallback_agy`/`fallback_openrouter` legs' existing behavior:
  - In `run()`, change the `providers` list (currently lines 192–197):
    ```python
    providers = [
        {"name": "ollama", "model": model_override or models_cfg.get("primary", "mistral-small:latest")},
        {"name": "ollama", "model": model_override or fallback_local_block.get("models", {}).get("default")},
        {"name": "agy", "model": models_cfg.get("fallback_agy")},
        {"name": "openrouter", "model": model_override or models_cfg.get("fallback_openrouter")},
    ]
    ```
    to:
    ```python
    providers = [
        {
            "name": lib_config.get("provider", "ollama"),
            "model": model_override or models_cfg.get("primary", "mistral-small:latest"),
            "effort": lib_config.get("effort"),
        },
        {"name": "ollama", "model": model_override or fallback_local_block.get("models", {}).get("default")},
        {"name": "agy", "model": models_cfg.get("fallback_agy")},
        {"name": "openrouter", "model": model_override or models_cfg.get("fallback_openrouter")},
    ]
    ```
  - In the `if provider == "agy":` branch (currently lines 226–231), thread the effort through:
    ```python
    response_text, billing_type, input_tokens, output_tokens = llm_client.execute_agy(
        model=model,
        prompt=prompt,
        system_prompt="",
        effort=provider_info.get("effort"),
    )
    ```
  - Update the stale comment above the `providers` list (currently "primary (Ollama mistral-small) -> fallback_local (Ollama...) -> fallback_agy (agy CLI) -> fallback_openrouter...") to describe the provider as config-driven rather than naming a fixed model.
  - This is backward-compatible: when `tier_5_librarian.provider` is absent or `"ollama"` and `effort` is absent, behavior is byte-identical to today (existing tests must still pass unmodified).
  - Verify: `python3 -m py_compile scripts/librarian_escalate.py`

- [x] **`config/tiers.yaml`** — Pin the exact live `agy` model identifier, then edit the `tier_5_librarian` block. First confirm the real CLI shape rather than trusting the unverified assumption from prior planning attempts:
  ```bash
  agy models
  agy -p "reply with exactly OK" --model gemini-3.7-flash --effort low --dangerously-skip-permissions --output-format json
  ```
  Per the approved goal, mirror `tier_3_debugger`'s exact shape (`provider: agy`, bare model id in `models.default`/`models.primary`, separate top-level `effort:` field — not baked into the model string, the same pattern that already works for `gemini-3.1-pro`/`effort: high`). Use the bare id `gemini-3.7-flash` with `effort: low` **only if** the smoke command above returns `"status": "SUCCESS"`; if it instead requires a suffixed id (e.g. `gemini-3.7-flash-low`) with no `--effort` flag, use that exact id instead and note the deviation explicitly in Phase 4's doc-update step.
  Change the `tier_5_librarian` block (currently lines 97–109) from:
  ```yaml
  tier_5_librarian:
    enabled: true
    role: doc_librarian
    automatable: true
    provider: ollama
    models:
      primary: "mistral-small:latest"
      fallback_local: ollama_fallback
      fallback_openrouter: "nvidia/nemotron-3-ultra-550b-a55b:free"
      fallback_agy: default
    target_globs: ["*.md", "docs/**"]
    verify_command: null
    max_attempts: 2
  ```
  to:
  ```yaml
  tier_5_librarian:
    enabled: true
    role: doc_librarian
    automatable: true
    provider: agy
    effort: low
    models:
      primary: "gemini-3.7-flash"   # or the confirmed-live suffixed id if the bare form is rejected
      fallback_local: ollama_fallback
      fallback_openrouter: "nvidia/nemotron-3-ultra-550b-a55b:free"
      fallback_agy: default
    target_globs: ["*.md", "docs/**"]
    verify_command: null
    max_attempts: 2
  ```
  (Leave `fallback_local`, `fallback_agy`, `fallback_openrouter`, `ollama_fallback`, and `escalation_rules.tier5_to_fallbacks` untouched — only the primary changes.)
  Verify: `python3 -c "from scripts.config_loader import load_tiers; c = load_tiers()['tier_5_librarian']; print(c['provider'], c['effort'], c['models']['primary'])"` — expect `agy low gemini-3.7-flash` (or the confirmed alternate id).

- [x] **`tests/test_tier5_librarian.py`** — Add a regression test proving the new primary path is wired correctly and the paid ladder is still never touched. Add a new test method (e.g. `test_primary_provider_swaps_to_agy_with_effort_when_configured`) that:
  - Builds a config dict like `_tier5_config()` but with `"provider": "agy", "effort": "low", "models": {..., "primary": "gemini-3.7-flash"}`.
  - Mocks `librarian_escalate.llm_client.execute_agy` to return a valid SEARCH/REPLACE response on the first call, and asserts it was called with `model="gemini-3.7-flash"` and `effort="low"`.
  - Mocks `librarian_escalate.llm_client.execute_llm` (the ollama/openrouter path) and asserts it is **never** called (primary succeeds on the first attempt, `fallback_local` is never reached).
  - Reuses the existing `paid_ladder_sentinel` pattern (mock `_call_claude_cli`, `_call_gemini_api`, `tier1_escalate.escalate`, `tier2_escalate.escalate`, `tier3_escalate.escalate`) and asserts none are called.
  - Also confirm the existing `test_escalation_order_is_primary_then_fallback_local_then_agy_then_openrouter_then_log_and_notify` test (its `_tier5_config()` fixture still uses `"provider": "ollama"`) still passes unmodified, proving the default/backward-compat path is untouched.
  Verify: `wc -c tests/test_tier5_librarian.py` (confirm still comfortably under 73,728 chars) then `PYTHONPATH=. python3 -m unittest tests.test_tier5_librarian -v`

- [x] **Full regression suite** — Verify: `PYTHONPATH=. python3 -m unittest tests.test_branch_features tests.test_tier5_librarian -v` — expect all tests passing, zero `SKIPPED` (per this repo's known "fake skip-based tests" gotcha — run with `-v` and read every line, don't trust a bare summary).

---

## Phase 2 — Live end-to-end verification against the real librarian CLI

- [x] **`docs/_scratch_tier5_verify.md`** (throwaway, deleted at the end of this step) — Create a disposable scratch doc, dispatch it through the real `librarian_escalate.py` CLI using the now-agy primary, and confirm it completes correctly and fast (well under the 600s `_HTTP_TIMEOUT`), not just that config syntax is valid:
  ```bash
  mkdir -p docs
  printf '# Scratch\n\nThis library is at version 1.0.0.\n' > docs/_scratch_tier5_verify.md
  time python3 scripts/librarian_escalate.py \
    --task-id tier5-primary-verify \
    --description "Update the version number mentioned in this scratch file from 1.0.0 to 2.0.0. This is a disposable live-verification file for the tier_5_librarian primary agy/gemini-3.7-flash swap and will be deleted immediately after this check regardless of outcome." \
    --target docs/_scratch_tier5_verify.md \
    --workdir . \
    --verify-cmd "grep -q 2.0.0 docs/_scratch_tier5_verify.md"
  ```
  Verify:
  - Command output JSON has `"status": "success"` and `"resolved_by": "tier_5"`.
  - The `time` wall-clock is well under 600s (expect low tens of seconds given a fast model, not the 600s timeout the slow path always hit).
  - `tail -1 logs/cost_log.jsonl` shows `"tier": "librarian"`, `"billing": "subscription"`, and a model field matching the id confirmed in Phase 1 — proving the primary attempt actually used `agy`, not a silent fall-through to `fallback_local`.
  - Clean up regardless of outcome: `rm -f docs/_scratch_tier5_verify.md`

---

## Phase 3 — Resume the stuck run

- [x] **`logs/runs/20260827-100542-afee9f.json`** — Check the run's current exact state before touching it:
  ```bash
  triapi status 20260827-100542-afee9f
  ```
  Read the printed state (which item is stuck, its `status` field) before proceeding — don't assume it's still exactly where the carryover/prompt describes it.

- [x] **`logs/runs/20260827-100542-afee9f.json`** — Resume the run now that `tier_5_librarian`'s primary is fast, so its stuck `AGENTS.md` doc-edit item can finally complete instead of repeatedly hitting the 600s timeout → false-`FRESH` pattern:
  ```bash
  triapi dispatch 20260827-100542-afee9f
  ```
  Verify: `triapi status 20260827-100542-afee9f` reports `"status": "completed"` (or otherwise inspect the printed final status/`resolved_by` for the previously-stuck item); if it lands on `human_handoff` instead, stop here and report the exact failure rather than proceeding to Phase 4 as if it succeeded.

---

## Phase 4 — Correct the record, via the real librarian CLI only

- [x] **Active carryover file** (path resolved at execution time, not hardcoded) — Append a short, factual note via the real `librarian_escalate.py` CLI:
  ```bash
  ACTIVE_FILE="docs/carryover/$(jq -r '.active' docs/carryover/index.json)"
  python3 scripts/librarian_escalate.py \
    --task-id tier5-primary-swap-carryover-update \
    --description "Append a short dated note (do not remove or rewrite any existing content, only append): (1) tier_5_librarian's primary model changed from the slow local ollama/mistral-small (systematically timing out at 600s on real doc edits, ~10-11 tok/s on this iGPU) to agy/gemini-3.7-flash at effort low, verified live end-to-end well under the timeout in this session's Phase 2 check; the local (qwen2.5-coder) fallback, agy fallback (gemini-3.1-pro high), and OpenRouter fallback legs are unchanged. (2) Flag a separate still-open bug for next priority: librarian_escalate.py's FRESH escape hatch (librarian_escalate.py:277-280) has produced at least 3 confirmed false-negative FRESH judgments (AGENTS.md x2, ARCHITECTURE.md x1) where the target file demonstrably still needed the described edit -- not fixed by this change, needs its own investigation." \
    --target "$ACTIVE_FILE" \
    --workdir . \
    --verify-cmd "grep -qi 'gemini-3.7-flash' \"$ACTIVE_FILE\""
  ```
  Verify: `git diff -- "$ACTIVE_FILE" | head -60` — read the actual diff (per this repo's "verify, don't trust status" rule) and confirm it's a real, coherent appended note, not a hallucinated or truncated fragment; also `grep -n "FRESH" "$ACTIVE_FILE"` confirms point (2) landed.

- [x] **`AGENTS.md`** — Update its own index entry via the same CLI (never a hand `Edit`/`Write`):
  ```bash
  python3 scripts/librarian_escalate.py \
    --task-id tier5-primary-swap-agents-index-update \
    --description "In this file's config/ section, in the tier_5_librarian bullet, append 2-3 sentences noting: tier_5_librarian's primary model changed from ollama/mistral-small to agy/gemini-3.7-flash at effort low on 2026-08-27, fixing a systematic 600s timeout on doc-edit tasks; the local/agy-fallback/openrouter fallback chain is otherwise unchanged. Do not rewrite or restructure any other part of this file." \
    --target AGENTS.md \
    --workdir . \
    --verify-cmd "grep -qi 'gemini-3.7-flash' AGENTS.md"
  ```
  Verify: `git diff -- AGENTS.md | head -60` (confirm a small, correctly-scoped real diff) and `wc -c AGENTS.md` (confirm the edit didn't balloon the file further than the note itself warrants — it's already over this repo's ceiling, a pre-existing condition out of this plan's scope, but shouldn't be made worse by this step).
<!-- triapi:plan run_id=20260827-132236-806da1 end -->





<!-- triapi:plan run_id=20260827-222943-2c134b start -->
## TriAPI Plan (run 20260827-222943-2c134b, appended 2026-08-28)

Now I have full grounding. Here's the plan:

## Phase 1 — Fix `should_skip_model_call()` false-negative in `scripts/doc_staleness.py`
- [x] In `scripts/doc_staleness.py`, add a new module-level constant `_STALENESS_QUESTION_PHRASES` (a plain Python list of lowercase strings) placed after the existing `_is_doc_target = _get_is_doc_target()` line (~line 38) and before `should_skip_model_call()`. Seed it with exactly: `["stale", "out of date", "outdated", "up to date", "up-to-date", "reflect the current state", "sync with", "keep in sync", "no longer accurate", "is this doc accurate"]`. This is a single editable list per the repo's "everything configurable, no hardcoding" convention — no other literals duplicating these phrases anywhere else in the file.
- [x] In `should_skip_model_call(doc_path, workdir, task_description)`, add a new leading check evaluated first, inside the existing `try:` block, before step "(1) Explicit mention override" (i.e. immediately after `task_lower = task_description.lower()` is computed — move that assignment up above the new check since the new check needs it too): `if not any(phrase in task_lower for phrase in _STALENESS_QUESTION_PHRASES): return (False, "task description is not a code-sync staleness check -- skipping the fast-path, forcing a real edit attempt")`. This must run before any `subprocess.run` call (git work-tree check, clean-tree check, doc-commit check, epoch scan) so the common non-staleness case pays no git subprocess overhead. Do not alter any of the existing 5-step logic (explicit-mention override, work-tree check, clean-tree check, doc-has-commit check, epoch comparison) — it must still run exactly as before whenever the new leading check passes (i.e., the description does contain a staleness phrase).
- [x] Verify syntax only (no tests yet): `python3 -m py_compile scripts/doc_staleness.py`

## Phase 2 — Update `tests/test_tier5_librarian.py` to match the new gate
- [x] In `tests/test_tier5_librarian.py`, update the descriptions used by the 7 existing staleness-precheck tests (lines ~471–672, all currently passing `"review documentation"` — which contains none of the new staleness phrases) so each test still exercises the code path its name and docstring claim to exercise, since under the new gate a description without a staleness phrase now short-circuits to `(False, ...)` *before* any git subprocess call:
  - `test_staleness_precheck_skips_when_doc_newer_than_code` (line 471): change description from `"review documentation"` to `"is the documentation stale relative to the code"` (contains `"stale"`, does not mention `GUIDE`/`docs/GUIDE.md`) so it still reaches the existing epoch-comparison logic and still asserts `execute_llm.assert_not_called()` / `result.get("via") == "staleness_precheck"`.
  - `test_staleness_precheck_calls_model_when_dirty_tree` (line 494): change description to `"is the documentation up to date"` (contains `"up to date"`, no filename) so it still reaches the clean-tree check and still asserts `execute_llm.assert_called_once()`.
  - `test_staleness_precheck_calls_model_when_code_committed_after_doc` (line 520): change description to `"is the documentation up to date with the code"` so it still reaches the epoch-comparison step; keep `execute_llm.assert_called_once()`.
  - `test_staleness_precheck_calls_model_when_doc_untracked` (line 546): change description to `"is the documentation out of date"` so it still reaches the doc-has-commit check; keep `execute_llm.assert_called_once()`.
  - `test_staleness_precheck_explicit_mention_force_calls_by_relpath` (line 573): change description from `"update docs/GUIDE.md"` to `"is docs/GUIDE.md stale or out of date"` — keeps the relpath mention (`docs/GUIDE.md`) AND adds a staleness phrase (`"stale"`) so it still reaches step (1)'s explicit-mention override inside the existing logic; keep `execute_llm.assert_called_once()`.
  - `test_staleness_precheck_explicit_mention_force_calls_by_basename` (line 598): change description from `"update GUIDE.md"` to `"is GUIDE.md up to date"` (basename + staleness phrase); keep `execute_llm.assert_called_once()`.
  - `test_staleness_precheck_explicit_mention_force_calls_by_stem` (line 622): change description from `"update GUIDE to be current"` to `"is GUIDE stale"` (stem + staleness phrase); keep `execute_llm.assert_called_once()`.
  - `test_staleness_precheck_fail_open_when_subprocess_raises` (line 646): change description to `"is the documentation up to date with the code"` (staleness phrase, no filename) so it still reaches the patched, exception-raising `scripts.doc_staleness.subprocess.run` and still asserts `execute_llm.assert_called_once()` (fail-open behavior).
- [x] In the same file, add a new test method `test_staleness_precheck_forces_call_for_non_staleness_description_even_when_fresh` immediately after `test_staleness_precheck_skips_when_doc_newer_than_code` (~line 493), reproducing the exact false-negative shape from this session: reuse the `_init_git_repo`/`_commit_file` helpers to commit `src/main.py` then `docs/GUIDE.md` after it (doc genuinely newer/fresh, clean tree — the same fixture shape that previously produced a false FRESH), but call `librarian_escalate.run(...)` with a plain, non-staleness description such as `"append a note recording that X changed"` (no phrase from `_STALENESS_QUESTION_PHRASES`, no mention of `GUIDE`/`docs/GUIDE.md`). Mock `execute_llm` to return a normal success tuple (mirror the pattern used by `test_staleness_precheck_calls_model_when_dirty_tree`, e.g. `return_value=('FRESH\n', "ollama", 4, 2)`) and assert `execute_llm.assert_called_once()` — proving the model is now always invoked for a plain append/update-index task regardless of git freshness.
- [x] In the same file, add a new test method `test_staleness_precheck_skips_only_with_staleness_phrase_and_genuinely_fresh_doc` immediately after the new test above, as the explicit (b)-case regression: same fixture as the renamed `test_staleness_precheck_skips_when_doc_newer_than_code` (doc committed after code, clean tree) with a description containing a staleness phrase and no filename mention (e.g. `"is this doc out of date"`), asserting `execute_llm.assert_not_called()` and `result.get("via") == "staleness_precheck"` — proving the existing skip logic still works unchanged when a genuine staleness question is asked.
- [x] Also add a small direct-unit-level test (not going through `librarian_escalate.run`) named `test_should_skip_model_call_returns_false_immediately_for_non_staleness_description` that imports `scripts.doc_staleness` directly and calls `doc_staleness.should_skip_model_call(doc_path, workdir, "append this note to the index")` against a `workdir` that is *not* a git repo at all (e.g. a bare `tempfile.TemporaryDirectory()`), asserting the return is exactly `(False, "task description is not a code-sync staleness check -- skipping the fast-path, forcing a real edit attempt")` — proving the new leading check short-circuits before the git work-tree check would otherwise fail with a different reason string.
- [x] Verify syntax: `python3 -m py_compile tests/test_tier5_librarian.py`

## Phase 3 — Run the full regression suite and confirm zero failures
- [x] From the repo root, run: `PYTHONPATH=. python3 -m unittest tests.test_branch_features tests.test_tier5_librarian -v 2>&1 | tail -40` and confirm the tail shows `OK` with no `FAIL`/`ERROR`, and manually scan the full (non-tailed) output for any `SKIPPED` lines masking a weakened assertion (per this repo's known "fake skip-based tests" hazard) — rerun the same command without `| tail -40` first if anything is ambiguous: `PYTHONPATH=. python3 -m unittest tests.test_branch_features tests.test_tier5_librarian -v 2>&1 | grep -i "skip\|fail\|error"`.
- [x] If any test fails, fix the root cause in `scripts/doc_staleness.py` or the corresponding test in `tests/test_tier5_librarian.py` (never weaken an assertion to force a pass) and rerun the same command until clean.

## Phase 4 — Update docs via the librarian pipeline (not hand-edited) and resolve the carryover queue item
- [x] Update `AGENTS.md`'s `tier_5_librarian` bullet (the block in the `knowledge/` section documenting `tiers.yaml`'s `tier_5_librarian:` and `scripts/librarian_escalate.py`) by invoking the librarian CLI directly — do not use Edit/Write on `AGENTS.md`: `PYTHONPATH=. python3 scripts/librarian_escalate.py --task-id doc-staleness-fix-agents-md --description "Note that scripts/doc_staleness.py's should_skip_model_call() false-negative bug (queue item 3, git-epoch skip firing on non-staleness tasks like plain appends/index updates) is fixed: a new leading gate (_STALENESS_QUESTION_PHRASES module constant) now requires the task description to contain a code-sync-staleness phrase before the existing 5-step git-based skip logic runs at all; otherwise it always forces a real model call." --target AGENTS.md --workdir . --verify-cmd "python3 -m py_compile scripts/doc_staleness.py"`.
- [x] Mark queue item 3 RESOLVED in the active carryover file by invoking the same librarian CLI (not hand-edited) against the file path resolved via `jq -r '.active' docs/carryover/index.json` at execution time: run `ACTIVE=$(jq -r '.active' docs/carryover/index.json)` then `PYTHONPATH=. python3 scripts/librarian_escalate.py --task-id doc-staleness-fix-carryover --description "Mark queue item 3 (librarian_escalate.py's staleness_precheck false-negative FRESH bug) RESOLVED: fixed in scripts/doc_staleness.py via a new _STALENESS_QUESTION_PHRASES leading gate in should_skip_model_call(), covered by new regression tests in tests/test_tier5_librarian.py, full suite green." --target "docs/carryover/$(basename "$ACTIVE")" --workdir . --verify-cmd "PYTHONPATH=. python3 -m unittest tests.test_branch_features tests.test_tier5_librarian -v"`.
- [x] Confirm both doc updates actually landed (per this repo's "verify, don't trust status" convention): `git diff --stat -- AGENTS.md "docs/carryover/*.md"` and visually confirm non-empty diffs in both files before considering this phase done.
<!-- triapi:plan run_id=20260827-222943-2c134b end -->


<!-- triapi:plan run_id=20260827-234324-b88ea5 start -->
## TriAPI Plan (run 20260827-234324-b88ea5, appended 2026-08-28)

## Phase 1 — Add `_resolve_dynamic_target` helper to `scripts/dispatcher.py`

- [ ] In `scripts/dispatcher.py`, add a new module-level function `_resolve_dynamic_target(target: str, project_dir: str) -> str` placed near `_normalize_build_cmd` (currently defined at ~line 1009). Behavior: (a) if `target` contains none of the substrings `'$('`, `` '`' ``, or `'${'`, return `target` unchanged immediately with zero subprocess calls; (b) otherwise run `subprocess.run(["bash", "-c", f'printf %s "{target}"'], cwd=project_dir, capture_output=True, text=True, timeout=30)` — if `returncode == 0`, return `result.stdout.strip()`; on any nonzero returncode, `subprocess.TimeoutExpired`, or other exception, call `log.warning(...)` (matching this module's existing `log.warning("[%s] ...", ...)` style, e.g. `log.warning("Dynamic target expansion failed for %r: %s", target, e)`) and return the original, unexpanded `target` string unchanged — never raise, never return an empty/garbage path. Use the module's existing `log` logger (from `scripts.tri_logging.get_logger("dispatcher")`) and `subprocess`/`Path` imports already present at the top of the file — no new imports needed.
- [ ] Verify: `python3 -m py_compile scripts/dispatcher.py`

## Phase 2 — Wire the resolved target into `dispatch()`'s per-item loop

- [ ] In `scripts/dispatcher.py`'s `dispatch()` function, immediately after the line `task_id = f"{state['run_id']}-p{pi}-i{ii}"` (~line 1231, inside the `for pi, phase in enumerate(phases): for ii, item in enumerate(phase["items"]):` loop), add `resolved_target = _resolve_dynamic_target(item["target"], state["project_dir"])`. Note `item.get("target")`/`"git" in item`/`item.get("verify_only")` items may not have a `"target"` key at all — guard by only computing `resolved_target` when `"target" in item` (or compute unconditionally but only if `item.get("target")` is truthy, falling back to `None`), so a git-only item with no `target` key doesn't raise a `KeyError`.
- [ ] Replace every subsequent use of `item["target"]` within that same loop iteration with `resolved_target`, specifically: the `is_doc_target(item["target"], tier_5.get("target_globs", []))` call (~line 1273) → `is_doc_target(resolved_target, tier_5.get("target_globs", []))`; the `librarian_escalate.run(... target=item["target"], ...)` kwarg (~line 1280-1285) → `target=resolved_target`; the `run_task(... target=item["target"], ...)` kwarg (~line 1290-1298) → `target=resolved_target`; the `regression_guard.hash_file(Path(state["project_dir"]) / item["target"])` call (further down, content_hash computation) → `Path(state["project_dir"]) / resolved_target`; the `_is_test_target(item["target"])` check → `_is_test_target(resolved_target)`; the `mock_patch_lint.find_issues(Path(state["project_dir"]) / item["target"], ...)` call → `Path(state["project_dir"]) / resolved_target`; and the final bookkeeping line `entry["target"] = item["target"]` → `entry["target"] = resolved_target`. Do NOT change `item["description"]`, `build_cmd`'s own existing `_normalize_build_cmd` handling, the `_dispatch_git_item(...)` call, or any other logic in the function.
- [ ] Verify: `python3 -m py_compile scripts/dispatcher.py`

## Phase 3 — Regression tests for the new helper and its integration

- [ ] Create `tests/test_dispatcher_dynamic_target_resolution.py` following the fixture/tempdir pattern of `tests/test_dispatcher_test_context_guard.py` (read that file first for exact style: `unittest.TestCase`, `tempfile.TemporaryDirectory()` in `setUp`, `Path`-based fixture helpers, `tearDown` cleanup). Import `_resolve_dynamic_target` (and `dispatch` for the integration test) from `scripts.dispatcher`. Include these test methods:
  - [ ] `test_resolve_dynamic_target_passthrough_no_subprocess`: a target string with no `$(`, `` ` ``, or `${` (e.g. `"docs/carryover/plan.md"`) is passed to `_resolve_dynamic_target`; patch `subprocess.run` in `scripts.dispatcher` with `unittest.mock.patch` and assert it is `not called`, and assert the return value equals the input unchanged.
  - [ ] `test_resolve_dynamic_target_expands_real_shell_expression`: create a temp file under the fixture repo root (e.g. `docs/carryover/index.json` containing `{"active": "docs/carryover/20260827-foo.md"}`), build a target string `'docs/carryover/$(jq -r ".active" docs/carryover/index.json)'`, call `_resolve_dynamic_target(target, str(repo_root))`, and assert the result equals `"docs/carryover/20260827-foo.md"`. (If `jq` may not be installed in CI, use a simpler shell builtin like `` `echo foo` `` or `$(cat somefile)` instead of `jq` to keep the test hermetic — pick whichever avoids an extra binary dependency while still exercising real `$(...)` shell expansion via `bash -c`.)
  - [ ] `test_resolve_dynamic_target_falls_back_on_subprocess_failure`: patch `subprocess.run` in `scripts.dispatcher` to raise (e.g. `side_effect=OSError("boom")`) or return a `Mock(returncode=1, stdout="", stderr="err")`, call `_resolve_dynamic_target` with a target containing `$(...)`, and assert the return value equals the original unexpanded target string unchanged, and that no exception propagates.
  - [ ] `test_dispatch_uses_resolved_target_for_doc_item`: integration-level test — build a minimal `state` dict (task/run scaffolding matching what `dispatch()` expects: `run_id`, `project_dir` pointing at the temp fixture repo, `breakdown.phases` with one phase containing one item whose `target` is a `$(...)` expression that resolves (via a real fixture file, same technique as the expansion test) to a path matching `tier_5_librarian`'s `target_globs` (e.g. resolves to `docs/carryover/foo.md`), `results: []`). Patch `scripts.dispatcher.load_tiers` (or the config it reads) so `tier_5_librarian.enabled` is `True` and `target_globs` includes `*.md`/`docs/**`. Patch `scripts.dispatcher.librarian_escalate.run` (or `from scripts import librarian_escalate` reference used in `dispatch()`) to a `Mock` capturing its call kwargs and returning a well-formed success result dict (e.g. `{"status": "success", "resolved_by": "tier_5"}`). Call `dispatch(state)` and assert the mock was called with `target=` equal to the **expanded** path (e.g. `"docs/carryover/foo.md"`), not the literal `'docs/carryover/$(...)'` string. Mock/stub any other calls `dispatch()` makes along this path (e.g. `_recheck_regression_flags`, `save_run`, `regression_guard.hash_file`) as needed to isolate the assertion, following the same mocking granularity used elsewhere in `tests/test_tier5_librarian.py` for its success-path test.
- [ ] Verify the new file compiles and runs in isolation: `python3 -m py_compile tests/test_dispatcher_dynamic_target_resolution.py && PYTHONPATH=. python3 -m unittest tests.test_dispatcher_dynamic_target_resolution -v`

## Phase 4 — Full regression suite and skip-marker check

- [ ] Run `PYTHONPATH=. python3 -m unittest tests.test_branch_features tests.test_tier5_librarian tests.test_dispatcher_dynamic_target_resolution -v 2>&1 | tee /tmp/triapi_dynamic_target_test_run.log` and confirm the tail of `/tmp/triapi_dynamic_target_test_run.log` shows `OK`.
- [ ] Check for a real skip marker anchored to unittest's own per-test/summary syntax (NOT a bare substring grep for "skip", since test method names can contain that substring incidentally): `grep -E "\.\.\. skipped\$|^OK \(skipped=" /tmp/triapi_dynamic_target_test_run.log` — if this matches anything, investigate before considering the run clean; if it matches nothing, the run is confirmed clean of skips.

## Phase 5 — Update `AGENTS.md` and mark the carryover queue item resolved (via `librarian_escalate.py`, not hand-edited)

- [ ] Resolve the active carryover file path: `ACTIVE_CARRYOVER=$(jq -r '.active' docs/carryover/index.json)` (run in repo root).
- [ ] Update `AGENTS.md`'s `scripts/dispatcher.py`-related index note to mention the new `_resolve_dynamic_target` helper and the fixed dynamic-target bug, by invoking the real CLI (not hand-editing): `python3 scripts/librarian_escalate.py --task-id agents-md-dynamic-target-fix-note --description "Add a short note to AGENTS.md's dispatcher.py index entry describing the new _resolve_dynamic_target(target, project_dir) helper added near _normalize_build_cmd: it expands a breakdown item's target field through a real bash -c subprocess when it contains shell substitution markers ($( , backtick, or \${), fixing a bug where a dynamic $(...) target string was previously used literally as a Python path (confirmed live run 20260827-132236-806da1 Phase 4 item 0, silently producing a false success with zero real edit); falls back safely to the original string on any subprocess failure." --target AGENTS.md --workdir .`
- [ ] Mark queue item 4 RESOLVED in the active carryover file, by invoking the real CLI (not hand-editing): `python3 scripts/librarian_escalate.py --task-id carryover-dynamic-target-fix-resolved --description "In the file at path \$ACTIVE_CARRYOVER (resolved via jq -r '.active' docs/carryover/index.json), mark queue item 4 (the dispatcher.py dynamic $(...) target-resolution bug) as RESOLVED, noting the fix added _resolve_dynamic_target() in scripts/dispatcher.py plus tests/test_dispatcher_dynamic_target_resolution.py, all regression tests passing with no skips." --target "$ACTIVE_CARRYOVER" --workdir .`
- [ ] Verify both doc updates landed as real content changes (not a false success): `git diff --stat AGENTS.md "$ACTIVE_CARRYOVER"` — confirm both files show non-zero changed lines.
<!-- triapi:plan run_id=20260827-234324-b88ea5 end -->


<!-- triapi:plan run_id=20260828-003607-362ff2 start -->
## TriAPI Plan (run 20260828-003607-362ff2, appended 2026-08-28)

- [ ] Read the test file `tests/test_dispatcher_dynamic_target_resolution.py` to understand the exact structure of `_write_files()` helper
	- [ ] Apply the fix: add parent directory creation before `.touch()` in the `_write_files()` method
	- [ ] Run the specific test file to verify all 4 tests pass: `PYTHONPATH=. python3 -m unittest tests.test_dispatcher_dynamic_target_resolution -v`
	- [ ] Run the full regression suite to confirm no regressions: `PYTHONPATH=. python3 -m unittest tests.test_branch_features tests.test_tier5_librarian tests.test_dispatcher_dynamic_target_resolution -v`
	- [ ] Mark queue item 4 as RESOLVED in the active carryover file using `scripts/librarian_escalate.py`'s CLI (first check which file is active via `jq -r '.active' docs/carryover/index.json`)
<!-- triapi:plan run_id=20260828-003607-362ff2 end -->

<!-- triapi:plan run_id=20260828-004343-de5ad2 start -->
## TriAPI Plan (run 20260828-004343-de5ad2, appended 2026-08-28)

- [x] Read `tests/test_dispatcher_dynamic_target_resolution.py` to locate the `_write_files()` helper and the exact line to modify
- [x] Edit `tests/test_dispatcher_dynamic_target_resolution.py` to add `mkdir(parents=True, exist_ok=True)` before the `touch()` call in `_write_files()`
- [x] Run `PYTHONPATH=. python3 -m unittest tests.test_dispatcher_dynamic_target_resolution -v` to verify all 4 tests pass
- [x] Run `PYTHONPATH=. python3 -m unittest tests.test_branch_features tests.test_tier5_librarian tests.test_dispatcher_dynamic_target_resolution -v` to confirm full regression suite passes
- [x] Use `scripts/librarian_escalate.py` to mark queue item 4 as RESOLVED in the active carryover file (path resolved via `jq -r '.active' docs/carryover/index.json`)
<!-- triapi:plan run_id=20260828-004343-de5ad2 end -->



<!-- triapi:plan run_id=20260828-023258-1fe9e3 start -->
## TriAPI Plan (run 20260828-023258-1fe9e3, appended 2026-08-28)

1. Phase 1: Update Code Documentation
   - [x] `scripts/dispatcher.py`: Update the docstring of `_is_deepseek_peak_hours()` to state that the weekend exception uses "Beijing time" instead of the "America/Los_Angeles timezone". This aligns the text with the actual logic in `budget_guard.py`. Do not change any implementation logic. Verify with `python3 -m py_compile scripts/dispatcher.py`.

2. Phase 2: Update Carryover Documentation
   - [x] `docs/carryover/20260824-235900-misc-resolved-fixes.md`: Append a brief dated correction note (2026-08-28) stating that the test `test_cmd_dispatch_restores_ollama_state_on_exception` is now confirmed passing with full mocking in place. Do not remove or rewrite the original text, only append the correction. This edit MUST be executed using the `scripts/librarian_escalate.py` CLI, not via manual file write/edit tools. Verify with `python3 -m unittest tests.test_branch_features -v`.
<!-- triapi:plan run_id=20260828-023258-1fe9e3 end -->

<!-- triapi:plan run_id=20260901-002308-fa389b start -->
## TriAPI Plan (run 20260901-002308-fa389b, appended 2026-09-01)

1. Phase 1: Tier 5 librarian simplification
   - [x] `config/tiers.yaml`: Edit the `tier_5_librarian` block. Change `effort` from `low` to `high`. Keep `models: {primary: "gemini-3.7-flash"}` and delete the `fallback_local`, `fallback_openrouter`, and `fallback_agy` keys from `models`. Delete the `escalation_rules.tier5_to_fallbacks` block. Delete the `ollama_fallback` block entirely. Verify: `python3 -c "import yaml; yaml.safe_load(open('config/tiers.yaml'))"`
   - [x] `scripts/librarian_escalate.py`: Remove the `fallback_local_block` and `providers` list building. Replace the `for attempt_idx, provider_info in enumerate(providers):` loop with a single execution of the primary model using the `agy` provider (reading directly from `models_cfg.get("primary")`). If it fails, fail fast and call `_escalate_to_human` directly without looping through fallbacks. Verify: `python3 -m py_compile scripts/librarian_escalate.py && python3 -m pytest tests/ -q`
   - [x] `tests/test_tier5_librarian.py`: Remove any tests specifically asserting the escalation chain (`primary -> fallback_local -> fallback_agy -> fallback_openrouter`). Update tests to expect an immediate human handoff if the primary model fails. Verify: `python3 -m pytest tests/test_tier5_librarian.py -q`

2. Phase 2: Remove Gemini per-model daily-quota fallback
   - [x] `scripts/gemini_fallback.py`: Delete this file via `git rm scripts/gemini_fallback.py`. Verify: `git status`
   - [x] `config/tiers.yaml`: Delete the `gemini_fallback` top-level block. Remove any remaining `fallback_chain` keys under `tier_2_manager` or anywhere else. Verify: `python3 -c "import yaml; yaml.safe_load(open('config/tiers.yaml'))"`
   - [x] `scripts/dispatcher.py`: In `_breakdown_phase_attempt()`, remove the `if provider == "google":` branch and the `gemini_fallback` import entirely. Always use the `else` branch's `llm_client.execute_llm` code path for all providers, ensuring it passes the correct `endpoint` and `api_key` for the given provider. Verify: `python3 -m py_compile scripts/dispatcher.py && python3 -m pytest tests/ -q`
   - [x] `scripts/tier2_escalate.py`: In `escalate()`, remove the `fallback_chain` lookup (`chain = tier2.get("fallback_chain") or []`) and the `for candidate in models:` loop. Call `llm_client.execute_llm` exactly once using the `default_model` (or explicit `model` override) and remove the `continue` on HTTP 429/403 to fail fast instead. Verify: `python3 -m py_compile scripts/tier2_escalate.py && python3 -m pytest tests/ -q`
   - [x] `tests/test_tier2_escalate.py`: Remove any tests that specifically exercise the `fallback_chain` loop behavior. Verify: `python3 -m pytest tests/test_tier2_escalate.py -q`
   - [x] `tests/test_dispatcher.py`: Remove any tests that specifically exercise `gemini_fallback.py` or the `provider == "google"` special case in phase breakdown. Verify: `python3 -m pytest tests/test_dispatcher.py -q`

3. Phase 3: Simplify tiers 2/3/4's peak-hours provider assignment
   - [x] `config/tiers.yaml`: Update `tier_3_debugger`'s primary (off-peak) block to use `provider: agy` (replacing `deepseek`), `models: {default: gemini-3.1-pro}`, and `effort: high`, and remove its `endpoint` and `api_key_secret`. Leave its `peak_alt` block unchanged. Update `tier_2_manager`'s `peak_alt` block to use `provider: agy`, `models: {default: gemini-3.1-pro}`, and `effort: high` (replacing `gemini-3.7-flash`). Leave `tier_2_manager`'s primary block (with `peak_hours_utc`) and `tier_4_worker`'s primary/`peak_alt` blocks exactly as they are. Verify: `python3 -c "from scripts.config_loader import load_tiers; load_tiers()" && python3 -m pytest tests/ -q`
<!-- triapi:plan run_id=20260901-002308-fa389b end -->

<!-- triapi:plan run_id=20260902-105125-fa54aa start -->
## TriAPI Plan (run 20260902-105125-fa54aa, appended 2026-09-02)

1. Phase 1: Configuration Update and Live Verification
- [x] `config/tiers.yaml`: Update the `tier_5_librarian.models.primary` value from `gemini-3.7-flash` to `gemini-3.8-flash`. Leave the effort setting untouched. Verify command: `agy models | grep "gemini-3.8-flash" && agy -p "reply with exactly OK" --model gemini-3.8-flash --effort high --dangerously-skip-permissions --output-format json`

2. Phase 2: Documentation Updates
- [x] `ARCHITECTURE.md`: Locate the text describing the `tier_5_librarian` primary model and update `gemini-3.7-flash` to `gemini-3.8-flash`. Ensure all `gemini-3.1-pro` references are left untouched. Verify command: `grep "gemini-3.8-flash" ARCHITECTURE.md`
- [x] `AGENTS.md`: In the `config/` section documentation for `tiers.yaml`, update the note describing the `tier_5_librarian:` block's primary model swap, changing `gemini-3.7-flash` to `gemini-3.8-flash`. Do not modify any references to `gemini-3.1-pro`. Verify command: `grep "gemini-3.8-flash" AGENTS.md`

3. Phase 3: Script and Test Updates
- [x] `scripts/librarian_escalate.py`: Update the module docstring to replace `gemini-3.7-flash` with `gemini-3.8-flash` as the live model for Tier 5. Verify command: `python3 -m py_compile scripts/librarian_escalate.py && grep "gemini-3.8-flash" scripts/librarian_escalate.py`
- [x] `scripts/orchestrator.py`: Find the inline comment referencing `gemini-3.7-flash` as the librarian tier model and update it to `gemini-3.8-flash`. Additionally, fix the stale comment about Tier 2 peak_alt's actual current config to say `gemini-3.1-pro` instead of whatever it currently says. Verify command: `python3 -m py_compile scripts/orchestrator.py && grep "gemini-3.8-flash" scripts/orchestrator.py && grep "gemini-3.1-pro" scripts/orchestrator.py`
- [x] `tests/test_tier5_librarian.py`: Update the test fixture string literals that explicitly assert on the model id `gemini-3.7-flash`, changing them to `gemini-3.8-flash`. Verify command: `PYTHONPATH=. python3 -m unittest tests.test_branch_features tests.test_tier5_librarian -v`
<!-- triapi:plan run_id=20260902-105125-fa54aa end -->

<!-- triapi:plan run_id=20260902-134333-db9aba start -->
## TriAPI Plan (run 20260902-134333-db9aba, appended 2026-09-02)

## Phase 1: Fix `cmd_status` crash for tech-debt runs
- [ ] `scripts/triapi.py`: Update `cmd_tech_debt()` to include a `"prompt"` key in the `synthetic_state` dictionary (e.g., `"prompt": f"Tech debt: {len(filtered_entries)} entries"`) so that `cmd_status()` does not crash with a `KeyError`. Verify with `python3 -m py_compile scripts/triapi.py && PYTHONPATH=. python3 -m unittest tests.test_branch_features -v`

## Phase 2: Targeted verification for tech-debt items
- [ ] `scripts/triapi.py`: Update `cmd_tech_debt()` to generate a specific `build_cmd` for each item. It should always start with `python3 -m py_compile <target>`. If the target starts with `tests/test_` and ends with `.py`, derive its dotted module name and append `&& PYTHONPATH=. python3 -m unittest <module_name> -v`. For non-test files, append `&& PYTHONPATH=. python3 -m unittest tests.test_branch_features tests.test_tier5_librarian -v`. Verify with `python3 -m py_compile scripts/triapi.py && PYTHONPATH=. python3 -m unittest tests.test_branch_features -v`

## Phase 3: Clean up resolved tech-debt entries
- [ ] `scripts/tech_debt.py`: Add a `remove_resolved_entries(resolved_targets: set[str]) -> None` helper. It should read `knowledge/TECH_DEBT.md`, filter out any entry lines whose parsed `filepath` is in `resolved_targets`, and overwrite the file with the remaining lines (preserving the header intact). Verify with `python3 -m py_compile scripts/tech_debt.py && PYTHONPATH=. python3 -m unittest tests.test_branch_features -v`
- [ ] `scripts/triapi.py`: In `cmd_tech_debt()`, after `dispatcher.dispatch(synthetic_state)` returns, collect the targets of all items in `synthetic_state["results"]` that have `status == "success"`. Call `tech_debt.remove_resolved_entries()` with that set of targets. Verify with `python3 -m py_compile scripts/triapi.py && PYTHONPATH=. python3 -m unittest tests.test_branch_features -v`

## Phase 4: Manage self-fix backlog
- [ ] `scripts/dispatcher.py`: Add a `delete_run(run_id: str) -> None` helper that deletes the run state file at `logs/runs/<run_id>.json` if it exists. Verify with `python3 -m py_compile scripts/dispatcher.py && PYTHONPATH=. python3 -m unittest tests.test_branch_features -v`
- [ ] `scripts/triapi.py`: Add a `cmd_self_fix_discard(bug_id: str)` function. It should resolve the bug report via `_resolve_bug_report()` and delete the JSON file if found. It should also resolve the run via `_find_self_fix_run()` and call `dispatcher.delete_run(state["run_id"])` ONLY if the run's status is exactly `"self_fix_drafted"`. Print a one-line confirmation of what was deleted, or `"nothing found for <bug_id>"` if neither existed. Wire this function up as the `discard` subcommand under `triapi self-fix` in `main()`. Verify with `python3 -m py_compile scripts/triapi.py && PYTHONPATH=. python3 -m unittest tests.test_branch_features -v`
- [ ] `tests/test_branch_features.py`: In the `SelfFixTests` class, add tests for `triapi self-fix discard`: discarding a bug-report-only entry, discarding a drafted-run-only entry, discarding both together, discarding a nonexistent ID (must not crash and should print the clear message), and verifying it refuses to discard a run whose status is not `"self_fix_drafted"`. Verify with `PYTHONPATH=. python3 -m unittest tests.test_branch_features -v`

## Phase 5: Clear stale self-fix backlog
- [ ] `scripts/clear_stale_self_fixes.py`: Create a one-off python script that executes `python3 scripts/triapi.py self-fix list`, parses the unqueued bug reports and drafted run IDs, and verifies they fall into the known stale categories described in the goal (tempfile-style names like `tmp*`, or specific timestamped entries for already-fixed crashes). If an entry matches a stale category, invoke `python3 scripts/triapi.py self-fix discard <bug_id>`. If any entry does NOT match the known stale signatures, STOP and print a flag without discarding it. Verify with `python3 scripts/clear_stale_self_fixes.py && python3 scripts/triapi.py self-fix list`
<!-- triapi:plan run_id=20260902-134333-db9aba end -->

<!-- triapi:plan run_id=20260902-145318-d0c31a start -->
## TriAPI Plan (run 20260902-145318-d0c31a, appended 2026-09-02)

1. Phase 1: Test coverage for `triapi.cmd_self_fix_discard`
   - [x] tests/test_self_fix_discard.py: Create `tests/test_self_fix_discard.py` with regression coverage for `triapi.cmd_self_fix_discard`. Include testing: discarding a bug-report-only entry (no linked run), discarding a drafted-run-only entry (no resolvable bug report file), discarding both together in one call, discarding a nonexistent bug_id (must not crash, must print the "nothing found for <bug_id>" message), and confirming it refuses to delete a run whose status is anything other than "self_fix_drafted" (e.g. "planned" or "completed") -- the bug report file, if any, should still be deleted in that refusal case, only the run-state deletion is skipped. Use the same `tempfile.TemporaryDirectory() as tmp, mock.patch.object(self_fix, "BUGS_DIR", Path(tmp))` fixture pattern already used by the existing SelfFixTests class. Verify: `python3 -m py_compile tests/test_self_fix_discard.py && PYTHONPATH=. python3 -m unittest tests.test_self_fix_discard -v`

2. Phase 2: Fix `cmd_tech_debt` build command generation
   - [x] scripts/triapi.py: Modify `cmd_tech_debt()` to generate proper `build_cmd` for each item. Parse `entry['filepath']`: if it matches `tests/test_*.py`, derive the module name (e.g. `tests.test_llm_client_sanitize` from `tests/test_llm_client_sanitize.py`) and set `build_cmd` to include `python3 -m py_compile <target> && PYTHONPATH=. python3 -m unittest <module_name> -v`. For non-test targets, set `build_cmd` to include `python3 -m py_compile <target> && PYTHONPATH=. python3 -m unittest tests.test_branch_features tests.test_tier5_librarian -v`. Chain parts with `&&`. Verify: `python3 -m py_compile scripts/triapi.py`
   - [x] tests/test_self_fix_discard.py: Append a test for `cmd_tech_debt` to prove that for a `tests/test_something.py` target the generated `build_cmd` string contains both `py_compile` and `unittest tests.test_something`, and for a non-test target it contains both `py_compile` and the shared full-suite command. Verify: `PYTHONPATH=. python3 -m unittest tests.test_self_fix_discard -v`

3. Phase 3: Backlog clearing
   - [x] scripts/clear_stale_self_fixes.py: Create script to parse `python3 scripts/triapi.py self-fix list` output. Classify every unqueued bug-report stem and drafted run_id as stale if they match: bare tempfile-style names with no timestamp prefix (e.g. `tmp0eoz_tkm`), or a real timestamp-prefixed entry matching an exception signature already fixed (`gemini-2.5-flash-lite: 403`, `nvidia/nemotron...: 'choices'` KeyError, `KeyError: 'pricing'/'phases'/'item'/'default'/'pass'`, `Tier 2 failed on gemini-3.7-flash/gemini-3.1-pro: Command [agy...]`, `openrouter API ... returned choices with null message content`, `IsADirectoryError ... ohmyllama`). For every matched entry, invoke `python3 scripts/triapi.py self-fix discard <bug_id>`. If any entry does NOT match a known-stale signature, STOP without discarding it and print it clearly flagged in the script's own output. Verify: `python3 scripts/clear_stale_self_fixes.py && python3 scripts/triapi.py self-fix list && PYTHONPATH=. python3 -m unittest tests.test_branch_features tests.test_tier5_librarian tests.test_self_fix_discard -v && wc -c tests/test_branch_features.py scripts/triapi.py && git status --short`
<!-- triapi:plan run_id=20260902-145318-d0c31a end -->
