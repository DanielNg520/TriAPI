# AGENTS.md

TriAPI: multi-tier LLM dispatch pipeline. Read this file first, it is the only doc kept live.
Everything else, including `docs/artifact/`, is frozen history, not maintained.

## Current architecture

Old dispatcher (`scripts/dispatcher.py` + tier1-5 escalation) is deprecated in place, not deleted, not running.
Root cause: its own verification never verified real state.
See `SALVAGE_PLAN.md` for the keep/rewrite/drop decision.

Active work lives in `rebuild/`: DeepSeek writes code, agy writes docs, Claude plans+audits every response.
Nothing auto-applied. See `rebuild/README.md`, `rebuild/PHASES.md`, `rebuild/RULES.md` (hard rules shared by every call).

Design principle: hub-and-spoke, not waterfall. Every worker result routes through Claude before the next step.
No worker-to-worker handoff, ever — that chain shape is what let bugs propagate silently in the old pipeline.

Test command: `cd rebuild && python3 -m pytest -v tests/`

## Doc policy

One file only: this one. Carryover is the section below, not a separate file.
Hard cap: 1000 lines, 30 words per line. Precise, worth-noting entries only, no narrative.
Once work is done, delete its line entirely — don't move it to an archive file. Git history has it.
A removed/retired feature gets zero doc trace: no "X removed" line, no rationale footnote, nothing.
A pending removal task states the action only ("delete file X"), never the reasoning for removing it.
This repo's docs never reference or absorb another repo's content — relocate that repo's own docs there instead, never delete it.
This policy applies to every repo TriAPI supervises, not just this one — check each target repo's own AGENTS.md follows it too.

## Carryover (current state, 2026-09-05)

- TriAPI rebuild: Phases 1-3 done (`rebuild/scripts/verify.py`, `dispatch.py`, `cost.py`), 34/34 real tests passing.
- Phase 4 (auto tier-escalation) deferred by user decision — steady state is manual DeepSeek+agy+Claude.
- Efficiency additions done: spend cap (`cost.check_budget`, $5.00 default in `model_config.yaml`, hard-blocks `call_deepseek.py` before the API call, no bypass flag) and code-block extractor (`llm_client.extract_code_block`).
- One DeepSeek-written test batch (P3B-04) failed audit — wrong return type assumed, missing yaml key, bad call signature. Rewritten by Claude directly rather than re-dispatched.
- Design principle now explicit: hub-and-spoke, not waterfall — every worker result routes through Claude before the next step, see `## Current architecture` above.
- OpenRouter: recommended against adding for now — shared rate-limit pool, content-filter false positives, free-tier hallucination were all real problems in the old pipeline.
- If OpenRouter is added later, the right slot is a Phase-4 escalation fallback leg, not a peer to DeepSeek.
- SemAI Path B fixes applied via the rebuild pipeline (commit `e512904` in SemAI, local on branch `migration-clean-up`, not yet pushed — user hasn't confirmed the push).
- Found+fixed a bug in `verify.py` while dispatching against SemAI: stdout+stderr concatenation let stderr's unittest noise mask the real pytest result. Commit `3edebee`, regression-tested.
- SemAI's own docs purged to the same single-AGENTS.md policy (commit `c9861fa` in SemAI, same branch).
- Doc policy is now GLOBAL — applies to every repo, not just TriAPI.
- All rebuild commits pushed to origin/main as of `ee262c0`.

## Future plans (queued, not started)

### 1. Virtual Codebase Plan — tiered Planner-Materializer for large-file edits

Goal: a local model drafts edits on oversized files without hitting context limits.
A cloud model then integrates the draft into the real file precisely.

- Slicer: AST walk (Tree-sitter) to the target function's enclosing scope.
- Produces a small skeleton file: imports, class shell, other functions' signatures only, target function in full.
- Local Planner (Tier 4-equivalent): drafts logic on the skeleton. Correctness only, formatting doesn't matter.
- Cloud Materializer (DeepSeek/Gemini): given the full real file (prompt-cached) plus the local draft, emits a patch.
- Emit a Search/Replace block, not a unified diff — benchmarks show ~59% vs ~26% success rate.
- Patcher: normalize whitespace before matching, apply in-memory only, never write to disk directly.
- Re-parse with Tree-sitter after applying; one-shot auto-correct on syntax failure; commit only once it parses clean.
- Known building block: `scripts/edit_blocks.py` (old pipeline) already does Search/Replace materialization — reuse/extend, don't rebuild.
- Tree-sitter itself is a new dependency, not used anywhere in TriAPI today.
- Status: design reference only. User wants to work on this together personally — do not start solo.

### 2. `triapi tui` — interactive terminal driver

Goal: a `triapi tui` subcommand as an alternative entry point.
Each typed prompt triggers a fresh, independent `claude -p` call — explicitly no session continuity.
Instead, each call's outcome gets logged to this file's carryover section so the next call has context.
Streams output live as it's generated, not buffered.

Open questions, unresolved:
- Curses vs. a TUI library (textual/rich) — no dependency choice made yet.
- One log entry per call, or per session (multiple prompts)?
- Whether to inject fixed system framing around the raw prompt, or send it verbatim.
- Whether to block/warn if a dispatch is already running in the background.

Predates the rebuild and the new doc policy — needs re-scoping against whichever pipeline is live when planned.
Status: blocker cleared long ago, never dispatched. Needs the user's input on the open questions first.

## Archive

Old bloated docs moved into `docs/artifact/` (`docs/artifact/carryover/*`, `docs/artifact/agents/*`), frozen, not indexed here.
Covers plan-block history, file/dir doc overflow, old tier-escalation session notes — not indexed here.
Full detail recoverable via git history if ever needed.
