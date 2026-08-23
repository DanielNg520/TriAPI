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
