Produce a Search/Replace block (OLD/NEW fenced code blocks) for `src/semai/config/schema.py`. Reply with only the two blocks, no prose.

OLD:
```python
    n8n_webhook_url: str | None = None
```

NEW:
```python
    n8n_webhook_url: str | None = None
    searxng_url: str | None = None
```

Also produce a second Search/Replace pair for the same file, adding the matching env-resolution line in `Settings.load()`:

OLD:
```python
                n8n_webhook_url=e.get("N8N_WEBHOOK_URL") or None,
```

NEW:
```python
                n8n_webhook_url=e.get("N8N_WEBHOOK_URL") or None,
                searxng_url=e.get("SEARXNG_URL") or None,
```
