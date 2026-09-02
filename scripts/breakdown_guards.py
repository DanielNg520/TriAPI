import json
import re
import fnmatch
from pathlib import Path

from scripts.tier4_context import TIER4_MAX_CONTEXT_CHARS
from scripts.config_loader import load_tiers

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



