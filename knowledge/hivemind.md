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

### Self-Healing Cleanup: Layered Safety Nets Plus a Crash-Recovery Journal

When a process temporarily changes external system state (stopping services, mutating config, holding a lock) and must restore it afterward, never rely on a single cleanup path. Design cleanup to survive even the death of the process that initiated the change.

#### Key lessons from this pattern

1. **`try/finally` is not enough.** A normal `try/finally` does not run on `SIGTERM` or a hard kill. If a stuck dispatch may be terminated with `kill`, a signal handler plus `atexit` handler must be installed as soon as the external state is mutated, so `SIGTERM`, `SIGINT`, and normal interpreter exit all trigger restoration.

2. **Persist a journal/lock for hard-kill recovery.** Signal handlers still cannot run on `SIGKILL`, OOM kill, or power loss. Write a small lock/journal file containing:
   - the owning PID,
   - what was changed,
   - timestamp.

   On the next invocation, check whether the owning PID is still alive (`os.kill(pid, 0)`); if it is dead, treat the journal as orphaned and resume/restore the recorded state before doing new work. This gives self-healing behavior without a separate watchdog process.

3. **Make restoration idempotent.** Multiple cleanup paths may race or run redundantly: the caller's `try/finally`, the signal/atexit safety net, and the next-process stale-lock recovery. Guard restoration with an in-memory `done`/`resumed` flag so it runs exactly once, then remove the journal file only after successful restore.

4. **Snapshot the actual prior state, not just an on/off flag.** For services with warm state (like Ollama resident models), record both whether the service was active and which resources were loaded. On restore, reload warm resources and stop the service only if it was originally inactive. This preserves the user's real environment instead of forcing a cold state.

5. **Only manage what you actually changed.** Before pausing a service, check whether it is currently active. If it was already inactive, leave it alone and do not include it in the restore list. This avoids resurrecting something the user or another process deliberately stopped before your run began.

6. **Prefer exit-code checks over output parsing.** The diff replaced capturing and parsing `systemctl is-active` output with `systemctl --user is-active --quiet` and checking the return code. Exit codes are stable, locale-independent, and avoid brittle string matching.

### Tolerate Format Drift in LLM-Generated Structured Content — and Make the Tolerance Narrow Enough to Stay Selective

When your system consumes LLM-generated or LLM-influenced text (plans, checklists, breakdowns, structured metadata), **do not assume the model will honor a single canonical format for structural markers**, even if you asked for one in your system prompt. Models reliably drift between conventions: ATX headers of varying depth (`## Phase`, `### Phase`), numbered prose headers (`1. Phase 1 -- ...`), plain hyphen bullets with no checkbox syntax, etc. A parser that silently recognizes only one convention will quietly drop valid content — and because the output is well-formed overall, the failure often goes unnoticed until much later.

In this diff, `_PHASE_HEADER_RE` was hardened from matching only `#{1,6} ` to also matching numbered top-level markers like `N. Phase ...` or `N. Capitalized-Word ...`. The real incident: a plan used `1. Phase 1 -- ...`, `2. Phase 2 -- ...` with no `#` markers at all, so the splitter saw no phase headers, collapsed the whole plan into one chunk, and dropped every phase after the first.

Key practices this illustrates:

1. **Recognize that format drift is the norm, not the exception.** The same codebase's comments document real occurrences of: plans using `###` instead of `##`, numbered checkboxes instead of `- [ ]`, plain numbered items with no checkboxes, and `N. Phase N --` headers with no Markdown heading syntax. Treat any single-format assumption as a bug waiting to happen.

2. **When broadening a matcher, make the new branch deliberately narrower than the existing one.** The numbered-header regex requires `Phase` or an uppercase letter after the number, so numbered checklist sub-items inside a phase are not misread as new phase boundaries. Broadening a parser is only safe if the added flexibility doesn't create false positives that corrupt the structure you're trying to preserve.

3. **Fail loudly when tolerant parsing produces an empty result.** The surrounding file contains another important half of this lesson: `breakdown_plan()` explicitly refuses to report success when a non-empty plan yields zero items, because a previous silent "0 items" result was indistinguishable from a genuine empty-plan success. When you relax a parser to accept more formats, add a guard that turns "nothing matched" into an explicit error rather than a plausible-looking no-op.

4. **Document why the pattern was broadened.** Each regex in this file carries a comment explaining the exact real-world failure that motivated it (`found for real 2026-08-19 (run ...)`). This turns a cryptic regex into an operational memory: future maintainers know *why* the pattern is permissive, and know not to "simplify" it back into a single-format assumption.

**Applicability:** any pipeline that parses LLM output into structured units — plan splitters, task breakdowns, log parsers, config generators, code generators — especially when the parsed structure drives downstream work that would silently skip work if misparsed.

### Fail-Closed State Transitions: Verify Expected Counts Before Mutating Persistent Artifacts

When a function mutates a persistent, user-editable artifact to mark work as complete, do not blindly rewrite matched markers. Require the caller to supply an expected count of work items (e.g. `breakdown_item_count`), scan the actual artifact for both checked and unchecked items, and refuse to write if the actual count exceeds what was originally captured.

Key rules:

- **Count both `- [ ]` and `- [x]` items**, not just unchecked ones. The check is about "did the artifact gain work we never accounted for", not "is everything checked".
- **Fail closed on a mismatch**: if `block_item_count > breakdown_item_count`, do not write the file, log a warning identifying the discrepancy, and return `False` so the caller can surface the problem.
- **Keep the mutation atomic**: perform the substitution in memory first, then check the mismatch flag before writing. Never partially write or write first and validate later.
- **Use a nonlocal flag inside `re.sub` callbacks** to signal mismatch without throwing, then abort after the full substitution pass. This keeps the detection logic close to the regex logic while preserving a single write-point.
- **Return a boolean result** for state-transition operations so callers can distinguish "completed successfully" from "no-op / refused"; do not raise for benign missing-state cases like an absent file or unknown run id.

This pattern prevents silent false completion: if someone hand-edited the plan, a duplicate block exists, or a later step added unchecked work, the system will not mark unaccounted-for work as done.

### Pass Explicit Aggregate Counts When Finalizing Persisted Progress/Checklist State

When a system maintains a persistent, human-readable progress artifact (e.g., an appended plan checklist in `AGENTS.md`) alongside an authoritative internal state (e.g., a run's phase/step breakdown), finalization updates must receive exact counts from the authoritative state rather than re-deriving them inside the helper.

In this change, `mark_plan_complete` now receives the total number of breakdown items:

```python
agents_md_gate.mark_plan_complete(
    state["project_dir"],
    state["run_id"],
    sum(len(p["items"]) for p in state["breakdown"]["phases"]),
)
```

This matters because:

- The persisted checklist must be fully marked complete, or the "one incomplete plan per repo" gate will incorrectly block future planning.
- The breakdown in the run state is the source of truth for what was actually dispatched; the original approved plan text may be formatted differently or may not map 1:1 to executed steps.
- Letting the helper parse or guess the count from the artifact risks drift, partial completion, and stale blocks.

General guideline: whenever you synchronize external state (checklists, status files, reports, tickets) with internal state, pass the exact computed totals/values from the source of truth into the synchronization function. Avoid deriving those values from the very artifact you are trying to update.

### Pass the authoritative count/expectation explicitly instead of inferring it from mutable artifacts

When a function mutates or validates an external artifact (e.g., marking an `AGENTS.md` checklist complete), do not make the function infer the expected total from the artifact itself. Pass the authoritative expected value (such as `breakdown_item_count`) from the caller.

In the diff, `mark_plan_complete` now takes `breakdown_item_count`, and every call site supplies it explicitly. This makes the dependency visible, prevents the function from guessing based on the same mutable file it is about to rewrite, and avoids silently accepting an incomplete or corrupted plan.

General rules this reinforces:

- **Explicit parameters beat implicit environment/artifact inference.** A function should not re-derive facts the caller already knows; doing so couples it to file formats and mutable state.
- **Make completion criteria auditable.** When the caller passes the expected item count, tests and logs can verify that the plan was marked complete for the right reason.
- **Keep pure functions testable.** Supplying the count as an argument makes test setup clear and removes hidden assumptions from the function body.
- **Avoid “works by accident” behavior.** If the function counted checkboxes itself right before flipping them, it could easily produce the wrong result when the artifact is partially updated or contains unrelated prose/checkboxes.

### Guard completion against plan/execution count mismatch — never blindly check off declared work

When a system auto-completes or marks a plan as done, verify that the number of work items actually captured/executed matches the number of work items the plan declares. Do not flip every checkbox to `[x]` just because the overall run reported `completed`.

Concretely (from the TriAPI plan-completion bug):

- `mark_plan_complete()` was unconditionally replacing `- [ ]` with `- [x]` for a run's plan block. A partial breakdown — where the dispatcher captured fewer items than the plan's checklist contained — would still mark the whole block complete, falsely implying work was done that wasn't.
- Fix: require `breakdown_item_count` as a parameter, count the checklist items actually present in the block (`[ ]` and `[x]` both), and if the block declares more items than the breakdown captured, **refuse to write anything**, log a warning naming both counts, and return `False`.
- This is fail-closed behavior: an integrity mismatch leaves the gate closed rather than silently recording a false success.

Related integrity lessons from the same change:

- **Parsers must recognize every legitimate input format.** A phase-splitter that only matched `## ` headers silently dropped whole phases when plans used `### ` or numbered `1. Phase ...` markers. Widen the matcher deliberately and add regression tests for each real incident shape.
- **A non-empty plan that yields zero work items must be a hard error**, never a vacuous `status: "ok"` — silent no-op success is worse than a loud failure.
- **Pin each incident with a dedicated regression test**, preferably in a new test file when the existing suite has grown too large, using fixture repos rather than the repo's own files. The test name and comment should cite the run/incident that motivated it.
- When validating test output, check for the *exact* unittest skipped delimiter (`... skipped`) rather than a bare substring `skipped`, which false-positives on legitimate test method names.

### Best-Effort State Snapshot Before Mutating Long-Running Environments

Before a long-running process changes a shared external service (e.g., unloading models), snapshot the service's current state so it can be restored exactly on exit. Make the snapshot best-effort: wrap it in `try/except`, default to `None` on failure, and log a warning. A snapshot failure must never block the main operation.

Also load the configuration needed for that snapshot once, store it, and reuse it in later steps instead of reloading it:

```python
tiers_cfg = None
ollama_snapshot = None
try:
    tiers_cfg = load_tiers()
    ollama_snapshot = resource_guard.snapshot_ollama_state(...)
except Exception as exc:
    log.warning("Could not snapshot ...: %s", exc)

if load_unload_ollama_models_flag():
    try:
        if tiers_cfg is None:
            tiers_cfg = load_tiers()          # reuse if already loaded
        ...
```

This pattern keeps the critical path resilient to snapshot/config failures, avoids duplicate configuration loads, and preserves the ability to restore the original environment when capture succeeds.

### Snapshot-Restore External Resource State Around Long-Running Fallible Operations

When an operation pauses, unloads, or mutates external service state for the duration of a long-running task, treat that state like a transaction:

- **Snapshot before mutating.** Capture the original external state immediately before the first side effect, not later.
- **Initialize snapshot variables to safe sentinels.** Use `config = None; snapshot = None` so downstream code can tell whether a snapshot was actually captured.
- **Make the snapshot best-effort.** If capturing the snapshot fails, log the warning and proceed; the operation should not be blocked by an inability to record state. The `None` sentinel then disables restoration.
- **Restore in `finally`, exactly once.** Restore using the same endpoint/config that produced the snapshot. Guard the restore with `if config is not None` to handle the “snapshot never happened” case safely.
- **Reuse the loaded config across the whole operation.** Loading config once and reusing it for snapshot, mutation, and restore avoids inconsistent state if configuration changes mid-run.
- **Defer expensive or side-effecting failure handling until after restoration.** Do not queue follow-up work (e.g. self-fix) while external services are still paused; restore the environment first, then process failures.

This pattern prevents resource leaks, makes recovery behavior explicit, and keeps the external environment deterministic no matter whether the main work succeeds, fails, or crashes.

### Pre-Flight Resource-Ceiling Guards at Pipeline Boundaries

Before dispatching work to a downstream AI tier, validate each planned unit of work against that tier's known hard resource limits. If a single item already exceeds the downstream context/window ceiling (before any new content is even added), fail the whole breakdown early with a clear, actionable error instead of letting the run start and stall or corrupt later.

- **Identify the source of truth for the limit** and derive the check from it: `TIER4_MAX_CONTEXT_CHARS = 24576 * 3` documents both the tier config value and why `* 3` (token→char conservative floor), pointing at the exact call that sets the real limit.
- **Check the ground truth you actually have at planning time**: only the existing file size is known before dispatch, so only flag files already over the ceiling; don't guess at diff sizes. The comment explicitly says files that would tip over after new content are *not* flagged because that data isn't available yet.
- **Fail fast at the earliest safe checkpoint**: the guard runs immediately after phase breakdown and alongside other structural guards (module import order), before any item is dispatched—so the cost is a cheap read, not a long retrying worker run.
- **Return one structured, human-actionable message** naming the offending target, its current size, the ceiling, and what to do: "breakdown must split this file's work differently or route it elsewhere."
- **Skip items the guard doesn't apply to**: git actions are excluded; nonexistent targets are skipped.

This pattern generalizes beyond file size: whenever your executor has a hard constraint (context window, time limit, RPM, memory), surface violations at the planning/breakdown boundary rather than discovering them mid-execution after expensive work has already been done.

### Pre-Dispatch Constraint Validation Against Downstream Execution Limits

When a generated plan/checklist will be executed by a resource-constrained worker, validate every item against that worker's real execution limits **before dispatch begins**, not after expensive work has started.

This diff adds a post-breakdown guard that refuses to dispatch any file item whose existing size already exceeds the Tier 4 context-window ceiling. The pattern:

- **Derive the limit from the actual downstream configuration** (`TIER4_MAX_CONTEXT_CHARS = 24576 * 3` from `tier4_worker.py`'s `num_ctx`) and document the source of truth in a comment.
- **Validate only what is knowable at this stage.** The guard checks existing file size, not the unknown future diff size, so it avoids false failures based on speculation. Non-existent targets are skipped; git items are skipped.
- **Fail fast with an actionable error.** The message names the target file, the measured size, the ceiling, and what must change ("split this file's work differently or route it elsewhere") rather than silently proceeding into a doomed task.
- **Run the guard at the completion of a generation/transformation step**, before the state is marked successful, so a bad plan is caught as a hard error instead of surfacing halfway through execution as a confusing runtime failure.

General lesson: before handing generated work to a limited downstream system, add a cheap static preflight check for the constraint that would make the work impossible. A few lines of validation can prevent an entire long-running, retry-heavy pipeline from wasting effort on a task that could never succeed.

### Non-retryable failures should bypass the retry threshold and escalate immediately

When a system uses a consecutive-failure counter to decide when to escalate, not all failures should consume the same retry budget. Some failures are *known to be permanent for the current attempt* — retrying with the same inputs will almost certainly produce the same invalid result (e.g. a code-generation guard rejected the output as oversized, a malformed/unparseable response, a content-safety rejection). Counting these as ordinary retryable failures burns attempts, delays escalation, and can stall an unattended pipeline.

The pattern is to explicitly classify such failures as **non-retryable** at the failure-handling call site, and have the failure handler apply an **effective escalation threshold of 1** for those cases. This keeps all the existing bookkeeping (recording the failure, preserving state, emitting logs) while ensuring the process escalates immediately instead of looping.

Key implementation guidance:

- Add a boolean flag/parameter to the shared failure handler, e.g. `is_oversize_failure: bool = False`.
- When the flag is true, compute `effective_threshold = 1` instead of using the configured retry threshold.
- Always record the failure in state/logs first; only the escalation decision changes.
- Use the flag only for failure classes where another identical attempt is known to be futile.
- This composes cleanly with existing retry logic: normal failures still escalate only after the configured consecutive-failure threshold.

```python
def _tier4_fail(task_id, threshold, reason, is_oversize_failure=False):
    effective_threshold = 1 if is_oversize_failure else threshold
    state = record_failure(task_id, reason)
    status = "escalate" if state["consecutive_failures"] >= effective_threshold else "build_failed"
    return {"status": status, "consecutive_failures": state["consecutive_failures"], "stderr": reason}
```

This prevents an unattended automation loop from wasting N expensive retries on a condition that retrying cannot fix.

### Classify failures as "retryable" vs. "will never succeed on retry" and escalate unrecoverable ones immediately

Some failures are not transient — retrying with the same inputs will predictably fail again (e.g., a model response truncated mid-generation because it hit a length/cap limit, or a tool that is fundamentally incompatible). These should not be fed into the normal consecutive-failure counter; they should escalate on the first occurrence.

In practice:

- Add a category/flag to the failure-handling path (e.g. `is_oversize_failure`) that overrides the retry threshold to `1`.
- Use it only for failures that indicate a structural limit, not for ordinary build errors or slow requests.
- Refuse to write partial/truncated artifacts (e.g. an unterminated code fence) even if the content guard has nothing to compare against (e.g. brand-new files). A truncated response is a failed attempt, never a fallback source.
- Log the failure reason alongside the escalation so operators can distinguish "model hit a hard output limit" from "build still broken after N attempts."

This prevents an unattended system from burning retry attempts on an unrecoverable condition, and makes the status semantics honest: `build_failed` means "a retry may help," while `escalate` means "stop retrying, this needs a different approach."

### Treat optional external backends as degraded capacity, not fatal failures

When a system can use several interchangeable external providers, one unhealthy provider must not take down the whole discovery/selection path. Treat each backend as optional capacity: catch its errors, log a warning, skip it, and continue with whatever healthy providers remain.

Add a regression test that simulates the failure mode directly:

- Monkeypatch the HTTP client (`mock.patch("httpx.get", side_effect=...)`) so the test never touches the network.
- Return a fake response with the desired status code (`401`) and implement just enough of the response interface (`raise_for_status()`, `.json()`).
- Leave unrelated URLs returning empty-but-valid responses.
- Assert three things:
  1. The operation still completes and returns a usable result (it does not raise/abort).
  2. The failed backend contributes zero results/models.
  3. The failure is surfaced as a warning, not swallowed silently.

This pattern keeps the suite offline and deterministic while locking in graceful-degradation behavior, preventing regressions where a retired token, decommissioned gateway, or misconfigured optional provider makes the whole assistant unusable.

```python
class _FakeHttpxResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self.payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload

def _fake_httpx_get(url, *args, **kwargs):
    if "openclaw" in str(url):
        return _FakeHttpxResponse(401, {"error": "unauthorized"})
    return _FakeHttpxResponse(200, {"models": [], "data": []})

with mock.patch("httpx.get", side_effect=_fake_httpx_get):
    with mock.patch("ohmyllama.catalog.log.warning") as warn:
        discovered = discover(_Cfg)

check("openclaw 401 does not abort discovery", isinstance(discovered, list), True)
check("openclaw 401 contributes zero ModelCards",
      any(c.backend == "openclaw" for c in discovered), False)
check("openclaw 401 is logged as a warning", ...)
```

General guideline: every optional integration should have an explicit “this backend failed” path, and that path should be tested with a stub that returns the exact failure it must survive.

### Make post-validation guardrails path-aware, not binary blockers

When a validation guard rejects an item, ask whether the rejection reflects a fundamental invariant or just a limitation of one execution path. Shape the guard to route around the limitation, exempt legitimate inverse operations, and return actionable remediation when the artifact type demands a different mechanism.

**Key tactics from this change:**

- **Downgrade hard failures to routing hints when an alternative path exists.** An oversized file was previously a breakdown-blocking error because Tier 4's local context window couldn't hold it. The guard now sets `skip_tier4=True` so `run_task()` routes that item to Tier 3/2's larger cloud context, and appends an explicit "split this file" instruction to the item description so the work still reduces the size.

- **Whitelist the legitimate exception.** A package split must be able to retire the original oversized flat file, so a delete/remove item whose description names the target's filename is exempt from the size-ceiling guard. The exemption is narrow: the delete verb must occur near the target filename, preventing ordinary edit items from slipping through.

- **Use guards to enforce the correct tool, not just to say "no".** Sops-encrypted files must never be drafted/patched by an AI tier because SEARCH/REPLACE on ciphertext corrupts the MAC. The guard refuses such items but tells the caller the correct shape: make it `verify_only: true` and express the change as an immutable `sops set`/`--set` shell command in `build_cmd`.

- **Don't re-run creation-time guards on resume.** Post-breakdown guards now run only when `newly_broken_down` is true. Re-running them on an already-populated breakdown would let unrelated drift (e.g. AGENTS.md growing) retroactively block a resumable run that was valid when it was created. Validation should be anchored to the moment the state was produced, not re-litigated under later conditions.

### Centralize LLM provider calls behind a shared client abstraction and normalize failure/usage outcomes

When multiple escalation tiers need to call LLM providers, don't let each tier hand-build provider-specific HTTP requests, parse provider-specific response shapes, and reimplement fallback/error handling. Instead, introduce a single client API (e.g. `llm_client.execute_llm(...)`) that accepts provider, endpoint, API key, model, prompt, and system prompt, and returns a normalized result: `(response_text, billing_type, prompt_tokens, output_tokens)`.

This diff shows the payoff:

- The tier no longer imports provider-specific helpers (`gemini_fallback`) or constructs raw `requests.post(...)` payloads.
- Provider-specific concerns (request schema, usage metadata fields like `candidatesTokenCount`, fallback-model selection) live behind the client.
- The caller receives normalized token counts and billing type instead of hardcoding `"billing": "free_tier"` or digging through `data["candidates"][0]["content"]["parts"][0]["text"]`.
- Error handling becomes consistent with the rest of the system: `except Exception` at the escalation boundary returns a normal `{"status": "error"}` result, so a transient API failure doesn't crash the entire unattended dispatch process. Previously, direct `requests.HTTPError`/connection failures could propagate uncaught and take down the orchestrator.

General guidelines:

- **Define a stable internal client contract** that hides vendor-specific API differences. Callers should only consume normalized text, usage counts, and billing metadata.
- **Catch provider failures at the orchestration boundary** and convert them into domain results (e.g. status `"error"`/`"skipped"`/`"fix_rejected"`) so the caller can decide fallback/handoff instead of crashing.
- **Keep model fallback logic centralized**; don't let each tier reimplement “try default model, then fallback chain” with raw HTTP calls.
- **Use one cost-log shape across tiers** so accounting is uniform, even when providers report tokens differently.

### Provider-Agnostic LLM Client Pattern

Centralize external LLM API calls behind a shared client abstraction so callers do not know provider-specific endpoints, auth, or response shapes. Keep provider differences at the boundary, and treat provider failures as ordinary pipeline failures rather than uncaught crashes.

- **Use one client module for all providers.** Replace ad-hoc `requests.post` + JSON parsing in each tier with a common `llm_client.execute_llm(provider=..., endpoint=..., api_key=..., model=..., prompt=...)` entry point.
- **Return canonical fields from the client.** The client should normalize provider-specific token names (e.g. Ollama's `prompt_eval_count` vs. OpenRouter's `prompt_tokens`) into one shape like `(response_text, billing_type, input_tokens, output_tokens)`. Cost/reporting code then has a single schema across all tiers.
- **Resolve provider-specific config defensively.** Use `tier4.get('provider', 'ollama')`, `tier4.get('endpoint')`, and `secrets.get(tier4.get('api_key_secret', 'open_router_api_key'))` so old configs and new configs keep working without hard-coding a provider name in the worker.
- **Log dynamically, not by hard-coded provider.** A log line like `"Tier 4 (%s/%s) drafting %s"` with the configured provider name makes multi-provider runs traceable without code changes.
- **Catch both expected and unexpected request failures.** Catch `requests.RequestException` first for transport/HTTP errors, then a broad `Exception` for anything else. Convert both into the same failure-result object (e.g. `_tier4_fail(...)`) so an unattended/tiered pipeline can retry or escalate instead of crashing mid-run.
- **Don't let an external LLM outage become a hard crash.** Modeling provider errors as build/verification failures lets the existing consecutive-failure threshold and escalation state machine handle the outage naturally.

This pattern keeps agent/worker code focused on task logic while making provider swaps, multi-provider support, and consistent cost accounting a shared concern.

### Treat fallback services as first-class config blocks, not code branches

- Keep a single source of truth for every tier and fallback route in one central config file. Scripts should read model names, endpoints, API-key secret references, and escalation rules from that file rather than embedding them in code.
- Add a dedicated config block for each fallback/alternative service (`gemini_fallback`, `ollama_fallback`) alongside the primary tier blocks. A fallback is a distinct deployment decision: it has its own endpoint, model, and credential secret, and should be independently maintainable.
- Separate *normal-path* tier config from *degraded-path* fallback config. The primary block describes what a tier does by default; the fallback block describes what to use when the primary is unavailable. This keeps changes additive and low-risk: adding a fallback should not require rewriting existing tier definitions.
- Capture operational constraints and rationale in the config itself: `automatable` flags, quota/pricing notes, verified dates, and fallback ordering. This makes the failure-handling policy auditable and prevents future contributors from silently reversing a deliberate decision.
- Use logical names in fallback chains and map them to concrete services in config. This lets orchestration code stay generic (`try fallback chain`, `read next fallback from config`) while all provider-specific details remain centralized.

**Consequence:** When a new fallback provider is discovered or verified, it can be added as a new config stanza with full context, and every script that depends on the config automatically sees the updated failure-handling path without code changes.

### Removing Fallback Logic: The Danger of Silent Resilience Loss

When you remove a fallback or error-handling path from a codebase, you must audit every caller for now-unhandled failure modes and update signatures for newly-dead parameters. In this change, the entire multi-provider fallback chain was deleted from `execute_llm`, but the public function signature still advertises `is_tier4: bool = False` — a parameter that now does nothing. Any caller that previously relied on automatic failover (e.g., tier-4 jobs routing to Ollama when the primary CLI failed, or non-tier-4 jobs falling back to DeepSeek/Gemini) will now get an unhandled exception on primary failure instead of a graceful fallback.

**Actionable rules:**

1. **Before deleting a fallback path**, enumerate all callers and confirm they either (a) handle the exception themselves, or (b) are being updated in the same change to do so. A silent removal of resilience is a common source of production outages.
2. **Remove dead parameters immediately.** The `is_tier4` argument is now vestigial; leaving it in the signature misleads future maintainers into thinking tier-based routing still exists.
3. **If fallbacks are intentionally moved elsewhere** (e.g., to a higher-level orchestrator), add a comment in the simplified function pointing to the new location, rather than leaving the simplification unexplained.
4. **Consider whether the fallback was removed for good reason** (e.g., masking configuration errors, adding latency, or creating confusing billing attribution). If so, document that decision in the module docstring or a design doc so the deletion doesn't look like an oversight.

### Fail-Fast on Infrastructure Failures vs. Legitimate Escalation in Multi-Tier Pipelines

In a multi-tier escalation pipeline (e.g., Tier 4 → Tier 3 → Tier 2 → Tier 1 → human), a critical distinction must be made between two kinds of tier "failure":

1. **Legitimate non-fix**: The tier ran successfully, applied a patch, but the build still failed — or it explicitly declined to fix. This is a *signal to escalate*; the next tier should try.

2. **Infrastructure/dependency failure**: The tier couldn't even run — e.g., Ollama connection timeout, API returned an `"error"` status indicating the tool itself is broken. This is *not* a signal to escalate; lower tiers depend on the same infrastructure and can't help. The pipeline should **crash immediately** instead of burning budget on doomed fallback attempts.

#### The Anti-Pattern (Before)

```python
except Exception as e:
    log.warning("Tier 4 raised %s; escalating", e)
    record_failure(task_id, str(e))
    break  # silently fall through to Tier 3
```

And for lower tiers:

```python
result = tier3_escalate(...)
# No check for result["status"] == "error" — just continues to check fix_rejected / fix_applied
```

This means an Ollama outage causes Tier 4 to fail, then Tier 3 (DeepSeek cloud) gets tried, then Tier 2 (Gemini), then Tier 1 (Claude), then human handoff — wasting enormous time and money when the real problem is a broken local Ollama connection that none of the other tiers can fix either.

#### The Correct Pattern (After)

```python
except Exception as e:
    # Infrastructure failure — crash, don't escalate
    log.warning("Tier 4 raised %s; crashing pipeline", e)
    record_failure(task_id, str(e))
    raise  # fail fast
```

And for each escalation tier:

```python
result = tier3_escalate(...)
if result.get("status") == "error":
    raise RuntimeError(f"Tier 3 failed: {result3.get('reason')}")
```

#### Why This Matters

- **Escalation is for fix-attempts, not for broken tools.** Lower tiers are *different models/tools*, not redundant copies of the same broken one. If Tier 4's *runtime* is broken (Ollama down), Tier 3's cloud API is unaffected — but if the error is about the *task itself* (e.g., "cannot parse target file"), crashing is wrong. The key is distinguishing tooling failures from task failures.
- **Silent fallback hides systemic outages.** If Ollama is down for 10 minutes, the old code would generate a cascade of useless escalation attempts and eventually a confusing human handoff saying "unresolved after Tier 4 → Tier 3 → Tier 2 → Tier 1." The new code crashes immediately with a clear "Tier 4 raised <Ollama timeout>; crashing pipeline" — much easier to diagnose.
- **`"error"` status vs. `"fix_rejected"` status.** The escalation functions return `"error"` when *the tool itself failed to run* (network, auth, timeout) and `"fix_rejected"` / `"fix_applied"` when the tool ran but the outcome was a legitimate non-fix or a fix. Only the latter should trigger escalation. The added `raise RuntimeError(...)` guards enforce this contract.

#### Rule of Thumb

> **Catch exceptions and `"error"` statuses from a tier only when you can do something useful with them (retry, alert, degrade gracefully). Otherwise, let them propagate. A pipeline that silently falls through every tier on any failure is not resilient — it's just slow to report a broken environment.**

### Pre-Flight Validation Before Long-Running Operations

When starting a long-running, expensive, or stateful operation (like a dispatch that may run for hours unattended), validate all external dependencies **before** doing any real work — and place that validation inside the same `try/except/finally` block that handles resource cleanup and crash recovery.

**Why this matters:** Without the pre-flight check, a dispatch could spend minutes (or hours) breaking down a plan, executing phases, and mutating run state — only to discover at some later point that the LLM backend is unreachable. That's wasted time, wasted money, and messy partial state to clean up. Failing fast at the start is strictly better.

**How to apply it:**

1. **Probe early, probe cheaply.** Call a lightweight health-check function (`llm_client.probe_models()`) that verifies connectivity/auth to all configured LLM endpoints before any real work begins.

2. **Keep the probe inside the existing crash-recovery `try` block.** In the diff, `probe_models()` is placed inside the same `try` that wraps `_breakdown_and_dispatch(state)`. This means:
   - A probe failure is caught by the same `except` handler that captures crashes, saves a bug report, and queues a self-fix — consistent failure semantics.
   - The `finally` block (which restores Ollama state and resumes paused services) still runs, so no resources leak just because the probe failed.

3. **Don't let validation block resource teardown.** The probe must be inside the `try`, not before it. If the probe hangs or throws, the `finally` still fires. This is the same discipline as putting all cleanup in `finally` — the validation step is just another operation that can fail, and it must not bypass the cleanup path.

**General rule:** Before any operation that (a) takes significant time, (b) muts persistent state, or (c) acquires external resources — run a quick dependency health check, and put it inside the same `try/except/finally` that handles cleanup. Fail fast, clean up reliably, and let the existing crash-recovery infrastructure handle the failure uniformly.

**In this specific change:**
- `llm_client.probe_models()` was added as the first line inside the `try` block of `cmd_dispatch`, before `_breakdown_and_dispatch(state)`.
- This means a dead LLM backend is detected immediately, the crash is captured via `self_fix.capture_crash()`, and the `finally` block restores Ollama state and resumes resource-guarded services — all before any plan breakdown or phase execution begins.

### Validate Input Types Before Parsing — Defensive Input Handling for Untrusted Data

When a function receives data from an external/untrusted source (e.g., a model's raw output, user input, an API response), **validate the type and non-emptiness before any string operations**, even if the calling code's type hints suggest the data should already be a string.

**Applied here:** `apply_edit_blocks()` was documented to take a `response_text: str`, but a real-world failure surfaced where the caller (`cmd_dispatch`) passed `None` or a non-string value, causing an `AttributeError` on `.strip()` deep inside parsing. Uncaught, this would crash the pipeline with an opaque stack trace rather than a controllable failure.

**Pattern:**
```python
def apply_edit_blocks(original: str, response_text: str) -> tuple:
    # First line: guard against invalid types with a clear, actionable error
    if not isinstance(response_text, str) or not response_text.strip():
        return None, "model returned no usable text (None or empty)"
    # ...rest of parsing is now safe to assume a non-empty string
```

**Key lessons:**
1. **Type hints are documentation, not runtime guarantees** — especially at system boundaries where another module or an external service (like an LLM) produces the value.
2. **Guard at the entry point** of every parsing/processing function that operates on untrusted input; don't let an `AttributeError`/`TypeError` become the failure mode.
3. **Return a domain-meaningful error tuple** (here `(None, error_message)`) so the caller can retry, escalate, or log — never propagate a raw exception that crashes the whole operation.
4. **Check `strip()` on strings too** — an empty or whitespace-only string is as unusable as `None` for parsing purposes, and the same guard handles both.
5. This costs one line now and prevents a class of subtle, hard-to-reproduce bugs (e.g., intermittent model failures returning `None`) from becoming production incidents with unhelpful stack traces.

**General rule:** *Never assume your inputs match their declared types — validate at the boundary, fail gracefully with a descriptive message, and let callers decide how to handle the failure.*

### Handle Empty or Structured LLM Responses Explicitly Before Processing

When a language model API can return either a plain string or a structured object (and especially when it can return an empty/null response), always:

1. **Normalize the response into a consistent shape before processing.** Check whether the response is a dict and extract fields explicitly (`content`, `finish_reason`, `reasoning_content`) rather than assuming the raw result is directly usable. This makes the downstream code independent of the underlying provider's response format.

2. **Treat "no content" as a distinct, first-class failure state.** Do not let an empty string, `None`, or a dict with empty content flow through to text-processing functions like edit-block parsers or code extractors. A model that returns nothing is a failed attempt — short-circuit it with a clear rejection reason, log the diagnostics (`finish_reason`, whether reasoning content was present) to aid debugging, and still record cost/usage data (cost accounting should not be skipped just because the response was unhelpful).

3. **Destroy ambiguous failure modes at the boundary.** An empty or malformed response should never reach code that assumes content exists — otherwise you risk subtle behavior like passing `None` to string operations, or writing a truncated/incomplete file that only fails at build time. Define the contract: if content is falsy → reject immediately; otherwise, proceed with the normalized text.

4. **Propagate structured metadata** (e.g., `finish_reason`) into logs and return values so that repeated empty responses can be diagnosed (e.g., token limits, refusal, reasoning-only responses) without needing to replicate the API call.

This pattern is especially important in resilient multi-tier systems where the caller must not only handle expected failures but also degrade gracefully when the LLM returns surprising shapes.

### Normalize External CLI/API Failures into a Single Exception Family

When integrating multiple backend providers (local CLIs, REST APIs, SaaS services) behind a unified facade, normalize all failure modes into the **same exception type** your existing fallback/retry logic already handles.

**Pattern:**
- For subprocess-based providers, raise `subprocess.CalledProcessError` for **every** failure class — non-zero exit code, invalid JSON stdout, or unexpected status/response shape.
- Embed diagnostic details (status, stderr tail, raw stdout snippet) in the exception message or args so downstream handlers can log context without re-parsing or crashing.
- Add a shared `_CLI_TIMEOUT` constant to prevent hangs from becoming indefinite blocking calls, and pass it consistently to all subprocess invocations.

**Why:**
- Callers (e.g., per-tier fallback chains) already catch a known exception family. Introducing new exception types per backend forces callers to be updated — a fragile and easy-to-miss requirement.
- Embedding context in the exception preserves debuggability without requiring the fallback handler to know provider-specific internals.

**Example:**
```python
if result.returncode != 0:
    raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)

try:
    data = json.loads(result.stdout)
except json.JSONDecodeError as e:
    raise subprocess.CalledProcessError(0, cmd, result.stdout, result.stderr) from e

if data.get("status") != "SUCCESS":
    raise subprocess.CalledProcessError(0, cmd, result.stdout, f"status={data.get('status')!r} stderr_tail={result.stderr[-200:]!r}")
```

**Lesson:** A facade's contract should be defined by its **exception types**, not just return values. When adding a new backend, map its failure modes onto the existing exception taxonomy so upstream reliability logic (retries, fallbacks, circuit breakers) works unchanged.

### Generalize Provider Dispatch Instead of Hardcoding Provider Names

When code branches on a provider identifier (e.g., `provider == "openrouter"`), treat the provider as a **configurable value** and build the dispatch logic around the provider's **capabilities**, not its literal name. If you hardcode a specific provider in an `if/else`, you silently exclude any other provider that shares the same interface contract — and you make future provider additions require editing the conditional instead of just the config.

In this diff, the original code had:
```python
if provider == "openrouter":
    # use execute_llm
else:
    # assume google
```

The problem: any provider other than `"openrouter"` fell through to the Google branch — even if it was another non-Google provider (e.g., Anthropic, a local proxy) that should have used the `execute_llm` path. The fix inverts the check:
```python
if provider == "google":
    # google-specific call
else:
    # generic execute_llm path for ANY non-google provider
```

This is more than a cosmetic reordering. It changes the **default behavior** from "assume Google unless I say openrouter" to "use the generic LLM client for any unknown provider, and treat Google as the special case."

**General rules to extract:**
1. **Prefer negative/positive capability checks over provider-name checks.** Ask "does this provider need the special path?" rather than "is this provider X?"
2. **When you do branch on a provider name, make the *more common* / *more generic* path the `else`.** The fallback should be the path that works for the broadest set of inputs, not the narrowest.
3. **Never silently default to a specific vendor's behavior for an unrecognized value.** An unknown provider should either error loudly or go to a generic implementation — never to a path that assumes a different vendor's API contract.
4. **Reuse the config value in the dispatch.** The diff not only reorders the branch; it also passes `provider=provider` into `execute_llm()` instead of hardcoding `"openrouter"`, so the same generic path correctly forwards whatever provider was configured.

This is a small, surgical fix, but the pattern is universal: **when you find yourself special-casing a vendor, invert the logic so the special case is explicit and everything else gets the generic, provider-agnostic treatment.**

### Cost-Aware Gradual Escalation

**Context:**
When an automated task (like documentation generation or code drafting) fails with its primary model, it is standard practice to route the task through a fallback chain of alternative models or providers. 

**Pattern/Lesson:**
Avoid binary "cheap local vs. most expensive remote" fallback transitions. Instead, implement a **gradual escalation chain** that steps through intermediate capability and cost tiers. 

In this configuration change, a mid-tier fallback (`fallback_agy`) was strategically inserted between the secondary local fallback (`fallback_local`) and the premium, high-cost remote fallback (`fallback_openrouter`). 

**Benefits:**
- **Cost Optimization:** Tasks that are slightly too complex for small local models can often be resolved by mid-tier models, preventing unnecessary spend on top-tier, expensive APIs.
- **Resilience:** Introducing diverse providers and models into the fallback chain increases the overall reliability of the pipeline in the event of rate limits or provider downtime.
- **Resource Efficiency:** Reserves the most capable (and most expensive) models as true last resorts rather than immediate second choices.

### Distinguish Timeouts from Generic Errors

When wrapping operations that interact with external services or shell commands, explicitly catch specific timeout exceptions (e.g., `subprocess.TimeoutExpired`) before falling back to a blanket `Exception` catch block. 

Distinguishing a timeout from a general failure allows upstream logic to apply specific handling—such as implementing retry backoffs or reporting a distinct `timeout` status rather than a generic `error`. This improves system resilience and makes debugging much clearer when long-running external processes or CLI-backed providers hang.

### Graceful Degradation via Soft Escalation

In multi-tier fallback or escalation pipelines (such as LLM routing or service architectures), distinguish between **fatal structural errors** and **transient failures** (like network timeouts). 

When a specific tier encounters a transient issue such as a timeout, handle it by logging the issue and allowing the system to "soft escalate" (fall through) to the next available tier, rather than raising a hard exception that crashes the entire pipeline. Hard exceptions should be reserved for unrecoverable state errors where subsequent tiers are also guaranteed to fail.

### Asymmetric Critic-Worker Pattern
In tiered LLM pipelines, decouple generation from verification by routing the output of smaller, local models to larger, more capable models for evaluation. By configuring a high-volume "worker" tier (e.g., a fast, local model used for code drafting or compilation loops) to be evaluated by a smarter "critic" tier (e.g., a large frontier model), you optimize for both speed and cost without sacrificing quality. The cheaper model handles the bulk generation, while the expensive model is reserved solely for high-leverage review and critique.

### Config-Driven Evaluator Scoping

When introducing an advisory evaluation or critique step (such as a design judge or code reviewer) to a pipeline with multiple different workers or tiers, do not run the evaluation unconditionally on all successful outputs. 

Instead, gate the evaluator behind a centralized configuration block that includes:
1. A global `enabled` toggle to easily turn the feature on or off.
2. An explicit list of actors, tiers, or resolution methods it applies to (e.g., `applies_to_tiers`).

**Why:** Different tiers or workers (e.g., a documentation generator vs. a code refactoring model) have different output characteristics. Running a code-design judge on documentation or a human-provided fallback is wasteful and can lead to spurious failures. Centralizing this check ensures that new tiers bypass the evaluator by default until explicitly opted in.

**Example:**
```python
def _design_judge_applies(resolved_by: str | None, critique_cfg: dict) -> bool:
    """Gates the design judge to specific tiers based on configuration."""
    if not critique_cfg.get("enabled", False):
        return False
    return resolved_by in critique_cfg.get("applies_to_tiers", [])

# ... in the main execution loop ...
if result["status"] == "success" and is_regular_item and _design_judge_applies(result.get("resolved_by"), critique_cfg):
    result = _run_design_judge(...)
```

### Exhaustive Testing for Configuration-Driven Gates

When implementing a gating or filtering function that determines whether a feature should run based on configuration (e.g., feature flags, applicability lists), systematically test all logical branches and edge cases. Instead of combining multiple checks into a single test, write separate, focused unit tests for each scenario.

**Key Scenarios to Cover:**
- **Happy Path:** The feature is enabled, and the input meets the required conditions (e.g., the value is present in the applicability list).
- **Master Switch Off:** The feature is explicitly disabled in the configuration, regardless of other conditions.
- **Condition Not Met:** The feature is enabled, but the input does not match the allowed criteria (e.g., the value is missing from the applicability list).
- **Missing Configuration Keys:** The configuration dictionary or object is missing expected keys (e.g., missing the applicability list entirely).
- **Null or Invalid Inputs:** The function receives `None` or unexpected input types.

**Example (from the diff):**
```python
class TestDesignJudgeAppliesGate(unittest.TestCase):
    # Master Switch Off
    def test_disabled_critique_returns_false(self):
        config = {"enabled": False, "applies_to_tiers": ["tier_3"]}
        self.assertFalse(dispatcher._design_judge_applies("any", config))

    # Happy Path
    def test_tier_in_list_returns_true(self):
        config = {"enabled": True, "applies_to_tiers": ["tier_3", "tier_4"]}
        self.assertTrue(dispatcher._design_judge_applies("tier_4", config))

    # Condition Not Met
    def test_tier_not_in_list_returns_false(self):
        config = {"enabled": True, "applies_to_tiers": ["tier_3", "tier_4"]}
        self.assertFalse(dispatcher._design_judge_applies("tier_5", config))

    # Missing Configuration Keys
    def test_missing_applies_to_tiers_key_returns_false(self):
        config = {"enabled": True}
        self.assertFalse(dispatcher._design_judge_applies("any", config))

    # Null or Invalid Inputs
    def test_none_resolved_by_returns_false(self):
        config = {"enabled": True, "applies_to_tiers": ["tier_3"]}
        self.assertFalse(dispatcher._design_judge_applies(None, config))
```

### Testing Conditional Side-Effects Based on Resolution Paths

When a pipeline or orchestrator can resolve a task through multiple distinct paths (e.g., escalating fallback tiers, automated vs. manual resolution), downstream side-effects like design evaluation, telemetry, or pattern extraction often need to be selectively skipped or executed depending on the resolution path taken.

**Pattern:**
Write paired explicit tests to verify that downstream hooks (often expensive or stateful operations like LLM design evaluations) are correctly bypassed or triggered based on the specific metadata of the successful resolution.

**How to Apply:**
1. **Mock the Executor:** Mock the core execution step (e.g., `run_task`) to return a synthetic success payload that includes a resolution path identifier (e.g., `resolved_by: "tier_5"` vs `resolved_by: "tier_4"`).
2. **Mock the Hooks:** Mock the downstream side-effect functions (e.g., `evaluate_design`, `extract_pattern`).
3. **Test the Bypass:** For paths that should skip the side-effect (like an emergency tier or a manual override), assert `assert_not_called()` on the mocked hooks.
4. **Test the Execution:** For standard paths, write a sibling test asserting `assert_called_once()` to ensure normal post-processing still occurs.

By explicitly testing the boundary where execution metadata dictates subsequent workflow steps, you ensure that architectural rules (like "Tier 5 resolutions bypass the design judge") remain strictly enforced as pipeline complexity grows.

### Configuration-Driven Provider Selection

When defining service integrations, fallback chains, or strategy patterns (e.g., LLM routing), avoid hardcoding the primary provider or its configuration parameters in the execution logic. Instead, extract the provider identity and its capabilities into a centralized configuration object.

**Why this matters:**
Hardcoding a specific provider (like `"ollama"`) tightly couples your execution logic to a single implementation, requiring code changes to test new providers, switch environments, or pass new API arguments. By reading the provider name and optional arguments (such as an `"effort"` tier) from configuration, the system can seamlessly switch implementations without altering the core pipeline.

**Example Application:**
Instead of hardcoding a provider name in a fallback chain:
```python
# Bad: Hardcoded provider assumption
providers = [
    {"name": "ollama", "model": models_cfg.get("primary", "default-model")}
]
```

Read the provider and its provider-specific arguments from configuration, falling back to a sensible default:
```python
# Good: Configuration-driven with defaults
providers = [
    {
        "name": lib_config.get("provider", "ollama"),
        "model": models_cfg.get("primary", "default-model"),
        "effort": lib_config.get("effort"),
    }
]
```

### Intent-Guarded Fast Paths (Fail-Open)

**Context:** When implementing an optimization or "fast path" that skips expensive operations (such as a model call or complex computation), it can be risky if the optimization is applied to the wrong context. 

**Pattern:** Use heuristic intent filtering—such as scanning unstructured input for a specific set of keywords or phrases—as an early-exit guard. If the input does not strongly match the expected heuristic, "fail open" by immediately falling back to the standard, unoptimized execution path.

**Example:**
```python
_STALENESS_QUESTION_PHRASES = [
    "stale",
    "out of date",
    "up to date",
    # ...
]

def should_skip_expensive_call(task_description: str) -> tuple[bool, str]:
    task_lower = task_description.lower()
    
    # 1. Intent Guard: If the intent doesn't match, fail open immediately.
    if not any(phrase in task_lower for phrase in _STALENESS_QUESTION_PHRASES):
        return (False, "Intent not matched -- skipping fast-path, falling back to standard execution")
        
    # 2. Proceed with fast-path optimization logic...
    # ...
```

**Benefits:**
*   **Safety:** Prevents aggressive optimizations from causing false positives and breaking unrelated tasks.
*   **Performance:** Cheap substring checks effectively guard more complex or expensive logic from running unnecessarily.
*   **Robustness:** The system degrades gracefully to the default, safe behavior whenever the user's intent is ambiguous.

### Adding to a Discriminated Union Registry

When adding a new variant to a Pydantic discriminated union that also utilizes explicit registries for introspection, you must follow a strict registration checklist. Simply defining the new model class is insufficient.

In this codebase pattern, adding a new type (e.g., a new `Intent`) requires exactly **four updates** in the same file:

1.  **Define the Model Class:** Create the subclass with its specific `Literal` discriminator field (e.g., `kind: Literal["add_email_rule"]`).
2.  **Update the Union Type:** Append the new class to the explicit `Union` definition (`_AnyIntent`) so Pydantic knows it is a valid resolution target for the discriminator.
3.  **Update the Discriminator Tuple:** Add the string literal to the list of known keys (`INTENT_KINDS`).
4.  **Update the Introspection Dictionary:** Map the string literal to the new class in the models registry (`INTENT_MODELS`).

**Why this matters:** 
While Pydantic uses the `Union` type for its own runtime validation and payload parsing, other parts of the system (such as LLM tool schema generators) often rely on the explicit dictionaries (`INTENT_MODELS`) to introspect available fields without having to deconstruct complex `Annotated` or `Union` typing internals. Missing any of these four steps will lead to either runtime validation crashes or silent parser omissions.

### [Ensure Directory Existence Before File Operations]
When dynamically creating or appending to files within a nested directory structure, always ensure the parent directories exist to prevent `FileNotFoundError`s. The standard library's `pathlib.Path` provides a concise and safe way to handle this using `.mkdir(parents=True, exist_ok=True)` immediately before opening the target file.

**Example from code:**
```python
import pathlib

# Safely create the target directory and any intermediate parent directories
pathlib.Path("10-Memory/Rules/").mkdir(parents=True, exist_ok=True)

# Confidently write or append to the file knowing the path exists
with open("10-Memory/Rules/EmailRules.md", "a") as f:
    f.write(intent.rule_text + "\n")
```

### Intent-Based Worker Execution (Command Pattern)

**Pattern Description:**
When triggering background tasks or workers from adapters (like UI callbacks or webhooks), avoid ad-hoc method invocations that require reflection (e.g., checking if a `run` method exists or if it's asynchronous). Instead, encapsulate the request data into a strongly-typed `Intent` (or Command) object and pass it to a callable worker with a unified interface.

**Before:**
```python
# Ad-hoc, fragile invocation relying on reflection and specific method signatures
worker = MarkMailReadWorker()
if hasattr(worker, "run") and asyncio.iscoroutinefunction(worker.run):
    await worker.run(msg_id)
elif hasattr(worker, "run"):
    await asyncio.to_thread(worker.run, msg_id)
```

**After:**
```python
# Clean, uniform invocation using the Command pattern
from semai.core.intents import MarkMailRead

worker = MarkMailReadWorker()
intent = MarkMailRead(kind="mark_mail_read", msg_id=msg_id)
await worker(intent)  # Worker implements __call__(self, intent: Intent)
```

**Key Benefits:**
- **Uniform Interface:** All workers share a standard execution signature (e.g., `__call__`), completely eliminating the need for `hasattr` or `iscoroutinefunction` checks in the caller.
- **Extensibility:** If a worker needs more context (e.g., user ID, timestamp), you simply add fields to the `Intent` object rather than mutating the method signatures across multiple worker classes.
- **Decoupling:** The adapter (e.g., Telegram bot) is decoupled from the worker's implementation details. It only needs to know how to construct the intent.
- **Type Safety & Validation:** `Intent` objects (especially if built with Dataclasses or Pydantic) validate their own state, keeping data validation logic out of the adapter layer.

### Gate High-Impact Agent Actions Behind User Approval

When building action registries for automated agents or workflows, strictly differentiate between safe (read-only or low-impact) actions and high-impact (destructive or mutating) actions. 

Actions that modify external state, alter configurations, or perform destructive operations—such as adding email routing rules, trashing emails, running terminal commands, or modifying calendars—should be gated behind explicit user approval (e.g., using `register_approval_required`). Conversely, safe operations like fetching data, querying lists, or retrieving contexts can be registered to execute autonomously.

**Example:**
```python
# Safe, read-only action: can execute autonomously
registry.register("list_mail", ListMailWorker(settings))

# High-impact, state-mutating action: must require user approval
registry.register_approval_required("add_email_rule", AddEmailRuleWorker(settings))
```

### Dependency Injection for Protocol Adapters

When building protocol adapters, webhooks, or event listeners (such as a Telegram or Slack bot adapter), avoid hardcoding or globally importing the central message dispatcher. Instead, inject the dispatcher as a dependency through the constructor.

**Why it matters:**
- **Separation of Concerns:** The adapter remains strictly focused on protocol-specific mechanics (parsing payloads, making API calls, handling retries) while delegating all core business logic and command routing to the dispatcher.
- **Testability:** Injecting the dependency allows you to pass a mock or dummy dispatcher when unit testing the adapter. This makes it trivial to verify that the adapter correctly formats and forwards incoming messages without standing up the entire application core.
- **Avoids Circular Imports:** Adapters often need to trigger core application logic, and the core application often needs to send outbound messages through the adapter. Injecting dependencies at initialization prevents import cycles.

**Example:**
```python
class TelegramAdapter:
    # Inject the dispatcher dependency alongside config and state storage
    def __init__(self, cfg, store, dispatcher):
        self.cfg = cfg
        self.store = store
        self._dispatcher = dispatcher  # <--- Injected dependency

    async def _handle_message(self, upd: dict) -> None:
        text = upd.get("message", {}).get("text", "")
        # Delegate business logic to the injected dispatcher
        result = await asyncio.to_thread(self._dispatcher.dispatch, text)
        await self._send(chat_id, result.message)
```

### Approval Gates for Mutating Agent Actions
When designing worker architectures for AI agents, operations that produce side effects (like writing to a file, database, or memory vault) should use a two-step approval process rather than executing immediately. 

By splitting the worker into `propose(intent)` and `execute(action)` phases:
1. **Validation**: The `propose` phase can sanitize and validate inputs (e.g., bounds checking string lengths, ensuring data isn't empty) before asking for approval.
2. **Safety**: A `ProposedAction` can be surfaced to the user or an automated policy gate for explicit approval, preventing malformed, hallucinated, or runaway writes.
3. **Execution**: The `execute` phase operates only on pre-validated payloads, ensuring that when the side-effect finally occurs, the data is safe, approved, and correctly structured.

### Explicit Approval for State-Mutating Workers

When registering workers that perform state-mutating, destructive, or consequential actions (such as writing data, modifying files, or sending external requests), use `registry.register_approval_required()` instead of `registry.register()`. 

This routes the intent through an authorization or human-in-the-loop approval gate, ensuring sensitive operations are not executed automatically without appropriate oversight. Conversely, use `registry.register()` only for read-only or harmless actions (e.g., `recall_memory`, `list_mail`).

### Restrict Memorization of Retrieved Data (Prevent Tool-to-Memory Leakage)

**Context:**  
Agentic systems often feature both retrieval tools (e.g., reading emails, calendars, or documents) and long-term memory tools (e.g., saving facts or notes). A common failure mode occurs when an agent retrieves transient information using a read tool and then spontaneously decides to permanently store it using the memory tool. This creates redundant, duplicated, and potentially stale data in the user's long-term memory, or pollutes it with information that already belongs to another system of record.

**Solution:**  
Enforce mutual exclusivity between memory-writing tools and other data-gathering tools within a single agent invocation or reasoning loop. If the agent attempts to propose or write a fact to memory, verify that no other tools have been called during the current session. If other tools have been called, refuse the memorization request.

**Example (Python):**
```python
if tool_kind == "remember_fact":
    # Check if any other tools were called during this agent session
    other_tools = [name for name in agent.called_tools if name != "propose_remember_fact"]
    if other_tools:
        return f"REFUSED: Cannot remember facts after calling other tools. (Tools called: {other_tools})"
```

**Benefits:**
- **Prevents Stale Data:** Ensures transient states (like today's calendar events or emails) aren't saved as permanent facts.
- **Reduces Duplication:** Prevents the agent from unnecessarily copying data from one system of record into its own memory bank.
- **Enforces Explicit Intent:** Guarantees that memorization only happens when it is the primary and sole intent of the user's request, unprompted by other retrieved context.

### Human-in-the-Loop Action Approval Workflow

When integrating autonomous agents into an asynchronous task orchestration system, agents may propose actions (such as tool calls or system modifications) in addition to generating textual answers. To execute these safely, implement a suspension and approval pattern rather than ignoring the proposals or executing them blindly.

**Pattern:**
1. **Inspect the Full Result:** Rather than immediately extracting and returning an agent's string response, capture the entire result object.
2. **Detect Proposed Actions:** Check if the agent's result contains actionable items (e.g., `result.proposals`).
3. **Persist and Suspend:** If proposals are found:
   - Register the proposed action in a stateful approval store to generate a tracking record with the action's payload and description.
   - Transition the active task into an "awaiting approval" state, linked to the new approval record.
   - Return early from the handler to suspend execution.
4. **Defer Completion:** Allow an out-of-band process (like a human-in-the-loop confirmation UI) to review the payload, approve/reject it, and subsequently resume the orchestration flow.

This ensures safe, trackable execution of agent-driven side effects while maintaining non-blocking asynchronous task progression.

### Secure File Access via Root Narrowing

When implementing file ingestion or document reading (e.g., for RAG systems or file uploads), avoid using general-purpose file readers that lack path restrictions. Instead, delegate file operations to dedicated workers or components that enforce "allowed-roots narrowing." 

**Why it matters:**
*   **Security:** Intrinsically prevents path traversal vulnerabilities (e.g., `../../../etc/passwd`) and unauthorized access to sensitive system files.
*   **Isolation:** Ensures that operations on external files only occur within explicitly permitted sandbox directories.
*   **Centralized Policy:** Moving access control into a dedicated worker ensures that all file ingestion flows abide by the same security boundaries, rather than relying on individual callers to remember to validate paths.

**Implementation Pattern:**
Instead of a generic file reader (`DocumentIngester.read(path)`), use a structured command or intent (`IngestDocument(path)`) processed by a worker that validates the path against a set of allowed roots before attempting to read or process the file.

### Keep Handwritten Test Fakes Synchronized with Real Interfaces

When you use handwritten fake classes (like `FakeAgentResult`) to simulate dependencies in unit tests, you create a maintenance burden: these fakes must be manually updated whenever the real interface changes or when the code under test starts accessing new attributes. 

In this change, a `proposals = []` attribute had to be added to the `FakeAgentResult` mock because the production code started expecting that field on the result object, which would otherwise cause an `AttributeError` during the test run.

**Best Practice:**
To avoid the fragility of manually maintaining the shape of fake objects, prefer using Python's built-in mocking tools with strict interface enforcement, such as `unittest.mock.create_autospec` or `Mock(spec=RealClass)`. These tools automatically ensure your mock matches the real object's signature and attributes, preventing situations where your test suite's mocks drift from the actual production interfaces. If you must use handwritten fakes, ensure they are meticulously updated across the test suite whenever the underlying data models or return types are extended.

### Programmatic Instantiation of Semantic Intents

When manually constructing intent objects (such as `IngestDocument`) to bypass the NLP pipeline and invoke workers directly, you must ensure that standard base fields normally populated by the natural language router are provided. 

When faking an intent hit programmatically:
- Provide the required intent identifier (e.g., `kind="ingest_document"`).
- Provide a synthetic confidence score (e.g., `confidence=1.0`).
- Supply a fallback for the original query (e.g., using a filename or task description for `raw_utterance`) to prevent downstream validation errors.

Additionally, always ensure you are accessing the standardized response fields (e.g., using `result.message` instead of `result.text`) when extracting data from the returned worker result object.

### Actionable Error Messages for LLM Tool Calls

When returning an error or refusing a tool call from an LLM, do not return brief, cryptic error codes (e.g., `REFUSED: [list]`). LLMs rely on text to understand their environment, so a short error often leads to confusion, repeated failed attempts, or hallucinations.

Instead, return a highly descriptive, actionable error message that includes:
1. **The Rule**: Explain the specific invariant or rule that was violated (e.g., "a fact may only be proposed from what the user said directly").
2. **The Context**: Explain *how* the current state violates that rule (e.g., "you have already called [other tools] this turn").
3. **The Corrective Action**: Tell the agent exactly what it should do next (e.g., "Answer the question instead.").

By explaining *why* the action failed and *what* to do next, you steer the agent directly back onto the desired path without needing extra code to handle retry loops.

### Update Deployment Configurations When Extracting or Renaming Entrypoints

When refactoring a command-line application—such as extracting a subcommand (e.g., `omll telegram`) into a standalone binary (e.g., `semai-telegram`) or simply renaming an executable—it is critical to update all related deployment artifacts. 

**Best Practices:**
1. **Update Execution Paths:** Ensure directives like `ExecStart` in systemd unit files, entrypoints in Dockerfiles, or script invocations point to the new binary path.
2. **Update Inline Documentation:** Synchronize comments, descriptions, and manual installation instructions within the configuration files to reflect the new nomenclature. Leaving stale names in comments can cause confusion for operators or developers during future maintenance.

### Fast CLI Subcommand Dispatch with Lazy Imports

When building Python CLIs with multiple subcommands using `argparse`, you can keep startup times fast and dispatch logic clean by combining `set_defaults` with lazy imports. This is especially important for tools where some commands load heavy dependencies (like web frameworks, ML models, or UI libraries).

**1. Bind handler functions directly to subcommands:**
Use `.set_defaults(fn=handler)` when registering each subparser. This allows you to dispatch the command in a single line after parsing, completely avoiding long `if/elif` chains based on the command name.

```python
p = argparse.ArgumentParser()
sub = p.add_subparsers(dest="cmd", required=True)

# Register subcommands and bind their specific handler functions
sub.add_parser("telegram", help="run telegram bot").set_defaults(fn=_cmd_telegram)
sub.add_parser("panel", help="run TUI").set_defaults(fn=_cmd_panel)

# Parse and dispatch dynamically
args = p.parse_args(argv)
return args.fn(cfg, args)
```

**2. Lazy-import heavy dependencies inside the handler:**
Avoid importing heavy modules at the top of your CLI entrypoint file. Instead, import them inside the specific command handler that needs them. This ensures that running `app --help` or executing a simple, fast command doesn't incur the startup penalty of unrelated heavy dependencies.

```python
def _cmd_telegram(cfg: Config, _args) -> int:
    # Lazy import: only loaded if the 'telegram' command is actually invoked
    from .telegram import TelegramBot 
    
    TelegramBot(cfg).run()
    return 0
```

### Immutable, Environment-Driven Dataclass Configuration

When building application configuration in Python, define the configuration object as a `dataclass(frozen=True, slots=True)` to enforce immutability and minimize memory footprint. 

1. **Dedicated Factory Method**: Isolate environment variable parsing, defaulting, and type-casting inside a dedicated factory method (e.g., `@staticmethod def load()`). This keeps the dataclass definition clean and ensures the system fails fast if the environment is misconfigured.
2. **Immutable Collections**: Always cast iterable configuration values to their immutable counterparts (e.g., using `frozenset` instead of `set`, and `tuple` instead of `list`) to guarantee that the configuration remains strictly read-only throughout the application lifecycle.
3. **Rich Types**: Parse primitive environment strings into semantic types (like `pathlib.Path` for filesystem paths or `float` for timeouts) immediately in the factory method, rather than forcing downstream consumers to cast values or handle strings.
4. **Fail-Closed Security**: When configuring inbound entry points, default to restrictive states. If an access token or allowlist is missing or empty, the application should either refuse to start or deny all requests, rather than defaulting to an open state.

### Explicit Triage for Non-Imported Dependencies

When auditing project dependencies via static import scanning, finding zero direct imports does not always mean a package can be safely removed. Dependencies are sometimes explicitly declared in a manifest (e.g., `pyproject.toml`) for structural reasons that are invisible to source code import scanners:

1. **Transitive Version Pinning:** A package might be explicitly declared solely to enforce a version constraint on a transitive dependency that would otherwise break the environment (e.g., forcing `fastapi<0.140` because another required tool relies on an internal API removed in newer versions). 
2. **Subprocess CLI Tools:** A package might be installed entirely for its command-line binary rather than its Python modules (e.g., invoking a tool via `subprocess`).

**Best Practice:** 
When automating dependency triage, do not rely on static analysis alone. Always back your automation with an explicit, manual classification mapping (or override list). This ensures that when a package transitions from being directly imported to being strictly a transitive pin (e.g., removing the only file that imported it), the automation knows to retain it for its structural role rather than purging it as dead weight.

### Enforcing Dependency Triage Decisions through Tests

When auditing or cleaning up project dependencies, create tests that explicitly lock in your usage assumptions and findings against the real codebase and configuration (e.g., `pyproject.toml`). 

Instead of relying solely on comments or static documentation to explain why a dependency exists, write assertions that verify:
1. **Direct Usage:** Whether the dependency is actively imported in the source tree (and exactly where).
2. **Classification:** Whether the dependency is considered "core", "dev", or slated for a "drop".
3. **Justification:** Why a seemingly unused dependency might still be kept (e.g., as an internal pinned requirement for another tool).

**Why this matters:**
As the codebase evolves—such as removing a module that directly imported a library—these tests act as a regression check. They will fail when usage changes, forcing developers to consciously re-evaluate the dependency's status and explicitly update its justification. This prevents silent drift where unused dependencies are left orphaned ("someone will figure it out later") or kept around for outdated reasons.

### Sync Wrapper for Async CLI Entry Points

When writing CLI applications in Python that use `asyncio`, you should expose a synchronous `main()` function that delegates to `asyncio.run()`, rather than making `main()` itself an `async` function. 

**Why?**
Python packaging tools (such as those resolving `[project.scripts]` in `pyproject.toml`) generate console script wrappers that expect a synchronous callable. If `main` is an `async def`, the generated entry script simply calls `main()` and passes its return value to `sys.exit()`. This returns an unawaited coroutine object rather than executing the application, leading to a silent failure or an `Unclosed coroutine` warning.

**The Pattern:**
Rename your primary async logic to an internal function (like `_amain` or `async_main`), and provide a synchronous wrapper named `main` to serve as the project's entry point.

```python
import asyncio
import sys

async def _amain() -> int:
    # Your async CLI logic here
    await asyncio.sleep(0.1)
    return 0

def main() -> int:
    """Synchronous entry point for packaging console_scripts."""
    return asyncio.run(_amain())

if __name__ == "__main__":
    sys.exit(main())
```

### Fault-Tolerant Registry Initialization

**Pattern:** When building a registry of modular capabilities, plugins, or optional dependencies during application startup, initialize each component independently and isolate instantiation errors.

**Rationale:** 
If components are initialized synchronously without error isolation, a failure in one optional dependency (e.g., a missing binary or unreachable service) will abort the entire application boot sequence. In environments with auto-restart policies (like `systemd` with `Restart=always`), this transforms a minor feature degradation into a catastrophic restart loop that takes down the entire system.

**Implementation Guidelines:**
1. **Isolate Construction:** Map capability names to factory functions or lambdas (e.g., `_CAPABILITY_FACTORIES`), so each can be invoked independently.
2. **Catch and Degrade:** Iterate through the factories and wrap each instantiation in a `try...except` block.
3. **Log and Continue:** On failure, log a warning that the specific capability is unavailable and proceed with booting the rest of the application. The system should be designed to handle the absence of these optional components gracefully.
4. **Clean Up Hacks on Removal:** When deprecating or removing capabilities (as demonstrated in the diff), proactively remove any lazy-import workarounds (like module-level `__getattr__` overrides) that were previously introduced to prevent those specific components from breaking imports.

### Enforce Architectural Intent with Explicit Constraints and Routing

When designing distinct subsystems for an application (e.g., discrete "facts" vs. long-form documents for RAG), encode the architectural intent directly into the data model using explicit constraints.

**Best Practice:**
1. **Define the limit:** Set a hard boundary (e.g., `FACT_MAX_CHARS = 300`) that aligns with the intended use case (e.g., a fact is a single sentence).
2. **Document the alternative:** Always explain in the comment *why* the limit exists and *where* developers should route data that exceeds this limit (e.g., "longer material belongs in RAG, retrieved on demand").

This pattern prevents scope creep (e.g., treating a simple key-value fact store as a document database) and explicitly guides future developers on how to properly route different types of data within the broader system architecture.

### Consistent Project Namespacing During Code Migration

**Pattern / Lesson:**
When migrating, copying, or extracting code from one project to another, always ensure that absolute internal imports are updated to reflect the new project's namespace. Leaving stale imports creates hidden dependencies on the old project.

**Analysis of the Change:**
The diff reveals a correction of an import from a legacy or external project namespace (`ohmyllama.security.secrets`) to the current project's namespace (`semai.security.secrets`). The original code likely carried over this stale import during a copy-paste or modular extraction operation, which can lead to `ModuleNotFoundError` in a clean environment or unintended tight coupling if both packages happen to be installed.

**Best Practices for Future Reference:**
- **Thorough Search and Replace:** When porting modules between codebases, perform a codebase-wide search for the old root namespace (e.g., `ohmyllama.`) to catch any lingering absolute dependencies.
- **Isolated Testing:** Test newly migrated code in an isolated environment (like a fresh virtual environment, CI runner, or Docker container) where the old project is not installed. This ensures that any forgotten namespace updates fail loudly.
- **Linter Checks:** Rely on static analysis tools and linters (like `mypy`, `flake8`, or `pylint`) in your CI pipeline to automatically detect unresolved imports before they are merged.

### Correcting Project Namespace Imports
When copying or migrating code from another project (e.g., a template or an older repository like `ohmyllama`), always ensure that all module imports are updated to reflect the new project's namespace (e.g., `semai`). Failing to update these imports can lead to unintended external dependencies, broken builds, or security risks by resolving utilities (such as secret managers) from the wrong codebase.

**Best Practice:**
- Perform a project-wide search for the old namespace after migrating or copying code.
- Verify that core internal utilities (e.g., `resolve_secret`, `Settings`) are imported from the current project's own modules to maintain proper isolation and decoupling.

### Project Rename / Namespace Consistency

When renaming a project, forking a codebase, or migrating modules to a new namespace, ensure that all internal absolute imports are updated to use the new package name. In this change, an import from a legacy or external namespace (`ohmyllama.security.secrets`) is corrected to use the current project's namespace (`semai.security.secrets`). Failing to update these imports can cause `ModuleNotFoundError` if the old package is removed, or lead to subtle and dangerous bugs by accidentally importing and executing code from an older, globally installed version of the package.

### Pattern: Consistent Internal Package Renaming

**Context:**
When renaming a core project, namespace, or internal library (in this case, from `ohmyllama` to `semai`), absolute imports across the codebase can easily be overlooked. Leaving stale imports behind will lead to `ModuleNotFoundError` and broken functionality.

**Lesson / Best Practice:**
- **Thorough Update:** Whenever an internal package or namespace is renamed, ensure that you perform a comprehensive search and replace across the entire codebase to update all corresponding absolute imports.
- **Internal Consistency:** All modules within the project must reference the new package name (e.g., `semai.security.secrets`) rather than the legacy name (`ohmyllama.security.secrets`).
- **Tooling:** Utilize IDE refactoring tools or global search-and-replace (e.g., `grep` or `ripgrep`) to guarantee that no legacy package references remain in any files.

### Centralize Security Primitives in Dedicated Namespaces

**Lesson:**
Security-critical utilities, such as path validation guards and access control checks, should be maintained in a clearly defined, internal security namespace rather than imported from external, legacy, or generic "capabilities" modules. 

**Why it matters:**
* **Auditability:** Centralizing security logic into a dedicated module (like `security.path_guard`) makes it much easier to review and audit the code for vulnerabilities.
* **Decoupling:** Moving away from external dependencies (e.g., `ohmyllama`) for core security mechanisms ensures the project maintains full control over its own security boundaries and risk profile.
* **Clarity:** It clearly signals the intent and importance of the code to other developers, separating security rules from general business logic or generic utilities.

### Clean Up Legacy Imports After Module Migration

**Context:**
When migrating features from a legacy package or monolithic structure into a new architecture, constants, data structures, and functions are often moved into new domain-specific modules. 

**Lesson:**
Ensure that newly migrated code imports its dependencies (such as configuration constants or limits) from the new internal modules rather than the legacy package. 

**Why it matters:**
Leaving residual imports pointing to the old codebase creates a hidden dependency that bridges the new architecture back to the legacy system. This tangles architectural boundaries and prevents the legacy code from being safely deprecated and removed, ultimately undermining the structural goals of the migration.

### Standardize Internal Namespaces During Migration

When migrating code, renaming a project, or consolidating components into a unified namespace (e.g., migrating from `ohmyllama` to `semai`), always review and update your import statements to reflect the new internal structure. 

Leaving legacy imports that reference old project names or external packages—when an internal equivalent now exists—can lead to disjointed dependencies, potential versioning conflicts, and brittle code. Ensure that components within the same project rely on their internal modules rather than externalized legacy versions of themselves.

### Leverage Short-Circuit Evaluation in Compound Conditionals

When writing compound `if` conditions, order your checks from the cheapest and safest (e.g., null/existence checks) to the most expensive (e.g., function calls). Python's `and` operator short-circuits, meaning it stops evaluating as soon as it encounters a falsy condition.

**Anti-Pattern:**
Evaluating expensive or complex conditions before ensuring the required base objects even exist.
```python
if (
    (retry or _is_retryable_backend_error(error)) # ⚠️ Function executes even if row is None
    and row
    and row["attempts"] < max_attempts
):
```

**Best Practice:**
Place existence checks first, followed by simple attribute access, and defer function calls to the very end.
```python
if (
    row                                               # 1. Safest/cheapest existence check
    and row["attempts"] < max_attempts                # 2. Simple dictionary/attribute lookup
    and (retry or _is_retryable_backend_error(error)) # 3. Expensive function call (deferred)
):
```

This strict ordering prevents unnecessary computation and guarantees that variables are fully validated before their properties are accessed or passed into deeper logic.

### Prefer Instance Configuration Over Inline Global Config Loading

When a class requires configuration or dependencies to perform an action, use the configuration provided during the class's initialization (e.g., `self.cfg`) instead of dynamically loading global state within deeply nested methods. 

**Before:**
```python
def _notify(self, store: Store, title: str, message: str) -> None:
    try:
        from ohmyllama.alerts import deliver
        from ohmyllama.config import Config
        cfg = Config.load() # Hidden dependency, potential I/O overhead
        deliver(cfg, store, "topic", title, message)
    except Exception as e:
        log.warning("notify failed: %s", e)
```

**After:**
```python
def _notify(self, store: Store, title: str, message: str) -> None:
    try:
        from semai.adapters.push import deliver
        # Use the configuration already injected into the instance
        deliver(self.cfg, store, "topic", title, message)
    except Exception as e:
        log.warning("notify failed: %s", e)
```

**Benefits:**
*   **Testability:** It is much easier to mock or provide specific test configurations by instantiating the class with a custom `Settings` object, rather than having to monkeypatch a global `Config.load()` method.
*   **Performance:** Avoids the overhead of repeatedly parsing or loading configuration from disk or environment variables on every method invocation.
*   **Explicit Dependencies:** The state required by the class is explicitly declared in its constructor, making the code easier to reason about, maintain, and refactor.

### Targeted Stubs for Testing Fallback Logic

When testing configuration resolution, routing, or fallback behaviors, avoid loading the real, fully-hydrated application configuration object (e.g., `Config.load()`). Instead, define a minimal, explicit test double (stub) directly within the test file. 

By deliberately omitting specific attributes or methods from this minimal stand-in, you can predictably and reliably force the system under test to exercise its fallback paths and default values. This ensures your tests evaluate the pure resolution logic, remaining fast, deterministic, and entirely decoupled from the actual environment state or complex real-world configuration data.

**Example:**
```python
# Instead of loading a real configuration:
# cfg = Config.load()

class StubSettings:
    """Minimal stand-in: deliberately lacks specific routing attributes 
    to force the resolver to fall back to the default pool rather than blow up."""
    pass

settings = StubSettings()

# The resolver is forced to use the default pool because settings lacks overrides
assert resolve_model(settings) == DEFAULT_FALLBACK_MODEL
```

### Update Documentation When Relocating Code

When refactoring code by moving modules or functions to new namespaces (e.g., updating imports from `ohmyllama.alerts` to `semai.adapters.push`), always check for and update references to the old paths in comments and docstrings.

In this change, the `deliver` function was moved to a new adapter package, but the file-level docstring in the test still references the old module path (`ohmyllama.alerts.deliver`). 

**Best Practice:**
Make it a habit to perform a text search for the old module or function name whenever relocating code. This ensures that test descriptions, file headers, and inline comments do not become stale and misleading for future developers.

### Separation of Parsing and Authorization

**Context:** A pure parsing or routing module was previously responsible for both extracting route information and validating if the route (e.g., a chat ID) was allowed (authorization).

**Action:** The authorization functions (`is_allowed_chat`, `is_chat_id`) and their tests were removed from the routing module during an architectural migration to the `semai` architecture. 

**Lesson:** Maintain a strict separation of concerns between data parsing/routing and security/authorization. Pure parsing logic should only be responsible for structural validation, data extraction, and serialization. Security boundaries and access control checks should be handled by a dedicated, higher-level authorization layer, rather than being tightly coupled with low-level string parsing or routing utilities.

### Narrow Interfaces & Direct State Verification in Tests

When building a database-backed component (like a queue or task store), keep its public interface strictly limited to the operations actually needed by the application in production (e.g., `enqueue`, `claim_next`, `requeue_stale`). 

**Do not add generic accessors (like `get_task`) solely for the convenience of test assertions.** 

Instead, tests should verify persistence and state changes by querying the underlying database directly. In the provided diff, the removal of `get_task` from the queue assertions forces the test to verify state via raw SQL (`db.execute("SELECT status FROM ...")`). This approach provides two major benefits:

1. **Interface Segregation:** The production interface remains minimal and focused, exposing only the exact operational surface area required by the domain.
2. **True State Verification:** Direct database queries ensure the tests are verifying the actual persisted state on disk, bypassing any potential caching, ORM mapping, or logic errors that might exist inside the domain accessors.

**Secondary Pattern: Test Cohesion & Separation of Concerns** 
The diff also removes a large block of tests related to "model health and quarantine" from a file dedicated to "queue recovery." Orthogonal domain concepts should be decoupled into separate components and tested in separate, highly cohesive files.

### Append-Only Reverts (Roll-Forward Recovery)

When implementing undo or revert functionality in a system that tracks history or audit logs, treat the revert operation as a new state transition rather than a destructive rollback. 

**Pattern Characteristics:**
1. **Preserve the Audit Trail**: A revert should not erase or rewrite history. The current state immediately prior to the revert must be snapshotted, just like any standard update.
2. **Revert is just an Update**: Implement reverts by fetching the historical snapshot and applying it using your standard update mechanism (e.g., routing it through the same `put_fact` or `update` method). This ensures all existing business logic, validation, and history-tracking automatically apply to the revert action.
3. **Revertible Reverts**: Because a revert appends to the history rather than mutating it, the revert itself can be safely undone by simply reverting to the snapshot taken right before the revert occurred.

**Example:**
```python
def revert_fact(self, history_id: int) -> str | None:
    """Restore a fact to a specific retired snapshot. 
    Goes through `put_fact`, so the CURRENT version is itself
    snapshotted first -- a revert is not a hole in the history, 
    it is one more entry in it, and can itself be undone."""
    row = self.db.execute("SELECT * FROM fact_history WHERE id=?", (history_id,)).fetchone()
    if not row:
        return None
        
    # Re-use standard update path to ensure the current state is snapshotted
    self.put_fact(row["key"], row["fact"], scope=row["scope"],
                  source=row["source"], changed_by="revert")
    return row["key"]
```

### Match Sync/Async Signatures in Test Doubles

**Context:** 
Creating fakes, stubs, or side effects to replace real dependencies in tests (e.g., when using `unittest.mock.patch`).

**The Pitfall:** 
Stubbing a **synchronous** method with an **asynchronous** fake (`async def`) will cause the calling code to receive an unawaited coroutine object instead of the expected return value. Because the actual system-under-test expects a synchronous function, it will not `await` the result. Consequently, the fake's internal logic is never executed and the scripted behaviors are silently dropped, leading to baffling test failures or false positives.

**The Solution:** 
Always ensure your test double's signature (sync vs. async) exactly matches the real method's signature. If the target method is a standard `def`, the fake must also be a standard `def`—even if the surrounding test case or test runner uses `asyncio`.

**Example:**
```python
# Real implementation is synchronous
class LLMProvider:
    def chat(self, prompt): 
        ... 

# BAD: Async fake for a sync method
async def fake_chat(*args, **kwargs):
    # This logic is silently dropped because the sync caller won't `await` it
    return "fake response" 

# GOOD: Sync fake for a sync method
def fake_chat(*args, **kwargs):
    return "fake response"

with mock.patch("LLMProvider.chat", side_effect=fake_chat):
    ...
```

### [Refactoring Pattern] Namespace Migration and Configuration Schema Evolution

**Context:**
As a project matures, its core namespace may evolve from a working title or project-specific name (e.g., `ohmyllama`) to a permanent, library-oriented name (e.g., `semai`). During this transition, configuration management often shifts from generic classes (`Config`) to more structured, schema-validated models (`Settings`).

**Key Takeaways:**
1. **Namespace Updates in Tests:** When renaming a project's root namespace, ensure that all auxiliary scripts and integration/seam tests are updated to reflect the new package structure.
2. **Schema-Driven Configuration:** Evolving from a generic `Config` class to a `Settings` class (often backed by validation libraries like Pydantic) encourages stronger schema validation. When applying this change, update factory methods (e.g., changing `Config.load()` to `Settings.load()`).
3. **Decoupled Secret Resolution:** Keep sensitive credential resolution (e.g., `resolve_secret`) separate from the main configuration model. The diff shows that while the configuration class changed, secret resolution remained a dedicated utility, ensuring secure, decoupled handling of environment-specific overrides.

**Code Example:**
```python
# Before
from ohmyllama.config import Config
from ohmyllama.security.secrets import resolve_secret

cfg = Config.load()
vault_path = getattr(cfg, "obsidian_vault_path", None) or resolve_secret("OBSIDIAN_VAULT_PATH")

# After
from semai.config.schema import Settings
from semai.security.secrets import resolve_secret

cfg = Settings.load()
vault_path = getattr(cfg, "obsidian_vault_path", None) or resolve_secret("OBSIDIAN_VAULT_PATH")
```

### Updating Standalone Tests During Namespace Refactoring
When renaming a project's root namespace (e.g., `ohmyllama` to `semai`) or core configuration classes (e.g., `Config` to `Settings`), you must update imports in all standalone test scripts and integration tests. These scripts often manually configure `sys.path` and load settings directly to interact with the environment (such as fetching secrets or paths), making them easy to miss but critical to update to prevent test suite failures during large-scale refactors.

### Keep Documentation in Sync with Code Refactors

**Lesson:**
When refactoring module names, class names, or namespaces (such as migrating from `ohmyllama` to `semai`), it is critical to also update any docstrings, inline comments, and string literals that reference the old names. 

**Context from the Code:**
The provided diff shows a refactoring where `ohmyllama.config.Config` was replaced with `semai.config.schema.Settings` and `ohmyllama.security.secrets` was updated to `semai.security.secrets`. However, the file's top-level docstring was left untouched and still incorrectly references `ohmyllama's own Config.load()`. 

Failing to update comments during a refactoring leads to "documentation rot." The documentation no longer accurately describes the underlying code, which can confuse future maintainers who rely on it for context.

**Best Practice:**
Whenever you perform a structural refactor, rename classes, or move modules, always do a text search for the old terms (e.g., `ohmyllama`, `Config.load`) across the codebase. This ensures that documentation and comments are updated in tandem with the implementation.

### Declarative AI Model Configuration

**Context:** The application orchestrates multiple AI models across different tiers, roles, and fallback chains. 

**Lesson:** Avoid hardcoding model names, versions, and endpoints in your execution scripts. Instead, extract them into a centralized configuration file (e.g., `tiers.yaml`) that serves as a single source of truth. 

**Why it matters:** 
The AI ecosystem evolves rapidly. You will frequently need to upgrade model versions (as seen here, bumping `gemini-3.7-flash` to `gemini-3.8-flash`), switch providers due to rate limits, or adjust fallback logic. By keeping model configurations declarative:
- **Trivial Upgrades:** Bumping a model version is a one-line configuration change, requiring no changes to the underlying code.
- **Hot-Swapping:** You can cleanly swap providers or implement peak-hour alternatives without risking regressions in the core orchestration logic.
- **Visibility:** Developers can see exactly which models handle which roles (e.g., "strategic planning" vs. "doc_librarian") at a glance.

### Use Machine-Readable Model Identifiers in Documentation

When documenting the use of specific LLMs, external services, or configuration values, use the exact machine-readable identifier or slug (e.g., `gemini-3.8-flash`) rather than informal, human-readable display names (e.g., `Gemini 3.7 Flash`). 

**Why this matters:**
- **Searchability:** Developers frequently rely on code search tools (like `grep` or CodeGraph) to track down where a specific model or version is utilized. Using the exact programmatic slug ensures your documentation surfaces in those search results alongside code and configuration files.
- **Precision:** Model versions and variants often share similar human-readable names. Using the exact identifier eliminates ambiguity about which specific model version a component was tested with or depends on.
- **Consistency:** It aligns the documentation language directly with the code and configuration files (e.g., `config/tiers.yaml`), creating a single source of truth for terminology.

### Avoid Hardcoding Real Versioned Names in Config Mocks

When writing tests that verify configuration values are correctly passed through to mocked dependencies (like an LLM client), avoid hardcoding real, versioned names (e.g., `gemini-3.7-flash` or `gemini-3.8-flash`). 

Using real version strings makes tests brittle and creates unnecessary maintenance churn. Every time the project upgrades to a newer model or tool version, these tests have to be manually updated just to keep passing, even though the specific version string has no bearing on the routing or configuration logic being tested.

Instead, use obvious dummy or sentinel values (e.g., `dummy-model-v1` or `mock-test-model`). This clearly communicates to future readers that the specific string doesn't matter for the test's assertions, and ensures the test remains robust and untouched during routine real-world version bumps.

### Prefer `assertTrue` and `assertFalse` over `assertIs` for boolean assertions

When writing tests using Python's `unittest` framework, prefer using `self.assertTrue(x)` and `self.assertFalse(x)` instead of `self.assertIs(x, True)` and `self.assertIs(x, False)`. 

**Reasoning:**
- **Readability and Idiom:** `assertTrue` and `assertFalse` are the standard, idiomatic methods provided by `unittest` specifically for evaluating boolean conditions. They are more concise and make the intent of the test immediately clear.
- **Truthiness vs. Strict Identity:** `assertIs` checks for strict object identity (i.e., `x is True`). `assertTrue` and `assertFalse` evaluate the *truthiness* of the expression (i.e., `bool(x)`). In most testing scenarios, you only care whether a value evaluates to a truthy or falsy value in a boolean context, rather than it being the exact singleton `True` or `False` object. 

*Note: If your test specifically requires validating that a return value is exactly the `True` or `False` singleton and not just truthy/falsy, `assertIs` would still be the correct choice. However, for general boolean outcomes, `assertTrue`/`assertFalse` should be the default.*

**Example:**

```python
# Less idiomatic, strictly checks object identity
self.assertIs(is_valid, True)
self.assertIs(has_errors, False)

# Preferred, idiomatic, checks truthiness
self.assertTrue(is_valid)
self.assertFalse(has_errors)
```

### Populate Metadata in Synthetic State Objects

**Context:** 
Programmatically generating synthetic state objects (such as tasks, runs, or jobs) to bypass standard user-facing creation flows.

**Issue:** 
It is easy to only populate the fields strictly required by the execution engine (e.g., execution phases or steps), while omitting metadata fields that are normally provided by user input (such as `prompt`, `title`, or `description`).

**Consequence:** 
Downstream components like observability tools (CLI list/status commands), logging, or completion hooks (e.g., auto-generated commit messages) often assume these metadata fields are always present. Omitting them leads to unhandled exceptions like `KeyError: 'prompt'` when the system attempts to process or display the synthetic object.

**Best Practice:** 
When creating synthetic state objects, always supply sensible defaults or generated summaries for all expected metadata fields to satisfy the implicit data contracts of the object's entire lifecycle.

### Safe In-Place Filtering of Structured Text Files

**Pattern:** When programmatically removing data entries from a human-readable, text-based file (such as a Markdown backlog, custom log, or config file), read the file line-by-line and unconditionally preserve any lines that do not match the expected data format (e.g., headers, comments, or descriptions).

**Why this matters:** Data files often contain manual documentation, headers, or whitespace formatting that provide essential context. If a script naively parses the file into data objects and then overwrites the file using only the remaining objects, it will destroy this metadata. By using a regex or parser to identify *only* the data rows, you can safely filter out specific targets while passing through all structural and contextual content untouched.

**Implementation Example:**
```python
def remove_resolved_entries(file_path: Path, resolved_targets: set[str]) -> None:
    if not file_path.exists():
        return

    lines = file_path.read_text(encoding="utf-8").splitlines()
    kept_lines = []

    for line in lines:
        match = _ENTRY_RE.match(line.strip())
        if match:
            # Data entry line: keep only if it shouldn't be removed
            filepath = match.group("filepath")
            if filepath not in resolved_targets:
                kept_lines.append(line)
        else:
            # Non-entry lines (headers, descriptions, blank lines) are always kept
            kept_lines.append(line)

    file_path.write_text("\n".join(kept_lines) + "\n", encoding="utf-8")
```

### Prevent Runtime Errors from Missing Imports
When introducing new dependencies or modules (like `librarian_escalate`) into conditionally executed code paths, failing to add the corresponding `import` statement will result in a delayed `NameError` at runtime. Because this crash only occurs when the specific condition is met, it can easily slip past basic manual testing.

**Best Practice:** Always run a static analysis tool or linter (such as `ruff`, `flake8`, or `pyright`) on your codebase before committing. These tools instantly detect undefined names and missing imports, ensuring that new execution paths have all their required dependencies loaded.

### Beware Domain Mismatch When Extracting Helpers

When extracting inline logic into a reusable helper function, ensure the function name accurately reflects its implicit domain constraints. Hiding specific formatting requirements behind generic types and names often leads to silent failures when the helper is reused in a different context.

**Example from this code:**
The author extracted logic to find function names into a generically named helper with a generic signature:
```python
def extract_named_symbols(text: str) -> list[str]:
    return list(dict.fromkeys(_HUNK_FUNC_RE.findall(text) + _BODY_DEF_RE.findall(text)))
```

Because the signature implies it works on any `str` text, they immediately reused it in `detect_relocation_intent` to parse a plain-English PR `description`. However, the underlying regexes (`_HUNK_FUNC_RE` and `_BODY_DEF_RE`) strictly require Git diff syntax (lines starting with `@@...@@` or `+`/`-`). Consequently, calling this on a PR description will silently return an empty list, breaking the new relocation detection logic.

**Best Practice:**
* Name functions to explicitly state their expected input format (e.g., `extract_symbols_from_git_diff(diff_text: str)`).
* When reusing a newly extracted helper, verify that the new input data actually conforms to the assumptions baked into the implementation.

### Unified Application State Directory

**Pattern / Best Practice:**
Consolidate all local application state—including SQLite databases, configuration files, rules, and caches—into a single, unified hidden directory (e.g., `.state-semai/`).

**Problem:**
Scattering application state across multiple unrelated directories (like having a database in `.state-semai/` and rules in `10-Memory/Rules/`) makes the application fragile. It complicates directory setup, creates hidden dependencies on specific folder structures, and makes cleaning up, backing up, or resetting the application state significantly harder.

**Solution:**
Define a single root directory for the application's local state and store all necessary files within it. 

**Example from the code:**
```python
# Anti-pattern: State and configuration scattered across arbitrary paths
def __init__(
    self, 
    db_path=".state-semai/mail_state.sqlite3", 
    rules_path="10-Memory/Rules/EmailRules.md"
): ...

# Best Practice: Unified state directory
def __init__(
    self, 
    db_path=".state-semai/mail_state.sqlite3", 
    rules_path=".state-semai/EmailRules.md"
): ...
```
By moving `EmailRules.md` into the `.state-semai/` directory alongside `mail_state.sqlite3`, the application's local footprint becomes entirely self-contained and predictable.

### Resilient File I/O and Standardized State Directories in Workers

When implementing workers or background tasks that perform filesystem operations, adhere to the following practices for robustness and cleanliness:

1. **Handle I/O Exceptions Gracefully**: Always wrap file system operations (e.g., `mkdir`, `open`, `write`) in a `try...except` block. Instead of allowing raw `OSError` or `IOError` exceptions to bubble up and potentially crash the worker process, catch the exception and return a structured failure object (e.g., `Result(ok=False, message=str(exc))`). This allows the caller to handle the failure gracefully.
2. **Use Standardized Hidden State Directories**: Store local application state, generated rules, or caches in a designated, application-specific hidden directory (e.g., `.state-appname`) rather than arbitrary, unhidden folder structures (like `10-Memory/`). This keeps the project root organized and makes it easier to track or `.gitignore` state files.

**Example:**
```python
# Anti-pattern: Unhandled I/O and arbitrary directories
pathlib.Path("Random/Folder/").mkdir(parents=True, exist_ok=True)
with open("Random/Folder/Data.md", "a") as f:
    f.write(data + "\n")
return Result(ok=True)

# Best Practice: Handled I/O and standard hidden directories
try:
    pathlib.Path(".state-myapp").mkdir(parents=True, exist_ok=True)
    with open(".state-myapp/Data.md", "a") as f:
        f.write(data + "\n")
except Exception as exc:
    return Result(ok=False, message=str(exc))
return Result(ok=True)
```

### Testing File I/O and Error Handling with `mock_open`

When unit testing components that write to files in Python, use `unittest.mock.mock_open` to avoid actual disk I/O, verify file operations, and simulate file system errors.

**1. Verifying File Writes:**
Patch `builtins.open` with `new_callable=mock_open` to intercept file operations. You can verify the requested file path by inspecting `mock_open_file.call_args`. To assert against the complete written content—especially when data might be written in multiple chunks—concatenate the arguments from the file handle's `write.call_args_list`.

```python
@patch("builtins.open", new_callable=mock_open)
def test_execute_writes_to_file(mock_open_file):
    # ... trigger code that writes to a file ...
    
    # Verify the target file path
    written_path = mock_open_file.call_args[0][0]
    assert str(written_path) == "path/to/file.md"
    
    # Verify the entire written content
    handle = mock_open_file()
    written_content = "".join(call.args[0] for call in handle.write.call_args_list)
    assert "expected text" in written_content
```

**2. Simulating I/O Errors:**
To test your application's resilience to file system issues, patch `builtins.open` with a `side_effect` to simulate exceptions (like `PermissionError` or `FileNotFoundError`) and ensure your code handles them gracefully.

```python
@patch("builtins.open", side_effect=PermissionError("denied"))
def test_execute_returns_failure_on_write_error(mock_open_file):
    # ... trigger code that attempts to write ...
    
    # Assert that the error is caught and handled appropriately
    assert not result.ok
    assert "denied" in result.message
```

### Test Default File Paths by Observing Behavior, Not Just State

When testing that a component defaults to a specific file path, do not merely assert that its internal path variable is set to the expected string. Instead, create a mock file at that default location, invoke the component, and verify that its behavior actually reflects the contents of that file.

Asserting only the string value leaves a gap: the component might store the correct path but fail to read from it (e.g., due to a lazy-loading bug, incorrect initialization order, or hardcoded reads elsewhere). Testing the behavior proves the components are fully wired together.

**Example:**
```python
def test_watcher_consults_default_rules_path(tmp_path, monkeypatch):
    # 1. Setup the expected default directory and file
    monkeypatch.chdir(tmp_path)
    default_dir = tmp_path / ".config"
    default_dir.mkdir()
    (default_dir / "Rules.md").write_text("archive user@example.com\n")

    # 2. Initialize the component without providing an explicit path
    watcher = Watcher() 
    
    # 3. Assert the state (useful for clarity)
    assert str(watcher.rules_path) == ".config/Rules.md"

    # 4. Assert the behavior (crucial for correctness)
    # Proves the file at the default path was actually opened and parsed
    result = watcher.process_message("user@example.com")
    assert result == "archived"  
```

### Explicit Feature Flags and Model Configuration for AI Capabilities

When integrating new AI capabilities—such as Memory or Retrieval-Augmented Generation (RAG)—encapsulate the configuration in a dedicated block. Always include an explicit `enabled` toggle and define the exact models being used (e.g., `embedding_model: "nomic-embed-text:latest"`) in the configuration file rather than hardcoding them in the application logic.

**Why this is a best practice:**
- **Instant Feature Toggling:** The explicit `enabled` flag allows you to turn the feature on or off globally without touching code. This is crucial for safe testing, staged rollouts, or gracefully disabling the feature if the underlying model API goes down.
- **Seamless Model Swapping:** AI models iterate quickly. By extracting model identifiers into configuration files, you can easily swap models (e.g., upgrading to a new local embedding model) without a code redeploy.
- **Consistency:** It aligns with a configuration-driven architecture where behavior, routing, and model selection are centralized, making the system easier to audit and debug.

### Pattern: Expanding Configuration Scope and Validation

**Context:** 
When extending an existing configuration file and its loader to include new, distinct top-level blocks (e.g., adding a `memory_rag` configuration to a file originally dedicated to `tiers`).

**Best Practices:**
1. **Explicit Structural Validation:** Do not just append the new key to a required list. Explicitly validate the internal structure of the new block (e.g., ensure it is a dictionary and contains all required sub-keys) immediately after parsing. This fails fast and prevents obscure `KeyError` or `AttributeError` exceptions deep in downstream code.
2. **Semantic Naming & Backward Compatibility:** If the loader's original function name implies a narrow, specific scope (e.g., `load_tiers`), but it now returns a broader, multi-purpose configuration object, introduce a semantically accurate alias or rename the function (e.g., `load_config`). This clarifies the function's broader purpose for future callers while maintaining backward compatibility for existing integrations.

### Unified Context Threading for Agent Pipelines

**Context**: In multi-tier workflows or AI pipelines, a single task often passes through several retries, escalation layers, or specialized sub-agents, all of which require the same background context (e.g., RAG retrieval results, reference file contents).

**Pattern**: Build the complete, unified context payload exactly *once* at the orchestration entry point, and thread this single blob down through all subsequent pipeline components and retries. 

**Why it matters**:
1. **Consistency (No Drift)**: Prevents "context drift" between attempts. If context retrieval (like a vector search) is performed dynamically at each tier, a retry might fetch different context, causing non-deterministic or confusing behavior. Every tier must operate on the exact same grounding information.
2. **Efficiency**: Eliminates redundant and potentially expensive context-building operations (such as embedding generation, network requests, or repeated file I/O) across multiple retries or fallback tiers.
3. **Adaptability**: Even if a specific sub-component or legacy function lacks a dedicated `context` parameter, the pre-computed context blob can be injected directly into its main prompt (e.g., appending it to the task description), ensuring the single-source-of-truth guarantee remains intact across heterogeneous systems.

### Thread Context Upstream for Prompt Stability

When passing context to an escalation tier or retry loop (especially for LLMs with prefix caching), gather dynamic context (such as relevant guidelines, lessons, or search results) **once** in the upstream caller and thread it through as a stable blob. 

Do not re-compute or re-fetch this context independently within the downstream escalation tier.

**Why:**
* **Cache Hit Optimization:** Passing a threaded, stable context block ensures the prefix remains exactly identical across repeated escalation calls against the same target, maximizing prompt cache hits.
* **Avoid Duplicate Work:** Re-evaluating context locally during every retry or escalation attempt creates redundant operations (e.g., duplicate keyword-overlap selections) that waste compute and latency.

### Decouple Relevance Selection from Execution

When building multi-tiered pipelines or worker agents, decouple the logic that selects relevant context (such as lessons, rules, or documentation) from the execution script itself. 

Instead of having the downstream execution script compute relevance on the fly (e.g., calling `select_relevant(target, description)`), rely on the caller to inject a pre-computed `context_blob`. The execution script should simply parse and format the data already present in the provided context. 

This architectural pattern provides several benefits:
1. **Centralized Logic**: Context selection is handled in one place, making it easier to test and modify.
2. **Consistency**: It ensures that the specific rules injected into system prompts perfectly align with the broader context presented in the user prompt.
3. **Simplicity**: Downstream agents act as "dumb" executors that don't need to know how to query or filter metadata, reducing their complexity and preventing divergent behavior across tiers.

### Hoist Context Assembly to the Caller

**Pattern:** Pass pre-assembled context strings (e.g., a `context_blob`) into execution functions instead of retrieving or formatting context deep within the execution logic.

**Rationale:** 
Fetching context—like querying for relevant lessons or related file snippets—deep inside execution scripts tightly couples the execution logic to the context-retrieval mechanism. By hoisting the context assembly up the call stack and passing it down as a generic string, you achieve several benefits:

1. **Decoupled Systems:** The execution layer no longer needs to know how to query, rank, or format specific types of context (like lessons).
2. **Improved Testability:** You can easily test the execution logic by passing in mock context strings without needing to mock external context-retrieval dependencies.
3. **Increased Flexibility:** The caller can decide exactly what context to include (lessons, file contents, memory) without requiring modifications to the execution function's signature or internal logic.

### Guard Against Mindless Approvals in Human-in-the-Loop Systems

**The Problem:**
In conversational LLM workflows, the system often expects a specific type of structured deliverable (like an execution plan), but the LLM might instead ask a clarifying question or generate conversational filler. Human reviewers, habituated to the "happy path," can easily skim the output and reflexively type "approve," causing the system to accept an invalid payload and transition to an execution state.

**The Solution:**
Validate the structural shape of the LLM's output independently of the human's explicit approval. Even if a human says "looks good," the system should reject the state transition if the payload lacks the expected formatting markers.

**Key Guidelines:**
- **Assert Structural Markers:** Check for specific syntax that defines the expected deliverable (e.g., `- [ ] ` for checklist plans) *before* processing the user's approval.
- **Intercept and Explain:** When an approval is rejected, clearly explain to the user *why* (e.g., "This response contains no checklist steps. If it is a clarifying question, please answer it instead of approving").
- **Prevent Loop Escapes:** If dropping the user back into an input prompt, ensure that repeated mindless "approvals" are explicitly caught and rejected until the user provides meaningful textual feedback, answers the LLM's question, or cancels the operation.

### Sentinel Values for Validation Bypasses

When enforcing strict data constraints (such as a 64-character SHA-256 hash to track file staleness), you will inevitably encounter edge cases where the data cannot be generated or the validation needs to be skipped.

Instead of restructuring your schema to make fields optional or introducing complex conditional logic, use an explicit **sentinel value** (e.g., an `n/a` prefix). By updating the parser to accept this sentinel and adding an early return in your validation logic, you create a safe, self-documenting "escape hatch." This allows you to gracefully bypass checks for specific edge cases while maintaining strict validation for the vast majority of the system.

### Prefer Explicit Loops Over List Comprehensions for Observable Filtering
When filtering collections, list comprehensions (`[x for x in items if condition]`) are concise but silently drop excluded items. If the user or developer needs to know *what* was skipped and *why* (e.g., dropping stale entries, skipping invalid files, or ignoring failed checks), expand the comprehension into a standard `for` loop. This allows you to log, print, or otherwise record the skipped items, significantly improving system observability and user feedback.

**Anti-pattern (Silent filtering):**
```python
filtered_entries = [entry for entry in entries if not tech_debt.check_staleness(entry)]
```

**Best Practice (Observable filtering):**
```python
filtered_entries = []
for entry in entries:
    if tech_debt.check_staleness(entry):
        print(f"Skipping STALE entry: {entry['filepath']}")
        continue
    filtered_entries.append(entry)
```
