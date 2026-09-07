Repo: SemAI. File: `src/semai/adapters/daemon.py`. Class: `AsyncDaemon`.

Bug: the daemon hangs on shutdown. `run()`'s main loop blocks on `await self._slots.acquire()`
with no timeout. `_handle_signal()` only flips a bool (`self._stop = True`) that the loop can't
observe until `acquire()` returns — so if every concurrency slot is held (e.g. by a stuck
in-flight task), SIGTERM/SIGINT are silently swallowed and systemd eventually SIGABRTs the
process.

Current exact code, verbatim:

`__init__` (relevant line only):
```python
        self._stop = False
```

`_handle_signal`, in full:
```python
    def _handle_signal(self, *_: object) -> None:
        self._stop = True
```

`run()`'s loop header, in full:
```python
        try:
            while not self._stop:
                await self._slots.acquire()
                if self._stop:
                    self._slots.release()
                    break
                task = store.claim_next()
```

Required fix, three edits:

1. In `__init__`, add an `asyncio.Event` alongside `self._stop` (name it `self._stop_event`),
   so waiters can be woken immediately on shutdown instead of only polling a bool.
2. In `_handle_signal`, set that event in addition to the existing bool.
3. In `run()`'s loop, make the semaphore acquire race against that event (e.g. via
   `asyncio.wait(..., return_when=asyncio.FIRST_COMPLETED)` over the acquire and an
   `event.wait()`), so shutdown is noticed even while every slot is held. Cancel
   whichever side loses the race. If the acquire happened to win the race anyway
   right as shutdown was requested, release the slot back before breaking out of the
   loop so no permit leaks. Preserve the existing behavior below this block (the
   `task = store.claim_next()` line and everything after it) completely unchanged.

Reply with only the full, updated `__init__`, `_handle_signal`, and `run` method bodies
(three code blocks, one per method, each starting from the `def`/`async def` line), nothing
else. Do not modify or include any other method.
