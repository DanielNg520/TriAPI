# TriAPI Salvage Plan (2026-09-05)

**Verdict: stop patching this codebase. Salvage the infra listed below,
hand-rewrite the verification/dispatch core, drop the doc-bureaucracy
layer. This file is the decision record for that pivot — written at the
user's request after reviewing the SemAI Phase 8 audit, this repo's own
`docs/agents/20260905-000000-known-recurring-pipeline-problems.md`, and a
month of `CARRYOVER.md` history (2026-08-12 through 2026-09-05, 30+
sessions).**

## Why

- 71,051 lines of docs against 18,313 lines of code — the pipeline spends
  more text managing its own bureaucracy than doing work.
- `docs/agents/20260905-000000-known-recurring-pipeline-problems.md`
  (written by this repo's own audit process, same day) names the root
  disease directly: **"verification that doesn't actually verify."**
  Everything else — false success/failure, scope creep, doc-ceiling
  churn, bugs caught only by manual audit — traces back to that one weak
  link, and it has recurred for a month without being fixed, because the
  fix keeps getting dispatched back through the same broken verify loop
  it's about.
- `CARRYOVER.md`'s history table is close to wall-to-wall "N bugs found
  and fixed," "false-success," "regression caught," "N more variants of
  the same guard patched" — this is not steady-state maintenance, it's a
  system generating its own workload.
- Applied to SemAI: a month of dispatched phases produced a Phase 8
  "agentic" retrofit with a templated tool description
  (`"Work with the user's {kind}."`) and a system prompt that told the
  model tools are for local data only — bugs a careful human catches by
  reading three files. TriAPI's own tests reported these phases green.

## Keep as-is (provider/infra layer — no dependency on the broken verify loop)

| File | Why it survives |
|---|---|
| `scripts/llm_client.py` | Provider-agnostic model client; the multi-tier routing concept is the actual reusable IP here. |
| `scripts/cost_report.py` | Cost tracking is orthogonal to the verify bug. |
| `scripts/secrets_loader.py`, `config/secrets.enc.yaml` / `secrets.example.yaml` | Plumbing, no logic to distrust. |
| `scripts/config_loader.py`, `config/tiers.yaml`, `config/resource_guard.yaml` | Config plumbing. |
| `scripts/resource_guard.py` | Budget/rate-limit gating, independent subsystem. |
| `scripts/embedding_client.py` | Standalone client. |
| `scripts/tri_logging.py`, `scripts/state.py` | Small, mechanical — but re-audit `state.py` against `feedback_state_patch_replace_not_append` before trusting resume-by-count. |
| `scripts/git_ops.py` | Re-audit the known `git add -A` scoping gap (`20260826-193000` carryover entry, never closed) before reuse — small fix, not a rewrite. |
| `scripts/hivemind_util.py`, `scripts/jules_client.py`, `scripts/ollama_load_check.py` | Standalone provider/client glue. |
| `scripts/tier1_escalate.py` … `scripts/tier4_worker.py` (the escalation ladder itself) | The *concept* — tiered cost-ordered escalation with peak-hour gating — is sound and worth keeping; each file is small enough to re-audit individually once the verify layer under it is trustworthy, rather than thrown out. |

## Rewrite from scratch (don't patch further — these are exactly where "verification that doesn't verify" lives)

| File | Problem |
|---|---|
| `scripts/orchestrator.py` (`verify_task`) | Verification is "run whatever `build_cmd` string was configured" — no ground-truth check (real test pass/fail, actual post-write file diff, structural state). This is the #1 root cause per the pipeline's own audit. |
| `scripts/dispatcher_verify.py` | Currently a 13-line re-export stub — fine as a shape, but it re-exports the broken `verify_task`/`run_build`. Rebuild once those are trustworthy. |
| `scripts/scope_guard.py` (`detect_relocation_intent`, `find_out_of_scope_functions`) | Regex/text heuristics over the diff and description. Patched for false positives/negatives across 4+ sessions and still not reliable (most recently: matched "split" inside `.split()` calls). Replace with an AST/structural diff check, not another regex patch. |
| `scripts/dispatcher.py` (61,344 chars — repeatedly hit the file-size ceiling) | The escalation/dispatch control flow concept is fine; the file itself has been split and re-split reactively. Rewrite smaller and modular from day one instead of carrying forward a file that's already needed emergency surgery twice. |
| `scripts/judge.py`, `scripts/critique.py` | Named directly in the false-success audit (`_run_design_judge`/`handle_fix_forward` outcome-propagation bug, `20260825-173000`). The LLM-as-judge idea is fine; the outcome-propagation wiring is not proven. |
| `scripts/mock_patch_lint.py`, `scripts/content_guard.py`, `scripts/edit_blocks.py` | Same family of text/pattern-based guards as `scope_guard.py` — same failure mode likely applies. Re-derive requirements from real incidents, don't port the heuristics. |

## Drop entirely — don't carry forward

| File / subsystem | Why |
|---|---|
| `docs/carryover/` + `docs/agents/` + both `index.json` files + the size-ceiling-triggered auto-split machinery | This entire layer exists to manage a problem (docs/files repeatedly ballooning past a 73,728-char ceiling) that a smaller, leaner rebuild with fewer and smaller files won't have anywhere near as badly. It is itself ~4x the code volume. Start the new repo with a normal-sized `AGENTS.md`/`CHANGELOG` and no auto-splitting infrastructure. |
| `scripts/agents_md_gate.py`, `scripts/doc_staleness.py`, `scripts/librarian_escalate.py`, `scripts/dispatcher_breakdown.py`, `scripts/breakdown_prompts.py` | Support machinery for the doc-bureaucracy layer above. Goes with it. |
| `scripts/self_fix.py`, `scripts/clear_stale_self_fixes.py` | The self-fix loop is the most self-referential part of the system — TriAPI fixing TriAPI through the same unverified pipeline. This is exactly the trap described in "Why" above. Don't rebuild until the new verify core has stood on its own for a while, and even then treat it as the last piece to re-add, not the first. |
| `scripts/memory_retrieval.py`, `scripts/rag_index.py` | RAG/memory layer added very recently (Phase, 2026-09-03/04) and its own wiring dispatch needed 3 follow-up bug fixes to its own generated output. Unproven, not load-bearing for the core loop. Don't re-add until the new core is stable — re-derive it later if actually needed. |
| `scripts/tech_debt.py`, `knowledge/TECH_DEBT.md` | Concept (a backlog of known issues) is fine, but the implementation had its own silent-no-op bug on stale entries and its own corruption incident. Replace with something much simpler (a flat file or issue tracker) rather than porting the code. |
| `knowledge/lessons.jsonl`, `knowledge/hivemind.md` | Auto-growing lessons log — same shape as the doc-bureaucracy problem at smaller scale. If a lessons file is wanted, keep it small and hand-curated, not pipeline-appended. |

## Root files

| File | Disposition |
|---|---|
| `scripts/triapi.py` (38,893 chars, main CLI) | Keep as the entrypoint shape, trim it as the pieces underneath get rewritten. |
| `AGENTS.md`, `ARCHITECTURE.md`, `README.md`, `PLAN.md`, `CARRYOVER.md`, `AGENT_GUIDE.md`, `VIRTUAL_CODEBASE_PLAN.md` | Don't port content forward mechanically. Write a fresh, short `AGENTS.md` for the new core once it exists. `VIRTUAL_CODEBASE_PLAN.md` (queued, user wants to work on it together personally — see `project_triapi_virtual_codebase_plan` memory) stays a live idea to revisit, not a doc to migrate as-is. |
| `tests/` | `tests/test_branch_features.py` is 1,591 lines on its own — re-scope tests alongside the rewrite rather than carrying the existing suite forward; per the audit, this suite has been passing green on work that later proved broken, so its coverage can't be trusted as a baseline. |

## Proposed sequence

1. New core, hand-written, small: a ground-truth verify layer (real test
   pass/fail, real file-diff checks, no substring grep) + a minimal
   dispatcher that calls it. No self-fix loop, no doc-auto-split, no RAG
   layer. Built and tested by hand, not dispatched through the old
   pipeline.
2. Re-attach the "keep as-is" infra table above (llm_client, cost_report,
   config/secrets plumbing, resource_guard) once the new core exists.
3. Re-audit and re-attach the tier escalation ladder (tier1-4) file by
   file, now backed by real verification.
4. Only after the above has run clean for a while: reconsider self-fix,
   RAG/memory, and any doc-management layer — each as a deliberate
   feature decision, not a default carry-forward.
5. SemAI stays untouched by TriAPI dispatch until step 1-3 are done;
   the Path B fixes from `Agentic_Audit.md` get applied by hand in the
   meantime if the user wants SemAI usable sooner.
