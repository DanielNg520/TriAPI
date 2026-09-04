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
