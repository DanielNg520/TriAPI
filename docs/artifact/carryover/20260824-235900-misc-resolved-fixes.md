# 2026-08-24 23:59 — Misc resolved fixes: KeyError choices, probe retry, Ollama test hang

- **Self-fix `20260824-011749-b8ba34` (the `llm_client.py` `KeyError:
  'choices'` fix) is fully resolved (2026-08-24).** Phases 1-2 (the
  `_call_openai_api()` guard + regression tests) landed via the pipeline;
  Phase 3 (the one-sentence `AGENTS.md` addition) hit `human_handoff` three
  times in a row on real local Ollama inference timing out (300s+ per
  attempt across all 3 escalation legs) — applied by hand instead, since
  the underlying code fix was already done/tested and this was a trivial,
  fully-specified one-line doc edit. `AGENTS.md` confirmed at 73,380 chars
  (still under the 73,728 ceiling, but tight — worth trimming further
  before the next addition). Full suite green (83 tests).
- **`llm_client.probe_models()` gained retry tolerance, 2026-08-24.** It
  had zero tolerance for a single transient blip on *any* tier — one
  OpenRouter 429 or a free model's temporary 502 aborted the entire
  pre-flight gate and thus the whole dispatch, even for tiers the run
  doesn't use. `_probe_with_retry()` now retries 3x, 5s apart, before
  failing the gate; still fails hard on a genuinely broken/misconfigured
  tier.
- **Found, not fixed: `tests.test_ollama_service_lifecycle.
  CmdDispatchOllamaLifecycleTests.test_cmd_dispatch_restores_ollama_state_
  on_exception` hangs on a real unmocked network call** (confirmed live
  2026-08-24 — it doesn't fail fast, it blocks for minutes). Pre-existing,
  unrelated to tonight's Tier 5 work (an earlier Jules advisory pass had
  already flagged this test module's mocking as incomplete). Needs a
  proper mock at the HTTP boundary, not just a shorter timeout. Run
  `tests.test_branch_features`/`tests.test_tier5_librarian` directly
  instead of bare `unittest discover tests` until this is fixed. **Status
  as of 2026-08-25: not yet confirmed fixed — check
  `tests/test_ollama_service_lifecycle.py` directly if this test module
  is ever touched again before assuming it's still broken.**
- **Correction (2026-08-28):** `test_cmd_dispatch_restores_ollama_state_on_exception`
  is now confirmed passing with full mocking in place.
