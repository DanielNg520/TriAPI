# Rebuild phases

From `../SALVAGE_PLAN.md`'s sequence. One phase at a time, each usable on its own.

1. **Ground-truth verify layer** — real test pass/fail, real file-diff/state checks. No substring grep, no py_compile-only. Root fix for the old pipeline's core bug.
2. **Minimal single-task dispatcher** — apply one task's change, call phase-1 verify, report true result. No tiers, no escalation, no self-fix.
3. **Reattach kept infra** — cost tracking, config/secrets plumbing, resource_guard, wired into phase-2 dispatcher.
4. **Reattach tier escalation ladder** — REJECTED (user decision, 2026-09-08, superseding the 2026-09-05 "deferred" note): not being built, ever, in this form. Automatic threshold-based worker escalation (fail N times, then swap workers) is the waterfall failure mode the salvage was for — it burns tokens/calls/money retrying before a human-equivalent ever looks at *why* it failed. Hub-and-spoke's actual answer: every DeepSeek/agy failure routes to Claude immediately, who diagnoses the real cause and dispatches a targeted fix on the first retry, not after a threshold. Steady state (Phases 1-3, manual DeepSeek+agy+Claude) is the design, not a placeholder waiting for this.
5. **Deferred** — self-fix loop, RAG/memory, doc-management. Not started until 1-4 run clean for a while. Each is a deliberate later decision, not automatic carry-forward.

Status: Phase 1 done (`scripts/verify.py`). Phase 2 done (`scripts/dispatch.py` — apply_change/restore_file/dispatch_task, atomic apply + auto-rollback on failed verification). Phase 3 done: cost tracking (`scripts/cost.py`, wired into `call_deepseek.py`); secrets plumbing (`secrets_loader.py`, 6 keys); resource_guard reattached (2026-09-08) into `call_deepseek.py` and `call_agy.py` via `scripts/_root_resource_guard.py`. Phase 4 rejected (2026-09-08, see above) — core (1-3) is the permanent steady state, not an interim one.

`scripts/_root_resource_guard.py` exists because `rebuild/scripts` (has `__init__.py`) and TriAPI-root `scripts` (no `__init__.py`) share the name `scripts` — Python always resolves that name to `rebuild/scripts`, so root's `resource_guard.py` can't be reached as `scripts.resource_guard` by any sys.path ordering. The shim loads root's `tri_logging.py` and `resource_guard.py` by file path via `importlib`, pre-registering `sys.modules["scripts.tri_logging"]` so resource_guard.py's own `from scripts.tri_logging import get_logger` resolves from cache. `pause_services`/`resume_services` wrap the outbound call in both CLI scripts in a try/finally, config-gated by the same `config/resource_guard.yaml` (root, machine-specific, empty by default on a fresh clone — no-op).

Beyond the original 5-phase sequence, built on top of the Phase 1-3 core: a real task queue
CLI (`task_queue.py`), an interactive TUI (`tui.py` + 4 helper modules), and an OpenRouter
peak-hours fallback for DeepSeek (`openrouter_sanitizer.py`) — see AGENTS.md's carryover for
current detail. 66/66 real tests passing (`pytest` from `rebuild/`).
