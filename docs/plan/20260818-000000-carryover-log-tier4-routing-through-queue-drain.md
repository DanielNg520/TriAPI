# PLAN.md archive — Session Carryover Log, 2026-08-18 through 2026-08-20

Moved out of PLAN.md 2026-09-01, same size-ceiling reason as the Phase 0-9/10-22 archives. This is the first half of PLAN.md's former '## Session Carryover Log' section (dated entries 2026-08-18 through 2026-08-20's queue drain); content is reproduced verbatim.

---

## Session Carryover Log

### 2026-08-18 — Tier 4 Task-Type Model Routing ✅

Replaced `tier_4_worker`'s `draft`/`fallback` pair with `default`
(`qwen2.5-coder:14b-instruct-q8_0`)/`polyglot` (`deepseek-coder-v2:16b`)/
`heavy` (`qwen2.5-coder:32b`) in `config/tiers.yaml`; `default_model` set to
`default`, which also serves as the safe fallback on `polyglot`/`heavy`
load failure; `gpt-oss:20b` and `qwen3-coder:30b-cc` fully retired (old
load-failure writeup deleted, was specific to the purged 30b/quant, doesn't
apply to the newly-validated `heavy` model); `scripts/ollama_load_check.py`
now resolves its `keep_model`/test model from config instead of hardcoding;
`AGENTS.md`/`README.md` updated to match.

### 2026-08-19 — Self-Improvement feature (17/17) ✅, q6_K model swap, Jules/Tier-2 billing corrections

Run `20260818-152401-a589da`, dispatched against `AGENTS.md`'s
"Self-Improvement feature" section. Landed all 5 phases: `scripts/hivemind_util.py`
(snippet parsing/retrieval, wired into Tier 4's prompt), `scripts/judge.py`
(`evaluate_design`/`extract_pattern` via Tier 3, fail-closed on peak-hours
skip/parse failure), `scripts/dispatcher.py`'s judge hook +
`handle_fix_forward` (single-attempt Tier 3 rewrite, revert-and-log-tech-debt
on failure) wired into the real `dispatch(state)` success path, atomic
`save_run` (`.json.tmp` + `os.replace`), `scripts/tech_debt.py`
(`log_tech_debt`/`read_tech_debt_entries`/`check_staleness`),
`scripts/triapi.py`'s `--tech-debt` CLI, and `AGENTS.md`'s doc index.
Final state: 64/64 tests passing, independently confirmed by a real Jules
advisory session (`sessions/16732276460987641790`) that also ran a repo-wide
`py_compile` sweep clean. Commit `e33a79c`.

**Systemic bugs found and fixed along the way** (each queued for a durable
pipeline fix in `CARRYOVER.md`'s Next up, per the standing "auto-queue
recurring bugs" rule):
- `extract_code()`'s truncated-response fallback (in both `tier3_escalate.py`
  and `tier4_worker.py`, the latter shared by Tier 1/2) silently wrote a
  truncated LLM response as if it were the complete file — fixed to fail
  closed (detect an unclosed code fence / `finish_reason: "length"`, return
  `None`/reject instead of writing garbage).
- `context_files` grounding gaps (hit twice): a new test file's plan item
  didn't include the module it was testing, so drafting tiers guessed blindly
  at the real API shape; separately, a test item had no example test file to
  anchor style, so tiers defaulted to `pytest` (not installed here, this repo
  is `unittest`-only). Both patched in-run via the run's state JSON; systemic
  fix (auto-include the tested module + a style-anchor test file) queued.
- Plan phase-ordering / import-dependency bug: a `dispatcher.py` edit added
  `from scripts import ... tech_debt` before the phase that creates
  `scripts/tech_debt.py` ran — broke `triapi`'s own CLI bootstrap entirely
  (couldn't import `dispatcher` to run anything, including the fix). Unblocked
  by reordering the plan (move `tech_debt.py`-creation earlier) plus a direct,
  minimal hand-write of `tech_debt.py` since even the reordered dispatch
  couldn't boot without it existing first.
- Mock-patch-target bug, confirmed recurring **4 times** across this run,
  including reintroduced by the pipeline itself while "fixing" already-correct
  code: `@mock.patch("scripts.orchestrator.run_task")` /
  `scripts.tier4_worker.run_build` patched the wrong module — `dispatcher.py`
  imports both via `from X import Y` (name-binding), so the mock never
  intercepted the real call. Net effect: "unit" tests were making real,
  billed Tier 4/2/3/1 network calls on every suite run (confirmed live: a
  7+ minute hang with an established TCP connection to Ollama). All instances
  fixed directly; systemic lint/plan-validation check (flag patches at the
  defining module instead of the importing one) queued as this session's
  top priority per user, alongside a related file-size/timeout finding (see
  below).
- One genuinely different bug: `scripts/triapi.py`'s new `cmd_tech_debt()`
  called `uuid.uuid4()` without `import uuid` — simple missing import, fixed
  directly.
- New structural risk identified: dispatch retrying an item whose file is
  already correct can cause a drafting tier to regress it while "fixing"
  something that wasn't broken (observed twice, both caught by immediate
  post-landing test-suite verification and fixed the same way).

**User-driven finding, now top of the CARRYOVER.md queue**: the plan chunks
*tasks* into small units but not *files* — `tests/test_branch_features.py`
kept growing (items said "extend" it rather than creating new feature-scoped
files) until Tier 4 routinely timed out just ingesting the existing content,
regardless of diff size. Compounded by the escalation rule requiring 2
consecutive Tier 4 failures before trying Tier 3 (~10 min of guaranteed dead
time on an already-oversized file). User's refined spec: (1) hard file-length
ceiling at Tier 4's context window as a plan-approval rule; (2) escalate to
Tier 3 after just 1 Tier 4 failure when the failure is itself the
oversize/timeout case.

**q6_K model swap**: `tier_4_worker.models.default` switched from
`qwen2.5-coder:14b-instruct-q8_0` to `qwen2.5-coder:14b-instruct-q6_K`, with
`num_ctx=24576` added to `scripts/tier4_worker.py`'s `call_ollama()`. Reason:
Q8_0 (18.4GB) left only ~1.6GB headroom against this machine's shared-RAM
iGPU setup (512MB real VRAM) and was timing out on every real drafting
prompt. Q6_K (~12GB) + 24k context KV cache (~4.6GB) lands at ~16.6GB,
notably more headroom. Live evidence: the trivial load-check diagnostic went
from 230s (Q8_0) to 1.57s (Q6_K) — but on the largest real files in this run,
results were mixed: some first-attempt successes with no timeout at all,
others still hit the 300s ceiling. Real improvement, not a complete fix —
see the file-size/timeout queue item above.

**Jules/Tier-2 billing corrections**: user confirmed the account has Google
AI Pro (raises Jules from Free tier's 15 tasks/24h to 100/24h) and that the
Cloud project behind the Gemini API key is billing-enabled ($10/mo +
$300 intro credit, which auto-qualifies for Tier 1+ paid API limits, not
free tier). `config/tiers.yaml` updated: `jules_tester.daily_task_limit`
15→100; `tier_2_manager.pricing.free_tier_rpm/rpd` 10/250→60/1500 (a
documented conservative floor, not an independently-verified ceiling for the
specific flash models this repo calls — see the file's own comment for what
to re-verify).

**Also this session**: `fewer-permission-prompts` allowlist added to
`.claude/settings.json` (codegraph explore, `journalctl --user`, `triapi
status`, local Ollama health-check `curl`, `systemctl --user status`); two
new standing memory rules saved (auto-queue fixes for recurring bugs found
mid-dispatch; standing overnight authority to decide minor issues and
fix-at-root-or-patch-and-queue without blocking on approval); oh-my-llama's
webui fully purged as a separate user-directed cleanup (systemd units for
web/brief/discord removed+disabled, `ohmyllama/webui.py` deleted, all
references cleaned from `config.py`/`state.py`/`cli.py`) and `ollama`/
`oh-my-llama-telegram` enabled for boot persistence on this always-on box.

### 2026-08-19 — Mock-Patch Target Lint Check: dispatcher integration and regression tests ✅

Landed the top-priority queue item from the 2026-08-19 entry (the recurring
mock-patch-target bug, confirmed 4 times): a lint that catches `@mock.patch(...)`
targets specified at the defining module when the code under test imports the
name via `from module import name`, so patches like
`@mock.patch("scripts.orchestrator.run_task")` can no longer silently fail to
intercept the real call and let test suites make live network calls (including
the 7+ minute Ollama hang observed in the previous session).

- **Lint implementation**: new static checker in `scripts/mock_patch_lint.py` that parses test
  files, resolves every `mock.patch`/`@mock.patch` target string, and flags any
  target whose attribute is name-bound into the file by a `from X import Y`
  import — i.e. a patch that cannot affect the imported alias. Fail-closed on
  parse ambiguity so a missed check can't quietly regress.
- **Dispatcher integration**: `dispatcher.py`'s breakdown/validation path now
  runs the lint over test-file items before dispatch and refuses to dispatch a
  known-bad item (returns a normal error result fed through the existing retry
  loop) instead of handing the broken test to the tier pipeline.
- **Regression tests**: coverage added under `tests/test_mock_patch_lint.py` exercising the lint
  itself (patch at the defining module passes; import-binding patch is flagged)
  and reproducing the exact `dispatcher.py`/`run_task`/`run_build` shape from
  the 2026-08-19 failures.
- **Verified**: the previously-failing suites now complete with zero live
  Tier 4/2/3/1 calls, and the full `py_compile`/test pass is green.

### 2026-08-19 — Test-file context_files grounding guard ✅

Closes the two confirmed incidents from 2026-08-18 (see `_find_anchor_test_file`'s
docstring): a test-file breakdown item that only referenced "the test file" /
"existing test patterns" without naming an exact path left the drafting tier
with no grounding context, so it hallucinated a test structure that matched
nothing in the repo; and when an anchor test file was picked by alphabetical
order instead of the project's canonical `tests/test_branch_features.py`, the
worker copied a pattern that didn't apply to this project's conventions.

- **Deterministic fix**: `_apply_test_context_guard()` in `dispatcher.py`'s
  `breakdown_plan()` now auto-populates `context_files` for every item whose
  target is a standard `tests/test_*.py` file: the companion
  `scripts/<name>.py` helper (the module under test, derived by stripping the
  `test_` prefix) is added when it exists on disk, and the project's anchor
  test file (`tests/test_branch_features.py` when present, else the first
  sorted `tests/test_*.py`) is added as a style anchor. Each item only
  receives its own companion, never another item's; if no anchor test file
  exists at all, the breakdown errors out instead of dispatching an
  ungroundable test item.
- **Regression tests**: coverage added under
  `tests/test_dispatcher_test_context_guard.py` exercising the guard directly
  (companion + anchor injection, missing companion no-op, no-anchor error
  path, non-test/git items left untouched) and both real failure shapes from
  the incidents above.
- **Two root-cause bugs found and fixed in the same landing pass** (the
  pipeline's own first draft got the wiring right but the logic wrong):
  (1) the companion-file lookup used the target's raw filename stem
  (`"test_hivemind_util"`) without stripping the `test_` prefix, so it
  searched for `scripts/test_hivemind_util.py` instead of
  `scripts/hivemind_util.py` — this defeated the guard's entire purpose,
  since it's the exact incident it exists to fix; (2) the anchor-file loop
  ran over *every* item unconditionally (including git items and non-test
  items) using one companion list shared across all test items in the
  batch, so one item could pick up another item's companion file. Both
  fixed at the root; each test item now only ever receives its own
  companion plus the anchor.
- **Verified**: full `py_compile`/test pass is green (97/97), including the
  new regression file (10/10).

### 2026-08-19 — Plan-completion integrity bug ✅

Two compounding root causes, both found live from a real false-complete
run (`20260819-063339-9d23c7`, Ollama lifecycle management): (1)
`_split_plan_by_phase()` in `scripts/dispatcher.py` only recognized `## `
ATX headers as phase boundaries; that run's plan used numbered
`1. Phase 1 — ...` markers instead, collapsing all 4 phases into one
chunk, and Gemini's `breakdown_phase()` silently extracted only 3 of ~10
real checklist items with no error. (2) `agents_md_gate.mark_plan_complete()`
unconditionally flipped every `- [ ]` to `- [x]` in a run's AGENTS.md block
once dispatch status was `"completed"`, with no check that the breakdown
actually covered every item — so the run reported fully done and cleared
the one-plan-per-repo gate while 3 of 4 phases silently never ran.

**Fix, landed via `triapi plan --refactor`/`dispatch` (run
`20260819-070113-94a8cf`):** `_PHASE_HEADER_RE` widened to also match
`\d+\.\s+Phase\b` (case-insensitive) alongside ATX headers.
`mark_plan_complete(project_dir, run_id, breakdown_item_count)` gained a
required third argument and now refuses (returns `False`, logs a warning,
writes nothing) whenever the AGENTS.md block's actual checkbox count
exceeds the breakdown's captured item count — defense in depth, since
plan-writing style will keep varying and the phase-header heuristic can't
cover every case. New `tests/test_plan_phase_split_and_completion_guard.py`
(5 tests).

**Two bugs found and fixed post-landing, before trusting this "done":**
(1) the landed regex's first draft, `\d+\.\s+(?:Phase\b|[A-Z])`, over-matched
— any numbered checklist item starting with a capital letter (e.g.
`"1. Task one"`) was misread as a new phase boundary, exactly the failure
class the 2026-08-13 checklist-regex fix already closed once; caught by
the new test file's own `test_numbered_phase_markers_split_into_multiple_chunks`
failing, narrowed to require the literal word `Phase`. (2) The new test
file itself imported `_split_plan_by_phase` from the wrong module
(`scripts.agents_md_gate` instead of `scripts.dispatcher`, plus a stale
copy-pasted module docstring referencing an unrelated incident) — fixed
directly.

**Second-order finding, evidence the fix is fail-safe rather than
complete:** this very fix's own dispatch run (`20260819-070113-94a8cf`)
recurred the *same* phase-collapse symptom on itself — its plan's phase
titles ("1. Fix `_split_plan_by_phase()`...", "2. Add a defense-in-depth
...") don't contain the literal word "Phase", so `_split_plan_by_phase`
still collapsed all 5 phases into one chunk. Unlike the original incident,
nothing was silently lost this time: `mark_plan_complete`'s new safety net
correctly refused (12 AGENTS.md checkboxes vs. 11 breakdown items) and
left the block unchecked rather than lying. Investigated by hand: the
11-vs-12 gap was a benign Gemini consolidation of two closely-related
checklist lines ("run the suite" + "inspect for skipped") into one
dispatch item, not a real drop — independently verified all 12 conceptual
requirements were genuinely satisfied (110/110 tests, AGENTS.md/CARRYOVER.md
actually updated), then manually completed the gate via
`mark_plan_complete(..., 12)`. Conclusion: the phase-header content
heuristic (layer 1) will keep being overfit to whatever phrasing motivated
the last fix — that's expected and acceptable, since layer 2 (the
count-guard safety net) converts a would-be silent failure into a visible,
investigable one instead. Not re-queuing a "smarter" heuristic; the
fail-safe behavior is the actual fix.

**Verified**: full suite green, 110/110, zero failures/errors/real skips.

### 2026-08-19 — Ollama lifecycle management for dispatch ✅

Closes a real gap: `resource_guard.unload_other_ollama_models()` only
unloaded *other* resident models via Ollama's own API and required
`ollama.service` to already be running — found live mid-session, the
service was down and `triapi dispatch` would have failed Tier 4 outright
rather than bringing it up. `resource_guard.py` gained
`snapshot_ollama_state(ollama_host, service="ollama.service") -> dict`
(records whether the service was active and which models were resident,
starting it if inactive) and `restore_ollama_state(snapshot, ollama_host)`
(reloads whatever was resident, stops the service again if it was
inactive before — safe no-op on a `None` snapshot). Landed in two passes:
the helpers first (as part of the plan-completion-integrity incident,
since that run's breakdown silently dropped the wiring/tests/docs phases
after only the helpers landed — see the entry above), then this run
(`20260819-075913-f230a9`) wired them into `scripts/triapi.py`'s
`cmd_dispatch`: snapshot right after `pause_services`, restore in the
same `finally` block that already calls `resume_services`, guaranteed on
success, caught exception, or crash.

**One regression found and fixed post-landing:** the first draft re-derived
`ollama_host` from `tiers_cfg["tier_4_worker"]["endpoint"]` a second time
inside the `finally` block, guarded only by `if tiers_cfg is not None`.
Three pre-existing crash-recovery tests in `tests/test_branch_features.py`
mock `load_tiers()` with a minimal config lacking `tier_4_worker` (they
test the crash path, not Tier 4 itself) — `tiers_cfg` was non-`None` but
missing the key, so the `finally` block itself crashed with `KeyError`,
masking the tests' actual assertions. Fixed at the root: capture
`snapshot_ollama_host` once, at snapshot time, and reuse that stored value
in `finally` instead of re-indexing `tiers_cfg` — a failed/incomplete
config now correctly skips restore instead of crashing. New
`tests/test_ollama_service_lifecycle.py`, verified clean against
`scripts/mock_patch_lint.py`.

**Verified**: full suite green, 111/111, zero failures/errors/real skips.

### 2026-08-19 — Plan phase-ordering / import-dependency guard ✅

Closes the real 2026-08-18 bootstrap-deadlock incident (a plan sequenced
`dispatcher.py` adding `from scripts import tech_debt` before the phase
creating `scripts/tech_debt.py`, breaking `triapi`'s own CLI boot).
`scripts/dispatcher.py` gained `_IMPORT_RE`/`_SCRIPTS_TARGET_RE`/
`_extract_imported_modules()`/`_enforce_module_import_order()`, wired into
`breakdown_plan()` right after all phases are broken down: scans every
item's description/build_cmd text for `from scripts import X` / `import
scripts.X`, and if an importing item's plan position precedes the item that
creates that module, auto-reorders the creator ahead of it (looped until
stable, capped at `total_item_count + 1` iterations, returning a clear
error string instead of hanging on an unresolvable circular case).
Pre-existing on-disk modules are correctly skipped as non-issues.
Regression coverage in new `tests/test_dispatcher_test_context_guard.py`-
style file `tests/test_import_order_guard.py` (8 tests), reproducing the
exact incident shape plus both import styles, no-op-when-already-ordered,
pre-existing-file skip, git-item skip, and the unresolvable-circular-case
error path.

**One bug found and fixed post-landing:** the plan's own verification item
used `grep -Fi "skipped"` against `python3 -m unittest discover -v` output
to check for `SKIPPED` tests — but this substring-matches test *names*
containing the word "skipped" (e.g. `test_malformed_lines_are_skipped`,
`test_jules_test_skipped_when_push_fails`), producing a false-positive
`human_handoff` on an otherwise-clean 105/105 suite with zero real skips.
Not a `dispatcher.py` bug — an artifact of this one plan item's
natural-language-generated `build_cmd` — independently verified clean and
patched the run result directly rather than churn a tier against a
non-existent problem. Worth remembering if it recurs: a correct check needs
a pattern anchored to unittest's actual verbose-output delimiter (`" ...
skipped"`), not a bare substring search.

**Verified**: full suite green, 105/105, zero failures/errors/real skips.

### 2026-08-19 — File-Size Ceiling Guard + 1-Attempt Oversize Escalation ✅

User observation, confirmed against real data from the Self-Improvement
run: plan breakdown chunks *tasks* into small units but never checks file
*size* — items repeatedly targeted the same, ever-growing
`tests/test_branch_features.py` instead of a new file per feature, so
Tier 4 had to ingest the whole existing file as context regardless of how
small the new task was, hitting real 300s timeouts. Compounded by
`escalation_rules.tier4_to_tier3`'s 2-consecutive-failure threshold — on a
file already too large for one window, that wasted a second full ~300s
timeout before Tier 3 (fast, no local model loading) got a chance.

**Patch 1** (`scripts/dispatcher.py`): `_enforce_file_size_ceiling()` +
`TIER4_MAX_CONTEXT_CHARS = 24576 * 3` (conservative chars/token floor over
Tier 4's `num_ctx=24576`), wired into `breakdown_plan()` alongside the
existing test-context/import-order guards — rejects the plan at breakdown
time if any file item's existing on-disk content already exceeds the
ceiling, naming the file and its size. **Patch 2**
(`scripts/tier4_worker.py`): `_tier4_fail()` gained
`is_oversize_failure: bool = False`, using threshold 1 instead of the
configured 2 when set; passed `True` from the `run_build()` timeout path
and the truncated-response path specifically, leaving every other failure
reason (Ollama unreachable, edit-block-apply failure, content-guard
rejection, ordinary `build_failed`) at the normal 2-attempt budget.

**Two bugs found and fixed post-landing:** (1) the truncated-response call
site never actually got `is_oversize_failure=True` added despite the plan
explicitly calling for it — caught by the new test file's own assertion
failing (`'build_failed' != 'escalate'`), fixed at the root. (2) The new
test file called `_enforce_file_size_ceiling()` with the wrong signature
(a bare item dict instead of `(phases, project_dir)`), plus dead
copy-pasted scaffolding code and a duplicate `if __name__ == "__main__"`
block — fixed directly. New `tests/test_file_size_ceiling_and_oversize_escalation.py`
(6 tests), verified clean against `scripts/mock_patch_lint.py`.

**Real architectural finding, not yet fixed (queued in `CARRYOVER.md`):**
`breakdown_plan()`'s post-breakdown guards (this one, the import-order
guard, the test-context guard) re-run on *every* call, including resuming
an already-fully-broken-down run — not just once after initial breakdown.
This run's own resume hit exactly that: items 1-7 had already landed, but
resuming to dispatch items 8-14 (verify-only checks and doc edits) re-ran
`_enforce_file_size_ceiling()` against the whole plan and found
`AGENTS.md` itself — a *later* item's target, unrelated to what was
actually being resumed — at 143,773 chars, over the new 73,728-char
ceiling. `AGENTS.md` genuinely is oversized (this repo's own doc-hygiene
rule, see `feedback_doc_hygiene_all_docs` memory) and this guard is
working exactly as designed; the bug is that a resume re-litigates
validation against unrelated items' *current* disk state instead of
trusting the prior successful pass. Completed items 8-14 by hand this
time (verify-only checks independently re-confirmed clean; doc edits are
supervisor-owned anyway) rather than block on this. Two real follow-ups
queued: shrink `AGENTS.md`, and make the breakdown guards run once, not
on every resume.

**Verified**: full suite green, 117/117, zero failures/errors/real skips.

### 2026-08-19 — Encrypted-secrets corruption incident + guard (oh-my-llama dispatch, run 20260819-132222-9de752)

**Incident:** a plan item's job was to *investigate* the openclaw gateway's
401 (read `.secret/secrets.json`'s `OPENCLAW_GATEWAY_URL`/`_TOKEN`, curl
the gateway) but the breakdown never marked it `verify_only: true`, so
`run_task()` sent it through the normal Tier 4→3→2 draft/patch pipeline —
each tier tried to *edit* the sops-encrypted file via `edit_blocks.py`
SEARCH/REPLACE as if it were an ordinary text file. Tier 4's attempt
failed cleanly ("SEARCH text not found verbatim"), but Tier 3/2's
attempt(s) corrupted the file's MAC (cryptographic authentication tag) —
`sops -d` started failing with `MAC mismatch` on the real, live file.

**Recovery (verified safe, not guesswork):** `sops -d --ignore-mac
--output-type json` on the corrupted file, then confirmed every one of
this session's Phase 1 secret changes (7 role pins) and the untouched
literature keys matched exactly what had already been verified earlier in
the same session — the underlying encrypted *values* were intact, only
the MAC/metadata trailer was damaged. Cross-checked against the newest
on-disk `.bak-20260803*` backup (98 keys vs. the recovered file's 114 —
a plausible 16-day growth delta, not evidence of loss). Re-encrypted the
verified-correct plaintext fresh via `sops -e`, confirmed byte-identical
round-trip decrypt, replaced the corrupted file, shredded every plaintext
temp artifact. `sops -d .secret/secrets.json` now succeeds with no flags.

**Root-cause fix** (`scripts/dispatcher.py`): new
`_is_sops_encrypted_file()` (detects a sops file by its own *unencrypted*
top-level `"sops"` metadata key — no decryption needed) and
`_enforce_no_raw_edits_to_encrypted_files()`, wired into `breakdown_plan()`
alongside the existing guards — refuses any non-`verify_only`, non-`git`
item whose target is sops-encrypted, forcing the real change to be
expressed as `sops set`/`--set` inside an explicit `build_cmd` on a
`verify_only` item (the pattern Phase 1's own items already used
correctly for the same file). New `tests/test_encrypted_file_edit_guard.py`
(7 tests).

**Also found and fixed while investigating:** `OMLL_MODEL_LITERATURE`
*did* contain the stale `BookWormXtreme/fimbulvetr-11b-v2` id (the
earlier assumption in this same plan that it didn't was wrong) — fixed via
`sops --set` to `hf.co/Sao10K/Fimbulvetr-11B-v2-GGUF:Q4_K_M`, matching the
already-pulled local tag. `OPENCLAW_GATEWAY_URL`/`_TOKEN` are both empty —
openclaw was never configured (consistent with `project_ohmyllama_pivot`
memory: the in-repo "openclaw" code predates and is unrelated to the real
openclaw.ai), not an expired-token bug; `catalog.py` already degrades to 0
openclaw models via its existing per-source `try/except`, confirmed by
direct code inspection, no code change needed there.

**Verified**: TriAPI's own suite green (92/92 across the touched test
files) both before and after the guard landed; the live dispatch's own
`sops -d`/`jq` checkpoints passed once the two affected breakdown items
were hand-corrected to `verify_only: true` and re-dispatched.

### 2026-08-19 — ohmyllama/state.py package split reverted: fabricated, not extracted

Same run (`20260819-132222-9de752`). The split completed all 12 items and
every one *reported* success, but a routine post-split import check
(`bash run_tests.sh`) caught a circular import in the new package's
`__init__.py` — investigating that surfaced something much worse.

**What actually happened:** across the 6 new mixin files, only
`_model_health.py` and `_observability.py` were faithful extractions of
the real code (correctly used the shared `self.db` connection). The other
four — `_queue.py`, `_approvals.py`, `_memory.py`, `_ingest.py` — were
wholesale **fabrications**: plausible-looking code with completely
different method names than the original (`claim_next`→`atomic_claim`,
`meta_get`/`meta_set`→`kv_meta_get`/`kv_meta_set`, `mail_is_seen`→
`insert_mail_seen`, `add_message`/`recent_messages`/`facts`/`put_fact`
missing entirely), `_approvals.py` opening its own disconnected
`sqlite3.connect()` per call instead of the shared `self.db`, `_queue.py`
using a nonexistent `self._db` attribute and containing **invalid SQL**
(PostgreSQL-only `FOR NO KEY UPDATE SKIP LOCKED`, which SQLite doesn't
support) plus a live bug (`now_iso() - timedelta(...)`, subtracting a
timedelta from a string). `__init__.py` itself never defined the actual
database connection/schema setup — `Store.__init__` called
`super().__init__(db_path=db_path)` into mixins that don't implement it.
Every item's own `build_cmd` (mostly `py_compile`) passed anyway, since
none of them exercise the actual runtime logic — the same blind spot
`content_guard.py` was built for in the 2026-08-10 incident, just one
layer deeper (a *plausible rewrite*, not a *content-losing* one, so the
existing retention-ratio guard had nothing to catch).

**Recovery:** `ohmyllama/state.py` was git-tracked (its own deletion,
`git rm`, was one of the split's own items) — `git checkout --
ohmyllama/state.py` restored the exact, complete, correct 1745-line
original with zero loss. Deleted the broken `ohmyllama/state/` package.
Presented the finding to the user with three options (revert / do the
full correct re-split now / pause); user chose revert. Re-applied the one
still-wanted change (item 8's quarantine-pruning fix,
`model_health()` — same `CASE WHEN quarantined_until > ? THEN
quarantined_until ELSE NULL END` design as the earlier PLAN.md entries)
directly to the restored flat file, plus its regression test in
`tests/test_queue_recovery.py`. The size-ceiling problem that motivated
the split in the first place (`state.py` at ~79KB, over the 73,728-char
Tier 4 ceiling) is **not re-solved** — deferred to a dedicated future
session, likely informed by `VIRTUAL_CODEBASE_PLAN.md`'s Slicer/
Materializer design rather than a repeat of this approach.

**Verified**: `bash run_tests.sh` clean (161/161) both immediately before
and after the quarantine fix, against the restored file.

**Open question for a future session, not this repo's or TriAPI's
existing guards:** nothing in the pipeline currently distinguishes "code
that plausibly compiles and passes its own narrow build_cmd" from "code
that's actually semantically equivalent to what it replaced." A
multi-file mechanical refactor (a plain split, no behavior change
intended) is exactly the case where a tier drafting one file at a time,
each with only that file's own narrow context, has the least grounding to
notice it invented new method names instead of copying real ones. Worth
its own guard or process change before attempting a split like this
again — noted here rather than immediately designed, since the right fix
depends on how `VIRTUAL_CODEBASE_PLAN.md`'s architecture (if built) ends
up handling multi-file moves.

### 2026-08-19 — Queue wrap-up: literature-id fix, and a real heavy-fallback wiring bug found post-verification

Applied directly (small, well-understood, single-value changes; not routed
through another dispatch given the session's track record with the
automated pipeline tonight): `DEFAULT_LITERATURE_MODELS`'s third entry
fixed from the stale `BookWormXtreme/fimbulvetr-11b-v2` to the actually-
pulled `hf.co/Sao10K/Fimbulvetr-11B-v2-GGUF:Q4_K_M`, in both
`ohmyllama/config.py` and its verbatim duplicate in
`src/semai/workers/ghostwriter.py`. Verified: `bash run_tests.sh` clean
(161/161).

**Then, sanity-checking the earlier "OMLL_MODEL_HEAVY" work while writing
this entry, found a real bug that had passed every check tonight:**
`.secret/secrets.json` has `OMLL_MODEL_HEAVY` set as an actual env-var
override (`"qwen3-coder:30b-cc"`, the old blacklisted single model) — the
Phase 2 plan item only changed `config.py`'s *default*
(`os.environ.get("OMLL_MODEL_HEAVY", "gpt-oss:20b,...")`), which is never
consulted while the env var is set. The whole ordered-fallback feature
built and fixed earlier this session was inert in practice. Fixed via
`sops --set` to the ordered list.

**Deeper bug, found immediately after:** even with the secret corrected,
`Config.load()` showed `models_for('heavy')` returning `('qwen2.5:7b-
instruct-q8_0',)` — the FAST tier's model, not the 3-item list.
`models_for(role)` resolves *role* names (router/chat/code/critic/...)
against `model_roles`; "heavy" is a *tier* name (fast/heavy/reasoning/
literature), never a role, so the lookup always misses and silently falls
through to `model_fast`. `orchestrator.py`'s `_model_for()` and
`_escalation_model()` both called `self.cfg.models_for("heavy")` for the
fallback list — this never worked. The unit test added earlier
(`test_model_for_primary_*`) never caught it because it mocked
`cfg.models_for` directly rather than exercising the real method against
a real-shaped `Config`.

**Fix:** new `Config.heavy_fallbacks()` (comma-splits `self.model_heavy`
directly, independent of the role system), both orchestrator call sites
repointed to it, the unit test's mock corrected to patch
`heavy_fallbacks` (matching what the real code now calls) instead of
`models_for`. Verified live against the real `Config.load()`:
`heavy_fallbacks()` → `('gpt-oss:20b', 'deepseek-r1:32b',
'qwen2.5-coder:32b')`, `models_for('heavy')` still correctly falls
through (confirms the distinction, not just a lucky pass). `bash
run_tests.sh` clean (161/161) after this fix too.

**Lesson for later sessions, general:** a unit test that mocks the exact
method under test's own name proves nothing about whether the *caller*
wired that method correctly — this bug survived a full plan, a real
dispatch, and a passing test suite because nothing ever exercised
`orchestrator.py` against the real `Config` class end-to-end for this
path. Worth remembering next time a "logic is correct, just needs a
smoke test" item gets marked done on mocked-interface tests alone.

### 2026-08-20 — Queue drain: items #1-3, #4b/#5, #4c all closed; four real pipeline bugs found and fixed

**#1-#3 (TriAPI's own repo, run `20260819-224114-9884f8`):** dispatched
clean, 11/11 items. `breakdown_plan()`'s guards now only run on fresh
chunk assembly, not on resume of an already-populated breakdown.
`planner.py`'s `SYSTEM_PROMPT` documents this box's real `sops` 3.8.1
syntax (`--set`, not the nonexistent `set` subcommand). `TIER4_MAX_CONTEXT_CHARS`/
`MAX_WRITE_CHARS` deduplicated into new `scripts/tier4_context.py`.
Also confirmed the piped-`approve`-blocked-by-classifier note from the
prior session no longer reproduces — `printf 'approve\n' | triapi plan
...` worked fine this session, used throughout.

**#4b/#5 (oh-my-llama, run `20260820-021946-1a1bd7`):** `ohmyllama/webui.py`'s
stray uncommitted deletion investigated and confirmed intentional (coordinated
with `cli.py`'s `_cmd_web` removal in the same uncommitted session, zero
importers) — finalized via `git rm`; `dep_triage.py`/`test_dep_triage_seam.py`
updated to reflect fastapi's real dead status; `run_tests.sh`'s skip removed.
`AGENTS.md` pruned 224KB → 55KB (stale plan blocks retired). This run
surfaced three real TriAPI pipeline bugs, found and fixed live mid-dispatch:

1. **`run_build()`'s 120s default timeout** (`scripts/tier4_worker.py`) —
   the 2026-08-11 fix that raised *some* call sites to `timeout=300` never
   touched all of them; 4 of 7 call sites (`orchestrator.py`'s
   `_rebuild_after_patch`/critique-revision rebuild, `tier4_worker.py`'s
   own initial build, `dispatcher.py`'s fix-forward rebuild) still used
   the 120s default, and oh-my-llama's full suite (now 86 test files)
   crossed that wall — every tier hit the identical timeout on the
   identical slow command, so the whole Tier4→3→2→1 chain escalated to
   human_handoff on a build that was actually passing. Fixed by raising
   the default itself to 300s so no call site can silently regress back
   to the short timeout.
2. **`content_guard.check_write()`'s oversized-write refusal deadlocked
   legitimate shrinking edits.** The check (added earlier the same
   session for the AGENTS.md-growing incident) refused *any* write whose
   result was still over `MAX_WRITE_CHARS`, with no exception for a write
   that's making genuine progress — so the very first correct, size-
   reducing edit to a doc mid-prune got refused outright. Fixed: refuse
   only when authoring a new oversized file or growing an existing one;
   allow when the write shrinks an already-oversized file, even if still
   over ceiling afterward. 5 new regression tests
   (`tests/test_content_guard.py`).
3. **`_item_deletes_target_file()`'s 80-char proximity window was a
   false-positive magnet.** A plan item's own prose ("delete everything
   between and including the `<!-- ... -->` markers ... from
   `AGENTS.md`") put the word "delete" and the filename in the same
   sentence without the item actually deleting the file — the loose
   window matched it as a whole-file deletion and skipped the size-
   ceiling guard entirely, sending an oversized file through Tier 4
   undefended. Fixed: require the delete verb's own grammatical object to
   be the target filename (verb immediately followed by the name, modulo
   articles/backticks/path prefix), not just co-occurrence anywhere in
   the description. 2 new regression tests.

Also hand-corrected (not a code bug, a one-off plan-generation mistake)
two self-referential verify commands the planner baked into this specific
plan: a `grep`/`awk` check for a run-id string that the plan's own
appended checklist item necessarily quotes while describing itself, so
the check could never pass regardless of correctness. Patched the stored
`build_cmd`s to tolerate the plan's own one expected self-reference
instead of requiring zero occurrences.

**#4c (oh-my-llama, run `20260820-081806-d7c25f`): `ohmyllama/state.py`
(1754 lines, 81KB) split into `ohmyllama/state/` package, this time
correctly.** The prior 2026-08-19 attempt (see entry above) fabricated 4
of 6 mixin files because each tier was asked to *draft* a file from a
method-name sketch, with only `py_compile` checking the result — a
plausible-looking rewrite passed every check while silently inventing
content. This attempt used a fundamentally different mechanism instead of
trying to catch fabrication after the fact:

- Every phase's `build_cmd` is a **deterministic AST-extraction script**
  (`ast.get_source_segment` against `git show HEAD:ohmyllama/state.py`)
  that performs the actual file-write itself — no tier ever drafts
  content; the script mechanically copies the named methods verbatim and
  writes the file. Every item is `verify_only: true`.
- A **completeness check** (its own phase, run before the old file is
  deleted) parses both the original `Store` class and the full new
  package with `ast` and asserts the method-name sets are byte-for-byte
  identical — nothing missing, nothing duplicated, nothing invented.
- Given the stakes (this exact task fabricated content last time), the
  whole breakdown was **hand-constructed and dry-run tested against a
  disposable `git worktree`** of the real repo (including a real
  `bash run_tests.sh` run) before being dispatched for real — not because
  the pipeline can't be trusted with routine work, but because handing an
  LLM's breakdown step a long embedded Python heredoc script risked
  transcription/truncation errors, and this was cheap to verify directly
  first.
- Also fixed live: `scripts/dispatcher.py`'s `_PHASE_HEADER_RE` didn't
  recognize `1. **Phase 1 — ...**` (bold-markdown-wrapped numbered
  headers) as a phase boundary, silently collapsing this specific
  14-phase plan into one chunk — the third real incident of this same
  header-recognition gap (2026-08-12 ATX-depth, 2026-08-19 numbered-with-no-hash,
  now bold-wrapped-numbered). Regex now tolerates up to two `*`/`_`
  emphasis markers before "Phase". New regression test.
- **Two real extraction gotchas found and fixed during dry-run testing,
  before anything touched the real repo:** (a) `ast.get_source_segment`
  excludes decorator lines for the node handed to it directly — `Task`/
  `Approval`'s `@dataclass(slots=True)` silently vanished, leaving plain
  classes with no generated `__init__` (`TypeError: Task() takes no
  arguments`); fixed by manually prepending decorator source. (b) a
  name-only, `FunctionDef`-only extraction missed **class-level `Assign`
  constants** sitting directly in `Store`'s body between methods
  (`_QUARANTINE_AFTER`/`_QUARANTINE_BASE_S`/`_QUARANTINE_MAX_S`,
  `_LIVE_NOTIFIED_COL`, `MAIL_BROADCAST_MIN_CONFIDENCE`) — every method
  referencing them broke (`AttributeError: 'Store' object has no
  attribute '_QUARANTINE_AFTER'`) since nothing copied the constant
  itself; extraction extended to also walk class-level `Assign` nodes,
  and the completeness check extended to verify constants too, not just
  methods.

**Verified independently, twice over:** local `bash run_tests.sh` (both
in the disposable dry-run worktree and for real in the dispatch) and a
separate Jules advisory session against the pushed branch — Jules ran in
a fresh clone with an empty `.state/ohmyllama.sqlite3` (one expected,
unrelated test failure from that: `test_migrate_facts_seam.py` needs
seeded fixture data) and confirmed 25 script suites + 158 pytest suites
otherwise green, "does not indicate a regression in the
`ohmyllama/state.py` file splitting that was performed."

**Lesson for later sessions:** when a task is genuinely mechanical
(copy this exact text from A to B, nothing judged or generated), prefer
building a deterministic script over asking an LLM tier to reproduce the
content from a description, even a very precise one — this session's
first attempt at #4c (identical file, identical method list, far more
explicit anti-fabrication instructions than the original 2026-08-19
prompt) still fabricated a dataclass on the first item, across all four
tiers, before the mechanism was replaced rather than the instructions
tightened further. Verification can catch fabrication; it can't make an
LLM stop generating when the task calls for copying.


---

