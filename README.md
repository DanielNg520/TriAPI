# TriAPI

A 4-tier AI coding pipeline orchestrator: local Ollama → DeepSeek → Claude Code CLI → Gemini API → human review, cheapest first, so paid subscription quota is reserved for genuinely hard problems.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the design, and [PLAN.md](PLAN.md) for the full build history and decisions.

## Walkthrough: using this on your own project

This walks through running TriAPI against a real broken build for the first time, step by step. If you just want the command reference, skip to [Setup](#setup) / [Running](#running) below.

### 1. One-time setup

Do the four steps under [Setup](#setup) once: install Python deps, fill in `config/secrets.enc.yaml`, make sure Ollama's systemd service is running, and make sure `claude` is logged into your subscription (not an API key). You don't need to redo any of this for future tasks — it's persistent.

### 2. Pick a task

You need four things about the file you want fixed:
- **`--task-id`**: any string you choose, e.g. `fix-simd-crash`. This is how the pipeline tracks retry state and lets you look up cost later — reuse it if you re-run the *same* task, pick a new one for a different task.
- **`--target`**: the file to fix, e.g. `src/parser.cpp`.
- **`--workdir`**: the directory to run the build command in — usually your project root.
- **`--build-cmd`**: whatever you'd normally type to build, e.g. `"cmake -S . -B build && cmake --build build"` or `"make"`.

### 3. Run it

```bash
python3 scripts/orchestrator.py \
  --task-id fix-simd-crash \
  --description "Fix the SIMD alignment crash on startup" \
  --target src/parser.cpp \
  --workdir /path/to/your/project \
  --build-cmd "cmake -S . -B build && cmake --build build"
```

### 4. What happens, in order

You'll see this play out roughly as described in [ARCHITECTURE.md](ARCHITECTURE.md)'s escalation diagram:

1. **Tier 4 (local, free)** asks Ollama to draft/fix the file, then actually runs your build command. If the build passes, you're done — nothing else happens, nothing gets billed.
2. If the build fails **twice in a row**, it escalates to **Tier 3 (DeepSeek)**: DeepSeek gets the file + the error and writes a fix, which gets rebuilt (not redrafted — Tier 3's fix isn't overwritten).
3. If that still doesn't build, it tries **Tier 1 (Claude Code CLI)** — but only after confirming your subscription billing is safe (see the budget guard note below).
4. If that still doesn't build, it tries **Tier 2 (Gemini API)** — again, only after confirming you're within the free tier.
5. If nothing worked, it stops and writes a **human handoff** instead of guessing further — see step 6.

Each step patches the same file in place, so if you `git diff` mid-run you'll see whatever the current tier's attempt looks like.

### 5. Reading the output

At the end you get two things printed:

```
{"status": "success", "resolved_by": "tier_3"}

Cost report for task 'fix-simd-crash':
  tier_3: 1 call(s), $0.000041 actual [partial: some pricing in tiers.yaml is unverified]
Total actual spend: $0.000041
```

- **`status`**: `"success"` (the file now builds) or `"human_handoff"` (nothing automated could fix it).
- **`resolved_by`**: which tier actually produced the working fix — `null` if it reached human handoff.
- **Cost report**: what this specific task actually cost, broken out per tier. Notice it separates **actual dollars** (DeepSeek, metered) from **notional cost** (what Tier 1 would've cost on metered billing — but it's on your subscription, so the real charge is $0). A `[partial: ...]` tag means some price in `config/tiers.yaml` is still an unverified placeholder — the token counts logged are still exact, only the dollar conversion might be off.

### 6. If it reaches human handoff

Two things get written:
- `logs/escalation_<task_id>.md` — a readable summary: why it gave up, the last build error, how many attempts it made. Read this first.
- `logs/escalations.jsonl` — the same info, one machine-readable line, if you're aggregating across many tasks.

At this point, open the file yourself (or in Antigravity/your normal editor) — nothing further is automated, by design; the pipeline won't guess past this point.

### 7. Checking cost later

You don't have to read it off the run output — it's logged, so you can ask anytime:

```bash
python3 scripts/cost_report.py --task-id fix-simd-crash
```

### Gotchas

- **Re-running the same `--task-id`** picks up wherever the failure count left off (`logs/state/<task_id>.json`). If you want a clean slate, either pick a new task-id or delete that state file.
- **The budget guard can silently skip a tier** — if `ANTHROPIC_API_KEY` is set in your environment, Tier 1 is skipped entirely (printed as `[BUDGET GUARD] Tier 1 skipped: ...`) rather than risk metered billing. Unset it if you want Tier 1 available.
- **Tier 4's model matters for speed.** The configured default (`qwen3-coder:30b-cc`) is slow if it's not actually running on your GPU — see the hardware notes at the bottom of this file. `--tier4-model <name>` lets you override it per-run (e.g. a smaller/faster model while iterating).

## Multi-file projects: `triapi plan` / `triapi dispatch`

Everything above is for fixing one already-broken file. For building something from a natural-language goal (or a `plan.md` you've written) across multiple files, use the `triapi` command instead — it plans first, lets you review/revise before anything is built, then dispatches the approved plan through the same repair engine one file at a time.

### 1. Plan (interactive)

```bash
triapi plan "there is a plan.md in this project, follow it strictly to build the codebase as directed" --project-dir /path/to/project
```

Claude (read-only access to the project) proposes a plan, or asks a clarifying question if the goal is ambiguous. You respond with feedback to revise it, or type `approve` when it's right. Nothing gets built until you approve — getting the plan wrong costs nothing (subscription quota); letting a wrong plan run costs real time and money. This step needs an interactive terminal — it can't run under `--background`.

On approval it prints a run ID and the next command to run.

### 2. Dispatch

```bash
triapi dispatch <run_id>
```

Gemini breaks the approved plan into phases of concrete steps (one file + one verification command each), then each step runs through the same Tier4→3→1→2→handoff pipeline as the standalone workflow above, one at a time, in order. If a step can't be resolved, dispatch stops there (rather than building on top of a broken step) and tells you how to resume once you've looked at it: `triapi dispatch <run_id>` again — the failed step gets retried, not skipped.

For a long dispatch over a flaky SSH connection (e.g. via Tailscale), add `--background`:

```bash
triapi dispatch <run_id> --background
# prints: Check progress: triapi status <run_id>
```

The dispatch keeps running detached even if your SSH session drops.

### 3. Check on it

```bash
triapi status <run_id>      # progress of one run
triapi list                 # all runs, newest state
```

### Git steps in a plan

A plan can include explicit git steps — clone a repo, pull, push/commit — not just file edits. Mention it in your goal (e.g. "clone `git@github.com:you/repo.git`, then...") and Claude will include it as a step if the goal actually calls for it. **Safety rail:** pushing never lands directly on `main`/`master` unless a step explicitly names that branch — otherwise it creates a new `triapi/<name>-<timestamp>` branch instead, so an unattended dispatch can't clobber your primary branch. The plan you approve will say which behavior applies before anything runs.

**Use an SSH remote (`git@github.com:...`), not HTTPS**, for anything that needs to push or pull. Every git command strips credential helpers so a failure is immediate and clear instead of hanging, but that also means HTTPS remotes without a working non-interactive credential setup will simply fail — confirmed in practice in this environment. Cloning a public repo over HTTPS (read-only, no push) works fine either way.

## Debug logging

On by default, written to `logs/triapi.log` (`tail -f logs/triapi.log` to follow live). Covers tier calls, budget-guard decisions, escalation/handoff, and dispatch progress across every script.

```bash
TRIAPI_LOG=0 triapi ...              # disable entirely
TRIAPI_LOG_LEVEL=DEBUG triapi ...    # more verbose (default: INFO)
TRIAPI_LOG_FILE=/tmp/custom.log triapi ...   # different location
```

## Setup

### 1. Python dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Secrets (sops + age)

Secrets live encrypted at `config/secrets.enc.yaml`, safe to commit as ciphertext — never a plaintext `.env`. Requires the `sops` and `age` binaries and a usable age key (this repo's `.sops.yaml` already points at one).

Fill in the real values:

```bash
sops config/secrets.enc.yaml
```

This decrypts to your `$EDITOR`, and re-encrypts automatically on save. Required keys (see `config/secrets.example.yaml` for the template): `deepseek_api_key`, `google_ai_studio_api_key`, `ollama_host`.

### 3. Ollama (Tier 4)

Ollama runs via a systemd **user service**, not a manually-started process:

```bash
systemctl --user start ollama     # start now
systemctl --user status ollama    # check it's running
```

It's already `enabled`, so it starts automatically on login/reboot — you shouldn't normally need to start it by hand. **Do not** run `ollama serve` manually; that bypasses the service's environment configuration (iGPU enablement, flash attention, KV cache quantization) and falls back to slow CPU-only inference.

Pull the models configured in `config/tiers.yaml`'s `tier_4_worker.models` if you don't already have them:

```bash
ollama pull qwen3-coder:30b-cc
ollama pull gpt-oss:20b
```

### 4. Claude Code CLI (Tier 1)

Must be logged in via subscription (Pro/Max), **not** an API key — the pipeline's budget guard actively refuses to use Tier 1 if `ANTHROPIC_API_KEY` is set in the environment, since that would silently switch billing from your subscription to metered API charges.

## Running

### Standalone task

```bash
python3 scripts/orchestrator.py \
  --task-id my-task \
  --description "Fix the compile error" \
  --target path/to/file.cpp \
  --workdir path/to/project \
  --build-cmd "cmake -S . -B build && cmake --build build"
```

Prints a JSON status (`{"status": "success"|"human_handoff", "resolved_by": "tier_4"|"tier_3"|"tier_1"|"tier_2"|null}`) followed by a human-readable cost report showing exactly what was spent, per tier.

### Smoke test

`samples/broken_build/` is a small, real fixture with a genuine C++ compile error (copying a `std::vector<std::unique_ptr<...>>`, illegal since `unique_ptr` isn't copyable):

```bash
python3 scripts/orchestrator.py \
  --task-id smoke-test \
  --description "Fix the compile error in main.cpp" \
  --target main.cpp \
  --workdir samples/broken_build \
  --build-cmd "cmake -S . -B build && cmake --build build"
```

### Checking what a task cost

```bash
python3 scripts/cost_report.py --task-id my-task
```

## What's not built (yet)

- **Jules integration** (Google's async coding-agent CLI) — deferred pending `jules login` (interactive OAuth) and more research on its async session/poll/pull model and GitHub-repo requirement. See `PLAN.md` Phase 4's DEFERRED note for what's already known. If revisited, it would likely become the Tier 2 primary with the current Gemini API as fallback.
- **MCP server** — originally planned (Phase 5) so the Antigravity desktop app could dispatch tasks via MCP, but skipped once Tier 2 became a direct Gemini API call. `orchestrator.py`/`triapi.py` are already complete standalone entry points; nothing currently needs to invoke this pipeline as an MCP tool. Antigravity remains available as an optional manual review surface, just not part of the automated chain.

## Notes on the local hardware setup

This was built and tested against a machine with an AMD Ryzen iGPU (Radeon 780M). Ollama's systemd service (`~/.config/systemd/user/ollama.service`) has:

- `OLLAMA_IGPU_ENABLE=1` / `OLLAMA_VULKAN=1` — Ollama drops integrated GPUs by default; without this it silently falls back to CPU, which is dramatically slower for a 20-30B model.
- `OLLAMA_FLASH_ATTENTION=1` / `OLLAMA_KV_CACHE_TYPE=q8_0` — memory-efficient attention and a quantized KV cache, giving more headroom for larger models/contexts within the GPU's usable memory pool.

If raising the GPU-usable memory ceiling further (the amdgpu driver's GTT allocation, separate from Ollama's own config), that's a kernel module parameter requiring root and a reboot — not something this repo or Ollama controls.
