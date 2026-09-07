Write a new Python file, full content only, no prose before/after, no markdown fence unless it wraps the whole file.

Target file: `src/semai/workers/web_search.py` in the `semai` package.

Requirements:

1. Module docstring, one short paragraph: this is a minimal SearXNG-only web search worker, general-purpose (not tied to any specific intent domain), restored from the deleted `workers/research.py` (that file had a multi-provider waterfall — Tavily/Brave/SearXNG/DuckDuckGo; this replacement is SearXNG-only, no other providers, no quota tracking).

2. Imports: `from __future__ import annotations`, `httpx`, `from semai.core.results import Result`, `from semai.config.schema import Settings`.

3. Include this EXACT function verbatim, character for character, do not modify its body at all (only reindent/reformat if needed to fit module style, logic must be byte-identical):

```python
def _search_searxng(query: str, url: str) -> list[dict[str, str]]:
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(url.rstrip("/") + "/search" if "/search" not in url else url, params={"q": query, "format": "json"})
        resp.raise_for_status()
        data = resp.json()
        results = []
        items = data.get("results") or data.get("hits") or []
        for r in items:
            snippet = r.get("content") or r.get("snippet") or ""
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": snippet.strip()
            })
        return results
```

4. A class `WebSearchWorker`:
   - `__init__(self, settings: Settings, client: object | None = None)`: store `self.settings = settings`, `self.client = client or httpx`. (The `client` param exists for test injection, matching the style of `ListMailWorker` in `src/semai/workers/mail.py`, but `_search_searxng` above always builds its own `httpx.Client` internally — do not change `_search_searxng`'s signature or internals to use `self.client`; leave the injected client field unused by `_search_searxng`, only reserved for test-seam consistency with other workers in this file if a future test needs it. Do not add any code that pretends to use it.)
   - `available(self) -> bool`: return `bool(getattr(self.settings, "searxng_url", None))`.
   - `__call__(self, intent) -> Result`: read `query = getattr(intent, "query", "") or ""`. If not `self.available()`, return `Result(ok=False, message="SearXNG is not configured (searxng_url unset)")`. Otherwise call `_search_searxng(query, self.settings.searxng_url)` inside a `try/except Exception as e`, catching any request/parsing failure and returning `Result(ok=False, message=f"web search failed: {e}")` on error. On success with zero results, return `Result(ok=True, message="No results found.", data={"results": []})`. On success with results, build a `message` string of up to 5 results formatted as `"{i}. {title}\n   {url}\n   {snippet}"` joined by blank lines, and return `Result(ok=True, message=message, data={"results": results})` (the full `results` list goes in `data`, not just the top 5 — only the rendered `message` text is capped to 5).

Do not add logging, retries, caching, or a CLI wrapper. Do not touch any other file. Reply with only the file content.
