Produce a Search/Replace block (old text, then new text, unified as two fenced code blocks labeled OLD and NEW) for the file `src/semai/core/intents.py` in the `semai` package. Reply with only the two blocks, no prose.

OLD (find this exact existing block):
```python
class GhostwriterDraft(BaseIntent):
    kind: Literal["ghostwriter"]
    prompt: str = Field(min_length=1)
    url: str = ""
    job_dir: str = ""


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
)
```

NEW (replace with, adding a `WebSearch` intent kind `"web_search"` with a single required `query: str = Field(min_length=1)` field, inserted in both the union and the tuple, keeping every other existing entry in the exact same order and unmodified):
```python
class GhostwriterDraft(BaseIntent):
    kind: Literal["ghostwriter"]
    prompt: str = Field(min_length=1)
    url: str = ""
    job_dir: str = ""


class WebSearch(BaseIntent):
    kind: Literal["web_search"]
    query: str = Field(min_length=1)


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
```

Also produce a second Search/Replace pair for the same file, for the `INTENT_MODELS` dict:

OLD:
```python
    "ghostwriter": GhostwriterDraft,
    "browser_action": BrowserAction,
    "add_email_rule": AddEmailRule,
}
```

NEW:
```python
    "ghostwriter": GhostwriterDraft,
    "browser_action": BrowserAction,
    "add_email_rule": AddEmailRule,
    "web_search": WebSearch,
}
```
