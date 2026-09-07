Target file: `src/semai/adapters/telegram.py` in the SemAI repo (current file
content pasted below — edit in place, return the complete updated file).

Root cause being fixed: `semai.adapters.push.deliver()` writes a `kind='alert'`
row into the shared `tasks` table (via `store.enqueue()` + `store.finish()`)
but nothing ever reads it back out and sends it via Telegram — `reply_to` and
`kind='alert'` are written once and never queried anywhere else in the
codebase. Add the missing consumer to `TelegramAdapter`.

Three changes, all in this one file, nothing else:

1. Add one import alongside the existing ones at the top of the file, for a
   helper that returns the current UTC time as an ISO string:
   `from semai.adapters.task_store import now_iso`

2. Add a new async method to `TelegramAdapter`, `_poll_alerts(self) -> None`,
   placed near `run()`. Contract:
   - Runs forever (`while True`), sleeping 5.0 seconds between iterations
     (hardcoded — no configurable interval, this isn't a config knob task).
   - Each iteration, query `self.store.db` (a `sqlite3.Connection` with
     `row_factory` already set so `row["col"]` indexing works — see
     `TelegramStore` in this same file for the existing pattern) for rows
     where `kind = 'alert'`, `status = 'done'`, `last_notify IS NULL`, and
     `reply_to IS NOT NULL`, oldest first. Select `id, reply_to, result`.
   - For each row: call `await self._send(reply_to, result or "")`. If it
     returns `True`, set that row's `last_notify` to `now_iso()` (so it is
     never sent twice); if `False`, leave it NULL so the next tick retries.
   - Wrap each iteration's body in `try/except Exception`, logging a warning
     (`log.warning(...)`) on failure and continuing the loop — one bad
     iteration must never kill the poller.

3. In `run()`, start `_poll_alerts` as a background `asyncio` task before
   entering the existing `while True:` update-polling loop, and cancel +
   await that task in the existing `finally:` block (before
   `self._client.aclose()`), swallowing `asyncio.CancelledError`. Do not
   change anything else about `run()`'s existing logic or control flow.

Do not modify any other method, class, or the module docstring. Do not add
retries, backoff, or a configurable poll interval. Reply with only the
complete updated file content, no prose before or after, no markdown fence
unless it wraps the whole file.
