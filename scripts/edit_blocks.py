"""SEARCH/REPLACE-block editing for changes to an already-existing file.

PLAN.md Phase 13b. Every tier used to ask for "the complete, corrected file
contents" even for a one-line change to a real, existing file -- found for
real 2026-08-10 that this is fundamentally unsafe: a model asked to
reproduce a large file verbatim while also fixing something routinely just
regenerates a shorter, plausible-looking version instead, silently
dropping everything it judged irrelevant to the fix (705 -> 146 lines on
one real file, 529 -> 116 on another). content_guard.py is the safety net
that catches this after the fact; this module is the actual fix -- for an
existing file, ask for a small, targeted patch instead of the whole file,
so there is nothing large to accidentally drop in the first place.

Only applies to EDITS. A brand-new file has no existing content to lose,
so every tier keeps generating those in full via extract_code() -- there
is no "search" text to anchor a patch to.
"""

import re
from pathlib import Path

BLOCK_RE = re.compile(
    # REPLACE group's trailing "\n" is optional (not "\n>"): a delete-only
    # edit's most natural rendering is an EMPTY REPLACE section with the
    # closing marker immediately after "=======", no blank line in between
    # -- found for real 2026-08-12, a trivial "remove this one import line"
    # task failed at all four tiers/nine consecutive attempts because every
    # model wrote exactly that natural empty form and the old mandatory
    # "\n" before ">>>" could never match it (there was no spare newline
    # character left after "={3,}\s*\n" already consumed the only one).
    r"<{3,}\s*SEARCH\s*\n(.*?)\n={3,}\s*\n(.*?)\n?>{3,}\s*REPLACE",
    re.DOTALL | re.IGNORECASE,
)
_FENCE_RE = re.compile(r"^```[a-zA-Z0-9_+-]*\n(.*)\n```$", re.DOTALL)

EDIT_INSTRUCTION = (
    "The target file already exists (its current contents are included below). "
    "Make ONLY the specific change(s) needed for this task -- do NOT rewrite or "
    "reproduce the whole file. Respond with one or more SEARCH/REPLACE blocks in "
    "EXACTLY this format, and nothing else (no explanation, no surrounding code fence):\n\n"
    "<<<<<<< SEARCH\n"
    "(the exact existing lines to find, copied verbatim from the current file "
    "shown below, including enough surrounding context that this text appears "
    "only once in the file)\n"
    "=======\n"
    "(the replacement lines)\n"
    ">>>>>>> REPLACE\n\n"
    "Use multiple SEARCH/REPLACE blocks for multiple separate changes elsewhere in "
    "the file. Each SEARCH block's text must match the current file EXACTLY -- same "
    "whitespace, same characters, no added/removed line numbers -- and must be "
    "unique in the file. To delete lines, leave the REPLACE section empty."
)


def build_edit_prompt_header(target_name: str, lessons_block: str = "") -> str:
    header = (
        f"You are a coding/writing assistant working on {target_name}. "
        + EDIT_INSTRUCTION
    )
    if lessons_block:
        header += "\n\n" + lessons_block
    return header


def apply_edit_blocks(original: str, response_text: str) -> tuple[str | None, str]:
    """Parses SEARCH/REPLACE blocks out of response_text and applies them to
    original in order. Returns (new_content, "") on success, or (None,
    error_message) if the response can't be safely applied -- no blocks
    found, a SEARCH text missing from the file, or a SEARCH text matching
    more than once (ambiguous). Callers must treat a None return as a
    failure (retry/escalate), never fall back to overwriting the file with
    raw response_text -- that would reopen exactly the hole this module
    closes."""
    # Prevents cmd_dispatch's AttributeError when model output is None/non-string.
    if not isinstance(response_text, str) or not response_text.strip():
        return None, "model returned no usable text (None or empty)"
    text = response_text.strip()
    fence_match = _FENCE_RE.match(text)
    if fence_match:
        text = fence_match.group(1)

    blocks = BLOCK_RE.findall(text)
    if not blocks:
        return None, "No SEARCH/REPLACE blocks found in the response."

    content = original
    for i, (search, replace) in enumerate(blocks, start=1):
        count = content.count(search)
        if count == 0:
            return None, f"Block {i}: SEARCH text not found verbatim in the current file."
        if count > 1:
            return None, (
                f"Block {i}: SEARCH text matches {count} locations in the file -- "
                "ambiguous, needs more surrounding context to be unique."
            )
        content = content.replace(search, replace, 1)

    # Found for real 2026-08-10: a malformed multi-block response (missing
    # or duplicated markers between blocks) can fool BLOCK_RE's non-greedy
    # matching into treating two separate, differently-shaped edits as one
    # block whose SEARCH/REPLACE text happens to still be found/unique --
    # apply "succeeds" with no error, but the applied REPLACE text itself
    # contains a stray marker line (e.g. a leftover "=======" divider),
    # landing literally in the file. A leaked marker is never valid output
    # for any real file, so this is a strong, cheap, format-agnostic
    # backstop regardless of the exact malformed shape that produced it.
    #
    # Found for real 2026-09-03 (run 20260903-220300-6f7574, both Tier 2
    # attempts on the same item): checking only the exact 7-char markers
    # above misses shorter malformed dividers -- a bare "====" (4 equals)
    # from a truncated/clipped model output leaked into orchestrator.py
    # twice this session. It only got caught because it landed at module
    # top level and was a syntax error; the same leak inside a string or
    # comment would have been silently accepted. Generalize: catch any
    # run of 3+ <, =, or > characters alone on a line, BUT ignore lines
    # that were already present in the original (mirrors the existing
    # "marker not in original" exemption so legitimate Markdown setext-
    # style ==== headers in the file are not flagged as leaks) -- only a
    # NEW such line, introduced by the patch, counts as a leak.
    _LEAK_RE = re.compile(r"^[<=>]{3,}\s*$", re.MULTILINE)
    leaked = []
    for line in _LEAK_RE.findall(content):
        # Need to confirm it's actually present in original; if it is, this
        # is a legitimate Markdown setext divider, not a leak.
        if line not in original:
            leaked.append(line)
    if leaked:
        return None, (
            f"Applied result contains a leaked divider-like line "
            f"({leaked[0]!r}) -- response was malformed "
            "(shorter/duplicated/truncated marker slipped through)."
        )

    return content, ""
