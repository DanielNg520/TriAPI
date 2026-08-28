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
    touched = _HUNK_FUNC_RE.findall(git_diff) + _BODY_DEF_RE.findall(git_diff)
    if not touched:
        return []

    touched_unique = list(dict.fromkeys(touched))  # de-dupe, keep order
    named_in_scope = [
        name for name in touched_unique if re.search(rf"\b{re.escape(name)}\b", description)
    ]
    if not named_in_scope:
        # The description never named any of the touched functions by name
        # at all -- can't tell whether it's generic ("fix the bug in
        # llm_client.py") or actually scoped, so don't guess.
        return []

    return [name for name in touched_unique if name not in named_in_scope]
