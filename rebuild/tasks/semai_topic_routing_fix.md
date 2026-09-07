In `src/semai/adapters/telegram.py`, class `TelegramAdapter` has:

```python
    _FORUM_TOPICS = ("reminders",)
```

This list is missing four topic names that `push.deliver()` is already called with elsewhere in the
codebase (`daemon.py`): `"mail"`, `"ghostwriter"`, `"agent"`, `"dispatch"`. Because they're missing,
`_ensure_forum_topics()` never creates real Telegram forum topics for them, `telegram_topic_id()`
returns `None` for those names, and `push.deliver()` silently falls back to posting in the group's
General topic instead of a dedicated one.

Fix: change the line to:

```python
    _FORUM_TOPICS = ("reminders", "mail", "ghostwriter", "agent", "dispatch")
```

Reply with only that single corrected line, no other text.
