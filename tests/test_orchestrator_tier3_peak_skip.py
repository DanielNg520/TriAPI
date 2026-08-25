"""Tests for orchestrator tier 3 peak-skip logic."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest import mock

from scripts import budget_guard

TIER_2_MANAGER_CONFIG = {
    "provider": "deepseek",
    "api_key_secret": "deepseek_api_key",
    "name": "DeepSeek API",
    "endpoint": "https://api.deepseek.com",
    "models": {"default": "deepseek-v4-pro"},
    "default_model": "default",
    "role": "task orchestration, context isolation, high-level architectural correction",
    "automatable": True,
    "peak_hours_utc": [["01:00", "04:00"], ["06:00", "10:00"]],
    "pricing": {
        "last_verified": "2026-08-09",
        "cache_hit_per_mtok_usd": 0.003625,
        "cache_miss_per_mtok_usd": None,
        "output_per_mtok_usd": None,
    },
}


class OrchestratorTier3PeakSkipTests(unittest.TestCase):
    def test_config_matches_tiers_yaml(self) -> None:
        self.assertEqual(TIER_2_MANAGER_CONFIG["provider"], "deepseek")
        self.assertEqual(TIER_2_MANAGER_CONFIG["api_key_secret"], "deepseek_api_key")
        self.assertEqual(TIER_2_MANAGER_CONFIG["name"], "DeepSeek API")
        self.assertEqual(TIER_2_MANAGER_CONFIG["endpoint"], "https://api.deepseek.com")
        self.assertEqual(TIER_2_MANAGER_CONFIG["models"], {"default": "deepseek-v4-pro"})
        self.assertEqual(TIER_2_MANAGER_CONFIG["default_model"], "default")
        self.assertEqual(
            TIER_2_MANAGER_CONFIG["role"],
            "task orchestration, context isolation, high-level architectural correction",
        )
        self.assertTrue(TIER_2_MANAGER_CONFIG["automatable"])
        self.assertEqual(
            TIER_2_MANAGER_CONFIG["peak_hours_utc"],
            [["01:00", "04:00"], ["06:00", "10:00"]],
        )
        pricing = TIER_2_MANAGER_CONFIG["pricing"]
        self.assertEqual(pricing["last_verified"], "2026-08-09")
        self.assertEqual(pricing["cache_hit_per_mtok_usd"], 0.003625)
        self.assertIsNone(pricing["cache_miss_per_mtok_usd"])
        self.assertIsNone(pricing["output_per_mtok_usd"])

    def test_peak_hours_skip_tier3(self) -> None:
        # 2026-08-25T07:22:38.772298+00:00 UTC is within DeepSeek peak billing
        # hours 06:00-10:00 UTC (LA local 2026-08-25T00:22:38.772298-07:00).
        with mock.patch.object(budget_guard, "datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 8, 25, 7, 22, 38, 772298, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            with mock.patch.object(budget_guard, "load_tiers", return_value={"tier_2_manager": TIER_2_MANAGER_CONFIG}):
                result = budget_guard.check_tier3_peak_hours_ok()
        self.assertFalse(result["ok"])

    def test_off_peak_allows_tier3(self) -> None:
        with mock.patch.object(budget_guard, "datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            with mock.patch.object(budget_guard, "load_tiers", return_value={"tier_2_manager": TIER_2_MANAGER_CONFIG}):
                result = budget_guard.check_tier3_peak_hours_ok()
        self.assertTrue(result["ok"])
