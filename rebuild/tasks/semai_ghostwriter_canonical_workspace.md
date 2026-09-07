Change exactly this function. It already receives a `settings: Settings` argument. Replace its direct `os.environ.get("OMLL_GHOSTWRITER_DIR")` read with `settings.ghostwriter_dir` (a `Path | None` field that already resolves both `SEMAI_GHOSTWRITER_DIR` and legacy `OMLL_GHOSTWRITER_DIR` at config-load time, expanded). The three-way precedence (explicit path argument > ghostwriter dir setting > vault_path fallback > repo-relative fallback) must stay identical — only the source of the middle tier changes from a live env read to the already-resolved settings field. Since `settings.ghostwriter_dir` is already an expanded `Path` when set, do not call `.expanduser()`/`.resolve()` on it again beyond what's needed for consistency with the other branches (`.resolve()` is fine, `.expanduser()` is a no-op on an already-expanded path so it's fine to keep for consistency, but not required).

Do not change any other function in this file, and do not remove the `os` import if anything else in the file still needs it (check before removing).

Reply with only the corrected function in a single fenced code block.

```python
def canonical_workspace(settings: Settings, path: Path | str | None = None) -> Path:
    """Return the resolved canonical path for a workspace.

    Explicit ``path`` wins; otherwise ``OMLL_GHOSTWRITER_DIR``; otherwise
    ``settings.vault_path / 'ghostwriter'``.
    """
    if path is not None:
        return Path(path).expanduser().resolve()
    env_dir = os.environ.get("OMLL_GHOSTWRITER_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    vault_path = getattr(settings, "vault_path", None)
    if vault_path:
        return (Path(vault_path) / "ghostwriter").expanduser().resolve()
    return (
        Path(__file__).resolve().parents[3] / "personalization" / "ghostwriter"
    ).expanduser().resolve()
```
