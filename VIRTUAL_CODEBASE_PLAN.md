# Virtual Codebase Plan — Tiered Planner-Materializer Architecture

**Status: queued design reference, not started.** Consolidates the user's
design messages from the 2026-08-19 session (oh-my-llama dispatch night)
plus findings from checking it against TriAPI's actual codebase. Not an
execution plan yet — a future `triapi plan` session should turn this into
one, scoped down per the "what already exists" section below.

## The idea

Instead of Tier 4 always either loading a whole file (breaks on anything
near/over the context ceiling) or being skipped entirely for oversized
files (today's `skip_tier4` fix — a one-time escape hatch, not a standing
strategy), split editing into three roles that each play to a different
tier's strength:

1. **Slicer** — extracts just enough of the target file for a *local*
   model to understand the edit, regardless of the real file's size.
2. **Planner** (local, Tier 4) — drafts the logic on the slice. Free,
   fast, no context-ceiling concern since it never sees the whole file.
   Formatting/convention mistakes are expected and fine.
3. **Materializer** (cloud, Tier 3/2) — takes the local draft plus the
   *real, full* file (and related files) as a prompt-cached prefix, and
   produces a precise patch against the real codebase. Deep prompt-cache
   discounts apply because the large prefix is static across edits.

## Phase 1 — Semantic Extraction (the Slicer)

Avoid brittle line-number slicing or regex — line numbers drift and regex
can't reliably handle nested brackets/scopes. Use **Tree-sitter** (fast,
broad language support, resilient to syntax errors mid-edit) instead.

- Walk up the AST from the edit target to the nearest enclosing semantic
  boundary (function, method, class).
- Generate a **skeleton file**, not just the isolated function: keep all
  top-level imports, keep the enclosing class definition, keep every
  *other* function's signature with its body replaced by
  `// ... implementation hidden`, and keep the target function's body in
  full.
- Result: a small (~300-500 token), syntactically valid virtual file that
  gives the local model a complete map of its surroundings without the
  full file's bulk.

## Phase 2 — Local Ideation Loop (the Planner)

Feed the skeleton to a local model (e.g. this box's `qwen2.5-coder`
variants via Ollama). Iterate on logic/edge cases/pseudocode. Explicitly
**do not** expect correct formatting, indentation, or lint-convention
compliance here — only intent and core logic. The Materializer fixes
presentation.

## Phase 3 — Cloud Materialization (the Compiler)

Hand the approved local draft to DeepSeek or Gemini to integrate into the
real file:

- **Cache payload:** the full real target file plus closely related files
  (types, the test file). Static across repeated edits → hits the
  provider's prompt cache, large cost reduction.
- **Edit payload:** the local model's rough draft.
- **System prompt:** a strict "output only a Search/Replace block, no
  prose" instruction — integrate the draft, fix missing imports, align
  names/conventions with the real context.

## Phase 4 — Safe Merging (the Patcher)

Never ask the cloud model to output the whole rewritten file (slow,
truncation-prone) and never use unified diffs. Both are worse than
Search/Replace blocks for LLM-driven editing:

- **Why not unified diff:** requires exact leading-whitespace/prefix
  characters per line (` `/`+`/`-`) that LLM tokenization makes
  error-prone, plus arithmetic hunk headers (`@@ -15,7 +15,8 @@`) that
  LLMs are bad at computing since they don't "see" code spatially. Real
  benchmarks (JetBrains' Diff-XYZ, Aider's editing evals) show switching
  from unified diff to Search/Replace raises successful patch rates from
  roughly 26% to 59% on the same model/prompt. The one historical
  exception was GPT-4 Turbo's "laziness" problem, specific to that model.
- **Why Search/Replace works:** forces the model to first locate and
  reproduce the current code (grounding its attention on real state)
  before writing the replacement; matching is context-based
  (`codebase.find(search_block)`) rather than coordinate-based, so minor
  drift elsewhere in the file doesn't break it; no per-line +/- prefixes
  to get subtly wrong.

Format:
```
<<<<<<< SEARCH
    # (>= 2 lines of unchanged context above)
    def calculate_discount(price):
        return price * 0.9
    # (>= 2 lines of unchanged context below)
=======
    def calculate_discount(price, user_tier):
        discount_rate = 0.8 if user_tier == "premium" else 0.9
        return price * discount_rate
>>>>>>> REPLACE
```

Patcher responsibilities:
- **Fuzzy matching:** normalize whitespace and line endings (`\r\n`→`\n`)
  on both sides before matching — LLMs routinely drift on these.
- **In-memory validation:** apply the patch to a string, never disk
  directly.
- **Syntax check:** re-parse the patched string with Tree-sitter; a fatal
  parse error blocks the write.
- **Auto-correction loop:** on a syntax failure, send the error + failed
  content back to the cloud model once for a hidden one-shot fix (cap at
  one attempt — matches the existing 1-attempt oversize-escalation
  pattern already in `scripts/tier4_worker.py::_tier4_fail`).
- **Commit:** only once the syntax check passes.

## Edge cases and mitigations

| Failure mode | Risk | Mitigation |
|---|---|---|
| Stale cache / race | The file changes between slicing and materializing (e.g. an earlier plan item's edit lands after this item's slice was taken) | Hash the file right before the cloud call; if the hash changed before the patch applies, abort and flag a conflict rather than applying against stale content |
| Over-eager matching | A too-small SEARCH block (e.g. `return True`) matches the wrong occurrence | Require ≥2 lines of unchanged context above/below in the prompt; patcher aborts if `codebase.count(search_block) > 1` |
| Syntax destruction | REPLACE block drops a closing bracket, breaking the file | In-memory patch → Tree-sitter re-parse → block the write on `has_error`, one-shot auto-correction loop |
| Whitespace/indentation drift | Tabs vs. spaces, trimmed trailing whitespace breaks the string match | Normalize both sides (strip, `\r\n`→`\n`) before comparing |
| Hallucinated dependencies | Local model invents a helper function that doesn't exist | Cloud materializer prompt explicitly instructs: rewrite to use only real, available utilities from the provided context |

## What TriAPI already has vs. what's genuinely new

Checked against the live codebase before writing this doc, 2026-08-19:

- **Phase 4 (Search/Replace materialization) already exists**, in
  `scripts/edit_blocks.py` — built 2026-08-10/12 for the same underlying
  reason this plan cites (a tier asked to reproduce a whole file for a
  small change instead silently regenerated a shorter version, dropping
  unrelated content: 705→146 lines on one real file). Same block format,
  same "must match verbatim and be unique" constraint. This plan should
  **extend/reuse** it for the materializer step, not rebuild it.
- **Tree-sitter is not a dependency anywhere in TriAPI today** — genuinely
  new (Phase 1's Slicer, and Phase 4's syntax-check step).
- **No stale-file hash check exists** in the per-item dispatch flow today.
  Worth doing regardless of this plan: a real phase-ordering bug hit this
  session (an earlier item's content changed under a later item that
  assumed the old state) — see `PLAN.md`'s 2026-08-19 carryover log for
  the oh-my-llama `state.py`-split/quarantine-fix incident this plan's
  hash check would have caught structurally.
- **Targeting must be adapted**: TriAPI is a headless batch dispatcher
  (Tier 2 breaks a plan into per-file items with a text description), not
  an IDE plugin with a live cursor/selection. "User highlights a function"
  doesn't apply — targeting needs a symbol-resolution step that finds the
  relevant function/class from the breakdown item's own description text
  (e.g. "fix `model_health()`'s query" → resolve `model_health` in the
  target file's AST), not an interactive selection.

## Suggested scope for a future `triapi plan` session

1. Add Tree-sitter (+ grammars for whatever languages TriAPI dispatches
   against most — Python first, given oh-my-llama).
2. Build the Slicer: AST walk-up to enclosing scope + skeletonization,
   given a target file and a symbol name/description to resolve.
3. Build the symbol-resolution step bridging a breakdown item's
   description to an AST node.
4. Extend `scripts/edit_blocks.py`'s consumer path so Tier 3/2's
   materialization step can be invoked with (skeleton, local draft, full
   file + related files) instead of today's (full file, description)
   shape — additive, keep the existing direct-edit path working for cases
   that don't need slicing.
5. Add the file-hash staleness check to the per-item dispatch flow.
6. Add the in-memory Tree-sitter syntax-check + one-shot auto-correction
   loop before any write lands on disk.
7. Decide gating: does every Tier 4 item go through the Slicer now, or
   only items whose target is large/complex enough to warrant it? (Likely
   the latter, to avoid overhead on small files that today's direct path
   already handles fine.)
