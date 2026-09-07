### Task A: Keyboard layout and labels
- **Task ID**: TASK-A
- **Goal**: Replace the single-row 5-button inline keyboard in `_send()` with a 2-row emoji-prefixed keyboard.
- **Exact function/file**: `TelegramAdapter._send` in `/home/dyne/Documents/Coding/SemAI/src/semai/adapters/telegram.py` (lines 250-256)
- **Inputs/Outputs**:
  - **Inputs**: `msg_id: str` (extracted from the decoded `mail_ping` payload in `_send`)
  - **Outputs**: `keyboard: list[list[dict[str, str]]]` assigning:
    ```python
    keyboard = [
        [
            {"text": "📄 Full", "callback_data": f"mail_action:full:{msg_id}"},
            {"text": "📝 Summary", "callback_data": f"mail_action:summary:{msg_id}"},
            {"text": "⏰ Remind", "callback_data": f"mail_action:remind:{msg_id}"},
        ],
        [
            {"text": "✅ Task", "callback_data": f"mail_action:task:{msg_id}"},
            {"text": "🔇 Mute", "callback_data": f"mail_action:mute:{msg_id}"},
        ],
    ]
    ```
- **Explicit out-of-scope notes**: Anything outside the `keyboard = [[...]]` assignment block inside `_send()`. Do not alter payload extraction, text formatting, message chunking, or message dispatching.

---

### Task B1: Delete message helper
- **Task ID**: TASK-B1
- **Goal**: Add asynchronous `_delete_message(chat_id, message_id) -> bool` helper method to `TelegramAdapter`.
- **Exact function/file**: `TelegramAdapter._delete_message` in `/home/dyne/Documents/Coding/SemAI/src/semai/adapters/telegram.py` (add adjacent to `_edit` / `_answer_cb` at line ~326)
- **Inputs/Outputs**:
  - **Inputs**: `chat_id: int | str`, `message_id: int`
  - **Outputs**: `bool` (`True` if `self._call("deleteMessage", chat_id=chat_id, message_id=message_id)` succeeds; catches any exception/`TelegramError`, logs at debug level, and returns `False` without re-raising)
- **Explicit out-of-scope notes**: Modifying `_call`, `_send`, `_edit`, `_answer_cb`, or any other existing methods in `telegram.py`.

---

### Task B2: Feedback, auto-deletion, and fallback in callback handler
- **Task ID**: TASK-B2
- **Goal**: In `_handle_callback`'s `mail_action` branch, capture worker/dispatcher failures, delete original message on success (with fallback markup edit to "✅ Done" if delete fails), and report failure messages via `_answer_cb`.
- **Exact function/file**: `TelegramAdapter._handle_callback` in `/home/dyne/Documents/Coding/SemAI/src/semai/adapters/telegram.py` (lines 374-408)
- **Inputs/Outputs**:
  - **Inputs**: `data: str`, `callback_query: dict`
  - **Outputs**: `None`
    - On failure (worker raises exception or `dispatcher.dispatch` returns failure / raises exception): calls `await self._answer_cb(cb_id, error_message)` with a descriptive error string.
    - On success: extracts `chat_id` and `message_id` from `callback_query.get("message", {})`, calls `await self._delete_message(chat_id, message_id)`; if `_delete_message` returns `False`, calls `await self._call("editMessageReplyMarkup", chat_id=chat_id, message_id=message_id, reply_markup={"inline_keyboard": [[{"text": "✅ Done", "callback_data": "noop"}]]})` inside a try/except suppressing `TelegramError`; calls `await self._answer_cb(cb_id, "Done")`.
- **Explicit out-of-scope notes**: The approval callback path (`kind in ("a", "r")`, lines 410-424), `_decide_cb`, or any logic outside the `if mail_match:` block in `_handle_callback`.

---

### Task C1: Update existing mail ping keyboard assertions
- **Task ID**: TASK-C1
- **Goal**: Update existing keyboard structure assertions in `test_mail_watcher_seam.py` to match the new 2-row layout and emoji labels.
- **Exact function/file**: `test_send_renders_mail_ping_json_with_subject_snippet_and_buttons` in `/home/dyne/Documents/Coding/SemAI/tests/test_mail_watcher_seam.py` (lines 267-274)
- **Inputs/Outputs**:
  - **Inputs**: Mocked `_send` test setup sending a `mail_ping` JSON payload
  - **Outputs**: Assertions verifying `inline_keyboard` has 2 rows:
    - Row 0: `["📄 Full", "📝 Summary", "⏰ Remind"]` with respective `mail_action:*:m9` callback data
    - Row 1: `["✅ Task", "🔇 Mute"]` with respective `mail_action:*:m9` callback data
- **Explicit out-of-scope notes**: Any other test functions in `tests/test_mail_watcher_seam.py`.

---

### Task C2: Unit tests for callback handling, message deletion, and failure feedback
- **Task ID**: TASK-C2
- **Goal**: Add unit tests in `tests/test_semai_telegram.py` verifying `_delete_message` behavior, success path calling `deleteMessage`, failure fallback to "✅ Done" markup edit, and worker/dispatcher error reporting via `_answer_cb`.
- **Exact function/file**: New test functions in `/home/dyne/Documents/Coding/SemAI/tests/test_semai_telegram.py`
- **Inputs/Outputs**:
  - **Inputs**: Mocked `TelegramAdapter` instance and mock `callback_query` dictionaries for `mail_action`
  - **Outputs**: Assertions verifying:
    1. `_delete_message` returns `True` on success and `False` when `_call` raises `TelegramError`.
    2. Successful `mail_action` callback executes `deleteMessage` and does not call `_answer_cb` with "Action processed".
    3. `deleteMessage` failure triggers silent fallback to `editMessageReplyMarkup` with "✅ Done" button without raising.
    4. Worker exception or dispatcher failure invokes `_answer_cb` with an error message reflecting the failure.
- **Explicit out-of-scope notes**: Modifying existing approval callback tests (`test_approval_callbacks`) or modifying implementation files.

