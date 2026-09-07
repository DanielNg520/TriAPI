Mini-task 1 (deepseek) — `new_session_log_path`. See rebuild/tasks/triapi_tui_plan.md.
DONE 2026-09-06 — landed in `rebuild/scripts/tui_session_log.py` (module split out of the
original monolithic tui.py after this task was applied; prompt below is the original, pre-split).

Skeleton already exists at `rebuild/scripts/tui.py` (Claude-authored: module
docstring, imports, SESSIONS_DIR/FRAMING_PREFIX constants, the TriapiTUI class,
and main() are already real; `new_session_log_path` raises NotImplementedError).
Paste that file's current content into the prompt verbatim, then ask for only this:

Replace `new_session_log_path`'s body per its existing docstring contract:
call `SESSIONS_DIR.mkdir(parents=True, exist_ok=True)`. Build a base name from
`datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")`. Candidate path is
`SESSIONS_DIR / f"{base}.md"`; if that path already exists, try
`SESSIONS_DIR / f"{base}-2.md"`, then `-3`, etc., incrementing until an
unused path is found. Do not create the file itself. Return the first unused
Path.

Do not touch any other function, the class, or the constants — those are
already built and correct. Return the complete updated file.

Checkpoint: `pytest -v rebuild/tests/test_tui.py -k new_session_log_path`
passes (both the fresh-directory case and the collision-avoidance case).
