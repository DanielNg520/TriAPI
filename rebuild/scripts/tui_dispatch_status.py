"""Checks whether a `triapi claim` is currently in flight, for `triapi tui`'s
startup warning (see rebuild/tasks/triapi_tui_plan.md, re-scoping note).
"""

import sqlite3

from scripts.task_queue import DB_PATH, init_conn


def is_dispatch_running() -> bool:
    """Return True if the queue database (scripts.task_queue.DB_PATH)
    exists AND contains at least one row in `tasks` with
    status = 'in_progress' -- meaning a `triapi claim` is active.
    Return False if no such row exists, or if DB_PATH doesn't exist yet
    (don't create it -- a missing database means nothing is running).
    Open and close your own connection via sqlite3.connect(DB_PATH) and
    scripts.task_queue.init_conn(conn); don't assume one is passed in.
    """
    if not DB_PATH.exists():
        return False

    conn = sqlite3.connect(DB_PATH)
    try:
        init_conn(conn)
        row = conn.execute(
            "SELECT 1 FROM tasks WHERE status = 'in_progress' LIMIT 1"
        ).fetchone()
        return row is not None
    finally:
        conn.close()
