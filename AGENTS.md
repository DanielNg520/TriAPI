# AGENTS.md

TriAPI: multi-tier LLM dispatch pipeline. Read this file first, it is the only doc kept live.
Everything else, including `docs/artifact/`, is frozen history, not maintained.

## Current architecture

Old dispatcher (`scripts/dispatcher.py` + tier1-5 escalation) is deprecated in place, not deleted, not running.
Root cause: its own verification never verified real state.
See `SALVAGE_PLAN.md` for the keep/rewrite/drop decision.

Active work lives in `rebuild/`: DeepSeek writes code, agy writes docs, Claude plans+audits every response.
Nothing auto-applied. See `rebuild/README.md`, `rebuild/PHASES.md`, `rebuild/RULES.md` (hard rules shared by every call).

Design principle: hub-and-spoke, not waterfall. Every worker result routes through Claude before the next step.
No worker-to-worker handoff, ever — that chain shape is what let bugs propagate silently in the old pipeline.

Test command: `cd rebuild && python3 -m pytest -v tests/`

### Constructor/builder worker split — optional, judgment call (added 2026-09-06)

Not a universal default — one trial (`task_queue.py`, 5/5 clean, one spec-gap follow-up)
isn't enough to say it beats plain one-function dispatch generally, only that it removes
the "builder infers structure from a fragment" failure mode. Use it when:
- A new file has 3+ functions sharing infra (schema, connection, argparse) where a wrong
  early signature would force rework in every later call.
- Interface precision matters (exact return codes, error text, status transitions).

Skip it (plain one-function-per-call dispatch on the live file) for single-function tasks,
small edits to an existing file, or anything where writing a skeleton first is pure overhead.
Either way: write tests from the function's *intent*, not just its docstring — that's what
caught the one real gap (`cmd_claim`'s depends_on check), not the diff review.

### Hub-loop supervisor (queue-driven, doc only — loop not yet turned on)

- Task store: `rebuild/scripts/task_queue.py` (SQLite+WAL, `rebuild/queue.sqlite3`, gitignored).
- Global command: `triapi` (thin `~/.local/bin/triapi` wrapper, any cwd) — `add`, `list`,
  `approve`, `claim`, `complete`. See the file's own docstrings for each subcommand's contract.
- Intended loop, not yet started: a persistent `ScheduleWakeup`/`/loop` dynamic-mode session
  (not a fresh `claude -p` per cycle) calls `triapi claim` → dispatches to DeepSeek/agy per
  `rebuild/RULES.md` → Claude audits the result → `triapi complete`, rescheduling around
  `llm_client.is_deepseek_peak_hours()`.
- Context hygiene for that loop: `/compact` once each cycle's result is durably in the
  store; `/clear` before a long scheduled gap (prompt-cache TTL ~1hr won't survive a
  multi-hour peak-hour wait anyway); push any individually heavy dispatch into a fork
  rather than absorbing its transcript into the hub session directly.
- Textual TUI control panel remains a separate, future, not-yet-scoped follow-up.

## Doc policy

One file only: this one. Carryover is the section below, not a separate file.
Hard cap: 1000 lines, 30 words per line. Precise, worth-noting entries only, no narrative.
Once work is done, delete its line entirely — don't move it to an archive file. Git history has it.
A removed/retired feature gets zero doc trace: no "X removed" line, no rationale footnote, nothing.
A pending removal task states the action only ("delete file X"), never the reasoning for removing it.
This repo's docs never reference or absorb another repo's content — relocate that repo's own docs there instead, never delete it.
This policy applies to every repo TriAPI supervises, not just this one — check each target repo's own AGENTS.md follows it too.

## Carryover (current state, 2026-09-06)

- TriAPI rebuild: Phases 1-3 done (`rebuild/scripts/verify.py`, `dispatch.py`, `cost.py`), 66/66 real tests passing.
- Phase 4 (auto tier-escalation) deferred by user decision — steady state is manual DeepSeek+agy+Claude.
- Spend cap: `cost.check_budget`, $5.00 default in `model_config.yaml`, hard-blocks `call_deepseek.py` before the API call, no bypass flag. Confirmed the only call site (2026-09-06 audit).
- DeepSeek peak-hour guard (`llm_client.is_deepseek_peak_hours`, Beijing weekend bypass): `call_deepseek.py` now falls back to OpenRouter (`nvidia/nemotron-3-ultra-550b-a55b:free`, config in `model_config.yaml`) instead of blocking (2026-09-06, user-approved override of the prior no-OpenRouter stance).
- OpenRouter otherwise still not added as a general DeepSeek peer — shared rate-limit pool, content-filter false positives, free-tier hallucination were real old-pipeline problems; the peak-hours fallback above is the sole call site.
- OpenRouter content-filter sanitizer (email/phone/IP redaction) ported into `openrouter_sanitizer.py`, wired into `execute_openrouter` — was missing when the fallback first landed, added same day after being flagged.
- Nemotron fallback quirk (2026-09-06): 3/3 real dispatch calls through it made an unrequested edit to an unrelated line despite explicit "don't touch anything else" instructions (caught and reverted each time — see `triapi_tui_plan.md`'s mini-tasks). Always diff the full response against the untouched file, not just the requested function, when a call fell back to OpenRouter.
- Per-concern module split (2026-09-06): `tui.py`'s helpers moved into `tui_session_log.py`/`tui_framing.py`/`tui_dispatch_status.py`/`tui_stream.py`; `llm_client.py`'s sanitizer moved into `openrouter_sanitizer.py`. Convention going forward: split by concern while a file is still small, don't wait for a size ceiling.
- `triapi tui` (design in `rebuild/tasks/triapi_tui_plan.md`) done 2026-09-06/07: all 6 mini-tasks landed, `tui` subcommand wired, 66/66 tests pass, end-to-end verified via Textual's `App.run_test()` harness with a real `claude -p` call (streamed output, session log file written and formatted correctly, second launch gets a distinct file).
- Full audit (2026-09-06) of `rebuild/`'s own claims vs live code — queue lifecycle, task/commit cross-check — all accurate.
  No disconnect-from-live-path bugs here (two found+fixed in SemAI instead — see its own `AGENTS.md`).

## Future plans (queued, not started)

### 1. Virtual Codebase Plan — tiered Planner-Materializer for large-file edits

Goal: a local model drafts edits on oversized files without hitting context limits.
A cloud model then integrates the draft into the real file precisely.

- Slicer: AST walk (Tree-sitter) to the target function's enclosing scope.
- Produces a small skeleton file: imports, class shell, other functions' signatures only, target function in full.
- Local Planner (Tier 4-equivalent): drafts logic on the skeleton. Correctness only, formatting doesn't matter.
- Cloud Materializer (DeepSeek/Gemini): given the full real file (prompt-cached) plus the local draft, emits a patch.
- Emit a Search/Replace block, not a unified diff — benchmarks show ~59% vs ~26% success rate.
- Patcher: normalize whitespace before matching, apply in-memory only, never write to disk directly.
- Re-parse with Tree-sitter after applying; one-shot auto-correct on syntax failure; commit only once it parses clean.
- Known building block: `scripts/edit_blocks.py` (old pipeline) already does Search/Replace materialization — reuse/extend, don't rebuild.
- Tree-sitter itself is a new dependency, not used anywhere in TriAPI today.
- Status: design reference only. User wants to work on this together personally — do not start solo.

## Archive

Old bloated docs (plan-block history, file/dir doc overflow, old tier-escalation notes) removed from the tree entirely.
Recoverable via `git show 82e81f8:docs/artifact/<path>` (last commit before removal) if ever needed.
