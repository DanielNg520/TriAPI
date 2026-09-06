### TASK-P3-PEAK-TEST-02: Test for call_deepseek.py hard block

Goal: add a new test file asserting that `main()` refuses (returns 1, no API call attempted) during DeepSeek peak hours. No test file exists for this script today.

New file: TriAPI/rebuild/tests/test_call_deepseek.py

Full current source of the module under test, `TriAPI/rebuild/scripts/call_deepseek.py`:
```python
#!/usr/bin/env python3
"""CLI: send a code-writing task to DeepSeek, print the raw response.

Usage:
    python3 call_deepseek.py --prompt-file task.md --system-file system.md
    echo "..." | python3 call_deepseek.py --system-file system.md

Intended caller: a human/agent supervisor who writes a strict, detailed
prompt per function/section/task, reviews this script's stdout before
applying anything -- this script never touches the target repo itself.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import cost, llm_client, secrets_loader


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prompt-file", type=Path, help="Task prompt file; reads stdin if omitted")
    ap.add_argument(
        "--system-file",
        type=Path,
        required=True,
        help="System prompt file (the strict instructions/constraints for this task)",
    )
    ap.add_argument("--task-id", default=None, help="Task id for cost log (default: prompt filename or 'stdin')")
    args = ap.parse_args()

    prompt = args.prompt_file.read_text() if args.prompt_file else sys.stdin.read()
    system_prompt = llm_client.load_rules() + "\n\n" + args.system_file.read_text()

    if llm_client.is_deepseek_peak_hours():
        print("[BLOCKED] DeepSeek peak billing window active -- costs elevated, refusing call", file=sys.stderr)
        return 1

    limit = llm_client.load_model_config()["deepseek"]["spend_limit_usd"]
    budget = cost.check_budget(limit)
    if not budget["under_limit"]:
        print(
            f"[BLOCKED] Cumulative spend ${budget['total_cost_usd']:.4f} exceeds limit ${limit:.2f}",
            file=sys.stderr,
        )
        return 1

    secrets = secrets_loader.load_secrets()
    response, in_tok, out_tok = llm_client.execute_deepseek(
        prompt, system_prompt, secrets["deepseek_api_key"]
    )
    print(response)
    task_id = args.task_id or (args.prompt_file.stem if args.prompt_file else "stdin")
    cost.log_cost(task_id, in_tok, out_tok)
    print(f"[tokens] in={in_tok} out={out_tok} cost_usd={cost.calculate_cost(in_tok, out_tok):.6f}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Reference — existing test file's mocking style, `TriAPI/rebuild/tests/test_dispatch.py` (for convention only, do not copy its content):
```python
from unittest.mock import patch
...
with patch("scripts.dispatch.verify_task") as mock_verify:
    mock_verify.return_value = {"passed": True, "summary": "ok", "evidence": {}}
    result = dispatch_task(path, new_content="new\n")
```

Required test: `test_main_returns_1_and_skips_call_during_peak_hours`
- Patch `scripts.call_deepseek.llm_client.is_deepseek_peak_hours` to return `True`.
- Patch `sys.argv` (via `monkeypatch.setattr("sys.argv", [...])`) to `["call_deepseek.py", "--system-file", str(tmp_path / "system.md")]`; create that file with `tmp_path.write_text` (via a `tmp_path` fixture) containing placeholder text, since argparse requires it to exist as a path but `main()` should return before reading it in this code path... note `system_prompt` IS built before the peak-hours check, so the system file must actually exist and be readable, and stdin must not block: also patch `sys.stdin` (e.g. `monkeypatch.setattr("sys.stdin", io.StringIO(""))`) so `prompt = ... sys.stdin.read()` doesn't hang, since no `--prompt-file` is given.
- Also patch `scripts.call_deepseek.cost.check_budget` and `scripts.call_deepseek.secrets_loader.load_secrets` to raise `AssertionError("should not be called")` if invoked, proving the function returned before reaching them.
- Call `call_deepseek.main()` directly (import `from scripts import call_deepseek`) and assert it returns `1`.

Needed imports: `io`, `from pathlib import Path` (via `tmp_path` fixture, no direct import needed), `from unittest.mock import patch`, `from scripts import call_deepseek`. Use `pytest`'s built-in `tmp_path` and `monkeypatch` fixtures as test function parameters.

Scope: only this one test function in this one new file.
