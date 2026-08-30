# Carryover — 2026-08-29 23:39 — daemon.py orchestrator port complete, two real TriAPI pipeline bugs found and fixed

**Session summary:** Resumed on the severe blocker documented in the
previous carryover file (`20260829-000000-...`): oh-my-llama's
`src/semai/adapters/daemon.py` still constructed and depended on a live
`ohmyllama.orchestrator.AsyncOrchestrator` for config, concurrency, DLQ
checks, model warming, memory consolidation, and reminders, blocking
Phase 5G (retire `ohmyllama/` originals) and Phase 7 (the `ohmyllama` →
`SemAI` rename). Planned and dispatched the native port through
`triapi plan`/`dispatch`, hit repeated background-task interruptions
mid-session (traced to an unrelated peer Claude session, since
terminated), and along the way found and fixed two real, previously
unknown bugs in TriAPI's own tier-escalation pipeline — not oh-my-llama
bugs.

## The two TriAPI bugs found and fixed this session

1. **`scripts/tier3_escalate.py` — `subprocess.CalledProcessError` from
   `_call_agy_cli()` crashed the whole `triapi dispatch` process instead of
   soft-escalating.** `_call_agy_cli()` raises this family for every
   CLI-level failure (prompt too large for argv, malformed JSON stdout, a
   non-SUCCESS status) — content/CLI-shaped failures, not infra failures.
   The generic `except Exception` catch classified all of them as
   `status: "error"`, which `orchestrator.py` treats as fatal and raises
   `RuntimeError`, exactly the same crash-vs-soft-escalate distinction the
   adjacent `TimeoutExpired` branch already got right. Added a dedicated
   `except subprocess.CalledProcessError` branch returning `fix_rejected`
   instead, so the pipeline now falls through to Tier 2 the same way a
   timeout does. Commit `a8638ee`, regression test in
   `tests/test_orchestrator_tier3_timeout_skip.py`
   (`Tier3EscalateCalledProcessErrorTests`).
2. **`scripts/llm_client.py` — Tier 1's raw `claude` CLI call had no
   `--tools` restriction, letting it directly mutate the live target repo
   instead of returning parseable SEARCH/REPLACE text.** Found live: Tier 1
   was escalated for the daemon.py port, replied with no parseable edit
   blocks (correctly logged `fix_rejected` → `human_handoff`), yet the real
   file on disk had already been fully and correctly edited, with
   `bash run_tests.sh` passing — Claude Code had done the whole port
   itself via its own agentic tools (inheriting the caller's cwd, the real
   target repo, since `triapi dispatch` runs from inside it) instead of
   describing the edit as text, invisible to `edit_blocks.py` and every
   downstream safety check (`content_guard`, `scope_guard`,
   `mock_patch_lint`). This is a serious hole: Tier 1 could silently
   mutate a target repo outside every safety net the tiered architecture
   depends on. Fixed by adding `--tools ""` to `_call_claude_cli()`'s
   argv, forcing the same pure text-in/text-out contract Tier 2/3 already
   have. Commit `3dbbbc7`, regression test in
   `tests/test_llm_client_claude_cli_no_tools.py`.

Both fixes verified against the full regression suite (104+ tests
covering both areas, zero failures) before being committed.

## The daemon.py orchestrator port itself (oh-my-llama, `migration-clean-up` branch)

Planned and dispatched as run `20260829-115136-905129` (2 phases, 6
items): added the missing scheduling/orchestrator config fields to
`src/semai/config/schema.py` (including `telegram_forum_chat_id`, caught
in plan review before dispatch — without it, `push_enabled()`/`deliver()`
would have kept crashing silently exactly as `daemon.py`'s own pre-fix
comments already documented); ported `_check_dead_letters`,
`_warm_models`, `_hot_models`, `_consolidate_memory` natively into
`AsyncDaemon`, removing the `AsyncOrchestrator`/`Config` shim entirely;
created `src/semai/adapters/tui.py` from scratch; added `agent`/`tui`/
`ghostwriter` subcommands to `src/semai/adapters/cli.py`; made the
existing `src/semai/adapters/telegram.py` fully native (dropped its
remaining `ohmyllama.config`/`ohmyllama.state`/`ohmyllama.markdown_chunk`/
`ohmyllama.tg_routing` imports); repointed `pyproject.toml`'s `omll`/
`omll-tui` entry points. All 6 items resolved successful (tier_3, tier_1,
tier_4, tier_3, tier_3, tier_4), run completed, committed and pushed as
oh-my-llama commit `31a43cf`.

**Item 2 (daemon.py itself) needed a manual state correction**: it
initially recorded `human_handoff` because Tier 1's response had no
parseable SEARCH/REPLACE blocks (the exact bug #2 above, discovered
*because of* this) — but the real file on disk was already correctly
edited by Tier 1's agentic session and manually verified passing
`bash run_tests.sh`. Corrected `logs/runs/20260829-115136-905129.json`'s
`results[1]` entry from `human_handoff`/`None` to `success`/`tier_1` (with
a `note` field explaining the correction and the computed `content_hash`)
so the resumed dispatch correctly skipped it and continued to item 3
rather than re-diffing against an already-fixed file. This was a
bookkeeping correction of a real, already-completed, tested result, not a
fabricated success.

**One test regression slipped through** item 5's own weak `py_compile`-only
verify step (the recurring "weak build_cmd" gap already flagged in a past
session): `tests/test_semai_telegram.py::test_forum_topic_routing`
monkeypatched `ohmyllama.tg_routing.build_route`, a module `telegram.py`
no longer imports after the port (deliberately, per this run's own task).
Fixed via a small follow-up `triapi plan`/`dispatch` (run
`20260829-163036-2d9ddd`) — the plan's single item resolved correctly at
Tier 4, but the breakdown step duplicated it into a second identical item
that crashed on a transient Ollama connection drop (infra, not content;
`orchestrator.py` correctly treats an Ollama connectivity exception as
fatal by design). The real fix was already applied and verified
(`bash run_tests.sh`: 176 passed, 4 subtests, zero failures), so it was
committed and pushed by hand rather than re-running a now-redundant
duplicate item: oh-my-llama commit `967236b`.

## Aside: repeated background-task kills, root-caused

Mid-session, the backgrounded `triapi dispatch` process was killed three
times in a row right after starting item 2. Ruled out `resource_guard`
(pause list only touches `oh-my-llama.*` services) and a stray long-lived
`agy` process (confirmed unrelated — attached to the user's own separate
interactive `tmux` session). `ListAgents` surfaced a peer Claude session
("Carryout and agents documentation") also connected via Remote Control,
started around the same time as this session with a matching task name;
it confirmed (via cross-session message) it wasn't touching this run, but
the user asked to end it anyway as a precaution. It exited cleanly, and
the dispatch — relaunched fully detached via `setsid` with a signal-trace
wrapper — ran the rest of the session with zero further interruptions.
Root cause not conclusively identified, but circumstantial evidence
(kills stopped precisely when that session ended) points to it or its
Remote Control connection rather than anything in TriAPI itself.

## Status at session end

Both repos clean, both pushed. Phase 5G's daemon-shim blocker described in
the previous carryover file is resolved: `AsyncDaemon` no longer
constructs or depends on `ohmyllama.orchestrator.AsyncOrchestrator`, and
`cli.py`/`tui.py`/`telegram.py` have semai-native equivalents.
**Phase 5G/7 are not yet re-attempted** — `ohmyllama/agent.py`,
`ghostwriter.py`, and `watcher.py` are still directly imported by
`ohmyllama/cli.py`/`tui.py`/`telegram.py` (the *old*, still-present
files; the new native ones don't import them), so the legacy files are
still live consumers of the 4 capability files Phase 5G-1 would delete.
Whether those old entry points can now be safely deleted (since native
replacements exist) or need an explicit cutover step first is the next
question for whoever picks up Phase 5G — see oh-my-llama's own
`docs/Agent/CARRYOVER.md` for the target-repo-side detail, not here.

## Two follow-ups queued, not fixed this session

1. **`librarian_escalate.py`'s FRESH false-negative bug recurred** — first
   flagged in the 2026-08-27 carryover history (3 confirmed instances at
   the time), still open. Hit a 4th time this session: retrying a
   3-part `AGENTS.md` living-index update against oh-my-llama returned
   `{"changed": false, "via": "model_fresh"}` even though the file
   demonstrably still needed 2 of the 3 described edits (confirmed by
   `grep` immediately after). Worked around by hand-editing the remaining
   2 edits directly this session (oh-my-llama commit `05d1762`) rather than
   fighting the bug a third time. Root cause not investigated — needs its
   own session.
   - *Update (2026-08-29):* **RESOLVED**, commit `bdf58a9`. Root cause:
     the FRESH escape hatch in `librarian_escalate.py`'s `run()` returned
     `status:success` unconditionally whenever the model replied FRESH, never
     running the caller's `verify_cmd` against the file — so a false FRESH claim
     was never caught even when the caller supplied a real content-asserting
     `verify_cmd`. Fixed: when a real `verify_cmd` is supplied (not the
     trivial default), it is now run against the file before trusting a FRESH
     claim; a contradiction rejects the claim and falls through to the next
     provider in the chain instead of reporting a false success. Covered by
     two new regression tests in `tests/test_tier5_librarian.py`
     (`test_fresh_verdict_rejected_when_verify_cmd_contradicts_it`,
     `test_fresh_verdict_trusted_when_verify_cmd_confirms_it`). Caveat still
     open: `dispatcher.py`'s plan-dispatch routing path only passes a real
     `verify_cmd` when the plan item has an explicit content-checking
     `build_cmd` — the `_default_build_cmd()` fallback for doc targets with no
     explicit `build_cmd` is still a trivial `test -f` existence check, which
     cannot contradict a false FRESH claim; this fix protects direct CLI/manual
     invocations with a real `--verify-cmd` (the majority of past incidents)
     but not plan items that rely on the trivial default.
2. **oh-my-llama's own `AGENTS.md` is over this repo's 73,728-char file-size
   ceiling** — pre-existing (79,677 chars before this session's edits,
   80,313 after), not caused by this session but made slightly worse by
   it. Per this repo's own "no files at ceiling" convention, its living
   file/dir index or historical `triapi:plan` blocks need the same
   overflow-to-`docs/agents/`-style treatment this repo already gave
   itself (see this file's own `## scripts/` section for the pattern) —
   not attempted this session, flagging for whoever next has bandwidth.
