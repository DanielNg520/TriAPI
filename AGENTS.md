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
- `PLAN.md` — phase-by-phase implementation plan with checklists and end-of-phase tests. The permanent record of TriAPI's own build — read here for *why*, not `CARRYOVER.md`.
- `AGENTS.md` — this file (formerly `mapping.md`).
- `ARCHITECTURE.md` — system design: the 4-tier escalation state machine, DeepSeek cache-hit economics, budget guard rationale, and what changed during the build (Tier 2 redesign, MCP server dropped, Jules deferred).
- `README.md` — step-by-step walkthrough (first-time run, reading output/cost report, human-handoff files, common gotchas) plus setup (Python deps, sops/age, Ollama systemd service, Claude Code subscription login) and command reference (standalone task, smoke test, cost report).
- `AGENT_GUIDE.md` (2026-08-14) — for an agent operating `triapi` with Tier 1 off (`--no-tier1` / `tier_1_manager.enabled: false`): what actually changes (repair chain only, `planner.py` untouched), why the agent effectively becomes planner+supervisor+monitor with one less automated repair tier, and the concrete human_handoff diagnosis/patch/resume workflow. Also documents `scripts/self_fix.py` (crash-triggered plan drafting, never auto-dispatched) and `knowledge/lessons.py` + `scripts/critique.py` (failure-pattern knowledge store + advisory diff-quality gate) — both TriAPI's own features, proven via worked dispatches against a target repo; target-repo specifics of those dispatches live in that repo's own docs, not here.
- `CARRYOVER.md` — brief current-state resume note only. Read this first when resuming work.
- `.sops.yaml` — sops encryption rule: files matching `config/secrets.enc.yaml` are encrypted to the age recipient in `~/.config/sops/age/keys.txt`.
- `.gitignore` — excludes runtime logs/state, plaintext secrets, Python caches, venvs.
- `requirements.txt` — Python deps: `requests`, `PyYAML`, `mcp`.
- `LICENSE` — Apache-2.0.

## config/
- `tiers.yaml` — tier definitions: models, endpoints, roles, pricing (DeepSeek pricing needs periodic reverification, see `last_verified`), escalation thresholds. As of the Phase 33 reassignment (2026-08-25), `tier_2_manager` is the real DeepSeek API (`deepseek-v4-pro`; `peak_hours_utc` now lives here, moved from Tier 3), `tier_3_debugger` is `agy`/`gemini-3.1-pro` (Antigravity CLI, effort high, no peak-hours/pricing block), and `tier_4_worker` is local Ollama `qwen2.5-coder:14b-instruct-q6_K` at `http://localhost:11434` — check the file directly for the live assignment rather than trusting a snapshot here, since these get reassigned periodically (see `CARRYOVER.md`'s "Next up" for the most recent reassignment in flight). `tier_2_manager.peak_hours_utc` (or wherever `budget_guard.resolve_deepseek_tier()` currently finds the real DeepSeek API assignment — position-independent as of Phase 31, not hardcoded to a tier name) — UTC peak-window list checked by `budget_guard.check_tier3_peak_hours_ok()`, defaulting to the two DeepSeek V4 peak windows if absent; `tier_3_debugger.default_model` is `default` (`gemini-3.1-pro` via `agy`). `critique:` block (enabled, applies_to_tiers, critic, score_threshold, max_revision_attempts) gates the advisory diff-quality step in `orchestrator._critique_and_maybe_revise()`. `self_fix.enabled` controls crash-triggered plan drafting without disabling report capture. `tier_1_manager.enabled` (2026-08-14) — on/off switch for Tier 1's *repair* role in `orchestrator.run_task()`; distinct from `tier_1_planner` above, which configures `planner.py`'s interactive plan-authoring role and is untouched by this switch. Boolean, default `true` (both in the yaml and in `check_tier1_manager_ok()`'s own fallback). Overridable per-run via `triapi dispatch --no-tier1` / the `TRIAPI_NO_TIER1` env var without editing this file. `jules_tester:` block (2026-08-16/17, same documentation style as the DeepSeek peak-hour block above) — config for the advisory, never-blocking Jules post-dispatch verification tier: `enabled`; `source` (the confirmed-live REST source resource name from `GET /sources`, e.g. `sources/github/owner/repo` — NOT the bare `owner/repo` form); `daily_task_limit` (15, free tier, confirmed by the absence of a Pro/Ultra indicator on this account); `poll_timeout_s`/`poll_interval_s` (900s/15s, sized from real live discovery sessions that took several minutes including plan-approval delay). Also documents, inline as a comment, the corrected `sourceContext.githubRepoContext.startingBranch` field path vs. the public docs' wrong `sourceContext.githubBranch` — see `scripts/jules_client.py` above for the live-verification details. `requirePlanApproval: false` is sent by `jules_client.create_session()`'s default, but whether it actually skips the "Awaiting Plan Approval" delay is **NOT confirmed live** — both real sessions created during planning (one via the CLI, one a throwaway REST discovery call) went through an observed "Awaiting Plan Approval"/`planApproved` activity before proceeding regardless, and neither was created with this exact flag set and watched to completion. A post-implementation dispatch run initially documented this as "confirmed live" in this file, which was wrong (a fabricated confirmation, caught and corrected 2026-08-17) — treat the flag's actual effect as an open question until a manual smoke test observes it directly, and budget the ~30-60s plan-approval delay into `poll_timeout_s` regardless of whether the flag turns out to skip it. **We do not trigger a real live Jules session as part of automated tests** — `tests/test_branch_features.py` and the rest of the automated suite mock `jules_client`/`budget_guard` wherever Jules is touched and never make a real network call to `jules.googleapis.com`. `jules_client.run_jules_test()`/`main()`'s actual end-to-end session-create-and-poll path is reserved for a manual, human-supervised smoke test (run by hand, with the real `google_jules_apikey` secret and a real GitHub source) — not part of `PYTHONPATH=. python3 -m unittest tests.test_branch_features -v`. `ARCHITECTURE.md` was refreshed on 2026-08-26 to describe the current 5-tier state (Tier 2=DeepSeek, Tier 3=agy/gemini-3.1-pro, Tier 4=local Ollama, Tier 5=librarian) replacing its previous stale 4-tier description.
- `resource_guard.yaml` — machine-specific list of systemd `--user` services paused for the duration of every `triapi dispatch` run and resumed afterward (Phase 12), so Tier 4's local Ollama gets the shared iGPU/RAM without contention. Not portable to another deployment; empty/missing file just disables the guard. `unload_other_ollama_models: true` (2026-08-17) — complementary, separate mechanism layered on top of `pause_services`: force-unloads any other Ollama-resident model via the API (`GET /api/ps` then `POST /api/generate` with `keep_alive: 0`) immediately before every `triapi dispatch`, so Tier 4's configured model gets the full shared iGPU/RAM budget. Defaults to `true` (also when the file or key is absent — the loader defaults on); set it to `false` to disable model-unloading while keeping the systemd pause list active.
- `secrets.example.yaml` — plaintext template documenting required secret keys (`deepseek_api_key`, `ollama_host`, `google_ai_studio_api_key`, `google_jules_apikey`), no real values, safe to commit.
- `secrets.enc.yaml` — sops/age-encrypted real secrets. **As of 2026-08-17, local-only and gitignored, NOT committed** (a full `git filter-repo` history purge removed the previously-committed ciphertext from every past commit — see `ARCHITECTURE.md`). Edit with `sops config/secrets.enc.yaml`; the file must be created locally (from `secrets.example.yaml`'s template, then `sops -e -i`) on any new machine, since it no longer ships with `git clone`.

## knowledge/
- `lessons.jsonl` — committed failure-pattern knowledge store (deliberately *not* under `logs/`, which is gitignored wholesale). One JSON object per line with schema `{id, date, category ("bug_fix"|"unresolved_pattern"), component, bug_description, what_went_wrong, fix_description, tags[]}`. Seeded from real historical TriAPI bugs; appended at runtime by `scripts/lessons.add_lesson()` (including auto-capture from `orchestrator.human_handoff()`). Consumed cheaply/locally by `select_relevant()` keyword overlap — no LLM call — and folded into tier edit prompts as a "## Known past mistakes..." do/don't block.
- `hivemind.md` — central repository of reusable, stripped-down code snippets with XML-wrapped `<triapi_snippet>` blocks. Parsed at runtime to search for patterns matching the task description and file extension, and injected into Tier 4's prompt as reference.
- `TECH_DEBT.md` — record of accumulated technical debt from judge rejections where the fix-forward build loop failed to compile, storing the file path, file content hash, and reason.

- `tiers.yaml`'s `tier_5_librarian:` block (2026-08-24, `fallback_agy` leg added 2026-08-26, **primary swapped from `ollama`/`mistral-small` to `agy`/`gemini-3.7-flash` at `effort: low` on 2026-08-27**) — the doc-update tier: `provider: agy`, `effort: low`, `models: {primary: gemini-3.7-flash, fallback_local: ollama_fallback, fallback_agy: default, fallback_openrouter: stealth/ox-alpha}`, `target_globs: ["*.md", "docs/**"]` (matched by `dispatcher.is_doc_target()`), `verify_command`, `max_attempts`. The primary swap fixed a systematic 600s timeout on every real doc-edit task: local `mistral-small` on this machine's AMD iGPU ran at only ~10-11 tok/s, so any real-sized target routinely exceeded `_HTTP_TIMEOUT` before falling through to the fallback; the same edit via `agy`/Gemini 3.7 Flash completed in ~4s in live verification. `scripts/librarian_escalate.py`'s `providers` list is config-driven for the primary slot (reads `tier_5_librarian.provider`/`effort`, not hardcoded). `escalation_rules.tier5_to_fallbacks` (`threshold: 2`, `chain: [fallback_local, fallback_agy, fallback_openrouter, log_and_notify]`) is otherwise unchanged — `fallback_agy` (Antigravity CLI, `gemini-3.1-pro`, effort high) sits between the two Ollama legs and OpenRouter, subscription-billed at $0 marginal cost, same as the rest of this chain: all-local/free-or-subscription, zero paid/metered-API calls anywhere in it (do not confuse this fallback slot with the new primary — different model, different effort, different purpose). `llm_client.execute_agy()` is the thin public wrapper this leg calls (delegates to `_call_agy_cli`, the same subprocess helper Tier 3 uses). **Known open bug (unfixed as of 2026-08-28): `_call_agy_cli()` passes the prompt as a CLI argument (`cmd = ["agy", "-p", prompt]`), which raises `OSError: [Errno 7] Argument list too long` for any large prompt (e.g. this file's own full contents as edit context) — the bug is STILL OPEN as of 2026-08-28; a stdin-based fix was attempted and reverted after confirming agy's -p flag requires an argv value (does not support stdin, unlike claude's -p); the real fix still needs to be found (e.g. a prompt-size guard that fails fast/falls through to the next provider before hitting the OS argv limit, rather than blindly retrying an approach agy's CLI doesn't support).** See `scripts/librarian_escalate.py` below for the runtime logic.

## scripts/
Full reference moved to [`docs/agents/20260825-100000-scripts-directory-reference.md`](docs/agents/20260825-100000-scripts-directory-reference.md) (2026-08-25 — see `docs/agents/index.json`) to keep this file under the 73,728-char ceiling. Covers every pipeline module: `secrets_loader.py`, `config_loader.py`, `llm_client.py`, `state.py`, `gemini_fallback.py`, `content_guard.py`, `edit_blocks.py`, `lessons.py`, `hivemind_util.py`, `critique.py`, `judge.py`, `self_fix.py`, `tier4_context.py`, `tier4_worker.py`, `tier3_escalate.py`, `tier1_escalate.py`, `tier2_escalate.py`, `budget_guard.py`, `jules_client.py`, `cost_report.py`, `orchestrator.py`, `agents_md_gate.py`, `planner.py`, `dispatcher.py`, `regression_guard.py`, `mock_patch_lint.py`, `tech_debt.py`, `git_ops.py`, `triapi.py`, `resource_guard.py`, `tri_logging.py`, `librarian_escalate.py`.

## tests/
- `test_tier5_librarian.py` (2026-08-24, updated 2026-08-26 for the `fallback_agy` leg) — regression tests for `scripts/librarian_escalate.py`/`dispatcher.is_doc_target()`/`llm_client.detect_email_like_content()`: config schema, glob truth table, email-detection, the success write path (edit-block apply + cost-log `billing: "local"`), the primary→fallback_local→fallback_agy→fallback_openrouter→log_and_notify escalation order (with an `execute_agy` mock sentinel asserted invoked only after `fallback_local` exhausts its threshold) with paid-tier (DeepSeek/Claude/Gemini) call sentinels proving they're never touched, chain-exhaustion handoff, workdir-boundary refusal, and the advisory no-change verdict. Split out from `tests/test_branch_features.py` for the same size-ceiling reason as `test_mock_patch_lint.py` below.
- `test_llm_client_http_timeout.py` (2026-08-26) — regression coverage for `scripts/llm_client.py`'s `_HTTP_TIMEOUT` constant (fixture/mock style, zero network calls): default value 600, `TRIAPI_HTTP_TIMEOUT` env-override via `importlib.reload`, and both `_call_openai_api()`/`_call_gemini_api()` proven to actually pass `timeout=_HTTP_TIMEOUT` to `requests.post` (the original bug shape, a hardcoded 300, being the thing this guards against). Split out per the same size-ceiling convention as the other dedicated test files above.
- `test_orchestrator_tier3_timeout_skip.py` (2026-08-26) — regression coverage proving a `scripts/llm_client.py` `subprocess.TimeoutExpired` from the `agy` CLI (Tier 3) is returned by `scripts/tier3_escalate.py` as `status: 'timeout'` and soft-escalates to Tier 2 (DeepSeek) in `scripts/orchestrator.py`'s `run_task()`, rather than raising `RuntimeError` or falling through to `human_handoff`. Fixture/mock style, zero network calls.
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




