# Hivemind

Collective intelligence, lessons, and engineering patterns.


### Use canonical factories to build pipeline state; don't hand-assemble look-alike dicts

When adding a new command or flow that feeds work into an existing stateful pipeline, reuse the pipeline's own state factory (e.g. `dispatcher.new_run(...)`) or add a first-class factory for the new flow. Do not hand-construct a "synthetic_state" dict that imitates the schema.

The new `cmd_tech_debt` illustrates the risks:

- It leaves out fields real runs have (e.g., `prompt`), so later stages (`status`, push commit messages, etc.) can crash with `KeyError`.
- It must be updated every time the state schema changes, inviting drift.
- It bypasses invariants, ID generation, and normalization that the factory provides.
- It also uses modules (`tech_debt`, `uuid`) without importing them, so it fails immediately at runtime.

Prefer a small builder that starts from the canonical state factory and then specializes it, or add something like `dispatcher.new_tech_debt_run(...)` that returns a complete, valid state. Additionally, treat missing imports as a build/runtime error: add explicit imports for every new module referenced, and run static checks/import tests before merging.

### Verify-and-Rollback Automated Edits, Then Queue Hash-Keyed Debt

When an automated agent applies a fix to a source file, do not trust the edit just because the agent reported success. Treat the change as provisional:

1. **Snapshot first** — save the original file content before applying the fix.
2. **Apply the fix** — let the agent/escalation mutate the file.
3. **Verify with the real check** — run the build or test command against the modified state.
4. **Keep only verified changes** — if verification passes, the fix stays.
5. **Roll back on failure** — if verification fails, restore the saved snapshot so the workspace returns to the last-known-good state.
6. **Record deferred work with a content hash** — log a backlog entry containing the file path, reason, and a SHA-256 hash of the file content at the time the debt was recorded.
7. **Skip stale backlog entries later** — when replaying deferred work, recompute the file's current hash and skip entries whose hash no longer matches, or whose file has been deleted.

This pattern makes automated edits safe (no broken files left behind) and makes deferred work self-pruning and idempotent (no wasted retries on already-changed code).

### Treat independent post-success checks as part of the success decision

A task passing its own `build_cmd` is not enough to mark it done. When a cheap, deterministic, artifact-appropriate static check exists, run it after the task succeeds—and if it finds violations, downgrade the result to a normal retryable failure instead of merely logging a warning.

**Pattern**

1. After an item reports `success`, run any applicable post-check (linter, domain-specific scanner, static analyzer).
2. Scope the post-check narrowly to artifacts it actually understands (e.g. `tests/test_*.py`), so it does not produce false positives on unrelated files.
3. If the post-check finds issues, override the result status to a retryable failure such as `build_failed`, clear `resolved_by`, and set `reason` to the reported issues.
4. Invalidate any success-only metadata at the same time (e.g. clear the content hash), so later regression tracking cannot treat the artifact as known-good.
5. Record the downgraded result through the normal pipeline so the existing resume/retry logic automatically retries the item.

**Why**

- A warning-only approach leaves the bad artifact marked successful, so the orchestrator moves on and the defect is invisible in the final run state.
- Routing the violation through the normal failure path means the item is retried/fixed by the same machinery instead of requiring a bespoke manual intervention.
- Narrow scoping keeps the gate trustworthy: a test-specific linter applied broadly would create false failures and erode confidence in the whole pipeline.
- Clearing success metadata prevents a later regression guard from believing a file that actually failed still has a known-good hash.

### Patch at the Import Site, Not the Definition Site — and Gate on It

In Python, `from a import f` binds `f` into `b`'s namespace; `mock.patch("a.f")` patches the original, not the already-imported reference. Tests that patch `a.f` while exercising `b`'s copy silently run the real function — potentially a real network call. Rule: patch where the code under test looks up the name, i.e. `mock.patch("b.f")`, not where it was defined.

To prevent recurrence:

- Build a small static AST linter (stdlib only) that walks test files for `mock.patch("dotted.target")` / `mock.patch.object(...)`, resolves whether the target's defining module is imported via `from <defined_in> import <attr>` into another referenced module, and reports the correct target(s).
- Wire the linter into the existing pipeline as a post-write validation step: if it flags a result, override the result status to the same failure status used by a real build failure (`build_failed`), so it flows through existing stop/escalation/handoff logic with no new failure branch.
- Add regression tests using temporary fixture repos (not the repo's own files), and move to a dedicated test file once the shared test module exceeds a maintainable size.

This combines two reusable ideas: the correctness rule (patch where the name is bound/imported), and making a quality policy a first-class gate by reusing existing failure semantics instead of adding a separate path.

### Ground AI workers with deterministic canonical context files (fail closed when the anchor is missing)

When an AI worker/agent can only see repository files explicitly listed in its `context_files`, any step that references “the existing pattern”, “the test file”, or “follow the structure of X” must be backed by a deterministic, post-generation grounding step. Do not rely on the model to correctly infer or fill in these references.

**Problem observed:**  
- A step referenced “the test file” / “existing test patterns” without naming a path. The worker had no context file to read, so it hallucinated a test structure.  
- When an anchor test file was chosen merely by alphabetical order, the worker copied a pattern from the wrong file instead of the project’s canonical example.

**Solution pattern:**  
- After the LLM produces each phase/plan item, run a deterministic “context guard” that enriches every item with the right supporting files.  
- Prefer a known canonical file (`tests/test_branch_features.py`) when present; otherwise fall back to a deterministic, stable selection (e.g. first sorted `tests/test_*.py`).  
- Also add closely related helper files (for a `tests/test_foo.py` target, include `scripts/foo.py` if it exists) so the worker sees the implementation it is testing.  
- Add the canonical anchor file to *every* item’s `context_files`, so workers pattern new tests against the real existing example rather than inventing one.  
- If no anchor can be found, return a hard error instead of silently proceeding with ungrounded items. “Fail closed” is better than letting a hallucinating worker run.

**Also apply the guard before persisting state:**  
- Run the enrichment/validation immediately after the LLM returns an item, before appending it to the persisted run state.  
- If the guard fails, stop the phase rather than saving a plan that cannot be reliably executed.

This is a reusable pattern for any LLM-generated work order where downstream workers have a limited, explicit view of the codebase: give them a concrete, canonical thing to imitate, make the inclusion deterministic, and treat “no canonical example available” as a blocking error rather than a creative-writing opportunity.

### Deterministic Context Grounding for LLM Code-Editing Tasks

When an LLM-driven pipeline edits code (especially tests or generated files), never rely on the model to infer which companion files it needs. Instead, assemble context explicitly and deterministically from the target's naming convention, verify every path exists, and fail fast at plan time if a required anchor is missing.

**The failure it prevents:** An LLM editing `tests/test_hivemind_util.py` was given no content from `scripts/hivemind_util.py`, so it invented wrong parameter names. An LLM editing `tests/test_judge.py` was given no existing example test file, so all 4 escalation attempts defaulted to `import pytest` — which the repo doesn't use — before human handoff. Relying on the LLM to populate its own `context_files` proved unreliable: a real 96-item breakdown left `context_files` empty on all 15 dispatched items.

**The pattern:**
1. **Derive companion files from naming conventions.** Parse the target (`tests/test_<name>.py`) and deterministically add the same-stem source file (`scripts/<name>.py`) to the context — no LLM judgment required.
2. **Verify existence before injecting.** Only add paths that actually resolve on disk. Never fabricate or guess a path; a missing companion is simply skipped.
3. **Always include an anchor/exemplar for convention-driven code.** For test files, guarantee at least one existing `tests/test_*.py` is in the context so the model can mirror the repo's real framework and style (prefer a canonical file like `test_branch_features.py`, then fall back to a sorted glob).
4. **Fail fast at plan approval time.** If no anchor exists, reject the plan immediately with a clear, actionable reason instead of letting the runtime pipeline burn escalation attempts against a task that cannot succeed. Reuse the existing error-return contract so callers handle it like any other breakdown failure.
5. **Make it idempotent and narrowly scoped.** Don't duplicate paths already present; leave non-matching targets untouched; never mutate a shared default list in place without copying.
6. **Lock it in with regression tests.** Use temp fixture repos covering: companion present/absent, canonical anchor vs. fallback anchor, missing-anchor rejection, non-target no-op, and no-duplication on repeated calls.

**Why it works:** It converts implicit knowledge the LLM would guess (or silently omit) into explicit, checked inputs, and it moves the cost of a missing prerequisite from expensive runtime escalation to an early, cheap, deterministic rejection.

**Related lesson:** Treat "the model didn't populate the context" as a pipeline bug, not a model quirk. Add a deterministic backstop (`_backstop_context_files`-style regex extraction or naming-convention derivation) as a floor under any LLM-produced metadata.

### Deterministic Context Grounding for AI-Generated Files: Companion + Style Anchor

When an AI tier will draft or modify a file, never rely on the task description or on the AI's own initiative to gather the context it needs — derive and inject that context deterministically from the file's structure.

**The failure mode this prevents:** a task like "write tests for the new module" or "extend the existing test patterns" gives the drafting model no concrete grounding. The model hallucinates file names, project conventions, and API shapes that match nothing in the repo — then reports `success` because the (weak) build check only verified existence/syntax.

**The pattern — for test files specifically:**
1. **Derive the companion module automatically.** For a target `tests/test_<name>.py`, strip the `test_` prefix and add `scripts/<name>.py` (or the equivalent source path) to the grounding context whenever it exists on disk. This ties the test to the real API it must exercise.
2. **Add a canonical style anchor.** Inject the project's conventional test file (e.g. `tests/test_branch_features.py`) as a style reference — not the first file found alphabetically, but the one that encodes the project's actual testing conventions. An arbitrary alphabetical pick can anchor the model to a non-representative pattern.
3. **Fail closed when grounding is impossible.** If no anchor test file exists, error out during breakdown/dispatch rather than dispatching an ungroundable item. An ungroundable task will waste expensive escalation attempts and produce confidently wrong output.

**Generalize the lesson beyond tests:**
- Whenever an AI will author or edit a file, ask: *what real files define the expected shape of this output?* Inject them as read-only context automatically.
- Prefer deterministic structural derivation (target path → companion module → anchor file) over prompt instructions like "include context_files when needed" — prompt compliance is unreliable; structural rules are not.
- A "verify" step that only checks existence/syntax cannot detect hallucinated content. Grounding prevents the hallucination; the build check is not the safety net.

**Applies to:** any LLM-based code-generation pipeline, internal scaffolding tools, or agentic workflows where a model drafts files that must match existing conventions.

### Prefer Explicit Dependency Discovery + Stable Topological Sort Over Hardcoded Ordering Heuristics

When a pipeline dispatches a sequence of file-creation/editing tasks, and one task's verification command (`build_cmd`) imports another task's target module, the dispatch order must guarantee dependencies run first.

A naive fix—e.g. hardcoding `"creator"` and moving all non-importing items to the front—is fragile:

- It reorders unrelated items needlessly.
- It may fail to converge when the qualifying item is already first, producing a spurious error.

The robust pattern:

1. **Extract the dependency relation explicitly.** Parse the actual commands/build steps for import statements (`from scripts import X`, `import scripts.X`) and map each importer to the task whose target creates that module.
2. **Apply a stable topological sort per batch/phase.** Emit items with no unsatisfied dependencies in their original relative order; only reorder when a real edge requires it.
3. **Only fail on a genuine cycle.** If a full pass makes no progress, the remaining items form a circular dependency—report that as the error, rather than tripping an arbitrary loop cap or order heuristic.
4. **Preserve unrelated order.** Topological sorting should be stable: items not involved in any dependency edge keep their original order, so the plan's intended sequencing remains intact.

This pattern is reusable anywhere tasks have implicit ordering constraints discoverable from their content or commands: build systems, code-generation pipelines, migration runners, or any "create file A then run B that imports A" workflow.

```python
# Shape of the pattern:
dependencies = build_dependency_graph(items)   # explicit edges from parsed imports
ordered = stable_topological_sort(items, dependencies)
if cycle_detected(ordered, dependencies):
    return error("circular dependency")
```

The key lesson: don't guess ordering from names or hardcoded roles—inspect the actual dependency evidence and sort deterministically.
