### TASK-P3-PEAK-01: DeepSeek peak-hours weekend bypass

Goal: `is_deepseek_peak_hours()` currently returns True purely from UTC hour-of-day, even on weekends when DeepSeek does not apply peak pricing. Add the weekend bypass.

File: TriAPI/rebuild/scripts/llm_client.py
Signature (unchanged, edit the body only):
```python
def is_deepseek_peak_hours(cfg: dict | None = None) -> bool:
```

Current body:
```python
def is_deepseek_peak_hours(cfg: dict | None = None) -> bool:
    """DeepSeek peak billing window (UTC), configurable in model_config.yaml."""
    cfg = cfg or load_model_config()
    start, end = cfg["deepseek"]["peak_hours_utc"]
    hour = datetime.now(timezone.utc).hour
    return start <= hour < end
```

Required change: before checking the hour window, check the current day in the `Asia/Shanghai` timezone (DeepSeek is a Beijing-based provider; peak pricing does not apply on Beijing weekends). If it is Saturday or Sunday in `Asia/Shanghai`, return False immediately without checking the hour window.

Needed imports: add `from zoneinfo import ZoneInfo` at the top of the file (module already imports `datetime, timezone` from `datetime`). Define `_BEIJING_TZ = ZoneInfo("Asia/Shanghai")` as a module-level constant next to the existing `_CONFIG_PATH`/`_RULES_PATH` constants.

Scope:
- In scope: the weekend bypass and its constant only.
- Out of scope: do not touch `execute_deepseek`, `load_model_config`, `load_rules`, `extract_code_block`, or any other function in the file. Do not change the function signature or docstring wording beyond noting the weekend bypass in one line.
