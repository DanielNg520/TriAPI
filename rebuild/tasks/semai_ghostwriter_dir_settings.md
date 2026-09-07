Add exactly one new field to this file's `Settings` class and wire it into `Settings.load()`. Nothing else changes — no reordering, no reformatting, no touching any other field or line.

1. Add a new field anywhere in the field-declaration block (near `vault_path` makes sense, but exact position doesn't matter): `ghostwriter_dir: Path | None = None`.
2. In `load()`, add a new keyword argument to the `cls(...)` call: `ghostwriter_dir=Path(e["SEMAI_GHOSTWRITER_DIR"]).expanduser() if e.get("SEMAI_GHOSTWRITER_DIR") else (Path(e["OMLL_GHOSTWRITER_DIR"]).expanduser() if e.get("OMLL_GHOSTWRITER_DIR") else None),` — `SEMAI_GHOSTWRITER_DIR` takes priority, `OMLL_GHOSTWRITER_DIR` is a legacy fallback, unset env means the field stays `None` (this is load-bearing: `None` must mean "the caller decides its own default" for a later change, not get a default value here).

Reply with the complete corrected file content only, in a single fenced code block, verbatim except for this one addition in the two places named above.

```python
"""
semai.config.schema
─────────────────────
Phase 0 skeleton: Pydantic Settings that fails loudly at boot on bad
config. Deliberately NOT a full
port of ohmyllama/config.py's 956 lines — this is the pattern (validated
settings, explicit env resolution, no silent defaults for anything that
matters) seeded with what Phase 0 itself needs. Each module ported in
Phase 3 adds its own settings here as it migrates, rather than this file
trying to anticipate all of them up front.

No `pydantic-settings` dependency — env resolution is explicit via
`Settings.load()`, mirroring the existing `Config.load()` pattern in
ohmyllama/config.py rather than introducing a second way to configure the
same kind of thing. Keeps `semai.config` as light as `semai.core`.

SAFETY: defaults to its OWN state directory (`SEMAI_STATE_DIR`, default
`.state-semai/`), never `ohmyllama`'s live `.state/ohmyllama.sqlite3` — the
two packages coexist in this repo during the migration (D3) and must not
share mutable state before the migration actually ports the data.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from semai.core.errors import ConfigurationError

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class SettingsError(ConfigurationError):
    """Config failed validation at boot. Subclasses ConfigurationError
    directly (see semai.core.errors) so callers can catch either name."""


class Settings(BaseModel):
    agent_timeout_s: float = 180.0
    agent_max_steps: int = 6

    model_config = {"extra": "forbid", "frozen": True}

    environment: Literal["dev", "prod", "test"] = "dev"
    log_level: LogLevel = "INFO"
    log_json: bool = True

    state_dir: Path
    db_path: Path

    # Added Phase 1, alongside providers/ + parser/llm_parser.py — this is
    # the "each module adds its own settings as it ports" pattern from the
    # module docstring, not a speculative field added ahead of need.
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:4b-instruct"
    confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)

    # Added Phase 3 (2026-08-06), closing the gap where vector search was
    # never actually wired into reindex/recall_memory anywhere. Same
    # model ohmyllama's rag.py already uses — no reason to pick a
    # different one for the same box.
    embed_model: str = "nomic-embed-text"
    poll_interval_s: float = 2.0
    max_concurrent_tasks: int = Field(default=2, ge=1)
    shutdown_grace_s: float = 30.0

    # Added Phase 2, alongside memory/vault.py. Changed 2026-08-06: this
    # USED to default to None (no real Obsidian vault path assumed, since
    # requiring one meant installing Obsidian as an extra dependency).
    # Personalization now lives inside the repo itself
    # (personalization/ — profile/, writing-style/, rules/, plus whatever
    # semai.memory.vault writes at runtime: 10-Memory/, 00-System/), so
    # the app is self-contained by default — no separate vault app or
    # config step required. `personalization/` is gitignored (never
    # committed) and created on first write if it doesn't exist yet
    # (Vault.write_note() calls mkdir(parents=True)). Still overridable
    # via SEMAI_VAULT_PATH for anyone who wants a vault elsewhere.
    vault_path: Path = Field(default_factory=lambda: _REPO_ROOT / "personalization")
    n8n_webhook_url: str | None = None
    searxng_url: str | None = "http://127.0.0.1:8888"

    # Added fields for scheduling and orchestrator config
    stale_task_s: float = 600.0
    max_attempts: int = 3
    model_warm_s: float = 300.0
    memory_consolidate_s: float = 3600.0
    agent_enabled: bool = True
    model_keep_alive: str = "30m"
    telegram_push_enabled: bool = False
    watch_ticker: bool = False
    watch_products: bool = False

    # Telegram integration fields
    telegram_forum_chat_id: str | int | None = None
    telegram_bot_token: str | None = None
    telegram_allowed_chats: list[int] = Field(default_factory=list)
    telegram_poll_timeout_s: float = 60.0
    whisper_model: str = "base"



    @field_validator("state_dir")
    @classmethod
    def _state_dir_must_be_creatable(cls, v: Path) -> Path:
        v = v.expanduser()
        try:
            v.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise ValueError(f"state_dir {v} is not creatable/writable: {e}") from e
        return v

    @field_validator("ollama_base_url")
    @classmethod
    def _ollama_base_url_must_use_ipv4_loopback(cls, v: str) -> str:
        # localhost can resolve to ::1 while Ollama listens on 127.0.0.1;
        # normalize so a reachable IPv4 server isn't skipped via the wrong
        # address family (or a hardcoded localhost in SEMAI_OLLAMA_URL).
        return v.replace("://localhost:", "://127.0.0.1:")

    @classmethod
    def load(cls, env: Mapping[str, str] | None = None) -> Settings:
        """Explicit env resolution, mirroring ohmyllama.config.Config.load().
        Raises SettingsError (not a bare pydantic error) on failure, since
        this is meant to be a fatal, caught-once-at-boot condition."""
        e = env if env is not None else os.environ
        state_dir = Path(e.get("SEMAI_STATE_DIR", str(_REPO_ROOT / ".state-semai")))
        try:
            return cls(
                agent_timeout_s=float(e.get("SEMAI_AGENT_TIMEOUT_S", "180")),
                agent_max_steps=max(1, int(e.get("SEMAI_AGENT_MAX_STEPS", "6"))),
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
