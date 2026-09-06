### TASK-P3-PEAK-TEST-01: Tests for is_deepseek_peak_hours

Goal: add pytest tests for the weekend-bypass and hour-window logic in `is_deepseek_peak_hours`. No test exists for this function today.

File to add tests to: TriAPI/rebuild/tests/test_llm_client.py
Function under test (full current source, `rebuild/scripts/llm_client.py`):
```python
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

_BEIJING_TZ = ZoneInfo("Asia/Shanghai")

def is_deepseek_peak_hours(cfg: dict | None = None) -> bool:
    """DeepSeek peak billing window (UTC), configurable in model_config.yaml; Beijing weekends are off-peak."""
    cfg = cfg or load_model_config()
    now = datetime.now(timezone.utc)
    if now.astimezone(_BEIJING_TZ).weekday() >= 5:
        return False
    start, end = cfg["deepseek"]["peak_hours_utc"]
    return start <= now.hour < end
```

Existing test file's current full content (append new tests after this, do not modify existing tests):
```python
from scripts.llm_client import extract_code_block
import pytest


def test_extract_code_block_exact_language():
    response = "some text\n```python\ndef f():\n    return 1\n```\nmore text"
    assert extract_code_block(response) == "def f():\n    return 1"


def test_extract_code_block_bare_fallback():
    response = "text\n```\nkey: value\n```\n"
    assert extract_code_block(response, language="yaml") == "key: value"


def test_extract_code_block_preserves_content_whitespace():
    response = "```python\n    a = 1\n\n    b = 2   \n```"
    expected = "    a = 1\n\n    b = 2   "
    assert extract_code_block(response) == expected


def test_extract_code_block_first_block_priority():
    response = "```python\nfirst = 1\n```\n```python\nsecond = 2\n```"
    assert extract_code_block(response) == "first = 1"


def test_extract_code_block_custom_language():
    response = "text\n```yaml\nkey: value\n```\n"
    assert extract_code_block(response, language="yaml") == "key: value"


def test_extract_code_block_missing_raises_value_error():
    with pytest.raises(ValueError):
        extract_code_block("no code blocks here at all")
```

Required new tests (add `is_deepseek_peak_hours` to the existing `from scripts.llm_client import ...` line, and add `from datetime import datetime, timezone` and `from unittest.mock import patch` imports):

1. `test_is_deepseek_peak_hours_true_inside_window_on_weekday` — patch `scripts.llm_client.datetime` so `datetime.now(timezone.utc)` returns a fixed weekday (e.g. `datetime(2026, 9, 8, 2, 0, tzinfo=timezone.utc)` — 2026-09-08 is a Tuesday) whose hour (2) falls inside a `cfg = {"deepseek": {"peak_hours_utc": [1, 4]}}` window. Assert `is_deepseek_peak_hours(cfg) is True`.
2. `test_is_deepseek_peak_hours_false_outside_window_on_weekday` — same weekday, hour 12 (outside `[1, 4]`). Assert `is_deepseek_peak_hours(cfg) is False`.
3. `test_is_deepseek_peak_hours_false_on_beijing_weekend` — pick a UTC datetime whose Beijing-timezone equivalent falls on a Saturday or Sunday AND whose UTC hour would otherwise be inside the peak window (e.g. `datetime(2026, 9, 12, 2, 0, tzinfo=timezone.utc)` — UTC Saturday 02:00 is Beijing Saturday 10:00). Assert `is_deepseek_peak_hours(cfg) is False` even though the hour is inside `[1, 4]`.

Mocking approach: `with patch("scripts.llm_client.datetime") as mock_dt: mock_dt.now.return_value = <fixed datetime>` — the fixed datetime object's own `.astimezone(...)` method works normally since it's a real `datetime` instance, only the module-level `datetime` class's `.now` is mocked.

Scope: only these three new test functions plus the necessary import-line edits. Do not modify or remove any existing test.
