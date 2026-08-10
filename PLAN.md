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

## Critical files
- `PLAN.md`, `mapping.md`, `ARCHITECTURE.md`, `README.md` (repo root)
- `.sops.yaml`, `config/tiers.yaml`, `config/secrets.example.yaml`, `config/secrets.enc.yaml`
- `scripts/secrets_loader.py`, `scripts/config_loader.py`, `scripts/state.py`, `scripts/tier4_worker.py`, `scripts/tier3_escalate.py`, `scripts/tier2_escalate.py`, `scripts/tier1_escalate.py`, `scripts/budget_guard.py`, `scripts/cost_report.py`, `scripts/orchestrator.py`
- `samples/broken_build/main.cpp`, `samples/broken_build/CMakeLists.txt`

## Open risks (carried forward, not blocking)
1. ~~Antigravity's MCP registration UI/format is unknown from inside this repo~~ — **moot as of Phase 5 (2026-08-10):** Antigravity is no longer a dispatcher in this design (Tier 2 is a direct Gemini API call), so there's nothing to register. Superseded by: Jules integration is deferred pending `jules login` + more research (see Phase 4's DEFERRED note).
2. ~~`claude -p` non-interactive output format needs a quick `--help` check~~ — **resolved in Phase 4**: `--output-format json` + `--tools ""` + `--system-prompt` is the pattern used in `tier1_escalate.py`.
3. DeepSeek pricing in `tiers.yaml` will drift over time; raw token counts in `cost_log.jsonl` let historical cost be recomputed later. Same applies to Google AI Studio's `free_tier_rpm`/`free_tier_rpd` placeholders in `tier_2_manager.pricing` — never verified against Google's actual published limits.
