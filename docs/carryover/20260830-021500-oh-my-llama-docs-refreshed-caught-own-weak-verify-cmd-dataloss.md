# Carryover — 2026-08-30 02:15 — oh-my-llama docs refreshed for new session; caught a real content-loss bug in my own plan

**Session summary:** User asked what's queued in both repos, then to
refresh all docs for a fresh session. Verified oh-my-llama's own
`CARRYOVER.md` was stale (claimed the `AGENTS.md`/`MAPPING.md` cleanup was
still queued — already done last session) and that 4 of the 5 plan blocks
excluded from that fold were actually already resolved, just never
checked off. Dispatched a docs-refresh run; **the dispatch silently
deleted content it was explicitly told to preserve**, caught only because
I verify tier-reported `success` against the actual file instead of
trusting the status line. Fixed by hand (git-history recovery), verified,
committed, pushed. No TriAPI code changed — the bug was in my own plan
prompt, not the pipeline.

## Verified oh-my-llama's real queue (its own `CARRYOVER.md` was stale)

- `AGENTS.md`/`MAPPING.md` size cleanup: already done (previous session).
- 4 of 5 previously-"incomplete" plan blocks (`test_cli_workers_seam.py`,
  `test_memory_ops.py`, Telegram service `ExecStart`, fact-proposal
  provenance port) are actually resolved — confirmed by running
  `bash run_tests.sh` (the repo's real test runner; a bare `python3 -m
  pytest` gave false failures from a wrong interpreter/missing
  `pytest-asyncio`, worth remembering: **always use the target repo's own
  test command, never assume `python3 -m pytest` matches it**).
- Only 1 of the 5 is genuinely still open: Sub-Phase 5G
  (`ohmyllama/cli.py`/`tui.py`/`telegram.py` still import the old
  `agent.py`/`ghostwriter.py`/`watcher.py` instead of the semai-native
  replacements).
- User separately confirmed the parked "openclaw Telegram channel" stale
  BotFather token item is resolved (new token in place).

## Bug found and fixed: my own plan gave a tautological `verify_cmd` for a delete-with-preservation task

Dispatched a 4-item docs-refresh run (`20260830-015733-8a2baf`) to: append
the 4 newly-confirmed-resolved blocks (+ the prior run's own already-complete
plan block) to the existing `docs/agents/` archive, update its
`index.json`, prune those same ranges out of `AGENTS.md` while explicitly
preserving the one still-open block, and rewrite oh-my-llama's
`CARRYOVER.md`. All 4 items reported `success`.

**On verification, the `AGENTS.md`-prune item had deleted the block it was
told to preserve** (`20260828-182931-264248`, Sub-Phase 5G) — gone from
both `AGENTS.md` and the archive file, a genuine content-loss regression,
already committed and pushed by the pipeline before I checked. Root cause:
the plan item's own `verify_cmd` (which I wrote, in the plan prompt) was
`wc -c AGENTS.md && grep -c 'triapi:plan run_id=' AGENTS.md` — this asserts
*a* count changed, never *which* content survived, so it could not have
caught "wrong content deleted" even in principle. This is the same failure
class `AGENT_GUIDE.md` already documents ("a check that's tautological...
doesn't actually assert the described change happened") — I wrote a weak
check for a task with a preservation constraint, and content_guard's
survival-ratio check doesn't help here either, since a large deletion is
the *intended* shape of a prune task and can't be distinguished from an
over-deletion by size alone.

Separately, the append step (`sed ... >> archive.md`) ran **twice**,
duplicating the 5 newly-appended blocks in the archive file (60,773 chars
instead of the expected 48,424) — consistent with the same
`verify_cmd == build_cmd, re-run unconditionally on any accepted write`
mechanic already documented in the two prior carryover files this
session, now confirmed to also duplicate output for a non-idempotent
`>>` command specifically.

**Fixed by hand** (last resort was warranted: the content was already
gone from both live locations, recoverable only from git history, and
git-based recovery isn't itself an LLM-suited task): recovered the exact
lost block from `git show HEAD~1:AGENTS.md`, reinserted it into `AGENTS.md`
verbatim, deduplicated the archive file back to 22 unique blocks
(48,424 chars, matching `index.json`'s claimed count), reran
`bash run_tests.sh` (176 passed, clean), committed and pushed
(`7988577`).

**Lesson for future plan-writing, not a TriAPI code fix:** when a plan
item's task has a "delete X, but preserve Y" shape, its `verify_cmd` must
positively assert Y still exists (e.g. `grep -q "<marker unique to Y>"
target_file`) — a size/count-only check cannot distinguish "deleted the
right things" from "deleted everything." Apply this the next time a plan
prompt for TriAPI includes a preservation constraint alongside a deletion.

## Status at session end

TriAPI: clean, no code changes (the bug was in a plan prompt, not
TriAPI's own scripts). oh-my-llama: clean, `AGENTS.md` correctly holds
only the one genuinely-open Sub-Phase 5G block (53,633 chars), archive
has exactly 22 unique blocks (48,424 chars), `docs/Agent/CARRYOVER.md`
refreshed and accurate (openclaw Telegram row removed, size-cleanup
section removed, Phase 5G called out as the sole open item), all pushed
to `migration-clean-up`. Full `bash run_tests.sh` green (176 passed).
Queue for both repos is effectively just Sub-Phase 5G now — see
oh-my-llama's own `docs/Agent/CARRYOVER.md` for that item's detail.
