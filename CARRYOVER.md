# CARRYOVER — INDEX ONLY

This file is an **index**, not content. It is never pruned or trimmed for
size — it only ever grows by one row per session/task. Real carryover
content lives in dated files under `docs/carryover/`. **Read only the
row(s) below relevant to your current task — do not read every file.**

**Machine-readable index: [`docs/carryover/index.json`](docs/carryover/index.json)
is the authoritative source** (this table is a human-readable mirror of
it, kept in sync by hand). Fastest way to resume: `jq -r '.active'
docs/carryover/index.json`, then read only that file — no need to parse
this markdown table at all.

## Read first, always

| File | Status |
|---|---|
| [`docs/carryover/20260825-092344-active-tier-flip-plan-and-queue.md`](docs/carryover/20260825-092344-active-tier-flip-plan-and-queue.md) | **ACTIVE** — current state, standing rules, full queue |

The ACTIVE file is the only one required reading for "what do I do next."
Everything below is historical — read a row only if your task needs that
specific history (debugging a regression in the area it covers, or
understanding why a past decision was made).

## History index

| File | Date | Status | Topic |
|---|---|---|---|
| [`20260823-210000-openrouter-merge-and-tier-swap.md`](docs/carryover/20260823-210000-openrouter-merge-and-tier-swap.md) | 2026-08-23 | RESOLVED | OpenRouter branch merge into `main`; Tier 3/4 provider swap; 4 early bug fixes; backend-registry and complexity-router architecture items first queued |
| [`20260824-030000-librarian-tier5-redesign-debugging.md`](docs/carryover/20260824-030000-librarian-tier5-redesign-debugging.md) | 2026-08-24 | RESOLVED | Tier 5 librarian build: 5 debugging addenda (epoch-collision staleness bug, stale test mocks, human_handoff bookkeeping bug, PLAN.md-too-large stall, OpenRouter phone-filter fix drafted) |
| [`20260824-190000-queue-snapshot-openrouter-obstacles.md`](docs/carryover/20260824-190000-queue-snapshot-openrouter-obstacles.md) | 2026-08-24 | SUPERSEDED | Old queue snapshot mid-fix — OpenRouter dispatch obstacles (403s, 429s, `probe_models()` over-gating found) |
| [`20260824-235900-misc-resolved-fixes.md`](docs/carryover/20260824-235900-misc-resolved-fixes.md) | 2026-08-24 | RESOLVED | `KeyError: 'choices'` fix; `probe_models()` retry tolerance; Ollama lifecycle test hang (found, not fixed) |
| [`20260825-000000-openrouter-fixes-tier-prep-pipefail-complete.md`](docs/carryover/20260825-000000-openrouter-fixes-tier-prep-pipefail-complete.md) | 2026-08-25 | RESOLVED | OpenRouter phone/IP sanitizer + peak-hours dedup (Phase 30); `agy` provider + generic routing + position-independent peak gate (Phase 31); `run_build()` pipefail fix (Phase 32); `git_ops` auto-branch removed |

## Convention for adding a new entry (read once, then follow every session)

1. **Filename**: `docs/carryover/YYYYMMDD-HHMMSS-brief-kebab-title.md` —
   timestamp of when the entry was written, title is 3-6 words.
2. **Update BOTH `index.json` and this markdown table together, every
   time** — `index.json` is authoritative for tooling/queries, this table
   is for a human skimming the file directly. Never let them drift.
3. **Exactly one entry is ever tagged/marked `ACTIVE`** (`index.json`'s
   top-level `"active"` key, and this table's "Read first, always" row) —
   the current-state file a new session reads first. When that file's
   work is fully done: move it into `index.json`'s `history` array with
   status `RESOLVED`/`SUPERSEDED`, update this table's History index the
   same way, create a new dated file, and point `"active"`/the "Read
   first" row at it. Never leave two active at once; never leave zero.
4. **Never delete or prune** a `docs/carryover/` file or its index entry.
   If content becomes wrong, add a short correction note at its use site
   (or in the ACTIVE file) rather than editing history away.
5. **Keep each dated file under 73,728 characters** (this repo's
   file-size ceiling). Split further by topic/timestamp if a session
   would otherwise overflow one file — see the multiple entries from
   2026-08-24 for the pattern (one file per distinct sub-topic/session
   segment, not one giant file per day).
6. **Index entries stay one line/one topic clause** — file, date,
   status, topic only, same shape in both `index.json` and this table.
   Full detail belongs in the dated file itself.
7. This is the same convention `AGENTS.md`'s own top-of-file index and
   `docs/agents/index.json` follow for file/dir documentation overflow —
   see `AGENTS.md`'s index section.
