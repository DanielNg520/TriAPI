# Carryover — 2026-09-04 — RAG/Memory Layer Implementation Complete

**Status: RESOLVED.** Run `20260903-220300-6f7574` (RAG/memory layer Phases 1-4, implementing the approved `docs/design_rag_layer.md`) is fully complete -- all 15/15 checklist items succeeded, run status `completed`. Full suite: 346 passed, 13 subtests passed. Working tree clean.

## What shipped

- `scripts/embedding_client.py` + tests: local Ollama embedding client (`nomic-embed-text:latest`), strict 5s timeout, typed None on any failure.
- `scripts/rag_index.py` + tests: unified in-memory index over `knowledge/hivemind.md` + `knowledge/lessons.jsonl`, embeddings computed once per run, `has_embeddings` fallback flag.
- `scripts/memory_retrieval.py` + tests: `retrieve_context()` -- cosine-similarity top-K=3 / 4096-char hard cap, falls back to existing keyword search (`hivemind_util.search_hivemind`/`lessons.select_relevant`) when embeddings are unavailable.
- `config/tiers.yaml` `memory_rag` block (`enabled: true`, `embedding_model: nomic-embed-text:latest`), exposed via `config_loader.py` -- config-driven per this repo's "everything configurable" rule.
- `orchestrator.run_task` now calls `memory_retrieval.retrieve_context` exactly once per item and threads the combined `context_blob` through every tier (`tier4_run`, `tier3_escalate`, `tier2_escalate`, `tier1_escalate`, `librarian_escalate.run`) instead of each tier independently re-querying `hivemind_util`/`lessons`.
- `tests/test_rag_pipeline_wiring.py`: integration tests confirming the single-retrieval threading and that no tier makes independent keyword searches anymore.

## Bugs found and fixed this session (all via supervisor hand-fix, minor/mechanical -- logged per standing rule)

1. **`scripts/scope_guard.py` relocation-guard false positive** (`6d5a918`): `_RELOCATION_VERBS` check used plain substring matching, so `"remove"` always matched the `"move"` verb. Any item description saying "remove X's independent calls" got misclassified as a relocation, then correctly found the removed symbol gone -- hard-failing an otherwise-successful edit. This was the actual root cause blocking Phase 4 item 4/9 across all 4 escalation tiers, twice. Fixed with `\b`-bounded regex; genuine move/split/extract descriptions still detect correctly (verified).
2. **`tests/test_file_size_ceiling_and_oversize_escalation.py` stale mock** (`6dddca8`): mocked `scripts.tier4_worker.hivemind_util.search_hivemind`, an attribute that no longer exists now that `tier4_worker.py` no longer imports `hivemind_util` (retrieval moved upstream). Removed the obsolete mock.
3. **Three bugs in the dispatch's own generated output** (`2c8a99e`), only surfaced on a full-suite run (per-item `build_cmd` was just `py_compile`, too weak to catch these):
   - `tests/test_rag_pipeline_wiring.py` mocked `orchestrator.tierN_escalate.escalate` -- wrong, since orchestrator imports these as `from scripts.tierN_escalate import escalate as tierN_escalate` (the module-level name IS the function). Also referenced a nonexistent `orchestrator.state` attribute, duplicating what `_patch_state_module()` already handles. Also two tests mocked `tier4_run` to return `status=success`, which never escalates past Tier 4 at all, contradicting each test's own docstring.
   - `tier2_escalate.py` called a hallucinated `lessons.parse_lessons_from_context()` that doesn't exist anywhere in `scripts/lessons.py`.
   - `tier1_escalate.py` called `edit_blocks.build_edit_prompt_header(name, context_blob=context_blob)` -- that function has no `context_blob` parameter, so **every real Tier 1 edit of an existing file would have crashed with `TypeError`**. Fixed to match tier2/tier3's now-correct `lessons_block=""` pattern (RAG content already lives in the threaded `context_blob` via `build_prompt`).

## Open / carried forward

- **`scripts/edit_blocks.py` marker-leak guard** (queued in `knowledge/TECH_DEBT.md`, commit `98df02b`): the leak-detection check only matches the exact 7-char `<<<<<<<`/`=======`/`>>>>>>>` markers. A shorter malformed `====` (4 equals) leaked into `orchestrator.py` **twice** this session (both caught only because they happened to be top-level syntax errors -- a leak inside a string/comment would land silently). Needs generalizing to catch shorter marker runs without false-positiving on legitimate Markdown setext `====` headers. Next time `scripts/edit_blocks.py` is touched.
- **`knowledge/TECH_DEBT.md` over the file-size ceiling**: already ~78KB before this session's one-line addition, over this repo's 73,728-char ceiling. Pre-existing, not caused by this session. Worth pruning/splitting next time that file is touched.
- Carried forward from the prior file, still unresolved: `scripts/content_guard.py`/`scripts/edit_blocks.py`'s edit-block-marker checks are 7-char-exact (same root cause as the item above -- these two items should probably be fixed together).

## Next Steps

RAG/memory layer feature work is done and merged to `main`. No implementation work pending. Next session should pick from: the marker-leak guard generalization, or resume normal supervision (self-fix backlog, tech-debt backlog, oh-my-llama dispatch).
