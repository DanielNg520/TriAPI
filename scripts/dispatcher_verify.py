"""Verification helpers for the Tier 2 dispatcher.

Moved out of scripts/dispatcher.py verbatim -- these were never actually
defined in dispatcher.py, only imported/re-exported from their real homes
(scripts.tier4_worker.run_build, scripts.orchestrator.verify_task). This
file exists to give the import targets a stable home and to shrink
dispatcher.py back down.
"""

from scripts.orchestrator import verify_task
from scripts.tier4_worker import run_build

__all__ = ["run_build", "verify_task"]
