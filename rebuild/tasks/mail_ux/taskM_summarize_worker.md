File: `/home/dyne/Documents/Coding/SemAI/src/semai/workers/mail.py`

Add a new worker class, `SummarizeMailWorker`, for the `summarize_mail` intent
(`src/semai/core/intents.py`'s `SummarizeMail(BaseIntent)`, field `msg_id: str`).

Reference: the existing `GetMailFullWorker` in this same file shows the established pattern for
fetching a Gmail message by id via `gmail_access_token()` (already imported in this file) and
`httpx`:

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
            ...
        except Exception as exc:
            return Result(ok=False, message=str(exc))
```

For fetching just the metadata needed here (subject/sender/snippet, not the full body), use
`?format=metadata&metadataHeaders=Subject&metadataHeaders=From` instead of `format=full` -- lighter
weight, matches the pattern already used in `src/semai/workers/mail_watcher.py`'s `MailWatcher.poll()`.
That module also has these reusable static helpers for pulling subject/sender out of the response
(importable via `from semai.workers.mail_watcher import MailWatcher`):

```python
    @staticmethod
    def _extract_sender(message: dict) -> str: ...  # returns lowercased email address

    @staticmethod
    def _extract_subject(message: dict) -> str: ...  # returns the Subject header or "(no subject)"
```

A `format=metadata` response also has a top-level `"snippet"` field (Gmail's own short plain-text
preview).

For the actual summarization, this class needs an `OllamaProvider` (`semai.providers.ollama`):

```python
class OllamaProvider:
    def __init__(self, base_url: str, timeout_s: float = 60.0) -> None: ...
    def chat(
        self, model: str, prompt: str,
        *, system: str | None = None,
        num_predict: int | None = None,
        num_ctx: int | None = None,
    ) -> str: ...  # raises ProviderError on failure
```

And `Settings` (`semai.config.schema`) has `ollama_base_url: str` and `ollama_model: str` fields
already used elsewhere in this codebase for exactly this purpose.

Task: write `SummarizeMailWorker.__init__(self, settings)` (stores `settings`) and
`__call__(self, intent) -> Result`. It should: fetch the message's subject/sender/snippet by
`intent.msg_id` (metadata fetch, as described above); build a prompt asking for a short (2-3
sentence) summary of the email given that subject/sender/snippet; call `OllamaProvider(...).chat(...)`
using `settings.ollama_base_url` and `settings.ollama_model`; return `Result(ok=True, message=<the
summary text>)` on success. On any exception (network, Gmail API, or `ProviderError` from Ollama),
return `Result(ok=False, message=str(exc))` -- same error-handling shape as `GetMailFullWorker`.

Reply with ONLY the new `SummarizeMailWorker` class plus any new import lines it needs at the top of
this file, as python code block(s), no other text.
