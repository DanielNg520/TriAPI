You previously wrote this test code for `/home/dyne/Documents/Coding/SemAI/tests/test_semai_telegram.py`:

```python
import contextlib
from unittest.mock import AsyncMock, MagicMock

from semai.adapters.telegram import TelegramAdapter


@pytest.mark.asyncio
async def test_run_calls_ensure_forum_topics_once(store):
    cfg = DummyConfig(
        token="test-token",
        allowed_chats={123},
        forum_chat_id=-100,
    )
    adapter = TelegramAdapter(cfg, store)

    adapter._ensure_forum_topics = AsyncMock()
    adapter._call = AsyncMock(
        side_effect=[
            {"result": {"id": 1, "username": "test_bot"}},
            {"result": []},
            {"result": []},
            {"result": []},
        ]
    )
    adapter._load_offset = AsyncMock(return_value=0)
    adapter._poll_alerts = AsyncMock()
    adapter._client = MagicMock()
    adapter._client.aclose = AsyncMock()

    run_task = asyncio.create_task(adapter.run())
    await asyncio.sleep(0.1)
    run_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await run_task

    adapter._ensure_forum_topics.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_dispatches_callback_query_to_handle_callback(store):
    cfg = DummyConfig(
        token="test-token",
        allowed_chats={123},
        forum_chat_id=-100,
    )
    adapter = TelegramAdapter(cfg, store)

    callback_query = {
        "id": "cb_42",
        "data": "vote:option_1",
        "message": {"message_id": 10, "chat": {"id": 123}},
    }
    processed = asyncio.Event()

    async def track_callback(data, callback_query_arg):
        processed.set()

    adapter._ensure_forum_topics = AsyncMock()
    adapter._call = AsyncMock(
        side_effect=[
            {"result": {"id": 1, "username": "test_bot"}},
            {"result": [{"update_id": 42, "callback_query": callback_query}]},
            {"result": []},
            {"result": []},
        ]
    )
    adapter._load_offset = AsyncMock(return_value=0)
    adapter._poll_alerts = AsyncMock()
    adapter._client = MagicMock()
    adapter._client.aclose = AsyncMock()
    adapter._handle_callback = AsyncMock(side_effect=track_callback)
    adapter._handle_message = AsyncMock()

    run_task = asyncio.create_task(adapter.run())
    await asyncio.wait_for(processed.wait(), timeout=1)
    run_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await run_task

    adapter._handle_callback.assert_awaited_once_with(
        "vote:option_1", callback_query
    )
    adapter._handle_message.assert_not_awaited()
```

Two problems, found during review:

1. `TelegramAdapter.__init__` (in the real `telegram.py`) has this signature: `def __init__(self, cfg, store, dispatcher):` -- `dispatcher` is a required positional argument with no default. Your `TelegramAdapter(cfg, store)` calls in both tests will raise `TypeError: missing 1 required positional argument: 'dispatcher'`.

2. In the real `run()`, when `getUpdates` returns no updates, the loop does `if not updates: continue` -- there is no `await asyncio.sleep(...)` anywhere in that branch, so with `_call` mocked via a finite `side_effect` list, the loop will call `_call` again immediately (no delay) and can exhaust the whole `side_effect` list well before your test's `await asyncio.sleep(0.1)` (test 1) or `await asyncio.wait_for(processed.wait(), timeout=1)` (test 2) elapses. Once a `side_effect` list is exhausted, the mock raises on the next call, and that exception propagates out of `run()`'s `try` block (it isn't a `TelegramError`, so the `except TelegramError` clause doesn't catch it) into the background task -- which will surface as a test failure unrelated to what these tests are trying to verify.

Fix both problems and reply with the corrected two test functions (plus the import block), same format as before (python code block(s), no other text). You decide how to fix each problem; you are not being handed a specific implementation to copy.
