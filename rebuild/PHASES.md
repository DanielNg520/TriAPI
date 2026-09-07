# Rebuild phases

From `../SALVAGE_PLAN.md`'s sequence. One phase at a time, each usable on its own.

1. **Ground-truth verify layer** — real test pass/fail, real file-diff/state checks. No substring grep, no py_compile-only. Root fix for the old pipeline's core bug.
2. **Minimal single-task dispatcher** — apply one task's change, call phase-1 verify, report true result. No tiers, no escalation, no self-fix.
3. **Reattach kept infra** — cost tracking, config/secrets plumbing, resource_guard, wired into phase-2 dispatcher.
4. **Reattach tier escalation ladder** — DEFERRED (user decision, 2026-09-05): keep using the manual DeepSeek+agy two-role split (Phases 1-3) for now, no automatic escalation/fallback ladder until the core has run longer.
5. **Deferred** — self-fix loop, RAG/memory, doc-management. Not started until 1-4 run clean for a while. Each is a deliberate later decision, not automatic carry-forward.

Status: Phase 1 done (`scripts/verify.py`). Phase 2 done (`scripts/dispatch.py` — apply_change/restore_file/dispatch_task, atomic apply + auto-rollback on failed verification). Phase 3 partial: cost tracking done (`scripts/cost.py`, wired into `call_deepseek.py`); secrets plumbing done (`secrets_loader.py`, 6 keys); resource_guard reattachment still on hold, not needed until tier ladder work starts. Phase 4 deferred — core (1-3) is the current steady state.

Beyond the original 5-phase sequence, built on top of the Phase 1-3 core: a real task queue
CLI (`task_queue.py`), an interactive TUI (`tui.py` + 4 helper modules), and an OpenRouter
peak-hours fallback for DeepSeek (`openrouter_sanitizer.py`) — see AGENTS.md's carryover for
current detail. 66/66 real tests passing (`pytest` from `rebuild/`).
