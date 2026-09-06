# Carryover — 2026-08-29 23:52 — Three real oh-my-llama runtime bugs found+fixed live, one dispatch regression caught and reverted

**Session summary:** Resumed from the previous carryover file. TriAPI itself
needed no code changes this session — all work was supervising `triapi
plan`/`dispatch` against oh-my-llama for its two remaining queued
follow-ups, which turned out to be three separate real bugs (one queued
item split into two once properly root-caused). oh-my-llama's `AGENTS.md`
over-ceiling item (queued last session) was intentionally **not** started —
user asked to pick it up in a fresh session.

## Regression caught and reverted: a dispatch attempt broke the running orchestrator service

The first attempt at the queued `oh-my-llama.service` `WorkingDirectory=`
fix was misled by that same file's own top-of-file comment (an alternate
"if you run from source instead" `ExecStart` example mentioning
`WorkingDirectory`). The tier copied that fallback form wholesale, reverting
the correct `ExecStart=%h/.local/bin/semai-daemon`/`Type=exec` lines back to
a stale `python -m omll run`/`Type=simple` form — which doesn't exist
post-port (`omll` is the new semai-native CLI with different subcommands),
crash-looping `oh-my-llama.service` (`203/EXEC`, then `2/INVALIDARGUMENT`).

Caught by manual diff review, not by trusting the reported run status — the
build_cmd (`grep WorkingDirectory ...`) only checked the one line it cared
about and would have reported success despite the regression. Reverted by
hand (`git checkout HEAD --`), the correct unit redeployed and restarted.
The run was marked `cancelled` in TriAPI's own `logs/runs/*.json` and its
stale appended plan block removed from oh-my-llama's `AGENTS.md`, since it
was aborted mid-flight, never resumed.

**Lesson for future prompts:** when a target file has its own explanatory
comments mentioning alternate/legacy invocations, say so explicitly in the
dispatch prompt and tell the tier which lines are load-bearing and must stay
byte-for-byte identical — don't assume "add one line" is unambiguous to a
model that also sees a same-file comment suggesting a different, wrong form.

## Bug 1 fixed: `oh-my-llama.service` missing `WorkingDirectory=`

Root cause confirmed via `systemctl --user show oh-my-llama.service -p
WorkingDirectory` (reported `/home/dyne`, i.e. unset/default, not the repo).
This is why `MailWatcher`'s relative `db_path` never resolved correctly.
Redispatched with a much more surgical prompt (explicit "do not touch
ExecStart/Type", explicit instruction to ignore the misleading comment).
Landed cleanly this time — diff was exactly the one new line. Committed and
auto-pushed by TriAPI (run `20260829-222718-57ebd4`).

## Bug 2 fixed: `MailWatcher`'s SQLite tables never initialized

Fixing bug 1 alone wasn't sufficient — the db file now opened at the right
path, but `mail_watcher.py`'s `init_db()` (which creates the
`processed_emails`/`sender_defaults` tables) was never called anywhere in
`src/semai/`. `poll()` failed live with `no such table: processed_emails`
immediately after bug 1 landed. Fixed: `AsyncDaemon.__init__` (in
`src/semai/adapters/daemon.py`) now calls `mail_watcher.init_db()` before
constructing `self._mail_watcher`, matching how `ReminderStore` is already
initialized nearby. Commit `155603b`. Verified live: zero
`MailWatcher`-related errors across a ~6 minute window post-restart, versus
the prior ~60s-recurring failure.

## Bug 3 fixed: Telegram bot silently misconfigured — wrong env var name

The queued "wire `sops exec-env` into `deploy/oh-my-llama-telegram.service`"
item was completed correctly (mirrored the pattern recovered via `git log`/
`git show` from the deleted `oh-my-llama-web.service`), but the bot still
fail-closed with `TELEGRAM_ALLOWED_CHAT_IDS is empty` even after the user
confirmed the value was genuinely set in `.secret/secrets.json`. Root cause:
`src/semai/config/schema.py`'s `Settings.load()` read the allow-list from
`SEMAI_TELEGRAM_ALLOWED_CHATS` — a name that appears nowhere else in the
repo (not in docs, not in the deploy service's own header comment, not in
`secrets.example.json`, not even in the adjacent `telegram_bot_token=
e.get("TELEGRAM_BOT_TOKEN")` line two lines above it in the same function).
One-string-literal fix to `TELEGRAM_ALLOWED_CHAT_IDS`, commit
`1a55065`. Verified live: `oh-my-llama-telegram.service` now `active
(running)`, no fail-closed error, bot connects.

## Environment note: dispatch background processes keep dying mid-flight, cause still not identified

Recurring this session too (see the two previous carryover files for
earlier instances): a `triapi dispatch` invocation started via the
harness's `run_in_background` gets reported as killed/completed with no
result within roughly 1-3 minutes, while `triapi status` shows the run
still non-terminal. Twice this session, simply re-running `triapi dispatch
<run_id>` from a clean state (no dirty diff, no stale resource_guard lock)
picked the run back up and it completed normally on retry. Root cause still
not identified — flagging again for whoever next hits this.

## Status at session end

TriAPI: clean, no code changes this session (all fixes were in the target
repo). oh-my-llama: clean, three real bugs fixed and verified live,
`oh-my-llama.service` and `oh-my-llama-telegram.service` both `active
(running)`. Commits `0c3e86`-era WorkingDirectory fix, `155603b` (init_db),
`1a55065` (telegram env var) — see oh-my-llama's own git log for the exact
TriAPI-run commit messages.

## Queue item still open, not attempted this session (by explicit user request — start fresh next session)

oh-my-llama's own `AGENTS.md` is over this repo's 73,728-char ceiling (was
86,562 chars as of this session's check) — needs the same index/overflow-
to-`docs/agents/`-style treatment this repo already gave itself. User asked
to pick this up in a new session rather than continuing here.
