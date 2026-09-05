### TASK-P3-01: Reference Pricing & Cost Calculator
- **One-line goal**: Load `deepseek_reference_pricing` from `TriAPI/config/tiers.yaml` and compute the USD cost of given input and output token counts without hardcoding rates.
- **Target file & signature**:
  File: `TriAPI/rebuild/scripts/cost.py`
  ```python
  def calculate_cost(
      input_tokens: int,
      output_tokens: int,
      config_path: str | Path | None = None,
  ) -> float:
  ```
- **Inputs**:
  - `input_tokens: int`: Number of input tokens.
  - `output_tokens: int`: Number of output tokens.
  - `config_path: str | Path | None`: Optional path to `tiers.yaml` (default: repo root two levels up from `rebuild/scripts/` at `config/tiers.yaml`).
- **Outputs**:
  - `float`: Computed USD cost based on verified rates: `(input_tokens / 1_000_000 * cache_miss_rate) + (output_tokens / 1_000_000 * output_rate)`.
- **Exceptions**:
  - Raises `FileNotFoundError` if config file does not exist at resolved path.
  - Raises `KeyError` or `ValueError` if `deepseek_reference_pricing` block or `cache_miss_per_mtok_usd` is missing.
- **Scope boundaries**:
  - **In scope**: Resolve config path defaulting to `Path(__file__).resolve().parents[2] / "config" / "tiers.yaml"`; load YAML using `yaml.safe_load`; extract `deepseek_reference_pricing`; use `cache_miss_per_mtok_usd` for input tokens; use `output_per_mtok_usd` for output tokens (falling back to `cache_miss_per_mtok_usd` if null/None); compute and return total float USD cost.
  - **Out of scope**: Do NOT hardcode pricing defaults; do NOT log to disk; do NOT query remote pricing endpoints.

---

### TASK-P3-02: Cost Log Appender
- **One-line goal**: Append a single call entry with task ID, token counts, and call-time ISO8601 UTC timestamp to the JSONL log, creating missing parent directories and file automatically.
- **Target file & signature**:
  File: `TriAPI/rebuild/scripts/cost.py`
  ```python
  def log_cost(
      task_id: str,
      input_tokens: int,
      output_tokens: int,
      log_path: str | Path | None = None,
  ) -> dict[str, Any]:
  ```
- **Inputs**:
  - `task_id: str`: Task identifier string.
  - `input_tokens: int`: Number of input tokens consumed.
  - `output_tokens: int`: Number of output tokens generated.
  - `log_path: str | Path | None`: Optional path to `cost_log.jsonl` (default: `TriAPI/rebuild/logs/cost_log.jsonl`).
- **Outputs**:
  - `dict[str, Any]`: The appended record dictionary containing:
    - `"task_id"` (`str`): Task identifier.
    - `"input_tokens"` (`int`): Input token count.
    - `"output_tokens"` (`int`): Output token count.
    - `"timestamp"` (`str`): ISO8601 UTC timestamp string generated at call time (e.g. `datetime.now(timezone.utc).isoformat()`).
- **Scope boundaries**:
  - **In scope**: Resolve default log path to `Path(__file__).resolve().parents[1] / "logs" / "cost_log.jsonl"`; create parent directory if missing (`path.parent.mkdir(parents=True, exist_ok=True)`); format JSON object on a single line; append to file in UTF-8; return the record dict.
  - **Out of scope**: Do NOT calculate USD cost within this function; do NOT overwrite existing lines; do NOT rotate logs.

---

### TASK-P3-03: Cost Log Summary Aggregator
- **One-line goal**: Read all entries from `cost_log.jsonl` and return aggregated token totals, entry count, and total USD cost using `calculate_cost`.
- **Target file & signature**:
  File: `TriAPI/rebuild/scripts/cost.py`
  ```python
  def read_cost_summary(
      log_path: str | Path | None = None,
      config_path: str | Path | None = None,
  ) -> dict[str, Any]:
  ```
- **Inputs**:
  - `log_path: str | Path | None`: Optional path to JSONL log file (default: `TriAPI/rebuild/logs/cost_log.jsonl`).
  - `config_path: str | Path | None`: Optional path to `tiers.yaml` (passed to `calculate_cost`).
- **Outputs**:
  - `dict[str, Any]` containing:
    - `"total_input_tokens"` (`int`): Sum of input tokens across all entries (0 if log missing or empty).
    - `"total_output_tokens"` (`int`): Sum of output tokens across all entries (0 if log missing or empty).
    - `"total_cost_usd"` (`float`): Total USD cost calculated via `calculate_cost` (0.0 if log missing or empty).
    - `"entry_count"` (`int`): Number of valid log entries read (0 if log missing or empty).
- **Scope boundaries**:
  - **In scope**: Gracefully return zeroed dictionary if log file does not exist or is empty; parse non-empty lines with `json.loads`; sum tokens; compute total cost via `calculate_cost(total_input_tokens, total_output_tokens, config_path=config_path)`.
  - **Out of scope**: Do NOT print terminal tables or ANSI colors; do NOT delete or archive log entries.

---

### TASK-P3-04: Cost Tracking Unit Test Suite
- **One-line goal**: Unit test reference pricing calculation, YAML fallback resolution, JSONL log appending / directory creation, and summary aggregation.
- **Target file**:
  File: `TriAPI/rebuild/tests/test_cost.py`
- **Inputs**:
  - Functions imported from `TriAPI.rebuild.scripts.cost`.
- **Outputs**:
  - Pytest-compatible unit test suite covering:
    - `test_calculate_cost_from_tiers_yaml`: Computes cost using actual `TriAPI/config/tiers.yaml` reference rates and asserts expected USD output.
    - `test_calculate_cost_output_rate_fallback`: Verifies that `output_per_mtok_usd: null` properly falls back to `cache_miss_per_mtok_usd`, and uses explicit rate when present.
    - `test_calculate_cost_missing_config`: Verifies `FileNotFoundError` is raised on invalid path.
    - `test_log_cost_creates_file_and_appends`: Verifies directory auto-creation, valid JSONL output format, valid ISO8601 UTC timestamp, and sequential entry appending.
    - `test_read_cost_summary_empty_and_missing_log`: Verifies graceful zero-handling when log file does not exist or is 0-byte.
    - `test_read_cost_summary_multiple_entries`: Verifies exact summation of inputs, outputs, entry counts, and calculated USD spend across multiple records.
- **Scope boundaries**:
  - **In scope**: Use `pytest` and `tmp_path` fixtures; test edge cases (missing file, empty file, null rates); assert real arithmetic results.
  - **Out of scope**: Do NOT write to real production `TriAPI/rebuild/logs/cost_log.jsonl`; do NOT mock arithmetic calculations.

