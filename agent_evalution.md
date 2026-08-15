# Cursor branch implementation evaluation

Date: 2026-08-15  
Branch: `cursor`  
Repositories reviewed:

- `/home/dyne/Documents/Coding/TriAPI`
- `/home/dyne/Documents/Coding/oh-my-llama`

## Scope

I read `AGENT_GUIDE.md`, `agent_testrun.md`, and the relevant parts of
`PLAN.md` before reviewing the implementation. The audit covered all four
worked cases recorded in the guide/testrun:

1. Ghostwriter with Tier 1 disabled.
2. TriAPI crash capture and self-fix drafting.
3. Failure-pattern lessons and advisory diff critique.
4. Generic/Amazon HTML ingestion.

The oh-my-llama worktree also contains a separate 92-file overhaul. Per the
approved scope, I did not alter or evaluate that overhaul except where one of
its files directly participates in the worked-case implementation or its test
suite.

## Executive result

The worked cases were not fully correct despite their recorded `completed`
statuses. The audit found and fixed multiple real defects:

- Importing `scripts.self_fix` replaced the process-wide `sys.excepthook`.
- Most real dispatch exceptions were captured by inner handlers and converted
  to `SystemExit`, bypassing the outer auto-queue path.
- Self-fix planning ran while resource-competing services were still paused.
- Crash-report writing could mask the original exception.
- Malformed lesson JSON called a nonexistent logging API and crashed loading.
- Malformed critique scores could abort dispatch after a fix already passed.
- The critique CLI called `critique_diff` with the wrong arguments.
- Critique configuration, cost accounting, and revision prompts were
  inconsistent with the documented behavior.
- Ghostwriter accepted orphan numbered files and duplicate prompt numbers.
- Amazon extraction crashed rather than falling back when BeautifulSoup was
  unavailable.
- `DocumentIngester` write actions bypassed the read-side path allowlist.
- Ingestion dependencies were optional even though the core `ghostwrite`
  command requires them.

After correction, TriAPI's new regression suite passes, the worked-case
oh-my-llama tests pass, and the full oh-my-llama suite passes.

## TriAPI changes

### Self-fix

Files:

- `scripts/self_fix.py`
- `scripts/triapi.py`
- `config/tiers.yaml`
- `logs/triapi_bugs/.gitkeep`

Changes:

- Removed the import-time `sys.excepthook` replacement and other unnecessary
  import-time mutation.
- Replaced the dual-purpose exception-hook API with an explicit
  `capture_crash(exc, *, run_id, context)` API.
- Made report creation fail-safe: any directory, serialization, or write error
  is logged and returns `None` without replacing the original exception.
- Reports now use timestamp/run-based names, timezone-aware timestamps, valid
  formatted tracebacks, and an explicit list of TriAPI source files extracted
  from traceback frames.
- Self-fix planner prompts explicitly identify source files and force the
  target to TriAPI's resolved repository root.
- Removed production `assert` use from the queue path and replaced it with an
  explicit refusal.
- Inner breakdown/dispatch exception handlers now save resumable state and
  re-raise the original exception; one outer path captures it once.
- Resource-guarded services resume before the potentially long planner call.
- A configuration failure during crash recovery cannot mask the original
  dispatch exception.
- Added `self_fix.enabled: true`.
- Added `triapi self-fix queue <bug_id>` for reports that were captured but not
  automatically drafted.
- Hardened report-ID lookup against path traversal.
- Preserved the documented recursion guard: runs marked as self-fix, and runs
  already targeting TriAPI itself, produce a report but do not recursively
  auto-draft another run.

Operational breakdown/planner responses with `status != "ok"` still exit
nonzero without generating self-fix reports. This is intentional: they are
normal backend/quota failures, not uncaught TriAPI code exceptions.

### Lessons

Files:

- `scripts/lessons.py`
- `knowledge/lessons.jsonl`
- `scripts/orchestrator.py`
- `scripts/tier1_escalate.py`
- `scripts/tier2_escalate.py`
- `scripts/tier3_escalate.py`

Changes:

- Fixed malformed-line logging to use `get_logger()` rather than a nonexistent
  module-level `tri_logging.warning`.
- Added exclusive locking, flush/fsync, and identity-based deduplication for
  JSONL appends.
- Changed lesson IDs/dates to consistent timezone-aware UTC values.
- Removed short extension noise such as `py` from token matching and weighted
  component/tag matches above generic description matches.
- Added CLI category selection.
- Removed two run-specific handoff artifacts from the curated seeded store.
- `human_handoff` now accepts a real component/target, records failures without
  claiming every handoff exhausted all tiers, deduplicates via `add_lesson`,
  and cannot fail the handoff if lesson persistence fails.
- Tier 1/2/3 lesson selection now receives the task description instead of
  relying only on the filename.

### Critique and revision

Files:

- `scripts/critique.py`
- `scripts/orchestrator.py`
- `scripts/tier1_escalate.py`
- `scripts/tier2_escalate.py`
- `scripts/tier3_escalate.py`
- `scripts/cost_report.py`

Changes:

- Removed duplicate module documentation and reused the shared fence parser.
- Fixed the CLI argument/signature mismatch.
- Added strict validation for outer CLI JSON, score range/type, and issues
  shape. Bad model output returns an advisory error instead of raising.
- Normalized verdicts from the same YAML threshold used by orchestration.
- Cost-logged `ok`, `skipped`, and `error` calls.
- Included critique token fields in run-level cost summaries.
- Guarded malformed numeric YAML values so critique can never abort a passing
  item.
- Honored `critic` support and `max_revision_attempts: 0`.
- Skipped blind revisions when a low score supplies no actionable issues.
- Revision prompts now say that the build passes and request only the named
  quality improvements; they no longer present an empty build error.
- Tier 1/2 now snapshot the same current file content for prompting and
  SEARCH/REPLACE application, matching Tier 3's race-safe behavior.
- Critique/revision exceptions remain advisory and never change `resolved_by`
  or trigger a handoff.

### Tests and documentation

Files:

- `tests/test_branch_features.py`
- `PLAN.md`
- `mapping.md`
- `agent_testrun.md`

Added 14 standard-library regression tests covering:

- no global exception-hook mutation;
- valid and failed crash capture;
- source-frame planner grounding;
- hardcoded TriAPI queue target;
- service-resume-before-queue ordering;
- preservation of the original exception when config is invalid;
- malformed lessons and deduplicated selection;
- malformed/valid critique output and threshold behavior;
- invalid critique config;
- failed-revision rollback;
- critique token accounting.

`PLAN.md` now records the audit as Phase 22, and `mapping.md` reflects the
completed worked cases and hardened APIs. Trailing whitespace in
`agent_testrun.md` was removed so the TriAPI diff passes `git diff --check`.

## oh-my-llama changes

### Ghostwriter

Files:

- `ohmyllama/ghostwriter.py`
- `tests/test_ghostwriter.py`

Changes:

- Reject duplicate prompt numbers.
- Reject numbered source files that have no matching prompt (the previously
  missing “vice versa” requirement).
- Expand `~` for CLI and programmatic job paths.
- Added tests for duplicate prompts, orphan files, user-home expansion,
  explicit temporary allowlist roots, and CLI `ghostwrite --help`.

The core style-profile, per-prompt draft, model selection, delimiter ordering,
and human-readable error behavior were otherwise correct.

### Ingestion and security

Files:

- `ohmyllama/capabilities/ingestion.py`
- `tests/test_ingestion_html.py`
- `docs/MAPPING.md`

Changes:

- Centralized canonical allowed roots and reused them for reads and writes.
- Write proposals can no longer create or overwrite arbitrary filesystem
  paths.
- Amazon extraction catches a missing BeautifulSoup dependency and continues
  to trafilatura/MarkItDown fallback.
- HTML reads replace invalid UTF-8 bytes instead of crashing an entire
  ghostwriter job.
- Added tests for BeautifulSoup fallback, invalid UTF-8, rejected outside
  writes, and allowed ghostwriter-root writes.
- Updated the security mapping to describe read/write roots,
  `OMLL_GHOSTWRITER_DIR`, trusted `extra_allowed_dirs`, and extraction order.

`extra_allowed_dirs` remains read-only by design. It is supplied by trusted
ghostwriter code, while `execute(document_ingester_write)` receives
agent-controlled action payloads and must not be able to grant itself a new
write root.

### Dependencies

Files:

- `pyproject.toml`
- `uv.lock`
- `src/semai/tooling/dep_triage.py`
- generated `docs/semai-preflight-p6-report.md`

Changes:

- Promoted `markitdown[pdf]`, `trafilatura`, and `beautifulsoup4` to core
  dependencies because `ghostwrite` is a core CLI command that cannot function
  without ingestion.
- Regenerated `uv.lock`.
- Added import names/classifications so the repository's dependency-triage
  seam remains complete.

This makes the default installation heavier, but avoids shipping a core
command that fails immediately after a normal `uv sync`.

## Verification performed

TriAPI:

```text
python3 -m unittest discover -s tests -v
14 tests passed

python3 -m py_compile scripts/*.py
passed

git diff --check
passed

PYTHONPATH=. python3 scripts/triapi.py self-fix --help
showed list, queue, show, approve

python3 -m scripts.lessons --help
passed
```

oh-my-llama:

```text
uv lock
resolved successfully

uv run pytest -q tests/test_ghostwriter.py tests/test_ingestion_html.py
21 passed

uv run python3 -m py_compile \
  ohmyllama/ghostwriter.py \
  ohmyllama/capabilities/ingestion.py \
  ohmyllama/cli.py
passed

PYTHONPATH=.:src uv run python tests/test_dep_triage_seam.py
passed

bash run_tests.sh
all script suites passed; pytest suites: 24 passed

git diff --check -- <worked-case files>
passed
```

The first full oh-my-llama run exposed the newly promoted dependencies as
unclassified in `dep_triage.py`. I corrected the classification and reran both
the seam and full suite successfully.

`uv run ruff check ...` was attempted, but `ruff` is not installed in the
environment (`Failed to spawn: ruff`). No dependency was added solely for this
audit; compilation, scoped diff checks, targeted tests, and the full project
suite were used instead.

## Residual risks and intentionally unperformed checks

- The two real Amazon fixture tests use absolute files under
  `/home/dyne/Documents/Ghostwriter` and skip on other machines. Portable
  synthetic tests cover extraction/fallback behavior, but CI does not reproduce
  the full real-page size/content checks.
- The trafilatura real-fixture length band can vary with extractor versions;
  the lockfile currently makes it stable for this environment.
- Self-fix plan drafting and critique were tested with mocks. I did not trigger
  paid/quota-consuming live Claude calls merely to test error plumbing.
- No deliberate live crash was injected into a background production dispatch;
  the shared foreground child path and capture/queue ordering are covered by
  regression tests.
- A full `git diff --check` for all of oh-my-llama remains blocked by unrelated
  pre-existing overhaul changes, including conflict-marker-like content in
  `docs/semai-phase3.md` and whitespace in unrelated files. The worked-case
  file set passes its scoped diff check.
- The unrelated 92-file oh-my-llama overhaul was explicitly outside this audit.
- No commits were created.

## Final assessment

The four worked cases are now implemented substantially more safely and match
their documented contracts. The highest-risk control flow—TriAPI crash
recovery and post-success critique—is fail-safe and regression-tested. The
remaining risks are portability/live-integration concerns rather than known
blocking correctness defects in the audited implementation.
