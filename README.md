# TriAPI

A 4-tier AI coding pipeline orchestrator: local Ollama → DeepSeek → Claude Code CLI → Gemini API → human review, cheapest first, so paid subscription quota is reserved for genuinely hard problems.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the design, and [PLAN.md](PLAN.md) for the full build history and decisions.

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
- **MCP server** — originally planned (Phase 5) so the Antigravity desktop app could dispatch tasks via MCP, but skipped once Tier 2 became a direct Gemini API call. `orchestrator.py` is already a complete standalone entry point; nothing currently needs to invoke this pipeline as an MCP tool. Antigravity remains available as an optional manual review surface, just not part of the automated chain.

## Notes on the local hardware setup

This was built and tested against a machine with an AMD Ryzen iGPU (Radeon 780M). Ollama's systemd service (`~/.config/systemd/user/ollama.service`) has:

- `OLLAMA_IGPU_ENABLE=1` / `OLLAMA_VULKAN=1` — Ollama drops integrated GPUs by default; without this it silently falls back to CPU, which is dramatically slower for a 20-30B model.
- `OLLAMA_FLASH_ATTENTION=1` / `OLLAMA_KV_CACHE_TYPE=q8_0` — memory-efficient attention and a quantized KV cache, giving more headroom for larger models/contexts within the GPU's usable memory pool.

If raising the GPU-usable memory ceiling further (the amdgpu driver's GTT allocation, separate from Ollama's own config), that's a kernel module parameter requiring root and a reboot — not something this repo or Ollama controls.
