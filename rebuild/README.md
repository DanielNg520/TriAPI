# rebuild/ — DeepSeek/agy call scaffold

No dispatcher, no verify loop, no auto-apply. Manual, one task at a time.

## Files

- `config/model_config.yaml` — endpoint/model/effort/timeouts. Edit here, not in code.
- `scripts/secrets_loader.py` — reads `../config/secrets.enc.yaml`, needs `deepseek_api_key` only.
- `scripts/llm_client.py` — `execute_deepseek()`, `execute_agy()`.
- `scripts/call_deepseek.py`, `scripts/call_agy.py` — CLI wrappers, print response to stdout only.

## Roles

- **DeepSeek**: writes code. One function/task per call, strict prompt, exact scope.
- **agy**: docs + trivial tasks. Prompt must end "reply with complete file content only, no other text" (required for `--mode plan` to not write directly).
- **Claude**: writes every prompt, audits every response before applying.

## Usage

```
python3 scripts/call_deepseek.py --prompt-file task.md --system-file system.md > out.txt
python3 scripts/call_agy.py --prompt-file task.md --system-file system.md > out.txt
```

Review `out.txt` before applying anything.
