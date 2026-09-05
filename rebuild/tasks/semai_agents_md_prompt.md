Draft a complete replacement for a repo's root `AGENTS.md` file, following this exact doc policy and structure (a sibling repo, TriAPI, just adopted this same policy):

DOC POLICY (put this near the top, adapted to this repo):
- One file only: AGENTS.md. No separate CARRYOVER.md, no docs/carryover/, no docs/agents/ split-file system.
- Carryover is a section inside AGENTS.md, not a separate file.
- Hard cap: AGENTS.md never exceeds 1000 lines. Each line at most 30 words.
- Entries are precise, worth-noting-only reports — no narrative, no play-by-play.
- Once work is done, its record can stay in the docs folder as frozen archive, but AGENTS.md itself doesn't keep expanding with completed-work narrative.

FACTS FOR THIS REPO (SemAI, a local-first assistant — Telegram/CLI/TUI front-ends, worker+intent architecture):
- Test command: `bash run_tests.sh` (wraps both a script-style suite and pytest; `python tests/test_X.py` alone silently collects nothing on a pytest file).
- Architecture: `src/semai/` is the active worker-based architecture (`src/semai/adapters/cli.py`'s `build_registry()` is the intent→worker wiring). `ohmyllama/` was the original tree; the multi-phase consolidation retiring it into `src/semai/` is now FULLY COMPLETE (both the "wobbly-yawning-seal" consolidation track, phases 0-8, and a separate capability track, phases 1-9, are both done as of 2026-09-05).
- `.state/` is the live ohmyllama database; `.state-semai/` is semAI's own separate state dir — never the same file.
- Standing rule: target-repo code changes go through TriAPI's rebuild pipeline (DeepSeek writes, Claude audits/verifies with real tests, no auto-apply) rather than hand-edits, except genuine last-resort hand-fixes, logged inline where they happen.
- Current state (2026-09-05): consolidation fully done. Three real bugs from an agentic-behavior audit (`Agentic_Audit.md`) were just found and fixed via the rebuild pipeline: a templated tool description that hid the research tool's real web-search capability, a system prompt paragraph that told the model to never use tools for anything outside local data, and a tool-call telemetry bug that silently reported an empty list even when tools ran. All fixed in `src/semai/agent.py`, 114/114 real tests passing.
- Live services: `oh-my-llama.service`, `oh-my-llama-telegram.service`, and `openclaw.service` were stopped 2026-09-05 at the user's request (freeing memory during a dispatch session) and have NOT been restarted. `miki-sorter.service` was deliberately left running. Check `systemctl --user is-active` before assuming they're up.
- Known small debt, not yet fixed, worth carrying forward: `.state-semai/*.sqlite3` files are tracked in git and shouldn't be (every local test run produces a binary diff) — flagged, not fixed, no urgency; `openclaw-todoist` plugin still enabled with a live token though Todoist was cut on the SemAI side, forgotten, not touched.
- Future plans: NONE currently queued. The next session should ask the user what to work on next rather than assuming a phase.
- Archive note: the previous, much larger `AGENTS.md`, `MAPPING.md`, `docs/Agent/CARRYOVER.md`, and `docs/Agent/AGENT_GUIDE.md` contained the full consolidation history — `MAPPING.md` and `docs/Agent/AGENT_GUIDE.md` are left in place, frozen, not migrated; full detail recoverable via git history if ever needed.

Structure to follow (mirror this shape exactly, adjusting wording to this repo):
```
# AGENTS.md
<one-line repo description. Read this file first, it is the only doc kept live.>

## Current architecture
<brief, a few short lines>

## Doc policy
<the policy above, compressed to ~3 short lines>

## Carryover (current state, 2026-09-05)
<bullet list of the facts above, each line under 30 words>

## Future plans (queued, not started)
<state clearly: none queued>

## Archive
<one line: what's frozen in place and not migrated>
```

Reply with the complete AGENTS.md file content only, no other text, no markdown code fence — just the raw file content starting with "# AGENTS.md".
