import json

def main():
    run_id = "20260821-114229-5e1f9c"
    path = f"logs/runs/{run_id}.json"
    with open(path) as f:
        state = json.load(f)
    
    plan_text = """
1. **Phase 1 -- CLI and Config**
- Modify `config/tiers.yaml`: Add a `single_api_mode:` block with `max_retries: 3` and `allowed_backends: ["gemini", "claude", "deepseek"]`. (Build check: `cat config/tiers.yaml | grep single_api_mode`)
- Modify `scripts/triapi.py`: Add `--single-api` to `dispatch` parser and pass it to `cmd_dispatch`. (Build check: `python3 -m py_compile scripts/triapi.py && grep single_api scripts/triapi.py`)
- Modify `scripts/dispatcher.py`: Update state JSON schema to store `single_api_mode`, and pass it to `orchestrator.run_task` inside `dispatch()`. (Build check: `python3 -m py_compile scripts/dispatcher.py && grep single_api scripts/dispatcher.py`)

2. **Phase 2 -- Orchestrator Hook**
- Modify `scripts/orchestrator.py`: Add `single_api_mode` to `run_task` signature. If enabled, import `single_api_worker` and delegate to `single_api_worker.run(task_id, description, target, workdir, build_cmd, context_blob, config, single_api_mode)`, returning its result directly, bypassing Tiers 4-1. (Build check: `python3 -m py_compile scripts/orchestrator.py && grep single_api_worker scripts/orchestrator.py`)

3. **Phase 3 -- Single API Worker**
- Create `scripts/single_api_worker.py`: Implement `run(task_id, description, target, workdir, build_cmd, context_blob, config, backend)`. This function should perform a draft-apply-build loop like `tier4_worker.py` but use the given backend (using `gemini_fallback.post_generate_content` for Gemini, or subprocess for Claude, or requests for DeepSeek). Reuse `edit_blocks.apply_edit_blocks` and `content_guard.check_write`. If it hits `max_retries`, log a warning and escalate to `human_handoff` in orchestrator. Return `{"status": "success", "resolved_by": backend}` on success. (Build check: `python3 -m py_compile scripts/single_api_worker.py`)
"""
    state["plan_text"] = plan_text
    state["status"] = "planned"
    state["breakdown"] = {"phases": []}
    
    with open(path, "w") as f:
        json.dump(state, f, indent=2)

if __name__ == "__main__":
    main()
