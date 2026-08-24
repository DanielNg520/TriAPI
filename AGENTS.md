# AGENTS.md

Repo-root reference for coding agents: codebase conventions, test commands, architecture, and guidelines, plus a living index of every file/dir in this repo. Read this before exploring — updated at the end of every phase. (Renamed from `mapping.md` 2026-08-17; conventions/test-commands/architecture content is being folded in incrementally as it's touched, not as a one-time rewrite — see `AGENT_GUIDE.md`/`ARCHITECTURE.md`/`README.md` for the fuller versions of each until then.)

**Standing rule, effective 2026-08-18: docs stay clean, no sprawl, no oversized
files.** What's worth knowing goes in exactly one of two places, and only if
it's actually load-bearing: `PLAN.md` (this repo's phase-by-phase record) or
a source-code comment at the point it matters. Session narrative, per-run
diagnostic play-by-play, and anything about a *target* repo TriAPI dispatched
against (e.g. oh-my-llama) do not belong in TriAPI's docs at all — that
content is the target repo's own history, not TriAPI's, and belongs in that
repo's own docs. `CARRYOVER.md` stays brief: only what's needed to resume the
next session. (2026-08-18: `agent_evalution.md`, `agent_testrun.md`, and
`GHOSTWRITER_PLAN.md` were removed outright — all three were narrative about
target-repo work, not TriAPI itself. `CARRYOVER.md` was cut from ~2,400 lines
of cross-session play-by-play to a short current-state brief; the play-by-play
itself was discarded, not relocated — it wasn't durable knowledge, it was
session noise. 2026-08-19: this same treatment applied to `AGENTS.md` itself —
9 fully-checked-off `triapi:plan` history blocks, ~417 lines of completed
per-run checklists whose outcomes are already documented in `PLAN.md`'s
carryover log, were removed outright rather than left to accumulate forever;
file went from 146,117 to ~53,000 chars (confirmed 53,420 chars via `wc -c` on 2026-08-20, safely below the 73,728-char Tier 4 ceiling). A completed plan block's narrative
value ends the moment its work lands — `mark_plan_complete()`/
`find_incomplete_plan()` only ever care about the single most-recently
appended block, so older completed blocks are pure historical weight with no
functional purpose.) **Standing convention across the user's repos** — see
oh-my-llama's own `AGENTS.md`/`MAPPING.md` for the same discipline applied
there.

## Conventions, test commands, architecture (quick reference)
- **Conventions/guidelines:** full detail in `AGENT_GUIDE.md` (agent operating manual — what's safe to hand-edit vs. must route through the dispatch pipeline, phase discipline, verification requirements).
- **Test commands:** `PYTHONPATH=. python3 -m unittest tests.test_branch_features -v` (full regression suite); `python3 -m py_compile <file>` before any script change is considered done.
- **Architecture:** full detail in `ARCHITECTURE.md` (4-tier escalation state machine, budget guard rationale, DeepSeek cache-hit economics).

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
- `tiers.yaml` — tier definitions: models, endpoints, roles, pricing (DeepSeek pricing needs periodic reverification, see `last_verified`), escalation thresholds. `tier_2_manager.fallback_chain` (Phase 14) — ordered list of real Gemini model names tried in sequence when the current one's free-tier daily quota is exhausted (Google buckets this per-model, confirmed live 2026-08-10). `tier_2_manager.models.pro` is `gemini-2.5-pro` (`gemini-3.5-pro` confirmed not to exist 2026-08-10; a plain `gemini-3-pro` was also checked and confirmed not to exist 2026-08-16 — only `gemini-3.1-pro-preview` and image-only `gemini-3-pro-image` variants exist under `gemini-3`). `default_model` stays `flash`; switching the permanent default to a Gemini 3 Pro model is deliberately deferred until a stable (non-preview) release exists — the down-only `fallback_chain` is unaffected either way. `tier_4_worker` now uses task-type routing (`config/tiers.yaml`'s `tier_4_worker.models`): `default` (`qwen2.5-coder:14b-instruct-q8_0`, ~15GB), `polyglot` (`deepseek-coder-v2:16b`, ~8.9GB, niche/uncommon languages), `heavy` (`qwen2.5-coder:32b`, ~19GB); `default_model` is `default`, which also serves as the safe fallback if `polyglot`/`heavy` fails to load; `gpt-oss:20b` and `qwen3-coder:30b-cc` are fully retired (2026-08-18) -- note that memory headroom is handled by `resource_guard.unload_other_ollama_models()`, not a static budget in this table. `tier_3_debugger.peak_hours_utc` — UTC peak-window list checked by `budget_guard.check_tier3_peak_hours_ok()`, defaulting to the two DeepSeek V4 peak windows if absent (one of which is 06:00-10:00 UTC). **Point-in-time as of 2026-08-20T06:42:41Z (LA local 2026-08-19T23:42:41-07:00): Tier 3 is in DeepSeek peak billing hours (06:00-10:00 UTC)**, so `budget_guard.check_tier3_peak_hours_ok()` refuses Tier 3 calls until 10:00 UTC. `tier_3_debugger.default_model` is `flash` (`deepseek-v4-flash`). `critique:` block (enabled, applies_to_tiers, critic, score_threshold, max_revision_attempts) gates the advisory diff-quality step in `orchestrator._critique_and_maybe_revise()`. `self_fix.enabled` controls crash-triggered plan drafting without disabling report capture. `tier_1_manager.enabled` (2026-08-14) — on/off switch for Tier 1's *repair* role in `orchestrator.run_task()`; distinct from `tier_1_planner` above, which configures `planner.py`'s interactive plan-authoring role and is untouched by this switch. Boolean, default `true` (both in the yaml and in `check_tier1_manager_ok()`'s own fallback). Overridable per-run via `triapi dispatch --no-tier1` / the `TRIAPI_NO_TIER1` env var without editing this file. `jules_tester:` block (2026-08-16/17, same documentation style as the DeepSeek peak-hour block above) — config for the advisory, never-blocking Jules post-dispatch verification tier: `enabled`; `source` (the confirmed-live REST source resource name from `GET /sources`, e.g. `sources/github/owner/repo` — NOT the bare `owner/repo` form); `daily_task_limit` (15, free tier, confirmed by the absence of a Pro/Ultra indicator on this account); `poll_timeout_s`/`poll_interval_s` (900s/15s, sized from real live discovery sessions that took several minutes including plan-approval delay). Also documents, inline as a comment, the corrected `sourceContext.githubRepoContext.startingBranch` field path vs. the public docs' wrong `sourceContext.githubBranch` — see `scripts/jules_client.py` above for the live-verification details. `requirePlanApproval: false` is sent by `jules_client.create_session()`'s default, but whether it actually skips the "Awaiting Plan Approval" delay is **NOT confirmed live** — both real sessions created during planning (one via the CLI, one a throwaway REST discovery call) went through an observed "Awaiting Plan Approval"/`planApproved` activity before proceeding regardless, and neither was created with this exact flag set and watched to completion. A post-implementation dispatch run initially documented this as "confirmed live" in this file, which was wrong (a fabricated confirmation, caught and corrected 2026-08-17) — treat the flag's actual effect as an open question until a manual smoke test observes it directly, and budget the ~30-60s plan-approval delay into `poll_timeout_s` regardless of whether the flag turns out to skip it. **We do not trigger a real live Jules session as part of automated tests** — `tests/test_branch_features.py` and the rest of the automated suite mock `jules_client`/`budget_guard` wherever Jules is touched and never make a real network call to `jules.googleapis.com`. `jules_client.run_jules_test()`/`main()`'s actual end-to-end session-create-and-poll path is reserved for a manual, human-supervised smoke test (run by hand, with the real `google_jules_apikey` secret and a real GitHub source) — not part of `PYTHONPATH=. python3 -m unittest tests.test_branch_features -v`.
- `resource_guard.yaml` — machine-specific list of systemd `--user` services paused for the duration of every `triapi dispatch` run and resumed afterward (Phase 12), so Tier 4's local Ollama gets the shared iGPU/RAM without contention. Not portable to another deployment; empty/missing file just disables the guard. `unload_other_ollama_models: true` (2026-08-17) — complementary, separate mechanism layered on top of `pause_services`: force-unloads any other Ollama-resident model via the API (`GET /api/ps` then `POST /api/generate` with `keep_alive: 0`) immediately before every `triapi dispatch`, so Tier 4's configured model gets the full shared iGPU/RAM budget. Defaults to `true` (also when the file or key is absent — the loader defaults on); set it to `false` to disable model-unloading while keeping the systemd pause list active.
- `secrets.example.yaml` — plaintext template documenting required secret keys (`deepseek_api_key`, `ollama_host`, `google_ai_studio_api_key`, `google_jules_apikey`), no real values, safe to commit.
- `secrets.enc.yaml` — sops/age-encrypted real secrets. **As of 2026-08-17, local-only and gitignored, NOT committed** (a full `git filter-repo` history purge removed the previously-committed ciphertext from every past commit — see `ARCHITECTURE.md`). Edit with `sops config/secrets.enc.yaml`; the file must be created locally (from `secrets.example.yaml`'s template, then `sops -e -i`) on any new machine, since it no longer ships with `git clone`.

## knowledge/
- `lessons.jsonl` — committed failure-pattern knowledge store (deliberately *not* under `logs/`, which is gitignored wholesale). One JSON object per line with schema `{id, date, category ("bug_fix"|"unresolved_pattern"), component, bug_description, what_went_wrong, fix_description, tags[]}`. Seeded from real historical TriAPI bugs; appended at runtime by `scripts/lessons.add_lesson()` (including auto-capture from `orchestrator.human_handoff()`). Consumed cheaply/locally by `select_relevant()` keyword overlap — no LLM call — and folded into tier edit prompts as a "## Known past mistakes..." do/don't block.
- `hivemind.md` — central repository of reusable, stripped-down code snippets with XML-wrapped `<triapi_snippet>` blocks. Parsed at runtime to search for patterns matching the task description and file extension, and injected into Tier 4's prompt as reference.
- `TECH_DEBT.md` — record of accumulated technical debt from judge rejections where the fix-forward build loop failed to compile, storing the file path, file content hash, and reason.

## scripts/
- `secrets_loader.py` — `load_secrets()` shells out to `sops -d` to decrypt `config/secrets.enc.yaml` into a dict at runtime. Never logs values.
- `config_loader.py` — `load_tiers()` loads and validates `config/tiers.yaml`, raises `ValueError` if required top-level keys are missing. `REQUIRED_KEYS` includes both `tier_1_planner` (plan-authoring) and `tier_1_manager` (repair dispatch) — added `tier_1_manager` 2026-08-23 after finding it was missing and a malformed/absent block for the tier that actually drives Tier 1 repair went uncaught. `load_resource_guard_services()` (Phase 12) loads `config/resource_guard.yaml`'s `pause_services` list, returning `[]` (not an error) if the file is missing -- optional, machine-specific. `load_unload_ollama_models_flag()` (2026-08-17) reads the same file's `unload_other_ollama_models` boolean, returning `True` by default (missing file or missing key both default on, per explicit instruction) -- feeds `cmd_dispatch`'s decision whether to call `resource_guard.unload_other_ollama_models()`.
- `llm_client.py` — single dispatch point for every tier's model call: `execute_llm(provider, endpoint, api_key, model, prompt, system_prompt, is_tier4=False, effort=None)` routes to `_call_claude_cli()` (provider `cli`), `_call_gemini_api()` (`google`), or `_call_openai_api()` (OpenRouter/DeepSeek/Ollama/any OpenAI-compatible endpoint) — no hardcoded model strings anywhere in tier scripts, all provider/model/effort selection is config-driven (hot-swappable via `config/tiers.yaml`, or a per-call `--model` override where the caller exposes one). `_call_claude_cli()` (2026-08-23 fix) now passes `--model <model>` and `--effort <level>` to `claude -p` when given (previously ignored both, silently running whatever the CLI's own default was). `probe_models()` — pre-flight pings every tier's default model before a real dispatch (`triapi.py`'s `cmd_dispatch`, before `_breakdown_and_dispatch`); a probe failure raises `RuntimeError` and aborts the dispatch. **2026-08-23 fix:** now probes `tier_1_manager` (the Claude CLI tier that actually drives repair dispatch) in addition to `tier_1_planner` (OpenRouter, plan-authoring only) — previously only `tier_1_planner` was probed, so a real Claude-CLI outage/misconfig would sail through undetected.
- `state.py` — per-task escalation state (`logs/state/<task_id>.json`): `read_state`, `write_state`, `record_failure`, `clear_state`.
- `gemini_fallback.py` (Phase 14) — `post_generate_content(post_fn, endpoint, api_key, body, models, timeout)`: calls `generateContent` against each model in `models` in order, advancing only on confirmed per-model quota exhaustion (`is_quota_exhausted()`: 429 + `error.status == "RESOURCE_EXHAUSTED"`), never on other failures (those return immediately for the caller's own retry/backoff handling). Records every attempt via `budget_guard.record_gemini_call(model)`. Shared by `dispatcher.py`'s breakdown and `tier2_escalate.py`'s repair calls — both previously gave up (or instantly re-hit the same exhausted model) the moment one model's daily allowance was spent.
- `content_guard.py` (Phase 13a) — `check_write(task_id, target_path, new_content)`: refuses a write to an *existing* file if the proposed replacement retains fewer than 50% of its original non-blank lines (below `MIN_RETENTION_RATIO`, only checked once a file has at least `MIN_LINES_TO_CHECK`=15 lines). Every tier's write goes through this before landing on disk. On refusal the original is left untouched and the rejected content is saved to `logs/rejected_writes/<task_id>.txt` for review. Brand-new files always pass (nothing to lose).
- `edit_blocks.py` (Phase 13b) — SEARCH/REPLACE-block patch format + `apply_edit_blocks(original, response_text)` for edits to an existing file: parses one or more `<<<<<<< SEARCH / ======= / >>>>>>> REPLACE` blocks out of a model's response and applies them via exact-text matching (fails closed — returns `None` plus a reason — if a SEARCH block doesn't match the current file exactly once, rather than guessing). Also fails closed the same way (Phase 28, 2026-08-25) when `response_text` itself is `None`/empty (a real DeepSeek response with null `message.content`), instead of raising `AttributeError` on `.strip()`. `build_edit_prompt_header(target_name, lessons_block="")` is the shared instruction text every tier uses when the target already exists; optional `lessons_block` (from `scripts/lessons.format_lessons_for_prompt`) is appended after `EDIT_INSTRUCTION` when non-empty. Replaces the old "output the complete corrected file" prompting for edits — that approach was asking every tier (including DeepSeek) to reproduce a whole file verbatim while fixing one thing, and it doesn't: two real files lost 500+ lines each on 2026-08-10 when the tiers "helpfully" regenerated shorter versions instead. New-file creation (nothing to diff against) still uses the old full-content path via `tier4_worker.extract_code()`.
- `lessons.py` — failure-pattern knowledge store API over `knowledge/lessons.jsonl`: malformed records are logged/skipped; appends are locked and deduplicated; `select_relevant(target_name, description, max_n=3)` uses weighted component/tag/description overlap and skips `unresolved_pattern` rows so they cannot crowd prompt injection; `format_lessons_for_prompt(lessons)` renders the prompt block; CLI supports manual category-aware capture. Runtime `human_handoff` captures go to gitignored `logs/handoff_lessons.jsonl` via `add_lesson(..., path=HANDOFF_LESSONS_PATH)`, not the committed store.
- `hivemind_util.py` — parses structural pattern templates from `knowledge/hivemind.md`'s `<triapi_snippet>` blocks, and filters/retrieves them via `search_hivemind(task_description, file_extension)` for injection into Tier 4 prompts based on word-overlap and language matching.
- `critique.py` — advisory diff-quality critic for Tiers 3/1/2. `critique_diff(...)` shells out to `claude -p`, is budget guarded, validates model JSON defensively, normalizes verdict against the configured threshold, and cost-logs ok/skipped/error outcomes. Malformed critique output is an advisory error and cannot abort dispatch.
- `judge.py` — evaluates task design via Tier 3 (DeepSeek) using `evaluate_design()`. Enforces JSON-only output with robust sanitization and a fail-closed single retry on parse/request failure (unless skipped during peak-hours). Also provides `extract_pattern()` to securely write approved snippets into `knowledge/hivemind.md` with file-level locking (`fcntl.flock`).
- `self_fix.py` — fail-safe structured crash capture under `logs/triapi_bugs/`, traceback-source extraction, planner reuse for TriAPI-only fix plans, and creation of human-approval-gated `self_fix_drafted` runs. It has no import-time exception-hook mutation and never auto-dispatches.
- `tier4_context.py` — shared module defining the Tier-4 context-size-ceiling constant `TIER4_MAX_CONTEXT_CHARS = 73728` (24576 tokens * 3 chars/token), imported by `scripts/dispatcher.py` and `scripts/content_guard.py` to avoid circular imports.
- `tier4_worker.py` — local Ollama drafting + build-loop worker, exposes callable `run(...)` (used directly by `orchestrator.py`) and a CLI `main()`; tracks consecutive build failures via `state.py`, escalates once `escalation_rules.tier4_to_tier3.threshold` is hit. **1-attempt oversize escalation (2026-08-19):** `_tier4_fail()` gained an `is_oversize_failure: bool = False` parameter that escalates after 1 failure instead of the configured threshold; passed `True` from the `run_build()` timeout path (output starting `"Command timed out after"`) and the truncated-response ("unterminated code fence") path, since both indicate the target file itself is too large for one Tier 4 generation window rather than an ordinary fixable build error — an unrelated `build_failed` keeps its full 2-attempt budget. Also owns `extract_code()` (fenced-code extraction, used only for brand-new files as of Phase 13b), `run_build()`, and `build_context_blob(paths, workdir)` (Phase 11 — reads other repo files a task references into a labeled read-only block for grounding, capped at 20K chars/file), all reused by every other tier. `run()` branches on whether the target already exists: existing files go through `edit_blocks.apply_edit_blocks()` (Phase 13b) then `content_guard.check_write()` (Phase 13a) before writing; **2026-08-23 correction:** `run()` no longer catches exceptions around its `llm_client.execute_llm()` call at all — a systemic/connectivity error (Ollama down, timeout, HTTP error) now propagates out of `run()` and is caught by `orchestrator.run_task()`'s own wrapper, which crashes the pipeline (`raise`), matching how tiers 1-3 fail hard on the same class of error via their `{"status": "error"}` -> `orchestrator` `RuntimeError` path. Previously `run()` swallowed `requests.RequestException`/`Exception` into an ordinary `_tier4_fail()` build_failed/escalate result, silently defeating the fall-fast/fall-hard design for Tier 4 specifically (orchestrator's own comment already said an exception here "should crash the pipeline," but it was unreachable). The older note below ("a `requests.RequestException` ... is caught and treated as a build failure") is superseded by this fix. `call_ollama()` returns the full response dict (not just `["response"]`) so `run()` can log `prompt_eval_count`/`eval_count` to `logs/cost_log.jsonl` (Phase 15) — previously the only tier with zero token accounting, since local inference has no per-call bill to justify logging it. Edit-mode prompts now fold in `lessons.select_relevant`/`format_lessons_for_prompt` via `build_edit_prompt_header(..., lessons_block=...)`.
- `tier3_escalate.py` — DeepSeek escalation client: stable system-message prefix (instructions + context-blob + file contents, Phase 11) + volatile stderr user message for prefix-cache hits; applies the returned fix via `edit_blocks.apply_edit_blocks()` then `content_guard.check_write()` (Phase 13, the target always exists by the time Tier 3 runs since Tier 4 always drafts first) — a rejected/unappliable fix returns `status: "fix_rejected"` instead of writing. A null/empty DeepSeek `message.content` (Phase 28, 2026-08-25) is logged with `finish_reason`/whether `reasoning_content` was populated instead, still logs cost when a usage block exists, and returns the same `fix_rejected` shape. Escalate() also logs cache-hit/miss/output tokens + cost (partial where pricing is unverified) to `logs/cost_log.jsonl`. The `requests.post()` call plus its `raise_for_status()` are now both wrapped in one `try/except requests.RequestException` (2026-08-13) returning a normal `status: "error"` result instead of crashing — previously the raw POST had no exception handling at all, and the status-check's own `except requests.HTTPError` logged then re-raised anyway, so any DeepSeek-side failure (a real Gemini 503 exposed the identical bug in `tier2_escalate.py` first) would have taken the whole unattended dispatch process down. Edit-mode header also folds in relevant lessons keyed on `target_path.name` (empty description — this path has no task description in scope).
- `tier1_escalate.py` — Tier 1 Manager escalation client. Uses `llm_client.execute_llm()` to dispatch requests based on `config["tier_1_manager"]`. Defaults to the `cli` provider (Claude Code), model `claude-sonnet-5`, `effort: high` (2026-08-23: `tier1.get('effort')` is now passed through to `execute_llm()`, which forwards it to `claude -p --model ... --effort ...` — previously the CLI invocation had no `--model`/`--effort` flags at all, so it silently ran on the CLI's own default rather than a verified Sonnet 5 high). When using the Claude CLI, the prompt (target file contents + context_blob) is piped via **stdin** (`input=prompt`), not passed as a CLI argv token (Phase 16) — passing it as `-p prompt` hit the kernel's `execve()` argument-list size limit for real on 2026-08-12 (`OSError: [Errno 7] Argument list too long`). The OpenRouter integration (when tested) proved that `stealth/ox-alpha` fails with a 429 when processing large repair prompts due to an upstream `upstream_provider_shared_pool` limit, not a simple retriable throttle, meaning fallback or robust model choice is required. Must only be called after `budget_guard.check_tier1_ok()`. Logs `cost_usd: 0.0` (actual, subscription-covered) alongside `notional_cost_usd` (what it would've cost on metered billing) when using the CLI. Prompt takes an optional context-blob (Phase 11); response applied via `edit_blocks`/`content_guard` same as Tier 3. Edit-mode system prompt folds in lessons the same way as the other tiers.
- `tier2_escalate.py` — Gemini escalation client via Google AI Studio REST API (`google_ai_studio_api_key`), mirrors `tier3_escalate.py`'s structure (including the Phase 11 context-blob and the Phase 13 edit-block/content-guard write path). Must only be called after `budget_guard.check_tier2_ok()`; calls `budget_guard.record_gemini_call()` after every attempt. `escalate()`'s `gemini_fallback.post_generate_content()` call and its `raise_for_status()` check are now both exception-guarded (2026-08-13) — a real `503 Server Error` propagated all the way up through `orchestrator.run_task()`/`dispatcher.dispatch()` and killed a whole unattended dispatch process (`raise_for_status()`'s `except requests.HTTPError` previously logged the error and then re-raised it anyway, which is not a fix). Both failure points now return a normal `status: "error"` result instead, matching how Tier 1/Tier 4 already treat their own request failures. Edit-mode system instruction folds in lessons via `select_relevant`/`format_lessons_for_prompt`.
- `budget_guard.py` — pre-flight checks before Tier 1/Tier 2 calls: `check_tier1_ok()` refuses if `ANTHROPIC_API_KEY` is set (would force metered billing over subscription); `check_tier2_ok()` refuses if the next call would exceed `tiers.yaml`'s `tier_2_manager.pricing.free_tier_rpm/rpd` (tracked in `logs/gemini_usage.jsonl`, currently unverified placeholder limits). `check_tier1_manager_ok(config)` (2026-08-14) — separate feature on/off switch for Tier 1's repair role, checked in `orchestrator.run_task()` alongside `check_tier1_ok()`; refuses if `tier_1_manager.enabled` is `false` in `config/tiers.yaml` (default `true`) or if the `TRIAPI_NO_TIER1` env var is set (set by `triapi dispatch --no-tier1`, or manually). `check_tier3_peak_hours_ok()` — refuses the Tier 3 call during the DeepSeek V4 peak windows: it reads `tier_3_debugger.peak_hours_utc` from `tiers.yaml` (defaulting to the two DeepSeek V4 peak windows if absent, one of which is 06:00-10:00 UTC) and uses `zoneinfo.ZoneInfo("America/Los_Angeles")` purely for DST-correct local-time reporting — the actual peak-window comparison is done in UTC. `check_jules_ok()`/`record_jules_call()` (2026-08-17) — same daily-limit-guard shape as Tier 2's RPM/RPD check but for Jules: refuses if the next task would exceed `jules_tester.daily_task_limit` from `tiers.yaml` (tracked in `logs/jules_usage.jsonl`); advisory-only elsewhere in the pipeline (Jules is never a repair tier), but this check itself is a hard stop like the others.
- `jules_client.py` (2026-08-17) — REST-only client for Google's async coding agent (`jules.googleapis.com/v1alpha`), auth via `X-Goog-Api-Key` (`secrets_loader.load_secrets()["google_jules_apikey"]`, never logged — an initial dispatch of this file read the wrong key name, `jules_api_key`, which doesn't exist in `secrets.enc.yaml`; the pipeline's own mocked tests used the same wrong name and so didn't catch it, a fabricated-fact bug caught and fixed by hand 2026-08-17, same class as the `gemini-3-pro` incident). **REST-only by design, not CLI**: confirmed live during planning that the `jules` CLI has no machine-readable status/output and no explicit branch-targeting flag — `jules remote pull` only returns file diffs, `jules remote list --session` is unparseable plain text with no `--json` option, and a CLI-created session's `sourceContext` showed no branch info at all, versus a REST-created session's explicit `githubRepoContext.startingBranch`. **Confirmed real field names (live-verified 2026-08-17):** `POST /sessions` body uses `sourceContext.githubRepoContext.startingBranch` — public Jules docs claim `sourceContext.githubBranch`, which is confirmed WRONG against the live API (`400: Unknown name "githubBranch" at 'session.source_context': Cannot find field`). `get_final_message()` extracts the result by reverse-scanning the activity feed for the last `agentMessaged.agentMessage` (also initially miscoded as `agentMessaged.get("message")` — fixed alongside the secret-key bug, and now pinned by a direct regression test against the real confirmed-live activity shape, `JulesGetFinalMessageTests`), falling back to `progressUpdated.description`, then `""`, if no agent message is present. `run_jules_test()`/`main()` provide a manual/CLI smoke-test entry point (create session → `poll_session_result()` to a terminal state) and are also what `triapi.py`'s post-dispatch hook calls — despite an earlier, incorrect docstring claiming otherwise, this path IS used by the automated dispatch pipeline (see `triapi.py`'s entry below), just never with a real live call during the automated test suite.
- `cost_report.py` — `report(task_id)`/`format_report()` (unchanged): per-task actual $ vs. notional/subscription-covered cost. Phase 15 added a second, whole-run report alongside it: `run_summary(entries)` aggregates `logs/cost_log.jsonl` by tier (tokens + actual/list-price $, reading each tier's own field names via `_tier_tokens()` — Claude's `input_tokens`/`output_tokens`, Gemini's `prompt_tokens`/`cached_tokens`, DeepSeek's `cache_hit_tokens`/`cache_miss_tokens`, Ollama's `prompt_eval_count`/`eval_count`); `claude_baseline_cost()` prices that same total volume as if a single Claude model (Sonnet 5 or Opus 5, hardcoded `CLAUDE_PRICING`) had done every item alone, no tiering — the "let Claude Code do all the work" comparison; `deepseek_flash_cost()` prices Tier 4's local-Ollama volume as if it had run on Tier 3's DeepSeek instead (reads `config/tiers.yaml`'s own verified pricing, not a re-guess); `gpu_amortized_cost()` compares that same local volume against the amortized cost of GPU ownership (hardware price ÷ lifetime hours × hours used, plus electricity) — deliberately CLI-overridable assumptions (`--gpu-price`/`--gpu-lifetime-years`/`--gpu-power-watts`/`--electricity-rate`/`--gpu-hours`, all defaulted but never asserted as fact, since actual GPU usage-duration has no reliable signal in this repo). `format_run_report()` renders all of it with ANSI color/box-drawing (auto-disabled when stdout isn't a tty) so the headline savings number visually pops. `triapi.py`'s `_breakdown_and_dispatch()` prints this automatically after every dispatch run, right after the existing per-item cost lines.
- `orchestrator.py` — `run_task(...)` ties Tier 4 (draft+build loop) → Tier 3 (patch + plain rebuild) → Tier 2 (budget-guarded, patch + rebuild) → Tier 1 (budget-guarded, patch + rebuild) → human handoff. Tier 1 is deliberately last (2026-08-17 reorder): it's the strongest automated repair tier, so it's reserved for problems Tier 2 (Gemini) couldn't already resolve rather than spent ahead of it; this only reorders the *repair* chain, not `tier_1_planner`'s separate initial-planning role. A new Tier 3 peak-hours gate (`budget_guard.check_tier3_peak_hours_ok()`) runs immediately before the Tier 3 call; when it refuses, the skip is logged at INFO (not WARNING) and falls through to Tier 2 exactly like a normal Tier 3 miss. Logs a warning with the specific reason whenever a downstream tier returns `status: "fix_rejected"` (Phase 13 — content-guard or edit-block-apply refusal) instead of silently discarding it, so a rejected fix is visible in `triapi.log` even though the retry/escalation control flow doesn't otherwise change (the next rebuild attempt naturally fails again since nothing was written, falling through to the next tier on its own). Prints a cost report at the end of every run. Downstream tiers only patch the file and rebuild — they never trigger another Ollama draft, which would overwrite their fix. This is the execution primitive `dispatcher.py` calls per checklist item. Also owns the public `human_handoff(task_id, reason, detail)` writer, reused by `dispatcher.py` for failed git items, and `verify_task(task_id, build_cmd, workdir)` (Phase 10) for `verify_only` items — runs `build_cmd` as-is with no draft step, straight to human handoff on failure, no Tier 1/2/3 escalation. `human_handoff()` also auto-appends an `unresolved_pattern` lesson to gitignored `logs/handoff_lessons.jsonl` (not the committed `knowledge/lessons.jsonl`) via `scripts.lessons.add_lesson()`. After each successful Tier 3/1/2 rebuild, `_critique_and_maybe_revise()` optionally scores the diff via `scripts.critique` and may request up to `max_revision_attempts` `revision_note` passes (advisory only — unexpected exceptions cannot abort a passing item or change `resolved_by`). Also takes an optional `context_files` list (Phase 11), builds one `context_blob` via `tier4_worker.build_context_blob()` per item and reuses it across every tier attempt. Tier 1's block is also gated by `budget_guard.check_tier1_manager_ok(config)` (2026-08-14) alongside the existing `check_tier1_ok()` budget check — either refusing skips Tier 1 for that run, printed the same `[BUDGET GUARD] Tier 1 skipped: ...` way.
- `agents_md_gate.py` (2026-08-16) — enforces "one Tier 1 plan per repo until it's checked off": each approved plan lives as an HTML-comment-delimited `<!-- triapi:plan run_id=... start/end -->` block in the *target* repo's own `AGENTS.md` (not TriAPI's), so multiple runs' plans can coexist and each is tracked independently.
  - `append_plan(project_dir, run_id, plan_text, appended_date)` — writes the approved plan as a new block, creating `AGENTS.md` with a minimal header if it doesn't exist yet.
  - `find_incomplete_plan(project_dir)` — looks at only the most recently appended block and returns its `run_id`/unchecked-step count if it still has any `- [ ] ` checkbox line, else `None`; a block with zero checkboxes at all (planner didn't use checkbox syntax) fails open rather than blocking forever, since there's nothing to check off.
  - `mark_plan_complete(project_dir, run_id, breakdown_item_count)` (2026-08-19) — flips every `- [ ]` to `- [x]` inside that run's block only (leaves other blocks/prose untouched), but only when the block's own checklist-item count (`_CHECKLIST_ITEM_ANY_RE`, counting both `[ ]` and `[x]`) is not greater than `breakdown_item_count`; if the breakdown captured fewer items than the block declares (the partial-breakdown symptom from run `20260819-063339-9d23c7`), it refuses to check anything off, logs a warning, and returns `False` without writing the file. Still returns `False` as a no-op if the block or file can't be found (e.g. hand-edited AGENTS.md) rather than raising.
  - Callers: `cmd_plan()` in `triapi.py` calls `find_incomplete_plan()` before starting a new session and refuses (printing the blocking run_id and how to resume/inspect it) unless `--refactor` is passed; `_breakdown_and_dispatch()` calls `mark_plan_complete()` only when a run's final `state["status"]` is `"completed"` (all items resolved) — a `stopped_on_failure` run leaves the gate closed, which is the intended block. `planner.py`'s `SYSTEM_PROMPT` requires every step to be a literal `- [ ] ` checkbox line so this stays parseable.
- `planner.py` — Interactive planner (distinct from `tier1_escalate.py`'s repair role): `plan_turn(message, project_dir, session_id)`. The provider is now decoupled and read from `tier_1_planner` (Phase 18) — currently OpenRouter `stealth/ox-alpha`, primary by deliberate choice. If the provider is `cli`, it runs a `claude -p --resume` conversation with native read-only tools (`Read,Glob,Grep`). For non-CLI providers (e.g., OpenRouter, DeepSeek), it automatically enriches the prompt with a context blob (`AGENTS.md`, `PLAN.md`, `README.md`) to ground the LLM since cloud models lack native tools. **Content-filter sanitization + CLI fallback (2026-08-23):** the enriched context blob legitimately contains `git@github.com:...` SSH URLs (from README.md/AGENTS.md), which OpenRouter's free `stealth/ox-alpha` content filter flags as PII and 403s with `"Request blocked by content filter: [EMAIL]"` — confirmed live, this bricked `triapi plan` entirely. `_sanitize_for_content_filter()` obscures email-like tokens (`user@host` -> `user(at)host`) in the copy of the prompt sent to non-cli providers only (the CLI path is untouched). On any primary-path failure (this filter, a 403/429, connectivity), both the `cli` branch's parse failure and the non-cli branch's exception now fall back to `_fallback_to_tier1_manager_cli()`, which calls `tier_1_manager`'s Claude CLI (Sonnet 5, high effort) — this replaces two dead calls to a `llm_client._fallback_request()` that never existed in `llm_client.py` (would have raised `AttributeError` if ever hit). Verified live end-to-end 2026-08-23: a real `plan_turn()` call returned `status: ok` via the OpenRouter primary path after sanitization. Nothing is built until the user approves a turn's output.
- `dispatcher.py` — Tier 2 as manager (distinct from `tier2_escalate.py`'s repair role): breaks an approved plan into phases of concrete per-file checklist items and dispatches them one at a time, in order, through the existing repair pipeline (`orchestrator.run_task()`). Must only be called after `budget_guard.check_tier2_ok()`. **File-size ceiling guard (2026-08-19):** `_enforce_file_size_ceiling()` (with `TIER4_MAX_CONTEXT_CHARS`, derived from Tier 4's `num_ctx=24576`) runs in `breakdown_plan()` alongside the existing test-context and import-order guards, rejecting the plan if any file item's existing on-disk content already exceeds Tier 4's context window — closes real 300s Tier-4 timeouts on oversized files.
  - **Phase split:** `_split_plan_by_phase()` splits plan markdown into per-phase chunks on `_PHASE_HEADER_RE = re.compile(r"^(?:#{1,6} |\d+\.\s+Phase\b)", re.IGNORECASE)` — any ATX heading depth (`#`–`######`) or a numbered top-level `N. Phase ...` marker (found for real 2026-08-12: a `### Phase 2` header silently vanished its whole phase when only `## ` was recognized; run `20260819-063339-9d23c7` (2026-08-19): a plan with numbered `1. Phase 1 -- ...` headers and no `#` at all collapsed into one chunk, dropping every phase after the first). The companion filter `_CHECKLIST_ITEM_RE = re.compile(r"^\s*(?:[-*]|\d+\.)\s+", re.MULTILINE)` accepts any bulleted/numbered list item, checkbox syntax optional (a numbered `1. [ ]` plan, and later a plain `1. **file** — ...` plan with no `[ ]`, were each dropped as "no checklist items" for real), so only chunks with no list markers (e.g. a leading title block) are discarded.
  - **Breakdown:** `breakdown_plan(state)` (Phase 10 — takes the run `state` dict, not raw plan text) converts an approved plan into `state["breakdown"] = {"phases": [{"name", "items": [ITEM]}]}` **one phase at a time**, saving state after each phase so a partially-broken-down run resumes instead of restarting; post-breakdown guards now run only on fresh chunk assembly, not on resume of an already-populated breakdown (resolving the known limitation previously documented in CARRYOVER.md). Each phase goes through Gemini's JSON mode with up to 3 retries (malformed JSON from Gemini is a real, observed, stochastic failure) and `_parse_retry_after()` backoff (honors a 429 body's own suggested delay, e.g. "Please retry in 27.33s", else 5s); a raw `requests.RequestException` is folded into the retry loop, not propagated. A non-empty `plan_text` that yields zero total items is a hard error, never a vacuous `status: "ok"`. ITEM is a file item `{"description", "target", "build_cmd", "verify_only", "context_files"}` (`context_files`, Phase 11 — other repo files this step's description references, for grounding) or a git item `{"description", "git": {"action", ...}}`.
  - **Context grounding:** `_backstop_context_files(item)` (Phase 13c) regex-extracts path-like tokens from the item's own description (with or without backticks; Gemini doesn't reliably preserve the source plan's backticks) and unions them into `context_files`, deterministically, as a floor under Gemini's compliance — a real 96-item breakdown left every item's `context_files` empty, including items whose description named another file to follow. **Test-file guard (2026-08-19):** `_apply_test_context_guard()` (with `_TEST_TARGET_RE`/`_find_anchor_test_file()`) auto-adds the same-stem `scripts/<name>.py` companion to `context_files` for any item targeting `tests/test_<name>.py` when that source file exists, always ensures at least one existing `tests/test_*.py` anchor (preferring `tests/test_branch_features.py`), and rejects the plan at approval time if no anchor exists at all — closing the two real 2026-08-18 incidents (`tests/test_hivemind_util.py` missing `scripts/hivemind_util.py` context; `tests/test_judge.py` missing a style anchor, causing 4 escalation attempts to default to unavailable `pytest`).
  - **Build commands & verification items:** `_normalize_build_cmd(build_cmd, project_dir)` rewrites a bare `python`/`python3`/`pytest` at a command/sub-command boundary (including after a leading `!` and/or `VAR=value` env assignments) to `uv run python`/`uv run pytest`, only when the target project has a `pyproject.toml`/`uv.lock` (TriAPI itself has neither); applied to every item's `build_cmd` in `dispatch()`. `BREAKDOWN_SYSTEM_INSTRUCTION` (Phase 16) forbids generating a standalone verification script as an ordinary file item — a file item's contract lets any tier freely rewrite `target` on failure, and applied to a verification script a stuck worker loosens the script's own assertion instead of fixing the real bug (observed for real 2026-08-12); verification content must instead be baked into `build_cmd` as an immutable heredoc under a `verify_only: true` item, never drafted. Empty `build_cmd` (a non-code file item) becomes `test -f <target>`, not the code-project default build.
  - **Dispatch loop:** `dispatch()` walks items sequentially — git items to `git_ops` via `_dispatch_git_item()`, `verify_only` items to `orchestrator.verify_task()` (Phase 10: pure checks, e.g. "run the test suite", never go through the file-draft path), everything else to `orchestrator.run_task()`; persists `logs/runs/<run_id>.json` after every item via atomic `save_run()` (temp file + rename, so a process kill can't corrupt state), stopping on the first non-success item (retried, not skipped, on resume). After each successful regular item, a judge/fix-forward loop runs: `judge.evaluate_design()` scores the diff, and a DRY/SOLID rejection triggers a single-shot Tier 3 fix-forward rewrite in `handle_fix_forward()` — reverting to a SHA-256 snapshot and logging tech debt to `TECH_DEBT.md` if the rebuild fails, or extracting structural snippets to `hivemind.md` via `judge.extract_pattern()` if the judge approves.
  - **Regression detection (Phase 17, 2026-08-13):** every successful regular item's `state["results"]` entry carries `"target"`/`"build_cmd"`/`"content_hash"` (the last populated only on success); after each success `_check_for_regressions(state, task_id)` hashes every earlier-successful item's target (`regression_guard.hash_file()`, cheap, no subprocess) and only re-runs a possibly-expensive `build_cmd` for a file whose hash actually drifted — a still-failing drifted file writes a `state["regression_flags"]` entry, calls `orchestrator.human_handoff()`, and hard-stops the dispatch (`stopped_on_failure`), while a drifted-but-still-passing file just refreshes its stored hash. `_recheck_regression_flags(state)` re-verifies unresolved flags once at the start of `dispatch()` before resuming. Known limitation: cross-file regressions (item N edits shared code that breaks item M's untouched file) aren't covered, deliberately, to keep the cost bounded (hashing is O(n); re-running every prior `build_cmd` unconditionally would reintroduce the O(n²)/full-suite-every-time cost).
  - **Import-order guard (2026-08-19):** `_enforce_module_import_order()`/`_extract_imported_modules()`/`_SCRIPTS_TARGET_RE`/`_IMPORT_RE` — wired into `breakdown_plan()` after all phases are broken down, deterministically reorders any plan item that imports a `scripts/<name>.py` module before the item that creates it, closing the real 2026-08-18 incident where `dispatcher.py` added `from scripts import tech_debt` before the phase creating `scripts/tech_debt.py`, breaking `triapi`'s own CLI boot. Pre-existing modules on disk are skipped; unresolvable circular orders return an error instead of looping.
- `regression_guard.py` (Phase 17) — `hash_file(path: Path) -> str | None` (sha256, `None` on `FileNotFoundError`) and `check_regressions(state: dict, project_dir: str) -> list[dict]` (pure detection only, never runs `build_cmd` itself -- that's `dispatcher.py`'s job so it can decide whether the cost of re-running is warranted). Used exclusively by `dispatcher.py`'s regression-detection wiring described above.
- `mock_patch_lint.py` (2026-08-19) — static-analysis lint for `mock.patch` target/import binding mismatches: `find_issues()` AST-walks a test file for `mock.patch("dotted.target")`/`mock.patch.object(...)` calls and flags any whose target is the name's *defining* module rather than the *importing* module that actually looks it up at call time (a `from <defined_in> import <attr>` name-binding import), so patching the quoted target silently leaves the real function live — the bug class that let a real Ollama network call slip through via `scripts.orchestrator.run_task` / `scripts.dispatcher.py`. CLI: `python3 scripts/mock_patch_lint.py <test_file> [--repo-root ...]` — prints `line N: ...` issues to stderr and exits 1 when found, prints `OK`/exits 0 otherwise.
- `tech_debt.py` — manages structural tech-debt logging. Appends file path, current SHA-256 hash, and rejection reason to `knowledge/TECH_DEBT.md` using `log_tech_debt()`. Provides `check_staleness()` to verify if a logged file has been edited/deleted, skipping stale entries on subsequent runs.

- `git_ops.py` — `clone(url, path)`, `pull(repo_dir)`, `push(repo_dir, message, branch=None)`. Direct shell git commands, logged via `tri_logging`. Safety rails: never force-push; `push()` never lands directly on `main`/`master` unless a plan step explicitly names that branch — otherwise creates a new `triapi/<dirname>-<timestamp>` branch. Every invocation strips credential helper/askpass (`-c credential.helper= -c core.askpass=`) so an auth failure is immediate and clear rather than hanging. **Automatically rewrites `https://github.com/owner/repo` URLs to SSH** (`git@github.com:owner/repo.git`) — in `clone()` and via `_ensure_ssh_remote()` before every `pull()`/`push()` — since HTTPS has no working non-interactive credentials in this environment; confirmed end-to-end (Phase 9.2) with zero manual intervention needed against the real TriAPI GitHub repo. `get_github_owner_repo(repo_dir)` (2026-08-17) — parses `origin`'s URL (SSH or HTTPS github.com form) into `(owner, repo)`, `None` if it isn't a github.com remote. Added because `triapi.py`'s post-dispatch Jules step was building the Jules `source` from `config/tiers.yaml`'s hardcoded `jules_tester.source` (TriAPI's own repo) regardless of which repo the run actually dispatched against — a run against oh-my-llama would have pushed oh-my-llama's branch and then asked Jules to test TriAPI's repo instead. `cmd_dispatch`'s finalization now calls this against `state["project_dir"]` and only falls back to the config default when the origin isn't a github.com remote. Note this reflects a deliberate policy call (2026-08-17): TriAPI's dispatch pipeline pushes on `completed` regardless of a target repo's own no-push convention (e.g. oh-my-llama's `docs/Agent/CARRYOVER.md`) — TriAPI's own behavior takes precedence over a target repo's local doc.
- `triapi.py` — CLI entry point (installed as the real `triapi` command via `~/.local/bin/triapi` symlink). Subcommands: `plan [--refactor]` (interactive, foreground-only; refuses via `agents_md_gate.find_incomplete_plan()` — see that file's entry above — unless `--refactor` is passed), `dispatch [--background] [--no-tier1]` (can run detached, safe against SSH/Tailscale disconnects; `--no-tier1` sets `TRIAPI_NO_TIER1=1` in the process environment before dispatching — inherited automatically by the detached `--background` child, since its `subprocess.Popen` call passes no `env=` override), `status`, `list`, `self-fix list|queue|show|approve`, and `tech-debt` (verifies non-stale file hashes and dispatches outstanding tech debt entries from `TECH_DEBT.md` using synthetic state in `dispatch()`). `cmd_dispatch`'s non-background path (which the `--background` path also re-execs into) wraps `_breakdown_and_dispatch()` in `resource_guard.pause_services()`/`resume_services()` (Phase 12), try/finally so services resume regardless of run outcome; an uncaught exception is captured via `self_fix.capture_crash` then auto-queued unless the crashing run already carries `self_fix_bug_report` (recursion guard is that marker only — a normal TriAPI-rooted run still auto-queues). `cmd_status()`/`_breakdown_and_dispatch()` (Phase 17) print unresolved `regression_flags` (see `dispatcher.py`); each flag bundles a LIST of regressed items under `regressed_items`, not a single `task_id`/`target` on the flag itself -- crashed with `KeyError` the first time this fired for real against a multi-item regression (2026-08-13), fixed to iterate `f["regressed_items"]`. `cmd_dispatch` now also force-unloads other resident Ollama models (2026-08-17) right alongside `pause_services()`: when `load_unload_ollama_models_flag()` is true it resolves `keep_model` from `tiers.yaml`'s `tier_4_worker.default_model` mapped through `tier_4_worker.models` (e.g. `"qwen2.5-coder:14b-instruct-q8_0"` for `default_model: default`) and `ollama_host` from `tier_4_worker.endpoint`, calls `resource_guard.unload_other_ollama_models(keep_model=..., ollama_host=...)`, and logs the unloaded list at INFO. The whole flag-check/`load_tiers()`/call is wrapped in its own try/except, so any unexpected error (including an unreachable Ollama — already handled inside the function) logs a warning and cannot abort dispatch. `cmd_dispatch` also snapshots `ollama.service` state via `resource_guard.snapshot_ollama_state()` right after `pause_services()` (wrapped in try/except, defaulting to `None` on failure) and restores it via `resource_guard.restore_ollama_state()` in the existing `finally` block alongside `resume_services()`, guaranteeing restoration on success, caught exception, or uncaught crash.
- `resource_guard.py` — `pause_services(services)`/`resume_services(paused)` (Phase 12): stops/starts systemd `--user` services by name via `systemctl --user`, tracking only the subset that was actually active before pausing so it never resurrects something already off for an unrelated reason. Service list comes from `config/resource_guard.yaml` via `config_loader.load_resource_guard_services()`. Self-healing (Phase 12.1): a signal/`atexit` safety net resumes services on `SIGTERM`/`SIGINT`/normal exit even if the caller's own `try`/`finally` doesn't run; a lock file (`logs/resource_guard_lock.json`, gitignored) records what got paused and by which pid, so a hard `SIGKILL`/OOM-kill of the dispatch process gets healed automatically by the *next* call to `pause_services()` instead of leaving services down forever. `unload_other_ollama_models(keep_model, ollama_host)` (2026-08-17) — force-unloads every Ollama-resident model except `keep_model` from `ollama_host`: `GET {ollama_host}/api/ps` to list, then `POST {ollama_host}/api/generate` with `{"model": name, "keep_alive": 0}` per other model. Returns the list of names actually unloaded (matches `pause_services()`'s list-returning convention); intentionally has NO `resume_*` counterpart — Ollama lazily reloads on next use. Failure-proof by design: any `requests.RequestException` on the listing step logs a warning and returns `[]` (no crash, zero models unloaded), and a failing per-model unload logs a warning and continues with the rest rather than aborting. **Ollama service lifecycle (2026-08-19):** `snapshot_ollama_state(ollama_host, service="ollama.service")` records whether the service was active and which models were resident before a dispatch run, starting the service if it was inactive; `restore_ollama_state(snapshot, ollama_host)` reloads whatever was resident and stops the service again if it was inactive before (safe no-op on a `None` snapshot) — full lifecycle ownership for a `triapi dispatch` run's duration, restoring exactly the prior state on exit. See `triapi.py`'s entry above for the `cmd_dispatch` wiring.
- `tri_logging.py` — centralized logging used by every script above, **on by default**. `TRIAPI_LOG=0` disables, `TRIAPI_LOG_LEVEL` sets verbosity (default `INFO`), `TRIAPI_LOG_FILE` overrides the target (default `logs/triapi.log`). Named `tri_logging`, not `logging`, so it doesn't shadow the stdlib module.
- (no `mcp_server.py` — Phase 5 was skipped; Antigravity is no longer a dispatcher in this design, and `orchestrator.py`/`triapi.py` are already complete standalone entry points. A future MCP-style integration, if any, points toward Jules, not Antigravity.)

## tests/
- `test_mock_patch_lint.py` — regression tests for `scripts/mock_patch_lint.py` (the mock-patch target/import-binding-mismatch linter above): covers wrong vs. correct patch targets and CLI exit codes, using temporary fixture repos rather than the repo's own files. Split out from `tests/test_branch_features.py`, which had grown well past the size ceiling for further extension.
- `test_dispatcher_test_context_guard.py` — regression tests for `scripts/dispatcher.py`'s test-file context grounding guard (`_find_anchor_test_file`/`_apply_test_context_guard`): covers companion-script and anchor-test-file auto-inclusion, missing-anchor rejection, and no-fabrication/no-duplication behavior, using temporary fixture repos rather than the repo's own files. Split out as a new file per the "split out, don't keep extending `test_branch_features.py`" convention already used for `test_mock_patch_lint.py`.
- `test_import_order_guard.py` — regression tests for `scripts/dispatcher.py`'s module import-order guard (`_enforce_module_import_order`/`_extract_imported_modules`/`_SCRIPTS_TARGET_RE`/`_IMPORT_RE`): covers both `from scripts import X` and `import scripts.X` extraction, the exact 2026-08-18 incident shape (importer before creator gets reordered), no-op when already ordered or the module pre-exists on disk, git items skipped, and unresolvable circular imports returning an error string, using temporary fixture repos rather than the repo's own files. Split out as a new file per the same convention as `test_mock_patch_lint.py`/`test_dispatcher_test_context_guard.py`.
- `test_plan_phase_split_and_completion_guard.py` — regression tests for the 2026-08-19 plan-completion integrity bug: covers `scripts/dispatcher.py`'s `_split_plan_by_phase` now recognizing numbered `N. Phase ...` top-level markers (not just ATX headers) and `scripts/agents_md_gate.py`'s `mark_plan_complete` now refusing to check off AGENTS.md boxes when the breakdown captured fewer items than the block declares (run `20260819-063339-9d23c7`), using temporary fixture repos rather than the repo's own files. Split out as a new file per the same convention as `test_mock_patch_lint.py`/`test_dispatcher_test_context_guard.py`/`test_import_order_guard.py`.
- `test_ollama_service_lifecycle.py` — regression coverage for the `cmd_dispatch` Ollama snapshot/restore wiring (mocking `scripts.triapi.resource_guard.snapshot_ollama_state`/`restore_ollama_state` at their use site).
- `test_file_size_ceiling_and_oversize_escalation.py` — regression coverage for `scripts/dispatcher.py`'s `_enforce_file_size_ceiling` (rejects a plan item targeting an existing over-ceiling file, ignores small/nonexistent targets) and `scripts/tier4_worker.py`'s `_tier4_fail(..., is_oversize_failure=...)` 1-attempt escalation shortcut for timeout and truncated-response failures vs. the normal 2-attempt threshold for ordinary build failures. Fixture-repo pattern, split out per the same convention as the other dedicated test files above.

## logs/
- `state/` — per-task JSON state files (gitignored contents, dir kept via `.gitkeep`).
- `cost_log.jsonl` — per-call cost/usage log across all paid/metered tiers, one JSON line per call (gitignored).
- `gemini_usage.jsonl` — Tier 2 call timestamps, used by `budget_guard.check_tier2_ok()` to enforce free-tier RPM/RPD limits (gitignored).
- `escalations.jsonl`, `escalation_<task_id>.md` — final human-handoff records, written only when Tier 4→3→1→2 all fail to resolve a task (gitignored).
- `triapi.log` — centralized debug log from `tri_logging.py`, on by default; `tail -f` it live (gitignored).
- `runs/<run_id>.json` — persisted plan/dispatch state for `triapi`, updated after every item so a run survives SSH disconnects; `runs/<run_id>.log` is the raw output when dispatched with `--background` (gitignored).

## samples/
- `broken_build/` — fixture C++ project: `main.cpp` has a genuine compile error (copying a `std::vector<std::unique_ptr<Widget>>`, illegal since `unique_ptr` isn't copyable) plus `CMakeLists.txt`. Used for end-to-end pipeline verification (Phase 6) — a full production-config `orchestrator.py` run resolved it correctly at Tier 4 alone, $0 cost. `build/` (CMake output) is gitignored, regenerated by running the smoke test in `README.md`.

<!-- triapi:plan run_id=20260819-224114-9884f8 start -->
## TriAPI Plan (run 20260819-224114-9884f8, appended 2026-08-20)

Line numbers all match the queued plan exactly (SYSTEM_PROMPT at 36 vs "starts at line 40" — close enough, minor drift, not worth flagging). The queued plan in `queued_plans/triapi_items_1-3.md` is accurate against current disk state and matches CARRYOVER.md's directive. I'll present it as the plan, in the required checkbox format.

## Plan: TriAPI self-repo — CARRYOVER items #1, #2, #3

1. Phase 1: Fix `breakdown_plan()` re-running post-breakdown guards on resume
   - [x] In `scripts/dispatcher.py`, modify `breakdown_plan()` (`def breakdown_plan(state: dict) -> dict:` at line 664) so the three post-breakdown guard calls — `_enforce_module_import_order(state["breakdown"]["phases"], state["project_dir"])` (line 695), `_enforce_file_size_ceiling(state["breakdown"]["phases"], state["project_dir"])` (line 700), and `_enforce_no_raw_edits_to_encrypted_files(state["breakdown"]["phases"], state["project_dir"])` (line 705) — run only when this call performed fresh chunk-to-phase assembly, not on a resume of an already-fully-populated `state["breakdown"]`. Implementation: keep the existing `already_done = len(state["breakdown"]["phases"])` at line 675 (captured before the `for i, chunk in enumerate(chunks):` loop), and also capture `chunks = _split_plan_by_phase(state["plan_text"])`'s length (existing line 674) to compute `newly_broken_down = already_done < len(chunks)` before the loop runs. Wrap the three guard-call blocks (lines 695–709) plus their `save_run(state)` at line 710 in `if newly_broken_down:`, so they fire only when the loop appended at least one new phase this invocation, and are skipped when re-entered purely to resume a state whose `phases` already equals `len(chunks)` at entry (the AGENTS.md-size incident case). Do not alter the empty-plan/zero-items check at lines 723–734 or the final `return {"status": "ok"}` — both must still run unconditionally every call. Add a comment above the new `if newly_broken_down:` gate referencing CARRYOVER.md item #1 and explaining why. Verify: `python3 -m py_compile scripts/dispatcher.py`
   - [x] In `tests/test_file_size_ceiling_and_oversize_escalation.py` (or a new `tests/test_breakdown_resume_guard_skip.py`, matching this repo's one-file-per-guard-behavior test convention), add a regression test that: (a) builds a `state` with `state["breakdown"]["phases"]` already fully populated (`len(phases) == len(_split_plan_by_phase(state["plan_text"]))`) where one phase's item targets a file currently on disk above `TIER4_MAX_CONTEXT_CHARS`, (b) calls `breakdown_plan(state)` on this already-broken-down state, and (c) asserts it returns `{"status": "ok"}` (not blocked by `_enforce_file_size_ceiling`), since no fresh chunk-to-phase assembly occurred. Also keep/add a test asserting the guard still fires during a genuine fresh initial breakdown (`state["breakdown"]` starts `None` or partially populated, oversized target present), so the fix doesn't disable the guard outright. Verify: `PYTHONPATH=. python3 -m unittest tests.test_branch_features tests.test_file_size_ceiling_and_oversize_escalation tests.test_encrypted_file_edit_guard tests.test_dispatcher_test_context_guard -v`

2. Phase 2: Teach the planner correct `sops` syntax for this box's installed version
   - [x] In `scripts/planner.py`, edit the `SYSTEM_PROMPT` string constant (`SYSTEM_PROMPT = (` at line 36) to append a new paragraph stating: this box's installed `sops` is version 3.8.1 (confirmed via `sops --version`), which has NO `set` subcommand — `sops --help`'s COMMANDS list is only `exec-env`/`exec-file`/`publish`/`keyservice`/`groups`/`updatekeys`/`help`. Any plan step editing a secrets file in place MUST use the `--set` flag on the default (edit-mode) invocation, never the `sops set FILE key value` subcommand form. Include concrete working syntax: for a nested key, `sops --set '["key"][0] "value"' FILE`; for a top-level key, `sops --set '["key"] "value"' FILE`. State explicitly: "Never generate `sops set FILE key value` — that subcommand does not exist on this box's sops 3.8.1." Append as a distinct new paragraph; do not restructure or shorten existing paragraphs. Verify: `python3 -m py_compile scripts/planner.py`
   - [x] Confirm no test asserts on literal `SYSTEM_PROMPT` contents by checking `grep -rn "SYSTEM_PROMPT" tests/` (currently no matches). If any test does assert against `SYSTEM_PROMPT` contents, update that assertion to account for the new paragraph in the same step. Verify: `PYTHONPATH=. python3 -m unittest tests.test_branch_features tests.test_file_size_ceiling_and_oversize_escalation tests.test_encrypted_file_edit_guard tests.test_dispatcher_test_context_guard -v`

3. Phase 3: Deduplicate the shared `TIER4_MAX_CONTEXT_CHARS`/`MAX_WRITE_CHARS` constant
   - [x] Create `scripts/tier4_context.py` containing only: a short module docstring (single source of truth for the Tier 4 context-size ceiling, shared by `scripts/dispatcher.py` and `scripts/content_guard.py`, split out to avoid the circular import `dispatcher -> tier4_worker -> content_guard -> dispatcher`), and `TIER4_MAX_CONTEXT_CHARS = 24576 * 3  # tier_4_worker num_ctx=24576 tokens (config/tiers.yaml) * 3 chars/token conservative floor -- see scripts/tier4_worker.py's call_ollama() options={"num_ctx": 24576}, the source of truth` (moved verbatim from `scripts/dispatcher.py` line 416). No other code or imports. Verify: `python3 -m py_compile scripts/tier4_context.py`
   - [x] Edit `scripts/dispatcher.py`: remove the local definition `TIER4_MAX_CONTEXT_CHARS = 24576 * 3` and its trailing comment at line 416; add `from scripts.tier4_context import TIER4_MAX_CONTEXT_CHARS` to the existing `from scripts...` import block (lines 33–39), so it remains importable from `scripts.dispatcher` via plain re-export (no alias). Usages at lines 480 and 487 must keep working unchanged. Verify: `python3 -m py_compile scripts/dispatcher.py`
   - [x] Edit `scripts/content_guard.py`: remove the local definition `MAX_WRITE_CHARS = 24576 * 3` at line 47 and the cross-referencing comment block at lines 43–46; add `from scripts.tier4_context import TIER4_MAX_CONTEXT_CHARS as MAX_WRITE_CHARS` to the import block after line 27 (`from scripts.tri_logging import get_logger`), so `MAX_WRITE_CHARS` remains the name used at lines 61 and 67 unchanged. Replace the removed comment with a one-line comment above the import noting it now shares its value with `scripts.dispatcher.TIER4_MAX_CONTEXT_CHARS` via `scripts/tier4_context.py`. Verify: `python3 -m py_compile scripts/content_guard.py`
   - [x] Check `tests/test_file_size_ceiling_and_oversize_escalation.py` line 23's `from scripts.dispatcher import (... TIER4_MAX_CONTEXT_CHARS)` and any other match from `grep -rln "TIER4_MAX_CONTEXT_CHARS\|MAX_WRITE_CHARS" tests/` — both names stay importable from their original modules via re-export, so no import path should need to change; if any test imports from a now-removed local-definition path, fix it to import from `scripts.tier4_context` instead. Verify: `PYTHONPATH=. python3 -m unittest tests.test_branch_features tests.test_file_size_ceiling_and_oversize_escalation tests.test_encrypted_file_edit_guard tests.test_dispatcher_test_context_guard -v`

4. Phase 4: Full verification and docs
   - [x] Run `python3 -m py_compile scripts/dispatcher.py scripts/content_guard.py scripts/tier4_context.py scripts/planner.py` and confirm zero errors/output.
   - [x] Run `PYTHONPATH=. python3 -m unittest tests.test_branch_features tests.test_file_size_ceiling_and_oversize_escalation tests.test_encrypted_file_edit_guard tests.test_dispatcher_test_context_guard -v` and confirm all tests pass (no `SKIPPED`, no failures/errors).
   - [x] Update `AGENTS.md` at the repo root: first run `wc -c AGENTS.md` to check current size against the 73,728-char Tier 4 ceiling; add `scripts/tier4_context.py` to the living file/dir index (one line: shared Tier-4 context-size-ceiling constant module, imported by `scripts/dispatcher.py` and `scripts/content_guard.py`); note the `breakdown_plan()` resume-guard behavior change (post-breakdown guards now run only on fresh chunk assembly, not on resume of an already-populated breakdown) in whatever section documents `breakdown_plan()`/dispatcher guard behavior. Keep additions concise per this repo's doc-hygiene convention.
<!-- triapi:plan run_id=20260819-224114-9884f8 end -->

<!-- triapi:plan run_id=20260823-135914-18f8c0 start -->
## TriAPI Plan (run 20260823-135914-18f8c0, appended 2026-08-23)

# Plan: Audit why TriAPI is not working right now

Scope: read-only diagnosis. No repo files are modified; all evidence is captured under `/tmp/triapi_audit/` (kept out of the repo per `AGENTS.md`'s doc-hygiene rule). The deliverable is a root-cause report at `/tmp/triapi_audit/findings.md`, printed at the end. Applying fixes is a follow-up the user approves after seeing the findings.

## Phase 1 — Reproduce the failure and read current state

- [x] Capture the repo's own current-state note, recent git history, and root listing into `/tmp/triapi_audit/carryover.txt` so the audit starts from what the repo itself already says: `mkdir -p /tmp/triapi_audit && { echo '=== CARRYOVER.md (head) ==='; head -n 120 CARRYOVER.md 2>&1; echo; echo '=== recent git log ==='; git -C . log --oneline -15 --decorate 2>&1; echo; echo '=== root listing ==='; ls -la; } > /tmp/triapi_audit/carryover.txt 2>&1; cat /tmp/triapi_audit/carryover.txt`
- [x] Capture exactly how the `triapi` command behaves right now (exists on PATH? crashes on startup?) into `/tmp/triapi_audit/repro_triapi.txt`: `{ command -v triapi || echo NOT_ON_PATH; } > /tmp/triapi_audit/repro_triapi.txt 2>&1; timeout 20 triapi --help >> /tmp/triapi_audit/repro_triapi.txt 2>&1; echo "exit=$?" >> /tmp/triapi_audit/repro_triapi.txt; head -100 /tmp/triapi_audit/repro_triapi.txt` — a nonzero `exit=` or `NOT_ON_PATH` here is itself a root-cause candidate.
- [x] Locate where the `triapi` entry point ships from (console script, `scripts/triapi.py`, aliases) into `/tmp/triapi_audit/entry_points.txt`: `{ pip show triapi 2>/dev/null | head -8; echo '---'; ls -la /usr/local/bin/triapi ~/.local/bin/triapi "$HOME/bin/triapi" 2>/dev/null; echo '---'; find . -maxdepth 3 \( -iname 'triapi*' -o -name 'pyproject.toml' -o -name 'setup.py' -o -name 'setup.cfg' \) -not -path './.git/*' | sort; } > /tmp/triapi_audit/entry_points.txt 2>&1; cat /tmp/triapi_audit/entry_points.txt`
- [x] Run the repo's own regression suite to separate "code is broken" from "environment is broken", recording to `/tmp/triapi_audit/unittest.txt`: `PYTHONPATH=. timeout 600 python3 -m unittest tests.test_branch_features -v > /tmp/triapi_audit/unittest.txt 2>&1; echo "exit=$?" >> /tmp/triapi_audit/unittest.txt; tail -80 /tmp/triapi_audit/unittest.txt`

## Phase 2 — Environment, dependencies, secrets, config

- [x] Check Python/deps on the global interpreter and any venv, into `/tmp/triapi_audit/deps.txt`: `{ python3 --version; echo '--- global imports ---'; PYTHONPATH=. python3 -c "import requests, yaml; print('requests+PyYAML OK')" 2>&1; PYTHONPATH=. python3 -c "import mcp; print('mcp OK')" 2>&1; echo '--- venv imports ---'; for p in .venv/bin/python venv/bin/python; do if [ -x "$p" ]; then "$p" --version; "$p" -c "import requests, yaml; print('requests+PyYAML OK')" 2>&1; "$p" -c "import mcp; print('mcp OK')" 2>&1; fi; done; echo '--- pip versions ---'; pip show requests PyYAML mcp 2>/dev/null | grep -E '^(Name|Version)'; } > /tmp/triapi_audit/deps.txt 2>&1; cat /tmp/triapi_audit/deps.txt` — `mcp` was not yet installed at planning time, so a missing `mcp` on the interpreter `triapi` actually runs under is a prime suspect.
- [x] Verify the sops/age secrets path works, without printing any secret values, into `/tmp/triapi_audit/secrets.txt`: `{ ls -la config/ 2>&1; echo '--- age key ---'; test -f ~/.config/sops/age/keys.txt && echo AGE_KEY_PRESENT || echo AGE_KEY_MISSING; echo '--- secrets file ---'; test -f config/secrets.enc.yaml && echo SECRETS_EXISTS || echo SECRETS_MISSING; echo '--- decrypt check ---'; if [ -f config/secrets.enc.yaml ]; then sops -d config/secrets.enc.yaml > /dev/null 2>&1 && echo DECRYPT_OK || echo DECRYPT_FAIL; else echo SKIP_DECRYPT_NO_FILE; fi; } > /tmp/triapi_audit/secrets.txt 2>&1; cat /tmp/triapi_audit/secrets.txt` — as of 2026-08-17 `config/secrets.enc.yaml` is gitignored/local-only, so on a fresh clone `SECRETS_MISSING` would hard-fail `load_secrets()`.
- [x] Validate `config/tiers.yaml` parses and loads through the repo's own loader, into `/tmp/triapi_audit/config_load.txt`: `{ PYTHONPATH=. python3 -c "import yaml; yaml.safe_load(open('config/tiers.yaml')); print('tiers.yaml YAML_OK')" 2>&1; PYTHONPATH=. python3 -c "from scripts.config_loader import load_tiers; t=load_tiers(); print('load_tiers keys:', sorted(t.keys()))" 2>&1; } > /tmp/triapi_audit/config_load.txt 2>&1; cat /tmp/triapi_audit/config_load.txt` — a `ValueError` naming a missing required key is a root cause.
- [x] Record the optional sidecar files and gitignore state into `/tmp/triapi_audit/sidecars.txt`: `{ echo '=== config/resource_guard.yaml ==='; test -f config/resource_guard.yaml && cat config/resource_guard.yaml || echo RESOURCE_GUARD_MISSING_OPTIONAL; echo; echo '=== .sops.yaml ==='; test -f .sops.yaml && cat .sops.yaml || echo SOPS_RULE_MISSING; echo; echo '=== gitignore status of config/secrets.enc.yaml ==='; git check-ignore -v config/secrets.enc.yaml 2>&1 || echo NOT_GITIGNORED; } > /tmp/triapi_audit/sidecars.txt 2>&1; cat /tmp/triapi_audit/sidecars.txt`

## Phase 3 — Live subsystem health (Ollama, Claude, budget guard, logs)

- [x] Check the Ollama systemd user service and which models are actually pulled, into `/tmp/triapi_audit/ollama.txt`: `{ systemctl --user is-active ollama 2>&1; echo '--- status ---'; systemctl --user status ollama --no-pager 2>&1 | head -20; echo '--- ollama list ---'; ollama list 2>&1; } > /tmp/triapi_audit/ollama.txt 2>&1; cat /tmp/triapi_audit/ollama.txt` — confirm whether `qwen2.5-coder:14b-instruct-q8_0`, `deepseek-coder-v2:16b`, `qwen2.5-coder:32b` are present.
- [x] Confirm Ollama's HTTP API actually responds on `127.0.0.1:11434` (using the first model listed) into `/tmp/triapi_audit/ollama_api.txt`: `MODEL=$(ollama list 2>/dev/null | sed -n '2p' | awk '{print $1}'); echo "model: ${MODEL:-none}" > /tmp/triapi_audit/ollama_api.txt; [ -n "$MODEL" ] && curl -s --max-time 120 http://127.0.0.1:11434/api/generate -d "{\"model\":\"$MODEL\",\"prompt\":\"Reply with exactly OK\",\"stream\":false,\"options\":{\"num_predict\":10}}" >> /tmp/triapi_audit/ollama_api.txt 2>&1; head -c 600 /tmp/triapi_audit/ollama_api.txt` — a connection refusal vs. a model-not-found error are different findings.
- [x] Check Claude CLI presence, auth mode, and that the exact flags the scripts use still exist, into `/tmp/triapi_audit/claude.txt`: `{ claude --version 2>&1; echo "ANTHROPIC_API_KEY set: $([ -n "$ANTHROPIC_API_KEY" ] && echo YES_BUDGET_GUARD_WILL_REFUSE || echo no)"; echo '--- claude -p flags still supported? ---'; claude -p --help 2>&1 | grep -oE '\-\-(output-format|system-prompt|tools|bare)[a-z-]*' | sort -u | head -20; } > /tmp/triapi_audit/claude.txt 2>&1; cat /tmp/triapi_audit/claude.txt` — a missing flag (e.g. if the CLI was updated past what `scripts/tier1_escalate.py` invokes) is a classic "stopped working" cause.
- [x] Exercise the budget-guard gates and read the usage counters, into `/tmp/triapi_audit/budget_guard.txt`: `{ PYTHONPATH=. python3 -c "import scripts.budget_guard as bg; print('check_tier1_ok ->', bg.check_tier1_ok()); print('check_tier3_peak_hours_ok ->', bg.check_tier3_peak_hours_ok())" 2>&1; echo '--- usage counters ---'; wc -l logs/gemini_usage.jsonl logs/cost_log.jsonl logs/escalations.jsonl 2>&1; echo '--- gemini usage tail ---'; tail -n 5 logs/gemini_usage.jsonl 2>&1; } > /tmp/triapi_audit/budget_guard.txt 2>&1; cat /tmp/triapi_audit/budget_guard.txt` — note the known gate: Tier 3 is refused inside the DeepSeek peak window 06:00-10:00 UTC, and a near-cap `gemini_usage.jsonl` would refuse Tier 2.
- [x] Inspect runtime logs, leftover per-task state, and escalations into `/tmp/triapi_audit/logs.txt`: `{ echo '=== logs/triapi.log tail ==='; tail -n 200 logs/triapi.log 2>&1; echo; echo '=== logs/state/ ==='; ls -la logs/state/ 2>&1; echo; echo '=== escalations.jsonl tail ==='; tail -n 20 logs/escalations.jsonl 2>&1; } > /tmp/triapi_audit/logs.txt 2>&1; cat /tmp/triapi_audit/logs.txt` — a stale `logs/state/<task_id>.json` can make a re-run escalate instantly without any real failure.

## Phase 4 — End-to-end smoke test

- [x] Run one real end-to-end orchestrator invocation against the repo's own `samples/broken_build/` fixture (first model listed as the fast tier-4 override), recording to `/tmp/triapi_audit/e2e.txt`: `MODEL=$(ollama list 2>/dev/null | sed -n '2p' | awk '{print $1}'); { PYTHONPATH=. timeout 900 python3 scripts/orchestrator.py --task-id audit-e2e-$(date +%s) --description "Fix the compile error in main.cpp (audit)" --target main.cpp --workdir samples/broken_build --build-cmd "cmake -S . -B build && cmake --build build" --tier4-model "$MODEL" > /tmp/triapi_audit/e2e.txt 2>&1; echo "exit=$?" >> /tmp/triapi_audit/e2e.txt; } 2>&1; tail -100 /tmp/triapi_audit/e2e.txt` — this may make real sub-cent DeepSeek calls and budget-guarded subscription calls (consistent with the repo's own documented smoke test); the point is to see which tier/step is where it actually chokes.

## Phase 5 — Synthesize and report root cause

- [x] Auto-draft a raw red-flag index from every evidence file into `/tmp/triapi_audit/findings.md`: `{ echo "# TriAPI audit findings — $(date -Is)"; echo; echo "Scope: read-only diagnosis; evidence in /tmp/triapi_audit/*.txt; no repo files modified."; echo; for f in /tmp/triapi_audit/{carryover,repro_triapi,entry_points,unittest,deps,secrets,config_load,sidecars,ollama,ollama_api,claude,budget_guard,logs,e2e}.txt; do [ -f "$f" ] || continue; HITS=$(grep -niE 'error|fail|missing|refused|exception|traceback|not on path|decrypt_fail|secrets_missing|api_key_set|not found|cannot|denied|exit=[1-9]' "$f" | head -15); if [ -n "$HITS" ]; then echo "### $(basename "$f")"; echo "$HITS"; echo; fi; done; } > /tmp/triapi_audit/findings.md && echo "draft written"` — then rewrite the same file by hand into a clean audit report.
- [x] Author the final root-cause report at `/tmp/triapi_audit/findings.md` (one section per confirmed problem: symptom, evidence file + line, how it breaks TriAPI, minimal fix — fixes are NOT applied in this audit), then print it for the user: compose `/tmp/triapi_audit/findings.md` from the red-flag draft above, then verify with `cat /tmp/triapi_audit/findings.md && wc -l /tmp/triapi_audit/findings.md` — done means every evidence file has been reviewed/attributed and the root cause(s) are stated with the exact command/step that will unblock TriAPI.
<!-- triapi:plan run_id=20260823-135914-18f8c0 end -->

<!-- triapi:plan run_id=20260823-143024-5e6d61 start -->
## TriAPI Plan (run 20260823-143024-5e6d61, appended 2026-08-23)

<｜｜DSML｜｜tool_calls>
<｜｜DSML｜｜invoke name="read_file">
<｜｜DSML｜｜parameter name="filePath" string="true">tests/test_file_size_ceiling_and_oversize_escalation.py</｜｜DSML｜｜parameter>
</｜｜DSML｜｜invoke>
<｜｜DSML｜｜invoke name="read_file">
<｜｜DSML｜｜parameter name="filePath" string="true">scripts/tier4_worker.py</｜｜DSML｜｜parameter>
</｜｜DSML｜｜invoke>
</｜｜DSML｜｜tool_calls>
<!-- triapi:plan run_id=20260823-143024-5e6d61 end -->

<!-- triapi:plan run_id=20260823-144422-e0c98e start -->
## TriAPI Plan (run 20260823-144422-e0c98e, appended 2026-08-23)

1. Phase 1: Environment and Dependency Audit
   - [x] File: `config/secrets.enc.yaml`. Change needed: Read-only verification to ensure the local `age` key successfully decrypts the encrypted configuration without errors. Command: `sops -d config/secrets.enc.yaml > /dev/null`
   - [x] File: `config/resource_guard.yaml`. Change needed: Read-only verification of the Ollama dependency to ensure its systemd user service is currently active and running. Command: `systemctl --user status ollama --no-pager`
   - [x] File: `scripts/tier1_escalate.py`. Change needed: Read-only verification that the Anthropic `claude` CLI dependency is installed and accessible in the system path. Command: `claude --version`

2. Phase 2: Regression Test Suite Audit
   - [x] File: `tests/test_branch_features.py`. Change needed: Read-only execution of the full test suite to ensure all baseline logic, integrations, and mocked budget/Jules behaviors still pass. Command: `PYTHONPATH=. python3 -m unittest tests.test_branch_features -v`
<!-- triapi:plan run_id=20260823-144422-e0c98e end -->


<!-- triapi:plan run_id=20260823-999999-audit start -->
## TriAPI Plan (run 20260823-999999-audit, appended 2026-08-23)

1. Phase 1: Audit OpenRouter Refactor
   - [x] File: `tests/test_branch_features.py`. Change needed: Verify the full test suite passes after the manual OpenRouter refactoring applied to `scripts/dispatcher.py` and `scripts/triapi.py`. Note: `verify_only: true`. Command: `cat > /tmp/verify_audit.py <<'INNER_EOF'
import sys, subprocess
res = subprocess.run(["python3", "-m", "unittest", "discover", "tests", "-v"], capture_output=True, text=True)
if res.returncode != 0:
    print(res.stderr)
    sys.exit(1)
print("Audit OK")
INNER_EOF
python3 /tmp/verify_audit.py`
<!-- triapi:plan run_id=20260823-999999-audit end -->

<!-- triapi:plan run_id=20260823-163311-6c33a3 start -->
## TriAPI Plan (run 20260823-163311-6c33a3, appended 2026-08-23)

# OpenRouter Refactor Audit Plan

All steps are **read-only** and **non-mutating**: they parse/inspect the named file, never import it for side effects beyond standard-library AST parsing, never call the network, and never write code. Every verification is a HEREDOC shell command with `verify_only=true`.

---

## Phase 1 — Audit `scripts/llm_client.py`

- [ ] **Read-only target: `scripts/llm_client.py`** — verify the module has a provider-aware request path and an OpenRouter marker.
  ```bash
  bash -s -- verify_only=true <<'BASH'
  set -euo pipefail
  python3 - <<'PY'
  import ast, pathlib, re
  p = pathlib.Path('scripts/llm_client.py')
  src = p.read_text()
  tree = ast.parse(src, filename=str(p))
  provider_funcs = []
  for node in ast.walk(tree):
      if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
          if any(a.arg == 'provider' for a in node.args.args):
              provider_funcs.append(f'{node.name}:{node.lineno}')
  assert provider_funcs, 'FAIL: no function accepts a provider argument'
  assert re.search(r'openrouter', src, re.IGNORECASE), 'FAIL: no OpenRouter mention'
  print(f'PASS llm_client provider signature + OpenRouter marker: {provider_funcs}')
  PY
  BASH
  ```

- [ ] **Read-only target: `scripts/llm_client.py`** — verify the fallback loop is provider-guarded so it cannot silently cross from one provider to another.
  ```bash
  bash -s -- verify_only=true <<'BASH'
  set -euo pipefail
  python3 - <<'PY'
  import ast, pathlib
  p = pathlib.Path('scripts/llm_client.py')
  src = p.read_text()
  tree = ast.parse(src, filename=str(p))
  guards = []
  for node in ast.walk(tree):
      if isinstance(node, ast.If):
          test = ast.unparse(node.test)
          if 'provider' in test or 'model' in test:
              guards.append((node.lineno, test))
  assert guards, 'FAIL: no provider/model guard found'
  assert any('provider' in test for _, test in guards), 'FAIL: fallback guard does not check provider'
  print(f'PASS llm_client provider-aware fallback guard(s): {guards}')
  PY
  BASH
  ```

- [ ] **Read-only target: `scripts/llm_client.py`** — verify OpenAI-compatible response JSON is parsed defensively through `choices`/`message`/`content`.
  ```bash
  bash -s -- verify_only=true <<'BASH'
  set -euo pipefail
  python3 - <<'PY'
  import ast, pathlib
  p = pathlib.Path('scripts/llm_client.py')
  src = p.read_text()
  tree = ast.parse(src, filename=str(p))
  parse_calls = []
  for node in ast.walk(tree):
      if isinstance(node, ast.Call):
          try:
              s = ast.unparse(node)
          except Exception:
              continue
          if any(term in s for term in ('choices', 'message', 'content', 'response')):
              parse_calls.append((node.lineno, s[:240]))
  assert parse_calls, 'FAIL: no JSON/response parsing call found'
  assert any(('choices' in s or 'message' in s) and 'content' in s for _, s in parse_calls), \
      'FAIL: no choices/message + content extraction'
  print(f'PASS llm_client JSON parse sites: {len(parse_calls)}')
  PY
  BASH
  ```

---

## Phase 2 — Audit `scripts/dispatcher.py`

- [ ] **Read-only target: `scripts/dispatcher.py`** — verify the dispatcher actually uses `llm_client` and passes `provider=` explicitly to it.
  ```bash
  bash -s -- verify_only=true <<'BASH'
  set -euo pipefail
  python3 - <<'PY'
  import ast, pathlib, re
  p = pathlib.Path('scripts/dispatcher.py')
  src = p.read_text()
  tree = ast.parse(src, filename=str(p))
  assert 'llm_client' in src, 'FAIL: dispatcher does not reference llm_client'
  call_lines = []
  for node in ast.walk(tree):
      if isinstance(node, ast.Call) and any(kw.arg == 'provider' for kw in getattr(node, 'keywords', [])):
          call_lines.append(node.lineno)
  assert call_lines, 'FAIL: no dispatcher call passes provider= keyword'
  assert re.search(r'openrouter', src, re.IGNORECASE), 'FAIL: no OpenRouter gate/mention'
  print(f'PASS dispatcher llm_client + provider= at lines {call_lines}')
  PY
  BASH
  ```

- [ ] **Read-only target: `scripts/dispatcher.py`** — verify OpenRouter handling is kept separate from the Gemini fallback chain.
  ```bash
  bash -s -- verify_only=true <<'BASH'
  set -euo pipefail
  python3 - <<'PY'
  import pathlib, re
  src = pathlib.Path('scripts/dispatcher.py').read_text()
  assert 'gemini_fallback' in src, 'FAIL: gemini_fallback module not referenced'
  assert re.search(r'provider\s*(?:==|!=)\s*[\'"]openrouter[\'"]', src, re.IGNORECASE), \
      'FAIL: OpenRouter provider gate not found'
  assert re.search(r'breakdown|fallback_chain', src), 'FAIL: breakdown/fallback chain path not found'
  print('PASS dispatcher OpenRouter gate is separate from gemini_fallback')
  PY
  BASH
  ```

- [ ] **Read-only target: `scripts/dispatcher.py`** — verify the dispatcher does not hardcode an OpenRouter endpoint independently of `llm_client`.
  ```bash
  bash -s -- verify_only=true <<'BASH'
  set -euo pipefail
  python3 - <<'PY'
  import pathlib, re
  src = pathlib.Path('scripts/dispatcher.py').read_text()
  assert 'llm_client' in src, 'FAIL: dispatcher does not delegate to llm_client'
  # A clean refactor keeps the HTTP endpoint in llm_client, not duplicated here.
  assert not re.search(r'https?://[^\s\'"]*(?:openrouter|chat/completions)', src, re.IGNORECASE), \
      'FAIL: dispatcher appears to hardcode an OpenRouter/chat-completions URL'
  print('PASS dispatcher delegates OpenRouter transport to llm_client')
  PY
  BASH
  ```

---

## Phase 3 — Audit `scripts/triapi.py`

- [ ] **Read-only target: `scripts/triapi.py`** — verify the CLI exposes an OpenRouter provider selection path.
  ```bash
  bash -s -- verify_only=true <<'BASH'
  set -euo pipefail
  python3 - <<'PY'
  import pathlib, re
  src = pathlib.Path('scripts/triapi.py').read_text()
  assert 'openrouter' in src.lower(), 'FAIL: triapi has no OpenRouter mention'
  assert re.search(r'--provider', src), 'FAIL: triapi missing --provider flag'
  assert re.search(r'add_argument\([^)]*--provider', src), 'FAIL: argparse missing --provider option'
  print('PASS triapi --provider CLI flag')
  PY
  BASH
  ```

- [ ] **Read-only target: `scripts/triapi.py`** — verify the provider value selected at the CLI reaches the dispatcher call.
  ```bash
  bash -s -- verify_only=true <<'BASH'
  set -euo pipefail
  python3 - <<'PY'
  import ast, pathlib
  src = pathlib.Path('scripts/triapi.py').read_text()
  tree = ast.parse(src, filename='scripts/triapi.py')
  dispatch_calls = []
  for node in ast.walk(tree):
      if isinstance(node, ast.Call):
          try:
              func = ast.unparse(node.func)
          except Exception:
              continue
          if 'dispatch' in func or 'dispatcher' in func:
              dispatch_calls.append((node.lineno, func, [kw.arg for kw in getattr(node, 'keywords', [])]))
  assert dispatch_calls, 'FAIL: no dispatcher/dispatch call in triapi'
  assert any('provider' in kwargs for _, _, kwargs in dispatch_calls), 'FAIL: dispatcher call missing provider'
  print(f'PASS triapi provider reaches dispatcher call: {dispatch_calls}')
  PY
  BASH
  ```

- [ ] **Read-only target: `scripts/triapi.py`** — verify `triapi.py` parses as valid Python without executing any pipeline code.
  ```bash
  bash -s -- verify_only=true <<'BASH'
  set -euo pipefail
  python3 - <<'PY'
  import ast, pathlib
  p = pathlib.Path('scripts/triapi.py')
  ast.parse(p.read_text(), filename=str(p))
  print('PASS syntax scripts/triapi.py')
  PY
  BASH
  ```

---

## Phase 4 — Immutability verification for the three audited files

- [ ] **Read-only target: `scripts/llm_client.py`** — confirm the audit did not modify the file.
  ```bash
  bash -s -- verify_only=true <<'BASH'
  set -euo pipefail
  git diff --exit-code -- scripts/llm_client.py
  echo 'PASS scripts/llm_client.py is unchanged'
  BASH
  ```

- [ ] **Read-only target: `scripts/dispatcher.py`** — confirm the audit did not modify the file.
  ```bash
  bash -s -- verify_only=true <<'BASH'
  set -euo pipefail
  git diff --exit-code -- scripts/dispatcher.py
  echo 'PASS scripts/dispatcher.py is unchanged'
  BASH
  ```

- [ ] **Read-only target: `scripts/triapi.py`** — confirm the audit did not modify the file.
  ```bash
  bash -s -- verify_only=true <<'BASH'
  set -euo pipefail
  git diff --exit-code -- scripts/triapi.py
  echo 'PASS scripts/triapi.py is unchanged'
  BASH
  ```
<!-- triapi:plan run_id=20260823-163311-6c33a3 end -->
