This test monkeypatches `ingester._allowed_roots` with a zero-argument lambda. `_allowed_roots` was just changed to accept an optional `settings` parameter (`_allowed_roots(settings=None)`), and it's now called internally as `_allowed_roots(settings)`, so the zero-arg lambda now raises `TypeError: takes 0 positional arguments but 1 was given`.

Fix: change exactly this one line —

```python
        ingester._allowed_roots = lambda: [allow_dir]
```

to accept an optional positional argument it ignores:

```python
        ingester._allowed_roots = lambda settings=None: [allow_dir]
```

Nothing else in the file changes. Reply with only that one corrected line, in a single fenced code block.
