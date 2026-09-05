Current code in `src/semai/agent.py`, inside `Agent.tools()`:

```python
            base_tool = {
                "type": "function",
                "function": {
                    "name": None,
                    "description": f"Work with the user's {kind.replace('_', ' ')}.",
                    "parameters": {"type": "object", "properties": properties, "required": list(required)},
                },
            }
```

Bug: this generic description makes a small LLM think every tool (including "research") only reads the user's own local data. In practice `research` performs a live internet web search — the model needs to know that or it refuses web-search requests, believing it has no such capability.

Task: replace the description line with a per-kind lookup so `research` gets an accurate description while every other kind keeps its current generic phrasing. Write:

1. A module-level dict `_TOOL_DESCRIPTIONS: dict[str, str] = {"research": "<a clear one-sentence description saying this performs a live internet web search for current events, prices, facts, or anything outside the user's local data or your own knowledge>"}`
2. A one-line replacement for the `"description": f"Work with the user's {kind.replace('_', ' ')}.",` line: `"description": _TOOL_DESCRIPTIONS.get(kind, f"Work with the user's {kind.replace('_', ' ')}."),`

Reply with exactly two fenced python blocks in this order: first the `_TOOL_DESCRIPTIONS` dict definition, second the single replacement line for the `"description"` key. Nothing else.
