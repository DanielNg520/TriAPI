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
