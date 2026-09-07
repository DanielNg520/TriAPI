URGENT: live production bug.

File: `/home/dyne/Documents/Coding/SemAI/src/semai/adapters/telegram.py`, class `TelegramStore`.

Current state of the two relevant methods:

```python
    def _init_schema(self) -> None:
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS telegram_meta (key TEXT PRIMARY KEY, value TEXT)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS telegram_topics (name TEXT PRIMARY KEY, topic_id INTEGER)"
        )

    def set_topic_id(self, name: str, topic_id: int) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO telegram_topics (name, topic_id, created_at) VALUES (?, ?, ?)",
            (name, topic_id, now_iso()),
        )
```

(`now_iso` is already imported at the top of this file: `from semai.adapters.task_store import now_iso`.)

Observed failures:
- In production, against a `telegram_topics` table that another class (`TaskStore` in
  `task_store.py`) already created elsewhere with a NOT NULL `created_at` column, `set_topic_id`
  used to fail with `sqlite3.IntegrityError: NOT NULL constraint failed: telegram_topics.created_at`
  before it was changed to the form shown above.
- Against a fresh database where `_init_schema` above is what actually creates the table (this is
  what this repo's test suite exercises, e.g. `tests/test_semai_telegram.py::test_forum_topic_routing`),
  `set_topic_id` in its current (shown) form now fails instead with
  `sqlite3.OperationalError: table telegram_topics has no column named created_at`.

Fix `_init_schema` so both code paths work against the schema `set_topic_id` actually needs. Do not
change `telegram_meta`'s creation statement or `set_topic_id` itself.

Reply with ONLY the corrected `_init_schema` method, as a single python code block, no other text.
