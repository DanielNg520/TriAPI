# Carryover — 2026-08-30 01:25 — oh-my-llama `AGENTS.md` fold complete; `agy` direct-write bug fixed and shipped

**Session summary:** Continuation of the previous carryover file. Completed
the second (final) item of the two-item queue, then fixed the `agy`
direct-file-write bug found while doing it. Both TriAPI's own repo and
oh-my-llama are clean; queue is empty.

## Completed: oh-my-llama `AGENTS.md` plan-block fold (96,339 → 63,634 chars)

Ran `triapi plan`/`dispatch` (run `20260830-011144-7e1fa5`) against
oh-my-llama. Of the 20 accumulated `<!-- triapi:plan run_id=... -->`
blocks, 5 (`20260828-182931-264248`, `20260828-215731-5e5e2b`,
`20260828-223808-971593`, `20260828-224859-4711c3`,
`20260829-225157-6e19ee`) still had unchecked `- [ ]` steps — all 5 map to
runs whose own `triapi list` status is `stopped_on_failure`, i.e. genuinely
incomplete work, not historical done-work. Deliberately excluded these
from the fold and left them in place in `AGENTS.md` for a future session
to actually resolve (not just re-file as "done"). The other 17
fully-checked blocks were moved verbatim to
`docs/mapping/../docs/agents/20260830-archived-plan-blocks.md` (new
`docs/agents/` dir, mirroring TriAPI's own `docs/agents/` overflow
convention) plus `docs/agents/index.json`, with a single pointer paragraph
left in `AGENTS.md` in their place. Verified via `wc -c`, `grep -c`, and
`git log` — clean, committed, pushed by the pipeline.

**Why this one worked cleanly (no manual patching needed), unlike the
`MAPPING.md` split:** the plan prompt gave the planner exact,
already-computed non-contiguous line ranges and had it emit fully
deterministic `build_cmd`s (a `sed` one-liner for the archive, a small
inline Python script for the prune) — no item asked a model to reproduce
large verbatim content from scratch. This confirms the mechanism
discovered during the `MAPPING.md` split: for `tier_5_librarian` items,
the item's `build_cmd` is also passed as `verify_cmd`, which runs
*unconditionally* once `content_guard` allows any write to proceed —
so a build_cmd that is itself the complete, correct mutation succeeds
regardless of which model/attempt handles it (including a bare `FRESH`
claim, since `verify_cmd` still runs to contradict-check it). Worth
remembering for any future oversized-doc-split work: write the plan so
the model's job is redundant, not just simple.

## Fixed and shipped: `agy --dangerously-skip-permissions` direct-file-write hole

Root cause, found during the `MAPPING.md` split (previous carryover
file): `scripts/llm_client.py`'s `_call_agy_cli()` ran `agy` with
`--dangerously-skip-permissions` and no mode restriction, giving it real
filesystem tool access. Twice in that session, `agy` wrote the correct
target file directly via its own tools mid-call, then returned unrelated
"response" text that `content_guard` correctly rejected as the *proposed*
content — triggering a spurious `human_handoff` despite the file on disk
already being correct. Same bug class already fixed for the Claude CLI
(`--tools ""`), never applied to `agy`.

**This session, verified live and fixed:** `agy --help` lists `--mode
plan` as a valid mode (`accept-edits`, `plan`). Tested directly (outside
the librarian's code path, in a scratch dir) against both response shapes
`librarian_escalate.py` relies on:
- New-file prompt (fenced code block): `agy --mode plan` returned only
  the fenced content, file **not** created on disk.
- Existing-file prompt (SEARCH/REPLACE): `agy --mode plan` returned only
  the SEARCH/REPLACE block, file **not** modified on disk.

Both used the exact real prompt shape `build_prompt()` generates — plan
mode's default "let me propose a plan for your approval" framing is
overridden by the prompt's own explicit "reply with ... no other text"
instruction. Shipped: `scripts/llm_client.py`'s `_call_agy_cli()` now
always passes `--mode plan` alongside `--dangerously-skip-permissions`;
docstring updated with the full incident writeup (see the function itself
for detail, not repeated here). `tests/test_tier_reassignment_prep.py`'s
exact-argv assertion updated to match. Full suite green: 259 passed, 12
subtests passed. Committed (`1ecee06`).

**Not separately re-tested against a live dispatch run** (the
`AGENTS.md` fold run above was already spawned before this fix landed,
so it exercised the old code path and hit the same `agy`
prompt-too-large-for-argv issue on one item, unrelated to this fix,
before falling through to Ollama and succeeding). The next live
`tier_5_librarian` or `tier_1_planner` dispatch that routes through `agy`
will be the first real-world exercise of the fix — worth a closer look at
its logs than usual, once one comes up naturally, rather than manufacturing
a dedicated test run for it.

## Status at session end

TriAPI: clean, `agy --mode plan` fix committed (`1ecee06`). oh-my-llama:
clean, both items of the queue done and pushed
(`fe47d20` MAPPING.md split, `8b87173` AGENTS.md fold). Queue is empty —
no carried-forward items this time. `oh-my-llama.service`/
`oh-my-llama-telegram.service` were paused for the AGENTS.md fold
dispatch; confirm they're back up (Jules advisory test + resource_guard
resume, same pattern as every dispatch run) before closing out if not
already visible in this session's tail end.
