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


## This file's own index

PLAN.md was split 2026-09-01 to bring it back under this repo's
73,728-char ceiling (it had grown to ~205,040 chars, ~2.7x the limit --
flagged as a queued item since Phase 30-33, 2026-08-25). Convention
mirrors AGENTS.md's own split (see `docs/agents/index.json`): nothing
was deleted, completed content was relocated verbatim to dated files
under `docs/plan/`, each kept under the ceiling on its own.
**Machine-readable: [`docs/plan/index.json`](docs/plan/index.json)**.
Human-readable mirror:

| File | What's there |
|---|---|
| [`docs/plan/20260810-000000-phase0-through-phase9-scaffolding-through-git-authority.md`](docs/plan/20260810-000000-phase0-through-phase9-scaffolding-through-git-authority.md) | Phase 0 (scaffolding/secrets) through Phase 9 (git clone/pull/push authority), all complete |
| [`docs/plan/20260813-000000-phase10-through-phase22-breakdown-retries-through-hardening.md`](docs/plan/20260813-000000-phase10-through-phase22-breakdown-retries-through-hardening.md) | Phase 10 (per-phase breakdown/retries) through Phase 22 (worked-case audit/hardening), all complete |
| [`docs/plan/20260818-000000-carryover-log-tier4-routing-through-queue-drain.md`](docs/plan/20260818-000000-carryover-log-tier4-routing-through-queue-drain.md) | Former "Session Carryover Log" section, dated entries 2026-08-18 through 2026-08-20's queue drain |
| [`docs/plan/20260822-000000-carryover-log-phase17-through-phase33-provider-decoupling-tier-reassignment.md`](docs/plan/20260822-000000-carryover-log-phase17-through-phase33-provider-decoupling-tier-reassignment.md) | Former "Session Carryover Log" section continued, reused "Phase N" numbering, 2026-08-22 through the 2026-08-25 tier reassignment |
| [`docs/plan/20260904-145433-rag-memory-retrieval-layer.md`](docs/plan/20260904-145433-rag-memory-retrieval-layer.md) | RAG and memory retrieval layer implementation (exactly-once retrieval, local Ollama embeddings, fallback to keyword search) |

Read a file only when your task needs that specific historical detail —
`ARCHITECTURE.md`/`AGENTS.md` cover the live current state; this index
is for "why was it built this way" archaeology. Later work (everything
after the 2026-08-25 tier reassignment, including the 2026-09-01 tier
simplification) is tracked in `CARRYOVER.md`/`docs/carryover/` instead,
per this repo's "docs are index files" convention — nothing new should
be appended as inline Phase blocks here going forward; add a
`docs/plan/` entry (dated file + index row) for durable "why" record
if a future phase needs one, matching the pattern above.

## Phase 0 through Phase 9 — Scaffolding, secrets, config, Tier 3/4 clients, orchestrator, fixture, docs, planner/CLI, git authority (all ✅)

Moved to [`docs/plan/20260810-000000-phase0-through-phase9-scaffolding-through-git-authority.md`](docs/plan/20260810-000000-phase0-through-phase9-scaffolding-through-git-authority.md) 2026-09-01 (see "This file's own index" above) — content preserved verbatim, not summarized.

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

## Phase 10 through Phase 22 — Breakdown retries, context injection, resource guard, content-preservation guard, quota fallback, self-verifying-script fix, Tier 1 on/off, lessons/critique, worked-case hardening (all ✅)

Moved to [`docs/plan/20260813-000000-phase10-through-phase22-breakdown-retries-through-hardening.md`](docs/plan/20260813-000000-phase10-through-phase22-breakdown-retries-through-hardening.md) 2026-09-01 (see "This file's own index" above) — content preserved verbatim, not summarized.

## Session Carryover Log

Moved to `docs/plan/` 2026-09-01 in two dated files, split at the point where the original section's own "Phase N" numbering restarted and collided with the Phase 0-22 numbering above (a pre-existing historical artifact, not corrected) — see "This file's own index" above for both:
- [`docs/plan/20260818-000000-carryover-log-tier4-routing-through-queue-drain.md`](docs/plan/20260818-000000-carryover-log-tier4-routing-through-queue-drain.md) (2026-08-18 through 2026-08-20)
- [`docs/plan/20260822-000000-carryover-log-phase17-through-phase33-provider-decoupling-tier-reassignment.md`](docs/plan/20260822-000000-carryover-log-phase17-through-phase33-provider-decoupling-tier-reassignment.md) (2026-08-22 through the 2026-08-25 tier reassignment)

Content preserved verbatim in both, not summarized.
