# TriAPI

LLM dispatch pipeline (DeepSeek + agy workers, Claude supervision).
Runs on Ubuntu, Fedora, and macOS — no OS-specific setup required.

See [AGENTS.md](AGENTS.md) — the only maintained doc, covers architecture,
active work, and doc policy. The live pipeline lives in `rebuild/` (see
`rebuild/README.md`) — call targets are DeepSeek, a narrow OpenRouter
peak-hours fallback, and the local `agy` CLI. There is no local-model call
target today.

## Hooking up your own local model

`rebuild/scripts/llm_client.py` has three call functions:
`execute_deepseek()`, `execute_openrouter()`, `execute_agy()` — all defined
in `rebuild/config/model_config.yaml`, nothing hardcoded. Adding your own
local model (Ollama, LM Studio, llama.cpp's `server`, vLLM, or anything
else that speaks the OpenAI-compatible `/v1/chat/completions` API) means
adding a fourth: an `execute_local()` following `execute_openrouter()`'s
exact shape — same request/response handling, pointed at your own
`endpoint`/`model` in `model_config.yaml` instead of OpenRouter's. No API
key is required for a local server with no auth (skip the `api_key`
parameter, or pass an empty string).

This is an extension point, not a built-in feature — nothing in `rebuild/`
calls a local model today, so wire it into `call_deepseek.py`/`call_agy.py`
(or add a `call_local.py` alongside them) the same way those two scripts
already call their targets.
