"""Centralized logging for TriAPI. On by default, toggleable via env vars.

    TRIAPI_LOG=0                disable logging entirely (default: enabled)
    TRIAPI_LOG_LEVEL=DEBUG|INFO|WARNING|ERROR   (default: INFO)
    TRIAPI_LOG_FILE=<path>      override the log file (default: logs/triapi.log)

Named tri_logging, not logging, so it doesn't shadow the stdlib module for
any file that does `import logging` alongside this.

Callers must never pass secret values to a logger -- this module has no way
to redact what it's given. Tail the file live with:
    tail -f logs/triapi.log
"""

import logging
import os
from pathlib import Path

_DEFAULT_LOG_FILE = Path(__file__).resolve().parent.parent / "logs" / "triapi.log"
_configured = False


def get_logger(name: str) -> logging.Logger:
    global _configured
    if not _configured:
        _configure_root()
        _configured = True
    return logging.getLogger(f"triapi.{name}")


def _configure_root() -> None:
    root = logging.getLogger("triapi")

    if os.environ.get("TRIAPI_LOG", "1") == "0":
        root.addHandler(logging.NullHandler())
        root.setLevel(logging.CRITICAL + 1)
        return

    level_name = os.environ.get("TRIAPI_LOG_LEVEL", "INFO").upper()
    root.setLevel(getattr(logging, level_name, logging.INFO))

    log_file = Path(os.environ.get("TRIAPI_LOG_FILE", str(_DEFAULT_LOG_FILE)))
    log_file.parent.mkdir(parents=True, exist_ok=True)

    handler = logging.FileHandler(log_file)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    root.addHandler(handler)
