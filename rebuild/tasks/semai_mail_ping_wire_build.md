Fill in the two skeletons below with real logic. `json` is already imported in both files (module-level).

Site A — `src/semai/adapters/daemon.py`. This replaces the current loop body:

```python
                            async for payload in self._mail_watcher.poll():
                                # Validate that payload is a well-formed "mail_ping:" JSON string.
                                try:
                                    # Parse the JSON after the "mail_ping:" prefix.
                                    ...
                                    # Extract msg_id and sender for logging/title purposes only.
                                    ...
                                except Exception:
                                    # Handle malformed payload without forwarding it.
                                    ...
                                else:
                                    # Forward the entire original payload string unchanged.
                                    deliver(self.settings, store, "mail", "unmatched email", payload)
```

Rules for filling it in:
- `payload` always starts with the literal prefix `"mail_ping:"` (this is guaranteed by the caller — still
  guard with `payload.startswith("mail_ping:")` and skip via `continue` if not, logging
  `log.warning("unexpected mail_ping payload shape: %s", payload)`).
- Parse everything after that prefix with `json.loads(...)`.
- Extract `msg_id = info["msg_id"]` and `sender = info["sender"]` (KeyError should be caught by the same
  `except Exception:`).
- On any exception (JSON parse failure or missing keys): log
  `log.warning("unexpected mail_ping payload shape: %s", payload)` and `continue` — do NOT call `deliver()`.
- On success: call `deliver(self.settings, store, "mail", "unmatched email", payload)` exactly as shown
  (the raw original `payload` string, unchanged) — `msg_id`/`sender` are not used in that call, they exist
  only so a future caller could log them; you may add one `log.debug` line using them if you want, optional.
- `deliver` is a plain synchronous function — do not `await` it.

Site B — `src/semai/adapters/telegram.py`. This replaces the current `if text.startswith("mail_ping:"):`
block inside `_send()`:

```python
        if text.startswith("mail_ping:"):
            # Parse the JSON object with keys msg_id, sender, subject, snippet.
            try:
                ...
            except Exception:
                # Malformed JSON: leave text/keyboard completely unchanged, fall through.
                pass
            else:
                # Build human-readable message from parsed fields.
                ...
                # Build 5-button inline keyboard keyed off msg_id.
                ...
```

Rules for filling it in:
- Parse `json.loads(text[len("mail_ping:"):])` into `info`.
- `msg_id = info["msg_id"]`, `sender = info["sender"]`, `subject = info.get("subject", "(no subject)")`,
  `snippet = info.get("snippet", "")`.
- Build the new `text` (reassign the outer `text` variable): if `snippet` is non-empty,
  `text = f"📧 **{subject}**\nFrom: {sender}\n\n{snippet}"`; if empty, `text = f"📧 **{subject}**\nFrom: {sender}"`.
  (Markdown `**`, not raw HTML — this codebase's `_format_for_telegram`, called later on `text`, unchanged,
  not shown here, converts `**bold**` to `<b>` and would double-escape literal `<b>` tags.)
- Build `keyboard` (reassign the outer `keyboard` variable) with exactly these 5 buttons in one row, same
  as before:
  `{"text": "[ Full ]", "callback_data": f"mail_action:full:{msg_id}"}`,
  `{"text": "[ Summary ]", "callback_data": f"mail_action:summary:{msg_id}"}`,
  `{"text": "[ Remind me ]", "callback_data": f"mail_action:remind:{msg_id}"}`,
  `{"text": "[ Add task ]", "callback_data": f"mail_action:task:{msg_id}"}`,
  `{"text": "[ Mute ]", "callback_data": f"mail_action:mute:{msg_id}"}`.
- On any exception: leave `text` and `keyboard` exactly as they were passed into `_send()` — `pass`, no
  logging needed (this mirrors the method's existing fail-soft style).

Reply with exactly two fenced python blocks, no other text:
1. Complete filled-in Site A loop body (same indentation level as shown above).
2. Complete filled-in Site B `if` block (same indentation level as shown above).
