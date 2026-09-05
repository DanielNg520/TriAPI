Break the following phase into small, independent coding tasks. Each task must be codeable by another model in one sitting, touching one function or one small file, with an exact scope boundary (what to write, what NOT to touch).

## Phase 1: Ground-truth verify layer

Goal: a small Python module (target: `TriAPI/rebuild/scripts/verify.py`) that verifies a code change actually worked, instead of trusting a weak proxy. The old pipeline's bug: `build_cmd` was often just `py_compile` or a substring grep, so broken/reverted changes were reported as success repeatedly (see TriAPI's own `docs/agents/20260905-000000-known-recurring-pipeline-problems.md`, item #1).

Required capabilities (turn each into one or more small tasks):
1. Run a real test command (e.g. `pytest -v` or a project's own test script) as a subprocess, parse its real pass/fail/skip counts from output — not just exit code, since exit code 0 can hide skipped-instead-of-asserted tests.
2. Flag if a test run reports 0 tests actually executed (skip-only run) as NOT a pass, even if exit code is 0.
3. Given a file path and expected content (or a SEARCH/REPLACE-style diff), verify the on-disk file actually matches after a write — real string/structural comparison, not a grep for a keyword.
4. Given a task's declared scope (e.g. "only touch function X in file Y"), diff the file before/after and flag any change outside the declared function/section as a scope violation — no regex heuristic on the change description, use the actual diff.
5. A single `verify_task(...)` entrypoint that runs the applicable checks above and returns a dict with an honest boolean `passed` plus the raw evidence (test output, diff, violations) — never a bare pass/fail with no evidence attached.

Each task in your output must include: task id, one-line goal, exact function signature or file to write, inputs/outputs, and explicit out-of-scope notes. Keep each task small enough that a fresh model with no other context could do it correctly from the task description alone.

Reply with the task list only, no other text.
