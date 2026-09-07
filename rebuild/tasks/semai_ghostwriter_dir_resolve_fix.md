Bug: `settings.ghostwriter_dir` is only `.expanduser()`'d in `Settings.load()`, never `.resolve()`'d, while `_allowed_roots()` in `path_guard.py` uses it raw as one of the returned roots — every other root in that same list, and the env-var fallback branch, call `.expanduser().resolve()`. `_is_allowed_path` does a purely lexical `Path.is_relative_to()` check against an always-`.resolve()`d candidate path, so a relative or symlinked `SEMAI_GHOSTWRITER_DIR`/`OMLL_GHOSTWRITER_DIR` value would silently fail to match even for a legitimate path, spuriously denying access.

Two separate one-line fixes, same root cause, in two different files:

**File 1 — `semai/config/schema.py`, the `ghostwriter_dir=` line inside `Settings.load()`'s `cls(...)` call.** Change:
```python
ghostwriter_dir=Path(e["SEMAI_GHOSTWRITER_DIR"]).expanduser() if e.get("SEMAI_GHOSTWRITER_DIR") else (Path(e["OMLL_GHOSTWRITER_DIR"]).expanduser() if e.get("OMLL_GHOSTWRITER_DIR") else None),
```
to (add `.resolve()` after each `.expanduser()`):
```python
ghostwriter_dir=Path(e["SEMAI_GHOSTWRITER_DIR"]).expanduser().resolve() if e.get("SEMAI_GHOSTWRITER_DIR") else (Path(e["OMLL_GHOSTWRITER_DIR"]).expanduser().resolve() if e.get("OMLL_GHOSTWRITER_DIR") else None),
```

**File 2 — `semai/security/path_guard.py`'s `_allowed_roots` function.** Change:
```python
def _allowed_roots(settings: "Settings | None" = None) -> list[Path]:
    """Return the canonical roots this worker may write to."""
    return [
        Path("~/Downloads").expanduser().resolve(),
        Path("~/Documents").expanduser().resolve(),
        settings.ghostwriter_dir
        if settings is not None and settings.ghostwriter_dir is not None
        else Path(os.environ.get("OMLL_GHOSTWRITER_DIR", "~/ghostwriter")).expanduser().resolve(),
    ]
```
to (resolve the settings-sourced value too, defense in depth even though it's already resolved at the source after the File 1 fix):
```python
def _allowed_roots(settings: "Settings | None" = None) -> list[Path]:
    """Return the canonical roots this worker may write to."""
    return [
        Path("~/Downloads").expanduser().resolve(),
        Path("~/Documents").expanduser().resolve(),
        settings.ghostwriter_dir.resolve()
        if settings is not None and settings.ghostwriter_dir is not None
        else Path(os.environ.get("OMLL_GHOSTWRITER_DIR", "~/ghostwriter")).expanduser().resolve(),
    ]
```

Reply with exactly two fenced code blocks, one per file in the order given above, each containing only that one corrected line/function. No other text.
