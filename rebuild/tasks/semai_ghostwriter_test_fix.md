`canonical_workspace()` (in `semai/workers/ghostwriter.py`) no longer reads `OMLL_GHOSTWRITER_DIR` from the environment — it now reads `settings.ghostwriter_dir` directly. This test's fake `Settings` stub (a plain class, not the real pydantic `Settings`) relies on the old env-var behavior and now fails with `AttributeError: 'Settings' object has no attribute 'ghostwriter_dir'`.

Fix, in this exact function, changing only what's needed:
1. Delete the stale comment block above `workspace = Path(tmpdir) / "workspace"` that describes the old env-var behavior (the 4 lines starting `# canonical_workspace() prefers OMLL_GHOSTWRITER_DIR...`), and replace it with a short comment noting the fake `Settings` sets `ghostwriter_dir` directly for a hermetic corpus dir.
2. Delete the two lines `original_ghostwriter_dir = os.environ.get(...)` and `os.environ["OMLL_GHOSTWRITER_DIR"] = str(workspace)` — no longer needed.
3. Add `ghostwriter_dir = workspace` as a class attribute on the fake `Settings` class, alongside the existing `state_dir = Path(tmpdir) / "state"`.
4. In the `finally` block, delete the 4 lines that restore `OMLL_GHOSTWRITER_DIR` (the `if original_ghostwriter_dir is None: ... else: ...` block) — no longer needed. Keep `ghostwriter.client_for = original_client_for`.
5. If `import os` becomes unused elsewhere in the file after this, remove it; otherwise keep it (check the rest of the file for other `os.` usage first).

Reply with only the corrected `run_all_assertions` function in a single fenced code block, plus, on a second line before the code block starts, either the word `KEEP_OS_IMPORT` or `REMOVE_OS_IMPORT` depending on your check in step 5.

```python
def run_all_assertions():
    calls = []

    class FakeLLM:
        def chat(self, model, prompt_text, *, system=None, **kwargs) -> str:
            calls.append(prompt_text)
            return "mocked generation result"
        def ping(self):
            return ["fake-model"]

    original_client_for = ghostwriter.client_for
    ghostwriter.client_for = lambda settings: FakeLLM()

    with tempfile.TemporaryDirectory() as tmpdir:
        # canonical_workspace() prefers OMLL_GHOSTWRITER_DIR over settings.vault_path
        # -- this machine has that env var set globally to a real production path
        # that doesn't exist here, so the test must override it with its own
        # hermetic corpus dir rather than depending on ambient environment state.
        workspace = Path(tmpdir) / "workspace"
        sample_dir = workspace / "sample"
        sample_dir.mkdir(parents=True)
        (sample_dir / "Writing_Style_Guide.md").write_text(
            "terse, dry, second person\n", encoding="utf-8"
        )
        (sample_dir / "casual.txt").write_text(
            "sample casual writing about coffee mornings.\n", encoding="utf-8"
        )

        original_ghostwriter_dir = os.environ.get("OMLL_GHOSTWRITER_DIR")
        os.environ["OMLL_GHOSTWRITER_DIR"] = str(workspace)

        class Settings:
            state_dir = Path(tmpdir) / "state"

        settings = Settings()
        worker = ghostwriter.GhostwriterWorker(settings)

        intent = GhostwriterDraft(
            kind="ghostwriter",
            confidence=1.0,
            raw_utterance="write a poem about rain",
            prompt="write a poem about rain"
        )

        try:
            # 1. worker.execute(intent) returns Result(ok=True) containing the mocked draft text
            result = worker.execute(intent)
            assert result.ok, f"Expected ok=True, got: {result.message}"
            assert result.message == "mocked generation result", (
                f"Unexpected result message: {result.message!r}"
            )
            # run_prompt makes two LLM calls: [0] builds the style profile from the
            # sample corpus, [1] is the actual draft call, which embeds the intent's
            # prompt text inside its "Instruction:\n..." user message (not verbatim-
            # equal to intent.prompt).
            assert len(calls) == 2, f"Expected 2 LLM calls (style + draft), got {len(calls)}: {calls!r}"
            assert intent.prompt in calls[-1], (
                f"Draft call did not include the intent prompt: {calls[-1]!r}"
            )

            # 2. worker.execute(intent) returns Result(ok=False) with an informative message when the mocked client's .chat() raises
            class ErrorFakeLLM:
                def chat(self, model, prompt_text, *, system=None, **kwargs) -> str:
                    raise RuntimeError("LLM failed")
                def ping(self):
                    return ["fake-model"]

            ghostwriter.client_for = lambda settings: ErrorFakeLLM()
            result_fail = worker.execute(intent)
            assert not result_fail.ok, "Expected ok=False when client.chat raises"
            assert "LLM failed" in result_fail.message or "RuntimeError" in result_fail.message, (
                f"Unexpected error message: {result_fail.message!r}"
            )

            # 3. worker(intent) (the __call__ path used by the registry) also returns Result(ok=True) for the same intent
            ghostwriter.client_for = lambda settings: FakeLLM()
            calls.clear()
            result_call = worker(intent)
            assert result_call.ok, f"Expected ok=True from __call__, got: {result_call.message}"
            assert result_call.message == "mocked generation result", (
                f"Unexpected result message from __call__: {result_call.message!r}"
            )

        finally:
            ghostwriter.client_for = original_client_for
            if original_ghostwriter_dir is None:
                os.environ.pop("OMLL_GHOSTWRITER_DIR", None)
            else:
                os.environ["OMLL_GHOSTWRITER_DIR"] = original_ghostwriter_dir

    print("All tests passed successfully!")
```

For step 5's check, here is the full list of lines matching `os\.` in the whole file outside this function: none (this function is the only place `os` is used in the file).
