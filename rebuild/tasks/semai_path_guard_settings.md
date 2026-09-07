Add an optional `settings` parameter to both functions in this file. Existing callers that pass no `settings` must behave byte-for-byte identically to today (this is a security allow-list; do not change default behavior). Do not touch any other file or add any new import beyond what's listed.

1. `_allowed_roots(settings: "Settings | None" = None) -> list[Path]`: when `settings is not None and settings.ghostwriter_dir is not None`, use `settings.ghostwriter_dir` (already an expanded `Path`, do not re-expand) as the third root instead of the current `os.environ.get("OMLL_GHOSTWRITER_DIR", "~/ghostwriter")` line. Otherwise (settings is None, or settings.ghostwriter_dir is None) keep the exact current env-var-based line unchanged.
2. `_is_allowed_path(path: Path, settings: "Settings | None" = None) -> bool`: add the same optional `settings` parameter and pass it through to its call to `_allowed_roots(settings)`.
3. Add `from typing import TYPE_CHECKING` and a `if TYPE_CHECKING: from semai.config.schema import Settings` guarded import at the top (avoids a real circular import at runtime; the annotation above is a string so this is enough), instead of a normal top-level import.

Reply with the complete corrected file content only, in a single fenced code block.

```python
from pathlib import Path
import os


def _allowed_roots() -> list[Path]:
    """Return the canonical roots this worker may write to."""
    return [
        Path("~/Downloads").expanduser().resolve(),
        Path("~/Documents").expanduser().resolve(),
        Path(os.environ.get("OMLL_GHOSTWRITER_DIR", "~/ghostwriter"))
        .expanduser()
        .resolve(),
    ]


def _is_allowed_path(path: Path) -> bool:
    """Check whether the path is inside one of the allowed roots."""
    for root in _allowed_roots():
        try:
            if path.is_relative_to(root):
                return True
        except AttributeError:  # Python <3.9 doesn't have is_relative_to
            try:
                path.relative_to(root)
                return True
            except ValueError:
                pass
    return False
```
