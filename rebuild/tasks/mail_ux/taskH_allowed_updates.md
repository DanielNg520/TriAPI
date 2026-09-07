Edit one call in `/home/dyne/Documents/Coding/SemAI/src/semai/adapters/telegram.py`, inside `TelegramAdapter.run`.

Current exact call inside the `while True:` loop:

```python
                resp = await self._call(
                    "getUpdates",
                    offset=offset,
                    timeout=self.cfg.telegram_poll_timeout_s,
                )
```

Context: the previous (pre-migration) implementation of this same bot in this repo's git history explicitly passed `allowed_updates=["message", "callback_query"]` to every `getUpdates` call. Per Telegram's Bot API docs, `allowed_updates` is sticky server-side per bot token once any client sets it -- if it was ever narrowed by some other tool/session using this same bot token, omitting the parameter here does not reset it back to "all types," it just keeps whatever was last set. This call currently omits it entirely.

Task: add the `allowed_updates` parameter to this call so both update types this adapter needs (`"message"` and `"callback_query"`) are explicitly requested every poll.

Reply with ONLY the corrected `self._call("getUpdates", ...)` call block, as a single python code block, no other text.
