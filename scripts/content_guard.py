"""Guards against an AI tier silently deleting most of an existing file's
content while claiming to make a small, targeted edit.

Found for real 2026-08-10 (PLAN.md Phase 13a): dispatching a real 96-item
plan against oh-my-llama, both Tier 4 (Ollama) and Tier 3 (DeepSeek) --
asked for a one-line addition or a two-line removal to an existing file --
instead regenerated the *entire* file from scratch and silently dropped
everything else: `docs/semai-phase3.md` 705 -> 146 lines, `docs/overhaul.md`
427 -> 129 lines, `ohmyllama/memory.py` 529 -> 116 lines. Every item's own
build_cmd (existence check, `py_compile`, a `grep` for the one new string)
passed anyway, since none of them look at the rest of the file -- so every
one of these reported `status: success`.

Tier 3 is in DeepSeek peak billing hours 06:00-10:00 UTC (LA local
2026-08-19T23:33:06.698767-07:00, UTC 2026-08-20T06:33:06.698767+00:00).

Every tier's write of an *existing* file must go through check_write()
before landing on disk. A brand-new file has nothing to lose against the
retention-ratio check below, but the size ceiling check applies to every
write regardless -- new file or edit -- so a tier can never author a file
already too big for Tier 4 to ever work on again. Found for real
2026-08-19: a plan's own documentation-update item pushed AGENTS.md from
183KB to 213KB, retroactively blocking dispatcher._enforce_file_size_
ceiling on every later run -- nothing at write time had stopped it from
growing that far in the first place.
"""

from pathlib import Path

from scripts.tri_logging import get_logger

log = get_logger("content_guard")

REJECTED_DIR = Path(__file__).resolve().parent.parent / "logs" / "rejected_writes"

# Below this line count, a full rewrite is plausibly intentional (e.g. a
# short file that's genuinely being replaced) -- not worth flagging.
MIN_LINES_TO_CHECK = 15
# Fraction of the original file's non-blank lines that must still appear
# verbatim in the proposed replacement. 705 -> 146 lines is a 0.15 ratio;
# 0.5 gives real edits (which touch a handful of lines) wide headroom while
# still catching a wholesale regeneration.
MIN_RETENTION_RATIO = 0.5

# MAX_WRITE_CHARS now shares its value with scripts.dispatcher.TIER4_MAX_CONTEXT_CHARS via scripts/tier4_context.py
from scripts.tier4_context import TIER4_MAX_CONTEXT_CHARS as MAX_WRITE_CHARS


def _nonblank_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def check_write(task_id: str, target_path: Path, new_content: str) -> dict:
    """Returns {"ok": True} to allow the write. Returns {"ok": False, "reason":
    ...} to refuse it -- the caller must NOT write new_content to target_path
    in that case; the original stays untouched (or, for a new file, simply
    never created). The refused content is saved to
    logs/rejected_writes/<task_id>.txt so a human can still see what the
    model proposed."""
    if len(new_content) > MAX_WRITE_CHARS:
        REJECTED_DIR.mkdir(parents=True, exist_ok=True)
        rejected_path = REJECTED_DIR / f"{task_id}.txt"
        rejected_path.write_text(new_content)
        reason = (
            f"Refused write to {target_path}: proposed content is "
            f"{len(new_content)} chars, over the {MAX_WRITE_CHARS}-char Tier 4 "
            f"context ceiling. Writing it would make the file permanently "
            f"unworkable by Tier 4 (dispatcher._enforce_file_size_ceiling "
            f"blocks any later item that targets an oversized file). If this "
            f"file genuinely needs to hold this much content, split it into "
            f"cohesive smaller files/modules instead of writing one oversized "
            f"file. Original left untouched (or file not created); proposed "
            f"content saved to {rejected_path} for review."
        )
        log.warning("[%s] %s", task_id, reason)
        return {"ok": False, "reason": reason, "content_chars": len(new_content)}

    if not target_path.exists():
        return {"ok": True}

    original = target_path.read_text(errors="replace")
    old_lines = _nonblank_lines(original)
    if len(old_lines) < MIN_LINES_TO_CHECK:
        return {"ok": True}

    new_lines = set(_nonblank_lines(new_content))
    retained = sum(1 for line in old_lines if line in new_lines)
    ratio = retained / len(old_lines)

    if ratio >= MIN_RETENTION_RATIO:
        return {"ok": True}

    REJECTED_DIR.mkdir(parents=True, exist_ok=True)
    rejected_path = REJECTED_DIR / f"{task_id}.txt"
    rejected_path.write_text(new_content)
    reason = (
        f"Refused write to {target_path}: only {ratio:.0%} of the original "
        f"{len(old_lines)} non-blank lines survive in the proposed replacement "
        f"({len(new_lines)} non-blank lines), below the {MIN_RETENTION_RATIO:.0%} "
        f"threshold. This usually means the model regenerated the whole file "
        f"instead of making a targeted edit, silently deleting unrelated content. "
        f"Original left untouched; proposed content saved to {rejected_path} for review."
    )
    log.warning("[%s] %s", task_id, reason)
    return {"ok": False, "reason": reason, "retained_ratio": ratio}
