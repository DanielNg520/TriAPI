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

Test command: `cd rebuild && python3 -m pytest -v tests/` (100/100, 2026-09-11)

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

## Doc policy

One file only: this one. Carryover is the section below, not a separate file.
Hard cap: 1000 lines, 30 words per line. Precise, worth-noting entries only, no narrative.
Once work is done, delete its line entirely — don't move it to an archive file. Git history has it.
A removed/retired feature gets zero doc trace: no "X removed" line, no rationale footnote, nothing.
A pending removal task states the action only ("delete file X"), never the reasoning for removing it.
This repo's docs never reference or absorb another repo's content — relocate that repo's own docs there instead, never delete it.
This policy applies to every repo TriAPI supervises, not just this one — check each target repo's own AGENTS.md follows it too.
Hard rule: wrap-up always ends with `git push` right after committing, not just a local commit. This repo runs on multiple machines (git is the only sync path in use) — a commit that never leaves the local machine is what caused the two copies to diverge before (see 2026-09-12 reconciliation in git log).

## Carryover (current state, 2026-09-13)

- SemAI ghostwriter mechanism port (root Ghostwriter → SemAI, full detail in SemAI's own AGENTS.md): 6 queued tasks (5 DeepSeek + 1 settings field) all clean first-pass, plus Claude's own constructor-level wiring (run_job/_refine_draft) and one mechanical correction (ai_score wired to a new resolve_ai_score_model, not the drafting literature pool, per plan). 1 agy test task (stray code-fence quirk again, stripped before applying). Resource-guard pause/resume around one DeepSeek call tripped systemd's start-limit, downing both live SemAI services for ~1min — caught immediately via `systemctl is-active`, reset-failed+start restored both. 189/189 SemAI pytest + all script suites pass, 0 regressions.
- Full supervisor audit of SemAI: 5 issues found and dispatched (async daemon loop, silent-failure logging, path-guard drift, missing import, `_poll_cleanup` test gap). The test task took 3 rejected DeepSeek rounds (hallucinated `log_sent_message` kwarg, wrong `_calls`/`expired_message_ids` tuple shapes, wrong await on a sync method) before a clean reply — plus one own-authored assertion bug (TTL=0.0 also flags fresh messages) and one missing `DummyConfig` fixture field, both fixed directly as mechanical, no-design-decision corrections. Mid-session, the resource-guard pause/resume around a DeepSeek call hit systemd's start-limit and left SemAI's live services down for ~15s until `reset-failed`+`start` — worth a live `systemctl is-active` check right after any dispatch that pauses services, not just at session end. 6 files changed in SemAI (`a21fa8a`, pushed), 175/175 pytest + all script suites pass.
- SemAI's ADR-0019 (autonomous Notion database provisioning, amends ADR-0018) also fully dispatched and shipped this session, same session as ADR-0018 above: 8 tasks, `NotionClient.create_database`/`ensure_database` backed by `TaskStore.meta_get`/`meta_set` (create-once-cache-forever, no new table needed), `available()` narrowed to token-only, fixed schema constants. 7 new tests, 2 commits pushed (design ADR separate from implementation, same split as ADR-0018). One agy reply duplicated its entire output into two identical fenced code blocks — used the first, no functional issue, just a formatting quirk worth watching for on future agy calls (take the first complete block, don't assume a single clean reply).

- SemAI's ADR-0018 (bidirectional Notion: actions core, stocks watchlist extension, email/calendar categorized export) fully dispatched and shipped this session: 22 originally-planned tasks plus ~14 inserted sub-tasks (settings fields, missed skeleton pieces, a topic-registration gap, a golden-set/kind-count fixup), all via this same claim→dispatch→review→apply→verify→complete cycle, no loop automation used (plain sequential supervision). 5 new SemAI test files, full suite green throughout (156→164 pytest passes as sections landed), 8 commits pushed. Real bugs caught in review before applying (not sent back — fixed mechanically, no design decision involved): a `sqlite3.Row.get()` call (no such method) in a DeepSeek reply; an inverted conflict-resolution skip-list that would have let a stale local push immediately clobber a Notion-wins resolution; a golden-set fixture example phrased ambiguously enough to collide with an existing deterministic rule.
- One dispatch-discipline near-miss, self-caught via the standing "re-read the file before dispatching a task that touches it" rule: a `CreateReminderWorker` edit task was drafted from a stale hand-copied snapshot of `reminder.py` (remembered from earlier in the session) instead of the file's actual current on-disk content, which had been updated by a concurrent unrelated commit. The stale prompt would have produced a reply that regressed `make_check_reminders_worker` to an older implementation. Caught by diffing the reply against a freshly-`cat`'d copy before applying, not by any special vigilance — reinforces that this rule needs mechanical re-reading (a fresh `cat`/Read call), not memory of "what the file probably still looks like," even within the same session.
- `triapi add --depends-on` only stores a single free-text value — passing multiple space-joined ids (attempting a multi-parent dependency) silently corrupts the column (stored as a literal multi-id string, or empty/whitespace if the shell variables were unset in a later command), which only surfaces later as a cryptic "depends on X which is not done" from `claim`. Fixed post-hoc via direct sqlite `UPDATE` to a single valid parent per affected task. `task_queue.py`'s schema is genuinely single-parent only — don't pass more than one id to `--depends-on`, and validate a chain's dependencies resolve to real, existing task ids immediately after a bulk `add` sequence, not just when a claim happens to fail.
- Two `complete` calls were silently missed among a long dispatch sequence (found via a post-hoc `select status, count(*) from tasks group by status` sweep, not proactively) — one task sat `in_progress` with its actual code change already applied, reviewed, and committed. Completed retroactively. Worth a periodic status sweep on a long solo dispatch run, not just trusting that every `triapi complete` call in a long command sequence actually landed.
- Second same-session run of SemAI's daily-briefing/movement-alert stocks refactor (per-ticker messages, LLM-summarized link-free bullets, no shared header) took 4 queue tasks + 1 dependent test-fix task, 9 total dispatch rounds (avg ~1.8 rejections per task) before all passed audit — recurring DeepSeek failure modes this round: dropping/mangling a requested method signature entirely even when explicitly requested to fix only one line of it (fixed by showing DeepSeek its own prior near-correct draft back and asking for one narrow addition, rather than re-describing the target behavior again); a multi-point checklist correction (7 items) landing only 2 of 7 on the first retry, needing a second correction naming the exact one item still missed; a test-file edit request returning the file byte-for-byte unchanged (zero edits applied) until given literal FIND/REPLACE text instead of a behavioral description — for test-file edits specifically, prefer literal diffs over behavioral prose from the first attempt, not as a fallback after a no-op reply. One genuine double-delivery bug caught (kept a `deliver()` call on top of a method that now self-delivers internally) — always check for redundant side effects, not just missing ones, when a call site's callee contract changes.
- Plain (non-VCB) dispatch this session for SemAI's morning-briefing stocks feature caught two dispatch-discipline slips (mid-session, flagged by the user): early task prompts spelled out finished code instead of signature+behavior, and both DeepSeek and Claude repeated the same class of bug — mock news items as dicts instead of `NewsItem` attribute access. Every task from that point on stayed signature/behavior-only; DeepSeek's own bugs (test double signature mismatches, a wrong constructor arity, a `now` variable shadowing bug in daemon.py, a `.get()` on a frozen dataclass) get caught by verify-before-apply and either sent back with a precise fix description or hand-fixed directly when purely mechanical (no design decision) — never silently applied.
- VCB's first live dispatch against an external target repo (SemAI's `src/semai/adapters/stocks.py`, target symbol `price`, silent-exception-swallow fix) ran the full Slicer→Planner(Nemotron)→Materializer(DeepSeek) chain end to end and produced a clean, minimal, exactly-scoped diff on the first try. Applied via the dispatch-gate escape hatch; SemAI's full suite (143 tests) still passes.
- Bug that dispatch surfaced: `vcb_slicer.run_single_symbol`/`build_skeleton` called `codegraph node <symbol> -p <repo_path>` with no file disambiguation, so a symbol name that isn't unique repo-wide (e.g. a method also matched by a same-named local variable elsewhere) made `codegraph` return a multi-match listing and `parse_single_symbol_output` raise. Fixed: `run_single_symbol` takes an optional `file_path`, passed as `-f <file_path>` (codegraph's documented disambiguation flag) whenever `build_skeleton` already knows the file. Test added (`test_run_single_symbol_with_file_path`). 100/100 rebuild tests pass.
- `~/.claude/hooks/dispatch-gate.sh` (global PreToolUse hook on Edit|Write|NotebookEdit): escalated 2026-09-09 from a nudge (`permissionDecision: allow` + reminder) to a **hard `deny`** on any path listed in `~/.claude/dispatch-gate-paths.txt` (gated target-repo dirs plus this repo's `rebuild/scripts`/`rebuild/tests`; the actual target-repo paths live only in that file, not named here) — the nudge kept getting ignored under task momentum despite repeated memory tightening. Escape hatch: `~/.claude/hooks/dispatch-gate-arm.sh <ttl_seconds> <file>...` writes a single-use, short-TTL marker (`~/.claude/dispatch-gate-armed.json`) that the hook consumes on the next matching Edit/Write for that exact path; run it immediately before applying an already-reviewed DeepSeek/agy response, or before a hand fix the user explicitly approves in the moment. Live-tested 2026-09-09: real Edit denied with no marker, allowed once after arming, denied again on reuse (single-use), denied on an expired marker. Still relies on Claude choosing to run the arm command honestly, but converts a silent drift into a hand-edit into a deliberate, separately-timed, auditable action instead of a same-call self-check that's easy to skip.
- Nemotron promoted from one-off trial to a standing Planner role: `rebuild/scripts/call_planner.py` + `llm_client.execute_planner()` + `config/model_config.yaml`'s `planner:` section, documented in `rebuild/README.md`. Not gated by DeepSeek peak-hours; shares the OpenRouter free-tier rate-limit pool with that fallback role. Hub-and-spoke unchanged: planner drafts route through Claude before becoming queue tasks, never straight to DeepSeek/agy. 69/69 rebuild tests pass, live end-to-end call confirmed.
- Third same-session recurrence of the finished-code-in-prompt violation (this time as a full reference file pasted + line-by-line mirror instructions for a new file) — caught by the user, not self-caught despite having just fixed the rule twice earlier the same day and built a hook meant to catch exactly this. Output was correct and kept per user call, but the pattern needs active attention at the start of every dispatch prompt, not just when editing an existing file.
- CodeGraph: installed system-wide (`~/.local/bin/codegraph`, v1.6.0, upgraded from v1.5.0 this session). `codegraph init` run for TriAPI (1,839 nodes/3,543 edges, 120 files) — this repo had no index before. Machine-wide rollout status (other repos indexed/re-indexed) is a supervisor-level fact, not TriAPI's own — tracked in memory (`project` type), not here.
- Hands-on tested `codegraph node <file> --symbols-only` (deterministic full signature map of a file's top-level functions/classes/methods/vars, no relevance filtering) and `codegraph node <symbol>` (one symbol's full verbatim source + call trail) — both confirmed via `Nodes by Kind` in `codegraph status` to track imports too as their own node kind, contrary to an earlier assumption that `--symbols-only`'s text output omits them; worth re-checking the actual CLI output shape (not just node-kind counts) before the Virtual Codebase Plan's assembly module depends on it.
- Virtual Codebase Plan: Slicer/Patcher/Materializer all shipped this session — see Future plans below for full current status, don't duplicate here as it progresses.
- Cross-platform (Ubuntu/Fedora/macOS): root `scripts/resource_guard.py` no-ops when `systemctl` is absent, instead of crashing on macOS (no systemd). Frozen infra (SALVAGE_PLAN), reattached below.
- Ollama gap resolved 2026-09-10: `ollama` was already installed (`~/.local/bin/ollama`, v0.32.5) with `mistral-small:latest` pulled and `ollama serve` running (pid confirmed, `/api/tags` responds). Full `tests/` suite: 352 passed, 0 skipped, no real-server dependency triggered — the old "13 tests need a local Ollama server" note no longer reproduces and is removed. Those old-dispatcher tests mock the Ollama call site (`scripts/llm_client.py`'s `provider == "ollama"` branch, `tier_5_librarian`'s endpoint), so a live server was never actually required for them to pass.
- `rebuild/tasks/*.md` are per-run dispatch task descriptions, not pipeline code — gitignored. Ephemeral, often reference a target repo's absolute path from whichever machine dispatched them.
- `rebuild/scripts/llm_client.py` calls no local model today — cloud only (DeepSeek, OpenRouter peak-hours fallback, Planner/nemotron, plus local `agy` CLI which is not Ollama). Ollama/Gemini/Claude-CLI were deliberately dropped in the salvage rebuild (see its module docstring). README documents adding a local-model call target back in as an extension point, unimplemented — the frozen `scripts/llm_client.py` (old pipeline) is the one with an actual `ollama` provider branch, used by `tier_5_librarian`.
- Queue purged 2026-09-10: removed 3 `approved` + 1 `blocked` permanently-inert tasks (chained to a design that got replaced mid-dispatch, target-repo specifics live in that repo's own AGENTS.md) and 1 stray "test task, ignore" (`pending`) from `rebuild/queue.sqlite3`. Queue is now empty except 86 `done`.
- Rebuild Phases 1-3 done (`verify.py`, `dispatch.py`, `cost.py`, resource_guard reattached), 66/66 tests passing; Phase 4 (tier escalation) rejected permanently — see PHASES.md.
- Spend cap: `cost.check_budget`, $5.00 default in `model_config.yaml`, hard-blocks `call_deepseek.py` before the API call, no bypass flag. Confirmed the only call site.
- `call_deepseek.py` falls back to OpenRouter (`nvidia/nemotron-3-ultra-550b-a55b:free`, config in `model_config.yaml`) during DeepSeek peak hours instead of blocking — sanitized via `openrouter_sanitizer.py` (content filter blocks email/phone/IP-shaped tokens).
- OpenRouter still not a general DeepSeek peer — shared rate-limit pool, content-filter/hallucination issues in the old pipeline. The peak-hours fallback is the sole call site.
- Nemotron quirk: 3/3 real calls made an unrequested edit to an unrelated line despite explicit scope instructions (caught, reverted each time).
- Always diff the full response, not just the requested function, on OpenRouter-fallback calls — a real `deepseek-v4-pro` call came back clean (n=1, still worth diffing, just less suspicion).
- `agy.model` pinned to `"gemini-3.8-flash-medium"` in `model_config.yaml` — was `null`, silently inheriting from `~/.gemini/antigravity-cli/settings.json`, shared with other projects.
- Per-concern module split: `tui.py`'s helpers live in 4 `tui_*.py` modules; `llm_client.py`'s sanitizer lives in `openrouter_sanitizer.py`. Split by concern while a file's still small, don't wait for a size ceiling.
- agy wrapped a plain-file reply in a stray triple-backtick fence despite "file content only" instructions (pyproject.toml task) — strip before applying; check future agy file-content calls too.
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
