Edit one block in `/home/dyne/Documents/Coding/SemAI/src/semai/adapters/telegram.py`, inside `TelegramAdapter._send`.

Current exact block (inside the `else:` branch that runs when `mail_ping:` payload decodes successfully):

```python
                keyboard = [[
                    {"text": "[ Full ]", "callback_data": f"mail_action:full:{msg_id}"},
                    {"text": "[ Summary ]", "callback_data": f"mail_action:summary:{msg_id}"},
                    {"text": "[ Remind me ]", "callback_data": f"mail_action:remind:{msg_id}"},
                    {"text": "[ Add task ]", "callback_data": f"mail_action:task:{msg_id}"},
                    {"text": "[ Mute ]", "callback_data": f"mail_action:mute:{msg_id}"},
                ]]
```

Task: replace it with exactly this (2 rows instead of 1, emoji labels instead of bracket text, same indentation — 16 spaces before `keyboard =`):

```python
                keyboard = [
                    [
                        {"text": "📄 Full", "callback_data": f"mail_action:full:{msg_id}"},
                        {"text": "📝 Summary", "callback_data": f"mail_action:summary:{msg_id}"},
                        {"text": "⏰ Remind", "callback_data": f"mail_action:remind:{msg_id}"},
                    ],
                    [
                        {"text": "✅ Task", "callback_data": f"mail_action:task:{msg_id}"},
                        {"text": "🔇 Mute", "callback_data": f"mail_action:mute:{msg_id}"},
                    ],
                ]
```

Reply with ONLY that replacement block (the `keyboard = [...]` assignment, nothing else) as a single python code block, no other text.
