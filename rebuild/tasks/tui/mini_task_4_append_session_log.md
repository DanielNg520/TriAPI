Mini-task 4 (deepseek) — `append_session_log`. See rebuild/tasks/triapi_tui_plan.md.

Paste current `rebuild/scripts/tui.py` verbatim, ask for only this:

Replace `append_session_log`'s body per its existing docstring contract:
`log_path.parent.mkdir(parents=True, exist_ok=True)`, then open `log_path`
in append mode (`"a"`, `encoding="utf-8"`) and write `entry` to it. No
return value.

Do not touch any other function or the class. Return the complete updated file.

Checkpoint: `pytest -v rebuild/tests/test_tui.py -k append_session_log` passes.
