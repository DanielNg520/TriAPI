# Rebuild phases

From `../SALVAGE_PLAN.md`'s sequence. One phase at a time, each usable on its own.

1. **Ground-truth verify layer** — real test pass/fail, real file-diff/state checks. No substring grep, no py_compile-only. Root fix for the old pipeline's core bug.
2. **Minimal single-task dispatcher** — apply one task's change, call phase-1 verify, report true result. No tiers, no escalation, no self-fix.
3. **Reattach kept infra** — cost tracking, config/secrets plumbing, resource_guard, wired into phase-2 dispatcher.
4. **Reattach tier escalation ladder** — tier1-4 files, re-audited one at a time, now backed by phase-1 verify.
5. **Deferred** — self-fix loop, RAG/memory, doc-management. Not started until 1-4 run clean for a while. Each is a deliberate later decision, not automatic carry-forward.

Status: Phase 1 done (`scripts/verify.py`). Phase 2 done (`scripts/dispatch.py` — apply_change/restore_file/dispatch_task, atomic apply + auto-rollback on failed verification). Phase 3 partial: cost tracking done (`scripts/cost.py`, wired into `call_deepseek.py` — every DeepSeek call now logs tokens+cost to `logs/cost_log.jsonl`); config/secrets plumbing and resource_guard reattachment deferred to Phase 4, where they're actually needed (tier ladder work will use them). 22/22 real tests passing (`tests/test_verify.py` + `tests/test_dispatch.py` + `tests/test_cost.py`). Phase 4 next.
