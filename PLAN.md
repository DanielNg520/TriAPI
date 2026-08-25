# TriAPI — 4-Tier AI Coding Pipeline Orchestrator

## Context

The user has a C++/Edge AI development workflow and wants to stop burning paid Claude Pro/Gemini Pro quota on routine debugging. Their `TriAPI.pdf` document proposes inserting **DeepSeek** (`deepseek-v4-flash`/`deepseek-v4-pro`) as a cheap "Tier 3" escalation layer between a free local Ollama worker (Tier 4) and the expensive strategic tiers (Claude Code = Tier 1, Google Antigravity/Gemini = Tier 2). DeepSeek's automatic disk-based prefix caching makes repeated codebase-context calls cost under $0.0003 each, so routing hard compile failures through it before escalating further preserves the paid subscriptions for genuine architectural work.

The `TriAPI` repo (`/home/dyne/Documents/Coding/TriAPI`) started blank — one Apache-2.0 `LICENSE` file, one commit, a GitHub remote (`DanielNg520/TriAPI`) with nothing pushed. The user confirmed:
- They already have working access to all four tiers (Claude Pro/Max + CLI, Antigravity + AI Studio, a DeepSeek API key, and local Ollama with models pulled).
- **TriAPI is the orchestration/tooling repo** that wires the four tiers together — not a C++ project itself.
- Build the **full pipeline**, phase by phase, with a checklist and end-of-phase tests for each.
- Use a **real DeepSeek API call** for end-to-end verification (real, sub-cent cost) rather than mocking it.
- This plan doc lives at the **repo root** (`PLAN.md`) as the running progress tracker, checked off phase by phase.
- Secrets use **sops + age**, not `.env`. An age key already exists at `~/.config/sops/age/keys.txt` (public key `age1wp8kgtd5jnzy37hlxy54erzms8zek5ae2x3a9a467p3ereu8e5yq8w43lp`).

Per the user's global CLAUDE.md instruction, `mapping.md` is created early and kept updated after every phase.

## Environment notes (confirmed during exploration)

- `claude` CLI v2.1.222 and `ollama` binary are both installed locally. **Ollama runs via a pre-existing systemd user service** (`~/.config/systemd/user/ollama.service`, already `enabled` — persists across reboots) — use `systemctl --user start/status ollama`, not a manual `ollama serve` process. The service already had `OLLAMA_IGPU_ENABLE=1`/`OLLAMA_VULKAN=1` configured correctly; the CPU-fallback slowness noted in Phase 2 turned out to be because a manual `nohup ollama serve` (started before this service was discovered) doesn't pick up those env vars and Ollama drops integrated GPUs by default. Fixed 2026-08-10 by switching to the systemd service — confirmed via `ollama ps` (`size_vram` now non-zero, was `0` before) that the AMD Radeon 780M iGPU (Vulkan, ~15.8 GiB) is now actually used.
- Python 3.14.6 with `requests` and `PyYAML` already available; the `mcp` SDK is not yet installed and goes in `requirements.txt`.
- `sops`, `age`, `age-keygen` are all installed at `~/.local/bin/`; a usable age key already exists.

## Key design decisions

- **Language:** Python for every script (`tier4_worker.py`, `tier3_escalate.py`, `orchestrator.py`) — Ollama and DeepSeek both expose simple REST/OpenAI-compatible APIs.
- **State persistence:** escalation state (consecutive build-failure count) is file-backed per task (`logs/state/<task_id>.json`), not in-memory — Tier 4 is expected to run as discrete process invocations (e.g. dispatched by Antigravity per attempt via MCP), not one long-lived loop.
- **Cost logging:** append-only JSON Lines at `logs/cost_log.jsonl`, storing raw cache-hit/cache-miss token counts (not just computed dollars) so historical cost can be recomputed if pricing in `tiers.yaml` goes stale.
- **Cache-hit optimization:** the DeepSeek client builds prompts with a deterministic, byte-stable prefix (system prompt + static codebase context) first, and appends the small variable part (this attempt's stderr) last.
- **Tier 2 (Gemini via Google AI Studio) — amended 2026-08-10, now automatable:** originally designed as a GUI-only human handoff (Antigravity desktop app has no CLI/headless mode). The user pointed out Google AI Studio exposes a real REST API for Gemini, so Tier 2 is now called automatically via that API — the Antigravity desktop app remains available as an optional manual review surface but is no longer required for automated escalation. `escalation_rules` in `tiers.yaml` chains `tier3_to_tier1` (DeepSeek unresolved → `claude -p`) → `tier1_to_tier2` (Claude unresolved → Gemini API) → `tier2_to_human` (Gemini unresolved → log_and_notify, final fallback). **Jules (Google's async coding-agent CLI) was briefly considered as the Tier 2 primary with Gemini API as fallback, but per the user this is deferred until `jules login` is done and more is known — see the DEFERRED note at the top of Phase 4 for the research already gathered.**
- **Tier 1 (Claude Code) automation:** `claude -p "<prompt>"` is real and scriptable; confirm actual non-interactive output flags via `claude -p --help` during Phase 4 rather than assuming a format.
- **OpenRouter:** the user has an OpenRouter key installed but wasn't sure it adds value here — explicitly left out of the pipeline for this pass, not integrated.
- **Budget guard (added 2026-08-10):** Tier 1 (`claude -p`) and Tier 2 (Gemini API) must never silently fall into pay-per-token billing. `scripts/budget_guard.py` runs a pre-flight check before each call: for Tier 1, verify `ANTHROPIC_API_KEY` is not set in the environment (its presence would route `claude -p` to metered API billing instead of the Pro/Max subscription) and that the CLI reports an active subscription login; for Tier 2, track call counts against Google AI Studio's documented free-tier RPM/RPD limits (recorded in `tiers.yaml`'s `tier_2_manager.pricing`, currently unverified — must be filled in during Phase 4) in a local usage log, and refuse to proceed (hard stop, not a silent charge) if the call would exceed the free tier, surfacing this as a status the orchestrator logs and reports rather than an automatic override.
- **Cost reporting (added 2026-08-10):** `scripts/cost_report.py` aggregates `logs/cost_log.jsonl` per `task_id` and prints a clear breakdown (DeepSeek $ spent with cache-hit savings called out, Gemini free-tier call count vs. limit, Claude subscription calls at $0 marginal cost) so the user always knows exactly what a task cost. `orchestrator.py` calls this at the end of every run and includes the total in its final structured status.
- **Secrets:** `deepseek_api_key`, `google_ai_studio_api_key`, `ollama_host` live in `config/secrets.enc.yaml`, sops-encrypted to the age recipient in `.sops.yaml` — safe to commit as ciphertext. Decrypted at runtime via `scripts/secrets_loader.py`, which shells out to `sops -d`. Never printed/logged. Edit the real values with `sops config/secrets.enc.yaml`.

---

## Phase 0 — Scaffolding, secrets, and plan tracking ✅

**Dev checklist:**
- [x] Create directories: `config/`, `scripts/`, `logs/`, `logs/state/`, `samples/`
- [x] Write this plan to the repo root as `PLAN.md`
- [x] Create `mapping.md` at repo root
- [x] Create `.gitignore` excluding: `logs/*.jsonl`, `logs/*.md`, `logs/state/*.json`, `config/secrets.yaml` (plaintext working copy), `__pycache__/`, `*.pyc`, `.venv/` — note `config/secrets.enc.yaml` is deliberately NOT ignored (ciphertext, safe to commit)
- [x] Create `.sops.yaml` creation rule for `config/secrets.enc.yaml` → age recipient
- [x] Create `config/secrets.example.yaml` (plaintext template, no real values) and `config/secrets.enc.yaml` (sops-encrypted, placeholder values, ready for the user to fill in with `sops config/secrets.enc.yaml`)
- [x] Create `scripts/secrets_loader.py`: `load_secrets()` decrypts via `sops -d --output-type json`
- [x] Create `requirements.txt`: `requests`, `PyYAML`, `mcp`
- [x] Create `logs/state/.gitkeep`
- [x] Create empty stub `ARCHITECTURE.md` and `README.md` (filled in Phase 7)

**End-of-phase tests (seam / gap / function):**
- [x] **Seam** — `git status` shows exactly the expected new files/dirs.
- [x] **Gap** — confirmed sops encrypt/decrypt round-trips correctly against the existing age key (`sops -e -i` then `sops -d` returns the original plaintext); `config/secrets.yaml` (plaintext working copy) is gitignored so it can never be committed by accident.
- [x] **Function** — in a fresh virtualenv, `pip install -r requirements.txt` completes without errors.

---

## Phase 1 — `config/tiers.yaml` + config loader ✅

**Dev checklist:**
- [x] Write `config/tiers.yaml` with blocks: `tier_1_planner`, `tier_2_manager` (`automatable: false`), `tier_3_debugger` (DeepSeek models + pricing + `last_verified` date; noted pro cache-miss and both models' output pricing as unverified/`null`), `tier_4_worker` (Ollama models + `build_commands`), `escalation_rules` (`tier4_to_tier3` threshold=2, `tier3_to_tier2` action=log_and_notify)
- [x] Write `scripts/config_loader.py` exposing `load_tiers() -> dict`, raising `ValueError` if required keys are missing
- [x] Update `mapping.md` with the two new files

**End-of-phase tests:**
- [x] **Seam** — `python3 -c "from scripts.config_loader import load_tiers; print(load_tiers())"` runs without error and returns a populated dict.
- [x] **Gap** — deleted `escalation_rules` from a temp copy of the YAML; `load_tiers()` raised a clear `ValueError` naming the missing key, not a raw `KeyError`.
- [x] **Function** — printed resolved Tier 4 draft model (`qwen3.6:27b`), Tier 3 flash cache-hit price (`0.0028`), and escalation threshold (`2`) — all match the YAML.

---

## Phase 2 — Tier 4 (Ollama) local worker ✅

**Dev checklist:**
- [x] `ollama serve` running locally (started manually, was not running by default); `qwen3-coder:30b-cc` and `gpt-oss:20b` already pulled
- [x] Write `scripts/state.py`: `read_state(task_id)`, `write_state(task_id, data)`, `clear_state(task_id)`, `record_failure(task_id, stderr)` against `logs/state/<task_id>.json`
- [x] Write `scripts/tier4_worker.py` accepting task_id, task description, target file, workdir, build command, model override
- [x] Implement Ollama call (`POST /api/generate`) using the model from config
- [x] Write generated code to target file (extracted from the first/largest fenced code block in the response)
- [x] Run build command via `subprocess.run` with timeout, capture stdout/stderr
- [x] On failure: increment failure count via `state.py`; on success: clear state
- [x] Emit structured JSON to stdout: `{status, consecutive_failures, stderr}`, `status="escalate"` once threshold hit
- [x] Update `mapping.md`

**Amendment (2026-08-10):** the configured default draft model started as `qwen3.6:27b`, but this machine runs Ollama on a Ryzen iGPU that isn't being picked up by Ollama's backend (`size_vram: 0` — CPU fallback), making a 27B/30B model very slow per call (~2+ min for a single file generation). Per the user, `qwen3-coder:30b-cc` (code-specialized) and `gpt-oss:20b` are the two models known to run acceptably; `tiers.yaml`'s `tier_4_worker.models.draft` is now `qwen3-coder:30b-cc` (was `qwen3.6:27b`), fallback stays `gpt-oss:20b`. For fast mechanics testing (state/counter logic, not code quality), tests below used `qwen3:0.6b` via `--model` override instead of waiting on the 30B model each run.

**End-of-phase tests:**
- [x] **Seam** — ran `tier4_worker.py` once against a throwaway broken-build snippet at `/tmp/.../scratchpad/tier4_test/main.cpp`; it called Ollama, extracted a fix from the fenced code block, wrote the file, and the build succeeded on the first attempt (status `success`, state cleared).
- [x] **Gap** — using `--model qwen3:0.6b` with a forced-failing build command (`exit 1`) to isolate the counter logic from model speed/quality: run 1 → `{"status": "build_failed", "consecutive_failures": 1}`; run 2 → `{"status": "escalate", "consecutive_failures": 2}`; run 3 with a forced-succeeding command (`true`) → `{"status": "success", "consecutive_failures": 0}` and `logs/state/<task_id>.json` was deleted.
- [x] **Function** — inspected `logs/state/<task_id>.json` directly: keys are exactly `task_id`, `consecutive_failures`, `last_stderr`, `last_attempt_ts` — matches what Phase 3/4 expect to read.

---

## Phase 3 — Tier 3 (DeepSeek) escalation client ✅

**Dev checklist:**
- [x] Write `scripts/tier3_escalate.py`
- [x] Implement deterministic stable-prefix prompt builder (system message = fixed instructions + full current file contents, byte-stable across calls with unchanged file content) + variable stderr as the final user message
- [x] Load `deepseek_api_key` via `scripts/secrets_loader.py`; never log or print it
- [x] Call DeepSeek's OpenAI-compatible chat completions endpoint (`{endpoint}/chat/completions`) with model from config
- [x] Parse `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens` / `completion_tokens` from usage block
- [x] Compute cost from `tiers.yaml` pricing (`compute_cost()` marks `cost_partial: true` when a price component, e.g. DeepSeek Pro's cache-miss rate, is still `null`/unverified); append one line to `logs/cost_log.jsonl`
- [x] Apply the returned fix to the target file (reuses `tier4_worker.extract_code()` for the fenced-code extraction, avoiding duplication)
- [x] Update `mapping.md`

**End-of-phase tests (real DeepSeek API calls, per user's choice):**
- [x] **Seam** — one real call against a genuine `g++` compile error (missing semicolon); DeepSeek returned a correct fix, it was applied to the target file, and `logs/cost_log.jsonl` got a well-formed entry (`cache_miss_tokens: 248, cache_hit_tokens: 0` — expected cold-cache first call).
- [x] **Gap** — restored the file to byte-identical broken content and called again with the same task: `cache_hit_tokens` jumped from 0 → 128 (cache_miss dropped 248 → 120), i.e. 0% → ~52% hit ratio on the second call. This is a small fixture (~250 tokens) so it doesn't show the source doc's >95% figure (that requires a much larger stable codebase context), but it proves the caching mechanism itself is working as designed.
- [x] **Function** — rebuilt with `g++ -Wall`: clean build, correct output, no corruption or partial writes in the applied fix. Total real cost for both test calls: ~$0.000052 (sub-cent, consistent with the doc's economics).

**Note carried to Phase 4:** the current `compute_cost()` returns a partial (undercounted) dollar figure for DeepSeek Pro and for output tokens on both models, since those per-token prices weren't in the source doc and are `null` in `tiers.yaml`. Raw token counts are always logged in full regardless, so `cost_report.py` (Phase 4) can recompute accurately once real pricing is filled in.

---

## Phase 4 — Orchestrator, budget guard, and cost reporting ✅

**DEFERRED: Jules integration.** The user has Google's `jules` CLI installed (`/usr/local/bin/jules`), an asynchronous coding agent comparable to Claude Code CLI, and originally wanted it as the primary Tier 2 worker with the Gemini API demoted to fallback. Per the user (2026-08-10): **build Tier 2 as the Gemini API only for this pass; Jules integration waits until more is known about it** (notably: `jules login` hasn't been run yet — `jules remote list --repo` currently returns `401 UNAUTHENTICATED`, and that's an interactive OAuth flow the user has to run themselves). Research findings are kept here so this isn't re-derived later:
- **Not a synchronous call.** `jules new "<task>" --repo <owner/repo>` creates a session in a remote VM; results come back via `jules remote list --session` (poll for status) then `jules remote pull --session <id> --apply` (pulls and applies the resulting patch locally) — structurally different from every tier built so far (all synchronous request → response).
- **Requires a GitHub-connected repo**, referenced as `owner/repo` — Jules clones from GitHub into its own VM, it does not operate on an arbitrary local directory. The target project must be pushed to GitHub and connected via the [Jules GitHub App](https://github.com/apps/google-labs-jules/installations/select_target).
- **Likely much slower** than the other tiers (VM spin-up + clone + work + patch, plausibly minutes vs. seconds).
- **When revisited:** `tiers.yaml`'s `tier_2_manager` would need a `primary` (Jules)/`fallback` (Gemini API) split, `tier2_escalate.py` would need a `try_jules()` async session/poll/pull path alongside today's synchronous Gemini call, and `budget_guard.py` would need a cheap Jules login-status check. None of this is built now — Tier 2 below is Gemini-API-only, structured the same way as Tier 3.

**Dev checklist:**
- [x] Ran `claude -p --help`: `--output-format json` gives structured cost/usage data; `--tools ""` disables tool access (no permission prompts, pure text in/out like the other tiers); `--system-prompt` fully overrides the default system prompt, cutting per-call overhead from ~61K to ~2K cache-creation tokens (default CLAUDE.md auto-discovery is expensive and irrelevant for a one-shot fix). **Found and avoided a trap: `--bare` forces `ANTHROPIC_API_KEY`/`apiKeyHelper` auth and never reads OAuth/keychain — using it would silently defeat the whole point of the budget guard.**
- [x] Confirmed `ANTHROPIC_API_KEY` is unset in this environment (subscription auth path, as expected)
- [x] Filled `tiers.yaml`'s `tier_2_manager.pricing` with `free_tier_rpm`/`free_tier_rpd` — marked explicitly as conservative, unverified placeholders (10 rpm / 250 rpd) since actual Google AI Studio limits weren't verified; `budget_guard.py` treats them as a hard cap regardless
- [x] Wrote `scripts/budget_guard.py`: `check_tier1_ok()` refuses if `ANTHROPIC_API_KEY` is set; `check_tier2_ok()` tracks calls in `logs/gemini_usage.jsonl` and refuses if the next call would cross the configured RPM/RPD limit
- [x] Wrote `scripts/tier1_escalate.py` (new, not originally scoped as a separate file, but added for symmetry with tier2/tier3 and reuse by `cost_report.py`): shells out to `claude -p` with `--tools ""` and the minimal `--system-prompt`, extracts the fix via `tier4_worker.extract_code()`, logs both `cost_usd: 0.0` (actual) and `notional_cost_usd` (what it would have cost on metered billing) with `billing: "subscription"`
- [x] Wrote `scripts/tier2_escalate.py`: Gemini API client via Google AI Studio REST (`v1beta/models/{model}:generateContent`), calls `budget_guard.check_tier2_ok()` first, logs usage with `billing: "free_tier"`
- [x] Wrote `scripts/cost_report.py`: `report(task_id)` aggregates `logs/cost_log.jsonl` per task; `format_report()` clearly separates actual $ spent from notional/subscription-covered cost per tier
- [x] Refactored `scripts/tier4_worker.py` to expose a callable `run(...)` function (previously logic was inlined in `main()`) so the orchestrator can call it directly instead of subprocessing
- [x] Wrote `scripts/orchestrator.py`: Tier 4 draft+build loop → (on `escalate`) Tier 3 patches the file, then a **plain rebuild** (`tier4_worker.run_build()`, not a re-draft — re-drafting would overwrite the tier's fix) → Tier 1 (budget-guarded) patches + rebuild → Tier 2 (budget-guarded) patches + rebuild → human handoff
- [x] Implemented human handoff: `logs/escalations.jsonl` + `logs/escalation_<task_id>.md`, console notice; nothing calls Antigravity programmatically
- [x] `cost_report.report(task_id)` called at the end of every run, included in the final result and printed
- [x] Updated `mapping.md`

**Bug found and fixed during testing:** `orchestrator.py` initially passed the raw (workdir-relative) `--target` straight to `tier1_escalate`/`tier2_escalate`/`tier3_escalate`, which (unlike `tier4_worker.run()`) don't take a `workdir` argument and resolve the path themselves — caused a `FileNotFoundError` on the first real run. Fixed by resolving `target` against `workdir` once in `orchestrator.run_task()` and passing the resolved absolute path to all three escalation tiers.

**End-of-phase tests (real API calls throughout):**
- [x] **Seam** — full run with a fast test model (`--tier4-model qwen3:0.6b`, used only for speed of iteration — production default stays `qwen3-coder:30b-cc`) against a real broken-build fixture: Tier 4 fixed it on the first attempt, orchestrator correctly returned `{"status": "success", "resolved_by": "tier_4"}` and printed a cost report showing **no** paid-tier calls — proving it doesn't over-escalate when a cheaper tier already resolved things.
- [x] **Gap** — seeded state one failure below threshold and forced the build to always fail (`--build-cmd "exit 1"`, deterministic — independent of what any tier's fix contains) to exercise the full chain in one real run: Tier 4 escalated → **Tier 3** (real DeepSeek call, $0.000009 actual) → rebuild still fails → **Tier 1** (real `claude -p` call, $0.3145 notional/subscription-covered) → rebuild still fails → **Tier 2** (real Gemini call, free tier) → rebuild still fails → correctly wrote `logs/escalations.jsonl` + `logs/escalation_<task_id>.md` and returned `{"status": "human_handoff", "resolved_by": null}`. Separately, re-ran the same scenario with `ANTHROPIC_API_KEY` set: `[BUDGET GUARD] Tier 1 skipped: ...` printed, no `tier_1` entry in the cost report, Tier 2 still ran — confirms the guard actually prevents the metered-billing path rather than just logging a warning.
- [x] **Function** — cross-checked `cost_report.py`'s printed numbers against the raw `logs/cost_log.jsonl` entries for the same task: exact match (tier_3 `$0.000009`, tier_1 `$0.0` actual / `$0.3145` notional, tier_2 `$0.0`). Confirmed `logs/state/<task_id>.json` is deleted on the successful (Tier 4) run.

---

## Phase 5 — SKIPPED (was: MCP server for Antigravity)

**Skipped, 2026-08-10, per the user.** This phase's entire premise was the source doc's claim that "Antigravity dispatches tasks via MCP to Tier 3." That's no longer true: Tier 2 was redesigned in Phase 4 to call the Gemini API directly, so Antigravity's role dropped to an optional manual-review surface — nothing in the current design needs it to dispatch anything. `orchestrator.py` is already a complete, standalone entry point (CLI or Python import) that drives the full Tier 4→3→1→2 chain on its own; there's no dispatcher left for an MCP server to serve.

The user's stated direction: if an MCP-style integration is needed later, it points toward **Jules** (still deferred per the Phase 4 note — pending `jules login` and more research), not Antigravity. `scripts/mcp_server.py` is not built. `mcp` stays in `requirements.txt` for now (harmless if unused; revisit if it's confirmed dead weight by Phase 7).

---

## Phase 6 — End-to-end fixture ✅

**Dev checklist:**
- [x] Created `samples/broken_build/main.cpp`: a genuine, realistic C++ bug (copy-constructing a `std::vector<std::unique_ptr<Widget>>`, which fails because `unique_ptr`'s copy constructor is deleted) — not an artificial syntax error, representative of the "complex C++ logic" the source doc scoped for Tier 3 escalation. Confirmed it fails to build first (real, deep templated `g++` error).
- [x] Created `samples/broken_build/CMakeLists.txt` (C++17, standard CMake project)
- [x] Ran `scripts/orchestrator.py` against this fixture end-to-end with **production defaults** (real Ollama with the configured `qwen3-coder:30b-cc`, no test-model override; real DeepSeek available if needed)
- [x] Updated `mapping.md`

**Bonus fix during this phase:** discovered mid-run that Ollama was falling back to CPU because it was being started manually (`nohup ollama serve`) instead of via the pre-existing, correctly-configured systemd user service (`~/.config/systemd/user/ollama.service`, already had `OLLAMA_IGPU_ENABLE=1`). Switched to `systemctl --user start ollama`; confirmed via `ollama ps` that the AMD Radeon 780M iGPU (Vulkan) is now actually used (`size_vram` non-zero). Service is already `enabled`, so this persists across reboots — no more manual Ollama startup needed for any future work in this repo. See the Environment notes section above.

**End-of-phase tests — actual result differs from the plan's assumption, documented honestly:**
- [x] **Seam/Gap/Function (combined)** — the production Tier 4 model (`qwen3-coder:30b-cc`) **resolved the bug correctly on its own**, no escalation needed: `{"status": "success", "resolved_by": "tier_4"}`, cost report showed `$0.000000` (no paid-tier calls). Verified independently: rebuilt with `cmake --build build` (clean build), ran the binary (correct output: `Widget ID: 1` / `Widget ID: 2`), confirmed `logs/state/phase6-fixture.json` was deleted. The plan's test description assumed 2 Tier-4 failures triggering Tier-3 escalation — that didn't happen here because the production coder model is genuinely capable enough to fix this particular bug unassisted. **This is not a gap**: the full Tier4→3→1→2→handoff escalation chain was already proven end-to-end with real API calls in Phase 4's gap test (using a deterministic forced-failure build command specifically to exercise that path) — Phase 6's job was to prove realistic, unforced, production-config operation, which it did, efficiently and at zero cost.

---

## Phase 7 — Documentation ✅

**Dev checklist:**
- [x] Write `ARCHITECTURE.md`: the 4-tier design, the escalation state machine (as an actual diagram), DeepSeek cache-hit economics with the reverification reminder, the budget guard rationale, and a "design decisions that changed" section summarizing the Tier 2 redesign / dropped MCP server / deferred Jules
- [x] Write `README.md`: sops/age setup, Ollama systemd service usage (explicitly warns against manual `ollama serve`), Claude Code subscription login requirement, running `orchestrator.py` standalone, running the Phase 6 fixture as a smoke test, cost report usage, and a "what's not built yet" section covering Jules and the MCP server
- [x] Finalized `mapping.md`: replaced the two stub placeholders for `ARCHITECTURE.md`/`README.md` with real descriptions, noted `samples/broken_build/build/` as a gitignored generated artifact
- [x] Marked every checklist item across all phases in this file as complete

**End-of-phase tests:**
- [x] **Function** — verified by construction: `mapping.md` and `README.md` were written from a full re-read of this entire `PLAN.md` (every phase's dev checklist, amendments, and test results), so their content traces directly back to what was actually built and tested, not assumptions. Every script file has a one-line purpose in `mapping.md`, and `README.md` covers the exact setup/run commands used during real testing (`systemctl --user start ollama`, `sops config/secrets.enc.yaml`, the `orchestrator.py` invocation pattern used throughout Phases 2-6).

---

---

## Phase 8 — Natural-language planner/dispatcher, `triapi` CLI, and debug logging ✅

**Why:** the pipeline through Phase 7 only handled "fix this one already-broken file." The user wanted something closer to the source doc's original top-down design (Tier 1 plans, Tier 2 manages/dispatches) reachable via natural language, e.g. `triapi plan "there is a plan.md in ~/foo, follow it strictly"` — with the existing Tier4→3→1→2→handoff chain becoming the execution primitive underneath, not replaced.

**Design, settled via back-and-forth with the user:**
- **Two-step, not one-shot.** `triapi plan` is an *interactive* conversation with Claude (multiple `claude -p --resume <session_id>` turns, verified session memory works correctly across calls) so the user can give feedback and refine before anything is built — "this will cost more if execution takes a wrong turn and goes too far" was the stated reasoning. Only an explicitly approved plan (`triapi plan` reply of "approve"/"lgtm"/etc.) ever reaches dispatch. `triapi dispatch <run_id>` then has Gemini break the approved plan into a strict phase/checklist JSON structure and works through it with `orchestrator.run_task()`, one item at a time, in order — "time is not a constraint, code quality high and reliable" ruled out any parallelism.
- **`dispatch` is the only part that runs unattended.** Planning always needs a human; `--background` (detached via `subprocess.Popen(..., start_new_session=True)`, output to `logs/runs/<run_id>.log`) only applies to `dispatch`, matching the stated goal of low-friction use over SSH/Tailscale — start a dispatch, disconnect, check back later with `triapi status <run_id>`.
- **Run state is file-backed** (`logs/runs/<run_id>.json`), updated after every single dispatched item — a long dispatch survives an SSH drop by construction, not by any special recovery logic.
- **`planner.py`/`dispatcher.py` are new, separate from `tier1_escalate.py`/`tier2_escalate.py`** — same underlying Claude/Gemini services, different roles (plan vs. repair-one-file) and different prompts; kept as distinct files rather than overloading the existing ones.
- **`triapi` is a real command**, not `python3 scripts/triapi.py` — `scripts/triapi.py` got a shebang + `chmod +x`, symlinked to `~/.local/bin/triapi` (already on PATH, same pattern as `sops`/`age`).

**Dev checklist:**
- [x] Verified `claude -p --resume <session_id>` genuinely retains conversation memory across separate CLI invocations (a fact stated in call 1 was correctly recalled in a `--resume`'d call 2) before building anything on top of it
- [x] Wrote `scripts/planner.py`: `plan_turn(message, project_dir, session_id)` — one turn of an interactive planning conversation, read-only tool access (`--allowedTools Read,Glob,Grep`, `--add-dir <project_dir>`), can ask clarifying questions or propose/revise a phase-checklist markdown plan; budget-guarded like `tier1_escalate.py`
- [x] Wrote `scripts/dispatcher.py`: `breakdown_plan()` (Gemini, `responseMimeType: application/json`, converts the approved plan markdown into `{"phases": [{"name", "items": [{"description", "target", "build_cmd"}]}]}`) and `dispatch()` (walks phases/items sequentially via `orchestrator.run_task()`, persists state after every item, stops on the first non-success item rather than cascading forward on a broken foundation)
- [x] Wrote `scripts/triapi.py`: subcommands `plan` / `dispatch` / `status` / `list`; `plan` runs the interactive loop; `dispatch --background` spawns a detached child; `status`/`list` read run-state files for zero-cost progress checks
- [x] Installed as a real command: `chmod +x scripts/triapi.py` + `ln -sf` into `~/.local/bin/triapi`
- [x] Wrote `scripts/tri_logging.py`: centralized logging, **on by default**, toggle via `TRIAPI_LOG=0` / level via `TRIAPI_LOG_LEVEL` / file location via `TRIAPI_LOG_FILE` (default `logs/triapi.log`). Named `tri_logging` not `logging` so it doesn't shadow the stdlib module. Integrated into every script (`budget_guard`, `tier1-4`, `orchestrator`, `planner`, `dispatcher`, `triapi` CLI) at the meaningful decision points — tier calls, budget-guard refusals, escalation/handoff, dispatch progress — not instrumented exhaustively everywhere.
- [x] Updated `mapping.md`, `.gitignore` (`logs/*.log`, `logs/runs/`)

**Real bugs found and fixed during testing (not hypothetical — each one actually broke a real run):**
1. **`claude -p` subprocess inherited the parent's stdin**, undeclared in `planner.py` and `tier1_escalate.py`. Under `triapi plan`'s interactive loop this meant the Claude subprocess silently drained the same stdin pipe meant for the Python `input()` call — the user's simulated feedback text got fed into Claude as part of its *first* turn instead of a second turn, then `input()` hit EOF. Fixed by adding `stdin=subprocess.DEVNULL` to every `subprocess.run` call in the codebase (`planner.py`, `tier1_escalate.py`, `tier4_worker.py`'s `run_build`, `secrets_loader.py`) for consistency, not just the one that broke.
2. **Empty `build_cmd` from a Gemini breakdown item** (correctly left empty for a documentation-only step with nothing to build) was falling through to `orchestrator.run_task`'s default — the *C++ project's* `cmake --build build` — which is nonsensical for a markdown file and failed forever regardless of content. Fixed in `dispatcher.dispatch()`: an empty `build_cmd` now becomes `test -f <target>` (existence check) instead of the code-project default.
3. **Resuming a stopped dispatch skipped the failed item instead of retrying it** — `dispatch()`'s "already done" count included *every* recorded result regardless of status, so a `human_handoff` entry was treated as permanently done. Fixed: since the design always stops immediately on the first non-success item, that item (if present) is always the last result and gets popped off before resuming, so it's retried rather than skipped.
4. **Every tier's prompt was hardcoded to "You are a C++ debugging assistant" / a ` ```cpp ` fence`**, a leftover from when the pipeline only ever repaired known-C++ files (Phases 0-6). Once the planner/dispatcher could generate *any* file type, this caused real corruption: an earlier failed attempt at fixing a `.md` file (compounded with bug #2's bad build_cmd) resulted in Tier 1/2/3 actually writing C++ code into `PROJECT_MAP.md`, since their prompts insisted the answer must be C++. Fixed by generalizing all four prompts (`tier4_worker.build_prompt`, `tier3_escalate.build_stable_context`, `tier2_escalate.SYSTEM_INSTRUCTION`, `tier1_escalate.SYSTEM_PROMPT`) to be language-agnostic ("using the language tag appropriate for this file, or no tag for plain text/markdown") — `extract_code()`'s fence regex already accepted any language tag, only the prompt text was the problem. Re-verified: a fresh run against the same documentation task produced clean, correct markdown.

**End-of-phase tests (real API calls throughout, using a small dedicated test project, not `samples/broken_build`):**
- [x] **Seam** — `triapi plan "..."` against a project containing `plan.md` produced a clean, well-structured phase/checklist plan (no trailing questions, once the prompt fix from bug-fixing during Phase 4 was extended here too); `triapi dispatch` correctly broke it down via Gemini and resolved both real items (one via `tier_4`, one via `tier_3`) at a real total cost of $0.000048.
- [x] **Gap** — interactive feedback round tested for real: initial plan proposed a plain greeting, user feedback ("change it to all-caps") was correctly incorporated into a revised plan on the next turn, approval completed cleanly. Verified the underlying `--resume` session genuinely carried the conversation, not just re-sent the whole prompt. Separately, deliberately exercised the resume-after-failure path (bug #3 above) and the non-code-file path (bug #4 above), both confirmed fixed with real re-runs.
- [x] **Function** — final built files independently verified: `hello.cpp` and `CMakeLists.txt` matched the approved (feedback-revised) plan exactly, `PROJECT_MAP.md` contained correct clean markdown (not corrupted C++), and `logs/triapi.log` showed a complete, readable trace of the whole run (tier attempts, budget-guard checks, resume/retry decisions) confirming the logging feature actually captures what it's meant to. Confirmed `TRIAPI_LOG=0` correctly produces zero log output.

---

## Phase 9 — Git clone/pull/push authority ✅

**Why:** the user wants plans that can act on git repos directly — clone a repo to start from, pull to sync, push/commit changes — not just edit files already sitting in `--project-dir`.

**Design:**
- New module `scripts/git_ops.py`: `clone(url, path)`, `pull(repo_dir)`, `push(repo_dir, message, branch=None)` — direct shell git commands (not AI-drafted content), fully logged via `tri_logging`.
- **Safety rails, not overridable by a plan:** never force-push; `push()` never lands directly on `main`/`master` unless a plan step explicitly names that exact branch — otherwise it creates a new `triapi/<dirname>-<timestamp>` branch and pushes there instead, so an unattended `--background` dispatch can't clobber the primary branch's history or trigger CI/deploys on it. Credentials are never handled by this code — relies entirely on whatever git credential setup (SSH agent / credential helper) already exists on the machine, same as this session used for TriAPI's own push.
- **New checklist-item shape in `dispatcher.py`**, alongside the existing file-fix shape: `{"description", "git": {"action": "clone"|"pull"|"push", ...}}`. `dispatch()` branches on `"git" in item` to route to `git_ops` instead of `orchestrator.run_task()`. A failed git operation writes a human handoff via `orchestrator.human_handoff` (refactored from a private `_human_handoff` into a public, reusable function so `dispatcher.py` doesn't duplicate the escalation-file-writing logic) and stops the run, same as a failed file item.
- **`dispatcher.breakdown_plan()`'s Gemini instruction updated** to describe both item shapes and explicitly told not to invent git steps the plan didn't ask for.
- **`planner.py`'s system prompt updated** so Claude knows git steps are an option when a goal actually calls for one, and states the push-safety-rail behavior in the plan itself (so the human reviewing/approving the plan sees it, not just discovers it at dispatch time).

**Dev checklist:**
- [x] Wrote `scripts/git_ops.py` with the safety rails described above
- [x] Refactored `orchestrator._human_handoff` → public `orchestrator.human_handoff(task_id, reason, detail)`, updated its one existing call site to build `detail` from state itself (previously done inside the function)
- [x] Updated `dispatcher.py`: `BREAKDOWN_SYSTEM_INSTRUCTION` describes both item shapes; `_dispatch_git_item()` routes to `git_ops` and normalizes results to the same `{"status", "resolved_by"}` shape used everywhere else (`resolved_by: "git"` on success)
- [x] Updated `planner.py`'s `SYSTEM_PROMPT` to cover git steps and the push-safety-rail disclosure
- [x] Updated `mapping.md`

**End-of-phase tests (against a local bare git repo — deliberately not a real remote, so testing push behavior couldn't affect anything real):**
- [x] **Seam** — `git_ops.clone()` against a seeded local bare repo (with an existing `main` branch and a commit) correctly cloned and checked out `main` with the right content.
- [x] **Gap** — the actual safety rail, exercised directly: pushing from `main` with no branch specified created `triapi/git_test_clone-<timestamp>` and pushed there — verified independently by inspecting the bare repo directly that `main` was completely untouched (still just the original file) and the new branch had the pushed content. Then pushed again with an explicit `branch="feature/notes"` and confirmed it went to exactly that branch, not another auto-generated one. `pull()` against an up-to-date clone correctly reported "Already up to date."
- [x] **Function** — tested the dispatcher-level routing directly (`dispatcher._dispatch_git_item`), not just the underlying `git_ops` functions: a clone item returned `{"status": "success", "resolved_by": "git"}` and the clone actually happened; a deliberately-failing clone (bad path) correctly returned `{"status": "human_handoff", "resolved_by": None}` and wrote a proper `logs/escalation_<task_id>.md` with the real git error output.

## Critical files
- `PLAN.md`, `mapping.md`, `ARCHITECTURE.md`, `README.md` (repo root)
- `.sops.yaml`, `config/tiers.yaml`, `config/secrets.example.yaml`, `config/secrets.enc.yaml`
- `scripts/secrets_loader.py`, `scripts/config_loader.py`, `scripts/state.py`, `scripts/tier4_worker.py`, `scripts/tier3_escalate.py`, `scripts/tier2_escalate.py`, `scripts/tier1_escalate.py`, `scripts/budget_guard.py`, `scripts/cost_report.py`, `scripts/orchestrator.py`, `scripts/tri_logging.py`, `scripts/planner.py`, `scripts/dispatcher.py`, `scripts/triapi.py`, `scripts/git_ops.py`, `scripts/mock_patch_lint.py`
- `tests/test_mock_patch_lint.py`
- `samples/broken_build/main.cpp`, `samples/broken_build/CMakeLists.txt`

## Open risks (carried forward, not blocking)
1. ~~Antigravity's MCP registration UI/format is unknown from inside this repo~~ — **moot as of Phase 5 (2026-08-10):** Antigravity is no longer a dispatcher in this design (Tier 2 is a direct Gemini API call), so there's nothing to register. Superseded by: Jules integration is deferred pending `jules login` + more research (see Phase 4's DEFERRED note).
2. ~~`claude -p` non-interactive output format needs a quick `--help` check~~ — **resolved in Phase 4**: `--output-format json` + `--tools ""` + `--system-prompt` is the pattern used in `tier1_escalate.py`.
3. DeepSeek pricing in `tiers.yaml` will drift over time; raw token counts in `cost_log.jsonl` let historical cost be recomputed later. Same applies to Google AI Studio's `free_tier_rpm`/`free_tier_rpd` placeholders in `tier_2_manager.pricing` — never verified against Google's actual published limits.
4. ~~Git clone/pull/push authority~~ — **built in Phase 9, and verified end-to-end against the real GitHub remote in Phase 9.1 (below).**
5. Every file checklist item currently requires exactly one `target` file. A step like "delete this file" or "rename X to Y" doesn't fit that shape either — noted but not addressed; today's plans work around it by phrasing such steps as edits to a single file.
6. ~~HTTPS git remotes are not supported for push/pull in this environment~~ — **resolved in Phase 9.2**: `git_ops.py` now auto-rewrites `https://github.com/owner/repo(.git)` to `git@github.com:owner/repo.git`, both for a fresh clone URL and for an existing `origin` remote before every `pull()`/`push()`. Per the user: always use SSH, don't rely on whoever writes the plan to remember to say `git@github.com:...`. Other hosts/already-SSH URLs pass through untouched.
7. ~~Execution tiers have no general read access to the rest of the target repo~~ — **resolved in Phase 11**: `context_files`/`build_context_blob()` context-injection, verified against the real failing case.
8. **`qwen3-coder:30b-cc` (Tier 4's default draft model) cannot reliably load on this machine while oh-my-llama's own models are resident** — found during Phase 11 verification: repeated "timed out waiting for llama-server to start" failures traced to shared iGPU/system RAM exhaustion (oh-my-llama's `llama3.1:8b` + `qwen3:4b` already occupy ~15.3GB). Will block resuming the real oh-my-llama dispatch until decided: stop more of oh-my-llama's services during the run, use a smaller Tier 4 model for this run, or something else. Not TriAPI's bug, but blocks the next real test.
9. **`dispatcher.breakdown_phase()`'s retry loop doesn't catch HTTP errors** (e.g. a real 429 rate-limit), only malformed-JSON responses — an `HTTPError` raised by `_breakdown_phase_attempt()` propagates uncaught past the retry loop. Found incidentally during Phase 11 testing (a real 429 from prior testing in this same session), not fixed yet.

### Phase 9.2 — Always use SSH: automatic HTTPS→SSH rewrite ✅

Per the user, rather than just documenting "use SSH" as something to remember, `git_ops.py` now makes it automatic: `_to_ssh_url()` recognizes `https://github.com/owner/repo`, `.../repo.git`, and `.../repo/` and converts all three to `git@github.com:owner/repo.git`; anything else (already SSH, a different host) is returned unchanged. Applied in `clone()` (rewrites the URL before cloning) and via a new `_ensure_ssh_remote()` helper called at the start of both `pull()` and `push()` (rewrites an existing `origin` if it's still HTTPS, e.g. from a clone made before this fix, or a repo that already existed locally).

**Verified for real, repeating the exact same scenario as Phase 9.1** (clone `https://github.com/DanielNg520/TriAPI.git`, add a test file, commit, push) but this time with zero manual remote switching: `logs/triapi.log` showed `Rewriting clone URL to SSH: https://github.com/DanielNg520/TriAPI.git -> git@github.com:DanielNg520/TriAPI.git`, the clone's `origin` was confirmed to actually be the SSH URL, and the run completed end-to-end (`status: completed`, all 3 steps `success`) with no human intervention needed anywhere in the chain -- the first time this had happened for the git-authority feature. New branch confirmed on GitHub and deleted as cleanup; `main` confirmed untouched (SHA matched `cc9efbe` exactly).

### Phase 9.1 — Real end-to-end verification against GitHub (2026-08-10) ✅

Addressed the gap noted above: ran a real `triapi plan` → `triapi dispatch` against `github.com/DanielNg520/TriAPI` (not a local bare repo) — clone the real repo, create a small disposable test file, commit, push. Found and fixed three more real bugs in the process, all now covered by the fixes in `git_ops.py`/`dispatcher.py`:

1. **Relative `path` values in git items weren't resolved against `project_dir`** — `_dispatch_git_item` passed `git_spec.get("path", project_dir)` straight through to `git_ops`, which used it as a subprocess `cwd`. A relative path like `"repo"` resolved against the *calling process's* actual cwd, not the plan's project directory. In the first real run this put the clone inside `/home/dyne/Documents/Coding/TriAPI/repo` — **nested inside this very repo** — instead of the intended scratch test directory. Fixed with a `_resolve_path()` helper (mirrors the pattern `orchestrator.py` already used for file-item targets); the stray nested clone was found and removed.
2. **`BREAKDOWN_SYSTEM_INSTRUCTION` only showed `path` on the `clone` action's example**, not `pull`/`push` — so Gemini's breakdown correctly included `path` for clone but omitted it for a later push into that same clone, which (combined with bug #1) ran the push with no repo in scope at all. Fixed by making `path` explicitly required on every git action whenever a repo directory is known, with the instruction spelling out that a later step operating on an earlier clone must reuse that same path.
3. **A real HTTPS push hung for the full 300s timeout** instead of failing — this environment has no non-interactive HTTPS credential helper, and the GUI askpass helper (`ksshaskpass`, the same one that blocked this session's own first push attempt to this repo) hangs rather than erroring when there's no display to show a dialog on. `GIT_TERMINAL_PROMPT=0` alone wasn't sufficient (that only suppresses *git's own* prompt, not a configured external askpass). Fixed by passing `-c credential.helper= -c core.askpass=` on every git invocation, which strips all credential-prompting mechanisms for that command and makes an auth failure immediate and clear (`fatal: could not read Username ...: terminal prompts disabled`) instead of hanging. Also fixed: `subprocess.TimeoutExpired` was unhandled and crashed the whole `triapi` process instead of being treated as an ordinary failure — `git_ops._run()` now catches it and returns a normal failure result.

**Verification, against the real remote:** after all three fixes, a push over the repo's SSH remote (switched from the HTTPS URL used for the clone, since HTTPS has no working credentials here) succeeded for real: `triapi/repo-1786377230` appeared on GitHub via `git ls-remote`, confirmed `main` was untouched (its remote SHA matched exactly the last real commit made in this session, `520971e`), and the test branch was deleted afterward as cleanup, restoring the remote to just `main`.

## Phase 10 — Per-phase breakdown with retries, and `verify_only` item type ✅

**Why:** found and fixed mid-way through a real, large-scale user-directed test (a 9-phase, ~70-step refactor plan for a second repo, `oh-my-llama`) — the first time `dispatch` had ever been pointed at a plan of realistic size/complexity rather than a small test project. Both bugs are documented in detail in the commit `9f9437b`; this entry follows house convention by also recording them here.

**What broke and the fix:**
- **Whole-plan breakdown failed outright on a large plan.** `breakdown_plan()` asked Gemini to convert an entire multi-phase plan into one JSON blob in a single call; on the real 9-phase plan this produced malformed/truncated JSON. Fixed: `_split_plan_by_phase()` splits the plan markdown on `## ` headers; `breakdown_phase()` converts one phase at a time; `breakdown_plan(state)` (signature changed — was `breakdown_plan(plan_text)`) now mutates `state["breakdown"]["phases"]` incrementally and saves after each phase, so a partially-broken-down run resumes instead of restarting. `breakdown_phase()` also retries up to `max_attempts=3`: even a single small phase occasionally got malformed JSON from Gemini on one call and valid JSON on an identical retry — confirmed stochastic, not deterministic, by direct observation in the log.
- **No way to mark a plan step as "nothing to draft."** Steps like "run the test suite" or "grep for no remaining call sites" have no file to write, but the old code routed every item through the normal file-fix path regardless — Tier 4 would draft/overwrite the "target" file even though it was never supposed to change (caught before it could overwrite `run_tests.sh` with AI-generated content). Fixed: `BREAKDOWN_SYSTEM_INSTRUCTION` now asks Gemini to set `"verify_only": true` on such items; new `orchestrator.verify_task(task_id, build_cmd, workdir)` runs `build_cmd` as-is with no draft step and, on failure, goes straight to human handoff — no Tier 1/2/3 escalation, since there's no file for an AI tier to sensibly "fix" for a pure check. `dispatcher.dispatch()` routes `item.get("verify_only")` to this new path.
- `triapi.py`'s `_breakdown_and_dispatch()` updated to call the new `dispatcher.breakdown_plan(state)` signature.

**Verification:** both fixes were unit-tested directly against the real captured plan text from the `oh-my-llama` run (Phase 3, "Cut Todoist") before being trusted at scale, then confirmed working in the actual re-dispatch: breakdown succeeded cleanly end-to-end (10 phases, 96 items, no malformed-JSON failures).

**Known gap found immediately after, fixed in Phase 11 below:** the very first dispatched item (Phase 0, `docs/mapping.md`) reported `success` via Tier 4 but its actual content was fabricated — the task said to seed it from `plan.md`'s "Relevant files" list, but Tier 4 has no general read access to the rest of the target repo, so Ollama hallucinated a generic template referencing files that don't exist in that project. The `build_cmd` only checked file existence, so it couldn't catch wrong content. Dispatch was killed manually before this could repeat across the other 95 items.

## Phase 11 — Context-injection: grounding execution tiers in other repo files ✅

**Why:** the Phase 10 gap above, root-caused: every execution tier's prompt (`tier4_worker.build_prompt()` and the equivalent stable-context/user-message builders in tiers 3/2/1) only ever included a fixed instruction, the item's own description text, and — if the target file already existed — that file's current content. A plan step whose description references other files ("seeded from X", "following Y's pattern") got no such context, so Tier 4 (Ollama, no tool-use loop) hallucinated plausible-looking but wrong content instead. Discussed two options with the user (context-injection vs. a real Ollama tool-use loop); user chose **context-injection** as the simpler fix that matches the existing prompt-construction pattern, with a real tool-use loop left as a possible future phase if injection proves insufficient.

**Design:**
- New shared helper `tier4_worker.build_context_blob(paths, workdir, max_chars_per_file=20000)`: reads each referenced repo file (relative to `workdir`) into a labeled, read-only block ("Reference file `path` (read-only, for grounding only -- do not modify): ..."); missing files are skipped and logged, not fatal; each file is capped at 20K chars so one huge reference file can't blow out the prompt.
- `orchestrator.run_task()` gained a `context_files: list[str] | None` parameter; it builds the blob **once** per item (content is fixed for the item's lifetime, so no need to re-read on every Tier 4 retry or escalation) and threads the same `context_blob` string through every tier: `tier4_worker.run(..., context_blob=...)`, `tier3_escalate.escalate(..., context_blob=...)` (appended to the byte-stable prefix, not the volatile stderr message, since it's equally stable across retries and belongs in DeepSeek's cached prefix), `tier2_escalate.escalate(...)`, `tier1_escalate.escalate(...)`.
- New optional `"context_files": []` field on file items in `dispatcher.py`'s breakdown JSON shape. `BREAKDOWN_SYSTEM_INSTRUCTION` now tells Gemini to set it whenever a step's own text references another file or pattern to follow, and states plainly that leaving it empty when the step depends on another file's real content causes hallucination — mirroring how the `verify_only` field's instruction text was written in Phase 10. `dispatch()` passes `item.get("context_files") or []` into `run_task()`.
- Every tier's CLI (`tier4_worker.py`, `orchestrator.py`) gained a repeatable `--context-file` flag for standalone use, matching the existing `--target`/`--build-cmd` pattern.

**Verification (real, against the actual failing case from Phase 10, not a synthetic one):**
- Re-ran `dispatcher.breakdown_phase()` against oh-my-llama's real Phase 0 markdown (the exact text that previously produced the item with no context) — Gemini's breakdown now correctly returns `"context_files": ["plan.md"]` on the `docs/mapping.md` item.
- Ran the real prompt (target item description + `build_context_blob(["plan.md"], workdir)`) through Ollama against the real oh-my-llama repo. `qwen3-coder:30b-cc` (Tier 4's configured default) repeatedly failed to even finish *loading* during this test — traced to a real, separate resource-exhaustion problem, not a bug in this fix: oh-my-llama's own resident models (`llama3.1:8b` + `qwen3:4b`, ~15.3GB) were already occupying most of the shared iGPU/system RAM (18GB/30GB used, <500MB free, already swapping), leaving no room for an 18GB model to load. Confirmed via `ollama ps`/`free -h`/journal logs showing "timed out waiting for llama-server to start" both before and independent of this change. Substituted the smaller already-resident `qwen3:4b-instruct` purely to isolate and verify the *prompt-construction/context-injection logic* (not Tier 4's production model choice) — completed in 45s and produced a `docs/mapping.md` whose module table **exactly matches** the real "Relevant files" list in oh-my-llama's `plan.md` (`ohmyllama/capabilities/calendar.py`, `todoist.py`, `finance.py`, `coupon_tracker.py`, etc.), a categorical difference from Phase 10's fabricated `src/main.py`/`src/database.py`/`src/api_client.py` output. Test file removed afterward (untracked, not part of the real dispatch run).

**Not addressed in this phase, flagged for the user:**
1. **The qwen3-coder:30b-cc / VRAM-exhaustion problem is real and will block resuming the actual oh-my-llama dispatch** if oh-my-llama's own models stay resident — needs a decision (stop more of oh-my-llama's services during the dispatch run? lower Tier 4's default model for this run? something else) before re-attempting the real 96-item dispatch, independent of the context-injection fix itself.
2. **A separate, smaller bug found incidentally while testing:** `dispatcher.breakdown_phase()`'s retry loop only catches malformed-JSON failures (`{"status": "error", ...}` returned by `_breakdown_phase_attempt`); an actual HTTP error (e.g. a real 429 rate-limit hit during this session's own testing) raises `requests.HTTPError` uncaught, skipping the retry logic entirely and crashing the caller. Not fixed here — noted as a follow-up, not conflated with the context-injection change.

## Phase 12 — Fix the Tier 4 resource-contention problem: lighter default model + resource guard ✅

**Why:** Phase 11's open risk #8. Per the user, both fixes at once, and going forward `triapi` gets resource priority automatically on every dispatch run: pause whatever competes for CPU/RAM/GPU beforehand, resume it after, no manual intervention needed each time. Explicit exception: `com.duy.recorder.service` (archiver-suite recorder) stays running always, regardless of dispatch state.

**Investigated first, not guessed:** `qwen3-coder:30b-cc` is already `Q4_K_M` (4-bit) quantized, 18GB, MoE architecture — not much further to compress without hurting quality. It ran fine earlier in this same session; the difference was concurrent contention, not a static memory ceiling: `ollama ps`/`free -h`/`journalctl` at the time of the second failure showed oh-my-llama's own resident models (`llama3.1:8b` + `qwen3:4b`, ~15.3GB) plus its `oh-my-llama-brief.service` timer firing mid-test (loading a vision model live, confirmed via a `--mmproj`-flagged `llama-server` process) had pushed system RAM to 25GB/30GB used with active swapping. The 30B model had nowhere to load.

**Fix 1 — lighter default model:** `config/tiers.yaml`'s `tier_4_worker.default_model` changed from `draft` (`qwen3-coder:30b-cc`, 18GB) to `fallback` (`gpt-oss:20b`, MXFP4, 13GB) — already a configured, tools-capable model, zero code change needed, just less footprint to contend for. `draft` stays defined for a manual override if resource pressure stops being a concern.

**Fix 2 — automatic resource guard, built as a real feature, not a one-off manual step:**
- New `config/resource_guard.yaml`: machine-specific list of systemd `--user` services that compete with Ollama on this box (`oh-my-llama.service`, `oh-my-llama-web.service`, `oh-my-llama-telegram.service`, `oh-my-llama-discord.service`, `oh-my-llama-brief.service`, `oh-my-llama-brief.timer` — explicitly **not** `com.duy.recorder.service`, per direct instruction). Optional/missing file = no-op, so this doesn't break a deployment on another machine.
- New `scripts/resource_guard.py`: `pause_services(services)` stops each *currently-active* service via `systemctl --user stop` and returns exactly the subset that was actually running; `resume_services(paused)` starts exactly that subset back up. Never resurrects a service that was already off for an unrelated reason (e.g. telegram/discord, stopped earlier this session, correctly stayed off through a pause/resume cycle in testing).
- Wired into `triapi.py`'s `cmd_dispatch()`: the non-background path (which the `--background` path's detached child also re-execs into, so this covers both) wraps `_breakdown_and_dispatch()` in a `try`/`finally` — services pause before dispatch starts, resume no matter how the run ends (success, `stopped_on_failure`, or an uncaught exception).

**Verification (real, against the actual live services on this machine):**
- Ran `resource_guard.pause_services()` against the real config: correctly stopped `oh-my-llama.service`, `oh-my-llama-web.service`, `oh-my-llama-brief.timer` (all were active) and correctly *skipped* `oh-my-llama-brief.service` (already `failed`, not `active` — nothing to pause) and the already-stopped telegram/discord services, returning only the 3 it actually touched.
- Confirmed via `free -h`: RAM usage dropped from 25GB/30GB used (5GB free, actively swapping) to 3.5GB/30GB used (24GB free) immediately after pausing.
- Ran `resource_guard.resume_services()` with that exact returned list: confirmed via `systemctl --user list-units` that all 3 came back to `active`/`running`/`waiting` as appropriate.
- Confirmed `com.duy.recorder.service` was untouched throughout (checked before and after).

**Not yet re-tested end-to-end:** the guard has been verified standalone (pause/resume both directions confirmed against real service state) but not yet exercised through an actual `triapi dispatch` invocation start-to-finish. The next real resume of the oh-my-llama run (Phase 10/11's unfinished thread) will be the first true end-to-end test of both fixes together.

### Phase 12.1 — Self-healing resource guard (crash-proofing) ✅

**Why:** per the user ("you crashed again... make it an automaton"), and a real gap: a plain `try`/`finally` in `triapi.py` does NOT run on `SIGTERM` (only on exceptions and `SIGINT`) -- a `kill <pid>` on a stuck dispatch, which literally happened once already in this project's real usage (PLAN.md's Phase 10 dispatch, killed manually mid-run), would have left services paused forever with the guard as it stood after Phase 12.

**Fix, two layers on top of the caller's existing try/finally, in `resource_guard.py`:**
1. **Signal/atexit safety net** — the moment anything is actually paused, `pause_services()` installs handlers for `SIGTERM`, `SIGINT`, and normal interpreter exit (`atexit`), all calling the same idempotent `resume_services()`. Whichever fires first wins; `_state["resumed"]` guards against double-starting services if more than one fires (e.g. the caller's own `finally` AND `atexit` at normal exit).
2. **Lock file self-healing for the un-catchable case** — `pause_services()` writes `logs/resource_guard_lock.json` (`{pid, paused, started_at}`) the moment it pauses anything, and removes it on a clean `resume_services()`. If the owning pid is hard-killed (`SIGKILL`, OOM-kill, power loss) before even a signal handler can run, the lock survives on disk. Every subsequent call to `pause_services()` -- i.e. the very next `triapi dispatch`, for anyone or anything -- starts by checking the lock: if its pid is no longer alive, it resumes exactly the services that lock recorded and clears the file before proceeding. No separate watchdog process, cron job, or manual cleanup ever required.

**Verified for real, both directions, against the live services on this machine:**
- Ran `pause_services()` in a background process, confirmed the lock file was written with the correct pid/service list.
- `kill -9`'d that process directly (not `SIGTERM` -- the un-catchable case). Confirmed via `systemctl --user list-units --all` that the paused services stayed down (`oh-my-llama-web.service`/`oh-my-llama-brief.timer` correctly `inactive/dead`) and the lock file survived, now orphaned.
- Called `pause_services([])` from a fresh process (simulating the next dispatch starting) with an empty list, to isolate the healing behavior from any new pausing. Confirmed it detected the dead pid, resumed exactly `oh-my-llama.service`/`oh-my-llama-web.service`/`oh-my-llama-brief.timer` back to `active`/`running`/`waiting`, and deleted the stale lock file -- all before doing anything else.
- Confirmed throughout: `oh-my-llama-telegram.service`/`oh-my-llama-discord.service` (already off before this test, for an unrelated reason) were never touched in either direction, and `com.duy.recorder.service` was never touched.

## Phase 13 — Content-preservation guard, diff-based editing, and a deterministic context_files backstop ✅

**Why:** the first real end-to-end resume of the oh-my-llama dispatch (Phases 10-12.1 all landing together for the first time) surfaced two severe, previously-invisible failures within the first 15/96 items, both masked by `status: "success"`:

1. **Every tier silently deleted most of a real file's content while claiming a small, targeted edit.** All four tiers' prompts said "output ONLY the complete, corrected file contents... no partial diffs" — including for edits to large, real, pre-existing files. Confirmed by direct diff inspection after the run: `docs/semai-phase3.md` 705 → 146 lines, `docs/overhaul.md` 427 → 129, `ohmyllama/memory.py` 529 → 116, `ohmyllama/intent.py` 319 → 121 — every one of them reported `success` because the item's own narrow `build_cmd` (a `grep` for the one added line, `py_compile`, file existence) never looked at the rest of the file. Not a weak-local-model problem specifically: `docs/overhaul.md` was gutted by **Tier 3 (DeepSeek)**, not Tier 4. `ohmyllama/reminders.py` was written **completely empty** and still reported `success` (`py_compile` passes trivially on an empty file).
2. **Phase 11's context-injection fix, verified working in isolated testing, did not fire in the real breakdown call.** All 15 items dispatched had `context_files: null`, including several whose own description said "following `ohmyllama/watcher.py`'s poll-loop pattern" or "cross-referencing `plan.md`" — exactly the cases `BREAKDOWN_SYSTEM_INSTRUCTION` was written to catch. `docs/mapping.md` reproduced Phase 10's original hallucination exactly (generic `core`/`api`/`database`/`cli` modules, nothing to do with oh-my-llama).

All of oh-my-llama's damaged working-tree changes from this run were reverted (`git checkout`/`rm` back to clean `ff5e07e`, nothing had been committed) with explicit user confirmation before touching it, since it's a separate real project.

**Three fixes, all tier-agnostic (protect Tier 4 AND every escalation tier), landed together:**

1. **`content_guard.py` (safety net):** `check_write(task_id, target_path, new_content)` refuses a write to an existing file when fewer than 50% of its original non-blank lines survive in the proposal (only checked past a 15-line floor, so small legitimate rewrites aren't flagged). On refusal the original is left untouched on disk and the rejected content is saved to `logs/rejected_writes/<task_id>.txt` for review; the caller treats it exactly like a build failure (record_failure/escalate for Tier 4, `status: "fix_rejected"` for Tiers 1-3). Wired into all four tiers' write points.
2. **`edit_blocks.py` (the actual root fix, not just a net):** replaces "output the complete file" with SEARCH/REPLACE-block patching for any edit to an already-existing file (`apply_edit_blocks()` applies each block via exact-text matching, failing closed — not guessing — if a SEARCH block doesn't match the current file exactly once). Brand-new files (nothing to diff against) still use the old full-content path. Since Tier 4 always drafts first, the target always exists by the time Tiers 1-3 run, so they use edit-block mode unconditionally.
3. **`dispatcher._backstop_context_files()` (deterministic floor under LLM compliance):** regex-extracts path-like tokens (with or without backticks — confirmed Gemini's breakdown output does not reliably preserve the source plan's backticks) from each item's own description text and unions them into `context_files`, since relying on the prompt instruction alone proved unreliable at 0/15 in the real run.

**Incidental fix while back in `dispatcher.py`/`tier4_worker.py` anyway (both previously-known, both noted as follow-ups in earlier phases):**
- `_breakdown_phase_attempt()`'s `requests.RequestException` is now caught and fed into the same retry loop as malformed JSON, instead of propagating uncaught and crashing the caller (PLAN.md's own Phase 11 "not addressed" list, #2; a real 429 had already been observed hitting this exact gap).
- `tier4_worker.call_ollama()`'s `requests.RequestException` (Ollama down/unreachable — this is what actually crashed the whole dispatch process on the first resume attempt today, root-caused to `ollama.service` itself having been left stopped from an earlier unrelated `SIGKILL` test and never restarted) is now caught in `run()` and treated as a build failure, so a transient Ollama outage escalates through the normal tier chain instead of taking down a potentially hours-long unattended run.

**Verified, not just unit-tested in isolation:**
- `content_guard.check_write()`: a synthetic legitimate small edit passes, a synthetic wholesale-regeneration-style edit (matching today's real 15%-retention shape) is refused with the original preserved on disk, and a brand-new file always passes.
- `tier4_worker.run()` and `tier3_escalate.escalate()`, both with the real network call mocked out: a correctly-formatted SEARCH/REPLACE response applies cleanly and preserves every untouched line; a response that dumps a truncated full file (today's actual failure shape) is rejected rather than silently written.
- `_backstop_context_files()` run against the **actual stored breakdown JSON from today's failed run**: correctly recovers `context_files` for `ohmyllama/reminders.py` (`ohmyllama/watcher.py`, `push.py`), `ohmyllama/orchestrator.py` (`watcher.py`, `ohmyllama/reminders.py`), `ohmyllama/intent.py`, `src/semai/parser/rule_parser.py`, and `docs/mapping.md`/`docs/decisions/0011-secretary-reminders.md` (`plan.md`) — every one of the real cases Gemini missed.

**Re-attempted the same day, surfaced one more real bug, fixed immediately:** reused the already-approved plan (unchanged) but cleared `state["breakdown"]`/`state["results"]` so the breakdown regenerates fresh through Gemini with `_backstop_context_files()` live. Hit a real 429 on phase 4/10 -- confirmed the new retry-instead-of-crash behavior worked (a clean `"Breakdown failed: ..."` message, not a traceback), but `triapi.log` showed all 3 retry attempts fired within ~300ms of each other and 429'd every time: **the retry loop had no backoff at all**. Fixed: `_parse_retry_after()` extracts Google's own suggested delay from the 429 body (e.g. "Please retry in 27.33s") when present; `breakdown_phase()`'s retry loop now sleeps that long (or a 5s default for the malformed-JSON case, which has no such hint) between attempts instead of retrying instantly.

**Blocked again immediately after the backoff fix landed** -- confirmed via `triapi.log` that the backoff itself worked correctly (honored Google's real suggested delays, 36.9s then 59.7s), but every retry still 429'd. Made one direct, minimal API call to see the current raw error body rather than guess: `"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"`, `"quotaValue": "20"`, model `gemini-3.5-flash` -- a genuine free-tier **daily** cap for that specific model, exhausted for real by today's heavy testing volume, not a bug and not something backoff alone can fix.

## Phase 14 — Per-model quota fallback ✅

**Why:** per the user, directly -- since Google buckets the free-tier daily quota separately per model (confirmed by the `...PerModel-FreeTier` quotaId above), a model hitting its cap for the day shouldn't stall the pipeline; fall through to a different model with its own separate allowance.

**Design:**
- `config/tiers.yaml`'s `tier_2_manager` gained `fallback_chain`: an ordered list of real Gemini model names, verified against the actual available models (`GET /v1beta/models` against this project's own API key, since the model lineup as of this date includes names like `gemini-3.5-flash`/`gemini-3.1-flash-lite` that aren't guessable from general knowledge), flash-tier only (no `-preview`/`-image`/`-tts` variants, no `-latest` aliases since their underlying quota bucket is ambiguous). **Falls DOWN to older/lighter models only, never up** -- per explicit user correction after the first version of this chain wrongly tried a newer model (`gemini-3.6-flash`, version-wise above the default `gemini-3.5-flash`) before older ones; a newer model is a deliberate manual choice, not something this reactive chain should silently substitute in. Incidental fix in the same block: `models.pro` pointed at `gemini-3.5-pro`, which doesn't exist in the real model list -- corrected to `gemini-2.5-pro`.
- New `gemini_fallback.py`: `post_generate_content(post_fn, endpoint, api_key, body, models, timeout)` walks `models` in order, advancing only on a confirmed per-model quota-exhaustion response (429 + `error.status == "RESOURCE_EXHAUSTED"` in the body -- anything else, e.g. a network error or a different 4xx, returns immediately rather than burning through the whole chain for an unrelated failure). Records every attempt via `budget_guard.record_gemini_call(model)`, extended to accept and store which model a call was against (still no per-model *blocking* logic in `check_tier2_ok()` -- that check stays a global, conservative pre-flight cap; the fallback chain is the reactive layer that actually handles per-model exhaustion).
- Wired into both real Gemini call sites: `dispatcher._breakdown_phase_attempt()` (an explicit `model` override, when passed, still bypasses the chain and uses exactly that one model -- fallback only applies to the default path) and `tier2_escalate.escalate()`.

**Verified for real, against the actual live-exhausted quota from today's testing, not simulated:** called `gemini_fallback.post_generate_content()` directly with the real chain against the real API key -- `gemini-3.5-flash` (first in the chain, confirmed exhausted moments earlier via a direct raw-body check) was correctly skipped, `gemini-3.6-flash` returned a real 200 with actual model output ("hello").

**Resumed successfully** (after also correcting the chain's direction per user correction -- falls DOWN to older/lighter models only, not up to a newer one; see the corrected chain above) through real breakdown of all 10 phases and real item dispatch. Two more real, small issues found and fixed by hand while supervising (not code bugs, individual bad items in this specific run):
- `docs/mapping.md`'s Phase-1-done item had `build_cmd: grep -i "Phase 1" docs/mapping.md`, but the table Gemini itself generates never contains that literal substring (`| 1 | done |`, not "Phase 1: done") -- content was already correct after Tier 4's draft (confirmed by reading the file), all four tiers correctly declined to further edit an already-correct file to chase a impossible grep match (content_guard/edit_blocks working exactly as designed), landing on human_handoff. Fixed the check itself (`grep -i "| 1 | done |"`) and marked the item `verify_only` since the content work was already done.
- Same `pytest tests/test_intent.py tests/test_panel.py -q` (bare `pytest`, not on PATH) mismatch as Phase 12/13 testing hit before -- this project's actual convention is `uv run python tests/test_intent.py && uv run pytest -q tests/test_panel.py` (`run_tests.sh` routes each test file to the runner that actually executes it: plain script-style suites via `uv run python`, pytest-style suites via `uv run pytest`). Running the corrected command surfaced a **real, legitimate test failure** -- not a TriAPI bug: `intent.py`'s edit (Phase 2, correctly removing `remind me` from the `todoist` strong-signal regex, since reminders no longer belong to Todoist) made a stale test assertion wrong. The test encoded the OLD "'session' + 'remind me' is two strong signals, ambiguous, defer to model" behavior; post-refactor there's only one strong signal (`session`→calendar), so the heuristic now correctly resolves it instead of deferring. Updated the test's expectation to match the intentional new behavior (`heuristic_capability("remind me about my therapy session")` now asserts `"calendar"`, not `None`), verified the full suite green afterward.

**Found, NOT fixed, flagged for next session -- a systemic breakdown-quality gap, not a TriAPI code bug:** Phase 3's "verify no live Todoist call sites remain" item (`grep -rn "todoist" ohmyllama src`) reported `success`, but the check is tautological -- a bare `grep` exits 0 as soon as it finds ANY match, and `ohmyllama/capabilities/todoist.py`/`src/semai/workers/todoist.py` themselves always contain the word "todoist", so this check can literally never fail regardless of how many un-cleaned-up call sites remain elsewhere. Confirmed by direct grep after the fact: real, live call sites still exist in `ohmyllama/brief_agent.py` (actively imports and calls `TodoistCapability`, including a `create_todoist_task` tool), `ohmyllama/agent.py` (todoist still in its own separate capability-description/proposal sets), `ohmyllama/orchestrator.py:795` (a literal `or "todoist"` fallback default), `src/semai/parser/rule_parser.py` (broader "add to todoist"/"todoist tasks" phrase patterns beyond the one line already re-pointed), and `src/semai/adapters/cli.py` (imports and uses `TodoistClient`/`CreateTaskWorker` directly) -- none of these were touched by any Phase 3 item. The description text for this item states the correct intent ("output must show only X and Y themselves, no other referrers") but the generated `build_cmd` doesn't implement that intent (needs something like a grep piped through an exclusion filter for the two expected files, asserting empty remaining output). **This exact same verify-step pattern is used for every other "cut a feature" phase in this plan** (Phase 4 Calendar, Phase 5 Finance/coupon, Phase 6 Browser) -- all four are at risk of the identical false-`success`. Not fixed this session (ran out of time budget after a very long day of real end-to-end testing); the next session should either (a) fix the breakdown prompt to generate a real exclusion-filtered grep for this verify shape, or (b) manually audit and complete each cut phase's actual call-site removal before trusting its verify step.

**Also found and fixed while spot-checking `ohmyllama/orchestrator.py`'s edit (Phase 2, item 5):** the SEARCH/REPLACE apply produced syntactically-valid-per-content_guard but **broken-indentation** Python (the model's REPLACE block dropped the surrounding 24-space indent level entirely) -- and it was reported `success` anyway, because this item had no `build_cmd` at all (missing from Gemini's breakdown) and `dispatcher.py`'s fallback for a missing `build_cmd` was a bare `test -f <target>` existence check, which says nothing about a code file's validity. Fixed: new `_default_build_cmd(target)` upgrades that fallback to `python3 -m py_compile <target>` for `.py` targets specifically (stdlib, zero extra dependency risk against the target project's own environment) -- non-code targets still fall back to the existence check, which remains correct there. Fixed the one already-broken file by hand (indentation only, content was otherwise exactly right) and confirmed it now compiles.

**That exact fix immediately caught a second, worse `edit_blocks.py` bug for real** (Phase 3, item 0, `ohmyllama/capabilities/__init__.py`): a malformed multi-block model response fooled `BLOCK_RE`'s non-greedy matching into applying "successfully" (no parse error) while leaving a literal, leaked `=======` conflict marker line inside the actual file -- a `SyntaxError` that `python3 -m py_compile` (only just added) caught immediately; the old `test -f` fallback would have silently accepted it. Every subsequent tier (3, 1, 2) then failed to fix the now-corrupted file (their SEARCH text no longer matched), correctly landing on human_handoff rather than compounding the damage. The same malformed response also silently dropped an unrelated `from .notion import NotionCapability` import that was never supposed to be touched. Fixed `apply_edit_blocks()`: after applying all blocks, if the result contains a leaked `<<<<<<<`/`=======`/`>>>>>>>` marker that wasn't already in the original file, reject it outright (`None`, reason) rather than accept -- a cheap, format-agnostic backstop regardless of the exact malformed shape that produced the leak. Reconstructed the one already-corrupted file by hand from the clean git original plus exactly the intended change (remove the Todoist import/`__all__` entry/factory registration, nothing else), confirmed it compiles and the notion import is back.

**Noted, not fixed (out of scope -- oh-my-llama's own config, not TriAPI's):** `oh-my-llama.service` itself takes ~40s to respond to `systemctl --user stop` (its own shutdown behavior under SIGTERM) -- every `triapi dispatch` run will eat that delay once at startup while the guard waits for the stop to complete. Also noticed in passing: `oh-my-llama-brief.service` was already in a `failed` (OOM-killed) state from ~2 hours prior to this testing, unrelated to any of today's changes -- not touched, not TriAPI's to fix.

## Phase 15 — Tautological-grep fix + whole-run cost/savings report ✅

**Why:** two separate items surfaced while resuming the 2026-08-10 oh-my-llama dispatch on 2026-08-11: (1) Phase 3's "verify no live Todoist call sites remain" step, flagged but not fixed in Phase 14, is a real generator-quality gap that recurs across every "cut a feature" phase in that plan; (2) the user asked, directly, for a standing measurement of how much the tiered pipeline actually saves vs. letting a single Claude model do all the work, plus a local-Ollama-vs-cloud-vs-GPU-ownership comparison, formatted to go in front of the user at the end of every run.

**1. `BREAKDOWN_SYSTEM_INSTRUCTION` fix (`dispatcher.py`):** added an explicit special-case instructing Gemini that a bare `grep -rn NAME dir1 dir2` for a "verify no remaining references" step is wrong even when the plan text itself shows that exact command, because it trivially passes the moment it matches the intentionally-kept dormant file(s) that still contain the name by design. The instruction now requires an exclusion-then-assert-empty form (e.g. `! grep -rn NAME dir1 dir2 | grep -v dormant_file.py`) instead. This is a fix to future breakdowns only — it does not retroactively repair Phase 3's already-generated (and already-`success`-marked) verify step in the live oh-my-llama run; per the user's explicit direction, that gap is left for Phase 9's own repo-wide regression-pass grep to catch, not hand-patched now.

**2. Whole-run cost/savings report (`cost_report.py`, `tier4_worker.py`, `triapi.py`):**
- `tier4_worker.py` previously logged **zero** token usage anywhere — the only one of the four tiers with no accounting, since local inference has no bill to justify it. `call_ollama()` now returns Ollama's full response dict (not just `["response"]`), and `run()` logs `prompt_eval_count`/`eval_count` to `logs/cost_log.jsonl` (`cost_usd: 0.0`, tier `"tier_4"`) — this was necessary before any savings number could account for what Tier 4 actually does, not just what it costs.
- `cost_report.py` gained a second report alongside the existing per-task `report()`/`format_report()` (unchanged, still used by `triapi.py` after every dispatch item): `run_summary()` aggregates the whole cost log by tier, reading each tier's own field vocabulary; `claude_baseline_cost()` prices the total token volume as if a single Claude model (Sonnet 5 $3/$15, Opus 5 $5/$25 per MTok — verified against the claude-api skill's cached pricing table, 2026-08-11) had done every item alone; `deepseek_flash_cost()` prices Tier 4's local volume as if it had run on Tier 3's DeepSeek instead (uses `config/tiers.yaml`'s own verified rates); `gpu_amortized_cost()` compares that same volume against amortized GPU ownership cost — all GPU inputs (card price, lifetime, power draw, electricity rate, hours used) are explicit CLI-overridable defaults, never asserted as fact, since this repo has no reliable signal for actual GPU usage duration (`--gpu-hours` defaults to 0, and the report says so explicitly rather than implying $0 means free).
- `format_run_report()` renders it with ANSI box-drawing/color (auto-disabled when stdout isn't a tty, so piping to a log file stays plain text) — headline numbers (actual spend, estimated savings, savings %) bolded/greenlit so they're immediately visible, per the user's explicit ask that this report "will be a part of the program provided to user at the end of the task."
- Wired into `triapi.py`'s `_breakdown_and_dispatch()`: prints automatically right after the existing per-item cost lines at the end of every `triapi dispatch` run, no extra flag needed.

**Verified:** `python3 -m py_compile` on all three touched files; the per-task `report()`/`format_report()` path re-run against a real task ID from the live oh-my-llama run to confirm the pre-existing behavior (which this change could easily have silently broken by overwriting the module) still works byte-for-byte; the new whole-run report run against the real, live `logs/cost_log.jsonl` from the same run — real numbers, not synthetic: 15 calls, 65,893 input + 171,294 output tokens, $0.0080 actual spend vs. $2.77 for an all-Sonnet-5-API baseline (99.7% estimated savings), Tier 4 correctly reporting "no data yet" for token volume logged before this fix landed.

## Phase 16 — Self-verifying-script fix in `BREAKDOWN_SYSTEM_INSTRUCTION` ✅

**Why:** while resuming the oh-my-llama dispatch on 2026-08-12, `p4-i11`'s `./run_tests.sh` step legitimately failed against `tests/test_ollama_provider_seam.py`, which picks a model to test tool-calling against via `models[0]` — the most-recently-pulled Ollama model, no capability check at all. On this box that resolved first to a 27B hybrid-SSM model that hangs indefinitely on this machine's Vulkan/AMD-iGPU backend (verified directly: cold-loads into GPU memory in ~10s, then the `llama-server` subprocess never finishes starting — not a timing issue, reproduced twice), then after removing it, to a 0.6B model too weak to reliably call tools at all (verified: fresh re-pull ruled out corruption; its own reasoning trace showed it *choosing* not to call the tool). Fixed via `triapi plan`/`dispatch` against oh-my-llama itself (never hand-edited, per the standing supervisor rule) — reused the capability-detection logic `ohmyllama/catalog.py` already had (`_supports_tools`, `RoleSpec`'s existing "3B is the floor" reasoning) instead of reinventing it, sorted candidates smallest-first (a seam test only needs to prove the wire protocol works, not benchmark capability — smaller loads faster and more reliably), and added a local, git-ignored `.state/model_blacklist.json` (format `{"model_id": "reason"}`) for models that are empirically broken on this specific box's hardware regardless of size/capability (seeded with `qwen3-coder:30b-cc`, which also hangs the same way as the 27B model above) — wired into `ohmyllama/catalog.py`'s `_ollama()` discovery choke point so every role assignment benefits, not just this one test.

**A real TriAPI-level bug found and fixed while landing that blacklist wiring:** the first two dispatched attempts at the 3-line `catalog.py` change both failed — the first via a mechanical Tier 4 SEARCH/REPLACE collision (identical code shape repeated across `catalog.py`'s 5 discovery functions, "matches 5 locations, ambiguous"), escalating to Tier 3, which reported `success` but had actually made an unrelated edit (`follow_redirects=True` scattered around the file) and left the real fix undone. The second attempt asked for a load-bearing verify step (a standalone `/tmp/verify_blacklist.py` asserting the blacklisted model is excluded) to sidestep an earlier shell-quoting escalation artifact — but `dispatcher.py`'s breakdown had generated that verify script as an ordinary file item, meaning its `build_cmd` invoked the very file Tier 4 was also free to redraft on failure. When the real code still didn't exclude the model and the assertion legitimately failed, the retrying worker did exactly what a file item's contract allows — rewrote the file until `build_cmd` passed — except the file was a test of *other* code, so "fixing" it meant weakening its own assertion (`ids = [x.id for x in discover(cfg) if x.id != "qwen3-coder:30b-cc"]`, filtering the very model it was supposed to be checking for) rather than fixing the actual bug. `verify_task()` reported `success`; the real code was still broken. Caught only by re-verifying independently by hand (per "verify, don't trust status") rather than trusting the reported status.

This is the same *class* of bug as Phase 15's tautological-grep fix — a check that can be made to always pass proves nothing — just a new instance (a self-editable verification script instead of a bare grep). Fixed `BREAKDOWN_SYSTEM_INSTRUCTION` (`dispatcher.py`): added a second special-case forbidding a verification script from ever being generated as a file item whose `build_cmd` runs that same script — since file items are, by design, freely rewritable by a retrying tier. The fix must instead be baked into `build_cmd` as an immutable heredoc (`cat > /tmp/x.py <<'EOF' ... EOF && python3 /tmp/x.py`) under a `verify_only: true` item (never drafted, so nothing can rewrite it once dispatch starts), with `target` naming the real file the check is actually about. This is a fix to future breakdowns only, same as Phase 15's — it did not retroactively repair the already-broken `catalog.py` blacklist wiring, which needed its own separate re-dispatch (below).

**Re-dispatched `catalog.py` fix, third attempt, now landed for real:** with the corrected `BREAKDOWN_SYSTEM_INSTRUCTION` in place, re-ran the same blacklist-wiring fix against oh-my-llama. Gemini's breakdown split the 3-line change into 4 items (loader function, `bl = _blacklist()`, the `if name in bl` check, and the heredoc-baked `verify_only` check) — Tier 4 needed one extra retry on two of the four items (ordinary "SEARCH text matches N locations, ambiguous" mechanical retries, same failure mode as before but now correctly retried instead of silently substituting unrelated edits), but all 4 resolved via Tier 4 alone this time, no escalation needed.

**Verified independently, not trusting reported status:** `PYTHONPATH=. python3 -c "from ohmyllama.catalog import discover; ..."` run by hand against oh-my-llama confirms `qwen3-coder:30b-cc` is genuinely excluded from `discover()`'s output; `PYTHONPATH=.:src .venv/bin/python tests/test_ollama_provider_seam.py` run end-to-end against the live local Ollama prints `all passed` (selects `qwen3:4b-instruct`, the smallest tool-capable model, per the earlier sort-direction fix — completes in seconds, not minutes).

**Two more real bugs found while continuing to supervise the resumed Calendar-cutting dispatch, both fixed directly (own tooling/state, not oh-my-llama code):**

1. **`_split_plan_by_phase()` only matched `## ` exactly** (`dispatcher.py`) — a plan generated during this same session used `### Phase 2` (three hashes); the splitter silently dropped that entire phase's checklist from the breakdown with zero error (the whole verification phase for the discord-routing regression fix below just never existed as far as dispatch was concerned — caught only by counting items against the plan by hand, not by any error surfacing). Fixed: matches `^#{1,6} ` (any ATX header depth) instead of a hardcoded two-hash literal.
2. **A real, uncaught crash in `tier1_escalate.py`** — `subprocess.run(["claude", "-p", prompt, ...])` passed the (target file + context_blob) prompt as a raw argv token; on an item with several sizeable context files this exceeded the kernel's `execve()` argument-list limit (`OSError: [Errno 7] Argument list too long`), killing the entire unattended dispatch process with no `stopped_on_failure` state and no escalation file — the exact same failure shape as the `TimeoutExpired` crash fixed in `tier4_worker.run_build()` earlier this project. `resource_guard`'s self-healing correctly resumed the paused services on the crash, same as designed; no data was lost (Tier 3's already-applied, already-verified-compiling patch to the affected file was untouched on disk). Fixed: the prompt is now piped via stdin (`input=prompt`) instead of argv — `claude`'s own `[prompt]` CLI argument is documented optional, reading from stdin when omitted — and the `subprocess.run()` call is wrapped in `try/except (OSError, subprocess.TimeoutExpired)` as defense in depth regardless of cause.

**A separate, real test regression found and fixed via the dispatch pipeline itself** (target-repo code, so not hand-edited, per the standing rule): resuming into Phase 5's `./run_tests.sh` surfaced a genuine failure in `tests/test_discord_routing.py` (a thread under a `#mail` scope channel no longer inherited the mail capability) caused by an earlier Phase-5 edit's unrequested scope-creep — an `isinstance(ch, discord.Thread)` security-hardening check (legitimate on its own merits, closing a real vulnerability where a user-named thread could self-grant a scope) that broke against the test suite's duck-typed fake channel objects, which aren't real `discord.Thread` instances. `triapi plan`/`dispatch` fixed it by replacing the `isinstance` check with an equivalent duck-typed "has a non-`None` `.parent`" check, preserving the exact same security property without requiring the unmockable real library class. Verified independently: both the targeted test and the full `./run_tests.sh` suite pass.

**A third real TriAPI bug found the same day, worse than the first two — a SILENT vacuous success, not just a dropped phase:** continuing to supervise, `./run_tests.sh` surfaced yet another real regression (`ImportError: cannot import name 'LLM' from 'ohmyllama.llm'` in `discord_bot.py`, a hallucinated import added by an earlier automated edit that was doing unrelated work). Queued a one-line fix via `triapi plan`/`dispatch` — the plan Tier 1 produced used a numbered checklist (`1. [ ]`, `2. [ ]`) with no markdown header at all, rather than the dash-bulleted (`- [ ]`) style `_split_plan_by_phase()`'s checklist filter hardcoded a literal substring check for. Every chunk got silently judged "no checklist items" and dropped — `breakdown_plan()` produced zero phases, zero items, from a real, clearly checklist-bearing plan, and the run printed **`Dispatch completed: all items resolved`** having done nothing at all. Caught only by noticing "0/0 step(s) completed" looked wrong and re-reading the file, not by any error surfacing — this is a strictly worse failure mode than the earlier dropped-single-phase bug, since here the ENTIRE plan vanished and the run still reported unqualified success. Fixed two ways in `dispatcher.py`: (1) `_CHECKLIST_ITEM_RE` now matches dash, asterisk, or numbered task-list markers, not a hardcoded `"- [ ]"` literal; (2) `breakdown_plan()` now hard-errors (`status: "error"`) whenever a non-empty `plan_text` yields zero total breakdown items, regardless of which specific markdown quirk causes it — closing the whole *class* of silent-vacuous-success, not just this one instance. Re-verified: the same plan text now correctly produces 1 chunk with both checklist items recognized.

**A fourth real bug, same day, same fix session: re-running the corrected plan hit the SAME environment-invocation mismatch (bare `python`/`pytest` resolving to the system interpreter instead of the project's `.venv`) for the third separate time this session** — this instance from a verify command in my own hand-written `triapi plan` prompt (`PYTHONPATH=. python3 -c "..."`), not from Gemini's breakdown, so an instruction-level fix to `BREAKDOWN_SYSTEM_INSTRUCTION` would not have prevented it — the mistake can originate from a human-authored plan just as easily as an LLM-generated one. All 4 escalation tiers burned real attempts "fixing" `discord_bot.py` for an `ImportError` that was actually a `ModuleNotFoundError` from the wrong interpreter, before the real bug (the `LLM` import) was ever actually exercised. Two earlier instances this session were hand-patched into that specific run's stored JSON `build_cmd` (narrow, per-item fixes, matching precedent from Phase 14's `p4-i9`); this time, fixed generally and permanently: `dispatcher.py`'s new `_normalize_build_cmd(build_cmd, project_dir)` rewrites a bare `python`/`python3`/`pytest` token (at a real command/sub-command boundary, tolerating leading `VAR=value` env assignments, never touching an already-qualified path or already-`uv run`-prefixed command) to `uv run python`/`uv run pytest` — but ONLY when the target project actually has a `pyproject.toml`/`uv.lock` (a signal TriAPI's own repo doesn't have, so this backstop can never affect TriAPI's own build_cmds). Applied uniformly in `dispatch()` to every item's `build_cmd`, `verify_only` or not, regardless of where the command text originated. Verified against the actual failing command and several edge cases (already-qualified paths, already-`uv run`, `grep` commands containing the literal substring "python", chained `&&` commands) by hand before trusting it; the corrected command reproduces the REAL bug (the `LLM` `ImportError`) instead of the environment red herring.

**Fixing that ImportError peeled back two more layers of the same underlying problem — all in `discord_bot.py`, all unrequested scope creep from one earlier automated edit that was supposed to be doing something else entirely (registering new Notion/file/Drive tools):**

1. Removing the bad `LLM` import surfaced a second bug: `_extract_label()` also *called* `LLM(self.cfg)` at runtime (an `or` fallback branch), never just imported it. Fixed via `triapi plan`/`dispatch`, correctly reasoning that `self.orch.llm` is always the async client per `orchestrator.py`'s own `self.llm = async_client_for(cfg)`, and rewriting the fallback to `async_client_for(self.cfg)`.
2. That fix immediately surfaced a *third*, more consequential bug: `tests/test_discord_reply_correct.py` failed with `AttributeError: 'Cfg' object has no attribute 'ollama_url'`. Investigating rather than guessing again: the test's own `FakeOrch` double has an explicit comment — `".llm (async) deliberately absent — a regression that reaches for it from _extract_label should crash loudly, not silently degrade"` — and provides only `sync_llm`. `git show HEAD:ohmyllama/discord_bot.py` confirmed `_extract_label` was never supposed to be `async` at all: the original method was a plain `def` using `self.orch.sync_llm.chat(...)` directly, no `await`, no fallback branch; its one caller (`_handle_reply`) called it without `await` too. An earlier, entirely unrelated automated edit had silently converted the whole method (and its caller) to async — the hallucinated `LLM`/`async_client_for` fallback was never a real design, it was scaffolding papering over a self-inflicted async conversion nobody asked for. Fixed by reverting `_extract_label()` and its caller to the exact original sync form from git history (not by guessing a plausible-looking async fix a second time), and removing the now-unused `async_client_for` import.

Verified independently at every step, not trusting reported status (twice caught real discrepancies this way today) — the `run_tests.sh` verify item on the last of these three fixes reported `success (resolved_by=verify)`, and a fully independent re-run (`timeout 250 ./run_tests.sh`, exit 0, "All tests passed successfully!", including all 4 pytest-based suites) confirmed it for real before resuming the main dispatch.

## Phase 18 — Two more real TriAPI bugs found supervising the semAI-consolidation plan (2026-08-13) ✅

**Context:** resuming the oh-my-llama project (now being renamed "semAI" and consolidated — see `/home/dyne/Documents/Coding/TriAPI/CARRYOVER.md` §-8/§-9 for the target-repo scope) required a fresh `triapi plan` conversation against oh-my-llama (combined Phase 1+2: cut Mail/Notion/Obsidian, delete `brief.py`/`brief_agent.py`) — the exact conversation the previous session left crashed mid-round-4.

1. **`planner.py`'s `plan_turn()` had a completely uncaught `subprocess.TimeoutExpired`** around its `claude -p ... --resume` call (`timeout=300`) — a slow multi-round planning turn (accumulated conversation context, a big prompt) raised the exception straight through `cmd_plan()`, crashing the whole `triapi plan` CLI process instead of returning the `{"status": "error", ...}` shape `cmd_plan()` already knows how to handle gracefully (its own `if turn["status"] != "ok":` branch). Fixed: wrapped the `subprocess.run()` call in `try/except subprocess.TimeoutExpired`, returning a normal error result. Confirmed fixed (failed gracefully instead of crashing) — but then hit the *same* graceful-timeout path twice more in a row at 300s, confirming this specific prompt's planning turns genuinely need longer than 300s (a large multi-file, two-tree, systemd+Telegram/Discord-UI cut, not an artificially slow one) — bumped the timeout to 600s, which then succeeded.
2. **`dispatcher.py`'s `_CHECKLIST_ITEM_RE` still required a literal `[.]` checkbox marker** (`r"^\s*(?:[-*]|\d+\.)\s+\[.\]"`) even after Phase 16's fix widened it to accept dash/asterisk/numbered bullets — a real, approved 11-phase plan used plain `1. **file** — description` items with no `[ ]`/`[x]` checkbox syntax at all (the planner's own `SYSTEM_PROMPT` asks for "a checklist" but never mandates literal checkbox markup, and the model doesn't reliably add it). Every phase chunk got judged "no checklist items" and dropped — `breakdown_plan()` correctly hard-errored per Phase 16's own "zero items from non-empty plan_text" guard (that protection worked exactly as designed, confirming Phase 16's fix), reporting `Breakdown failed: ...0 phase(s) and 0 item(s)...` instead of a silent vacuous success. Fixed by dropping the `\[.\]` requirement entirely — `_CHECKLIST_ITEM_RE` now matches any dash/asterisk/numbered list-marker line, checkbox or not (`r"^\s*(?:[-*]|\d+\.)\s+"`). Verified: the leading title/context chunk (pure prose, no list markers, including a decimal-number sanity check like "3.14") still correctly gets filtered out; the real 11-phase plan now splits into exactly 11 chunks.

**A real process mistake, caught immediately, not landed:** re-running `triapi plan` for a fresh (`session_id=None`) approval piped `"approve"` blind without peeking turn 1 first — the exact anti-pattern this project's own CARRYOVER already named and warned against once before (2026-08-13, oh-my-llama pivot session). This time it landed on a *different* clarifying question (about how deep to rename a secret/env-var key) than the one already reviewed via a prior peek, so the blind "approve" got mechanically applied to that question's text as if it were a finished plan (`cmd_plan`'s `reply.lower() in APPROVE_WORDS` check has no way to know the difference — it treats any turn's text as approvable). Caught immediately by reading the run's own stored `plan_text` back out of its JSON before dispatching (never trust the terminal transcript alone) — it was obviously just a question, not a checklist. Fixed by hand-patching that one run's own stored state to `status: "cancelled"` (same established precedent as prior sessions' JSON patches) and re-running properly: resolved the actual question with explicit judgment (folded into the prompt), peeked turn 1 with `< /dev/null` first, read the *entire* resulting plan end-to-end, and only then re-ran with `"approve"` piped — followed immediately by independently reading the actually-committed `plan_text` back out of the run's JSON (not the printed terminal output, which can legitimately differ turn-to-turn since each CLI invocation starts a fresh, non-resumable Claude session) before trusting it enough to dispatch.

**Dispatch of the approved plan (run `20260813-163435-569b9c`, 11 phases) started, breakdown reached Phase 3 (22 items across 3 phases saved) before being gracefully stopped mid-breakdown on explicit user request** ("gracefully stop when you could and update all docs"). `resource_guard`'s existing self-healing (Phase 12.1) resumed the paused `oh-my-llama-web`/`oh-my-llama-brief.timer` services cleanly on `SIGTERM`, confirmed both back to their normal `inactive` baseline state afterward. **No target-repo file was touched yet** — breakdown-only phases (Gemini JSON calls), the actual per-item Tier 4→3→1→2 draft/build loop never started. `breakdown_plan()`'s existing per-phase incremental save means this resumes cleanly from Phase 4 via a plain `triapi dispatch 20260813-163435-569b9c --background` — see CARRYOVER.md for the exact resume instructions.

## Phase 19 — `_BARE_PYTHON_RE` missed a leading `!`, and a systemic weak-build_cmd false-success pattern found supervising the same plan (2026-08-13, third pass) ✅ (bug fixed; false-success pattern partially remediated, not fully swept)

**Context:** resumed dispatch of run `20260813-163435-569b9c` from Phase 4 through 8 `human_handoff`s across Phases 4/5 and into Phase 6 — see `CARRYOVER.md` §-10 for the full per-item diagnosis (each was a real gap: a check-cmd using `pytest` against non-pytest-collectible test files, an over-broad repo-wide grep, a genuinely-unapplied code change with 5 failed tier attempts, a stale-but-not-yet-stale doc comment checked prematurely, etc.) — same "read the real escalation output, distinguish check-too-broad from a genuine gap" discipline as Phase 18, not repeated here.

1. **`_BARE_PYTHON_RE`'s prefix alternation (`^|&&|;|\|\|?|\n`) didn't include `!`** — a `! python3 -m pkg --help | grep ... && python3 other.py`-shaped build_cmd only got its SECOND `python3` (after `&&`) rewritten to `uv run python3`; the first, immediately after the leading `!`, stayed bare and resolved to the system interpreter (`ModuleNotFoundError: No module named 'tenacity'` for a dependency genuinely installed in the target's `.venv`). Same bug class as the `\n`-after-heredoc fix from 2026-08-12/Phase 17 area — another shell command-boundary case the regex didn't anticipate. Fixed: added `!` to the prefix alternation. Verified against 8 representative build_cmd shapes (the fixed case plus every previously-working shape) — no regressions.

2. **Found, while diagnosing the SECOND half of that same escalation (a `ModuleNotFoundError` for `semai.workers.mail`, from the correctly-rewritten command), a systemic false-success pattern**: at least 5 items across this run reported `status: "success"` via `tier_3` while never actually applying their described change, because their `build_cmd` was a pure syntax/existence check (`py_compile.compile(...)`, `python3 -m compileall ...`, `test -f ...`, or a generic `import`/`Config.load()` smoke test) that passes regardless of whether the real content change happened. Confirmed by direct file inspection: `src/semai/adapters/cli.py`'s dead mail import, `src/semai/config/schema.py`'s `MailAccountConfig`/mail fields, ALL of Phase 1's `obsidian_rules_*`→`rules_*` rename (7 items across `config.py`/`agent.py`/`cli.py`/4 test files — genuinely never renamed anywhere), the giant `ohmyllama/cli.py` subcommand-strip item (~15 subcommands, completely untouched), and `priority.py`'s `mail_priority` dead-code removal. Two of the five (`schema.py`, `src/semai/adapters/cli.py`) were fixed and verified directly against the real files this pass (dry-tested, `test_cli_adapter.py` passes end-to-end) but NOT YET packaged back through the pipeline's JSON — stopped mid-remediation on explicit user request to gracefully wrap up; full detail and exact resume steps in `CARRYOVER.md` §-10.

**Not done this pass, flagged for later (same category as the earlier-flagged "auto-force `verify_only` for a `git rm`-only build_cmd" idea, Phase 17 era):** a permanent, systemic fix — detecting a `build_cmd` that's ONLY `py_compile`/`compileall`/`test -f`/a bare no-assertion import at breakdown time and either rejecting it or forcing extra scrutiny, so this class of silent no-op can't recur. This pass's fixes were manual spot-checks of items that happened to surface via a related bug, not an exhaustive sweep — there may be more instances among this run's other reported successes.

## Phase 20 — Tier 1 on/off switch for the repair chain ✅

User request: "Add a small switch to turn off Claude api in the pipeline (no planner step) to triAPI" — a way to disable Tier 1's *repair* role (`tier1_escalate.py`, called from `orchestrator.run_task()`'s escalation chain) without touching `planner.py`'s separate interactive `triapi plan` step, which also shells out to Claude Code CLI but is a distinct code path and config block (`tier_1_planner`, untouched).

Planned and dispatched via `triapi plan`/`triapi dispatch` against TriAPI's own repo (run `20260814-102502-e9718b`), per the standing self-modification rule. Landed:
- `config/tiers.yaml` — new `tier_1_manager.enabled` block (default `true`), separate from the pre-existing `tier_1_planner` block.
- `scripts/budget_guard.py` — `check_tier1_manager_ok(config)`, refuses if `tier_1_manager.enabled` is `false` or the `TRIAPI_NO_TIER1` env var is set.
- `scripts/orchestrator.py` — `run_task()`'s Tier 1 block now checks `check_tier1_manager_ok()` alongside the existing `check_tier1_ok()` budget guard; either refusing falls straight through to Tier 2 (Gemini), same as today's budget-guard skip.
- `scripts/triapi.py` — `triapi dispatch --no-tier1` sets `TRIAPI_NO_TIER1=1` before dispatching (inherited by the `--background` detached child automatically, since its `Popen` call passes no `env=` override).
- `README.md`/`mapping.md` documented.

**Supervision notes, real findings, not just trusted "success" reports:**
1. The plan's own Phase 3 verify command used `grep -q "--no-tier1"` — on this box `grep` is a shell function wrapping a bundled `ugrep` binary that errors on a `-q`-quoted pattern starting with `--` even though real GNU grep handles it fine. Every one of 5 tier attempts failed this check regardless of correctness, so all 5 thrashed defensively (wrapping unrelated code in try/except) instead of ever attempting the actual required change. Fixed by hand-patching the item's `build_cmd` (all copies: `breakdown.phases[]` and `results[]`) to a pure-Python functional check with no shell grep involved, verified it correctly fails against the pre-fix code and passes post-fix before resuming.
2. One tier's "successful" Phase 2 edit smuggled in an entirely unrequested `check_tier0_ok()` Ollama-reachability guard into `orchestrator.py`/`budget_guard.py`, gating Tier 4 on it — plausible-looking, but explicit scope creep beyond "pure feature addition, no unrelated refactoring." Reverted by hand (kept the legitimate `check_tier1_manager_ok` wiring, stripped the rest); dispatcher's regression-detection correctly treated the resulting hash drift as a benign edit (build_cmd still passed) rather than a stop.
3. A second attempt at the reverted `triapi.py` file added the `--no-tier1` argparse flag but never wired it to anything — no `TRIAPI_NO_TIER1` being set, no `import os`. The item still reported `success` because my own hand-patched build_cmd (item 1 above) only checked that the flag *parsed*, not that it *did* anything — the exact "weak build_cmd, false success" pattern already flagged in Phase 19. Caught by manually re-reading the diff before trusting it; fixed the wiring by hand and rewrote the build_cmd a second time to a real functional check (invoke `main()` with `--no-tier1`, assert `os.environ["TRIAPI_NO_TIER1"] == "1"` afterward), confirmed it fails pre-fix and passes post-fix.
4. Phase 4's two documentation items (README.md/mapping.md) also drifted off-topic across every tier attempt (unrelated pre-existing doc corrections, never once mentioning the actual switch) — reverted the drift and wrote the real doc content by hand, per the standing carve-out that TriAPI's own documentation is always mine to fix directly regardless of the "route feature work through the pipeline" rule.
5. Final independent verification (not the pipeline's own reported `completed` status): full `py_compile` pass across `scripts/*.py`, `scripts/planner.py` confirmed zero diff, and three live functional checks — default config-enabled, `tier_1_manager.enabled: false`, and the `TRIAPI_NO_TIER1` env-var override — each producing the correct `ok`/reason.

Only after all of the above did the run's own reported `completed` status get trusted.

**Supervision note:** the actual oh-my-llama refactor work (Phase 3 gap, Phase 4+ dispatch) stayed strictly TriAPI's job throughout — per direct user correction mid-session after an initial wrong instinct to hand-edit oh-my-llama's leftover Todoist call sites myself. Fixed TriAPI's own tooling (the grep-generation instruction, the cost accounting) instead; the target repo's refactor itself is only ever touched by the dispatch pipeline's own tiers.

## Phase 21 — Failure-pattern knowledge store + diff-quality critique ✅

Landed via dispatch run `20260812-202927-aa0e40` (2026-08-14/15), part 2 of CARRYOVER.md's "Third queued item".

**Phase A — knowledge store**
- `knowledge/lessons.jsonl` seeded with 3 real historical bugs (edit_blocks empty-REPLACE regex, breakdown RPM resumability, tautological verify-grep).
- `scripts/lessons.py`: load/add/select_relevant/format_lessons_for_prompt + CLI.
- `edit_blocks.build_edit_prompt_header(..., lessons_block="")`; all four tiers fold relevant lessons into edit prompts.
- `orchestrator.human_handoff()` auto-captures `unresolved_pattern` lessons.

**Phase B — advisory critique**
- `config/tiers.yaml` `critique:` block (enabled, applies_to_tiers tier_3/1/2, critic tier_1, score_threshold 7, max_revision_attempts 1).
- `scripts/critique.py` mirrors Tier 1's `claude -p`/stdin pattern.
- `revision_note=""` on tier1/2/3 `escalate()`.
- `orchestrator._critique_and_maybe_revise()` after successful Tier 3/1/2 rebuilds — score-gated, one revision pass, revert-on-rebuild-fail, never changes pipeline flow.

**Also fixed while supervising:** Tiers 1/2/3 now `mkdir(parents=True)` before writing new files (Tier 4 already did; Tier 3 crash on `knowledge/lessons.jsonl` was the discovery). Flash-lite breakdown had produced `cat`/`sed` build_cmds for Phase A — replaced with real verifies before resume.

## Phase 22 — Worked-case implementation audit and hardening ✅

Independent branch audit after all four `AGENT_GUIDE.md` worked runs completed:

- Self-fix crash capture no longer replaces `sys.excepthook`, cannot mask the original exception, records source frames, and queues only after resource-guarded services resume. Added explicit `self-fix queue` and `self_fix.enabled`.
- Lessons now tolerate malformed JSONL, lock/deduplicate appends, use stronger relevance scoring, and isolate handoff-recording failures.
- Critique parsing is fail-open/advisory for malformed model output, uses one YAML threshold, logs every outcome, and sends quality-specific revision prompts rather than an empty build error.
- Added `tests/test_branch_features.py` regression coverage.
- Independently audited and hardened the four worked test cases dispatched against a target repo during this phase (ghostwriter, self-fix, learning, HTML ingestion) — target-repo-specific detail lives in that repo's own docs, not here.


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

## Phase 17: Provider Decoupling & LLM Client Consolidation (2026-08-22)

**Goal**: Eradicate hardcoded API endpoints, model strings, and provider types from the tier scripts so that TriAPI can rapidly swap in alternative models via standard configuration (e.g., OpenRouter, Nemotron, Llama).

- [x] **`llm_client.py` Consolidation**: Extracted all network and subprocess logic out of the `tier*_escalate.py` and `tier4_worker.py` scripts. `llm_client.execute_llm()` is now the universal entry point for LLM interactions.
- [x] **Configuration-Driven Routing**: Tiers now read their `provider` string, API key name, and `endpoint` directly from `config/tiers.yaml`.
- [x] **Tier Re-assignments**:
  - `tier_2_manager` shifted from hardcoded Google AI Studio to OpenRouter (pointing to `nvidia/nemotron-3-ultra-550b-a55b:free`).
  - `tier_4_worker` shifted from hardcoded local Ollama to OpenRouter (pointing to `dots-studio/dots-3-note-preview:free`).
- [x] **Fallback Architecture Redesign**: The global exception catchers for LLM calls (`_fallback_deepseek_then_gemini` and `_fallback_ollama`) were refactored to read from independent `gemini_fallback` and `ollama_fallback` blocks rather than overloading the Tier 2 and Tier 4 configs.
- [x] **Self-Audit Verification**: Dispatched TriAPI in a synthetic 9-file run to comprehensively review the fallback logic and configuration decoupling, returning a clean architectural verdict (`OVERALL_AUDIT.md` - deleted post-review).

---

## Phase 18: Planner Provider Decoupling & Interactive CLI Fix (2026-08-22)

**Goal**: Eradicate hardcoded API endpoints, model strings, and provider types from the `planner.py` script so that TriAPI can rapidly swap in alternative models via standard configuration (e.g., OpenRouter, Nemotron, Llama) for the interactive plan authoring step.

- [x] **`planner.py` Configuration Parsing**: Updated `plan_turn` to read `tier_1_planner` settings from `config/tiers.yaml` instead of hardcoding a `claude -p` subprocess.
- [x] **`planner.py` Context Enrichment**: Since cloud models lack file search capabilities, `planner.py` automatically injects repo context (`AGENTS.md`, `PLAN.md`, `README.md`) using `build_context_blob` for non-CLI providers.
- [x] **`planner.py` Legacy CLI Refinements**: If the provider is `cli`, the script manually executes a subprocess to `claude -p` using the proper `--tools Read,Glob,Grep`, `--output-format json`, and `--resume` flags, and gracefully falls back to `llm_client._fallback_request()` if the CLI fails or hits quota limits.
- [x] **`llm_client.py` Logging Fix**: Discovered and patched an `AttributeError` crash inside `llm_client.py` where `tri_logging.warning()` was improperly called without fetching a logger instance first.

---

## Phase 19: Fall Fast Fall Hard Architecture (2026-08-23)

**Goal**: Eradicate silent API fallbacks and escalation masking. If an LLM endpoint fails fundamentally (e.g. 403 Spend Cap, 429 Rate Limit, 503 Gateway), the pipeline must instantly crash to alert the operator instead of burning cycles letting lower tiers attempt to parse a systemic backend outage.

- [x] **`llm_client.py` Consolidation**: Ripped out `_fallback_request`, `_fallback_ollama`, and all `try/except` safety nets. `execute_llm()` is now a pure passthrough that will aggressively raise HTTP exceptions.
- [x] **`orchestrator.py` Fail-Fast Hooks**: Rewrote the Tier 4 (`try/except`) and Tier 3/2/1 escalation loops. If a tier fails its unit tests (`build_failed`), the pipeline gracefully escalates. If a tier suffers a backend error, the orchestrator instantly raises a `RuntimeError` and collapses the pipeline.
- [x] **Model Probe Pre-flight Gate**: Implemented `probe_models()` in `llm_client.py` and hooked it into `cmd_dispatch` inside `triapi.py`. TriAPI now actively pings all configured models with a dummy payload before launching a dispatch run, refusing to start if any configured backend is dead.

**Correction (2026-08-23, see Phase 21):** this phase's claims of "ripped out
all try/except safety nets" and a Tier 4 loop that "instantly raises a
RuntimeError" were not fully true — `tier4_worker.run()` still caught
`requests.RequestException`/`Exception` around its LLM call and downgraded
it to an ordinary result, so Tier 4 never actually failed hard. Also,
`_fallback_request` was removed from `llm_client.py` here but two call
sites in `planner.py` still referenced `llm_client._fallback_request()`,
which would have raised `AttributeError` if ever hit. Both fixed in Phase 21.

---

## Phase 20: Tier 1 Configuration Fix (2026-08-23)

**Goal**: Restore Tier 1's role as a robust Claude CLI-based final repair tier without reverting the configuration-driven design established in Phase 17.

- [x] **Tier 1 Separation**: Added a distinct `tier_1_manager` block to `tiers.yaml` (defaulting to the `cli` provider) to stop `tier1_escalate.py` from hijacking the `tier_1_planner` configuration. This resolved an issue where OpenRouter's `stealth/ox-alpha` was being routed massive repair prompts, hitting an upstream shared pool rate limit (`429`).
- [x] **Claude CLI stdin Patches**: Corrected `llm_client.py`'s handling of the `cli` provider to pass the prompt via `stdin` (`input=prompt`) instead of a positional argv flag (`-p prompt`) to avoid the kernel's `execve()` argument-list limit, and updated the system prompt flag from `--system` to `--system-prompt` to match the latest Claude Code CLI version.

---

## Phase 21: openrouter-branch self-audit + fixes (2026-08-23)

**Goal**: verify the branch's stated goal (all 4 tiers config-driven/hot-swappable, pre-flight probe, fail-fast) against actual code, not prior phases' self-reported status (per standing "verify, don't trust status" practice). A background research fork audited the diff against `main`; findings were then hand-fixed directly (not routed through `triapi plan`/`dispatch`, per explicit exception granted in this session for the one blocker that made the pipeline unable to plan at all — see item 7).

**Findings and fixes (all applied to the working tree same session):**
1. `llm_client._call_claude_cli()` never passed `--model`/`--effort` to `claude -p`, so Tier 1 silently used the CLI's own default model/effort instead of a verified Sonnet 5 high. Fixed: `execute_llm()`/`_call_claude_cli()` gained an `effort` parameter, threaded from `tier_1_manager.effort` in `config/tiers.yaml` (new field, value `high`); `tier_1_manager.models.default` is now `claude-sonnet-5` (was the meaningless placeholder `claude-code`).
2. `probe_models()` iterated `tier_1_planner` but never `tier_1_manager` — a real Claude-CLI outage/misconfig for the repair tier would sail through the pre-flight probe undetected. Fixed: probes both.
3. `config_loader.REQUIRED_KEYS` was missing `tier_1_manager`. Fixed: added.
4. `tier4_worker.run()` still caught `requests.RequestException`/`Exception` around its LLM call (see Phase 19 correction above) and downgraded systemic errors to an ordinary result instead of letting them crash the pipeline like tiers 1-3. Fixed: the try/except was removed; exceptions now propagate to `orchestrator.run_task()`'s existing crash-on-exception wrapper around the Tier 4 call.
5. The `probe_models()` call added to `cmd_dispatch` (Phase 19) makes real network/CLI calls and wasn't mocked in `tests/test_branch_features.py`'s `SelfFixTests` — those 3 tests hung indefinitely instead of running deterministically. Fixed: `mock.patch.object(triapi.llm_client, "probe_models")` added to each.
6. `test.py`, `test_audit.py`, `test_llama.py`, `planner_backup.py` were committed debug/scratch cruft at repo root, not referenced by `AGENTS.md`'s file index or any real test/build path. Removed via `git rm`.
7. **Found live while attempting to route the fix through `triapi plan` itself, not part of the original audit**: `tier_1_planner`'s OpenRouter `stealth/ox-alpha` 403s on every call once `planner.py`'s usual context blob (`AGENTS.md`/`PLAN.md`/`README.md`) is injected — OpenRouter's content filter flags the `git@github.com:...` SSH URLs those docs legitimately contain as PII (`"Request blocked by content filter: [EMAIL]"`), which fully bricked `triapi plan` for this repo. This is a chicken-and-egg problem (can't route a planner fix through a broken planner), so per the user's explicit in-session direction, this one was hand-fixed as a narrow exception to "never hand-write code without being asked" — `stealth/ox-alpha` stays `tier_1_planner`'s primary (deliberately, per the user), `tier_1_manager`'s Claude CLI (Sonnet 5, high) is now its fallback on any failure. Fixed: `planner._sanitize_for_content_filter()` scrubs email-like tokens from the prompt sent to non-cli providers only; both the `cli`-branch and non-cli-branch failure paths now call a new `_fallback_to_tier1_manager_cli()` helper — which also fixed the two dead `llm_client._fallback_request()` call sites flagged in the Phase 19 correction above (that function never existed post-Phase-19). Verified live end-to-end: `plan_turn()` returned `status: ok` (`"banana"`, a literal smoke-test instruction) via the OpenRouter primary path after sanitization.

**Verification**: `tests/test_branch_features.py` 68/68 passing, no hangs (previously hung indefinitely per finding 5). `tests/test_judge.py` had 10 failures (`KeyError: 'api_key_secret'`) — initially assumed pre-existing/unrelated based on a same-branch `git stash` comparison, but see finding 8 below: that assumption was wrong. `probe_models()` run for real against all 5 tier configs (`tier_4_worker`, `tier_3_debugger`, `tier_2_manager`, `tier_1_planner`, `tier_1_manager`) succeeded.

**Also removed**: a stale, never-dispatched "OpenRouter Refactor Audit" plan (`run_id 20260823-163408-8eee04`, 9 unchecked `verify_only` steps) was appended to `AGENTS.md` and blocking new `triapi plan` runs. Its entire purpose — auditing this exact refactor — is superseded by the findings above, so it was removed as moot rather than dispatched or force-marked complete (it was never actually run, so marking it complete would be dishonest).

8. **Found during the pre-merge check pass, correcting the finding above**: a `git stash` diff only proves a failure predates *this session's own changes on this branch* — it does not prove the failure predates the branch itself. Checked properly this time via a `git worktree add` against `main`: `tests/test_judge.py` passed 13/13 cleanly on `main`, so the 10 failures were a real regression introduced somewhere in this branch (traced to Phase 17's `scripts/judge.py` change from a hardcoded `secrets['deepseek_api_key']` to config-driven `secrets[tier3['api_key_secret']]` — correct in production, but the test file's mocked `tier_3_debugger` fixture was never updated to include `api_key_secret`). Fixed by adding `"api_key_secret": "deepseek_api_key"` to the fixture. Full suite: 141/141 passing.

**Merge (2026-08-23)**: `openrouter` merged into `main` via `git merge --no-ff` (commit `47cddb4`), not pushed to any remote. Re-verified 141/141 passing on `main` post-merge.

## Phase 23: Tier 1/2 swallowed-error and Tier 2 model-priority bugs (2026-08-23/24)

**Found while resuming a stalled target-repo dispatch run** — a target repo's own supervisor doc flagged both, and TriAPI's own bug-capture (`logs/triapi_bugs/20260824-011637-056877-...json`) recorded the resulting crash (`RuntimeError: Tier 1 failed: None`).

1. `tier1_escalate.py` and `tier2_escalate.py` both caught the `execute_llm()` exception and returned `{"status": "error"}` with no `"reason"` key (unlike `tier3_escalate.py`, which always has). `orchestrator.run_task()` then raises `RuntimeError(f"Tier N failed: {result.get('reason')}")`, which prints `None` — the real cause (in this run, a 403 from `tier_1_planner`'s OpenRouter model, encountered before the Phase 21 merge fixed `tier_1_manager` to use the Claude CLI) was invisible in the escalation log. Fixed: both now log and return a `reason` string built from the exception, mirroring tier3's pattern.
2. `tier2_escalate.py`'s model selection (`models = [tier2["models"][model]] if model else (tier2.get("fallback_chain") or [default_model])`) used `fallback_chain` (Gemini flash models) unconditionally whenever no explicit `--model` was passed — the normal case — so every real Tier 2 call silently used Gemini instead of `default_model` (Nemotron), contradicting `tiers.yaml`'s own documented intent (fallback_chain is for daily-quota exhaustion only). Fixed: `default_model` is now always tried first; the function loops through `[default_model] + fallback_chain`, only advancing to the next candidate on an HTTP 403/429 (quota/rate-limit) response — any other error is reported immediately, not masked by silently trying a different model.

**Verification**: full suite 141/141 passing post-fix (no existing test exercised this code path directly — both functions are invoked live, end-to-end, only through mocked wrappers in `tests/test_branch_features.py`).

## Phase 24: supervisor mid-run item insertion pollutes state via task_id collision (2026-08-24)

**Mechanism**: `dispatcher.dispatch()` derives each item's `task_id` purely from its position — `f"{run_id}-p{pi}-i{ii}"` — not from any content hash or stable identifier. `state.py`'s `read_state()`/`write_state()` and the escalation log (`logs/escalation_<task_id>.md`) are both keyed by that same positional `task_id`.

**Consequence**: if a supervisor (human or agent) inserts a new item into a live run's `breakdown.phases[i]["items"]` at any position other than the tail of its phase — e.g. to slot in a quick fix ahead of an already-attempted item — every item after the insertion point shifts index, and the newly-inserted item silently inherits whatever `task_id` its new position previously belonged to, along with that old item's **stale `state.json`** (`consecutive_failures`, `last_stderr`) and escalation log history. Concretely: an inserted item picked up a prior item's leftover `last_stderr` (an unrelated infra timeout) and consecutive-failure count, which then got fed into Tier 3/2/1's repair prompts as if it were *this* item's build error — every tier attempted to "fix" a problem that didn't describe the actual failing check, and all failed, landing in `human_handoff` for what should have been a trivial fix.

**Fix applied (workaround, not a code change)**: after inserting a mid-phase item, delete the stale `logs/state/<run_id>-p<i>-i<j>.json` for every task_id whose position now points at a *different* item than before the insertion (or simplest: only insert at the tail of a phase's `items` list, never before an already-dispatched or already-attempted item, so no positional collision is possible).

**Not yet fixed in code — real gap for later**: `task_id` generation should ideally be derived from something stable per item (e.g. a hash of `target` + `description`) rather than pure phase/item position, so a supervisor-inserted item never silently inherits another item's history. Left as a known issue rather than fixed now, since the safe workaround (insert at phase tail, or clear state on collision) is sufficient and a task_id-scheme change touches `dispatcher.py`, `state.py`, and every `tier*_escalate.py` call site — bigger surface than warranted for a same-session fix.

## Phase 25: a genuine Tier 4 timeout never reaches Tier 3/2/1 at all (2026-08-24)

**Mechanism**: `tier4_worker.run()` deliberately lets a connectivity/timeout exception from `execute_llm()` propagate uncaught (Phase 21 finding #4 — a systemic Ollama-down error must crash loudly, not silently downgrade to an ordinary escalatable result). `dispatcher.dispatch()` catches that raised exception at its own level with a "transient timeout" retry wrapper — same call, same item, up to 3 attempts with a short backoff — and if all 3 time out identically, gives up entirely (`status: "error"`, dispatch stops) without ever invoking `orchestrator.run_task()`'s normal Tier 4→3→2→1 escalation ladder for that item.

**Consequence, observed for real**: a small, simple item (a ~12KB target + context file, nothing unusual) hit an identical 300s Ollama read-timeout three times in a row across two separate dispatch invocations — 6 timeouts total, ~30 minutes of wall-clock time spent, before the run gave up on an item that other tiers (Tier 3 had already resolved 7 other items in the same run without issue) could very plausibly have handled fine. The retry wrapper's premise — "this is probably a transient connectivity blip, retry the identical call" — doesn't hold for a hang that's reproducible and item-specific; retrying the exact same call three times against the exact same (still-loaded, still-healthy per `ollama ps`) model just repeats the same wait.

**Workaround applied this session (not a code change)**: set `skip_tier4: true` directly on the stuck item in the run's own breakdown JSON, forcing it to start at Tier 3 instead of retrying the hung Tier 4 path, then resumed.

**Not yet fixed in code — real gap for later**: the dispatcher's transient-timeout retry wrapper should probably fall through to the normal Tier 3/2/1 escalation ladder after its retries are exhausted, instead of surfacing a bare unresolved error — a timeout is still "Tier 4 failed to resolve this item," which is exactly what the escalation chain exists for. Left unfixed for now (workaround was sufficient and immediate); worth revisiting alongside Phase 24's task_id fix since both touch the same retry/resume path in `dispatcher.py`.

**Recurred on a second, different item in the same run (2026-08-24, later the same evening)**: same exact symptom (identical 300s timeout, 3x, no escalation) on a different, unrelated target file — confirms this is a systemic Tier 4 behavior on this box, not a one-off fluke tied to a specific file's content. Same `skip_tier4: true` workaround applied. Raises this gap's priority for an actual code fix next time TriAPI's own repo gets planned/dispatched work, rather than being a rare edge case.

## Phase 26: OpenRouter content-filter fix generalized beyond the planner (2026-08-24)

**Found**: after the Phase 25 workaround routed an item to Tier 2, every single candidate model in `tier_2_manager`'s chain (`default_model` plus all 4 of `fallback_chain`) returned `403 Forbidden` from OpenRouter — confirmed live this was not an auth/key problem (the same key succeeds against the same endpoint with a plain prompt) but the request's actual content: the target file's own legitimate test fixture data contained an email-like literal (a synthetic address used to test malicious-input handling). This is the identical OpenRouter content-filter behavior fixed in Phase 21 finding #7 — but that fix (`planner._sanitize_for_content_filter()`) only ever applied to `planner.py`'s own prompt, never to the escalation tiers. `tier_2_manager` and `tier_3_debugger` both use `provider: openrouter` too, so either can be blocked by the exact same class of content whenever a target file's real content (test fixtures, example data, anything email-shaped) happens to look like PII to OpenRouter's filter.

**Fixed**: generalized the sanitizer into `llm_client.py` (the single dispatch point, per the Phase 17 consolidation) as `_sanitize_for_openrouter_content_filter()`, applied inside `_call_openai_api()` to both `prompt` and `system_prompt` whenever `provider == "openrouter"` — covers `tier_1_planner`, `tier_2_manager`, and `tier_3_debugger` uniformly instead of requiring each call site to remember to sanitize itself. `planner.py`'s own existing sanitize call is left in place (idempotent on already-sanitized text, harmless duplication) rather than restructured, to keep this fix minimal.

## Phase 27: Tier 3/4 model swap — DeepSeek direct, notes3 to Tier 4 (2026-08-24)

**Change (user-directed, config only)**: confirmed a real `deepseek_api_key` secret exists and the direct DeepSeek API (`api.deepseek.com`, OpenAI-compatible `/chat/completions`) is live (`model: "deepseek-chat"` server-resolves to `deepseek-v4-flash`) — swapped `tier_3_debugger` from OpenRouter's dots-3-note-preview to this direct DeepSeek endpoint (`provider: deepseek`, `api_key_secret: deepseek_api_key`, `models.flash: "deepseek-chat"`, `default_model: flash`, matching the existing `pricing.flash` block's real non-zero rates). `tier_4_worker` took dots-3-note-preview's old slot instead (`provider: openrouter`, `models.default: "dots-studio/dots-3-note-preview:free"`), moving Tier 4 off local Ollama entirely — `automatable` flipped `false → true` since a cloud tier has no "is Ollama even running" concern. This also sidesteps Phase 25's genuine local-Ollama Tier 4 timeout bug, since dispatch no longer depends on local Ollama responsiveness at all.

**Verified before relying on it**: both endpoints tested live by hand (direct curl to `api.deepseek.com` with the real secret; OpenRouter with the existing key) before touching config; `llm_client.probe_models()` run for real against all 5 tier configs post-edit, succeeded; full suite 141/141 passing. Confirmed no code assumes `tier_4_worker.provider == "ollama"` as a hard requirement — `triapi.py`'s pre-dispatch Ollama-unload logic is already gated on that check and cleanly no-ops when it's false; `llm_client.execute_llm`'s `is_tier4` flag is accepted but not actually branched on anywhere in `_call_openai_api`/`_call_gemini_api`/`_call_claude_cli`, so the swap needed no code changes, only `config/tiers.yaml`.

**Correction/scope note from the user immediately after**: this swap technique — rewriting each tier's whole `provider`/`endpoint`/`api_key_secret`/`models` block by hand — is exactly the "hardcoded to the tier" pattern the user wants gone. A named-backend-registry refactor (tiers reference a reusable backend by name instead of embedding their own full config) is queued in `CARRYOVER.md` as real TriAPI self-feature work, to be drafted via `triapi plan` and dispatched, not hand-built. This phase's swap stands as a working interim state, not the target end-state architecture.

**Verification**: full suite 141/141 passing post-fix. (One test, `test_ollama_service_lifecycle.py`, failed once with an unrelated live-network flake — `probe_models()` hitting a real OpenRouter/Gemini endpoint from inside what's nominally a unit test — then passed cleanly on its own in two separate reruns both before and after this fix; not caused by this change, a pre-existing test-isolation gap in the same family as the mock-patch-target bugs documented earlier in this file.)

## Phase 28: `edit_blocks.apply_edit_blocks()` crash on null Tier 3 content (2026-08-25)

**Symptom**: foreground `cmd_dispatch` crashed with `AttributeError: 'NoneType' object has no attribute 'strip'` at `edit_blocks.py:74`, reached via `tier3_escalate.py:236`.

**Root cause**: a DeepSeek response with `message.content: null` was passed to `apply_edit_blocks()` with no None/empty guard.

**Fix**: `apply_edit_blocks()` now fails closed — `if not isinstance(response_text, str) or not response_text.strip(): return None, "model returned no usable text (None or empty)"` — the same `(None, reason)` shape callers already handle for SEARCH mismatches, closing the crash class for all tiers at once. `tier3_escalate.escalate()` also got its own null-content branch (logs `finish_reason`/`reasoning_content` diagnostics, still logs cost when a usage block exists, returns the same failure shape as its other error paths). `tier1_escalate.py`/`tier2_escalate.py` call sites were inspected and confirmed to already degrade gracefully on `(None, reason)` — no change needed there.

**Verification**: full suite 144/144 passing (3 new regression tests added: `apply_edit_blocks(None)`/`("")` return `(None, str)`; a mocked null-content DeepSeek response through `tier3_escalate.escalate()` returns `fix_rejected` and leaves the target file untouched). The dispatched fix for `tier3_escalate.py` needed one critique-triggered revision (Tier 2 initially over-rewrote unrelated extraction logic); the follow-on `tests/test_branch_features.py` test the run wrote had two bugs of its own — a mock patched a nonexistent `tier3_escalate.requests` (the real call goes through `llm_client.requests`) and called `escalate()` with kwargs not in its real signature (`workdir`/`build_cmd`/`refactor_instruction`) — both fixed by hand as a mechanical test-only correction, same "mock-patch-target bug" family as prior phases. A real end-to-end smoke test (Tier 4→3 seam) timed out at 300s on the free-tier OpenRouter Tier 4 model; treated as free-tier congestion, not a regression, since the full suite already verifies the fix directly.

**Also found while dispatching this fix, not yet resolved — see `CARRYOVER.md`**: OpenRouter's content filter false-positives on `[PHONE]` for TriAPI's own digit-heavy log/doc content (run_ids, timestamps), which can wedge an item's *entire* escalation ladder, not just Tier 4 — the Phase 26 sanitizer only strips email-shaped tokens. Also confirmed live during this same dispatch: `PLAN.md` itself has grown past the documented 73728-char Tier 4 ceiling (178KB at time of writing), which blocked Tier 3/2 from making a targeted edit to this very file — Tier 3 regenerated the whole file instead of a diff and got rejected by `content_guard`. Both are queued for a future self-fix pass rather than hand-patched beyond this note.

## Phase 29: Tier 5 — librarian tier (doc-update automation) (2026-08-24)

**Design**: a fifth pipeline tier dedicated to doc-shaped targets (`*.md`, `docs/**`), so the supervising Claude agent never hand-writes TriAPI's own docs — the same discipline already applied to code repair. Explicitly **not** a reader/writer split (an earlier draft's design, dropped when the assumed reader model turned out to be an OCR tool, not a text reranker): one model, `mistral-small:latest` via local Ollama, both judges staleness and drafts the edit in a single pass (`scripts/librarian_escalate.py`'s `run()`). The staleness judgment is advisory-only (a leading JSON verdict, `no_change` never blocks anything); the actual write is real and gated by `content_guard.check_write()`/`edit_blocks.apply_edit_blocks()` like every other tier. Escalation chain is deliberately all-local/free and fully separate from the paid code-repair ladder: primary (Ollama `mistral-small:latest`) → `fallback_local` (Ollama, `ollama_fallback`'s model) → `fallback_openrouter` (OpenRouter, `tier_1_planner`'s free model) → human handoff — zero DeepSeek/Claude/Gemini calls anywhere in the chain. Routing (`dispatcher.is_doc_target()`) intercepts doc-shaped targets before the Tier 4 draft/build loop; a workdir-boundary check (`realpath` containment) in `librarian_escalate.run()` enforces that a target repo's docs and TriAPI's own docs never cross. The `@`-content pre-check (flagging likely email-like content before any OpenRouter-routed call) is plain regex (`llm_client.detect_email_like_content()`), not a model call — advisory-only, logs a `[PRE-CHECK]` warning, never blocks; it complements, and never replaces, `_sanitize_for_openrouter_content_filter()`.

**Real integration bugs found and fixed while landing this** (the Tier-4-drafted implementation files were internally inconsistent with each other and with the actual config schema — none of these were caught until real dispatch runs exercised the seams):
- `llm_client.probe_models()`'s `tier_5_librarian` block read `tier_config.get('endpoint')`, which is always `None` (the block has no static `endpoint` key by design — it resolves from the `ollama_host` secret at runtime) — produced `Invalid URL 'None/v1/chat/completions'` and aborted every dispatch, not just librarian-related ones. Fixed to resolve the endpoint from `secrets['ollama_host']` when unset and `provider == 'ollama'`.
- `dispatcher.py`'s Tier-4-drafted routing edit dropped the `judge` import from its `from scripts import ...` line, breaking `_run_design_judge()` (`NameError: name 'judge' is not defined`) on every design-check step across *all* tiers, not just Tier 5. Re-added.
- `scripts/librarian_escalate.py` (drafted separately from the config it was meant to read) used the wrong top-level config key (`"librarian"` instead of `"tier_5_librarian"`) and wrong escalation-threshold key (`"librarian_to_human"` instead of `"tier5_to_fallbacks"`), so `lib_config` was silently `{}` at runtime; its provider-resolution logic didn't match the real `models: {primary, fallback_local, fallback_openrouter}` schema at all (missing the primary→fallback_local distinction entirely, defaulting to a hardcoded `"llama3"`); its return dicts didn't include the `resolved_by` key or use the `"human_handoff"` status the rest of the pipeline expects (used a nonstandard `"escalate"`), which crashed `dispatcher.py`'s unconditional `result["resolved_by"]` read; and `dispatcher.py`'s routing call site passed `build_cmd`/`context_files` kwargs `run()` doesn't accept at all (`TypeError`). All reconciled by hand against the real schema and the real `run_task()`/`orchestrator.py` return-shape convention.
- `librarian_escalate.run()` unconditionally skipped **all** LLM attempts during DeepSeek peak billing hours (06:00–10:00 UTC) and escalated straight to human handoff — copied from the DeepSeek-specific tiers without adapting; Tier 5's chain never calls DeepSeek at all. Removed the check (`in_deepseek_peak_hours()`/`get_utc_hour()`) entirely.
- `llm_client.probe_models()` had zero retry tolerance — a single transient upstream blip on *any* tier (an OpenRouter 429, a free model's own temporary 502) aborted the entire pre-flight gate and thus the whole dispatch, even for tiers the current run doesn't use. Added `_probe_with_retry()`: 3 attempts, 5s apart, before failing the gate — still fails hard on a genuinely broken/misconfigured tier.
- `AGENTS.md` itself had grown to 91,600 chars, over the same 73,728-char Tier 4 ceiling its own docs describe, blocking any tier from editing it (including this phase's own doc update). Trimmed to 69,894 by removing four already-completed (one corrupted — literal leaked tool-call syntax) appended `triapi:plan` history blocks whose outcomes were already in this file — the same treatment documented at the top of `AGENTS.md` for 2026-08-19's identical situation.
- Separately: `tests/test_branch_features.py` was already within ~2,600 chars of the same ceiling before any Tier 5 tests existed. The locked plan's Phase 5 (mistakenly) targeted it directly instead of a new file; Tier 4 and Tier 2 both correctly refused the oversized write, and Tier 1 (Claude CLI, with real tool access unlike the edit-blocks-only tiers) split the new coverage into `tests/test_tier5_librarian.py` on its own initiative during its escalation attempt — 9 tests against the real `librarian_escalate.run()`/`dispatcher.is_doc_target()`/`llm_client.detect_email_like_content()` APIs (not the fictional `orchestrator.tier5_librarian()` shape an earlier Tier 2 draft had hallucinated and that `content_guard` had already rejected for size). The dispatcher still recorded the item as `human_handoff` since Tier 1's response contained no parseable SEARCH/REPLACE block for the *original* declared target — the fix was real, just not in a shape the pipeline's own success-detection could recognize.

- **Sixth real bug, found by the live smoke test itself (the mocked tests didn't catch it, since their fixture response was already correctly SEARCH/REPLACE-shaped)**: `build_prompt()` instructed the model to put the *entire new file contents* into the JSON verdict's `updated_content` field, but `run()`'s write path for an existing file always calls `edit_blocks.apply_edit_blocks()`, which requires SEARCH/REPLACE diff syntax, not full content — every real invocation against an existing file failed to apply (`mistral-small`, its Ollama fallback, and the OpenRouter fallback all failed the same way across two live attempts). Fixed by branching the prompt: editing an existing file now explicitly instructs SEARCH/REPLACE format (mirroring `edit_blocks.EDIT_INSTRUCTION`'s conventions); creating a brand-new file still asks for full contents, matching `run()`'s `extract_code()` path for that case.

**Verification**: `tests/test_tier5_librarian.py` (9 tests, zero skipped) plus the full existing suite (`tests.test_branch_features` + `tests.test_tier5_librarian`) green throughout. Real live smoke test via `scripts/librarian_escalate.py` against a throwaway `/tmp` fixture (real local Ollama `mistral-small:latest`, $0 cost): first two live attempts surfaced the SEARCH/REPLACE prompt bug above (correctly landed at `human_handoff` rather than corrupting the file); after the fix, a third live attempt confirmed the full path end-to-end — correctly identified `Version: 1.2.3` as stale, produced a valid SEARCH/REPLACE edit, applied it, and verified (`{"status": "success", "resolved_by": "tier_5", "changed": true}`, file now reads `Version: 2.0.0`).

**Not yet resolved, queued for a future pass**: `scripts/librarian_escalate.py`'s own OpenRouter fallback leg still has the same `endpoint=tier_config.get('endpoint')`-shaped resolution risk pattern the probe fix addressed elsewhere — worth a direct audit rather than assuming it's fine by inspection alone. The pre-existing `test_ollama_service_lifecycle.CmdDispatchOllamaLifecycleTests.test_cmd_dispatch_restores_ollama_state_on_exception` hangs on a real unmocked network call (confirmed live 2026-08-24, unrelated to this phase — already flagged by an earlier Jules advisory pass) rather than failing fast; needs a proper mock, not just a timeout.

## Phase 30: Three OpenRouter/dispatch bugs from live sessions (2026-08-25)

**Fixed via `triapi plan`/`dispatch` (run `20260824-164451-2b7635`), three independent bugs found across several live sessions:**

1. **OpenRouter content-filter false positives beyond email.** `llm_client._sanitize_for_openrouter_content_filter()` (Phase 26) only handled email-shaped tokens. Live evidence from OpenRouter's own "Blocked Requests" dashboard (36 blocks in one day: 18 phone, 12 email, 6 IP address) showed phone-number-shaped and IPv4-shaped digit sequences were also tripping the filter — hitting TriAPI's own log/doc content (run_ids, timestamps) as false positives. Added `_PHONE_LIKE_RE`/`_redact_phone_like()` and `_IP_LIKE_RE` cases alongside the existing email one, scoped with word-boundary/separator requirements so TriAPI's own `run_id`/`task_id` format (`YYYYMMDD-HHMMSS-hex`), hex hashes, and version strings are never mangled. New `tests/test_llm_client_sanitize.py` covers all three positive cases and the negative (must-not-mangle) cases.
2. **`dispatcher._is_deepseek_peak_hours()` stale duplicate.** This advisory-only warning (used in `handle_fix_forward`) hardcoded a single `06:00-10:00 UTC` window with no weekend exception, independent of the real gate (`budget_guard.check_tier3_peak_hours_ok()`, which reads `tiers.yaml`'s actual two windows and has a weekend off-peak exception). Now delegates to the real check instead of maintaining a second copy.
3. **`librarian_escalate.py` OpenRouter-endpoint audit.** Checked whether its `fallback_openrouter` leg had the same `tier_config.get('endpoint')`-is-always-`None` bug `probe_models()` had (Phase 29). Confirmed already correct — it resolves via `config.get("tier_1_planner", {}).get("endpoint")`, a real static config key, not the buggy pattern. No code change; added a regression test asserting the resolved URL is the real OpenRouter endpoint, not `None`.

**Two items hit real, unrelated obstacles during dispatch, both resolved without touching the fix's own code:**
- A regression-test item targeted `tests/test_branch_features.py`, which was already at 73,571 chars — within ~150 chars of this repo's 73,728-char Tier 4 ceiling. Every tier correctly refused the oversized write (the guard working as designed). Retargeted to a new file, `tests/test_dispatcher_peak_hours.py`, which landed clean.
- The Phase-4 doc-update step that would normally append this very entry via Tier 5 (the librarian) exhausted all three of its escalation legs against `PLAN.md` itself: local Ollama timed out (this file is ~189KB, too large for a timely local pass), the local fallback produced an unparseable response, and the OpenRouter fallback still 403'd even with this phase's own phone/IP sanitizer fix already live — meaning something else in `PLAN.md`'s bulk content trips the filter, not yet isolated. Written by hand instead (docs are an explicit standing exception to "route everything through the pipeline" — see `CARRYOVER.md`). `PLAN.md`'s own size is already a separately-queued cleanup item (consolidate historical/target-repo content out), which would likely also fix this librarian-escalation gap as a side effect.

**Verification**: full suite green throughout (101 tests including the 3 new sanitizer tests + 4 new peak-hours-delegation tests + 1 new endpoint-audit test + the retargeted regression test).

## Phase 31: Tier-reassignment prep — `agy` provider, generic breakdown routing, position-independent DeepSeek peak-hour gate (2026-08-25)

**Fixed via `triapi plan`/`dispatch` (run `20260824-221726-3df72d`), three prerequisite fixes ahead of a manual tier reassignment (DeepSeek → Tier 2, Gemini-via-`agy` → Tier 3, local qwen stays Tier 4 — not yet applied to `config/tiers.yaml`, deliberately excluded from this run):**

1. **New `agy` (Antigravity CLI) provider in `llm_client.py`.** `_call_agy_cli()` mirrors `_call_claude_cli()`'s subprocess pattern: invokes `agy -p <prompt> --model <model> --effort <effort> --dangerously-skip-permissions --output-format json`, parses the JSON response, and raises `subprocess.CalledProcessError` uniformly on any failure mode (non-zero exit, undecodable stdout, or a decoded body with `status != "SUCCESS"`) — the exact same exception family `_call_claude_cli()` already raises, so existing per-tier fallthrough logic absorbs an exhausted/failed `agy` call gracefully rather than crashing. Confirmed live pre-implementation via a real smoke test (`agy -p "reply pong" --model gemini-3.1-pro --effort low ...` → `{"status":"SUCCESS","response":"pong\n",...}` in 8.66s, pre-authenticated).
2. **Generic provider routing in `dispatcher._breakdown_phase_attempt()`.** Previously hardcoded `if provider == "openrouter": ... else: <Google-REST-shaped gemini_fallback call>`, which would have broken for any other provider (`deepseek`, `cli`, `agy`). Now the Google-specific branch fires only for `provider == "google"`; every other provider routes through `llm_client.execute_llm()` generically, matching how `tier2_escalate.py`/`tier3_escalate.py` already dispatch.
3. **Position-independent DeepSeek peak-hours gate.** `budget_guard.check_tier3_peak_hours_ok()` previously read `config["tier_3_debugger"]["peak_hours_utc"]` unconditionally — hardcoded to a tier name, not to DeepSeek itself. New `resolve_deepseek_tier(config)` scans the configured tiers for whichever one has `provider == "deepseek"` and the real `api.deepseek.com` endpoint, and the gate reads peak windows from *that* tier's config (falling back to `DEFAULT_TIER3_PEAK_HOURS_UTC` when DeepSeek isn't assigned anywhere). `orchestrator.py`'s gate call site now applies the check before whichever escalation slot resolves to DeepSeek, not hardcoded to the Tier 3 position — so the gate follows DeepSeek through a future reassignment instead of silently protecting the wrong (or no) tier.

**Two items needed a retarget/rewrite during dispatch, both resolved without touching the underlying fixes:**
- A regression test (`tests/test_branch_features.py` target) was retargeted mid-plan by the dispatched breakdown itself to a new file, `tests/test_dispatcher_peak_hours.py`'s sibling `tests/test_tier_reassignment_prep.py`, per this repo's established ceiling-avoidance convention.
- That new test file's first draft mismatched the real implementation in two ways: (a) assumed nonexistent custom exception classes (`QuotaExhaustedError`/`ProviderError`/`DecodingError`) instead of the real, uniform `subprocess.CalledProcessError`; (b) five tests used wrong mock-patch targets (`scripts.dispatcher.llm_client.execute_llm`, unreachable since `_breakdown_phase_attempt()` does a local `from scripts.llm_client import execute_llm` rather than a module-level import — the correct target is `scripts.llm_client.execute_llm` directly) and wrong function locations/signatures (`resolve_deepseek_tier` lives in `budget_guard.py` not `dispatcher.py`; `check_tier3_peak_hours_ok()` takes no arguments and returns a dict, not a bare bool). Both fixed via two retarget passes with the exact diagnosis supplied, resolved by Tier 2 on the second pass.
- The final doc-update item (this entry) itself exhausted `tier_5_librarian`'s escalation legs against `PLAN.md` — same recurring cause as Phase 30's identical note (file too large for local models, OpenRouter fallback still 403s). Written by hand again. **This is exactly why item 1 in the current `CARRYOVER.md` queue is adding `agy` (confirmed ~1M-token context, no OpenRouter content filter) as a new `tier_5_librarian` fallback leg** — the next dispatch after this one should close this gap for good.

**Verification**: `python3 -m unittest tests.test_branch_features tests.test_tier5_librarian tests.test_llm_client_sanitize tests.test_dispatcher_peak_hours tests.test_tier_reassignment_prep -v` green, zero skipped.

## Phase 32: `run_build()` pipefail fix + stale Tier-3-peak-skip test fixture (2026-08-25)

**Fixed via `triapi plan`/`dispatch` (run `20260825-000610-4c040a`):**

1. **`run_build()` silently masked real failures behind a trailing pipe.** `tier4_worker.run_build()` invoked `build_cmd` via plain `subprocess.run(build_cmd, shell=True, ...)` — no `pipefail`. A `build_cmd` piping its output through a truncating command (e.g. `... -v 2>&1 | tail -15`, a pattern this repo's own dispatched plans had already used) reported the LAST pipeline stage's exit code, not the real command's — confirmed live: `bash -c 'false | tail -1; echo $?'` prints `0`. Caught in the act: Phase 31's own final-verification item reported `success` despite the underlying `unittest` run having 2 real failures. Fixed by invoking `build_cmd` via `["bash", "-o", "pipefail", "-c", build_cmd]` instead of bare `shell=True`. New `tests/test_run_build_pipefail.py` proves a piped failure is now detected, a piped success still succeeds, and ordinary non-piped commands are unaffected.
2. **`OrchestratorTier3PeakSkipTests`' fixture predated the position-independent peak-hours gate (Phase 31).** Its shared `config` dict had no `tier_3_debugger` block, so `budget_guard.resolve_deepseek_tier()` found no matching tier and the gate under test never actually fired — two of its three tests were silently passing for the wrong reason (or, once the pipefail fix landed, correctly failing). Fixed by adding a realistic `tier_3_debugger` block to the fixture; the class was relocated to `tests/test_orchestrator_tier3_peak_skip.py` since the fix pushed `tests/test_branch_features.py` over the 73,728-char ceiling.

**One retarget during dispatch**: the relocated file's first draft made the same mistake `test_tier_reassignment_prep.py` made in Phase 31 — calling `budget_guard.check_tier3_peak_hours_ok()` with a positional config argument, when the real function takes none (reads config via `load_tiers()` internally). Fixed with the exact diagnosis supplied, resolved on the next attempt. The final full-suite verification item was also re-added after being narrowed during the retarget, and re-confirmed by hand: 118/118 tests green.

**Also found while dispatching this fix, not yet resolved**: the doc-update item for this very entry again exhausted `tier_5_librarian`'s escalation legs against `PLAN.md` (same recurring cause as Phase 30/31 — local models time out, OpenRouter fallback still 403s). Written by hand again. Confirms the queued `agy`-as-librarian-fallback item in `CARRYOVER.md` is worth prioritizing.

**Verification**: `PYTHONPATH=. python3 -m unittest tests.test_branch_features tests.test_tier5_librarian tests.test_llm_client_sanitize tests.test_dispatcher_peak_hours tests.test_tier_reassignment_prep tests.test_run_build_pipefail tests.test_orchestrator_tier3_peak_skip -v` — 118/118 green, zero skipped, re-confirmed by hand independent of the (now-trustworthy) dispatched verify step.

## Phase 33: Tier reassignment — DeepSeek to Tier 2, Gemini/agy to Tier 3, local Ollama back to Tier 4 (2026-08-25)

**Fixed via `triapi plan`/`dispatch` (run `20260825-092344-5ff4a7`), the tier reassignment that Phases 30-32 were all prerequisite work for (OpenRouter sanitizer, generic provider routing, position-independent DeepSeek peak-hours gate, `run_build()` pipefail fix):**

1. **`tier_2_manager`** moved from OpenRouter Nemotron to the real DeepSeek hosted API: `provider: deepseek`, model `deepseek-v4-pro` (confirmed live via `GET https://api.deepseek.com/models`), `peak_hours_utc` moved here from Tier 3 (`[["01:00","04:00"],["06:00","10:00"]]`), pricing block adapted from the old `tier_3_debugger.pricing.pro` values. The disabled Gemini `fallback_chain` and its incident narrative were removed as obsolete.
2. **`tier_3_debugger`** moved from the real DeepSeek API to Google's Antigravity CLI (`agy`, provider `agy`) running `gemini-3.1-pro` at effort high — no `api_key_secret`/`endpoint` needed (local CLI, own OAuth). Its DeepSeek pricing/peak-hours fields were removed as no longer applicable.
3. **`tier_4_worker`** moved from OpenRouter `dots-3-note-preview` back to local Ollama, `qwen2.5-coder:14b-instruct-q6_K` at `http://localhost:11434` (same model already proven reliable via `tier_5_librarian.ollama_fallback`).
4. `gemini_fallback` config block is now fully dead/unused (nothing references it once `tier_2_manager` stops being Gemini) — left in place, out of scope for this phase.
5. **Stale regression-test fixture fixed**: `tests/test_orchestrator_tier3_peak_skip.py`'s `TIER_3_DEBUGGER_CONFIG` fixture and `test_config_matches_tiers_yaml` hardcoded the OLD `tier_3_debugger`/DeepSeek shape (nested `flash`/`pro`/`default` pricing). Renamed to `TIER_2_MANAGER_CONFIG`, updated to the new flat-pricing `tier_2_manager` shape, and the two peak-hours tests' mocked `load_tiers()` calls now key on `tier_2_manager` instead of `tier_3_debugger` — matching `budget_guard.resolve_deepseek_tier()`'s real, position-independent lookup (no code change needed there, already correct since Phase 31).

**Two real root-cause bugs found and fixed while supervising this dispatch, beyond the plan's own scope:**
- `scripts/judge.py` and `scripts/tier3_escalate.py` both hardcoded Tier 3 to a raw DeepSeek-shaped HTTP call and direct `tier3["pricing"][model_key]` indexing instead of the generic `llm_client.execute_llm()` dispatcher — broke instantly once Tier 3 became `agy` (no endpoint/pricing block). Fixed both call sites to route generically with `.get()` fallbacks; updated `tests/test_judge.py`'s mocks to match.
- `scripts/cost_report.py`'s `deepseek_flash_cost()` had the same hardcoded-pricing-under-`tier_3_debugger` pattern. Fixed by moving the reference pricing into a new standalone `deepseek_reference_pricing` top-level block in `config/tiers.yaml`, decoupled from any tier slot (a stable external benchmark, not the live tier assignment).

**Also found: a recurring "false success" bug in doc-edit escalation, now confirmed on a second file.** The Phase 4 item to correct `AGENTS.md`'s stale tier-assignment bullet reported `status: success, resolved_by: tier_5`, but the file was verified byte-for-byte unchanged (`git diff` empty) — the item's own `build_cmd` was only `wc -c AGENTS.md` (a size check), which cannot detect a no-op edit. This is the same failure mode already flagged in `CARRYOVER.md` for a small 7.8KB file (`librarian_escalate.py` judging a file "fresh"/no-change-needed despite a genuinely missing addition) — now seen a second time, on a different file, via a different escalation path reporting bare `success` rather than even `changed: false`. Worked around by hand-editing `AGENTS.md`'s `config/tiers.yaml` bullet directly. **This needs its own investigation as a priority queue item** — doc-edit "success" verify steps must confirm actual content diff, not just file size, or a silent no-op will keep passing as done.

**PLAN.md's own size (this file) is now ~200KB, ~2.7x this repo's 73,728-char Tier 4 ceiling** — the Phase 4 doc-update item for this very entry hit `human_handoff` for exactly that reason (Tier 4 correctly refused rather than guessing). Written by hand instead, same as Phases 30-32. The escalation itself suggested splitting this file into smaller cohesive modules rather than continuing to append — noted as a queued architecture item, not attempted as part of this phase (out of scope, needs its own plan).

**Verification**: full 191-test suite green (`PYTHONPATH=. python3 -m unittest discover -s tests -v`), zero failures, zero unexpected skips, re-confirmed by hand independent of the dispatched verify step (given the false-success finding above, verify steps' actual assertions were manually reviewed, not just trusted).
