# Carryover — 2026-09-04 — RAG/Memory Design Doc Dispatched, Awaiting User Review

**Status: RESOLVED for dispatch, AWAITING USER REVIEW.** The design doc itself is now awaiting user review before any implementation phase gets planned — do not start Phase 2+ without the user's explicit go-ahead.

## What this session covered

### RAG/Memory design plan dispatched (run `20260903-104712-c4164e`, commit `bc67318`)

Run `20260903-104712-c4164e` was dispatched successfully this session (commit `bc67318`), producing `docs/design_rag_layer.md`. The design document covers:
1. **Exactly-once retrieval**: Context is fetched once at task breakdown / dispatch preparation time alongside `build_context_blob()`, threaded through `orchestrator.run_task` and downstream escalation tiers rather than re-queried at every tier attempt, preventing prompt-token spend multiplication across the fallback chain.
2. **Local Ollama embeddings with graceful keyword-fallback**: Vector embeddings generated locally via existing Ollama models (`nomic-embed-text` or lightweight local equivalents) with mandatory graceful fallback to `scripts/hivemind_util.py` and `scripts/lessons.py` keyword matching if Ollama is unreachable, with zero external paid embedding API dependencies.
3. **Strict context ceilings**: Enforces a top-K=3 limit and a hard context cap of 4,096 characters on total injected memory.
4. **Dual on-disk schemas with query-time unified in-memory index**: Preserves `knowledge/hivemind.md` and `knowledge/lessons.jsonl` as separate files on disk (distinct schemas/lifecycles) while unifying them into a single in-memory index at query time for a single ranking pass and global character-budget enforcement.

### Jules advisory investigation

The Jules advisory run flagged 5 test errors, but investigation confirmed these are caused by a `sops`-secret-decryption environment gap within Jules's own cloud sandbox (which lacks the local `age` secret key). This was confirmed NOT to be a real regression by successfully decrypting `config/secrets.enc.yaml` locally on this machine.

## Open / Carried-Forward Items

### Hardening item from prior carryover (`scripts/dispatcher.py`)

Carry forward one still-open non-urgent hardening item from the prior carryover file:
- `scripts/dispatcher.py`'s relocation-guard hard-fail check (around line 1449, from commit `637d0d1`) runs **unconditionally**, unlike its sibling `scope_concerns` and `mock_patch_lint` checks which are gated behind `is_regular_item and result["status"] == "success"`.
- It is worth gating this check the same way next time `scripts/dispatcher.py` is touched, to avoid false positives on `verify_only`/`git`-type items and prevent masking underlying failure reasons.

## Next Steps

- **Awaiting User Review**: `docs/design_rag_layer.md` is complete and awaits explicit user review. Do not start Phase 2+ or any implementation planning without the user's explicit go-ahead.

## Queued bug -- edit-block-marker-leak variant, hand-fixed live

During run 20260903-220300-6f7574 phase 3 item 2 (scripts/orchestrator.py memory_rag wiring), Tier 4's raw model output contained a bare 4-character '====' divider line (not the standard 7-character '<​<<<<<< SEARCH'/='​======'/'>​

## Session paused for DeepSeek peak hours (2026-09-04, ~06:01 UTC)

Implementation dispatch run 20260903-220300-6f7574 (the RAG/memory layer's Phase 1-4 implementation, following the approved docs/design_rag_layer.md) is IN PROGRESS, stopped at Phase 4 item 4 of 9 ('Dispatch Wiring and Config' -- removing tier4_worker.py's own independent hivemind_util/lessons calls). Items 1-8 succeeded (scripts/embedding_client.py, tests/test_embedding_client.py, scripts/rag_index.py, tests/test_rag_index.py, scripts/memory_retrieval.py, tests/test_memory_retrieval.py, the new memory_rag config block in config/tiers.yaml + config_loader.py exposure, and orchestrator.py's exactly-once retrieval wiring) -- all uncommitted, sitting in the working tree (git status shows modified: AGENTS.md, CARRYOVER.md, config/tiers.yaml, this carryover file, knowledge/TECH_DEBT.md, knowledge/hivemind.md, scripts/config_loader.py, scripts/orchestrator.py, scripts/tier4_worker.py; new untracked: scripts/embedding_client.py, scripts/memory_retrieval.py, scripts/rag_index.py, tests/test_embedding_client.py, tests/test_memory_retrieval.py, tests/test_rag_index.py). Item 4 (scripts/tier4_worker.py) is a REAL regression, not an infra bug: removing the hivemind_util/lessons import (correct per the design -- tier4_worker should no longer do its own independent retrieval now that orchestrator retrieves once upstream) breaks 3 existing tests in tests/test_file_size_ceiling_and_oversize_escalation.py that mock.patch('scripts.tier4_worker.hivemind_util...')/'lessons...' by name -- AttributeError: module has no attribute 'hivemind_util', since the import removal also removes that attribute binding. This item has now failed twice (tier_4 then tier_3, both build_failed on the same regression) out of the tier4_to_tier3 threshold of 2, so resuming should escalate further (tier_2) on the next attempt. To resume in the new session: run 'triapi dispatch 20260903-220300-6f7574' -- state is file-backed (logs/state/, logs/runs/) so it re-enters exactly where it stopped. If escalation keeps failing on this same regression, the actual fix is straightforward: update tests/test_file_size_ceiling_and_oversize_escalation.py's mocks to patch the NEW call sites instead (memory_retrieval.retrieve_context in orchestrator.py, not tier4_worker.hivemind_util/lessons directly) since tier4_worker legitimately no longer imports those modules by design. ALSO CARRY FORWARD, still unresolved: (1) the edit-block-marker-leak hardening item logged in the prior session-continuation note in this same file (scripts/content_guard.py/scripts/edit_blocks.py only check for the 7-char '<​<<<<<< SEARCH'/='​======'/'>​
