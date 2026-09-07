Mini-task 1 (deepseek) — schema + `add`. See AGENTS.md, "Queue pipeline".

Skeleton already exists at `rebuild/scripts/task_queue.py` (Claude-authored: schema,
`init_conn`, `utcnow`, `new_task_id`, `insert_event`, `build_parser`, `main` are
already real; `cmd_add` raises `NotImplementedError`). Paste that file's current
content into the prompt verbatim, then ask for only this:

Replace `cmd_add`'s body per its existing docstring contract: generate
`task_id = new_task_id()`, `ts = utcnow()`. In one transaction: `INSERT INTO
tasks (id, description, status, worker, depends_on, result, created_at,
updated_at) VALUES (?, ?, 'pending', ?, ?, NULL, ?, ?)` with `args.description`,
`args.worker`, `args.depends_on`, then `insert_event(conn, task_id, "created",
None, ts)`, then `conn.commit()`. Print `task_id` to stdout (bare, nothing
else). Return 0.

Do not touch any other function, the schema, or argparse wiring — those are
already built and correct. Return the complete updated file.

Checkpoint: `python3 rebuild/scripts/task_queue.py add --description "test"` prints
a task id; `sqlite3 rebuild/queue.sqlite3 "select * from tasks"` shows one
pending row; `pytest -v rebuild/tests/test_task_queue.py::test_cmd_add_creates_pending_task`
(un-skip it first) passes.
