File: `/home/dyne/Documents/Coding/SemAI/src/semai/adapters/cli.py`

Two new workers exist in `src/semai/workers/mail.py` and need registering, same file/function as
the existing mail workers below (this function is `build_registry`, shown here with its current
mail-related lines and their existing import block):

```python
from semai.workers.mail import (
    AddEmailRuleWorker,
    GetMailFullWorker,
    ListMailWorker,
    MarkMailReadWorker,
    TrashMailWorker,
)
```

```python
    registry.register("list_mail", ListMailWorker(settings))
    registry.register_approval_required("trash_mail", TrashMailWorker(settings))
    registry.register("mark_mail_read", MarkMailReadWorker())
    registry.register("get_mail_full", GetMailFullWorker())
    registry.register_approval_required("add_email_rule", AddEmailRuleWorker(settings))
```

The two new workers: `SummarizeMailWorker(settings)` (takes `settings` in `__init__`, for
`kind="summarize_mail"`) and `CreateGoogleTaskWorker()` (no constructor args, for
`kind="create_google_task"`) -- both in `semai.workers.mail`, same module as the ones already
imported above.

Task: add both to the import block, and register both with `registry.register(...)` (neither needs
approval, same as `get_mail_full`/`mark_mail_read`/`list_mail` above -- they don't mutate anything
destructive) right after the existing `registry.register("get_mail_full", GetMailFullWorker())` line.

Reply with ONLY the corrected import block and the corrected registration lines (the 5-line block
shown above, now with 2 more lines added), as python code block(s), no other text.
