Add one new test function to `/home/dyne/Documents/Coding/SemAI/tests/test_mail_watcher_seam.py`. Do not modify any existing function in that file.

Here is an EXISTING test already in that exact file, verbatim -- your new test must copy this pattern exactly (same imports, same `DummyTelegramConfig`/`Store`/`FakeResp`/`fake_post`/`fake_aclose` shapes, same `adapter._client.post`/`adapter._client.aclose` attribute names, same `TelegramAdapter(cfg, store, None)` 3-arg constructor call, same `tmp_path` fixture usage). Do not invent different attribute names, different constructor arity, or a different fake response shape:

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

Write a NEW test function, `test_send_unescapes_html_entities_and_strips_invisible_chars_in_mail_ping(tmp_path)`,
with the exact same structure (same `sent = {}`, same `FakeResp`/`fake_post`/`fake_aclose`, same
`cfg`/`store`/`adapter` setup lines, same `adapter._client.post = fake_post` / `adapter._client.aclose = fake_aclose`,
same `await adapter._send(111, payload)` call), but with this payload instead:

```python
    payload = "mail_ping:" + json.dumps({
        "msg_id": "m10",
        "sender": "shop@example.com",
        "subject": "Delivery update: &quot;2Pcs 1.3&quot; OLED Display\u034f",
        "snippet": "",
    })
```

Then assert:
```python
    assert ok
    text = sent["params"]["text"]
    assert '2Pcs 1.3" OLED Display' in text
    assert "&quot;" not in text
    assert "\u034f" not in text
```

Reply with ONLY that one new test function as a single python code block, no other text.
