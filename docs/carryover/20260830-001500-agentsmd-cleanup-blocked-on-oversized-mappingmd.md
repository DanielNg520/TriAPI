# Carryover — 2026-08-30 00:15 — oh-my-llama `AGENTS.md` cleanup attempted, blocked on a much bigger `MAPPING.md` problem

**Session summary:** Continued from the previous carryover file, picking up
the queued oh-my-llama `AGENTS.md` over-ceiling item in this fresh session
as planned. TriAPI itself needed no code changes. The attempt surfaced a
bigger, previously-unknown problem that blocks the original fix.

## Attempted: fold oh-my-llama `AGENTS.md`'s 20 accumulated `TriAPI Plan` blocks into `MAPPING.md`

`AGENTS.md` was 91,354 chars (grown further since last session's 86,562
check, from three more dispatch runs' auto-appended plan blocks). All 20
`<!-- triapi:plan run_id=... -->`-wrapped sections (lines 697-961,
~42,507 chars) documented fully-complete historical dispatch work and, per
the file's own standing rule, should be condensed and folded into
`MAPPING.md`'s Part 10 (TriAPI Plan Execution Log), then deleted from
`AGENTS.md` — exactly the treatment this repo already gave itself.

Dispatched via `triapi plan`/`dispatch` (run `20260829-235659-7bc513`),
surgically scoped (exact line range, explicit "don't touch anything else").

## Blocker found: `MAPPING.md` itself is 375,554 chars — over 5x this repo's own 73,728-char ceiling

The pipeline correctly refused rather than blindly appending: Tier routed
the target to `tier_5_librarian` (large-context doc target, not blocked by
Tier 4's context window) but the tier itself flagged the oversized target
in its own human_handoff note and did no work. Result: `stopped_on_failure`,
**nothing actually changed** — no MAPPING.md edit, no AGENTS.md deletion.
The only side effect was the run's own plan-block getting auto-appended to
`AGENTS.md` (making it briefly *larger*, 95,360 chars) plus a stray
`extract.py` scratch file left untracked. Both cleaned up by hand
(`git checkout HEAD -- AGENTS.md`, `rm extract.py`) — reverting to a clean
working tree, no commit made (nothing to commit).

**This means the real fix is two-phase, not one:** `MAPPING.md` needs the
same index/overflow-to-dated-files split this repo (`TriAPI`) already
applied to its own `CARRYOVER.md`/`AGENTS.md` — condense the existing
`MAPPING.md` into a permanent index pointing at topic/date-scoped files
under (e.g.) `docs/mapping/`, *before* anything else can safely be appended
to it. Only after that split lands can the original `AGENTS.md`
plan-block-folding item be retried.

## Not attempted this session (scope decision, not a blocker)

Splitting a 375K-char file into a proper dated-index structure is a
substantial restructuring task in its own right — comparable in size to
this repo's own 2026-08-25 `AGENTS.md`/`CARRYOVER.md` conversion, not a
quick follow-up. Flagging rather than improvising a fix inline.

## Status at session end

TriAPI: clean, no code changes. oh-my-llama: clean working tree (the two
stray edits from the failed attempt were reverted, nothing committed for
this item). Both `oh-my-llama.service` and `oh-my-llama-telegram.service`
still healthy from the previous session's fixes, but were found `inactive`
after this run's `human_handoff` exit and had to be started by hand
(`systemctl --user start`) — `resource_guard.py`'s pause/resume is designed
to be self-healing on any exit path (see its own docstring), and its lock
file was correctly cleared, but the services didn't come back up on their
own this time. Single occurrence, not reproduced/root-caused — flagging in
case it recurs, not chasing further this session.

## Queue item carried forward, revised

Previous item ("fold `AGENTS.md`'s TriAPI Plan blocks into `MAPPING.md`,
delete them from `AGENTS.md`") is now **two** items, in order:
1. Split oh-my-llama's `MAPPING.md` (375,554 chars) into a permanent index
   + topic/date-scoped files under `docs/mapping/` (or similar), mirroring
   this repo's own `docs/carryover/`/`docs/agents/` convention — needed
   before item 2 can land.
2. Then retry folding `AGENTS.md`'s 20 `TriAPI Plan` blocks (still at lines
   697-961 as of this session, ~42,507 of `AGENTS.md`'s 91,354 chars) into
   whatever the new split `MAPPING.md` structure's execution-log file is,
   and delete them from `AGENTS.md`.
