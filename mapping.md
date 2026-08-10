# Project Mapping

Living index of every file/dir in this repo. Read this before exploring — updated at the end of every phase.

## Root
- `PLAN.md` — phase-by-phase implementation plan with checklists and end-of-phase tests. Progress tracker.
- `mapping.md` — this file.
- `ARCHITECTURE.md` — system design: the 4-tier escalation state machine, DeepSeek cache-hit economics, budget guard rationale, and what changed during the build (Tier 2 redesign, MCP server dropped, Jules deferred).
- `README.md` — setup (Python deps, sops/age, Ollama systemd service, Claude Code subscription login) and usage (standalone task, smoke test, cost report).
- `.sops.yaml` — sops encryption rule: files matching `config/secrets.enc.yaml` are encrypted to the age recipient in `~/.config/sops/age/keys.txt`.
- `.gitignore` — excludes runtime logs/state, plaintext secrets, Python caches, venvs.
- `requirements.txt` — Python deps: `requests`, `PyYAML`, `mcp`.
- `LICENSE` — Apache-2.0.

## config/
- `tiers.yaml` — tier definitions: models, endpoints, roles, pricing (DeepSeek pricing needs periodic reverification, see `last_verified`), escalation thresholds.
- `secrets.example.yaml` — plaintext template documenting required secret keys (`deepseek_api_key`, `ollama_host`, `google_ai_studio_api_key`), no real values, safe to commit.
- `secrets.enc.yaml` — sops/age-encrypted real secrets. Safe to commit (ciphertext). Edit with `sops config/secrets.enc.yaml`.

## scripts/
- `secrets_loader.py` — `load_secrets()` shells out to `sops -d` to decrypt `config/secrets.enc.yaml` into a dict at runtime. Never logs values.
- `config_loader.py` — `load_tiers()` loads and validates `config/tiers.yaml`, raises `ValueError` if required top-level keys are missing.
- `state.py` — per-task escalation state (`logs/state/<task_id>.json`): `read_state`, `write_state`, `record_failure`, `clear_state`.
- `tier4_worker.py` — local Ollama drafting + build-loop worker, exposes callable `run(...)` (used directly by `orchestrator.py`) and a CLI `main()`; tracks consecutive build failures via `state.py`, escalates once `escalation_rules.tier4_to_tier3.threshold` is hit. Also owns `extract_code()` (fenced-code extraction) and `run_build()`, reused by every other tier.
- `tier3_escalate.py` — DeepSeek escalation client: stable system-message prefix (instructions + file contents) + volatile stderr user message for prefix-cache hits; applies the returned fix; logs cache-hit/miss/output tokens + cost (partial where pricing is unverified) to `logs/cost_log.jsonl`.
- `tier1_escalate.py` — Claude Code CLI escalation client: shells out to `claude -p` with `--tools ""` (no tool access needed) and a minimal `--system-prompt` override (avoids ~60K tokens/call of default CLAUDE.md auto-discovery overhead — do NOT use `--bare`, it forces API-key auth and defeats the budget guard). Must only be called after `budget_guard.check_tier1_ok()`. Logs `cost_usd: 0.0` (actual, subscription-covered) alongside `notional_cost_usd` (what it would've cost on metered billing).
- `tier2_escalate.py` — Gemini escalation client via Google AI Studio REST API (`google_ai_studio_api_key`), mirrors `tier3_escalate.py`'s structure. Must only be called after `budget_guard.check_tier2_ok()`; calls `budget_guard.record_gemini_call()` after every attempt.
- `budget_guard.py` — pre-flight checks before Tier 1/Tier 2 calls: `check_tier1_ok()` refuses if `ANTHROPIC_API_KEY` is set (would force metered billing over subscription); `check_tier2_ok()` refuses if the next call would exceed `tiers.yaml`'s `tier_2_manager.pricing.free_tier_rpm/rpd` (tracked in `logs/gemini_usage.jsonl`, currently unverified placeholder limits).
- `cost_report.py` — `report(task_id)` aggregates `logs/cost_log.jsonl` per task; `format_report()` prints actual $ spent vs. notional/subscription-covered cost, per tier.
- `orchestrator.py` — `run_task(...)` ties Tier 4 (draft+build loop) → Tier 3 (patch + plain rebuild) → Tier 1 (budget-guarded, patch + rebuild) → Tier 2 (budget-guarded, patch + rebuild) → human handoff. Prints a cost report at the end of every run. Downstream tiers only patch the file and rebuild — they never trigger another Ollama draft, which would overwrite their fix.
- (no `mcp_server.py` — Phase 5 was skipped; Antigravity is no longer a dispatcher in this design, and `orchestrator.py` is already a complete standalone entry point. A future MCP-style integration, if any, points toward Jules, not Antigravity.)

## logs/
- `state/` — per-task JSON state files (gitignored contents, dir kept via `.gitkeep`).
- `cost_log.jsonl` — per-call cost/usage log across all paid/metered tiers, one JSON line per call (gitignored).
- `gemini_usage.jsonl` — Tier 2 call timestamps, used by `budget_guard.check_tier2_ok()` to enforce free-tier RPM/RPD limits (gitignored).
- `escalations.jsonl`, `escalation_<task_id>.md` — final human-handoff records, written only when Tier 4→3→1→2 all fail to resolve a task (gitignored).

## samples/
- `broken_build/` — fixture C++ project: `main.cpp` has a genuine compile error (copying a `std::vector<std::unique_ptr<Widget>>`, illegal since `unique_ptr` isn't copyable) plus `CMakeLists.txt`. Used for end-to-end pipeline verification (Phase 6) — a full production-config `orchestrator.py` run resolved it correctly at Tier 4 alone, $0 cost. `build/` (CMake output) is gitignored, regenerated by running the smoke test in `README.md`.
