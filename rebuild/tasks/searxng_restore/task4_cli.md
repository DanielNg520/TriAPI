Produce a Search/Replace block (OLD/NEW fenced code blocks) for `src/semai/adapters/cli.py`. Reply with only the two blocks, no prose.

OLD:
```python
from semai.workers.terminal import TerminalWorker
```

NEW:
```python
from semai.workers.terminal import TerminalWorker
from semai.workers.web_search import WebSearchWorker
```

Also produce a second Search/Replace pair for the same file:

OLD:
```python
    registry.register("ghostwriter", GhostwriterWorker(settings))
    return registry
```

NEW:
```python
    registry.register("ghostwriter", GhostwriterWorker(settings))
    registry.register("web_search", WebSearchWorker(settings))
    return registry
```
