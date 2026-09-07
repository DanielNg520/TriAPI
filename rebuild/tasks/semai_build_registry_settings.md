Three worker constructions in this function were just changed to accept an optional `settings` parameter (`make_ingest_worker`, `FileWriteWorker`, `BrowserActionWorker`), matching the pattern already used a few lines below for `N8nWorker(settings)`, `ListMailWorker(settings)`, etc. This function already has `settings` in scope as its own parameter. Wire it through to those three.

Change exactly these three lines, nothing else in the function:
- `registry.register("ingest_document", make_ingest_worker())` → `registry.register("ingest_document", make_ingest_worker(settings))`
- `registry.register_approval_required("write_file", FileWriteWorker())` → `registry.register_approval_required("write_file", FileWriteWorker(settings))`
- `registry.register_approval_required("browser_action", BrowserActionWorker())` → `registry.register_approval_required("browser_action", BrowserActionWorker(settings))`

Reply with only those three corrected lines, each on its own line, in a single fenced code block. No other text, no surrounding context.
