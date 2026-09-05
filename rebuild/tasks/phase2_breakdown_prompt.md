Break the following phase into small, independent coding tasks. Same format as before: task id, one-line goal, exact function signature/file, inputs/outputs, explicit out-of-scope notes. Each task small enough for a fresh model to do correctly from the description alone.

## Phase 2: Minimal single-task dispatcher

Goal: a small Python module (target: `TriAPI/rebuild/scripts/dispatch.py`) that applies ONE task's file change and calls Phase 1's `scripts/verify.py::verify_task()` to report a true result. No tiers, no escalation, no retries, no self-fix — that's explicitly out of scope for this phase.

Existing Phase 1 module (`scripts/verify.py`) already provides:
```python
def verify_task(file_path=None, before_content=None, expected_content=None, search_replace_blocks=None, allowed_function_name=None, allowed_line_range=None, test_cmd=None, cwd=None, timeout=120) -> dict:
    # returns {"passed": bool, "summary": str, "evidence": dict}
```

Required capabilities (turn each into one or more small tasks):
1. Given a target file path and either full new content or a list of (search_text, replace_text) blocks, apply the change to disk. Must snapshot the file's original content first (in memory, return it to the caller) so a caller can restore it if verification fails. If search/replace blocks are used, each search_text must appear in the file's current content exactly once — if it appears zero or more than once, fail before writing anything (no partial/ambiguous writes).
2. Given the original content (from step 1) and a file path, restore the file to that exact original content (a simple write-back, used on verify failure or by a caller that wants to roll back).
3. A single `dispatch_task(...)` entrypoint that: reads the file's current content as before_content, applies the change (task 1), calls `verify_task(...)` with the appropriate args (file_path, before_content, expected_content/search_replace_blocks, allowed_function_name/allowed_line_range, test_cmd, cwd, timeout), and if verification fails, restores the original content (task 2) before returning. Returns a dict with the verify_task result plus a "rolled_back" bool (True if restore happened).

Reply with the task list only, no other text.
