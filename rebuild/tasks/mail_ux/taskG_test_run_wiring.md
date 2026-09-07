Add two new test functions to `/home/dyne/Documents/Coding/SemAI/tests/test_semai_telegram.py`. Do not modify any existing function in that file.

Context you need (read, don't copy verbatim unless it's genuinely the right shape):

Production code under test, `TelegramAdapter.run` (already implemented, in `src/semai/adapters/telegram.py`):

```python
    async def run(self) -> None:
        """Async long‑polling loop."""
        alerts_task: asyncio.Task | None = None
        try:
            me = (await self._call("getMe")).get("result", {})
            log.info("Telegram bot ready: %s", me)
            await self._ensure_forum_topics()
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
                    callback_query = upd.get("callback_query")
                    if callback_query is not None:
                        await self._handle_callback(
                            callback_query.get("data", ""), callback_query
                        )
                        continue
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

This file already has a `store` pytest fixture (`def store(tmp_path: Path) -> Store: return Store(tmp_path / "store.db")`, decorated `@pytest.fixture`) and this `DummyConfig` class, both already present and reusable as-is:

```python
class DummyConfig:
    def __init__(self, token: str, allowed_chats: set[int], forum_chat_id=None, agent_enabled=False):
        self.telegram_bot_token = token
        self.telegram_allowed_chats = allowed_chats
        self.telegram_poll_timeout_s = 30
        self.telegram_forum_chat_id = forum_chat_id
        self.agent_enabled = agent_enabled
        self.ollama_base_url = "http://fake-ollama"
```

`tests/test_semai_daemon.py` in this same repo has this established pattern for testing a `while True` polling loop without waiting it out (adapt it to `TelegramAdapter.run()` instead of a daemon's run loop):

```python
async def _run_one_idle_iteration(daemon):
    """Start daemon.run() in the background, let it execute its idle
    branch once, then cancel directly (not via stop(), which would wait
    out the current poll_interval_s sleep)."""
    run_task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.1)
    run_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await run_task
```

Write two tests that catch regressions in `run`'s wiring:

1. A test proving `run()` calls `_ensure_forum_topics()` once at startup (this is what actually registers Telegram forum topic IDs -- without it, alerts silently fall back to the main chat instead of their topic). You'll need to keep the rest of `run()`'s dependencies (`_call`, `_poll_alerts`) from doing real network/DB work during the test.

2. A test proving that when `run()` receives an update containing a `callback_query` (Telegram's shape for a button press), it dispatches to `_handle_callback` with that callback's `data` and the full callback_query dict -- and does NOT fall through to `_handle_message` for that update (which only looks at `upd["message"]` and would silently no-op on a callback_query update).

Use whatever mocking approach (`unittest.mock.AsyncMock`, a hand-written async stub function, `monkeypatch`) fits this file's existing conventions best. Add any additional imports you need at the top of the file if they aren't already there.

Reply with ONLY the code you're adding to the file (imports if any, plus the two new test functions), as python code block(s), no other text.
