# Carryover — 2026-08-30 00:55 — oh-my-llama `MAPPING.md` split complete, serious `agy` direct-write bug found

**Session summary:** Resumed from the previous carryover file's blocker.
Completed item 1 of the two-item queue (split oh-my-llama's oversized
`MAPPING.md`). Item 2 (folding `AGENTS.md`'s `TriAPI Plan` blocks) is
still pending, now unblocked. Along the way, found and root-caused a real,
previously-undocumented TriAPI safety gap in how the `agy` CLI is
invoked — not yet fixed, queued below.

## Completed: oh-my-llama `MAPPING.md` split (375,554 → 3,971 chars)

Ran `triapi plan`/`dispatch` against oh-my-llama (run `20260830-002820-7a9e88`),
mirroring this repo's own `docs/carryover/`/`docs/agents/` overflow
convention. Result: `MAPPING.md` is now a permanent index (3,971 chars);
its content lives in 7 new files under `docs/mapping/` (all under the
73,728-char ceiling) plus `docs/mapping/index.json`. Pushed to
`migration-clean-up` by the pipeline's own `git_ops.push()`. Nothing
discarded — every line accounted for by the index's `moved_from` ranges,
spot-checked with `diff` against the original line ranges.

Two of the 9 plan items needed manual intervention (see next section) —
in both cases the correct content was **already on disk** before I
touched anything, verified byte-identical via `diff` against the expected
`sed` extraction before patching run state (`"resolved_by": "manual"`,
refreshed `content_hash`) per `AGENT_GUIDE.md`'s human_handoff workflow.
A third item (final `MAPPING.md` overwrite) had a genuine failure across
all 4 tier_5_librarian legs — see below — and was hand-written after
confirming the plan text itself fully specified the content (no tier work
was skipped to save time; all 4 legs were exhausted first).

## Bug found, root-caused, NOT yet fixed: `agy` runs with unrestricted file-write access

**Symptom:** Two Phase-1 items (`docs/mapping/03-...md`,
`docs/mapping/05-...md`) hit `human_handoff` after all 4 `tier_5_librarian`
legs failed — but on inspection, the target file was *already on disk*,
byte-identical to the correct extraction, mid-way through the very
`agy` call that then reported failure.

**Root cause:** `scripts/llm_client.py`'s `_call_agy_cli()` invokes
`agy -p ... --dangerously-skip-permissions --output-format json`
unconditionally. `--dangerously-skip-permissions` makes `agy` a fully
agentic CLI with real filesystem tool access — it can (and did) write the
target file directly via its own tools, *outside* the librarian's
intended read-response/guarded-write contract. The wrapper then treats
whatever `agy` separately returns as `"response"` text (unrelated to the
file it just wrote) as the *proposed file content*, feeds it through
`content_guard.check_write()`, which correctly rejects it as a
near-total content loss (10%, then 0%, then 0% survival across the two
`agy` legs in the chain) — but the wrapper has no way to notice "the file
on disk is already correct, the *response text* is just wrong," so it
escalates every affected item to `human_handoff` regardless.

**This is the exact same bug class already fixed for the Claude CLI**
(see `_call_claude_cli`'s own docstring/comment, `--tools ""` mandatory,
fixed after the 2026-08-29 daemon.py incident) — but the equivalent fix
was never applied to `_call_agy_cli`. Confirmed live twice in this
session alone; likely also affects `tier_1_planner` (also routed through
`agy`, per `project_tier1_planner_nemotron_hallucination` memory) any
time it's asked to edit an existing file rather than write a fresh one.

**Not fixed this session, on purpose:** `agy --help` lists no direct
`--tools ""`-equivalent flag. The closest candidate is `--mode plan`
("Set the agent execution mode... accept-edits, plan" per `agy --help`),
which by naming convention should make `agy` propose changes without
applying them — but this repo's own environment blocks Claude Code's
Bash tool from invoking `agy -p ...` directly for verification (auto-mode
classifier refusal), so this could not be tested live before shipping.
Shipping an untested change to a flag used by both `tier_1_planner` and
`tier_5_librarian` — both load-bearing, both used constantly per recent
carryover history — was judged too risky without verification.

**Impact so far:** No actual data loss observed — `content_guard` caught
every mismatched write attempt, and the real (correct) file state
survived both times. But this is luck, not by design: if `agy` had
instead made an *incorrect but plausible-looking* edit via its own tools
elsewhere in the target repo (not just the intended target file), nothing
in this pipeline would notice — the exact failure mode the
`_call_claude_cli` docstring already describes for Claude, now confirmed
possible for `agy` too.

## Queue item, new

**Fix `_call_agy_cli()`'s unrestricted tool access** (`scripts/llm_client.py`,
~line 242). Investigate `--mode plan` as the fix (test it manually outside
Claude Code's Bash sandbox restriction, or from a context that isn't
classifier-blocked, before touching the invocation used by two live
tiers). If `--mode plan` doesn't fully suppress filesystem writes,
escalate to human — there may be no clean flag-level fix, and a other
mitigation (e.g. running `agy` inside a scratch copy of the repo, or
comparing target-repo `git status` before/after every `agy` call and
treating any change outside the intended target as a hard failure) would
be needed instead.

## Queue item carried forward, unblocked

Now that `MAPPING.md` is split, retry folding oh-my-llama `AGENTS.md`'s
(currently 96,339 chars) accumulated `TriAPI Plan` blocks into the new
`docs/mapping/` structure's execution-log file
(`docs/mapping/06-parts3-to-10-migrations-proposals.md`, which already
holds the old Part 10 TriAPI Plan Execution Log), then delete them from
`AGENTS.md`.

## Status at session end

TriAPI: clean, no code changes (the `agy` bug fix was deliberately not
attempted — see above). oh-my-llama: `MAPPING.md` split committed and
pushed by the pipeline; working tree clean. `oh-my-llama.service` and
`oh-my-llama-telegram.service` were paused for the dispatch run as
normal; confirm they came back up before closing out (`resource_guard`'s
resume runs after the pipeline's own post-push Jules validation session,
which was still `IN_PROGRESS` as this file was written).
