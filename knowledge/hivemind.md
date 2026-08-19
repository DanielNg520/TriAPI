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
