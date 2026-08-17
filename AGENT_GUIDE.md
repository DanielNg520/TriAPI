# Agent guide: operating TriAPI with Tier 1 off

For an agent (human-directed AI, not necessarily this same assistant)
running `triapi dispatch --no-tier1` or with `config/tiers.yaml`'s
`tier_1_manager.enabled: false`. Read this before dispatching in that mode.

## What actually changes

Only the **repair role** (`scripts/tier1_escalate.py`, called from
`orchestrator.run_task()`'s escalation chain) is disabled. The chain becomes:

```
Tier 4 (Ollama, local)  →  Tier 3 (DeepSeek)  →  [Tier 1 skipped]  →  Tier 2 (Gemini)  →  human_handoff
```

`triapi plan`'s interactive planning step (`scripts/planner.py`) is a
**separate code path and a separate config block** (`tier_1_planner`, not
`tier_1_manager`) — it still uses Claude Code CLI regardless of this switch.
Planning is unaffected; only automated repair loses its strongest tier.

## Why this changes your job

Tier 1 (Claude Code CLI) was the strongest automated repair tier — closest
in capability to a careful human edit, and the one most likely to correctly
diagnose a subtle bug or an ambiguous plan-item description rather than
pattern-matching a shallow fix. With it off, more items than usual will
exhaust Tier 4 → Tier 3 → Tier 2 and land in `human_handoff` — not because
the plan was worse, but because there's one less capable safety net between
"a cheap/local model's best guess" and "give up and ask a human."

**Practically: you (the agent running triapi in this mode) are now the
de facto Tier 1.** You take on three roles a fully-tiered run would have
partly automated:

1. **Planner** — still literally true regardless of the switch (`triapi
   plan` is always interactive and human/agent-reviewed before dispatch).
   Nothing new here, but worth restating: a vague or under-specified plan
   item that Tier 1 might have quietly disambiguated correctly will now more
   often surface as a stuck item instead — so scope plan items a little more
   precisely than you might with Tier 1 available.
2. **Supervisor** — expect to personally diagnose a higher fraction of
   `human_handoff`s. Two failure classes to distinguish immediately (same
   discipline this project has used throughout, see `PLAN.md`/`CARRYOVER.md`
   for many real examples):
   - **The build_cmd itself is broken/too weak** (a check that's
     environment-fragile, tautological, or doesn't actually assert the
     described change happened) — fix the check, not the code.
   - **A genuine gap** — the described change really didn't happen, or
     happened incorrectly/incompletely — fix the target file (by hand if
     needed) or let a corrected build_cmd give Tier 3/Tier 2 another real
     shot.
3. **Monitor** — watch dispatch output / `logs/triapi.log` actively rather
   than firing a long run and checking back at the end. A `stopped_on_failure`
   run does not resume itself; expect to intervene mid-run more often than
   with Tier 1 on.

## Concrete workflow when a human_handoff hits

1. Read `logs/escalation_<task_id>.md` — the actual last build error, not
   just the summary line. An empty or uninformative error body is itself a
   signal the build_cmd is weak (e.g. a bare `grep`/pipe failure with no
   real assertion), not that the fix attempts were all equally bad.
2. Read the actual target file's current diff (`git diff <target>`) —
   never trust a tier's reported `success`/`fix_rejected` status. Check
   whether the real described change landed, landed partially, or was
   replaced by unrelated scope-creep (a tier "fixing" something adjacent
   instead of the actual ask — has happened for real in this project).
3. If the build_cmd is at fault: patch it in **all copies** it can appear
   in — `state["breakdown"]["phases"][i]["items"][j]["build_cmd"]` (live
   definition), `state["results"][k]["build_cmd"]` (historical record,
   re-checked by `dispatcher._recheck_regression_flags()` before resume),
   and any `state["regression_flags"]` entry's own frozen snapshot. Missing
   one of these can cause a stale/wrong check to keep firing after you
   think you've fixed it.
4. Verify your fix manually before resuming: run the corrected build_cmd
   by hand against both the pre-fix and post-fix file state if possible,
   confirming it fails/passes as expected — a build_cmd that always passes
   (tautological) is worse than no check at all, since it hides the gap
   permanently instead of surfacing it once.
5. If you hand-patch the target file directly (rather than letting a tier
   redo it): mark that item's `results[]` entry `"status": "success"`,
   `"resolved_by": "manual"`, and refresh `"content_hash"` via
   `scripts.regression_guard.hash_file()` — otherwise the item stays
   `human_handoff` and blocks the run indefinitely, or a resume re-attempts
   Tier 4 from scratch and overwrites your fix.
6. Resume: `triapi dispatch <run_id>` (add `--background` for a long run
   over an unreliable connection). Confirm no dispatch process is already
   alive first (`pgrep -af "triapi dispatch"`) before hand-patching state —
   editing a run's JSON while a live process holds it risks a lost write.

## What's still safe to trust automatically

- Phase-by-phase `verify_only` items (pure checks, no draft step) — these
  never touch a file, so a `success` here is lower-risk to trust than a
  file-editing item's `success`.
- Tier 4/Tier 3/Tier 2 successfully resolving a *simple, well-scoped* item
  end-to-end — spot-check occasionally, but this project's real failures
  have concentrated in large/ambiguous items and weak build_cmds, not
  small precise ones.

## What never changes, switch or no switch

- **Never hand-edit a target repo directly.** Fix TriAPI's own scripts/
  config/build_cmds so the pipeline handles it correctly, or hand-patch a
  run's own state JSON per the workflow above — the actual file-content
  work for a *target* repo item still goes through a tier whenever
  possible. Hand-writing a target file's content should be a last resort
  when a tier has genuinely and repeatedly failed on that exact item, not
  a shortcut to avoid supervising.
- **Documentation in TriAPI's own repo** (this file, `README.md`,
  `PLAN.md`, `mapping.md`, `CARRYOVER.md`) is always fine to edit directly
  — it's not target-repo work and doesn't need to go through dispatch.
- **Verify, don't trust status.** The single most repeated lesson across
  this project: read the real file diff, the real escalation log, the real
  test output — never take a `success`/`completed` string at face value.

## Worked test case: ghostwriter (bare, local, no AI-detection loop)

A concrete, detailed plan for exercising `--no-tier1` mode end-to-end
against the real oh-my-llama repo. Brief rationale/scope is in
`GHOSTWRITER_PLAN.md` — this section is the detailed, dispatch-ready
breakdown, written specifically so another agent can hand it to
`triapi plan` (with `--no-tier1` active) as a realistic multi-file test and
practice the human_handoff workflow above on real escalations.

**Your job here is to run this through `triapi`, not to implement it.**
Concretely, in order:
1. Feed the phases below into `triapi plan --project-dir <oh-my-llama path>`
   (as-is, or split/reworded into your own prompt — re-phasing into your own
   words is fine, writing the actual code yourself is not) and approve the
   resulting plan after reading it in full, same discipline as everywhere
   else in this guide.
2. `triapi dispatch <run_id> --no-tier1` it.
3. **"Phase it out" only if the pipeline's own breakdown needs help** —
   e.g. if `triapi plan`'s draft doesn't naturally split into phases the
   way `dispatcher.py` expects, or a phase is too large for one item to
   resolve reliably (this project has repeatedly found "the giant single
   item" failure mode — see `PLAN.md`'s history). Re-splitting a plan into
   smaller, more resolvable phases before dispatch is a supervisor/planning
   judgment call, not implementation work — still fine to do by hand.
4. From dispatch onward: **you are the monitor and supervisor, not the
   worker.** Watch the run, diagnose `human_handoff`s using the workflow
   above (weak build_cmd vs. genuine gap), patch build_cmds/state JSON as
   needed, and — per "What never changes" below — only hand-write
   `ghostwriter.py`/`cli.py`/`ingestion.py` content yourself as a last
   resort after a tier has genuinely and repeatedly failed on that exact
   item, never as a shortcut to get through the plan faster. The point of
   this test is to see how the pipeline behaves with one fewer repair tier,
   not to produce the feature by any means necessary.

**Goal**: given a job folder, ingest style-reference files + per-prompt
source files, generate one `result.txt` with a draft per numbered prompt,
reusing the model in the user's own writing voice. No AI-detection/critique
loop, no Telegram delivery, no approval gate — v1 is a single pass per
prompt, straight to a text file, proofread by hand.

**Grounded against the real repo** (verified 2026-08-14, re-check before
relying on any of this if it's been a while):
- `ohmyllama/capabilities/ingestion.py`'s `DocumentIngester.read(path_str)`
  already extracts text from PDF/DOC/CSV/XLSX/HTML (via MarkItDown) and
  images (via a hardcoded `"moondream"` Ollama vision call) — reuse this,
  don't reimplement extraction. Its `read()` restricts access to an
  `allowed_dirs` allowlist (`~/Downloads`, `~/Documents`) — a ghostwriter
  job folder outside those will be rejected unless this plan's own item
  extends the allowlist (see Phase 1).
- `ohmyllama/llm.py`'s `client_for(cfg).chat(model, prompt, system=...)` is
  the one-shot chat-completion call used throughout this repo (e.g.
  `ohmyllama/cli.py:319`) — reuse this for both the style-profile call and
  the per-prompt draft call, not a raw HTTP call to Ollama.
- `ohmyllama/config.py`'s `Config.model_heavy` (`qwen3-coder:30b`) is the
  only locally-resident model sized for long-form generation in this
  repo's roster; `model_fast` is triage/classification-tuned, not prose.
  Use `model_heavy` for both model calls in this pass — do not add a new
  `model_ghostwriter` role speculatively (see `GHOSTWRITER_PLAN.md`).
- `ohmyllama/cli.py` follows a `_cmd_<name>(cfg, args) -> int` + argparse
  `sub.add_parser(...).set_defaults(fn=_cmd_<name>)` pattern (e.g.
  `_cmd_rag` at line ~316) — add the new command the same way, a plain CLI
  subcommand, not a semAI intent/worker registration. v1 doesn't need the
  intent-routing machinery (`src/semai/core/registry.py`) — this is a
  directly-invoked batch job, not something the router should guess at
  from free text.

### Phase 1 — Ingestion allowlist + folder-walk/pairing helper

1. `ohmyllama/capabilities/ingestion.py` — extend `DocumentIngester.read()`'s
   `allowed_dirs` check to also permit a configurable ghostwriter root (e.g.
   read from an env var `OMLL_GHOSTWRITER_DIR`, default
   `~/ghostwriter`), OR accept an explicit `extra_allowed_dirs` parameter
   threaded from the new command — pick whichever fits the existing method
   signature with the least disruption; do not silently bypass or remove
   the allowlist check itself, it's a real security boundary.
   - Verify: a `DocumentIngester().read(path)` call against a file inside
     the ghostwriter root succeeds (returns extracted text, not the
     `"Security Error"` string) in a real test.
2. New file `ohmyllama/ghostwriter.py` — folder-walk + pairing logic:
   - `discover_job(job_dir: Path) -> GhostwriterJob` (or similar): reads
     `sample/` (any file count), parses `prompt.md`'s numbered list
     (`^\d+\.\s+`), matches each prompt number to a root-level file sharing
     that number (`1.pdf`, `1.png`, `1.doc`, extension-agnostic match on
     the leading integer). A missing pair (a prompt with no matching
     numbered file, or vice versa) must raise a clear, human-readable error
     — never silently skip a prompt or a file.
   - Verify: a synthetic tmp-dir fixture (matching the shape in
     `tests/test_dep_triage.py` — build a fake job folder in
     `tempfile.TemporaryDirectory()`, no dependency on a real job) proves
     correct pairing, and proves a deliberately-introduced gap (e.g. prompt
     2 with no `2.*` file) raises instead of silently continuing.

### Phase 2 — Style profile + per-prompt draft

3. `ohmyllama/ghostwriter.py` (continued) — `build_style_profile(cfg, sample_texts: list[str]) -> str`:
   one `client_for(cfg).chat(cfg.model_heavy, prompt, system=...)` call over
   the concatenated `sample/` ingested text, producing a compact style
   summary (tone, rhythm, vocabulary, quirks) — NOT the raw sample text
   itself, so it can be reused cheaply across every per-prompt call instead
   of re-sending the full sample each time.
   - Verify: given a fixed fake sample text, the function returns a
     non-empty string shorter than the input (a real assertion on behavior,
     not just "doesn't crash").
4. `ohmyllama/ghostwriter.py` (continued) — `draft_for_prompt(cfg, style_profile: str, source_text: str, prompt_text: str) -> str`:
   one `client_for(cfg).chat(cfg.model_heavy, ...)` call combining the style
   profile, the paired source file's ingested text, and the prompt's own
   instruction text. No genre restriction — whatever the prompt asks for.
   - Verify: same fixture-based shape as above — non-empty output, and the
     function signature/call actually reaches `client_for(...).chat(...)`
     (e.g. via a monkeypatched/injected fake client in the test, asserting
     it was called with the expected model name — `cfg.model_heavy`, not a
     hardcoded string).

### Phase 3 — Orchestration + CLI entry point

5. `ohmyllama/ghostwriter.py` (continued) — `run_job(cfg, job_dir: Path) -> Path`:
   ties Phases 1-2 together — `discover_job()`, ingest `sample/` via
   `DocumentIngester`, `build_style_profile()` once, then for each paired
   prompt: ingest its source file, `draft_for_prompt()`, append to
   `result.txt` under a clear per-prompt delimiter (e.g. `--- 1 ---`).
   Returns the path to the written `result.txt`.
   - Verify: an end-to-end run against the synthetic tmp-dir fixture from
     Phase 1 (with a fake/injected LLM client so it doesn't need a live
     Ollama call in CI) produces a `result.txt` containing all expected
     delimiters in the right order.
6. `ohmyllama/cli.py` — add a `ghostwrite` subcommand: `_cmd_ghostwrite(cfg, args) -> int`
   calling `ghostwriter.run_job(cfg, Path(args.job_dir))`, printing the
   output path on success. Register via
   `sub.add_parser("ghostwrite", help="...").set_defaults(fn=_cmd_ghostwrite)`
   plus one positional `job_dir` argument, following the exact pattern of
   the existing `_cmd_rag`/`rag` subcommand wiring.
   - Verify: `python3 -m ohmyllama.cli ghostwrite --help` shows the new
     subcommand and its `job_dir` argument.

### Phase 4 — Final sweep (mandatory, same discipline as every other plan in this project)

7. Full real test suite: `bash run_tests.sh` (never `pytest --collect-only`
   or a partial subset) — confirms nothing in the existing test suite
   regressed.
8. `python3 -m py_compile ohmyllama/ghostwriter.py ohmyllama/cli.py ohmyllama/capabilities/ingestion.py` —
   confirms no syntax errors across every touched file.
9. Manual smoke test (documented as a verify step, not skipped): build a
   real tiny job folder under the ghostwriter root with one short sample,
   one short source file, one prompt, run the actual CLI command against a
   live local Ollama, and read the resulting `result.txt` by eye — this is
   the one step in this plan that a `build_cmd` genuinely cannot substitute
   for (judging prose quality is exactly the "good-vs-bad code/design
   judgment" problem this project has already flagged as needing new,
   not-yet-built infrastructure — see `PLAN.md`/`CARRYOVER.md`'s "Third
   queued item"). A human (or the supervising agent) reads the output and
   judges it, same as the user's own stated plan ("I will personally
   proofread to see how good it is").

**When using this as a `--no-tier1` test**: expect Phases 1-3 (real new
code, not doc/config tweaks) to be where Tier 1's absence is felt most —
`ghostwriter.py` is a brand-new file, and Tier 4/Tier 3 may need several
attempts or land on a `human_handoff` for the pairing-logic edge cases in
particular (gap detection, extension-agnostic matching). That's expected
and is exactly the scenario this guide's human_handoff workflow section is
for — don't treat a handoff here as a plan failure, treat it as the normal
cost of running without Tier 1.

## Worked test case: TriAPI self-fix (bug-detection-and-self-fix, part 1 of the "Third queued item")

A concrete, detailed plan for TriAPI's next queued *self*-feature: when a
`dispatch` run hits a genuine, uncaught TriAPI-level bug (not a normal
target-repo `human_handoff`), capture it structurally and auto-draft a
`triapi plan` against **TriAPI's own repo** to fix it — formalizing the
habit this project has used by hand throughout `PLAN.md`/`CARRYOVER.md`
(argv-size crash in `tier1_escalate.py`, silently-dropped phase in
`_split_plan_by_phase()`, zero-item vacuous-success breakdown, uncaught
`requests.RequestException` in `tier2_escalate.py`/`tier3_escalate.py` —
all found the same way: a human reading real output instead of trusting
reported status). Scope is deliberately narrower than "TriAPI writes
better code" — see `CARRYOVER.md`'s "Third queued item" note, which splits
this into two efforts and explicitly defers part 2 (design/quality
judgment, needs a new critique tier) to a later plan. **This section is
part 1 only: bug-detection-and-self-fix, reusing the existing binary
`build_cmd` pass/fail machinery as-is** — "genuine bug" here still means
something that concretely, verifiably fails (an uncaught exception, a
check provably tautological, a silent zero-result success), not a
subjective quality call.

**Your job here is to run this through `triapi` against TriAPI's own repo,
not to implement it by hand.** Per the standing rule (`CARRYOVER.md` §3,
"Never do a job TriAPI's own dispatch pipeline can do" — broadened
2026-08-12 to cover new feature work on TriAPI itself, not just
target-repo work): feed the phases below into
`triapi plan --project-dir <this TriAPI repo's own path>`, approve after
reading in full, `triapi dispatch <run_id>` it, and supervise exactly as
the ghostwriter test case above describes — weak-build_cmd vs.
genuine-gap diagnosis, patch build_cmds in the live breakdown, hand-write
a touched file only as a last resort after repeated tier failures on that
exact item. **Self-modification raises the stakes of "verify before
resuming"** — a bad automated edit here doesn't just break a test feature,
it can break the pipeline that's supposed to keep working correctly for
every future run, including the ability to detect and fix its own next
bug. Read every diff against the real files in `mapping.md`'s
`scripts/` section before trusting a `success`.

**Grounded against the real repo** (verified 2026-08-14, re-check before
relying on any of this if it's been a while):
- `scripts/triapi.py`'s `cmd_dispatch(run_id, background)` (line ~200) has
  exactly two places an unhandled exception can currently kill the whole
  process: the foreground `_breakdown_and_dispatch(state)` call (line
  ~238, already wrapped in `try/finally` for `resource_guard.resume_services`
  but nothing catches/classifies the exception itself), and the
  `--background` path's detached child, which re-execs
  `[sys.executable, script_path, "dispatch", run_id]` (line ~218-225)
  without `--background` and lands in that same foreground path. Both
  matter — a crash in either currently leaves nothing behind but a
  Python traceback in `logs/runs/<run_id>.log` (background) or on stderr
  (foreground) and whatever `resource_guard`'s existing `atexit` self-heal
  catches; no structured record survives for a human or a future pipeline
  to act on.
- `scripts/planner.py`'s `plan_turn(message: str, project_dir: str,
  session_id: str | None) -> dict` (line ~69) is the exact machinery
  `triapi plan` already uses — reuse it verbatim for auto-drafting a
  self-fix plan, don't build a second planning path. It already returns
  `{"status": "error", ...}` on its own internal timeout instead of
  raising (Phase 13-era fix, see `mapping.md`), so the self-fix drafter
  can treat that the same way `cmd_plan()` already does.
- `scripts/dispatcher.py`'s `new_run(prompt: str, project_dir: str) ->
  dict` (line ~541) and `load_run`/`list_runs` (lines ~515/520) are the
  existing run-state primitives — a self-fix run is a completely ordinary
  run in `logs/runs/<run_id>.json` with `project_dir` pointed at TriAPI's
  own repo root, nothing new needed in `dispatcher.py` itself for this
  part.
- `scripts/triapi.py`'s `main()` (line ~272) follows a plain
  `sub.add_parser("<name>", help="...")` + `set_defaults`/`args.command ==
  "<name>"` dispatch pattern for each subcommand (`plan`, `dispatch`,
  `status`, `list`) — add `self-fix` (with `list`/`show`/`approve`
  sub-subcommands, or a top-level `sub.add_parser("self-fix", ...)` with
  its own nested `argparse` group, whichever fits with the least
  disruption to the existing flat structure) the same way.
- `config/tiers.yaml`'s `tier_1_manager.enabled` on/off switch (Phase 20,
  same mechanism this guide's `--no-tier1` mode uses) is a precedent for
  where a new self-fix on/off switch belongs if one turns out to be
  needed (e.g. `self_fix.enabled`, default `true`) — don't invent a
  separate config file for one boolean.

### Phase 1 — Bug capture (crash → structured report, no behavior change on the happy path)

1. New file `scripts/self_fix.py` — `capture_crash(exc: BaseException, *,
   run_id: str | None, context: str) -> Path`: extracts
   `type(exc).__name__`, `str(exc)`, and the full formatted traceback
   (`traceback.format_exception`), plus `run_id` and a short `context`
   string identifying where the catch happened (e.g.
   `"cmd_dispatch:foreground"`), and writes one JSON file to
   `logs/triapi_bugs/<timestamp>-<run_id-or-'unknown'>.json`. Create the
   directory with a `.gitkeep` (same pattern as `logs/state/`), add
   `logs/triapi_bugs/*.json` to `.gitignore` alongside the existing
   `logs/` exclusions. Never raises itself — a failure to write the
   report must not mask or replace the original exception.
   - Verify: a real Python exception raised in a test, passed through
     `capture_crash()`, produces a JSON file with non-empty `traceback`,
     correct `exception_type`, and the file is valid JSON
     (`json.load()` round-trips it) — a real content assertion, not just
     "the function didn't crash."
2. `scripts/triapi.py`'s `cmd_dispatch()` — wrap the existing
   `_breakdown_and_dispatch(state)` call (inside the current
   `try/finally` around `resource_guard.resume_services`) so an
   exception is caught, passed to `self_fix.capture_crash(exc,
   run_id=run_id, context="cmd_dispatch")`, and **re-raised** (or the
   process still exits non-zero) afterward — this must not change
   existing crash-visibility/exit-code behavior at all, only add a
   structured record alongside it. Do not swallow the exception; a
   silently-caught crash that looks like a clean exit would be strictly
   worse than today's uncaught-traceback status quo.
   - Verify: a test that monkeypatches `_breakdown_and_dispatch` to
     raise a fake `RuntimeError`, calls `cmd_dispatch()`, and asserts
     BOTH that the `RuntimeError` still propagates (or `sys.exit` still
     fires non-zero — match whatever the real current behavior is) AND
     that exactly one new file appears under `logs/triapi_bugs/`
     containing that error's message.

### Phase 2 — Auto-drafted plan (reuses `planner.plan_turn`, human approval still required)

3. `scripts/self_fix.py` (continued) — `draft_self_fix_plan(bug_report:
   dict) -> dict`: builds a planning-prompt string from the bug report
   (traceback, `context`, the specific TriAPI source file(s) named in the
   traceback's own frames — extract via `traceback.extract_tb`, don't
   ask the model to re-derive the file from prose), prefixed with a
   fixed instruction that this is a TriAPI-internal bug fix, not
   target-repo work. Calls `planner.plan_turn(message, project_dir=
   <TriAPI's own repo root, resolved via `Path(__file__).resolve().
   parent.parent>`, session_id=None)` — the exact same call `cmd_plan()`
   makes, just with a generated `message` instead of a human-typed one.
   - Verify: given a fixture bug_report dict (a fake traceback string
     naming a real file in this repo, e.g. `scripts/tier1_escalate.py`),
     `draft_self_fix_plan()` returns the same `{"status": ..., ...}`
     shape `plan_turn()` normally returns — stub/monkeypatch the
     underlying `claude -p` subprocess call the same way this project's
     existing tests stub tier calls (see `tests/` for the pattern
     `tier3_escalate.py`/`tier4_worker.py` tests already use), so this
     doesn't require a live Claude session in CI.
4. `scripts/self_fix.py` (continued) — `queue_self_fix(bug_report_path:
   Path) -> dict`: reads a bug report JSON, calls
   `draft_self_fix_plan()`, and if it returns a usable `plan_text`,
   creates a normal run via `dispatcher.new_run(prompt=<the bug-fix
   framing text>, project_dir=<TriAPI's own repo root>)` and stores the
   drafted `plan_text` on it with `status="self_fix_drafted"` — **but does
   not call `dispatch()`**. `triapi self-fix approve` is the only
   transition from `self_fix_drafted` to `planned`. This is the queuing
   step only; a human still explicitly approves before anything executes,
   same discipline as
   `triapi plan`'s existing "nothing is built until approved" rule
   (`planner.py`'s own docstring/comment already states this — don't
   weaken it for self-fix).
   - Verify: given the same fixture bug report, `queue_self_fix()`
     produces a real `logs/runs/<run_id>.json` with
     `status="self_fix_drafted"`,
     non-null `plan_text`, and `project_dir` equal to TriAPI's own repo
     root (assert the actual path, not just "is a string").
5. `scripts/triapi.py` — new `self-fix` subcommand group:
   `triapi self-fix list` (lists `logs/triapi_bugs/*.json` not yet
   queued, plus queued-but-unapproved runs — reuses
   `dispatcher.list_runs()`, filtered), `triapi self-fix show <bug_id>`
   (prints the bug report + drafted plan text in full, same spirit as
   `cmd_status()`), `triapi self-fix approve <bug_id>` (the only
   state-changing entry point — flips the queued run to dispatchable,
   i.e. functionally identical to typing `approve` in `triapi plan`,
   reusing whatever `cmd_plan()`'s own approval path already does rather
   than duplicating it).
   - Verify: `triapi self-fix list` against a fixture
     `logs/triapi_bugs/` directory shows the right bug IDs and nothing
     else; `triapi self-fix approve <id>` on a fixture queued run leaves
     it in a state `triapi dispatch <run_id>` accepts (i.e.
     `state["status"]` is one of `cmd_dispatch()`'s own accepted values
     — `"planned"`, `"dispatching"`, `"stopped_on_failure"` per the real
     check at `triapi.py` line ~202 — verify against that exact set, not
     a guess).

### Phase 3 — Wiring + safety rails

6. Apply Phase 1's `capture_crash()` wrapping at **both** real
   crash-capable entry points identified above — the foreground
   `_breakdown_and_dispatch()` call in `cmd_dispatch()` and (since the
   `--background` child re-execs into the exact same foreground code
   path rather than a separate function) confirm by test that a crash
   during a `--background` dispatch also produces a bug report — no
   separate wrapping needed if Phase 1's placement is correct, but this
   must be verified, not assumed, since the background path's
   stdout/stderr redirect to `logs/runs/<run_id>.log` could plausibly
   hide whether the wrapping actually ran.
7. **Self-fix must only ever target TriAPI's own repo.** In
   `draft_self_fix_plan()`/`queue_self_fix()`, hardcode or explicitly
   validate `project_dir` against TriAPI's own resolved repo root — never
   read a `project_dir` value out of the *failing* run's own state for
   this purpose, even though that seems convenient, since a bug
   corrupting that exact field is not implausible and must not be able
   to redirect the self-fix machinery at an unrelated repo.
   - Verify: a fixture bug report whose (attacker-controlled-shaped)
     fields include a bogus `project_dir`-like value is still queued
     against TriAPI's real root, never the bogus one — assert the
     resulting run's `project_dir` directly.
8. **No recursive self-fix.** If a dispatch run that is *itself* a
   self-fix run (marked with `self_fix_bug_report` when
   `queue_self_fix()` creates it) crashes, `capture_crash()` must still
   write the bug report (for human visibility) but the auto-drafting/
   queuing step (`Phase 2`) must not fire again for it — fall through
   to a plain, clearly-labeled stop instead, avoiding an infinite
   self-fix-of-a-self-fix loop. A crash in a normal run whose
   `project_dir` happens to be TriAPI's own root still auto-queues —
   that is the intended capture path for bugs found while working on
   TriAPI itself. The marker, not the project_dir, is the recursion
   guard.
   - Verify: a fixture crash inside a run whose state carries that
     self-fix marker produces exactly one bug report and zero new
     queued runs — assert `logs/runs/` didn't grow. A fixture crash
     in a TriAPI-rooted run *without* the marker does auto-queue.

### Phase 4 — Final sweep (mandatory, same discipline as every other plan in this project)

9. Full real test suite: `bash run_tests.sh` if this repo has one at
   dispatch time, otherwise this project's actual test runner as named
   in `README.md`/`mapping.md` — never a partial subset.
10. `python3 -m py_compile scripts/self_fix.py scripts/triapi.py` —
    confirms no syntax errors across every touched file.
11. Manual smoke test (documented as a verify step, not skipped):
    on a throwaway branch/copy, deliberately reintroduce one of the
    already-fixed real crashes documented in `mapping.md` (e.g.
    temporarily remove `tier1_escalate.py`'s `try/except (OSError,
    subprocess.TimeoutExpired)` guard around its `subprocess.run()`
    call), trigger a dispatch that hits it, confirm a bug report lands
    in `logs/triapi_bugs/`, `triapi self-fix list` shows it, and
    `triapi self-fix show <id>` displays a plan that plausibly names the
    right file and the right fix — then revert the deliberate
    regression before it touches the real repo state. Judging whether
    the *drafted plan itself* is sensible (not just non-empty) is the
    one step here a `build_cmd` genuinely can't substitute for, same
    reasoning as the ghostwriter test case's own prose-judgment step
    above.

**When using this as a test**: expect this to surface real edge cases in
how cleanly TriAPI's own exceptions are currently caught — per
`mapping.md`, most of the individual tier scripts (`tier1_escalate.py`,
`tier2_escalate.py`, `tier3_escalate.py`, `tier4_worker.py`) already wrap
their own request/subprocess failures and return a normal `status:
"error"` result rather than raising, which means Phase 1's crash-capture
will mostly only fire for the *next*, not-yet-discovered bug class — same
as every other real bug found in this project's history. That's the
point: this feature exists for the failure mode this project keeps
finding by hand, not the ones already fixed.

## Worked test case: clean Amazon-page ingestion for ghostwriter

A concrete, detailed plan for improving `DocumentIngester`'s HTML path
(`ohmyllama/capabilities/ingestion.py`) so ghostwriter jobs whose numbered
source files are saved Amazon product pages (`.html`) get usable extracted
text instead of mostly-navigation noise. Discovered supervising a real
ghostwriter job attempt against `/home/dyne/Documents/Ghostwriter` (13
saved Amazon product-page `.html` files) — this is real-world-motivated,
not speculative.

**Your job here is to run this through `triapi` against oh-my-llama, not
to implement it by hand.** Same standing rule as the two worked cases
above: `triapi plan --project-dir <oh-my-llama path>`, approve after
reading in full, `triapi dispatch <run_id>`, supervise (weak build_cmd vs.
genuine gap, hand-write only as a last resort). This is target-repo work
(oh-my-llama), same category as the ghostwriter case — not TriAPI
self-modification, so the self-fix section above doesn't apply here.

**Grounded against the real repo** (verified 2026-08-14 by directly
reading a real ingestion, not assumed):
- `DocumentIngester._ingest_html()` (`ingestion.py` line ~159) already
  has the *right idea* wired in: try `trafilatura.extract()` for clean
  main-content text, fall back to the generic MarkItDown path
  (`_ingest_generic()`) only `except ImportError` or if `trafilatura`
  returns empty. **The bug is that `trafilatura` is not actually a
  dependency** — it's absent from `pyproject.toml` (confirmed: only
  `markitdown[pdf]>=0.0.1` is listed, no `trafilatura` anywhere), so in
  every real environment today the `except ImportError: pass` branch
  silently fires and every `.html` file falls all the way through to
  `_ingest_generic()` — the noisiest path, not a deliberate design
  choice. This alone explains the bad result: a real 240W-cable Amazon
  page ingested via the current (broken-fallback) path produced **135,478
  characters**, with the actual `Product Description` text not starting
  until character ~55,500 — everything before it is Amazon's nav menu,
  department list, keyboard-shortcut list, and an "Alexa AI" widget.
- Installing `trafilatura` and re-running `trafilatura.extract()` against
  the *same* real file (verified directly in a throwaway venv, not
  assumed) drops it to **22,170 characters** — a real ~6x reduction — and
  the actual `Product Description`/feature-bullet text is reachable at
  character ~11,500 instead of ~55,500. **Still not clean**: the first
  ~11K characters are whitespace-mangled price-history and delivery-date
  widget text ("Price history", "FREE delivery Tomorrow, August 15",
  columns of blank lines from a stripped table layout) — trafilatura's
  generic "main content" heuristic partially works on Amazon's
  JS-heavy/widget-dense markup but doesn't fully separate widget chrome
  from the actual description. So: trafilatura is a necessary, cheap,
  *generic* fix (helps every HTML source, not just Amazon), but is not by
  itself sufficient for Amazon pages specifically — that's Phase 2 below.
- `ext in (".html", ".htm")` already routes to `_ingest_html()`
  (`ingestion.py` line ~77-78) — no dispatch changes needed, only the
  method's own internals.
- No test file currently exercises `_ingest_html()` at all (grep
  `tests/` for `_ingest_html`/`trafilatura` before assuming otherwise —
  re-confirm at plan time) — this plan is also adding first-time coverage
  for a previously-untested code path, not just fixing behavior nobody
  was checking.

### Phase 1 — Wire up the already-intended trafilatura path (generic fix, benefits all HTML sources)

1. `pyproject.toml` — add `trafilatura` to the real dependency list
   (alongside the existing `markitdown[pdf]>=0.0.1` line), pin a lower
   bound the same way that line does, then `uv lock` so `uv.lock`
   reflects it. Do not vendor or hand-roll a substitute — the code
   already expects the real package's `trafilatura.extract()` API.
   - Verify: `uv run python3 -c "import trafilatura"` succeeds (currently
     fails with `ModuleNotFoundError` — confirm the failing case first,
     then confirm it passes after the dependency lands, a real
     before/after assertion, not just "doesn't crash now").
2. New test `tests/test_ingestion_html.py` (or extend an existing
   ingestion test file if one turns out to exist — re-check) —
   `test_ingest_html_uses_trafilatura_when_available`: feed
   `DocumentIngester()._ingest_html()` a small synthetic HTML fixture
   with an obvious nav/menu block AND an obvious content block (e.g. a
   `<nav>` full of junk links plus an `<article>` with a distinct sentence),
   assert the returned text contains the article sentence and does
   **not** contain the nav junk — a real content-shape assertion, not
   just "returns non-empty string". Also add
   `test_ingest_html_falls_back_without_trafilatura`: monkeypatch the
   import to fail (simulating the pre-fix environment) and assert it
   still returns *something* usable via `_ingest_generic()` rather than
   crashing — preserves the existing fallback behavior as a real
   contract, not just an implementation detail.
3. Manual verify against the real fixture: re-run the same command used
   to discover this bug —
   `uv run python3 -c "from ohmyllama.capabilities.ingestion import DocumentIngester; print(len(DocumentIngester().read('<path to a real saved Amazon .html file>')))"`
   — confirm the returned length drops from the ~135K-character
   MarkItDown-fallback range to the ~20K-character trafilatura range on
   at least one real file (not just the synthetic fixture), same
   discipline as this plan's own grounding above.

### Phase 2 — Amazon-specific structured extraction (targeted, on top of Phase 1)

4. `ohmyllama/capabilities/ingestion.py` — add a private
   `_looks_like_amazon_product_page(html: str) -> bool` heuristic (e.g.
   checks for `id="feature-bullets"` or `id="productDescription"` or
   `id="dp-container"` markers that are stable across Amazon's product
   page template — verify these exact IDs against a real saved page
   before hardcoding, Amazon's markup drifts and this plan's own IDs are
   only as good as the one file inspected so far) and a
   `_extract_amazon_product(html: str) -> str | None` function using
   `BeautifulSoup` (already an implicit dependency via `markitdown`/
   `trafilatura` — confirm at plan time whether it needs to be added to
   `pyproject.toml` directly rather than relying on a transitive
   dependency, which is fragile) to pull just: the product title
   (`#productTitle`), the feature bullets (`#feature-bullets li`), and
   the product description block (`#productDescription`,
   `#aplus_feature_div`, or whichever the real page actually uses —
   confirm exact selector against a real saved file before writing the
   plan item's `build_cmd`, don't guess blind). Returns `None` (not an
   empty string) if the page doesn't match the expected structure, so
   the caller can fall back cleanly rather than silently returning
   nothing useful.
5. `_ingest_html()` — call `_looks_like_amazon_product_page()` first; if
   true, try `_extract_amazon_product()` and use its result if non-`None`,
   otherwise fall through to the existing trafilatura → generic chain
   from Phase 1 unchanged. This must be a strict narrowing (Amazon-only),
   never a change to how non-Amazon HTML is handled — the whole point is
   this is an *additional*, targeted branch, not a replacement for the
   generic path.
   - Verify: a real saved Amazon product page (`.html`) run through
     `_ingest_html()` now returns text under some concrete, asserted
     size ceiling (pick a real number after inspecting actual output —
     e.g. "under 3,000 characters" based on what a title + bullets +
     description block actually run to on a real file, don't invent a
     number blind) and contains the exact known feature-bullet text
     confirmed present in the real file inspected during grounding
     above (the `◆Note:`/`◆90° Elbow Design` bullets from the 240W-cable
     page, or whichever file the plan's own item ends up testing
     against) — a real content match, not a size check alone (a
     build_cmd that only checks length is exactly the "weak build_cmd"
     failure class this project has hit repeatedly, see the
     human_handoff workflow section above).
6. A second real saved Amazon page from the actual job folder (pick one
   with a visibly different category/template shape than the first, e.g.
   a fashion/clothing listing versus the electronics one already
   inspected, since Amazon's template can vary by category) run through
   the same extraction, to catch a selector that only happens to work on
   the one file this plan was grounded against — confirm it still
   returns real bullet/description text and not `None`/empty.

### Phase 3 — Final sweep (mandatory, same discipline as every other plan in this project)

7. Full real test suite: `bash run_tests.sh` — confirms nothing
   regressed, including in `tests/test_ingestion_html.py` from Phase 1.
8. `python3 -m py_compile ohmyllama/capabilities/ingestion.py`.
9. Manual smoke: re-run an actual `ghostwrite` job (or at minimum
   `DocumentIngester().read()`) against 2-3 real files from
   `/home/dyne/Documents/Ghostwriter` — the `.html` files with their
   original (non-renamed) descriptive filenames still work fine for this
   smoke step since it's calling `DocumentIngester` directly, not going
   through `discover_job()`'s numbered-pairing requirement — and read
   the output by eye to confirm it reads like an actual product
   description, not a page dump. This is the step a `build_cmd` can
   assert *shape* for but a human/agent should still eyeball once, same
   reasoning as the other two worked test cases' own final smoke steps.

**When using this as a test**: Phase 1 alone (the missing-dependency fix)
is a good small-scope, low-ambiguity item to see the pipeline resolve
cleanly even with Tier 1 available or not — it's a one-line dependency
addition plus wiring already half-built. Phase 2 is where real judgment
enters (selector choice, "does this count as clean enough"), and is a
better test of whether a tier can follow a precisely-scoped-but-genuinely-
new-code item versus where it needs supervisor correction — don't be
surprised if Phase 2's `_extract_amazon_product()` needs at least one
human_handoff round on selector correctness, same as `ghostwriter.py`'s
own pairing logic did in its worked test case above.

## Worked test case: TriAPI learning (failure-pattern knowledge store + diff-quality critique)

Unlike the three worked cases above, **this one is not a fresh plan to
write** — it's an already-planned, already-approved run sitting idle in
`logs/runs/20260812-202927-aa0e40.json` (`status: "planned"`,
`plan_text` populated in full), authored 2026-08-12, queued but
deliberately never dispatched because a different oh-my-llama run held
the shared Ollama/`resource_guard` lock at the time. **Confirmed still
current** (2026-08-14): no live `triapi dispatch` process right now
(`pgrep -af "triapi dispatch"` returns nothing), the run's own `status`
is still `"planned"`, and the specific line numbers/call sites its
checklist items reference (`orchestrator.py`'s `human_handoff()` at line
46, `build_edit_prompt_header()`'s call sites in all four tier scripts)
still match the real files closely enough to trust — re-check this
yourself before dispatching if it's been a while, same discipline as
every other "grounded against the real repo" note in this guide, since
line numbers drift as the repo evolves.

**Your job here is simpler than the other three cases: re-verify the
checklist below is still accurate against the current repo state (line
numbers drift — check each referenced call site before trusting it),
then either `triapi dispatch 20260812-202927-aa0e40 --background` the
existing approved run as-is, or feed this same text into a fresh
`triapi plan` if your re-check finds it meaningfully stale (a referenced
function renamed/removed, not just a shifted line number) — then
supervise exactly as the other three cases describe: weak build_cmd vs.
genuine gap, hand-write only as a last resort.** This is part 2 of
`CARRYOVER.md`'s "Third queued item" ("good-vs-bad code/design judgment
for TriAPI" / the user's own phrase "learning capacity" — see
`CARRYOVER.md`, search "Third queued item"), scoped into two
independent, sequenced phases. This repo currently has no `tests/`
directory of its own (confirmed at plan-authoring time — re-check before
assuming), so every verify below is `python3 -m py_compile` (syntax)
plus a direct `python3 -c` smoke invocation exercising the new function
against real repo state, same convention prior TriAPI phases used.

### Phase A — Failure-pattern knowledge store (the "learning" half)

1. New `knowledge/lessons.jsonl` (new top-level `knowledge/` dir —
   deliberately *not* under `logs/`, which `.gitignore` excludes
   wholesale via `logs/*.jsonl`; this store is committed project
   knowledge, like `PLAN.md`/`CARRYOVER.md`, not runtime state). Seed it
   with one JSON line per real historical example already on record in
   `CARRYOVER.md`, each object:
   `{"id": "<slug>", "date": "YYYY-MM-DD", "category":
   "bug_fix"|"unresolved_pattern", "component": "<file/module>",
   "bug_description": str, "what_went_wrong": str, "fix_description":
   str, "tags": [str, ...]}`. Seed with at least these 3 (paraphrased
   from `CARRYOVER.md`, not fabricated): (1) `edit_blocks.py`'s
   `BLOCK_RE` regex requiring a mandatory `\n` before `>>>>>>> REPLACE`,
   which structurally could never match the natural no-blank-line
   empty-REPLACE form the prompt itself instructs models to produce for
   deletions — fixed by `\n>{3,}` → `\n?>{3,}`; (2) `dispatcher.py`/
   `triapi.py`'s breakdown-RPM-resumability gap — an RPM-throttled
   `breakdown_phase()` failure set run status to `"failed"`, but
   `cmd_dispatch` only accepts `planned`/`dispatching`/
   `stopped_on_failure`, silently blocking an otherwise-clean resume
   path; fixed by moving the `check_tier2_ok()` guard inside the
   existing per-attempt retry loop and using `"stopped_on_failure"`
   instead of `"failed"`; (3) `dispatcher.py`'s tautological
   verify-grep — a checklist item's own "verify no call sites remain"
   grep passed trivially against dormant/commented files while the real
   `_CAPABILITY_FACTORIES` registry entries were still live; fixed by
   checking the one ground-truth signal (registry dict) instead of a
   bare substring grep.
   - Verify: `python3 -c "import json; [json.loads(l) for l in
     open('knowledge/lessons.jsonl')]; print('ok')"`.
2. New `scripts/lessons.py` (Python 3.10+ style, `str | None` unions,
   matching this repo's existing convention). Implements:
   - `LESSONS_PATH = Path(__file__).resolve().parent.parent /
     "knowledge" / "lessons.jsonl"`
   - `load_lessons() -> list[dict]` — reads and parses every line,
     skips/logs malformed lines via `tri_logging` rather than crashing.
   - `add_lesson(bug_description: str, what_went_wrong: str,
     fix_description: str, category: str = "bug_fix", component: str =
     "", tags: list[str] | None = None) -> dict` — appends one new
     record with a generated `id` (slug from `component`+timestamp) and
     today's date; returns the record written.
   - `select_relevant(target_name: str, description: str, max_n: int =
     3) -> list[dict]` — deterministic keyword-overlap scoring (no LLM
     call — this must be cheap/local since it runs before every tier
     prompt): tokenizes `target_name` (minus extension) + `description`,
     scores each lesson by overlap against its own
     `component`/`tags`/`bug_description` tokens, returns top `max_n`
     non-zero-scoring lessons (empty list if nothing scores, not padded
     with irrelevant ones).
   - `format_lessons_for_prompt(lessons: list[dict]) -> str` — renders
     the given lessons as a markdown "## Known past mistakes on this
     project (do/don't)" block, one `- **Don't:** <what_went_wrong>
     **Do:** <fix_description>` bullet per lesson; returns `""` if
     `lessons` is empty (so callers can unconditionally append it with
     no blank-section artifact).
   - `main()` CLI (`argparse`): `python3 -m scripts.lessons add --bug
     "..." --wrong "..." --fix "..." --component scripts/foo.py --tags
     tag1,tag2` — the manual-capture path a supervising session runs
     after hand-fixing a genuine TriAPI bug (per the user's own global
     instruction to keep persistent project knowledge updated after
     every implementation — this gives that habit a queryable store
     instead of prose-only `CARRYOVER.md` history).
   - Verify: `python3 -m py_compile scripts/lessons.py && python3 -c
     "from scripts.lessons import load_lessons, select_relevant,
     format_lessons_for_prompt; ls=load_lessons(); print(len(ls));
     print(format_lessons_for_prompt(select_relevant('edit_blocks.py',
     'fix a SEARCH/REPLACE regex')))"` — confirms the seeded regex-bug
     lesson surfaces for a relevant query.
3. `scripts/edit_blocks.py` — change `build_edit_prompt_header(
   target_name: str) -> str` to `build_edit_prompt_header(target_name:
   str, lessons_block: str = "") -> str`, appending `lessons_block` (if
   non-empty) after the existing `EDIT_INSTRUCTION` text, separated by
   `"\n\n"`. Default `""` keeps every existing call site working
   unchanged until each tier is updated in the next steps.
   - Verify: `python3 -m py_compile scripts/edit_blocks.py && python3 -c
     "from scripts.edit_blocks import build_edit_prompt_header as h;
     print(h('x.py')); print('---'); print(h('x.py', '## lessons\n-
     a'))"`.
4. `scripts/tier4_worker.py` — in `build_prompt(description,
   target_path, last_stderr, context_blob="")`, in the edit-mode header
   branch (existing-file case only — Tier 4 is in scope since drafting
   is cheap/local, the extra `select_relevant()` call costs nothing
   here), call `lessons.select_relevant(target_path.name, description)`,
   format via `lessons.format_lessons_for_prompt(...)`, and pass as
   `build_edit_prompt_header(target_path.name,
   lessons_block=lessons_text)`. Add `from scripts import lessons` to
   the imports.
   - Verify: `python3 -m py_compile scripts/tier4_worker.py`.
5. `scripts/tier3_escalate.py` — same pattern in
   `build_stable_context(target_path, context_blob="")`: fetch relevant
   lessons keyed on `target_path.name` (this function doesn't currently
   receive a `description` parameter — check the real call chain before
   assuming otherwise; if it's still absent, key `select_relevant()` on
   `target_path.name` alone with an empty description string rather
   than plumbing a new parameter through `orchestrator.run_task()`,
   keeping this step additive-only). Add `from scripts import lessons`
   import.
   - Verify: `python3 -m py_compile scripts/tier3_escalate.py`.
6. `scripts/tier1_escalate.py` — same pattern at the
   `build_edit_prompt_header(target_path.name)` call site, keyed on
   `target_path.name` for the same no-description-in-scope reason. Add
   `from scripts import lessons` import.
   - Verify: `python3 -m py_compile scripts/tier1_escalate.py`.
7. `scripts/tier2_escalate.py` — same pattern at its own
   `build_edit_prompt_header(target_path.name)` call site. Add `from
   scripts import lessons` import.
   - Verify: `python3 -m py_compile scripts/tier2_escalate.py`.
8. `scripts/orchestrator.py` — in `human_handoff(task_id, reason,
   detail="")`, after the existing `escalations.jsonl`/summary-file
   writes, add one call to `scripts.lessons.add_lesson(...,
   path=lessons.HANDOFF_LESSONS_PATH)` with `category=
   "unresolved_pattern"` — auto-captures the near-term, low-risk case
   to gitignored `logs/handoff_lessons.jsonl`, not the committed
   `knowledge/lessons.jsonl` store. `select_relevant()` skips
   `unresolved_pattern` so these cannot crowd prompt injection. Add
   `from scripts import lessons` import. This function is already reused
   by `run_task()`'s tier-2-exhausted case, `verify_task()`'s
   verification-failure case, and `dispatcher.py`'s git-item failures —
   correct for all three, all genuine "the pipeline couldn't handle
   this" patterns worth capturing.
   - Verify: `python3 -m py_compile scripts/orchestrator.py && python3
     -c "
from scripts.orchestrator import human_handoff
from scripts.lessons import load_lessons, HANDOFF_LESSONS_PATH
before = len(load_lessons())
human_handoff('plan-test-task', 'test reason for verification only')
after = len(load_lessons())
assert after == before, (before, after)
assert HANDOFF_LESSONS_PATH.exists()
print('ok, committed store unchanged')
"` then delete the matching `logs/escalations.jsonl`/
     `logs/escalation_plan-test-task.md` / `logs/handoff_lessons.jsonl`
     artifacts afterward.
9. `mapping.md` — add a `## knowledge/` section documenting
   `lessons.jsonl`'s schema and purpose, and update the `scripts/`
   section's entries for `lessons.py`, `edit_blocks.py` (new
   `lessons_block` param), `orchestrator.py` (auto-capture on handoff),
   and all four tier files (lessons now folded into their prompt
   headers), matching this file's existing per-file documentation
   style. Docs-only — re-read by eye to confirm it renders correctly
   rather than a shell verify.
10. `PLAN.md` — append a new `## Phase 17 — Failure-pattern knowledge
    store` section (or whatever the next free phase number actually is
    by dispatch time — re-check `PLAN.md`'s own numbering, don't assume
    17 is still free given other phases may have landed since this plan
    was authored) once Phase A is dispatched and lands, summarizing
    what was built and the seeded lessons.

### Phase B — Diff-quality critique step (the "good vs. bad code" half, strictly advisory, never blocking)

11. `config/tiers.yaml` — add a new top-level `critique:` block:
    ```yaml
    critique:
      enabled: true
      applies_to_tiers: ["tier_3", "tier_1", "tier_2"]  # Tier 4 excluded per explicit scoping decision
      critic: "tier_1"  # Claude Code CLI/Sonnet judges every diff, including Tier 1's own — subscription-covered, $0 actual cost
      score_threshold: 7  # out of 10; strictly below this triggers the one revision pass
      max_revision_attempts: 1  # hard cap, no further retries regardless of the revised score
    ```
    - Verify: `python3 -c "import yaml; c =
      yaml.safe_load(open('config/tiers.yaml'))['critique']; assert
      c['max_revision_attempts'] == 1; print(c)"`.
12. New `scripts/critique.py`. Implements:
    - `COST_LOG_PATH` same as other tiers, writes to
      `logs/cost_log.jsonl` with `"tier": "critique"`.
    - `build_critique_prompt(target_name: str, description: str,
      diff_text: str, tier_name: str) -> str` — asks the critic to score
      the *diff*, not the whole file: includes `description` (the
      task's stated goal), `tier_name` (context only, not to bias
      leniency), and `diff_text` (a real unified diff, keeping the
      critique call's input tokens small). Explicitly instructs: judge
      unnecessary complexity, wrong abstraction level, dead code left
      behind, and style consistency with the surrounding file.
    - `CRITIQUE_SYSTEM_PROMPT` — instructs the critic to respond with
      **strict JSON only**, no prose: `{"score": <int 1-10>, "verdict":
      "pass"|"revise", "issues": ["<short bullet>", ...]}`. `verdict`
      must be `"revise"` iff `score < score_threshold` (interpolated
      from `config/tiers.yaml`, not hardcoded) — but the caller checks
      the numeric threshold itself as the actual gate, never trusting
      the model's own `verdict` string alone.
    - `critique_diff(task_id: str, target_name: str, description: str,
      diff_text: str, tier_name: str) -> dict` — mirrors
      `tier1_escalate.escalate()`'s subprocess pattern exactly (same
      `claude -p --output-format json --tools "" --system-prompt ...`,
      prompt piped via **stdin** per the same argv-length lesson
      `tier1_escalate.py` already encodes — reuse that pattern, don't
      regress it): guarded by `budget_guard.check_tier1_ok()` first
      (returns `{"status": "skipped", "reason": ...}` on refusal,
      exactly like Tier 1 itself does — critique must never force
      metered billing); wraps `subprocess.run()` in the same
      `try/except (OSError, subprocess.TimeoutExpired)`
      `tier1_escalate.py` uses; on success, `json.loads()`s the result
      defensively (strip a possible surrounding code fence the same way
      `edit_blocks.apply_edit_blocks()` already does — reuse its fence
      regex rather than re-deriving it) and returns `{"status": "ok",
      "score": int, "verdict": str, "issues": list, "notional_cost_usd":
      float}`; a JSON-parse failure returns `{"status": "error",
      "reason": "..."}` rather than crashing — treated as "skip
      critique for this item" by the caller, never as a low score. Logs
      every call (skipped/error/ok) to `cost_log.jsonl` with the same
      `cost_usd: 0.0` / `notional_cost_usd` fields Tier 1 uses (same
      underlying `claude -p` call).
    - Verify: `python3 -m py_compile scripts/critique.py && python3 -c
      "
from scripts.critique import critique_diff
r = critique_diff('plan-test-task', 'foo.py', 'fix a typo', '--- a/foo.py\n+++ b/foo.py\n@@\n-foo bar\n+foo baz\n', 'tier_3')
print(r)
assert r['status'] in ('ok', 'skipped', 'error')
"` — a real end-to-end call against a trivial synthetic diff, confirming
      the JSON round-trips.
13. `scripts/tier3_escalate.py` — extend `escalate(task_id, target,
    model=None, context_blob="", revision_note="")` (new optional
    param, default `""`) so a revision pass can append critique feedback
    into the prompt (`if revision_note: parts.append(f"A previous
    attempt at this fix had a quality issue: {revision_note}. Address
    this in your fix.")` at the prompt-assembly point). Minimal change
    so Phase B's revision call can reuse the existing `escalate()` entry
    point instead of duplicating tier logic.
    - Verify: `python3 -m py_compile scripts/tier3_escalate.py`.
14. `scripts/tier1_escalate.py` — same `revision_note=""` param added to
    `escalate()`, threaded into `build_prompt()`.
    - Verify: `python3 -m py_compile scripts/tier1_escalate.py`.
15. `scripts/tier2_escalate.py` — same `revision_note=""` param added to
    `escalate()`, threaded into `build_user_content()`.
    - Verify: `python3 -m py_compile scripts/tier2_escalate.py`.
16. `scripts/orchestrator.py` — the core wiring, in `run_task()`:
    - Immediately before each of the three escalation calls (Tier 3,
      Tier 1, Tier 2), capture `before_content =
      Path(resolved_target).read_text() if
      Path(resolved_target).exists() else ""` — needed to build a diff
      after the tier writes its fix, since these functions patch the
      file in place with no return value carrying the diff.
    - Add a new helper `_critique_and_maybe_revise(task_id: str,
      resolved_target: str, build_cmd: str, workdir: str,
      before_content: str, tier_name: str, description: str,
      context_blob: str, escalate_fn, escalate_kwargs: dict) -> None`
      (no return value — advisory only, per the approved design it never
      changes `resolved_by`/pipeline flow):
      - loads `config/tiers.yaml`'s `critique` block; no-ops immediately
        if `enabled: false` or `tier_name not in applies_to_tiers`.
      - reads `after_content = Path(resolved_target).read_text()`,
        builds a unified diff via `difflib.unified_diff(
        before_content.splitlines(keepends=True),
        after_content.splitlines(keepends=True),
        fromfile=resolved_target, tofile=resolved_target)`, joined to a
        string.
      - calls `critique.critique_diff(task_id,
        Path(resolved_target).name, description, diff_text, tier_name)`.
      - if `status != "ok"`: log at debug level and return (skipped/
        error → no action — a broken critique call must never block
        anything).
      - if `score >= threshold`: log at info level (`"[%s] Critique
        passed (score=%s)"`) and return.
      - else (below threshold): log a warning at the same visibility
        class as existing "Tier X fix rejected" warnings —
        `log.warning("[%s] Critique flagged %s's fix (score=%s/10): %s
        -- attempting one revision pass", task_id, tier_name, score,
        issues)`. Then:
        - snapshot `pre_revision_content = after_content` (the
          currently-passing fix, in case the revision makes things
          worse).
        - call `escalate_fn(**escalate_kwargs,
          revision_note="; ".join(issues))` (the same tier, once, with
          critique feedback folded in via the `revision_note` param
          added above).
        - if that call's `status` is `fix_applied`: rebuild via
          `run_build(build_cmd, workdir)` (reuse — not
          `_rebuild_after_patch`, since `state.py`'s own bookkeeping
          shouldn't treat this as a fresh failure/success cycle). If the
          rebuild **fails**, revert:
          `Path(resolved_target).write_text(pre_revision_content)`, then
          log a warning that the revision broke the build and the
          pre-revision fix was kept. If the rebuild **passes**, keep the
          revised content and log that the revision applied cleanly.
        - if the revision call itself didn't apply (`fix_rejected`/
          `error`/`skipped`), leave `pre_revision_content` on disk
          untouched and log that the revision attempt itself failed.
      - **Never** touches `resolved_by`, never calls `human_handoff`,
        never causes `run_task()` to fall through to the next tier —
        matches the approved "accept-with-warning" design exactly.
    - Call `_critique_and_maybe_revise(...)` right after each of the
      three tier-success blocks, inside the `if resolved_by is None:`
      branch after `resolved_by` is set, still in scope for
      `before_content`/`context_blob`/`description` (`run_task()`
      already receives `description` as a parameter — no new plumbing
      needed beyond passing it into the new calls).
    - Add `import difflib` and `from scripts import critique` to the top
      of the file.
    - Verify: `python3 -m py_compile scripts/orchestrator.py` — full
      behavioral verification happens in the next item against a real
      fixture.
17. `samples/broken_build/` (existing fixture, no file change) — use it
    for an end-to-end manual verification pass: run the existing
    smoke-test invocation from `README.md` once against a deliberately-
    introduced small bug that Tier 4 alone can't fix cleanly (forcing an
    escalation to Tier 3+ so the critique path actually triggers) —
    confirm via `grep -n critique logs/triapi.log` that a critique call
    ran and logged a score, and via `logs/cost_log.jsonl` (`grep
    '"tier": "critique"' logs/cost_log.jsonl`) that it was cost-logged.
    This is a one-off manual dispatch-time check, not a permanent
    addition to the fixture.
18. `mapping.md` — add `scripts/critique.py` to the `scripts/` section
    (schema of its JSON, the `revision_note` addition to the three
    escalation clients, and the new `_critique_and_maybe_revise()`
    helper in `orchestrator.py`), and add a `critique:` bullet to the
    `config/tiers.yaml` entry describing the new block. Read back by eye
    to confirm formatting, same as Phase A's docs step.

**Why the split matters, don't conflate the two phases:** Phase A is
low-risk, additive-only (a `lessons_block=""` default keeps every
existing call site working unchanged until touched), and cheap to
verify (`py_compile` + a direct smoke call per file). Phase B is
higher-risk — it's new control flow inside `orchestrator.py`'s core
`run_task()` loop, touches the file most other features in this project
depend on, and needs its own end-to-end fixture verification (item 17)
rather than a syntax check alone. Watch Phase B especially closely per
this guide's human_handoff workflow — a bug introduced into
`orchestrator.py` here doesn't just break one feature, it can silently
degrade every future dispatch run's core repair loop, the same
"self-modification raises the stakes" caution already noted in the
self-fix worked case above.
