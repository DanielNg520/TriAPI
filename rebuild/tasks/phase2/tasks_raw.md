### TASK-P2-01: Atomic File Change Applicator
- **One-line goal**: Snapshot a file's original content and apply either full new content or strictly unambiguous search/replace edits to disk, failing before write if ambiguous.
- **Target file & signature**:
  File: `TriAPI/rebuild/scripts/dispatch.py`
  ```python
  def apply_change(
      file_path: str | Path,
      new_content: str | None = None,
      search_replace_blocks: list[tuple[str, str]] | None = None,
  ) -> str:
  ```
- **Inputs**:
  - `file_path: str | Path`: Path to the target file to modify on disk.
  - `new_content: str | None`: Optional full replacement string for the file.
  - `search_replace_blocks: list[tuple[str, str]] | None`: Optional list of `(search_text, replace_text)` pairs to sequentially replace in the file.
- **Outputs**:
  - `str`: The exact original content snapshot of the file prior to any modifications.
- **Exceptions**:
  - Raises `FileNotFoundError` if `file_path` does not exist.
  - Raises `ValueError` if neither or both `new_content` and `search_replace_blocks` are provided.
  - Raises `ValueError` if any `search_text` appears zero times or more than once in the content (before writing any changes to disk).
- **Scope boundaries**:
  - **In scope**: Read target file as UTF-8; snapshot content into memory; validate occurrence counts (`content.count(search) == 1`) for all blocks before altering anything; apply replacements in order; write modified content to disk; return original content string.
  - **Out of scope**: Do NOT call `verify_task`; do NOT restore backups on external exceptions; do NOT run git commands or subprocesses.

---

### TASK-P2-02: File Content Restorer
- **One-line goal**: Restore a target file to its exact original content snapshot on disk.
- **Target file & signature**:
  File: `TriAPI/rebuild/scripts/dispatch.py`
  ```python
  def restore_file(
      file_path: str | Path,
      original_content: str,
  ) -> None:
  ```
- **Inputs**:
  - `file_path: str | Path`: Path to the file to restore.
  - `original_content: str`: The original file content to write back.
- **Outputs**:
  - `None`
- **Scope boundaries**:
  - **In scope**: Overwrite `file_path` with `original_content` using UTF-8 encoding.
  - **Out of scope**: Do NOT verify correctness; do NOT catch filesystem write errors; do NOT invoke git checkout.

---

### TASK-P2-03: Single-Task Dispatcher Entrypoint
- **One-line goal**: Read original content, apply file change, run verification, and automatically restore original content if verification fails.
- **Target file & signature**:
  File: `TriAPI/rebuild/scripts/dispatch.py`
  ```python
  def dispatch_task(
      file_path: str | Path,
      new_content: str | None = None,
      search_replace_blocks: list[tuple[str, str]] | None = None,
      allowed_function_name: str | None = None,
      allowed_line_range: tuple[int, int] | None = None,
      test_cmd: str | list[str] | None = None,
      cwd: str | Path | None = None,
      timeout: int = 120,
  ) -> dict[str, Any]:
  ```
- **Inputs**:
  - `file_path: str | Path`: Target file to modify and verify.
  - `new_content: str | None`: Optional full replacement string for the file.
  - `search_replace_blocks: list[tuple[str, str]] | None`: Optional list of `(search_text, replace_text)` pairs.
  - `allowed_function_name: str | None`: Optional function name allowed to change (passed to `verify_task`).
  - `allowed_line_range: tuple[int, int] | None`: Optional line range allowed to change (passed to `verify_task`).
  - `test_cmd: str | list[str] | None`: Optional test command (passed to `verify_task`).
  - `cwd: str | Path | None`: Working directory for test execution / verification (default: None).
  - `timeout: int`: Test command timeout in seconds (default: 120).
- **Outputs**:
  - `dict[str, Any]` containing all keys from `verify_task(...)` (`"passed"`, `"summary"`, `"evidence"`) plus:
    - `"rolled_back"` (`bool`): `True` if original file content was restored due to verification failure; `False` if verification passed or if change could not be applied.
- **Behavior**:
  - If `apply_change` fails (e.g. `ValueError` from ambiguous search block or `FileNotFoundError`), catch it and return:
    `{"passed": False, "summary": f"Dispatch error: {err}", "evidence": {"dispatch_error": str(err)}, "rolled_back": False}`.
  - Otherwise, call `verify_task` from `scripts.verify` with the parameters (`file_path`, `before_content=original_content`, `expected_content=new_content`, `search_replace_blocks`, `allowed_function_name`, `allowed_line_range`, `test_cmd`, `cwd`, `timeout`).
  - If `verify_task` returns `passed == False`, call `restore_file(file_path, original_content)` and return `{**result, "rolled_back": True}`.
  - If `verify_task` returns `passed == True`, return `{**result, "rolled_back": False}`.
- **Scope boundaries**:
  - **In scope**: Orchestrate `apply_change`, `restore_file`, and `verify_task`; handle rollback upon failed verification; report `"rolled_back"` flag accurately.
  - **Out of scope**: No retries; no tiered model escalations; no auto-fix attempts; no git commits.

---

### TASK-P2-04: Dispatcher Unit Test Suite
- **One-line goal**: Test `apply_change`, `restore_file`, and `dispatch_task` across full-content updates, search/replace updates, ambiguous block rejections, and rollback on verification failure.
- **Target file**:
  File: `TriAPI/rebuild/tests/test_dispatch.py`
- **Inputs**:
  - Functions imported from `TriAPI.rebuild.scripts.dispatch`.
- **Outputs**:
  - Pytest-compatible unit test suite covering:
    - `test_apply_change_new_content`: Verifies full file replacement writes correctly to disk and returns original content snapshot.
    - `test_apply_change_search_replace_blocks`: Verifies multiple sequential search/replace edits apply correctly.
    - `test_apply_change_missing_or_duplicate_search_blocks`: Verifies `ValueError` is raised when a search block occurs 0 times or >1 times, and asserts on-disk file remains completely unmodified.
    - `test_restore_file`: Verifies restoring original content overwrites modified disk content back to snapshot.
    - `test_dispatch_task_success`: Tests successful dispatch with mock `verify_task` returning `passed=True`, asserting file remains changed and `rolled_back is False`.
    - `test_dispatch_task_verification_failure_triggers_rollback`: Tests failed verification (`passed=False`), asserting on-disk file is restored to original snapshot and `rolled_back is True`.
    - `test_dispatch_task_apply_error_returns_failure`: Tests that pre-flight `apply_change` failure returns `passed=False` with `rolled_back=False`.
- **Scope boundaries**:
  - **In scope**: Use `pytest`, `tmp_path`, and `unittest.mock.patch` for `verify_task`; verify disk states before and after calls.
  - **Out of scope**: Do NOT execute real external test suites; do NOT modify `verify.py` or production code.

