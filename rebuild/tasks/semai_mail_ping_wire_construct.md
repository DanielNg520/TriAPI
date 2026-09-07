Two call sites in the SemAI codebase must agree on one data contract: a JSON object with keys
`msg_id` (str), `sender` (str), `subject` (str), `snippet` (str), carried as the string
`"mail_ping:" + json.dumps({...})`.

Site A — `src/semai/adapters/daemon.py`, inside `AsyncDaemon._process()`'s mail-watcher branch. It
currently receives this JSON-prefixed string from `self._mail_watcher.poll()`, must validate it's
well-formed and extract `msg_id`/`sender` for logging/title purposes only, then forward the *entire
original string unchanged* as the `message` argument to `deliver()` (so the JSON stays intact for
the next site to parse) — it must NOT reconstruct or reformat the payload.

Site B — `src/semai/adapters/telegram.py`, inside `TelegramAdapter._send()`. It receives that same
string as its `text` argument, must parse the JSON, and build a human-readable message plus a 5-button
inline keyboard from it (keyboard already fully specified, keyed off `msg_id`).

Task: write ONLY the skeleton (function signature unchanged, docstring/comments marking each step,
NO real logic in the body — use `...` placeholders) for the two changed pieces, so the exact shape of
the JSON-handling contract is locked in before either piece is filled in. Do not write the try/except
error-handling logic, do not write the f-string content, do not write the keyboard list — just the
control-flow shape (if/try scaffolding) with a comment at each `...` saying what goes there.

Reply with exactly two fenced python blocks, no other text:
1. Skeleton for Site A: the `async for payload in self._mail_watcher.poll():` loop body only (not the
   whole method) — same variable name `payload`, same call to `deliver(self.settings, store, "mail", ...)`.
2. Skeleton for Site B: the `if text.startswith("mail_ping:"):` block only (not the whole `_send` method).
