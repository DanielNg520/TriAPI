# Carryover — 2026-09-04 — Full doc audit: RAG layer documented, stale model refs fixed

**Status: RESOLVED.** Working tree clean, all changes committed (`407c040`). Session ending here per user request.

## What happened

User asked for a full audit and update of all docs before ending the session (standing practice per `feedback_auto_update_docs_at_session_end`, this time explicitly requested). Found and fixed via `triapi plan`/`dispatch` (run `20260904-145428-31fa69`):

1. **Stale model names in `ARCHITECTURE.md`'s tier table and `README.md`'s walkthrough**: both still said Tier 4's off-peak model and Tier 3's peak-alt model were `OpenRouter nvidia/nemotron-3.5-lightning:free`, but that was swapped 2026-09-03 to `minimax/minimax-m3:free` (per `config/tiers.yaml`, already reflected in `project_triapi_tier_assignment_20260901` memory but never propagated to these two docs). Fixed in both.
2. **`README.md`'s `ollama pull` list and Tier-4-speed gotcha referenced the wrong local model quant** (`qwen2.5-coder:14b-instruct-q8_0`, plus two models — `deepseek-coder-v2:16b`, `qwen2.5-coder:32b` — not actually configured anywhere) instead of the real `tier_4_worker.peak_alt` model, `qwen2.5-coder:14b-instruct-q6_K`. Fixed, and added the missing `ollama pull nomic-embed-text:latest` line for the RAG layer's embedding model, which wasn't in the pull list at all.
3. **The RAG/memory retrieval layer (shipped 2026-09-04, see the `114500` carryover file) had zero documentation** in `ARCHITECTURE.md` — a full subsystem (`scripts/embedding_client.py`, `scripts/rag_index.py`, `scripts/memory_retrieval.py`, `config/tiers.yaml`'s `memory_rag` block) merged with no architecture write-up. Added a new `## RAG and Memory Retrieval Layer` section; verified accurate against the real code (`build_context_blob()` in `tier4_worker.py`, `retrieve_context()` threading in `orchestrator.py`) after dispatch, not just trusted the tier's "success" report.
4. **`PLAN.md`'s own convention** (a `docs/plan/` entry for every durable build-rationale record) was never followed for the RAG layer build. Created `docs/plan/20260904-145433-rag-memory-retrieval-layer.md`, added it to `docs/plan/index.json` and `PLAN.md`'s index table.
5. **`knowledge/TECH_DEBT.md`'s one entry (the narrow-test-command bug) was already resolved** (fixed this session in commit `d6ab54c`), but `triapi tech-debt` silently no-op'd on it — `check_staleness()` correctly filtered it out (file hash changed) but nothing then removes a stale-but-resolved entry, so it would have sat there forever with zero feedback. Dropped by hand (established precedent, commit `0a9e46b` did the same); queued the tool gap itself as a new tech-debt entry (`scripts/triapi.py`'s `cmd_tech_debt()`).

Pushed back once on the plan's first draft (verify commands only checked a header/file existed, not that the content named real symbols) before approving — given this was a doc-writing task with real hallucination risk, insisted on assertions naming the actual module/function names. All 7 dispatch items succeeded via `tier_5`; spot-checked the new `ARCHITECTURE.md` section and `docs/plan/` file against the real source (`grep`'d `build_context_blob`, `retrieve_context` wiring in `orchestrator.py`) rather than trusting the "success" status alone — no hallucinated specifics found this time.

## Doc sizes at session end (all under the 73,728-char ceiling)

AGENTS.md 17,452 · CARRYOVER.md 22,857 · PLAN.md 19,247 · ARCHITECTURE.md 11,179 · README.md 16,586 · AGENT_GUIDE.md 43,717 · knowledge/TECH_DEBT.md 1,389.

## Open / carried forward

- **`cmd_tech_debt()`'s silent no-op on stale-but-resolved entries** — queued in `knowledge/TECH_DEBT.md` this session, not yet fixed.
- **`AGENT_GUIDE.md` was not audited for RAG-layer staleness** this session — it's a worked-test-case narrative doc (Tier-1-off operating manual), different shape from `ARCHITECTURE.md`/`README.md`, and only had scattered `context_blob` mentions (accurate, not stale) rather than a missing section. Left as-is; worth a closer look if it's ever touched for other reasons.
- SemAI Phase 8 (full agentic mode) remains queued in SemAI's own carryover, not started.
- The two background-test-suite-stalls-silently and `agy` transient-failure patterns flagged in the prior session remain unexplained, not reproduced further this session.

## Next Steps

Session ending here per user request. Next session should pick from: SemAI Phase 8 (needs a rewrite-then-plan pass), the `cmd_tech_debt()` stale-entry gap, or normal supervision.
