Break the following into small, independent coding tasks. Format: task id, one-line goal, exact function/file, inputs/outputs, explicit out-of-scope notes.

## Feature: redesign the mail_ping Telegram keyboard

File: `/home/dyne/Documents/Coding/SemAI/src/semai/adapters/telegram.py`

Context: `_send()` builds a `mail_ping` inline keyboard as a single row of 5 buttons (lines ~250-256):

```python
keyboard = [[
    {"text": "[ Full ]", "callback_data": f"mail_action:full:{msg_id}"},
    {"text": "[ Summary ]", "callback_data": f"mail_action:summary:{msg_id}"},
    {"text": "[ Remind me ]", "callback_data": f"mail_action:remind:{msg_id}"},
    {"text": "[ Add task ]", "callback_data": f"mail_action:task:{msg_id}"},
    {"text": "[ Mute ]", "callback_data": f"mail_action:mute:{msg_id}"},
]]
```

This truncates on a phone screen. The existing `_approval_kb` method (lines ~338-348) already shows the wanted style elsewhere in the same file:

```python
def _approval_kb(self, approval_id: int) -> list:
    return [
        [
            {"text": "✅ Approve", "callback_data": f"a:{approval_id}"},
            {"text": "❌ Reject", "callback_data": f"r:{approval_id}"},
        ]
    ]
```

`_handle_callback`'s `mail_action` branch (lines ~374-408) currently always answers with a hardcoded
`await self._answer_cb(callback_query.get("id", ""), "Action processed")` regardless of whether
`MarkMailReadWorker` raised or the dispatcher call failed, and never removes/updates the original message.

### Task A: keyboard layout + labels
Goal: replace the 5-button single row with 2 rows and emoji-prefixed labels, no brackets, matching
`_approval_kb`'s existing style. Exact replacement for the `keyboard = [[...]]` block only:
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
Out of scope: anything outside this one assignment inside `_send`.

### Task B: real success/failure feedback + auto-delete on success
Goal: in `_handle_callback`'s `mail_action` branch, track whether `MarkMailReadWorker` raised and whether
the dispatcher's result indicates failure. On success: delete the original mail_ping message via the
Telegram `deleteMessage` API (chat_id + message_id from `callback_query["message"]`); if the delete call
raises/fails, fall back silently to editing the message's `reply_markup` to a single "✅ Done" button with
no callback_data, never surface a raw Telegram error to the user. On failure (worker raised or dispatcher
signals failure): call `_answer_cb` with a real error message describing what failed, not "Action processed".
Needs a new small helper `_delete_message(chat_id, message_id) -> bool` (uses `self._call("deleteMessage", ...)`,
returns False on any exception, does not raise) — model it after the existing `_call`/`_answer_cb` pattern in
this file (read the file's current `_call` signature before writing this, don't guess it).
Out of scope: `_approval_kb`'s own callback path (`kind in ("a", "r")`, lines ~350-365) — must remain unaffected,
it also calls `_answer_cb` but through a different code path than `mail_action`.

### Task C (tests)
File: existing test file covering `telegram.py`'s callback handling (find it — likely
`tests/test_telegram*.py` in SemAI). Add/extend tests for: 2-row keyboard shape from Task A; Task B's
success path calls deleteMessage and does not call the old generic "Action processed" text; Task B's
failure path (worker raises) answers with a message reflecting the failure, not "Action processed";
deleteMessage failure falls back to the edit-to-"Done" path without raising. List this as a task too.

Reply with the task list only, no other text.
