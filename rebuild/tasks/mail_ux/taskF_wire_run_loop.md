Edit one function, `TelegramAdapter.run`, in `/home/dyne/Documents/Coding/SemAI/src/semai/adapters/telegram.py`.

Current full function (edit in place, do not reconstruct from memory):

```python
    async def run(self) -> None:
        """Async long‑polling loop."""
        alerts_task: asyncio.Task | None = None
        try:
            me = (await self._call("getMe")).get("result", {})
            log.info("Telegram bot ready: %s", me)
            offset = await self._load_offset()
            alerts_task = asyncio.create_task(self._poll_alerts())
            while True:
                resp = await self._call(
                    "getUpdates",
                    offset=offset,
                    timeout=self.cfg.telegram_poll_timeout_s,
                )
                updates = resp.get("result", [])
                if not updates:
                    continue
                for upd in updates:
                    log.debug("got update %s", upd)
                    offset = max(offset, int(upd["update_id"]) + 1)
                    await self._handle_message(upd)
        except TelegramError as e:
            log.warning("Telegram error: %s", e)
        finally:
            if alerts_task is not None:
                alerts_task.cancel()
                try:
                    await alerts_task
                except asyncio.CancelledError:
                    pass
            await self._client.aclose()
```

Two confirmed bugs, both fixed by editing ONLY this function:

1. `_handle_message(upd)` only reads `upd.get("message")` and returns early if absent. A button press arrives as `upd["callback_query"]` (no `"message"` key at the top level), so `_handle_callback` (an existing method on this class, signature `async def _handle_callback(self, data: str, callback_query: dict) -> None`) is never invoked in production -- only in tests that call it directly. Fix: in the `for upd in updates:` loop, check for `upd.get("callback_query")` first; if present, call `await self._handle_callback(cb.get("data", ""), cb)` and `continue` to the next update instead of falling through to `_handle_message`.

2. `_ensure_forum_topics` (an existing async method on this class, no required arguments beyond `self` -- its `store` parameter is optional and unused internally) is defined but never called anywhere, so the `telegram_topics` table is always empty and mail/reminder alerts always fall back to the bare group chat instead of their forum topic. Fix: call `await self._ensure_forum_topics()` once, right after the existing `log.info("Telegram bot ready: %s", me)` line and before `offset = await self._load_offset()`.

Do not change `_handle_message`, `_handle_callback`, `_ensure_forum_topics`, `_poll_alerts`, or anything in the `except`/`finally` blocks.

Reply with ONLY the full corrected `run` function, as a single python code block, no other text.
