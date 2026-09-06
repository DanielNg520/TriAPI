### TASK-P3-PEAK-02: Hard-block DeepSeek calls during peak hours

Goal: `call_deepseek.py`'s `main()` currently only prints a `[WARN]` when `llm_client.is_deepseek_peak_hours()` is true, then proceeds with the call anyway. Change this to a hard refusal, matching the existing spend-limit block just below it in the same function.

File: TriAPI/rebuild/scripts/call_deepseek.py

Current relevant lines inside `main()`:
```python
    if llm_client.is_deepseek_peak_hours():
        print("[WARN] DeepSeek peak billing window (01:00-04:00 UTC) -- costs elevated", file=sys.stderr)

    limit = llm_client.load_model_config()["deepseek"]["spend_limit_usd"]
    budget = cost.check_budget(limit)
    if not budget["under_limit"]:
        print(
            f"[BLOCKED] Cumulative spend ${budget['total_cost_usd']:.4f} exceeds limit ${limit:.2f}",
            file=sys.stderr,
        )
        return 1
```

Required change: replace the `[WARN]` block with a hard block that prints `[BLOCKED] DeepSeek peak billing window active -- costs elevated, refusing call` to stderr and returns 1 immediately (same pattern as the spend-limit block that follows it), instead of printing and continuing.

Scope:
- In scope: only this `if llm_client.is_deepseek_peak_hours():` block inside `main()`.
- Out of scope: do not touch the spend-limit block, the docstring's usage lines, argument parsing, or any other function. Do not add a bypass flag or env var — this must be an unconditional hard stop, no bypass, per RULES.md ("never bypass a spend cap or verification step").

Reply with the full corrected body of `main()` from its `def main() -> int:` line through its final `return 0`, as a single Python code block.
