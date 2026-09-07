Produce a Search/Replace block (OLD/NEW fenced code blocks) for `src/semai/tooling/dep_triage.py`. Reply with only the two blocks, no prose.

OLD:
```python
def _iter_source_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for sub in ("ohmyllama", "tests", "scripts"):
        d = root / sub
        if d.exists():
            files.extend(d.rglob("*.py"))
    return files
```

NEW:
```python
def _iter_source_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for sub in ("src/semai", "tests", "scripts"):
        d = root / sub
        if d.exists():
            files.extend(d.rglob("*.py"))
    return files
```
