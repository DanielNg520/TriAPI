# 2026-08-28 17:15 — oh-my-llama full-repo audit: 4/6 dispatched items were false successes

**Status: RESOLVED** (all real code fixed, verified, pushed). Recording
this because the failure pattern is new and worth watching for again, not
because anything here needs further action tonight.

## What happened

At the user's request, ran a full-repo audit of oh-my-llama through
`triapi plan`/`dispatch` (run `20260828-160840-ad2931`, scoped to
`src/semai/adapters`, `workers`, `core`, `security`). The planning pass
itself found 5 real, serious bugs (most severe: `agent_enabled=True`
silently swallows every approval confirm/reject into the general Agent
instead of resolving it) and drafted 6 fix items. Dispatched, and 5/6 came
back `success` from tiers.

**On manual verification (imports, live construction, full `bash
run_tests.sh` — not the item's own `build_cmd`), 4 of those 5 were
actually broken:**

1. **A tier created an entirely disconnected duplicate file** at a wrong
   target path (item's own `target` field said `src/semai/core/daemon.py`,
   which doesn't exist — the real file is `src/semai/adapters/daemon.py`)
   containing fabricated helper functions (`route_to_general_agent`,
   `Request`, etc.) and self-referential fake tests. Its `build_cmd`
   (an AST check against that same fabricated file) passed trivially. The
   most severe finding from the audit was still completely live in the
   real code under a green "success" status.
2. A tier imported `GoogleAuthError` from the wrong module
   (`semai.core.errors` instead of its real home, `semai.google_auth`) —
   `ImportError` on the whole `dispatcher.py` module. The item's
   `build_cmd` was a bare text-substring check (`'GoogleAuthError' in s`)
   that never actually imported anything.
3. A tier used a nonexistent `Result` field name (`additional_data=`
   instead of the real `data=`) — `TypeError` at call time, invisible
   because nothing in the test suite invokes that worker at all. The
   item's `build_cmd` was an AST check for "no raw dict return", which
   passed even though the replacement was itself broken.
4. A tier's fix was genuinely correct in isolation but broke 4
   pre-existing tests it never accounted for (a constructor signature
   change with call sites outside the item's own `target` scope).

## Why this matters beyond tonight

This is a step beyond the already-known "weak `build_cmd` lets a
regression slip through" pattern (queued and partially addressed earlier
tonight) — here the `build_cmd`s were **drafted by `triapi plan`'s own
planning tier**, not hand-authored by a supervisor under time pressure,
and several were self-referential in a way that made them structurally
incapable of catching the very failure they existed to prevent (checking
a hallucinated file's own AST; checking for a `GoogleAuthError` substring
regardless of which module it came from). A `build_cmd` that only
inspects source text/AST, rather than actually importing/instantiating/
running the changed code, cannot distinguish "the fix is real" from
"words that look like the fix are present somewhere in the file."

## Not fixed — flagged as a real, undesigned improvement idea

- [ ] Possible angle, not designed yet: have `dispatcher.py` sanity-check
  that a tier's diff actually touched the item's declared `target` path
  (and, ideally, no *new* file outside it) before accepting a `success` —
  would have caught finding #1 immediately regardless of the flawed
  `build_cmd`. Not urgent: caught this time via manual supervision with
  no lasting damage, and a stricter check risks false-positives on
  legitimately-scoped multi-file fixes (e.g. tonight's own daemon.py +
  mail_watcher.py coupling), so it needs real design thought before
  implementing, not a quick patch.

## Session state

oh-my-llama: all 5 audit findings genuinely fixed now (commit `fa76279`),
full suite 177 passed/3 skipped, pushed clean, working tree clean. TriAPI:
nothing mid-flight, no code changes made here tonight (this session's
TriAPI-side work was supervision only, consistent with the standing
"never do TriAPI's job for target-repo work" split — the fixes above all
landed in oh-my-llama, not here).

## Session closed here — resume point for the next session

Nothing mid-flight in either repo, no live `triapi.py dispatch` process,
no active monitors. **Next queued action is on oh-my-llama's side, not
here:** Sub-Phase 5G (retire the old `ohmyllama/` runtime originals —
`orchestrator.py`, `agent.py`, `ghostwriter.py`, `watcher.py`) is READY —
its 7-day production-soak gate elapsed 3 days ago (5F finished 2026-08-18,
today 2026-08-28). The user wants it run via `triapi plan`/`dispatch`
timed to a DeepSeek off-peak window; off-peak was confirmed open as of
this session's close (`budget_guard.check_tier3_peak_hours_ok()` →
weekend off-peak rate in effect). Full detail recorded in oh-my-llama's
own `docs/Agent/CARRYOVER.md`, which the standing "target-repo docs stay
in target repo" rule keeps as the authoritative copy — this is a pointer,
not a duplicate.
