# Agent testrun log — ghostwriter `--no-tier1`

Date: 2026-08-14  
Agent branch (TriAPI): `cursor` (created from `main`)  
Guide followed: `AGENT_GUIDE.md` (worked test case: ghostwriter, bare/local, no AI-detection loop)  
Target repo: `/home/dyne/Documents/Coding/oh-my-llama`  
Run ID: `20260814-184711-451738`  
Final status: **completed**

This file records what the supervising agent actually did while operating TriAPI with Tier 1 (Claude Code CLI repair) forced off via `triapi dispatch … --no-tier1` / `TRIAPI_NO_TIER1=1`. Per the guide, the agent was planner + supervisor + monitor — not the default worker — and only hand-wrote target-repo content after repeated tier failures / false successes.

---

## 0. Setup

1. Created git branch `cursor` in TriAPI (`git checkout -b cursor` from clean `main`).
2. Read `AGENT_GUIDE.md` end-to-end and treated the ghostwriter section as the dispatch-ready plan to feed into `triapi`, not code to implement by default.
3. Confirmed `triapi` on PATH (`~/.local/bin/triapi`), oh-my-llama at `/home/dyne/Documents/Coding/oh-my-llama`, no pre-existing `ohmyllama/ghostwriter.py`.
4. Confirmed no live `triapi dispatch` process before starting / before any state JSON hand-patches (`pgrep -af "triapi dispatch"` / `scripts/triapi.py dispatch`).

Artifacts written during planning (TriAPI repo):

- `logs/ghostwriter_plan_prompt.txt` — full phased prompt fed to the planner
- `logs/ghostwriter_draft_plan_20260814-184711-451738.md` — Claude planner output
- `logs/ghostwriter_draft_meta_20260814-184711-451738.json` — session_id / notional cost
- `logs/patch_gw_buildcmds.py` — supervisor helper that strengthened weak `build_cmd`s

---

## 1. Plan

- Drove planning via `scripts.planner.plan_turn` + `dispatcher.new_run` (same machinery as `triapi plan`; interactive stdin not available in this agent environment).
- Planner notional cost: ~$0.6449 (subscription-covered).
- Reviewed the draft plan in full: 4 phases matching the guide (ingestion allowlist + `discover_job`, style/draft APIs, `run_job` + CLI, final sweep). Approved by setting `status=planned` and `plan_text` on the run JSON (equivalent to typing `approve` in `triapi plan`).

Approved plan file: `logs/ghostwriter_draft_plan_20260814-184711-451738.md`.

---

## 2. Dispatch (`--no-tier1`)

```bash
triapi dispatch 20260814-184711-451738 --no-tier1 --background
```

Breakdown (Tier 2 / Gemini, phase-by-phase): **4 phases, 13 items**.

| Phase | Name | Items |
|-------|------|-------|
| p0 | Ingestion allowlist + folder-walk/pairing | 3 |
| p1 | Style profile + per-prompt draft | 4 |
| p2 | Orchestration + CLI entry point | 3 |
| p3 | Final sweep | 3 |

Notes during breakdown / early dispatch:

- Default Gemini model `gemini-3.5-flash` hit free-tier daily quota; fallbacks used (`gemini-3.1-flash-lite`, etc.).
- Local Ollama (`localhost:11434`) was **down** for most of the run → Tier 4 failed immediately every time (`Connection refused`), so the real chain was effectively **Tier 3 (DeepSeek) → [Tier 1 skipped] → Tier 2 (Gemini) → human_handoff**.
- `TRIAPI_NO_TIER1=1` confirmed in logs (`Tier 1 manager refused: TRIAPI_NO_TIER1 is set in the environment`).
- Background dispatch child does not re-pass `--no-tier1` on argv, but inherits the env var set by the parent — that worked.

Monitored via `logs/triapi.log` and `logs/runs/20260814-184711-451738.json` (the per-run `.log` stayed empty due to Python stdout buffering when redirected).

---

## 3. Human_handoff / supervisor interventions

Discipline from `AGENT_GUIDE.md`: read escalation log + real `git diff` / file contents; distinguish **weak build_cmd** vs **genuine gap**; patch build_cmds in breakdown (+ results when present); verify by hand before resume; only hand-write target files as last resort; mark `status=success`, `resolved_by=manual`, refresh `content_hash` via `scripts.regression_guard.hash_file()`; never edit run JSON while a live dispatch holds it.

### 3.1 p0-i0 — ingestion allowlist

- First landed as `success` via **tier_2**.
- Allowlist gained `~/ghostwriter` (later strengthened by supervisor to `OMLL_GHOSTWRITER_DIR` + `extra_allowed_dirs=` on `DocumentIngester.read()` so tmp-dir tests / job folders outside Downloads/Documents work without bypassing the security check).
- Diff also showed adjacent churn in `propose()` / `_ingest_image` mixed with a dirty oh-my-llama working tree — spot-checked; allowlist ask itself did land.

### 3.2 p0-i1 — `ohmyllama/ghostwriter.py` (pairing)

**Failure class: weak build_cmd, then genuine gap after strengthening.**

1. First “success” via **tier_3** with build_cmd ≈ `py_compile` only.
2. Spot-check: file was an unrelated **Ollama CLI** (`requests`, `normalize_host`, `generate`, …) — **no** `discover_job` / `GhostwriterJob`. Classic tautological check.
3. Escalation / stop on p0-i2 (tests collected 0 pytest items against that wrong API).
4. Supervisor patched breakdown `build_cmd` to import/assert real pairing API + tempfile pairing check (`logs/patch_gw_buildcmds.py`); removed false-success p0-i1 and failed p0-i2 from `results[]` so resume restarted at p0-i1.
5. Resume: Tier 3 bolted a stub `discover_job` onto the wrong CLI file (`sources: list[str]`, wrong types) → still failed strong build_cmd → handoff. Tightened item description to “REPLACE entire file…”. Third attempt: Tier 3 still wrong shape; Tier 2 **503 high demand** → handoff again.
6. **Last resort hand-write** of Phase-1-only then later full module (see §4). Marked `resolved_by=manual`, refreshed hash, resumed.

Escalation logs: `logs/escalation_20260814-184711-451738-p0-i1.md`, `…-p0-i2.md`.

### 3.3 p0-i2 — `tests/test_ghostwriter.py`

- Tiers kept rewriting tests for the **wrong** Ollama CLI (`run_tests()` / `normalize_host`, no `def test_*`) → pytest `-k discover_job` collected **0 items**.
- Large Tier 3 token outputs did not produce correct pytest tests; Tier 2 often 503.
- **Hand-wrote** proper pytest tests (pairing, extension-agnostic match, missing-pair raise). Verified green. Marked manual. Resumed.

### 3.4 p1-i0 — `build_style_profile`

- Marked `success` via **tier_2** with weak build_cmd:  
  `python3 -c "import …; print(…build_style_profile)"` (symbol exists only).
- Spot-check: function was  
  `def build_style_profile(job: GhostwriterJob) -> str: return ""` — wrong signature, empty placeholder.
- Caught by supervisor; later overwritten as part of full hand-write of `ghostwriter.py`.

### 3.5 p1-i1 — `test_build_style_profile`

- Handoff: 3 existing discover tests deselected; no `test_build_style_profile` (`logs/escalation_…-p1-i1.md`).
- Included in full test file hand-write.

### 3.6 Phases 1–3 bulk manual completion

After repeated Tier 3/2 failures under no Ollama + Gemini quota/503, supervisor implemented the remaining Phase 2–3 surface in the target repo (still last-resort / unblock the pipeline), verified locally, then rebuilt `results[]` for phases 0–2 as `success` / `resolved_by=manual` with fresh hashes so dispatch could run Phase 4 verify_only items.

Also fixed a **pre-existing CLI bug** blocking `python3 -m ohmyllama.cli …`: `Config` is frozen and `main()` assigned `cfg.ollama_url = …` → `FrozenInstanceError`. Switched to `object.__setattr__`. Later smoke showed `Config.load()` can return `127.0.0.1:11434` **without** a scheme; httpx then errors `Request URL is missing an 'http://' or 'https://' protocol`. Normalized to prepend `http://` when missing.

### 3.7 Phase 4

| Item | Outcome |
|------|---------|
| p3-i0 `bash run_tests.sh` | **success** (`resolved_by=verify`) |
| p3-i1 `py_compile` touched modules | **success** (`resolved_by=verify`) |
| p3-i2 live smoke CLI + read `result.txt` | initially handoff (Ollama down / bare host URL); after starting `ollama serve` + URL scheme fix, smoke **passed**; supervising agent judged prose; marked **manual** |

Smoke job: `~/ghostwriter/smoke/`  
Output: `~/ghostwriter/smoke/result.txt` — contains `--- 1 ---` once with non-empty draft; short/direct sentences roughly matching the sample voice (acceptable for v1 smoke; not a quality gate beyond “human/agent reads it”).

Escalation: `logs/escalation_20260814-184711-451738-p3-i2.md`.

---

## 4. What landed in oh-my-llama (target)

Not committed by this agent unless the user asks — work is in the oh-my-llama working tree.

| Path | Change |
|------|--------|
| `ohmyllama/capabilities/ingestion.py` | `OMLL_GHOSTWRITER_DIR` (default `~/ghostwriter`) + optional `extra_allowed_dirs` on `read()`; allowlist kept |
| `ohmyllama/ghostwriter.py` | **New**: `GhostwriterError`, `GhostwriterJob`, `discover_job`, `build_style_profile`, `draft_for_prompt`, `run_job` using `client_for(cfg).chat(cfg.model_heavy, …)` and `DocumentIngester` |
| `tests/test_ghostwriter.py` | **New**: 6 pytest tests (discover ×3, style, draft, run_job e2e with fakes) |
| `ohmyllama/cli.py` | `_cmd_ghostwrite` + `ghostwrite` subparser; frozen-Config + URL-scheme fixes in `main()` |

Verify commands that passed under supervision:

- `uv run python3 -m pytest tests/test_ghostwriter.py -v` → 6 passed  
- `uv run python3 -m ohmyllama.cli ghostwrite --help` → shows `job_dir`  
- `uv run python3 -m py_compile ohmyllama/ghostwriter.py ohmyllama/cli.py ohmyllama/capabilities/ingestion.py`  
- `bash run_tests.sh` (via dispatch verify)  
- Live: `uv run python3 -m ohmyllama.cli ghostwrite ~/ghostwriter/smoke`

---

## 5. Final run ledger

```
20260814-184711-451738-p0-i0  success  manual   ohmyllama/capabilities/ingestion.py
20260814-184711-451738-p0-i1  success  manual   ohmyllama/ghostwriter.py
20260814-184711-451738-p0-i2  success  manual   tests/test_ghostwriter.py
20260814-184711-451738-p1-i0  success  manual   ohmyllama/ghostwriter.py
20260814-184711-451738-p1-i1  success  manual   tests/test_ghostwriter.py
20260814-184711-451738-p1-i2  success  manual   ohmyllama/ghostwriter.py
20260814-184711-451738-p1-i3  success  manual   tests/test_ghostwriter.py
20260814-184711-451738-p2-i0  success  manual   ohmyllama/ghostwriter.py
20260814-184711-451738-p2-i1  success  manual   tests/test_ghostwriter.py
20260814-184711-451738-p2-i2  success  manual   ohmyllama/cli.py
20260814-184711-451738-p3-i0  success  verify   (run_tests.sh)
20260814-184711-451738-p3-i1  success  verify   (py_compile)
20260814-184711-451738-p3-i2  success  manual   (live smoke + prose judgment)
```

Run JSON: `logs/runs/20260814-184711-451738.json` — `status: completed`.

---

## 6. Lessons (for the next `--no-tier1` agent)

1. **Never trust `success` without reading the file.** Weak build_cmds (`py_compile`, `print(symbol)`) produced the worst false positives in this run.
2. **Patch build_cmds in the live breakdown** (and any frozen `results[]` / regression_flags copies) before resume, or the same tautology fires again.
3. **Environment matters:** Tier 4 was useless with Ollama down; Gemini free-tier exhaustion + 503s made Tier 2 a coin flip. Starting `ollama serve` and fixing scheme-less URLs unblocked the mandatory smoke step.
4. **Background dispatch** inherits `TRIAPI_NO_TIER1` via env; confirm with log lines, not argv alone.
5. **Hand-writing target content** was required for the new module/tests/CLI after multiple full escalation chains — matching the guide’s expectation that Tier 1’s absence shows up hardest on brand-new files and pairing edge cases.
6. Do **not** edit run state JSON while a dispatch process is alive.

---

## 7. TriAPI branch note

Work on TriAPI itself was limited to: branch `cursor`, this log, and under `logs/` (prompt, draft plan, patch helper, run/escalation artifacts). Product code changes for the feature live in **oh-my-llama**, as intended.
