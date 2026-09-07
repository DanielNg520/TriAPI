Thread an optional `settings` parameter through this file, mirroring the same pattern already applied to `semai/security/path_guard.py`'s `_allowed_roots`/`_is_allowed_path` (same function bodies, same fallback rule: when `settings` is None or `settings.ghostwriter_dir` is None, behavior is byte-for-byte identical to today). Do not touch any other file.

1. `_allowed_roots(settings: "Settings | None" = None) -> list[Path]`: same change as path_guard.py — third root becomes `settings.ghostwriter_dir` when `settings is not None and settings.ghostwriter_dir is not None`, else the current env-var line unchanged.
2. `_is_allowed_path(path: Path, extra_allowed_dirs: list[Path] | None = None, settings: "Settings | None" = None) -> bool`: add `settings` as a new parameter after `extra_allowed_dirs`, pass it to `_allowed_roots(settings)`.
3. `make_ingest_worker(settings: "Settings | None" = None) -> Worker`: accept `settings`, and the inner `worker(intent, extra_allowed_dirs=None)` closure must pass it through to both `_is_allowed_path(file_path, extra_allowed_dirs, settings)` and `_allowed_roots(settings)` (used when building the `allowed_str` error message).
4. Add `from typing import TYPE_CHECKING` and a `if TYPE_CHECKING: from semai.config.schema import Settings` guarded import at the top, same pattern as path_guard.py.

Reply with the complete corrected file content only, in a single fenced code block.

```python
"""This worker implements on-request file reading via the ingest_document intent.
It supersedes ohmyllama/capabilities/ingestion.py for such reads."""
import os
from pathlib import Path

from semai.core.intents import IngestDocument, Intent
from semai.core.registry import Worker
from semai.core.results import Result


def _allowed_roots() -> list[Path]:
    """Return the canonical roots this worker may read from."""
    return [
        Path("~/Downloads").expanduser().resolve(),
        Path("~/Documents").expanduser().resolve(),
        Path(os.environ.get("OMLL_GHOSTWRITER_DIR", "~/ghostwriter"))
        .expanduser()
        .resolve(),
    ]


def _is_allowed_path(path: Path, extra_allowed_dirs: list[Path] | None = None) -> bool:
    """Check whether the path is inside one of the allowed roots."""
    roots = _allowed_roots()
    if extra_allowed_dirs:
        roots += extra_allowed_dirs
    for root in roots:
        try:
            if path.is_relative_to(root):
                return True
        except AttributeError:
            # Python <3.9 doesn't have Path.is_relative_to
            if str(path).startswith(str(root)):
                return True
    return False


def make_ingest_worker() -> Worker:
    """
    Return a worker that extracts text from a document.
    The worker expects an IngestDocument intent with a path attribute.
    It enforces strict access to only three allowed directories.
    """

    def worker(intent: Intent, extra_allowed_dirs: list[Path] | None = None) -> Result:
        if not isinstance(intent, IngestDocument):
            return Result(ok=False, message="Expected IngestDocument intent")

        # Resolve the supplied path
        try:
            file_path = Path(intent.path).expanduser().resolve()
        except Exception as e:
            return Result(ok=False, message=f"Error resolving path: {e}")

        # Security check
        if not _is_allowed_path(file_path, extra_allowed_dirs):
            allowed_str = ", ".join(str(r) for r in _allowed_roots())
            return Result(
                ok=False,
                message=(
                    "Security Error: Access to "
                    f"{file_path} is forbidden. Only the following roots are allowed: "
                    f"{allowed_str}"
                ),
            )

        # If markitdown is available, use it
        try:
            from markitdown import MarkItDown

            parser = MarkItDown()
            parsed = parser.convert(str(file_path))
            return Result(ok=True, message=parsed.text_content)
        except ImportError:
            pass
        except Exception as e:
            return Result(ok=False, message=f"MarkItDown error: {e}")

        # Fallback for plain text or markdown files
        ext = file_path.suffix.lower()
        if ext in (".txt", ".md"):
            try:
                content = file_path.read_text(encoding="utf-8")
                return Result(ok=True, message=content)
            except Exception as e:
                return Result(ok=False, message=f"Error reading file: {e}")

        # Unsupported file type
        return Result(
            ok=False,
            message=f"Unsupported file type '{ext}'. "
            "Only .txt and .md files are supported without markitdown.",
        )

    return worker
```
