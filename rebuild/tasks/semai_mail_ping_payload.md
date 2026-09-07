In `src/semai/workers/mail_watcher.py`, `MailWatcher.poll()` only fetches the `From` header, so the
downstream Telegram alert has no email subject or preview text. Extend it to also fetch `Subject` and
include the Gmail API's `snippet` field (already present in the metadata-format response, top-level key
`"snippet"`, no extra API call needed), and change the yielded payload to a JSON-based format instead of
plain colon-joined fields (a subject line commonly contains colons, which would break simple splitting).

New payload format: `"mail_ping:" + json.dumps({"msg_id": msg_id, "sender": sender, "subject": subject, "snippet": snippet})`.
`subject` must default to `"(no subject)"` if the header is absent. `snippet` must default to `""` if absent.

Here is the current method, verbatim (only this method changes; `_extract_sender` stays exactly as-is
and is still used for the sender):

```python
    async def poll(self):
        """Yield mail_ping payloads for unread messages matching no rules."""
        rules_text = self._load_rules()
        token = await asyncio.to_thread(gmail_access_token)
        headers = {"Authorization": f"Bearer {token}"}
        base_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"

        params = {"q": "is:unread"}
        resp = await asyncio.to_thread(
            self.client.get, base_url, headers=headers, params=params, timeout=10.0
        )
        resp.raise_for_status()
        results = resp.json()
        messages = list(results.get("messages") or [])

        while results.get("nextPageToken"):
            params["pageToken"] = results["nextPageToken"]
            resp = await asyncio.to_thread(
                self.client.get, base_url, headers=headers, params=params, timeout=10.0
            )
            resp.raise_for_status()
            results = resp.json()
            messages.extend(results.get("messages") or [])

        for message in messages:
            msg_id = message["id"]
            if self._is_processed(msg_id):
                continue

            try:
                msg_resp = await asyncio.to_thread(
                    self.client.get,
                    f"{base_url}/{msg_id}",
                    headers=headers,
                    params={"format": "metadata", "metadataHeaders": "From"},
                    timeout=10.0,
                )
                msg_resp.raise_for_status()
                msg = msg_resp.json()
                sender = self._extract_sender(msg)
            except Exception:
                continue

            if rules_text and self._matches_rules(rules_text, sender):
                self._mark_processed(msg_id)
                continue

            if self._has_default(sender):
                self._mark_processed(msg_id)
                continue

            self._mark_processed(msg_id)
            yield f"mail_ping:{msg_id}:{sender}"
```

Required changes, nothing else:
1. In the `params` dict for the per-message `msg_resp` fetch, change `"metadataHeaders": "From"` to
   `"metadataHeaders": ["From", "Subject"]` (Gmail API accepts a list here for multiple headers).
2. Add a call to a new `self._extract_subject(msg)` staticmethod to get `subject`. Write this new method
   too, mirroring the existing `_extract_sender` staticmethod exactly in structure:

   ```python
    @staticmethod
    def _extract_sender(message: dict) -> str:
        headers = {
            header.get("name", "").lower(): header.get("value", "")
            for header in message.get("payload", {}).get("headers", [])
        }
        _, sender = parseaddr(headers.get("from", ""))
        return sender.lower()
   ```

   `_extract_subject(message: dict) -> str` should build the same `headers` dict, then return
   `headers.get("subject", "(no subject)")` (no `parseaddr`, no lowercasing — subjects are free text).
3. Get `snippet = msg.get("snippet", "")`.
4. Add `import json` at the top of the function's needs (module-level import, so just add `import json`
   as a new line among the file's existing top-of-file imports — mention this separately, do not put it
   inside the method).
5. Change the final `yield` line to:
   `yield "mail_ping:" + json.dumps({"msg_id": msg_id, "sender": sender, "subject": subject, "snippet": snippet})`

Reply with three things only, in this exact order, no other text:
1. A fenced python block with the single line `import json` (to be added to the file's existing import block).
2. A fenced python block with the complete corrected `poll()` method.
3. A fenced python block with the new `_extract_subject` staticmethod.
