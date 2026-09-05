"""Heuristic, non-blocking check for out-of-scope function edits.

Queue item found 2026-08-28: Tier 3 made two unauthorized out-of-scope
edits in the same session, both explicitly outside the item's stated diff
scope -- rewrote `_call_claude_cli()` when only `_call_agy_cli()` was in
scope, and separately rewrote `handle_fix_forward()`'s peak-hours logic
when only item-target wiring was in scope. Both were caught only by hand
review of `git diff` before commit.

This module gives dispatcher.py an automated, best-effort version of that
same hand review: git's own diff driver already tags each hunk with its
enclosing Python function/class name (`@@ ... @@ def foo(` -- confirmed
live, no .gitattributes/config needed, this is git's built-in xfuncname
regex for .py files). Comparing those names against what the item's own
description names lets a scope-creep edit be flagged automatically.

Blind spot found and fixed live, 2026-08-28: the hunk-header heuristic
alone MISSES a fully deleted function -- git anchors the hunk header to
whichever function precedes the deletion in the pre-image context, not
the deleted function's own name (its `def` line is inside the hunk body,
not before it). Confirmed live: an item scoped to
`_is_deepseek_peak_hours()` (docstring-only, "do not change any
implementation logic") instead had that whole function deleted and
inlined elsewhere by Tier 4, and this module reported zero concerns
because the deleted function's name literally never appeared as a hunk
header -- only the *preceding* function (`_run_design_judge`) and the
one it got inlined into (`handle_fix_forward`) did, neither named in the
description, so the "can't tell, don't guess" branch fired instead of
flagging. Fixed by also scanning each hunk's body for `-def`/`-class`
(deleted) and `+def `/`+class ` (added) lines directly, unioned with the
hunk-header names -- this catches a fully deleted or newly added
function even when it never appears as any hunk's own header context.

Deliberately advisory, not enforced: a real, legitimate change sometimes
does need to touch a helper the description didn't name (e.g. renaming a
shared symbol). Flagging false positives as a hard failure would stall
correct work, so this only surfaces a warning for human review -- see
dispatcher.py's dispatch() loop for how the flag is attached to the
item's result entry (`scope_concerns`), the same non-blocking pattern
mock_patch_lint's *test-file* lint findings use, generalized to any
target.
"""

import re
from pathlib import Path

_HUNK_FUNC_RE = re.compile(r"^@@[^@]*@@\s*(?:def|class)\s+(\w+)", re.MULTILINE)

# Catches a def/class line's own name directly from a hunk's added or
# removed body lines (not just the hunk header's preceding-function
# context) -- see the module docstring's "Blind spot" note for why the
# header alone isn't enough for a fully deleted function.
_BODY_DEF_RE = re.compile(r"^[+-]\s*(?:def|class)\s+(\w+)", re.MULTILINE)


def find_out_of_scope_functions(git_diff: str, description: str) -> list[str]:
    """Returns the list of function/class names touched by `git_diff`
    that are NOT named anywhere in `description` -- but ONLY when
    `description` names at least one function/class that IS actually
    touched, i.e. the description clearly scopes this edit to specific
    function(s) rather than being generic prose about the file as a
    whole. Returns [] when nothing looks out of scope, when the diff has
    no per-hunk function context to check (e.g. pure module-level edits),
    or when the description doesn't name any specific function at all.
    """
    touched_unique = list(dict.fromkeys(_HUNK_FUNC_RE.findall(git_diff) + _BODY_DEF_RE.findall(git_diff)))
    if not touched_unique:
        return []
    named_in_scope = [
        name for name in touched_unique if re.search(rf"\b{re.escape(name)}\b", description)
    ]
    if not named_in_scope:
        # The description never named any of the touched functions by name
        # at all -- can't tell whether it's generic ("fix the bug in
        # llm_client.py") or actually scoped, so don't guess.
        return []

    return [name for name in touched_unique if name not in named_in_scope]


_IDENTIFIER_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")


def extract_named_symbols(text: str) -> set[str]:
    """Returns the set of tokens in `text` that look like a specific
    Python function/class name rather than ordinary prose -- either
    PascalCase (an uppercase letter appears after the first character,
    e.g. `CheckJulesOkTests`) or containing an underscore (e.g.
    `_is_deepseek_peak_hours`). A single capitalized English word
    (`Move`, `Test`) matches neither shape and is excluded, so this
    stays precise enough to use directly against free-text item
    descriptions, not just git-diff hunk headers.
    """
    symbols = set()
    for token in _IDENTIFIER_RE.findall(text):
        # A PascalCase-shaped token also needs a lowercase letter somewhere,
        # not just internal uppercase -- otherwise a bare all-caps acronym
        # used as ordinary prose (e.g. "NOT", "LLM", "PLAN") would qualify
        # too. Confirmed live 2026-09-04 (run 20260904-172545-dd6087):
        # detect_relocation_intent() flagged "NOT"/"LLM"/"PLAN" as missing
        # relocation targets even though they were never named as such.
        if "_" in token or (
            any(c.isupper() for c in token[1:]) and any(c.islower() for c in token)
        ):
            symbols.add(token)
    return symbols


_RELOCATION_VERBS = (
    "move", "moved", "split", "split out", "extract", "extracted",
    "relocate", "relocated",
)


def detect_relocation_intent(description: str) -> set[str]:
    """Returns the symbol names `description` names as being moved,
    split out, extracted, or relocated -- but ONLY when `description`
    also uses one of those relocation verbs, so a description that
    merely mentions a symbol for some other reason (e.g. "fix a bug in
    TestBeta") never triggers this. Feeds a hard-blocking post-edit
    existence check in dispatcher.py's dispatch loop -- deliberately
    separate from find_out_of_scope_functions()'s advisory-only
    out-of-scope-touch warning; see that function's docstring for why
    THIS check does not need the same false-positive caution (a symbol
    named as a relocation target either still exists somewhere after
    the edit, or it doesn't).
    """
    # (?<!\.) excludes a method call named after a relocation verb (e.g.
    # `build_output.split()`, `text.split(...)`) from counting as relocation
    # intent -- this is the root cause of the ORIGINAL false build_failed
    # bug this whole investigation was for (run 20260904-154839-ccfa17,
    # tracked in knowledge/TECH_DEBT.md): an item description that used
    # `" ".join(build_output.split())` was flagged as naming a "split"
    # relocation, and `build_output` (a local variable, not a def/class)
    # was then reported "missing," permanently failing three genuinely
    # successful tier attempts in a row (tier_4, tier_3, tier_2).
    lowered = description.lower()
    if not any(re.search(rf"(?<!\.)\b{re.escape(verb)}\b", lowered) for verb in _RELOCATION_VERBS):
        return set()
    # A "Verify: `...`" clause is a shell command, and a parenthetical
    # aside (an "out of scope"/"do NOT" caveat, an "e.g." example) is
    # commentary, not a relocation target -- strip both before extracting.
    # A token named as "<token>.py" or "scripts.<token>" is also a module
    # being referenced by its own name (a file path or package-qualified
    # import target), not a def/class expected to still exist under
    # symbol_exists_in_project()'s check. Confirmed live 2026-09-04 (run
    # 20260904-172545-dd6087) across three separate items: "py_compile",
    # "dispatcher_git.py"/"scripts.dispatcher_git", and then
    # "HTTPError"/"PLAN"/"tier2_escalate" (all from one parenthetical
    # caveat) were each wrongly flagged as missing, failing otherwise
    # genuinely successful moves.
    scoped = description.split("Verify:", 1)[0]
    scoped = re.sub(r"\([^()]*\)", " ", scoped)
    candidates = extract_named_symbols(scoped)
    return {
        sym for sym in candidates
        if f"{sym}.py" not in description and f"scripts.{sym}" not in description
    }


_SKIP_DIR_NAMES = {".git", "logs", "__pycache__", ".venv", "venv"}


def symbol_exists_in_project(project_dir: str, symbol_name: str) -> bool:
    """Returns True if `symbol_name` is defined (`def NAME(`, `class NAME:`
    / `class NAME(`, or a module-level constant assignment `NAME = ` /
    `NAME: `) in any .py file under `project_dir` (excluding .git/, logs/,
    __pycache__/, and venv dirs), False if no file defines it anywhere.
    Used to confirm a symbol an item's own description named as a
    relocation target actually landed somewhere in the project, not just
    in whatever the item's own `target` file happened to be. The constant
    forms matter: confirmed live 2026-09-04 (run 20260904-172545-dd6087)
    -- an item named `BREAKDOWN_SYSTEM_INSTRUCTION` (a plain module-level
    constant, not a def/class) as a relocation target, and this check
    couldn't see it defined anywhere, wrongly failing a correct move that
    had actually reused an existing import rather than duplicating it.
    """
    root = Path(project_dir)
    needles = (
        f"def {symbol_name}(",
        f"class {symbol_name}:",
        f"class {symbol_name}(",
        f"{symbol_name} = ",
        f"{symbol_name}: ",
    )
    for path in root.rglob("*.py"):
        if any(part in _SKIP_DIR_NAMES for part in path.relative_to(root).parts):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if any(needle in content for needle in needles):
            return True
    return False
