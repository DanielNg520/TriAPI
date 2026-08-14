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

Every tier's write of an *existing* file must go through check_write()
before landing on disk. A brand-new file has nothing to lose and always
passes -- this only guards edits.
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


def _nonblank_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def check_write(task_id: str, target_path: Path, new_content: str) -> dict:
    """Returns {"ok": True} to allow the write. Returns {"ok": False, "reason":
    ...} to refuse it -- the caller must NOT write new_content to target_path
    in that case; the original stays untouched. The refused content is saved
    to logs/rejected_writes/<task_id>.txt so a human can still see what the
    model proposed."""
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
