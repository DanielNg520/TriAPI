File: `/home/dyne/Documents/Coding/SemAI/src/semai/adapters/telegram.py`, method `_handle_callback`.

Bug just reported live: pressing a mail-action button in a forum topic (e.g. the "mail" topic) sends
the dispatcher's reply to the chat's General topic instead of back into the same topic the button
was pressed in.

Relevant current code, inside the `if mail_match:` block:

```python
            dispatch_failed = False
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
                if not result or not hasattr(result, "message") or not getattr(result, "ok", True):
                    dispatch_failed = True
                if chat_id and result and hasattr(result, "message"):
                    await self._send(chat_id, result.message)
```

Root cause: `chat_id` here is a bare int (`callback_query["message"]["chat"]["id"]`), with no topic
information, so `_send()` posts to the chat's default/General topic. This same file already has the
mechanism for topic-aware sends elsewhere -- `build_route(chat_id: int, topic_id: int | None = None)
-> str` builds a route string like `"<chat_id>.t<topic_id>"`, and `_send()` already knows how to
parse a route string like that (via `parse_route`/`send_kwargs`) and add the right
`message_thread_id` to the Telegram API call.

A Telegram message posted inside a forum topic carries a `message_thread_id` field at the top level
of the message object -- so `callback_query["message"]["message_thread_id"]` (a sibling of `"chat"`
and `"message_id"` in that same dict) is present when the original mail-ping message was itself
inside a topic, and absent otherwise.

Task: fix the `chat_id`/`_send(...)` lines above (only this block, and only what's needed to route
the reply back into the same topic) so the reply lands in whatever topic the original message was
in, falling back to the bare chat (current behavior) when there's no topic. Use `build_route` for
this, consistent with how the rest of this file routes topic-aware sends.

Reply with ONLY the corrected lines from `chat_id = callback_query.get(...)` through
`await self._send(chat_id, result.message)`, as a single python code block, no other text.
