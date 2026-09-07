Edit one block in `/home/dyne/Documents/Coding/SemAI/src/semai/adapters/telegram.py`, inside `TelegramAdapter._send`.

Current exact block:

```python
        if text.startswith("mail_ping:"):
            try:
                info = json.loads(text[len("mail_ping:"):])
                msg_id = info["msg_id"]
                sender = info["sender"]
                subject = info.get("subject", "(no subject)")
                snippet = info.get("snippet", "")
            except Exception:
                pass
            else:
                if snippet:
                    text = f"📧 **{subject}**\nFrom: {sender}\n\n{snippet}"
                else:
                    text = f"📧 **{subject}**\nFrom: {sender}"
```

Problem: `_format_for_telegram` (elsewhere in this file, unchanged, do not touch it) HTML-escapes `&` to `&amp;` before sending with `parse_mode: "HTML"`. Some marketing-email senders put literal HTML entities (e.g. `&quot;`) straight into the raw Subject header or Gmail's snippet field. That escape step double-encodes them (`&quot;` -> `&amp;quot;`), so Telegram displays the literal text `&quot;` instead of a real `"`. Some senders also inject invisible Unicode characters (zero-width space U+200B, zero-width non-joiner U+200C, zero-width joiner U+200D, combining grapheme joiner U+034F, BOM U+FEFF) into subjects to dodge spam/clipping filters, which show up as stray glyphs.

Task: add a module-level import `import html` at the top of the file (alongside the other stdlib imports: `asyncio`, `json`, `logging`, `re`, `sys`), and add a small static helper method to `TelegramAdapter` plus use it on `subject`/`sender`/`snippet` before building `text`. Exact changes:

1. Add this static method to `TelegramAdapter` (place it directly above `_format_for_telegram`):

```python
    @staticmethod
    def _clean_mail_text(value: str) -> str:
        """Undo any HTML-entity-encoding already present in raw mail text
        (some senders put literal `&quot;` etc. straight in the Subject
        header) and strip invisible Unicode characters some marketing
        senders inject to dodge spam/clipping filters."""
        value = html.unescape(value)
        for ch in ("\u200b", "\u200c", "\u200d", "\u034f", "\ufeff"):
            value = value.replace(ch, "")
        return value
```

The 5 characters, via `\uXXXX` escapes so the file stays unambiguous to read/diff: zero-width
space (U+200B), zero-width non-joiner (U+200C), zero-width joiner (U+200D), combining grapheme
joiner (U+034F), byte-order-mark (U+FEFF). Use these exact `\uXXXX` escape sequences in the reply
-- do not substitute literal invisible characters.

2. Replace the block above with:

```python
        if text.startswith("mail_ping:"):
            try:
                info = json.loads(text[len("mail_ping:"):])
                msg_id = info["msg_id"]
                sender = self._clean_mail_text(info["sender"])
                subject = self._clean_mail_text(info.get("subject", "(no subject)"))
                snippet = self._clean_mail_text(info.get("snippet", ""))
            except Exception:
                pass
            else:
                if snippet:
                    text = f"📧 **{subject}**\nFrom: {sender}\n\n{snippet}"
                else:
                    text = f"📧 **{subject}**\nFrom: {sender}"
```

Do not touch `_format_for_telegram`, the keyboard block below this, or anything else in the file.

Reply with ONLY: (a) the single new import line, (b) the new `_clean_mail_text` static method, and (c) the replacement `if text.startswith("mail_ping:")` block -- three separate labeled python code blocks, no other text.
