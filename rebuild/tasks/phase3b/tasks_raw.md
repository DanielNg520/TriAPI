### TASK-P3B-01: Cumulative Spend Budget Checker
- **One-line goal**: Check if cumulative spend from `read_cost_summary` is under a specified USD limit and return status with remaining balance without side effects or raising exceptions.
- **Target file & signature**:
  File: `TriAPI/rebuild/scripts/cost.py`
  ```python
  def check_budget(
      limit_usd: float,
      log_path: str | Path | None = None,
      config_path: str | Path | None = None,
  ) -> dict[str, Any]:
  ```
- **Inputs**:
  - `limit_usd: float`: Configured spending limit in USD.
  - `log_path: str | Path | None`: Optional path to `cost_log.jsonl` (passed through to `read_cost_summary`).
  - `config_path: str | Path | None`: Optional path to `tiers.yaml` (passed through to `read_cost_summary`).
- **Outputs**:
  - `dict[str, Any]` containing exactly the keys:
    - `"under_limit"` (`bool`): `True` if `total_cost_usd <= limit_usd`, `False` otherwise.
    - `"total_cost_usd"` (`float`): Cumulative spend in USD from `read_cost_summary`.
    - `"limit_usd"` (`float`): Target limit passed in.
    - `"remaining_usd"` (`float`): `limit_usd - total_cost_usd` (negative if spend exceeds limit).
- **Scope boundaries**:
  - **In scope**: Call `read_cost_summary(log_path=log_path, config_path=config_path)`; compare `total_cost_usd` against `limit_usd`; compute `remaining_usd`; return result dictionary.
  - **Out of scope**: Do NOT raise exceptions when over budget; do NOT modify files or log records; do NOT read `model_config.yaml` directly; do NOT print messages to stdout or stderr.

---

### TASK-P3B-02: Spend Limit Config & Pre-Call Guard Wiring
- **Assignee**: Claude does this directly
- **One-line goal**: Add default `spend_limit_usd` to model config and enforce the budget check in `call_deepseek.py` before executing API calls.
- **Target files & signatures**:
  File: `TriAPI/rebuild/config/model_config.yaml`
  File: `TriAPI/rebuild/scripts/call_deepseek.py`
  ```python
  def main() -> int:
  ```
- **Inputs**:
  - `TriAPI/rebuild/config/model_config.yaml`: `spend_limit_usd: 5.0` entry added under the `deepseek` block.
  - `call_deepseek.py` execution flow: inspects configuration and calls `cost.check_budget`.
- **Outputs**:
  - If `under_limit` is `True`: proceeds with normal execution and API invocation.
  - If `under_limit` is `False`: prints `f"[BLOCKED] Cumulative spend ${total_cost_usd:.4f} exceeds limit ${limit_usd:.2f}"` to `sys.stderr` and terminates process with exit code `1` without calling `llm_client.execute_deepseek`.
- **Scope boundaries**:
  - **In scope**: Add `spend_limit_usd: 5.0` to `model_config.yaml`; in `call_deepseek.py`, load config via `llm_client.load_model_config()`, invoke `cost.check_budget`, check `under_limit`, write blocking message to stderr, and exit with code 1 before secret loading or API execution.
  - **Out of scope**: Do NOT make the DeepSeek API call when over limit; do NOT modify `cost.py` or `llm_client.py`; do NOT add CLI flags to bypass the limit.

---

### TASK-P3B-03: Fenced Code-Block Extractor
- **One-line goal**: Extract content from the first fenced code block matching a specified language (or bare fence fallback) and raise ValueError if no block exists.
- **Target file & signature**:
  File: `TriAPI/rebuild/scripts/llm_client.py`
  ```python
  def extract_code_block(
      response: str,
      language: str = "python",
  ) -> str:
  ```
- **Inputs**:
  - `response: str`: Raw text response containing markdown fenced code blocks.
  - `language: str`: Target language identifier for the code block (default: `"python"`).
- **Outputs**:
  - `str`: Content of the first matching fenced block, stripped only of opening and closing fence lines and their newlines, with all internal whitespace preserved.
- **Exceptions**:
  - Raises `ValueError("no fenced code block found")` if neither a ````{language}```` block nor a bare ```` ``` ```` block is present.
- **Scope boundaries**:
  - **In scope**: Match first block of pattern ````{language}\n(.*?)\n``` ``; if not found, match first bare block ```` ```\n(.*?)\n``` ``; remove opening and closing fence delimiters; preserve leading/trailing whitespace within the body; raise `ValueError` on failure.
  - **Out of scope**: Do NOT strip internal indentation or blank lines; do NOT parse or execute the code block; do NOT modify the input string.

---

### TASK-P3B-04: Spend Cap Unit Test Suite
- **One-line goal**: Unit test `check_budget` across under-limit, over-limit, exact-limit, missing-log, and empty-log scenarios.
- **Target file**:
  File: `TriAPI/rebuild/tests/test_cost.py` (append)
- **Inputs**:
  - `check_budget` imported from `scripts.cost`.
  - Synthetic log entries and pricing configurations created via `tmp_path`.
- **Outputs**:
  - Pytest unit tests covering:
    - `test_check_budget_under_limit`: Log total spend < limit returns `under_limit=True`, correct `total_cost_usd`, and positive `remaining_usd`.
    - `test_check_budget_over_limit`: Log total spend > limit returns `under_limit=False`, correct `total_cost_usd`, and negative `remaining_usd`.
    - `test_check_budget_exact_limit`: Log total spend == limit returns `under_limit=True` and `remaining_usd == 0.0`.
    - `test_check_budget_missing_and_empty_log`: Missing or empty log file returns `under_limit=True`, `total_cost_usd=0.0`, and `remaining_usd == limit_usd`.
- **Scope boundaries**:
  - **In scope**: Use `pytest` and `tmp_path`; assert exact dictionary keys, types, and numerical values for budget evaluation.
  - **Out of scope**: Do NOT test CLI exit codes from `call_deepseek.py`; do NOT write to production log paths.

---

### TASK-P3B-05: Code-Block Extractor Unit Test Suite
- **One-line goal**: Unit test `extract_code_block` for language matching, bare fallback, whitespace preservation, and missing fence error handling.
- **Target file**:
  File: `TriAPI/rebuild/tests/test_llm_client.py` (new)
- **Inputs**:
  - `extract_code_block` imported from `scripts.llm_client`.
- **Outputs**:
  - Pytest unit test suite covering:
    - `test_extract_code_block_exact_language`: Extracts Python block when `language="python"` from mixed text.
    - `test_extract_code_block_bare_fallback`: Extracts bare ```` ``` ```` block when requested language tag is absent.
    - `test_extract_code_block_preserves_content_whitespace`: Verifies internal indentation, blank lines, and trailing spaces in code body are preserved.
    - `test_extract_code_block_first_block_priority`: Verifies that the first matching block is returned when multiple blocks exist.
    - `test_extract_code_block_custom_language`: Extracts non-python block when `language` argument is specified (e.g. `"yaml"`).
    - `test_extract_code_block_missing_raises_value_error`: Verifies `ValueError("no fenced code block found")` is raised when input lacks fenced blocks.
- **Scope boundaries**:
  - **In scope**: Pure unit testing of markdown extraction using `pytest`; tests valid, malformed, and missing blocks.
  - **Out of scope**: Do NOT mock network requests or test `execute_deepseek` / `execute_agy`.

