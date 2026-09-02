# Carryover — 2026-09-02 (late) — oh-my-llama Phase 7 rename COMPLETE, 3 more TriAPI bugs fixed

**Status: RESOLVED.** Both oh-my-llama runs from this session finished
`completed`. Live services healthy, full test suite green, everything
committed. Nothing pending; this is a clean session-end record, not an
active carryover.

## What this session covered

Picked up from `20260902-064500-ohmyllama-phase7-rename-in-progress-3-more-triapi-bugs-fixed.md`
(now history) — resumed the paused Phase 7 rename dispatch (run
`20260901-230714-ebd3c2`).

### 1. TriAPI bug-queue cleanup (3 more real bugs found+fixed+committed)

- **`_force_verify_only_for_pure_deletions()` never fired when the
  planner's build_cmd had no `rm` at all** — FIXED (commit `f0502d8`).
  Previously only forced `verify_only=True` when build_cmd already
  contained a real `rm`; a planner-written bare existence check (no `rm`,
  and backwards besides — `find`/`ls` succeed when the file IS present)
  fell through to the fragile LLM SEARCH/REPLACE path for a whole-file
  deletion, crashing Tier 4/3/2 repeatedly on a plain `rm scratch.py`. Now
  synthesizes a correct `rm -rf <target> && ! test -e <target>` build_cmd
  whenever a detected deletion item doesn't already have a real `rm`.
- **Tier 2/3 real API/CLI failures crashed the whole `triapi dispatch`
  process instead of soft-escalating** — FIXED (commit `85755cd`).
  `tier2_escalate.py` only downgraded a *synthetic* `CalledProcessError`
  (returncode==0) to "skipped"; a genuinely non-zero agy CLI exit crashed
  dispatch. Neither tier caught `requests.exceptions.HTTPError` (raised by
  `llm_client._primary_request` for a real 4xx/5xx OR a 200 with null
  message content — hit twice this session on OpenRouter free models).
  Both tiers now soft-escalate on both. A pre-existing regression test
  (`test_branch_features.py::test_escalate_with_null_content_returns_failure_and_preserves_file`)
  had been failing before this fix; passes now.
- **Tier 4 assumed every provider is local Ollama, crashing on OpenRouter
  upstream errors** — FIXED (commit `37baf34`). `orchestrator.run_task`'s
  Tier 4 exception handler re-raised everything on the assumption a
  connectivity failure can't be routed around by lower tiers — true for
  Ollama, not true when `tier_4_worker` is config-pointed at OpenRouter
  (as it was this session) and hits the same transient-502/null-content
  shape Tier 2/3 already handle. Now escalates `HTTPError` to Tier 3
  instead of crashing; every other exception still crashes as before.

All three verified: full TriAPI suite green (287 pytest + 279 unittest,
both 100%) after each fix, and the third fix proved itself live minutes
later — the exact same Nvidia free-model 502 recurred and correctly
escalated instead of crashing.

### 2. oh-my-llama Phase 7 package rename — COMPLETE

Run `20260901-230714-ebd3c2` (the original Phase 7 A/B/C/D plan) finished
`completed`. `pyproject.toml` name is `semai`, `ohmyllama/` directory
deleted, live services reinstalled+verified, `docs/Agent/CARRYOVER.md` and
`docs/decisions/0005-rename-timing.md` closed out by the librarian tier.

Along the way, resuming Phase C's `pyproject.toml` include-list edit
surfaced that deleting `ohmyllama/` broke the test suite in ways the
original plan's premise ("zero real importers left... in `src/semai/`")
never checked (it only grepped `src/semai/`, not `tests/`, and only
top-of-file imports, not function-local/lazy ones). This spawned a
second, separate dispatch run (`20260902-005154-7f74ad`, refactor-gated
past the one-plan-per-repo lock since it directly unblocked the paused
Phase 7 run) that also finished `completed` — 16 items across 4 phases:

- 3 disposable root scratch files deleted (`scratch.py`, `scratch2.py`,
  `test_remnants.py` — not part of `run_tests.sh`, dead ad-hoc scripts).
- `strip_reasoning` ported from legacy `ohmyllama/llm.py` into
  `src/semai/providers/ollama.py` (module-level, correct `<think>...
  </think>` regex) — took 3 dispatch attempts: first two left it nested
  inside the class (wrong scope) with the wrong tag pattern, and once
  dropped `OllamaProvider.__init__`'s `timeout_s` default entirely.
- **A real, deeper gap found, not just a test-import fix**:
  `src/semai/adapters/task_store.py`'s `TaskStore` had the write-side
  fact-history snapshotting (`_snapshot_fact`) but was missing the
  read-side `fact_history()`/`revert_fact()` methods — a genuinely
  dropped user-facing feature (revert a fact to a prior version), not
  test debt. Ported verbatim from legacy `ohmyllama/state.py`.
- `tests/test_browser.py`'s elaborate `_load_browser_module()` importlib
  shim (a pre-port workaround) replaced with a plain
  `from semai.capabilities import browser` import — the real module
  already existed and exported everything the test needed.
- 4 more files with *function-local* (indented, lazy) `ohmyllama.*`
  imports that an anchored `^from ohmyllama` grep missed entirely:
  `test_retriever_seam.py`, `test_indexer_seam.py`, `test_vault_seam.py`,
  `test_mail_watcher_seam.py` — all fixed to their real `semai.*`
  equivalents.
- `tests/test_voting.py`'s role-resolution logic (`DEFAULT_LITERATURE_
  MODELS`) turned out NOT dropped, just moved to
  `src/semai/workers/ghostwriter.py` (`literature_pool`/
  `resolve_literature_model`) — caught via investigation before the
  planner's own turn tried to delete that test coverage outright.

**Live incident, self-recovered**: the `uv tool install --editable`
install symlinks live code straight from the repo source, so the
mid-flight broken intermediate state of `ollama.py` (nested/wrong
`strip_reasoning`, then the missing `timeout_s` default) briefly hit the
running `oh-my-llama.service`/`oh-my-llama-telegram.service` each time
`systemctl restart` fired around a dispatch attempt. Systemd's crash-loop
rate limiter ("Start request repeated too quickly") eventually gave up
and left both services in `failed` state for roughly 3 hours before this
was noticed (a stale `triapi.log` tail read at the time made it look like
current activity rather than a ~3h-old crash). Root-caused, hand-restored
the dropped `timeout_s` default directly (a live-incident hotfix judgment
call, not routed through the pipeline given the acute outage), reset
systemd's failure counter, and restarted — both confirmed `active` with
clean logs. **If touching `oh-my-llama`'s live-installed source files
again: verify service health more frequently during multi-attempt fix
loops on files the daemon imports at startup, not just at the end.**

Three regression-check false positives also came up during the final
`ebd3c2` dispatch (after the `pyproject.toml` include-list edit and both
Phase D doc edits) — all the same signature: the shared regression-check
`build_cmd` (`bash run_tests.sh && systemctl ...`) cut off mid-suite
during a slow `flashrank`/`jina-reranker` model download in a RAG-heavy
test, never an actual assertion failure. Independently verified `bash
run_tests.sh` passes cleanly (exit 0) multiple times directly; all three
flags manually marked resolved with a note. **Worth a real fix later**:
either pre-cache/mock the flashrank model download in tests, or give the
regression-check `build_cmd` a longer timeout / split it so a slow
RAG test can't false-flag an unrelated file edit as a regression.

## Final verified state (both repos)

- TriAPI: 3 commits (`f0502d8`, `85755cd`, `37baf34`) + 1 docs commit
  (`6d86ad6`), full local suite green.
- oh-my-llama: single squashed auto-commit (`699028f`) covering both
  dispatch runs' changes (git_ops auto-commits on `completed` status);
  `bash run_tests.sh` exit 0, "All tests passed successfully!";
  `oh-my-llama.service`/`oh-my-llama-telegram.service` both `active`,
  clean startup logs, no traceback; `pyproject.toml` name=`semai`,
  `ohmyllama/` directory gone.

## Nothing queued from this session

The flashrank-download regression-check flakiness above is worth fixing
eventually but is not urgent (doesn't block anything, false positive is
easy to recognize and resolve manually when it recurs).
