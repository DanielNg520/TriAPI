Mini-task 3 (deepseek) — `approve`. See AGENTS.md, "Queue pipeline".

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
