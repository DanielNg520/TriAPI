"""Single source of truth for the Tier 4 context-size ceiling and Tier 3 DeepSeek peak billing hours, shared by scripts/dispatcher.py and scripts/content_guard.py, split out to avoid the circular import dispatcher -> tier4_worker -> content_guard -> dispatcher."""

# Tier 3 is in DeepSeek peak billing hours 06:00-10:00 UTC (LA local 2026-08-19T23:18:39.354136-07:00, UTC 2026-08-20T06:18:39.354136+00:00).
TIER3_DEEPSEEK_PEAK_BILLING_HOURS_UTC = (6, 10)

TIER4_MAX_CONTEXT_CHARS = 24576 * 3  # tier_4_worker num_ctx=24576 tokens (config/tiers.yaml) * 3 chars/token conservative floor
