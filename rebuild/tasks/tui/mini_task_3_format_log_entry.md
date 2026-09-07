Mini-task 3 (deepseek) — `format_log_entry`. See rebuild/tasks/triapi_tui_plan.md.
DONE 2026-09-06 — landed in `rebuild/scripts/tui_session_log.py` (module split out of the
original monolithic tui.py after this task was applied; prompt below is the original, pre-split).

Paste current `rebuild/scripts/tui.py` verbatim, ask for only this:

Replace `format_log_entry`'s body per its existing docstring contract: return
this exact f-string (note the blank lines are part of the required output,
and there are exactly two trailing newlines at the very end):

    f"## {ts}\n\n**Prompt:** {prompt}\n\n**Response:**\n\n{response}\n\n"

Do not touch any other function or the class. Return the complete updated file.

Checkpoint: `pytest -v rebuild/tests/test_tui.py -k format_log_entry` passes.
