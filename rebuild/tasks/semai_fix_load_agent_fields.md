Fix a bug in this exact function. `agent_timeout_s` and `agent_max_steps` are computed on their own lines but never passed as arguments into the `cls(...)` call below them — they're a discarded tuple expression, so `SEMAI_AGENT_TIMEOUT_S` and `SEMAI_AGENT_MAX_STEPS` are silently ignored and the class defaults always apply instead.

Fix: pass `agent_timeout_s=...` and `agent_max_steps=...` as keyword arguments into the `cls(...)` call, using the same expressions already computed. Remove the two now-orphaned standalone lines. Do not change anything else — no other field, no reordering, no reformatting of unrelated lines, no comments added.

Reply with the complete corrected `load` classmethod only, verbatim except for this fix, in a single fenced code block.

```python
    @classmethod
    def load(cls, env: Mapping[str, str] | None = None) -> Settings:
        """Explicit env resolution, mirroring ohmyllama.config.Config.load().
        Raises SettingsError (not a bare pydantic error) on failure, since
        this is meant to be a fatal, caught-once-at-boot condition."""
        e = env if env is not None else os.environ
        state_dir = Path(e.get("SEMAI_STATE_DIR", str(_REPO_ROOT / ".state-semai")))
        try:
            agent_timeout_s=float(e.get("SEMAI_AGENT_TIMEOUT_S", "180")),
            agent_max_steps=max(1, int(e.get("SEMAI_AGENT_MAX_STEPS", "6"))),

            return cls(
                environment=e.get("SEMAI_ENV", "dev"),  # type: ignore[arg-type]
                log_level=e.get("SEMAI_LOG_LEVEL", "INFO"),  # type: ignore[arg-type]
                log_json=e.get("SEMAI_LOG_JSON", "1") not in ("0", "false", "False", "no"),
                state_dir=state_dir,
                db_path=state_dir / "semai.sqlite3",
                ollama_base_url=e.get("SEMAI_OLLAMA_URL") or "http://127.0.0.1:11434",
                ollama_model=e.get("SEMAI_OLLAMA_MODEL", "qwen3:4b-instruct"),
                confidence_threshold=float(e.get("SEMAI_CONFIDENCE_THRESHOLD", "0.5")),
    poll_interval_s=float(e.get("SEMAI_POLL_S", "2")),
    max_concurrent_tasks=int(e.get("SEMAI_MAX_CONCURRENT_TASKS","2")),
    shutdown_grace_s=float(e.get("SEMAI_SHUTDOWN_GRACE_S", "30")),
                embed_model=e.get("SEMAI_EMBED_MODEL", "nomic-embed-text"),
                vault_path=Path(e["SEMAI_VAULT_PATH"]) if e.get("SEMAI_VAULT_PATH")
                        else _REPO_ROOT / "personalization",
                n8n_webhook_url=e.get("N8N_WEBHOOK_URL") or None,
                searxng_url=e.get("SEARXNG_URL") or "http://127.0.0.1:8888",

                # added for scheduling and orchestrator config
                stale_task_s=float(e.get("SEMAI_STALE_TASK_S", "600")),
                max_attempts=int(e.get("SEMAI_MAX_ATTEMPTS", "3")),
                model_warm_s=float(e.get("SEMAI_MODEL_WARM_S", "300")),
                memory_consolidate_s=float(e.get("SEMAI_MEMORY_CONSOLIDATE_S", "3600")),
                agent_enabled=e.get("SEMAI_AGENT_ENABLED", "True").lower() in ("true", "yes", "1"),
                model_keep_alive=e.get("SEMAI_MODEL_KEEP_ALIVE", "30m"),
                telegram_push_enabled=e.get("SEMAI_TELEGRAM_PUSH_ENABLED", "False").lower() in ("true", "yes", "1"),
                watch_ticker=e.get("SEMAI_WATCH_TICKER", "False").lower() in ("true", "yes", "1"),
                watch_products=e.get("SEMAI_WATCH_PRODUCTS", "False").lower() in ("true", "yes", "1"),

                # Telegram adapter fields
                telegram_forum_chat_id=e.get("TELEGRAM_FORUM_CHAT_ID") or None,
                telegram_bot_token=e.get("TELEGRAM_BOT_TOKEN") or None,
                telegram_allowed_chats=[
                    int(chat_id.strip()) for chat_id in e.get("TELEGRAM_ALLOWED_CHAT_IDS", "").split(",")
                    if chat_id.strip()
                ],
                telegram_poll_timeout_s=float(e.get("SEMAI_TELEGRAM_POLL_TIMEOUT_S", "60")),
                whisper_model=e.get("WHISPER_MODEL", "base"),

            )
        except Exception as ex:  # pydantic.ValidationError or the validator's ValueError
            raise SettingsError(f"invalid SemAI configuration: {ex}") from ex
```
