Add one new test function to `/home/dyne/Documents/Coding/SemAI/tests/test_mail_watcher_seam.py`. Do not modify any existing function in that file.

Production code under test (already implemented in `src/semai/adapters/telegram.py`):

```python
    @staticmethod
    def _clean_mail_text(value: str) -> str:
        """Undo any HTML-entity-encoding already present in raw mail text
        (some senders put literal `&quot;` etc. straight in the Subject
        header) and strip invisible Unicode characters some marketing
        senders inject to dodge spam/clipping filters."""
        value = html.unescape(value)
        for ch in ("​", "‌", "‍", "͏", "﻿"):
            value = value.replace(ch, "")
        return value
```

It is called on `sender`/`subject`/`snippet` inside `_send`'s `mail_ping:` branch before building the display text, so a raw payload like:

```python
payload = "mail_ping:" + json.dumps({
    "msg_id": "m10",
    "sender": "shop@example.com",
    "subject": 'Delivery update: &quot;2Pcs 1.3&quot; OLED Display͏',
    "snippet": "",
})
```

should render with real quote characters and no stray invisible character in the sent message text, not literal `&quot;`.

Write one new `@pytest.mark.asyncio` test function, `test_send_unescapes_html_entities_and_strips_invisible_chars_in_mail_ping`, appended to the end of the file. Model it on the existing `test_send_renders_mail_ping_json_with_subject_snippet_and_buttons` test already in this file (same `DummyTelegramConfig`, `Store`, `FakeResp`/`fake_post`/`fake_aclose` pattern, same way of calling `adapter._send(chat_id, payload)` and reading `sent["params"]["text"]`). Assert the final `sent["params"]["text"]`:
- contains `"2Pcs 1.3"` OLED Display" with real `"` characters (i.e. contains the substring `2Pcs 1.3" OLED Display`)
- does NOT contain the substring `&quot;`
- does NOT contain the U+034F character

Reply with ONLY that one new test function as a single python code block, no other text.
