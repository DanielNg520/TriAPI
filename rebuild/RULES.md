Hard rules for every DeepSeek/agy call in this pipeline. Prepended automatically — do not repeat in per-task prompts.

- One function/section/task per call. Nothing outside the stated scope.
- Match the given function signature exactly.
- No unrequested extras: no retries, fallbacks, logging, CLI wrappers, comments explaining obvious code.
- Never bypass a spend cap or verification step.
- No hardcoded config (provider, model, price, path) — read from the given config file.
- Reply with only what was asked — code block or file content, no prose before/after — unless the task explicitly asks for prose.
- Never ask for a "full corrected function/file" from an excerpt. Two incidents (P3B-04, peak-guard task 2) show DeepSeek fabricates the unseen parts instead of reproducing them. If the reply must contain the whole function, the prompt must already contain the whole function verbatim — edit-in-place, don't reconstruct from a fragment.
