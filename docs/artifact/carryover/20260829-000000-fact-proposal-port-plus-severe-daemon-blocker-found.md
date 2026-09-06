# Carryover — 2026-08-29 00:00 — fact-proposal port complete, Phase 5G/7 blocked by daemon shim

**Session summary:** Resumed oh-my-llama's Phase 5G (retire `ohmyllama/`
runtime originals). First attempt found a real feature regression, not a
pipeline bug — `build_fact_proposal()`'s provenance safety gate was never
ported to `src/semai` during Sub-Phases 5A-5F. Deleted files were
restored via `git checkout` (nothing had been committed), and the gap was
ported properly across 4 supervised `triapi plan`/`dispatch` runs this
session, fully verified, then a re-attempt at the actual Phase 5G
deletions surfaced a *second, more severe* blocker.

## What got done (all committed, oh-my-llama branch `migration-clean-up`)

1. **`RememberFactWorker`** (`src/semai/workers/memory_ops.py`) — converted
   `remember_fact` from an immediately-executing plain `Worker` to an
   `ApprovalRequiredWorker` (propose/execute split), porting the old
   `build_fact_proposal()`'s exact validation (strip/collapse whitespace,
   reject empty, reject over `FACT_MAX_CHARS`).
2. **Provenance-check gate** (`src/semai/agent.py`) — `Agent._dispatch()`'s
   `propose_remember_fact` tool now refuses if any other tool was called
   earlier the same turn, citing them by name — the exact safety property
   the old `ohmyllama/agent.py` had and the new one silently dropped.
3. **Daemon proposal routing** (`src/semai/adapters/daemon.py`) — the
   agent-fallback branch previously discarded `AgentResult.proposals`
   entirely (used only `.answer`); now persists the first proposal via
   the same `ApprovalStore` the Dispatcher path uses, and suspends the
   task pending human approval — without this, the provenance-gated
   `propose_remember_fact` tool would have queued proposals that were
   silently thrown away, never actually completing an approval flow.
4. **`ohmyllama/rag.py`** — `ingest_file()`'s non-md/txt/csv branch now
   calls `src/semai/workers/ingester.py`'s `make_ingest_worker()` instead
   of the deleted `DocumentIngester` (a deliberate allowed-roots
   narrowing vs. the old unrestricted-path behavior).
5. **Test fallout** — `tests/test_agent_memory.py` retired, replaced by
   `tests/test_semai_agent_propose_remember.py` (6 real assertions, real
   mocking, no LLM/network calls); `tests/test_terminal_sandbox.py` and
   `tests/test_ingestion_html.py` deleted (superseded by
   `tests/test_terminal_worker.py`/`test_ingester_worker.py`);
   `tests/test_memory_ops.py`, `tests/test_memory_gaps_seam.py`,
   `tests/test_cli_workers_seam.py`, `tests/test_semai_daemon.py` all
   updated for the new propose/execute worker shape;
   `docs/semai-preflight-p6-report.md` (auto-generated) regenerated.
6. **Two real bugs found by manual post-dispatch audit** (not caught by
   `bash run_tests.sh`, since nothing exercised the code path): the
   `rag.py` fix used `result.text` (doesn't exist on `Result`, should be
   `.message`) and constructed `IngestDocument(path=...)` missing
   required `kind`/`confidence`/`raw_utterance` fields — both silently
   masked by a bare `except Exception: text = ""`. Fixed, plus a new
   regression test (`tests/test_rag_ingest_file.py`) added since this
   exact bug shape had zero prior coverage.
7. **Full verification**: `bash run_tests.sh` green — 176 pytest passed +
   4 subtests, all script suites passed, zero failures, zero skips beyond
   the pre-existing known set. oh-my-llama commits `7257174`, `64f1e73`.

## The severe blocker found afterward (nothing deleted/renamed as a result)

Re-attempting the actual Phase 5G-1/5G-2 file deletions (this session's
original goal) surfaced that `src/semai/adapters/daemon.py`'s
`AsyncDaemon.__init__` constructs a **real, live**
`ohmyllama.orchestrator.AsyncOrchestrator(Config.load())` instance and
depends on it throughout the daemon's main loop — config, concurrency
slots, dead-letter-queue checks, model warming, memory consolidation,
reminders. This is core, currently-running plumbing, not vestigial —
deleting `ohmyllama/orchestrator.py` would break the live daemon outright.
`ohmyllama/agent.py`, `ghostwriter.py`, and `watcher.py` are also still
directly imported by `ohmyllama/cli.py`/`tui.py`/`telegram.py`, and are
themselves the consumers of 3 of the 4 capability files Phase 5G-1 would
delete. **Full detail and the recommended next step are documented in
oh-my-llama's own `docs/Agent/CARRYOVER.md`** (per house rule, that
target-repo narrative lives there, not here) — commit `b184d03`.

**User also asked this session for the full `ohmyllama` → `SemAI` package
rename (Phase 7).** Given the same finding — the semai port isn't
feature-complete enough to retire the old runtime files yet — attempting
that rename right now would touch the exact same live-dependency web.
Declined to attempt it autonomously while the user was unreachable
overnight; no reboot was performed. This needs the user's explicit
go-ahead once the daemon's orchestrator shim is replaced with a native
semai implementation (see oh-my-llama's CARRYOVER.md point 4 for the
concrete scope: config loading, concurrency, DLQ, model warming, memory
consolidation, reminders need native semai homes first).

## TriAPI-side fixes made this session (this repo, already committed)

- `scripts/dispatcher.py`: `_force_verify_only_for_pure_deletions()` —
  whole-file-deletion plan items now correctly bypass the LLM
  SEARCH/REPLACE edit-block path (found live: an identically-shaped
  deletion item was inconsistently marked `verify_only` by the planner,
  causing one to succeed and one to fail across every tier). Commit
  `99df062`, tests in
  `tests/test_file_size_ceiling_and_oversize_escalation.py`.
- `AGENTS.md`: corrected a stale claim that the `agy` argv-too-long bug
  was still open — it was fixed same-day in `3cbdeba`. Commit `8024aa6`.
- `knowledge/hivemind.md`: auto-captured 5 reusable patterns from
  tonight's real dispatch work (approval-gate propose/execute split,
  provenance mutual-exclusivity check, human-in-the-loop suspend/resume,
  allowed-roots file access narrowing, handwritten-test-fake-drift
  lesson). Commit `3c871d0`.

Nothing mid-flight in either repo. Both working trees clean.
