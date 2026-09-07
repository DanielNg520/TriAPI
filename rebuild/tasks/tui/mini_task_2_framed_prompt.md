Mini-task 2 (deepseek) — `build_framed_prompt`. See rebuild/tasks/triapi_tui_plan.md.

Paste current `rebuild/scripts/tui.py` verbatim, ask for only this:

Replace `build_framed_prompt`'s body per its existing docstring contract:
return `FRAMING_PREFIX + raw_prompt`. Nothing else — no stripping, no
formatting, no validation of `raw_prompt`.

Do not touch any other function, the class, or the constants (especially
`FRAMING_PREFIX` itself — its wording is already decided, don't rewrite it).
Return the complete updated file.

Checkpoint: `pytest -v rebuild/tests/test_tui.py -k build_framed_prompt` passes.
