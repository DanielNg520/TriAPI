Add new test functions to `/home/dyne/Documents/Coding/SemAI/tests/test_semai_telegram.py`. Do not modify any existing function in that file.

For context, here is the file's existing shared scaffolding (already present, do not redefine it — reuse it):

```python
class DummyConfig:
    def __init__(self, token: str, allowed_chats: set[int], forum_chat_id=None, agent_enabled=False):
        self.telegram_bot_token = token
        self.telegram_allowed_chats = allowed_chats
        self.telegram_poll_timeout_s = 30
        self.telegram_forum_chat_id = forum_chat_id
        self.agent_enabled = agent_enabled
        self.ollama_base_url = "http://fake-ollama"


class Result:
    """Minimal result object used by a dispatcher mock."""
    def __init__(self, message: str, ok=True, data=None):
        self.message = message
        self.ok = ok
        self.data = data or {}


class DummyDispatcher:
    """Mock dispatcher that records calls to dispatch."""
    def __init__(self, result: Result):
        self.result = result
        self.calls = []
        self.resolved_intents = []
        self._registry = {}
        self._approval_store = None

    @property
    def registry(self):
        return self._registry

    @registry.setter
    def registry(self, value):
        self._registry = value

    @property
    def approval_store(self):
        return self._approval_store

    @approval_store.setter
    def approval_store(self, value):
        self._approval_store = value

    def dispatch(self, text: str) -> Result:
        self.calls.append(text)
        return self.result

    def _resolve_confirm(self, intent) -> None:
        self.resolved_intents.append(intent)


class FakeResponse:
    """Simple httpx-like response for our mocked AsyncClient.post."""
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {}

    def json(self) -> Any:
        return self._json_data

    @property
    def text(self) -> str:
        return str(self._json_data)


@pytest.fixture
def store(tmp_path: Path) -> Store:
    return Store(tmp_path / "store.db")


async def _setup_adapter(
    store, allowed_chats: set[int], forum_chat_id=None, dispatcher_result=Result("ok")
):
    cfg = DummyConfig(token="TEST_TOKEN", allowed_chats=allowed_chats, forum_chat_id=forum_chat_id)
    dispatcher = DummyDispatcher(dispatcher_result)
    adapter = TelegramAdapter(cfg, store, dispatcher)
    calls = []

    async def fake_post(url: str, *, json):
        method_name = url.split("/")[-1]
        if "sendMessage" in method_name:
            response = FakeResponse(json_data={"result": {"message_id": len(calls) + 42}})
        elif "editMessageText" in method_name:
            response = FakeResponse()
        elif "answerCallbackQuery" in method_name:
            response = FakeResponse()
        else:
            response = FakeResponse(json_data={})
        calls.append((method_name, json))
        return response

    adapter._client.post = fake_post
    async def aclose():
        pass
    adapter._client.aclose = aclose

    adapter._calls = calls
    return adapter, dispatcher
```

Production code under test, `TelegramAdapter._handle_callback`'s `mail_action` branch (already implemented, in `src/semai/adapters/telegram.py`):

```python
        mail_match = re.match(r'^mail_action:(.+):(.+)$', data)
        if mail_match:
            action, msg_id = mail_match.groups()
            worker_failed = False
            try:
                from semai.core.intents import MarkMailRead
                from semai.workers.mail import MarkMailReadWorker
                worker = MarkMailReadWorker()
                intent = MarkMailRead(
                    kind="mark_mail_read",
                    msg_id=msg_id,
                    confidence=1.0,
                    raw_utterance=f"mail_action:{action}:{msg_id}",
                )
                await asyncio.to_thread(worker, intent)
            except Exception as e:
                log.error("Failed to invoke MarkMailReadWorker: %s", e)
                worker_failed = True

            dispatch_failed = False
            if hasattr(self, "_dispatcher") and self._dispatcher is not None:
                utterance_by_action = {
                    "full": f"show full email {msg_id}",
                    "summary": f"summarize email {msg_id}",
                    "remind": f"remind me about email {msg_id}",
                    "task": f"add task from email {msg_id}",
                    "mute": f"mute email {msg_id}",
                }
                utterance = utterance_by_action.get(
                    action, f"Handle email {msg_id} action {action}"
                )
                chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
                result = await asyncio.to_thread(self._dispatcher.dispatch, utterance)
                if not result or not hasattr(result, "message") or not getattr(result, "ok", True):
                    dispatch_failed = True
                if chat_id and result and hasattr(result, "message"):
                    await self._send(chat_id, result.message)

            if worker_failed or dispatch_failed:
                await self._answer_cb(callback_query.get("id", ""), "Failed to process email action")
                return

            chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
            message_id = callback_query.get("message", {}).get("message_id")
            if chat_id and message_id:
                deleted = await self._delete_message(chat_id, message_id)
                if not deleted:
                    try:
                        await self._call(
                            "editMessageReplyMarkup",
                            chat_id=chat_id,
                            message_id=message_id,
                            reply_markup={"inline_keyboard": [[{"text": "✅ Done", "callback_data": "noop"}]]},
                        )
                    except TelegramError as e:
                        log.debug("editMessageReplyMarkup failed for %s/%s: %s", chat_id, message_id, e)

            await self._answer_cb(callback_query.get("id", ""), "Done")
            return
```

And `_delete_message` itself:
```python
    async def _delete_message(self, chat_id: int | str, message_id: int) -> bool:
        """Delete a message. Returns True on success, False on any failure (never raises)."""
        try:
            await self._call("deleteMessage", chat_id=chat_id, message_id=message_id)
            return True
        except TelegramError as e:
            log.debug("deleteMessage failed for %s/%s: %s", chat_id, message_id, e)
            return False
```

Note: `MarkMailReadWorker()` is constructed with no arguments inside the try block, then called via `await asyncio.to_thread(worker, intent)` -- so `worker(intent)` (calling the instance) is what can raise. `MarkMailReadWorker` is imported from `semai.workers.mail`.

Write 4 new `@pytest.mark.asyncio` test functions, appended to the end of the file:

1. `test_mail_action_success_deletes_message`: use `_setup_adapter` with a successful `Result("done", ok=True)`. Monkeypatch `semai.workers.mail.MarkMailReadWorker` (use the `monkeypatch` fixture, patch the class so an instance is callable and does nothing / returns None) so the worker step succeeds. Build a `callback_query` dict with `"id": "cb1"`, `"message": {"chat": {"id": 123}, "message_id": 55}`. Call `await adapter._handle_callback("mail_action:full:m1", callback_query)`. Assert a `("deleteMessage", ...)` call is present in `adapter._calls` with `message_id == 55`. Assert the `answerCallbackQuery` call's json params has `"text": "Done"`. Assert no `editMessageReplyMarkup` call was made (delete succeeded, no fallback needed).

2. `test_mail_action_delete_failure_falls_back_to_done_markup`: same setup as test 1, but override `adapter._client.post` afterward (after `_setup_adapter` returns) so that a `deleteMessage` call raises `httpx.HTTPError("boom")` while all other methods behave like the original `fake_post`. Call `_handle_callback` the same way. Assert an `editMessageReplyMarkup` call is present in `adapter._calls` whose `reply_markup` is `{"inline_keyboard": [[{"text": "✅ Done", "callback_data": "noop"}]]}`. Assert this does not raise.

3. `test_mail_action_worker_failure_reports_error`: use `_setup_adapter` with a successful `Result`. Monkeypatch `semai.workers.mail.MarkMailReadWorker` so calling an instance raises `RuntimeError("db locked")`. Call `_handle_callback`. Assert the `answerCallbackQuery` call's params has `"text": "Failed to process email action"`. Assert no `deleteMessage` call was made.

4. `test_mail_action_dispatch_failure_reports_error`: use `_setup_adapter` with `dispatcher_result=Result("nope", ok=False)`. Monkeypatch `semai.workers.mail.MarkMailReadWorker` so the worker step succeeds (no-op). Call `_handle_callback`. Assert the `answerCallbackQuery` call's params has `"text": "Failed to process email action"`. Assert no `deleteMessage` call was made.

Follow the existing file's import style, `callback_query` shape, and assertion style (inspect `adapter._calls` list of `(method_name, json_params)` tuples) exactly as used elsewhere in this file.

Reply with ONLY the 4 new test functions (plus any additional imports they need placed as a short block before them, e.g. `httpx` if not already imported at module level -- it already is), as a single python code block, no other text.
