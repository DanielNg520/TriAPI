Break the following into small, independent coding tasks. Same format as before: task id, one-line goal, exact function signature/file, inputs/outputs, explicit out-of-scope notes.

## Efficiency additions (two small features, not a redesign)

### Feature A: Spend cap
Goal: refuse a DeepSeek call before it happens if cumulative logged spend already exceeds a configured USD limit. Uses the existing `scripts/cost.py::read_cost_summary()` (already returns "total_cost_usd"). Add a `spend_limit_usd` field to `rebuild/config/model_config.yaml` under the `deepseek` block (set it to 5.0 as a starting default). Add a function in `scripts/cost.py`:
```python
def check_budget(limit_usd: float, log_path: str | None = None, config_path: str | None = None) -> dict:
```
Returns `{"under_limit": bool, "total_cost_usd": float, "limit_usd": float, "remaining_usd": float}` (remaining can be negative if already over). Pure check, no side effects, no raising.

Then wire it into `scripts/call_deepseek.py`: before calling `llm_client.execute_deepseek`, load `model_config.yaml`, call `check_budget` with `deepseek.spend_limit_usd`. If `under_limit` is False, print an error to stderr (`f"[BLOCKED] Cumulative spend ${total:.4f} exceeds limit ${limit:.2f}"`) and exit with code 1 WITHOUT making the API call. This wiring task is small enough to do directly, not a DeepSeek task — just note it as a task so the plan is complete, mark it "Claude does this directly" as the assignee.

### Feature B: Code-block extractor
Goal: stop hand-rolling `re.search(r'```python\n(.*)\n```', ...)` for every DeepSeek response. Add to `scripts/llm_client.py`:
```python
def extract_code_block(response: str, language: str = "python") -> str:
```
Finds the first fenced code block matching \`\`\`{language} ... \`\`\` (or bare \`\`\` ... \`\`\` if no exact language match is found) and returns its contents (stripped of the fence lines, content itself NOT stripped of leading/trailing whitespace beyond removing the fence lines and their newlines). Raises `ValueError("no fenced code block found")` if none exists.

### Feature C (test suite)
File: `TriAPI/rebuild/tests/test_cost.py` (append) for `check_budget`, and `TriAPI/rebuild/tests/test_llm_client.py` (new) for `extract_code_block`. List these as tasks too.

Reply with the task list only, no other text.
