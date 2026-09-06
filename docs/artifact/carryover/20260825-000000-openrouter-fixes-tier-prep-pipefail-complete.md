# 2026-08-25 00:00 — OpenRouter fixes + tier-reassignment prep + pipefail fix, all COMPLETE

Everything in this file was DONE and committed to `main` by the end of
the 2026-08-24/25 overnight session. Three stale `triapi/TriAPI-*` review
branches from earlier sessions (all already fully merged into `main`)
were cleaned up and deleted — `main` is the single source of truth,
nothing stranded on an unmerged branch.

**Completed this session** (full detail in `PLAN.md` Phases 30-32):
- OpenRouter fixes (phone/IP content-filter sanitizer, dispatcher
  peak-hours dedup, librarian endpoint audit) — run `20260824-164451-2b7635`.
- Tier-reassignment prep: new `agy` (Antigravity CLI) provider in
  `llm_client.py`, generic (non-hardcoded) provider routing in
  `dispatcher._breakdown_phase_attempt()`, position-independent DeepSeek
  peak-hours gate (`budget_guard.resolve_deepseek_tier()`) — run
  `20260824-221726-3df72d`.
- Critical fix: `run_build()` no longer silently masks a failing
  `build_cmd` behind a truncating pipe (`| tail`, etc.) — was giving false
  "verified green" results. Plus a stale test fixture regression found
  alongside it. — run `20260825-000610-4c040a`.
- `git_ops.push()`'s auto-branch-creation safety rail **removed at the
  user's explicit request** — it now always pushes to whatever branch is
  checked out (including `main`/`master` directly), no more auto-created
  `triapi/<dirname>-<timestamp>` review branches. See `AGENTS.md`'s
  `git_ops.py` bullet.

This session also produced the OpenRouter incident writeup (unauthorized
billing from a Gemini `fallback_chain` bug) and the standing rules that
came out of it — those are folded into the current active carryover
entry (see the carryover index) rather than duplicated here, since they
remain live policy, not history.
