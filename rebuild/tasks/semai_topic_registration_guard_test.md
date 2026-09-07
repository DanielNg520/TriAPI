Add a new test file `tests/test_topic_registration.py` to the SemAI project (pytest style, sync,
no async needed). Its job: catch the exact bug class that just happened — a `push.deliver()` call
site using a topic name that was never added to `TelegramAdapter._FORUM_TOPICS`, so that topic
silently falls back to the group's General chat instead of getting its own forum topic.

Write ONE function: `test_all_deliver_topic_names_are_registered()`.

It must:
1. Read the text of these two files (relative to the repo root, use `pathlib.Path(__file__).parent.parent`
   to find the root): `src/semai/adapters/daemon.py` and `src/semai/workers/watcher.py`.
2. Find every call to `deliver(` in that text and extract the topic-name string literal argument
   (the argument is always a double-quoted string, e.g. `"mail"`, and it is always the argument
   immediately after the `store` argument — it may be on its own line). Use a regex like
   `deliver\(\s*[^,]+,\s*store\s*,\s*"([^"]+)"` applied with `re.DOTALL` and `re.findall`, since
   some calls span multiple lines with `self.settings,\n store,\n "name",` and others are single-line
   `self.settings, store, "name",`.
3. Import `TelegramAdapter` from `semai.adapters.telegram` and read `TelegramAdapter._FORUM_TOPICS`.
4. Assert every extracted topic name is present in `_FORUM_TOPICS` (use a plain `assert`, with a
   message listing which names are missing, e.g.
   `assert missing == set(), f"deliver() topic names not in _FORUM_TOPICS: {missing}"`).
5. Also assert the extracted-names list is non-empty (so a future refactor that changes the calling
   convention and silently breaks the regex is caught too, not swallowed as "no names found = pass").

Reply with the complete content of `tests/test_topic_registration.py`, nothing else.
