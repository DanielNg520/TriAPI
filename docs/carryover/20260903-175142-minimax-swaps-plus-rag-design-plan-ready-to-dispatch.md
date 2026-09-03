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

## Post-session independent audit (fresh agent, no session context, re-verified against real repo state)

Covered all 8 commits from `532ff28..HEAD`. Full findings: ran the suite fresh (295/295, `OK`, zero skip-indicators, not trusted from any log); independently reproduced the pre-fix P0 crash by loading the parent commit's `scope_guard.py` standalone and calling `detect_relocation_intent()` (`AttributeError`, confirming the bug was real, not just asserted); diffed the restored Jules test classes byte-for-byte against the original pre-split content (identical); confirmed the state-patch in `bcbaf4d` has no duplicate `task_id`s (replace-not-append honored) and that `agents_md_gate.find_incomplete_plan()` correctly resolves to the still-open `c4164e` RAG plan, not the completed `818725` one; confirmed all doc cross-references (index.json <-> CARRYOVER.md <-> actual files <-> actual SHAs) are internally consistent. All 8 commits: CONFIRMED CORRECT (one, the Jules split `c6a799e`, is CONFIRMED WITH MINOR ISSUE only in the sense that it's the exact bug the very next commit `7b20572` exists to fix — the pair is correct together).

**One real finding to carry forward, not yet tracked anywhere else:** the new relocation-guard hard-fail block in `scripts/dispatcher.py` (~line 1449, from `637d0d1`) runs **unconditionally**, unlike its sibling checks (`scope_concerns`, `mock_patch_lint`) which are gated behind `is_regular_item and result["status"] == "success"`. Two consequences, neither exercised by current tests: (1) it can fire on `verify_only`/`git`-type items whose descriptions happen to contain relocation language even though they were never real move/split edits; (2) if a `build_cmd` already failed for a real, different reason (e.g. a genuine compile error) on an item that also happens to name a relocation-worded symbol that's missing, this check can silently overwrite that legitimate failure `reason` with the relocation message, masking the original root cause. Worth a small follow-up hardening item (gate this check the same way its siblings are gated) next time `dispatcher.py` is touched — not urgent, no test currently depends on the unconditional behavior.

Minor, cosmetic-only nit also found: commit `bcbaf4d`'s message says "Phase 4's 4 items" but Phase 4 actually has 5 items (i0-i4) in the patched state/AGENTS.md checkboxes — the actual patched data is correct, only the prose undercounted.

## Final verified state

TriAPI: 2 commits this stretch (`55d4443`, `e0d183a`) plus this doc commit, full local suite green (295 tests via `unittest discover`, OK, zero SKIPPED), working tree clean after this commit. No oh-my-llama work this session. Independent post-session audit found no false claims across any of this session's 8 commits; one real (non-blocking) hardening gap queued above.
