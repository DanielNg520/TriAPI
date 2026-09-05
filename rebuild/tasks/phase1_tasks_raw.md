### TASK-P1-01: Test Output Parser
- **One-line goal**: Parse stdout/stderr from test runners (pytest, unittest) into exact counts of passed, failed, errors, and skipped tests.
- **Target file & signature**: 
  File: `TriAPI/rebuild/scripts/verify.py`
  ```python
  def parse_test_output(output: str) -> dict[str, int]:
  ```
- **Inputs**:
  - `output: str`: Combined stdout and stderr text produced by running a test suite (e.g. pytest summary line `5 passed, 1 skipped in 0.12s` or unittest `Ran 6 tests in 0.05s ... OK (skipped=1)`).
- **Outputs**:
  - `dict[str, int]` containing exactly the keys:
    - `"passed"`: number of tests that passed.
    - `"failed"`: number of failed assertions / test failures.
    - `"errors"`: number of setup/teardown/unhandled errors.
    - `"skipped"`: number of skipped tests.
    - `"total_executed"`: `passed + failed + errors` (tests that actually executed assertions, excluding skipped).
- **Scope boundaries**:
  - **In scope**: Pure string parsing via regular expressions matching standard pytest (`X passed, Y failed, Z skipped, W error`) and unittest terminal summary formats; default missing counts to `0`.
  - **Out of scope**: Do NOT execute any subprocess commands, do NOT read files from disk, do NOT determine pass/fail status.

---

### TASK-P1-02: Test Command Subprocess Runner
- **One-line goal**: Execute a test command in a subprocess and determine ground-truth pass/fail based on exit code and parsed test execution counts.
- **Target file & signature**:
  File: `TriAPI/rebuild/scripts/verify.py`
  ```python
  def run_test_command(
      command: str | list[str],
      cwd: str | Path | None = None,
      timeout: int = 120,
  ) -> dict[str, Any]:
  ```
- **Inputs**:
  - `command: str | list[str]`: Command to execute (e.g. `"pytest -v tests/"` or `["pytest", "-v"]`).
  - `cwd: str | Path | None`: Working directory for execution (defaults to current working directory).
  - `timeout: int`: Maximum execution duration in seconds before raising timeout (default: `120`).
- **Outputs**:
  - `dict[str, Any]` containing:
    - `"passed"` (`bool`): `True` ONLY IF exit code is `0`, `failed == 0`, `errors == 0`, and `total_executed > 0`. `False` if exit code != 0, if any test failed/errored, or if `total_executed == 0` (even if exit code is 0).
    - `"returncode"` (`int`): Subprocess exit code (or `-1` on timeout).
    - `"counts"` (`dict[str, int]`): Output of `parse_test_output`.
    - `"zero_executed"` (`bool`): `True` if `total_executed == 0` (flagging skip-only or empty runs).
    - `"stdout"` (`str`): Captured standard output.
    - `"stderr"` (`str`): Captured standard error.
    - `"error_message"` (`str | None`): Explanation if failed (e.g. `"Zero tests executed"`, `"Process timed out after 120s"`, `"Exit code 1 with 2 failures"`).
- **Scope boundaries**:
  - **In scope**: Use `subprocess.run(..., capture_output=True, text=True, shell=isinstance(command, str), cwd=cwd, timeout=timeout)`; handle `subprocess.TimeoutExpired`; call `parse_test_output(stdout + "\n" + stderr)`.
  - **Out of scope**: Do NOT inspect source files or git diffs; do NOT retry failed commands; do NOT accept exit code 0 as success when `total_executed == 0`.

---

### TASK-P1-03: On-Disk Content Verification
- **One-line goal**: Verify that an on-disk file exactly matches expected target content or that specified search/replace edits are fully present and replaced.
- **Target file & signature**:
  File: `TriAPI/rebuild/scripts/verify.py`
  ```python
  def verify_file_content(
      file_path: str | Path,
      expected_content: str | None = None,
      search_replace_blocks: list[tuple[str, str]] | None = None,
  ) -> dict[str, Any]:
  ```
- **Inputs**:
  - `file_path: str | Path`: Path to the file on disk.
  - `expected_content: str | None`: Optional complete expected content of the file.
  - `search_replace_blocks: list[tuple[str, str]] | None`: Optional list of `(search_text, replace_text)` pairs that were supposed to be applied.
- **Outputs**:
  - `dict[str, Any]` containing:
    - `"passed"` (`bool`): `True` if all provided checks pass, `False` otherwise.
    - `"file_exists"` (`bool`): `True` if the file exists on disk.
    - `"diff"` (`str`): Unified diff between actual on-disk content and `expected_content` (empty string if identical or not supplied).
    - `"violations"` (`list[str]`): List of failure descriptions (e.g. `"File not found: ..."` , `"Search block still present: '...'"` , `"Replace block missing: '...'"` , `"Content mismatch"`).
- **Scope boundaries**:
  - **In scope**: Read file from disk with UTF-8 encoding; generate unified diff via `difflib.unified_diff`; check literal presence/absence of blocks; reject keyword-only grep.
  - **Out of scope**: Do NOT write or modify any files on disk; do NOT run git commands; do NOT run tests.

---

### TASK-P1-04: Scope Boundary Diff Validator
- **One-line goal**: Diff a file before and after a change and flag any modified lines falling outside the target function or section as scope violations.
- **Target file & signature**:
  File: `TriAPI/rebuild/scripts/verify.py`
  ```python
  def verify_scope_boundaries(
      before_content: str,
      after_content: str,
      allowed_function_name: str | None = None,
      allowed_line_range: tuple[int, int] | None = None,
  ) -> dict[str, Any]:
  ```
- **Inputs**:
  - `before_content: str`: File content prior to modification.
  - `after_content: str`: File content after modification.
  - `allowed_function_name: str | None`: Function name that was permitted to change. If provided and content is valid Python, parse AST of `before_content` (and `after_content`) to find line span `(start_line, end_line)`.
  - `allowed_line_range: tuple[int, int] | None`: Explicit 1-indexed `(start_line, end_line)` range allowed to change (used directly or as fallback).
- **Outputs**:
  - `dict[str, Any]` containing:
    - `"passed"` (`bool`): `True` if all modified lines in `after_content` fall strictly within the allowed range/function; `False` if changes occur outside or if `before_content == after_content` when a change was required.
    - `"allowed_range"` (`tuple[int, int] | None`): The resolved line span `(start, end)` permitted to change.
    - `"modified_lines"` (`list[int]`): 1-indexed line numbers in `after_content` modified or inserted.
    - `"violations"` (`list[str]`): List of violations describing lines modified outside the permitted boundary (e.g. `"Line 42 modified outside allowed span (10, 30)"`).
    - `"diff"` (`str`): Unified diff between `before_content` and `after_content`.
- **Scope boundaries**:
  - **In scope**: Use `difflib.unified_diff` to parse modified line numbers; use Python `ast` to find function line boundaries (`lineno` to `end_lineno`) when `allowed_function_name` is provided; produce explicit line-level violation descriptions.
  - **Out of scope**: Do NOT use regex heuristics on commit/task descriptions; do NOT read or write to filesystem directly; do NOT run test suites.

---

### TASK-P1-05: Ground-Truth Task Verification Entrypoint
- **One-line goal**: Compose test execution, content verification, and scope validation into a single entrypoint returning an honest boolean and complete raw evidence.
- **Target file & signature**:
  File: `TriAPI/rebuild/scripts/verify.py`
  ```python
  def verify_task(
      file_path: str | Path | None = None,
      before_content: str | None = None,
      expected_content: str | None = None,
      search_replace_blocks: list[tuple[str, str]] | None = None,
      allowed_function_name: str | None = None,
      allowed_line_range: tuple[int, int] | None = None,
      test_cmd: str | list[str] | None = None,
      cwd: str | Path | None = None,
      timeout: int = 120,
  ) -> dict[str, Any]:
  ```
- **Inputs**:
  - `file_path`: Path to modified file on disk (optional).
  - `before_content`: File content before change (optional).
  - `expected_content`: Full expected file content (optional).
  - `search_replace_blocks`: List of `(search, replace)` tuples to verify on disk (optional).
  - `allowed_function_name`: Target function name for scope checking (optional).
  - `allowed_line_range`: Target line range for scope checking (optional).
  - `test_cmd`: Command string or list to execute real test suite (optional).
  - `cwd`: Directory for test execution / file path resolution (optional).
  - `timeout`: Subprocess timeout in seconds (default: `120`).
- **Outputs**:
  - `dict[str, Any]` containing:
    - `"passed"` (`bool`): `True` if and only if at least one check was executed AND all executed checks passed; `False` if any check failed or if no checks were supplied.
    - `"summary"` (`str`): High-level description of verification outcome (e.g. `"All checks passed (tests: 5 passed; file content matched; scope intact)"` or `"Verification failed: test suite reported 0 tests executed"`).
    - `"evidence"` (`dict[str, Any]`): Raw dictionary records for `"test_run"`, `"content_check"`, and `"scope_check"`.
- **Scope boundaries**:
  - **In scope**: Orchestrate calls to `verify_file_content`, `verify_scope_boundaries`, and `run_test_command`; read `file_path` from disk to supply `after_content` if `before_content` is provided; enforce that empty verification specifications fail by default.
  - **Out of scope**: Do NOT catch or silently swallow unexpected exceptions; do NOT perform Git commits or edits; do NOT implement retry or auto-fix logic.

---

### TASK-P1-06: Verification Layer Test Suite
- **One-line goal**: Write unit tests covering all functions in `verify.py`, specifically validating zero-test detection, scope violation detection, and content diffing.
- **Target file**:
  File: `TriAPI/rebuild/tests/test_verify.py`
- **Inputs**:
  - Functions imported from `TriAPI.rebuild.scripts.verify`.
- **Outputs**:
  - Pytest-compatible unit test suite covering:
    - `test_parse_test_output_pytest_and_unittest`: Verifies counts extracted from sample stdout.
    - `test_run_test_command_zero_executed_fails`: Simulates test run reporting 0 executed tests and asserts `passed is False` despite exit code `0`.
    - `test_run_test_command_failure_and_timeout`: Asserts failures, non-zero return codes, and timeouts report `passed is False`.
    - `test_verify_file_content_matching_and_mismatch`: Tests exact match, missing replace block, remaining search block, and file-missing cases.
    - `test_verify_scope_boundaries_allowed_function`: Tests AST-based boundary check allowing edits inside target function and failing on edits outside.
    - `test_verify_task_honest_evidence`: Verifies `verify_task` returns complete evidence dictionary and fails when checks fail or no checks are provided.
- **Scope boundaries**:
  - **In scope**: Write standard `pytest` test cases in `TriAPI/rebuild/tests/test_verify.py` using `unittest.mock.patch` for subprocess calls and `tmp_path` for file operations.
  - **Out of scope**: Do NOT modify `TriAPI/rebuild/scripts/verify.py`; do NOT depend on external network or remote APIs.

