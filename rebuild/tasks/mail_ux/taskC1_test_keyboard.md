Edit one test function in `/home/dyne/Documents/Coding/SemAI/tests/test_mail_watcher_seam.py`.

Current exact function (edit in place, do not reconstruct from memory):

```python
@pytest.mark.asyncio
async def test_send_renders_mail_ping_json_with_subject_snippet_and_buttons(tmp_path):
    """(e) the exact gap that shipped: daemon.py's real mail-ping path calls
    deliver(), whose message reaches _send() verbatim. _send() must decode
    that JSON payload into a subject/sender/snippet message with the 5-button
    keyboard -- not the plain colon-format the old code only handled."""
    from semai.memory.store import Store
    from semai.adapters.telegram import TelegramAdapter

    sent = {}

    class FakeResp:
        status_code = 200

        def json(self):
            return {"result": {"message_id": 1}}

        text = "{}"

    async def fake_post(url, *, json):
        sent["params"] = json
        return FakeResp()

    async def fake_aclose():
        pass

    cfg = DummyTelegramConfig()
    store = Store(tmp_path / "telegram_store2.sqlite3")
    adapter = TelegramAdapter(cfg, store, None)
    adapter._client.post = fake_post
    adapter._client.aclose = fake_aclose

    payload = "mail_ping:" + json.dumps({
        "msg_id": "m9",
        "sender": "boss@example.com",
        "subject": "Q3 numbers",
        "snippet": "Please review before Friday.",
    })
    ok = await adapter._send(111, payload)

    assert ok
    text = sent["params"]["text"]
    assert "Q3 numbers" in text
    assert "boss@example.com" in text
    assert "Please review before Friday." in text
    buttons = sent["params"]["reply_markup"]["inline_keyboard"][0]
    assert [b["callback_data"] for b in buttons] == [
        "mail_action:full:m9",
        "mail_action:summary:m9",
        "mail_action:remind:m9",
        "mail_action:task:m9",
        "mail_action:mute:m9",
    ]
```

The production code this tests now renders the keyboard as 2 rows instead of 1:
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

Task: update ONLY the final assertion block (from `buttons = sent["params"]...` to the end of the function) to check both rows instead of one flat row. Keep everything above `buttons = ...` (including the docstring) exactly as-is. Replace the trailing block with:

```python
    inline_keyboard = sent["params"]["reply_markup"]["inline_keyboard"]
    assert len(inline_keyboard) == 2
    assert [b["callback_data"] for b in inline_keyboard[0]] == [
        "mail_action:full:m9",
        "mail_action:summary:m9",
        "mail_action:remind:m9",
    ]
    assert [b["callback_data"] for b in inline_keyboard[1]] == [
        "mail_action:task:m9",
        "mail_action:mute:m9",
    ]
    assert inline_keyboard[0][0]["text"] == "📄 Full"
    assert inline_keyboard[1][1]["text"] == "🔇 Mute"
```

Reply with ONLY the full corrected `test_send_renders_mail_ping_json_with_subject_snippet_and_buttons` function, as a single python code block, no other text.
