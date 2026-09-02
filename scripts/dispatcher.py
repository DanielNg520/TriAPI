"""Tier 2 dispatcher: breaks a Tier-1 plan into checklist items and dispatches them sequentially."""

import contextlib
import fnmatch
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
from scripts import git_ops, judge, mock_patch_lint, regression_guard, scope_guard, tech_debt, tier3_escalate, librarian_escalate
from scripts.tier4_worker import run_build
from scripts.tier4_context import TIER4_MAX_CONTEXT_CHARS
from scripts.budget_guard import check_tier2_ok, check_tier3_peak_hours_ok, resolve_peak_conditional
from scripts.config_loader import load_tiers
from scripts.orchestrator import human_handoff, run_task, verify_task
from scripts.secrets_loader import load_secrets
from scripts.tri_logging import get_logger

log = get_logger("dispatcher")

RUNS_DIR = Path(__file__).resolve().parent.parent / "logs" / "runs"


class RunAlreadyDispatchingError(RuntimeError):
    """Raised when dispatch(state) is called for a run_id another live process is already dispatching."""


def _lock_path(run_id: str) -> Path:
    return RUNS_DIR / f"{run_id}.lock"


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, just owned by someone else
    return True


@contextlib.contextmanager
def _run_lock(run_id: str):
    """Exclusive pidfile lock for the duration of dispatch(state)."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = _lock_path(run_id)
    if lock_path.exists():
        try:
            other_pid = int(lock_path.read_text().strip())
        except (ValueError, OSError):
            other_pid = None
        if other_pid is not None and _pid_alive(other_pid):
            raise RunAlreadyDispatchingError(
                f"Run {run_id} is already being dispatched by pid {other_pid}. "
                "Wait for it to finish (see `triapi status`), or confirm that "
                "process is really dead before retrying -- do not start a "
                "second dispatch for the same run_id."
            )
        log.warning("[%s] Clearing stale dispatch lock (pid %s no longer alive)", run_id, other_pid)
    lock_path.write_text(str(os.getpid()))
    try:
        yield
    finally:
        try:
            if lock_path.exists() and lock_path.read_text().strip() == str(os.getpid()):
                lock_path.unlink()
        except OSError:
            pass

# BREAKDOWN_SYSTEM_INSTRUCTION itself lives in breakdown_prompts.py (split
# out 2026-08-28 to stay under this repo's file-size ceiling); re-exported
# here so existing callers/tests referencing dispatcher.BREAKDOWN_SYSTEM_INSTRUCTION
# keep working unchanged.
from scripts.breakdown_prompts import BREAKDOWN_SYSTEM_INSTRUCTION

_PHASE_HEADER_RE = re.compile(r"^(?:#{1,6} |\d+\.\s+\*{0,2}_{0,2}Phase\b)", re.IGNORECASE)

# Matches top-level markdown checklist items regardless of bullet style.
_CHECKLIST_ITEM_RE = re.compile(r"^\s*(?:[-*]|\d+\.)\s+", re.MULTILINE)


def _split_plan_by_phase(plan_text: str) -> list[str]:
    """Splits plan markdown into chunks on phase-header markers (one chunk
    per phase, keeping its header), so each phase can be broken down into JSON
    independently. Asking Gemini for the WHOLE plan's JSON in one call fails
    on large plans -- observed: malformed/truncated JSON past ~500 lines of
    output for a real 9-phase plan. Smallest reliable batch, not fewer,
    bigger calls.

    _PHASE_HEADER_RE matches: any ATX heading level ('#' through '######'),
    not just '## ' (a plan using '### Phase 2' silently dropped that whole
    phase under a narrower match, found live 2026-08-12); a numbered
    top-level marker 'N. ' followed by 'Phase ...' or a capitalized word,
    for plans with no '#' markers at all (found live 2026-08-19, run
    20260819-063339-9d23c7) -- deliberately narrower than the ATX case so
    numbered checklist sub-items aren't misread as new phases; and up to
    two leading '*'/'_' emphasis markers before 'Phase' for bold-wrapped
    numbered headers like '1. **Phase 1 -- ...**' (found live 2026-08-20,
    run 20260820-081806-d7c25f). A stray leading '# Title' line produces a
    harmless chunk, filtered out below. A plan with no header at all
    produces exactly one chunk -- the whole text -- correct as long as the
    checklist-item filter below still recognizes it."""
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
    # Drop a leading single-'#' (H1) title/rationale block that precedes a
    # real, "Phase"-named section -- e.g. a plan's own
    # "# Execution Plan -- ..." header followed by prose "Key decisions"
    # bullets before the first "## Phase 1 -- ..." section. Position- and
    # header-level-based, not content-based: the loose bullet check below
    # cannot tell a rationale bullet ("- `X` -> ported to Y because...")
    # apart from a real actionable item, and requiring '- [ ]' checkbox
    # syntax was already tried and reverted (2026-08-13: a real plan using
    # plain, checkbox-less numbered items got silently dropped entirely).
    # An H1 opening a document is reliably a title, never itself a phase in
    # this repo's own convention (every real phase chunk seen is '##' or
    # deeper and named "Phase") -- found live 2026-09-01, run
    # 20260901-135001-dd5f98: this exact block's rationale bullets matched
    # the loose checklist filter and were dispatched as 9 bogus duplicate
    # items before the real phases even started.
    if (
        len(chunks) > 1
        and re.match(r"^#(?!#)\s+", chunks[0])
        and not re.search(r"\bphase\b", chunks[0].splitlines()[0], re.IGNORECASE)
    ):
        chunks = chunks[1:]
    # Drop chunks with no checklist items (e.g. a leading title/context
    # block before the first phase header) -- nothing to break down.
    return [c for c in chunks if _CHECKLIST_ITEM_RE.search(c)]


# Path-like references in item description text; used as deterministic context_files fallback.
_FILE_REF_RE = re.compile(
    r"[\w][\w-]*(?:/[\w.-]+)+\.\w+"
    r"|\b[\w-]+\.(?:py|md|yaml|yml|json|js|ts|jsx|tsx|toml|cfg|ini|sh|txt)\b"
)


_IMPORT_RE = re.compile(r'from scripts import ([\w][\w,\s]*)|import scripts\.(\w+)')
_SCRIPTS_TARGET_RE = re.compile(r'^scripts/(\w+)\.py$')

def _extract_imported_modules(text: str) -> set[str]:
    matches = _IMPORT_RE.findall(text)
    modules = set()
    for match in matches:
        if match[0]:  # 'from scripts import ...'
            modules.update(name.strip() for name in match[0].split(',') if name.strip())
        elif match[1]:  # 'import scripts.module'
            modules.add(match[1])
    return modules

def _enforce_module_import_order(phases: list[dict], project_dir: str) -> str | None:
    """Reorders each phase's items so a scripts/<name>.py item that another
    script item's build_cmd imports is dispatched before the importer.

    The previous implementation hardcoded 'creator' and moved every
    non-importing script item to the front, which both reordered unrelated
    items and never converged when the qualifying item was already first
    (the unconditional `reordering_needed = True` eventually tripped the
    loop cap and returned a spurious error). Instead, use
    _extract_imported_modules() to discover real cross-script dependencies
    and apply a stable topological sort per phase, preserving original
    relative order for unrelated items. Returns an error string only when a
    genuine import cycle remains within a phase."""
    for phase in phases:
        items = phase["items"]

        # Index every scripts/*.py item by its module name so a build_cmd's
        # `from scripts import X` can be resolved to the item that creates X.
        target_indices: dict[str, list[int]] = {}
        for idx, item in enumerate(items):
            m = _SCRIPTS_TARGET_RE.match(item.get("target", ""))
            if m:
                target_indices.setdefault(m.group(1), []).append(idx)

        # Build explicit dependency edges: item idx must come after every
        # script item its build_cmd imports.
        dependencies: dict[int, set[int]] = {}
        for idx, item in enumerate(items):
            if "build_cmd" not in item:
                continue
            if not _SCRIPTS_TARGET_RE.match(item.get("target", "")):
                continue
            deps = {
                dep_idx
                for module in _extract_imported_modules(item["build_cmd"])
                for dep_idx in target_indices.get(module, [])
                if dep_idx != idx
            }
            if deps:
                dependencies[idx] = deps

        # Stable topological sort. Items with no unsatisfied dependencies are
        # emitted in their original order; a full pass with no progress means
        # the remaining script items form a cycle, which is the only case the
        # old loop-cap error should ever have reported.
        ordered: list[int] = []
        placed: set[int] = set()
        remaining = list(range(len(items)))
        while remaining:
            progressed = False
            for idx in list(remaining):
                if dependencies.get(idx, set()).issubset(placed):
                    ordered.append(idx)
                    placed.add(idx)
                    remaining.remove(idx)
                    progressed = True
            if not progressed:
                return "Error: Failed to reorder modules: circular import dependency"
        phase["items"] = [items[i] for i in ordered]

    return None

def _backstop_context_files(item: dict) -> None:
    """Extract referenced paths from the item description into context_files as a deterministic fallback."""
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

    Found for real 2026-08-18 (CARRYOVER.md queue item #1): a step that
    referenced "the test file" with no exact path left the worker with no
    context to ground against, and picking an anchor by alphabetical order
    instead of the project's canonical file led to a copied pattern that
    didn't apply. This is the deterministic fallback for both cases.

    Args:
        project_dir: The root directory of the project.
        exclude: Optional regex pattern to exclude specific files/dirs.

    Returns:
        The path to the anchor test file, or None if none found.
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


def _item_deletes_target_file(item: dict) -> bool:
    """True if this item's own description says it deletes/removes the
    target file wholesale, not merely edits/trims its contents.

    Lets _enforce_file_size_ceiling allow the one step a package-split plan
    always needs -- retiring the oversized flat file once its content has
    moved to new (individually under-ceiling) modules -- without opening
    the door to edit items that would grow an already-oversized file
    further. Requires the delete verb's own grammatical object to be the
    target filename (allowing a few filler words/articles/backticks in
    between, e.g. "delete the old `state.py` file"), not just proximity
    anywhere in the description -- a looser proximity match once let an
    in-place prune ("delete everything ... from `AGENTS.md`") false-
    positive and skip the size-ceiling guard entirely (found live
    2026-08-20). The filler-word list also needs a bare "file"/"module"
    BEFORE the filename, not just after it -- "Delete file
    ohmyllama/conversational.py via git rm" (found live 2026-08-30,
    oh-my-llama Sub-Phase 5H) didn't match the older after-only filler
    list, so _force_verify_only_for_pure_deletions never fired and the
    item went through the fragile LLM-driven edit-block path for a
    whole-file deletion instead."""
    desc = item.get("description", "")
    target_name = Path(item["target"]).name
    pattern = re.compile(
        r"\b(?:delete|remove)\b\s+(?:the\s+)?"
        r"(?:file\s+|module\s+|old\s+|entire\s+|whole\s+|flat\s+)*"
        rf"[`\"']?(?:[\w./-]*/)?{re.escape(target_name)}[`\"']?\b",
        re.I,
    )
    return bool(pattern.search(desc))


def _force_verify_only_for_pure_deletions(phases: list[dict], project_dir: str) -> None:
    """Force verify_only=True on any item whose own description deletes its
    target file wholesale (_item_deletes_target_file), synthesizing a
    correct `rm` + absence-check build_cmd for it if one isn't already
    present.

    Found live 2026-08-29 (run 20260828-182931-264248, oh-my-llama Phase
    5G): the planner marked one deletion item verify_only=true (worked)
    and an identically-shaped deletion item verify_only=false in the SAME
    breakdown -- the latter failed with "SEARCH text not found verbatim",
    because a non-verify_only whole-file deletion routes through the LLM
    SEARCH/REPLACE path, asking a model to reproduce the entire file
    content verbatim just to replace it with nothing. The planner's own
    verify_only choice for this item shape isn't reliable, so enforce it
    here instead.

    Originally this only fired when build_cmd ALREADY contained an `rm` of
    the target, leaving the item alone (still fragile) otherwise. Found
    live 2026-09-02 (run 20260902-005154-7f74ad): the planner instead wrote
    a bare existence check as build_cmd (e.g. `ls scratch.py`) with no `rm`
    at all -- worse, that check is backwards for a post-deletion verify
    (`ls` exits 0 when the file is still THERE). That build_cmd never
    matched the old rm-required condition, so the item fell through to the
    same fragile LLM edit path this guard exists to prevent, crashing Tier
    4/3/2 repeatedly on a plain file deletion. Now synthesizes a correct
    `rm -f <target> && ! test -e <target>` build_cmd whenever a detected
    deletion item doesn't already have a real `rm` of the target in its
    build_cmd, instead of requiring the planner to have gotten it right."""
    for phase in phases:
        for item in phase["items"]:
            if "git" in item or item.get("verify_only") or not item.get("target"):
                continue
            if not _item_deletes_target_file(item):
                continue
            build_cmd = item.get("build_cmd") or ""
            target = item["target"]
            target_name = Path(target).name
            if not re.search(rf"\brm\b[^&|;]*\b{re.escape(target_name)}\b", build_cmd):
                item["build_cmd"] = f'rm -rf "{target}" && ! test -e "{target}"'
            item["verify_only"] = True


def _enforce_file_size_ceiling(phases: list[dict], project_dir: str) -> str | None:
    """Guard file items whose target already exceeds the Tier 4 context ceiling."""
    tier_5 = (load_tiers().get("tier_5_librarian") or {})
    tier_5_enabled = tier_5.get("enabled", True)
    tier_5_globs = tier_5.get("target_globs", [])

    for phase in phases:
        for item in phase["items"]:
            if "git" in item:
                continue
            target_path = Path(project_dir) / item["target"]
            if not target_path.exists():
                continue
            if target_path.is_dir():
                # A directory-deletion item (e.g. "delete the ohmyllama/
                # directory") has no text content to measure against a
                # per-file char ceiling -- read_text() on a directory
                # crashes with IsADirectoryError, found live 2026-09-02
                # (oh-my-llama Phase 7 rename's directory-delete item).
                continue
            existing_chars = len(target_path.read_text())
            if existing_chars > TIER4_MAX_CONTEXT_CHARS:
                if _item_deletes_target_file(item):
                    continue
                if tier_5_enabled and is_doc_target(item["target"], tier_5_globs):
                    item["description"] = (
                        item["description"]
                        + f"\n\nNOTE: {item['target']} is already {existing_chars} chars, over "
                        f"this repo's {TIER4_MAX_CONTEXT_CHARS}-char size ceiling. This target "
                        "routes to tier_5_librarian, not Tier 4, so this isn't a context-window "
                        "block -- but as part of this fix, reduce the file's size (split it into "
                        "smaller, topic-scoped files per the docs/carryover and docs/agents "
                        "overflow convention) anyway, since a doc this large is costly for any "
                        "agent that has to read it directly."
                    )
                    continue
                item["skip_tier4"] = True
                item["description"] = (
                    item["description"]
                    + f"\n\nNOTE: {item['target']} is already {existing_chars} chars, over "
                    f"the Tier 4 context ceiling of {TIER4_MAX_CONTEXT_CHARS} chars -- Tier 4 "
                    "cannot be used on it. As part of this fix, reduce the file's size (split "
                    "it into cohesive smaller files/modules, don't just mechanically truncate "
                    "it) so it drops back under the ceiling -- a one-time patch that leaves it "
                    "still oversized just defers the same problem to the next item that "
                    "touches it."
                )
    return None


def _is_sops_encrypted_file(target_path: Path) -> bool:
    """True if target_path's raw (still-encrypted) content is a sops file.

    sops's own metadata trailer (key info, MAC, version) is stored as a
    top-level "sops" key in the plaintext JSON structure alongside each
    field's "ENC[...]" ciphertext -- no decryption needed to detect this,
    just a JSON parse of the file as it sits on disk."""
    try:
        data = json.loads(target_path.read_text())
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return False
    return isinstance(data, dict) and "sops" in data


def _enforce_no_raw_edits_to_encrypted_files(phases: list[dict], project_dir: str) -> str | None:
    """Post-breakdown guard: refuse any non-verify_only, non-git item whose
    target is a sops-encrypted file.

    Found for real 2026-08-19: an "investigate the openclaw 401" item's
    target was .secret/secrets.json but it wasn't marked verify_only, so
    Tier 4/3/2 each tried to DRAFT/PATCH the file via the normal
    edit_blocks.py SEARCH/REPLACE mechanism -- text-editing sops ciphertext
    invalidated the file's MAC (its cryptographic authentication tag),
    corrupting it, even though the underlying encrypted values were
    untouched (recovered via `sops -d --ignore-mac`, re-encrypted fresh).
    No tier should ever be handed an encrypted file to draft/patch as if
    it were an ordinary text file -- any legitimate change to one must go
    through `sops set`/`--set` inside an explicit, immutable build_cmd on
    a verify_only item (the working pattern this same plan's Phase 1 used
    correctly for the same file), never a drafted content replacement."""
    for phase in phases:
        for item in phase["items"]:
            if "git" in item or item.get("verify_only"):
                continue
            target_path = Path(project_dir) / item["target"]
            if not target_path.exists():
                continue
            if _is_sops_encrypted_file(target_path):
                return (
                    f"Error: {item['target']} is a sops-encrypted file -- it cannot be a "
                    "draft/patch target for any tier (text-editing ciphertext corrupts its "
                    "MAC). Rephrase this item as verify_only: true with the actual change "
                    "expressed as a 'sops set'/'--set' shell command inside build_cmd instead."
                )
    return None



def _breakdown_phase_attempt(phase_text: str, models: list[str], tier2: dict, secrets: dict) -> dict:
    # 2026-09-01: always the generic execute_llm path now, for every
    # provider -- the special-cased "google" branch (gemini_fallback.py's
    # per-model quota fallback) was removed once the account moved off
    # Google AI Studio's free tier, where that quota limit applied.
    provider = tier2.get("provider", "openrouter")

    from scripts.llm_client import execute_llm
    try:
        api_key = secrets.get(tier2.get("api_key_secret", "open_router_api_key"))
        text, _, _, _ = execute_llm(
            provider=provider,
            # .get(), not tier2["endpoint"] -- an agy-provider block (e.g.
            # tier_2_manager's peak_alt, resolved by resolve_peak_conditional()
            # above during DeepSeek's peak billing window) has no "endpoint"
            # key at all, same as every other agy call site in this repo
            # (tier2_escalate.py, tier3_escalate.py both already use .get()
            # here). A strict subscript crashed with KeyError: 'endpoint'
            # the first time a real breakdown ran during peak hours -- found
            # live 2026-09-02.
            endpoint=tier2.get("endpoint"),
            api_key=api_key,
            model=models[0],
            prompt=phase_text,
            system_prompt=BREAKDOWN_SYSTEM_INSTRUCTION,
            # tier2.get("effort"), not omitted -- an agy-provider block
            # (e.g. tier_2_manager's peak_alt, effort: high in
            # config/tiers.yaml) is rejected by the live `agy` CLI with
            # "--model gemini-3.1-pro requires --effort" when no effort is
            # passed at all. Every other real agy call site in this repo
            # (tier2_escalate.py, tier3_escalate.py) already threads this
            # through; this one didn't. Found live 2026-09-02, right after
            # the endpoint KeyError above was fixed -- exit status 1 with no
            # stderr surfaced in the logged exception message (see
            # _call_agy_cli's non-JSON-decode CalledProcessError branch,
            # which doesn't embed stderr like its sibling branches do).
            effort=tier2.get("effort"),
        )
    except Exception as e:
        log.error("Phase breakdown request failed: %s", e)
        return {"status": "error", "reason": f"LLM request failed: {e}", "retry_after": None}
        
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

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


# Top-level checklist bullet: no leading indentation, unlike a bullet's own
# wrapped continuation lines or nested sub-bullets. Deliberately narrower
# than _CHECKLIST_ITEM_RE (which allows any indentation) -- this is used to
# find bullet BOUNDARIES within a phase, where an indented match would
# wrongly split a bullet's own body away from its marker line.
_TOP_LEVEL_BULLET_RE = re.compile(r"^(?:[-*]|\d+\.)\s+")

# Chars: a real incident (2026-09-01/02) showed a single unusually long/
# dense checklist bullet losing most of its technical detail during Tier 2
# phase-breakdown compression, despite BREAKDOWN_SYSTEM_INSTRUCTION's
# explicit "carry forward every concrete technical requirement... failure
# to do so" instruction -- the instruction alone isn't enough once one call
# has to compress many bullets at once including one much longer than the
# rest. No principled threshold exists; this is a conservative starting
# point (well above a normal single-file bullet, which is usually under
# 1,000 chars in practice).
_DENSE_BULLET_THRESHOLD = 4000


def _split_phase_by_dense_bullet(phase_text: str, threshold: int = _DENSE_BULLET_THRESHOLD) -> tuple[str, str] | None:
    """If phase_text has a single top-level checklist bullet whose own text
    clearly dominates the phase (>= threshold chars AND >= half of all
    bullet text combined), split it out so a later breakdown_phase() call
    gives it undivided attention instead of competing for compression
    budget against every other bullet in the same Gemini call.

    Returns None when no split is warranted (nothing to split against, or
    no single bullet dominates -- several long-ish bullets of similar size
    are left alone, since there's no one bullet to isolate). Otherwise
    returns (rest_text, dense_text): two standalone phase-shaped chunks,
    each keeping the phase's own header line so both stay independently
    breakdownable -- rest_text has the dense bullet excised, dense_text is
    the header plus the dense bullet alone."""
    lines = phase_text.splitlines(keepends=True)
    bullet_starts = [i for i, line in enumerate(lines) if _TOP_LEVEL_BULLET_RE.match(line)]
    if len(bullet_starts) < 2:
        return None
    header = "".join(lines[:bullet_starts[0]])
    bullets = [
        "".join(lines[start:(bullet_starts[idx + 1] if idx + 1 < len(bullet_starts) else len(lines))])
        for idx, start in enumerate(bullet_starts)
    ]
    lengths = [len(b) for b in bullets]
    max_idx = max(range(len(lengths)), key=lengths.__getitem__)
    max_len = lengths[max_idx]
    if max_len < threshold or max_len < sum(lengths) / 2:
        return None
    dense_text = header + bullets[max_idx]
    rest_text = header + "".join(b for i, b in enumerate(bullets) if i != max_idx)
    if not _CHECKLIST_ITEM_RE.search(rest_text):
        return None  # the dense bullet was the only bullet -- nothing to split off
    return rest_text, dense_text


def breakdown_phase(phase_text: str, model: str | None = None, max_attempts: int = 3, _dense_split_depth: int = 0) -> dict:
    """Breaks down ONE phase's markdown into {"name", "items"}. See
    _split_plan_by_phase for why this is per-phase, not per-plan.

    Retries on malformed JSON: Gemini's responseMimeType=application/json
    mode is not 100% reliable even for small, simple inputs -- the exact
    same tiny (307-char) phase produced valid JSON on one call and
    malformed JSON on the next, with no input change. Transient/stochastic,
    not deterministic, so retrying is right -- time isn't a constraint
    here, a wrong plan running is what actually costs something.

    An RPM refusal from check_tier2_ok() is retried the same way (the
    sliding window empties within 60s) -- found live 2026-08-12: a large
    plan's per-phase Gemini calls easily burst past a 10 RPM cap, and the
    previous immediate "skipped" return killed the whole breakdown (marking
    the run "failed" instead of resumable) over a condition that clears in
    under a minute. An RPD refusal is NOT retried -- it won't clear until
    the next day, so this case still returns immediately.

    If one checklist bullet clearly dominates this phase's size, it's
    split off (_split_phase_by_dense_bullet) and broken down in its own
    recursive call so it isn't compressed alongside the rest -- see that
    function's docstring for the incident this fixes. `_dense_split_depth`
    is internal (bounds the recursion so unusual markdown, e.g. an
    unindented dash line inside the dense bullet's own body, can't loop
    indefinitely) and isn't meant to be passed by callers."""
    if _dense_split_depth < 3:
        split = _split_phase_by_dense_bullet(phase_text)
        if split is not None:
            rest_text, dense_text = split
            log.info(
                "Phase breakdown: splitting off one dense bullet (%d chars) from the rest (%d chars) for separate breakdown calls",
                len(dense_text), len(rest_text),
            )
            rest_result = breakdown_phase(rest_text, model=model, max_attempts=max_attempts, _dense_split_depth=_dense_split_depth + 1)
            if rest_result["status"] != "ok":
                return rest_result
            dense_result = breakdown_phase(dense_text, model=model, max_attempts=max_attempts, _dense_split_depth=_dense_split_depth + 1)
            if dense_result["status"] != "ok":
                return dense_result
            return {
                "status": "ok",
                "phase": {
                    "name": rest_result["phase"]["name"] or dense_result["phase"]["name"],
                    "items": rest_result["phase"]["items"] + dense_result["phase"]["items"],
                },
            }

    config = load_tiers()
    # Resolve peak_alt like every other real Tier 2 call site (e.g.
    # tier2_escalate.py) does -- without this, phase-breakdown calls kept
    # hitting DeepSeek's raw off-peak config even during its peak billing
    # window, instead of promoting to the configured peak_alt provider.
    tier2 = resolve_peak_conditional(config["tier_2_manager"])
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
    # Only run the post-breakdown guards when this call actually assembled
    # new phases (CARRYOVER.md item #1): on a resume of an already-fully-
    # populated breakdown, `already_done` equals `len(chunks)` at entry, and
    # re-running the guards could retroactively block the resume because a
    # later unrelated item (e.g. AGENTS.md's size) drifted past a guard's
    # threshold since the original breakdown.
    newly_broken_down = already_done < len(chunks)

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

    # CARRYOVER.md item #1: these guards run only on fresh chunk-to-phase
    # assembly, not on resume of an already-fully-populated breakdown -- a
    # later unrelated item drifting past a guard's threshold must not
    # retroactively block a resume (real incident: AGENTS.md's size).
    if newly_broken_down:
        reorder_error = _enforce_module_import_order(state["breakdown"]["phases"], state["project_dir"])
        if reorder_error is not None:
            log.error("Module import order guard failed: %s", reorder_error)
            return {"status": "error", "reason": reorder_error}

        size_error = _enforce_file_size_ceiling(state["breakdown"]["phases"], state["project_dir"])
        if size_error is not None:
            log.error("File size ceiling guard failed: %s", size_error)
            return {"status": "error", "reason": size_error}

        _force_verify_only_for_pure_deletions(state["breakdown"]["phases"], state["project_dir"])

        encrypted_edit_error = _enforce_no_raw_edits_to_encrypted_files(
            state["breakdown"]["phases"], state["project_dir"])
        if encrypted_edit_error is not None:
            log.error("Encrypted-file edit guard failed: %s", encrypted_edit_error)
            return {"status": "error", "reason": encrypted_edit_error}
        save_run(state)

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


def delete_run(run_id: str) -> None:
    path = _run_path(run_id)
    try:
        path.unlink()
    except FileNotFoundError:
        pass


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
    interpreter that may not be on PATH in the target project.

    A test file (`_is_test_target()`) gets a stronger default than plain
    `py_compile`: `py_compile` only checks syntax, so a hallucinated test
    file that imports a nonexistent symbol or calls a nonexistent function
    still passes it cleanly -- confirmed live 2026-08-28, twice, once with
    a fully fabricated test file. Running the test module via `unittest`
    catches import-time and collection-time NameError/ImportError/
    AttributeError as well as syntax errors, at the (small, since these
    are already-fast unit tests by this repo's own convention) cost of
    actually executing it."""
    if _is_test_target(target):
        module = target[:-3].replace("/", ".")
        return f"PYTHONPATH=. python3 -m unittest {module} -v"
    if target.endswith(".py"):
        return f"python3 -m py_compile {shlex.quote(target)}"
    return f"test -f {shlex.quote(target)}"


def _is_test_target(target: str) -> bool:
    """True when `target` is a test file of the repo's standard shape
    (`tests/test_<name>.py`), the only targets mock_patch_lint applies to."""
    return re.match(r"^tests/test_[^/]+\.py$", target) is not None


def is_doc_target(rel_path: str, globs: list[str]) -> bool:
    """True when `rel_path` matches any of `tier_5_librarian.target_globs`,
    case-insensitively (fnmatch).

    Used by dispatch() to route documentation targets out of the Tier 4
    draft/build loop and into the tier_5_librarian escalation path instead.
    '*.md' matches any .md file (PLAN.md, AGENTS.md, README.md, ...);
    'docs/**' matches everything under docs/. Backslashes are normalized to
    slashes and both sides are lowercased so the match is case-insensitive on
    every platform (fnmatch.fnmatch itself only case-normalizes via
    os.path.normcase(), which is a no-op on Linux)."""
    rel_path = rel_path.replace("\\", "/").lower()
    for pattern in globs:
        if fnmatch.fnmatch(rel_path, pattern.replace("\\", "/").lower()):
            return True
    return False


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
# with optional leading whitespace and `VAR=value` env assignments, e.g.
# `PYTHONPATH=. python3 -c ...`) -- but NOT already qualified with a path
# (`.venv/bin/python`, `/usr/bin/python3`) or run through `uv run`. Matches
# the interpreter name only, not every "python" substring in a command.
#
# `!` (negation) added after a real miss: a leading `! python3 ...` left
# that first interpreter bare while a later `&&`-joined one got rewritten,
# resolving to the system interpreter instead of the project's `.venv`.
_BARE_PYTHON_RE = re.compile(
    r"(?P<prefix>^|&&|;|\|\|?|\n|!)(?P<ws>\s*(?:[A-Za-z_][A-Za-z0-9_]*=\S+\s+)*)"
    r"(?P<interp>python3?|pytest)(?=\s|$)"
)


def _normalize_build_cmd(build_cmd: str, project_dir: str) -> str:
    """Rewrites a bare `python`/`python3`/`pytest` invocation in build_cmd
    to `uv run python`/`uv run pytest`, IF the target project is uv-managed
    (a `pyproject.toml` or `uv.lock` at its root) -- found for real
    2026-08-12, three times in one session: a bare interpreter resolves to
    the system Python, not the project's own `.venv`, and fails on a
    dependency that's actually installed, just in the venv nobody asked to
    use. This is the general, permanent fix (vs. two earlier per-run hand
    patches), since the mistake can come from a human-written plan prompt
    just as easily as from the LLM's own breakdown.

    Deliberately conservative: only rewrites the interpreter token itself,
    at a command/sub-command boundary, and only for a project this signal
    actually applies to -- never touches an already-qualified interpreter
    path or a project with no uv project files at all (TriAPI itself has
    neither and must be left alone)."""
    if not (Path(project_dir, "pyproject.toml").exists() or Path(project_dir, "uv.lock").exists()):
        return build_cmd

    def _sub(m: "re.Match[str]") -> str:
        return f"{m['prefix']}{m['ws']}uv run {m['interp']}"

    return _BARE_PYTHON_RE.sub(_sub, build_cmd)


def _resolve_dynamic_target(target: str, project_dir: str) -> str:
    """Dynamically resolves the target path by expanding any dynamic references.

    Args:
        target (str): The original target path which may contain dynamic references.
        project_dir (str): The directory from which to run the expansion script.

    Returns:
        str: The resolved target path after expansion, or the original target if no expansion was needed.
    """
    if "$(" not in target and "`" not in target and "${" not in target:
        return target

    try:
        completed_process = subprocess.run(
            ["bash", "-c", f'printf %s "{target}"'],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=30
        )
        if completed_process.returncode == 0:
            return completed_process.stdout.strip()
    except (subprocess.TimeoutExpired, Exception) as e:
        log.warning("Dynamic target expansion failed for %r: %s", target, e)

    return target


def _git_diff_for(target: str, project_dir: str) -> str:
    res = subprocess.run(
        ["git", "-C", project_dir, "diff", "--", target],
        capture_output=True,
        text=True,
    )
    return res.stdout


def _design_judge_applies(resolved_by: str | None, critique_cfg: dict) -> bool:
    """Mirrors orchestrator.py's _critique_and_maybe_revise_inner() gate: the
    design judge is advisory scaffolding scoped to the same tiers as the
    diff-quality critique step, driven by config/tiers.yaml's critique block
    (critique.enabled, critique.applies_to_tiers) so tier_5 (and any future
    tier not listed there) is never routed through it."""
    if not critique_cfg.get("enabled", False):
        return False
    return resolved_by in critique_cfg.get("applies_to_tiers", [])


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
        ff = handle_fix_forward(item, judge_res["reason"], state, task_id)
        if isinstance(ff, dict) and (ff.get("fixed") or ff.get("reverted")):
            # `fixed`: fix-forward's own edit applied and rebuilt clean.
            # `reverted`: fix-forward's edit attempt failed, but the file
            # was restored to the state that already passed run_task()'s
            # own build check before this advisory judge ever ran -- the
            # item's original success stands either way. See
            # handle_fix_forward()'s docstring-comment for why downgrading
            # here was wrong (discarded working Tier 4 output over an
            # unrelated Tier 3 SEARCH/REPLACE failure, confirmed live
            # 2026-08-28).
            return result

        downgraded = dict(result)
        downgraded["status"] = "build_failed"
        downgraded["resolved_by"] = None
        downgraded["reason"] = ff.get("reason") if isinstance(ff, dict) else "fix-forward repair failed"
        return downgraded
    return result


def _is_deepseek_peak_hours(now_utc: time.struct_time | None = None) -> bool:
    """True when the given UTC time (default: now) is inside DeepSeek's peak
    billing window (06:00-10:00 UTC). Used by handle_fix_forward to warn about
    expensive Tier 3 escalations. Delegates to
    budget_guard.check_tier3_peak_hours_ok(), which reads peak windows from
    config/tiers.yaml and applies weekend (Sat/Sun) exceptions in Beijing
    time -- on weekends the off-peak rate is in effect and this returns
    False."""
    return not check_tier3_peak_hours_ok()["ok"]


def handle_fix_forward(item: dict, refactor_instruction: str, state: dict, task_id: str) -> dict:
    """Invokes Tier 3 to apply the design judge's refactor instructions directly.

    Note: Tier 3 (tier3_escalate) uses DeepSeek, which charges a higher rate
    during peak billing hours 06:00-10:00 UTC. This is called from the design
    judge's rejection path only, so the added cost is scoped to items that
    already failed design review.
    """
    if _is_deepseek_peak_hours():
        log.warning(
            "[%s] Tier 3 is in DeepSeek peak billing hours (06:00-10:00 UTC); "
            "fix-forward escalation may be expensive",
            task_id,
        )
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
        if not escalate_ok:
            log.info("[%s] handle_fix_forward reverted %s: Tier 3 could not apply the refactor", task_id, item["target"])
            reason = esc_res.get("reason") or "Tier 3 escalation did not apply the fix"
        else:
            log.info("[%s] handle_fix_forward reverted %s: rebuild failed after Tier 3 refactor rewrite", task_id, item["target"])
            reason = f"Rebuild failed after Tier 3 rewrite: {build_output}"
        tech_debt.log_tech_debt(str(target_path), reason=reason)

    if escalate_ok and rebuild_ok:
        return {"fixed": True, "reason": "fix-forward edit applied and rebuild passed"}
    elif not escalate_ok:
        # The design judge's critique is advisory (see this function's
        # caller, _run_design_judge): the item's ORIGINAL build already
        # passed before fix-forward was ever invoked -- `snapshot_path` was
        # taken from that exact passing state, so the revert above restores
        # a demonstrably-working file, not a broken one. Reporting
        # `fixed: False` here previously caused _run_design_judge to
        # downgrade the whole item to `build_failed` even though the file
        # on disk was correctly restored to working code -- confirmed live
        # 2026-08-28, three times in one run, discarding a passing Tier 4
        # draft over an unrelated SEARCH/REPLACE-apply failure in Tier 3's
        # own remedy attempt. `reverted: True` lets the caller keep the
        # item's original success status instead, while the tech_debt
        # entry above still records the judge's concern for later review.
        return {"fixed": False, "reverted": True, "reason": "tier3 escalation produced no applicable SEARCH/REPLACE edit; file reverted to its last-passing state and tech debt logged"}
    else:
        # Same reasoning as above -- the revert on this path also restores
        # the pre-fix-forward passing snapshot, not a broken file.
        return {"fixed": False, "reverted": True, "reason": "rebuild failed after fix-forward edit; file reverted to its last-passing state and tech debt logged"}


def _is_transient_timeout_failure(result: dict, remaining: int) -> bool:
    """True when an item's failure is a transient infrastructure timeout that
    should be retried in place instead of stopping the whole dispatch run.

    Exact trigger found for real: the tier-4 local Ollama drafting step fed
    back a Read-timed-out error from a slow/busy local model -- a statement
    about the drafting infrastructure, not the item, so stopping the whole
    dispatch (forcing an SSH reconnect + manual resume) is the wrong
    response; a small number of retries is worth it instead.

    Deliberately narrow: this must NOT become a generic retry-until-success
    loop -- a retrying worker that keeps editing a failed item is exactly
    the failure mode verify_only/heredoc rules exist to prevent (seen live
    2026-08-12: a retrying worker loosened its own verification assertion
    until it trivially passed, leaving the real bug in place). Only a
    failure whose own text says the infrastructure timed out earns a
    retry, and only while retries remain."""
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
    already-partially-dispatched run doesn't redo completed items).

    Wrapped in _run_lock() so two processes can never dispatch the same
    run_id concurrently -- see RunAlreadyDispatchingError's docstring."""
    with _run_lock(state["run_id"]):
        return _dispatch_locked(state)


def _dispatch_locked(state: dict) -> dict:
    phases = state["breakdown"]["phases"]
    state["status"] = "dispatching"
    state.setdefault("regression_flags", [])

    # tier_5_librarian routes documentation targets out of the Tier 4
    # draft/build loop and into the librarian escalation path instead.
    _cfg = load_tiers()
    tier_5 = (_cfg.get("tier_5_librarian") or {})
    critique_cfg = _cfg.get("critique", {})

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
                if item.get("target"):
                    resolved_target = _resolve_dynamic_target(item["target"], state["project_dir"])
                else:
                    resolved_target = None
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
                    build_cmd = item.get("build_cmd") or _default_build_cmd(resolved_target)
                    build_cmd = _normalize_build_cmd(build_cmd, state["project_dir"])

                    # Documentation targets (anything matching
                    # tier_5_librarian.target_globs, e.g. *.md, docs/**) are
                    # routed to the tier_5_librarian escalation path instead of
                    # the Tier 4 draft/build loop when tier_5_librarian is
                    # enabled; a disabled block falls through to the existing
                    # path unchanged.
                    doc_target = is_doc_target(
                        resolved_target, tier_5.get("target_globs", [])
                    )
                    if tier_5.get("enabled", True) and doc_target:
                        log.info("[%s] [ROUTING] %s -> tier_5_librarian", task_id, resolved_target)
                        try:
                            result = librarian_escalate.run(
                                task_id=task_id,
                                description=item["description"],
                                target=resolved_target,
                                workdir=state["project_dir"],
                                # Without this, librarian_escalate.run()'s own
                                # verify_cmd_resolved falls through to the
                                # literal no-op "true", meaning the item's
                                # real build_cmd never ran for a tier_5-routed
                                # item and "Verification succeeded" logged
                                # unconditionally. Confirmed live 2026-08-28:
                                # a MAPPING.md update reported success twice
                                # while writing to a wrong resolved path, and
                                # the item's own build_cmd (git diff check)
                                # would have caught it immediately, had it run.
                                verify_cmd=build_cmd,
                            )
                        except requests.exceptions.RequestException as e:
                            result = {"status": "error", "reason": str(e), "resolved_by": None}
                    else:
                        try:
                            result = run_task(
                                task_id=task_id,
                                description=item["description"],
                                target=resolved_target,
                                workdir=state["project_dir"],
                                build_cmd=build_cmd,
                                context_files=item.get("context_files") or [],
                                skip_tier4=item.get("skip_tier4", False),
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
            if result["status"] == "success" and is_regular_item and _design_judge_applies(result.get("resolved_by"), critique_cfg):
                result = _run_design_judge(item, result, state, task_id)

            content_hash = (
                regression_guard.hash_file(Path(state["project_dir"]) / resolved_target)
                if is_regular_item and result["status"] == "success"
                else None
            )
            if (
                is_regular_item
                and result["status"] == "success"
                and _is_test_target(resolved_target)
            ):
                lint_issues = mock_patch_lint.find_issues(
                    Path(state["project_dir"]) / resolved_target,
                    Path(state["project_dir"]),
                )
                if lint_issues:
                    reasons = mock_patch_lint.format_issues(lint_issues)
                    log.warning(
                        "[%s] mock_patch_lint found issues in %s (override to build_failed):\n%s",
                        state["run_id"],
                        resolved_target,
                        reasons,
                    )
                    result = dict(result)
                    result["status"] = "build_failed"
                    result["resolved_by"] = None
                    result["reason"] = reasons
                    content_hash = None

            scope_concerns = []
            if is_regular_item and result["status"] == "success":
                scope_concerns = scope_guard.find_out_of_scope_functions(
                    _git_diff_for(resolved_target, state["project_dir"]),
                    item["description"],
                )
                if scope_concerns:
                    log.warning(
                        "[%s] Possible out-of-scope edit in %s: touched %s, not named "
                        "in item description -- not blocking, review this diff by hand",
                        task_id, resolved_target, scope_concerns,
                    )

            entry = {
                "task_id": task_id,
                "phase": phase["name"],
                "item": item["description"],
                "status": result["status"],
                "resolved_by": result["resolved_by"],
            }
            if is_regular_item:
                entry["target"] = resolved_target
                entry["build_cmd"] = build_cmd
                entry["content_hash"] = content_hash
                if scope_concerns:
                    entry["scope_concerns"] = scope_concerns
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
