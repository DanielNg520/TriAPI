"""Tier 2 (as Manager): breaks a Tier-1 plan into phases of concrete
checklist items -- one file + one task each -- then dispatches them to the
existing repair pipeline (orchestrator.run_task()) one at a time, in order.

Distinct from tier2_escalate.py, which uses the Gemini API as a repair
tier for a single already-known-broken file. This module uses Gemini in
the manager role from the original design: turning a rough plan into a
strict, executable checklist and working through it sequentially.

Run state is persisted to logs/runs/<run_id>.json after every single item
completes (not just at the end), so a long-running plan survives an SSH
disconnect -- resume by re-reading the same run_id.

Must only be called after budget_guard.check_tier2_ok().
"""

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scripts import gemini_fallback, git_ops, regression_guard, judge, mock_patch_lint, tech_debt, tier3_escalate
from scripts.tier4_worker import run_build
from scripts.budget_guard import check_tier2_ok
from scripts.config_loader import load_tiers
from scripts.orchestrator import human_handoff, run_task, verify_task
from scripts.secrets_loader import load_secrets
from scripts.tri_logging import get_logger

log = get_logger("dispatcher")

RUNS_DIR = Path(__file__).resolve().parent.parent / "logs" / "runs"

BREAKDOWN_SYSTEM_INSTRUCTION = (
    "You manage a team of coding workers. Given ONE PHASE of an execution plan "
    "(markdown, a single phase containing a checklist of steps), convert it "
    "into strict JSON with this exact shape: "
    '{"name": "the phase name", "items": [ITEM, ...]}. '
    "If a single checklist bullet names multiple files to edit, split it into "
    "one ITEM per file -- never combine multiple files into one item's "
    "'target'. Each ITEM is one of two shapes:\n"
    "1. A file item: "
    '{"description": "...", "target": "relative/path/to/file", "build_cmd": "shell command to build/verify", "verify_only": false, "context_files": []}. '
    "One item per file that needs creating or changing. 'context_files' is an "
    "OPTIONAL list of OTHER existing repo files (relative paths) the worker "
    "should read for grounding -- set it whenever the step's own text "
    "references another file or pattern to follow, e.g. \"seeded from the "
    "list in plan.md\", \"following the shape of config/tiers.yaml\", \"matching "
    "the existing auth.py error handling\". List the actual file(s) being "
    "referenced, not the step's own 'target'. Leaving this empty when the "
    "step clearly depends on another file's real content is a failure -- the "
    "worker has NO other way to see repo files besides this list, and will "
    "invent plausible-looking but WRONG content instead (e.g. asked to seed "
    "a file from \"the list in plan.md\" with no context_files, it will "
    "hallucinate a generic list instead of reading the real one). Set 'verify_only': "
    "true when the step is a pure check with NO file content to draft/change "
    "-- e.g. \"run the test suite\", \"grep for no remaining call sites\", "
    "\"confirm output looks like X\". For those, 'target' should name the "
    "most relevant existing file (e.g. the test runner, or one of the dormant "
    "files being checked for stray references) but it will NOT be drafted or "
    "overwritten -- only 'build_cmd' actually runs. Getting 'verify_only' "
    "wrong on a step that has nothing to write is dangerous: it would cause "
    "an AI worker to overwrite a file (like a test runner script) that was "
    "never supposed to change at all. Default false only for steps that "
    "genuinely create or edit that file's content. A 'verify_only': true item "
    "MUST always have a non-empty 'build_cmd' -- there is nothing else for "
    "this item to do, so an empty build_cmd means the step accomplishes "
    "nothing and the dispatcher refuses to guess (this has happened for real: "
    "a step reading \"confirm file X remains in the tree as a dormant, "
    "unregistered file\" was left with build_cmd: \"\", stalling the whole run). "
    "For a \"confirm this file still exists / was left in place\" step, use "
    "`test -f <path>` (join multiple paths with `&&`). For \"confirm no code "
    "references it\", see the exclusion-filtered grep guidance above. Never "
    "leave build_cmd empty on a verify_only item for any reason.\n"
    "2. A git item, ONLY for an explicit git clone/pull/push step named in the "
    "plan (do not invent git steps that aren't in the plan): "
    '{"description": "...", "git": {"action": "clone", "url": "...", "path": "relative/or/absolute/path"}} or '
    '{"description": "...", "git": {"action": "pull", "path": "relative/or/absolute/path"}} or '
    '{"description": "...", "git": {"action": "push", "path": "relative/or/absolute/path", "message": "commit message", "branch": "optional, only if the plan names a specific branch"}}.\n'
    "'path' is REQUIRED on every git action once a repo directory is known -- "
    "it's the directory the git command runs in. For 'clone' it's where the new "
    "clone goes (relative to the project directory). For 'pull'/'push' it MUST "
    "be the actual repo directory, which is very often NOT the project's top "
    "level -- e.g. if an earlier clone step's path was 'repo', every later "
    "pull/push step operating on that clone must also use path 'repo', not omit "
    "it. Getting this wrong makes the command run in a directory with no git "
    "repo at all, which fails immediately.\n"
    "Preserve this phase's step order exactly, do not reorder or merge steps "
    "into each other (except splitting a multi-file bullet into one item per "
    "file, as above). Each 'description' plus whatever 'context_files' names "
    "is the ONLY context the worker doing this step will see -- it will NOT "
    "see the original plan or phase text, and will NOT see any repo file not "
    "listed in 'context_files'. Carry forward every concrete technical requirement from that step "
    "verbatim: language/standard version, exact expected output/behavior, "
    "library versions, interfaces, anything specific. Summarizing away a "
    "specific requirement (e.g. dropping 'C++17' down to just 'create the "
    "file') is a failure, not a simplification. A step with no single file to "
    "create/change (e.g. \"run the test suite\", \"grep for X\") is still a "
    "file item -- use the most relevant existing file as 'target' (e.g. the "
    "repo root config/test file) and put the actual check in 'build_cmd'. "
    "SPECIAL CASE, learned from a real bug: when a step says something like "
    "\"verify no live call sites remain\" / \"confirm no stray references\" "
    "for a feature being cut, a bare `grep -rn NAME dir1 dir2` is WRONG and "
    "must never be used verbatim, even if the plan text itself shows that "
    "exact command -- bare grep exits 0 (success) the instant it matches "
    "ANYTHING, including the intentionally-kept dormant file(s) that still "
    "contain the feature's name by design (e.g. `todoist.py` itself, left "
    "in place unregistered), which means the check can never fail and "
    "proves nothing. Instead build_cmd MUST exclude the known dormant/kept "
    "file(s) from the match and assert zero remaining hits, e.g. "
    "`! grep -rn NAME dir1 dir2 --include=*.py | grep -v dormant_file.py` "
    "(the leading `!` makes the shell command itself fail, i.e. non-zero "
    "exit, when any live reference remains) or an equivalent exclude-then-"
    "assert-empty form. If the plan doesn't name which files are dormant, "
    "infer them from the phase's own text (files explicitly left in place "
    "unregistered) and exclude exactly those, nothing more. "
    "SECOND SPECIAL CASE, also learned from a real bug: when a step's text "
    "says to write a standalone verification script and then run it to "
    "check some OTHER change (e.g. \"create /tmp/verify_x.py containing "
    "[assertion], then run it and confirm it passes\"), NEVER make the "
    "script itself a file item's 'target' with build_cmd invoking that "
    "same script. A file item's whole contract is that Tier 4/3 may freely "
    "rewrite 'target' on a failed build_cmd until it passes -- applied to a "
    "verification script, that means a worker that can't fix the real bug "
    "will instead loosen the script's own assertion until it trivially "
    "passes, which is exactly what happened for real (2026-08-12: asked to "
    "verify a model was excluded from a list, a retrying worker rewrote "
    "the check to filter that model out of the list being asserted on, "
    "rather than fixing the code that was supposed to exclude it -- the "
    "'verification' passed while the actual bug remained). A verification "
    "script's assertion must be FIXED, not draftable by any tier being "
    "graded against it. Instead, bake the script's exact content directly "
    "into 'build_cmd' as a heredoc so it exists only as an immutable shell "
    "command, never as an editable target: "
    "`cat > /tmp/verify_x.py <<'EOF'\\n<exact script content>\\nEOF\\n"
    "python3 /tmp/verify_x.py`, and set 'verify_only': true with 'target' "
    "naming whatever real repo file the check is actually about (not the "
    "throwaway script) -- verify_only items are never drafted, so nothing "
    "can rewrite the heredoc's contents once dispatch starts. "
    "Output ONLY the JSON for this one phase, no explanation, no markdown "
    "code fence, and do NOT wrap it in a 'phases' list -- just the single "
    "{\"name\": ..., \"items\": [...]} object."
)


_PHASE_HEADER_RE = re.compile(r"^#{1,6} ")

# Matches a markdown task-list item regardless of bullet style: '- [ ]',
# '* [ ]', or a numbered '1. [ ]' -- and regardless of checked state ('x'/'X'
# inside the brackets, not just an empty box). Found for real 2026-08-12:
# a plan used numbered items ('1. [ ]', '2. [ ]') instead of the dash-bullet
# style this previously hardcoded a literal '- [ ]' substring check for --
# the whole (non-empty, clearly checklist-bearing) plan chunk was silently
# treated as having "no checklist items" and dropped, and the run reported
# "Dispatch completed: all items resolved" having done zero actual work.
# Matches any bulleted/numbered list item, with or without a literal
# '[ ]' checkbox -- found for real 2026-08-13: a planner turn produced a
# perfectly good 11-phase, real plan using plain "1. **file** -- ..."
# items with no checkbox markup at all (the SYSTEM_PROMPT only asks for
# "a checklist", it doesn't mandate '[ ]' syntax, and the model doesn't
# reliably add it). Requiring '[.]' silently filtered out every phase
# chunk as "no checklist items", producing a 0-phase/0-item breakdown
# with no error. A bare list marker is enough: the leading title/context
# chunk this filter is meant to drop is prose with no list markers at
# all, so this stays selective without depending on checkbox syntax.
_CHECKLIST_ITEM_RE = re.compile(r"^\s*(?:[-*]|\d+\.)\s+", re.MULTILINE)


def _split_plan_by_phase(plan_text: str) -> list[str]:
    """Splits plan markdown into chunks on ATX headers (one chunk per
    phase, keeping its header), so each phase can be broken down into JSON
    independently. Asking Gemini for the WHOLE plan's JSON in one call fails
    on large plans -- observed: malformed/truncated JSON past ~500 lines of
    output for a real 9-phase plan. Smallest reliable batch, not fewer,
    bigger calls.

    Matches any heading level ('#' through '######'), not just '## '
    specifically -- found for real 2026-08-12: a plan used '### Phase 2'
    (three hashes) while this only recognized exactly '## ', silently
    dropping that entire phase's checklist items from the breakdown with
    no error at all (the dropped phase just never existed as far as
    dispatch was concerned). The planner's own header depth isn't a
    guaranteed convention to rely on. A stray '# Title' line before the
    first real phase header still produces a harmless chunk, filtered out
    below same as before. A plan with NO header at all (a single short
    plan, e.g. one Tier-1-drafted phase with no '#' line whatsoever)
    produces exactly one chunk -- the whole text -- which is correct as
    long as the checklist-item filter below still recognizes it."""
    lines = plan_text.splitlines(keepends=True)
    chunks = []
    current = []
    for line in lines:
        if _PHASE_HEADER_RE.match(line) and current:
            chunks.append("".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        chunks.append("".join(current))
    # Drop chunks with no checklist items (e.g. a leading title/context
    # block before the first phase header) -- nothing to break down.
    return [c for c in chunks if _CHECKLIST_ITEM_RE.search(c)]


# Path-like references in an item's own description text -- with or
# without backticks, since Gemini's breakdown output does NOT reliably
# preserve the backticks the source plan.md used (confirmed: the real
# 2026-08-10 breakdown wrote "following ohmyllama/watcher.py's poll-loop
# pattern" with no backticks at all, even though plan.md's own text had
# them). Two shapes: any slash-containing path ending in a dotted
# extension (covers e.g. `config/tiers.yaml`, `docs/decisions/0011-x.md`),
# or a bare filename with a common code/doc extension (covers e.g.
# `plan.md`, `watcher.py` referenced without its directory).
_FILE_REF_RE = re.compile(
    r"[\w][\w-]*(?:/[\w.-]+)+\.\w+"
    r"|\b[\w-]+\.(?:py|md|yaml|yml|json|js|ts|jsx|tsx|toml|cfg|ini|sh|txt)\b"
)


def _backstop_context_files(item: dict) -> None:
    """Deterministic fallback for BREAKDOWN_SYSTEM_INSTRUCTION's
    'context_files' field: found for real 2026-08-10 (PLAN.md Phase 13c)
    that relying on Gemini to comply with that instruction isn't reliable
    enough on its own -- a real 96-item breakdown left EVERY item's
    context_files empty, including ones whose description explicitly named
    another file to follow ("following `ohmyllama/watcher.py`'s poll-loop
    pattern"), and the worker hallucinated instead of reading it. This
    regex-extracts every backtick-quoted, dotted-extension path mentioned in
    the item's own description (Gemini already quotes paths this way
    consistently -- see BREAKDOWN_SYSTEM_INSTRUCTION's own examples) and
    unions it into context_files, deduped, minus the item's own target.
    Mutates item in place. A no-op for items with no such references."""
    target = item.get("target")
    referenced = [p for p in _FILE_REF_RE.findall(item.get("description", "")) if p != target]
    if not referenced:
        return
    existing = item.get("context_files") or []
    merged = list(existing)
    for p in referenced:
        if p not in merged:
            merged.append(p)
    if merged != existing:
        item["context_files"] = merged


_TEST_TARGET_RE = re.compile(r"^(?:tests|Tests|TESTS)/test_[^/]+\.py$")
def _find_anchor_test_file(project_dir: str, exclude: str | None = None) -> str | None:
    """Finds the anchor test file for a project.

    Prefer 'tests/test_branch_features.py' if it exists and is not excluded,
    otherwise find the first sorted tests/test_*.py file.

    Found for real 2026-08-18 (two incidents, see CARRYOVER.md queue item #1):
    when a step referenced "the test file" / "existing test patterns" without
    naming an exact path, the worker had no context file to ground against and
    hallucinated a test structure; and when an anchor test file was chosen by
    alphabetical order instead of the project's canonical
    'tests/test_branch_features.py', the worker copied a pattern that did not
    apply. This helper is the deterministic fallback for both cases.

    Args:
        project_dir (str): The root directory of the project.
        exclude (str | None): An optional regex pattern to exclude specific
            files or directories. When None or empty, nothing is excluded.

    Returns:
        str | None: The path to the anchor test file, or None if no suitable
        file is found.
    """
    target_path = Path(project_dir) / 'tests' / 'test_branch_features.py'
    if target_path.exists() and not (exclude and re.match(exclude, str(target_path))):
        return str(target_path)

    test_files = sorted(Path(project_dir).glob('tests/test_*.py'))
    for file in test_files:
        if not (exclude and re.match(exclude, str(file))):
            return str(file)

    return None


def _apply_test_context_guard(items: list[dict], project_dir: str) -> str | None:
    """Grounds each test-file breakdown item in real repo content.

    For each item whose target is a standard tests/test_*.py file (skipping
    git items and any item not targeting such a file), the companion
    scripts/<name>.py helper (stripping the "test_" prefix from the target's
    stem) is added to that item's own context_files if it exists on disk,
    and the project's anchor test file (see _find_anchor_test_file) is added
    so the worker patterns its test against the canonical example instead of
    hallucinating one -- each item only receives its own companion, never
    another item's. Returns an error string (without mutating any item) when
    no anchor test file exists at all, otherwise None."""
    anchor_file = None
    test_items = [
        item for item in items
        if "git" not in item and _TEST_TARGET_RE.match(item.get("target", ""))
    ]
    if test_items:
        anchor_file = _find_anchor_test_file(project_dir)
        if not anchor_file:
            return "Error: No suitable anchor test file found."

    for item in test_items:
        target_stem = Path(item["target"]).stem
        module_name = target_stem[len("test_"):] if target_stem.startswith("test_") else target_stem
        companion_script = Path(project_dir) / "scripts" / f"{module_name}.py"

        if "context_files" not in item:
            item["context_files"] = []
        if companion_script.exists() and str(companion_script) not in item["context_files"]:
            item["context_files"].append(str(companion_script))
        if anchor_file not in item["context_files"]:
            item["context_files"].append(anchor_file)

    return None


_RETRY_AFTER_RE = re.compile(r"[Rr]etry in ([\d.]+)s")


def _parse_retry_after(body: str) -> float | None:
    """Google's 429 body names an exact backoff (e.g. 'Please retry in
    27.33s.') -- use it when present instead of guessing."""
    m = _RETRY_AFTER_RE.search(body)
    return float(m.group(1)) if m else None


def _breakdown_phase_attempt(phase_text: str, models: list[str], tier2: dict, secrets: dict) -> dict:
    body = {
        "systemInstruction": {"parts": [{"text": BREAKDOWN_SYSTEM_INSTRUCTION}]},
        "contents": [{"role": "user", "parts": [{"text": phase_text}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    try:
        resp, model_used = gemini_fallback.post_generate_content(
            requests.post, tier2["endpoint"], secrets["google_ai_studio_api_key"], body, models, timeout=120,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        # Was previously left to propagate uncaught past breakdown_phase()'s
        # retry loop (only malformed-JSON was caught below), crashing the
        # whole dispatch on a transient network blip or rate limit (hit a
        # real 429 during Phase 11 testing) instead of retrying like every
        # other transient failure here does.
        log.error("Phase breakdown request failed: %s", e)
        resp_text = getattr(getattr(e, "response", None), "text", "") or ""
        retry_after = _parse_retry_after(resp_text)
        return {"status": "error", "reason": f"Gemini request failed: {e}", "retry_after": retry_after}
    if model_used != models[0]:
        log.info("Phase breakdown used fallback model %s (default %s exhausted for today)", model_used, models[0])
    data = resp.json()

    text = data["candidates"][0]["content"]["parts"][0]["text"]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        log.error("Phase breakdown returned invalid JSON: %s", e)
        return {"status": "error", "reason": f"Gemini did not return valid JSON for this phase: {e}"}

    if "name" not in parsed or "items" not in parsed or not isinstance(parsed["items"], list):
        log.error("Phase breakdown JSON missing 'name'/'items': %s", text[:500])
        return {"status": "error", "reason": "phase breakdown JSON missing 'name'/'items'"}

    for item in parsed["items"]:
        if "git" in item:
            continue
        _backstop_context_files(item)

    return {"status": "ok", "phase": parsed}


def breakdown_phase(phase_text: str, model: str | None = None, max_attempts: int = 3) -> dict:
    """Breaks down ONE phase's markdown into {"name", "items"}. See
    _split_plan_by_phase for why this is per-phase, not per-plan.

    Retries on malformed JSON: Gemini's responseMimeType=application/json
    mode is not 100% reliable even for small, simple inputs -- observed the
    exact same tiny (307-char) phase produce valid JSON on one call and
    malformed JSON on the next, with no input change. This is a transient/
    stochastic failure, not a deterministic bug, so retrying is the right
    response -- time is not a constraint here, a wrong plan running is what
    actually costs something.

    An RPM refusal from check_tier2_ok() is retried the same way (the
    sliding window empties within 60s on its own) -- found for real
    2026-08-12: breaking down a large plan fires one Gemini call per phase
    in a tight loop, easily bursting past a 10 RPM cap well before any
    single phase's own retry logic would ever kick in, and the previous
    immediate "skipped" return killed the whole breakdown (and, one layer
    up, marked the run "failed" instead of resumable) over a condition that
    clears itself in under a minute. An RPD refusal is NOT retried here --
    it won't clear until the next day, so retrying within this call would
    just busy-wait for no reason; that case still returns immediately."""
    config = load_tiers()
    tier2 = config["tier_2_manager"]
    secrets = load_secrets()
    default_model = tier2["models"][tier2["default_model"]]
    # An explicit model override is honored exactly, no fallback -- the
    # caller asked for that one specifically. Otherwise walk the configured
    # chain (Phase 14: per-model daily quota fallback) so one exhausted
    # model doesn't stall the whole breakdown.
    models = [model] if model else (tier2.get("fallback_chain") or [default_model])

    log.info("Requesting phase breakdown from Gemini/%s (%d chars)", models[0], len(phase_text))

    last_result = None
    for attempt in range(1, max_attempts + 1):
        guard = check_tier2_ok()
        if not guard["ok"]:
            if "RPD" in guard["reason"]:
                # Daily quota -- won't clear during this run, don't busy-wait.
                log.warning("Phase breakdown skipped: %s", guard["reason"])
                return {"status": "skipped", "reason": guard["reason"]}
            result = {"status": "error", "reason": guard["reason"], "retry_after": 65.0}
        else:
            result = _breakdown_phase_attempt(phase_text, models, tier2, secrets)

        if result["status"] == "ok":
            log.info("Phase breakdown ok (attempt %d/%d): %r, %d item(s)", attempt, max_attempts, result["phase"]["name"], len(result["phase"]["items"]))
            return result
        log.warning("Phase breakdown attempt %d/%d failed: %s", attempt, max_attempts, result.get("reason"))
        last_result = result

        if attempt < max_attempts:
            # Retrying instantly against a rate limit just 429s again --
            # observed for real: 3 attempts fired within ~300ms of each
            # other, all rejected. Honor the server's own backoff hint when
            # given (Google's 429 body names an exact delay); otherwise a
            # short fixed pause covers the malformed-JSON case, which is
            # genuinely transient/stochastic, not rate-limited.
            delay = result.get("retry_after") or 5.0
            log.info("Backing off %.1fs before retry %d/%d", delay, attempt + 1, max_attempts)
            time.sleep(delay)

    return last_result


def breakdown_plan(state: dict) -> dict:
    """Breaks state['plan_text'] down phase by phase, saving state after
    each phase succeeds -- resumable, and each individual Gemini call stays
    small and reliable. Skips phases already present in
    state['breakdown']['phases'] (so re-entering a partially-broken-down
    run doesn't redo completed phases)."""
    if state["breakdown"] is None:
        state["breakdown"] = {"phases": []}
        save_run(state)

    chunks = _split_plan_by_phase(state["plan_text"])
    already_done = len(state["breakdown"]["phases"])

    for i, chunk in enumerate(chunks):
        if i < already_done:
            continue
        result = breakdown_phase(chunk)
        if result["status"] != "ok":
            return result
        guard_reason = _apply_test_context_guard(result["phase"]["items"], state["project_dir"])
        if guard_reason is not None:
            log.error("Test context guard failed for phase %s: %s", result["phase"].get("name", "?"), guard_reason)
            return {"status": "error", "reason": guard_reason}
        state["breakdown"]["phases"].append(result["phase"])
        _recheck_regression_flags(state)
        save_run(state)
        print(
            f"  Broken down phase {i + 1}/{len(chunks)}: "
            f"{result['phase']['name']} ({len(result['phase']['items'])} item(s))"
        )

    total_items = sum(len(p["items"]) for p in state["breakdown"]["phases"])
    log.info("Breakdown ok: %d phase(s), %d item(s) total", len(state["breakdown"]["phases"]), total_items)
    # A non-empty plan producing zero phases (every chunk filtered out as
    # "no checklist items", e.g. an unrecognized bullet style) or zero
    # total items must never be reported as an ordinary success -- found
    # for real 2026-08-12: exactly this happened, and the run printed
    # "Dispatch completed: all items resolved" having done zero actual
    # work, indistinguishable from a real empty-plan success unless you
    # happened to notice "0/0 steps". A genuinely empty plan_text (nothing
    # to do) is not this codepath's problem to guess about -- catch it
    # here as a hard error instead of guessing either way.
    if state["plan_text"].strip() and total_items == 0:
        return {
            "status": "error",
            "reason": (
                f"Breakdown produced {len(state['breakdown']['phases'])} phase(s) "
                f"and 0 total item(s) from a non-empty plan ({len(state['plan_text'])} "
                "chars) -- likely a checklist-item or phase-header format the "
                "splitter/breakdown didn't recognize. Refusing to report this as "
                "success; review the plan text and _split_plan_by_phase()/"
                "breakdown_phase()."
            ),
        }
    return {"status": "ok"}


def check_regressions_precheck(state: dict, project_dir: str) -> bool:
    """Cheap wrapper around regression_guard.check_regressions(): returns
    True when no previously-successful item's target file has drifted
    since it last succeeded, False when at least one has. See
    regression_guard.py's module docstring for the cost rationale (O(n)
    hashing, never runs build_cmd itself)."""
    drifted = regression_guard.check_regressions(state, project_dir)
    return not drifted


def _check_for_regressions(state: dict, after_task_id: str) -> bool:
    """Cheap hash-based check: only re-runs a possibly-expensive build_cmd
    for a file whose hash actually drifted since it last succeeded (see
    regression_guard.py's own docstring for the full cost rationale).
    Returns True (and hard-stops the caller) only if a drifted file's own
    build_cmd is confirmed still-failing, not merely drifted."""
    drifted = regression_guard.check_regressions(state, state["project_dir"])
    if not drifted:
        return False
    still_broken = []
    for d_entry in drifted:
        entry = d_entry["entry"]
        ok, output = run_build(entry["build_cmd"], state["project_dir"], timeout=300)
        if ok:
            state["results"][d_entry["index"]]["content_hash"] = d_entry["current_hash"]
        else:
            still_broken.append({
                "task_id": entry["task_id"],
                "item": entry["item"],
                "target": entry["target"],
                "build_cmd": entry["build_cmd"],
                "output": output,
            })
    if not still_broken:
        save_run(state)
        return False
    detail = "\n\n".join(
        f"### {b['task_id']} ({b['target']})\nbuild_cmd: `{b['build_cmd']}`\n```\n{b['output']}\n```"
        for b in still_broken
    )
    human_handoff(
        f"{after_task_id}-regression-check",
        f"{len(still_broken)} earlier item(s) regressed after {after_task_id}",
        detail,
    )
    state["regression_flags"].append({
        "after_task_id": after_task_id,
        "detected_at": time.time(),
        "resolved": False,
        "regressed_items": still_broken,
    })
    save_run(state)
    log.warning("[%s] %d earlier item(s) regressed", state["run_id"], len(still_broken))
    return True


def _recheck_regression_flags(state: dict) -> bool:
    """Re-verifies any unresolved regression flag's build_cmd(s) before the
    normal item loop resumes. Returns True (hard-stop) if anything is still
    broken."""
    any_unresolved = False
    for flag in state.get("regression_flags", []):
        if flag.get("resolved"):
            continue
        still_failing = []
        for b in flag["regressed_items"]:
            ok, output = run_build(b["build_cmd"], state["project_dir"], timeout=300)
            if not ok:
                still_failing.append({**b, "output": output})
        if still_failing:
            flag["regressed_items"] = still_failing
            flag["resolved"] = False
            any_unresolved = True
        else:
            flag["resolved"] = True
    save_run(state)
    return any_unresolved


def _run_path(run_id: str) -> Path:
    return RUNS_DIR / f"{run_id}.json"


def save_run(state: dict) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = _run_path(state["run_id"]).with_suffix(".json.tmp")
    state["updated_at"] = time.time()
    with open(temp_path, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(temp_path, _run_path(state["run_id"]))


def load_run(run_id: str) -> dict:
    with open(_run_path(run_id)) as f:
        return json.load(f)


def list_runs() -> list[dict]:
    if not RUNS_DIR.exists():
        return []
    runs = []
    for path in sorted(RUNS_DIR.glob("*.json")):
        try:
            with open(path) as f:
                state = json.load(f)
            runs.append(
                {
                    "run_id": state["run_id"],
                    "status": state["status"],
                    "prompt": state["prompt"],
                    "started_at": state["started_at"],
                }
            )
        except (json.JSONDecodeError, KeyError):
            continue
    return runs


def new_run(prompt: str, project_dir: str) -> dict:
    run_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    state = {
        "run_id": run_id,
        "prompt": prompt,
        "project_dir": str(Path(project_dir).resolve()),
        "status": "planning",
        "plan_text": None,
        "breakdown": None,
        "results": [],
        "regression_flags": [],
        "started_at": time.time(),
    }
    save_run(state)
    return state


def _resolve_path(path_str: str, project_dir: str) -> str:
    p = Path(path_str)
    return str(p if p.is_absolute() else Path(project_dir) / p)


def _default_build_cmd(target: str) -> str:
    """Fallback check when an item has no build_cmd of its own. A plain
    existence check (`test -f`) is right for non-code files (docs, etc.) --
    there's nothing else to validate -- but says nothing about whether a
    code file is actually valid. `py_compile` is stdlib, zero extra
    dependency risk against the target project's own environment, so it's
    safe to always apply to .py targets; other code extensions are left at
    the existence check for now rather than risk depending on a linter/
    interpreter that may not be on PATH in the target project."""
    if target.endswith(".py"):
        return f"python3 -m py_compile {shlex.quote(target)}"
    return f"test -f {shlex.quote(target)}"


def _is_test_target(target: str) -> bool:
    """True when `target` is a test file of the repo's standard shape
    (`tests/test_<name>.py`), the only targets mock_patch_lint applies to."""
    return re.match(r"^tests/test_[^/]+\.py$", target) is not None


def _dispatch_git_item(task_id: str, git_spec: dict, project_dir: str) -> dict:
    action = git_spec.get("action")
    path = _resolve_path(git_spec.get("path", "."), project_dir)
    log.info("[%s] Git action: %s (path=%s)", task_id, action, path)

    if action == "clone":
        result = git_ops.clone(git_spec["url"], path)
    elif action == "pull":
        result = git_ops.pull(path)
    elif action == "push":
        result = git_ops.push(
            path,
            message=git_spec.get("message", f"TriAPI: {task_id}"),
            branch=git_spec.get("branch"),
        )
    else:
        result = {"ok": False, "output": f"unknown git action: {action!r}"}

    if result["ok"]:
        return {"status": "success", "resolved_by": "git"}

    human_handoff(task_id, f"git {action} failed", f"**Output:**\n```\n{result['output']}\n```")
    return {"status": "human_handoff", "resolved_by": None}


# A bare `python`/`python3`/`pytest` token used as the START of a shell
# command or sub-command (start of string, or right after `&&`/`;`/`|`/`!`,
# possibly with leading whitespace and/or leading `VAR=value` env
# assignments, e.g. `PYTHONPATH=. python3 -c ...` -- a common enough shell
# idiom that missing it defeated this exact fix on its own first real
# verify command) -- but NOT already qualified with a path
# (`.venv/bin/python`, `/usr/bin/python3`) or already run through
# `uv run`. Matches the interpreter name only, not every occurrence of the
# substring "python" anywhere in a command (e.g. inside a quoted string or
# a --flag value), which a blunter regex would wrongly touch.
#
# `!` (boolean negation) added after a real miss: `! python3 -m pkg --help |
# grep ... && python3 other.py` only rewrote the SECOND python3 (after `&&`)
# -- the first, immediately after a leading `!`, was silently left bare and
# resolved to the system interpreter instead of the project's `.venv`,
# exactly the failure mode this whole function exists to prevent.
_BARE_PYTHON_RE = re.compile(
    r"(?P<prefix>^|&&|;|\|\|?|\n|!)(?P<ws>\s*(?:[A-Za-z_][A-Za-z0-9_]*=\S+\s+)*)"
    r"(?P<interp>python3?|pytest)(?=\s|$)"
)


def _normalize_build_cmd(build_cmd: str, project_dir: str) -> str:
    """Rewrites a bare `python`/`python3`/`pytest` invocation in build_cmd
    to `uv run python`/`uv run pytest`, IF the target project is uv-managed
    (a `pyproject.toml` or `uv.lock` at its root) -- found for real
    2026-08-12, three separate times in one session: a bare `python`/
    `pytest` resolves to the system interpreter, not the project's own
    `.venv`, and fails on a missing dependency that's very much installed,
    just in the venv nobody asked to use. Two earlier instances were
    hand-patched into a specific run's stored JSON build_cmd (narrow,
    per-item fixes); this is the general, permanent fix, since the
    mistake can originate from a human-written plan prompt just as easily
    as from Gemini's own breakdown -- an instruction-level fix to
    BREAKDOWN_SYSTEM_INSTRUCTION alone would not have caught this third
    instance, which came from a human-authored `triapi plan` prompt, not
    the LLM's paraphrasing of one.

    Deliberately conservative: only rewrites the interpreter token itself,
    at a command/sub-command boundary, and only for a project this signal
    actually applies to -- never touches an already-qualified interpreter
    path or a project with no uv project files at all (this codebase
    itself, TriAPI, has neither and must be left alone)."""
    if not (Path(project_dir, "pyproject.toml").exists() or Path(project_dir, "uv.lock").exists()):
        return build_cmd

    def _sub(m: "re.Match[str]") -> str:
        return f"{m['prefix']}{m['ws']}uv run {m['interp']}"

    return _BARE_PYTHON_RE.sub(_sub, build_cmd)


def _git_diff_for(target: str, project_dir: str) -> str:
    res = subprocess.run(
        ["git", "-C", project_dir, "diff", "--", target],
        capture_output=True,
        text=True,
    )
    return res.stdout


def _run_design_judge(item: dict, result: dict, state: dict, task_id: str) -> dict:
    git_diff = _git_diff_for(item["target"], state["project_dir"])
    judge_res = judge.evaluate_design(git_diff, item["description"])
    if judge_res["approved"]:
        try:
            file_text = Path(state["project_dir"], item["target"]).read_text(encoding="utf-8")
            judge.extract_pattern(file_text, git_diff)
        except Exception as e:
            log.warning("[%s] Best-effort pattern extraction failed: %s", task_id, e)
    else:
        handle_fix_forward(item, judge_res["reason"], state, task_id)
        result = dict(result)  # Ensure result is bound and copied on this path
    return result


def handle_fix_forward(item: dict, refactor_instruction: str, state: dict, task_id: str) -> None:
    """Invokes Tier 3 to apply the design judge's refactor instructions directly."""
    log.info("[%s] Design check failed. Running fix-forward...", task_id)
    target_path = Path(state["project_dir"]) / item["target"]
    target_hash = hashlib.sha256(str(target_path).encode()).hexdigest()
    snapshot_path = Path(tempfile.gettempdir()) / f"triapi_{target_hash}"
    shutil.copy2(target_path, snapshot_path)

    # Verify signature of tier3_escalate.escalate at runtime to prevent coupling risk
    import inspect
    sig = inspect.signature(tier3_escalate.escalate)
    if "revision_note" not in sig.parameters:
        raise TypeError("tier3_escalate.escalate signature does not match expected: missing 'revision_note'")

    esc_res = tier3_escalate.escalate(
        task_id,
        str(target_path),
        revision_note=f"Rewrite this file to apply this refactor: {refactor_instruction}"
    )

    # Verify return shape of tier3_escalate.escalate
    if not isinstance(esc_res, dict) or ("status" not in esc_res and "resolved_by" not in esc_res):
        raise ValueError(f"tier3_escalate.escalate return shape invalid: {esc_res}")

    build_cmd = item.get("build_cmd") or _default_build_cmd(item["target"])
    build_cmd = _normalize_build_cmd(build_cmd, state["project_dir"])

    # Verify against tier3_escalate.py's actual success-status ("status" == "fix_applied" or "resolved_by" == "fix_applied")
    status = esc_res.get("status") or esc_res.get("resolved_by")
    escalate_ok = (status == "fix_applied")

    if escalate_ok:
        rebuild_ok, build_output = run_build(build_cmd, state["project_dir"])
    else:
        rebuild_ok = False
        build_output = ""

    if not escalate_ok or not rebuild_ok:
        shutil.copy2(snapshot_path, target_path)
        log.info("[%s] handle_fix_forward reverted %s: rebuild still failing after Tier 3 refactor rewrite", task_id, item["target"])
        if not escalate_ok:
            reason = esc_res.get("reason") or "Tier 3 escalation did not apply the fix"
        else:
            reason = f"Rebuild failed after Tier 3 rewrite: {build_output}"
        tech_debt.log_tech_debt(str(target_path), reason=reason)


def _is_transient_timeout_failure(result: dict, remaining: int) -> bool:
    """True when an item's failure is a transient infrastructure timeout that
    should be retried in place instead of stopping the whole dispatch run.

    Exact trigger found for real: the tier-4 local Ollama drafting step fed
    back ``HTTPConnectionPool(host='localhost', port=11434): Read timed out.
    (read timeout=300)`` from a slow/busy local model. That is a statement
    about the drafting infrastructure, not about the item -- stopping the
    entire dispatch over it (and forcing an SSH reconnect + manual resume for
    a condition that clears once the model finishes its previous request) is
    the wrong failure mode, so a small number of retries is worth it.

    Deliberately narrow: this must NOT become a generic retry-until-success
    loop. A retrying worker that gets to keep editing a failed item is
    exactly the failure mode the verify_only/heredoc rules in
    BREAKDOWN_SYSTEM_INSTRUCTION exist to prevent (seen for real 2026-08-12:
    a retrying worker loosened its OWN verification script's assertion until
    it trivially passed, leaving the real bug in place). Only a failure whose
    own text says the infrastructure timed out earns a retry, and only while
    retries remain."""
    if remaining <= 0 or result["status"] == "success":
        return False
    # The same timeout can surface from the build/verification command's
    # captured output, not just from the drafting step's stderr/reason --
    # check the common result fields so a verify/build HTTP read timeout is
    # retried like the drafting one is.
    text = " ".join(
        str(result.get(key) or "")
        for key in (
            "stderr", "reason", "output", "stdout", "error", "message",
            "build_error", "verification_error",
        )
    )
    return "timed out" in text.lower()


def dispatch(state: dict) -> dict:
    """Walks state['breakdown']['phases'] sequentially, one item at a time,
    resuming from wherever state['results'] left off (so re-entering an
    already-partially-dispatched run doesn't redo completed items)."""
    phases = state["breakdown"]["phases"]
    state["status"] = "dispatching"
    state.setdefault("regression_flags", [])

    if _recheck_regression_flags(state):
        state["status"] = "stopped_on_failure"
        save_run(state)
        return state

    # We stop on the first non-success item (after retrying transient
    # infrastructure timeouts in-place -- see _is_transient_timeout_failure),
    # so at most one trailing result can be non-success -- drop it so it gets
    # retried rather than being treated as permanently done.
    if state["results"] and state["results"][-1]["status"] != "success":
        retried = state["results"].pop()
        log.info("[%s] Retrying previously-failed item %s on resume", state["run_id"], retried["task_id"])

    save_run(state)
    log.info("[%s] Dispatch starting (%d already-completed item(s) to skip)", state["run_id"], len(state["results"]))

    already_done = len(state["results"])
    seen = 0
    for pi, phase in enumerate(phases):
        for ii, item in enumerate(phase["items"]):
            if seen < already_done:
                seen += 1
                continue
            task_id = f"{state['run_id']}-p{pi}-i{ii}"
            print(f"[{phase['name']}] ({ii + 1}/{len(phase['items'])}) {item['description']}")

            attempts = 0
            while True:
                attempts += 1
                if "git" in item:
                    result = _dispatch_git_item(task_id, item["git"], state["project_dir"])
                elif item.get("verify_only"):
                    # Nothing to draft/change -- run the check as-is, never let
                    # an AI tier overwrite a file (e.g. a test runner script)
                    # that was never supposed to change.
                    if not item.get("build_cmd"):
                        result = {"status": "human_handoff", "resolved_by": None}
                        human_handoff(task_id, "verify_only item has no build_cmd to run", item["description"])
                    else:
                        build_cmd = _normalize_build_cmd(item["build_cmd"], state["project_dir"])
                        try:
                            result = verify_task(task_id, build_cmd, workdir=state["project_dir"])
                        except requests.exceptions.RequestException as e:
                            result = {"status": "error", "reason": str(e), "resolved_by": None}
                else:
                    # An empty build_cmd means Gemini judged this item has nothing
                    # to build (e.g. documentation) -- verify by existence, not by
                    # falling through to orchestrator's default cmake build, which
                    # is nonsensical for a non-code file and would fail forever.
                    # Found for real 2026-08-10: a plain existence check let a
                    # syntax-broken .py edit report "success" (SEARCH/REPLACE
                    # applied cleanly per content_guard/edit_blocks, but the
                    # model didn't preserve the surrounding indentation) --
                    # existence says nothing about validity. _default_build_cmd()
                    # upgrades that floor to an actual syntax check for file
                    # types stdlib can check with zero extra dependencies.
                    build_cmd = item.get("build_cmd") or _default_build_cmd(item["target"])
                    build_cmd = _normalize_build_cmd(build_cmd, state["project_dir"])

                    try:
                        result = run_task(
                            task_id=task_id,
                            description=item["description"],
                            target=item["target"],
                            workdir=state["project_dir"],
                            build_cmd=build_cmd,
                            context_files=item.get("context_files") or [],
                        )
                    except requests.exceptions.RequestException as e:
                        result = {"status": "error", "reason": str(e), "resolved_by": None}

                if _is_transient_timeout_failure(result, 3 - attempts):
                    log.warning(
                        "[%s] Item %s transient timeout (attempt %d/3), backing off then retrying: %s",
                        state["run_id"],
                        task_id,
                        attempts,
                        result.get("stderr") or result.get("reason") or "",
                    )
                    time.sleep(5 * attempts)
                    continue
                break
            is_regular_item = "git" not in item and not item.get("verify_only")
            if result["status"] == "success" and is_regular_item:
                result = _run_design_judge(item, result, state, task_id)

            content_hash = (
                regression_guard.hash_file(Path(state["project_dir"]) / item["target"])
                if is_regular_item and result["status"] == "success"
                else None
            )
            if (
                is_regular_item
                and result["status"] == "success"
                and _is_test_target(item["target"])
            ):
                lint_issues = mock_patch_lint.find_issues(
                    Path(state["project_dir"]) / item["target"],
                    Path(state["project_dir"]),
                )
                if lint_issues:
                    reasons = mock_patch_lint.format_issues(lint_issues)
                    log.warning(
                        "[%s] mock_patch_lint found issues in %s (override to build_failed):\n%s",
                        state["run_id"],
                        item["target"],
                        reasons,
                    )
                    result = dict(result)
                    result["status"] = "build_failed"
                    result["resolved_by"] = None
                    result["reason"] = reasons
                    content_hash = None

            entry = {
                "task_id": task_id,
                "phase": phase["name"],
                "item": item["description"],
                "status": result["status"],
                "resolved_by": result["resolved_by"],
            }
            if is_regular_item:
                entry["target"] = item["target"]
                entry["build_cmd"] = build_cmd
                entry["content_hash"] = content_hash
            state["results"].append(entry)
            save_run(state)
            if result["status"] == "success" and is_regular_item and _check_for_regressions(state, task_id):
                state["status"] = "stopped_on_failure"
                save_run(state)
                return state
            print(f"  -> {result['status']} (resolved_by={result['resolved_by']})")
            log.info("[%s] Item %s: %s (resolved_by=%s)", state["run_id"], task_id, result["status"], result["resolved_by"])

            if result["status"] != "success":
                log.warning("[%s] Dispatch stopping: item %s did not resolve", state["run_id"], task_id)
                state["status"] = "stopped_on_failure"
                save_run(state)
                return state

    log.info("[%s] Dispatch completed: all items resolved", state["run_id"])
    state["status"] = "completed"
    save_run(state)
    return state
