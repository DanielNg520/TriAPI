Mini-task 4 (deepseek) — `claim`. See AGENTS.md, "Queue pipeline".

Paste current `rebuild/scripts/task_queue.py` verbatim, ask for only this:

Replace `cmd_claim`'s body per its existing docstring contract: if `args.id`
is given, that row must be `approved` or this errors (stderr, return 1). If
not given, pick the oldest `approved` row (by `created_at`) whose
`depends_on` is NULL or points at a `done` task; if none, print "no approved
task ready to claim" to stderr, return 1. Then `UPDATE tasks SET
status='in_progress', updated_at=? WHERE id=? AND status='approved'`; if
`cursor.rowcount != 1` (lost a race), roll back, print `f"task {id} was
already claimed"` to stderr, return 1. Otherwise insert a `claimed` event,
commit, print the claimed row in the same tab-separated format as
`cmd_list`, return 0.

Do not modify prior functions, the schema, or argparse wiring. Return the
complete updated file.

Checkpoint: claiming an approved task with no `depends_on` succeeds; a
second claim of the same id errors; a task whose `depends_on` isn't `done`
is skipped; `pytest -v rebuild/tests/test_task_queue.py -k cmd_claim`
(un-skip first) passes.
