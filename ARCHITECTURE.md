# Architecture

TriAPI orchestrates a C++/Edge AI debugging workflow across five tiers (four automated repair tiers plus a doc-only librarian tier), cheapest first, so that paid subscription quota (Claude Pro/Max, and previously intended Gemini/Antigravity usage) is reserved for genuinely hard problems instead of routine build failures.

## The five tiers

| Tier | Surface | Cost model | Role |
|---|---|---|---|
| **4 — Worker** | OpenRouter nvidia/nemotron-3.5-lightning:free off-peak, local Ollama qwen2.5-coder:14b-instruct-q6_K during DeepSeek peak hours | OpenRouter API / $0 local | Drafts/fixes code, runs the build, tries repeatedly |
| **3 — Debugger** | agy/gemini-3.1-pro (effort high) off-peak, OpenRouter nvidia/nemotron-3.5-lightning:free during DeepSeek peak hours | Subscription-billed ($0 marginal) off-peak, $0 OpenRouter during DeepSeek peak hours | Harder logic errors Tier 4 couldn't fix |
| **2 — Manager** | DeepSeek v4 Pro off-peak, agy/gemini-3.1-pro (effort high) during DeepSeek peak hours | Metered (prefix-cache discount) off-peak, subscription-billed during DeepSeek peak hours | Second automated repair attempt |
| **1 — Planner** | Claude Code CLI (`claude -p`) | Subscription (Pro/Max quota, $0 marginal) | Strongest, last automated repair attempt before human review (its `tier_1_planner` role, initial `triapi plan` authoring, is separate and always runs first regardless of this repair ordering) |
| **5 — Librarian** | agy/gemini-3.8-flash (effort high) | Subscription-billed, $0 marginal cost | Doc-only repair for *.md/docs/** targets, no fallback chain -- fails fast to human handoff on any failure instead of escalating through Ollama/OpenRouter fallbacks |

If all four repair tiers are exhausted, the task is logged for manual review — nothing tries to call a GUI app programmatically. Tier 1 (Claude) is deliberately ordered last in the repair chain, after Tier 2 (DeepSeek), so subscription quota is spent only on problems the cheaper/free tiers couldn't already resolve.

## Escalation state machine

```
Tier 4 (OpenRouter/Ollama): draft + build
  │
  ├─ success ──────────────────────────────────────────► done
  │
  └─ fails twice (escalation_rules.tier4_to_tier3.threshold)
       │
       ▼
     Tier 3 (agy/OpenRouter): patch file, then Tier 4 does a PLAIN REBUILD
       │  (not a re-draft -- that would overwrite the patch)
       ├─ builds ───────────────────────────────────────► done
       └─ still fails
            │
            ▼
          budget_guard.check_tier2_ok()
            │
            ├─ refused (free-tier limit) ─► skip to Tier 1
            └─ ok
                 ▼
               Tier 2 (DeepSeek/agy): patch file, plain rebuild
                 ├─ builds ─────────────────────────────► done
                 └─ still fails
                      │
                      ▼
                    budget_guard.check_tier1_ok()
                      │
                      ├─ refused (ANTHROPIC_API_KEY set) ─► human handoff
                      └─ ok
                           ▼
                         Tier 1 (Claude Code CLI): patch file, plain rebuild
                           ├─ builds ───────────────────► done
                           └─ still fails ──────────────► human handoff
```

Claude (Tier 1) sits last in this chain, not because it's the weakest tier -- it's the strongest -- but because its subscription quota is the one worth conserving for problems nothing cheaper could resolve.

State (consecutive build-failure count, last stderr) is file-backed at `logs/state/<task_id>.json`, not in-memory, because Tier 4 is designed to run as discrete process invocations rather than one long-lived loop.

Human handoff writes `logs/escalations.jsonl` (one line per escalation) and a readable `logs/escalation_<task_id>.md` summary, and prints a console notice. Except for the Tier 5 doc librarian (which programmatically calls the Antigravity CLI), nothing in this repo calls Antigravity, Jules, or any other GUI/agent tool programmatically — those remain manual review surfaces the user opens themselves.

## Why DeepSeek's cache-hit economics matter

DeepSeek uses automatic disk-based prefix caching: the first call against a given file is a cold cache-miss (full price, `$0.14`/MTok on Flash), but a second call with a byte-identical stable prefix (system instructions + unchanged file contents) hits the cache at a 98% discount (`$0.0028`/MTok). `tier3_escalate.py` is deliberately structured so the large, stable part of the prompt (instructions + file contents) comes first and the small, volatile part (this attempt's stderr) comes last — any instability in the "stable" part (timestamps, non-deterministic ordering) silently kills the hit rate. Verified in Phase 3 testing: cache-hit ratio went from 0% (cold) to ~52% on a repeat call against the same file content, and both real test calls together cost under $0.0001.

**DeepSeek's pricing block in `config/tiers.yaml` is a cache of a fact that will go stale** — verify against DeepSeek's live pricing page periodically. `logs/cost_log.jsonl` always stores raw token counts (not just computed dollars), so historical cost can be recomputed if the pricing on file was wrong at call time. The same caveat applies to Google AI Studio's `free_tier_rpm`/`free_tier_rpd` values in `tiers.yaml`, which are conservative unverified placeholders `budget_guard.py` treats as a hard cap.

## Budget guard — never pay for what should be free

The whole premise of this pipeline is conserving paid quota, so Tier 1 and Tier 2 have pre-flight checks (`scripts/budget_guard.py`) that are hard stops, not warnings:

- **Tier 1**: refuses if `ANTHROPIC_API_KEY` is set in the environment. Its presence routes `claude -p` to metered API billing instead of the Pro/Max subscription — the opposite of the goal. (Also documented: never pass `--bare` to `claude -p`, since that flag forces API-key auth and never reads the subscription OAuth login, silently defeating this guard.)
- **Tier 2**: tracks call timestamps in `logs/gemini_usage.jsonl` and refuses if the next call would exceed the configured free-tier RPM/RPD limits.

`scripts/cost_report.py` aggregates `logs/cost_log.jsonl` per task and clearly separates **actual dollars spent** (DeepSeek, metered) from **notional cost** (what Tier 1 would have cost on metered billing, but was actually covered by the subscription at $0 real cost) — so the user always knows exactly what a task cost.

## Tier 5 — doc librarian and CLI/HTTP timeouts

Tier 5 (`tier_5_librarian`, added 2026-08-24) keeps `*.md`/`docs/**` targets
out of the code-repair tiers above: a single-model dispatcher
(`scripts/librarian_escalate.py`) that makes exactly one call using
`agy/gemini-3.8-flash` (effort high, subscription-billed at $0 marginal cost)
and fails fast to human handoff (`human_handoff`) on any failure -- no
fallback chain at all (the previous multi-provider fallback chain was removed
2026-09-01). Designed to be invoked once per attempt; `consecutive_failures`
persists across external retries so verification thresholds are still
enforced across calls without an internal fallback loop.

For CLI and HTTP calls across the pipeline, timeouts are standardized to prevent
shallow failures: the CLI-subprocess path uses `_CLI_TIMEOUT` (default 600s, commit
`5a6ae01`), while direct HTTP calls use a sibling constant, `_HTTP_TIMEOUT` (default
600s, override via `TRIAPI_HTTP_TIMEOUT`), defined in `scripts/llm_client.py` and used
by both `_call_openai_api()` (the Ollama/OpenRouter-shaped HTTP path) and
`_call_gemini_api()`, following the same "everything configurable" env-var convention
as `_CLI_TIMEOUT`.

## Design decisions that changed during the build

The plan (`PLAN.md`) is the authoritative record of how this design evolved; summarized here:

- **Tier 2 was redesigned from GUI-only (Antigravity desktop app has no CLI/headless mode) to a direct Gemini API call**, once it became clear Google AI Studio exposes a real REST API. Antigravity's role dropped to an optional manual review surface (though the Antigravity CLI was later adopted for the Tier 5 librarian).
- **An MCP server (originally Phase 5) was skipped entirely** once Tier 2 stopped needing Antigravity to dispatch anything — `orchestrator.py` is already a complete, standalone entry point (CLI or importable Python function).
- **Jules (Google's async coding-agent CLI) was considered as a Tier 2 primary** with Gemini API as fallback, but is deferred pending `jules login` (interactive OAuth, not run yet) and more research — see `PLAN.md` Phase 4's DEFERRED note for what's already known (async session/poll/pull model, requires a GitHub-connected repo, likely much slower than the other tiers).
- **Secrets use sops + age, not `.env`** — `config/secrets.enc.yaml` is sops-encrypted ciphertext; only `scripts/secrets_loader.py` (which shells out to `sops -d`) ever sees plaintext values, at runtime, in memory. **As of 2026-08-17 the encrypted file itself is also gitignored/local-only, not committed** — the earlier design committed the ciphertext (encryption alone was judged sufficient), but the convention changed to keep it off the public repo entirely; a full git-history purge (`git filter-repo`) removed the previously-committed ciphertext from every past commit. `config/secrets.example.yaml` (real, safe-to-commit placeholder values) remains the only tracked reference for which keys are needed.

## Local inference: iGPU, not CPU

Ollama runs via the pre-existing systemd user service `~/.config/systemd/user/ollama.service` (already `enabled`, persists across reboots) — **do not** start it manually with `ollama serve`, which won't pick up the service's environment configuration. The service enables the AMD Radeon 780M iGPU via Vulkan (`OLLAMA_IGPU_ENABLE=1`), plus flash attention and `q8_0` KV cache quantization for memory efficiency. See `README.md` for the exact commands.
