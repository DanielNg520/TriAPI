This function already receives `settings: Settings` but doesn't pass it to `make_ingest_worker()`, so the ingest worker always falls back to its default allow-list instead of respecting `settings.ghostwriter_dir`. `make_ingest_worker` was changed to accept an optional `settings` parameter.

Fix: change `ingest_worker = make_ingest_worker()` to `ingest_worker = make_ingest_worker(settings)`. Nothing else changes.

Reply with only the corrected function in a single fenced code block.

```python
def _ingest(settings: Settings, path: Path, *, extra_allowed_dirs: list[Path] | None = None) -> str:
    ingest_worker = make_ingest_worker()
    intent = IngestDocument(confidence=1.0, raw_utterance="", kind="ingest_document", path=str(path))
    result = ingest_worker(intent, extra_allowed_dirs=extra_allowed_dirs)
    if not result.ok:
        raise GhostwriterError(result.message)
    return result.message
```
