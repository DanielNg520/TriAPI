Current first paragraph of `_SYSTEM_PROMPT` in `src/semai/agent.py`:

```python
    "You have tools that read the user's own systems. Use them when the answer "
    "depends on the user's actual data; answer directly when it does not.\n\n"
```

Bug: this tells the model tools exist ONLY to read the user's own local data, and to answer directly (never use a tool) for anything else. In practice one tool (`research`) reaches outside the user's systems — live web search. The model follows this instruction literally and refuses web-search requests, saying it's "outside the scope of the tools I have."

Task: rewrite ONLY this paragraph (keep it two lines joined the same way, same string-literal style with trailing `\n\n` on the second line) so it: (a) distinguishes tools that read the user's own local systems from tools that reach outside them (e.g. live web search for current events, prices, or facts outside the user's data or your own knowledge), and (b) instructs the model to use whichever tool the question actually needs rather than guessing or refusing.

Reply with exactly one fenced python block containing only the two replacement string-literal lines (same format as the original: two adjacent string literals that Python will concatenate, ending in `\n\n`).
