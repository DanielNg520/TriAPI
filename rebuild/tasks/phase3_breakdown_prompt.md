Break the following phase into small, independent coding tasks. Same format as before: task id, one-line goal, exact function signature/file, inputs/outputs, explicit out-of-scope notes.

## Phase 3: Cost tracking for the rebuild dispatcher

Goal: a small module (target: `TriAPI/rebuild/scripts/cost.py`) that logs every DeepSeek call's token usage to a local JSONL file and reports total spend, using the real DeepSeek pricing already verified in `TriAPI/config/tiers.yaml`'s `deepseek_reference_pricing` block (cache_miss_per_mtok_usd: 0.14, cache_hit_per_mtok_usd: 0.0028, output_per_mtok_usd: null -> falls back to cache_miss rate). Do not hardcode these numbers as a fallback default — read them from that file so a future price update only requires editing the yaml. No new pricing logic beyond what's needed to reuse that block.

Required capabilities:
1. Append one entry (task_id: str, input_tokens: int, output_tokens: int, timestamp: an ISO8601 UTC string generated at call time) to `TriAPI/rebuild/logs/cost_log.jsonl` (create the file/parent dir if missing), one JSON object per line.
2. Compute the USD cost of a given (input_tokens, output_tokens) pair using TriAPI/config/tiers.yaml's deepseek_reference_pricing block (load via yaml, path: repo root two levels up from rebuild/scripts/ -> "config/tiers.yaml", i.e. TriAPI/config/tiers.yaml not TriAPI/rebuild/config/).
3. Read all entries from the JSONL log and return total input tokens, total output tokens, total USD cost, and entry count.

Reply with the task list only, no other text.
