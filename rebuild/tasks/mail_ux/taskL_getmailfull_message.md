File: `/home/dyne/Documents/Coding/SemAI/src/semai/workers/mail.py`

Current `GetMailFullWorker`:

```python
class GetMailFullWorker:
    """Fetches the full Gmail message payload for a single message."""

    def __call__(self, intent) -> Result:
        token = gmail_access_token()
        url = (
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/"
            f"{intent.msg_id}?format=full"
        )
        headers = {"Authorization": f"Bearer {token}"}
        try:
            resp = httpx.get(url, headers=headers, timeout=10.0)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            message = "Full Gmail message payload fetched successfully."
            return Result(ok=True, message=message, data=data)
        except Exception as exc:
            return Result(ok=False, message=str(exc))
```

Problem: `Result.message` is a hardcoded confirmation string, not the actual email content. Whatever
calls this worker and shows `result.message` to a human (e.g. a chat bot) currently shows that
useless string instead of the email.

This same file's `mail_watcher.py` module (different file, `src/semai/workers/mail_watcher.py`) has
static helpers for pulling readable fields out of a Gmail message dict of this same shape, already
proven correct and directly importable/reusable:

```python
    @staticmethod
    def _extract_sender(message: dict) -> str:
        headers = {
            header.get("name", "").lower(): header.get("value", "")
            for header in message.get("payload", {}).get("headers", [])
        }
        _, sender = parseaddr(headers.get("from", ""))
        return sender.lower()

    @staticmethod
    def _extract_subject(message: dict) -> str:
        headers = {
            header.get("name", "").lower(): header.get("value", "")
            for header in message.get("payload", {}).get("headers", [])
        }
        return headers.get("subject", "(no subject)")
```

A `format=full` Gmail message response also has a top-level `"snippet"` field (a short plain-text
preview Gmail itself generates), same as a `format=metadata` response does.

Task: change `GetMailFullWorker.__call__` so `Result.message` is human-readable -- built from the
subject, sender, and snippet of the fetched message, not a static confirmation string. Reuse
`MailWatcher`'s static helpers above (importable via `from semai.workers.mail_watcher import
MailWatcher`) rather than re-deriving header-parsing logic. Keep `data=data` in the returned
`Result` as-is (the raw payload is still useful to keep around). Keep the `except Exception` error
path unchanged.

Reply with ONLY the corrected `GetMailFullWorker` class (plus the one new import line, if you add
one), as python code block(s), no other text.
