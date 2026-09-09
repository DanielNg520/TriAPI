# rebuild/ — DeepSeek/agy call scaffold

Task queue and LLM call scaffold with manual audit step before applying.

## Files

- `config/model_config.yaml` — endpoint/model/effort/timeouts, spend limit, and OpenRouter fallback model. Edit here, not in code.
- `queue.sqlite3` — SQLite backing database for task queue.
- `scripts/secrets_loader.py` — reads `../config/secrets.enc.yaml`. Requires `deepseek_api_key`, `ollama_host`, `google_ai_studio_api_key`, `open_router_api_key` (optional: `google_jules_apikey`, `groq_api_key`).
- `scripts/llm_client.py` — `execute_deepseek()`, `execute_openrouter()`, `execute_agy()`.
- `scripts/_root_resource_guard.py` — bridges to TriAPI-root's `scripts/resource_guard.py` (importlib file-path loading, works around a `scripts` package-name collision between this repo and the root repo — see PHASES.md Phase 3). `call_deepseek.py`/`call_agy.py` wrap their outbound call in `pause_services()`/`resume_services()`, config-gated by root `config/resource_guard.yaml` (empty by default — no-op).
- `scripts/openrouter_sanitizer.py` — sanitizes OpenRouter-bound text (content filter blocks email/phone/IP-shaped tokens).
- `scripts/cost.py` — logs DeepSeek tokens and cost to `logs/cost_log.jsonl`.
- `scripts/call_deepseek.py`, `scripts/call_agy.py` — CLI wrappers, print response to stdout. `call_deepseek.py` hard-blocks if cumulative spend exceeds `model_config.yaml`'s `deepseek.spend_limit_usd` ($5.00 default, no bypass flag) and calls OpenRouter during peak hours.
- `scripts/call_planner.py` — CLI interface for invoking the Planner role, structured identically to `call_deepseek.py`/`call_agy.py` with `--prompt-file` and `--system-file` options, outputting generated text to stdout. Backed by `execute_planner()` in `scripts/llm_client.py`, which dispatches requests to OpenRouter according to the configuration defined in `config/model_config.yaml`'s `planner:` section.
- `scripts/task_queue.py` — task queue CLI (`add`, `list`, `approve`, `claim`, `complete`, `tui`).
- `scripts/tui.py` — interactive Textual terminal driver (`App` class + `main()`).
- `scripts/tui_session_log.py` — `new_session_log_path`, `format_log_entry`, `append_session_log` (session logs under `tasks/tui_sessions/`).
- `scripts/tui_framing.py` — `build_framed_prompt` (prefixes prompts with supervisor-role reminder).
- `scripts/tui_dispatch_status.py` — `is_dispatch_running` (warns if a queue task is `in_progress`).
- `scripts/tui_stream.py` — `stream_claude_output` (streams `claude -p` subprocess output line by line).

## Roles

- **DeepSeek**: writes code. One function/task per call, strict prompt, exact scope.
- **OpenRouter**: peak-hours-only fallback for DeepSeek (01:00-04:00 UTC daily, Beijing weekends off-peak) using free model (`nvidia/nemotron-3-ultra-550b-a55b:free`). Not a general peer.
- **agy**: docs + trivial tasks. Prompt must end "reply with complete file content only, no other text" (required for `--mode plan` to not write directly).
- **Claude**: writes every prompt, audits every response before applying. Prompts give signature/skeleton/requirements only — never a finished implementation to paste in, even under time pressure or on a precision-sensitive task (that instinct is itself the failure mode: not trusting the worker is a reason to write a tighter spec, not to write the code yourself). This includes prose: dictating exact variable names, exact control flow ("if X is None, do A and return, else flip Y, persist, call Z with these params"), exact strings/regexes step by step is the same violation as pasting a code block — a test for whether a prompt is actually a spec: could two different competent implementations satisfy it, or does it only admit the one you already wrote? A behavioral requirement ("look up the draft; if missing, tell the user it expired and stop") is fine — a call-by-call transcription is not.
- **Planner**: breaks down bug reports and feature requests into an ordered sequence of concise, dispatchable tasks. Promoted from an initial experiment into a permanent standing role, operational at all times rather than being restricted to DeepSeek's peak-hours schedule. Planner output never routes directly to worker models like DeepSeek or agy; adhering to the hub-and-spoke workflow, Claude must first evaluate and amend every draft (preventing issues from Planner hallucinating nonexistent file paths or function identifiers due to lack of codebase access) before creating actual task queue entries. Connects through the shared OpenRouter free tier, pooling limits (20 RPM / 1000 RPD) alongside the peak-hours fallback worker, so high activity in one role risks throttling the other.

## Usage

### Task Queue

```
python3 scripts/task_queue.py add --description "..." [--worker deepseek|agy] [--depends-on ID]
python3 scripts/task_queue.py list [--status STATUS]
python3 scripts/task_queue.py approve <id>
python3 scripts/task_queue.py claim [id]
python3 scripts/task_queue.py complete --id ID --result RESULT --status done|blocked
python3 scripts/task_queue.py tui
```

### Direct LLM Calls

```
python3 scripts/call_deepseek.py --prompt-file task.md --system-file system.md > out.txt
python3 scripts/call_agy.py --prompt-file task.md --system-file system.md > out.txt
```

Review `out.txt` before applying anything.

## Tests

66/66 real tests pass (`pytest` from the `rebuild/` directory).

