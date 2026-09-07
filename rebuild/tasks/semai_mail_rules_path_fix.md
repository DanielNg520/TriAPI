In `src/semai/workers/mail.py`, `AddEmailRuleWorker.execute()` writes new rules to `.state-semai/EmailRules.md`,
but the live `MailWatcher` (wired in `daemon.py` with `rules_path="10-Memory/Rules/EmailRules.md"`) and the
Telegram `/rule` command both read from `10-Memory/Rules/EmailRules.md`. Different files — rules added via
chat never take effect. Fix: write to the same path the readers use.

Here is the current method, verbatim:

```python
    def execute(self, action: ProposedAction) -> Result:
        rule_text = action.payload.get("rule_text")
        if not rule_text:
            return Result(ok=False, message="No rule_text in action payload")

        import pathlib
        try:
            pathlib.Path(".state-semai").mkdir(parents=True, exist_ok=True)
            with open(".state-semai/EmailRules.md", "a") as f:
                f.write(rule_text + "\n")
        except Exception as exc:
            return Result(ok=False, message=str(exc))
        return Result(ok=True, message="Rule added successfully.")
```

Change ONLY the two path strings: `.state-semai` -> `10-Memory/Rules` (the mkdir target) and
`.state-semai/EmailRules.md` -> `10-Memory/Rules/EmailRules.md` (the open target). Nothing else in the
method changes — same signature, same control flow, same error handling.

Reply with the complete corrected method only, in a single fenced python block, no other text.
