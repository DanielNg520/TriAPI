URGENT: this is a live production crash, fix is small and precise.

Edit one method, `TelegramStore.set_topic_id`, in `/home/dyne/Documents/Coding/SemAI/src/semai/adapters/telegram.py`.

Current exact method:

```python
    def set_topic_id(self, name: str, topic_id: int) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO telegram_topics (name, topic_id) VALUES (?, ?)",
            (name, topic_id)
        )
```

The live `telegram_topics` table (created elsewhere in this codebase, by `TaskStore`'s own schema
migration, not by this class) has a `created_at` column that is `NOT NULL`. This class's own
`_init_schema` uses `CREATE TABLE IF NOT EXISTS telegram_topics (name TEXT PRIMARY KEY, topic_id
INTEGER)`, which is a no-op against the already-existing table with the extra column, so it never
adds `created_at`. The result: this INSERT crashes in production with
`sqlite3.IntegrityError: NOT NULL constraint failed: telegram_topics.created_at`, because it never
supplies a value for that column.

This file already imports `now_iso` at the top: `from semai.adapters.task_store import now_iso`.
`TaskStore.telegram_set_topic` (a different class in `task_store.py`, same table) already does this
correctly:

```python
    def telegram_set_topic(self, name: str, topic_id: int) -> None:
        self.db.execute(
            """INSERT OR REPLACE INTO telegram_topics(name, topic_id, created_at)
               VALUES (?,?,?)""",
            (name, topic_id, now_iso()),
        )
```

Fix `TelegramStore.set_topic_id` so it no longer crashes against the live table shape (which has a
NOT NULL `created_at` column). Reply with ONLY the corrected `set_topic_id` method, as a single
python code block, no other text.
