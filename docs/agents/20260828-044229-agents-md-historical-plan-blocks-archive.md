# Historical `triapi:plan` blocks archived from AGENTS.md (moved 2026-08-28)

Moved out of `AGENTS.md` to bring it back under this repo's 73,728-char
ceiling (session 2026-08-28, `feedback_docs_are_index_files`/
`feedback_supervisor_never_do_triapi_job` convention: these are fully
**completed** plan runs, historical record only — no unresolved work,
nothing here gates a new `triapi plan` call). Only the most recent
`<!-- triapi:plan -->` block still lives inline in `AGENTS.md` (that's the
one `scripts/agents_md_gate.py`'s `find_incomplete_plan()` actually checks).

A separate, unrelated ~71,600-char block (`run_id=20260827-130810-27dd58`,
a fully hallucinated plan from an overloaded/malfunctioning model — invented
a nonexistent `scripts.librarian_escalate.escalate_librarian()` function and
fake `config/tiers.yaml` model names) was **deleted outright**, not archived
here — it was never approved, never dispatched, and contains no real
history worth preserving. See the active carryover file for that incident.

Five complete, real plan runs are archived below, in original order:

| run_id | appended | topic |
|---|---|---|
| `20260825-092344-5ff4a7` | 2026-08-25 | Tier reassignment: DeepSeek→Tier 2, agy/gemini-3.1-pro→Tier 3, local Ollama→Tier 4 |
| `20260825-154633-8927c3` | 2026-08-25 | Fix silent false-`"success"` after design-judge rejection (`_run_design_judge`/`handle_fix_forward`) |
| `20260825-194415-b54313` | 2026-08-26 | Tier-5 `agy` fallback leg + shared 600s HTTP timeout root fix |
| `20260826-121026-fa6eea` | 2026-08-26 | Tier 3 CLI-timeout soft-escalation + `ARCHITECTURE.md` refresh |
| `20260827-100542-afee9f` | 2026-08-27 | Gate `_run_design_judge` by `critique.applies_to_tiers` (tier_5 doc-edit routing bug fix) |

A sixth, tiny block (`20260827-130627-e41ad6`) is also archived below as-is:
a truncated one-sentence non-plan from an overloaded free Nemotron model
during this same debugging session — never approved or dispatched, kept
only as the literal record of that specific incident (see the active
carryover file, point 3).

---

<!-- triapi:plan run_id=20260825-092344-5ff4a7 start -->
## TriAPI Plan (run 20260825-092344-5ff4a7, appended 2026-08-25)

# Plan: Reassign TriAPI tier models (config/tiers.yaml only)

## Phase 1 — Reassign tier providers in `config/tiers.yaml`

- [ ] In `config/tiers.yaml`, replace the entire `tier_2_manager:` block (currently OpenRouter Nemotron with a disabled Gemini `fallback_chain`) with the real DeepSeek API assignment. Set exactly: `provider: deepseek`, `api_key_secret: deepseek_api_key`, `name: "DeepSeek API"`, `endpoint: "https://api.deepseek.com"`, `models: {default: "deepseek-v4-pro"}`, `default_model: default`, `role: "task orchestration, context isolation, high-level architectural correction"`, `automatable: true`. Add `peak_hours_utc: [["01:00", "04:00"], ["06:00", "10:00"]]` (the same two DeepSeek peak windows currently on `tier_3_debugger`). Add a `pricing:` block with `last_verified: "2026-08-09"`, `cache_hit_per_mtok_usd: 0.003625`, `cache_miss_per_mtok_usd: null  # not given in source doc -- verify before relying on it`, `output_per_mtok_usd: null      # not given in source doc -- verify before relying on it` (moved/adapted from today's `tier_3_debugger.pricing.pro` block — do not invent new numbers). Delete the obsolete comments referencing OpenRouter Nemotron, the disabled-Gemini-incident narrative, the free-tier RPM/RPD billing-status comment block, and the empty `fallback_chain: []` line plus its trailing comment — none apply to a real DeepSeek API tier. Verify: `python3 -c "import yaml; c = yaml.safe_load(open('config/tiers.yaml')); t = c['tier_2_manager']; assert t['provider']=='deepseek' and t['models']['default']=='deepseek-v4-pro' and t['endpoint']=='https://api.deepseek.com' and 'fallback_chain' not in t and t['peak_hours_utc']==[['01:00','04:00'],['06:00','10:00']]; print('tier_2_manager OK')"`
- [ ] In `config/tiers.yaml`, replace the entire `tier_3_debugger:` block (currently the real DeepSeek API) with the `agy` (Antigravity CLI) / Gemini 3.1 Pro assignment. Set exactly: `provider: agy`, `models: {default: "gemini-3.1-pro"}`, `default_model: default`, `effort: "high"`, `role:` updated to reflect Gemini-3.1-Pro-backed (e.g. `"complex C++ logic, hard SIMD fixes, algorithmic diffs (Gemini 3.1 Pro via Antigravity CLI)"`), `automatable: true`. Do **not** add `api_key_secret` (agy uses its own local OAuth token) or `endpoint` (agy is a local CLI subprocess). Remove `peak_hours_utc` and the entire DeepSeek `pricing:` block (`flash`/`pro`/`default` sub-blocks) — neither applies once DeepSeek is no longer here. Do **not** add any `--dangerously-skip-permissions` config field — `llm_client._call_agy_cli()` already passes that flag unconditionally. Verify: `python3 -c "import yaml; c = yaml.safe_load(open('config/tiers.yaml')); t = c['tier_3_debugger']; assert t['provider']=='agy' and t['models']['default']=='gemini-3.1-pro' and t['effort']=='high' and 'peak_hours_utc' not in t and 'pricing' not in t and 'api_key_secret' not in t and 'endpoint' not in t; print('tier_3_debugger OK')"`
- [ ] In `config/tiers.yaml`, replace the entire `tier_4_worker:` block (currently OpenRouter `dots-studio/dots-3-note-preview:free`) with the local-Ollama assignment. Set exactly: `provider: ollama`, `endpoint: "http://localhost:11434"`, `models: {default: "qwen2.5-coder:14b-instruct-q6_K"}`, `default_model: default`. Remove the `api_key_secret: open_router_api_key` line (Ollama needs no API key) and the stale `name: "OpenRouter Dots (notes3)"` field/comment block describing the 2026-08-24 OpenRouter swap (no longer accurate). Keep `automatable: true`, the existing `role:` field text, and `build_commands: ["cmake --build build"]` unchanged. Verify: `python3 -c "import yaml; c = yaml.safe_load(open('config/tiers.yaml')); t = c['tier_4_worker']; assert t['provider']=='ollama' and t['endpoint']=='http://localhost:11434' and t['models']['default']=='qwen2.5-coder:14b-instruct-q6_K' and 'api_key_secret' not in t and t['build_commands']==['cmake --build build']; print('tier_4_worker OK')"`
- [ ] Confirm nothing else in `config/tiers.yaml` moved: `tier_1_planner`, `tier_1_manager`, `gemini_fallback`, `tier_5_librarian`, `ollama_fallback`, `escalation_rules`, `critique`, `self_fix`, `jules_tester` must be byte-identical to before this phase. Verify: `git diff config/tiers.yaml | grep -E '^[-+]' | grep -viE 'tier_2_manager|tier_3_debugger|tier_4_worker|deepseek|agy|gemini-3.1-pro|ollama|qwen2.5-coder|peak_hours_utc|cache_hit|cache_miss|output_per_mtok|pricing|last_verified|role|automatable|models|default_model|provider|endpoint|api_key_secret|name|build_commands|effort|^\s*#|^---|^\s*$' | head -50` should print nothing unexpected outside the three reassigned blocks (spot-check any hits by eye).

## Phase 2 — Live pre-flight probe of every tier

- [ ] Run the repo's standard pre-flight probe against the real, edited config to confirm every tier (including the new DeepSeek Tier 2 and the new `agy` Tier 3) resolves and responds: `PYTHONPATH=. python3 -c "from scripts.llm_client import probe_models; probe_models()"`. This makes real, cheap ping/pong calls to each tier's configured provider/model/endpoint using the real secrets already present in `config/secrets.enc.yaml`. If it raises, diagnose from the actual exception (e.g. wrong model id, missing `agy` auth, Ollama not pulled/running) and fix the specific tier's block in `config/tiers.yaml` from Phase 1 accordingly — do not guess at unrelated values. Command must complete with no exception raised and no output other than whatever `probe_models()` itself prints.
- [ ] If the probe fails specifically on Tier 4 because the model isn't pulled locally, pull it first, then re-run the probe: `ollama pull qwen2.5-coder:14b-instruct-q6_K && PYTHONPATH=. python3 -c "from scripts.llm_client import probe_models; probe_models()"`.

## Phase 3 — Audit and fix the one stale regression-test fixture

- [ ] In `tests/test_orchestrator_tier3_peak_skip.py`, update the hardcoded `TIER_3_DEBUGGER_CONFIG` fixture and its `test_config_matches_tiers_yaml` test — this file's docstring/test name explicitly claims to mirror `config/tiers.yaml`, and today it hardcodes `provider: "deepseek"`, `api_key_secret: "deepseek_api_key"`, `endpoint: "https://api.deepseek.com"`, `models: {"flash": "deepseek-chat"}`, the DeepSeek `pricing` block (flash/pro/default), and `peak_hours_utc`, all under the name `tier_3_debugger` — which after Phase 1 describes the wrong tier (DeepSeek now lives under `tier_2_manager`). Rename the constant to `TIER_2_MANAGER_CONFIG` and update its fields to match the new `tier_2_manager` block from Phase 1 exactly: `provider: "deepseek"`, `api_key_secret: "deepseek_api_key"`, `name: "DeepSeek API"`, `endpoint: "https://api.deepseek.com"`, `models: {"default": "deepseek-v4-pro"}`, `default_model: "default"`, `role: "task orchestration, context isolation, high-level architectural correction"`, `automatable: True`, `peak_hours_utc: [["01:00", "04:00"], ["06:00", "10:00"]]`, and a flat `pricing` dict `{"last_verified": "2026-08-09", "cache_hit_per_mtok_usd": 0.003625, "cache_miss_per_mtok_usd": None, "output_per_mtok_usd": None}`. Update `test_config_matches_tiers_yaml`'s assertions to match this new shape (drop the old nested `flash`/`pro`/`default` pricing sub-block assertions, assert the new flat pricing keys instead). In `test_peak_hours_skip_tier3` and `test_off_peak_allows_tier3`, change the `mock.patch.object(budget_guard, "load_tiers", return_value={"tier_3_debugger": TIER_3_DEBUGGER_CONFIG})` calls to `return_value={"tier_2_manager": TIER_2_MANAGER_CONFIG}` (matching `budget_guard.resolve_deepseek_tier()`'s real, position-independent lookup — it scans for whichever tier has `provider == "deepseek"`, confirmed already working via `tests/test_tier_reassignment_prep.py`, no code change needed). Do not weaken any assertion — same count and strength of checks, just correct tier/field names. Verify: `python3 -m py_compile tests/test_orchestrator_tier3_peak_skip.py`
- [ ] Confirm the other four listed test files need no change (their tier_2/3/4-shaped fixtures are self-contained and don't assert real `config/tiers.yaml` values): `grep -n "tier_2_manager\|tier_3_debugger\|tier_4_worker\|deepseek-chat\|dots-3-note-preview\|nvidia/nemotron\|gemini-3.5-flash\|gemini-2.5-pro" tests/test_branch_features.py tests/test_tier5_librarian.py tests/test_tier_reassignment_prep.py tests/test_dispatcher_peak_hours.py`. Expected: the only hits are (a) `test_branch_features.py`'s `LlmClientOpenAIErrorBodyTests`, which passes `"nvidia/nemotron-3-ultra-550b-a55b:free"` as an arbitrary literal model-string argument to `llm_client._call_openai_api()` to test generic HTTP-200-no-`choices` error handling, unrelated to which real tier uses that model; (b) `test_branch_features.py`'s `SkipTier4Tests`, whose `tier_4_worker` fixture only sets `build_commands`, no provider; (c) `test_tier5_librarian.py`'s fixture, which is for the unchanged `tier_5_librarian`/`ollama_fallback` blocks. If this grep instead turns up a hit asserting a real provider/model value for `tier_2_manager`/`tier_3_debugger`/`tier_4_worker` that this scan missed, fix that specific assertion the same way as the step above before proceeding — do not skip it.
- [ ] Run the full regression suite plus every test file named in this task: `PYTHONPATH=. python3 -m unittest tests.test_branch_features tests.test_tier5_librarian tests.test_tier_reassignment_prep tests.test_dispatcher_peak_hours tests.test_orchestrator_tier3_peak_skip -v 2>&1 | tail -40`. Confirm zero failures, zero errors, and zero unexpected `SKIPPED` lines (a skip masquerading as a pass is a known failure mode in this repo — check the `-v` output by eye, don't trust a bare "OK").

## Phase 4 — Update `AGENTS.md` and `PLAN.md`

- [ ] In `AGENTS.md`, grep first to find every stale reference: `grep -n "tier_2_manager\|tier_3_debugger\|tier_4_worker" AGENTS.md`. Fix each bullet that states the OLD assignment as present-tense fact (leave historical "Phase N did X" narrative sentences alone — only correct claims that are now false): (1) the `config/tiers.yaml` bullet's `tier_2_manager.fallback_chain`/`models.pro` Gemini-fallback paragraph and its `tier_4_worker` task-type-routing (`default`/`polyglot`/`heavy`) paragraph — both describe assignments no longer true; replace with a short accurate note that `tier_2_manager` is now the real DeepSeek API (`deepseek-v4-pro`, `peak_hours_utc` moved here from Tier 3), `tier_3_debugger` is now `agy`/`gemini-3.1-pro` (no peak-hours/pricing), and `tier_4_worker` is local Ollama `qwen2.5-coder:14b-instruct-q6_K` at `http://localhost:11434`; (2) the same bullet's "Point-in-time... Tier 3 is in DeepSeek peak billing hours" sentence and "`tier_3_debugger.default_model` is `flash` (`deepseek-v4-flash`)" sentence — update to say Tier 2 is now the one subject to DeepSeek peak-hour gating, and `tier_3_debugger.default_model` is `default` (`gemini-3.1-pro` via `agy`); (3) the `llm_client.py` bullet's parenthetical `(tier_2_manager's default_model)` next to the Nemotron example — remove or correct, since `tier_2_manager`'s default model is no longer Nemotron; (4) the `budget_guard.py` bullet's `check_tier3_peak_hours_ok()` description — correct "it reads `tier_3_debugger.peak_hours_utc`" to describe the real, already-implemented position-independent lookup (`resolve_deepseek_tier()` finds whichever tier has `provider: deepseek`, currently `tier_2_manager`, and falls back to `DEFAULT_TIER3_PEAK_HOURS_UTC` if none); (5) the `triapi.py` bullet's `tier_4_worker.default_model` example (`qwen2.5-coder:14b-instruct-q8_0`) — update to the new real value `qwen2.5-coder:14b-instruct-q6_K`. Keep every edit surgical — do not rewrite surrounding unrelated history. Verify size stays under the ceiling both before and after: `wc -c AGENTS.md` (record the before value from this same command run at the start of this phase) then re-run `wc -c AGENTS.md` after editing and confirm the result is `< 73728`.
- [ ] Append a new dated phase entry to `PLAN.md` (repo root) in the same style as Phase 30/31/32 (see those entries for exact tone/format — one `## Phase 33: ...` heading, a short bolded context line, a numbered list of what changed, and a one-line `**Verification**:` sentence). Content: title something like `## Phase 33: Tier reassignment — DeepSeek to Tier 2, Gemini/agy to Tier 3, local Ollama back to Tier 4 (2026-08-25)`; state this is a config-only change to `config/tiers.yaml` (no application code touched, per `llm_client.execute_llm()`'s already-generic provider dispatch, confirmed by Phases 31/32's prerequisite work); list the three reassignments (Tier 2 → DeepSeek `deepseek-v4-pro` with peak-hours gating moved here, Tier 3 → `agy`/`gemini-3.1-pro` high effort, Tier 4 → local Ollama `qwen2.5-coder:14b-instruct-q6_K`); note `gemini_fallback` is now fully dead/unused config, deliberately left in place, out of scope; note the one regression-test fixture fix (`tests/test_orchestrator_tier3_peak_skip.py`) and why it was needed; close with the verification command from Phase 3's last step and its pass count. Verify: `grep -c "^## Phase 33" PLAN.md` returns `1`.
- [ ] Run `git status` and `git diff --stat` to confirm the full change set is exactly: `config/tiers.yaml`, `tests/test_orchestrator_tier3_peak_skip.py`, `AGENTS.md`, `PLAN.md` — no other file touched (in particular, `scripts/llm_client.py`, `scripts/dispatcher.py`, `scripts/budget_guard.py`, `scripts/orchestrator.py` must show zero diff).
<!-- triapi:plan run_id=20260825-092344-5ff4a7 end -->

<!-- triapi:plan run_id=20260825-154633-8927c3 start -->
## TriAPI Plan (run 20260825-154633-8927c3, appended 2026-08-25)

## Execution plan — fix silent false-`"success"` after design-judge rejection (`_run_design_judge`/`handle_fix_forward`, run 20260825-092344-5ff4a7)

### Phase 1 — Ground truth & baseline (read-only, no edits)

- [x] **`scripts/dispatcher.py`** — Pin the exact current code shapes before touching anything: line numbers and full bodies of `_run_design_judge()` (~line 1048) and `handle_fix_forward()` (~line 1071 area), the main-loop call site (~line 1288), and verbatim the analogous `"build_failed"` downgrade block at the mock_patch_lint override just below the call site (its exact field set is the convention the fix must mirror). Also record, from inside `handle_fix_forward`: every exit path (there must be no remaining implicit-`None` return after the fix), the `escalate_ok`/`rebuild_ok` variable flow, the revert-to-snapshot call, the `tech_debt.log_tech_debt(...)` call, and the **exact rebuild callable + argument names** it invokes (needed as the mock target in Phase 3). Record output:
  ```bash
  grep -n "def _run_design_judge\|def handle_fix_forward\|handle_fix_forward(\|_run_design_judge(\|build_failed" scripts/dispatcher.py && sed -n '1040,1110p' scripts/dispatcher.py && sed -n '1260,1330p' scripts/dispatcher.py
  ```
- [x] **`scripts/judge.py`** — Record the exact return-dict key contract of `judge.evaluate_design(git_diff, description)` (e.g. `{"approved": bool, "reason": str}` — use the real key names, not assumed ones) so the regression-test mocks in Phase 3 return faithfully-shaped values:
  ```bash
  grep -n "def evaluate_design" -A 30 scripts/judge.py
  ```
- [x] **`tests/` (size-ceiling check)** — Measure every existing test file against the 73,728-char ceiling to confirm the goal's "check first" instruction; expected conclusion either way: create a **new** dedicated file `tests/test_design_judge_fix_forward_status.py`, matching the repo's established split-out convention (`test_mock_patch_lint.py`, `test_dispatcher_test_context_guard.py`, etc.) and keeping headroom:
  ```bash
  wc -c tests/*.py | sort -n | tail -12
  ```
- [x] **`tests/test_branch_features.py` + full suite (baseline)** — Capture the pre-change suite baseline for later comparison (this fix sits on a path that runs after every successful dispatch item, so the post-change delta must be exactly +3 tests): record total tests run, failures, errors, and skipped counts; require `OK`:
  ```bash
  PYTHONPATH=. python3 -m unittest discover -s tests -v 2>&1 | tail -15
  ```

### Phase 2 — Surgical fix in `scripts/dispatcher.py`

- [x] **`scripts/dispatcher.py` — `handle_fix_forward()` returns its outcome.** First audit all callers (`grep -rn "handle_fix_forward" scripts/ tests/` — expected: the only production caller is `_run_design_judge()`; any other caller ignores the return today and tolerates a dict). Then change **only the return behavior**: keep the signature `(item, judge_reason, state, task_id)` and every internal statement of the existing `escalate_ok`/`rebuild_ok`/snapshot-revert/tech-debt logic byte-identical; replace each exit path's implicit `None` with an explicit return of a dict `{"fixed": <bool>, "reason": <str>}`:
  - `escalate_ok and rebuild_ok` → `{"fixed": True, "reason": "fix-forward edit applied and rebuild passed"}`
  - not `escalate_ok` (Tier 3 response had no parseable SEARCH/REPLACE blocks; file reverted, tech debt logged) → `{"fixed": False, "reason": "tier3 escalation produced no applicable SEARCH/REPLACE edit; file reverted and tech debt logged"}`
  - `escalate_ok` but not `rebuild_ok` → `{"fixed": False, "reason": "rebuild failed after fix-forward edit"}`

  Verify compile-clean:
  ```bash
  python3 -m py_compile scripts/dispatcher.py
  ```
- [x] **`scripts/dispatcher.py` — `_run_design_judge()` rejection branch consumes the outcome.** Replace the buggy tail (the no-op `result = dict(result)` followed by returning the original untouched result) so the branch becomes: call `ff = handle_fix_forward(item, judge_res["reason"], state, task_id)`; if `isinstance(ff, dict) and ff.get("fixed")` → return the original `result` unchanged (genuine repair occurred; `"success"` legitimately stands, `resolved_by` untouched). Otherwise build `downgraded = dict(result)` and set **exactly the field set the mock_patch_lint-override downgrade block uses** (required: `status = "build_failed"`, `resolved_by = None`; plus copy verbatim any diagnostic/message field that block sets) and return it. Do **not** touch the judge-approval path, `judge.evaluate_design()`, `tier3_escalate.escalate()`, or anything else in `dispatcher.py`:
  ```bash
  python3 -m py_compile scripts/dispatcher.py && grep -n "build_failed" scripts/dispatcher.py
  ```

### Phase 3 — Regression test (new file)

- [x] **`tests/test_design_judge_fix_forward_status.py`** — New dedicated test file (confirmed in Phase 1 that splitting out is correct per convention + ceiling). `unittest.TestCase`, fixture-repo/tempdir pattern like the sibling dispatcher tests, **zero real LLM/network calls**. Fixture: a `tempfile.TemporaryDirectory` containing a small target file (known broken→fixed content pair); item shaped like a real dispatch item (`{"target": <tmpfile>, "description": "..."}`); seed `result={"status": "success", "resolved_by": "tier_5", ...}`; call `dispatcher._run_design_judge(item, result, state, task_id)` directly. Mock **at the use sites as looked up inside `scripts.dispatcher`**, using the exact symbols/keys recorded in Phase 1: `_git_diff_for` → deterministic diff string; `judge.evaluate_design` → approval or rejection dict with the real key contract; `tier3_escalate.escalate` → case (b): `side_effect` writes the corrected content to the tmp target and returns `"fix_applied"`; case (c): returns a non-`"fix_applied"` status; the rebuild callable used inside `handle_fix_forward` → `True`; and `tech_debt.log_tech_debt` → `MagicMock` (**mandatory** — protects the real `knowledge/TECH_DEBT.md` from test writes in case c). Three tests:
  - (a) judge approves → returned `status == "success"` unchanged, and `handle_fix_forward` asserted **not called** (guards against regressing the approval path);
  - (b) judge rejects + fix-forward succeeds (escalate `"fix_applied"`, rebuild ok) → final `status == "success"`;
  - (c) judge rejects + `tier3_escalate.escalate` returns non-`"fix_applied"` → final `status == "build_failed"` **and** `resolved_by is None` (explicitly not `"success"`), `log_tech_debt` asserted called, fixture file reverted to original bytes.
  
  Verify:
  ```bash
  python3 -m py_compile tests/test_design_judge_fix_forward_status.py && PYTHONPATH=. python3 -m unittest tests.test_design_judge_fix_forward_status -v
  ```
  Expected output: `Ran 3 tests ... OK`. Also confirm ceiling headroom: `wc -c tests/test_design_judge_fix_forward_status.py` (< 73,728).

### Phase 4 — Full regression gate

- [x] **Full suite re-run** — Compare strictly against the Phase 1 baseline: total = baseline total **+ 3**, **0 failures, 0 errors, skipped == baseline skipped count (zero unexpected skips)**. Any deviation → stop and diagnose before proceeding:
  ```bash
  PYTHONPATH=. python3 -m unittest discover -s tests -v 2>&1 | tail -15
  ```

### Phase 5 — Index/bookkeeping (repo convention: docs updated at end of the work)

- [x] **`AGENTS.md`** — Append one row to the tests/ file-map table for `tests/test_design_judge_fix_forward_status.py` in the exact style of its sibling rows (bold markdown link, date, one-sentence coverage summary: judge-approve / successful-fix-forward / failing-fix-forward status outcomes; note fixture-repo pattern, full mocking, split out per the size-ceiling convention). Verify the file stays under the ceiling and the row landed:
  ```bash
  wc -c AGENTS.md && grep -c "test_design_judge_fix_forward_status" AGENTS.md
  ```
  Expected: size < 73,728; count ≥ 1.
- [x] **`docs/agents/20260825-100000-scripts-directory-reference.md`** — Update the `dispatcher.py` entry (this is where full per-script documentation lives since the 2026-08-25 move) to document the changed contracts: `handle_fix_forward()` now returns `{"fixed": bool, "reason": str}` instead of implicit `None`; `_run_design_judge()`'s rejection branch downgrades the item to `status: "build_failed"` / `resolved_by: None` (mirroring the mock_patch_lint-override convention) whenever fix-forward does not genuinely repair + rebuild, and leaves `"success"` standing only on judge approval or a verified fix-forward repair; cite run 20260825-092344-5ff4a7 item `-p3-i1` as the motivating reproduced incident. Date-stamp with the actual edit date. Verify:
  ```bash
  grep -n "handle_fix_forward" docs/agents/20260825-100000-scripts-directory-reference.md
  ```

No git clone/pull/commit/push steps are included — the goal requests none (the triggering run is already committed; this fix makes no git operation part of its definition).
<!-- triapi:plan run_id=20260825-154633-8927c3 end -->

<!-- triapi:plan run_id=20260825-194415-b54313 start -->
## TriAPI Plan (run 20260825-194415-b54313, appended 2026-08-26)

# Execution Plan — Tier-5 `agy` fallback leg + shared 600s HTTP timeout root fix

**Assumptions (flag anything you want changed before dispatch):**
- Chain position: `fallback_agy` is inserted **between** `fallback_local` and `fallback_openrouter` → `[fallback_local, fallback_agy, fallback_openrouter, log_and_notify]`. Rationale: preserves cheapest-first (local free → agy = Antigravity CLI subscription, $0 marginal → OpenRouter last). Easy to reorder if you want agy after OpenRouter.
- `fallback_agy` model value mirrors Tier 3's convention: `default` (the agy CLI resolves `gemini-3.1-pro` itself, effort high).
- No git operations (clone/pull/commit/push) are included — none were requested. No `secrets.enc.yaml` edits are needed (agy authenticates via CLI login, no new secret key).

---

## Phase 1 — Root cause: shared HTTP timeout in `llm_client.py` (fixes the 20260825-174353-a25d29 crash class)

- [x] **`scripts/llm_client.py`** — First read the file to locate `_CLI_TIMEOUT` (600 since commit 5a6ae01) and the two hardcoded `requests.post(..., timeout=300)` literals in `_call_openai_api()` (used for the Ollama/localhost:11434 path — the one that caused the crash) and `_call_gemini_api()`. Changes: (1) add a single module-level constant `_HTTP_TIMEOUT` immediately next to `_CLI_TIMEOUT`, default `600`, env-overridable via `TRIAPI_HTTP_TIMEOUT` (int-parsed; absent/invalid → 600), following the same "everything configurable" env-var pattern as `TRIAPI_LOG`/`TRIAPI_LOG_FILE`; (2) replace **both** `timeout=300` literals with `timeout=_HTTP_TIMEOUT` — no other behavior change (raising Gemini's remote-API timeout to 600 is intentional and harmless). Verify: `python3 -m py_compile scripts/llm_client.py && ! grep -qE 'timeout=300' scripts/llm_client.py && grep -c '_HTTP_TIMEOUT' scripts/llm_client.py` (expect ≥3 matches: definition + 2 call sites)
- [x] **`tests/test_llm_client_http_timeout.py`** (new file) — Regression coverage for the shallow-timeout incident, fixture/mock style (zero network calls): (1) assert `scripts.llm_client._HTTP_TIMEOUT == 600` by default; (2) env-override case — set `TRIAPI_HTTP_TIMEOUT=900`, `importlib.reload(scripts.llm_client)`, assert 900, restore env and reload in tearDown; (3) stub `requests.post` (fake 200 response exposing `.json()`) and call both `_call_openai_api()` and `_call_gemini_api()` against dummy endpoints, asserting the captured kwargs contain `timeout == scripts.llm_client._HTTP_TIMEOUT` (proves the request layer actually receives it — the original bug shape where 300 was baked in). Verify: `PYTHONPATH=. python3 -m unittest tests.test_llm_client_http_timeout -v`

## Phase 2 — `agy` fallback leg for `tier_5_librarian`

- [x] **`config/tiers.yaml`** — Under the `tier_5_librarian:` block: (1) add `fallback_agy: default` to `models:` (alongside `primary: mistral-small:latest`, `fallback_local: ollama_fallback`, `fallback_openrouter: stealth/ox-alpha`); (2) change `escalation_rules.tier5_to_fallbacks.chain` from `[fallback_local, fallback_openrouter, log_and_notify]` to `[fallback_local, fallback_agy, fallback_openrouter, log_and_notify]`. Leave `threshold: 2` and `max_attempts` untouched. Verify: `python3 -c "from scripts.config_loader import load_tiers; load_tiers(); print('tiers.yaml parses OK')" && grep -n -A6 'tier5_to_fallbacks' config/tiers.yaml`
- [x] **`scripts/librarian_escalate.py`** — First read its chain-dispatch loop plus `scripts/tier3_escalate.py`'s agy invocation (and both entries in `docs/agents/20260825-100000-scripts-directory-reference.md`) to mirror existing patterns. Add a `fallback_agy` branch to the leg dispatcher: invoke the agy CLI through the **same shared code path Tier 3 uses** (reuse the existing helper — no duplicated subprocess logic), model taken from `tier_5_librarian.models.fallback_agy`, inheriting `_CLI_TIMEOUT` (600s) automatically. Failure semantics identical to other legs: nonzero exit / empty output / missing binary → treat as leg failure and continue to the next chain entry. Success still flows through the existing edit-block apply path; cost-log billing tag for this leg follows the file's existing non-local-leg convention (subscription-class, $0 marginal — analogous to Tier 1's `billing: "subscription"`, not `"local"`). No budget_guard gate required (agy is subscription CLI, same class as Tier 3's usage — no metered-API exposure), and the hard guarantee that paid APIs (DeepSeek/Claude API/Gemini API) are never called from this chain stays intact. Verify: `python3 -m py_compile scripts/librarian_escalate.py`
- [x] **`tests/test_tier5_librarian.py`** — Update the existing escalation-order test: expected chain becomes primary → `fallback_local` → `fallback_agy` → `fallback_openrouter` → `log_and_notify`. Add an agy-CLI mock sentinel asserted (a) invoked exactly when `fallback_local` exhausts its threshold of 2, and (b) never invoked on primary/local/openrouter success paths. Extend the chain-exhaustion handoff case to cover the now-4-leg chain ending in `log_and_notify`. Keep all existing paid-tier (DeepSeek/Claude/Gemini API) never-touched sentinel assertions unchanged. Follow the file's existing temp-fixture-repo pattern. Verify (this doubles as the full regression run): `PYTHONPATH=. python3 -m unittest tests.test_branch_features tests.test_tier5_librarian tests.test_llm_client_http_timeout -v`

## Phase 3 — Docs & index upkeep (per AGENTS.md standing rules)

- [x] **`ARCHITECTURE.md`** — Update the Tier 5 section: chain now includes `fallback_agy` (Antigravity CLI, `gemini-3.1-pro`, effort high, subscription/$0-marginal, positioned after `fallback_local`); record the motivating incidents (Phases 30–32 PLAN.md-too-large librarian gap; run 20260825-174353-a25d29 self_fix_drafted crash via 300s read timeout on localhost:11434); document `_HTTP_TIMEOUT` (600s default, `TRIAPI_HTTP_TIMEOUT` override) alongside `_CLI_TIMEOUT` in the timeout discussion. Verify: `grep -n 'fallback_agy\|_HTTP_TIMEOUT' ARCHITECTURE.md`
- [x] **`AGENTS.md`** — Update the `tier_5_librarian:` bullet in config/ (new `models.fallback_agy` key and extended chain); add a `tests/test_llm_client_http_timeout.py` row to the tests/ index (one line: what it covers, fixture style, date 2026-08-25+); note `llm_client._HTTP_TIMEOUT` wherever the timeout convention is mentioned. Must stay under the 73,728-char ceiling — trim only redundant prose, never index rows. Verify: `wc -c AGENTS.md` (must be < 73728) `&& grep -n 'fallback_agy\|test_llm_client_http_timeout' AGENTS.md`
- [x] **`docs/agents/20260825-100000-scripts-directory-reference.md`** — Refresh two entries so the reference doesn't drift: `llm_client.py` (new `_HTTP_TIMEOUT` constant, `TRIAPI_HTTP_TIMEOUT` env override, applied at both `_call_openai_api`/`_call_gemini_api` sites, supersedes the old hardcoded 300s) and `librarian_escalate.py` (new `fallback_agy` leg, updated chain order, subscription-class billing tag, `_CLI_TIMEOUT` inheritance, unchanged failure/continue semantics). Verify: `grep -n '_HTTP_TIMEOUT\|fallback_agy' docs/agents/20260825-100000-scripts-directory-reference.md`
- [x] **Active carryover file** (resolve exact path with `f=$(jq -r '.active' docs/carryover/index.json); echo "$f"`) — Mark both queued fixes (agy fallback leg; HTTP-timeout root fix) as done in place with one-line outcomes each pointing at this plan's artifacts (new test file, config keys, constant name). Index-file convention: status flip + pointers only, no session narrative dumped into the index. Verify: `f=$(jq -r '.active' docs/carryover/index.json); grep -n 'fallback_agy\|_HTTP_TIMEOUT' "$f"`
<!-- triapi:plan run_id=20260825-194415-b54313 end -->

<!-- triapi:plan run_id=20260826-121026-fa6eea start -->
## TriAPI Plan (run 20260826-121026-fa6eea, appended 2026-08-26)

## Execution plan: Tier 3 CLI-timeout soft-escalation + ARCHITECTURE.md refresh

Grounding done before writing this plan: confirmed the gap is real. `scripts/llm_client.py`'s `_call_agy_cli()` (`scripts/llm_client.py:230-233`) runs `subprocess.run(cmd, ..., timeout=_CLI_TIMEOUT)` (`_CLI_TIMEOUT = 600`), so a hang raises `subprocess.TimeoutExpired`. `scripts/tier3_escalate.py`'s `escalate()` wraps the `llm_client.execute_llm(...)` call (`scripts/tier3_escalate.py:199-208`) in a single broad `except Exception as e:` (line 209) that returns `{"status": "error", ...}` — a timeout is indistinguishable from any other failure. `scripts/orchestrator.py`'s `run_task()` (Tier 3 block, `scripts/orchestrator.py:397-407`) then does `if result3.get("status") == "error": raise RuntimeError(...)`, which propagates uncaught — the pipeline crashes instead of falling through to the next `if resolved_by is None:` block (Tier 2/DeepSeek). This confirms the gap the goal describes; no confirmation step is needed inside the plan itself, just the fix.

Also confirmed `ARCHITECTURE.md` is stale: it says "four tiers" (line 5), `Tier 2 = Nemotron` (line 11), `Tier 3 = DeepSeek` (line 10), with no mention of Tier 5 or the Phase 33 reassignment (Tier 2 = DeepSeek, Tier 3 = agy/gemini-3.1-pro, Tier 4 = local Ollama, Tier 5 = librarian doc-updater with its `fallback_agy` leg).

---

### 1. Phase 1 — Distinguish Tier 3 CLI timeout from other Tier 3 failures and soft-escalate to Tier 2

- [x] In `scripts/tier3_escalate.py`: add `import subprocess` to the top-level imports (alongside the existing `argparse, json, re, sys, time` block), then in `escalate()` add a new `except subprocess.TimeoutExpired as e:` clause immediately before the existing `except Exception as e:` at line 209 (must come first — more specific exception types must precede the broad catch), wrapping the same `try:` block that calls `llm_client.execute_llm(...)` (lines 192-208). The new clause returns a dict shaped like the existing error-path return but with a distinct status: `{"status": "timeout", "reason": f"Tier 3 request timed out after {e.timeout}s: {e}", "model": model_name, "cache_hit_tokens": 0, "cache_miss_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}`. Log via `log.warning("[%s] Tier 3 request timed out: %s", task_id, e)` (warning, not error, since this is expected-and-handled, not a crash). Verify: `python3 -m py_compile scripts/tier3_escalate.py`

- [x] In `scripts/orchestrator.py`: in `run_task()`'s Tier 3 block (around line 397-407, inside `if resolved_by is None:`), add a new branch handling `result3.get("status") == "timeout"` that does **not** raise — it must only log and fall through to the next block (mirroring the existing peak-hour-skip log style at line 394). Insert it as its own `if` (not `elif`, matching the existing style where `"error"`/`"fix_rejected"`/`"fix_applied"` are each their own `if` against the same `result3` dict) directly after `result3 = tier3_escalate(...)` and before the existing `if result3.get("status") == "error":` check:
  ```python
  if result3.get("status") == "timeout":
      log.warning("[%s] Tier 3 timed out; soft-escalating to Tier 2: %s", task_id, result3.get("reason"))
  ```
  Leave the existing `"error"`, `"fix_rejected"`, and `"fix_applied"` checks unchanged — since `result3["status"]` is a single string value, only the matching branch fires, so `"timeout"` will never hit the `raise RuntimeError(...)` branch. After this change, a Tier 3 timeout leaves `resolved_by = None` and execution proceeds to the existing Tier 2 (`tier2_escalate`, DeepSeek/`tier_2_manager`) block starting at line ~411, unmodified. Verify: `python3 -m py_compile scripts/orchestrator.py`

- [x] Create `tests/test_orchestrator_tier3_timeout_skip.py` (new file, following the existing split-out convention used by `tests/test_orchestrator_tier3_peak_skip.py` and the `SkipTier4Tests` class in `tests/test_branch_features.py`) with two test classes:
  - `Tier3EscalateTimeoutTests` (unit level, targets `scripts/tier3_escalate.py`): mock `llm_client.execute_llm` (via `mock.patch.object(tier3_escalate.llm_client, "execute_llm", side_effect=subprocess.TimeoutExpired(cmd=["agy", "-p"], timeout=600))`) inside a `tempfile.TemporaryDirectory()`-backed target file, call `tier3_escalate.escalate(task_id, target, context_blob="ctx", description="desc")`, and assert the returned dict has `status == "timeout"` (not `"error"`) and a non-empty `reason` string mentioning the timeout.
  - `OrchestratorTier3TimeoutSoftEscalateTests` (integration level, targets `scripts/orchestrator.py`, mirroring `SkipTier4Tests.test_skip_tier4_never_calls_tier4_run_and_starts_at_tier3`'s mocking pattern): build a minimal `config` dict (`tier_4_worker.build_commands`, `tier_1_manager.enabled`, `critique.enabled: False`), mock `orchestrator.tier4_run` to return `{"status": "escalate", "consecutive_failures": 2}` (forcing the Tier 3 path), mock `orchestrator.check_tier3_peak_hours_ok` → `{"ok": True}`, mock `orchestrator.tier3_escalate` to return `{"status": "timeout", "reason": "Tier 3 request timed out after 600s"}`, mock `orchestrator.check_tier2_ok` → `{"ok": True}`, mock `orchestrator.tier2_escalate` to return `{"status": "fix_applied", ...}`, mock `orchestrator._rebuild_after_patch` → `True`, mock `orchestrator.read_state` → `{}`, mock `orchestrator.report` → `{}`, mock `orchestrator.human_handoff` (assert never called). Call `orchestrator.run_task("task-t3-timeout", "fix it", target, workdir=tmp, build_cmd="true")` inside the mock context (no exception must propagate — assert this implicitly by the call completing) and assert: `result["status"] == "success"`, `result["resolved_by"] == "tier_2"`, `orchestrator.tier2_escalate` (the mock) was called exactly once, and `human_handoff` mock was never called. This is the concrete proof that a Tier 3 timeout lands on Tier 2, not a crash and not straight to `human_handoff`.
  Verify: `PYTHONPATH=. python3 -m unittest tests.test_orchestrator_tier3_timeout_skip -v` — both test classes must show `ok`, none `SKIPPED`.

- [x] Run the full regression suite to confirm nothing else regressed: `PYTHONPATH=. python3 -m unittest tests.test_branch_features tests.test_tier5_librarian tests.test_orchestrator_tier3_timeout_skip tests.test_orchestrator_tier3_peak_skip -v` — every test must report `ok`, none `SKIPPED` (per the "watch for fake skip-based tests" convention — inspect the `-v` output directly, don't trust a bare "all passed").

### 2. Phase 2 — Refresh `ARCHITECTURE.md` via the Tier 5 librarian (do not hand-write the doc edit)

- [x] Invoke `scripts/librarian_escalate.py` directly against `ARCHITECTURE.md` (per this repo's standing convention: doc edits to `AGENTS.md`/`CARRYOVER.md`/`PLAN.md`-class files route through this script, not `Edit`/`Write`), with a description precise enough that Tier 5 (`mistral-small:latest` primary, escalating through `fallback_local` → `fallback_agy` → `fallback_openrouter` per `config/tiers.yaml`'s `tier_5_librarian.escalation_rules.tier5_to_fallbacks` if needed) can make the exact edit without guessing:
  ```bash
  python3 scripts/librarian_escalate.py \
    --task-id refresh-architecture-md-20260826 \
    --description "ARCHITECTURE.md is stale (still describes a 4-tier system). Update it to reflect the current 5-tier state: (1) the system is now 5 tiers, not 4 -- add Tier 5 (librarian doc-updater, config/tiers.yaml's tier_5_librarian block, provider ollama/mistral-small:latest primary, target_globs *.md and docs/**, escalation chain fallback_local -> fallback_agy (Antigravity CLI, gemini-3.1-pro, subscription-billed) -> fallback_openrouter -> log_and_notify, added 2026-08-24, fallback_agy leg added 2026-08-26); (2) the Phase 33 tier reassignment (2026-08-25): Tier 2 (tier_2_manager) is now the real DeepSeek API (deepseek-v4-pro), replacing the old Nemotron/OpenRouter assignment; Tier 3 (tier_3_debugger) is now agy/gemini-3.1-pro via the Antigravity CLI (effort high, no peak-hours/pricing block), replacing the old DeepSeek assignment; Tier 4 (tier_4_worker) remains local Ollama (qwen2.5-coder:14b-instruct-q6_K); (3) note that Tier 3 (agy CLI) timeouts now soft-escalate to Tier 2 (DeepSeek) instead of crashing the pipeline, per orchestrator.run_task()'s Tier 3 block in scripts/orchestrator.py. Keep the existing DeepSeek cache-hit economics section and budget-guard rationale sections intact -- only update the tier-identity/tier-count claims and the escalation-order table/diagram to match the current assignment, and add a short Tier 5 section in the same style as the existing per-tier sections. Do not change file layout/heading structure beyond what's needed for this update." \
    --target ARCHITECTURE.md \
    --workdir .
  ```
  This prints a JSON result to stdout — confirm `"status"` indicates a successful write (not `log_and_notify`/exhausted-chain).

- [x] Verify the applied edit landed correctly (read-only checks, no hand-editing): `grep -n "four tiers\|Nemotron" ARCHITECTURE.md` must return no matches (stale claims removed), and `grep -n "Tier 5\|librarian\|agy\|gemini-3.1-pro\|deepseek-v4-pro" ARCHITECTURE.md` must return matches (new content present). Also confirm the cost/billing entry landed: `tail -5 logs/cost_log.jsonl | grep refresh-architecture-md-20260826` should show a line with `"billing": "local"` (or the fallback tier actually used, per `tests/test_tier5_librarian.py`'s documented cost-log shape).

### 3. Phase 3 — Update `AGENTS.md`'s own index to record this change (per standing repo/global convention: update after every implementation, via the librarian, not by hand)

- [x] Invoke `scripts/librarian_escalate.py` against `AGENTS.md` to record: (a) the new test file `tests/test_orchestrator_tier3_timeout_skip.py` under the `## tests/` section, one line in the same style as the other split-out test file rows (e.g. "regression coverage for `scripts/tier3_escalate.py`/`scripts/orchestrator.py`'s Tier 3 CLI-timeout soft-escalation to Tier 2 — distinguishes `subprocess.TimeoutExpired` from other Tier 3 failure modes and proves it lands on Tier 2 rather than crashing or going straight to `human_handoff`"); (b) a short note in the `## scripts/` pointer section (or the existing `tiers.yaml`/tier-behavior paragraph) that Tier 3 CLI timeouts now return `status: "timeout"` and soft-escalate rather than raising; (c) a one-line pointer noting `ARCHITECTURE.md` was refreshed 2026-08-26 for the 5-tier state (per this repo's doc-hygiene convention: pointer only, not a content duplicate).
  ```bash
  python3 scripts/librarian_escalate.py \
    --task-id update-agents-md-tier3-timeout-20260826 \
    --description "Record two changes in AGENTS.md's index, following its existing style exactly (do not restructure or prune anything else): (1) add tests/test_orchestrator_tier3_timeout_skip.py to the ## tests/ section's file list, describing it as regression coverage proving a scripts/llm_client.py subprocess.TimeoutExpired from the agy CLI (Tier 3) is returned by scripts/tier3_escalate.py as status: 'timeout' and soft-escalates to Tier 2 (DeepSeek) in scripts/orchestrator.py's run_task(), rather than raising RuntimeError or falling through to human_handoff; (2) add a short note near the tiers.yaml/scripts description that ARCHITECTURE.md was refreshed on 2026-08-26 to describe the current 5-tier state (Tier 2=DeepSeek, Tier 3=agy/gemini-3.1-pro, Tier 4=local Ollama, Tier 5=librarian) replacing its previous stale 4-tier description." \
    --target AGENTS.md \
    --workdir .
  ```
- [x] Verify: `grep -n "test_orchestrator_tier3_timeout_skip\|ARCHITECTURE.md was refreshed\|2026-08-26" AGENTS.md` returns matches, and confirm `AGENTS.md`'s total size is still under the repo's 73,728-char ceiling: `wc -c AGENTS.md` (must print a number ≤ 73728; if not, this is an escalation-worthy gap — a section would need moving to `docs/agents/` per the existing overflow convention, not a reason to trim content).
<!-- triapi:plan run_id=20260826-121026-fa6eea end -->

<!-- triapi:plan run_id=20260827-100542-afee9f start -->
## TriAPI Plan (run 20260827-100542-afee9f, appended 2026-08-27)

I have enough grounding. Here's the plan.

## 1. Fix the root cause: gate `_run_design_judge` by `critique.applies_to_tiers`

- [x] Edit `config/tiers.yaml`: change the `critique.applies_to_tiers` list (currently `["tier_3", "tier_1", "tier_2"]`, line ~142) to `["tier_3", "tier_1", "tier_2", "tier_4"]`. **Design decision, stated explicitly per the task's requirement to not silently pick one:** `_run_design_judge` currently runs unconditionally for every `is_regular_item` success, which today includes `tier_4`. Rather than change `tier_4`'s existing (correct, desired) behavior of going through the design judge, `tier_4` is added to `applies_to_tiers` so the new gate (below) preserves it explicitly instead of relying on the absence of a gate. `tier_5` is deliberately left out — that's the bug being fixed. Verify the edit didn't break YAML parsing: `python3 -c "from scripts.config_loader import load_tiers; c = load_tiers(); print(c['critique']['applies_to_tiers'])"` — must print `['tier_3', 'tier_1', 'tier_2', 'tier_4']`.

- [x] Edit `scripts/dispatcher.py`: add a small helper function near `_run_design_judge` (defined just above it, around line 1048), mirroring `orchestrator.py:80-82`'s exact gate pattern:
  ```python
  def _design_judge_applies(resolved_by: str | None, critique_cfg: dict) -> bool:
      """Mirrors orchestrator.py's _critique_and_maybe_revise_inner() gate: the
      design judge is advisory scaffolding scoped to the same tiers as the
      diff-quality critique step, driven by config/tiers.yaml's critique block
      (critique.enabled, critique.applies_to_tiers) so tier_5 (and any future
      tier not listed there) is never routed through it."""
      if not critique_cfg.get("enabled", False):
          return False
      return resolved_by in critique_cfg.get("applies_to_tiers", [])
  ```
  Then in `dispatch()`, at line ~1193 where `tier_5 = (load_tiers().get("tier_5_librarian") or {})` is currently fetched, change this to load the config once and derive both values:
  ```python
  _cfg = load_tiers()
  tier_5 = (_cfg.get("tier_5_librarian") or {})
  critique_cfg = _cfg.get("critique", {})
  ```
  Then at line 1301, change:
  ```python
  if result["status"] == "success" and is_regular_item:
      result = _run_design_judge(item, result, state, task_id)
  ```
  to:
  ```python
  if result["status"] == "success" and is_regular_item and _design_judge_applies(result.get("resolved_by"), critique_cfg):
      result = _run_design_judge(item, result, state, task_id)
  ```
  Verify syntax: `python3 -m py_compile scripts/dispatcher.py`.

## 2. Regression tests proving the fix

- [x] Edit `tests/test_design_judge_fix_forward_status.py`: add a new test class `TestDesignJudgeAppliesGate(unittest.TestCase)` with isolated, no-mocking-needed unit tests for the new pure helper: `test_disabled_critique_returns_false` (`{"enabled": False, "applies_to_tiers": ["tier_3"]}`, any `resolved_by` → `False`), `test_tier_in_list_returns_true` (`{"enabled": True, "applies_to_tiers": ["tier_3", "tier_4"]}`, `resolved_by="tier_4"` → `True`), `test_tier_not_in_list_returns_false` (same config, `resolved_by="tier_5"` → `False`), `test_missing_applies_to_tiers_key_returns_false` (`{"enabled": True}`, any `resolved_by` → `False`), `test_none_resolved_by_returns_false` (`{"enabled": True, "applies_to_tiers": ["tier_3"]}`, `resolved_by=None` → `False`). Verify: `python3 -m py_compile tests/test_design_judge_fix_forward_status.py && PYTHONPATH=. python3 -m unittest tests.test_design_judge_fix_forward_status -v`

- [x] Edit `tests/test_branch_features.py`: in the existing `DispatcherHookAndFixForwardTests` class (starts at line ~1232, same fixture/mock pattern as `test_successful_item_passing_judge_calls_extract_pattern` at line ~1249), add two new integration tests against the real `dispatch()` gate (these read the real `config/tiers.yaml` via `load_tiers()`, same as the existing tests in this class already do — no mock needed since step 1 already sets the real file's `applies_to_tiers` correctly):
  - `test_tier5_success_skips_design_judge`: same `@mock.patch` stack as `test_successful_item_passing_judge_calls_extract_pattern`, but `mock_run_task.return_value = {"status": "success", "resolved_by": "tier_5"}`. After `dispatcher.dispatch(state)`, assert `mock_eval.assert_not_called()`, `mock_extract.assert_not_called()`, `mock_handle_ff.assert_not_called()` — proves a tier_5 success never reaches `judge.evaluate_design` at all (the exact real-run bug: AGENTS.md/ARCHITECTURE.md tier_5 doc edits wrongly triggering fix-forward).
  - `test_tier4_success_still_runs_design_judge`: same stack, `mock_run_task.return_value = {"status": "success", "resolved_by": "tier_4"}`, `mock_eval.return_value = {"status": "ok", "approved": True, "reason": "looks good", "cost_usd": 0.0}`. After `dispatcher.dispatch(state)`, assert `mock_eval.assert_called_once()` and `mock_extract.assert_called_once()` — proves tier_4's pre-existing behavior (now explicit via config) is unchanged by the fix.
  Verify: `python3 -m py_compile tests/test_branch_features.py && PYTHONPATH=. python3 -m unittest tests.test_branch_features.DispatcherHookAndFixForwardTests -v`

- [x] Run the full regression suite named in `AGENTS.md`'s test-commands row, plus the two files touched above, and inspect for any `SKIPPED` lines (per the repo's standing "don't trust a bare OK" convention): `PYTHONPATH=. python3 -m unittest tests.test_branch_features tests.test_tier5_librarian tests.test_design_judge_fix_forward_status -v 2>&1 | tail -60`. Confirm zero failures, zero errors, zero unexpected `SKIPPED`.

## 3. Doc/carryover updates (via the repo's own conventions, not hand-edited)

- [x] Resolve the active carryover file and mark this queue item resolved via the librarian (per the "use librarian for doc edits" convention — do not hand-edit `CARRYOVER.md`/`docs/carryover/*.md` with Edit/Write): run `jq -r '.active' docs/carryover/index.json` to get the current active filename (`20260826-193000-tier3-timeout-softescalate-architecture-refresh-agentsmd-routing-bug.md` as of this writing — re-resolve at execution time in case it changed), then dispatch a librarian doc-edit task against it, e.g.:
  ```bash
  python3 scripts/librarian_escalate.py --task-id docfix-design-judge-gate \
    --description "Mark the tier_5-fed-into-_run_design_judge bug (AGENTS.md doc-edit wrongly triggering Tier 3 fix-forward, run 20260826-121026-fa6eea) RESOLVED: fixed by gating scripts/dispatcher.py's dispatch() call to _run_design_judge() on config/tiers.yaml's critique.applies_to_tiers (now includes tier_4, still excludes tier_5), mirroring orchestrator.py's existing critique gate. Regression tests added in tests/test_design_judge_fix_forward_status.py and tests/test_branch_features.py." \
    --target "docs/carryover/$(jq -r '.active' docs/carryover/index.json)" \
    --workdir . \
    --verify-cmd "true"
  ```
  Verify the file now states the resolution: `grep -n "design_judge\|applies_to_tiers" "docs/carryover/$(jq -r '.active' docs/carryover/index.json)"`.

- [x] Update `AGENTS.md`'s index the same way (per the same convention, and per its own standing rule that it's an index file updated after every implementation) — dispatch a librarian doc-edit task against `AGENTS.md` itself describing the new `_design_judge_applies` gate and the `critique.applies_to_tiers` addition of `tier_4`, e.g.:
  ```bash
  python3 scripts/librarian_escalate.py --task-id docfix-agentsmd-design-judge-gate \
    --description "Note in AGENTS.md's config/ (tiers.yaml) and scripts/ (dispatcher.py) index entries: dispatcher.dispatch()'s call to _run_design_judge() is now gated by a new _design_judge_applies() helper against config/tiers.yaml's critique.applies_to_tiers (now ['tier_3','tier_1','tier_2','tier_4']), mirroring orchestrator.py's existing critique gate -- fixes a bug where tier_5_librarian doc-edit successes were wrongly routed through the design judge and Tier 3 fix-forward." \
    --target AGENTS.md \
    --workdir . \
    --verify-cmd "python3 -c \"open('AGENTS.md').read()\""
  ```
  Verify: `grep -n "_design_judge_applies\|applies_to_tiers" AGENTS.md`.
<!-- triapi:plan run_id=20260827-100542-afee9f end -->

<!-- triapi:plan run_id=20260827-130627-e41ad6 start -->
## TriAPI Plan (run 20260827-130627-e41ad6, appended 2026-08-27)

I'll analyze the current configuration and create a precise execution plan. Let me first examine the relevant files to understand the exact current
<!-- triapi:plan run_id=20260827-130627-e41ad6 end -->
