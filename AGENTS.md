# AGENTS.md

TriAPI: LLM dispatch pipeline (DeepSeek + agy workers, Claude supervision). Read this file first, it is the only doc kept live.
Everything else, including `docs/artifact/`, is frozen history, not maintained.

## Current architecture

Old dispatcher (`scripts/dispatcher.py` + tier1-5 escalation) is deprecated in place, not deleted, not running.
Root cause: its own verification never verified real state.
See `SALVAGE_PLAN.md` for the keep/rewrite/drop decision.

Active work lives in `rebuild/`: DeepSeek writes code, agy writes docs, Claude plans+audits every response.
Nothing auto-applied. See `rebuild/README.md`, `rebuild/PHASES.md`, `rebuild/RULES.md` (hard rules shared by every call).

Design principle: hub-and-spoke, not waterfall. Every worker result routes through Claude before the next step.
No worker-to-worker handoff, ever — that chain shape is what let bugs propagate silently in the old pipeline.

Test command: `cd rebuild && python3 -m pytest -v tests/` (100/100, 2026-09-16)

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
- `triapi tui` (Textual UI over the queue) is implemented and wired (`rebuild/scripts/tui.py` + 4 `tui_*.py` helper modules, `cmd_tui` subcommand in `task_queue.py`), end-to-end verified.
- Native-app launchers, 2026-09-16: `packaging/linux/` (`triapi.desktop` + `install.sh`, copies to `~/.local/share/applications/`) and `packaging/macos/` (`TriAPI.command` + `install.sh`, copies to `~/Applications/`). Original agy-dispatched version assumed a `triapi` command on PATH, which doesn't exist (no console-script entry point anywhere in the repo) — both launchers failed. Fixed on macOS (hand fix, user-approved): resolve the repo path themselves (baked in at install time via `sed`) and invoke `-m scripts.task_queue tui` from `rebuild/` directly — that `-m` form is required by a real `cmd_tui` bug (`from scripts import tui`, task_queue.py:282, only resolves under `-m`; `rebuild/README.md` corrected to match). Fedora Fix 1 (hardcoded `x-terminal-emulator`, Debian/Ubuntu-only, missing on Fedora): `.desktop` switched to `Terminal=true` so the DE's own default terminal is used. Fedora Fix 2 (Mac's version hardcoded `.venv/bin/python`, but this repo has no `.venv` at all on Fedora — plain system `python3`): dispatched through this pipeline (3 agy tasks) — all three launcher files now prefer `.venv/bin/python` if present, else fall back to `python3` on PATH, erroring only if neither exists. Verified end-to-end on Fedora (no `.venv`, `python3` fallback path): installed `.desktop` baked in `python3` correctly, TUI rendered live with no errors. macOS side verified by the Mac session (`.venv` path), confirmed no regression against `a8feb33`. Xubuntu verified 2026-09-16 (Ubuntu 26.04 host, same code path as Fedora): `.venv`-at-repo-root created, `install.sh` baked in `.venv/bin/python` correctly, `.desktop` launcher and direct `-m scripts.task_queue tui` both rendered live with no errors.

## Doc policy

One file only: this one. Carryover is the section below, not a separate file.
Hard cap: 1000 lines, 30 words per line. Precise, worth-noting entries only, no narrative.
Once work is done, delete its line entirely — don't move it to an archive file. Git history has it.
A removed/retired feature gets zero doc trace: no "X removed" line, no rationale footnote, nothing.
A pending removal task states the action only ("delete file X"), never the reasoning for removing it.
This repo's docs never reference or absorb another repo's content — relocate that repo's own docs there instead, never delete it.
This policy applies to every repo TriAPI supervises, not just this one — check each target repo's own AGENTS.md follows it too.
Hard rule: wrap-up always ends with `git push` right after committing, not just a local commit. This repo runs on multiple machines (git is the only sync path in use) — a commit that never leaves the local machine is what caused the two copies to diverge before (see 2026-09-12 reconciliation in git log).

## Carryover (current state, 2026-09-16)

- Three-way cross-platform check (Mac/Fedora/Xubuntu-equivalent Ubuntu) via parallel sessions: 100/100 tests on Fedora and Ubuntu, 98/100 on Mac — the 2 "failures" are a false alarm (`test_verify.py` shells to bare `python3`, which only has `pytest` when a venv is active on `PATH`; confirmed passing on Ubuntu once activated), not a repo bug. Launcher verified live on all three.
- Gap, partially closed: `agy` (Google's Antigravity CLI, OAuth-only, no separate project/scope config — install itself has no known download URL from any machine checked, must come from Google's own Antigravity distribution) and `codegraph` (`@colbymchenry/codegraph` npm package, `npm install -g @colbymchenry/codegraph`, no auth needed, self-contained runtime) are external tools with no install doc in this repo — still true, still needed. The `triapi` global wrapper gap is fixed: `packaging/triapi-wrapper/install.sh` (same pattern as the native-app launchers — repo-path-relative, `.venv`-if-present else system `python3`) generates `~/.local/bin/triapi`, verified end-to-end (`add`/`list` round-trip from an arbitrary cwd, plus a live `triapi tui` launch) on all three: Mac, Fedora, and Xubuntu-equivalent Ubuntu, 2026-09-17.
- New gap found while verifying the wrapper: nothing installs `requirements.txt` into whichever `python3` the wrapper falls back to when no `.venv` exists. Fedora's system `python3` happened to already have `requests`/`PyYAML`/`textual`/`mcp` from earlier work, masking this — a genuinely fresh machine with no `.venv` and no system-wide deps would `ModuleNotFoundError` on `add`/`list` too, not just `tui` (`task_queue.py` imports `yaml` at module level, so no subcommand is actually stdlib-only). Not a wrapper bug, a missing setup step.
- Manual test-task cleanup note: deleting a test row from `tasks` alone leaves an orphaned `events` row (`events.task_id`, no FK cascade) — delete from both tables, or `events` accumulates references to nonexistent tasks.
- Python version floor: codebase uses PEP 604 `X | None` throughout, needs 3.10+. Fine on Ubuntu 22.04+/24.04+/26.04, current Fedora, and macOS; would break on a 20.04-based Xubuntu (ships 3.8). No 3.11+/3.12+-only syntax found.

## Carryover (current state, 2026-09-15)

- Ops Center dispatch (`/home/dyne/Documents/Coding/Ops Center`, not a git repo): `vlog_bridge/` gained multi-recipient recording-status broadcast (new `broadcast.py`, `bridge_state.py` report-state tracking, `telegram_io.py` delete/return-id support, `bridge.py` lock-file-diff watcher covering both manual `/record` and the recorder's own automatic polling) — 5 tasks, hub-and-spoke reviewed. Two DeepSeek responses rejected and redispatched (fabricated code for parts of the file only described, not pasted verbatim, in the prompt — always paste full current file content for a full-file edit-in-place task). Also replaced Ops Center's `MAPPING.md` with `AGENTS.md` per this repo's doc policy (single-call agy task timed out/returned empty twice; split into two section-level calls, both succeeded).

## Carryover (current state, 2026-09-14)

- Four SemAI dispatch sessions today, full detail in SemAI's own AGENTS.md: (1) Telegram mail-actions Delete button + `_clean_body_text` boilerplate-stripping fix. (2) Root-caused and fixed a real Notion duplicate-database/duplicate-interface incident (`ensure_database`/`_ensure_actions_page_structure` trusted local cache alone before creating — now reconciles against Notion's actual state first; general principle, not Notion-specific). (3) Confirmed email→task/reminder→Notion sync was already fully wired, just unexercised; added missing `Category` property push. (4) New email→calendar "📅 Event" button (`CreateCalendarEventWorker` gained an email-sourced path); live-tested against a real appointment email and caught+fixed two real bugs (snippet-only body truncating before the actual date/time; a found-start-but-no-title case leaking the literal string "None") that the mocked unit tests didn't surface — live testing against real data caught what mocks missed. All work went through this repo's dispatch pipeline (DeepSeek/agy write, Claude reviews/applies/verifies), OpenRouter free-fallback used throughout (session ran during DeepSeek peak hours), several 502 "Nvidia overloaded" transient failures resolved by one retry each. 195/195 SemAI pytest pass, both live services restarted clean after each fix.

## Carryover (current state, 2026-09-13)

- `task_queue.py`'s schema is single-parent only — `--depends-on` silently corrupts on multiple space-joined ids. Validate a bulk `add` sequence's dependencies resolve to real task ids right away, don't wait for a `claim` failure.
- `rebuild/tasks/*.md` are per-run dispatch task descriptions, not pipeline code — gitignored, ephemeral, often reference a target repo's absolute path from whichever machine dispatched them.
- `rebuild/scripts/llm_client.py` calls no local model — cloud only (DeepSeek, OpenRouter peak-hours fallback, Planner/Nemotron, plus local `agy` which is not Ollama); the frozen old `scripts/llm_client.py` is the one with an actual `ollama` provider branch.
- Spend cap: `cost.check_budget`, $5.00 default in `model_config.yaml`, hard-blocks `call_deepseek.py` before the API call, no bypass flag — confirmed the only call site.
- `call_deepseek.py` falls back to OpenRouter (`nvidia/nemotron-3-ultra-550b-a55b:free`, config in `model_config.yaml`) during DeepSeek peak hours instead of blocking, sanitized via `openrouter_sanitizer.py`. Not a general DeepSeek peer otherwise — shared rate-limit pool, content-filter/hallucination issues in the old pipeline; peak-hours fallback is the sole call site. Nemotron quirk: has made an unrequested edit to an unrelated line despite explicit scope instructions on 3/3 real calls seen so far — always diff the full response, not just the requested function.
- `agy.model` pinned to `"gemini-3.8-flash-medium"` in `model_config.yaml` (was `null`, silently inheriting a shared setting file). agy occasionally wraps a plain-file reply in a stray triple-backtick fence despite "file content only" instructions — strip before applying.
- `~/.claude/hooks/dispatch-gate.sh` (global PreToolUse hook on Edit|Write|NotebookEdit): hard `deny` on any path in `~/.claude/dispatch-gate-paths.txt`. Escape hatch: `~/.claude/hooks/dispatch-gate-arm.sh <ttl_seconds> <file>...` writes a single-use, short-TTL marker consumed by the next matching Edit/Write — run it immediately before applying an already-reviewed DeepSeek/agy response, or before a hand fix the user explicitly approves in the moment.
- Nemotron is a standing Planner role: `rebuild/scripts/call_planner.py` + `llm_client.execute_planner()` + `model_config.yaml`'s `planner:` section (documented in `rebuild/README.md`). Not gated by DeepSeek peak-hours; shares the OpenRouter free-tier pool. Planner drafts still route through Claude before becoming queue tasks, never straight to DeepSeek/agy.
- Cross-platform (Ubuntu/Fedora/macOS): root `scripts/resource_guard.py` no-ops when `systemctl` is absent instead of crashing on macOS (no systemd). Frozen infra (SALVAGE_PLAN).
- Per-concern module split: `tui.py`'s helpers live in 4 `tui_*.py` modules; `llm_client.py`'s sanitizer lives in `openrouter_sanitizer.py`. Split by concern while a file's still small, don't wait for a size ceiling.
- When dispatching against any target repo, run its tests via the command its own AGENTS.md documents — don't assume system python; a repo's real test command (venv, wrapper script, etc.) is that repo's own convention, recorded there, not here.

## Future plans (queued, not started)

### 1. Virtual Codebase Plan — tiered Planner-Materializer for large-file edits

Goal: a local model drafts edits on oversized files without hitting context limits.
A cloud model then integrates the draft into the real file precisely.

- Slicer: revised 2026-09-09, no Tree-sitter — reuse the already-installed/indexed CodeGraph CLI instead. `codegraph node <file> --symbols-only` gives every other symbol's signature; `codegraph node <target-symbol>` gives its full verbatim source; the file's own import block is grabbed by a plain text read. No new parsing dependency needed — see carryover above for the hands-on verification.
- Produces a small skeleton file: imports, other functions'/class's signatures only, target function in full.
- Local Planner (Tier 4-equivalent): drafts logic on the skeleton. Correctness only, formatting doesn't matter.
- Cloud Materializer (DeepSeek/Gemini): given the full real file (prompt-cached) plus the local draft, emits a patch.
- Emit a Search/Replace block, not a unified diff — benchmarks show ~59% vs ~26% success rate.
- Patcher: normalize whitespace before matching, apply in-memory only, never write to disk directly.
- Re-parse (via CodeGraph re-sync, or a plain `ast.parse`/`py_compile` check) after applying; one-shot auto-correct on syntax failure; commit only once it parses clean.
- Known building block: `scripts/edit_blocks.py` (old pipeline) already does Search/Replace materialization — reuse/extend, don't rebuild.
- Status: chain fully shipped 2026-09-10 — Slicer, Patcher, Materializer,
  Planner/DeepSeek call wrappers, `vcb_run.py` entrypoint. 99/99 rebuild
  tests pass. File map and per-module contracts: `rebuild/README.md`.
- Design decisions and rationale for each piece: git log on
  `rebuild/scripts/vcb_*.py`, not repeated here.
- Live smoke test passed 2026-09-10: real end-to-end run against
  `scripts/dispatcher.py`'s `_default_build_cmd` (1279 lines) produced a
  correct, syntactically valid patch; rest of the file byte-for-byte
  unchanged; disk untouched (`run_vcb` only returns content).
- Bug found by that test, fixed same session: `run_vcb` and
  `vcb_slicer.build_skeleton` both called plain `open(file_path)`, but
  `codegraph` resolves `file_path` relative to `repo_path` regardless of
  cwd — the two only agreed by coincidence. Both call sites now join
  `repo_path`/`file_path`. Mocked tests couldn't catch this; only the live
  run did. 99/99 rebuild tests still pass.
- First real-world dispatch done 2026-09-11 (SemAI `stocks.py` fix, see
  carryover above) — surfaced and fixed one gap (symbol disambiguation).
  No more queued work here unless a future run surfaces another gap.

## Archive

Old bloated docs (plan-block history, file/dir doc overflow, old tier-escalation notes) removed from the tree entirely.
Recoverable via `git show 82e81f8:docs/artifact/<path>` (last commit before removal) if ever needed.
