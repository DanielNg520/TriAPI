Add one new method to `TelegramAdapter` in `/home/dyne/Documents/Coding/SemAI/src/semai/adapters/telegram.py`.

For context, here are the existing methods it must be consistent with (verbatim, do not change these):

```python
    async def _call(self, method: str, **params):
        """One Bot API call. Raises TelegramError (already redacted, and marked
        permanent/transient) instead of leaking httpx's URL-bearing errors."""
        try:
            r = await self._client.post(f"{self._api}/{method}", json=params)
        except httpx.HTTPError as e:
            raise TelegramError(
                f"{method}: {self._redact(str(e))}"
            ) from None
        if r.status_code >= 400:
            try:
                desc = str(r.json().get("description", ""))
            except ValueError:
                desc = r.text[:200]
            raise TelegramError(
                f"{method}: HTTP {r.status_code} {self._redact(desc)}",
                permanent=r.status_code in (400, 403) and bool(_PERMANENT.search(desc)),
            ) from None
        try:
            return r.json()
        except ValueError as e:
            raise TelegramError(f"{method}: bad JSON ({e})") from None

    async def _edit(self, chat_id: int | str, message_id: int, text: str,
                   keyboard: list | None = None) -> None:
        """Rewrite a message asynchronously."""
        try:
            params: dict[str, Any] = {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text[:4000],
            }
            if keyboard is not None:
                params["reply_markup"] = {"inline_keyboard": keyboard}
            await self._call("editMessageText", **params)
        except TelegramError as e:
            log.debug("editMessageText failed for %s/%s: %s", chat_id, message_id, e)
```

Task: write a new method `_delete_message`, to be inserted immediately after `_edit` (same class, same indentation level as `_call`/`_edit`):

```python
    async def _delete_message(self, chat_id: int | str, message_id: int) -> bool:
        """Delete a message. Returns True on success, False on any failure (never raises)."""
        try:
            await self._call("deleteMessage", chat_id=chat_id, message_id=message_id)
            return True
        except TelegramError as e:
            log.debug("deleteMessage failed for %s/%s: %s", chat_id, message_id, e)
            return False
```

Reply with ONLY that `_delete_message` method as a single python code block, no other text.
