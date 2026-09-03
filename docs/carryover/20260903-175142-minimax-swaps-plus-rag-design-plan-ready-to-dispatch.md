# Carryover — 2026-09-03 (evening) — Two model swaps to minimax-m3; RAG/memory design plan drafted and approved, ready to dispatch in a new session

**Status: RESOLVED for everything except one explicit next step.** Session ending here at the user's request; picking up dispatch in a new session.

## What this session covered (continuing from 20260903-162623)

After the relocation-guard hard-fail fix and P0 crash recovery (see 20260903-162623), this stretch covered two independent things: config swaps, and a new design plan the user asked to review before dispatching.

### Config: two model swaps to minimax/minimax-m3:free (commits `55d4443`, `e0d183a`)

User asked to replace `dots-3-note-preview:free` with `minimax/minimax-m3:free`. Investigation found `dots-3-note-preview` isn't configured anywhere in `config/tiers.yaml` anymore — it was tier_1_planner's model on 2026-08-28 (moved off the same day for hallucinating fake tool-call syntax), demoted to `tier_3_debugger`'s `peak_alt` secondary, then swapped again by an untracked later commit to `nvidia/nemotron-3.5-lightning:free` without the explanatory comment ever being updated. Confirmed the actual live target with the user, then:
- `tier_3_debugger.peak_alt.models.default`: `nvidia/nemotron-3.5-lightning:free` -> `minimax/minimax-m3:free` (`55d4443`), plus corrected the stale comment.
- `tier_4_worker.models.default` (off-peak primary): same swap (`e0d183a`), user asked for it explicitly after a peak/off-peak mechanics discussion. `tier_4_worker.peak_alt` (local Ollama `qwen2.5-coder:14b`) is unaffected.

Both swaps verified live (`config_loader.load_tiers()`), full suite reconfirmed green (295/295) after each, and confirmed against the real `budget_guard.check_tier3_peak_hours_ok()` output that as of this session tier_3 and tier_4 both key off the exact same shared DeepSeek peak/off-peak clock and are never in different states from each other at the same moment (current state at write time: off-peak, UTC 16:34 Thursday; next peak window 01:00-04:00 UTC).

### RAG/memory design plan drafted and approved, NOT dispatched (run `20260903-104712-c4164e`)

User asked for a memory/RAG layer design for TriAPI's own pipeline (to sit alongside the existing keyword-based `hivemind_util.py`/`lessons.py` retrieval), specifically worried about a multi-tier escalation chain (tier_4->tier_3->tier_2->tier_1->tier_5) multiplying prompt-token spend if retrieval-augmented context gets re-fetched/re-injected at every tier attempt for the same item. Drafted via `triapi plan` with that constraint spelled out explicitly; the planner (Tier 2/Gemini) returned a single design-doc-only phase (deliberately no code phase, per the user's "let me look before we dig in"):

**Phase 1: Memory/RAG Layer Architectural Design** -- create `docs/design_rag_layer.md` covering: (1) exactly-once retrieval, fetched once at breakdown/dispatch time alongside `build_context_blob()` before the first Tier 4 attempt, threaded through `orchestrator.run_task` and every subsequent tier escalation rather than re-queried per tier; (2) local vector embeddings via the existing Ollama service (e.g. `nomic-embed-text`) recommended over keyword-only, with mandatory graceful fallback to `hivemind_util.py`/`lessons.py` if the embedding backend is unavailable -- never a paid external embeddings API; (3) a hard cap on injected context (top-K=3, 4,096-char ceiling) mirroring this repo's file-size-ceiling discipline; (4) `knowledge/hivemind.md` and `knowledge/lessons.jsonl` stay separate files on disk (different schemas) but unify into one in-memory index at query time for a single ranking pass.

Plan is approved (appended to `AGENTS.md`'s plan-gate block) but **deliberately not dispatched** -- user wants to review the design doc's content before any further phase gets planned. Shown to the user in full this session.

**Next up, explicit: resume with `triapi dispatch 20260903-104712-c4164e` in a new session** to produce `docs/design_rag_layer.md`, then bring the drafted doc back to the user for review before scoping any implementation phase. Because this plan is approved-but-undispatched, `AGENTS.md`'s plan-gate currently blocks a *different* new `triapi plan` from being drafted until this one is dispatched (or explicitly `--refactor`'d) -- that's expected and correct, not a bug, since this is the one the user wants picked up next.

## Final verified state

TriAPI: 2 commits this stretch (`55d4443`, `e0d183a`) plus this doc commit, full local suite green (295 tests via `unittest discover`, OK, zero SKIPPED), working tree clean after this commit. No oh-my-llama work this session.
