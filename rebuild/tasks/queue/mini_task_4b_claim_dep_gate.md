Follow-up to mini-task 4 (deepseek) — `cmd_claim` explicit-id dependency gate.

Paste current `rebuild/scripts/task_queue.py` verbatim, ask for only this:

In `cmd_claim`, the explicit-`args.id` branch currently only checks that the
fetched row's status is `'approved'`. Add the same dependency check the
auto-pick branch already has: after confirming `status == 'approved'`, also
read the row's `depends_on`. If it is not NULL, look up that task's status;
if it is not `'done'`, print `f"task {args.id} depends on {depends_on} which
is not done"` to stderr and return 1 (do not claim it). Otherwise proceed as
before.

Do not modify the auto-pick branch (already correct), any other function,
the schema, or argparse wiring. Return the complete updated file.
