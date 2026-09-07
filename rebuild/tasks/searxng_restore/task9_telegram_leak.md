Produce a Search/Replace block (OLD/NEW fenced code blocks) for `src/semai/adapters/telegram.py`. Reply with only the two blocks, no prose.

OLD:
```python
        if text.startswith("/memory"):
            try:
                import sqlite3
                conn = sqlite3.connect(".state-semai/mail_state.sqlite3")
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                lines = []
                for (tname,) in tables:
                    lines.append(f"Table: {tname}")
                    cursor.execute(f"SELECT * FROM {tname}")
                    for row in cursor.fetchall():
                        lines.append(str(row))
                conn.close()
                dump_str = "\n".join(lines)
                if len(dump_str) > 4000:
                    dump_str = dump_str[:3997] + "..."
                await self._send(chat_id, dump_str if dump_str else "Memory is empty.")
            except Exception as e:
                await self._send(chat_id, f"Failed to read memory: {e}")
            return
```

NEW (same behavior; the ONLY change is guaranteeing conn.close() runs even if an exception happens between connect() and the previous close() call — move the connect+read logic into its own try/finally nested inside the existing try/except, so `conn.close()` always executes once `conn` was successfully created, regardless of whether reading tables/rows raises):
```python
        if text.startswith("/memory"):
            try:
                import sqlite3
                conn = sqlite3.connect(".state-semai/mail_state.sqlite3")
                try:
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                    tables = cursor.fetchall()
                    lines = []
                    for (tname,) in tables:
                        lines.append(f"Table: {tname}")
                        cursor.execute(f"SELECT * FROM {tname}")
                        for row in cursor.fetchall():
                            lines.append(str(row))
                finally:
                    conn.close()
                dump_str = "\n".join(lines)
                if len(dump_str) > 4000:
                    dump_str = dump_str[:3997] + "..."
                await self._send(chat_id, dump_str if dump_str else "Memory is empty.")
            except Exception as e:
                await self._send(chat_id, f"Failed to read memory: {e}")
            return
```
