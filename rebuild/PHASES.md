# Rebuild phases

From `../SALVAGE_PLAN.md`'s sequence. One phase at a time, each usable on its own.

1. **Ground-truth verify layer** — real test pass/fail, real file-diff/state checks. No substring grep, no py_compile-only. Root fix for the old pipeline's core bug.
2. **Minimal single-task dispatcher** — apply one task's change, call phase-1 verify, report true result. No tiers, no escalation, no self-fix.
3. **Reattach kept infra** — cost tracking, config/secrets plumbing, resource_guard, wired into phase-2 dispatcher.
4. **Reattach tier escalation ladder** — REJECTED (user decision, 2026-09-08, superseding the 2026-09-05 "deferred" note): not being built, ever, in this form. Automatic threshold-based worker escalation (fail N times, then swap workers) is the waterfall failure mode the salvage was for — it burns tokens/calls/money retrying before a human-equivalent ever looks at *why* it failed. Hub-and-spoke's actual answer: every DeepSeek/agy failure routes to Claude immediately, who diagnoses the real cause and dispatches a targeted fix on the first retry, not after a threshold. Steady state (Phases 1-3, manual DeepSeek+agy+Claude) is the design, not a placeholder waiting for this.
5. **Deferred** — self-fix loop, RAG/memory, doc-management. Not started until 1-4 run clean for a while. Each is a deliberate later decision, not automatic carry-forward.

Status: Phase 1 done (`scripts/verify.py`). Phase 2 done (`scripts/dispatch.py` — apply_change/restore_file/dispatch_task, atomic apply + auto-rollback on failed verification). Phase 3 done: cost tracking (`scripts/cost.py`, wired into `call_deepseek.py`); secrets plumbing (`secrets_loader.py`, 6 keys); resource_guard was reattached 2026-09-08, then removed from the call scripts 2026-10-01 (remote clients have nothing local to protect; stopping user services around every call tripped systemd start limits; the guard stays in root `triapi.py` for local runs, and `tests/test_call_scripts_no_service_guard.py` pins its absence). Phase 4 rejected (2026-09-08, see above) — core (1-3) is the permanent steady state, not an interim one.


Beyond the original 5-phase sequence, built on top of the Phase 1-3 core: a real task queue
CLI (`task_queue.py`), an interactive TUI (`tui.py` + 4 helper modules), and an OpenRouter
peak-hours fallback for DeepSeek (`openrouter_sanitizer.py`) — see AGENTS.md's carryover for
current detail. 66/66 real tests passing (`pytest` from `rebuild/`).
