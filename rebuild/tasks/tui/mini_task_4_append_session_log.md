Mini-task 4 (deepseek) — `append_session_log`. See rebuild/tasks/triapi_tui_plan.md.

Code now lives in rebuild/scripts/tui_session_log.py (split out of the original
monolithic tui.py, one small module per concern -- see AGENTS.md). Paste
current `rebuild/scripts/tui_session_log.py` verbatim, ask for only this:

Replace `append_session_log`'s body per its existing docstring contract:
`log_path.parent.mkdir(parents=True, exist_ok=True)`, then open `log_path`
in append mode (`"a"`, `encoding="utf-8"`) and write `entry` to it. No
return value.

Do not touch any other function. Return the complete updated file.

Checkpoint: `pytest -v rebuild/tests/test_tui_session_log.py -k append_session_log` passes.
