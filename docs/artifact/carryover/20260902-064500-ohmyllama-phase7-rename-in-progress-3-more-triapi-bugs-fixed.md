# Carryover — 2026-09-02 (early, UTC) — oh-my-llama Phase 7 rename dispatch in progress, 3 more TriAPI bugs fixed

**Status: PAUSED mid-task at the user's explicit request** ("when you done
fixing triapi. stop and update docs, we will continue in the new session so
repo don't mix up"). Nothing destructive has happened to oh-my-llama on
disk — see "oh-my-llama state" below. Resume in a fresh session.

## What this session covered

Picked up from `20260902-000000-ohmyllama-phase7-prep-complete-3-triapi-bugs-fixed.md`
(now history). Two threads:

### 1. TriAPI bug-queue cleanup (done, both fixed+pushed)

- **`dispatcher.breakdown_phase()` silent detail drop on dense plan steps**
  — FIXED (commit `b82d8a5`). A checklist bullet whose text clearly
  dominates a phase's size is now split off into its own recursive
  `breakdown_phase()` call instead of being compressed alongside the rest.
  Regression-tested (`tests/test_breakdown_dense_bullet_split.py`), and
  confirmed firing correctly in the real dispatch below (log: "splitting
  off one dense bullet (7043 chars) from the rest (60 chars)").
- **`content_guard.py`'s edit-block-marker guard false-positive** — FIXED
  (commit `b82d8a5`). The guard now requires a marker to occupy its own
  line rather than matching as a bare substring, so prose quoting the
  marker strings inline no longer trips it.
- Tier 5 oversized-file fallback (third queued item) — left queued, not a
  plain bug fix, belongs in its own `triapi plan` session.

### 2. oh-my-llama Phase 7 package rename — dispatched, paused mid-run

Goal: `ohmyllama` → `semai` package identity (ADR-0005), phased into A
(pyproject.toml name field) / B (uv tool reinstall + live-service restart,
verify_only, treated as immutable/escalate-to-human-on-failure) / C (delete
the now-dead `ohmyllama/` dir, ~39 files, zero real importers left) / D
(close out CARRYOVER.md + ADR-0005). Planned interactively via
`triapi plan` (fifo-driven stdin, since the CLI's plan/approve loop needs
an interactive terminal — see the fifo/holder-process technique in this
session's raw transcript if repeating this). **Approved run:
`20260901-230714-ebd3c2`**, project dir
`/home/dyne/Documents/Coding/oh-my-llama`. An earlier abandoned planning
attempt (run `20260901-230301-73790d`) also got its plan text appended to
oh-my-llama's `AGENTS.md` before its session died mid-fifo-write — that
block is dead/superseded, **not** the one to dispatch; oh-my-llama's
`AGENTS.md` currently has both blocks appended, unchecked. Minor cleanup
item for the next session (or just let it resolve naturally once
`ebd3c2`'s real dispatch checks off its own block — `find_incomplete_plan()`
only reads the single most recent block per `AGENTS.md`'s own doc, so this
shouldn't actually block anything, just reads oddly).

Three dispatch attempts against `ebd3c2`, three different real TriAPI bugs
found and fixed live, each verified compiling + full suite green + pushed
before retrying:

1. **`_breakdown_phase_attempt()` used a strict `tier2["endpoint"]`
   subscript** — crashed with `KeyError: 'endpoint'` the moment DeepSeek's
   peak-hours window opened (06:00 UTC) and `breakdown_phase()` correctly
   resolved `tier_2_manager.peak_alt` (provider `agy`, no `endpoint` key,
   same shape as every other agy-provider block in this repo). Fixed:
   `.get("endpoint")`, matching `tier2_escalate.py`/`tier3_escalate.py`'s
   existing convention. Commit `42b85fd`.
2. **`_breakdown_phase_attempt()` never threaded `effort` through to
   `execute_llm()`** — the live `agy` CLI now rejects
   `--model gemini-3.1-pro` with no `--effort` at all ("requires
   --effort"), so the very next attempt (now past the endpoint bug) failed
   with exit status 1 and no diagnosable message (see the note below on
   `CalledProcessError`'s swallowed stderr — found by manually reproducing
   the `agy` CLI call by hand, not from the logged exception text). Fixed:
   pass `effort=tier2.get("effort")`. Commit `1d7870b`.
3. **`_enforce_file_size_ceiling()` crashed on a directory-deletion plan
   item** — Phase C's "delete the `ohmyllama/` directory" item has a
   directory as its `target`; `target_path.read_text()` raised
   `IsADirectoryError` before ever reaching the existing
   `_item_deletes_target_file()` exemption (which only runs after the size
   read). Fixed: skip directory targets outright, before attempting to
   read them as text. Commit `daf2190`.

After fix #3, dispatch was **not re-run** — the user asked to stop here
and document instead of continuing. **Breakdown itself now succeeds
cleanly** (confirmed in the attempt that hit bug #3: "Broken down phase
1/4... 2/4... 3/4... 4/4" all logged ok) — the remaining unknowns are
whatever Tier 4/3/2/1 do with the four real phase items once dispatch
actually runs them, especially Phase B's live-service restart.

**Known, not-yet-fixed side finding (do not fix without asking first, low
priority, tangential):** `scripts/llm_client.py`'s `_call_agy_cli()` (and
`_call_claude_cli()`, same pattern) raises `subprocess.CalledProcessError`
on a non-zero exit / bad JSON, but `CalledProcessError.__str__` never
includes `stdout`/`stderr` regardless of what's passed to the constructor
— so every "Phase breakdown request failed: %s" (or equivalent) log line
for a CLI-provider failure shows only "Command '[...]' returned non-zero
exit status N.", none of the actual diagnostic detail, even though the
docstrings claim otherwise ("a message embedding the status and stderr
tail"). Diagnosed bug #2 above by manually reproducing the `agy` call by
hand, not from the logs. Worth a real fix (wrap in a plain exception with
an informative `str()`, or log `e.stderr`/`e.output` explicitly at the
catch site) but is a pre-existing, repo-wide pattern (also affects
`_call_claude_cli`), not something introduced this session — flagging,
not fixing, per the user's stop-and-document instruction.

## oh-my-llama state (verify before resuming)

- **Live services**: `oh-my-llama.service` and `oh-my-llama-telegram.service`
  both confirmed `active`/healthy multiple times this session, including
  right after fix #1's failed dispatch attempt (resource_guard's own
  pause/resume cycle around a failed run, not Phase B — Phase B itself
  never actually ran yet, since breakdown kept failing before reaching
  dispatch until fix #3 was still pending verification). **Re-verify
  `systemctl --user is-active oh-my-llama.service
  oh-my-llama-telegram.service` before resuming dispatch regardless.**
- **`pyproject.toml`**: still `name = "ohmyllama"` — Phase A has not run.
- **`ohmyllama/` directory**: still present, untouched.
- **`AGENTS.md`**: has two appended `triapi:plan` blocks (see above) —
  both unchecked. `git status` shows only this file modified in
  oh-my-llama; nothing else touched.
- **`.state-semai/*.sqlite3`**: shows as locally modified in `git status`
  every session (known, pre-existing, should be gitignored but isn't —
  see oh-my-llama's own carryover history) — not caused by this session,
  do not try to "clean" it.

## To resume in the next session

1. `systemctl --user is-active oh-my-llama.service oh-my-llama-telegram.service`
   — confirm both `active` before touching anything.
2. `cd /home/dyne/Documents/Coding/TriAPI && triapi status 20260901-230714-ebd3c2`
   — confirm still `stopped_on_failure` with the state this session left it
   in (breakdown never completed through to dispatch).
3. `triapi dispatch 20260901-230714-ebd3c2` to resume — breakdown should
   now succeed cleanly (confirmed) and Phase A/B/C/D should actually run.
   **Watch Phase B closely** (live `systemctl --user restart` of both
   services) — it's marked immutable/escalate-to-human-on-failure in the
   plan text itself, but that's advisory to the AI tiers, not a hard
   guarantee; verify service health manually right after that item
   completes regardless of what the item reports.
4. If dispatch succeeds cleanly end to end, close out both repos' docs
   (oh-my-llama's `docs/Agent/CARRYOVER.md`/ADR-0005 get updated by Phase
   D itself; TriAPI's own carryover should get a short "Phase 7 complete"
   follow-up note).
