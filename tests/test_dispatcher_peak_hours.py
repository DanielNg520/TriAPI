"""Regression tests for dispatcher._is_deepseek_peak_hours() delegation."""

from __future__ import annotations

import unittest
from unittest import mock

from scripts import budget_guard, dispatcher


class IsDeepseekPeakHoursTests(unittest.TestCase):
    """Verify dispatcher._is_deepseek_peak_hours() delegates to
    budget_guard.check_tier3_peak_hours_ok() instead of hardcoding logic."""

    def test_weekend_case_returns_false(self) -> None:
        """When budget_guard says peak hours are OK (e.g. weekend),
        _is_deepseek_peak_hours() must return False."""
        with mock.patch.object(
            dispatcher,
            "check_tier3_peak_hours_ok",
            return_value={"ok": True},
        ) as mock_check:
            result = dispatcher._is_deepseek_peak_hours()

        self.assertFalse(result)
        mock_check.assert_called_once()

    def test_peak_window_case_returns_true(self) -> None:
        """When budget_guard says peak hours are NOT OK (e.g. peak window),
        _is_deepseek_peak_hours() must return True."""
        with mock.patch.object(
            dispatcher,
            "check_tier3_peak_hours_ok",
            return_value={"ok": False},
        ) as mock_check:
            result = dispatcher._is_deepseek_peak_hours()

        self.assertTrue(result)
        mock_check.assert_called_once()

    def test_mock_was_actually_called(self) -> None:
        """Assert the delegation mock was invoked (covers all branches)."""
        with mock.patch.object(
            dispatcher,
            "check_tier3_peak_hours_ok",
            return_value={"ok": True},
        ) as mock_check:
            dispatcher._is_deepseek_peak_hours()

        self.assertTrue(mock_check.called)
        self.assertEqual(mock_check.call_count, 1)


if __name__ == "__main__":
    unittest.main()
