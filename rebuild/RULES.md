Hard rules for every DeepSeek/agy call in this pipeline. Prepended automatically — do not repeat in per-task prompts.

- One function/section/task per call. Nothing outside the stated scope.
- Match the given function signature exactly.
- No unrequested extras: no retries, fallbacks, logging, CLI wrappers, comments explaining obvious code.
- Never bypass a spend cap or verification step.
- No hardcoded config (provider, model, price, path) — read from the given config file.
- Reply with only what was asked — code block or file content, no prose before/after — unless the task explicitly asks for prose.
- Never ask for a "full corrected function/file" from an excerpt. Two incidents (P3B-04, peak-guard task 2) show DeepSeek fabricates the unseen parts instead of reproducing them. If the reply must contain the whole function, the prompt must already contain the whole function verbatim — edit-in-place, don't reconstruct from a fragment.
- Before dispatching a task that edits a file another task already touched this session, re-read that file's current on-disk content first. A stale excerpt silently regressed a same-session fix once (SemAI: e512904 fixed, 57e2e8b's stale-excerpt dispatch deleted it, 66fb60e re-fixed it).
- The prompt describes required signature/behavior/scope only — never a finished implementation for you to copy, whether as a literal code block OR as step-by-step prose that dictates exact variable names, control flow, string literals, and call order (line-by-line pseudocode is still the answer, just spelled out in English). If a prompt reads like an implementation transcribed into sentences, that's a dispatch error, not a shortcut to take — leave the actual code decisions to the reply.
