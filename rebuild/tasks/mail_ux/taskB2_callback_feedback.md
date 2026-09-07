Edit one function, `TelegramAdapter._handle_callback`, in `/home/dyne/Documents/Coding/SemAI/src/semai/adapters/telegram.py`.

Current full function (edit in place, do not reconstruct from memory):

```python
    async def _handle_callback(self, data: str, callback_query: dict) -> None:
        """Handle a callback query from Telegram.

        The method is intentionally minimal; subclasses or callers can extend it.
        It parses the callback data, acknowledges the query to clear the spinner,
        and delegates to `_decide_cb` when appropriate.
        """
        mail_match = re.match(r'^mail_action:(.+):(.+)$', data)
        if mail_match:
            action, msg_id = mail_match.groups()
            try:
                from semai.core.intents import MarkMailRead
                from semai.workers.mail import MarkMailReadWorker
                worker = MarkMailReadWorker()
                intent = MarkMailRead(
                    kind="mark_mail_read",
                    msg_id=msg_id,
                    confidence=1.0,
                    raw_utterance=f"mail_action:{action}:{msg_id}",
                )
                await asyncio.to_thread(worker, intent)
            except Exception as e:
                log.error("Failed to invoke MarkMailReadWorker: %s", e)
            
            if hasattr(self, "_dispatcher") and self._dispatcher is not None:
                utterance_by_action = {
                    "full": f"show full email {msg_id}",
                    "summary": f"summarize email {msg_id}",
                    "remind": f"remind me about email {msg_id}",
                    "task": f"add task from email {msg_id}",
                    "mute": f"mute email {msg_id}",
                }
                utterance = utterance_by_action.get(
                    action, f"Handle email {msg_id} action {action}"
                )
                chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
                result = await asyncio.to_thread(self._dispatcher.dispatch, utterance)
                if chat_id and result and hasattr(result, "message"):
                    await self._send(chat_id, result.message)
            
            await self._answer_cb(callback_query.get("id", ""), "Action processed")
            return

        parsed = self._parse_cb(data)
        if not parsed:
            await self._answer_cb(callback_query.get("id", ""), "Invalid action")
            return
        kind, approval_id = parsed
        # Currently only approve/reject are supported. The decision logic
        # should be implemented in `_decide_cb`; here we just log.
        log.debug(
            "_handle_callback: kind=%s, approval_id=%s, query=%s",
            kind,
            approval_id,
            callback_query,
        )
        await self._answer_cb(callback_query.get("id", ""), "")
```

Task: modify ONLY the `if mail_match:` block (from `if mail_match:` through its `return`, i.e. everything up to but NOT including `parsed = self._parse_cb(data)`). Do not touch anything from `parsed = self._parse_cb(data)` onward.

Requirements for the new `if mail_match:` block:
1. Keep the existing `MarkMailReadWorker` call exactly as-is, but track success: set a local `worker_failed = True` in its `except Exception as e:` branch (keep the existing `log.error(...)` call too), else `worker_failed = False`.
2. Keep the existing dispatcher-utterance dispatch block, but track failure too: a `dispatch_failed` flag. Treat it as failed if `result` is falsy, or `result` has no `message` attribute, or `result` has an `ok` attribute that is falsy (use `getattr(result, "ok", True)` so results without an `ok` attribute are treated as success). If `hasattr(self, "_dispatcher")` is False or `self._dispatcher` is None, treat `dispatch_failed` as False (nothing to dispatch is not a failure).
3. After both steps, if `worker_failed` or `dispatch_failed`: call `await self._answer_cb(callback_query.get("id", ""), "Failed to process email action")` and `return` (do NOT attempt delete/edit in this case).
4. Otherwise (success): get `chat_id = callback_query.get("message", {}).get("chat", {}).get("id")` and `message_id = callback_query.get("message", {}).get("message_id")`. If both are truthy, call `deleted = await self._delete_message(chat_id, message_id)` (this method already exists on the class). If `deleted` is falsy, fall back by calling:
   ```python
   try:
       await self._call(
           "editMessageReplyMarkup",
           chat_id=chat_id,
           message_id=message_id,
           reply_markup={"inline_keyboard": [[{"text": "✅ Done", "callback_data": "noop"}]]},
       )
   except TelegramError as e:
       log.debug("editMessageReplyMarkup failed for %s/%s: %s", chat_id, message_id, e)
   ```
   If `chat_id` or `message_id` is falsy, skip both the delete and the fallback edit entirely.
5. Finally call `await self._answer_cb(callback_query.get("id", ""), "Done")` and `return`.

Do not change the `MarkMailReadWorker`/dispatcher logic's actual behavior beyond adding the flags described — same imports, same utterance_by_action dict, same asyncio.to_thread calls.

Reply with ONLY the full corrected `_handle_callback` function (the entire function, unchanged tail included), as a single python code block, no other text.
