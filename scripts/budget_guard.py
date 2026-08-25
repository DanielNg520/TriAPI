"""Pre-flight checks before calling Tier 1 (Claude) or Tier 2 (Gemini).

Tier 1 and Tier 2 must never silently fall into pay-per-token billing when
the whole point of this pipeline is to conserve paid subscription quota.
These checks are hard stops (return "not ok", never proceed anyway) --
callers must skip the tier or fall through to the next one on refusal.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.config_loader import load_tiers
from scripts.tri_logging import get_logger

log = get_logger("budget_guard")

GEMINI_USAGE_LOG = Path(__file__).resolve().parent.parent / "logs" / "gemini_usage.jsonl"

# Conservative defaults used only if tiers.yaml doesn't specify real
# verified limits yet. Google AI Studio free-tier RPM/RPD limits vary by
# model and change over time -- see the "unverified" note in tiers.yaml.
DEFAULT_FREE_TIER_RPM = 10
DEFAULT_FREE_TIER_RPD = 250

# DeepSeek V4 applies 2x pricing during these UTC windows (verified against
# America/Los_Angeles PDT/PST wall-clock; see check_tier3_peak_hours_ok).
# Used only when tier_3_debugger.peak_hours_utc is absent from tiers.yaml.
DEFAULT_TIER3_PEAK_HOURS_UTC = [
    ["01:00", "04:00"],
    ["06:00", "10:00"],
]

DEEPSEEK_ENDPOINT = "https://api.deepseek.com"
TIER_SCAN_ORDER = ["tier_1_planner", "tier_1_manager", "tier_2_manager", "tier_3_debugger", "tier_4_worker"]

LA_TZ = ZoneInfo("America/Los_Angeles")
BEIJING_TZ = ZoneInfo("Asia/Shanghai")

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


def check_tier1_manager_ok(config: dict) -> dict:
    """Refuses if tier_1_manager is disabled in config/tiers.yaml or if the
    TRIAPI_NO_TIER1 environment variable is set (manual kill switch)."""
    if os.environ.get("TRIAPI_NO_TIER1"):
        log.warning("Tier 1 manager refused: TRIAPI_NO_TIER1 is set in the environment")
        return {
            "ok": False,
            "reason": "TRIAPI_NO_TIER1 is set in the environment; Tier 1 manager is disabled.",
        }
    if not config.get("tier_1_manager", {}).get("enabled", True):
        log.warning("Tier 1 manager refused: disabled in config/tiers.yaml")
        return {
            "ok": False,
            "reason": "tier_1_manager is disabled in config/tiers.yaml",
        }
    log.debug("Tier 1 manager budget check passed")
    return {"ok": True, "reason": "tier_1_manager enabled and no kill switch set"}


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


def resolve_deepseek_tier(config: dict) -> str | None:
    """Return the first tier key in TIER_SCAN_ORDER whose block has
    provider == "deepseek" and endpoint matching DEEPSEEK_ENDPOINT, else None."""
    for tier_key in TIER_SCAN_ORDER:
        block = config.get(tier_key)
        if not block:
            continue
        if block.get("provider") == "deepseek" and block.get("endpoint") and str(block["endpoint"]).rstrip("/") == DEEPSEEK_ENDPOINT:
            return tier_key
    return None


def check_tier3_peak_hours_ok() -> dict:
    """Refuses if the current UTC time falls inside a DeepSeek peak-hour
    window (2x pricing). Peak windows are read from config/tiers.yaml and
    fall back to DEFAULT_TIER3_PEAK_HOURS_UTC when not configured."""
    now_utc = datetime.now(timezone.utc)
    now_beijing = now_utc.astimezone(BEIJING_TZ)
    if now_beijing.weekday() in (5, 6):
        log.debug("Tier 3 bypass: weekend off-peak rate in effect")
        return {"ok": True, "reason": "weekend off-peak rate in effect"}
    config = load_tiers()
    resolved = resolve_deepseek_tier(config)
    peak_windows = config[resolved].get("peak_hours_utc") if resolved else None
    if not peak_windows:
        peak_windows = list(DEFAULT_TIER3_PEAK_HOURS_UTC)

    now_la = now_utc.astimezone(LA_TZ)
    now_minutes = now_utc.hour * 60 + now_utc.minute

    for start, end in peak_windows:
        start_hh, start_mm = map(int, start.split(":"))
        end_hh, end_mm = map(int, end.split(":"))
        start_minutes = start_hh * 60 + start_mm
        end_minutes = end_hh * 60 + end_mm

        if start_minutes <= end_minutes:
            in_peak = start_minutes <= now_minutes <= end_minutes
        else:
            in_peak = now_minutes >= start_minutes or now_minutes <= end_minutes

        if in_peak:
            la_time = now_la.isoformat()
            utc_time = now_utc.isoformat()
            log.info(
                "Tier 3 refused: DeepSeek peak hours active (LA %s / UTC %s)",
                la_time,
                utc_time,
            )
            return {
                "ok": False,
                "reason": (
                    f"Tier 3 is in DeepSeek peak billing hours {start}-{end} UTC "
                    f"(LA local {la_time}, UTC {utc_time})"
                ),
            }

    log.debug("Tier 3 budget check passed (outside DeepSeek peak hours)")
    return {
        "ok": True,
        "reason": "outside DeepSeek peak billing hours "
        f"(LA local {now_la.isoformat()}, UTC {now_utc.isoformat()})",
    }


JULES_USAGE_LOG = Path(__file__).resolve().parent.parent / "logs" / "jules_usage.jsonl"

DEFAULT_JULES_DAILY_TASK_LIMIT = 15


def _read_jules_usage_window(window_seconds: float) -> int:
    if not JULES_USAGE_LOG.exists():
        return 0
    cutoff = time.time() - window_seconds
    count = 0
    with open(JULES_USAGE_LOG) as f:
        for line in f:
            entry = json.loads(line)
            if entry["timestamp"] >= cutoff:
                count += 1
    return count


def record_jules_call() -> None:
    JULES_USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {"timestamp": time.time()}
    with open(JULES_USAGE_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def check_jules_ok() -> dict:
    """Refuses if the next Jules task would exceed the configured daily task
    limit. Advisory-only elsewhere in the pipeline, but this check itself is
    a hard stop -- callers must not proceed on refusal."""
    config = load_tiers()
    limit = config.get("jules_tester", {}).get("daily_task_limit", DEFAULT_JULES_DAILY_TASK_LIMIT)

    tasks_last_day = _read_jules_usage_window(86400)

    if tasks_last_day >= limit:
        log.warning("Jules refused: daily task limit reached (%d/%d in last 24h)", tasks_last_day, limit)
        return {
            "ok": False,
            "reason": f"would exceed Jules daily task limit ({tasks_last_day}/{limit} in the last 24h)",
        }
    log.debug("Jules budget check passed (%d/%d tasks in last 24h)", tasks_last_day, limit)
    return {"ok": True, "reason": f"within daily task limit ({tasks_last_day}/{limit} in the last 24h)"}
