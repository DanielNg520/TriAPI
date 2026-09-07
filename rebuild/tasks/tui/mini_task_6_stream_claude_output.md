Mini-task 6 (deepseek) — `stream_claude_output`. See rebuild/tasks/triapi_tui_plan.md.
Highest-risk of the six mini-tasks (subprocess + generator semantics) — review this
one's diff more carefully than the others before applying.

Paste current `rebuild/scripts/tui.py` verbatim, ask for only this:

Replace `stream_claude_output`'s body per its existing docstring contract:

    proc = subprocess.Popen(
        ["claude", "-p", prompt],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    for line in proc.stdout:
        yield line.rstrip("\n")
    proc.wait()

Do not touch any other function or the class. Do not add exception handling,
timeouts, or a return code check — the docstring explicitly says not to raise
on a non-zero exit. Return the complete updated file.

Checkpoint: `pytest -v rebuild/tests/test_tui.py -k stream_claude_output`
passes (both tests use a fake `subprocess.Popen`, no real `claude` call).
