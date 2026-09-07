Mini-task 2 (deepseek) — `list`. See AGENTS.md, "Queue pipeline".

Paste current `rebuild/scripts/task_queue.py` verbatim, ask for only this:

Replace `cmd_list`'s body per its existing docstring contract: if
`args.status` is set, `SELECT id, status, worker, description FROM tasks
WHERE status = ? ORDER BY created_at ASC`, else the same query with no
`WHERE`. Print one line per row:
`f"{row['id']}\t{row['status']}\t{row['worker'] or ''}\t{row['description']}"`.
Return 0.

Do not modify `cmd_add`, the schema, or argparse wiring. Return the complete
updated file.

Checkpoint: `task_queue.py list` shows the task from mini-task 1; `task_queue.py list
--status pending` filters correctly;
`pytest -v rebuild/tests/test_task_queue.py::test_cmd_list_filters_by_status`
(un-skip it first) passes.
