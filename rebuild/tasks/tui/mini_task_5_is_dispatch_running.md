Mini-task 5 (deepseek) — `is_dispatch_running`. See rebuild/tasks/triapi_tui_plan.md.

Paste current `rebuild/scripts/tui.py` verbatim, ask for only this:

Replace `is_dispatch_running`'s body per its existing docstring contract: if
`not DB_PATH.exists()`, return False. Otherwise `conn =
sqlite3.connect(DB_PATH)`, call `init_conn(conn)` (already imported at the
top of the file), query
`conn.execute("SELECT 1 FROM tasks WHERE status = 'in_progress' LIMIT 1").fetchone()`,
close the connection in a `finally` block, and return `True` if a row was
found, `False` otherwise.

Do not touch any other function or the class. Return the complete updated file.

Checkpoint: `pytest -v rebuild/tests/test_tui.py -k is_dispatch_running` passes.
