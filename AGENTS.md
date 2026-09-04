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
four entries: the full `scripts/` reference, the file/dir documentation
archive, and two archives of historical `triapi:plan` blocks — see the
rows below).
Human-readable mirror:

| Section | What's there |
|---|---|
| [Conventions, test commands, architecture](#conventions-test-commands-architecture-quick-reference) | Pointer only — full reference moved to [`docs/agents/20260904-141041-file-and-dir-documentation.md`](docs/agents/20260904-141041-file-and-dir-documentation.md) |
| [Root](#root) | Pointer only — full reference moved to [`docs/agents/20260904-141041-file-and-dir-documentation.md`](docs/agents/20260904-141041-file-and-dir-documentation.md) |
| [config/](#config) | Pointer only — full reference moved to [`docs/agents/20260904-141041-file-and-dir-documentation.md`](docs/agents/20260904-141041-file-and-dir-documentation.md) |
| [knowledge/](#knowledge) | Pointer only — full reference moved to [`docs/agents/20260904-141041-file-and-dir-documentation.md`](docs/agents/20260904-141041-file-and-dir-documentation.md) |
| [scripts/](#scripts) | Pointer only — full reference moved to [`docs/agents/20260825-100000-scripts-directory-reference.md`](docs/agents/20260825-100000-scripts-directory-reference.md) (2026-08-25, this file's largest section, moved to stay under the 73,728-char ceiling without pruning any content) |
| [tests/](#tests) | Pointer only — full reference moved to [`docs/agents/20260904-141041-file-and-dir-documentation.md`](docs/agents/20260904-141041-file-and-dir-documentation.md) |
| [logs/](#logs) | Pointer only — full reference moved to [`docs/agents/20260904-141041-file-and-dir-documentation.md`](docs/agents/20260904-141041-file-and-dir-documentation.md) |
| [samples/](#samples) | Pointer only — full reference moved to [`docs/agents/20260904-141041-file-and-dir-documentation.md`](docs/agents/20260904-141041-file-and-dir-documentation.md) |
| [Historical `triapi:plan` blocks](#historical-completed-triapiplan-blocks-2026-08-25-through-2026-09-04) | Pointer only — 19 completed plan runs across two archives: [`docs/agents/20260828-044229-agents-md-historical-plan-blocks-archive.md`](docs/agents/20260828-044229-agents-md-historical-plan-blocks-archive.md) (2026-08-28, 5 runs) and [`docs/agents/20260904-213926-agents-md-historical-plan-blocks-archive-2.md`](docs/agents/20260904-213926-agents-md-historical-plan-blocks-archive-2.md) (2026-09-04, 14 runs) |

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
Pointer only — full reference moved to [`docs/agents/20260904-141041-file-and-dir-documentation.md`](docs/agents/20260904-141041-file-and-dir-documentation.md).

## Root
Pointer only — full reference moved to [`docs/agents/20260904-141041-file-and-dir-documentation.md`](docs/agents/20260904-141041-file-and-dir-documentation.md).

## config/
Pointer only — full reference moved to [`docs/agents/20260904-141041-file-and-dir-documentation.md`](docs/agents/20260904-141041-file-and-dir-documentation.md).

## knowledge/
Pointer only — full reference moved to [`docs/agents/20260904-141041-file-and-dir-documentation.md`](docs/agents/20260904-141041-file-and-dir-documentation.md).

## scripts/
Full reference moved to [`docs/agents/20260825-100000-scripts-directory-reference.md`](docs/agents/20260825-100000-scripts-directory-reference.md) (2026-08-25 — see `docs/agents/index.json`) to keep this file under the 73,728-char ceiling. Covers every pipeline module: `secrets_loader.py`, `config_loader.py`, `llm_client.py`, `state.py`, `content_guard.py`, `edit_blocks.py`, `lessons.py`, `hivemind_util.py`, `critique.py`, `judge.py`, `self_fix.py`, `tier4_context.py`, `tier4_worker.py`, `tier3_escalate.py`, `tier1_escalate.py`, `tier2_escalate.py`, `budget_guard.py`, `jules_client.py`, `cost_report.py`, `orchestrator.py`, `agents_md_gate.py`, `planner.py`, `dispatcher.py`, `regression_guard.py`, `mock_patch_lint.py`, `tech_debt.py`, `git_ops.py`, `triapi.py`, `resource_guard.py`, `tri_logging.py`, `librarian_escalate.py`. (`gemini_fallback.py` deleted 2026-09-01 — see the reference file's own note.)

## tests/
Pointer only — full reference moved to [`docs/agents/20260904-141041-file-and-dir-documentation.md`](docs/agents/20260904-141041-file-and-dir-documentation.md).

## logs/
Pointer only — full reference moved to [`docs/agents/20260904-141041-file-and-dir-documentation.md`](docs/agents/20260904-141041-file-and-dir-documentation.md).

## samples/
Pointer only — full reference moved to [`docs/agents/20260904-141041-file-and-dir-documentation.md`](docs/agents/20260904-141041-file-and-dir-documentation.md).


## Historical, completed `triapi:plan` blocks (2026-08-25 through 2026-09-04)

**Historical, completed `triapi:plan` blocks were moved out of this file in
two archiving passes, both to bring this file back under the repo's
73,728-char ceiling — see `docs/agents/index.json`:**

- **2026-08-25 through 2026-08-27** (5 runs): moved 2026-08-28 to
  [`docs/agents/20260828-044229-agents-md-historical-plan-blocks-archive.md`](docs/agents/20260828-044229-agents-md-historical-plan-blocks-archive.md).
  A separate, unrelated ~71,600-char fully hallucinated block
  (`run_id=20260827-130810-27dd58` — an overloaded/malfunctioning model
  invented a nonexistent `scripts.librarian_escalate.escalate_librarian()`
  function and fake `config/tiers.yaml` values; never approved, never
  dispatched) was deleted outright, not archived, in the same pass.
- **2026-08-27 through 2026-09-04** (14 runs): moved 2026-09-04 to
  [`docs/agents/20260904-213926-agents-md-historical-plan-blocks-archive-2.md`](docs/agents/20260904-213926-agents-md-historical-plan-blocks-archive-2.md).

**Only the single most-recent `triapi:plan` block below is still tracked
inline — that's the one `scripts/agents_md_gate.py`'s
`find_incomplete_plan()` actually checks to gate a new `triapi plan`
call. Archive a completed span like this whenever this file is back
within a few KB of the ceiling — same convention as `docs/carryover/`.**

<!-- triapi:plan run_id=20260904-141037-83b449 start -->
## TriAPI Plan (run 20260904-141037-83b449, appended 2026-09-04)

1. Phase 1: Archive inline documentation
- [x] `docs/agents/20260904-141041-file-and-dir-documentation.md`: Create this new file. Move the detailed inline narrative and file/directory documentation from `AGENTS.md` verbatim into this file. Specifically, relocate the full contents of `## Conventions, test commands, architecture (quick reference)`, `## Root`, `## config/`, `## knowledge/`, and any other inline non-index sections (e.g., `tests/`, `logs/`, `samples/`). Do not summarize the moved content. Verification command: `grep -q '^## Conventions, test commands, architecture' docs/agents/20260904-141041-file-and-dir-documentation.md && grep -q '^## Root' docs/agents/20260904-141041-file-and-dir-documentation.md && grep -q '^## config/' docs/agents/20260904-141041-file-and-dir-documentation.md`

2. Phase 2: Update the machine-readable index
- [x] `docs/agents/index.json`: Edit this file to append a new entry to the `"entries"` array for `docs/agents/20260904-141041-file-and-dir-documentation.md`, following its existing JSON schema. The entry should contain `"file": "20260904-141041-file-and-dir-documentation.md"`, `"date": "2026-09-04"`, `"topic": "File, directory, and narrative documentation overflow from AGENTS.md inline sections (Conventions, Root, config, knowledge, tests, logs, samples)"`, and `"moved_from": "AGENTS.md's inline sections"`. Verification command: `jq -e '.entries[] | select(.file == "20260904-141041-file-and-dir-documentation.md")' docs/agents/index.json > /dev/null`

3. Phase 3: Trim AGENTS.md and fix test command
- [x] `AGENTS.md`: Remove the verbose content from the sections relocated in Phase 1 (`Root`, `config/`, `knowledge/`, `Conventions, test commands, architecture`, `tests/`, `logs/`, `samples/`). Replace each section's inline text with a short pointer paragraph linking to `[docs/agents/20260904-141041-file-and-dir-documentation.md](docs/agents/20260904-141041-file-and-dir-documentation.md)`. Update the human-readable "This file's own index" table to point to this new archive file. Find the stale test command `PYTHONPATH=. python3 -m unittest tests.test_branch_features tests.test_tier5_librarian -v` and replace it with the exact string `PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_*.py' -v`. Verification command: `test $(wc -c < AGENTS.md) -lt 73728 && grep -q "PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_*.py' -v" AGENTS.md`

4. Phase 4: Full regression suite verification
- [x] `AGENTS.md`: No edits needed in this phase. Run the full regression suite to confirm none of the doc-only work broke anything, expecting zero SKIPPED tests. Verification command: `PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_*.py' -v`
<!-- triapi:plan run_id=20260904-141037-83b449 end -->
