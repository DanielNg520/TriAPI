File: `/home/dyne/Documents/Coding/SemAI/src/semai/core/intents.py`

Two new intent kinds need adding to this file's schema: `summarize_mail` (fields: `msg_id: str`)
and `create_google_task` (fields: `msg_id: str`). Follow the exact same shape as the existing
`GetMailFull` intent, which is the closest precedent (same single `msg_id: str` field, same
mail-related purpose):

```python
class GetMailFull(BaseIntent):
    kind: Literal["get_mail_full"]
    msg_id: str
```

`BaseIntent` (all intents inherit from it):

```python
class BaseIntent(BaseModel):
    model_config = {"extra": "forbid"}
    confidence: float = Field(ge=0.0, le=1.0)
    raw_utterance: str
```

This file also maintains three places that must all agree on the full set of kinds, shown here
with their current content in full:

```python
_AnyIntent = Union[
    RememberFact, RecallMemory,
    Confirm,
    SystemStatus, CreateReminder, CheckReminders,
    Chat, Unknown, RunCommand,
    IngestDocument,
    WriteFile,
    ListMail,
    TrashMail,
    MarkMailRead,
    GetMailFull,
    ListCalendarEvents,
    CreateCalendarEvent,
    DeleteCalendarEvent,
    GhostwriterDraft,
    TriggerN8n,
    BrowserAction,
    AddEmailRule,
    WebSearch,
]
Intent = Annotated[_AnyIntent, Field(discriminator="kind")]

INTENT_KINDS = (
    "remember_fact",
    "recall_memory",
    "confirm",
    "system_status",
    "create_reminder",
    "check_reminders",
    "chat",
    "ingest_document",
    "write_file",
    "unknown",
    "run_command",
    "trigger_n8n",
    "list_mail",
    "trash_mail",
    "mark_mail_read",
    "get_mail_full",
    "list_calendar_events",
    "create_calendar_event",
    "delete_calendar_event",
    "ghostwriter",
    "browser_action",
    "add_email_rule",
    "web_search",
)

INTENT_MODELS: dict[str, type[BaseIntent]] = {
    "remember_fact": RememberFact,
    "recall_memory": RecallMemory,
    "confirm": Confirm,
    "system_status": SystemStatus,
    "create_reminder": CreateReminder,
    "check_reminders": CheckReminders,
    "chat": Chat,
    "ingest_document": IngestDocument,
    "write_file": WriteFile,
    "unknown": Unknown,
    "run_command": RunCommand,
    "trigger_n8n": TriggerN8n,
    "list_mail": ListMail,
    "trash_mail": TrashMail,
    "mark_mail_read": MarkMailRead,
    "get_mail_full": GetMailFull,
    "list_calendar_events": ListCalendarEvents,
    "create_calendar_event": CreateCalendarEvent,
    "delete_calendar_event": DeleteCalendarEvent,
    "ghostwriter": GhostwriterDraft,
    "browser_action": BrowserAction,
    "add_email_rule": AddEmailRule,
    "web_search": WebSearch,
}
```

Task:
1. Define the two new intent classes (`SummarizeMail` with `kind: Literal["summarize_mail"]`,
   `CreateGoogleTask` with `kind: Literal["create_google_task"]`), placed near `GetMailFull` since
   they're mail-related.
2. Add both to `_AnyIntent`'s `Union[...]`, to `INTENT_KINDS`, and to `INTENT_MODELS`, consistent
   with how every other kind already appears in all three places.

Reply with ONLY: the two new class definitions, plus the three corrected blocks (`_AnyIntent`/`Intent`,
`INTENT_KINDS`, `INTENT_MODELS`) in full, as python code block(s), no other text.
