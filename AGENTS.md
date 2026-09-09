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
- `triapi tui` (Textual UI over the queue) is implemented and wired (`scripts/tui.py` + 4 `tui_*.py` helper modules, `cmd_tui` subcommand), end-to-end verified.

## Doc policy

One file only: this one. Carryover is the section below, not a separate file.
Hard cap: 1000 lines, 30 words per line. Precise, worth-noting entries only, no narrative.
Once work is done, delete its line entirely — don't move it to an archive file. Git history has it.
A removed/retired feature gets zero doc trace: no "X removed" line, no rationale footnote, nothing.
A pending removal task states the action only ("delete file X"), never the reasoning for removing it.
This repo's docs never reference or absorb another repo's content — relocate that repo's own docs there instead, never delete it.
This policy applies to every repo TriAPI supervises, not just this one — check each target repo's own AGENTS.md follows it too.

## Carryover (current state, 2026-09-09)

- `~/.claude/hooks/dispatch-gate.sh` (global PreToolUse hook on Edit|Write|NotebookEdit): user confirmed the first version's `permissionDecision: ask` did prompt them live, then rejected it as pointless micromanagement (a blind yes/no with no content). Changed to `permissionDecision: allow` + `additionalContext` — a self-check reminder injected into Claude's own context at write time, naming the DeepSeek/agy workers, never a human prompt. Paths list: `~/.claude/dispatch-gate-paths.txt` (currently SemAI's `src/`/`tests/`). This is a nudge, not a hard stop — hooks can't detect intent (hand-write vs. applying an already-reviewed dispatch response), so it relies on the model actually reading and acting on the reminder each time, same judgment call as before, just re-surfaced every call instead of resting on memory.
- Nemotron (OpenRouter fallback model) trialed as a one-off Planner via `execute_openrouter` directly (bypassing the peak-hours-only gate, per explicit user request for this call) — drafted a 5-step task plan for a bug fix. Needed Claude correction on two hallucinated details (wrong method name `run()` vs actual `__call__`, wrong test file path) since it can't read the repo — otherwise structurally sound. Not yet added as a standing pipeline role; user said to evaluate first.
- SemAI mail "Full" button, mute AND-not-OR, and mute-loop-break fixes shipped this session (first one hand-edited by Claude in violation of dispatch-only rule, user approved keeping it after the fact; the rest fully dispatched). See SemAI's own AGENTS.md carryover for the features.

- Cross-platform (Ubuntu/Fedora/macOS): root `scripts/resource_guard.py` no-ops when `systemctl` is absent, instead of crashing on macOS (no systemd). Frozen infra (SALVAGE_PLAN), reattached below.
- Known gap, left as-is: 13 old-dispatcher tests (`tests/`) need a local Ollama server (`mistral-small:latest`). Frozen pipeline, not `rebuild/` (66/66 clean without it) — install only if needed.
- `rebuild/tasks/*.md` are per-run dispatch task descriptions, not pipeline code — gitignored. Ephemeral, often reference a target repo's absolute path from whichever machine dispatched them.
- README.md documents adding a local-model call target to `rebuild/scripts/llm_client.py` as an extension point — none exists today (DeepSeek/OpenRouter/agy only).
- Rebuild Phases 1-3 done (`verify.py`, `dispatch.py`, `cost.py`, resource_guard reattached), 66/66 tests passing; Phase 4 (tier escalation) rejected permanently — see PHASES.md.
- Spend cap: `cost.check_budget`, $5.00 default in `model_config.yaml`, hard-blocks `call_deepseek.py` before the API call, no bypass flag. Confirmed the only call site.
- `call_deepseek.py` falls back to OpenRouter (`nvidia/nemotron-3-ultra-550b-a55b:free`, config in `model_config.yaml`) during DeepSeek peak hours instead of blocking — sanitized via `openrouter_sanitizer.py` (content filter blocks email/phone/IP-shaped tokens).
- OpenRouter still not a general DeepSeek peer — shared rate-limit pool, content-filter/hallucination issues in the old pipeline. The peak-hours fallback is the sole call site.
- Nemotron quirk: 3/3 real calls made an unrequested edit to an unrelated line despite explicit scope instructions (caught, reverted each time).
- Always diff the full response, not just the requested function, on OpenRouter-fallback calls — a real `deepseek-v4-pro` call came back clean (n=1, still worth diffing, just less suspicion).
- `agy.model` pinned to `"gemini-3.8-flash-medium"` in `model_config.yaml` — was `null`, silently inheriting from `~/.gemini/antigravity-cli/settings.json`, shared with other projects.
- Per-concern module split: `tui.py`'s helpers live in 4 `tui_*.py` modules; `llm_client.py`'s sanitizer lives in `openrouter_sanitizer.py`. Split by concern while a file's still small, don't wait for a size ceiling.
- agy wrapped a plain-file reply in a stray triple-backtick fence despite "file content only" instructions (pyproject.toml task) — strip before applying; check future agy file-content calls too.
- Run SemAI tests with its own `.venv/bin/python3 -m pytest`, not system python — `pytest-asyncio` only lives in the venv.
- A1-1's first design (column on `ticker_watch`) got blocked mid-dispatch and replaced by A1-1-fixed (separate `watchlist` table) — 3 queue tasks written against the old design (old A1-2/A2/A3) are now permanently inert, chained to the blocked root task, harmless to leave.

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
