Produce a Search/Replace block (OLD/NEW fenced code blocks) for `pyproject.toml`. Reply with only the two blocks, no prose.

OLD:
```
    "textual>=0.85.2",
    "litellm[proxy]>=1.95.0",
    # litellm 1.95 imports `get_flat_dependant` from fastapi.dependencies.utils,
    # which fastapi removed in 0.140. Unpinned, uv resolves 0.141 and the proxy
    # dies on import — every cloud-routed role then falls through to Ollama,
    # which 404s a provider-prefixed tag. Nothing in the tree catches this
    # because the proxy is supervised in a background thread.
    "fastapi<0.140",
]
```

NEW:
```
    "textual>=0.85.2",
]
```
