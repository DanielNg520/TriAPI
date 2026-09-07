Mini-task 5 (deepseek) — `complete`. See AGENTS.md, "Queue pipeline".

Paste current `rebuild/scripts/task_queue.py` verbatim, ask for only this:

Replace `cmd_complete`'s body per its existing docstring contract:
`SELECT status FROM tasks WHERE id = ?` with `args.id`. If missing: stderr
error, return 1. If `status != "in_progress"`: print `f"task {args.id} is
{status}, expected in_progress"` to stderr, return 1. Otherwise, in one
transaction: `UPDATE tasks SET status=?, result=?, updated_at=? WHERE id=?`
with `args.status` and `args.result`, then insert a `completed` event with
payload `json.dumps({"status": args.status})` (add `import json` at top),
commit. Return 0.

Do not modify prior functions, the schema, or argparse wiring. Return the
complete updated file.

Checkpoint: `task_queue.py complete --id <id> --result "ok" --status done` closes
the task; `task_queue.py list --status done` shows it;
`pytest -v rebuild/tests/test_task_queue.py -k cmd_complete` (un-skip first) passes.
