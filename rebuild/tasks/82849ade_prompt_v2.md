Repo: SemAI. File: `src/semai/adapters/daemon.py`, class `AsyncDaemon`.

Three small SEARCH/REPLACE edits. For each, the SEARCH block is copied verbatim from the file
right now. Reproduce it exactly, character for character, then give the REPLACE block. Do not
add ellipsis (`...`), do not invent a different signature, do not summarize — reproduce the
SEARCH text exactly as given.

### Edit 1

SEARCH:
```
        self._stop = False
        self._inflight: set[asyncio.Task] = set()
```

REPLACE: same two lines, plus one new line adding `self._stop_event = asyncio.Event()` right
after `self._stop = False`.

### Edit 2

SEARCH:
```
    def _handle_signal(self, *_: object) -> None:
        self._stop = True
```

REPLACE: same, plus one new line `self._stop_event.set()` after `self._stop = True`.

### Edit 3

SEARCH:
```
        try:
            while not self._stop:
                await self._slots.acquire()
                if self._stop:
                    self._slots.release()
                    break
                task = store.claim_next()
```

REPLACE: same overall shape (still ends with `task = store.claim_next()`, still inside the same
`try:` / `while not self._stop:`), but the `await self._slots.acquire()` line must no longer be
a plain blocking await — it must race against `self._stop_event` so shutdown is noticed even
when every slot is held. Use `asyncio.wait({...}, return_when=asyncio.FIRST_COMPLETED)` over an
`asyncio.ensure_future(self._slots.acquire())` task and an `asyncio.ensure_future(self._stop_event.wait())`
task. Cancel whichever task did not complete. If the stop event won the race, break out of the
while loop (do not call `store.claim_next()` in that pass). If the acquire won the race, keep the
existing check-and-release-and-break-if-stopped logic, then proceed to `task = store.claim_next()`
as before.

Output format: three fenced code blocks, one per edit, each containing ONLY that edit's full
REPLACE text (no SEARCH text, no explanation, no other lines of the file).
