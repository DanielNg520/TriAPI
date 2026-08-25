# Carryover — 2026-08-24 (end of session)

## PAUSED, 2026-08-25 02:40 UTC — user directive: stop burning time on
retries, resume when DeepSeek is next off-peak. Currently inside the
01:00-04:00 UTC peak window (confirmed live via
`budget_guard.check_tier3_peak_hours_ok()`); off-peak resumes at **04:00
UTC**. All work up to this point is committed. Nothing is running.
**Resume order once off-peak:**
1. Retry `triapi dispatch 20260824-164451-2b7635` (OpenRouter fixes run,
   Phase 1 done, Phase 2 item 0 done, Phase 2 item 1 stuck on repeated
   transient Nemotron/OpenRouter errors — see the incident entry below)
   through to completion. Uses the still-working Nemotron/OpenRouter Tier
   2 for its own breakdown — unaffected by the tier changes below since
   those haven't landed yet.
2. THEN draft/dispatch the new-tier-layout plan (see the "FINAL,
   2026-08-25 (v2)" decision below): smoke-test `agy` headless mode +
   new `provider: "agy"` branch in `llm_client.py` +
   `_breakdown_phase_attempt()` provider-branch fix + peak-hours-gate
   generalization to DeepSeek specifically, THEN the actual
   `config/tiers.yaml` reassignment. Also queued and can bundle in: the
   Groq provider addition.

**FINAL, 2026-08-25 (v2) — supersedes the v1 draft immediately below
(kept only for historical trace, DO NOT implement v1): new tier layout
for the rest of the month —**
- **Tier 1** = `stealth/ox-alpha` (OpenRouter), Claude CLI fallback
  (unchanged).
- **Tier 2** = DeepSeek **v4 pro** (real hosted API, `api.deepseek.com`)
  — exact model string not yet verified against DeepSeek's real API
  (current config only has a `flash` model key resolving to
  `deepseek-v4-flash`; confirm the real "pro" model id before wiring,
  don't guess).
- **Tier 3** = `agy` (Antigravity CLI) running **Gemini 3.1 pro, effort
  high**, with `--dangerously-skip-permissions` where needed for
  non-interactive dispatch use. **This is Gemini use, explicitly
  re-authorized by the user for this specific path only** — see the
  scoped-exception note below, [[feedback_no_gemini_allowed_models]] in
  memory needs updating to reflect this once implemented.
- **Tier 4** = qwen, local via Ollama (`qwen2.5-coder:14b-instruct-q6_K`,
  unchanged, kept per the user's own condition "if triapi can run cli
  command" — already true, Tier 1's Claude CLI proves TriAPI can invoke
  CLI tools).
- v1 draft (Tier 3 = local DeepSeek-family model) is fully superseded —
  do not implement it.

**Scoped exception to the standing "no Gemini" rule (2026-08-25):**
Gemini is re-authorized specifically via `agy`'s own OAuth/subscription
auth, confirmed by the user to be a **separate pool from the exhausted
Google AI Studio monthly budget** (`google_ai_studio_api_key`) — but the
user also confirmed **`agy` has its own usage cap and calls will fail
once THAT is exhausted** ("we won't be able to call it if we exhaust the
usage"). This means Tier 3/`agy` needs its own budget-guard-style
protection (detect a quota/limit response and fall through to Tier 2,
the same way `check_tier1_manager_ok()` gates Tier 1 — not a hard crash).
Gemini via the raw API/OpenRouter/`google_ai_studio_api_key` path remains
OFF — this exception covers `agy` only, nothing else.

**Findings from a live (partial) investigation done during the pause —
read-only, no dispatch calls made:**
- `agy` is installed (`/home/dyne/.local/bin/agy`) with a CLI surface
  nearly identical in shape to Claude CLI (`--print`, `--model`,
  `--effort low|medium|high`, `--dangerously-skip-permissions`,
  `--output-format json`, etc.) — a new `provider: "agy"` branch in
  `llm_client.execute_llm()` should closely mirror the existing
  `_call_claude_cli()`.
- An OAuth token already exists at
  `~/.gemini/antigravity-cli/antigravity-oauth-token` — confirmed
  pre-authenticated, no login flow needed.
- **Smoke test DONE and CONFIRMED WORKING, 2026-08-25 (post-off-peak
  resume):** `agy -p "reply pong" --model gemini-3.1-pro --effort low
  --dangerously-skip-permissions --output-format json` returned in 8.66s:
  ```json
  {"conversation_id":"fef077ae-c157-4882-8587-791e1e85a073","status":"SUCCESS","response":"pong\n","duration_seconds":8.657321751,"num_turns":1,"usage":{"input_tokens":20775,"output_tokens":274,"thinking_tokens":273,"cache_read_tokens":0,"total_tokens":21049}}
  ```
  Confirms: (a) `gemini-3.1-pro` is a valid, accepted model string; (b)
  `--output-format json` gives a clean, parseable schema — a new
  `provider: "agy"` branch in `llm_client.execute_llm()` should extract
  `response` for the completion text and can log `usage.*` the same way
  other tiers log token counts; (c) the model uses `thinking_tokens` even
  at `effort low` (Gemini's own reasoning-token behavior, not an `agy`
  quirk) — worth accounting for in cost/token logging if `agy` calls ever
  get cost-tracked. No `agy models` output captured yet (not needed now
  that the exact model string is confirmed directly) — skip that step.

**Required alongside the config change — not optional, per the
"everything configurable" principle below:** `budget_guard.
check_tier3_peak_hours_ok()` is currently named/wired for "Tier 3"
specifically. It must be generalized to key off **the real DeepSeek
hosted API specifically** (`provider == "deepseek"` AND the paid
`api.deepseek.com` endpoint), not a tier-number position — DeepSeek now
sits in the Tier 2 slot, and Tier 3 (Gemini via `agy`) has no DeepSeek
pricing concept at all and must never be gated by this check. Whichever
tier's config resolves to the real DeepSeek API should be the one this
gate protects, found by provider+endpoint match, not by tier name — same
class of fix as `dispatcher._breakdown_phase_attempt()`'s hardcoded
provider branch (see the standing principle below); do both in the same
plan.

Also still needed regardless of which provider ends up in Tier 2:
`dispatcher._breakdown_phase_attempt()` hardcodes `if provider ==
"openrouter": ... else: <google/gemini_fallback path>` — DeepSeek (or
any non-openrouter/non-google provider) as Tier 2 would fall into the
wrong branch. Fix: make the `else` branch only handle `provider ==
"google"` specifically, and route everything else through
`llm_client.execute_llm()` generically (matching `tier2_escalate.py`'s
and `tier3_escalate.py`'s existing pattern — both already dispatch
DeepSeek generically with zero code changes needed on their end).

**Progress update, 2026-08-25: run `20260824-164451-2b7635` (the
OpenRouter-fixes run referenced throughout this file) completed all 4
phases.** All 3 bugs fixed and verified (full suite green, 101 tests).
One item needed a manual doc write instead of automated dispatch: the
Phase 4 PLAN.md-append step exhausted all three `tier_5_librarian`
escalation legs against `PLAN.md` itself — **even with this run's own
phone/IP sanitizer fix already live, the OpenRouter fallback leg still
403'd**, meaning something else in `PLAN.md`'s ~189KB of content trips
the content filter, not yet isolated (worth a closer look — possibly
another digit-shaped pattern not yet covered, or filter behavior keyed
on sheer volume/repetition rather than a specific pattern). Written by
hand instead (PLAN.md's own Phase 30 entry) per the standing docs
exception — **but the item's description also asked to shrink PLAN.md
back under the 73,728-char ceiling, which was NOT done** (it's now
192,722 chars, even larger) — that's a much bigger job, already covered
by the separately-queued "consolidate historical PLAN.md content out of
target-repo docs" follow-on (Tier 5 exists now, so that follow-on can
actually be planned/dispatched whenever it's picked up). Don't treat this
run's PLAN.md item as having addressed the size problem — it only added
the Phase 30 summary.

**Sequencing:** (1) ~~`agy` smoke test~~ **DONE, confirmed working** (see
above). Still to do: (2) new `provider: "agy"` branch in `llm_client.py`
+ its own budget-guard/quota-exhaustion handling, (3)
`_breakdown_phase_attempt()` provider-branch fix, (4) peak-hours-gate
generalization to DeepSeek specifically — all using the still-functional
current Tier 2 config (Nemotron/OpenRouter) to do that one
planning/breakdown call — only flip `config/tiers.yaml`'s tier
assignments to the FINAL (v2) layout above after those land and test
clean. Bundle with the Groq provider addition if convenient (all touch
`llm_client.py`/`config/tiers.yaml` in the same area), or run
separately — user's call. **This whole plan (steps 2-4 + config flip) is
the next thing to draft/dispatch via `triapi plan`.**

**Two more items queued, 2026-08-25 (after the above lands — don't bundle
into it, run as a follow-on plan):**
1. **Add `agy` as a `tier_5_librarian` fallback leg, specifically motivated
   by its ~1M-token context window.** Directly solves the recurring
   PLAN.md-doc-update problem hit twice tonight (local Ollama legs time
   out on ~189-192KB files; the OpenRouter fallback leg 403s on
   PLAN.md-scale content even with the phone/IP sanitizer fix). `agy`
   goes through neither path — no OpenRouter content filter, no local
   context-window ceiling — so it should be able to handle large docs
   directly. Exact placement in the escalation order (alongside
   `fallback_openrouter`, or reserved specifically for oversized docs) is
   an implementation-design question. Depends on the `provider: "agy"`
   branch from the in-flight plan landing first.
2. **Every tier's fallback mechanism should be as configurable
   (individually on/off) as the tiers themselves.** Currently fallback
   configurability is inconsistent: `tier_2_manager.fallback_chain` is a
   plain list (no per-entry enable/disable), `tier_5_librarian`'s
   `fallback_local`/`fallback_openrouter`/(new `fallback_agy`) legs have
   no toggle at all, `tier_1_planner`'s fallback to `tier_1_manager` is
   hardcoded in `planner.py` with no config gate. User wants every
   fallback leg, for every tier, individually configurable (turn on/off)
   the same way `tier_1_manager.enabled`/`jules_tester.enabled` already
   work for whole tiers. This is the natural extension of the
   already-queued "named backend registry" architecture item (see the
   "Architecture items" list further down this file) — worth designing
   together rather than as two separate passes, since both are about
   making the tier/fallback graph fully config-driven instead of
   partially hardcoded per call site.

<details>
<summary>v1 draft, superseded, kept for historical trace only</summary>

Tier 2 = DeepSeek (real API), Tier 3 = local DeepSeek-family model
(`deepseek-coder-v2:16b` or `deepseek-r1:14b`, avoiding `:32b` variants
per this box's documented iGPU OOM history), Tier 4 = local qwen
(unchanged). Fully replaced by the `agy`/Gemini-3.1-pro-for-Tier-3
version above — do not implement this v1 shape.
</details>

**Standing principle added, 2026-08-25 (user's own words): "Every single
feature of TriAPI pipeline has to be highly configurable. If there is
[a] hardcode[d] path then it needs to be fixed."** See
[[feedback_everything_configurable_no_hardcoding]] in memory. Did a
read-only audit of every `provider ==`/hardcoded-tier-name branch across
`scripts/*.py` while paused (no API calls) to check for other instances
beyond the already-queued `_breakdown_phase_attempt()` one: `tier1/2/3_
escalate.py` all already dispatch generically via
`llm_client.execute_llm(provider=tier.get("provider", ...))` — correctly
reassignable. `planner.py`'s `provider == "cli"` branch and `triapi.py`'s
`tier_4_worker...== "ollama"` checks are legitimately provider-specific
behavior (subprocess invocation; local-Ollama-lifecycle management), not
reassignment-breaking hardcodes. `librarian_escalate.py`'s
openrouter/ollama endpoint resolution is inherent to `tier_5_librarian`'s
fixed two-leg schema, already audited correct by the paused plan's Phase
3. **No new hardcoded-path bugs found beyond the one already queued.**

**New request queued while paused, 2026-08-25 (do not act on this until
resume — starting a `triapi plan` now would itself burn OpenRouter's
shared rate-limit budget, which is exactly what we're waiting out):** add
Groq as a new TriAPI provider, model `qwen/qwen3.6-27b`, with these limits
(feed into `config/tiers.yaml`'s pricing/rate-limit block the same way
`tier_2_manager`/`tier_3_debugger` record theirs, and wire a
`budget_guard` check for it the same way `check_tier3_peak_hours_ok()`/
`check_tier2_ok()` gate their tiers):
- RPM: 30
- RPD: 1,000
- TPM (tokens/min): 8,000
- TPS: 200,000 (as given by the user — confirm which unit this actually
  is against Groq's real docs before wiring a hard gate on it; 200K
  tokens/sec is implausibly high next to an 8K TPM cap, so this is more
  likely tokens/day or a context-window figure — don't guess, verify
  against Groq's console/docs for this exact model first.)

This is real new-provider code (a new `provider: "groq"` branch in
`llm_client.execute_llm()`, likely alongside `_call_openai_api()` since
Groq's API is OpenAI-compatible, plus config wiring and a budget-guard
check) — per the standing "never do TriAPI's job" rule this goes through
`triapi plan`/`dispatch` against TriAPI's own repo once we resume, not
hand-coded. **`groq_api_key` already exists (encrypted) in
`config/secrets.enc.yaml`** — confirmed by grep, no need for the plan to
add a new secret, just consume the existing `api_key_secret: groq_api_key`
reference. It's missing from `secrets.example.yaml`'s template though
(undocumented gap, unrelated to this feature) — worth a one-line addition
to that template while this item is in progress anyway. Worth noting:
Groq's rate limits are its own separate pool,
not shared with OpenRouter's 20 RPM/1000 RPD — this may be exactly why the
user wants it added (a way to route some tier work off the OpenRouter
shared-budget bottleneck found earlier tonight, see
[[project_openrouter_shared_rate_limit]] in memory). Where this model
should actually slot into the tier ladder (new tier? alternate for an
existing one?) wasn't specified — ask before assuming a slot when this is
picked up, rather than guessing.

**Standing rule for this file: stay brief.** Only what's needed to resume
the *next* session goes here. Finished-work narrative, per-round findings,
and "what happened" writeups belong in `PLAN.md` (this repo's permanent
build-history/decisions record), never here. Fold an item out of this file
into `PLAN.md` the moment it's resolved, in the same edit — don't leave it
lingering here in past tense. Full history through 2026-08-19 lives in
`PLAN.md`'s "Session Carryover Log" section.

**Read this first in a new session.** Then `AGENTS.md` for the file/dir
index, `AGENT_GUIDE.md` for the operating manual (what's safe to hand-edit
vs. must route through `triapi plan`/`dispatch`).

**Standing rule (2026-08-24): TriAPI's own docs never mention a specific
target repo by name**, whichever repo it dispatches against. A TriAPI-internal bug found via a
target-repo run still gets documented here (generically), but the
target-repo's own status/context goes into that repo's own docs instead —
see `feedback_target_repo_docs_stay_in_target_repo` memory.

## STOP — standing rule (2026-08-25): allowed models list, narrowed after
a real billing incident. Every tier's model MUST be one of: (1) an
OpenRouter model the user has explicitly indicated is free/approved
(currently: `stealth/ox-alpha`, `nvidia/nemotron-3-ultra-550b-a55b:free`,
`dots-studio/dots-3-note-preview:free` — do not add another OpenRouter
model to any tier without asking first, even a `:free`-suffixed one), (2)
DeepSeek (`api.deepseek.com` direct), or (3) Claude Code CLI. **No Gemini
calls in any form** — not via OpenRouter, not via the direct Google AI
Studio path — until the user explicitly re-enables it. **Exception,
confirmed by the user 2026-08-25: Jules (`jules_tester`) stays enabled.**
It runs on Gemini 3 Pro under the hood too, but its usage is metered
against its own separate daily task cap (`daily_task_limit`), not the
billing-enabled Google Cloud project that caused the incident below — a
different exposure, so the blanket "no Gemini" rule doesn't reach it.
(Briefly set to `enabled: false` in this same session before the user
clarified this — now back to `true`.)

**Situational exception, 2026-08-25 (user's own words):** until Tier 5 (or
a dedicated filter) reliably sanitizes what goes out in OpenRouter calls,
the user has authorized doing the librarian/sanitizer's job by hand as a
one-off carve-out — i.e. when preparing content that will flow through an
OpenRouter-routed tier, reviewing/redacting it manually first is fine, not
a violation of the standing "never do TriAPI's job" rule. This is scoped
narrowly to that one task (pre-filtering OpenRouter-bound content), not a
general license to hand-write TriAPI features.

## Incident, 2026-08-25: unauthorized OpenRouter billing from a Gemini
fallback-chain bug — root cause found and disabled (config only, not yet
dispatched as a proper fix)

User reported real financial harm: 36 OpenRouter content-filter blocks
today (the already-queued phone-number-false-positive bug, unrelated) PLUS
**unauthorized OpenRouter billing from Gemini calls**, on top of an
already-exhausted Google AI Studio monthly budget. Root cause confirmed by
reading the code (not guessed): `config/tiers.yaml`'s
`tier_2_manager.fallback_chain` held 4 Gemini model names
(`gemini-3.5-flash` etc.), intended for the separate Google-AI-Studio-direct
`gemini_fallback.py` path, but **two call sites instead sent those names
through `tier_2_manager`'s own `provider: openrouter`**:
- `tier2_escalate.py` (real repair fallback) tries Nemotron first, then
  walks the Gemini-named chain through OpenRouter on 429/403 — every one of
  those was actually an OpenRouter-billed call to a paid model, not the
  free/direct Google path the names implied.
- `dispatcher.breakdown_phase()` (plan breakdown, called every dispatch)
  is worse: `models = [model] if model else (tier2.get("fallback_chain") or
  [default_model])` — with a non-empty `fallback_chain`, this **skipped the
  free Nemotron default entirely** and used the Gemini chain as its primary
  model list, unconditionally, on every single phase breakdown. This has
  likely been the actual behavior since Tier 2 was last reconfigured, not
  just today.

**Fix applied directly (config-only, permitted without dispatch per the
docs/config carve-out, and urgent given ongoing financial exposure):**
`tier_2_manager.fallback_chain` set to `[]` in `config/tiers.yaml`.
Verified live: `load_tiers()["tier_2_manager"]["fallback_chain"] == []`,
both Tier 2 call sites now correctly fall through to Nemotron
(`nvidia/nemotron-3-ultra-550b-a55b:free`) only, and the full regression
suite (95 + 22 tests) still passes. No dispatch process was running at the
time this was found — nothing further was charged after the fix landed.
(`jules_tester.enabled` was also briefly set to `false` in this same
session, then reverted to `true` per the user's clarification above —
Jules is a separate, differently-metered exposure, not part of this
incident.)

**Not yet done — needs a real `triapi plan`/dispatch pass once Gemini use
is re-authorized (don't dispatch anything Gemini-touching before then, per
the STOP rule above):** decide the actual intended design (should Tier 2
ever fall back to Gemini at all, and if so, through which path/provider?)
and either restore a corrected `fallback_chain` wired through
`gemini_fallback.py`'s direct endpoint, or remove the dead
`gemini_fallback.py`/`gemini_fallback:` config block entirely if Gemini
should never come back into this tier. Also worth an explicit regression
test asserting no tier's configured chain can send a non-allowlisted model
through `provider: openrouter` without the
user's sign-off, so a future config edit can't silently reintroduce this.

## Incident evidence, 2026-08-25: OpenRouter's own "Blocked Requests"
dashboard (user-provided screenshot) — 36 total blocked today, broken down
by category: **PHONE 18, EMAIL 12, IP ADDRESS 6.** Two scope corrections
for the already-queued Phase 1 item (`_PHONE_LIKE_RE` in
`llm_client._sanitize_for_openrouter_content_filter()`, run
`20260824-164451-2b7635`, currently paused) before it's dispatched again:
1. **IP-address case is entirely unhandled** — needs its own regex/redact
   case alongside the phone one (IPv4-shaped, careful not to mangle
   version strings, hex hashes, or other dotted-number content).
2. **Email blocks (12) are non-trivial despite `_EMAIL_LIKE_RE` already
   existing** (Phase 26) and every known OpenRouter call site routing
   through `execute_llm()`'s sanitizer (`probe_models()`,
   `tier2_escalate.py`, `dispatcher.breakdown_phase()`'s openrouter
   branch, `librarian_escalate.py`'s fallback leg all confirmed to call
   `execute_llm`, which applies it) — plausible this is just historical
   (pre-Phase-26) volume in the same dashboard window, but worth an
   explicit audit before assuming the existing email case is complete:
   confirm no OpenRouter request body is ever built without going through
   `_sanitize_for_openrouter_content_filter()` first.
   Amend Phase 1's item description to cover both before dispatching.
   **DONE 2026-08-25: both items amended directly in the run's persisted
   breakdown JSON (item descriptions, not code) and dispatched — both
   landed clean via Tier 4** (`_IP_LIKE_RE` + audit added to
   `llm_client.py`, tests added). Phase 2 item 0 (dispatcher peak-hours
   dedup) also landed clean via Tier 4. Phase 2 item 1 then crashed the
   whole run on a genuine transient Nvidia 502 on Tier 2's free Nemotron
   model (`Upstream error from Nvidia: Service temporarily overloaded`) —
   **new finding: Tier 2 has no retry tolerance for a single transient
   upstream blip**, unlike `probe_models()`'s `_probe_with_retry()` (added
   2026-08-24 for exactly this class of issue). TriAPI's self-fix system
   auto-captured this crash and drafted a fix, queued as self-fix run
   `20260824-190921-1fc713` — let it sit for review, don't hand-patch
   `tier2_escalate.py`, don't auto-approve without reading it first.
   **Second, same-class crash on retry:** resumed dispatch, Phase 2 item 1
   crashed again — this time Tier 4 (`dots-studio/dots-3-note-preview:free`)
   hit a transient `{"message": "Provider returned error", "code": 400}`
   and orchestrator logged "crashing pipeline" instead of falling through
   to Tier 3. **Third crash on the next retry: Tier 2/Nemotron hit the
   identical 502 upstream-overload error again** — three occurrences of
   the same Nemotron 502 across three resumes in ~20 minutes now looks
   like sustained upstream instability on that free backend tonight, not
   a one-off blip; self-fix auto-drafted a SECOND duplicate fix for the
   same crash, `20260824-192405-f29d2c` (skip/dedupe against
   `1fc713` when reviewing, same as the existing 429-probe duplicates
   below). **Broader finding worth its own queued item**: a single
   transient upstream 4xx/5xx from a free model crashing the whole
   dispatch instead of retrying in-place or falling through the tier
   ladder has now hit both Tier 2 and Tier 4 independently this session —
   likely a systemic gap in `orchestrator.run_task()`'s error handling
   around `execute_llm()` calls generally (missing the same
   `_probe_with_retry()`-style tolerance `probe_models()` got
   2026-08-24), not several unrelated bugs. Worth folding into whichever
   self-fix run above actually gets approved, scoped broadly rather than
   just the one call site it was captured from.
   **Given three Nemotron 502s in ~20 minutes, back off longer (15-20 min)
   before the next `triapi dispatch 20260824-164451-2b7635` retry** rather
   than resuming immediately again — let the upstream backend recover.
   **Correction from the user, 2026-08-25: all OpenRouter models (free and
   paid) share ONE account-wide rate-limit pool — 20 RPM / 1000 RPD, not a
   per-model allowance.** This reframes tonight's cascade: `probe_models()`
   alone fires 4+ OpenRouter calls per dispatch resume (tier_5, tier_4,
   tier_2, tier_1_planner), so a handful of resumes in quick succession,
   plus real tier work, can burn through the shared 20 RPM ceiling on its
   own — the repeated `tier_1_planner` 429s and the Nemotron "502
   Upstream overloaded" messages may both really be the *same* shared-pool
   exhaustion wearing different error faces, not two unrelated upstream
   issues. Strengthens the case for the already-queued
   `probe_models()`-scoping fix (folded into the router/backend-registry
   architecture item) — it isn't just faster, it directly reduces pressure
   on a budget every tier draws from. A 60s-ish gap should be enough for
   the RPM side to clear on its own; if failures persist past that, it's
   more likely the 1000 RPD daily cap (account-wide, cumulative across the
   whole day/session, not per-tier) — which only clears at day rollover,
   so further short retries would be pointless in that case. Worth adding
   an account-wide (not per-tier) RPM/RPD budget tracker alongside
   `budget_guard.py`'s existing per-tier checks, queued as part of the
   same architecture-item scope, not hand-built.

## Standing rule (2026-08-25): explicit tier defaults, user-specified
after the billing incident, to be enforced going forward — **Tier 1 =
`stealth/ox-alpha` (OpenRouter free), Tier 2 = Nemotron (OpenRouter free)
— both already correct in `config/tiers.yaml`, no change needed.** For
Tier 3/4, the user wants a **peak-hours-conditional swap**, confirmed by
the user to be built via `triapi plan`/`dispatch` against TriAPI's own
repo, NOT hand-coded (their explicit choice when asked). Design, refined
by the user 2026-08-25 (startup-probe form, not a per-call gate):

- **At TriAPI process startup**, probe the current Beijing time
  (`Asia/Shanghai`) once, compute how long remains until the next off-peak
  window per `budget_guard`'s existing peak-window logic (weekday check +
  the two configured UTC windows in `tier_3_debugger.peak_hours_utc`), and
  set an **in-memory countdown/lockout** for that duration. This is
  explicitly startup-scoped, not persisted: "the count down dies when
  triapi shutdown" — a fresh process re-probes from scratch, it does not
  resume a saved countdown.
- **While the lockout is active, DeepSeek is blocked from entering the
  pipeline entirely** — not just skipped-with-a-warning like the current
  `check_tier3_peak_hours_ok()` gate, but structurally prevented from
  being selected as Tier 3 for the run's duration.
- **While locked out, Tier 3 and Tier 4 both promote/reassign
  automatically:** Tier 3 = notes3 (`dots-studio/dots-3-note-preview:free`,
  today's static Tier 4 default), Tier 4 = local Ollama qwen
  (`qwen2.5-coder`, already configured as `ollama_fallback`'s default).
- **Off-peak (no lockout active):** Tier 3 = DeepSeek, Tier 4 = notes3 —
  today's current static config, unchanged.

This needs a startup hook (compute the lockout once when `triapi` starts,
not per-call), an in-memory timer/flag threaded through to wherever
Tier 3/4 are selected (`tier3_escalate.py`, `tier4_worker.py`,
`probe_models()`), and default_model swapping at that selection point —
none of which exists today (`tier3_escalate.py`/`tier4_worker.py` currently
have no such branching, and `check_tier3_peak_hours_ok()` is a per-call
advisory/skip gate, not a startup lockout). Draft this as its own
`triapi plan` once the current OpenRouter-fixes run
(`20260824-164451-2b7635`) finishes — don't bundle it into that run, it's
unrelated in scope.

## Current state

- **`openrouter` branch merged into `main` (2026-08-23), commit `47cddb4`,
  NOT pushed to any remote.** All 4 tiers are config-driven/hot-swappable
  through `config/tiers.yaml` + `llm_client.py`'s single `execute_llm()`
  dispatch point, with a working `probe_models()` pre-flight gate and
  consistent fail-fast across all 4 tiers — confirmed by design and by a
  real live swap the same session (below): any tier slot can hold any
  provider (API, local model, or CLI), not just its original assignment.
  **Current tier assignments (updated 2026-08-24):** Tier 1 repair = Claude
  CLI (`claude-sonnet-5`, effort `high`, `tier_1_manager`); Tier 1 planning
  = OpenRouter `stealth/ox-alpha` (`tier_1_planner`), falling back to Tier
  1's own CLI config on any failure; Tier 2 = Nemotron 3 via OpenRouter;
  **Tier 3 = real DeepSeek API directly** (`api.deepseek.com`, model
  `deepseek-chat` → resolves to `deepseek-v4-flash`), swapped from
  OpenRouter's dots-3-note-preview; **Tier 4 = notes3 (dots-3-note-preview)
  via OpenRouter**, swapped from local Ollama qwen2.5-coder — this also
  sidesteps Phase 25's genuine local-Ollama Tier 4 timeout issue, since
  dispatch no longer depends on local Ollama being responsive at all. Both
  swaps live-probed OK and full suite 141/141 passing post-swap. Full
  bug-by-bug detail on the original merge (8 real bugs found and fixed
  pre-merge, including one that had fully bricked `triapi plan`) is in
  `PLAN.md`'s "Phase 21" entry.
- The `openrouter` branch itself still exists locally, now fully merged —
  safe to delete (`git branch -d openrouter`) once confirmed not needed for
  anything else; not done yet, not urgent.
- **Queue items #1-#6 from the 2026-08-19 carryover, and the 2026-08-20
  queue drain**, are done — see `PLAN.md` for that history if ever needed;
  nothing outstanding from either.
- **Four real bugs found/fixed 2026-08-23/24** — see `PLAN.md` Phases
  23/24/25/26: swallowed error reason on Tier 1/2 failure; a dispatcher
  mechanism gotcha where mid-run item insertion can collide `task_id`s with
  stale state (workaround documented, not yet a code fix); a genuine Tier 4
  timeout never falling through to Tier 3/2/1 (workaround: `skip_tier4` on
  the stuck item); OpenRouter's content-filter fix (Phase 21) generalized
  from the planner to every OpenRouter-routed tier.
- **Stale, superseded self-fix drafts: `20260823-204035-0c929e` and
  `20260823-204847-f50c6c`** (auto-captured `RuntimeError`s from
  `cmd_dispatch` crashing) — both are transient OpenRouter flakiness
  (content-filter 403, then a rate-limit 429), not real code bugs; the
  403 one is the exact thing Phase 26 already fixed by hand, the 429 one
  is just rate-limit pressure from resuming this run too many times too
  quickly in one evening. Do not approve/dispatch either. Safe to leave
  queued or clean up next time `triapi self-fix list`'s backlog gets
  reviewed.
- **Pacing lesson:** resumed the email-routing run 5+ times in under an
  hour tonight, each doing a fresh `probe_models()` pre-flight OpenRouter
  call — eventually tripped a real `429`. Next resume attempt should wait
  a few minutes rather than retry immediately.
- **Architecture change queued, 2026-08-24: a named backend registry so
  tier↔model reassignment never touches each tier's own config block.**
  Today's Tier 3/4 swap (below) worked, but required rewriting each tier's
  whole `provider`/`endpoint`/`api_key_secret`/`models` block by hand in
  `tiers.yaml` — exactly the "hardcoded to the tier" pattern the user wants
  gone. Target design: a `backends:` section defining each reusable model
  config once (name → provider/endpoint/model/api_key_secret/pricing), and
  every `tier_N_*` block reduced to a single reference (e.g. `backend:
  deepseek_flash`) plus tier-specific fields that stay per-tier (role,
  automatable, peak_hours_utc, build_commands). Reassigning a tier becomes
  a one-line pointer change, never a block rewrite. Touches
  `config/tiers.yaml`'s schema, `config_loader.py`'s validation, and every
  `tier*_escalate.py`/`tier4_worker.py`/`llm_client.probe_models()` call
  site that currently reads a tier's fields directly. **This is TriAPI
  self-feature work — draft via `triapi plan --project-dir` against this
  repo and dispatch it, don't hand-build it.**
- **Second architecture feature queued, 2026-08-24 (user's own framing):
  a complexity-aware router/orchestrator ahead of the tier ladder.**
  Currently every dispatched item walks the same escalation path
  regardless of shape. Wanted: something that reads the dispatch
  prompt/plan upfront and decides how much machinery a given task actually
  needs — a large multi-phase plan gets the full Tier 4→3→2→1 ladder as
  today, but something shaped like "just reconcile/update these docs"
  routes straight to Tier 5 (the librarian, once built) without walking
  the code-repair tiers at all. User's own words: "so TriAPI will work in
  the most efficient way." Depends on Tier 5 existing first (see the
  librarian entry below) and probably the backend-registry change above
  too (a router needs a clean way to address "which tier/backend" as a
  first-class concept). **Also TriAPI self-feature work — plan and
  dispatch it through the pipeline once Tier 5 lands, don't hand-build.**
- **Found, NOT fixed (per the new "let TriAPI fix itself" rule — queue it,
  don't hand-patch), 2026-08-24: a stale duplicate of the DeepSeek
  peak-hours check.** New policy: Sat/Sun Beijing time is off-peak all day.
  `budget_guard.check_tier3_peak_hours_ok()` implements this correctly
  (converts to `Asia/Shanghai`, checks `weekday() in (5, 6)` before the
  hourly windows) and is the one that actually gates Tier 3 dispatch — that
  part is right. But `dispatcher._is_deepseek_peak_hours()` is a separate,
  older duplicate (advisory-only, just logs a "may be expensive" warning in
  `handle_fix_forward`) that only checks a single hardcoded `06:00-10:00
  UTC` window, doesn't read `tiers.yaml`'s actual two-window list, and has
  no weekend exception at all — so it'll wrongly warn about peak pricing on
  a weekend. Route the fix through `triapi self-fix` or a normal plan
  against this repo: `dispatcher.py` should probably just call
  `budget_guard.check_tier3_peak_hours_ok()` instead of maintaining its own
  separate/stale copy.
- **Self-fix `20260823-213048-a51c20` approved and dispatched 2026-08-25** —
  `edit_blocks.apply_edit_blocks()` crash on `response_text is None` (see
  prior entry, now historical). Phase 2's core guard landed clean (Tier 4,
  `scripts/edit_blocks.py`). Phase 3's first item (`tier3_escalate.py`) hit
  a **new, confirmed-live systemic bug while dispatching** — queued below.
  Workaround applied to unblock this run: dropped `logs/triapi.log` and
  `logs/cost_log.jsonl` from that item's `context_files` (they weren't load-
  bearing for the edit) and set `skip_tier4: true`. If this run is still
  mid-flight next session, `triapi dispatch 20260823-213048-a51c20` resumes
  it; if it finished, check `PLAN.md` for the outcome instead of resuming.
- **New systemic bug found 2026-08-25, NOT fixed (queue it, don't hand-
  patch — same rule as the peak-hours duplicate above): OpenRouter's content
  filter false-positives on `[PHONE]` for TriAPI's own log files, and this
  can wedge an item's entire escalation ladder, not just Tier 4.** Repro'd
  live: feeding `logs/triapi.log` + `logs/cost_log.jsonl` as Tier 4 context
  for a real dispatch item got a `403 Client Error: Forbidden`; direct curl
  isolated the cause to `{"error":{"message":"Request blocked by content
  filter: [PHONE]", ...}}` — a false positive, almost certainly one of the
  many digit-heavy `run_id`/`task_id`/timestamp strings in those logs
  (e.g. `20260810-092820-8cbeaf`) pattern-matching as a phone number, not
  an actual phone number. Phase 26's sanitizer (`llm_client.
  _sanitize_for_openrouter_content_filter()`) only strips email-shaped
  tokens — it has no phone-number case, so it didn't catch this. **Worse
  than Phase 26's finding**: because `context_blob` is folded into the same
  `prompt` string sent to every OpenRouter-routed tier, this item's Tier 4
  failure fell through (via `skip_tier4`) straight into Tier 3 → Tier 2,
  and Tier 2 (Nemotron, OpenRouter) hit the *same* `[PHONE]` block on every
  candidate in its `fallback_chain` too, so the whole ladder failed and
  crashed the run (`RuntimeError: Tier 2 failed: ...403...`) rather than
  landing in `human_handoff` with a clear reason. Route the fix through
  `triapi self-fix`/a normal plan against this repo: extend
  `_sanitize_for_openrouter_content_filter()` with a phone-number-shaped
  regex case (careful not to also mangle legitimate digit-heavy content
  like hex hashes or line numbers), and consider whether `logs/*.log`/
  `logs/*.jsonl` should even be eligible as raw LLM context at all — they
  are internal operational logs, not source/docs, and stuffing them
  unsanitized into a prompt is the root cause both here and in Phase 26.

## Current state (addendum, 2026-08-24 continued)

- **Librarian improvements run `20260824-132910-a7b69b` is `stopped_on_failure`
  after Phase 1 (both items landed clean, Tier 4) and Phase 2's single item
  (`scripts/doc_staleness.py`) hit `human_handoff` after exhausting Tier 4 →
  3 → 2 → 1 — all four independently produced the same bug.** Root cause
  (confirmed by reading the generated file, not hand-fixed): the epoch-
  collision handling in `should_skip_model_call()`'s scan loop treats "a
  commit landed at the same UNIX-epoch second as the doc's last commit" as
  "this commit touched the doc" and discards it (`if current_epoch ==
  doc_commit_epoch: continue`). Git's commit timestamp has 1-second
  granularity, so two *different* commits made in quick succession — the
  test harness's own `git commit` calls, and realistically TriAPI's own
  automated commits too — can share an epoch even though only one touched
  the doc. That silently drops a genuine non-doc commit from the scan,
  leaving `found_non_doc_commit = False` and forcing permanent fail-open
  (never skips the model call) in exactly the fast-commit scenario the
  pre-check exists to handle. Fail-open itself is safe (matches spec:
  "ANY ... unexpected ... -> fail open"), so this isn't unsafe, just makes
  the whole feature inert whenever commits are fast/batched. Fix should
  distinguish "commit touched the doc" (check the file list, not the
  epoch) from "commit epoch ties the doc's epoch" — the same-epoch guard
  needs to check membership of `relpath_str` in that commit's file list,
  not epoch equality. Route via `triapi plan`/self-fix against
  `scripts/doc_staleness.py`, don't hand-patch. Once fixed, resume/retry
  run `20260824-132910-a7b69b`'s Phase 2 item (still awaiting Phases 3-9:
  wiring, tests, PLAN.md/AGENTS.md updates).

## Current state (addendum 2, 2026-08-24 continued)

- **Run `20260824-132910-a7b69b` resumed past the Phase 2 `doc_staleness.py`
  bug on retry (a fresh Tier 1/Claude attempt got it right this time,
  6/9 steps done) and hit a NEW `human_handoff` at Phase 4** (regression
  tests in `tests/test_tier5_librarian.py`). Root cause here is a plan-
  breakdown gap, not a code bug: **two pre-existing tests —
  `test_advisory_no_change_verdict_returns_changed_false_without_writing`
  and `test_success_path_lands_via_edit_block_with_local_billing` — still
  mock the OLD JSON-envelope response format (`'{"stale": false}'`) that
  Phase 1 deliberately eliminated.** Against the new single-call plain-
  text `run()`, that mocked JSON string correctly fails to parse as either
  `FRESH` or a SEARCH/REPLACE block, so `run()` (correctly, per the new
  design) escalates through the full chain and the test's
  `execute_llm.assert_called_once()` fails (actually called 3x). Phase
  4's item description only said to *add* new single-call-flow tests, not
  to update/remove these two now-incompatible old ones — that's the gap.
  4 escalation attempts (Tier 4→3→2→1) apparently thrashed on this,
  producing one genuinely broken syntax (`SyntaxError: unterminated
  string literal` at old line 358) that a later attempt already
  overwrote — current file parses clean (`ast.parse` succeeds), so no
  cleanup needed there. Resumed dispatch again after documenting this;
  if it's still stuck next session, the fix is either (a) let a tier
  finally rewrite those two tests for the new format on its own, or (b)
  if it keeps thrashing, a small follow-up `triapi plan` item explicitly
  naming those two tests for update would remove the ambiguity — draft
  via the pipeline, don't hand-edit the test file directly.

## Current state (addendum 3, 2026-08-24 continued)

- **New systemic bug found 2026-08-24, NOT fixed (queue it, don't hand-
  patch): `orchestrator.run_task()`'s Tier 4→3→2→1 escalation can declare
  `human_handoff` even when the FINAL tier attempt's write genuinely
  satisfies the item's own `build_cmd`.** Confirmed live on run
  `20260824-132910-a7b69b`'s Phase 4 item (`tests/test_tier5_librarian.py`
  regression tests): after sharpening the item's description (see prior
  addendum) and resuming, the run again reported `human_handoff` with a
  "Tier 4 -> Tier 3 -> Tier 2 -> Tier 1" exhaustion reason — but the file
  actually left on disk was completely correct: re-running the exact
  recorded `build_cmd` (`PYTHONPATH=. python3 -m unittest
  tests.test_tier5_librarian -v`) by hand passed clean, 14/14 tests green,
  including both previously-stale tests now correctly updated. So the
  last tier's write did succeed against its own acceptance check, but
  `run_task`'s own bookkeeping still escalated to human_handoff instead of
  returning success — most likely a consecutive-failure-threshold check
  firing on a stale counter without re-validating the final attempt's
  actual build result, similar in spirit to the epoch-collision bug found
  earlier this session but in a different module (root cause not yet
  isolated to a specific line — needs a read through `tier1_escalate.py`'s
  retry loop, or wherever the final tier's success/failure gets folded
  into the human_handoff decision). **Workaround applied this session
  (with explicit user sign-off, since it required overriding the run's
  own recorded verdict): manually corrected `logs/runs/
  20260824-132910-a7b69b.json`'s last result entry from `human_handoff` to
  `success` (resolved_by: tier_1, content_hash recomputed via
  `regression_guard.hash_file()`), since the target file was independently
  re-verified against its own build_cmd first.** Route the actual fix
  through `triapi plan`/self-fix against `scripts/orchestrator.py` (and
  whichever `tierN_escalate.py` turns out to hold the stale-counter logic)
  once this run completes — don't hand-patch.

## Current state (addendum 4, 2026-08-24 continued)

- **Run `20260824-132910-a7b69b` reached 8/9 (Phases 1-4 fully done and
  verified — full regression gate green) and stalled on Phase 5's PLAN.md
  update.** All three of `tier_5_librarian`'s escalation legs failed:
  local legs (`mistral-small`/Ollama fallback) can't fit `PLAN.md` at
  188,334 chars (well over Tier 4's 73,728-char ceiling — same standing
  ceiling problem as [[feedback_no_files_at_tier4_ceiling]]), and the
  OpenRouter fallback leg hit the already-queued `403 Forbidden` content-
  filter false-positive (see priority #2 in "Next up" below) — this is a
  second, independent live confirmation of that bug against a different
  digit-heavy file (`PLAN.md`'s many `run_id`/timestamp strings), not a
  new bug. This item is genuinely blocked on two already-queued fixes
  (the OpenRouter phone-regex sanitizer, and PLAN.md's own oversize —
  which is also the subject of the already-queued "consolidate historical
  PLAN.md content out to target-repo docs" follow-on). Not resolved this
  session; run left at `stopped_on_failure` on this item pending user
  direction on how to proceed (skip Phase 5 for now vs. wait for the
  OpenRouter/PLAN.md-size fixes to land first).

## Current state (addendum 5, 2026-08-24 continued)

- **Priority #2 (OpenRouter fixes), first attempt (`20260824-162206-4ae0a0`)
  hit a genuine chicken-and-egg failure: its own breakdown call (Tier 2/
  Gemini, routed through OpenRouter) got `403 Forbidden` because the
  approved plan text itself contained literal phone-number-shaped example
  strings (e.g. a fake pager number as a test fixture) — a fourth live
  confirmation of the exact bug being fixed, this time tripped by the fix's
  own plan. That run is abandoned/stuck (`stopped_on_failure`, 0 phases,
  still sitting in `AGENTS.md`'s plan-gate block — harmless to leave, next
  plan used `--refactor` to supersede it). Redrafted as
  `20260824-164451-2b7635`** with an explicit constraint in the prompt
  telling the planner not to emit literal phone-shaped digit strings
  anywhere in the plan/test text (describe the format structurally
  instead) — this one's breakdown succeeded and it's now dispatching.
- **Priority #2 now dispatching: run `20260824-164451-2b7635`**, plan
  approved and running in background.
  Bundles all three queued OpenRouter/dispatch bugs into one 4-phase plan:
  (1) phone-number content-filter false-positive fix in
  `llm_client._sanitize_for_openrouter_content_filter()` (new
  `_PHONE_LIKE_RE`/`_redact_phone_like()`, scoped to not mangle
  run_id/task_id-shaped strings, hex hashes, or line numbers); (2)
  `dispatcher._is_deepseek_peak_hours()` now delegates to
  `budget_guard.check_tier3_peak_hours_ok()` instead of its stale
  hardcoded 06:00-10:00-UTC-only duplicate; (3) audit of
  `librarian_escalate.py`'s `fallback_openrouter` endpoint resolution
  (plan's own read concluded it's already correct via
  `tier_1_planner`'s config block, not the buggy pattern
  `probe_models()` had — a regression test asserting the resolved URL
  either way is still item 3's deliverable). Phase 4 does the full
  regression gate + PLAN.md/AGENTS.md doc updates. Check
  `triapi status 20260824-162206-4ae0a0` for progress if resuming.

## Next up

**Priority order, per user directive 2026-08-24: finish the librarian
improvements first, then the OpenRouter fixes, then the architecture
items.** The Virtual Codebase Plan is separate — it's on hold for the user
specifically, not part of this sequence.

1. **Librarian improvements: DONE.** Run `20260824-132910-a7b69b`
   completed Phases 1-4 (single-call redesign, `doc_staleness.py`, wiring,
   full regression coverage — all verified green). Only Phase 5 (append a
   dated phase block to `PLAN.md`) is still stuck, blocked on the same
   OpenRouter content-filter bug item 2 below is fixing, applied to
   `PLAN.md` itself (188K chars, also over the Tier 4 context ceiling) —
   retry `triapi dispatch 20260824-132910-a7b69b` once item 2 ships.
   `AGENTS.md` bullet updates for this work are not yet done either
   (bundled with the same stuck Phase 5).
2. **OpenRouter fixes: IN PROGRESS, immediate next action for the new
   session.** Run `20260824-164451-2b7635` (plan approved, 4 phases, 9
   items) is dispatching the same 3 bugs listed below. Status as of
   end of last session: **Phase 1's first item just got unblocked and is
   ready to redispatch** — `triapi dispatch 20260824-164451-2b7635`. Two
   real obstacles hit and resolved so far, both live confirmations of bug
   (c) below:
   - The plan's *own* breakdown call 403'd because an earlier draft's
     generated text contained a literal phone-shaped test-fixture string
     — redrafted with an explicit "no literal phone-shaped strings in
     plan/test text" constraint (worked; this is run `2b7635`, superseding
     abandoned/stuck run `20260824-162206-4ae0a0` which can be ignored).
   - Phase 1's first item then crashed Tier 4 with the *same* 403, this
     time because Tier 2's breakdown mis-extracted `context_files` from
     the item's own prose (pulled `logs/cost_log.jsonl`, `PLAN.md`, and a
     bogus `file.py` that were only mentioned as *examples* in the
     description, not real context needed). Fixed by editing
     `logs/runs/20260824-164451-2b7635.json`'s Phase 1 item to
     `context_files: []` directly (established workaround pattern from
     earlier this session) — not yet redispatched after this edit.
   - The three bugs being fixed: (a) `librarian_escalate.py`'s
     `fallback_openrouter` endpoint resolution — plan's own read concluded
     it's already correct via `tier_1_planner`'s config block, a
     regression test is the only deliverable; (b) `dispatcher.py`'s stale
     duplicate DeepSeek peak-hours check — should delegate to
     `budget_guard.check_tier3_peak_hours_ok()` instead of its own
     hardcoded `06:00-10:00 UTC`-only copy; (c) OpenRouter's content
     filter false-positives on phone-shaped digit sequences — add
     `_PHONE_LIKE_RE`/redaction to `llm_client.
     _sanitize_for_openrouter_content_filter()`, careful not to mangle
     TriAPI's own run_id/task_id format or hex hashes.
   - **Also check the self-fix queue**: `20260824-165500-90f029` and
     `20260824-173338-8bf5ad` were both auto-captured from transient `429`
     rate-limit crashes on this same run (`cmd_dispatch:foreground` —
     `Probe failed for tier_1_planner: 429`) — same "transient OpenRouter
     flakiness, don't approve" noise pattern as the other stale drafts
     already flagged in this file; skip both rather than approving.
   - **2026-08-24/25 update: the `context_files: []` workaround (edited
     directly into `logs/runs/20260824-164451-2b7635.json`'s Phase 1 item
     0) DID hold on retry** — confirmed live: `run_task starting: ...
     context_files=[] skip_tier4=False` and Tier 4 began drafting with no
     403. The run is NOT yet resolved though: two back-to-back resumes
     since then both crashed mid-flight on `probe_models()`'s pre-flight
     gate hitting a genuine `429` (not the phone-content-filter bug) —
     each dispatch resume calls `probe_models()` fresh across ALL tiers
     before running anything, so repeated resumes in a short window
     compound OpenRouter rate-limit pressure even for tiers this run's
     Phase 1 item doesn't need. This is the same "Pacing lesson" already
     recorded above, now reconfirmed twice more. **Next session: wait
     several minutes since the last resume attempt before running `triapi
     dispatch 20260824-164451-2b7635` again** — don't retry immediately.
   - **Refined root cause, 2026-08-25: this isn't just "OpenRouter is
     rate-limited," it's `probe_models()` (`scripts/llm_client.py`)
     unconditionally hard-gating on ALL SIX tiers — including
     `tier_1_planner`, which `triapi dispatch` never actually calls (only
     `triapi plan` uses it) — before running a single item.** 20 separate
     `Probe failed for tier_1_planner: 429` captures across
     2026-08-23→08-25 in `logs/triapi.log`, spanning ~22h, but
     interspersed with successful planning calls in between (e.g. one
     succeeded at 17:33:38 the same evening) — so this is a bursty
     per-minute rate limit on the free `stealth/ox-alpha` model, not a
     hard daily quota. Every `triapi dispatch <run_id>` resume re-probes
     `tier_1_planner` regardless of whether the run's own breakdown
     touches it, so a repair-only run with zero planning calls left in it
     (like this one, already fully broken down) can still be blocked
     indefinitely by an unrelated tier's transient rate limit. **Not
     hand-patched** (per standing rule) — candidate fix for the queue:
     `probe_models()` should only probe tiers the run's breakdown actually
     references (or at minimum not hard-fail the whole gate on
     `tier_1_planner`/`tier_1_manager` specifically when dispatching an
     already-broken-down run, since planning is already done by that
     point). This is closely related to, and probably subsumed by, the
     already-queued "complexity-aware router" architecture item below —
     folding this into that item's scope (or the backend-registry item) is
     probably more efficient than a standalone fix. Third self-fix
     duplicate of the same 429 noise pattern: `20260824-173338-8bf5ad`.
3. **Architecture items** (both already flagged as TriAPI self-feature
   work — plan/dispatch through the pipeline, don't hand-build):
   - A named backend registry (`backends:` section in `tiers.yaml`
     defining each reusable model config once) so tier↔model reassignment
     is a one-line pointer change instead of rewriting a tier's whole
     `provider`/`endpoint`/`api_key_secret`/`models` block by hand.
   - A complexity-aware router ahead of the tier ladder that reads a
     dispatch prompt/plan upfront and decides how much machinery a task
     actually needs — a large multi-phase plan gets the full ladder, a
     pure doc-reconcile task routes straight to Tier 5. Depends on Tier 5
     (done) and probably the backend registry above.

**Separately, on hold for the user (not part of the ordering above):**
- **Virtual Codebase Plan (Tiered Planner-Materializer architecture).**
  `VIRTUAL_CODEBASE_PLAN.md` at this repo's root (restored 2026-08-23 —
  had been deleted in commit `8998db5`; the user asked for it back).
  **User wants to work on this one together, personally** — hold off
  starting it solo.
- **Follow-on task queued for once Tier 5 exists (it does now):
  consolidate all target-repo-specific content out of TriAPI's own docs.**
  A supervisor survey (2026-08-24) found ~700 lines of `PLAN.md`'s
  historical record (17 sections spanning many phases, heavily interleaved
  with genuinely generic TriAPI bug fixes) plus a few illustrative
  mentions in `AGENTS.md`/`README.md` that name a target repo and should
  relocate to that repo's own docs per the rule above. **Both the planning
  and the execution go through TriAPI itself** (`triapi plan` against this
  repo, then `triapi dispatch`, Tier 5 doing the actual doc rewriting) —
  do not hand-draft the plan and do not write a one-off script that calls
  the librarian model directly; that defeats the point of building Tier 5.

## Historical notes (already resolved, kept for context)

- **Self-fix `20260824-011749-b8ba34` (the `llm_client.py` `KeyError:
  'choices'` fix) is fully resolved (2026-08-24).** Phases 1-2 (the
  `_call_openai_api()` guard + regression tests) landed via the pipeline;
  Phase 3 (the one-sentence `AGENTS.md` addition) hit `human_handoff` three
  times in a row on real local Ollama inference timing out (300s+ per
  attempt across all 3 escalation legs) — applied by hand instead, since
  the underlying code fix was already done/tested and this was a trivial,
  fully-specified one-line doc edit. `AGENTS.md` confirmed at 73,380 chars
  (still under the 73,728 ceiling, but tight — worth trimming further
  before the next addition). Full suite green (83 tests).
- **`llm_client.probe_models()` gained retry tolerance, 2026-08-24.** It
  had zero tolerance for a single transient blip on *any* tier — one
  OpenRouter 429 or a free model's temporary 502 aborted the entire
  pre-flight gate and thus the whole dispatch, even for tiers the run
  doesn't use. `_probe_with_retry()` now retries 3x, 5s apart, before
  failing the gate; still fails hard on a genuinely broken/misconfigured
  tier.
- **Found, not fixed: `tests.test_ollama_service_lifecycle.
  CmdDispatchOllamaLifecycleTests.test_cmd_dispatch_restores_ollama_state_
  on_exception` hangs on a real unmocked network call** (confirmed live
  2026-08-24 — it doesn't fail fast, it blocks for minutes). Pre-existing,
  unrelated to tonight's Tier 5 work (an earlier Jules advisory pass had
  already flagged this test module's mocking as incomplete). Needs a
  proper mock at the HTTP boundary, not just a shorter timeout. Run
  `tests.test_branch_features`/`tests.test_tier5_librarian` directly
  instead of bare `unittest discover tests` until this is fixed.
