"""Pre-flight checks before calling Tier 1 (Claude) or Tier 2 (Gemini).

Tier 1 and Tier 2 must never silently fall into pay-per-token billing when
the whole point of this pipeline is to conserve paid subscription quota.
These checks are hard stops (return "not ok", never proceed anyway) --
callers must skip the tier or fall through to the next one on refusal.
"""

import json
import os
import time
from pathlib import Path

from scripts.config_loader import load_tiers
from scripts.tri_logging import get_logger

log = get_logger("budget_guard")

GEMINI_USAGE_LOG = Path(__file__).resolve().parent.parent / "logs" / "gemini_usage.jsonl"

# Conservative defaults used only if tiers.yaml doesn't specify real
# verified limits yet. Google AI Studio free-tier RPM/RPD limits vary by
# model and change over time -- see the "unverified" note in tiers.yaml.
DEFAULT_FREE_TIER_RPM = 10
DEFAULT_FREE_TIER_RPD = 250


def check_tier1_ok() -> dict:
    """Refuses if ANTHROPIC_API_KEY is set -- its presence routes `claude -p`
    to metered API billing instead of the Pro/Max subscription."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        log.warning("Tier 1 refused: ANTHROPIC_API_KEY is set in the environment")
        return {
            "ok": False,
            "reason": "ANTHROPIC_API_KEY is set in the environment; this would route "
            "`claude -p` to metered API billing instead of the Pro/Max subscription. "
            "Unset it to use Tier 1 safely, or this call is skipped.",
        }
    log.debug("Tier 1 budget check passed (subscription auth)")
    return {"ok": True, "reason": "subscription auth (no ANTHROPIC_API_KEY set)"}


def _read_gemini_usage_window(window_seconds: float) -> int:
    if not GEMINI_USAGE_LOG.exists():
        return 0
    cutoff = time.time() - window_seconds
    count = 0
    with open(GEMINI_USAGE_LOG) as f:
        for line in f:
            entry = json.loads(line)
            if entry["timestamp"] >= cutoff:
                count += 1
    return count


def record_gemini_call(model: str | None = None) -> None:
    GEMINI_USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {"timestamp": time.time()}
    if model:
        entry["model"] = model
    with open(GEMINI_USAGE_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def check_tier2_ok() -> dict:
    """Refuses if the next Gemini API call would exceed the configured
    free-tier RPM/RPD limits. Does not proceed on refusal -- this is a hard
    stop, not a warning."""
    config = load_tiers()
    limits = config["tier_2_manager"].get("pricing", {})
    rpm_limit = limits.get("free_tier_rpm", DEFAULT_FREE_TIER_RPM)
    rpd_limit = limits.get("free_tier_rpd", DEFAULT_FREE_TIER_RPD)

    calls_last_minute = _read_gemini_usage_window(60)
    calls_last_day = _read_gemini_usage_window(86400)

    if calls_last_minute >= rpm_limit:
        log.warning("Tier 2 refused: RPM limit reached (%d/%d in last 60s)", calls_last_minute, rpm_limit)
        return {
            "ok": False,
            "reason": f"would exceed free-tier RPM limit ({calls_last_minute}/{rpm_limit} in the last 60s)",
        }
    if calls_last_day >= rpd_limit:
        log.warning("Tier 2 refused: RPD limit reached (%d/%d in last 24h)", calls_last_day, rpd_limit)
        return {
            "ok": False,
            "reason": f"would exceed free-tier RPD limit ({calls_last_day}/{rpd_limit} in the last 24h)",
        }
    log.debug("Tier 2 budget check passed (%d/%d rpm, %d/%d rpd)", calls_last_minute, rpm_limit, calls_last_day, rpd_limit)
    return {"ok": True, "reason": f"within free tier ({calls_last_minute}/{rpm_limit} rpm, {calls_last_day}/{rpd_limit} rpd)"}
