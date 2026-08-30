# Carryover — 2026-08-29 21:00 — Phase 5G/7 web-frontend cut executed, three real TriAPI pipeline bugs fixed

**Session summary:** Continued supervising oh-my-llama from the previous
carryover file (`20260829-233950-...`), working the two follow-ups it
queued plus the still-open Phase 5G/7 decision. Along the way found and
fixed three more real, previously unknown bugs in TriAPI's own pipeline —
not oh-my-llama bugs — and executed a real product decision (cutting
oh-my-llama's web chat frontend) entirely through `triapi plan`/`dispatch`.

## Queue item resolved: `librarian_escalate.py`'s FRESH false-negative bug (4th recurrence)

Root cause found: the FRESH escape hatch (model claims a doc is already
accurate) returned `status: success` unconditionally, never running the
caller's `verify_cmd` against the file — so a false FRESH claim was never
caught even when a real content-asserting `verify_cmd` was supplied. Fixed:
a real `verify_cmd` is now run against the file before trusting FRESH; a
contradiction rejects the claim and falls through to the next provider.
Commit `bdf58a9`, two new regression tests in `tests/test_tier5_librarian.py`.
Live-reverified against the exact incident that triggered this session's
work (a stale, pre-fix background retry — `living_index_v2.out` — that had
returned a false FRESH for the daemon.py living-index update): re-run under
the fixed code correctly judged the same file genuinely FRESH this time
(content was already hand-patched), confirming the fix works both ways.

## Queue item resolved: doc-target file-size ceiling had stale Tier-4 wording

`dispatcher.py`'s `_enforce_file_size_ceiling()` flagged oversized doc files
with `skip_tier4=True` and "Tier 4 cannot be used on it" wording, even
though doc targets already route entirely to `tier_5_librarian` (agy, large
cloud context) and never touch Tier 4. Doc targets now get a size note with
an honest rationale (token economy for agents reading the file) instead,
`skip_tier4` left unset; falls back to old behavior when
`tier_5_librarian` is disabled. Commit `16cfd46`.

## Queue item resolved: Phase 5G/7 decision — oh-my-llama's web chat frontend formally cut

Live investigation found the old `omll`/`omll-tui`/telegram/web-frontend
picture was more broken than the previous carryover's open question
implied. Executed via two `triapi plan`/`dispatch` runs against
oh-my-llama (commits `0985257`, `d43812e` there):
- `ohmyllama/webui.py`, `deploy/oh-my-llama-web.service`, and `cli.py`'s
  `_cmd_web`/`web` subparser deleted outright — the browser chat UI was
  never ported to `src/semai/` and, per the project's documented pivot to a
  secretary/memory core, is a deliberate scope cut, not a gap. Recorded as
  `docs/decisions/0014-cut-web-chat-frontend.md` (ADR), with a companion
  `docs/semai-preflight.md` D14 row and `test_adr_check_seam.py` count
  fixes (13→14 ADRs).
- **Caught a tier attempting to wrongly delete `fastapi<0.140` from
  `pyproject.toml`.** The plan's own premise (fastapi only survives because
  of webui.py) was wrong — the real reason is an unrelated pin needed by
  `litellm[proxy]`'s internal `fastapi.dependencies.utils.get_flat_dependant`
  import. A tier attempted the deletion anyway; caught before it could
  commit (content_guard's retention-ratio check on a coincidental unrelated
  comment match, not a real safety check, so this was closer than it
  looks), reverted via `git checkout`, and the run's remaining items
  corrected with the real grounding before resuming.
- `deploy/oh-my-llama-telegram.service`'s `ExecStart` fixed from the
  nonexistent `omll telegram` subcommand to the real dedicated entry point,
  `semai-telegram`. Commit `d5f9284`.
- **New bug found live, not caused by this session but only surfaced by
  finally getting `omll`'s entry point fixed and reinstalled:** `omll`
  (`semai.adapters.cli:main`) was completely non-functional —
  `cli.py`'s `main()` is `async def`, but the packaged console-script
  wrapper does plain `sys.exit(main())`, which just creates and discards an
  unawaited coroutine. Fixed to match `daemon.py`'s own established
  `def main(): return asyncio.run(_amain())` pattern (oh-my-llama commit
  `d5f9284`, same commit as the telegram fix — see that repo's own log for
  the exact diff). Verified live: `omll --help` now prints real argparse
  help with no `RuntimeWarning`.
- `uv tool install --editable . --reinstall` run afterward so the installed
  `omll`/`omll-tui`/`semai-daemon`/`semai-telegram` binaries actually match
  current source (they hadn't been regenerated since the entry-point
  rename earlier this week, so `omll`/`omll-tui` were silently still
  importing the old `ohmyllama.cli`/`ohmyllama.tui` modules).
- `oh-my-llama.service` restarted and confirmed healthy.
  `oh-my-llama-telegram.service` restart uncovered a separate, genuinely
  pre-existing gap (not caused by today's fix): its `ExecStart` never wires
  `TELEGRAM_BOT_TOKEN`/`TELEGRAM_ALLOWED_CHAT_IDS` via `sops exec-env`
  despite its own comment saying it's required — currently **stopped**,
  queued in oh-my-llama's own `docs/Agent/CARRYOVER.md`, not fixed this
  session (needs the user's real token, out of scope for an automated fix).

**Phase 5G-1/5G-2 (deleting the old runtime files themselves) is still not
unblocked** — `ohmyllama/cli.py`/`tui.py`/`telegram.py` (the OLD files)
still directly import `agent.py`/`ghostwriter.py`/`watcher.py`, and while
nothing in `pyproject.toml` points at the old files anymore, they were
given semai-native siblings, not retired. That decision is still open —
see oh-my-llama's own `docs/Agent/CARRYOVER.md`.

## Queue item resolved: TriAPI's own dispatch-summary KeyError bug

Found while hand-correcting a run's stored results (this repo's own
"verify, don't trust status" convention, exercised several times this
session on false FRESH claims and false human_handoffs — see below):
`_breakdown_and_dispatch()`'s final summary print loop indexed
`r['phase']`/`r['item']` directly, so a hand-corrected results entry
missing those keys (a real entry I wrote, correctly recording an
already-verified-correct edit) raised `KeyError`, crashing the function
*before* it ever reached `agents_md_gate.mark_plan_complete()` — so a run
whose `status` was already `"completed"` silently never got its `AGENTS.md`
checkboxes ticked, and the crash also skipped past the Jules advisory
check. Fixed with `.get()` and sane fallbacks; regression test added
(`tests/test_triapi_summary_print_robustness.py`). Commit `2f635fb`.

## Recurring theme this session: several results the pipeline reported as
failed were actually already correct on disk

At least four separate incidents this session where a tier's own
diagnostic (`human_handoff`, or a rejected FRESH claim) was technically
"the pipeline said this failed" but the *actual file content on disk was
already correct* — verified by reading it directly, not by trusting the
reported status, matching this repo's own long-standing convention:
1. `fastapi<0.140`'s removal — correctly should NOT happen; the pipeline's
   own overly-broad `grep`-based build_cmd flagged it for the wrong reason,
   but the underlying premise (delete the pin) was itself wrong and got
   reverted.
2. `docs/decisions/0014`'s content — a *later* regeneration attempt was
   correctly rejected by content_guard's retention-ratio guard, but the
   *earlier* successful write (with fully correct content) was preserved
   untouched. Hand-corrected the run's result entry to reflect this rather
   than re-dispatching a redundant, already-done item.
3. The ADR `**Status:**` line fix — same shape: the edit was correct, the
   shared `bash run_tests.sh` build_cmd just couldn't show a clean pass
   until two *later*, still-pending items in the same plan also landed.
4. The `cli.py` async-main fix — the pipeline's fix was 90% right (the
   sync/async split matched the plan exactly) but missed one detail (a
   missing `import asyncio`) traceable to a false premise *in the plan
   prompt I wrote*, not a model quality issue — the AGENT_GUIDE.md-sanctioned
   last-resort hand-fix (one line, fully diagnosed) was used after the
   pipeline's own escalation chain was exhausted on it.

None of these were the model silently getting something wrong and me
missing it — each was caught specifically by reading the real diff/file
content instead of trusting the reported status, and corrected via the
established "hand-correct the run's stored result with a clear note"
pattern (never a raw hand-edit of the target file without that
bookkeeping) or, in case 4, the explicitly-sanctioned narrow exception.

## Environment note: repeated background-task kills, cause not identified this time

Unlike the earlier documented incident this same session (root-caused to a
peer Claude session, since ended), `ListAgents` showed no active peer
session during this round of kills — every background-wrapped
`triapi dispatch` invocation (both the harness's own `run_in_background`
and a `setsid`+`disown`-detached variant, which the auto-mode classifier
then blocked on a later attempt) got killed within roughly 1–3 minutes,
while the underlying dispatched process itself kept running unaffected and
resumable. Worked around by repeatedly checking `pgrep`/`triapi status`
directly and resuming rather than holding a live watcher. Root cause not
identified — flagging for whoever next hits this, in case it recurs.

## Status at session end

TriAPI: clean, all fixes committed (`16cfd46`, `bdf58a9`, `2f635fb`), 119
tests passing. oh-my-llama: clean, all fixes committed and auto-pushed by
TriAPI (`0985257`, `d43812e`, `d5f9284`, `9c84533`), 176 tests passing,
`docs/Agent/CARRYOVER.md` condensed per its own stated brevity convention
(finished narrative folded down, current state kept short).
`oh-my-llama.service` running; `oh-my-llama-telegram.service` stopped
pending the sops-secrets gap above.

## Two follow-ups queued, not fixed this session (in oh-my-llama's own `docs/Agent/CARRYOVER.md`)

1. `oh-my-llama.service` has no `WorkingDirectory=`, so `MailWatcher`'s
   relative `db_path` (`.state-semai/mail_state.sqlite3`) resolves against
   the wrong cwd — confirmed live via recurring `MailWatcher poll failed:
   unable to open database file` in `journalctl`.
2. `deploy/oh-my-llama-telegram.service` never wires
   `TELEGRAM_BOT_TOKEN`/`TELEGRAM_ALLOWED_CHAT_IDS` via `sops exec-env`
   despite its own comment saying it's required — mirror
   `deploy/oh-my-llama-web.service`'s working pattern.

## Original queue item still open, not attempted this session

Queue item 3 from the previous carryover file: oh-my-llama's own
`AGENTS.md` is over this repo's 73,728-char ceiling (was 80,313 chars as of
the last check, likely larger now after this session's own plan-block
appends) — needs the same index/overflow-to-`docs/agents/`-style treatment
this repo already gave itself. Not attempted this session, flagging again
for whoever next has bandwidth.
