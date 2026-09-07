Current file (rebuild/scripts/task_queue.py) — edit in place, do not regenerate from memory:
```python
"""CLI over the SQLite task queue used by the supervisor loop (see
AGENTS.md, "Queue pipeline"). The only sanctioned way anything touches
queue.sqlite3 -- no other code opens it directly.

Skeleton written by Claude (top-level constructor): schema, connection
setup, and every function signature/contract are fixed here. Each cmd_*
body is filled in by a separate DeepSeek call (lower-level builder), one
function per call, per rebuild/tasks/queue/mini_task_{1..5}_*.md.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "queue.sqlite3"

SCHEMA_TASKS = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','approved','in_progress','blocked','done')),
    worker TEXT
        CHECK (worker IS NULL OR worker IN ('deepseek','agy')),
    depends_on TEXT,
    result TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

SCHEMA_EVENTS = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT,
    ts TEXT NOT NULL
)
"""


def init_conn(conn: sqlite3.Connection) -> None:
    """Apply WAL/busy_timeout and create both tables if absent. Called once
    per connection before any operation."""
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute(SCHEMA_TASKS)
    conn.execute(SCHEMA_EVENTS)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_task_id() -> str:
    return uuid.uuid4().hex


def insert_event(
    conn: sqlite3.Connection,
    task_id: str,
    event_type: str,
    payload: str | None,
    ts: str,
) -> None:
    """Append-only write to events. Does not commit -- caller owns the
    transaction boundary (one UPDATE/INSERT to tasks + one insert_event
    call, committed together)."""
    conn.execute(
        "INSERT INTO events (task_id, event_type, payload, ts) VALUES (?, ?, ?, ?)",
        (task_id, event_type, payload, ts),
    )


def cmd_add(args: argparse.Namespace, conn: sqlite3.Connection) -> int:
    """Contract (mini-task 1): insert a new 'pending' task row with a fresh
    uuid4().hex id, insert a matching 'created' event, commit both in one
    transaction. Print the new task id (bare) to stdout. Return 0.

    args used: description (str, required), worker (str|None), depends_on
    (str|None).
    """
    task_id = new_task_id()
    ts = utcnow()
    conn.execute(
        "INSERT INTO tasks (id, description, status, worker, depends_on, result, created_at, updated_at) "
        "VALUES (?, ?, 'pending', ?, ?, NULL, ?, ?)",
        (task_id, args.description, args.worker, args.depends_on, ts, ts),
    )
    insert_event(conn, task_id, "created", None, ts)
    conn.commit()
    print(task_id)
    return 0


def cmd_list(args: argparse.Namespace, conn: sqlite3.Connection) -> int:
    """Contract (mini-task 2): SELECT id, status, worker, description FROM
    tasks, optionally filtered by args.status, ordered by created_at ASC.
    Print one tab-separated line per row: id\tstatus\tworker\tdescription
    (worker printed as '' when NULL). Return 0.

    args used: status (str|None).
    """
    if args.status is not None:
        rows = conn.execute(
            "SELECT id, status, worker, description FROM tasks WHERE status = ? ORDER BY created_at ASC",
            (args.status,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, status, worker, description FROM tasks ORDER BY created_at ASC"
        ).fetchall()

    for row in rows:
        print(f"{row['id']}\t{row['status']}\t{row['worker'] or ''}\t{row['description']}")

    return 0


def cmd_approve(args: argparse.Namespace, conn: sqlite3.Connection) -> int:
    """Contract (mini-task 3): look up args.id. If missing, print
    'task {id} not found' to stderr, return 1. If status != 'pending',
    print 'task {id} is {status}, expected pending' to stderr, return 1.
    Otherwise, in one transaction: set status='approved', updated_at=now,
    insert an 'approved' event, commit. Return 0.

    args used: id (str, required).
    """
    raise NotImplementedError("mini-task 3: cmd_approve body not yet built")


def cmd_claim(args: argparse.Namespace, conn: sqlite3.Connection) -> int:
    """Contract (mini-task 4): if args.id given, that row must be
    'approved' or this errors (stderr, return 1). If not given, pick the
    oldest 'approved' row (by created_at) whose depends_on is NULL or
    points at a 'done' task; if none, print 'no approved task ready to
    claim' to stderr, return 1. Then UPDATE ... SET status='in_progress'
    WHERE id = ? AND status = 'approved'; if rowcount != 1 (lost a race),
    roll back, print 'task {id} was already claimed' to stderr, return 1.
    Otherwise insert a 'claimed' event, commit, print the claimed row in
    the same tab-separated format as cmd_list, return 0.

    args used: id (str|None).
    """
    raise NotImplementedError("mini-task 4: cmd_claim body not yet built")


def cmd_complete(args: argparse.Namespace, conn: sqlite3.Connection) -> int:
    """Contract (mini-task 5): look up args.id. If missing, stderr error,
    return 1. If status != 'in_progress', print 'task {id} is {status},
    expected in_progress' to stderr, return 1. Otherwise, in one
    transaction: set status=args.status ('done'|'blocked'),
    result=args.result, updated_at=now; insert a 'completed' event with
    payload json.dumps({"status": args.status}); commit. Return 0.

    args used: id (str, required), result (str, required),
    status (one of 'done'|'blocked', required).
    """
    raise NotImplementedError("mini-task 5: cmd_complete body not yet built")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("--description", required=True)
    add_parser.add_argument("--worker", choices=["deepseek", "agy"], default=None)
    add_parser.add_argument("--depends-on", dest="depends_on", default=None)
    add_parser.set_defaults(func=cmd_add)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--status", default=None)
    list_parser.set_defaults(func=cmd_list)

    approve_parser = subparsers.add_parser("approve")
    approve_parser.add_argument("id")
    approve_parser.set_defaults(func=cmd_approve)

    claim_parser = subparsers.add_parser("claim")
    claim_parser.add_argument("id", nargs="?", default=None)
    claim_parser.set_defaults(func=cmd_claim)

    complete_parser = subparsers.add_parser("complete")
    complete_parser.add_argument("--id", required=True)
    complete_parser.add_argument("--result", required=True)
    complete_parser.add_argument("--status", choices=["done", "blocked"], required=True)
    complete_parser.set_defaults(func=cmd_complete)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    conn = sqlite3.connect(DB_PATH)
    init_conn(conn)
    try:
        return args.func(args, conn)
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

```

Paste current `rebuild/scripts/task_queue.py` verbatim, ask for only this:

Replace `cmd_approve`'s body per its existing docstring contract:
`SELECT status FROM tasks WHERE id = ?` with `args.id`. If no row: print
`f"task {args.id} not found"` to stderr, return 1. If `status != "pending"`:
print `f"task {args.id} is {status}, expected pending"` to stderr, return 1.
Otherwise, in one transaction: `UPDATE tasks SET status = 'approved',
updated_at = ? WHERE id = ?`, `insert_event(conn, args.id, "approved", None,
ts)`, `conn.commit()`. Return 0.

Do not modify prior functions, the schema, or argparse wiring. Return the
complete updated file.

Checkpoint: `task_queue.py approve <id>` flips status; re-running the same
command errors with "expected pending" and exit code 1;
`pytest -v rebuild/tests/test_task_queue.py -k cmd_approve` (un-skip first) passes.
